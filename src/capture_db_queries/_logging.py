from __future__ import annotations

import logging
from typing import Any


class CustomLogger(logging.Logger):
    def __init__(self, name: str, level: int = logging.NOTSET) -> None:
        super().__init__(name, level)

    def trace(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        if is_enabled_for_trace():
            self._log(logging.DEBUG, msg, args, **kwargs)

    def dump(self, title: str, msg: Any, *args: Any, **kwargs: Any) -> None:
        if is_enabled_for_trace():
            self._log(logging.DEBUG, '--- %s ---', (title,))
            self._log(logging.DEBUG, msg, args, **kwargs)
            self._log(logging.DEBUG, '-----------------------', ())


# Registering the CustomLogger as the default logger class
logging.setLoggerClass(CustomLogger)

log: CustomLogger = logging.getLogger('capture_db_queries')
try:
    from logging import NullHandler
except ImportError:

    class NullHandler(logging.Handler):  # type: ignore[no-redef]
        def emit(self, record: Any) -> Any:
            pass


log.addHandler(NullHandler())
log.propagate = False  # Disabling the transmission of logs higher up the chain

__all__ = ['switch_logger', 'switch_trace', 'is_enabled_for_trace']

_trace_enabled = False


def switch_logger(
    state: bool,
    handler: logging.Handler | None = None,
    formatter: logging.Formatter | None = None,
    level: str = 'DEBUG',
) -> None:
    if state:
        console_handler = handler or logging.StreamHandler()
        console_formatter = formatter or logging.Formatter(
            '%(filename)s:%(lineno)d | def %(funcName)s | %(message)s'
        )

        console_handler.setFormatter(console_formatter)
        log.addHandler(console_handler)
        log.setLevel(getattr(logging, level))
    else:
        log.addHandler(NullHandler)  # type: ignore[arg-type]


def switch_trace(traceable: bool, handler: logging.Handler | None = None, level: str = 'DEBUG') -> None:
    """
    Turn on/off the traceability.

    Parameters
    ----------
    traceable: bool
        If set to True, traceability is enabled.
    """
    global _trace_enabled
    _trace_enabled = traceable


def is_enabled_for_trace() -> bool:
    return _trace_enabled
