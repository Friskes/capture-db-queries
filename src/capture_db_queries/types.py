from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Any, TypeVar, Union

# https://mypy.readthedocs.io/en/stable/generics.html#decorator-factories
DecoratedCallable = TypeVar('DecoratedCallable', bound=Callable[..., Any])

T = TypeVar('T')

Query = dict[str, Union[str, float]]  # noqa: UP007

QueriesLog = deque[Query]

Explain = list[tuple[Union[int, str], ...]]  # noqa: UP007
