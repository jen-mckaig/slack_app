"""Connector and methods accessing S3"""

import codecs
import csv
import logging
import os
from io import BytesIO, StringIO
from typing import Tuple

import boto3


class S3BucketConnector:
    """
    Class for interacting with S3 Buckets
    """

    def __init__(
        self, access_key: str, secret_key: str, endpoint_url: str, bucket: str
    ):
        """
        Constructor for S3BucketConnector

        :param access_key: access key for accessing S3
        :param secret_key: secret key for accessing S3
        :param endpoint_url: endpoint url to S3
        :param bucket: S3 bucket name
        """

        self._logger = logging.getLogger(__name__)
        self.endpoint_url = endpoint_url
        self.session = boto3.Session(
            aws_access_key_id=os.environ[access_key],
            aws_secret_access_key=os.environ[secret_key],
        )
        self._s3 = self.session.resource(service_name="s3")
        self._client = self.session.client(service_name="s3")
        self._bucket = self._s3.Bucket(os.environ[bucket])

    def list_files_in_prefix(self, prefix: str) -> list:
        """
        listing all files with a prefix on the S3 bucket

        :param prefix: prefix on the S3 bucket that should be filtered with
        returns:
          list: file names containing the prefix in the key
        """
        files = [obj.key for obj in self._bucket.objects.filter(Prefix=prefix)]
        return files

    def read_csv(self, file_name: str) -> list:
        """
        reading a csv file from the S3 bucket and returning a list of dictionaires

        :param file_name: name of the file that should be read
        returns:
          list: records containing each line of a csv file
        """
        self._logger.info(
            f"Reading file {self.endpoint_url} {self._bucket.name} {file_name}"
        )
        data = self._bucket.Object(key=file_name).get()
        records = [
            row for row in csv.DictReader(codecs.getreader("utf-8")(data["Body"]))
        ]
        return records

    def get_most_recent_modified_file(self, prefix: str) -> Tuple[list, str]:
        """
        returning a file that was most recently modified and the name of that file

        :param prefix: the S3 directory containing the files you are looking for
        returns:
            list: records containing each line of a csv file
            str: name of the file that is returned
        """
        file_dates = [
            obj.last_modified.replace(tzinfo=None)
            for obj in self._bucket.objects.filter(Prefix=prefix)
            if obj != f"{prefix}/"
        ]
        file_dates.sort(reverse=True)
        most_recent_date = file_dates[0]
        files = [
            obj.key
            for obj in self._bucket.objects.filter(Prefix=prefix)
            if obj.last_modified.replace(tzinfo=None) == most_recent_date
            and obj != f"{prefix}/"
        ]
        file_name = files[0]
        csv_obj = self.read_csv(file_name)
        return csv_obj, file_name

    def write_to_s3(self, data: list, file_name: str) -> bool:
        """
        writing a list of dictionaries to the indicated s3 bucket
        supports csv format only

        :param data: a list of dictionaries to be written as a csv file to s3
        :param file_name: the file_name it will be saved under
        returns:
            boolean value
        """
        fields = list(data[0].keys())
        if not data:
            self._logger.info("The list is empty! No file will be written!")
            return None
        else:
            out_buffer = StringIO()
            writer = csv.DictWriter(out_buffer, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data)
            return self.__put_object(out_buffer, file_name)

    def __put_object(self, out_buffer: StringIO or BytesIO, file_name: str) -> bool:
        """
        Helper function for self.write_table_to_s3()

        :out_buffer: StringIO | BytesIO that should be written
        :file_name: file_name of the saved file
        returns:
            boolean value

        """
        self._logger.info(
            f"Writing file to {self.endpoint_url} {self._bucket.name} {file_name}"
        )
        self._bucket.put_object(Body=out_buffer.getvalue(), Key=file_name)
        return True

    def remove_object(self, file_name: str) -> None:
        """
        Helper function to delete files from the s3 bucket

        :param file_name: file to delete from bucket
        """

        response = self._client.delete_object(Bucket=self._bucket.name, Key=file_name)
        self._logger.info(f"Deleted file {file_name} - {response}")
