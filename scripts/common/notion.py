""" Connector and methods for accessing a Notion API & Database """

import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import NamedTuple

import requests
from dateutil import tz
from flatten_json import flatten
from requests.exceptions import HTTPError

from scripts.common.constants import DateTimeFormats


class NotionSourceConfig(NamedTuple):
    """
    Class for Notion payload configuration data
    """

    notion_page_title: dict
    notion_page_due_date: dict
    notion_page_requestor_name: dict
    notion_page_email: dict
    notion_page_request_details: dict
    notion_page_request_type: dict
    notion_page_slack_id: dict
    notion_page_project_link: dict
    notion_page_page_url: dict
    notion_page_archive_status: dict
    notion_page_ticket_id: dict
    notion_page_status: dict
    notion_page_created_at: dict
    notion_page_completion_labels: dict


class NotionConnector:
    """
    Class for interacting with the Notion API.

    :param notion_pages_endpoint: Notion Pages API endpoint
    :param notion_database_endpoint: Notion Database API endpoint
    :param notion_token: Notion API authentication token
    :param notion_database_id: the unique id for your Notion database
    :param notion_version: the version date of Notion app
    :param notion_args: NamedTuple class with Notion configuration data

    """

    def __init__(
        self,
        notion_pages_endpoint: str,
        notion_database_endpoint: str,
        notion_token: str,
        notion_database_id: str,
        notion_version: str = "2022-06-28",
        notion_args=NotionSourceConfig,
    ):
        self.pages_endpoint = os.environ[notion_pages_endpoint]
        self.database_id = os.environ[notion_database_id]
        self.headers = {
            "Authorization": "Bearer " + os.environ[notion_token],
            "Content-Type": "application/json",
            "Notion-Version": notion_version,
        }
        self.notion_db_full_url = (
            os.environ[notion_database_endpoint] + self.database_id + "/query"
        )
        self.notion_args = notion_args
        self._logger = logging.getLogger(__name__)

    def __assemble_payload(self, data: dict) -> dict:
        """
        Reformats the Slack data for Notion API

        :param data: dictionary of json headers & the inputs submitted through Slack
        returns:
            dct: json payload configured for Notion board
        """

        categories = data.get(self.notion_args.notion_page_request_type["text"])
        if isinstance(categories, str):
            categories = [categories]
        if isinstance(categories, list):
            request_type = [{"name": cat} for cat in categories]
        else:
            request_type = "None given"
            self._logger.info(f"The request type was not indicated properly.")

        payload = {
            "parent": {"type": "database_id", "database_id": self.database_id},
            "properties": {
                "Title": {
                    "title": [
                        {
                            "type": "text",
                            "text": {
                                "content": data.get(
                                    self.notion_args.notion_page_title["text"]
                                )
                            },
                        }
                    ]
                },
                "Due Date": {
                    "date": {
                        "start": data.get(self.notion_args.notion_page_due_date["text"])
                    }
                },
                "Requestor Name": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": data.get(
                                    self.notion_args.notion_page_requestor_name["text"]
                                )
                            },
                        }
                    ]
                },
                "Requestor Email": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": data.get(
                                    self.notion_args.notion_page_email["text"]
                                )
                            },
                        }
                    ]
                },
                "Request Details": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": data.get(
                                    self.notion_args.notion_page_request_details["text"]
                                )
                            },
                        }
                    ]
                },
                "Request Type": {"multi_select": request_type},
                "Slack ID": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": data.get(
                                    self.notion_args.notion_page_slack_id["text"]
                                )
                            },
                        }
                    ]
                },
                "URL": {
                    "url": data.get(self.notion_args.notion_page_project_link["text"])
                },
            },
        }

        return payload

    def post_object(self, data: dict) -> str:
        """
        Request function that sends a payload to a Notion Page and returns the status code.

        :param payload: json payload configured for Notion board
        returns:
            str: status code of Notion api response
        """
        payload = self.__assemble_payload(data)
        ticket_data = json.dumps(payload)

        try:
            response = requests.post(
                self.pages_endpoint, headers=self.headers, data=ticket_data
            )
            self._logger.info(
                f"Notion payload sent. Status code {response.status_code}"
            )

        except HTTPError as e:
            self._logger.info(f"Notion API Error - {e.response}")

        return response.status_code

    def get_db_object(self, page_size=100) -> list:
        """
        Getting the data stored in a Notion database.

        :param page_size: Indicate the length of responses to paginate through.
        returns:
            list: records containing data from each notion page

        """
        params = {"page_size": page_size}
        response_length = page_size
        data = []

        # paginate through all pages
        while response_length == page_size:
            try:
                response = requests.post(
                    self.notion_db_full_url, headers=self.headers, json=params
                )
                re = response.json()
                response_length = len(re)
                pages = re.get("results")  # returns a list of nested json objects
                records = [flatten(p) for p in pages]
                data.extend(records)

            except HTTPError as e:
                self._logger.info(f"Notion API Error - {e.response}")
                raise HTTPError
        return data

    def process_db_object(self, record_list) -> list:
        """
        Processing the list of dictionaries returned from get_db_object(). Using
        the config file to reformat and normalize data.

        :param dct_list: a list of records for each notion db page
        returns:
            list: a normalized list of records for each notion page
        """
        preferred_datetime_format = DateTimeFormats.datetime_format.value
        preferred_timezone = DateTimeFormats.timezone.value

        key_lookup = {
            self.notion_args[i]["json"]: self.notion_args[i]["text"]
            for i in range(len(self.notion_args._fields))
            if "json" in self.notion_args[i]
        }
        payload_keys = list(key_lookup.keys())

        processed_data = []
        for dct in record_list:
            # normalize headers
            dct_lowercase = {
                key.replace(" ", "_").lower(): value for key, value in dct.items()
            }
            # only take the data that are listed in the config file args
            dct_parsed = {
                key: value
                for key, value in dct_lowercase.items()
                if key in payload_keys
            }
            # replace the flattened json keys with simple text fields
            dct_simple = {key_lookup[key]: value for key, value in dct_parsed.items()}
            # reformat UTC date objects
            datetime_objects = [
                key
                for key, value in dct_simple.items()
                if value and re.match("\d{4}[/-]\d{2}[/-]\d{2}", value)
            ]
            dct_normalized = {
                key: datetime.fromisoformat(value.replace("Z", ""))
                .replace(tzinfo=timezone.utc)
                .astimezone(tz=tz.gettz(preferred_timezone))
                .strftime(preferred_datetime_format)
                if key in datetime_objects
                else value
                for key, value in dct_simple.items()
            }
            processed_data.append(dct_normalized)
        return processed_data
