import re
from io import StringIO

import pytest
from django.utils import timezone
from src.capture_db_queries.decorators import ExtCaptureQueriesContext, capture_queries

from tests.models import Article, Reporter

ANYNUM = r'0.0[0-9]+'


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

    output = intercept_output.getvalue()

    assert re.match(
        f'Tests count: 100  |  Total queries count: 200  |  Total execution time: {ANYNUM}s  |  Median time one test is: {ANYNUM}s\n',  # noqa: E501
        output,
    ), 'incorrect output'


@pytest.mark.django_db(transaction=True)
def test_capture_queries_with_advanced_verb_and_queries(intercept_output: StringIO) -> None:
    """Обязательно должен быть передан аргумент -s при запуске pytest, для вывода output"""

    date_now = timezone.now().date()

    @capture_queries(number_runs=2, advanced_verb=True, queries=True)
    def _() -> None:
        reporter = Reporter.objects.create(full_name='full_name')
        Article.objects.create(
            pub_date=date_now,
            headline='headline',
            content='content',
            reporter=reporter,
        )

    output = intercept_output.getvalue()
    result_outputs = [x for x in output.split('\n') if x != '']

    correct_outputs = [
        f'Test №1 | Queries count: 2 | Execution time: {ANYNUM}s',
        f'Test №2 | Queries count: 2 | Execution time: {ANYNUM}s',
        '---SQL query---',
        '---SQL query---',
        '---SQL query---',
        '---SQL query---',
        f'Tests count: 2  |  Total queries count: 4  |  Total execution time: {ANYNUM}s  |  Median time one test is: {ANYNUM}s',  # noqa: E501
    ]

    assert len(result_outputs) == len(correct_outputs)

    for result_output, correct_output in zip(result_outputs, correct_outputs):  # noqa: B905
        if result_output.startswith("{'sql':"):
            continue
        assert re.match(
            correct_output,
            result_output,
        ), 'incorrect output'


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

    output = intercept_output.getvalue()

    assert re.match(
        f'Queries count: 2  |  Execution time: {ANYNUM}s',
        output,
    ), 'incorrect output'
