from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any
from unittest.util import safe_repr

from django.utils.module_loading import import_string

from .handlers import IHandler
from .settings import PRINTER_HANDLERS

if TYPE_CHECKING:
    from collections.abc import Callable

    from .dtos import IterationPrintDTO, SeveralPrintDTO, SinglePrintDTO
    from .types import QueriesLog


class AbcPrinter(abc.ABC):
    assert_msg_template = '{queries_count} not less than or equal to {assert_q_count} queries'

    def __init__(
        self,
        vendor: str,
        assert_q_count: int | None = None,
        verbose: bool = True,
        advanced_verb: bool = False,
        queries: bool = False,
        log_func: Callable[..., None] = print,
    ) -> None:
        self.vendor = vendor
        self.assert_q_count = assert_q_count
        self.verbose = verbose
        self.advanced_verb = advanced_verb
        self.queries = queries
        self.log = log_func

    def print_sql(self, template: str, queries_log: QueriesLog, **format_kwargs: Any) -> str:
        if self.queries:
            self.log(self._beautiful_queries(queries_log))

        if self.verbose:
            data = template.format(**format_kwargs, vendor=self.vendor)
            self.log(data)
            return data
        return ''

    def _beautiful_queries(self, queries_log: QueriesLog) -> str:
        """"""
        for handler_path in PRINTER_HANDLERS:
            #
            handler = import_string(handler_path)
            if not issubclass(handler, IHandler):
                raise TypeError('Handler must be subclass: "capture_db_queries.handlers.IHandler"')

            queries_log = handler().handle(queries_log)

        return self.build_output_string(queries_log)

    def assert_msg(self, queries_count: int) -> str:
        return self.assert_msg_template.format(
            queries_count=safe_repr(queries_count), assert_q_count=safe_repr(self.assert_q_count)
        )

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
    def build_output_string(self, queries_log: QueriesLog) -> str:
        raise NotImplementedError


class PrinterSql(AbcPrinter):
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
            self.log('\n')
        return self.print_sql(self.several_sql_template, dto.queries_log, **format_kwargs)

    def iteration_print(self, dto: IterationPrintDTO) -> None:
        if self.advanced_verb:
            if dto.current_iteration == 1:
                self.log('\n')
            self.log(
                self.iteration_sql_template.format(
                    current_iteration=dto.current_iteration,
                    queries_count_per_iter=dto.queries_count_per_iter,
                    execution_time_per_iter=dto.execution_time_per_iter,
                )
            )

    def build_output_string(self, queries_log: QueriesLog) -> str:
        formatted_queries = '\n\n\n'.join(
            self.sql_template.format(
                ordinal_num=ordinal_num,
                time=query.time,
                sql=query.sql,
                explain=getattr(query, 'explain', ''),
            )
            for ordinal_num, query in enumerate(queries_log, start=1)
        )
        return f'\n\n{formatted_queries}\n\n'
