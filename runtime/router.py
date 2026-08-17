"""Workflow Router: the single mapping from a granted decision to one dispatcher.

The router answers exactly one question: *when continuation is granted, which one
action runs next?* It is deliberately thin.

It contains no policy. It does not classify an entity, resolve a lifecycle state,
check safety, or decide terminality — those are already settled by the time an
envelope reaches it, and re-deciding them here would create a second policy.

Two structural properties matter:

* the router is reachable only as the terminal gate's dispatcher, so nothing is
  routed for a `TERMINAL_*` decision;
* dispatchers are registered per workflow intent and the registry is fixed at
  construction, so one workflow's envelope can never reach another workflow's
  dispatcher. That is what makes "`/dev-close` never merges" structural rather
  than a prompt: no merge dispatcher is registered for `DEV_CLOSE`.

Standard library only.
"""

from __future__ import annotations

from typing import Any, Callable

from .decision import CONTINUE, Decision
from .state import WORKFLOW_INTENTS


class RouterRefused(RuntimeError):
    """The router was asked to route something it must never route.

    This is a structural assertion, not a decision: the gate is the only legal
    caller and it calls the router only for `CONTINUE`, so reaching this means the
    runtime was wired wrong.
    """


class WorkflowRouter:
    """Maps `CONTINUE` envelopes to exactly one registered dispatcher."""

    def __init__(self, dispatchers: dict[str, Callable[[Decision], Any]]) -> None:
        unknown = sorted(set(dispatchers) - WORKFLOW_INTENTS)
        if unknown:
            raise ValueError(f"unknown workflow intent(s): {', '.join(unknown)}")
        for intent, dispatcher in dispatchers.items():
            if not callable(dispatcher):
                raise TypeError(f"dispatcher for {intent} must be callable")
        # Copied and never mutated: a caller cannot add a dispatcher to an intent
        # after the router has been built.
        self._dispatchers: dict[str, Callable[[Decision], Any]] = dict(dispatchers)

    @property
    def intents(self) -> tuple[str, ...]:
        return tuple(sorted(self._dispatchers))

    def route(self, decision: Decision) -> Any:
        """Dispatch `decision` to the one dispatcher registered for its workflow."""
        if not isinstance(decision, Decision):
            raise RouterRefused("router accepts only a validated Decision envelope")
        if decision.decision != CONTINUE:
            raise RouterRefused(
                f"router reached with a non-CONTINUE decision: {decision.decision}"
            )
        dispatcher = self._dispatchers.get(decision.workflow)
        if dispatcher is None:
            raise RouterRefused(f"no dispatcher registered for workflow {decision.workflow}")
        return dispatcher(decision)

    def __call__(self, decision: Decision) -> Any:
        """Allow the router itself to be a terminal gate's dispatcher."""
        return self.route(decision)
