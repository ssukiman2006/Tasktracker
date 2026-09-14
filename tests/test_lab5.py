from __future__ import annotations

import types

from tasktracker.lazy import LazyPipeline, lazy_filter, lazy_map, take, task_stream
from tasktracker.models import Status


def test_task_stream_is_a_generator_not_a_list():
    stream = task_stream(1000)
    assert isinstance(stream, types.GeneratorType)


def test_take_pulls_only_requested_amount():
    stream = task_stream(1_000_000) 
    result = take(stream, 3)
    assert len(result) == 3
    assert [t.id for t in result] == [0, 1, 2]


def test_lazy_filter_only_checks_requested_elements():

    call_count = 0

    def counting_predicate(task) -> bool:
        nonlocal call_count
        call_count += 1
        return task.status == Status.TODO

    stream = task_stream(1000)
    filtered = lazy_filter(stream, counting_predicate)
    result = take(filtered, 2)

    assert len(result) == 2
    assert call_count < 1000  # не пробежались по всему потоку


def test_lazy_map_transforms_elements():
    stream = task_stream(5)
    mapped = lazy_map(stream, lambda t: t.title)
    result = take(mapped, 3)
    assert result == ["Task 0", "Task 1", "Task 2"]


def test_lazy_pipeline_does_not_evaluate_until_take_is_called():
    call_count = 0

    def counting_fn(task):
        nonlocal call_count
        call_count += 1
        return task.title

    pipeline = LazyPipeline(task_stream(100)).map(counting_fn)
    assert call_count == 0  

    result = pipeline.take(3)
    assert len(result) == 3
    assert call_count == 3  

def test_lazy_pipeline_filter_and_map_composition():
    result = (
        LazyPipeline(task_stream(20))
        .filter(lambda t: t.status == Status.TODO)
        .map(lambda t: t.title)
        .take(3)
    )
    assert result == ["Task 0", "Task 2", "Task 4"]
