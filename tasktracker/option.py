from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from tasktracker.models import Task

T = TypeVar("T")
U = TypeVar("U")


class Option(Generic[T]):
    def is_some(self) -> bool:
        raise NotImplementedError

    def is_none(self) -> bool:
        return not self.is_some()

    def map(self, fn: Callable[[T], U]) -> "Option[U]":
        raise NotImplementedError

    def flat_map(self, fn: Callable[[T], "Option[U]"]) -> "Option[U]":
        raise NotImplementedError

    def get_or_else(self, default: T) -> T:
        raise NotImplementedError


@dataclass(frozen=True)
class Some(Option[T]):
    value: T

    def is_some(self) -> bool:
        return True

    def map(self, fn):
        return Some(fn(self.value))

    def flat_map(self, fn):
        return fn(self.value)

    def get_or_else(self, default):
        return self.value


@dataclass(frozen=True)
class Nothing(Option[T]):
    def is_some(self) -> bool:
        return False

    def map(self, fn):
        return self 

    def flat_map(self, fn):
        return self

    def get_or_else(self, default):
        return default


def find_task_by_id(tasks: tuple[Task, ...], task_id: int) -> Option[Task]:
    for t in tasks:
        if t.id == task_id:
            return Some(t)
    return Nothing()
