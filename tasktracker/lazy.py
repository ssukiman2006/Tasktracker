from __future__ import annotations

import itertools
from datetime import date, timedelta
from typing import Callable, Generic, Iterable, Iterator, TypeVar

from tasktracker.models import Priority, Status, Task

T = TypeVar("T")
U = TypeVar("U")


def task_stream(n: int) -> Iterator[Task]:
    for i in range(n):
        yield Task(
            id=i,
            title=f"Task {i}",
            status=Status.TODO if i % 2 == 0 else Status.DONE,
            priority=Priority.LOW,
            created=date(2026, 1, 1) + timedelta(days=i),
        )


def lazy_filter(source: Iterable[T], predicate: Callable[[T], bool]) -> Iterator[T]:
    for item in source:
        if predicate(item):
            yield item


def lazy_map(source: Iterable[T], fn: Callable[[T], U]) -> Iterator[U]:
    for item in source:
        yield fn(item)


def take(source: Iterable[T], n: int) -> list[T]:
    return list(itertools.islice(source, n))


class LazyPipeline(Generic[T]):


    def __init__(self, source: Iterable[T]):
        self._source = source

    def filter(self, predicate: Callable[[T], bool]) -> "LazyPipeline[T]":
        return LazyPipeline(lazy_filter(self._source, predicate))

    def map(self, fn: Callable[[T], U]) -> "LazyPipeline[U]":
        return LazyPipeline(lazy_map(self._source, fn))

    def take(self, n: int) -> list[T]:
        return take(self._source, n)

    def to_list(self) -> list[T]:
        return list(self._source)
