
from __future__ import annotations

from tasktracker.models import Task


def _direct_children(tasks: tuple[Task, ...], parent_id: int) -> tuple[Task, ...]:
    return tuple(t for t in tasks if t.parent_id == parent_id)


def collect_descendants(tasks: tuple[Task, ...], root_id: int) -> tuple[Task, ...]:
    children = _direct_children(tasks, root_id)
    if not children:
        return () 

    result: tuple[Task, ...] = children
    for child in children:
        result += collect_descendants(tasks, child.id)  
    return result


def subtree_depth(tasks: tuple[Task, ...], root_id: int) -> int:
    children = _direct_children(tasks, root_id)
    if not children:
        return 1  

    return 1 + max(subtree_depth(tasks, child.id) for child in children)
