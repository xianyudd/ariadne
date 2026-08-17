#!/usr/bin/env python3
"""Runtime closure: the end-to-end chain and the runtime invariants (§F, §24).

Every case below walks the whole path on a real repository:

```text
repository fixture → evidence → state → decision → terminal gate → dispatcher
```

The dispatcher is a spy: it records what reached it and runs nothing. That is what
makes non-dispatch provable rather than asserted — a terminal decision is
demonstrated to leave the spy untouched.

Invariants proven here:

    INV-R1   There is exactly one executable decision policy.
    INV-R2   Terminal decisions make workflow dispatch unreachable.
    INV-R3   CONTINUE dispatches exactly once.
    INV-R4   Unknown or malformed state fails closed.
    INV-R5   Lifecycle state is repository-derived on normal runtime paths.
    INV-R6   No workflow bypasses TerminalGate.
    INV-R7   Router does not contain policy.
    INV-R9   Task DAG has one canonical implementation.
    INV-R10  The same repository state yields the same decision across hosts.

INV-R8 (host adapters hold no decision semantics) is a property of files outside
the runtime and is audited by `audit_wiring.py`.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SDLC = ROOT / ".agent-sdlc"
sys.path.insert(0, str(SDLC))
sys.path.insert(0, str(SDLC / "validation"))

from repo_fixture import (  # noqa: E402
    CLOSURE_RECORDED,
    GATES_RECORDED,
    REVIEW_CLEAN,
    REVIEW_OUTSTANDING,
    TASKS_COMPLETE,
    TASKS_CYCLE,
    TASKS_PARTIAL,
    TASKS_READY,
    make_repo,
)
from source_view import code_only  # noqa: E402
from runtime import dag as dag_module  # noqa: E402
from runtime import decision_engine, evidence as evidence_module, router as router_module  # noqa: E402
from runtime.api import enforce, evaluate_workflow, execute_workflow  # noqa: E402
from runtime.classification import NON_PRODUCT, PRODUCT_FEATURE  # noqa: E402
from runtime.classification import UNKNOWN as ENTITY_UNKNOWN  # noqa: E402
from runtime.decision import (  # noqa: E402
    CONTINUE,
    PROTOCOL_DECISION_INVALID,
    STOP,
    TERMINAL_BLOCKED,
    TERMINAL_NOT_APPLICABLE,
    Decision,
)
from runtime.decision_engine import decide  # noqa: E402
from runtime.evidence import collect_repository_evidence  # noqa: E402
from runtime.lifecycle import (  # noqa: E402
    CLOSED,
    IN_PROGRESS,
    READY_FOR_IMPLEMENTATION,
    READY_TO_CLOSE,
)
from runtime.lifecycle import UNKNOWN as LIFECYCLE_UNKNOWN  # noqa: E402
from runtime.router import RouterRefused, WorkflowRouter  # noqa: E402
from runtime.state import (  # noqa: E402
    DEV_CLOSE,
    DEV_MERGE,
    DEV_NEW,
    DEV_NEXT,
    HUMAN_GATE_APPROVED,
    HUMAN_GATE_NOT_APPROVED,
    HUMAN_GATE_UNKNOWN,
    WORKFLOW_INTENTS,
    resolve_state,
)
from runtime.terminal_gate import TerminalGate  # noqa: E402

checks = 0


def check(condition: object, label: str) -> None:
    global checks
    assert condition, label
    checks += 1


class SpyDispatchers:
    """One spy per workflow intent, so cross-workflow dispatch is observable."""

    def __init__(self) -> None:
        self.calls: dict[str, list[Decision]] = {intent: [] for intent in WORKFLOW_INTENTS}

    def dispatcher(self, intent: str):
        def dispatch(decision: Decision) -> str:
            self.calls[intent].append(decision)
            return f"{intent}_EXECUTED"

        return dispatch

    def router(self) -> WorkflowRouter:
        return WorkflowRouter({intent: self.dispatcher(intent) for intent in WORKFLOW_INTENTS})

    @property
    def total(self) -> int:
        return sum(len(calls) for calls in self.calls.values())

    def count(self, intent: str) -> int:
        return len(self.calls[intent])


# Fixture recipes, named by the real repository shape they build.
FIXTURES: dict[str, dict[str, object]] = {
    "ready": dict(tasks=TASKS_READY),
    "partial": dict(tasks=TASKS_PARTIAL),
    "partial-review-open": dict(tasks=TASKS_PARTIAL, handoff_lines=(REVIEW_OUTSTANDING,)),
    "complete-reviewed": dict(tasks=TASKS_COMPLETE, handoff_lines=(REVIEW_CLEAN, GATES_RECORDED)),
    "accepted": dict(
        tasks=TASKS_COMPLETE, handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED)
    ),
    "merged": dict(
        tasks=TASKS_COMPLETE,
        handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
        merge_into_main=True,
    ),
    "workflow-branch": dict(
        branch="agent-sdlc-v2",
        spec_branch="002-example",
        state_branch="002-example",
        feature_on_main=True,
        workflow_change=True,
        tasks=TASKS_COMPLETE,
        handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
    ),
    "mixed-changes": dict(
        branch="agent-sdlc-v2",
        spec_branch="002-example",
        state_branch="002-example",
        feature_on_main=True,
        workflow_change=True,
        product_change=True,
        tasks=TASKS_COMPLETE,
        handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
    ),
    "no-git": dict(git=False),
    "broken-graph": dict(tasks=TASKS_CYCLE),
}

# (fixture, intent, human gate, dry run) → (entity, lifecycle, decision, reason, dispatches)
CASES: tuple[tuple[str, str, str, bool, tuple[str, str, str, str | None, int]], ...] = (
    # /dev-new prepares the next Feature only from a closed one.
    ("merged", DEV_NEW, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, CLOSED, CONTINUE, None, 1)),
    ("partial", DEV_NEW, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, IN_PROGRESS, TERMINAL_BLOCKED, "LIFECYCLE_BASE_STATE_NOT_ALLOWED", 0)),
    ("accepted", DEV_NEW, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, READY_TO_CLOSE, TERMINAL_BLOCKED, "LIFECYCLE_BASE_STATE_NOT_ALLOWED", 0)),
    # /dev-next executes one batch while work remains.
    ("ready", DEV_NEXT, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, READY_FOR_IMPLEMENTATION, CONTINUE, None, 1)),
    ("partial", DEV_NEXT, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, IN_PROGRESS, CONTINUE, None, 1)),
    ("partial-review-open", DEV_NEXT, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, IN_PROGRESS, TERMINAL_BLOCKED, "REVIEW_UNRESOLVED", 0)),
    ("accepted", DEV_NEXT, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, READY_TO_CLOSE, TERMINAL_NOT_APPLICABLE, "FEATURE_ALREADY_CLOSED", 0)),
    ("broken-graph", DEV_NEXT, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, LIFECYCLE_UNKNOWN, TERMINAL_BLOCKED, "DAG_INVALID", 0)),
    # /dev-close runs final acceptance and stops at READY_TO_CLOSE.
    ("complete-reviewed", DEV_CLOSE, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, IN_PROGRESS, CONTINUE, None, 1)),
    ("partial", DEV_CLOSE, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, IN_PROGRESS, TERMINAL_BLOCKED, "TASKS_INCOMPLETE", 0)),
    ("merged", DEV_CLOSE, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, CLOSED, TERMINAL_NOT_APPLICABLE, "FEATURE_ALREADY_CLOSED", 0)),
    # /dev-merge, the strictest path: authorised, unauthorised, and planned.
    ("accepted", DEV_MERGE, HUMAN_GATE_APPROVED, False,
     (PRODUCT_FEATURE, READY_TO_CLOSE, CONTINUE, None, 1)),
    ("accepted", DEV_MERGE, HUMAN_GATE_UNKNOWN, False,
     (PRODUCT_FEATURE, READY_TO_CLOSE, TERMINAL_BLOCKED, "MERGE_AUTHORIZATION_REQUIRED", 0)),
    ("accepted", DEV_MERGE, HUMAN_GATE_NOT_APPROVED, False,
     (PRODUCT_FEATURE, READY_TO_CLOSE, TERMINAL_BLOCKED, "MERGE_AUTHORIZATION_REQUIRED", 0)),
    ("accepted", DEV_MERGE, HUMAN_GATE_UNKNOWN, True,
     (PRODUCT_FEATURE, READY_TO_CLOSE, CONTINUE, None, 1)),
    ("complete-reviewed", DEV_MERGE, HUMAN_GATE_APPROVED, False,
     (PRODUCT_FEATURE, IN_PROGRESS, TERMINAL_BLOCKED, "LIFECYCLE_NOT_READY_TO_CLOSE", 0)),
    ("workflow-branch", DEV_MERGE, HUMAN_GATE_APPROVED, False,
     (NON_PRODUCT, READY_TO_CLOSE, TERMINAL_NOT_APPLICABLE, "ENTITY_NOT_PRODUCT_FEATURE", 0)),
    ("mixed-changes", DEV_MERGE, HUMAN_GATE_APPROVED, False,
     (ENTITY_UNKNOWN, READY_TO_CLOSE, TERMINAL_BLOCKED, "ENTITY_UNKNOWN", 0)),
)

# --- F: the whole chain, one real repository at a time -----------------------
dispatched_on_terminal = 0
continue_dispatches = 0

for fixture_name, intent, gate_state, dry_run, expected in CASES:
    entity, lifecycle, decision_value, reason, dispatches = expected
    label = f"F {fixture_name}/{intent}/{gate_state}{'/dry-run' if dry_run else ''}"

    with make_repo(**FIXTURES[fixture_name]) as fixture:  # type: ignore[arg-type]
        # 1. evidence
        evidence = collect_repository_evidence(fixture.root)
        check(evidence.facts(), f"{label} evidence collected")

        # 2. state
        state = resolve_state(evidence, intent, human_gate=gate_state, dry_run=dry_run)
        check(state.entity == entity, f"{label} entity {state.entity} != {entity}")
        check(state.lifecycle_state == lifecycle, f"{label} lifecycle {state.lifecycle_state}")
        check(state.lifecycle_derived, f"{label} lifecycle is derived")  # INV-R5
        check(state.evidence is evidence, f"{label} state reuses the one evidence collection")

        # 3. decision
        decision = decide(state)
        check(decision.decision == decision_value, f"{label} decision {decision.decision}")
        check(decision.reason_code == reason, f"{label} reason {decision.reason_code}")

        # 4. gate → 5. dispatcher
        spies = SpyDispatchers()
        reports: list[str] = []
        result = enforce(decision, spies.router(), emit=reports.append)

        check(spies.count(intent) == dispatches, f"{label} dispatched {spies.count(intent)}x")
        check(spies.total == dispatches, f"{label} no other workflow was dispatched")
        if decision_value == CONTINUE:  # INV-R3
            continue_dispatches += spies.total
            check(not result.terminal, f"{label} continues")
            # The gate revalidates before dispatching, so what the dispatcher
            # receives is the gate's own settled envelope, equal to the decision.
            check(spies.calls[intent][0] is result.decision, f"{label} the settled envelope routed")
            check(spies.calls[intent][0] == decision, f"{label} routed envelope is the decision")
            check(reports == [], f"{label} a continued workflow emits no final report")
        else:  # INV-R2
            dispatched_on_terminal += spies.total
            check(result.terminal, f"{label} is terminal")
            check(decision.next_legal_action == STOP, f"{label} has no successor phase")
            check(len(reports) == 1, f"{label} emits exactly one final report")

        # The one-call entrypoint must be the same path, not a shortcut past it.
        api_spies = SpyDispatchers()
        api_result = execute_workflow(
            fixture.root,
            intent,
            api_spies.router(),
            human_gate=gate_state,
            dry_run=dry_run,
            emit=lambda _report: None,
        )
        check(
            api_result.decision.as_dict() == decision.as_dict(),
            f"{label} execute_workflow reaches the same decision",
        )
        check(api_spies.total == dispatches, f"{label} execute_workflow dispatches identically")

check(dispatched_on_terminal == 0, "INV-R2 no terminal decision reached a dispatcher")
check(continue_dispatches == sum(1 for *_, expected in CASES if expected[2] == CONTINUE),
      "INV-R3 every CONTINUE dispatched exactly once")

covered_intents = {intent for _, intent, *_ in CASES}
check(covered_intents == set(WORKFLOW_INTENTS), "F every workflow has a key path")
covered_continue = {intent for _, intent, _, _, expected in CASES if expected[2] == CONTINUE}
check(covered_continue == set(WORKFLOW_INTENTS), "F every workflow has a proven CONTINUE path")

# --- INV-R4: unknown or malformed state fails closed -------------------------
with make_repo(**FIXTURES["no-git"]) as fixture:  # type: ignore[arg-type]
    for intent in sorted(WORKFLOW_INTENTS):
        spies = SpyDispatchers()
        result = execute_workflow(
            fixture.root, intent, spies.router(), emit=lambda _report: None
        )
        check(result.decision.decision == TERMINAL_BLOCKED, f"INV-R4 {intent} blocks without Git")
        check(
            result.decision.reason_code == "GIT_STATE_UNAVAILABLE",
            f"INV-R4 {intent} names the missing evidence",
        )
        check(spies.total == 0, f"INV-R4 {intent} dispatched nothing")

with make_repo(**FIXTURES["accepted"]) as fixture:  # type: ignore[arg-type]
    for intent in ("", "DEV_DEPLOY", "dev-merge"):
        spies = SpyDispatchers()
        result = execute_workflow(
            fixture.root, intent, spies.router(), emit=lambda _report: None
        )
        check(
            result.decision.reason_code == "WORKFLOW_INTENT_UNSUPPORTED",
            f"INV-R4 intent {intent!r} is unsupported",
        )
        check(spies.total == 0, f"INV-R4 intent {intent!r} dispatched nothing")

    # A malformed envelope reaching the gate cannot be repaired into a dispatch.
    spies = SpyDispatchers()
    result = enforce({"decision": CONTINUE}, spies.router(), emit=lambda _report: None)
    check(result.decision.reason_code == PROTOCOL_DECISION_INVALID, "INV-R4 malformed fails closed")
    check(spies.total == 0, "INV-R4 malformed dispatched nothing")

# --- INV-R1: exactly one executable decision policy -------------------------
# Every reason code the engine can emit is declared in exactly one runtime module.
# A second policy would have to either reuse this vocabulary (caught here) or
# invent its own (caught by `audit_wiring.py`, which greps for decision literals).
runtime_sources = {
    path.name: path.read_text(encoding="utf-8") for path in (SDLC / "runtime").glob("*.py")
}
for code in sorted(decision_engine.REASON_CODES):
    holders = sorted(name for name, text in runtime_sources.items() if f'= "{code}"' in text)
    check(holders == ["decision_engine.py"], f"INV-R1 {code} is declared once: {holders}")

# `DAG_INVALID` is also a graph status, which is the one word the two layers share.
# It is a status there and a reason code here; the graph layer must not be able to
# turn it into a decision, which is what the next assertion pins down.
check("DAG_INVALID" in runtime_sources["dag.py"], "INV-R1 the graph status word is shared")

# Only the engine may put a workflow reason code into an envelope. `decision.py`
# constructs one envelope of its own — the framework's fail-closed rejection —
# and that carries a reserved `PROTOCOL_` code, not a workflow code.
for name, text in runtime_sources.items():
    if name in ("decision_engine.py", "decision.py"):
        continue
    check(f"reason_code=" not in text, f"INV-R1 {name} does not populate a reason code")
check(
    'reason_code=PROTOCOL_DECISION_INVALID' in runtime_sources["decision.py"],
    "INV-R1 the framework's own envelope uses a reserved code",
)
for code in sorted(decision_engine.REASON_CODES):
    check(
        f'"{code}"' not in runtime_sources["decision.py"],
        f"INV-R1 the envelope module holds no workflow reason code ({code})",
    )

# The engine is the only module that maps a classification to a decision.
for name, text in runtime_sources.items():
    if name in ("decision_engine.py", "decision.py", "__init__.py"):
        continue
    mentions_entity = "PRODUCT_FEATURE" in text
    mentions_decision = "TERMINAL_BLOCKED" in text or "TERMINAL_NOT_APPLICABLE" in text
    check(
        not (mentions_entity and mentions_decision),
        f"INV-R1 {name} pairs a classification with a decision",
    )
check(
    len(decision_engine._ENGINE) == len(WORKFLOW_INTENTS),
    "INV-R1 one decision function per workflow intent, and no more",
)

# --- INV-R6: no workflow bypasses the terminal gate -------------------------
check(
    "dispatcher" not in inspect.signature(evaluate_workflow).parameters,
    "INV-R6 evaluating a workflow cannot dispatch it",
)
check(
    "dispatcher" not in inspect.signature(decide).parameters,
    "INV-R6 the decision engine cannot dispatch",
)
api_source = (SDLC / "runtime" / "api.py").read_text(encoding="utf-8")
check("TerminalGate(dispatcher" in api_source, "INV-R6 enforcement builds a gate over the dispatcher")
check(".route(" not in api_source, "INV-R6 the API never routes around the gate")
for name, text in runtime_sources.items():
    if name in ("terminal_gate.py", "router.py"):
        continue
    check(
        "dispatcher(" not in text.replace("TerminalGate(dispatcher", ""),
        f"INV-R6 {name} does not call a dispatcher itself",
    )

# The router refuses to be used as a bypass, even when called directly.
spies = SpyDispatchers()
router = spies.router()
with make_repo(**FIXTURES["complete-reviewed"]) as fixture:  # type: ignore[arg-type]
    blocked_decision = evaluate_workflow(fixture.root, DEV_MERGE)
check(blocked_decision.decision == TERMINAL_BLOCKED, "INV-R6 the case under test is terminal")
try:
    router.route(blocked_decision)
except RouterRefused:
    checks += 1
else:  # pragma: no cover - the router must refuse a terminal envelope
    raise AssertionError("INV-R6 the router accepted a terminal envelope")
check(spies.total == 0, "INV-R6 a refused route dispatches nothing")

# --- INV-R7: the router holds no policy -------------------------------------
# Checked against code with comments and string literals removed: the router's
# docstring names the things it must not do, and prose disclaiming a policy is the
# opposite of holding one.
router_source = code_only(SDLC / "runtime" / "router.py")
for token in (
    "PRODUCT_FEATURE",
    "NON_PRODUCT",
    "READY_TO_CLOSE",
    "IN_PROGRESS",
    "TERMINAL_BLOCKED",
    "TERMINAL_NOT_APPLICABLE",
    "tracked_dirty",
    "human_gate",
    "REVIEW_",
    "lifecycle",
    "tasks",
):
    check(token not in router_source, f"INV-R7 router code mentions no {token}")
check(
    not any(name in dir(router_module) for name in ("decide", "resolve_lifecycle", "classify_evidence")),
    "INV-R7 the router imports no resolver",
)
# Its only decision-shaped comparison is the gate's own guarantee, re-asserted.
check(router_source.count("CONTINUE") == 2, "INV-R7 the router reads exactly one decision value")

# A workflow's envelope can only reach its own dispatcher: /dev-close has no
# merge dispatcher, so "never merges" is structural.
close_only = WorkflowRouter({DEV_CLOSE: spies.dispatcher(DEV_CLOSE)})
check(close_only.intents == (DEV_CLOSE,), "INV-R7 a router registers exactly what it was given")
with make_repo(**FIXTURES["accepted"]) as fixture:  # type: ignore[arg-type]
    merge_decision = evaluate_workflow(
        fixture.root, DEV_MERGE, human_gate=HUMAN_GATE_APPROVED
    )
check(merge_decision.decision == CONTINUE, "INV-R7 the case under test would continue")
try:
    close_only.route(merge_decision)
except RouterRefused:
    checks += 1
else:  # pragma: no cover
    raise AssertionError("INV-R7 a merge envelope reached a close-only router")
try:
    WorkflowRouter({"DEV_DEPLOY": spies.dispatcher(DEV_CLOSE)})
except ValueError:
    checks += 1
else:  # pragma: no cover
    raise AssertionError("INV-R7 an undeclared intent was registered")

# --- INV-R9: one canonical task DAG implementation --------------------------
check(evidence_module.resolve_dag is dag_module.resolve_dag, "INV-R9 evidence uses the resolver")
for name, text in runtime_sources.items():
    if name == "dag.py":
        continue
    for token in ("Depends:", "- [x]", "- [ ]"):
        check(token not in text, f"INV-R9 {name} does not re-parse tasks.md ({token})")
with make_repo(**FIXTURES["partial"]) as fixture:  # type: ignore[arg-type]
    evidence = collect_repository_evidence(fixture.root)
    direct = dag_module.resolve_dag(evidence.feature.tasks_path)
    check(evidence.dag == direct, "INV-R9 evidence carries the canonical resolution")

# --- INV-R10: one repository state, one decision, on any host ---------------
# A host contributes only the invocation, so two hosts differ at most in the
# dispatcher they register. The envelope must be identical.
with make_repo(**FIXTURES["accepted"]) as fixture:  # type: ignore[arg-type]
    host_a = SpyDispatchers()
    host_b = SpyDispatchers()
    result_a = execute_workflow(
        fixture.root, DEV_MERGE, host_a.router(),
        human_gate=HUMAN_GATE_APPROVED, emit=lambda _r: None,
    )
    # A second host, dispatching through a bare callable rather than a router.
    recorded: list[Decision] = []
    result_b = execute_workflow(
        fixture.root, DEV_MERGE, recorded.append,
        human_gate=HUMAN_GATE_APPROVED, emit=lambda _r: None,
    )
    check(
        result_a.decision.as_dict() == result_b.decision.as_dict(),
        "INV-R10 the same repository state yields the same envelope on either host",
    )
    check(host_a.total == 1 and len(recorded) == 1, "INV-R10 each host dispatched once")
    check(host_b.total == 0, "INV-R10 an unused host dispatches nothing")

    # Re-collecting the same repository must not change the answer either.
    repeated = [evaluate_workflow(fixture.root, DEV_MERGE, human_gate=HUMAN_GATE_APPROVED)
                for _ in range(3)]
    check(
        all(item == repeated[0] for item in repeated),
        "INV-R10 repeated evaluation is deterministic",
    )

# --- The live repository ----------------------------------------------------
# Read-only, and the strongest available evidence of closure: the runtime resolves
# this repository's real state and refuses the merge path on a workflow branch.
live = evaluate_workflow(ROOT, DEV_MERGE, human_gate=HUMAN_GATE_APPROVED)
check(live.classification == NON_PRODUCT, f"live repository classifies {live.classification}")
check(live.decision == TERMINAL_NOT_APPLICABLE, f"live repository decides {live.decision}")
check(live.next_legal_action == STOP, "live repository stops")
live_spies = SpyDispatchers()
live_result = enforce(live, live_spies.router(), emit=lambda _r: None)
check(live_spies.total == 0, "live repository dispatches nothing")
check(live_result.terminal, "live repository settles terminally")

print(
    f"runtime closure checks passed ({checks} assertions)\n"
    f"end-to-end cases: {len(CASES)} over {len(covered_intents)} workflows\n"
    f"CONTINUE dispatches: {continue_dispatches}   terminal dispatches: {dispatched_on_terminal}\n"
    "INV-R1 INV-R2 INV-R3 INV-R4 INV-R5 INV-R6 INV-R7 INV-R9 INV-R10 verified"
)
