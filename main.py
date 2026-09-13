
from datetime import date

from tasktracker.models import Priority, Status, Task
from tasktracker.pipelines import active_high_priority_pipeline
from tasktracker.transforms import summarize_by_status, title_with_priority_tag

SAMPLE_TASKS = (
    Task(1, "Fix login bug", Status.IN_PROGRESS, Priority.HIGH, date(2026, 1, 1)),
    Task(2, "Write docs", Status.TODO, Priority.LOW, date(2026, 1, 2)),
    Task(3, "Server outage", Status.TODO, Priority.CRITICAL, date(2026, 1, 3)),
    Task(4, "Refactor tests", Status.DONE, Priority.MEDIUM, date(2026, 1, 4)),
    Task(5, "Cancelled feature", Status.CANCELLED, Priority.HIGH, date(2026, 1, 5)),
)


def section_overview() -> None:
    print("=== Overview ===")
    for t in SAMPLE_TASKS:
        print(f"  #{t.id} {title_with_priority_tag(t)} [{t.status.value}]")


def section_reports() -> None:
    print("\n=== Reports: tasks by status ===")
    for status, count in summarize_by_status(SAMPLE_TASKS).items():
        print(f"  {status.value}: {count}")


def section_pipelines() -> None:
    print("\n=== Pipelines: active + high/critical priority ===")
    for t in active_high_priority_pipeline(SAMPLE_TASKS):
        print(f"  #{t.id} {t.title}")


if __name__ == "__main__":
    section_overview()
    section_reports()
    section_pipelines()
