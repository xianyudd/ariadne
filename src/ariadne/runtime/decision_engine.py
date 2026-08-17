"""Canonical Decision Engine: the one executable decision policy.

This module answers exactly one question: *given the resolved state, what does
the protocol permit right now?* It is the single executable source of truth for
`CONTINUE`/`TERMINAL_*`. Markdown in `contracts/` specifies these rules
for humans and agents; the tables here are what actually runs, and
`tests/test_decision_consistency.py` fails if the two drift.

The engine is a pure function of `ResolvedState`. It reads no repository, holds
no control flow, and dispatches nothing: `terminal_gate.py` owns enforcement and
`router.py` owns dispatch.

Every rule below is derived from an existing repository contract. No new product
flow is invented here.

Standard library only.
"""

from __future__ import annotations

from . import lifecycle as lc
from .classification import NON_PRODUCT, PRODUCT_FEATURE, UNKNOWN
from .decision import (
    CONTINUE,
    PROTOCOL_VERSION,
    STOP,
    TERMINAL_BLOCKED,
    TERMINAL_NOT_APPLICABLE,
    Decision,
)
from .state import (
    DEV_CLOSE,
    DEV_MERGE,
    DEV_NEW,
    DEV_NEXT,
    HUMAN_GATE_APPROVED,
    REVIEW_OUTSTANDING,
    REVIEW_RESOLVED,
    ResolvedState,
)

# Reported statuses. `contracts/terminal-contract.md` fixes the terminal
# mapping; `READY` is the CONTINUE status used by the dev-merge and dev-new tables.
STATUS_READY = "READY"
STATUS_BLOCKED = "BLOCKED"
STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"

# Workflow-owned reason codes. The `PROTOCOL_` prefix is reserved for the
# framework (`contracts/decision-envelope.md`), so none appears here.
REASON_GIT_UNAVAILABLE = "GIT_STATE_UNAVAILABLE"
REASON_ENTITY_UNKNOWN = "ENTITY_UNKNOWN"
REASON_ENTITY_NOT_PRODUCT = "ENTITY_NOT_PRODUCT_FEATURE"
REASON_LIFECYCLE_UNKNOWN = "LIFECYCLE_UNKNOWN"
REASON_NOT_READY_TO_CLOSE = "LIFECYCLE_NOT_READY_TO_CLOSE"
REASON_BASE_STATE_NOT_ALLOWED = "LIFECYCLE_BASE_STATE_NOT_ALLOWED"
REASON_TASKS_INCOMPLETE = "TASKS_INCOMPLETE"
REASON_DAG_INVALID = "DAG_INVALID"
REASON_NO_READY_FRONTIER = "NO_READY_FRONTIER"
REASON_REVIEW_UNRESOLVED = "REVIEW_UNRESOLVED"
REASON_WORKING_TREE_UNSAFE = "WORKING_TREE_UNSAFE"
REASON_MERGE_AUTHORIZATION = "MERGE_AUTHORIZATION_REQUIRED"
REASON_FEATURE_CLOSED = "FEATURE_ALREADY_CLOSED"
REASON_UNSUPPORTED_INTENT = "WORKFLOW_INTENT_UNSUPPORTED"

# Every reason code this engine can emit. Declared as a set so the vocabulary is
# enumerable: `tests/test_decision_consistency.py` requires each
# entry to be documented in Core, and requires nothing here to be unreachable.
REASON_CODES = frozenset(
    {
        REASON_GIT_UNAVAILABLE,
        REASON_ENTITY_UNKNOWN,
        REASON_ENTITY_NOT_PRODUCT,
        REASON_LIFECYCLE_UNKNOWN,
        REASON_NOT_READY_TO_CLOSE,
        REASON_BASE_STATE_NOT_ALLOWED,
        REASON_TASKS_INCOMPLETE,
        REASON_DAG_INVALID,
        REASON_NO_READY_FRONTIER,
        REASON_REVIEW_UNRESOLVED,
        REASON_WORKING_TREE_UNSAFE,
        REASON_MERGE_AUTHORIZATION,
        REASON_FEATURE_CLOSED,
        REASON_UNSUPPORTED_INTENT,
    }
)

# The decision point that precedes every workflow pipeline. `/dev-merge` declares
# this phase name explicitly (`ariadne doc dev-merge`); the runtime
# uses the same name for every workflow so one phase label means one thing.
DECISION_PHASE = "CLASSIFY"

# First phase each workflow may enter once the gate returns CONTINUE.
_NEXT_PHASE = {
    DEV_NEW: "PREFLIGHT",
    DEV_NEXT: "PREFLIGHT",
    DEV_CLOSE: "PREFLIGHT",
    DEV_MERGE: "PREFLIGHT",
}
_NEXT_PHASE_DRY_RUN = {
    # `/dev-new --dry-run` decides at CLASSIFY inside its bounded pipeline.
    DEV_NEW: "PREDICT_SCOPE",
}

# Base lifecycle states from which `/dev-new` may prepare a new Feature. Its
# PREFLIGHT requires the current Feature to be CLOSED, or no Feature to exist.
DEV_NEW_ALLOWED_BASE_STATES = frozenset({lc.CLOSED, lc.NEW})

# States in which `/dev-next` may execute a batch.
DEV_NEXT_ALLOWED_STATES = frozenset({lc.READY_FOR_IMPLEMENTATION, lc.IN_PROGRESS})

# States in which `/dev-close` may run final acceptance.
DEV_CLOSE_ALLOWED_STATES = frozenset({lc.IN_PROGRESS, lc.READY_TO_CLOSE})


def _envelope(
    state: ResolvedState,
    *,
    decision: str,
    status: str,
    reason_code: str | None,
    extra_evidence: tuple[str, ...] = (),
) -> Decision:
    """Build the envelope for a decision.

    `next_legal_action` is derived from the decision, never passed in: a terminal
    decision has no legal successor, so `STOP` is structural here rather than a
    value a rule could get wrong.
    """
    if decision == CONTINUE:
        table = _NEXT_PHASE_DRY_RUN if state.dry_run else {}
        next_legal_action = table.get(state.workflow_intent) or _NEXT_PHASE[state.workflow_intent]
    else:
        next_legal_action = STOP

    human_action_required = decision == TERMINAL_BLOCKED
    return Decision(
        protocol_version=PROTOCOL_VERSION,
        workflow=state.workflow_intent,
        phase=DECISION_PHASE,
        classification=state.entity,
        decision=decision,
        status=status,
        reason_code=reason_code,
        evidence=state.facts() + extra_evidence,
        next_legal_action=next_legal_action,
        human_action_required=human_action_required,
    )


def _blocked(state: ResolvedState, reason_code: str, *detail: str) -> Decision:
    return _envelope(
        state,
        decision=TERMINAL_BLOCKED,
        status=STATUS_BLOCKED,
        reason_code=reason_code,
        extra_evidence=detail,
    )


def _not_applicable(state: ResolvedState, reason_code: str, *detail: str) -> Decision:
    return _envelope(
        state,
        decision=TERMINAL_NOT_APPLICABLE,
        status=STATUS_NOT_APPLICABLE,
        reason_code=reason_code,
        extra_evidence=detail,
    )


def _continue(state: ResolvedState, *detail: str) -> Decision:
    return _envelope(
        state,
        decision=CONTINUE,
        status=STATUS_READY,
        reason_code=None,
        extra_evidence=detail,
    )


def _decide_dev_new(state: ResolvedState) -> Decision:
    """`/dev-new`: prepare exactly one Feature.

    `ariadne doc dev-new` fixes this table and states explicitly
    that `/dev-merge`'s `NON_PRODUCT → NOT_APPLICABLE` mapping must not be reused
    here: for this entrypoint both `NON_PRODUCT` and `UNKNOWN` are BLOCKED.
    """
    if state.entity == NON_PRODUCT:
        return _blocked(
            state,
            REASON_ENTITY_NOT_PRODUCT,
            "a workflow/infrastructure branch cannot start a Product Feature",
        )
    if state.entity == UNKNOWN:
        return _blocked(state, REASON_ENTITY_UNKNOWN, "entity evidence is insufficient or mixed")
    if state.lifecycle_state == lc.UNKNOWN:
        return _blocked(state, REASON_LIFECYCLE_UNKNOWN, state.lifecycle.reason)
    if state.lifecycle_state not in DEV_NEW_ALLOWED_BASE_STATES:
        return _blocked(
            state,
            REASON_BASE_STATE_NOT_ALLOWED,
            f"a new Feature requires a CLOSED current Feature, not {state.lifecycle_state}",
        )
    if not state.dry_run and not state.safety.safe:
        return _blocked(state, REASON_WORKING_TREE_UNSAFE, "tracked working tree has changes")
    return _continue(state)


def _decide_dev_next(state: ResolvedState) -> Decision:
    """`/dev-next`: execute exactly one dependency-coherent batch.

    Applicability follows `contracts/lifecycle.md`: implementation happens
    at `READY_FOR_IMPLEMENTATION` or `IN_PROGRESS`. A complete graph has no batch
    to select, which is a successful guard rather than a failure
    (`contracts/lifecycle-entity.md`), and a graph with no ready frontier
    is blocked (`contracts/task-dag.md`).
    """
    if state.entity == NON_PRODUCT:
        return _not_applicable(
            state, REASON_ENTITY_NOT_PRODUCT, "no Product Feature batch exists on this branch"
        )
    if state.entity == UNKNOWN:
        return _blocked(state, REASON_ENTITY_UNKNOWN, "entity evidence is insufficient or mixed")

    dag = state.evidence.dag
    if not dag.valid:
        return _blocked(state, REASON_DAG_INVALID, *dag.errors[:3])
    if state.lifecycle_state == lc.CLOSED:
        return _not_applicable(state, REASON_FEATURE_CLOSED, "the Feature is already closed")
    if dag.completed:
        return _not_applicable(
            state, REASON_FEATURE_CLOSED, "every task is complete; no batch remains"
        )
    if state.lifecycle_state == lc.UNKNOWN:
        return _blocked(state, REASON_LIFECYCLE_UNKNOWN, state.lifecycle.reason)
    if state.lifecycle_state not in DEV_NEXT_ALLOWED_STATES:
        return _blocked(
            state,
            REASON_BASE_STATE_NOT_ALLOWED,
            f"implementation is not permitted from {state.lifecycle_state}",
        )
    if not dag.ready:
        return _blocked(state, REASON_NO_READY_FRONTIER, "every unfinished task is blocked")
    if state.review == REVIEW_OUTSTANDING:
        return _blocked(
            state, REASON_REVIEW_UNRESOLVED, "resolve recorded review findings before a new batch"
        )
    if not state.dry_run and not state.safety.safe:
        return _blocked(state, REASON_WORKING_TREE_UNSAFE, "tracked working tree has changes")
    return _continue(state, f"selected_frontier={','.join(dag.ready)}")


def _decide_dev_close(state: ResolvedState) -> Decision:
    """`/dev-close`: final acceptance, stopping at `READY_TO_CLOSE`.

    `ariadne doc dev-close` requires every task complete before
    final acceptance, so an incomplete graph is blocked. `/dev-close` never
    merges; that is enforced structurally by the router, which has no merge
    dispatcher for this intent.
    """
    if state.entity == NON_PRODUCT:
        return _not_applicable(
            state, REASON_ENTITY_NOT_PRODUCT, "no Product Feature to close on this branch"
        )
    if state.entity == UNKNOWN:
        return _blocked(state, REASON_ENTITY_UNKNOWN, "entity evidence is insufficient or mixed")

    dag = state.evidence.dag
    if not dag.valid:
        return _blocked(state, REASON_DAG_INVALID, *dag.errors[:3])
    if state.lifecycle_state == lc.CLOSED:
        return _not_applicable(state, REASON_FEATURE_CLOSED, "the Feature is already closed")
    if not dag.completed:
        return _blocked(
            state,
            REASON_TASKS_INCOMPLETE,
            f"incomplete tasks: {','.join(dag.incomplete[:5]) or '-'}",
        )
    if state.lifecycle_state == lc.UNKNOWN:
        return _blocked(state, REASON_LIFECYCLE_UNKNOWN, state.lifecycle.reason)
    if state.lifecycle_state not in DEV_CLOSE_ALLOWED_STATES:
        return _blocked(
            state,
            REASON_BASE_STATE_NOT_ALLOWED,
            f"final acceptance is not permitted from {state.lifecycle_state}",
        )
    if state.review == REVIEW_OUTSTANDING:
        return _blocked(state, REASON_REVIEW_UNRESOLVED, "recorded review findings are unresolved")
    return _continue(state)


def _decide_dev_merge(state: ResolvedState) -> Decision:
    """`/dev-merge`: the strictest path.

    The classification table is fixed by `contracts/terminal-contract.md`:

    ```text
    PRODUCT_FEATURE + READY_TO_CLOSE → CONTINUE
    PRODUCT_FEATURE + IN_PROGRESS     → TERMINAL_BLOCKED
    NON_PRODUCT                      → TERMINAL_NOT_APPLICABLE
    UNKNOWN                          → TERMINAL_BLOCKED
    ```

    A merge is an outward-facing mutation, so `contracts/git-policy.md`
    requires explicit authorisation. An unknown Human Gate state therefore fails
    closed for a real merge, while `--dry-run` mutates nothing and does not need
    it.

    The task graph is checked here as well as in the lifecycle resolver. In a real
    repository `READY_TO_CLOSE` already implies a valid, complete graph, so these
    two rules never change a real outcome; they exist so the strictest path does
    not depend on one derivation being correct.
    """
    if state.entity == NON_PRODUCT:
        return _not_applicable(
            state,
            REASON_ENTITY_NOT_PRODUCT,
            "changed paths are declared workflow/infrastructure paths",
        )
    if state.entity == UNKNOWN:
        return _blocked(
            state,
            REASON_ENTITY_UNKNOWN,
            "Unable to establish that current branch is a managed Product Feature.",
        )
    dag = state.evidence.dag
    if not dag.valid:
        return _blocked(state, REASON_DAG_INVALID, *dag.errors[:3])
    if state.lifecycle_state == lc.CLOSED:
        return _not_applicable(state, REASON_FEATURE_CLOSED, "the Feature is already closed")
    if not dag.completed:
        return _blocked(
            state,
            REASON_TASKS_INCOMPLETE,
            f"incomplete tasks: {','.join(dag.incomplete[:5]) or '-'}",
        )
    if state.lifecycle_state == lc.UNKNOWN:
        return _blocked(state, REASON_LIFECYCLE_UNKNOWN, state.lifecycle.reason)
    if state.lifecycle_state != lc.READY_TO_CLOSE:
        return _blocked(
            state,
            REASON_NOT_READY_TO_CLOSE,
            f"lifecycle is {state.lifecycle_state}",
        )
    if state.review != REVIEW_RESOLVED:
        return _blocked(state, REASON_REVIEW_UNRESOLVED, "no resolved review evidence is recorded")
    if not state.dry_run:
        if not state.safety.safe:
            return _blocked(state, REASON_WORKING_TREE_UNSAFE, "tracked working tree has changes")
        if state.human_gate != HUMAN_GATE_APPROVED:
            return _blocked(
                state,
                REASON_MERGE_AUTHORIZATION,
                f"merge requires explicit authorisation; human_gate={state.human_gate}",
            )
    return _continue(state)


_ENGINE = {
    DEV_NEW: _decide_dev_new,
    DEV_NEXT: _decide_dev_next,
    DEV_CLOSE: _decide_dev_close,
    DEV_MERGE: _decide_dev_merge,
}


def decide(state: ResolvedState) -> Decision:
    """Decide what the protocol permits for `state`.

    Two conditions short-circuit every workflow, because neither leaves anything
    a rule could legitimately read: an unsupported intent, and an unavailable Git
    state. Both fail closed.
    """
    if state.workflow_intent not in _ENGINE:
        return Decision(
            protocol_version=PROTOCOL_VERSION,
            workflow=str(state.workflow_intent) or "UNDECLARED_INTENT",
            phase=DECISION_PHASE,
            classification=None,
            decision=TERMINAL_BLOCKED,
            status=STATUS_BLOCKED,
            reason_code=REASON_UNSUPPORTED_INTENT,
            evidence=(f"workflow_intent={state.workflow_intent}",),
            next_legal_action=STOP,
            human_action_required=True,
        )
    if not state.safety.git_available:
        return _blocked(state, REASON_GIT_UNAVAILABLE, "repository Git state could not be read")
    return _ENGINE[state.workflow_intent](state)
