"""Ariadne — a governed runtime for agentic software development.

An agent asked to carry a change through a software lifecycle has to be told what it
may do next. Ariadne answers that from the repository rather than from the agent's
own reading of a document:

```text
Repository → Evidence → State → Decision → TerminalGate → Router → Workflow
```

Each layer owns one question and no layer restates another's policy. Evidence judges
nothing, the engine dispatches nothing, the gate maps nothing, the router decides
nothing. A terminal decision is enforced structurally: the gate is the only path to
dispatch, it settles once, and it calls a dispatcher only for `CONTINUE`.

Ariadne knows nothing about the project it governs and nothing about the host running
the agent. A repository's own facts — where its specifications live, which paths are
framework work, what its quality gates are called — arrive through `ProjectConfig`
and the integrations it names. The same repository state and intent therefore produce
the same envelope on every host and in every language.

```python
from ariadne import execute_workflow

result = execute_workflow(repo, "DEV_MERGE", dispatcher, human_gate="APPROVED")
```

This module is a re-export surface. It defines no name of its own and makes no
decision; every symbol below is owned by the module it comes from.
"""

from __future__ import annotations

from .config import (
    CONFIG_DIR,
    CONFIG_FILE,
    DEFAULT_CONFIG,
    ProjectConfig,
    config_path,
    load_project_config,
    parse_project_config,
)
from .dag import (
    DagState,
    Task,
    missing_dag,
    parse_tasks,
    resolve_dag,
    resolve_dag_text,
)
from .documents import (
    contract_names,
    document_names,
    document_path,
    document_text,
    workflow_names,
)
from .integrations import (
    GATE_PASS,
    GATE_UNKNOWN,
    DirectoryPlanning,
    FeatureRegistration,
    GateResults,
    GateSpec,
    NoPlanning,
    PlanningProvider,
    build_provider,
    resolve_gates,
)
from .runtime import (
    CLASSIFICATIONS,
    CLOSED,
    CONTINUE,
    DECISIONS,
    DEV_CLOSE,
    DEV_MERGE,
    DEV_NEW,
    DEV_NEXT,
    HUMAN_GATE_APPROVED,
    HUMAN_GATE_NOT_APPROVED,
    HUMAN_GATE_STATES,
    HUMAN_GATE_UNKNOWN,
    IN_PROGRESS,
    LEGAL_TRANSITIONS,
    LIFECYCLE_STATES,
    NEW,
    NON_PRODUCT,
    PRODUCT_FEATURE,
    PROTOCOL_DECISION_INVALID,
    PROTOCOL_VERSION,
    READY_FOR_IMPLEMENTATION,
    READY_TO_CLOSE,
    REVIEW_OUTSTANDING,
    REVIEW_RESOLVED,
    REVIEW_UNKNOWN,
    STOP,
    TERMINAL_BLOCKED,
    TERMINAL_DECISIONS,
    TERMINAL_NOT_APPLICABLE,
    TERMINAL_SUCCESS,
    UNKNOWN,
    WORKFLOW_INTENTS,
    Decision,
    GateAlreadySettled,
    GateResult,
    InvalidDecision,
    LifecycleResolution,
    RepositoryEvidence,
    ResolvedState,
    RouterRefused,
    TerminalGate,
    WorkflowRouter,
    classify_evidence,
    coerce,
    collect_repository_evidence,
    decide,
    enforce,
    evaluate_state,
    evaluate_workflow,
    execute_workflow,
    protocol_invalid,
    resolve_lifecycle,
    resolve_repository_state,
    resolve_state,
)
from .workflows import WORKFLOWS, workflow_path, workflow_text

__version__ = "2.1.0"

__all__ = [
    "__version__",
    # configuration
    "CONFIG_DIR",
    "CONFIG_FILE",
    "DEFAULT_CONFIG",
    "ProjectConfig",
    "config_path",
    "load_project_config",
    "parse_project_config",
    # integrations
    "GATE_PASS",
    "GATE_UNKNOWN",
    "DirectoryPlanning",
    "FeatureRegistration",
    "GateResults",
    "GateSpec",
    "NoPlanning",
    "PlanningProvider",
    "build_provider",
    "resolve_gates",
    # task graph
    "DagState",
    "Task",
    "missing_dag",
    "parse_tasks",
    "resolve_dag",
    "resolve_dag_text",
    # decision envelope
    "CONTINUE",
    "DECISIONS",
    "PROTOCOL_DECISION_INVALID",
    "PROTOCOL_VERSION",
    "STOP",
    "TERMINAL_BLOCKED",
    "TERMINAL_DECISIONS",
    "TERMINAL_NOT_APPLICABLE",
    "TERMINAL_SUCCESS",
    "Decision",
    "InvalidDecision",
    "coerce",
    "protocol_invalid",
    # classification
    "CLASSIFICATIONS",
    "NON_PRODUCT",
    "PRODUCT_FEATURE",
    "UNKNOWN",
    "classify_evidence",
    # lifecycle
    "CLOSED",
    "IN_PROGRESS",
    "LEGAL_TRANSITIONS",
    "LIFECYCLE_STATES",
    "NEW",
    "READY_FOR_IMPLEMENTATION",
    "READY_TO_CLOSE",
    "LifecycleResolution",
    "resolve_lifecycle",
    # evidence and state
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
    "RepositoryEvidence",
    "ResolvedState",
    "collect_repository_evidence",
    "resolve_repository_state",
    "resolve_state",
    # decision and enforcement
    "GateAlreadySettled",
    "GateResult",
    "RouterRefused",
    "TerminalGate",
    "WorkflowRouter",
    "decide",
    "enforce",
    "evaluate_state",
    "evaluate_workflow",
    "execute_workflow",
    # workflow definitions
    "WORKFLOWS",
    "workflow_path",
    "workflow_text",
    # shipped documents
    "contract_names",
    "document_names",
    "document_path",
    "document_text",
    "workflow_names",
]
