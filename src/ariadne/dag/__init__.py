"""Task graph: the one place a task file is parsed and its frontier calculated.

`tasks.md` is the only task source of truth (`contracts/task-dag.md`), and this is
the only implementation that reads it. No other module in Ariadne parses a task
file, so a ready frontier cannot mean two things.

Standard library only.
"""

from __future__ import annotations

from .tasks import (
    DagState,
    Task,
    missing_dag,
    parse_tasks,
    resolve_dag,
    resolve_dag_text,
)

__all__ = [
    "DagState",
    "Task",
    "missing_dag",
    "parse_tasks",
    "resolve_dag",
    "resolve_dag_text",
]
