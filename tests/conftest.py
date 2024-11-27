from __future__ import annotations

import sys
import time
import warnings
from contextlib import contextmanager
from io import StringIO
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import django
import pytest
from django.conf import settings
from django.db.backends.utils import CursorWrapper
from src.capture_db_queries._logging import switch_logger, switch_trace  # noqa: F401

if TYPE_CHECKING:
    from collections.abc import Callable, Generator


def pytest_configure(config: pytest.Config) -> None:
    settings.configure(
        INSTALLED_APPS=('tests',),
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
    )
    django.setup()


@contextmanager
def intercept_output_ctx() -> Generator[StringIO, None, None]:
    """Перехватывает вывод для последующей проверки в тесте"""
    capture_output = StringIO()
    sys.stdout = capture_output
    try:
        yield capture_output
    finally:
        sys.stdout = sys.__stdout__


@pytest.fixture
def intercept_output() -> Generator[StringIO, None, None]:
    """Перехватывает вывод для последующей проверки в тесте"""
    with intercept_output_ctx() as capture_output:
        yield capture_output


@pytest.fixture
def _ignore_deprecation() -> Generator[None, None, None]:
    warnings.simplefilter('ignore', DeprecationWarning)
    yield
    warnings.resetwarnings()


@pytest.fixture
def _debug_true() -> Generator[None, None, None]:
    switch_logger(True)
    # switch_trace(True)
    yield
    switch_logger(False)
    # switch_trace(False)


@contextmanager
def slow_down_execute(seconds: float = 0.1) -> Generator[None, None, None]:
    """
    Фикстура для замедления CursorWrapper._execute и CursorWrapper._executemany

    Замедляет как для explain вызова так и для обычного,
    но т.к. время для explain не учитывается, замедления не видно.
    """
    # Сохраняем оригинальные методы _execute и _executemany
    original_execute: Callable[..., CursorWrapper | None] = CursorWrapper._execute
    original_executemany: Callable[..., CursorWrapper | None] = CursorWrapper._executemany

    def slow_execute(
        self: CursorWrapper, sql: str, params: tuple[Any, ...], *ignored_wrapper_args: tuple[Any, ...]
    ) -> CursorWrapper | None:
        time.sleep(seconds)  # Искусственная задержка
        return original_execute(self, sql, params, *ignored_wrapper_args)

    def slow_executemany(
        self: CursorWrapper, sql: str, params: tuple[Any, ...], *ignored_wrapper_args: tuple[Any, ...]
    ) -> CursorWrapper | None:
        time.sleep(seconds)  # Искусственная задержка
        return original_executemany(self, sql, params, *ignored_wrapper_args)

    with patch('django.db.backends.utils.CursorWrapper._execute', new=slow_execute):  # noqa: SIM117
        with patch('django.db.backends.utils.CursorWrapper._executemany', new=slow_executemany):
            yield


@contextmanager
def skip_colorize_sql() -> Generator[None, None, None]:
    with patch(
        'src.capture_db_queries.printers.PrinterSql.colorize_sql', new=lambda _, queries_log: queries_log
    ):
        yield
