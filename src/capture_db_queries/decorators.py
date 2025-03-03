from __future__ import annotations

import functools
import statistics
import sys
import time
import warnings
from functools import wraps
from typing import TYPE_CHECKING, Any
from unittest.util import safe_repr

from asgiref.sync import sync_to_async
from django.core.signals import request_started
from django.db import (
    connection as db_connection,
    reset_queries,
)
from django.test.utils import CaptureQueriesContext
from typing_extensions import Self

from ._logging import log
from .dtos import IterationPrintDTO, SeveralPrintDTO, SinglePrintDTO
from .printers import AbcPrinter, PrinterSql
from .wrappers import BaseExecutionWrapper, ExplainExecutionWrapper

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from django.db.backends.base.base import BaseDatabaseWrapper

    from .dtos import Query
    from .types import DecoratedCallable, T

__all__ = ('CaptureQueries', 'capture_queries', 'ExtCaptureQueriesContext')


def _detect_pytest_xdist() -> None:
    try:
        is_pytest = sys.argv[0].endswith('pytest')
    except IndexError:
        pass
    else:
        is_xdist = '-n' in sys.argv
        is_spot_test_launch = any('.py::' in arg for arg in sys.argv)

        if is_pytest and is_xdist and is_spot_test_launch:
            warnings.warn(
                'If you want to see the result of CaptureQueries, then remove the '
                '-n <workers> parameter when starting pytest or use --capture=tee-sys -rP parameters.',
                category=UserWarning,
                stacklevel=2,
            )


class CaptureQueries:
    """
    #### Class to simplify the search for slow and suboptimal sql queries\
    to the database in django projects.

    ---

    #### About class
    - Class allows you to track any sql queries that are executed inside the body of a loop,
    a decorated function, or a context manager,
    the body can be executed a specified number of times to get the average query execution time.

    - The class allows you to display formatted output data
    containing brief information about the current iteration of the measurement,
    display sql queries and explain information on them,
    as well as summary information containing data on all measurements.

    `Do not use the class inside the business logic of your application,
    this will greatly slow down the execution of the queries,
    the class is intended only for the test environment.`

    ---

    #### - Optional parameters:
        - `assert_q_count`: The expected number of database queries during all `number_runs`, otherwise an exception will be raised: "AssertionError: `N` not less than or equal to `N` queries".
        - `number_runs`: The number of runs of the decorated function or test for loop.
        - `verbose`: Displaying the final results of test measurements within all `number_runs`.
        - `advanced_verb`: Displaying the result of each test measurement.
        - `auto_call_func`: Autorun of the decorated function. (without passing arguments to the function, since the launch takes place inside the class).
        - `queries`: Displaying colored and formatted SQL queries to the database.
        - `explain`: Displaying explain information about each query. (has no effect on the original query).
        - `explain_opts`: Parameters for explain. (for more information about the parameters for explain, see the documentation for your DBMS).
        - `connection`: Connecting to your database, by default: django.db.connection

    ---

    #### WARNING: If you use `pytest-xdist` and run the test with the `-n <workers>` flag,
    the results will not be reflected in the terminal. Remove the `-n <workers>` flag to display them
    or use `--capture=tee-sys -rP` parameters.

    ---

    #### Usage examples::

        for ctx in CaptureQueries(number_runs=2, advanced_verb=True):
            response = self.client.get(url)

        >>> Test №1 | Queries count: 10 | Execution time: 0.04s
        >>> Test №2 | Queries count: 10 | Execution time: 0.04s
        >>> Tests count: 2  |  Total queries count: 20  |  Total execution time: 0.08s  |  Median time one test is: 0.041s  |  Vendor: sqlite

        # OR

        @CaptureQueries(number_runs=2, advanced_verb=True)
        def test_request():
            response = self.client.get(url)

        >>> Test №1 | Queries count: 10 | Execution time: 0.04s
        >>> Test №2 | Queries count: 10 | Execution time: 0.04s
        >>> Tests count: 2  |  Total queries count: 20  |  Total execution time: 0.08s  |  Median time one test is: 0.041s  |  Vendor: sqlite

        # OR

        # NOTE: The with context manager does not support multi-launch number_runs > 1
        # NOTE: Also you can use `async with` if you capture queries in async context.
        with CaptureQueries(number_runs=1, advanced_verb=True) as ctx:
            response = self.client.get(url)

        >>> Queries count: 10  |  Execution time: 0.04s  |  Vendor: sqlite

    ---

    #### Example of output when using queries and explain::

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
        >>> WHERE "tests_reporter"."id" = 1
        >>>
        >>>
        >>> №[2] time=[0.109] explain=['2 0 0 SEARCH TABLE tests_article USING INTEGER PRIMARY KEY (rowid=?)']
        >>> SELECT "tests_article"."id",
        >>>     "tests_article"."pub_date",
        >>>     "tests_article"."headline",
        >>>     "tests_article"."content",
        >>>     "tests_article"."reporter_id"
        >>> FROM "tests_article"
        >>> WHERE "tests_article"."id" = 1
        >>>
        >>>
        >>> Tests count: 1  |  Total queries count: 2  |  Total execution time: 0.22s  |  Median time one test is: 0.109s  |  Vendor: sqlite
    """  # noqa: E501

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
        _detect_pytest_xdist()
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

        self.wrapper = self.wrapper_cls(connection=self.connection, explain_opts=explain_opts or {})
        self.wrapper_ctx_manager = self.wrapper.wrap_reqs_in_wrapper()

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

    async def __aenter__(self) -> Self:
        return await sync_to_async(self.__enter__)()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await sync_to_async(self.__exit__)(exc_type, exc_value, traceback)

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

        self.current_iteration += 1
        queries_count = len(self)
        self.printer.print_single_sql(
            SinglePrintDTO(
                queries_count=queries_count,
                queries_log=self.wrapper.queries_log,
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
                queries_log=self.wrapper.queries_log,
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

        return len(self.wrapper.queries_log)

    def __getitem__(self, index: int) -> Query | None:
        log.debug('')

        try:
            return self.wrapper.queries_log[index]
        except IndexError:
            return None

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
