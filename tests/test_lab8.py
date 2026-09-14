from __future__ import annotations

import asyncio
import time
from datetime import date

from tasktracker.async_processing import (
    process_tasks_async,
    process_tasks_sequential,
    run_end_to_end_demo,
)
from tasktracker.models import Priority, Status, Task


def _make_tasks(n: int) -> tuple[Task, ...]:
    return tuple(
        Task(i, f"Task {i}", Status.TODO, Priority.LOW, date(2026, 1, 1)) for i in range(n)
    )


def test_process_tasks_async_returns_all_results_in_order():
    tasks = _make_tasks(5)
    results = asyncio.run(process_tasks_async(tasks, delay=0.001))
    assert results == [f"processed: Task {i}" for i in range(5)]


def test_process_tasks_sequential_returns_all_results():
    tasks = _make_tasks(5)
    results = process_tasks_sequential(tasks, delay=0.001)
    assert results == [f"processed: Task {i}" for i in range(5)]


def test_async_processing_is_faster_than_sequential():
    tasks = _make_tasks(10)
    delay = 0.02

    start = time.perf_counter()
    asyncio.run(process_tasks_async(tasks, delay=delay))
    async_time = time.perf_counter() - start

    start = time.perf_counter()
    process_tasks_sequential(tasks, delay=delay)
    sequential_time = time.perf_counter() - start

    assert async_time < sequential_time / 3 


def test_run_end_to_end_demo_returns_expected_structure():
    result = asyncio.run(run_end_to_end_demo(n=10))
    assert result["loaded_count"] == 10
    assert result["processed_count"] == 10
    assert isinstance(result["report"], dict)
    assert sum(result["report"].values()) == 10


def test_run_end_to_end_demo_with_zero_tasks():
    result = asyncio.run(run_end_to_end_demo(n=0))
    assert result["loaded_count"] == 0
    assert result["processed_count"] == 0
