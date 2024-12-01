from __future__ import annotations

import json
import time
import traceback
from collections import deque
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, NamedTuple

from django.utils.regex_helper import _lazy_re_compile

from ._logging import log
from .dtos import ExpQuery, Query
from .timers import ContextTimer

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.backends.base.operations import BaseDatabaseOperations
    from django.db.backends.utils import CursorWrapper

    from .types import Explain, QueryDataT


class BaseExecutionWrapper:
    def __init__(self, connection: BaseDatabaseWrapper, *args: Any, **kwargs: Any) -> None:
        log.debug('')

        self.connection = connection
        self.queries_log: deque[Query | ExpQuery] = deque(maxlen=self.connection.queries_limit)
        self.timer = ContextTimer(time.perf_counter)

        # Wrappers for specific databases are stored at addresses:
        # django.db.backends.sqlite3.operations.DatabaseOperations
        # django.db.backends.postgresql.operations.DatabaseOperations
        self.db_operations: BaseDatabaseOperations = self.connection.ops

    def __call__(
        self,
        execute: Callable[..., CursorWrapper],
        sql: str,
        params: tuple[Any, ...],
        many: bool,
        context: dict[str, Any],
    ) -> CursorWrapper | None:
        """
        Executes the original SQL request.
        """
        with self.timer as timer:
            try:
                result = execute(sql, params, many, context)
            except Exception as exc:
                print('Something went wrong:', exc)
                return None

        if not many:
            # Get filled SQL with params
            sql = self.db_operations.last_executed_query(context['cursor'], sql, params)

        query_data: QueryDataT = {'sql': sql, 'time': timer.execution_time}
        query: Query | ExpQuery = self.update_query(query_data)
        self.queries_log.append(query)

        log.trace('Location of SQL Call:\n%s', ''.join(traceback.format_stack()))

        return result

    @contextmanager
    def wrap_reqs_in_wrapper(self) -> Generator[None, None, CursorWrapper]:
        """Wraps all database requests in a wrapper."""
        log.debug('')

        # https://docs.djangoproject.com/en/5.1/topics/db/instrumentation/#connection-execute-wrapper
        with self.connection.execute_wrapper(self):
            yield

    def update_query(self, query_data: QueryDataT) -> Query:
        return Query(**query_data)


class ExplainExecutionWrapper(BaseExecutionWrapper):
    """
    A class for calling EXPLAIN before each original SELECT request.
    While maintaining the full functionality of the Query Set.explain() method.

    The EXPLAIN call is not fixed in any way and does not affect the measurement results.

    https://docs.djangoproject.com/en/5.1/ref/models/querysets/#explain
    https://www.postgresql.org/docs/current/sql-explain.html
    """

    # Inspired from
    # https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS
    EXPLAIN_OPTIONS_PATTERN = _lazy_re_compile(r'[\w\-]+')

    class ExplainInfo(NamedTuple):
        format: str | None
        options: dict[str, Any]

    def __init__(
        self,
        connection: BaseDatabaseWrapper,
        explain_opts: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(connection, *args, **kwargs)
        self.explain_info = self.build_explain_info(**explain_opts)

    def __call__(
        self,
        execute: Callable[..., CursorWrapper],
        sql: str,
        params: tuple[Any, ...],
        many: bool,
        context: dict[str, Any],
    ) -> CursorWrapper | None:
        self.explain_data = self._execute_explain(sql, params, many)
        return super().__call__(execute, sql, params, many, context)

    def update_query(self, query_data: QueryDataT) -> ExpQuery:
        return ExpQuery(**query_data, explain=self.explain_data)

    def _execute_explain(self, sql: str, params: tuple[Any, ...], many: bool) -> str:
        # Checking whether the request is a SELECT request
        if not sql.strip().lower().startswith('select'):
            return ''

        explain_query = self.db_operations.explain_query_prefix(
            self.explain_info.format, **self.explain_info.options
        )
        explain_query = f'{explain_query} {sql}'

        try:
            raw_explain = self.__execute_explain(explain_query, params, many)
        except Exception as exc:
            print('Something went wrong:', exc)
            return ''
        else:
            return '\n'.join(self.format_explain(raw_explain))

    def __execute_explain(self, explain_query: str, params: tuple[Any, ...], many: bool) -> Explain:
        with self.connection.cursor() as cursor:
            # you cannot call execute or executemany
            # which invokes a wrapper inside itself,
            # because it will result in duplicate call,
            # and will call __call__ of the current wrapper

            # these requests bypass wrappers
            if many:
                cursor._executemany(explain_query, params)
            else:
                cursor._execute(explain_query, params)

            return cursor.fetchall()

    def build_explain_info(self, *, format: str | None = None, **options: dict[str, Any]) -> ExplainInfo:  # noqa: A002
        """
        Validates explain options and build ExplainInfo object.
        """
        for option_name in options:
            if not self.EXPLAIN_OPTIONS_PATTERN.fullmatch(option_name) or '--' in option_name:
                raise ValueError(f'Invalid option name: {option_name!r}.')
        return self.ExplainInfo(format, options)

    def format_explain(self, result: Explain) -> Generator[str, None, None]:
        """
        Splits the explain tuple into its components and collects the final explain string from them.
        """
        nested_result = [list(result)]
        # Some backends return 1 item tuples with strings, and others return
        # tuples with integers and strings. Flatten them out into strings.
        format_ = self.explain_info.format
        output_formatter = json.dumps if format_ and format_.lower() == 'json' else str
        for row in nested_result[0]:
            if not isinstance(row, str):
                yield ' '.join(output_formatter(c) for c in row)
            else:
                yield row
