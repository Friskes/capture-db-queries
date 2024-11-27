from __future__ import annotations

import abc
import functools
import statistics
import time
import warnings
from collections import deque
from contextlib import contextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any
from unittest.util import safe_repr

from django.core.signals import request_started
from django.db import (
    connection as db_connection,
    reset_queries,
)
from django.test.utils import CaptureQueriesContext
from typing_extensions import Self  # noqa: UP035

from ._logging import log
from .dtos import IterationPrintDTO, SeveralPrintDTO, SinglePrintDTO
from .printers import AbcPrinter, PrinterSql
from .wrappers import BaseExecutionWrapper, ExplainExecutionWrapper

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from types import TracebackType

    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.backends.utils import CursorWrapper

    from .types import DecoratedCallable, QueriesLog, Query, T

__all__ = ('CaptureQueries', 'capture_queries', 'ExtCaptureQueriesContext')


class AbcCapture(abc.ABC):
    def __init__(
        self,
        assert_q_count: int | None = None,
        number_runs: int = 1,
        verbose: bool = True,
        advanced_verb: bool = False,
        auto_call_func: bool = False,
        queries: bool = False,
        explain: bool = False,
        explain_opts: dict[str, Any] | None = None,
        connection: BaseDatabaseWrapper | None = None,
    ) -> None:
        log.debug('')

        self.assert_q_count = assert_q_count
        self.number_runs = number_runs
        self.verbose = verbose
        self.advanced_verb = advanced_verb
        self.auto_call_func = auto_call_func
        self.queries = queries
        self.explain = explain

        # Wrappers for specific databases are stored at addresses:
        # django.db.backends.sqlite3.base.DatabaseWrapper
        # django.db.backends.postgresql.base.DatabaseWrapper
        if connection is None:
            self.connection = db_connection
        else:
            self.connection = connection

        self.current_iteration = 0

        self.printer = self.printer_cls(
            self.connection.vendor, assert_q_count, verbose, advanced_verb, queries
        )

        self.queries_log: QueriesLog = deque(maxlen=self.connection.queries_limit)

        self.wrapper = self.wrapper_cls(
            connection=self.connection, queries_log=self.queries_log, explain_opts=explain_opts or {}
        )
        self.wrapper_ctx_manager = self.__wrap_reqs_in_wrapper()

    @property
    def printer_cls(self) -> type[AbcPrinter]:
        """Returns a class that should perform the formatting and output functions of SQL queries."""
        return PrinterSql

    @property
    def wrapper_cls(self) -> type[BaseExecutionWrapper]:
        """Returns a class that should execute all SQL queries generated by the user."""
        if self.explain:
            return ExplainExecutionWrapper
        return BaseExecutionWrapper

    @contextmanager
    def __wrap_reqs_in_wrapper(self) -> Generator[None, None, CursorWrapper]:
        """Wraps all database requests in a wrapper."""
        log.debug('')

        # https://docs.djangoproject.com/en/5.1/topics/db/instrumentation/#connection-execute-wrapper
        with self.connection.execute_wrapper(self.wrapper):
            yield

    def __enter__(self) -> Self:
        log.debug('')

        if self.number_runs > 1:
            warnings.warn(
                f'When using: {type(self).__name__} as a context manager,'
                ' the number_runs > 1 parameter is not used.',
                category=UserWarning,
                stacklevel=2,
            )

        self.wrapper_ctx_manager.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        log.debug('')

        self.wrapper_ctx_manager.__exit__(None, None, None)

        if exc_type is not None:
            return

        queries_count = len(self)
        self.printer.print_single_sql(
            SinglePrintDTO(
                queries_count=queries_count,
                queries_log=self.queries_log,
                execution_time_per_iter=self.wrapper.timer.execution_time_per_iter,
            )
        )
        self._assert_queries_count(queries_count)

    def __iter__(self) -> Self:
        log.debug('')

        self.wrapper_ctx_manager.__enter__()
        return self

    def __next__(self) -> Self:
        log.debug('')

        if self.current_iteration > 0:
            self.printer.iteration_print(
                IterationPrintDTO(
                    current_iteration=self.current_iteration,
                    queries_count_per_iter=self.wrapper.timer.queries_count_per_iter,
                    execution_time_per_iter=self.wrapper.timer.execution_time_per_iter,
                )
            )

        self.wrapper.timer.clear_exec_times_per_iter()

        if self.current_iteration < self.number_runs:
            self.current_iteration += 1
            return self

        self.wrapper_ctx_manager.__exit__(None, None, None)

        queries_count = len(self)
        self.printer.print_several_sql(
            SeveralPrintDTO(
                queries_count=queries_count,
                queries_log=self.queries_log,
                current_iteration=self.current_iteration,
                all_execution_times=self.wrapper.timer.all_execution_times,
            )
        )
        self._assert_queries_count(queries_count)

        raise StopIteration

    def __call__(self, func: DecoratedCallable) -> DecoratedCallable | Any:
        log.debug('')

        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            log.debug('')

            # The measurement consists of number_runs runs in a row
            for _ in self:
                return_value = func(*args, **kwargs)
            return return_value

        if not self.auto_call_func:
            return wrapped
        return wrapped()  # Auto-calling of the decorated function

    def __len__(self) -> int:
        log.debug('')

        return len(self.queries_log)

    def __getitem__(self, index: int) -> Query | None:
        log.debug('')

        try:
            return self.queries_log[index]
        except IndexError:
            return None

    @abc.abstractmethod
    def _assert_queries_count(self, queries_count: int) -> None:
        raise NotImplementedError


class CaptureQueries(AbcCapture):
    """
    Measures the number of database requests and
    displays detailed information about the measurements,
    validates the number of requests.

    ---

    UseCases::

        for ctx in CaptureQueries(number_runs=2, advanced_verb=True):
            response = self.client.get(url)

        OR

        @CaptureQueries(number_runs=2, advanced_verb=True)
        def test_request():
            response = self.client.get(url)

        OR

        # NOTE: The with context manager does not support multi-launch number_runs > 1
        with CaptureQueries(number_runs=1, advanced_verb=True) as ctx:
            response = self.client.get(url)

        >>> Test №1 | Queries count: 10 | Execution time: 0.04s
        >>> Test №2 | Queries count: 10 | Execution time: 0.04s
        >>> Tests count: 2  |  Total queries count: 20  |  Total execution time: 0.08s  |  Median time one test is: 0.041s  |  Vendor: sqlite

        # Example of output when using queries and explain parameters:

        for _ in CaptureQueries(advanced_verb=True, queries=True, explain=True):
            list(Reporter.objects.filter(pk=1))
            list(Article.objects.filter(pk=1))

        >>> Test №1 | Queries count: 2 | Execution time: 0.22s
        >>>
        >>>
        >>> №[1] time=[0.109] explain=['2 0 0 SEARCH TABLE tests_reporter USING INTEGER PRIMARY KEY (rowid=?)']
        >>> SELECT "tests_reporter"."id",
        >>>     "tests_reporter"."full_name"
        >>> FROM "tests_reporter"
        >>> WHERE "tests_reporter"."id" = %s
        >>>
        >>>
        >>> №[2] time=[0.109] explain=['2 0 0 SEARCH TABLE tests_article USING INTEGER PRIMARY KEY (rowid=?)']
        >>> SELECT "tests_article"."id",
        >>>     "tests_article"."pub_date",
        >>>     "tests_article"."headline",
        >>>     "tests_article"."content",
        >>>     "tests_article"."reporter_id"
        >>> FROM "tests_article"
        >>> WHERE "tests_article"."id" = %s
        >>>
        >>>
        >>> Tests count: 1  |  Total queries count: 2  |  Total execution time: 0.22s  |  Median time one test is: 0.109s  |  Vendor: sqlite

    ---

    - assert_q_count: The expected number of database requests otherwise an
     "AssertionError: N not less than or equal to N queries"
    - number_runs: The number of runs of the test function / test cycle
    - verbose: Displaying the final results of the test measurements
    - advanced_verb: Displaying the result of each test measurement
    - auto_call_func: Autorun of the decorated function (without arguments)
    - queries: Displaying raw SQL queries to the database
    - explain: Displaying additional information about each request (has no effect on the orig. requests)
    - explain_opts: Parameters for explain, find out more in the documentation for your DBMS
    - connection: Connecting to your database, by default: django.db.connection

    ---

    Tests count: Total number of test measurements
    Total queries count: The total number of database requests
     within the test function within all measurements
    Total execution time: Total time for executing database queries
     inside the test function within all measurements
    Median time one test is: Average execution time of one test measurement
    Vendor: The database under test
    """  # noqa: E501

    def _assert_queries_count(self, queries_count: int) -> None:
        log.debug('')

        if self.assert_q_count is not None:
            assert queries_count <= self.assert_q_count, self.printer.assert_msg(queries_count)


def capture_queries(
    assert_q_count: int | None = None,
    number_runs: int = 1,
    verbose: bool = True,
    advanced_verb: bool = False,
    queries: bool = False,
) -> Callable[[DecoratedCallable], None]:
    """
    Замеряет количество запросов к бд внутри тела тестовой функции,
    выводит подробную информацию о замерах,
    валидирует количество запросов.

    Вызов тестовой функции `_` произойдёт автоматически.

    UseCase::

        @capture_queries(number_runs=2, advanced_verb=True)
        def _():
            response = self.client.get(url)

        >>> Test №1 | Queries count: 10 | Execution time: 0.04s
        >>> Test №2 | Queries count: 10 | Execution time: 0.04s
        >>> Tests count: 2  |  Total queries count: 20  |  Total execution time: 0.08s  |  Median time one test is: 0.041s

    - assert_q_count: Ожидаемое количество запросов к БД иначе
     "AssertionError: N not less than or equal to N queries"
    - number_runs: Количество запусков тестовой функции `_`
    - verbose: Отображение финальных результатов тестовых замеров
    - advanced_verb: Отображение результа каждого тестового замера
    - queries: Отображение сырых SQL запросов к БД

    Tests count: Общее количество тестовых замеров
    Total queries count: Общее количество запросов к БД внутри тестовой функции в рамках всех замеров
    Total execution time: Общее время выполнения запросов к БД
     внутри тестовой функции в рамках всех замеров
    Median time one test is: Среднее время выполнения одного тестового замера
    """  # noqa: E501

    def _wrapper(func: DecoratedCallable) -> None:
        """"""

        @functools.wraps(func)
        def spoof_func(*args: Any, **kwargs: Any) -> None:
            """"""
            warnings.warn(
                'Декоратор @capture_queries устарел и будет удален в будущих версиях. '
                'Используйте класс @CaptureQueries вместо него.',
                category=DeprecationWarning,
                stacklevel=2,
            )

            force_debug_cursor = db_connection.force_debug_cursor
            db_connection.force_debug_cursor = True
            # Run any initialization queries if needed so that they won't be
            # included as part of the count.
            db_connection.ensure_connection()
            initial_queries = len(db_connection.queries_log)
            final_queries = None
            request_started.disconnect(reset_queries)

            all_execution_times = []
            for i in range(1, number_runs + 1):  # замер состоит из number_runs прогонов подряд
                start_queries = len(db_connection.queries)
                start = time.perf_counter()

                return_value = func(*args, **kwargs)

                end = time.perf_counter()
                end_queries = len(db_connection.queries)
                execution_time = end - start

                all_execution_times.append(execution_time)
                if advanced_verb:
                    print(
                        f'Test №{i} | '
                        f'Queries count: {end_queries - start_queries} | '
                        f'Execution time: {execution_time:.2f}s'
                    )

            db_connection.force_debug_cursor = force_debug_cursor
            request_started.connect(reset_queries)
            final_queries = len(db_connection.queries_log)

            if queries:
                for query in db_connection.queries[initial_queries:final_queries]:
                    print(query, end='\n\n')

            if verbose:
                print(
                    f'Tests count: {i}  |  '
                    f'Total queries count: {final_queries}  |  '
                    f'Total execution time: {sum(all_execution_times):.2f}s  |  '
                    f'Median time one test is: {statistics.median(all_execution_times):.3f}s'
                )

            if assert_q_count is not None:
                standard_msg = (
                    f'{safe_repr(final_queries)} not less than or equal to '
                    f'{safe_repr(assert_q_count)} queries'
                )
                assert final_queries <= assert_q_count, standard_msg

            return return_value

        spoof_func()  # автовызов декорируемой функции

    return _wrapper


class ExtCaptureQueriesContext(CaptureQueriesContext):
    """
    Замеряет количество запросов к бд внутри тела контекстного менеджера,
    выводит подробную информацию о замере,
    валидирует количество запросов.

    UseCase::

        with ExtCaptureQueriesContext():
            response = self.client.get(url)

        >>> Queries count: 164  |  Execution time: 0.923s

    - assert_q_count: Ожидаемое количество запросов к БД иначе
     "AssertionError: N not less than or equal to N queries"
    - verbose: Отображение финальных результатов тестового замера
    - queries: Отображение сырых SQL запросов к БД

    Queries count: Количество запросов к БД внутри контекстного менеджера
    Execution time: Время выполнения запросов к БД внутри контекстного менеджера
    """

    def __init__(
        self, assert_q_count: int | None = None, verbose: bool = True, queries: bool = False
    ) -> None:
        warnings.warn(
            'Класс контекстного менеджера with ExtCaptureQueriesContext '
            'устарел и будет удален в будущих версиях. '
            'Используйте класс @CaptureQueries вместо него.',
            category=DeprecationWarning,
            stacklevel=2,
        )

        super().__init__(db_connection)

        self.assert_q_count = assert_q_count
        self.verbose = verbose
        self.queries = queries

    def __enter__(self: T) -> T:
        self.start = time.perf_counter()
        return super().__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        super().__exit__(exc_type, exc_value, traceback)

        end = time.perf_counter()
        execution_time = end - self.start

        if self.queries:
            for query in self.captured_queries:
                print(query, end='\n\n')

        if self.verbose:
            print(f'Queries count: {self.final_queries}  |  Execution time: {execution_time:.3f}s')

        if self.assert_q_count is not None:
            standard_msg = (
                f'{safe_repr(self.final_queries)} not less than or equal to '
                f'{safe_repr(self.assert_q_count)} queries'
            )
            assert self.final_queries <= self.assert_q_count, standard_msg
