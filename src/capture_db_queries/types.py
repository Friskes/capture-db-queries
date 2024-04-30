from __future__ import annotations

from typing import Any, Callable, TypeVar  # noqa: UP035

# https://mypy.readthedocs.io/en/stable/generics.html#decorator-factories
DecoratedCallable = TypeVar('DecoratedCallable', bound=Callable[..., Any])

T = TypeVar('T')
