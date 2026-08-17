#!/usr/bin/env python3
"""Deterministic checks for the Agent SDLC runtime terminal gate.

Dispatch is exercised through a spy that records calls and runs nothing. No host
agent, model, or provider is involved, so every invariant below is proven by
control flow rather than by observed agent behaviour.

Invariants:

    INV-T1  Terminal Non-Dispatch          TERMINAL_* never reaches the dispatcher
    INV-T2  Single Terminal Emission       exactly one final report per terminal decision
    INV-T3  No Post-Terminal Phase         a settled gate has no successor phase
    INV-T4  Invalid Decision Fails Closed  malformed input becomes TERMINAL_BLOCKED

The envelope producer is the untrusted party: it does not hold the dispatcher, so
envelope shape is its only lever. Section F therefore treats a supplied
`Decision` instance as hostile input rather than as a trusted value.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).parents[2]
CORE = ROOT / ".agent-sdlc" / "core"
RUNTIME = ROOT / ".agent-sdlc" / "runtime"
sys.path.insert(0, str(ROOT / ".agent-sdlc"))
sys.path.insert(0, str(ROOT / ".agent-sdlc" / "validation"))

import runtime as runtime_package  # noqa: E402
from source_view import code_only  # noqa: E402
from runtime import (  # noqa: E402  (path is prepared above)
    CONTINUE,
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
    GateAlreadySettled,
    TerminalGate,
    coerce,
    protocol_invalid,
)

WORKFLOW_REASON = "EXAMPLE_WORKFLOW_REASON"


class SpyDispatcher:
    """Stands in for host dispatch; records calls, invokes no agent."""

    def __init__(self) -> None:
        self.calls: list[Decision] = []

    def __call__(self, decision: Decision) -> str:
        self.calls.append(decision)
        return "HOST_DISPATCHED"

    @property
    def count(self) -> int:
        return len(self.calls)


class SpyEmitter:
    """Records every final report the gate emits."""

    def __init__(self) -> None:
        self.reports: list[str] = []

    def __call__(self, report: str) -> None:
        self.reports.append(report)

    @property
    def count(self) -> int:
        return len(self.reports)


def envelope(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol_version": PROTOCOL_VERSION,
        "workflow": "example-workflow",
        "phase": "CLASSIFY",
        "classification": "EXAMPLE_CLASSIFICATION",
        "decision": TERMINAL_NOT_APPLICABLE,
        "status": "NOT_APPLICABLE",
        "reason_code": None,
        "evidence": ["deterministic preflight fact"],
        "next_legal_action": STOP,
        "human_action_required": False,
    }
    payload.update(overrides)
    return payload


def blocked(**overrides: object) -> dict[str, object]:
    payload = envelope(
        decision=TERMINAL_BLOCKED,
        status="BLOCKED",
        reason_code=WORKFLOW_REASON,
        human_action_required=True,
    )
    payload.update(overrides)
    return payload


def run(payload: object) -> tuple[TerminalGate, object, SpyDispatcher, SpyEmitter]:
    dispatcher, emitter = SpyDispatcher(), SpyEmitter()
    gate = TerminalGate(dispatcher, emit=emitter)
    return gate, gate.apply(payload), dispatcher, emitter


class _SubclassedDecision(Decision):
    """A producer subclass must not be able to lie about terminality."""

    @property
    def is_terminal(self) -> bool:
        return False


class _SneakyText(str):
    """Renders as one decision value while comparing as another."""

    def __eq__(self, other: object) -> bool:
        return other == CONTINUE

    def __hash__(self) -> int:
        return hash(CONTINUE)


class _AlwaysEqual(str):
    """Claims to equal anything, to try to pass as the framework's own envelope.

    Both comparison methods lie: `str.__ne__` would otherwise answer honestly and
    the probe would not exercise the normalisation it is aimed at.
    """

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return hash(str(self))


class _UnnormalisableText(str):
    """Owns `__str__` and `strip`, then lies about equality.

    `str(value).strip()` would hand this object straight back, keeping the forged
    `__hash__`/`__eq__` alive through validation and into the membership test that
    decides dispatch, while `render()` still printed the underlying value.
    """

    def __str__(self) -> str:
        return self

    def strip(self, *args: object) -> str:
        return self

    def upper(self) -> str:
        return self

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False

    def __hash__(self) -> int:
        return hash(CONTINUE)


class _StripLie(str):
    """Lies only in `strip`, to slip a reserved reason code past the prefix check."""

    def strip(self, *args: object) -> str:
        return WORKFLOW_REASON


class _SpoofedStr:
    """Passes `isinstance(value, str)` without being a `str`."""

    @property
    def __class__(self) -> type:  # type: ignore[override]
        return str


class _DoubleReadMapping(Mapping):
    """Answers a second read of `reason_code` with a forged framework code."""

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = dict(payload)
        self.reads = 0

    def __getitem__(self, key: str) -> object:
        if key == "reason_code":
            self.reads += 1
            if self.reads > 1:
                return PROTOCOL_DECISION_INVALID
        return self._payload[key]

    def __iter__(self):
        return iter(self._payload)

    def __len__(self) -> int:
        return len(self._payload)


_mutated = Decision.from_mapping(blocked())
object.__setattr__(_mutated, "decision", CONTINUE)  # frozen only by convention

_double_read = _DoubleReadMapping(blocked())

TERMINAL_CASES = {
    TERMINAL_NOT_APPLICABLE: envelope(),
    TERMINAL_BLOCKED: blocked(),
    TERMINAL_SUCCESS: envelope(decision=TERMINAL_SUCCESS, status="COMPLETE"),
}
CONTINUE_CASE = envelope(
    decision=CONTINUE,
    status="READY",
    reason_code=None,
    next_legal_action="PREFLIGHT",
)
MALFORMED_CASES = (
    None,
    "CONTINUE",
    42,
    ["CONTINUE"],
    envelope(decision="MAYBE"),
    envelope(decision="continue"),
    envelope(decision=["CONTINUE"]),  # unhashable: must not raise out of validation
    envelope(decision={"key": "value"}),
    {name: value for name, value in envelope().items() if name != "status"},
    envelope(host_specific_field="value"),
    envelope(protocol_version="2.0"),
    envelope(decision=TERMINAL_SUCCESS, status="COMPLETE", next_legal_action="PREFLIGHT"),
    envelope(decision=CONTINUE, status="READY"),
    envelope(decision=CONTINUE, status="READY", next_legal_action="STOP "),
    envelope(decision=CONTINUE, status="READY", next_legal_action="stop"),
    envelope(decision=TERMINAL_BLOCKED, status="BLOCKED", reason_code=None),
    envelope(reason_code=f"{RESERVED_REASON_PREFIX}FORGED"),  # reserved for the framework
    # every field claims to equal the framework's own fail-closed envelope, to
    # smuggle a reserved reason code onto a CONTINUE
    envelope(
        workflow=_AlwaysEqual("producer-workflow"),
        phase=_AlwaysEqual("CLASSIFY"),
        classification=_AlwaysEqual("EXAMPLE_CLASSIFICATION"),
        decision=_AlwaysEqual(CONTINUE),
        status=_AlwaysEqual("READY"),
        reason_code=_AlwaysEqual(f"{RESERVED_REASON_PREFIX}FORGED"),
        next_legal_action=_AlwaysEqual("PREFLIGHT"),
        human_action_required=True,
    ),
    # the same claim, from values that also own `__str__` and `strip`: the
    # exemption check must not normalise through the producer's methods either
    envelope(
        workflow=_UnnormalisableText("producer-workflow"),
        phase=_UnnormalisableText("CLASSIFY"),
        classification=_UnnormalisableText("EXAMPLE_CLASSIFICATION"),
        decision=_UnnormalisableText(CONTINUE),
        status=_UnnormalisableText("READY"),
        reason_code=_UnnormalisableText(f"{RESERVED_REASON_PREFIX}FORGED"),
        next_legal_action=_UnnormalisableText("PREFLIGHT"),
        human_action_required=True,
    ),
    envelope(human_action_required="true"),
    envelope(human_action_required=1),
    envelope(evidence="single fact"),
    envelope(evidence=["fact", ""]),
    envelope(workflow=""),
    envelope(phase=None),
)
# Hostile payloads that stay legal envelopes: the declared field wins over any
# property, comparison, or post-construction mutation the producer supplies.
HOSTILE_CASES = (
    (_SubclassedDecision(**blocked()), TERMINAL_BLOCKED, WORKFLOW_REASON),
    (_mutated, TERMINAL_BLOCKED, PROTOCOL_DECISION_INVALID),
    (blocked(decision=_SneakyText(TERMINAL_BLOCKED)), TERMINAL_BLOCKED, WORKFLOW_REASON),
    (_double_read, TERMINAL_BLOCKED, WORKFLOW_REASON),
    # normalisation must not be routed through the producer's own methods
    (
        blocked(decision=_UnnormalisableText(TERMINAL_BLOCKED), next_legal_action="PREFLIGHT"),
        TERMINAL_BLOCKED,
        PROTOCOL_DECISION_INVALID,
    ),
    (
        blocked(reason_code=_StripLie(f"{RESERVED_REASON_PREFIX}FORGED")),
        TERMINAL_BLOCKED,
        PROTOCOL_DECISION_INVALID,
    ),
    (blocked(decision=_SpoofedStr()), TERMINAL_BLOCKED, PROTOCOL_DECISION_INVALID),
)

# --- A/B/C: every terminal decision refuses dispatch -------------------------
for name, payload in TERMINAL_CASES.items():
    gate, result, dispatcher, emitter = run(payload)
    assert dispatcher.count == 0, (name, dispatcher.count)  # INV-T1
    assert result.dispatch_count == 0, name
    assert result.terminal is True, name
    assert result.decision.decision == name, name
    assert emitter.count == 1, (name, emitter.count)  # INV-T2
    assert len(result.reports) == 1, name
    assert emitter.reports[0] == result.final_report, name
    assert f"DECISION {name}" in result.final_report, name
    assert f"STATUS {payload['status']}" in result.final_report, name
    assert f"NEXT_LEGAL_ACTION {STOP}" in result.final_report, name
    assert gate.settled is True, name

# --- D: CONTINUE dispatches exactly once ------------------------------------
gate, result, dispatcher, emitter = run(CONTINUE_CASE)
assert dispatcher.count == 1, dispatcher.count
assert result.dispatch_count == 1
assert result.terminal is False
assert result.decision.decision == CONTINUE
assert result.decision.next_legal_action == "PREFLIGHT"
assert result.dispatch_result == "HOST_DISPATCHED"
assert dispatcher.calls[0] is result.decision
assert emitter.count == 0, "the gate emits no final report for a continued workflow"
assert result.reports == ()
assert result.final_report is None

# --- E: malformed or unknown decisions fail closed --------------------------
malformed_dispatches = 0
for payload in MALFORMED_CASES:
    gate, result, dispatcher, emitter = run(payload)
    malformed_dispatches += dispatcher.count
    assert dispatcher.count == 0, payload  # INV-T1
    assert result.dispatch_count == 0, payload
    assert result.terminal is True, payload
    assert result.decision.decision == TERMINAL_BLOCKED, payload  # INV-T4
    assert result.decision.reason_code == PROTOCOL_DECISION_INVALID, payload
    assert result.decision.status == "BLOCKED", payload
    assert result.decision.human_action_required is True, payload
    assert result.decision.classification is None, payload
    assert len(result.decision.evidence) == 1, payload
    assert emitter.count == 1, payload  # INV-T2
assert malformed_dispatches == 0

# --- F: a supplied Decision instance is never trusted -----------------------
hostile_dispatches = 0
for payload, expected_decision, expected_reason in HOSTILE_CASES:
    gate, result, dispatcher, emitter = run(payload)
    hostile_dispatches += dispatcher.count
    assert dispatcher.count == 0, payload  # INV-T1
    assert result.terminal is True, payload
    assert result.decision.decision == expected_decision, payload
    assert type(result.decision) is Decision, payload
    assert type(result.decision.decision) is str, payload
    assert result.decision.reason_code == expected_reason, payload
    assert result.decision.next_legal_action == STOP, payload
    assert f"DECISION {expected_decision}" in result.final_report, payload
    assert emitter.count == 1, payload  # INV-T2
assert hostile_dispatches == 0
assert _double_read.reads == 1, (
    "each field is read once, so a second read cannot forge a framework reason code"
)

# a framework rejection survives serialisation with its evidence intact, and no
# producer envelope may claim that exemption to carry its own fields through
framework = protocol_invalid("original rejection detail")
assert coerce(framework) == framework
assert Decision.from_mapping(framework.as_dict()) == framework
assert coerce(framework).evidence == ("original rejection detail",)
_, result, dispatcher, _ = run(framework)
assert result.decision == framework and dispatcher.count == 0
_, result, dispatcher, _ = run(blocked(reason_code=PROTOCOL_DECISION_INVALID))
assert result.decision.decision == TERMINAL_BLOCKED
assert result.decision.reason_code == PROTOCOL_DECISION_INVALID
assert result.decision.evidence != framework.evidence
assert result.decision.evidence != ("deterministic preflight fact",), (
    "a forged framework reason code must not carry the producer's envelope through"
)
assert dispatcher.count == 0

# --- INV-T1: aggregate non-dispatch over every terminal path ----------------
total_terminal_dispatches = 0
terminal_paths = (
    *TERMINAL_CASES.values(),
    *MALFORMED_CASES,
    *(payload for payload, _, _ in HOSTILE_CASES),
)
for payload in terminal_paths:
    _, result, dispatcher, _ = run(payload)
    assert result.terminal is True
    total_terminal_dispatches += dispatcher.count
assert total_terminal_dispatches == 0, total_terminal_dispatches

# --- INV-T2: a terminal decision is emitted once, never twice ---------------
gate, result, dispatcher, emitter = run(envelope())
assert emitter.count == 1
try:
    gate.apply(envelope())
except GateAlreadySettled:
    pass
else:  # pragma: no cover - the gate must refuse a second decision
    raise AssertionError("a settled gate accepted a second decision")
assert emitter.count == 1, "re-application must not emit a second final report"
assert dispatcher.count == 0


def broken_sink(report: str) -> None:
    raise RuntimeError("sink unavailable")


gate = TerminalGate(SpyDispatcher(), emit=broken_sink)
result = gate.apply(envelope())
assert result.terminal is True, "a broken sink must not lose the terminal decision"
assert len(result.reports) == 1
assert result.emit_error is not None and "sink unavailable" in result.emit_error
assert gate.dispatch_count == 0

# --- INV-T3: no post-terminal phase, including a later CONTINUE attempt -----
gate, result, dispatcher, emitter = run(envelope(decision=TERMINAL_SUCCESS, status="COMPLETE"))
try:
    gate.apply(CONTINUE_CASE)
except GateAlreadySettled:
    pass
else:  # pragma: no cover - a terminal decision has no successor phase
    raise AssertionError("a settled gate accepted a post-terminal CONTINUE")
assert dispatcher.count == 0, "a post-terminal CONTINUE must not reach the dispatcher"
assert gate.dispatch_count == 0
assert emitter.count == 1

# a CONTINUE gate is also single-use: one gate decides one decision point
gate, result, dispatcher, emitter = run(CONTINUE_CASE)
assert dispatcher.count == 1
try:
    gate.apply(CONTINUE_CASE)
except GateAlreadySettled:
    pass
else:  # pragma: no cover
    raise AssertionError("a settled gate accepted a second dispatch")
assert dispatcher.count == 1, "a settled gate must not dispatch twice"


class ReentrantDispatcher(SpyDispatcher):
    """A dispatched host that tries to push a second decision through the gate."""

    def __init__(self) -> None:
        super().__init__()
        self.refused = False

    def __call__(self, decision: Decision) -> str:
        try:
            reentrant_gate.apply(blocked())
        except GateAlreadySettled:
            self.refused = True
        return super().__call__(decision)


reentrant = ReentrantDispatcher()
reentrant_gate = TerminalGate(reentrant)
reentrant_gate.apply(CONTINUE_CASE)
assert reentrant.refused is True, "a re-entrant dispatcher must be refused, not deadlocked"
assert reentrant.count == 1
assert reentrant_gate.dispatch_count == 1

# --- INV-T4: invalid input can never be repaired into CONTINUE --------------
observed = set()
for payload in MALFORMED_CASES:
    _, result, dispatcher, _ = run(payload)
    observed.add((result.decision.decision, result.decision.reason_code))
    assert dispatcher.count == 0
assert observed == {(TERMINAL_BLOCKED, PROTOCOL_DECISION_INVALID)}, observed
assert CONTINUE not in {decision for decision, _ in observed}

# --- Envelope shape ---------------------------------------------------------
decision = Decision.from_mapping(envelope())
assert tuple(decision.as_dict()) == FIELD_ORDER
assert decision.evidence == ("deterministic preflight fact",)
assert decision.decision in TERMINAL_DECISIONS
_, result, dispatcher, _ = run(decision)  # a Decision instance is accepted, then revalidated
assert result.decision == decision and dispatcher.count == 0
empty_evidence = Decision.from_mapping(envelope(evidence=[]))
assert empty_evidence.evidence == ()
assert "EVIDENCE -" in empty_evidence.render()
assert "\n" not in Decision.from_mapping(envelope(status=" NOT_APPLICABLE ")).status
assert Decision.from_mapping(envelope(status=" NOT_APPLICABLE ")).status == "NOT_APPLICABLE"
assert Decision.from_mapping(envelope(decision=f" {TERMINAL_BLOCKED} ", status="BLOCKED",
                                      reason_code=WORKFLOW_REASON)).decision == TERMINAL_BLOCKED

# --- Core/runtime carry no workflow-specific or host-specific semantics -----
# The envelope and the gate must not know what a workflow or a host is. The
# package `__init__` is excluded because it is the aggregation point for the whole
# runtime and necessarily re-exports classification and intent names; that it only
# re-exports is asserted separately below.
for path in (
    CORE / "decision-envelope.md",
    RUNTIME / "decision.py",
    RUNTIME / "terminal_gate.py",
):
    text = path.read_text(encoding="utf-8")
    for token in (
        "dev-new",
        "dev-next",
        "dev-close",
        "dev-merge",
        "PRODUCT_FEATURE",
        "NON_PRODUCT",
        "READY_TO_CLOSE",
        "Claude",
        "claude",
        "Codex",
        "OpenCode",
    ):
        assert token not in text, (path.name, token)

# The public surface re-exports and decides nothing: no branch, no comparison, no
# call. A name it exports must be a name some module already owns.
package_init = code_only(RUNTIME / "__init__.py")
for forbidden in (" if ", "elif", "else", "==", "!=", " in ", "def ", "class ", "raise"):
    assert forbidden not in package_init, ("__init__.py", forbidden)
for host in ("Claude", "claude", "Codex", "OpenCode"):
    assert host not in (RUNTIME / "__init__.py").read_text(encoding="utf-8"), host
for name in runtime_package.__all__:
    assert hasattr(runtime_package, name), name
    owner = getattr(runtime_package, name)
    module = getattr(owner, "__module__", None)
    if module is not None:
        assert module != "runtime", (name, "defined in the package rather than a module")

envelope_doc = (CORE / "decision-envelope.md").read_text(encoding="utf-8")
for name in FIELD_ORDER:
    assert f"`{name}`" in envelope_doc, name
assert PROTOCOL_DECISION_INVALID in envelope_doc
assert f"`{PROTOCOL_VERSION}`" in envelope_doc, "Core must state the current envelope version"
assert RESERVED_REASON_PREFIX in envelope_doc
assert "Invalid input fails closed" in envelope_doc
# Core must describe the normalisation the runtime actually performs
assert "whitespace" in envelope_doc and "case-insensitively" in envelope_doc

print(
    "terminal gate checks passed\n"
    f"{TERMINAL_NOT_APPLICABLE} dispatch=0\n"
    f"{TERMINAL_BLOCKED} dispatch=0\n"
    f"{TERMINAL_SUCCESS} dispatch=0\n"
    f"{CONTINUE} dispatch=1\n"
    f"MALFORMED ({len(MALFORMED_CASES)} cases) dispatch={malformed_dispatches}\n"
    f"HOSTILE_INSTANCE ({len(HOSTILE_CASES)} cases) dispatch={hostile_dispatches}\n"
    f"TERMINAL_PATHS_TOTAL ({len(terminal_paths)} cases) dispatch={total_terminal_dispatches}\n"
    "INV-T1 INV-T2 INV-T3 INV-T4 verified"
)
