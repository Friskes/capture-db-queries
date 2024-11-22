from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import QueriesLog


@dataclass(frozen=True)
class BasePrintDTO:
    queries_count: int
    queries_log: QueriesLog


@dataclass(frozen=True)
class SinglePrintDTO(BasePrintDTO):
    execution_time_per_iter: float


@dataclass(frozen=True)
class SeveralPrintDTO(BasePrintDTO):
    current_iteration: int
    all_execution_times: list[float]

    @property
    def sum_all_execution_times(self) -> float:
        return sum(self.all_execution_times)

    @property
    def median_all_execution_times(self) -> float:
        return statistics.median(self.all_execution_times)


@dataclass(frozen=True)
class IterationPrintDTO:
    current_iteration: int
    queries_count_per_iter: int
    execution_time_per_iter: float
