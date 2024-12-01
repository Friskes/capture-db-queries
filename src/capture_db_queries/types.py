# ruff: noqa: UP007, UP040

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Any, TypeVar, Union

from typing_extensions import TypeAlias

from .dtos import ExpQuery, Query

# https://mypy.readthedocs.io/en/stable/generics.html#decorator-factories
DecoratedCallable = TypeVar('DecoratedCallable', bound=Callable[..., Any])

T = TypeVar('T')

QueryDataT: TypeAlias = Union[dict[str, str], dict[str, float]]

QueriesLog: TypeAlias = Union[deque[Query], deque[ExpQuery]]

Explain: TypeAlias = list[tuple[Union[int, str], ...]]
