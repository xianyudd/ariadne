#!/usr/bin/env python3
"""Canonical task DAG checks (§B).

The graph algorithm has exactly one implementation, `dag/tasks.py`. These checks
run the existing fixture corpus through the reusable API and assert that the CLI
is a rendering of the same result rather than a second implementation.
"""
from __future__ import annotations

import contextlib
import inspect
import io
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts the package on sys.path)

from ariadne import cli  # noqa: E402
from ariadne.dag import missing_dag, resolve_dag, resolve_dag_text  # noqa: E402

FIXTURES = Path(__file__).with_name("fixtures")

checks = 0


def check(condition: object, label: str) -> None:
    global checks
    assert condition, label
    checks += 1


# The whole fixture corpus, with the verdict each file is designed to produce.
# Five files are classification/terminal-contract fixtures that contain no task
# lines at all; they are listed with `0` tasks so the corpus stays fully covered
# and so an empty graph's semantics are asserted rather than assumed.
EXPECTED: dict[str, tuple[str, bool, int]] = {
    # name: (dag status, legacy, task count)
    "acceptance-terminal.md": ("COMPLETE", False, 2),
    "cycle.md": ("DAG_INVALID", False, 3),
    "impossible-terminal.md": ("DAG_INVALID", False, 2),
    "legacy-complete.md": ("COMPLETE", True, 2),
    "lifecycle-classification.md": ("VALID", True, 0),
    "malformed-id.md": ("DAG_INVALID", True, 0),
    "missing-dependency.md": ("DAG_INVALID", False, 1),
    "mixed-metadata.md": ("DAG_INVALID", False, 2),
    "non-t-id.md": ("DAG_INVALID", True, 0),
    "order.md": ("VALID", False, 2),
    "product-in-progress.md": ("VALID", False, 2),
    "product-ready.md": ("COMPLETE", False, 2),
    "terminal-non-product.md": ("VALID", True, 0),
    "terminal-product-in-progress.md": ("VALID", True, 0),
    "terminal-product-ready.md": ("VALID", True, 0),
    "terminal-unknown.md": ("VALID", True, 0),
    "valid.md": ("VALID", False, 3),
}

present = {path.name for path in FIXTURES.glob("*.md")}
check(present == set(EXPECTED), f"B0 fixture corpus is fully covered: {present ^ set(EXPECTED)}")

for name, (status, legacy, total) in sorted(EXPECTED.items()):
    state = resolve_dag(FIXTURES / name)
    check(state.status == status, f"B1 {name} status {state.status} != {status}")
    check(state.legacy == legacy, f"B1 {name} legacy {state.legacy} != {legacy}")
    check(state.total == total, f"B1 {name} total {state.total} != {total}")
    check(state.valid == (status != "DAG_INVALID"), f"B1 {name} valid tracks status")
    check(bool(state.errors) != state.valid, f"B1 {name} errors iff invalid")
    check(state.readable, f"B1 {name} was readable")
    if total == 0:
        # An empty graph is vacuously valid but must never read as a finished
        # Feature: `completed` is what `/dev-close` and `/dev-merge` rest on.
        check(not state.completed, f"B1 {name} empty graph is not completed")

# --- B2: frontier and blocked sets ------------------------------------------
state = resolve_dag(FIXTURES / "valid.md")
check(state.ready and all(task_id.startswith("T") for task_id in state.ready), "B2 frontier is task IDs")
check(set(state.ready).isdisjoint(state.blocked), "B2 ready and blocked are disjoint")
check(
    len(state.ready) + len(state.blocked) == len(state.incomplete),
    "B2 every unfinished task is either ready or blocked",
)

# Membership, not only shape. `valid.md` is a chain whose first task is done, so
# exactly one task can be ready — and every partition assertion above holds just as
# well when *all* tasks are ready, which is what makes this the load-bearing check
# rather than a restatement.
check(state.ready == ("T002",), f"B2 the frontier is the unblocked task, not every task: {state.ready}")
check(state.blocked == ("T003",), f"B2 an incomplete dependency blocks: {state.blocked}")

# The same rule derived independently for every fixture, so a graph added later
# cannot slip past: READY(task) = unfinished AND every declared dependency completed.
# Compared as sets because ordering is a separate claim, checked just below.
for name in sorted(EXPECTED):
    graph = resolve_dag(FIXTURES / name)
    finished = {task.task_id for task in graph.tasks if task.done}
    satisfied = {
        task.task_id
        for task in graph.tasks
        if not task.done and all(dependency in finished for dependency in task.depends_on)
    }
    check(
        set(graph.ready) == satisfied,
        f"B2 {name} frontier {graph.ready} != dependency-satisfied {sorted(satisfied)}",
    )

order = resolve_dag(FIXTURES / "order.md")
check(list(order.ready) == sorted(order.ready, key=lambda t: int(t[1:])), "B2 frontier order is stable")
check(resolve_dag(FIXTURES / "order.md").ready == order.ready, "B2 resolution is deterministic")

# --- B3: specific diagnostics -----------------------------------------------
check(
    any("cycle" in error for error in resolve_dag(FIXTURES / "cycle.md").errors),
    "B3 cycle is reported as a cycle",
)
check(
    any("depends on missing task" in error for error in resolve_dag(FIXTURES / "missing-dependency.md").errors),
    "B3 missing dependency is reported",
)
check(
    any("impossible terminal" in error for error in resolve_dag(FIXTURES / "impossible-terminal.md").errors),
    "B3 impossible terminal node is reported",
)
check(
    any("malformed task ID" in error for error in resolve_dag(FIXTURES / "malformed-id.md").errors),
    "B3 malformed task ID is reported",
)

# --- B4: completeness and emptiness -----------------------------------------
complete = resolve_dag(FIXTURES / "product-ready.md")
check(complete.completed and not complete.ready, "B4 a complete graph has no frontier")
check(complete.incomplete == (), "B4 a complete graph has no unfinished tasks")

empty = resolve_dag_text("# Tasks\n\nNothing here.\n")
check(empty.valid and not empty.completed and empty.total == 0, "B4 an empty graph is vacuously valid")

# --- B5: unreadable is evidence, not an exception ---------------------------
absent = resolve_dag(FIXTURES / "does-not-exist.md")
check(not absent.valid and not absent.readable, "B5 an unreadable graph is invalid and unreadable")
check(len(absent.errors) == 1, "B5 unreadable reports one diagnostic")
check(not missing_dag("no tasks.md").readable, "B5 a missing graph is unreadable")

# --- B6: the CLI is a renderer over this API --------------------------------
check(cli.resolve_dag is resolve_dag, "B6 CLI uses the canonical resolver")
rendered = cli.render_dag(resolve_dag(FIXTURES / "valid.md"))
check(rendered[0] == "STATUS VALID", "B6 CLI renders the canonical status")
check(any(line.startswith("READY_FRONTIER ") for line in rendered), "B6 CLI renders the frontier")
check(
    cli.render_dag(resolve_dag(FIXTURES / "cycle.md"))[0] == "DAG INVALID",
    "B6 CLI renders an invalid graph",
)

# The renderer must not re-parse the task file. Asserted against the function's own
# source rather than the module's: `cli.py` legitimately reads files elsewhere, and a
# claim about the renderer should be scoped to the renderer.
renderer = inspect.getsource(cli.render_dag)
for forbidden in ("re.compile", "read_text", "Depends:"):
    check(forbidden not in renderer, f"B6 the renderer does not re-implement parsing ({forbidden})")


def validate(path: Path) -> tuple[int, str]:
    """Run `ariadne validate tasks <path>` in-process, returning code and output."""
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = cli.main(["validate", "tasks", str(path)])
    return code, stream.getvalue()

# The documented exit codes, which are how a host learns a graph is unusable: 0 valid,
# 1 read and rejected, 2 not readable at all.
code, output = validate(FIXTURES / "valid.md")
check(code == 0 and output.startswith("STATUS VALID"), "B6 a valid graph exits 0")
code, output = validate(FIXTURES / "cycle.md")
check(code == 1 and output.startswith("DAG INVALID"), "B6 a rejected graph exits 1")
code, output = validate(FIXTURES / "does-not-exist.md")
check(code == 2 and output.startswith("DAG INVALID"), "B6 an unreadable graph exits 2")

print(f"task DAG checks passed ({checks} assertions)")
