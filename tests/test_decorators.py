from __future__ import annotations

import re
import statistics
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import pytest
from django.db import connection
from django.utils import timezone
from src.capture_db_queries.decorators import CaptureQueries, ExtCaptureQueriesContext, capture_queries
from src.capture_db_queries.wrappers import BaseExecutionWrapper, ExplainExecutionWrapper

from tests.conftest import slow_down_execute
from tests.models import Article, Reporter

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from datetime import date
    from io import StringIO
    from uuid import UUID

    from django.db.backends.utils import CursorWrapper

ANYNUM = r'0.0[0-9]+'


def request_to_db(date_now: date | None = None) -> tuple[Reporter, Article]:
    reporter = Reporter.objects.create(full_name='full_name')
    return reporter, Article.objects.create(
        pub_date=date_now or timezone.now().date(),
        headline='headline',
        content='content',
        reporter=reporter,
    )


def _select(reporter_id: UUID, article_id: UUID) -> None:
    list(Reporter.objects.filter(pk=reporter_id))
    list(Article.objects.filter(pk=article_id))


class BasicTestsFor3ChoicesOfCaptureQueries:
    """"""

    def setup_method(self, method: Callable[..., Any]) -> None:
        self.reporter, self.article = request_to_db()

    def call_capture_queries(self, **kwargs: Any) -> CaptureQueries:
        raise NotImplementedError

    # @pytest.mark.usefixtures('_debug_true')
    def test_basic_logic(self) -> None:
        obj = self.call_capture_queries()

        assert isinstance(obj.wrapper, BaseExecutionWrapper), type(obj.wrapper).__name__

        data = (obj.current_iteration, len(obj), obj.connection.vendor)
        assert data == (1, 2, 'sqlite'), data

        data = sum(obj.wrapper.timer.all_execution_times)
        gt, lt = 0.1, 0.3
        assert gt < data < lt, f'{gt} < {data} < {lt}'

        data = statistics.median(obj.wrapper.timer.all_execution_times)
        gt, lt = 0.08, 0.13
        assert gt < data < lt, f'{gt} < {data} < {lt}'

        data = obj.queries_log[0]['time']
        assert gt < data < lt, f'{gt} < {data} < {lt}'

        data = obj.queries_log[1]['time']
        assert gt < data < lt, f'{gt} < {data} < {lt}'

        data = obj.queries_log[0]['sql']
        assert obj.queries_log[0]['sql'] == (
            'SELECT "tests_reporter"."id", "tests_reporter"."full_name" '
            'FROM "tests_reporter" WHERE "tests_reporter"."id" = %s' % self.reporter.pk
        ), data

        data = obj.queries_log[1]['sql']
        assert obj.queries_log[1]['sql'] == (
            'SELECT "tests_article"."id", "tests_article"."pub_date", "tests_article"."headline", '
            '"tests_article"."content", "tests_article"."reporter_id" '
            'FROM "tests_article" WHERE "tests_article"."id" = %s' % self.article.pk
        ), data

        with pytest.raises(KeyError, match='explain'):
            obj.queries_log[0]['explain']

        with pytest.raises(KeyError, match='explain'):
            obj.queries_log[1]['explain']

    def test_param__assert_q_count(self) -> None:
        with pytest.raises(AssertionError, match='2 not less than or equal to 1 queries'):
            self.call_capture_queries(assert_q_count=1)

    def test_param__explain(self) -> None:
        obj = self.call_capture_queries(explain=True)

        assert isinstance(obj.wrapper, ExplainExecutionWrapper), type(obj.wrapper).__name__

        gt, lt = 0.08, 0.13

        data = obj.queries_log[0]['time']
        assert gt < data < lt, f'{gt} < {data} < {lt}'

        data = obj.queries_log[1]['time']
        assert gt < data < lt, f'{gt} < {data} < {lt}'

        data = obj.queries_log[0]['sql']
        assert data == (
            'SELECT "tests_reporter"."id", "tests_reporter"."full_name" '
            'FROM "tests_reporter" WHERE "tests_reporter"."id" = %s' % self.reporter.pk
        ), data

        data = obj.queries_log[1]['sql']
        assert data == (
            'SELECT "tests_article"."id", "tests_article"."pub_date", "tests_article"."headline", '
            '"tests_article"."content", "tests_article"."reporter_id" '
            'FROM "tests_article" WHERE "tests_article"."id" = %s' % self.article.pk
        ), data

        # data = obj.queries_log[0]['explain']
        # assert data == '2 0 0 SEARCH TABLE tests_reporter USING INTEGER PRIMARY KEY (rowid=?)', data

        # data = obj.queries_log[1]['explain']
        # assert data == '2 0 0 SEARCH TABLE tests_article USING INTEGER PRIMARY KEY (rowid=?)', data

    # def test_param__explain_opts(self) -> None:
    #     with pytest.raises(ValueError, match='Unknown options: opt1, opt12'):
    #         self.call_capture_queries(explain=True, explain_opts={'opt1': 'value1', 'opt2': 'value2'})

    def test_param__connection(self) -> None:
        class FakeConnection:
            vendor = 'fake_vendor'
            queries_limit = 4
            ops = connection.ops

            @contextmanager
            def execute_wrapper(
                self, wrapper: BaseExecutionWrapper
            ) -> Generator[None, None, CursorWrapper]:
                connection.execute_wrappers.append(wrapper)
                try:
                    yield
                finally:
                    connection.execute_wrappers.pop()

        obj = self.call_capture_queries(connection=FakeConnection())

        data = obj.connection.vendor
        assert data == FakeConnection.vendor, data


@pytest.mark.django_db(transaction=True)
class TestLoopCaptureQueries(BasicTestsFor3ChoicesOfCaptureQueries):
    """"""

    def call_capture_queries(self, **kwargs: Any) -> CaptureQueries:
        with slow_down_execute(0.1):
            obj = CaptureQueries(**kwargs)
            for _ in obj:
                _select(self.reporter.pk, self.article.pk)
        return obj

    # @pytest.mark.usefixtures('_debug_true')
    def test_param__number_runs(self) -> None:
        obj = self.call_capture_queries(number_runs=3)

        data = (obj.current_iteration, len(obj), obj.connection.vendor)
        assert data == (3, 6, 'sqlite'), data

        data = sum(obj.wrapper.timer.all_execution_times)
        gt, lt = 0.6, 0.7
        assert gt < data < lt, f'{gt} < {data} < {lt}'

        data = statistics.median(obj.wrapper.timer.all_execution_times)
        gt, lt = 0.08, 0.13
        assert gt < data < lt, f'{gt} < {data} < {lt}'

    def test_execute_raw_sql(self) -> None:
        reporter_raw_sql = (
            'SELECT "tests_reporter"."id", "tests_reporter"."full_name" '
            'FROM "tests_reporter" WHERE "tests_reporter"."id" = %s' % self.reporter.pk
        )
        article_raw_sql = (
            'SELECT "tests_article"."id", "tests_article"."pub_date", "tests_article"."headline", '
            '"tests_article"."content", "tests_article"."reporter_id" '
            'FROM "tests_article" WHERE "tests_article"."id" = %s' % self.article.pk
        )
        obj = CaptureQueries()
        for _ in obj:
            list(Reporter.objects.raw(reporter_raw_sql))
            list(Article.objects.raw(article_raw_sql))

        data = obj.queries_log[0]['sql']
        assert data == (reporter_raw_sql), data

        data = obj.queries_log[1]['sql']
        assert data == (article_raw_sql), data

    def test_without_requests(self) -> None:
        for _ in CaptureQueries(advanced_verb=True):
            pass  # no have requests


@pytest.mark.django_db(transaction=True)
class TestDecoratorCaptureQueries(BasicTestsFor3ChoicesOfCaptureQueries):
    """"""

    def call_capture_queries(self, **kwargs: Any) -> CaptureQueries:
        with slow_down_execute(0.1):
            obj = CaptureQueries(**dict({'auto_call_func': True}, **kwargs))

            @obj
            def _() -> None:
                _select(self.reporter.pk, self.article.pk)

        return obj

    def test_param__number_runs(self) -> None:
        with slow_down_execute(0.1):
            obj = CaptureQueries(auto_call_func=False, number_runs=3)

            @obj
            def func(a: int, b: int) -> int:
                _select(self.reporter.pk, self.article.pk)
                return a + b

            result, eq = func(2, 2), 4

        assert result == eq, f'{result} == {eq}'

        data = (obj.current_iteration, len(obj), obj.connection.vendor)
        assert data == (3, 6, 'sqlite'), data

        data = sum(obj.wrapper.timer.all_execution_times)
        gt, lt = 0.6, 0.7
        assert gt < data < lt, f'{gt} < {data} < {lt}'

        data = statistics.median(obj.wrapper.timer.all_execution_times)
        gt, lt = 0.08, 0.13
        assert gt < data < lt, f'{gt} < {data} < {lt}'

    def test_param__auto_call_func(self) -> None:
        obj = self.call_capture_queries(auto_call_func=True)

        data = (obj.current_iteration, len(obj), obj.connection.vendor)
        assert data == (1, 2, 'sqlite'), data

        data = sum(obj.wrapper.timer.all_execution_times)
        gt, lt = 0.1, 0.3
        assert gt < data < lt, f'{gt} < {data} < {lt}'

        data = statistics.median(obj.wrapper.timer.all_execution_times)
        gt, lt = 0.08, 0.13
        assert gt < data < lt, f'{gt} < {data} < {lt}'

    def test_execute_raw_sql(self) -> None:
        reporter_raw_sql = (
            'SELECT "tests_reporter"."id", "tests_reporter"."full_name" '
            'FROM "tests_reporter" WHERE "tests_reporter"."id" = %s' % self.reporter.pk
        )
        article_raw_sql = (
            'SELECT "tests_article"."id", "tests_article"."pub_date", "tests_article"."headline", '
            '"tests_article"."content", "tests_article"."reporter_id" '
            'FROM "tests_article" WHERE "tests_article"."id" = %s' % self.article.pk
        )
        obj = CaptureQueries(auto_call_func=True)

        @obj
        def _() -> None:
            list(Reporter.objects.raw(reporter_raw_sql))
            list(Article.objects.raw(article_raw_sql))

        data = obj.queries_log[0]['sql']
        assert data == (reporter_raw_sql), data

        data = obj.queries_log[1]['sql']
        assert data == (article_raw_sql), data

    def test_without_requests(self) -> None:
        @CaptureQueries(advanced_verb=True, auto_call_func=True)
        def func() -> None:
            pass  # no have requests


@pytest.mark.django_db(transaction=True)
class TestContextManagerCaptureQueries(BasicTestsFor3ChoicesOfCaptureQueries):
    """"""

    def call_capture_queries(self, **kwargs: Any) -> CaptureQueries:
        with slow_down_execute(0.1):  # noqa: SIM117
            with CaptureQueries(**kwargs) as obj:
                _select(self.reporter.pk, self.article.pk)
        return obj

    # @pytest.mark.filterwarnings("ignore::UserWarning")  # warn not show, and not raise exc
    # @pytest.mark.filterwarnings('default::UserWarning')  # warn show, and not raise exc
    def test_param__number_runs(self) -> None:
        with pytest.raises(  # noqa: SIM117
            UserWarning,
            match=(
                'When using: CaptureQueries as a context manager,'
                ' the number_runs > 1 parameter is not used.'
            ),
        ):
            with CaptureQueries(number_runs=3):
                pass

    def test_execute_raw_sql(self) -> None:
        reporter_raw_sql = (
            'SELECT "tests_reporter"."id", "tests_reporter"."full_name" '
            'FROM "tests_reporter" WHERE "tests_reporter"."id" = %s' % self.reporter.pk
        )
        article_raw_sql = (
            'SELECT "tests_article"."id", "tests_article"."pub_date", "tests_article"."headline", '
            '"tests_article"."content", "tests_article"."reporter_id" '
            'FROM "tests_article" WHERE "tests_article"."id" = %s' % self.article.pk
        )
        with CaptureQueries() as obj:
            list(Reporter.objects.raw(reporter_raw_sql))
            list(Article.objects.raw(article_raw_sql))

        data = obj.queries_log[0]['sql']
        assert data == (reporter_raw_sql), data

        data = obj.queries_log[1]['sql']
        assert data == (article_raw_sql), data

    def test_without_requests(self) -> None:
        with CaptureQueries(advanced_verb=True):
            pass  # no have requests


@pytest.mark.django_db(transaction=True)
class TestOutputCaptureQueries:
    """The -s argument must be passed when running py test to output output"""

    # @pytest.mark.usefixtures('_debug_true')
    def test_capture_queries_loop(self, intercept_output: StringIO) -> None:
        date_now = timezone.now().date()

        for _ctx in CaptureQueries(assert_q_count=200, number_runs=100, auto_call_func=True):
            request_to_db(date_now)

        output = intercept_output.getvalue()

        assert re.match(
            f'\n\nTests count: 100  |  Total queries count: 200  |  Total execution time: {ANYNUM}s  |  Median time one test is: {ANYNUM}s\n',  # noqa: E501
            output,
        ), f'incorrect output = {output}'

    # @pytest.mark.usefixtures('_debug_true')
    def test_capture_queries_decorator(self, intercept_output: StringIO) -> None:
        date_now = timezone.now().date()

        @CaptureQueries(assert_q_count=200, number_runs=100, auto_call_func=True)
        def _() -> None:
            request_to_db(date_now)

        output = intercept_output.getvalue()

        assert re.match(
            f'\n\nTests count: 100  |  Total queries count: 200  |  Total execution time: {ANYNUM}s  |  Median time one test is: {ANYNUM}s\n',  # noqa: E501
            output,
        ), f'incorrect output = {output}'

    # @pytest.mark.usefixtures('_debug_true')
    def test_capture_queries_context_manager(self, intercept_output: StringIO) -> None:
        with CaptureQueries() as ctx:  # noqa: F841
            request_to_db()

        output = intercept_output.getvalue()

        assert re.match(
            f'\nQueries count: 2  |  Execution time: {ANYNUM}s  |  Vendor: sqlite\n\n',
            output,
        ), f'incorrect output = {output}'


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures('_ignore_deprecation')
def test_capture_queries(intercept_output: StringIO) -> None:
    """Обязательно должен быть передан аргумент -s при запуске pytest, для вывода output"""

    @capture_queries(assert_q_count=200, number_runs=100)
    def _() -> None:
        request_to_db()

    output = intercept_output.getvalue()

    assert re.match(
        f'Tests count: 100  |  Total queries count: 200  |  Total execution time: {ANYNUM}s  |  Median time one test is: {ANYNUM}s\n',  # noqa: E501
        output,
    ), 'incorrect output'


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures('_ignore_deprecation')
def test_capture_queries_with_advanced_verb_and_queries(intercept_output: StringIO) -> None:
    """Обязательно должен быть передан аргумент -s при запуске pytest, для вывода output"""

    date_now = timezone.now().date()

    @capture_queries(number_runs=2, advanced_verb=True, queries=True)
    def _() -> None:
        request_to_db(date_now)

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
@pytest.mark.usefixtures('_ignore_deprecation')
def test_ext_capture_queries_context(intercept_output: StringIO) -> None:
    """Обязательно должен быть передан аргумент -s при запуске pytest, для вывода output"""

    with ExtCaptureQueriesContext() as ctx:  # noqa: F841
        request_to_db()

    output = intercept_output.getvalue()

    assert re.match(
        f'Queries count: 2  |  Execution time: {ANYNUM}s',
        output,
    ), 'incorrect output'
