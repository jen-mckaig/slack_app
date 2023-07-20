"""
File to store constants
"""

from enum import Enum


class DateTimeFormats(Enum):
    """
    Datetime formats
    """

    datetime_format = "%Y-%m-%d %H:%M:%S"
    date_format = "%Y-%m-%d"
    date_file_name_format = "%Y%m%d_%H%M"
    timezone = "America/New_York"
