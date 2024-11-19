from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class BasePrintDTO:
    final_queries: int
    captured_queries: list[dict[str, str]]


@dataclass(frozen=True)
class SinglePrintDTO(BasePrintDTO):
    _execution_time: float

    @property
    def execution_time(self) -> str:
        return f'{self._execution_time:.3f}'


@dataclass(frozen=True)
class SeveralPrintDTO(BasePrintDTO):
    current_iteration: int
    all_execution_times: list[float]

    @property
    def sum_all_execution_times(self) -> str:
        return f'{sum(self.all_execution_times):.2f}'

    @property
    def median_all_execution_times(self) -> str:
        return f'{statistics.median(self.all_execution_times):.3f}'


@dataclass(frozen=True)
class IterationPrintDTO:
    current_iteration: int
    queries_count: int
    _execution_time: float

    @property
    def execution_time(self) -> str:
        return f'{self._execution_time:.2f}'
