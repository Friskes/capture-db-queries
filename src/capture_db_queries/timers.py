from __future__ import annotations

import time
from typing import TYPE_CHECKING

from typing_extensions import Self  # noqa: UP035

if TYPE_CHECKING:
    from types import TracebackType


class ContextTimer:
    def __init__(self) -> None:
        self.execution_time = 0.0
        self.all_execution_times: list[float] = []
        self.exec_times_per_iter: list[float] = []

    @property
    def execution_time_per_iter(self) -> float:
        return sum(self.exec_times_per_iter)

    @property
    def queries_count_per_iter(self) -> int:
        return len(self.exec_times_per_iter)

    def __enter__(self) -> Self:
        self._start = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            return

        self._end = time.monotonic()
        self.execution_time = self._end - self._start
        self.all_execution_times.append(self.execution_time)
        self.exec_times_per_iter.append(self.execution_time)

    def clear_exec_times_per_iter(self) -> None:
        self.exec_times_per_iter.clear()