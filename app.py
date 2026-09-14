from __future__ import annotations

import asyncio
import subprocess
import time
from datetime import date

import streamlit as st
from streamlit_option_menu import option_menu

from tasktracker.async_processing import process_tasks_async, process_tasks_sequential
from tasktracker.closures import combine_predicates, make_priority_filter, make_status_filter
from tasktracker.either import create_task
from tasktracker.event_bus import EventBus, make_logging_handler, simulate_timer_ticks
from tasktracker.lazy import LazyPipeline, task_stream
from tasktracker.models import Priority, Status, Task
from tasktracker.option import find_task_by_id
from tasktracker.pipelines import active_high_priority_pipeline
from tasktracker.recursion import collect_descendants, subtree_depth
from tasktracker.service import create_task_service
from tasktracker.stats import generate_dataset, status_breakdown_report
from tasktracker.transforms import mark_done, title_with_priority_tag

st.set_page_config(page_title="Task Tracker", page_icon="\U0001F4CB", layout="wide")

# --- Light custom styling on top of the pastel theme (soft rounded cards) ---
st.markdown(
    """
    <style>
    div[data-testid="stMetric"], div[data-testid="stForm"] {
        background-color: #F8F2FA;
        border-radius: 16px;
        padding: 16px;
        border: 1px solid #EADFF0;
    }
    .stButton>button {
        border-radius: 10px;
        border: 1px solid #D9C7EA;
        background-color: #F3ECF7;
    }
    .stButton>button:hover {
        background-color: #E4D3F0;
        border-color: #B7A6E8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Application state (persists across Streamlit reruns) ---

if "service" not in st.session_state:
    service = create_task_service()
    service.add_task(1, "Epic: launch v2", Status.IN_PROGRESS, Priority.HIGH, date(2026, 1, 1))
    service.add_task(2, "Backend work", Status.TODO, Priority.HIGH, date(2026, 1, 1), parent_id=1)
    service.add_task(3, "Frontend work", Status.TODO, Priority.MEDIUM, date(2026, 1, 1), parent_id=1)
    service.add_task(4, "API endpoint", Status.TODO, Priority.HIGH, date(2026, 1, 1), parent_id=2)
    service.add_task(5, "Write endpoint tests", Status.TODO, Priority.LOW, date(2026, 1, 1), parent_id=4)
    service.add_task(6, "Write docs", Status.TODO, Priority.LOW, date(2026, 1, 2))
    service.add_task(7, "Server outage", Status.TODO, Priority.CRITICAL, date(2026, 1, 3))
    st.session_state.service = service

if "event_log" not in st.session_state:
    st.session_state.event_log = []
    st.session_state.service.bus.subscribe(
        "task_created", make_logging_handler(st.session_state.event_log, "CREATED")
    )
    st.session_state.service.bus.subscribe(
        "task_completed", make_logging_handler(st.session_state.event_log, "COMPLETED")
    )

service = st.session_state.service


# --- Top navigation ("burger menu" of the project) ---

section = option_menu(
    menu_title=None,
    options=["Overview", "Data", "Functional Core", "Pipelines", "Async / FRP", "Reports", "Tests", "About"],
    icons=["house", "database", "gear", "diagram-3", "lightning-charge", "bar-chart", "check2-square", "info-circle"],
    orientation="horizontal",
    styles={
        "container": {"padding": "6px!important", "background-color": "#F8F2FA", "border-radius": "14px"},
        "icon": {"color": "#9B7FD4", "font-size": "15px"},
        "nav-link": {
            "font-size": "14px",
            "text-align": "center",
            "margin": "2px",
            "padding": "10px 14px",
            "border-radius": "10px",
            "color": "#5B5560",
        },
        "nav-link-selected": {"background-color": "#B7A6E8", "color": "white", "font-weight": "500"},
    },
)


def task_table(tasks: tuple[Task, ...]):
    st.table(
        [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "priority": t.priority.value,
                "parent_id": str(t.parent_id) if t.parent_id is not None else "\u2014",
            }
            for t in tasks
        ]
    )


# ======================= OVERVIEW =======================
if section == "Overview":
    st.title("Task Tracker")
    st.write(
        "Immutable tasks, pure functions, closures, recursion, memoization, "
        "Option/Either, lazy evaluation, events and async processing — all "
        "implemented in the `tasktracker/` package and demonstrated below."
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Total tasks", len(service.tasks))
    col2.metric("Done", len(service.tasks_by_status(Status.DONE)))
    col3.metric("In progress", len(service.tasks_by_status(Status.IN_PROGRESS)))
    task_table(service.tasks)


# ======================= DATA =======================
elif section == "Data":
    st.header("Data")

    st.subheader("Add a task")
    with st.form("add_task_form"):
        title = st.text_input("Title")
        status = st.selectbox("Status", list(Status), format_func=lambda s: s.value)
        priority = st.selectbox("Priority", list(Priority), format_func=lambda p: p.value)

        parent_options = ["\u2014 none (top-level task) \u2014"] + [
            f"#{t.id} {t.title}" for t in service.tasks
        ]
        parent_choice = st.selectbox("Parent task (leave as none for a top-level task)", parent_options)
        parent_id = None if parent_choice.startswith("\u2014") else int(parent_choice.split(" ")[0][1:])

        submitted = st.form_submit_button("Add task")

        if submitted:
            new_id = max((t.id for t in service.tasks), default=0) + 1
            result = service.add_task(new_id, title, status, priority, date.today(), parent_id=parent_id)
            if result.is_right():
                st.success(f"Task added: {result.value.title}")
                st.rerun()  # refresh widgets so the new task shows up immediately everywhere
            else:
                st.error(f"Validation failed: {result.value}")

    st.divider()
    st.subheader("Mark a task as done")
    if service.tasks:
        complete_choice = st.selectbox(
            "Choose a task",
            service.tasks,
            format_func=lambda t: f"#{t.id} {t.title} [{t.status.value}]",
            key="complete_select",
        )
        if st.button("Mark as done"):
            result = service.complete_task(complete_choice.id)
            if result.is_some():
                st.success(f"Marked done: {result.value.title}")
                st.rerun()
            else:
                st.error("Task not found.")

    st.divider()
    st.subheader("All tasks")
    task_table(service.tasks)


# ======================= FUNCTIONAL CORE =======================
elif section == "Functional Core":
    st.header("Functional Core")
    st.caption("Immutability, pure functions, Option/Either")

    task_ids = [t.id for t in service.tasks]
    selected_id = st.selectbox("Choose a task", task_ids)

    found = find_task_by_id(service.tasks, selected_id)
    if found.is_some():
        task = found.value
        st.write(f"**Original task:** {title_with_priority_tag(task)} \u00b7 status `{task.status.value}`")

        preview = mark_done(task)
        st.write(f"**After mark_done() (preview only, nothing was mutated):** `{preview.status.value}`")
        st.info(
            "Note: the original `task` above is still in its old status — "
            "mark_done() returned a new object instead of mutating the original one."
        )

    st.divider()
    st.subheader("Recursive subtask tree")
    root_id = st.selectbox("Root task", task_ids, key="tree_root")
    descendants = collect_descendants(service.tasks, root_id)
    depth = subtree_depth(service.tasks, root_id)
    st.write(f"Subtree depth: **{depth}**, descendants: **{len(descendants)}**")
    if descendants:
        task_table(descendants)

    st.divider()
    st.subheader("Either: task creation validation")
    demo_title = st.text_input("Try leaving this empty, or type something normal", value="")
    demo_result = create_task(999, demo_title, Status.TODO, Priority.LOW, date.today())
    if demo_result.is_right():
        st.success(f"Right: valid task ({demo_result.value.title})")
    else:
        st.warning(f"Left: {demo_result.value}")


# ======================= PIPELINES =======================
elif section == "Pipelines":
    st.header("Pipelines")
    st.caption("map/filter/reduce, closure-based filters, lazy pipelines")

    st.subheader("Ready-made pipeline: active + high/critical priority")
    task_table(active_high_priority_pipeline(service.tasks))

    st.subheader("Closure-based filter configurators")
    status_choice = st.selectbox("Filter by status", list(Status), format_func=lambda s: s.value)
    priority_choice = st.selectbox("And priority", list(Priority), format_func=lambda p: p.value)
    combined = combine_predicates(make_status_filter(status_choice), make_priority_filter(priority_choice))
    matched = tuple(t for t in service.tasks if combined(t))
    st.write(f"Matched tasks: **{len(matched)}**")
    task_table(matched)

    st.subheader("Lazy pipeline")
    n = st.slider("How many tasks to generate in the stream", 10, 10_000, 1_000)
    take_n = st.slider("How many to actually take (.take)", 1, 20, 5)
    result = (
        LazyPipeline(task_stream(n))
        .filter(lambda t: t.status == Status.TODO)
        .map(lambda t: t.title)
        .take(take_n)
    )
    st.write(
        f"A stream of {n} tasks was built instantly (nothing was computed yet); "
        f"only {take_n} elements were actually evaluated:"
    )
    st.write(result)


# ======================= ASYNC / FRP =======================
elif section == "Async / FRP":
    st.header("Async / FRP")
    st.caption("Event bus and asynchronous processing")

    st.subheader("Event bus: activity log")
    st.write("Adding/completing tasks on the Data page publishes events here:")
    st.code("\n".join(st.session_state.event_log) or "(empty so far \u2014 try adding a task on the Data page)")

    if st.button("Simulate 5 timer ticks"):
        ticks_log: list[str] = []
        temp_bus = EventBus()
        temp_bus.subscribe("tick", make_logging_handler(ticks_log, "TICK"))
        simulate_timer_ticks(temp_bus, count=5)
        st.write(ticks_log)

    st.divider()
    st.subheader("Async processing: concurrent vs sequential")
    n_async = st.slider("How many tasks to process", 5, 30, 10)
    delay = st.slider("Simulated delay per task (sec)", 0.01, 0.1, 0.03)

    if st.button("Run comparison"):
        tasks_subset = service.tasks[:n_async] if len(service.tasks) >= n_async else tuple(task_stream(n_async))

        start = time.perf_counter()
        asyncio.run(process_tasks_async(tasks_subset, delay=delay))
        async_time = time.perf_counter() - start

        start = time.perf_counter()
        process_tasks_sequential(tasks_subset, delay=delay)
        sequential_time = time.perf_counter() - start

        col1, col2 = st.columns(2)
        col1.metric("Concurrent (asyncio)", f"{async_time:.2f} s")
        col2.metric("Sequential", f"{sequential_time:.2f} s")
        st.success(f"Speedup: roughly {sequential_time / async_time:.1f}x")


# ======================= REPORTS =======================
elif section == "Reports":
    st.header("Reports")
    st.caption("Memoized statistics")

    report = service.report()
    st.bar_chart({status.value: count for status, count in report.items()})

    st.subheader("Memoization payoff: first call vs cached call")
    size = st.slider("Test dataset size", 10, 200, 50)
    if st.button("Measure"):
        status_breakdown_report.cache_clear()
        big_dataset = generate_dataset(size)

        start = time.perf_counter()
        status_breakdown_report(big_dataset)
        first_call = time.perf_counter() - start

        start = time.perf_counter()
        status_breakdown_report(big_dataset)
        second_call = time.perf_counter() - start

        col1, col2 = st.columns(2)
        col1.metric("First call (no cache)", f"{first_call * 1000:.1f} ms")
        col2.metric("Second call (cached)", f"{second_call * 1000:.1f} ms")


# ======================= TESTS =======================
elif section == "Tests":
    st.header("Tests")
    st.caption("Run pytest right from the interface \u2014 handy for the defense")

    if st.button("Run pytest -v"):
        with st.spinner("Running tests..."):
            result = subprocess.run(
                ["python3", "-m", "pytest", "-v"], capture_output=True, text=True
            )
        st.code(result.stdout + result.stderr)
        if result.returncode == 0:
            st.success("All tests passed \u2705")
        else:
            st.error("Some tests failed \u274c")


# ======================= ABOUT =======================
elif section == "About":
    st.header("About")
    st.write(
        """
        **Project:** Task Tracker \u2014 a learning platform for a functional programming course.

        **Laboratory works covered:**
        - Laboratory Work 1 \u2014 pure functions, immutability, higher-order functions
        - Laboratory Work 2 \u2014 closure-based configurators, recursion over the subtask tree
        - Laboratory Work 3 \u2014 memoization
        - Laboratory Work 4 \u2014 Option/Maybe/Either
        - Laboratory Work 5 \u2014 lazy evaluation
        - Laboratory Work 6 \u2014 event bus (FRP)
        - Laboratory Work 7 \u2014 service wrapper class + dependency injection
        - Laboratory Work 8 \u2014 asyncio, end-to-end scenario

        **Stack:** Python, Streamlit, pytest.
        """
    )
