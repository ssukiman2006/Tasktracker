from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Generic, TypeVar

from tasktracker.models import Priority, Status, Task

L = TypeVar("L")
R = TypeVar("R")
R2 = TypeVar("R2")


class Either(Generic[L, R]):
    def is_left(self) -> bool:
        raise NotImplementedError

    def is_right(self) -> bool:
        return not self.is_left()

    def map(self, fn: Callable[[R], R2]) -> "Either[L, R2]":
        raise NotImplementedError

    def flat_map(self, fn: Callable[[R], "Either[L, R2]"]) -> "Either[L, R2]":
        raise NotImplementedError

    def get_or_else(self, default: R) -> R:
        raise NotImplementedError


@dataclass(frozen=True)
class Left(Either[L, R]):
    value: L  # причина ошибки

    def is_left(self) -> bool:
        return True

    def map(self, fn):
        return self  

    def flat_map(self, fn):
        return self

    def get_or_else(self, default):
        return default


@dataclass(frozen=True)
class Right(Either[L, R]):
    value: R  

    def is_left(self) -> bool:
        return False

    def map(self, fn):
        return Right(fn(self.value))

    def flat_map(self, fn):
        return fn(self.value)

    def get_or_else(self, default):
        return self.value


def create_task(
    id: int,
    title: str,
    status: Status,
    priority: Priority,
    created: date,
    due: date | None = None,
    parent_id: int | None = None,
) -> Either[str, Task]:

    if not title or not title.strip():
        return Left("Title не может быть пустым")
    if due is not None and due < created:
        return Left("Дедлайн не может быть раньше даты создания")
    return Right(Task(id, title, status, priority, created, due, parent_id))
