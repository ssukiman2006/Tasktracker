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
        "**Проект:** Task Tracker \u2014 учебная платформа, сделанная для курса по "
        "функциональному программированию. Эта страница подробно объясняет, по каждой "
        "лабе: что требовалось, что это означает простыми словами, и где именно и как "
        "это реализовано в проекте \u2014 используйте её, чтобы подготовиться к защите."
    )

    st.subheader("Лабораторные работы")

    with st.expander("Лабораторная работа 1 \u2014 Чистые функции, иммутабельность, HOF"):
        st.markdown(
            "**Что требовалось:** описать доменные сущности как неизменяемые (иммутабельные) "
            "структуры; написать чистые функции преобразования; построить пайплайны обработки "
            "данных через map/filter/reduce.\n\n"
            "**Простыми словами:** *иммутабельный* объект нельзя изменить после создания \u2014 "
            "любое 'изменение' на самом деле создаёт совершенно новый объект. *Чистая* функция "
            "всегда даёт одинаковый результат для одинаковых входных данных и не имеет побочных "
            "эффектов (ничего не меняет вне себя самой). *Функции высшего порядка* (HOF) \u2014 это "
            "функции, которые принимают другие функции как аргументы (например, `filter`, `map`)."
        )
        st.markdown("**Где в проекте:** `tasktracker/models.py`, `transforms.py`, `pipelines.py`")
        st.code(
            "@dataclass(frozen=True)\n"
            "class Task:\n"
            "    id: int\n"
            "    title: str\n"
            "    status: Status\n"
            "    ...\n\n"
            "# frozen=True означает: попытка сделать task.status = Status.DONE\n"
            "# вызовет ошибку. Чтобы 'изменить' задачу, нужно создать новую:\n\n"
            "def mark_done(task: Task) -> Task:\n"
            "    return replace(task, status=Status.DONE)  # новый объект, исходный не тронут",
            language="python",
        )
        st.markdown("**На интерфейсе:** страница *Functional Core* \u2014 выбери задачу, "
                     "увидишь, что `mark_done()` создаёт предпросмотр, не меняя исходную задачу.")

    with st.expander("Лабораторная работа 2 \u2014 Замыкания, лямбды, рекурсия"):
        st.markdown(
            "**Что требовалось:** замыкание-конфигуратор (генератор фильтров/предикатов, "
            "например 'по категории/дате/цене'); минимум 2 рекурсивных алгоритма в предметной "
            "области.\n\n"
            "**Простыми словами:** *замыкание* \u2014 это функция, созданная внутри другой функции, "
            "которая 'запоминает' переданное ей значение, даже после того как внешняя функция "
            "уже закончила работу. *Рекурсия* \u2014 функция, вызывающая саму себя для меньшей части "
            "задачи, пока не дойдёт до самого простого случая (базового случая)."
        )
        st.markdown("**Где в проекте:** `closures.py`, `recursion.py`")
        st.code(
            "def make_status_filter(status: Status):\n"
            "    def predicate(task: Task) -> bool:\n"
            "        return task.status == status   # 'status' запоминается здесь\n"
            "    return predicate\n\n"
            "is_todo = make_status_filter(Status.TODO)  # готовая функция-фильтр\n\n"
            "def collect_descendants(tasks, root_id):\n"
            "    children = _direct_children(tasks, root_id)\n"
            "    if not children:\n"
            "        return ()                       # базовый случай: детей нет, стоп\n"
            "    result = children\n"
            "    for child in children:\n"
            "        result += collect_descendants(tasks, child.id)  # рекурсивный вызов\n"
            "    return result",
            language="python",
        )
        st.markdown("**На интерфейсе:** страница *Pipelines* \u2014 выпадающие списки статуса/"
                     "приоритета используют замыкания. Страница *Functional Core* \u2014 блок "
                     "'Recursive subtask tree' показывает, как `collect_descendants` обходит "
                     "дерево задач.")

    with st.expander("Лабораторная работа 3 \u2014 Мемоизация"):
        st.markdown(
            "**Что требовалось:** функция с дорогими вычислениями + мемоизация "
            "(`functools.lru_cache` или свой вариант); показать выгоду до/после на реальных "
            "данных.\n\n"
            "**Простыми словами:** *мемоизация* \u2014 это сохранение результата вызова функции, "
            "чтобы при повторном вызове с ТЕМИ ЖЕ аргументами результат отдавался мгновенно из "
            "памяти, а не считался заново с нуля."
        )
        st.markdown("**Где в проекте:** `memoization.py`, `stats.py`")
        st.code(
            "def memoize(fn):\n"
            "    cache = {}\n"
            "    def wrapper(*args):\n"
            "        if args in cache:\n"
            "            return cache[args]      # уже считали -> отдаём готовый результат\n"
            "        result = fn(*args)\n"
            "        cache[args] = result        # сохраняем на будущее\n"
            "        return result\n"
            "    return wrapper\n\n"
            "@memoize\n"
            "def status_breakdown_report(tasks):\n"
            "    _expensive_work(2_000_000)      # имитация тяжёлых вычислений\n"
            "    ...",
            language="python",
        )
        st.markdown("**На интерфейсе:** страница *Reports* \u2014 кнопка 'Measure' замеряет "
                     "первый вызов (медленный) и второй вызов на тех же данных (мгновенный, "
                     "из кэша).")

    with st.expander("Лабораторная работа 4 \u2014 Option/Maybe/Either"):
        st.markdown(
            "**Что требовалось:** ввести Option/Maybe/Either (простые контейнеры "
            "монадоподобного стиля) для обработки ошибок/отсутствующих значений; "
            "продемонстрировать композицию преобразований поверх них.\n\n"
            "**Простыми словами:** вместо того чтобы возвращать `None` (рискуя падением "
            "программы, если кто-то забудет это проверить), мы возвращаем `Some(значение)` "
            "или `Nothing()`. Вместо того чтобы кидать исключение при неверных данных, мы "
            "возвращаем `Right(значение)` при успехе или `Left(сообщение об ошибке)` при "
            "провале. У обоих есть `.map()`, поэтому можно безопасно строить цепочку шагов \u2014 "
            "если что-то пошло не так в середине цепочки, ошибка/отсутствие просто передаётся "
            "дальше без падений."
        )
        st.markdown("**Где в проекте:** `option.py`, `either.py`")
        st.code(
            "def find_task_by_id(tasks, task_id):\n"
            "    for t in tasks:\n"
            "        if t.id == task_id:\n"
            "            return Some(t)\n"
            "    return Nothing()                # без падений, без None \u2014 явное 'отсутствие'\n\n"
            "def create_task(id, title, status, priority, created, due=None, parent_id=None):\n"
            "    if not title.strip():\n"
            "        return Left(\"Title cannot be empty\")   # понятная явная ошибка\n"
            "    return Right(Task(id, title, status, priority, created, due, parent_id))\n\n"
            "# пример композиции, используется на странице Functional Core:\n"
            "find_task_by_id(tasks, 1).map(mark_done).map(title_with_priority_tag)",
            language="python",
        )
        st.markdown("**На интерфейсе:** страница *Data* \u2014 оставь заголовок пустым и "
                     "отправь форму, получишь ошибку `Left(...)` вместо падения программы. "
                     "Страница *Functional Core* \u2014 блок с Either демонстрирует то же самое "
                     "вживую.")

    with st.expander("Лабораторная работа 5 \u2014 Ленивые вычисления"):
        st.markdown(
            "**Что требовалось:** потоковая обработка через генераторы/итераторы, ленивые "
            "пайплайны, отложенные вычисления.\n\n"
            "**Простыми словами:** обычная (*жадная*) функция сразу строит весь список "
            "результата целиком. *Ленивый* генератор выдаёт следующий элемент только тогда, "
            "когда его реально запросили (через `next()` или цикл). Это значит, можно "
            "построить пайплайн поверх огромного (или даже бесконечного) потока и заплатить "
            "по вычислениям только за ту часть, которая реально использовалась."
        )
        st.markdown("**Где в проекте:** `lazy.py`")
        st.code(
            "def task_stream(n):\n"
            "    for i in range(n):\n"
            "        yield Task(id=i, ...)     # ничего не строится, пока не запросили\n\n"
            "class LazyPipeline:\n"
            "    def filter(self, predicate):\n"
            "        return LazyPipeline(lazy_filter(self._source, predicate))  # всё ещё лениво\n"
            "    def take(self, n):\n"
            "        return list(itertools.islice(self._source, n))  # А ВОТ ТУТ вычисление и запускается",
            language="python",
        )
        st.markdown("**На интерфейсе:** страница *Pipelines* \u2014 два ползунка внизу: "
                     "подними 'сколько сгенерировать' хоть до 10 000, приложение останется "
                     "мгновенным, потому что реально считается только количество из 'take'.")

    with st.expander("Лабораторная работа 6 \u2014 Обработка событий / FRP"):
        st.markdown(
            "**Что требовалось:** мини event bus (таймеры/события ввода) + функции-"
            "подписчики/обработчики.\n\n"
            "**Простыми словами:** вместо того чтобы одна часть кода напрямую вызывала "
            "другую, она 'публикует' событие ('что-то произошло'). Любая функция, "
            "'подписавшаяся' на этот тип события, вызывается автоматически. Издатель и "
            "подписчик не обязаны знать друг о друге \u2014 это называется слабой связанностью."
        )
        st.markdown("**Где в проекте:** `event_bus.py`")
        st.code(
            "class EventBus:\n"
            "    def subscribe(self, event_type, handler):\n"
            "        self._subscribers[event_type].append(handler)\n"
            "    def publish(self, event_type, payload=None):\n"
            "        for handler in self._subscribers[event_type]:\n"
            "            handler(payload)\n\n"
            "bus.subscribe(\"task_completed\", make_logging_handler(log, \"COMPLETED\"))\n"
            "bus.publish(\"task_completed\", finished_task)   # обработчик выше сработает",
            language="python",
        )
        st.markdown("**На интерфейсе:** страница *Async / FRP* \u2014 лог событий заполняется "
                     "автоматически при добавлении/завершении задачи где угодно в приложении; "
                     "кнопка 'Simulate timer ticks' публикует 5 фейковых событий 'tick'.")

    with st.expander("Лабораторная работа 7 \u2014 Композиция, модульность, интеграция с ООП"):
        st.markdown(
            "**Что требовалось:** класс-'обёртка' сервиса, методы которого \u2014 композиции "
            "чистых функций; внедрение зависимостей (DI) через фабричные функции.\n\n"
            "**Простыми словами:** сам класс не содержит новой бизнес-логики \u2014 каждый его "
            "метод просто вызывает (комбинирует) чистые функции из других лаб по очереди. "
            "*Dependency injection* (внедрение зависимостей) означает, что класс получает свои "
            "зависимости (например, event bus) СНАРУЖИ, а не создаёт их сам внутри \u2014 это "
            "упрощает замену и тестирование."
        )
        st.markdown("**Где в проекте:** `service.py`")
        st.code(
            "class TaskService:\n"
            "    def complete_task(self, task_id):\n"
            "        found = find_task_by_id(self.tasks, task_id)   # Лаба 4\n"
            "        updated = found.map(mark_done)                 # Лаба 1\n"
            "        if updated.is_some():\n"
            "            self.tasks = ...                           # обновление состояния\n"
            "            self.bus.publish(\"task_completed\", updated.value)  # Лаба 6\n"
            "        return updated\n\n"
            "def create_task_service(initial_tasks=(), bus=None):\n"
            "    # DI: bus передаётся снаружи, а не создаётся внутри класса\n"
            "    return TaskService(tasks=initial_tasks, bus=bus if bus else EventBus())",
            language="python",
        )
        st.markdown("**На интерфейсе:** каждая страница реально обращается к одному общему "
                     "экземпляру `TaskService`, который хранится для твоей сессии \u2014 именно "
                     "к этому объекту обращаются все кнопки и формы.")

    with st.expander("Лабораторная работа 8 \u2014 Параллелизм / asyncio + финальная интеграция"):
        st.markdown(
            "**Что требовалось:** asyncio/пулы исполнителей для параллельной обработки "
            "больших наборов данных; сквозной сценарий (загрузка \u2192 обработка \u2192 отчёт/"
            "визуализация).\n\n"
            "**Простыми словами:** если обработка каждого элемента \u2014 это в основном "
            "*ожидание* (например, сетевого запроса), невыгодно ждать каждый по очереди. "
            "`asyncio.gather` запускает все ожидания сразу, поэтому общее время близко ко "
            "времени ОДНОГО элемента, а не (время ожидания) \u00d7 (количество элементов)."
        )
        st.markdown("**Где в проекте:** `async_processing.py`")
        st.code(
            "async def process_tasks_async(tasks, delay=0.01):\n"
            "    results = await asyncio.gather(\n"
            "        *(_process_one(t, delay) for t in tasks)   # все ожидания идут параллельно\n"
            "    )\n"
            "    return list(results)\n\n"
            "async def run_end_to_end_demo(n=20):\n"
            "    tasks = tuple(task_stream(n))              # загрузка (Лаба 5)\n"
            "    processed = await process_tasks_async(tasks)  # обработка (эта лаба)\n"
            "    report = status_breakdown_report(tasks)    # отчёт (Лаба 3)\n"
            "    return {...}",
            language="python",
        )
        st.markdown("**На интерфейсе:** страница *Async / FRP* \u2014 кнопка 'Run comparison' "
                     "замеряет и показывает время конкурентной и последовательной обработки "
                     "рядом, с реальным числом ускорения.")

    st.divider()
    st.subheader("Гид по интерфейсу \u2014 страница за страницей")

    with st.expander("Overview"):
        st.markdown(
            "Сводный экран: сколько всего задач, сколько выполнено, сколько в работе, и "
            "таблица со всеми задачами. Тут нечего нажимать \u2014 страница просто отражает "
            "состояние, которое создали другие страницы."
        )

    with st.expander("Data"):
        st.markdown(
            "- Форма **Add a task**: название, статус, приоритет и опциональная "
            "родительская задача (выбери родителя, чтобы создать подзадачу). Если отправить "
            "форму с пустым названием \u2014 появится ошибка валидации \u2014 это `Either`/`Left` "
            "из Лабы 4 в действии.\n"
            "- **Mark a task as done**: выбери любую задачу из списка и нажми кнопку \u2014 это "
            "вызывает `TaskService.complete_task()` (Лаба 7), которая использует `mark_done` "
            "(Лаба 1) и публикует событие `task_completed` (Лаба 6).\n"
            "- Таблица внизу всегда показывает актуальный полный список задач."
        )

    with st.expander("Functional Core"):
        st.markdown(
            "- Выбери любую задачу в первом списке, чтобы увидеть иммутабельность вживую: "
            "`mark_done()` создаёт новую задачу, исходная остаётся без изменений.\n"
            "- Выбери задачу во втором списке ('Root task'), чтобы увидеть рекурсивное "
            "дерево подзадач \u2014 сколько у неё потомков и насколько глубоко дерево.\n"
            "- Поле внизу \u2014 живое демо валидации через `Either`, без реального добавления "
            "задачи."
        )

    with st.expander("Pipelines"):
        st.markdown(
            "- Верхняя таблица: готовый пайплайн (активные задачи с высоким/критическим "
            "приоритетом).\n"
            "- Два выпадающих списка: выбери статус и приоритет, таблица ниже фильтруется "
            "вживую через замыкания-предикаты (Лаба 2).\n"
            "- Два ползунка внизу управляют ленивым пайплайном (Лаба 5) \u2014 первый задаёт "
            "размер (ленивого) потока, второй \u2014 сколько элементов реально извлекается и "
            "вычисляется."
        )

    with st.expander("Async / FRP"):
        st.markdown(
            "- Лог событий вверху заполняется автоматически при создании/завершении задачи "
            "где угодно в приложении (это event bus, Лаба 6).\n"
            "- Кнопка 'Simulate 5 timer ticks': публикует 5 фейковых событий просто чтобы "
            "показать, как работает подписка.\n"
            "- Кнопка 'Run comparison': замеряет время обработки одних и тех же задач "
            "конкурентно (asyncio) и по одной, показывает ускорение (Лаба 8)."
        )

    with st.expander("Reports"):
        st.markdown(
            "- Столбчатый график количества задач по каждому статусу, посчитанный "
            "мемоизированной `status_breakdown_report()` (Лаба 3).\n"
            "- Кнопка 'Measure': очищает кэш, затем замеряет первый вызов (медленный, "
            "реальные вычисления) против второго вызова на тех же данных (мгновенный, из "
            "кэша)."
        )

    with st.expander("Tests"):
        st.markdown(
            "- Кнопка 'Run pytest -v': запускает весь набор тестов (по всем лабам) и "
            "показывает тот же вывод, что был бы в терминале, прямо в браузере \u2014 удобно "
            "показать на защите, не переключаясь между окнами."
        )

    st.divider()
    st.write("**Стек:** Python, Streamlit, pytest.")
