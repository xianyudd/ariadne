"""Unified resolved state for the Agent SDLC runtime.

`RepositoryEvidence` is collected once; this module resolves it once into the
single state value every later layer consumes. The classifier, the lifecycle
resolver, the decision engine, the gate and the router therefore all see the
same repository, and none of them re-reads it.

This module answers *what is the current state?* It grants nothing.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import ProjectConfig
from .classification import classify_evidence
from .evidence import RepositoryEvidence, collect_repository_evidence
from .lifecycle import LifecycleResolution, resolve_lifecycle

# Workflow intents. These are the runtime's own identifiers for the declared
# entry points, documented by `ariadne doc <workflow>`; not host command syntax.
DEV_NEW = "DEV_NEW"
DEV_NEXT = "DEV_NEXT"
DEV_CLOSE = "DEV_CLOSE"
DEV_MERGE = "DEV_MERGE"

WORKFLOW_INTENTS = frozenset({DEV_NEW, DEV_NEXT, DEV_CLOSE, DEV_MERGE})

# Review state, from recorded evidence only. The runtime never performs a review.
REVIEW_RESOLVED = "RESOLVED"
REVIEW_OUTSTANDING = "OUTSTANDING"
REVIEW_UNKNOWN = "UNKNOWN"

# Human Gate state. `UNKNOWN` fails closed wherever a gate is required.
HUMAN_GATE_APPROVED = "APPROVED"
HUMAN_GATE_NOT_APPROVED = "NOT_APPROVED"
HUMAN_GATE_UNKNOWN = "UNKNOWN"

HUMAN_GATE_STATES = frozenset({HUMAN_GATE_APPROVED, HUMAN_GATE_NOT_APPROVED, HUMAN_GATE_UNKNOWN})


@dataclass(frozen=True)
class SafetyState:
    """Deterministic safety facts that a decision may rest on."""

    tracked_dirty: bool
    protected_paths: tuple[str, ...]
    git_available: bool

    @property
    def safe(self) -> bool:
        """Whether the working tree is safe for a mutating workflow phase.

        Protected paths are exempt by project policy but still reported, so their
        presence alone never makes the tree unsafe.
        """
        return self.git_available and not self.tracked_dirty

    def facts(self) -> tuple[str, ...]:
        return (
            f"tracked_dirty={'yes' if self.tracked_dirty else 'no'}",
            f"protected_paths_exempted={len(self.protected_paths)}",
        )


@dataclass(frozen=True)
class ResolvedState:
    """Everything the decision engine is allowed to read.

    Constructed once per invocation from one evidence collection. A caller may
    supply `human_gate` (an out-of-band human authorisation the repository cannot
    prove) but never `lifecycle`: that is always derived.
    """

    workflow_intent: str
    entity: str
    lifecycle: LifecycleResolution
    review: str
    safety: SafetyState
    human_gate: str
    dry_run: bool
    evidence: RepositoryEvidence

    @property
    def lifecycle_state(self) -> str:
        return self.lifecycle.state

    @property
    def lifecycle_derived(self) -> bool:
        return self.lifecycle.derived

    def facts(self) -> tuple[str, ...]:
        """The ordered evidence a decision envelope records."""
        return (
            f"workflow_intent={self.workflow_intent}",
            f"entity={self.entity}",
            f"lifecycle={self.lifecycle.state}",
            f"lifecycle_derived={'yes' if self.lifecycle.derived else 'no'}",
            f"lifecycle_reason={self.lifecycle.reason}",
            f"review={self.review}",
            f"human_gate={self.human_gate}",
            f"dry_run={'yes' if self.dry_run else 'no'}",
            *self.safety.facts(),
            *self.evidence.facts(),
        )


def _review_state(evidence: RepositoryEvidence) -> str:
    recorded = evidence.recorded
    if recorded.review_outstanding:
        return REVIEW_OUTSTANDING
    if recorded.review_resolved:
        return REVIEW_RESOLVED
    return REVIEW_UNKNOWN


def resolve_state(
    evidence: RepositoryEvidence,
    workflow_intent: str,
    *,
    human_gate: str = HUMAN_GATE_UNKNOWN,
    dry_run: bool = False,
) -> ResolvedState:
    """Resolve one state value from one evidence collection.

    An unrecognised `human_gate` is narrowed to `UNKNOWN` rather than trusted, so
    an unexpected token cannot read as approval.
    """
    if human_gate not in HUMAN_GATE_STATES:
        human_gate = HUMAN_GATE_UNKNOWN
    return ResolvedState(
        workflow_intent=workflow_intent,
        entity=classify_evidence(evidence),
        lifecycle=resolve_lifecycle(evidence),
        review=_review_state(evidence),
        safety=SafetyState(
            tracked_dirty=evidence.git.tracked_dirty,
            protected_paths=evidence.git.protected_paths,
            git_available=evidence.git.available,
        ),
        human_gate=human_gate,
        dry_run=dry_run,
        evidence=evidence,
    )


def resolve_repository_state(
    root: Path,
    workflow_intent: str,
    *,
    human_gate: str = HUMAN_GATE_UNKNOWN,
    dry_run: bool = False,
    config: ProjectConfig | None = None,
    default_branch: str | None = None,
) -> ResolvedState:
    """Collect evidence once, then resolve state once.

    Configuration is read from the repository unless a caller supplies it. It
    describes the repository; it never reaches decision-making, which reads only
    the resolved state.
    """
    evidence = collect_repository_evidence(root, config=config, default_branch=default_branch)
    return resolve_state(
        evidence,
        workflow_intent,
        human_gate=human_gate,
        dry_run=dry_run,
    )
