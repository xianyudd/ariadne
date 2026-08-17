#!/usr/bin/env python3
"""Canonical task DAG checks (§B).

The graph algorithm has exactly one implementation, `runtime/dag.py`. These checks
run the existing fixture corpus through the reusable API and assert that the CLI
is a rendering of the same result rather than a second implementation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_tasks  # noqa: E402
from runtime.dag import missing_dag, resolve_dag, resolve_dag_text  # noqa: E402

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
check(validate_tasks.resolve_dag is resolve_dag, "B6 CLI uses the canonical resolver")
rendered = validate_tasks.render(resolve_dag(FIXTURES / "valid.md"))
check(rendered[0] == "STATUS VALID", "B6 CLI renders the canonical status")
check(any(line.startswith("READY_FRONTIER ") for line in rendered), "B6 CLI renders the frontier")
check(
    validate_tasks.render(resolve_dag(FIXTURES / "cycle.md"))[0] == "DAG INVALID",
    "B6 CLI renders an invalid graph",
)

# The CLI must not re-parse tasks.md itself.
cli_source = Path(validate_tasks.__file__).read_text(encoding="utf-8")
for forbidden in ("re.compile", "read_text", "Depends:"):
    check(forbidden not in cli_source, f"B6 CLI does not re-implement parsing ({forbidden})")

print(f"task DAG checks passed ({checks} assertions)")
