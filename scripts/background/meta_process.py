"""
Methods for processing the meta file
"""
import logging
from datetime import datetime

from scripts.common.constants import DateTimeFormats
from scripts.common.notion import NotionConnector
from scripts.common.s3 import S3BucketConnector

logger = logging.getLogger(__name__)


class MetaProcess:
    """
    Wrapper for processing the meta file.
    """

    @staticmethod
    def generate_meta_file(notion_meta: NotionConnector) -> list:
        """
        Getting data from the Notion DB API and returning
        a list fo records.

        :param: notion_meta -> connection to the Notion DB API
        returns:
            list: a list of dictionaires, each record contains notion page data
        """
        data = notion_meta.get_db_object()

        # logger.info(f'View Notion json - {data[0].keys()}') # review flattened json keys
        meta_file = notion_meta.process_db_object(data)

        logger.info(f"Metafile contains {len(meta_file)} records.")
        return meta_file

    @staticmethod
    def load_meta_file(
        s3_bucket_meta: S3BucketConnector, meta_file: list, prefix: str
    ) -> None:
        """
        writing data to s3 bucket as a csv file

        :param: s3_bucket_meta -> S3BucketConnector for the bucket with the meta file
        :param: meta_file -> list of dictionaries/records
        :param: prefix -> s3 directory where files are stored

        """
        now = datetime.now()
        log_date = now.strftime(DateTimeFormats.datetime_format.value)
        file_date = now.strftime(DateTimeFormats.date_file_name_format.value)
        meta_file = [{**file, **{"uploaded_at": log_date}} for file in meta_file]
        file_name = f"{prefix}/{file_date}.csv"
        s3_bucket_meta.write_to_s3(meta_file, file_name)

    @staticmethod
    def delete_meta_files(
        s3_bucket_meta: S3BucketConnector, prefix: str, date_threshold: str
    ) -> None:
        """
        Deleting files from an S3 bucket that have a modified date
        earlier than the threshhold date.

        :param: s3_bucket_meta -> connection to the S3 bucket
        :param: prefix -> s3 directory where metafiles are stored
        :param: date_threshold -> string format 'YYYY-MM-DD'
                files older than this date will be deleted
        """

        date_threshold = datetime.strptime(
            date_threshold, DateTimeFormats.datetime_format.value
        )
        to_delete = [
            obj.key
            for obj in s3_bucket_meta._bucket.objects.filter(Prefix=prefix)
            if obj.last_modified.replace(tzinfo=None) < date_threshold
            and obj.key != f"{prefix}/"
        ]
        if to_delete:
            for file in to_delete:
                s3_bucket_meta.remove_object(f"{file}.csv")
