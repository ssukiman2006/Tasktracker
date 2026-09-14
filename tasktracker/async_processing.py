from __future__ import annotations

import asyncio
import time

from tasktracker.models import Task


async def _process_one(task: Task, delay: float) -> str:
    await asyncio.sleep(delay)
    return f"processed: {task.title}"


async def process_tasks_async(tasks: tuple[Task, ...], delay: float = 0.01) -> list[str]:
    results = await asyncio.gather(*(_process_one(t, delay) for t in tasks))
    return list(results)


def process_tasks_sequential(tasks: tuple[Task, ...], delay: float = 0.01) -> list[str]:
    results = []
    for t in tasks:
        time.sleep(delay)
        results.append(f"processed: {t.title}")
    return results


async def run_end_to_end_demo(n: int = 20) -> dict:
    from tasktracker.lazy import task_stream
    from tasktracker.stats import status_breakdown_report

    tasks = tuple(task_stream(n))  # load
    processed = await process_tasks_async(tasks)  # process
    report = status_breakdown_report(tasks)  # report

    return {
        "loaded_count": len(tasks),
        "processed_count": len(processed),
        "report": report,
    }
