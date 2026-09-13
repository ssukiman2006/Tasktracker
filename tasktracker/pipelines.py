from __future__ import annotations

from functools import reduce
from typing import Callable, Iterable

from tasktracker.models import Priority, Status, Task


def filter_tasks(tasks: Iterable[Task], predicate: Callable[[Task], bool]) -> tuple[Task, ...]:
    return tuple(filter(predicate, tasks))


def map_tasks(tasks: Iterable[Task], fn: Callable[[Task], Task]) -> tuple[Task, ...]:
    return tuple(map(fn, tasks))


def reduce_tasks(tasks: Iterable[Task], fn: Callable[[int, Task], int], initial: int = 0) -> int:
    return reduce(fn, tasks, initial)


def active_high_priority_pipeline(tasks: Iterable[Task]) -> tuple[Task, ...]:
    active = filter_tasks(tasks, lambda t: t.status in (Status.TODO, Status.IN_PROGRESS))
    high_priority = filter_tasks(
        active, lambda t: t.priority in (Priority.HIGH, Priority.CRITICAL)
    )
    return high_priority


def count_matching(tasks: Iterable[Task], predicate: Callable[[Task], bool]) -> int:
    return reduce_tasks(tasks, lambda acc, t: acc + (1 if predicate(t) else 0))
