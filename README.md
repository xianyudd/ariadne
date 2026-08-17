# Agent SDLC v2

Agent SDLC is the repository workflow protocol for turning one approved Feature into a reviewed, closable, and mergeable change. The durable protocol is here; a host adapter only exposes an invocation, loads these files, and maps host-native capabilities.

## Architecture

```text
.agent-sdlc/       Agent-independent Core + tflow project policy
  core/            decision semantics, lifecycle, contracts
  runtime/         control-flow enforcement (standard library only)
  workflows/       host-independent workflow definitions
  validation/      deterministic protocol checks
.agents/           portable skill adapter (Codex/OpenCode-compatible)
.claude/           Claude Code invocation and reviewer adapter
.codex/            Codex reviewer adapter
.opencode/         OpenCode command and reviewer adapters
```

Core must not depend on a host tool name, model name, provider, context-window number, or invocation syntax. Project policy supplies Rust/tflow facts. The same workflow decision must result from the same repository state on every host.

### Core vs adapter

Core owns lifecycle, terminal decision semantics, the Decision Envelope, state precedence, task DAG validation, ready-frontier calculation, batch policy, review contract, Human Gates, Git policy, and context/session boundaries. The runtime owns control-flow enforcement over a decision: Core says what a decision means, the runtime decides what may run next. Project policy owns quality gates, module ownership, persistence semantics, and protected paths. Adapters own only command exposure, portable loading instructions, host permissions, and reviewer delegation.

To add another host, add a thin adapter that loads the existing `.agent-sdlc/workflows/` and required policy files. Do not copy the workflow into the adapter.

## Managed lifecycle entity

`/dev-merge` is not a generic Git merge command. It first classifies the current repository entity using `.agent-sdlc/core/lifecycle-entity.md`:

```text
PRODUCT_FEATURE | NON_PRODUCT | UNKNOWN
```

A workflow/infrastructure branch such as `agent-sdlc-v2` is `NON_PRODUCT` only when positive repository evidence supports that classification. A random branch with insufficient evidence remains `UNKNOWN`; absence of a Feature registration alone is not enough.
`/dev-merge` applies the terminal decision contract before any closure phase:

```text
PRODUCT_FEATURE + READY_TO_CLOSE → CONTINUE
PRODUCT_FEATURE + IN_PROGRESS     → TERMINAL_BLOCKED
NON_PRODUCT                      → TERMINAL_NOT_APPLICABLE
UNKNOWN                          → TERMINAL_BLOCKED
```

Terminal decisions emit their status and stop immediately; only `CONTINUE` enters the normal Product Feature merge flow. Each decision carries the reportable status `READY`, `BLOCKED`, or `NOT_APPLICABLE`; that mapping belongs to `.agent-sdlc/core/terminal-contract.md`, which states it once. This table is the same table, verified row by row against the engine by `.agent-sdlc/validation/test_decision_consistency.py`.

## Runtime

A terminal decision must not depend on an agent choosing to stop, and a workflow decision must not depend on an agent reading a table correctly. Both belong to code. `.agent-sdlc/runtime/` is the one path from repository facts to a dispatched phase, and every host takes it:

```text
Evidence     collect_repository_evidence   what the repository contains
State        resolve_state                 what state that evidence proves
Decision     decide                        what the protocol permits
Enforcement  TerminalGate                  whether control flow may continue
Router       WorkflowRouter                where the one next action goes
Workflow     .agent-sdlc/workflows/        how that phase is carried out
```

Each layer consumes the layer above and owns one question. No layer restates another's policy: evidence judges nothing, the engine dispatches nothing, the gate maps nothing, and the router decides nothing. `.agent-sdlc/runtime/README.md` documents the modules and the reason-code vocabulary.

The decision crossing those boundaries is a structured Decision Envelope (`.agent-sdlc/core/decision-envelope.md`), and the runtime owns what may happen next:

```text
deterministic preflight
    ↓
Decision Envelope
    ↓
Runtime Terminal Gate
    ↓
TERMINAL_* → emit exactly one final report → no host dispatch
CONTINUE   → host dispatch may proceed
```

`.agent-sdlc/runtime/` is standard-library Python with no host, model, or provider dependency: no async runtime, event bus, scheduler, database, or orchestration framework. The gate is the only path to dispatch, one gate decides one decision point, and it calls the dispatcher only for `CONTINUE`. Every envelope is revalidated where it is used, so a producer cannot force a terminal decision through by supplying a subclass, a lying comparison, a method it overrides, or an object mutated after construction. An envelope that is malformed, unknown, or from another protocol version fails closed to `TERMINAL_BLOCKED` with `PROTOCOL_DECISION_INVALID` and never becomes `CONTINUE`.

Lifecycle state is derived from repository evidence on every runtime path. It cannot be supplied by an argument, and evidence that proves no position yields `UNKNOWN`, which fails closed rather than resolving to the nearest plausible state.

```text
Core      defines semantics
Runtime   owns control-flow enforcement
Workflow  uses Core semantics
Adapter   may invoke an agent only after the runtime returns CONTINUE
```

### How hosts enter the runtime

Every adapter — `.claude/skills/`, `.agents/skills/`, `.opencode/commands/` — runs one command before it loads a workflow or reads any evidence:

```bash
python3 .agent-sdlc/runtime/cli.py DEV_MERGE --human-gate UNKNOWN [--dry-run]
```

That command is the decision, not an advisory check. A non-zero exit means it has already printed the one final report and the adapter emits it and stops; exit `0` prints the single phase that is granted. Because all three families call the same entry point, the same repository state and intent produce the same envelope on every host. Establishing the Human Gate state is the only judgement an adapter makes, and anything but `APPROVED` fails closed.

### Before and after

| | Before | After |
|---|---|---|
| Decision policy | restated in Markdown per workflow and per host | one engine, `runtime/decision_engine.py`; Markdown is its specification and is tested against it |
| Lifecycle state | injectable through a `--lifecycle-state` argument | derived from evidence; the argument no longer exists |
| Terminal enforcement | an obligation the workflow prose placed on the agent | a gate the agent cannot reach around |
| Dispatch | the agent chose its next phase | the router dispatches exactly the phase the envelope grants, exactly once |
| Task graph | parsed wherever a workflow needed it | one resolver, `runtime/dag.py` |
| Host adapters | each carried its own copy of the rules | each calls `runtime/cli.py` and carries none |

`.agent-sdlc/validation/test_terminal_gate.py` proves the enforcement invariants against a spy dispatcher, with no agent involved: `INV-T1` terminal non-dispatch, `INV-T2` single terminal emission, `INV-T3` no post-terminal phase, `INV-T4` invalid decision fails closed. Coverage includes hostile envelope shapes, and the suite fails if any of them reaches the dispatcher. `test_runtime_closure.py` proves the same chain end to end from a real repository fixture, and `audit_wiring.py` reads the repository as text to prove nothing bypasses it.

## Workflow entries

- `/dev-next`: restore → DAG-aware one-batch selection → implement → project gates → commit → independent review/fix loop → handoff → stop.
- `/dev-close`: final gates, smoke, scope and review audit → `READY_TO_CLOSE` Human Gate; never merges.
- `/dev-merge`: closure checkpoint → normal merge policy → post-merge gates → `CLOSED`; never deletes branches/worktrees or starts another Feature.

An explicit `dev-next` after a successful preparation checkpoint is the implementation approval. No extra confirmation prompt is required.

## Task DAG and batch selection

`tasks.md` remains the only task truth. New tasks retain their checkbox and add compact metadata:

```text
- [ ] T007 [US1] Implement the persistence path in src/app.rs
  Depends: T003, T004
  Story: US1
  Area: app,persistence
  Risk: high
```

`Depends:` defines scheduling. The validator rejects unknown dependencies, self-dependencies, duplicate IDs, cycles, unreachable nodes, and incoherent completion state. The ready frontier is `unfinished(task) AND all(depends_on(task)) == completed`. The DAG answers what can run; Batch Policy chooses one coherent batch, usually 2–5 tasks but never by artificial counting. Parallel writers are not enabled.

Historical tasks without per-task metadata are explicitly legacy. They are not rewritten or silently treated as fully schedulable. A legacy file with all tasks complete can be audited; an incomplete legacy frontier that cannot be proven requires a Human Gate.

## Reviewer

The reviewer is read-only and independent where the host supports it. It checks correctness, acceptance, regression, persistence/data semantics, tests, architecture boundaries, release/debug seams, and scope. It reports `PASS` or `NEEDS_FIX` with `BLOCKER`, `MAJOR`, and `MINOR` findings. If the host cannot create an independent reviewer, the result is `REVIEW CAPABILITY BLOCKED`, never a fabricated PASS.

## Human Gates

Stop for substantive artifact conflicts, architecture or dependency changes, installations, destructive Git/worktree actions, data-loss risk, scope expansion, merge conflicts/target drift, unavailable review capability, unknown context safety, or three failed review/fix cycles. Report evidence and the decision needed.

## Context and session model

```text
Repository = durable memory
Session    = disposable worker
```

Restore from actual Git/source, tasks, spec/plan/contracts, and current-state. Context is abstractly `HEALTHY`, `PRESSURE`, `BOUNDARY_REQUIRED`, or `UNKNOWN`; unavailable telemetry must remain `UNKNOWN`, never a guessed percentage. On overflow or compaction failure, preserve safe repository state, report `SESSION_BOUNDARY_REQUIRED`, and stop rather than retrying an oversized request forever.

## Host invocation matrix

| Host | Entry points | Status |
|---|---|---|
| Claude Code | `/dev-new`, `/dev-next`, `/dev-close`, `/dev-merge` | adapter present; locally invocable host |
| Codex | `$dev-new`, `$dev-next`, `$dev-close`, `$dev-merge` | static adapter present; local host not assumed |
| OpenCode | `/dev-new`, `/dev-next`, `/dev-close`, `/dev-merge` | static adapter present; local host not assumed |

All entries load the same `.agent-sdlc Core`; only invocation syntax, permission mapping, and reviewer delegation differ.

## Feature 002 read-only DAG example

Feature 002 has 17 tasks and five historically recorded batches. Its current `tasks.md` is a legacy-format artifact: dependencies are expressed in phase/key-chain prose rather than per-task `Depends:` metadata, so the validator must report legacy compatibility instead of inventing a second truth.

```text
T001–T003  preparation / setup
T004–T006  edit-state and persistence foundation
T007–T011  complete edit interaction path
T012–T014  validation and failure safety
T015–T017  final quality, manual verification, scope audit
```

The historical key chain is dependency-coherent: setup precedes the edit reducer; the reducer precedes UI/runtime wiring; the complete path precedes failure/retry verification; final gates follow both user stories. A read-only audit therefore reports `17/17 complete`, `READY FRONTIER = empty`, and `STATUS = COMPLETE (LEGACY_TASK_FORMAT)`, without changing Feature 002 or making it a new task source.

## Verification and boundaries

Use `.agent-sdlc/project/quality-gates.md` for project commands and `.agent-sdlc/project/protected-paths.md` for protected paths. This repository's workflow refactor does not modify `src/`, `tests/`, Cargo dependencies, closed Feature product semantics, or `.claude/worktrees/`; it does not install software or create Feature 003.
