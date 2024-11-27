from __future__ import annotations

import abc
from collections import deque
from typing import TYPE_CHECKING, Any
from unittest.util import safe_repr

import pygments.formatters
import pygments.lexers
import sqlparse

if TYPE_CHECKING:
    from .dtos import IterationPrintDTO, SeveralPrintDTO, SinglePrintDTO
    from .types import QueriesLog

_EXCLUDE = True


class AbcPrinter(abc.ABC):
    def __init__(
        self,
        vendor: str,
        assert_q_count: int | None = None,
        verbose: bool = True,
        advanced_verb: bool = False,
        queries: bool = False,
    ) -> None:
        self.vendor = vendor
        self.assert_q_count = assert_q_count
        self.verbose = verbose
        self.advanced_verb = advanced_verb
        self.queries = queries

    def print_sql(self, template: str, queries_log: QueriesLog, **format_kwargs: Any) -> str:
        if self.queries:
            print(self._beautiful_queries(queries_log))

        if self.verbose:
            data = template.format(**format_kwargs, vendor=self.vendor)
            print(data)
            return data
        return ''

    def _beautiful_queries(self, queries_log: QueriesLog) -> str:
        """"""
        filtered_queries = self.filter_queries(queries_log)

        formatted_queries = self.format_sql(filtered_queries)

        formatted_queries = self.colorize_sql(formatted_queries)

        formatted_queries = self.format_explain(formatted_queries)

        return self.build_output_string(formatted_queries)

    @abc.abstractmethod
    def print_single_sql(self, dto: SinglePrintDTO) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def print_several_sql(self, dto: SeveralPrintDTO) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def iteration_print(self, dto: IterationPrintDTO) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def assert_msg(self, queries_count: int) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def filter_queries(self, queries_log: QueriesLog) -> QueriesLog:
        raise NotImplementedError

    @abc.abstractmethod
    def format_sql(self, queries_log: QueriesLog) -> QueriesLog:
        raise NotImplementedError

    @abc.abstractmethod
    def colorize_sql(self, queries_log: QueriesLog) -> QueriesLog:
        raise NotImplementedError

    @abc.abstractmethod
    def format_explain(self, queries_log: QueriesLog) -> QueriesLog:
        raise NotImplementedError

    @abc.abstractmethod
    def build_output_string(self, queries_log: QueriesLog) -> str:
        raise NotImplementedError


class PrinterSql(AbcPrinter):
    EXCLUDE = ('BEGIN', 'COMMIT', 'ROLLBACK')

    single_sql_template = (
        '\nQueries count: {queries_count}  |  '
        'Execution time: {execution_time_per_iter:.6f}s  |  Vendor: {vendor}\n'
    )
    several_sql_template = (
        'Tests count: {current_iteration}  |  '
        'Total queries count: {queries_count}  |  '
        'Total execution time: {sum_all_execution_times:.5f}s  |  '
        'Median time one test is: {median_all_execution_times:.6f}s  |  '
        'Vendor: {vendor}\n'
    )
    iteration_sql_template = (
        'Test №{current_iteration} | '
        'Queries count: {queries_count_per_iter} | '
        'Execution time: {execution_time_per_iter:.6f}s'
    )
    assert_msg_template = '{queries_count} not less than or equal to {assert_q_count} queries'

    sql_template = '№[{ordinal_num}] time=[{time:.6f}]{explain}\n{sql}'

    def print_single_sql(self, dto: SinglePrintDTO) -> str:
        return self.print_sql(
            self.single_sql_template,
            dto.queries_log,
            queries_count=dto.queries_count,
            execution_time_per_iter=dto.execution_time_per_iter,
        )

    def print_several_sql(self, dto: SeveralPrintDTO) -> str:
        format_kwargs: dict[str, int | float] = {
            'queries_count': dto.queries_count,
            'current_iteration': dto.current_iteration,
            'sum_all_execution_times': dto.sum_all_execution_times,
            'median_all_execution_times': dto.median_all_execution_times,
        }
        if self.verbose and not self.advanced_verb and not self.queries:
            print('\n')
        return self.print_sql(self.several_sql_template, dto.queries_log, **format_kwargs)

    def iteration_print(self, dto: IterationPrintDTO) -> None:
        if self.advanced_verb:
            if dto.current_iteration == 1:
                print('\n')
            print(
                self.iteration_sql_template.format(
                    current_iteration=dto.current_iteration,
                    queries_count_per_iter=dto.queries_count_per_iter,
                    execution_time_per_iter=dto.execution_time_per_iter,
                )
            )

    def assert_msg(self, queries_count: int) -> str:
        return self.assert_msg_template.format(
            queries_count=safe_repr(queries_count), assert_q_count=safe_repr(self.assert_q_count)
        )

    def filter_queries(self, queries_log: QueriesLog) -> QueriesLog:
        if _EXCLUDE:
            return deque(query for query in queries_log if query['sql'].upper() not in self.EXCLUDE)
        return queries_log

    def format_sql(self, queries_log: QueriesLog) -> QueriesLog:
        formatted_queries = queries_log.copy()
        for query in formatted_queries:
            # A hint on the parameters: sqlparse.formatter.validate_options
            query['sql'] = sqlparse.format(
                sql=query['sql'],
                encoding='utf-8',
                output_format='sql',
                reindent_aligned=True,
            )
        return formatted_queries

    def colorize_sql(self, queries_log: QueriesLog) -> QueriesLog:
        for query in queries_log:
            colorized_sql = pygments.highlight(
                query['sql'],
                pygments.lexers.get_lexer_by_name('sql'),
                pygments.formatters.TerminalFormatter(),
            )
            query['sql'] = colorized_sql
        return queries_log

    def format_explain(self, queries_log: QueriesLog) -> QueriesLog:
        for query in queries_log:
            if 'explain' in query:
                explain_count = len(query['explain'].split('\n'))
                if explain_count > 1:
                    explain = f' explain=[\n{query["explain"]}\n]'
                else:
                    explain = f' explain=[{query["explain"]}]'
                query['explain'] = explain
        return queries_log

    def build_output_string(self, queries_log: QueriesLog) -> str:
        formatted_queries = '\n\n\n'.join(
            self.sql_template.format(
                ordinal_num=ordinal_num,
                time=query['time'],
                sql=query['sql'],
                explain=query.get('explain', ''),
            )
            for ordinal_num, query in enumerate(queries_log, start=1)
        )
        return f'\n\n{formatted_queries}\n\n'
