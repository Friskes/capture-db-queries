import warnings

warnings.filterwarnings(
    'ignore',
    message="'cgi' is deprecated and slated for removal in Python 3.13",
    category=DeprecationWarning,
)

from ._logging import switch_logger, switch_trace  # noqa: F401, E402
from .decorators import CaptureQueries, ExtCaptureQueriesContext, capture_queries  # noqa: F401, E402
