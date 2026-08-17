"""Canonical task DAG resolution for the Agent SDLC runtime.

`tasks.md` remains the only task source of truth (`.agent-sdlc/core/task-dag.md`).
This module owns the one executable implementation of parsing, validation, and
frontier calculation; `.agent-sdlc/validation/validate_tasks.py` is a thin CLI
wrapper over it and no other runtime code re-parses `tasks.md`.

Standard library only. This module answers only "what does the task graph say?".
It holds no lifecycle, decision, or workflow policy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TASK_RE = re.compile(r"^- \[(?P<done>[ xX])\] (?P<id>T\d{3,})\b(?P<body>.*)$")
CHECKBOX_RE = re.compile(r"^- \[[ xX]\](?:\s+|$)")
DEPENDS_RE = re.compile(r"^\s+Depends:\s*(?P<deps>.*)$", re.IGNORECASE)
ACCEPTANCE_RE = re.compile(r"^\s+Acceptance:\s*(?P<value>true|false|yes|no|1|0)\s*$", re.IGNORECASE)
TERMINAL_RE = re.compile(r"^\s+Terminal:\s*(?P<value>true|false|yes|no|1|0)\s*$", re.IGNORECASE)

_TRUE_TOKENS = frozenset({"true", "yes", "1"})


@dataclass
class Task:
    """One `tasks.md` entry with its compact scheduling metadata."""

    task_id: str
    done: bool
    line: int
    depends_on: list[str] = field(default_factory=list)
    has_metadata: bool = False
    acceptance: bool = False
    terminal: bool = False


@dataclass(frozen=True)
class DagState:
    """The resolved task graph.

    `valid` is the single machine-readable verdict: it is false whenever any
    diagnostic was produced, so a caller never has to re-derive validity from the
    error list. `legacy` marks a file with no per-task metadata, which Core
    treats as `LEGACY_TASK_FORMAT` rather than as a fully schedulable graph.
    """

    valid: bool
    legacy: bool
    completed: bool
    tasks: tuple[Task, ...]
    ready: tuple[str, ...]
    blocked: tuple[str, ...]
    errors: tuple[str, ...]
    readable: bool = True
    """False when the task file itself could not be read, as distinct from a graph
    that was read and found invalid. Both are `valid=False`; only this separates
    "no graph" from "bad graph"."""

    @property
    def total(self) -> int:
        return len(self.tasks)

    @property
    def incomplete(self) -> tuple[str, ...]:
        """Unfinished task IDs, ready or blocked, in declared order."""
        return tuple(task.task_id for task in self.tasks if not task.done)

    @property
    def status(self) -> str:
        """The reported DAG status token."""
        if not self.valid:
            return "DAG_INVALID"
        if self.completed:
            return "COMPLETE"
        return "VALID"


def parse_tasks(text: str) -> tuple[list[Task], bool, list[str]]:
    """Parse task lines and their trailing metadata block from `tasks.md` text."""
    tasks: list[Task] = []
    errors: list[str] = []
    has_metadata = False
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if CHECKBOX_RE.match(line) and not TASK_RE.match(line):
            errors.append(f"malformed task ID at line {index + 1}: {line}")
            continue
        match = TASK_RE.match(line)
        if not match:
            continue
        task = Task(match.group("id"), match.group("done").lower() == "x", index + 1)
        cursor = index + 1
        while cursor < len(lines) and not TASK_RE.match(lines[cursor]):
            dep_match = DEPENDS_RE.match(lines[cursor])
            acceptance_match = ACCEPTANCE_RE.match(lines[cursor])
            terminal_match = TERMINAL_RE.match(lines[cursor])
            if dep_match:
                has_metadata = True
                task.has_metadata = True
                raw = dep_match.group("deps").strip()
                task.depends_on = [item for item in re.split(r"[, ]+", raw) if item]
            if acceptance_match:
                has_metadata = True
                task.has_metadata = True
                task.acceptance = acceptance_match.group("value").lower() in _TRUE_TOKENS
            if terminal_match:
                has_metadata = True
                task.has_metadata = True
                task.terminal = terminal_match.group("value").lower() in _TRUE_TOKENS
            cursor += 1
        tasks.append(task)
    return tasks, has_metadata, errors


def _validate(tasks: list[Task], metadata: bool) -> tuple[list[str], list[Task], list[Task]]:
    errors: list[str] = []
    by_id: dict[str, Task] = {}
    for task in tasks:
        if task.task_id in by_id:
            errors.append(f"duplicate task ID: {task.task_id} (line {task.line})")
        by_id[task.task_id] = task
    for task in tasks:
        for dependency in task.depends_on:
            if dependency not in by_id:
                errors.append(f"{task.task_id} depends on missing task {dependency}")
            if dependency == task.task_id:
                errors.append(f"self dependency: {task.task_id}")

    visiting: list[str] = []
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            start = visiting.index(task_id)
            cycle = visiting[start:] + [task_id]
            errors.append(f"cycle: {' → '.join(cycle)}")
            return
        if task_id in visited or task_id not in by_id:
            return
        visiting.append(task_id)
        for dependency in by_id[task_id].depends_on:
            visit(dependency)
        visiting.pop()
        visited.add(task_id)

    for task in tasks:
        visit(task.task_id)

    ready = sorted(
        (
            task
            for task in tasks
            if not task.done
            and all(dependency in by_id and by_id[dependency].done for dependency in task.depends_on)
        ),
        key=lambda task: int(task.task_id[1:]),
    )
    blocked = sorted(
        (task for task in tasks if not task.done and task not in ready),
        key=lambda task: int(task.task_id[1:]),
    )
    if tasks and not ready and blocked and not errors:
        errors.append("no initial ready node; unfinished tasks are blocked")
    if metadata:
        for task in tasks:
            if not task.has_metadata:
                errors.append(f"incomplete task metadata: {task.task_id}")
            if task.done and any(
                dependency in by_id and not by_id[dependency].done for dependency in task.depends_on
            ):
                errors.append(f"completed task has incomplete dependency: {task.task_id}")
        acceptance_tasks = [task for task in tasks if task.acceptance]
        terminal_tasks = [task for task in tasks if task.terminal]
        if acceptance_tasks or terminal_tasks:
            reachable: set[str] = set()
            outgoing: dict[str, list[str]] = {task.task_id: [] for task in tasks}
            for task in tasks:
                for dependency in task.depends_on:
                    if dependency in outgoing:
                        outgoing[dependency].append(task.task_id)
            roots = [task.task_id for task in tasks if not task.depends_on]
            stack = roots[:]
            while stack:
                current = stack.pop()
                if current in reachable:
                    continue
                reachable.add(current)
                stack.extend(outgoing[current])
            for task in acceptance_tasks + terminal_tasks:
                if task.task_id not in reachable:
                    errors.append(f"unreachable acceptance/terminal task: {task.task_id}")
            if terminal_tasks:
                terminal_ids = {task.task_id for task in terminal_tasks}
                if any(
                    task_id in terminal_ids for task_id, children in outgoing.items() if children
                ):
                    errors.append("impossible terminal node: terminal task has dependents")
    return errors, ready, blocked


def resolve_dag_text(text: str) -> DagState:
    """Resolve a task graph from `tasks.md` content."""
    tasks, metadata, parse_errors = parse_tasks(text)
    errors, ready, blocked = _validate(tasks, metadata)
    errors = parse_errors + errors
    completed = bool(tasks) and all(task.done for task in tasks)
    return DagState(
        valid=not errors,
        legacy=not metadata,
        completed=completed,
        tasks=tuple(tasks),
        ready=tuple(task.task_id for task in ready),
        blocked=tuple(task.task_id for task in blocked),
        errors=tuple(errors),
    )


def resolve_dag(path: Path) -> DagState:
    """Resolve the task graph at `path`.

    An unreadable `tasks.md` is a graph error, not an exception: a missing task
    file must reach the decision layer as evidence rather than crash collection.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return DagState(
            valid=False,
            legacy=False,
            completed=False,
            tasks=(),
            ready=(),
            blocked=(),
            errors=(f"cannot read {path}: {error}",),
            readable=False,
        )
    return resolve_dag_text(text)


def missing_dag(detail: str) -> DagState:
    """The DAG state for a repository with no task file at all."""
    return DagState(
        valid=False,
        legacy=False,
        completed=False,
        tasks=(),
        ready=(),
        blocked=(),
        errors=(detail,),
        readable=False,
    )
