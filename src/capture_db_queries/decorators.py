from __future__ import annotations

import functools
import statistics
import time
from typing import TYPE_CHECKING, Any
from unittest.util import safe_repr

from django.core.signals import request_started
from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from capture_db_queries.types import DecoratedCallable, T

__all__ = ('capture_queries', 'ExtCaptureQueriesContext')


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
            force_debug_cursor = connection.force_debug_cursor
            connection.force_debug_cursor = True
            # Run any initialization queries if needed so that they won't be
            # included as part of the count.
            connection.ensure_connection()
            initial_queries = len(connection.queries_log)
            final_queries = None
            request_started.disconnect(reset_queries)

            all_execution_times = []
            for i in range(1, number_runs + 1):  # замер состоит из number_runs прогонов подряд
                start_queries = len(connection.queries)
                start = time.perf_counter()

                return_value = func(*args, **kwargs)

                end = time.perf_counter()
                end_queries = len(connection.queries)
                execution_time = end - start

                all_execution_times.append(execution_time)
                if advanced_verb:
                    print(
                        f'Test №{i} | '
                        f'Queries count: {end_queries - start_queries} | '
                        f'Execution time: {execution_time:.2f}s'
                    )

            connection.force_debug_cursor = force_debug_cursor
            request_started.connect(reset_queries)
            final_queries = len(connection.queries_log)

            if queries:
                for query in connection.queries[initial_queries:final_queries]:
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
        super().__init__(connection)

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
