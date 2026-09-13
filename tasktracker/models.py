from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Status(str, Enum):

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class Priority(str, Enum):

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Task:

    id: int
    title: str
    status: Status
    priority: Priority
    created: date
    due: date | None = None
    parent_id: int | None = None

    def is_overdue(self, today: date) -> bool:
        return self.due is not None and self.due < today and self.status != Status.DONE
