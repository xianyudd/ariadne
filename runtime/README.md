# AGENT-SDLC Runtime

The executable runtime. Core (`.agent-sdlc/core/`) specifies what the protocol
means; this directory is what actually runs, and it is the only path a workflow
takes from repository facts to a dispatched action.

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
layer may read what precedes it. Nothing reads backwards, and nothing skips a
step.

| Module | Layer | Owns |
| --- | --- | --- |
| `evidence.py` | Evidence | `collect_repository_evidence()`; reads Git, Feature artifacts, recorded state, `tasks.md`. Structured data, no policy, no stdout. |
| `dag.py` | Evidence | The one `tasks.md` parser and dependency resolver: `resolve_dag()` → `DagState`. |
| `classification.py` | State | `RepositoryEvidence` → `EntityClassification`. |
| `lifecycle.py` | State | `LifecycleResolver`, `LEGAL_TRANSITIONS`, `assert_legal_transition()`. |
| `state.py` | State | `resolve_state()` → the single `ResolvedState`, including `SafetyState`. |
| `decision_engine.py` | Decision | `decide()` → `Decision`. The one executable decision policy. |
| `decision.py` | Decision | The `Decision` envelope: frozen, validated, self-rendering. |
| `terminal_gate.py` | Enforcement | `TerminalGate`; the only path to dispatch. |
| `router.py` | Execution | `WorkflowRouter`: intent → dispatcher. Mapping only. |
| `api.py` | Entry point | `evaluate_workflow()`, `execute_workflow()`; what a host adapter calls. |

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

Evidence is collected once, state is resolved once, and every layer downstream
reads that one result. A host adapter calls `execute_workflow()` and does none of
this itself.

Lifecycle state is derived from repository evidence on every normal path. No
runtime entry point accepts an injected lifecycle state, and insufficient or
contradictory evidence resolves to `UNKNOWN`, which fails closed — never to the
nearest plausible state.

## Reason codes

Every terminal decision carries a reason code. These are the only codes the engine
emits; `decision_engine.REASON_CODES` is the enumerable form, and
`validation/test_decision_consistency.py` fails if this reference and that set
disagree in either direction.

The `PROTOCOL_` prefix is reserved for the framework
(`../core/decision-envelope.md`), so no workflow reason code uses it.

```text
GIT_STATE_UNAVAILABLE             Repository Git state could not be read. Blocks every workflow.
ENTITY_UNKNOWN                    Entity evidence is insufficient or mixed. Blocks every workflow.
ENTITY_NOT_PRODUCT_FEATURE        The branch is workflow/infrastructure, not a Product Feature.
LIFECYCLE_UNKNOWN                 Lifecycle evidence explains no declared position.
LIFECYCLE_NOT_READY_TO_CLOSE      /dev-merge requires READY_TO_CLOSE.
LIFECYCLE_BASE_STATE_NOT_ALLOWED  The workflow does not run from this lifecycle state.
TASKS_INCOMPLETE                  Final acceptance requires every task complete.
DAG_INVALID                       The task graph does not validate; no workflow proceeds on its authority.
NO_READY_FRONTIER                 Every unfinished task is blocked; no batch can be selected.
REVIEW_UNRESOLVED                 Recorded review findings are unresolved, or no resolved-review evidence exists.
WORKING_TREE_UNSAFE               The tracked working tree has changes outside protected paths.
MERGE_AUTHORIZATION_REQUIRED      A real merge needs an APPROVED Human Gate; NOT_APPROVED and UNKNOWN both fail closed.
FEATURE_ALREADY_CLOSED            There is no remaining work for this entry point. Reported NOT_APPLICABLE, not BLOCKED.
WORKFLOW_INTENT_UNSUPPORTED       The declared intent is not one of the four workflows.
PROTOCOL_DECISION_INVALID         Framework-reserved. A malformed, unknown, or wrong-version envelope, coerced to TERMINAL_BLOCKED.
```

`ENTITY_NOT_PRODUCT_FEATURE` and `FEATURE_ALREADY_CLOSED` are the two codes whose
decision depends on the entry point. `/dev-new` blocks on a non-Product-Feature
branch, because starting a Feature there is an error; the other three workflows
report `TERMINAL_NOT_APPLICABLE`, because there is simply nothing of theirs to do.
Each workflow's document states its own table.

## What the runtime does not do

The runtime holds control flow and nothing else. It is deliberately small:
standard library only, no async runtime, no event bus, no scheduler, no database,
no orchestration framework.

- The decision engine reads no repository and dispatches nothing.
- The router re-judges nothing. It maps an intent to one dispatcher and refuses
  anything else, including any envelope that is not `CONTINUE`.
- Host adapters hold no decision semantics. The same repository state and intent
  produce the same envelope on every host.
- Markdown does not own runtime decision semantics. `../core/` is the
  specification, `validation/fixtures/` are examples, and both are bound to this
  code by `validation/test_decision_consistency.py`.

## Validation

```bash
python3 .agent-sdlc/validation/run_all.py
```

`validation/audit_wiring.py` is the architecture-level check: it fails if a second
decision policy, a dispatch path that bypasses the gate, or a host adapter with
decision semantics reappears.
