
from __future__ import annotations

from datetime import date

import pytest

from tasktracker.either import Left, Right, create_task
from tasktracker.models import Priority, Status, Task
from tasktracker.option import Nothing, Some, find_task_by_id
from tasktracker.transforms import mark_done, title_with_priority_tag


@pytest.fixture
def tasks() -> tuple[Task, ...]:
    return (
        Task(1, "Fix login bug", Status.IN_PROGRESS, Priority.HIGH, date(2026, 1, 1)),
        Task(2, "Write docs", Status.TODO, Priority.LOW, date(2026, 1, 2)),
    )


# --- Option ---

def test_find_task_by_id_returns_some_when_found(tasks):
    result = find_task_by_id(tasks, 1)
    assert isinstance(result, Some)
    assert result.value.title == "Fix login bug"


def test_find_task_by_id_returns_nothing_when_not_found(tasks):
    result = find_task_by_id(tasks, 999)
    assert isinstance(result, Nothing)
    assert result.is_none() is True


def test_option_map_applies_function_when_some(tasks):
    result = find_task_by_id(tasks, 2).map(title_with_priority_tag)
    assert result == Some("[low] Write docs")


def test_option_map_is_noop_when_nothing(tasks):
    result = find_task_by_id(tasks, 999).map(title_with_priority_tag)
    assert isinstance(result, Nothing)  # fn ни разу не вызвалась, ошибки нет


def test_option_get_or_else():
    assert Some(42).get_or_else(0) == 42
    assert Nothing().get_or_else(0) == 0


def test_option_composition_chain(tasks):
    """
    Композиция: находим задачу -> помечаем выполненной -> форматируем título.
    Если на любом шаге получится Nothing, вся цепочка останется Nothing,
    без ручных проверок 'if result is not None' на каждом шаге.
    """
    result = find_task_by_id(tasks, 1).map(mark_done).map(title_with_priority_tag)
    assert result == Some("[HIGH] Fix login bug")


# --- Either ---

def test_create_task_returns_right_for_valid_input():
    result = create_task(1, "Valid title", Status.TODO, Priority.LOW, date(2026, 1, 1))
    assert isinstance(result, Right)
    assert result.value.title == "Valid title"


def test_create_task_returns_left_for_empty_title():
    result = create_task(1, "   ", Status.TODO, Priority.LOW, date(2026, 1, 1))
    assert isinstance(result, Left)
    assert "Title" in result.value


def test_create_task_returns_left_for_due_before_created():
    result = create_task(
        1, "Task", Status.TODO, Priority.LOW,
        created=date(2026, 1, 10), due=date(2026, 1, 1),
    )
    assert isinstance(result, Left)
    assert "Дедлайн" in result.value


def test_either_map_is_noop_on_left():
    result = create_task(1, "", Status.TODO, Priority.LOW, date(2026, 1, 1))
    mapped = result.map(title_with_priority_tag)
    assert isinstance(mapped, Left)  # ошибка просто передалась дальше, fn не вызывалась


def test_either_composition_chain():
    """Композиция: создать задачу -> сразу пометить выполненной -> получить заголовок."""
    result = (
        create_task(1, "Deploy", Status.TODO, Priority.HIGH, date(2026, 1, 1))
        .map(mark_done)
        .map(title_with_priority_tag)
    )
    assert result == Right("[HIGH] Deploy")


def test_either_get_or_else():
    ok = create_task(1, "Task", Status.TODO, Priority.LOW, date(2026, 1, 1))
    bad = create_task(1, "", Status.TODO, Priority.LOW, date(2026, 1, 1))
    assert ok.get_or_else(None) is not None
    assert bad.get_or_else("fallback") == "fallback"
