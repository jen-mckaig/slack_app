"""
Uses the connectors to send Slack notifications to users
when their request is marked complete or launched. 
"""

import logging
from datetime import datetime, timedelta
from typing import NamedTuple

from scripts.background.meta_process import MetaProcess
from scripts.common.constants import DateTimeFormats
from scripts.common.notion import NotionConnector
from scripts.common.s3 import S3BucketConnector
from scripts.common.slack import SlackConnector


class CompletedTicketNotifier:
    """
    Class for sending Slack users ticket completion notifications.

    :param: notion ->  NotionConnector to get ticket data
    :param: slack ->  SlackConnector to send user notifications
    :param: slack_channel -> team slack channel id
    :param: s3 -> S3BucketConnector and bucket for the meta & notification log files
    :param: file_config -> NamedTuple class containing csv file headers
    """

    def __init__(
        self,
        notion: NotionConnector,
        slack: SlackConnector,
        slack_channel: str,
        s3: S3BucketConnector,
    ):
        self._logger = logging.getLogger(__name__)
        self.notion = notion
        self.slack = slack
        self.slack_channel = slack_channel
        self.s3 = s3

    def get_completed_tickets(self) -> list:
        """
        Pulling latest completed tickets and filtering records that do
        not have notifications logged.
        """

        today = datetime.today().date()
        week_ago = today - timedelta(days=7)

        # parse notion args
        ticket_status = self.notion.notion_args.notion_page_status["text"]
        completed_labels = self.notion.notion_args.notion_page_completion_labels["text"]
        ticket_id = self.notion.notion_args.notion_page_ticket_id["text"]

        # generate new metafile
        current_meta_file = MetaProcess.generate_meta_file(self.notion)

        # check the status of each ticket and filter to just those marked completed
        completed_tickets = [
            dct
            for dct in current_meta_file
            if dct[self.notion.notion_args.notion_page_status["text"]]
            in completed_labels
        ]
        self._logger.info(
            f"Generated new metafile containing {len(completed_tickets)} completed tickets."
        )
        # check that the completed tickets were not marked as completed previously
        filtered_tickets = self.__filter_records_marked_completed_not_notified(
            completed_tickets
        )
        # check the notification log to ensure that these ticket ids are not marked as notified
        to_notify = self.__check_notifications_log(filtered_tickets)
        return to_notify

    def __filter_records_marked_completed_not_notified(self, completed_tickets) -> list:
        """
        Accessing the most recent metafile and filtering out
        tickets that were already marked as completed.
        :param: completed_tickets -> a list of dictionaries from Notion that are marked as completed
        returns:
            list: a list of records that are newly marked as completed
        """

        try:
            last_meta_file, last_metafile_name = self.s3.get_most_recent_modified_file(
                "data_tickets"
            )
            self._logger.info(f"Retrieved last metafile ->{last_metafile_name}")
        except Exception as e:
            self._logger.debug(f"The last metafile cannot be accessed: {e}")
        # get ticket id for tickets marked completed in the previous metafile
        previously_completed_tickets = [
            dct[self.notion.notion_args.notion_page_ticket_id["text"]]
            for dct in last_meta_file
            if dct[self.notion.notion_args.notion_page_status["text"]]
            in self.notion.notion_args.notion_page_completion_labels["text"]
        ]
        self._logger.info(
            f"{len(previously_completed_tickets)} previously completed tickets retrieved"
        )
        # get any tickets that were not yet marked completed in the previous metafile
        recent_tickets = [
            dct
            for dct in completed_tickets
            if dct[self.notion.notion_args.notion_page_ticket_id["text"]]
            not in previously_completed_tickets
        ]
        self._logger.info(
            f"{len(recent_tickets)} tickets were just marked as completed"
        )
        return recent_tickets

    def __check_notifications_log(self, ticket_data: list) -> list:
        """
        Accessing the most recent notifications log and filtering out
        tickets that have successful notifications logged.

        :param tickets: a list of dictionaries each containing a completed ticket data.
        returns:
            a filtered list of records that contain tickets that require completion
            notifications

        """

        try:
            self.notif_log, file_name = self.s3.get_most_recent_modified_file(
                "notifications"
            )
            self._logger.info(f"Retrieved last notification log - {file_name}")

        except Exception as e:
            self._logger.debug(f"The latest notification log cannot be accessed :{e}")
            return ticket_data

        # get the ticket ids of ticket owners that were successfully notified
        notified = [
            ticket["ticket_id"]
            for ticket in self.notif_log
            if ticket["notification_status"] == "success"
        ]
        # filter out any tickets that were already successfully notified
        ticket_id = self.notion.notion_args.notion_page_ticket_id["text"]
        need_notifications = [
            item for item in ticket_data if item[ticket_id] not in notified
        ]
        self._logger.info(f"Number of notifications to send: {len(need_notifications)}")
        return need_notifications

    def send_notifications(self, meta_data: list) -> list:
        """
        Sending notifications to Slack users and to a Team channel.

        :param ticket_data: List of dictionaries each containing ticket data.
        returns:
            a list of records containing notification log data
        """
        notifications_log = []
        for rec in meta_data:
            # reference metafile keys to get values and use in a customized message
            request_title = rec[self.notion.notion_args.notion_page_title["text"]]
            created_at = rec[self.notion.notion_args.notion_page_created_at["text"]]
            created_date = (
                datetime.strptime(created_at, DateTimeFormats.datetime_format.value)
                .date()
                .strftime(DateTimeFormats.date_format.value)
            )
            deadline = rec[self.notion.notion_args.notion_page_due_date["text"]]
            url = rec[self.notion.notion_args.notion_page_page_url["text"]]
            user_id = rec[self.notion.notion_args.notion_page_slack_id["text"]]

            # custome message for the ticket owner
            msg_to_user = f"""
            *Your Data Ticket is complete!*  :rocket: \n
            *Ticket*: {request_title} \n
            *Created on*: {created_date} \n
            *Due Date*: {deadline} \n
            <{url}|:point_right: Review here.>
            """
            # custome message for the team
            msg_to_team = f"""
            *<@{user_id}>'s Ticket is complete!* :rocket: \n
            *Ticket*: {request_title} \n
            *Created on*: {created_date} \n
            *Due Date*: {deadline} \n
            <{url}|:point_right: Review here.>
                    """
            now = datetime.now().strftime(DateTimeFormats.datetime_format.value)
            notification_record = {}
            try:
                self.slack.post_message(user_id, msg_to_user)
                self.slack.post_message(self.slack_channel, msg_to_team)
                notification_record["notification_status"] = "success"
            except Exception as e:
                notification_record["notification_status"] = "failed"
                self._logger.info(f"Failed Notification - {e}")
            notification_record["notified_at"] = now
            notification_record["ticket_id"] = rec[
                self.notion.notion_args.notion_page_ticket_id["text"]
            ]
            notifications_log.append(notification_record)
        return notifications_log

    def log_notifications(self, prefix: str, data: list) -> None:
        """
        Uploading the notifications log to the target S3 bucket.

        :param prefix: S3 bucket directory
        :param data: a list of dictionaries containing notification logs
        """
        today = datetime.now().strftime(DateTimeFormats.date_file_name_format.value)
        today_file_name = f"{prefix}/{today}.csv"
        # the previous notification log should have been retrieved in a prior method
        if self.notif_log:
            data = data + self.notif_log
        else:
            self._logger.debug(f"The most recent notification log was not retrieved")

        self.s3.write_to_s3(data, today_file_name)

    def notify(self) -> None:
        """
        Get new contacts, send notifications, and log notification status to notify.
        """
        contacts = self.get_completed_tickets()
        if contacts:
            log = self.send_notifications(contacts)
            self.log_notifications("notifications", log)
        else:
            self._logger.info("No newly completed tickets at this time")
