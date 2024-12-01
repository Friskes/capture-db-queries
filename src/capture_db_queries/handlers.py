from __future__ import annotations

import abc
from collections import deque
from typing import TYPE_CHECKING

import pygments.formatters
import pygments.lexers
import sqlparse

if TYPE_CHECKING:
    from .types import QueriesLog


class IHandler(abc.ABC):
    @abc.abstractmethod
    def handle(self, queries_log: QueriesLog) -> QueriesLog:
        raise NotImplementedError


class FilterQueriesHandler(IHandler):
    EXCLUDE_KEYWORDS = True
    EXCLUDE = ('BEGIN', 'COMMIT', 'ROLLBACK')

    def handle(self, queries_log: QueriesLog) -> QueriesLog:
        if self.EXCLUDE_KEYWORDS:
            queries_log = deque(query for query in queries_log if query.sql.upper() not in self.EXCLUDE)
        return queries_log


class FormatQueriesHandler(IHandler):
    def handle(self, queries_log: QueriesLog) -> QueriesLog:
        for query in queries_log:
            # A hint on the parameters: sqlparse.formatter.validate_options
            query.sql = sqlparse.format(
                sql=query.sql,
                encoding='utf-8',
                output_format='sql',
                reindent_aligned=True,
            )
        return queries_log


class ColorizeSqlHandler(IHandler):
    def handle(self, queries_log: QueriesLog) -> QueriesLog:
        for query in queries_log:
            colorized_sql = pygments.highlight(
                query.sql,
                pygments.lexers.get_lexer_by_name('sql'),
                pygments.formatters.TerminalFormatter(),
            )
            query.sql = colorized_sql
        return queries_log


class FormatExplainHandler(IHandler):
    def handle(self, queries_log: QueriesLog) -> QueriesLog:
        for query in queries_log:
            if hasattr(query, 'explain'):
                explain_count = len(query.explain.split('\n'))
                if explain_count > 1:
                    explain = f' explain=[\n{query.explain}\n]'
                else:
                    explain = f' explain=[{query.explain}]'
                query.explain = explain
        return queries_log
