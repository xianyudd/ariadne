#!/usr/bin/env python3
"""Decision engine checks (§D).

One executable policy, exercised as a table. The expectations below are literal
data, not a second implementation of the rules: nothing here recomputes a
decision, so the table cannot silently agree with a wrong engine.

Columns are the four workflows. Cells are `DECISION:REASON_CODE`, with `-` for no
reason code. `NA` abbreviates `TERMINAL_NOT_APPLICABLE` and `BLOCKED` abbreviates
`TERMINAL_BLOCKED`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts the package on sys.path)

import state_fixture as sf  # noqa: E402
from ariadne.runtime.classification import NON_PRODUCT, PRODUCT_FEATURE  # noqa: E402
from ariadne.runtime.classification import UNKNOWN as ENTITY_UNKNOWN  # noqa: E402
from ariadne.runtime.decision import (  # noqa: E402
    CONTINUE,
    PROTOCOL_VERSION,
    STOP,
    TERMINAL_BLOCKED,
    TERMINAL_DECISIONS,
    TERMINAL_NOT_APPLICABLE,
)
from ariadne.runtime.decision_engine import DECISION_PHASE, decide  # noqa: E402
from ariadne.runtime.lifecycle import (  # noqa: E402
    CLOSED,
    IN_PROGRESS,
    LIFECYCLE_STATES,
    NEW,
    READY_FOR_IMPLEMENTATION,
    READY_TO_CLOSE,
)
from ariadne.runtime.lifecycle import UNKNOWN as LIFECYCLE_UNKNOWN  # noqa: E402
from ariadne.runtime.state import (  # noqa: E402
    DEV_CLOSE,
    DEV_MERGE,
    DEV_NEW,
    DEV_NEXT,
    HUMAN_GATE_APPROVED,
    HUMAN_GATE_NOT_APPROVED,
    HUMAN_GATE_UNKNOWN,
    REVIEW_OUTSTANDING,
    REVIEW_RESOLVED,
    REVIEW_UNKNOWN,
)

checks = 0


def check(condition: object, label: str) -> None:
    global checks
    assert condition, label
    checks += 1


WORKFLOWS = (DEV_NEW, DEV_NEXT, DEV_CLOSE, DEV_MERGE)
ENTITIES = {"PF": PRODUCT_FEATURE, "NP": NON_PRODUCT, "UE": ENTITY_UNKNOWN}
LIFECYCLES = {
    "NEW": NEW,
    "RFI": READY_FOR_IMPLEMENTATION,
    "IP": IN_PROGRESS,
    "RTC": READY_TO_CLOSE,
    "CLOSED": CLOSED,
    "UNKNOWN": LIFECYCLE_UNKNOWN,
}
SHORT = {"CONTINUE": CONTINUE, "BLOCKED": TERMINAL_BLOCKED, "NA": TERMINAL_NOT_APPLICABLE}

# An unfinished but valid graph: work remains to be done.
UNFINISHED = """
PF NEW      CONTINUE:-                             BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED BLOCKED:TASKS_INCOMPLETE  BLOCKED:TASKS_INCOMPLETE
PF RFI      BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED CONTINUE:-                             BLOCKED:TASKS_INCOMPLETE  BLOCKED:TASKS_INCOMPLETE
PF IP       BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED CONTINUE:-                             BLOCKED:TASKS_INCOMPLETE  BLOCKED:TASKS_INCOMPLETE
PF RTC      BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED BLOCKED:TASKS_INCOMPLETE BLOCKED:TASKS_INCOMPLETE
PF CLOSED   CONTINUE:-                             NA:FEATURE_ALREADY_CLOSED              NA:FEATURE_ALREADY_CLOSED NA:FEATURE_ALREADY_CLOSED
PF UNKNOWN  BLOCKED:LIFECYCLE_UNKNOWN              BLOCKED:LIFECYCLE_UNKNOWN              BLOCKED:TASKS_INCOMPLETE  BLOCKED:TASKS_INCOMPLETE
NP NEW      BLOCKED:ENTITY_NOT_PRODUCT_FEATURE     NA:ENTITY_NOT_PRODUCT_FEATURE          NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE
NP RFI      BLOCKED:ENTITY_NOT_PRODUCT_FEATURE     NA:ENTITY_NOT_PRODUCT_FEATURE          NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE
NP IP       BLOCKED:ENTITY_NOT_PRODUCT_FEATURE     NA:ENTITY_NOT_PRODUCT_FEATURE          NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE
NP RTC      BLOCKED:ENTITY_NOT_PRODUCT_FEATURE     NA:ENTITY_NOT_PRODUCT_FEATURE          NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE
NP CLOSED   BLOCKED:ENTITY_NOT_PRODUCT_FEATURE     NA:ENTITY_NOT_PRODUCT_FEATURE          NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE
NP UNKNOWN  BLOCKED:ENTITY_NOT_PRODUCT_FEATURE     NA:ENTITY_NOT_PRODUCT_FEATURE          NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE
UE NEW      BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN    BLOCKED:ENTITY_UNKNOWN
UE RFI      BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN    BLOCKED:ENTITY_UNKNOWN
UE IP       BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN    BLOCKED:ENTITY_UNKNOWN
UE RTC      BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN    BLOCKED:ENTITY_UNKNOWN
UE CLOSED   BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN    BLOCKED:ENTITY_UNKNOWN
UE UNKNOWN  BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN    BLOCKED:ENTITY_UNKNOWN
"""

# Every task complete: nothing left to implement.
COMPLETE = """
PF NEW      CONTINUE:-                             NA:FEATURE_ALREADY_CLOSED  BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED BLOCKED:LIFECYCLE_NOT_READY_TO_CLOSE
PF RFI      BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED NA:FEATURE_ALREADY_CLOSED BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED BLOCKED:LIFECYCLE_NOT_READY_TO_CLOSE
PF IP       BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED NA:FEATURE_ALREADY_CLOSED CONTINUE:-               BLOCKED:LIFECYCLE_NOT_READY_TO_CLOSE
PF RTC      BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED NA:FEATURE_ALREADY_CLOSED CONTINUE:-               CONTINUE:-
PF CLOSED   CONTINUE:-                             NA:FEATURE_ALREADY_CLOSED  NA:FEATURE_ALREADY_CLOSED NA:FEATURE_ALREADY_CLOSED
PF UNKNOWN  BLOCKED:LIFECYCLE_UNKNOWN              NA:FEATURE_ALREADY_CLOSED  BLOCKED:LIFECYCLE_UNKNOWN BLOCKED:LIFECYCLE_UNKNOWN
NP NEW      BLOCKED:ENTITY_NOT_PRODUCT_FEATURE     NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE
NP RTC      BLOCKED:ENTITY_NOT_PRODUCT_FEATURE     NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE
NP CLOSED   BLOCKED:ENTITY_NOT_PRODUCT_FEATURE     NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE
UE NEW      BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN     BLOCKED:ENTITY_UNKNOWN    BLOCKED:ENTITY_UNKNOWN
UE RTC      BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN     BLOCKED:ENTITY_UNKNOWN    BLOCKED:ENTITY_UNKNOWN
UE CLOSED   BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN     BLOCKED:ENTITY_UNKNOWN    BLOCKED:ENTITY_UNKNOWN
"""

# A graph that does not validate: no workflow may proceed on its authority.
INVALID = """
PF RFI      BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED BLOCKED:DAG_INVALID      BLOCKED:DAG_INVALID       BLOCKED:DAG_INVALID
PF RTC      BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED BLOCKED:DAG_INVALID      BLOCKED:DAG_INVALID       BLOCKED:DAG_INVALID
PF CLOSED   CONTINUE:-                             BLOCKED:DAG_INVALID        BLOCKED:DAG_INVALID       BLOCKED:DAG_INVALID
PF UNKNOWN  BLOCKED:LIFECYCLE_UNKNOWN              BLOCKED:DAG_INVALID        BLOCKED:DAG_INVALID       BLOCKED:DAG_INVALID
NP RFI      BLOCKED:ENTITY_NOT_PRODUCT_FEATURE     NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE NA:ENTITY_NOT_PRODUCT_FEATURE
UE RFI      BLOCKED:ENTITY_UNKNOWN                 BLOCKED:ENTITY_UNKNOWN     BLOCKED:ENTITY_UNKNOWN    BLOCKED:ENTITY_UNKNOWN
"""

DAGS = {
    "unfinished": sf.dag_state(),
    "complete": sf.dag_state(completed=True),
    "invalid": sf.dag_state(valid=False, errors=("cycle: T001 → T002 → T001",), ready=()),
}


def run_table(table: str, dag_name: str) -> None:
    """Assert one table against the engine."""
    for line in table.strip().splitlines():
        entity_key, lifecycle_key, *cells = line.split()
        check(len(cells) == 4, f"D0 {dag_name} {entity_key} {lifecycle_key} has four columns")
        for workflow, cell in zip(WORKFLOWS, cells):
            expected_decision, expected_reason = cell.split(":")
            resolved = decide(
                sf.state(
                    workflow_intent=workflow,
                    entity=ENTITIES[entity_key],
                    lifecycle=LIFECYCLES[lifecycle_key],
                    review=REVIEW_RESOLVED,
                    human_gate=HUMAN_GATE_APPROVED,
                    dag=DAGS[dag_name],
                )
            )
            label = f"D1 {dag_name}/{entity_key}/{lifecycle_key}/{workflow}"
            check(
                resolved.decision == SHORT[expected_decision],
                f"{label} decision {resolved.decision} != {SHORT[expected_decision]}",
            )
            expected_code = None if expected_reason == "-" else expected_reason
            check(
                resolved.reason_code == expected_code,
                f"{label} reason {resolved.reason_code} != {expected_code}",
            )


run_table(UNFINISHED, "unfinished")
run_table(COMPLETE, "complete")
run_table(INVALID, "invalid")

# The tables must cover the whole space they claim to cover.
covered = {
    (line.split()[0], line.split()[1]) for line in UNFINISHED.strip().splitlines()
}
check(
    covered == {(entity, lifecycle) for entity in ENTITIES for lifecycle in LIFECYCLES},
    "D2 the unfinished table covers every entity × lifecycle pair",
)
check(len(LIFECYCLES) == len(LIFECYCLE_STATES) + 1, "D2 every lifecycle state plus UNKNOWN")


def decision_for(**kwargs: object):
    defaults: dict[str, object] = {
        "entity": PRODUCT_FEATURE,
        "lifecycle": READY_TO_CLOSE,
        "review": REVIEW_RESOLVED,
        "human_gate": HUMAN_GATE_APPROVED,
        "dag": sf.dag_state(completed=True),
    }
    defaults.update(kwargs)
    return decide(sf.state(**defaults))  # type: ignore[arg-type]


# --- D3: the Human Gate, where a merge needs one ----------------------------
check(
    decision_for(workflow_intent=DEV_MERGE, human_gate=HUMAN_GATE_APPROVED).decision == CONTINUE,
    "D3 an approved merge continues",
)
for gate in (HUMAN_GATE_NOT_APPROVED, HUMAN_GATE_UNKNOWN):
    result = decision_for(workflow_intent=DEV_MERGE, human_gate=gate)
    check(result.decision == TERMINAL_BLOCKED, f"D3 merge with {gate} is blocked")
    check(result.reason_code == "MERGE_AUTHORIZATION_REQUIRED", f"D3 merge with {gate} says why")
check(
    decision_for(workflow_intent=DEV_MERGE, human_gate=HUMAN_GATE_UNKNOWN, dry_run=True).decision
    == CONTINUE,
    "D3 a dry run mutates nothing and needs no authorisation",
)

# --- D4: review evidence ----------------------------------------------------
check(
    decision_for(workflow_intent=DEV_MERGE, review=REVIEW_UNKNOWN).reason_code
    == "REVIEW_UNRESOLVED",
    "D4 merge requires positive resolved-review evidence",
)
check(
    decision_for(workflow_intent=DEV_MERGE, review=REVIEW_OUTSTANDING).reason_code
    == "REVIEW_UNRESOLVED",
    "D4 merge refuses outstanding findings",
)
check(
    decision_for(workflow_intent=DEV_CLOSE, lifecycle=IN_PROGRESS, review=REVIEW_OUTSTANDING).reason_code
    == "REVIEW_UNRESOLVED",
    "D4 close refuses outstanding findings",
)
check(
    decision_for(workflow_intent=DEV_CLOSE, lifecycle=IN_PROGRESS, review=REVIEW_UNKNOWN).decision
    == CONTINUE,
    "D4 close is what produces review evidence, so it does not require it up front",
)
check(
    decision_for(
        workflow_intent=DEV_NEXT,
        lifecycle=IN_PROGRESS,
        review=REVIEW_OUTSTANDING,
        dag=sf.dag_state(),
    ).reason_code
    == "REVIEW_UNRESOLVED",
    "D4 next refuses a new batch while findings are open",
)

# --- D5: working-tree safety -------------------------------------------------
for workflow, lifecycle in ((DEV_NEW, CLOSED), (DEV_NEXT, IN_PROGRESS), (DEV_MERGE, READY_TO_CLOSE)):
    dag = sf.dag_state() if workflow == DEV_NEXT else sf.dag_state(completed=True)
    dirty = decision_for(
        workflow_intent=workflow, lifecycle=lifecycle, tracked_dirty=True, dag=dag
    )
    check(dirty.reason_code == "WORKING_TREE_UNSAFE", f"D5 {workflow} refuses a dirty tree")
    clean = decision_for(workflow_intent=workflow, lifecycle=lifecycle, dag=dag)
    check(clean.decision == CONTINUE, f"D5 {workflow} continues on a clean tree")
    planned = decision_for(
        workflow_intent=workflow, lifecycle=lifecycle, tracked_dirty=True, dry_run=True, dag=dag
    )
    check(planned.decision == CONTINUE, f"D5 {workflow} may still plan with a dirty tree")

# --- D6: no Git state, no decision ------------------------------------------
for workflow in WORKFLOWS:
    result = decision_for(workflow_intent=workflow, git_available=False)
    check(result.decision == TERMINAL_BLOCKED, f"D6 {workflow} blocks without Git")
    check(result.reason_code == "GIT_STATE_UNAVAILABLE", f"D6 {workflow} says why")

# --- D7: an unsupported intent fails closed ---------------------------------
for intent in ("", "DEV_DEPLOY", "dev_merge", "DEV_MERGE "):
    result = decision_for(workflow_intent=intent)
    check(result.decision == TERMINAL_BLOCKED, f"D7 intent {intent!r} is blocked")
    check(result.reason_code == "WORKFLOW_INTENT_UNSUPPORTED", f"D7 intent {intent!r} says why")
    check(result.classification is None, f"D7 intent {intent!r} classifies nothing")

# --- D8: envelope invariants hold for every cell ----------------------------
for workflow in WORKFLOWS:
    for entity in ENTITIES.values():
        for lifecycle in LIFECYCLES.values():
            for dag_name in DAGS:
                result = decide(
                    sf.state(
                        workflow_intent=workflow,
                        entity=entity,
                        lifecycle=lifecycle,
                        review=REVIEW_RESOLVED,
                        human_gate=HUMAN_GATE_APPROVED,
                        dag=DAGS[dag_name],
                    )
                )
                assert result.protocol_version == PROTOCOL_VERSION
                assert result.phase == DECISION_PHASE
                assert result.workflow == workflow
                if result.decision in TERMINAL_DECISIONS:
                    assert result.next_legal_action == STOP, "terminal must stop"
                    assert result.is_terminal
                else:
                    assert result.next_legal_action != STOP, "continue must not stop"
                    assert not result.is_terminal
                assert result.human_action_required == (result.decision == TERMINAL_BLOCKED)
                assert (result.reason_code is None) == (result.decision == CONTINUE)
                assert result.evidence, "every decision carries evidence"
checks += 1

# --- D9: the engine is a pure function --------------------------------------
state = sf.state(
    workflow_intent=DEV_MERGE,
    entity=PRODUCT_FEATURE,
    lifecycle=READY_TO_CLOSE,
    review=REVIEW_RESOLVED,
    human_gate=HUMAN_GATE_APPROVED,
    dag=sf.dag_state(completed=True),
)
first, second = decide(state), decide(state)
check(first.as_dict() == second.as_dict(), "D9 the same state yields the same envelope")
check(first is not second, "D9 each call builds its own envelope")

# --- D10: the migrated dev-merge classification table -----------------------
# These four rows are `contracts/terminal-contract.md`. They once had a second
# implementation to be asserted against; there is now one engine, which is the only
# place the mapping exists, so this table is checked directly against it.
TERMINAL_CONTRACT = (
    (PRODUCT_FEATURE, READY_TO_CLOSE, CONTINUE),
    (PRODUCT_FEATURE, IN_PROGRESS, TERMINAL_BLOCKED),
    (NON_PRODUCT, READY_TO_CLOSE, TERMINAL_NOT_APPLICABLE),
    (ENTITY_UNKNOWN, READY_TO_CLOSE, TERMINAL_BLOCKED),
    (PRODUCT_FEATURE, LIFECYCLE_UNKNOWN, TERMINAL_BLOCKED),
)
for entity, lifecycle, expected in TERMINAL_CONTRACT:
    result = decision_for(workflow_intent=DEV_MERGE, entity=entity, lifecycle=lifecycle)
    check(
        result.decision == expected,
        f"D10 {entity} + {lifecycle} → {result.decision}, expected {expected}",
    )

print(f"decision engine checks passed ({checks} assertions)")
