"""The single runtime boundary every host adapter and workflow goes through.

```text
Repository
  → Evidence      (evidence.py)      what are the facts?
  → State         (state.py)         what state is this?
  → Decision      (decision_engine.py) what does the protocol permit?
  → Envelope      (decision.py)      the one cross-layer value
  → TerminalGate  (terminal_gate.py) may control flow continue?
  → Router        (router.py)        which single action runs next?
  → Workflow      (host dispatcher)  how it is executed
```

`evaluate_workflow` produces the envelope. `execute_workflow` enforces it: it
builds one gate for the decision point and routes only a granted `CONTINUE`. A
caller never receives the dispatcher, so there is no path to workflow execution
that skips the gate.

Standard library only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .decision import Decision
from .decision_engine import decide
from .router import WorkflowRouter
from .state import (
    HUMAN_GATE_UNKNOWN,
    ResolvedState,
    resolve_repository_state,
)
from .terminal_gate import GateResult, TerminalGate


def evaluate_state(state: ResolvedState) -> Decision:
    """Decide from an already-resolved state."""
    return decide(state)


def evaluate_workflow(
    repo: Path,
    workflow_intent: str,
    *,
    human_gate: str = HUMAN_GATE_UNKNOWN,
    dry_run: bool = False,
    default_branch: str = "main",
) -> Decision:
    """Collect evidence, resolve state, and decide — once, for one invocation.

    The lifecycle state is always derived from the repository here; there is no
    parameter through which a caller could inject one.
    """
    state = resolve_repository_state(
        repo,
        workflow_intent,
        human_gate=human_gate,
        dry_run=dry_run,
        default_branch=default_branch,
    )
    return decide(state)


def enforce(
    decision: Decision,
    dispatcher: Callable[[Decision], Any] | WorkflowRouter,
    *,
    emit: Callable[[str], Any] | None = None,
) -> GateResult:
    """Run one decision through one fresh terminal gate.

    A new gate per decision point is deliberate: a shared gate would already be
    settled, and a gate reused across decision points would let one grant serve
    two dispatches.
    """
    gate = TerminalGate(dispatcher, emit=emit)
    return gate.apply(decision)


def execute_workflow(
    repo: Path,
    workflow_intent: str,
    dispatcher: Callable[[Decision], Any] | WorkflowRouter,
    *,
    human_gate: str = HUMAN_GATE_UNKNOWN,
    dry_run: bool = False,
    default_branch: str = "main",
    emit: Callable[[str], Any] | None = None,
) -> GateResult:
    """Evaluate a workflow against the repository and enforce the result.

    This is the only supported way to reach workflow execution: the dispatcher is
    invoked by the gate, for `CONTINUE`, exactly once, or not at all.
    """
    decision = evaluate_workflow(
        repo,
        workflow_intent,
        human_gate=human_gate,
        dry_run=dry_run,
        default_branch=default_branch,
    )
    return enforce(decision, dispatcher, emit=emit)
