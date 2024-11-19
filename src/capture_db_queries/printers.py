from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any
from unittest.util import safe_repr

import sqlparse

if TYPE_CHECKING:
    from .dtos import IterationPrintDTO, SeveralPrintDTO, SinglePrintDTO

_EXCLUDE = True


class AbcPrinter(abc.ABC):
    @abc.abstractmethod
    def _print_sql(self, template: str, **format_kwargs: Any) -> str:
        raise NotImplementedError

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
    def assert_msg(self, final_queries: int) -> str:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def beautiful_sql(self) -> str:
        raise NotImplementedError


# TODO: мб каких то дандер методов подкинуть в принтер для удобства чего либо
class PrinterSql(AbcPrinter):
    EXCLUDE = ('BEGIN', 'COMMIT', 'ROLLBACK')

    single_sql_template = (
        'Queries count: {final_queries}  |  Execution time: {execution_time}s  |  Vendor: {vendor}'
    )
    several_sql_template = (
        'Tests count: {current_iteration}  |  '
        'Total queries count: {final_queries}  |  '
        'Total execution time: {sum_all_execution_times}s  |  '
        'Median time one test is: {median_all_execution_times}s  |  '
        'Vendor: {vendor}'
    )
    iteration_sql_template = (
        'Test №{current_iteration} | '
        'Queries count: {queries_count} | '
        'Execution time: {execution_time}s'
    )
    assert_msg_template = '{final_queries} not less than or equal to {assert_q_count} queries'

    captured_queries_template = (
        '\n{captured_queries_count} queries executed on {vendor}, '
        '{assert_q_count} expected\nCaptured queries were:\n\n{sql}\n'
    )

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

    def _print_sql(self, template: str, **format_kwargs: Any) -> str:
        sql = ''
        if self.queries:
            print(self.beautiful_sql)

        if self.verbose:
            sql = template.format(**format_kwargs, vendor=self.vendor)
            print(sql)
        return sql

    def print_single_sql(self, dto: SinglePrintDTO) -> str:
        self.dto = dto
        return self._print_sql(
            self.single_sql_template, final_queries=dto.final_queries, execution_time=dto.execution_time
        )

    def print_several_sql(self, dto: SeveralPrintDTO) -> str:
        self.dto = dto  # type: ignore[assignment]
        format_kwargs: dict[str, str | int | float] = {
            'final_queries': dto.final_queries,
            'current_iteration': dto.current_iteration,
        }
        if dto.all_execution_times:
            format_kwargs.update(
                {
                    'sum_all_execution_times': dto.sum_all_execution_times,
                    'median_all_execution_times': dto.median_all_execution_times,
                }
            )
        return self._print_sql(self.several_sql_template, **format_kwargs)

    def iteration_print(self, dto: IterationPrintDTO) -> None:
        self.dto = dto  # type: ignore[assignment]
        if self.advanced_verb:
            print(
                self.iteration_sql_template.format(
                    current_iteration=dto.current_iteration,
                    queries_count=dto.queries_count,
                    execution_time=dto.execution_time,
                )
            )

    def assert_msg(self, final_queries: int) -> str:
        return self.assert_msg_template.format(
            final_queries=safe_repr(final_queries), assert_q_count=safe_repr(self.assert_q_count)
        )

    @property
    def beautiful_sql(self) -> str:
        if _EXCLUDE:
            filtered_queries = [
                q for q in self.dto.captured_queries if q['sql'].upper() not in self.EXCLUDE
            ]
        else:
            filtered_queries = self.dto.captured_queries

        # sqlparse.formatter.validate_options  # подсказка
        formatted_queries = [
            {
                'sql': sqlparse.format(
                    sql=query['sql'],
                    encoding='utf-8',
                    output_format='sql',
                    reindent_aligned=True,
                ),
                'time': query['time'],
            }
            for query in filtered_queries
        ]
        sql = '\n\n\n'.join(
            f'№[{ordinal_num}] ⧖[{query["time"]}]\n{query["sql"]}'
            for ordinal_num, query in enumerate(formatted_queries, start=1)
        )
        return self.captured_queries_template.format(
            captured_queries_count=len(self.dto.captured_queries),
            vendor=self.vendor,
            assert_q_count=self.assert_q_count,
            sql=sql,
        )
