from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

import pytest
from src.capture_db_queries.dtos import IterationPrintDTO, SeveralPrintDTO, SinglePrintDTO
from src.capture_db_queries.printers import PrinterSql

from tests.conftest import intercept_output_ctx

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.capture_db_queries.types import QueriesLog


@pytest.mark.django_db(transaction=True)
class TestPrinter:
    """"""

    def setup_method(self, method: Callable[..., Any]) -> None:
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
            '\n\n\n№[1] time=[0.094]\nSELECT "tests_reporter"."id",\n       '
            '"tests_reporter"."full_name"\n  FROM "tests_reporter"\n '
            'WHERE "tests_reporter"."id" = %s\n\n\n№[2] time=[0.109]\nSELECT "tests_article"."id",\n       '  # noqa: E501
            '"tests_article"."pub_date",\n       '
            '"tests_article"."headline",\n       '
            '"tests_article"."content",\n       '
            '"tests_article"."reporter_id"\n  '
            'FROM "tests_article"\n WHERE "tests_article"."id" = %s\n\n\n'
        )

        self.assert_msg = '4 not less than or equal to 2 queries'
        self.iter_output = 'Test №1 | Queries count: 2 | Execution time: 0.74s\n'
        self.single_output = 'Queries count: 2  |  Execution time: 0.743s  |  Vendor: fake_vendor\n'
        self.several_output = (
            'Tests count: 1  |  Total queries count: 2  |  '
            'Total execution time: 1.49s  |  Median time one test is: 0.743s  |  Vendor: fake_vendor\n'
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

    def test_assert_msg(self) -> None:
        obj = PrinterSql(vendor='fake_vendor', assert_q_count=2)
        data = obj.assert_msg(queries_count=4)
        assert data == self.assert_msg, repr(data)

    def test_param__verbose(self) -> None:
        with intercept_output_ctx() as ctx:
            obj = PrinterSql(vendor='fake_vendor', verbose=False, advanced_verb=False, queries=False)
            obj.print_single_sql(self.single_dto)
            output = ctx.getvalue()
            assert output == '', repr(output)

        with intercept_output_ctx() as ctx:
            obj = PrinterSql(vendor='fake_vendor', verbose=True, advanced_verb=False, queries=False)
            obj.print_single_sql(self.single_dto)
            output = ctx.getvalue()
            assert output == self.single_output, repr(output)

        with intercept_output_ctx() as ctx:
            obj = PrinterSql(vendor='fake_vendor', verbose=False, advanced_verb=False, queries=False)
            obj.print_several_sql(self.several_dto)
            output = ctx.getvalue()
            assert output == '', repr(output)

        with intercept_output_ctx() as ctx:
            obj = PrinterSql(vendor='fake_vendor', verbose=True, advanced_verb=False, queries=False)
            obj.print_several_sql(self.several_dto)
            output = ctx.getvalue()
            assert output == self.several_output, repr(output)

    def test_param__advanced_verb(self) -> None:
        with intercept_output_ctx() as ctx:
            obj = PrinterSql(vendor='fake_vendor', verbose=False, advanced_verb=False, queries=False)
            obj.iteration_print(self.iter_dto)
            output = ctx.getvalue()
            assert output == '', repr(output)

        with intercept_output_ctx() as ctx:
            obj = PrinterSql(vendor='fake_vendor', verbose=False, advanced_verb=True, queries=False)
            obj.iteration_print(self.iter_dto)
            output = ctx.getvalue()
            assert output == self.iter_output, repr(output)

    def test_param__queries(self) -> None:
        with intercept_output_ctx() as ctx:
            obj = PrinterSql(vendor='fake_vendor', verbose=False, advanced_verb=False, queries=False)
            obj.print_single_sql(self.single_dto)
            output = ctx.getvalue()
            assert output == '', repr(output)

        with intercept_output_ctx() as ctx:
            obj = PrinterSql(vendor='fake_vendor', verbose=False, advanced_verb=False, queries=True)
            obj.print_single_sql(self.single_dto)
            output = ctx.getvalue()
            assert output == self.queries_log_output, repr(output)

        with intercept_output_ctx() as ctx:
            obj = PrinterSql(vendor='fake_vendor', verbose=False, advanced_verb=False, queries=False)
            obj.print_several_sql(self.several_dto)
            output = ctx.getvalue()
            assert output == '', repr(output)

        with intercept_output_ctx() as ctx:
            obj = PrinterSql(vendor='fake_vendor', verbose=False, advanced_verb=False, queries=True)
            obj.print_several_sql(self.several_dto)
            output = ctx.getvalue()
            assert output == self.queries_log_output, repr(output)
