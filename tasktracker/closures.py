from __future__ import annotations

from datetime import date
from typing import Callable

from tasktracker.models import Priority, Status, Task

Predicate = Callable[[Task], bool]


def make_status_filter(status: Status) -> Predicate:
    def predicate(task: Task) -> bool:
        return task.status == status

    return predicate


def make_priority_filter(priority: Priority) -> Predicate:
    def predicate(task: Task) -> bool:
        return task.priority == priority

    return predicate


def make_date_range_filter(start: date, end: date) -> Predicate:
    def predicate(task: Task) -> bool:
        return task.due is not None and start <= task.due <= end

    return predicate


def combine_predicates(*predicates: Predicate) -> Predicate:
    def combined(task: Task) -> bool:
        return all(p(task) for p in predicates)

    return combined
