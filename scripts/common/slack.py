"""Connector and methods accessing Slack"""
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import NamedTuple, Tuple

from flatten_json import flatten
from slack_bolt import App
from slack_sdk.errors import SlackApiError

from scripts.common.constants import DateTimeFormats


class SlackSourceConfig(NamedTuple):
    """
    Class for Slack payload configuration data
    """

    min_days_until_due: int
    form_title_text: str
    form_greeting_text: str
    form_input_one_text: str
    form_input_three_text: str
    form_input_four_text: str
    form_input_five_text: str
    request_categories: dict
    slack_json_keys: dict


class SlackConnector:
    """
    Class for interacting with Slack APIs
    """

    def __init__(
        self, bot_token: str, signing_secret: str, slack_args: SlackSourceConfig
    ):
        """
        Constructor for SlackConnector

        :param bot_token: bot token to access Slack API
        :param signing_secret: secret key for accessing Slack API
        :parm app_token: app level token used in socket mode
        :param slack_args: NamedTuple class with Slack configuration data

        """
        self._logger = logging.getLogger(__name__)
        self.bot_token = bot_token
        self._slack_app = App(
            token=os.environ[self.bot_token], signing_secret=os.environ[signing_secret]
        )
        self.slack_args = slack_args

    def build_form_view(self) -> dict:
        """
        Constructs the form layout using Slack block kit UI framework.
        returns:
            dict: contains form content and modal blocks
        """

        # Create a timestamp to set a deadline no sooner than x days from today.
        min_due_date = (
            datetime.today().date() + timedelta(days=self.slack_args.min_days_until_due)
        ).strftime(DateTimeFormats.date_format.value)

        # format the request categories for a drop down menu
        category_names = list(self.slack_args.request_categories.keys())
        request_categories = [
            {
                "text": {
                    "type": "plain_text",
                    "text": self.slack_args.request_categories[cat],
                },
                "value": cat,
            }
            for cat in category_names
        ]

        form_view = {
            "type": "modal",
            "callback_id": "form_1",
            "title": {"type": "plain_text", "text": self.slack_args.form_title_text},
            "submit": {"type": "plain_text", "text": "Submit"},
            "close": {"type": "plain_text", "text": "Close"},
            "blocks": [
                # Block 1 - Greeting
                {
                    "type": "section",
                    "block_id": "greeting",
                    "text": {
                        "type": "mrkdwn",
                        "text": self.slack_args.form_greeting_text,
                    },
                },
                # Block 2 - Paragraph text input
                {
                    "type": "input",
                    "block_id": "input_one",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "title",
                        "placeholder": {
                            "type": "plain_text",
                            "text": self.slack_args.form_input_one_text,
                        },
                    },
                    "label": {"type": "plain_text", "text": "Request Title"},
                },
                # Block 3 - Request category drop down menu
                {
                    "type": "section",
                    "block_id": "input_two",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*What type of request is this?*",
                    },
                    "accessory": {
                        "action_id": "request_type",
                        "type": "multi_static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Choose one or more.",
                        },
                        "options": request_categories,
                    },
                },
                # Block 4 - URL input
                {
                    "type": "input",
                    "block_id": "input_three",
                    "optional": True,
                    "element": {
                        "type": "url_text_input",
                        "action_id": "important_links",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": self.slack_args.form_input_three_text,
                    },
                },
                # Block 5 - Paragraph Text with minimum character rule
                {
                    "type": "input",
                    "block_id": "input_four",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "request_details",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": self.slack_args.form_input_four_text,
                        },
                        "min_length": 10,
                    },
                    "label": {"type": "plain_text", "text": "Request details"},
                },
                # Block 6 - Due Date Calendar
                {
                    "type": "section",
                    "block_id": "input_five",
                    "text": {
                        "type": "mrkdwn",
                        "text": self.slack_args.form_input_five_text,
                    },
                    "accessory": {
                        "type": "datepicker",
                        "action_id": "duedate",
                        "initial_date": min_due_date,
                        "placeholder": {"type": "plain_text", "text": "Select a date"},
                    },
                },
            ],
        }

        return form_view

    def open_form_view(self, trigger_id: str, form_view: dict) -> None:
        """
        Opens the form as a pop up in the channel where the slash command was used and
        returns the status of the event.

        :param trigger_id: id that is generated by Slack when slash command is used
        :param form_view: the slack form content & modal blocks
        """

        try:
            result = self._slack_app.client.views_open(
                trigger_id=trigger_id, view=form_view
            )
            self._logger.info(
                f"Slash command triggered. Status code {result.status_code}"
            )

        except SlackApiError as e:
            self._logger.info(f"An API error has occured - {e.response}")

    def get_submitted_data(self, submission_body: dict) -> Tuple[str, dict]:
        """
        Parses the data submitted to Slack and returns a dictionary.

        :param submission_body: a json payload coming from the Slack API
        returns:
            str: the slack user id of the person submitting form response
            dict: a dict of the submitted responses

        """

        slack_json = self.slack_args.slack_json_keys
        slack_keys = list(slack_json.keys())
        data = flatten(submission_body)

        lookup = {}
        for key in slack_keys:
            json_value = slack_json[key]["json"]
            text_value = slack_json[key]["text"]
            if not isinstance(json_value, list):
                lookup[json_value] = text_value
            else:
                lookup = {**lookup, **{item: text_value for item in json_value}}

        submission_keys = [k for k in data.keys() if k in lookup.keys()]

        submission_dct = defaultdict(list)
        for key in submission_keys:
            submission_dct[lookup[key]].append(data[key])

        submission_data = {
            k: (
                submission_dct[k][0]
                if len(submission_dct[k]) == 1
                else submission_dct[k]
            )
            for k in submission_dct.keys()
        }
        user_id = submission_data["slack_user_id"]
        updated_data = self.__update_user_info(user_id, submission_data)
        return user_id, updated_data

    def __update_user_info(self, user_id: str, data: dict) -> dict:
        """
        Getting name & email address associated with a Slack
        user id from the Slack API. It returns the status of
        the request and an updated dictionary.

        :param data: a normalized dictionary of form data from Slack
        returns:
            dict: the submitted reponses with additional user info added
        """

        try:
            user_data = self._slack_app.client.users_info(
                user=user_id, token=os.environ[self.bot_token]
            )
            profile = user_data.get("user").get("profile")
            email = profile.get("email")
            name = profile.get("real_name")
            self._logger.info(f"Successfully parsed the Slack user profile for {name}")

        except SlackApiError as e:
            email = "No email"
            name = f"Slack user id {user_id}"
            self._logger.info(f"An API error has occured: {e.response}")

        data = {**data, **{"email": email}}

        data = {**data, **{"requestor_name": name}}

        return data

    def post_message(self, slack_id: str, msg: str) -> None:
        """
        Helper function to post messages in Slack

        :param slack_id: user id or channel id where the message will be sent
        :param msg: text of message being sent

        """
        block = [{"type": "section", "text": {"type": "mrkdwn", "text": msg}}]
        self._slack_app.client.chat_postMessage(
            channel=slack_id, blocks=block, text=msg
        )
        self._logger.info(f"A message was sent to Slack ID {slack_id}")
