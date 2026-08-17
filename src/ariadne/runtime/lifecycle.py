"""Lifecycle state resolution and legal transitions.

The lifecycle declared in `contracts/lifecycle.md` is:

```text
NEW → READY_FOR_IMPLEMENTATION → IN_PROGRESS → READY_TO_CLOSE → CLOSED
```

This module makes that machine executable. It answers exactly one question:
*what state is the repository in?* — derived from `RepositoryEvidence`, never
supplied by a caller on a normal runtime path. It grants nothing; permission is
`decision_engine.py`'s job.

Insufficient or contradictory evidence resolves to `UNKNOWN`, which the decision
layer treats as fail-closed. The resolver never guesses and never writes.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass

from .evidence import RepositoryEvidence

NEW = "NEW"
READY_FOR_IMPLEMENTATION = "READY_FOR_IMPLEMENTATION"
IN_PROGRESS = "IN_PROGRESS"
READY_TO_CLOSE = "READY_TO_CLOSE"
CLOSED = "CLOSED"
UNKNOWN = "UNKNOWN"

LIFECYCLE_STATES = (
    NEW,
    READY_FOR_IMPLEMENTATION,
    IN_PROGRESS,
    READY_TO_CLOSE,
    CLOSED,
)
"""The declared states, in forward order. `UNKNOWN` is not a lifecycle position."""

RESOLVABLE_STATES = frozenset(LIFECYCLE_STATES) | {UNKNOWN}

# The one legal-transition table. Core declares a strictly forward lifecycle and
# documents no rollback, so none is invented here.
LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    NEW: frozenset({READY_FOR_IMPLEMENTATION}),
    READY_FOR_IMPLEMENTATION: frozenset({IN_PROGRESS}),
    IN_PROGRESS: frozenset({READY_TO_CLOSE}),
    READY_TO_CLOSE: frozenset({CLOSED}),
    CLOSED: frozenset(),
}


@dataclass(frozen=True)
class LifecycleResolution:
    """A resolved lifecycle state with the evidence that produced it.

    `derived` records that the state came from repository evidence rather than
    from a caller. A normal runtime path requires it to be true; it is the
    machine-checkable form of "no manual lifecycle state in production".
    """

    state: str
    derived: bool
    evidence: tuple[str, ...]
    reason: str

    @property
    def known(self) -> bool:
        return self.state != UNKNOWN


def is_legal_transition(source: str, target: str) -> bool:
    """Whether `source → target` is a declared legal transition."""
    if source == target:
        return False
    return target in LEGAL_TRANSITIONS.get(source, frozenset())


def assert_legal_transition(source: str, target: str) -> None:
    """Raise `IllegalTransition` unless `source → target` is declared legal."""
    if not is_legal_transition(source, target):
        raise IllegalTransition(f"{source} → {target} is not a legal lifecycle transition")


class IllegalTransition(ValueError):
    """A lifecycle transition that the declared state machine does not permit."""


def resolve_lifecycle(evidence: RepositoryEvidence) -> LifecycleResolution:
    """Derive the lifecycle state of the registered Feature from evidence.

    The order below is deliberate: `CLOSED` is proven by Git ancestry, and every
    other state is proven by the task graph plus recorded acceptance evidence. Any
    combination that no rule explains resolves to `UNKNOWN` rather than to the
    nearest plausible state.
    """
    facts = evidence.facts()
    feature = evidence.feature
    dag = evidence.dag
    recorded = evidence.recorded

    if not evidence.git.available:
        return LifecycleResolution(UNKNOWN, True, facts, "git state is unavailable")

    if feature.registered_name is None:
        return LifecycleResolution(NEW, True, facts, "no Feature registration exists")

    if not feature.directory_exists:
        return LifecycleResolution(
            UNKNOWN, True, facts, "Feature registration does not resolve to a directory"
        )

    if not feature.required_artifacts:
        return LifecycleResolution(
            NEW, True, facts, "registered Feature lacks spec.md/plan.md/tasks.md"
        )

    # A merged Feature branch is the one closure fact Git can prove by itself.
    # The fact used is about the Feature's own branch, not about whatever branch
    # happens to be checked out: a Feature does not become un-closed because the
    # session moved to another branch. `None` means Git could not answer, which is
    # not evidence of closure.
    merged = evidence.git.feature_merged_into_default
    if merged is None and evidence.git.branch == evidence.git.feature_branch:
        merged = evidence.git.merged_into_default
    if merged is True and dag.completed:
        return LifecycleResolution(
            CLOSED,
            True,
            facts,
            f"Feature branch is an ancestor of {evidence.git.default_branch} and every task is complete",
        )

    if not dag.valid:
        return LifecycleResolution(
            UNKNOWN,
            True,
            facts,
            f"task graph is not valid: {dag.errors[0] if dag.errors else 'unknown defect'}",
        )

    if recorded.review_outstanding:
        return LifecycleResolution(
            IN_PROGRESS, True, facts, "recorded review findings are unresolved"
        )

    if dag.completed:
        if not recorded.review_resolved:
            return LifecycleResolution(
                IN_PROGRESS, True, facts, "all tasks complete but no resolved review is recorded"
            )
        if not recorded.quality_gates_recorded:
            return LifecycleResolution(
                IN_PROGRESS, True, facts, "all tasks complete but no quality-gate evidence is recorded"
            )
        if not recorded.closure_recorded:
            return LifecycleResolution(
                IN_PROGRESS,
                True,
                facts,
                "all tasks complete and reviewed but final acceptance is not recorded",
            )
        return LifecycleResolution(
            READY_TO_CLOSE,
            True,
            facts,
            "every task complete, review resolved, gates and final acceptance recorded",
        )

    if any(task.done for task in dag.tasks):
        return LifecycleResolution(IN_PROGRESS, True, facts, "some tasks are complete, others are not")

    if dag.legacy:
        return LifecycleResolution(
            UNKNOWN,
            True,
            facts,
            "legacy task format with an unproven frontier",
        )

    if dag.ready:
        return LifecycleResolution(
            READY_FOR_IMPLEMENTATION,
            True,
            facts,
            "specification artifacts and a valid task graph exist with a ready frontier",
        )

    return LifecycleResolution(UNKNOWN, True, facts, "task graph explains no lifecycle position")
