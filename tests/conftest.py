from __future__ import annotations

import sys
import warnings
from io import StringIO
from typing import TYPE_CHECKING, Any

import django
import pytest
from django.conf import settings
from src import capture_db_queries

if TYPE_CHECKING:
    from collections.abc import Generator


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


@pytest.fixture
def intercept_output() -> Generator[StringIO, Any, None]:
    """Перехватывает вывод для последующей проверки в тесте"""
    capture_output = StringIO()
    sys.stdout = capture_output
    yield capture_output
    sys.stdout = sys.__stdout__


@pytest.fixture
def _ignore_deprecation() -> Generator[None, Any, None]:
    warnings.simplefilter('ignore', DeprecationWarning)
    yield
    warnings.resetwarnings()


@pytest.fixture
def _debug_true() -> Generator[None, Any, None]:
    capture_db_queries.decorators._DEBUG = True
    yield
    capture_db_queries.decorators._DEBUG = False
