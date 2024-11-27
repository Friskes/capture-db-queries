# type: ignore

"""
https://github.com/WolfgangFahl/pyLoDStorage/issues/127
https://docs.python.org/3/library/sqlite3.html#adapter-and-converter-recipes

fix: DeprecationWarning: The default date converter is deprecated as of Python 3.12;
 see the sqlite3 documentation for suggested replacement recipes
"""

import datetime
import sqlite3


def adapt_date_iso(val):
    """Adapt datetime.date to ISO 8601 date."""
    return val.isoformat()


def adapt_datetime_iso(val):
    """Adapt datetime.datetime to timezone-naive ISO 8601 date."""
    return val.isoformat()


def adapt_datetime_epoch(val):
    """Adapt datetime.datetime to Unix timestamp."""
    return int(val.timestamp())


sqlite3.register_adapter(datetime.date, adapt_date_iso)
sqlite3.register_adapter(datetime.datetime, adapt_datetime_iso)
sqlite3.register_adapter(datetime.datetime, adapt_datetime_epoch)


def convert_date(val):
    """Convert ISO 8601 date to datetime.date object."""
    return datetime.date.fromisoformat(val.decode())


def convert_datetime(val):
    """Convert ISO 8601 datetime to datetime.datetime object."""
    return datetime.datetime.fromisoformat(val.decode())


def convert_timestamp(val):
    """Convert Unix epoch timestamp to datetime.datetime object."""
    return datetime.datetime.fromtimestamp(int(val))  # noqa: DTZ006


sqlite3.register_converter('date', convert_date)
sqlite3.register_converter('datetime', convert_datetime)
sqlite3.register_converter('timestamp', convert_timestamp)
