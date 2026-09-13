from __future__ import annotations

import random
from datetime import date, timedelta

from tasktracker.memoization import memoize
from tasktracker.models import Priority, Status, Task


def generate_dataset(n: int, seed: int = 42) -> tuple[Task, ...]:
    rng = random.Random(seed)
    statuses = list(Status)
    priorities = list(Priority)
    base = date(2026, 1, 1)
    tasks = tuple(
        Task(
            id=i,
            title=f"Task {i}",
            status=rng.choice(statuses),
            priority=rng.choice(priorities),
            created=base + timedelta(days=rng.randint(0, 300)),
        )
        for i in range(n)
    )
    return tasks


def _expensive_work(n: int) -> int:
    total = 0
    for i in range(n):
        total += i % 7
    return total


@memoize
def status_breakdown_report(tasks: tuple[Task, ...]) -> dict[Status, int]:

    _expensive_work(2_000_000)
    counts: dict[Status, int] = {status: 0 for status in Status}
    for t in tasks:
        counts[t.status] += 1
    return counts
