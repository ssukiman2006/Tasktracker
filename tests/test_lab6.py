from __future__ import annotations

from tasktracker.event_bus import EventBus, make_logging_handler, simulate_timer_ticks


def test_subscribe_and_publish_calls_handler():
    bus = EventBus()
    received = []
    bus.subscribe("task_created", lambda payload: received.append(payload))

    bus.publish("task_created", "Fix bug")

    assert received == ["Fix bug"]


def test_multiple_subscribers_all_get_called():
    bus = EventBus()
    received_a = []
    received_b = []
    bus.subscribe("task_created", lambda p: received_a.append(p))
    bus.subscribe("task_created", lambda p: received_b.append(p))

    bus.publish("task_created", "Fix bug")

    assert received_a == ["Fix bug"]
    assert received_b == ["Fix bug"]


def test_publish_with_no_subscribers_does_nothing():
    bus = EventBus()
    bus.publish("nonexistent_event", "payload")
    assert bus.subscriber_count("nonexistent_event") == 0


def test_subscriber_count():
    bus = EventBus()
    assert bus.subscriber_count("tick") == 0
    bus.subscribe("tick", lambda p: None)
    bus.subscribe("tick", lambda p: None)
    assert bus.subscriber_count("tick") == 2


def test_simulate_timer_ticks_publishes_correct_sequence():
    bus = EventBus()
    ticks = []
    bus.subscribe("tick", lambda payload: ticks.append(payload))

    simulate_timer_ticks(bus, count=5)

    assert ticks == [0, 1, 2, 3, 4]


def test_make_logging_handler_is_a_closure_that_writes_to_given_log():
    bus = EventBus()
    log: list[str] = []
    handler = make_logging_handler(log, label="AUDIT")
    bus.subscribe("task_completed", handler)

    bus.publish("task_completed", "Deploy release")

    assert log == ["[AUDIT] Deploy release"]
