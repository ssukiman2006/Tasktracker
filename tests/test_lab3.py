from __future__ import annotations

import time
from datetime import date

import pytest

from tasktracker.memoization import memoize
from tasktracker.models import Priority, Status, Task
from tasktracker.stats import generate_dataset, status_breakdown_report


def test_memoize_returns_correct_result_first_call():
    calls = []

    @memoize
    def add(a, b):
        calls.append((a, b))
        return a + b

    assert add(2, 3) == 5
    assert calls == [(2, 3)]


def test_memoize_does_not_call_function_again_for_same_args():
    calls = []

    @memoize
    def add(a, b):
        calls.append((a, b))
        return a + b

    add(2, 3)
    add(2, 3)  
    assert calls == [(2, 3)]  

def test_memoize_calls_function_again_for_different_args():
    calls = []

    @memoize
    def add(a, b):
        calls.append((a, b))
        return a + b

    add(2, 3)
    add(10, 20) 
    assert calls == [(2, 3), (10, 20)]


def test_memoize_cache_clear_resets_cache():
    calls = []

    @memoize
    def add(a, b):
        calls.append((a, b))
        return a + b

    add(2, 3)
    add.cache_clear()
    add(2, 3) 
    assert calls == [(2, 3), (2, 3)]


def test_status_breakdown_report_is_correct():
    tasks = (
        Task(1, "a", Status.TODO, Priority.LOW, date(2026, 1, 1)),
        Task(2, "b", Status.TODO, Priority.LOW, date(2026, 1, 1)),
        Task(3, "c", Status.DONE, Priority.LOW, date(2026, 1, 1)),
    )
    result = status_breakdown_report(tasks)
    assert result[Status.TODO] == 2
    assert result[Status.DONE] == 1


def test_memoized_report_is_faster_on_second_call():

    tasks = generate_dataset(50)

    start = time.perf_counter()
    status_breakdown_report(tasks)
    first_call_time = time.perf_counter() - start

    start = time.perf_counter()
    status_breakdown_report(tasks)  
    second_call_time = time.perf_counter() - start

    assert second_call_time < first_call_time / 5


@pytest.fixture(autouse=True)
def _clear_status_report_cache():
    yield
    status_breakdown_report.cache_clear()
