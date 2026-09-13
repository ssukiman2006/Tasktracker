
from __future__ import annotations

from datetime import date

import pytest

from tasktracker.closures import (
    combine_predicates,
    make_date_range_filter,
    make_priority_filter,
    make_status_filter,
)
from tasktracker.models import Priority, Status, Task
from tasktracker.recursion import collect_descendants, subtree_depth


@pytest.fixture
def flat_tasks() -> tuple[Task, ...]:
    return (
        Task(1, "Fix login bug", Status.IN_PROGRESS, Priority.HIGH, date(2026, 1, 1), due=date(2026, 1, 10)),
        Task(2, "Write docs", Status.TODO, Priority.LOW, date(2026, 1, 2), due=date(2026, 1, 20)),
        Task(3, "Server outage", Status.TODO, Priority.CRITICAL, date(2026, 1, 3), due=date(2026, 1, 5)),
    )


@pytest.fixture
def tree_tasks() -> tuple[Task, ...]:
    """
    Дерево:
        1 (root)
        ├── 2
        │   └── 4
        │       └── 5
        └── 3
    """
    return (
        Task(1, "Epic: launch v2", Status.IN_PROGRESS, Priority.HIGH, date(2026, 1, 1)),
        Task(2, "Backend work", Status.TODO, Priority.HIGH, date(2026, 1, 1), parent_id=1),
        Task(3, "Frontend work", Status.TODO, Priority.MEDIUM, date(2026, 1, 1), parent_id=1),
        Task(4, "API endpoint", Status.TODO, Priority.HIGH, date(2026, 1, 1), parent_id=2),
        Task(5, "Write endpoint tests", Status.TODO, Priority.LOW, date(2026, 1, 1), parent_id=4),
    )


def test_make_status_filter_matches_correct_status(flat_tasks):
    is_todo = make_status_filter(Status.TODO)
    matched = [t for t in flat_tasks if is_todo(t)]
    assert {t.id for t in matched} == {2, 3}


def test_make_priority_filter_matches_correct_priority(flat_tasks):
    is_critical = make_priority_filter(Priority.CRITICAL)
    matched = [t for t in flat_tasks if is_critical(t)]
    assert {t.id for t in matched} == {3}


def test_two_closures_are_independent(flat_tasks):

    is_todo = make_status_filter(Status.TODO)
    is_done = make_status_filter(Status.DONE)
    assert is_todo(flat_tasks[1]) is True
    assert is_done(flat_tasks[1]) is False


def test_make_date_range_filter(flat_tasks):
    in_early_january = make_date_range_filter(date(2026, 1, 1), date(2026, 1, 10))
    matched = [t for t in flat_tasks if in_early_january(t)]
    assert {t.id for t in matched} == {1, 3}


def test_combine_predicates_uses_logical_and(flat_tasks):
    is_todo = make_status_filter(Status.TODO)
    is_critical = make_priority_filter(Priority.CRITICAL)
    todo_and_critical = combine_predicates(is_todo, is_critical)
    matched = [t for t in flat_tasks if todo_and_critical(t)]
    assert {t.id for t in matched} == {3}  


def test_collect_descendants_of_root(tree_tasks):
    descendants = collect_descendants(tree_tasks, root_id=1)
    assert {t.id for t in descendants} == {2, 3, 4, 5}


def test_collect_descendants_of_middle_node(tree_tasks):
    descendants = collect_descendants(tree_tasks, root_id=2)
    assert {t.id for t in descendants} == {4, 5}


def test_collect_descendants_of_leaf_is_empty(tree_tasks):
    descendants = collect_descendants(tree_tasks, root_id=5)
    assert descendants == ()


def test_subtree_depth_of_root(tree_tasks):
    assert subtree_depth(tree_tasks, root_id=1) == 4


def test_subtree_depth_of_leaf_is_one(tree_tasks):
    assert subtree_depth(tree_tasks, root_id=5) == 1
