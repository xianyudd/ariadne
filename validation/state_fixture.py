#!/usr/bin/env python3
"""In-memory state fixtures for exhaustive decision coverage.

Test support, not runtime code. `repo_fixture.py` builds real repositories, which
is how evidence, classification, and lifecycle derivation are tested. This module
covers the complementary need: enumerating every entity × lifecycle × workflow
combination without building a repository for each one.

A synthetic state is still a complete `ResolvedState` built from a complete
`RepositoryEvidence`, so the decision engine sees exactly the shape it sees in
production. Only the facts are fabricated, never the derivation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.dag import DagState, Task  # noqa: E402
from runtime.evidence import (  # noqa: E402
    FeatureEvidence,
    GitEvidence,
    RecordedEvidence,
    RepositoryEvidence,
)
from runtime.lifecycle import LifecycleResolution  # noqa: E402
from runtime.state import (  # noqa: E402
    HUMAN_GATE_UNKNOWN,
    ResolvedState,
    SafetyState,
)

FIXTURE_ROOT = Path("/nonexistent/synthetic")


def dag_state(
    *,
    valid: bool = True,
    completed: bool = False,
    legacy: bool = False,
    ready: tuple[str, ...] = ("T001",),
    blocked: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
    tasks: tuple[Task, ...] | None = None,
) -> DagState:
    if tasks is None:
        tasks = (Task("T001", completed, 1),)
    return DagState(
        valid=valid,
        legacy=legacy,
        completed=completed,
        tasks=tasks,
        ready=() if completed else ready,
        blocked=blocked,
        errors=errors,
    )


def evidence(
    *,
    git_available: bool = True,
    branch: str = "002-example",
    tracked_dirty: bool = False,
    protected_paths: tuple[str, ...] = (),
    merged: bool | None = False,
    review_resolved: bool = True,
    review_outstanding: bool = False,
    dag: DagState | None = None,
) -> RepositoryEvidence:
    return RepositoryEvidence(
        root=FIXTURE_ROOT,
        git=GitEvidence(
            available=git_available,
            branch=branch if git_available else None,
            head="0" * 40 if git_available else None,
            changed_paths=("src/example.rs",),
            protected_paths=protected_paths,
            tracked_dirty=tracked_dirty,
            merged_into_default=merged,
            default_branch="main",
            feature_branch=branch,
            feature_merged_into_default=merged,
        ),
        feature=FeatureEvidence(
            registered_name="002-example",
            directory=FIXTURE_ROOT / "specs" / "002-example",
            directory_exists=True,
            required_artifacts=True,
            spec_branch="002-example",
            tasks_path=FIXTURE_ROOT / "specs" / "002-example" / "tasks.md",
        ),
        recorded=RecordedEvidence(
            state_branch="002-example",
            active_feature="002-example",
            review_resolved=review_resolved,
            review_outstanding=review_outstanding,
            quality_gates_recorded=True,
            closure_recorded=True,
        ),
        dag=dag if dag is not None else dag_state(),
    )


def state(
    *,
    workflow_intent: str,
    entity: str,
    lifecycle: str,
    review: str,
    human_gate: str = HUMAN_GATE_UNKNOWN,
    dry_run: bool = False,
    tracked_dirty: bool = False,
    git_available: bool = True,
    dag: DagState | None = None,
    lifecycle_derived: bool = True,
) -> ResolvedState:
    """Build one complete `ResolvedState` for a specific combination."""
    collected = evidence(git_available=git_available, tracked_dirty=tracked_dirty, dag=dag)
    return ResolvedState(
        workflow_intent=workflow_intent,
        entity=entity,
        lifecycle=LifecycleResolution(
            state=lifecycle,
            derived=lifecycle_derived,
            evidence=collected.facts(),
            reason="synthetic fixture",
        ),
        review=review,
        safety=SafetyState(
            tracked_dirty=tracked_dirty,
            protected_paths=collected.git.protected_paths,
            git_available=git_available,
        ),
        human_gate=human_gate,
        dry_run=dry_run,
        evidence=collected,
    )
