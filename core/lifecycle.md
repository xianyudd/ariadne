# Agent SDLC Lifecycle

This is the host-independent lifecycle contract. Hosts expose commands; they do not redefine these decisions.

## State machine

```text
NEW → READY_FOR_IMPLEMENTATION → IN_PROGRESS → READY_TO_CLOSE → CLOSED
```

- `NEW`: no prepared Feature artifacts.
- `READY_FOR_IMPLEMENTATION`: specification artifacts and a valid task graph passed the preparation checkpoint. Running `dev-next` is the user's approval to begin implementation.
- `IN_PROGRESS`: at least one selected batch is being implemented or has unresolved review work.
- `READY_TO_CLOSE`: all tasks are complete, final acceptance passed, and review findings are resolved. `dev-close` stops here.
- `CLOSED`: the closure record is committed, the Feature is merged according to project policy, and post-merge verification passed.

A handoff is evidence, not authority. Resolve conflicts using `.agent-sdlc/core/state-contract.md`.

## `dev-new`

```text
PREFLIGHT → INTAKE → SPECIFY → CLARIFY → PLAN → TASKS
→ DAG VALIDATE → ANALYZE → PREPARATION CHECKPOINT → HUMAN GATE → STOP
```

The preparation checkpoint commits only Feature specification artifacts. It never commits product code and does not approve implementation. The next explicit `dev-next` invocation is the implementation approval; do not ask for an additional confirmation.

## `dev-next`

```text
PREFLIGHT → RESTORE → SELECT → RECONCILE → IMPLEMENT → VERIFY
→ COMMIT → REVIEW → FIX / RE-VERIFY / RE-REVIEW → HANDOFF → STOP
```

Select exactly one dependency-coherent batch. Stop after its handoff; never start the next batch automatically. Review occurs only after an implementation commit. Every fix is independently verified, committed, and re-reviewed. If context is unsafe, stop with `SESSION_BOUNDARY_REQUIRED` and report the real unfinished state.

## `dev-close`

```text
PREFLIGHT → RESTORE → FINAL VERIFY → FINAL SMOKE → SCOPE AUDIT
→ REVIEW AUDIT → READY_TO_CLOSE → HUMAN GATE → STOP
```

`dev-close` never merges, deletes a branch, cleans a worktree, creates a tag/release, or creates a new Feature.

## `dev-merge`

```text
PREFLIGHT → RESTORE → CLOSURE RECORD → CLOSURE CHECKPOINT
→ MERGE → POST-MERGE VERIFY → STATE UPDATE → REPORT → STOP
```

The default target is `main`, subject to project policy. A merge conflict, unsafe working tree, changed target since checkpoint, data-loss risk, or missing closure evidence is a Human Gate. Do not delete branches, tags, releases, or worktrees; do not squash, rebase, or amend unless project policy explicitly says otherwise.

## Dry-run

Each entry supports a read-only dry-run that validates the relevant preconditions and reports the selected decision without running product implementation, tests that mutate state, commits, reviews, merges, or handoff changes.
