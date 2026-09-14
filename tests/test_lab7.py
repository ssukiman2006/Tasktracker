from __future__ import annotations

from datetime import date

from tasktracker.event_bus import EventBus
from tasktracker.models import Priority, Status
from tasktracker.service import create_task_service


def test_create_task_service_creates_default_bus_when_none_given():
    service = create_task_service()
    assert isinstance(service.bus, EventBus)


def test_add_task_adds_valid_task_and_publishes_event():
    service = create_task_service()
    events = []
    service.bus.subscribe("task_created", lambda t: events.append(t))

    result = service.add_task(1, "Fix bug", Status.TODO, Priority.HIGH, date(2026, 1, 1))

    assert result.is_right()
    assert len(service.tasks) == 1
    assert len(events) == 1


def test_add_task_with_invalid_title_does_not_add_and_does_not_publish():
    service = create_task_service()
    events = []
    service.bus.subscribe("task_created", lambda t: events.append(t))

    result = service.add_task(1, "", Status.TODO, Priority.HIGH, date(2026, 1, 1))

    assert result.is_left()
    assert len(service.tasks) == 0
    assert len(events) == 0


def test_complete_task_marks_existing_task_done_and_publishes_event():
    service = create_task_service()
    service.add_task(1, "Fix bug", Status.TODO, Priority.HIGH, date(2026, 1, 1))
    events = []
    service.bus.subscribe("task_completed", lambda t: events.append(t))

    result = service.complete_task(1)

    assert result.is_some()
    assert result.value.status == Status.DONE
    assert service.tasks[0].status == Status.DONE  
    assert len(events) == 1


def test_complete_task_with_unknown_id_returns_nothing_and_no_event():
    service = create_task_service()
    events = []
    service.bus.subscribe("task_completed", lambda t: events.append(t))

    result = service.complete_task(999)

    assert result.is_none()
    assert len(events) == 0


def test_tasks_by_status_filters_correctly():
    service = create_task_service()
    service.add_task(1, "A", Status.TODO, Priority.LOW, date(2026, 1, 1))
    service.add_task(2, "B", Status.TODO, Priority.LOW, date(2026, 1, 1))
    service.complete_task(2)

    todo = service.tasks_by_status(Status.TODO)
    done = service.tasks_by_status(Status.DONE)

    assert {t.id for t in todo} == {1}
    assert {t.id for t in done} == {2}


def test_dependency_injection_uses_the_provided_bus_not_a_new_one():
    custom_bus = EventBus()
    service = create_task_service(bus=custom_bus)

    assert service.bus is custom_bus 
