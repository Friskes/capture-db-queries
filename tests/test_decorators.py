from io import StringIO

import pytest
from django.utils import timezone
from src.capture_db_queries.decorators import ExtCaptureQueriesContext, capture_queries

from tests.models import Article, Reporter


# python -m pip install .
# pytest -s -v ./tests
@pytest.mark.django_db(transaction=True)
def test_capture_queries(intercept_output: StringIO) -> None:
    """Обязательно должен быть передан аргумент -s при запуске pytest, для вывода output"""

    @capture_queries(assert_q_count=200, number_runs=100)
    def _() -> None:
        reporter = Reporter.objects.create(full_name='full_name')
        Article.objects.create(
            pub_date=timezone.now().date(),
            headline='headline',
            content='content',
            reporter=reporter,
        )

    value = intercept_output.getvalue()
    assert value[:72] == 'Tests count: 100  |  Total queries count: 200  |  Total execution time: '
    # assert float(value[72:76]) in [x / 100.0 for x in range(1, 4)]
    assert value[76:107] == 's  |  Median time one test is: '
    # assert float(value[107:112]) in [x / 1000.0 for x in range(1)]
    assert value[112:114] == 's\n'


@pytest.mark.django_db(transaction=True)
def test_ext_capture_queries_context(intercept_output: StringIO) -> None:
    """Обязательно должен быть передан аргумент -s при запуске pytest, для вывода output"""

    with ExtCaptureQueriesContext() as ctx:
        reporter = Reporter.objects.create(full_name='full_name')
        Article.objects.create(
            pub_date=timezone.now().date(),
            headline='headline',
            content='content',
            reporter=reporter,
        )

    value = intercept_output.getvalue()
    assert value[:37] == 'Queries count: 2  |  Execution time: '
    # assert float(value[37:42]) in [x / 1000.0 for x in range(2)]
    assert value[42:43] == 's'
