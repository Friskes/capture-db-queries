from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, NamedTuple

from django.utils.regex_helper import _lazy_re_compile

from .timers import ContextTimer

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.backends.base.operations import BaseDatabaseOperations
    from django.db.backends.utils import CursorWrapper

    from .types import Explain, QueriesLog, Query


class BaseExecutionWrapper:
    def __init__(self, queries_log: QueriesLog, *args: Any, **kwargs: Any) -> None:
        self.timer = ContextTimer()
        self.queries_log = queries_log

    def __call__(
        self,
        execute: Callable[..., CursorWrapper | None],
        sql: str,
        params: tuple[Any, ...],
        many: bool,
        context: dict[str, Any],
    ) -> CursorWrapper | None:
        """
        Выполняет оригинальный запрос
        """
        with self.timer as timer:
            try:
                result = execute(sql, params, many, context)
            except Exception as exc:
                print('Что-то пошло не так:', exc)
                return None

        # from django.db.backends.utils import CursorDebugWrapper(connection.cursor(), connection)
        query: Query = {'sql': sql, 'time': timer.execution_time}
        query = self.update_query(query)
        self.queries_log.append(query)

        return result

    def update_query(self, query: Query) -> Query:
        return query


class ExplainExecutionWrapper(BaseExecutionWrapper):
    """
    Класс для вызова EXPLAIN на каждом SELECT-запросе.
    С сохранением полной функциональности метода QuerySet.explain().

    https://docs.djangoproject.com/en/5.1/topics/db/instrumentation/#connection-execute-wrapper
    https://docs.djangoproject.com/en/5.1/ref/models/querysets/#explain
    """

    # Inspired from
    # https://www.postgresql.org/docs/current/sql-syntax-lexical.html#SQL-SYNTAX-IDENTIFIERS
    EXPLAIN_OPTIONS_PATTERN = _lazy_re_compile(r'[\w\-]+')

    class ExplainInfo(NamedTuple):
        format: str | None
        options: dict[str, Any]

    def __init__(
        self,
        queries_log: QueriesLog,
        connection: BaseDatabaseWrapper,
        explain_opts: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        # # https://www.postgresql.org/docs/current/sql-explain.html
        super().__init__(queries_log, *args, **kwargs)
        self.connection = connection
        self.explain_info = self.build_explain_info(**explain_opts)

    def __call__(
        self,
        execute: Callable[..., CursorWrapper | None],
        sql: str,
        params: tuple[Any, ...],
        many: bool,
        context: dict[str, Any],
    ) -> CursorWrapper | None:
        self.__explain = self._execute_explain(sql, params, many)
        return super().__call__(execute, sql, params, many, context)

    def update_query(self, query: Query) -> Query:
        if self.__explain is not None:
            query.update({'explain': self.__explain})
        return query

    def _execute_explain(self, sql: str, params: tuple[Any, ...], many: bool) -> str | None:
        # Проверяем, является ли запрос SELECT-запросом
        if not sql.strip().lower().startswith('select'):
            return None

        # Обёртки для конкретных бд хранятся по адресам:
        # django.db.backends.sqlite3.operations.DatabaseOperations
        # django.db.backends.postgresql.operations.DatabaseOperations
        db_operations: BaseDatabaseOperations = self.connection.ops

        explain_query = db_operations.explain_query_prefix(
            self.explain_info.format, **self.explain_info.options
        )
        explain_query = f'{explain_query} {sql}'

        try:
            raw_explain = self.__execute(explain_query, params, many)
        except Exception as exc:
            print('Что-то пошло не так:', exc)
            return None
        else:
            return '\n'.join(self.format_explain(raw_explain))

    def __execute(self, explain_query: str, params: tuple[Any, ...], many: bool) -> Explain:
        with self.connection.cursor() as cursor:
            # нельзя вызывать execute или executemany
            # который вызывает внутри себя обёртку,
            # потому что это приведёт к дублированию вызова,
            # и вызовет __call__ текущей обёртки

            # данные запросы идут в обход обёрток
            if many:
                cursor._executemany(explain_query, params)
            else:
                cursor._execute(explain_query, params)

            return cursor.fetchall()

    def build_explain_info(self, *, format: str | None = None, **options: dict[str, Any]) -> ExplainInfo:  # noqa: A002
        """
        Runs an EXPLAIN on the SQL query this QuerySet would perform, and
        returns the results.
        """
        for option_name in options:
            if not self.EXPLAIN_OPTIONS_PATTERN.fullmatch(option_name) or '--' in option_name:
                raise ValueError(f'Invalid option name: {option_name!r}.')
        return self.ExplainInfo(format, options)

    def format_explain(self, result: Explain) -> Generator[str, None, None]:
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
