"""Runtime Terminal Gate: control-flow enforcement over a Decision Envelope.

A terminal decision must not depend on agent compliance. The gate therefore
owns dispatch: the caller cannot reach the dispatcher except through the gate,
and the gate calls it only for `CONTINUE`. For any `TERMINAL_*` decision the
dispatcher is never called, the final report is produced exactly once, and the
settled gate refuses any further decision.

One gate decides one decision point. There is deliberately no convenience
function that builds a gate per call, because a per-call gate would make single
use a caller convention again instead of a runtime guarantee.

Standard library only; no host tool, model, or provider is referenced.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from .decision import (
    TERMINAL_DECISIONS,
    Decision,
    InvalidDecision,
    coerce,
    protocol_invalid,
)


class GateAlreadySettled(RuntimeError):
    """A settled gate was asked to decide again."""


@dataclass(frozen=True)
class GateResult:
    """The outcome of one gate application.

    `decision` is the effective envelope, which is the framework's fail-closed
    envelope when the supplied payload was invalid. `reports` is the
    authoritative emission: it holds the single final report for a terminal
    decision even if the optional sink failed, in which case `emit_error`
    describes the failure. A continued workflow reports its own result, so the
    gate emits nothing for `CONTINUE`.
    """

    decision: Decision
    terminal: bool
    dispatch_count: int
    reports: tuple[str, ...] = ()
    dispatch_result: Any = field(default=None)
    emit_error: str | None = None

    @property
    def final_report(self) -> str | None:
        return self.reports[0] if self.reports else None


class TerminalGate:
    """Single-use gate between a workflow decision and host dispatch."""

    def __init__(
        self,
        dispatcher: Callable[[Decision], Any],
        *,
        emit: Callable[[str], Any] | None = None,
    ) -> None:
        if not callable(dispatcher):
            raise TypeError("dispatcher must be callable")
        if emit is not None and not callable(emit):
            raise TypeError("emit must be callable")
        self._dispatcher = dispatcher
        self._emit = emit
        self._lock = threading.Lock()
        self._settled = False
        self._dispatch_count = 0

    @property
    def settled(self) -> bool:
        return self._settled

    @property
    def dispatch_count(self) -> int:
        return self._dispatch_count

    def apply(self, payload: Any) -> GateResult:
        """Decide, then either dispatch once or terminate once.

        A dispatcher failure after a legal `CONTINUE` propagates to the caller;
        the gate has already granted continuation and does not retry it.
        """
        self._settle()

        try:
            decision = coerce(payload)
        except InvalidDecision as error:
            decision = protocol_invalid(str(error))
        except Exception as error:  # no validation path may escape without an envelope
            decision = protocol_invalid(f"{type(error).__name__}: {error}")

        # Branch on the validated field, never on an overridable property.
        if decision.decision in TERMINAL_DECISIONS:
            report = decision.render()
            emit_error: str | None = None
            if self._emit is not None:
                try:
                    self._emit(report)
                except Exception as error:  # a broken sink must not lose the decision
                    emit_error = f"{type(error).__name__}: {error}"
            return GateResult(
                decision=decision,
                terminal=True,
                dispatch_count=self._dispatch_count,
                reports=(report,),
                emit_error=emit_error,
            )

        self._dispatch_count += 1
        return GateResult(
            decision=decision,
            terminal=False,
            dispatch_count=self._dispatch_count,
            dispatch_result=self._dispatcher(decision),
        )

    def _settle(self) -> None:
        """Claim this gate's single decision, or refuse.

        The claim is taken under a lock and released before any dispatch, so
        concurrent hosts cannot both pass the guard and a re-entrant dispatcher
        is refused rather than deadlocked.
        """
        with self._lock:
            if self._settled:
                raise GateAlreadySettled("this gate already produced a final decision")
            self._settled = True
