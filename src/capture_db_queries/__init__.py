# ruff: noqa: F401, E402

import sys
import warnings

warnings.filterwarnings(
    'ignore',
    message="'cgi' is deprecated and slated for removal in Python 3.13",
    category=DeprecationWarning,
)

if sys.version_info >= (3, 12):
    from . import _sqlite3_adapters_and_converters

from ._logging import switch_logger, switch_trace
from .decorators import CaptureQueries, ExtCaptureQueriesContext, capture_queries
from .handlers import IHandler
