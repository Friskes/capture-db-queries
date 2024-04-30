import sys
from io import StringIO
from typing import Any, Generator  # noqa: UP035

import django
import pytest
from django.conf import settings


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
