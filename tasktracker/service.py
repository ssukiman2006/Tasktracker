
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from tasktracker.either import Either, create_task
from tasktracker.event_bus import EventBus
from tasktracker.models import Priority, Status, Task
from tasktracker.option import Option, find_task_by_id
from tasktracker.pipelines import filter_tasks
from tasktracker.stats import status_breakdown_report
from tasktracker.transforms import mark_done


@dataclass
class TaskService:
    tasks: tuple[Task, ...] = field(default_factory=tuple)
    bus: EventBus = field(default_factory=EventBus)

    def add_task(
        self,
        id: int,
        title: str,
        status: Status,
        priority: Priority,
        created: date,
        due: date | None = None,
        parent_id: int | None = None,
    ) -> Either[str, Task]:
        result = create_task(id, title, status, priority, created, due, parent_id)
        if result.is_right():
            self.tasks = self.tasks + (result.value,)
            self.bus.publish("task_created", result.value)
        return result

    def complete_task(self, task_id: int) -> Option[Task]:
        found = find_task_by_id(self.tasks, task_id)
        updated = found.map(mark_done)
        if updated.is_some():
            new_task = updated.value
            self.tasks = tuple(new_task if t.id == task_id else t for t in self.tasks)
            self.bus.publish("task_completed", new_task)
        return updated

    def tasks_by_status(self, status: Status) -> tuple[Task, ...]:
        return filter_tasks(self.tasks, lambda t: t.status == status)

    def report(self) -> dict[Status, int]:
        return status_breakdown_report(self.tasks)


def create_task_service(
    initial_tasks: tuple[Task, ...] = (),
    bus: EventBus | None = None,
) -> TaskService:
    return TaskService(tasks=initial_tasks, bus=bus if bus is not None else EventBus())
