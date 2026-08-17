"""Decision Envelope for the Agent SDLC runtime.

Standard library only. This module owns envelope shape and validity. It does
not own control flow (see `terminal_gate.py`), it knows no workflow's
classification vocabulary, and it names no host tool, model, or provider.

Semantics are declared in `.agent-sdlc/core/decision-envelope.md` and
`.agent-sdlc/core/terminal-contract.md`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from typing import Any

PROTOCOL_VERSION = "2.1"

CONTINUE = "CONTINUE"
TERMINAL_SUCCESS = "TERMINAL_SUCCESS"
TERMINAL_BLOCKED = "TERMINAL_BLOCKED"
TERMINAL_NOT_APPLICABLE = "TERMINAL_NOT_APPLICABLE"

TERMINAL_DECISIONS = frozenset({TERMINAL_SUCCESS, TERMINAL_BLOCKED, TERMINAL_NOT_APPLICABLE})
DECISIONS = frozenset({CONTINUE}) | TERMINAL_DECISIONS

STOP = "STOP"
PROTOCOL_DECISION_INVALID = "PROTOCOL_DECISION_INVALID"
RESERVED_REASON_PREFIX = "PROTOCOL_"

FIELD_ORDER = (
    "protocol_version",
    "workflow",
    "phase",
    "classification",
    "decision",
    "status",
    "reason_code",
    "evidence",
    "next_legal_action",
    "human_action_required",
)

_INVALID_WORKFLOW = "UNDECLARED"
_INVALID_PHASE = "RUNTIME_TERMINAL_GATE"
_INVALID_STATUS = "BLOCKED"
_EVIDENCE_LIMIT = 200
_NONE_TOKEN = "-"


class InvalidDecision(ValueError):
    """A payload cannot be read as a valid Decision Envelope."""


def _text(name: str, value: Any, *, nullable: bool = False) -> str | None:
    if value is None:
        if nullable:
            return None
        raise InvalidDecision(f"{name} is required")
    if not isinstance(value, str):
        raise InvalidDecision(f"{name} must be a non-empty string")
    # Unbound `str.strip`, never `value.strip()` or `str(value).strip()`: both
    # route through the producer's own `__str__`/`strip`, which a `str` subclass
    # can define to return itself and so carry a lying `__eq__`/`__hash__`
    # through validation into the membership tests that decide dispatch.
    text = str.strip(value)
    if not text:
        raise InvalidDecision(f"{name} must be a non-empty string")
    return text


_FRAMEWORK_SHAPE = {
    "workflow": _INVALID_WORKFLOW,
    "phase": _INVALID_PHASE,
    "classification": None,
    "decision": TERMINAL_BLOCKED,
    "status": _INVALID_STATUS,
    "reason_code": PROTOCOL_DECISION_INVALID,
    "next_legal_action": STOP,
    "human_action_required": True,
}


def _is_framework_authored(data: Mapping[str, Any]) -> bool:
    """Whether `data` is exactly the framework's own fail-closed envelope.

    Each value is normalised to a plain one before comparison, and the declared
    constant is on the left, so a `str` subclass with a lying `__eq__` cannot
    claim the exemption. `evidence` is free: the rejection detail is precisely
    what a round trip has to preserve.
    """
    for name, expected in _FRAMEWORK_SHAPE.items():
        value = data.get(name)
        if isinstance(value, str):
            value = str.strip(value)
        if expected != value:
            return False
    return True


def _detail(text: str) -> str:
    detail = " ".join(text.split()) or "decision payload rejected"
    if len(detail) > _EVIDENCE_LIMIT:
        detail = detail[: _EVIDENCE_LIMIT - 1] + "…"
    return detail


@dataclass(frozen=True, kw_only=True)
class Decision:
    """One workflow decision point, validated on construction.

    Every field is required and explicit: a safety-critical envelope has no
    implicit defaults, so an omitted field is a protocol error rather than a
    silently assumed value.
    """

    protocol_version: str
    workflow: str
    phase: str
    classification: str | None
    decision: str
    status: str
    reason_code: str | None
    evidence: tuple[str, ...]
    next_legal_action: str
    human_action_required: bool

    def __post_init__(self) -> None:
        set_field = object.__setattr__
        set_field(self, "protocol_version", _text("protocol_version", self.protocol_version))
        if self.protocol_version != PROTOCOL_VERSION:
            raise InvalidDecision(
                f"protocol_version {self.protocol_version!r} is not {PROTOCOL_VERSION!r}"
            )
        set_field(self, "workflow", _text("workflow", self.workflow))
        set_field(self, "phase", _text("phase", self.phase))
        set_field(self, "classification", _text("classification", self.classification, nullable=True))
        set_field(self, "status", _text("status", self.status))
        set_field(self, "reason_code", _text("reason_code", self.reason_code, nullable=True))

        # `decision` is validated as text before any membership test: an unhashable
        # value must fail closed rather than raise out of validation.
        set_field(self, "decision", _text("decision", self.decision))
        if self.decision not in DECISIONS:
            raise InvalidDecision(f"decision {self.decision!r} is not a declared decision value")

        # The reserved token has one canonical form, so no casing or padding of
        # `STOP` can disagree with the decision it accompanies.
        next_legal_action = _text("next_legal_action", self.next_legal_action)
        if next_legal_action.upper() == STOP:
            next_legal_action = STOP
        set_field(self, "next_legal_action", next_legal_action)

        if not isinstance(self.human_action_required, bool):
            raise InvalidDecision("human_action_required must be a boolean")
        if isinstance(self.evidence, (str, bytes)) or not isinstance(self.evidence, Sequence):
            raise InvalidDecision("evidence must be a sequence of non-empty strings")
        set_field(self, "evidence", tuple(_text("evidence entry", item) for item in self.evidence))

        if self.decision in TERMINAL_DECISIONS:
            if self.next_legal_action != STOP:
                raise InvalidDecision(
                    f"{self.decision} has no legal successor phase; "
                    f"next_legal_action must be {STOP}"
                )
            if self.decision == TERMINAL_BLOCKED and self.reason_code is None:
                raise InvalidDecision(f"{TERMINAL_BLOCKED} requires a reason_code")
        elif self.next_legal_action == STOP:
            raise InvalidDecision(f"{CONTINUE} requires a next legal phase, not {STOP}")

    @property
    def is_terminal(self) -> bool:
        return self.decision in TERMINAL_DECISIONS

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> Decision:
        """Validate an ingested envelope.

        Every field is read from the payload exactly once, so a mapping that
        answers differently on a second read cannot show one value to a check
        and another to the constructor.

        The `PROTOCOL_` reason-code prefix is refused so a producer cannot forge
        a framework rejection. The framework's own fail-closed envelope is the
        single exemption: it must survive a round trip through `as_dict`, and
        reproducing that exact shape yields a terminal decision either way.
        """
        if not isinstance(payload, Mapping):
            raise InvalidDecision("decision payload must be a mapping")
        # Key presence is settled from the key set alone: `key not in payload`
        # would reach `__getitem__` on a Mapping, making a second read of a field
        # observable to the payload before validation has seen the first.
        keys = set(payload)
        unknown = sorted(str(key) for key in keys - set(FIELD_ORDER))
        if unknown:
            raise InvalidDecision(f"unknown envelope field(s): {', '.join(unknown)}")
        missing = [name for name in FIELD_ORDER if name not in keys]
        if missing:
            raise InvalidDecision(f"missing envelope field(s): {', '.join(missing)}")
        data = {name: payload[name] for name in FIELD_ORDER}
        reason_code = data["reason_code"]
        if (
            isinstance(reason_code, str)
            and str.strip(reason_code).upper().startswith(RESERVED_REASON_PREFIX)
            and not _is_framework_authored(data)
        ):
            raise InvalidDecision(
                f"reason_code prefix {RESERVED_REASON_PREFIX!r} is reserved for the framework"
            )
        return cls(**data)

    def as_dict(self) -> dict[str, Any]:
        """Return the envelope in declared schema order."""
        value: dict[str, Any] = {}
        for field in fields(self):
            attribute = getattr(self, field.name)
            value[field.name] = list(attribute) if field.name == "evidence" else attribute
        return value

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=2)

    def render(self) -> str:
        """Render the deterministic final report for this envelope."""
        lines = [
            f"PROTOCOL_VERSION {self.protocol_version}",
            f"WORKFLOW {self.workflow}",
            f"PHASE {self.phase}",
            f"CLASSIFICATION {self.classification or _NONE_TOKEN}",
            f"DECISION {self.decision}",
            f"STATUS {self.status}",
            f"REASON_CODE {self.reason_code or _NONE_TOKEN}",
        ]
        if self.evidence:
            lines.append("EVIDENCE")
            lines.extend(f"- {item}" for item in self.evidence)
        else:
            lines.append(f"EVIDENCE {_NONE_TOKEN}")
        lines.append(f"NEXT_LEGAL_ACTION {self.next_legal_action}")
        lines.append(
            f"HUMAN_ACTION_REQUIRED {'true' if self.human_action_required else 'false'}"
        )
        return "\n".join(lines)


def coerce(payload: Any) -> Decision:
    """Read any payload as a validated plain `Decision`.

    An existing `Decision` instance is never trusted: its declared fields are
    re-read by name and revalidated. That downgrades a subclass, which could
    otherwise override `is_terminal` or a field property, and rejects an
    instance mutated after construction. Raises `InvalidDecision` otherwise.
    """
    if isinstance(payload, Decision):
        payload = {name: getattr(payload, name) for name in FIELD_ORDER}
    if isinstance(payload, Mapping):
        return Decision.from_mapping(payload)
    raise InvalidDecision(f"unsupported decision payload type: {type(payload).__name__}")


def protocol_invalid(detail: str) -> Decision:
    """Build the fail-closed envelope that replaces an invalid decision.

    No field of the rejected payload is carried forward; only a bounded
    description of the rejection is recorded as evidence. The result round-trips:
    `coerce` accepts it back and keeps that evidence, so a rejection can cross a
    serialisation boundary without losing why it was rejected.
    """
    return Decision(
        protocol_version=PROTOCOL_VERSION,
        workflow=_INVALID_WORKFLOW,
        phase=_INVALID_PHASE,
        classification=None,
        decision=TERMINAL_BLOCKED,
        status=_INVALID_STATUS,
        reason_code=PROTOCOL_DECISION_INVALID,
        evidence=(_detail(detail),),
        next_legal_action=STOP,
        human_action_required=True,
    )
