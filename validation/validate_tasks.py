#!/usr/bin/env python3
"""Validate compact task dependencies embedded in a tasks.md file.

This uses only the Python standard library. It is intentionally small: tasks.md
remains the sole task truth, while this script validates scheduling metadata.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

TASK_RE = re.compile(r"^- \[(?P<done>[ xX])\] (?P<id>T\d{3,})\b(?P<body>.*)$")
CHECKBOX_RE = re.compile(r"^- \[[ xX]\](?:\s+|$)")
DEPENDS_RE = re.compile(r"^\s+Depends:\s*(?P<deps>.*)$", re.IGNORECASE)
ACCEPTANCE_RE = re.compile(r"^\s+Acceptance:\s*(?P<value>true|false|yes|no|1|0)\s*$", re.IGNORECASE)
TERMINAL_RE = re.compile(r"^\s+Terminal:\s*(?P<value>true|false|yes|no|1|0)\s*$", re.IGNORECASE)


@dataclass
class Task:
    task_id: str
    done: bool
    line: int
    depends_on: list[str] = field(default_factory=list)
    has_metadata: bool = False
    acceptance: bool = False
    terminal: bool = False


def parse(path: Path) -> tuple[list[Task], bool, list[str]]:
    tasks: list[Task] = []
    errors: list[str] = []
    has_metadata = False
    lines = path.read_text(encoding="utf-8").splitlines()
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
                task.acceptance = acceptance_match.group("value").lower() in {"true", "yes", "1"}
            if terminal_match:
                has_metadata = True
                task.has_metadata = True
                task.terminal = terminal_match.group("value").lower() in {"true", "yes", "1"}
            cursor += 1
        tasks.append(task)
    return tasks, has_metadata, errors


def validate(tasks: list[Task], metadata: bool) -> tuple[list[str], list[Task], list[Task]]:
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
            if task.done and any(dependency in by_id and not by_id[dependency].done for dependency in task.depends_on):
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
                if any(task_id in terminal_ids for task_id, children in outgoing.items() if children):
                    errors.append("impossible terminal node: terminal task has dependents")
    return errors, ready, blocked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", type=Path)
    args = parser.parse_args()
    try:
        tasks, metadata, parse_errors = parse(args.tasks)
    except OSError as error:
        print(f"DAG INVALID\ncannot read {args.tasks}: {error}")
        return 2
    errors, ready, blocked = validate(tasks, metadata)
    errors = parse_errors + errors
    if errors:
        print("DAG INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    if not metadata:
        print("STATUS LEGACY_TASK_FORMAT")
    if not tasks or all(task.done for task in tasks):
        print(f"STATUS COMPLETE\nTASKS {len(tasks)}\nREADY_FRONTIER empty\nBLOCKED 0")
        return 0
    print(f"STATUS VALID\nTASKS {len(tasks)}")
    print("READY_FRONTIER " + (", ".join(task.task_id for task in ready) or "empty"))
    print("BLOCKED " + (", ".join(task.task_id for task in blocked) or "0"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
