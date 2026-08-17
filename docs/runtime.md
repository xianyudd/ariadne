# The Ariadne runtime

The executable runtime. The contracts (`ariadne doc --list`) specify what the
protocol means; this is what actually runs, and it is the only path a workflow takes
from repository facts to a dispatched action.

## Layering

Each layer answers one question and holds no other layer's policy.

```text
Evidence layer   → what are the repository facts?
State resolver   → what state is the repository in?
Decision engine  → what does the protocol permit right now?
Terminal gate    → may control flow continue?
Router           → where does the one permitted action go?
Workflow         → how is it executed?
```

The order is fixed: `Evidence → State → Decision → Enforcement → Execution`. A
layer may read what precedes it. Nothing reads backwards, and nothing skips a step.

| Module | Layer | Owns |
| --- | --- | --- |
| `runtime/evidence.py` | Evidence | `collect_repository_evidence()`; reads Git, Feature artifacts, recorded state, the tasks file. Structured data, no policy, no stdout. |
| `dag/tasks.py` | Evidence | The one tasks-file parser and dependency resolver: `resolve_dag()` → `DagState`. |
| `runtime/classification.py` | State | `RepositoryEvidence` → `EntityClassification`. |
| `runtime/lifecycle.py` | State | `LifecycleResolver`, `LEGAL_TRANSITIONS`, `assert_legal_transition()`. |
| `runtime/state.py` | State | `resolve_state()` → the single `ResolvedState`, including `SafetyState`. |
| `runtime/decision_engine.py` | Decision | `decide()` → `Decision`. The one executable decision policy. |
| `runtime/decision.py` | Decision | The `Decision` envelope: frozen, validated, self-rendering. |
| `runtime/terminal_gate.py` | Enforcement | `TerminalGate`; the only path to dispatch. |
| `runtime/router.py` | Execution | `WorkflowRouter`: intent → dispatcher. Mapping only. |
| `runtime/api.py` | Entry point | `evaluate_workflow()`, `execute_workflow()`; what a host adapter calls. |
| `config.py` | Consumer seam | `ProjectConfig`: the repository facts only a consumer knows. |
| `cli.py` | Entry point | `ariadne`; argument parsing and rendering, no decision of its own. |

## Canonical flow

```text
repository
    ↓  collect_repository_evidence()
RepositoryEvidence          facts only
    ↓  resolve_state(evidence, workflow_intent)
ResolvedState               entity + lifecycle + review + safety + human gate + DAG
    ↓  decide(state)
Decision                    CONTINUE | TERMINAL_SUCCESS | TERMINAL_BLOCKED | TERMINAL_NOT_APPLICABLE
    ↓  TerminalGate(dispatcher).apply(decision)
TERMINAL_* → one final report, zero dispatch
CONTINUE   → exactly one dispatch, through the router
```

Evidence is collected once, state is resolved once, and every layer downstream reads
that one result. A host adapter calls `execute_workflow()` — through `ariadne dev` —
and does none of this itself.

Lifecycle state is derived from repository evidence on every normal path. No runtime
entry point accepts an injected lifecycle state, and insufficient or contradictory
evidence resolves to `UNKNOWN`, which fails closed — never to the nearest plausible
state.

## Where a consumer enters

Three seams, and no others:

```text
project configuration → repository facts        (.ariadne/project.toml → ProjectConfig)
planning provider     → where Features live    (integrations/planning.py)
quality gate provider → structured verdicts    (integrations/gates.py)
```

A gate provider hands the runtime `test = PASS`. The runtime never runs a gate and
has no code path that could ask which tool produced one — see `examples/`, where the
same configuration is written three ways for three different languages.

## Reason codes

`ariadne doc reason-codes`, bound to `decision_engine.REASON_CODES` by
`tests/test_decision_consistency.py`.

## What the runtime does not do

The runtime holds control flow and nothing else. It is deliberately small: standard
library only, no async runtime, no event bus, no scheduler, no database, no
orchestration framework.

- The decision engine reads no repository and dispatches nothing.
- The router re-judges nothing. It maps an intent to one dispatcher and refuses
  anything else, including any envelope that is not `CONTINUE`.
- Host adapters hold no decision semantics. The same repository state and intent
  produce the same envelope on every host.
- Markdown does not own runtime decision semantics. The contracts are the
  specification, `tests/fixtures/` are examples, and both are bound to this code by
  `tests/test_decision_consistency.py`.

## Validation

```bash
python3 tests/run_all.py
```

`tests/audit_wiring.py` is the architecture-level check: it fails if a second
decision policy, a dispatch path that bypasses the gate, or a host adapter with
decision semantics reappears.
