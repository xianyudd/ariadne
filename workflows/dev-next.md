# Workflow: dev-next

Load `core/lifecycle.md`, `core/state-contract.md`, `core/task-dag.md`, `core/batch-policy.md`, `core/review-contract.md`, `core/human-gates.md`, `core/git-policy.md`, `core/context-policy.md`, and `project/quality-gates.md`, `project/architecture.md`, `project/protected-paths.md`.

Preserve this exact bounded execution:

```text
PREFLIGHT → RESTORE → SELECT → RECONCILE → IMPLEMENT → VERIFY
→ COMMIT → REVIEW → FIX / RE-VERIFY / RE-REVIEW → HANDOFF → STOP
```

PREFLIGHT confirms reviewer capability before implementation and safe protected-path status. RESTORE uses the source-of-truth order. SELECT parses `tasks.md`, validates the DAG, computes the ready frontier, removes blocked tasks, and applies Batch Policy. RECONCILE compares selected tasks with actual source/tests; never invents scope.

IMPLEMENT follows project architecture and candidate-save-then-commit rules. VERIFY runs project gates. COMMIT precedes review. REVIEW uses an independent host-native reviewer; each real finding gets a separate fix commit and complete re-verification. After PASS, update the durable handoff and stop. Never start the next batch automatically.

`--dry-run` is `PREFLIGHT → RESTORE → SELECT → RECONCILE → REPORT → STOP`; it does not invoke reviewers, tests/builds, task edits, commits, or product implementation. If context is unsafe, report `SESSION_BOUNDARY_REQUIRED` with the actual unfinished state.
