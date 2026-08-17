#!/usr/bin/env python3
"""Lifecycle checks (§C).

Every state below is derived from a real repository, not supplied. That is the
point: `contracts/lifecycle.md` declares the state machine, and the
resolver's job is to prove which position the repository is actually in.

Two properties are asserted throughout:

* insufficient or contradictory evidence resolves to `UNKNOWN` — never to the
  nearest plausible state;
* only the declared forward transitions are legal, and an illegal one is
  rejectable by machine.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts the package on sys.path)

from repo_fixture import (  # noqa: E402
    CLOSURE_RECORDED,
    GATES_RECORDED,
    REVIEW_CLEAN,
    REVIEW_OUTSTANDING,
    TASKS_COMPLETE,
    TASKS_CYCLE,
    TASKS_LEGACY,
    TASKS_PARTIAL,
    TASKS_READY,
    make_repo,
)
from ariadne.runtime.evidence import collect_repository_evidence  # noqa: E402
from ariadne.runtime.lifecycle import (  # noqa: E402
    CLOSED,
    IN_PROGRESS,
    LEGAL_TRANSITIONS,
    LIFECYCLE_STATES,
    NEW,
    READY_FOR_IMPLEMENTATION,
    READY_TO_CLOSE,
    UNKNOWN,
    IllegalTransition,
    assert_legal_transition,
    is_legal_transition,
    resolve_lifecycle,
)
from ariadne.runtime.state import resolve_repository_state  # noqa: E402

checks = 0


def check(condition: object, label: str) -> None:
    global checks
    assert condition, label
    checks += 1


def resolved(**kwargs: object) -> tuple[str, str]:
    """Build a repository, derive its lifecycle, and return (state, reason)."""
    with make_repo(**kwargs) as fixture:  # type: ignore[arg-type]
        resolution = resolve_lifecycle(collect_repository_evidence(fixture.root))
        check(resolution.derived, "C0 every resolution is repository-derived")
        check(resolution.evidence, "C0 every resolution carries its evidence")
        return resolution.state, resolution.reason


# --- C1: one real repository per declared state ------------------------------
CASES: dict[str, dict[str, object]] = {
    # NEW: nothing prepared. Two real shapes reach it.
    "NEW/no-registration": dict(feature=None),
    "NEW/no-artifacts": dict(tasks=None, include_plan=False),
    # READY_FOR_IMPLEMENTATION: artifacts, valid graph, nothing started.
    "READY_FOR_IMPLEMENTATION/frontier": dict(tasks=TASKS_READY),
    # IN_PROGRESS: work started, or finished but not yet accepted.
    "IN_PROGRESS/partial": dict(tasks=TASKS_PARTIAL),
    "IN_PROGRESS/unresolved-review": dict(tasks=TASKS_PARTIAL, handoff_lines=(REVIEW_OUTSTANDING,)),
    "IN_PROGRESS/complete-unreviewed": dict(tasks=TASKS_COMPLETE),
    "IN_PROGRESS/complete-no-gates": dict(tasks=TASKS_COMPLETE, handoff_lines=(REVIEW_CLEAN,)),
    "IN_PROGRESS/complete-no-acceptance": dict(
        tasks=TASKS_COMPLETE, handoff_lines=(REVIEW_CLEAN, GATES_RECORDED)
    ),
    # READY_TO_CLOSE: complete, reviewed, gated, accepted, not merged.
    "READY_TO_CLOSE/accepted": dict(
        tasks=TASKS_COMPLETE, handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED)
    ),
    # CLOSED: merged into the default branch with every task complete.
    "CLOSED/merged": dict(
        tasks=TASKS_COMPLETE,
        handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
        merge_into_main=True,
    ),
    # UNKNOWN: evidence that explains no position.
    "UNKNOWN/no-git": dict(git=False),
    "UNKNOWN/dangling-registration": dict(feature_dir_exists=False),
    "UNKNOWN/invalid-graph": dict(tasks=TASKS_CYCLE),
    "UNKNOWN/legacy-unproven": dict(tasks=TASKS_LEGACY),
}

for label, kwargs in CASES.items():
    expected = label.split("/", 1)[0]
    state, reason = resolved(**kwargs)
    check(state == expected, f"C1 {label} resolved {state}, expected {expected}")
    check(reason, f"C1 {label} states why")

covered = {label.split("/", 1)[0] for label in CASES}
check(covered == set(LIFECYCLE_STATES) | {UNKNOWN}, f"C1 every state has a fixture: {covered}")

# --- C2: a closed Feature stays closed from another branch ------------------
# The Feature's lifecycle depends on the Feature's own branch, not on whichever
# branch happens to be checked out.
with make_repo(
    branch="agent-sdlc-v2",
    spec_branch="002-example",
    state_branch="002-example",
    feature_on_main=True,
    workflow_change=True,
    tasks=TASKS_COMPLETE,
    handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(evidence.git.branch == "agent-sdlc-v2", "C2 on a different branch")
    check(
        resolve_lifecycle(evidence).state == READY_TO_CLOSE,
        "C2 an unprovable merge is not evidence of closure",
    )

# --- C3: `UNKNOWN` is not a lifecycle position ------------------------------
check(UNKNOWN not in LIFECYCLE_STATES, "C3 UNKNOWN is not a declared state")
check(UNKNOWN not in LEGAL_TRANSITIONS, "C3 UNKNOWN has no transitions out")
check(
    all(UNKNOWN not in targets for targets in LEGAL_TRANSITIONS.values()),
    "C3 nothing transitions into UNKNOWN",
)

# --- C4: only the declared forward transitions are legal --------------------
DECLARED = {
    (NEW, READY_FOR_IMPLEMENTATION),
    (READY_FOR_IMPLEMENTATION, IN_PROGRESS),
    (IN_PROGRESS, READY_TO_CLOSE),
    (READY_TO_CLOSE, CLOSED),
}
for source in LIFECYCLE_STATES:
    for target in LIFECYCLE_STATES:
        expected_legal = (source, target) in DECLARED
        check(
            is_legal_transition(source, target) == expected_legal,
            f"C4 {source} → {target} legality is {expected_legal}",
        )

check(not is_legal_transition(IN_PROGRESS, IN_PROGRESS), "C4 a state does not transition to itself")
check(not is_legal_transition(READY_TO_CLOSE, IN_PROGRESS), "C4 no documented rollback exists")
check(not is_legal_transition(NEW, CLOSED), "C4 no state is skipped")
check(not is_legal_transition(CLOSED, READY_TO_CLOSE), "C4 CLOSED is terminal")
check(not is_legal_transition(UNKNOWN, IN_PROGRESS), "C4 UNKNOWN grants no transition")

# --- C5: an illegal transition is machine-rejectable ------------------------
assert_legal_transition(IN_PROGRESS, READY_TO_CLOSE)
checks += 1
for source, target in (
    (READY_TO_CLOSE, IN_PROGRESS),
    (NEW, CLOSED),
    (CLOSED, CLOSED),
    (UNKNOWN, CLOSED),
):
    try:
        assert_legal_transition(source, target)
    except IllegalTransition:
        checks += 1
    else:  # pragma: no cover - the assertion below is the failure report
        raise AssertionError(f"C5 {source} → {target} was not rejected")

# --- C6: no runtime path accepts an injected lifecycle state ----------------
import inspect  # noqa: E402

for function in (resolve_lifecycle, resolve_repository_state):
    parameters = set(inspect.signature(function).parameters)
    check(
        not any("lifecycle" in name for name in parameters),
        f"C6 {function.__name__} has no lifecycle parameter",
    )

with make_repo(tasks=TASKS_PARTIAL) as fixture:
    state = resolve_repository_state(fixture.root, "DEV_NEXT")
    check(state.lifecycle_state == IN_PROGRESS, "C6 the resolved state is the derived state")
    check(state.lifecycle_derived, "C6 derivation is recorded on the state")

print(f"lifecycle checks passed ({checks} assertions)")
