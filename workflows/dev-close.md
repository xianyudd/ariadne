# Workflow: dev-close

Load `core/lifecycle.md`, `core/state-contract.md`, `core/task-dag.md`, `core/review-contract.md`, `core/human-gates.md`, `core/git-policy.md`, `core/context-policy.md`, and all project policies.

## Decision table

The runtime decides before any phase runs. For a proven `PRODUCT_FEATURE` with
resolved reviews:

Task graph: complete

```text
NEW                      → TERMINAL_BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED
READY_FOR_IMPLEMENTATION → TERMINAL_BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED
IN_PROGRESS              → CONTINUE
READY_TO_CLOSE           → CONTINUE
CLOSED                   → TERMINAL_NOT_APPLICABLE:FEATURE_ALREADY_CLOSED
```

Final acceptance runs from `IN_PROGRESS`, and re-runs from `READY_TO_CLOSE`. An
incomplete task graph is `TERMINAL_BLOCKED:TASKS_INCOMPLETE` from any state; there
is nothing to accept until the work is done.

`NON_PRODUCT` is `TERMINAL_NOT_APPLICABLE:ENTITY_NOT_PRODUCT_FEATURE` and `UNKNOWN`
is `TERMINAL_BLOCKED:ENTITY_UNKNOWN`. An invalid graph blocks with `DAG_INVALID` and
outstanding review findings with `REVIEW_UNRESOLVED`. This workflow produces review
evidence rather than requiring it up front, so absent evidence does not block it.
Reason codes are defined in `../runtime/README.md`.

## Execution

```text
PREFLIGHT → RESTORE → FINAL VERIFY → FINAL SMOKE → SCOPE AUDIT
→ REVIEW AUDIT → READY_TO_CLOSE → HUMAN GATE → STOP
```

Confirm every task is complete from `tasks.md`, final project gates and feature smoke evidence pass, scope matches the Feature artifacts, and every completed batch has resolved review findings. Reconcile handoff metadata against actual Git/source/tasks. Report metadata-incomplete separately from product staleness.

Stop at `READY TO CLOSE`. Do not merge, create a task or Feature, tag/release, delete a branch, or process protected worktrees.

`--dry-run` only plans final verification, scope audit, and review audit; it does not run product tests or mutate files.
