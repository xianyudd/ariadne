# Agent SDLC v2

Agent SDLC is the repository workflow protocol for turning one approved Feature into a reviewed, closable, and mergeable change. The durable protocol is here; a host adapter only exposes an invocation, loads these files, and maps host-native capabilities.

## Architecture

```text
.agent-sdlc/       Agent-independent Core + tflow project policy
.agents/           portable skill adapter (Codex/OpenCode-compatible)
.claude/           Claude Code invocation and reviewer adapter
.codex/            Codex reviewer adapter
.opencode/         OpenCode command and reviewer adapters
```

Core must not depend on a host tool name, model name, provider, context-window number, or invocation syntax. Project policy supplies Rust/tflow facts. The same workflow decision must result from the same repository state on every host.

### Core vs adapter

Core owns lifecycle, state precedence, task DAG validation, ready-frontier calculation, batch policy, review contract, Human Gates, Git policy, and context/session boundaries. Project policy owns quality gates, module ownership, persistence semantics, and protected paths. Adapters own only command exposure, portable loading instructions, host permissions, and reviewer delegation.

To add another host, add a thin adapter that loads the existing `.agent-sdlc/workflows/` and required policy files. Do not copy the workflow into the adapter.

## Managed lifecycle entity

`/dev-merge` is not a generic Git merge command. It first classifies the current repository entity using `.agent-sdlc/core/lifecycle-entity.md`:

```text
PRODUCT_FEATURE | NON_PRODUCT | UNKNOWN
```

```text
PRODUCT_FEATURE + READY_TO_CLOSE gates → READY
PRODUCT_FEATURE + missing gates         → BLOCKED
NON_PRODUCT                             → NOT_APPLICABLE
UNKNOWN                                 → BLOCKED
```

A workflow/infrastructure branch such as `agent-sdlc-v2` is `NON_PRODUCT` only when positive repository evidence supports that classification. A random branch with insufficient evidence remains `UNKNOWN`; absence of a Feature registration alone is not enough.


- `/dev-new`: intake → Spec Kit artifacts → DAG validation → preparation checkpoint → Human Gate; no product code.
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
