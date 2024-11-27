from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

import pytest
from src.capture_db_queries.dtos import IterationPrintDTO, SeveralPrintDTO, SinglePrintDTO
from src.capture_db_queries.printers import PrinterSql

from tests.conftest import intercept_output_ctx, skip_colorize_sql

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.capture_db_queries.types import QueriesLog


@pytest.mark.django_db(transaction=True)
class TestPrinter:
    """"""

    def setup_method(self, method: Callable[..., Any]) -> None:
        self.skip_colorize_sql = skip_colorize_sql()
        self.skip_colorize_sql.__enter__()

        queries_log: QueriesLog = deque(
            [
                {
                    'sql': 'SELECT "tests_reporter"."id", "tests_reporter"."full_name" '
                    'FROM "tests_reporter" WHERE "tests_reporter"."id" = %s',
                    'time': 0.09399999992456287,
                },
                {
                    'sql': 'SELECT "tests_article"."id", "tests_article"."pub_date", '
                    '"tests_article"."headline", "tests_article"."content", "tests_article"."reporter_id" '  # noqa: E501
                    'FROM "tests_article" WHERE "tests_article"."id" = %s',
                    'time': 0.10900000005494803,
                },
            ],
            maxlen=9000,
        )
        self.queries_log_output = (
            '\n\n№[1] time=[0.094000]\nSELECT "tests_reporter"."id",\n       '
            '"tests_reporter"."full_name"\n  FROM "tests_reporter"\n '
            'WHERE "tests_reporter"."id" = %s\n\n\n№[2] time=[0.109000]\nSELECT "tests_article"."id",\n       '  # noqa: E501
            '"tests_article"."pub_date",\n       '
            '"tests_article"."headline",\n       '
            '"tests_article"."content",\n       '
            '"tests_article"."reporter_id"\n  '
            'FROM "tests_article"\n WHERE "tests_article"."id" = %s\n\n\n'
        )

        self.assert_msg = '4 not less than or equal to 2 queries'
        self.iter_output = '\n\nTest №1 | Queries count: 2 | Execution time: 0.743167s\n'
        self.single_output = (
            '\nQueries count: 2  |  Execution time: 0.743167s  |  Vendor: fake_vendor\n\n'
        )
        self.several_output = (
            '\n\nTests count: 1  |  Total queries count: 2  |  Total execution time: 1.48633s  |  '
            'Median time one test is: 0.743167s  |  Vendor: fake_vendor\n\n'
        )

        self.iter_dto = IterationPrintDTO(
            current_iteration=1, queries_count_per_iter=2, execution_time_per_iter=0.74316726722147
        )
        self.single_dto = SinglePrintDTO(
            queries_count=2, queries_log=queries_log, execution_time_per_iter=0.74316726722147
        )
        self.several_dto = SeveralPrintDTO(
            queries_count=2,
            queries_log=queries_log,
            current_iteration=1,
            all_execution_times=[0.74316726722147, 0.74316726722147],
        )

    def teardown_method(self, method: Callable[..., Any]) -> None:
        self.skip_colorize_sql.__exit__(None, None, None)

    @staticmethod
    def build_printer(**kwargs: Any) -> PrinterSql:
        default_printer_kwargs: dict[str, Any] = {}
        return PrinterSql(**dict(default_printer_kwargs, **kwargs))

    def test_assert_msg(self) -> None:
        obj = self.build_printer(vendor='fake_vendor', assert_q_count=2)
        data = obj.assert_msg(queries_count=4)
        assert data == self.assert_msg, repr(data)

    def test_param__verbose(self) -> None:
        with intercept_output_ctx() as ctx:
            obj = self.build_printer(
                vendor='fake_vendor', verbose=False, advanced_verb=False, queries=False
            )
            obj.print_single_sql(self.single_dto)
            output = ctx.getvalue()
            assert output == '', repr(output)

        with intercept_output_ctx() as ctx:
            obj = self.build_printer(
                vendor='fake_vendor', verbose=True, advanced_verb=False, queries=False
            )
            obj.print_single_sql(self.single_dto)
            output = ctx.getvalue()
            assert output == self.single_output, repr(output)

        with intercept_output_ctx() as ctx:
            obj = self.build_printer(
                vendor='fake_vendor', verbose=False, advanced_verb=False, queries=False
            )
            obj.print_several_sql(self.several_dto)
            output = ctx.getvalue()
            assert output == '', repr(output)

        with intercept_output_ctx() as ctx:
            obj = self.build_printer(
                vendor='fake_vendor', verbose=True, advanced_verb=False, queries=False
            )
            obj.print_several_sql(self.several_dto)
            output = ctx.getvalue()
            assert output == self.several_output, repr(output)

    def test_param__advanced_verb(self) -> None:
        with intercept_output_ctx() as ctx:
            obj = self.build_printer(
                vendor='fake_vendor', verbose=False, advanced_verb=False, queries=False
            )
            obj.iteration_print(self.iter_dto)
            output = ctx.getvalue()
            assert output == '', repr(output)

        with intercept_output_ctx() as ctx:
            obj = self.build_printer(
                vendor='fake_vendor', verbose=False, advanced_verb=True, queries=False
            )
            obj.iteration_print(self.iter_dto)
            output = ctx.getvalue()
            assert output == self.iter_output, repr(output)

    def test_param__queries(self) -> None:
        with intercept_output_ctx() as ctx:
            obj = self.build_printer(
                vendor='fake_vendor', verbose=False, advanced_verb=False, queries=False
            )
            obj.print_single_sql(self.single_dto)
            output = ctx.getvalue()
            assert output == '', repr(output)

        with intercept_output_ctx() as ctx:
            obj = self.build_printer(
                vendor='fake_vendor', verbose=False, advanced_verb=False, queries=True
            )
            obj.print_single_sql(self.single_dto)
            output = ctx.getvalue()
            assert output == self.queries_log_output, repr(output)

        with intercept_output_ctx() as ctx:
            obj = self.build_printer(
                vendor='fake_vendor', verbose=False, advanced_verb=False, queries=False
            )
            obj.print_several_sql(self.several_dto)
            output = ctx.getvalue()
            assert output == '', repr(output)

        with intercept_output_ctx() as ctx:
            obj = self.build_printer(
                vendor='fake_vendor', verbose=False, advanced_verb=False, queries=True
            )
            obj.print_several_sql(self.several_dto)
            output = ctx.getvalue()
            assert output == self.queries_log_output, repr(output)
