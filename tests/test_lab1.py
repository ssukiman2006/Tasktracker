from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from tasktracker.models import Priority, Status, Task
from tasktracker.pipelines import (
    active_high_priority_pipeline,
    count_matching,
    filter_tasks,
    map_tasks,
    reduce_tasks,
)
from tasktracker.transforms import (
    change_priority,
    mark_done,
    postpone,
    summarize_by_status,
    title_with_priority_tag,
)


@pytest.fixture
def sample_tasks() -> tuple[Task, ...]:
    return (
        Task(1, "Fix login bug", Status.IN_PROGRESS, Priority.HIGH, date(2026, 1, 1)),
        Task(2, "Write docs", Status.TODO, Priority.LOW, date(2026, 1, 2)),
        Task(3, "Server outage", Status.TODO, Priority.CRITICAL, date(2026, 1, 3)),
        Task(4, "Refactor tests", Status.DONE, Priority.MEDIUM, date(2026, 1, 4)),
        Task(5, "Cancelled feature", Status.CANCELLED, Priority.HIGH, date(2026, 1, 5)),
    )


def test_task_is_immutable(sample_tasks):
    task = sample_tasks[0]
    with pytest.raises(FrozenInstanceError):
        task.status = Status.DONE 


def test_mark_done_returns_new_object_without_mutating_original(sample_tasks):
    original = sample_tasks[0]
    updated = mark_done(original)
    assert updated.status == Status.DONE
    assert original.status == Status.IN_PROGRESS 
    assert updated is not original


def test_change_priority_is_pure(sample_tasks):
    original = sample_tasks[1]
    updated = change_priority(original, Priority.CRITICAL)
    assert updated.priority == Priority.CRITICAL
    assert original.priority == Priority.LOW


def test_postpone_changes_only_due_date(sample_tasks):
    original = sample_tasks[0]
    new_due = date(2026, 2, 1)
    updated = postpone(original, new_due)
    assert updated.due == new_due
    assert updated.title == original.title
    assert updated.status == original.status


def test_title_with_priority_tag_formats_correctly(sample_tasks):
    assert title_with_priority_tag(sample_tasks[2]) == "[CRIT] Server outage"
    assert title_with_priority_tag(sample_tasks[1]) == "[low] Write docs"


def test_summarize_by_status_counts_correctly(sample_tasks):
    summary = summarize_by_status(sample_tasks)
    assert summary[Status.TODO] == 2
    assert summary[Status.IN_PROGRESS] == 1
    assert summary[Status.DONE] == 1
    assert summary[Status.CANCELLED] == 1


def test_filter_tasks_by_status(sample_tasks):
    todo_only = filter_tasks(sample_tasks, lambda t: t.status == Status.TODO)
    assert len(todo_only) == 2
    assert all(t.status == Status.TODO for t in todo_only)


def test_map_tasks_applies_transformation(sample_tasks):
    all_done = map_tasks(sample_tasks, mark_done)
    assert all(t.status == Status.DONE for t in all_done)
    # исходная коллекция не изменилась
    assert sample_tasks[0].status == Status.IN_PROGRESS


def test_reduce_tasks_aggregates(sample_tasks):
    total = reduce_tasks(sample_tasks, lambda acc, t: acc + 1)
    assert total == len(sample_tasks)


def test_active_high_priority_pipeline(sample_tasks):
    result = active_high_priority_pipeline(sample_tasks)
    assert {t.id for t in result} == {1, 3}


def test_count_matching(sample_tasks):
    overdue_count = count_matching(sample_tasks, lambda t: t.priority == Priority.HIGH)
    assert overdue_count == 2  
