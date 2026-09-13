from __future__ import annotations

import functools
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def memoize(fn: F) -> F:
    cache: dict[tuple, object] = {}

    @functools.wraps(fn)
    def wrapper(*args):
        if args in cache:
            return cache[args]
        result = fn(*args)
        cache[args] = result
        return result
    wrapper.cache_clear = cache.clear
    wrapper.cache_info = lambda: {"size": len(cache)}

    return wrapper
