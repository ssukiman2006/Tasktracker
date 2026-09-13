
from __future__ import annotations

from dataclasses import replace
from datetime import date

from tasktracker.models import Priority, Status, Task


def mark_done(task: Task) -> Task:
    return replace(task, status=Status.DONE)


def change_priority(task: Task, new_priority: Priority) -> Task:
    return replace(task, priority=new_priority)


def postpone(task: Task, new_due: date) -> Task:
    return replace(task, due=new_due)


def title_with_priority_tag(task: Task) -> str:
    tags = {
        Priority.LOW: "[low]",
        Priority.MEDIUM: "[med]",
        Priority.HIGH: "[HIGH]",
        Priority.CRITICAL: "[CRIT]",
    }
    return f"{tags[task.priority]} {task.title}"


def summarize_by_status(tasks: tuple[Task, ...]) -> dict[Status, int]:
    counts: dict[Status, int] = {status: 0 for status in Status}
    for t in tasks:
        counts[t.status] += 1
    return counts
