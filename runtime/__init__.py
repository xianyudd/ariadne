"""Agent SDLC runtime.

The runtime owns the executable path from repository facts to workflow execution:

```text
Repository → Evidence → State → Decision → Envelope → TerminalGate → Router → Workflow
```

Core declares the semantics in `.agent-sdlc/core/`; this package is what runs.
A decision is repository-derived, carried as one validated envelope, and enforced
structurally: the terminal gate is the only path to dispatch and it dispatches
only for `CONTINUE`.

Standard library only. Nothing here depends on a host tool, model, provider, or
invocation syntax, so the same repository state yields the same decision on every
host.
"""

from __future__ import annotations

from .api import (
    enforce,
    evaluate_state,
    evaluate_workflow,
    execute_workflow,
)
from .classification import (
    CLASSIFICATIONS,
    NON_PRODUCT,
    PRODUCT_FEATURE,
    UNKNOWN,
    classify_evidence,
    classify_facts,
)
from .dag import DagState, Task, missing_dag, parse_tasks, resolve_dag, resolve_dag_text
from .decision import (
    CONTINUE,
    DECISIONS,
    FIELD_ORDER,
    PROTOCOL_DECISION_INVALID,
    PROTOCOL_VERSION,
    RESERVED_REASON_PREFIX,
    STOP,
    TERMINAL_BLOCKED,
    TERMINAL_DECISIONS,
    TERMINAL_NOT_APPLICABLE,
    TERMINAL_SUCCESS,
    Decision,
    InvalidDecision,
    coerce,
    protocol_invalid,
)
from .decision_engine import (
    DECISION_PHASE,
    STATUS_BLOCKED,
    STATUS_NOT_APPLICABLE,
    STATUS_READY,
    decide,
)
from .evidence import (
    FeatureEvidence,
    GitEvidence,
    RecordedEvidence,
    RepositoryEvidence,
    collect_repository_evidence,
    workflow_only_changes,
)
from .lifecycle import (
    CLOSED,
    IN_PROGRESS,
    LEGAL_TRANSITIONS,
    LIFECYCLE_STATES,
    NEW,
    READY_FOR_IMPLEMENTATION,
    READY_TO_CLOSE,
    IllegalTransition,
    LifecycleResolution,
    assert_legal_transition,
    is_legal_transition,
    resolve_lifecycle,
)
from .router import RouterRefused, WorkflowRouter
from .state import (
    DEV_CLOSE,
    DEV_MERGE,
    DEV_NEW,
    DEV_NEXT,
    HUMAN_GATE_APPROVED,
    HUMAN_GATE_NOT_APPROVED,
    HUMAN_GATE_STATES,
    HUMAN_GATE_UNKNOWN,
    REVIEW_OUTSTANDING,
    REVIEW_RESOLVED,
    REVIEW_UNKNOWN,
    WORKFLOW_INTENTS,
    ResolvedState,
    SafetyState,
    resolve_repository_state,
    resolve_state,
)
from .terminal_gate import GateAlreadySettled, GateResult, TerminalGate

__all__ = [
    # decision envelope
    "CONTINUE",
    "DECISIONS",
    "FIELD_ORDER",
    "PROTOCOL_DECISION_INVALID",
    "PROTOCOL_VERSION",
    "RESERVED_REASON_PREFIX",
    "STOP",
    "TERMINAL_BLOCKED",
    "TERMINAL_DECISIONS",
    "TERMINAL_NOT_APPLICABLE",
    "TERMINAL_SUCCESS",
    "Decision",
    "InvalidDecision",
    "coerce",
    "protocol_invalid",
    # evidence
    "FeatureEvidence",
    "GitEvidence",
    "RecordedEvidence",
    "RepositoryEvidence",
    "collect_repository_evidence",
    "workflow_only_changes",
    # task dag
    "DagState",
    "Task",
    "missing_dag",
    "parse_tasks",
    "resolve_dag",
    "resolve_dag_text",
    # classification
    "CLASSIFICATIONS",
    "NON_PRODUCT",
    "PRODUCT_FEATURE",
    "UNKNOWN",
    "classify_evidence",
    "classify_facts",
    # lifecycle
    "CLOSED",
    "IN_PROGRESS",
    "LEGAL_TRANSITIONS",
    "LIFECYCLE_STATES",
    "NEW",
    "READY_FOR_IMPLEMENTATION",
    "READY_TO_CLOSE",
    "IllegalTransition",
    "LifecycleResolution",
    "assert_legal_transition",
    "is_legal_transition",
    "resolve_lifecycle",
    # state
    "DEV_CLOSE",
    "DEV_MERGE",
    "DEV_NEW",
    "DEV_NEXT",
    "HUMAN_GATE_APPROVED",
    "HUMAN_GATE_NOT_APPROVED",
    "HUMAN_GATE_STATES",
    "HUMAN_GATE_UNKNOWN",
    "REVIEW_OUTSTANDING",
    "REVIEW_RESOLVED",
    "REVIEW_UNKNOWN",
    "WORKFLOW_INTENTS",
    "ResolvedState",
    "SafetyState",
    "resolve_repository_state",
    "resolve_state",
    # decision engine
    "DECISION_PHASE",
    "STATUS_BLOCKED",
    "STATUS_NOT_APPLICABLE",
    "STATUS_READY",
    "decide",
    # enforcement
    "GateAlreadySettled",
    "GateResult",
    "TerminalGate",
    # router
    "RouterRefused",
    "WorkflowRouter",
    # runtime boundary
    "enforce",
    "evaluate_state",
    "evaluate_workflow",
    "execute_workflow",
]
