from __future__ import annotations

import abc
import functools
import statistics
import time
import warnings
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

from .dtos import IterationPrintDTO, SeveralPrintDTO, SinglePrintDTO
from .printers import PrinterSql

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from django.db.backends.base.base import BaseDatabaseWrapper

    from .types import DecoratedCallable, T

__all__ = ('CaptureQueries', 'capture_queries', 'ExtCaptureQueriesContext')

_DEBUG = False


class AbcCapture(abc.ABC):
    def __init__(
        self,
        assert_q_count: int | None = None,
        number_runs: int = 1,
        verbose: bool = True,
        advanced_verb: bool = False,
        auto_call_func: bool = False,
        queries: bool = False,
        connection: BaseDatabaseWrapper | None = None,
    ) -> None:
        self.debug = _DEBUG
        if self.debug:
            print('__init__')

        self.assert_q_count = assert_q_count
        self.number_runs = number_runs
        self.verbose = verbose
        self.advanced_verb = advanced_verb
        self.auto_call_func = auto_call_func
        self.queries = queries

        if connection is None:
            self.connection = db_connection
        else:
            self.connection = connection

        self.current_iteration = 0
        self.all_execution_times: list[float] = []
        self.final_queries = 0

        self.printer = PrinterSql(
            self.connection.vendor, assert_q_count, verbose, advanced_verb, queries
        )

    def __iter__(self) -> Self:
        if self.debug:
            print('__iter__')

        self._enter()
        return self

    def __getitem__(self, index: int) -> dict[str, str] | None:
        if self.debug:
            print('__getitem__')

        try:
            return self.captured_queries[index]
        except IndexError:
            return None

    def __len__(self) -> int:
        if self.debug:
            print('__len__')

        return len(self.captured_queries)

    def __enter__(self) -> Self:
        if self.debug:
            print('__enter__')

        if self.number_runs > 1:
            warnings.warn(
                f'При использовании: {type(self).__name__} как контекстного менеджера,'
                ' параметр number_runs > 1 не используеться.',
                category=FutureWarning,
                stacklevel=2,
            )
        self.start = time.perf_counter()
        self._enter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.debug:
            print('__exit__')

        self._exit()
        if exc_type is not None:
            return

        end = time.perf_counter()
        execution_time = end - self.start

        self.printer.print_single_sql(
            SinglePrintDTO(
                final_queries=self.final_queries,
                captured_queries=self.captured_queries,
                _execution_time=execution_time,
            )
        )
        self._assert_queries_count()

    def __next__(self) -> Self:
        if self.debug:
            print('__next__')

        execution_time, queries_count = self._run()
        if self.current_iteration > 0:
            self.all_execution_times.append(execution_time)

            self.printer.iteration_print(
                IterationPrintDTO(
                    current_iteration=self.current_iteration,
                    queries_count=queries_count,
                    _execution_time=execution_time,
                )
            )

        if self.current_iteration < self.number_runs:
            self.current_iteration += 1
            return self

        self._exit()
        self.printer.print_several_sql(
            SeveralPrintDTO(
                final_queries=self.final_queries,
                captured_queries=self.captured_queries,
                current_iteration=self.current_iteration,
                all_execution_times=self.all_execution_times,
            )
        )
        self._assert_queries_count()

        raise StopIteration

    def __call__(self, func: DecoratedCallable) -> DecoratedCallable | Any:
        if self.debug:
            print('__call__')

        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            return self._loop_counter(func, *args, **kwargs)

        if not self.auto_call_func:
            return wrapped
        return wrapped()  # автовызов декорируемой функции

    @abc.abstractmethod
    def _loop_counter(self, func: DecoratedCallable, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    @abc.abstractmethod
    def _run(self) -> tuple[float, int]:
        raise NotImplementedError

    @abc.abstractmethod
    def _enter(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def _exit(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def _assert_queries_count(self) -> None:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def captured_queries(self) -> list[dict[str, str]]:
        raise NotImplementedError


class CaptureQueries(AbcCapture):
    """
    Замеряет количество запросов к бд внутри тела тестовой функции,
    выводит подробную информацию о замерах,
    валидирует количество запросов.

    UseCases::

        for ctx in CaptureQueries(number_runs=2, advanced_verb=True):
            response = self.client.get(url)

        ИЛИ

        @CaptureQueries(number_runs=2, advanced_verb=True)
        def test_request():
            response = self.client.get(url)

        ИЛИ

        # NOTE: Контекстный менеджер with не поддерживает мульти запуск number_runs > 1
        with CaptureQueries(number_runs=1, advanced_verb=True) as ctx:
            response = self.client.get(url)

        >>> Test №1 | Queries count: 10 | Execution time: 0.04s
        >>> Test №2 | Queries count: 10 | Execution time: 0.04s
        >>> Tests count: 2  |  Total queries count: 20  |  Total execution time: 0.08s  |  Median time one test is: 0.041s  |  Vendor: sqlite

    - assert_q_count: Ожидаемое количество запросов к БД иначе
     "AssertionError: N not less than or equal to N queries"
    - number_runs: Количество запусков тестовой функции / тестового цикла
    - verbose: Отображение финальных результатов тестовых замеров
    - advanced_verb: Отображение результа каждого тестового замера
    - auto_call_func: Автозапуск декорируемой функции (без аргументов)
    - queries: Отображение сырых SQL запросов к БД
    - connection: Подключение к вашей базе данных, по умолчанию: django.db.connection

    Tests count: Общее количество тестовых замеров
    Total queries count: Общее количество запросов к БД внутри тестовой функции в рамках всех замеров
    Total execution time: Общее время выполнения запросов к БД
     внутри тестовой функции в рамках всех замеров
    Median time one test is: Среднее время выполнения одного тестового замера
    Vendor: Тестируемая база данных
    """  # noqa: E501

    def _loop_counter(self, func: DecoratedCallable, *args: Any, **kwargs: Any) -> Any:
        if self.debug:
            print('__loop_counter')

        self._enter()

        # замер состоит из number_runs прогонов подряд
        while self.current_iteration < self.number_runs:
            self.current_iteration += 1

            start_queries = len(self.connection.queries)
            start = time.perf_counter()

            return_value = func(*args, **kwargs)

            end = time.perf_counter()
            execution_time = end - start

            end_queries = len(self.connection.queries)
            queries_count = end_queries - start_queries

            self.all_execution_times.append(execution_time)

            self.printer.iteration_print(
                IterationPrintDTO(
                    current_iteration=self.current_iteration,
                    queries_count=queries_count,
                    _execution_time=execution_time,
                )
            )

        self._exit()
        self.printer.print_several_sql(
            SeveralPrintDTO(
                final_queries=self.final_queries,
                captured_queries=self.captured_queries,
                current_iteration=self.current_iteration,
                all_execution_times=self.all_execution_times,
            )
        )
        self._assert_queries_count()

        return return_value

    def _run(self) -> tuple[float, int]:
        if self.debug:
            print('__run')

        self.start_queries = len(self.connection.queries)
        self.start = time.perf_counter()

        if not hasattr(self, 'prev_start'):
            self.prev_start = self.start
            self.prev_queries = self.start_queries

            execution_time = 0.0
            queries_count = self.start_queries
        else:
            execution_time = self.start - self.prev_start
            self.prev_start = self.start

            queries_count = self.start_queries - self.prev_queries
            self.prev_queries = self.start_queries

        return execution_time, queries_count

    def _enter(self) -> None:
        if self.debug:
            print('__enter')

        self.force_debug_cursor = self.connection.force_debug_cursor
        self.connection.force_debug_cursor = True
        # Run any initialization queries if needed so that they won't be
        # included as part of the count.
        self.connection.ensure_connection()
        self.initial_queries = len(self.connection.queries_log)
        # self.final_queries = None
        request_started.disconnect(reset_queries)

    def _exit(self) -> None:
        if self.debug:
            print('__exit')

        self.connection.force_debug_cursor = self.force_debug_cursor
        request_started.connect(reset_queries)
        self.final_queries = len(self.connection.queries_log)

    def _assert_queries_count(self) -> None:
        if self.assert_q_count is not None:
            assert self.final_queries <= self.assert_q_count, self.printer.assert_msg(self.final_queries)

    @property
    def captured_queries(self) -> list[dict[str, str]]:
        return self.connection.queries[self.initial_queries : self.final_queries]


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
