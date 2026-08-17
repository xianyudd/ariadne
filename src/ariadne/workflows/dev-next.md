# Workflow: dev-next

Load `ariadne doc lifecycle`, `ariadne doc state-contract`, `ariadne doc task-dag`, `ariadne doc batch-policy`, `ariadne doc review-contract`, `ariadne doc human-gates`, `ariadne doc git-policy`, `ariadne doc context-policy`, and the repository's own project policies: quality gates, architecture rules, and protected paths.

## Decision table

The runtime decides before any phase runs. For a proven `PRODUCT_FEATURE` with
resolved reviews and a clean tracked working tree:

Task graph: unfinished

```text
NEW                      → TERMINAL_BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED
READY_FOR_IMPLEMENTATION → CONTINUE
IN_PROGRESS              → CONTINUE
READY_TO_CLOSE           → TERMINAL_BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED
CLOSED                   → TERMINAL_NOT_APPLICABLE:FEATURE_ALREADY_CLOSED
```

Implementation happens at `READY_FOR_IMPLEMENTATION` or `IN_PROGRESS`. A complete
task graph is `TERMINAL_NOT_APPLICABLE:FEATURE_ALREADY_CLOSED` from any state:
there is no batch left to select, which is a successful guard rather than a
failure.

`NON_PRODUCT` is `TERMINAL_NOT_APPLICABLE:ENTITY_NOT_PRODUCT_FEATURE` and `UNKNOWN`
is `TERMINAL_BLOCKED:ENTITY_UNKNOWN`. An invalid graph blocks with `DAG_INVALID`, a
valid graph whose every unfinished task is blocked with `NO_READY_FRONTIER`,
outstanding review findings with `REVIEW_UNRESOLVED`, and a dirty tracked working
tree with `WORKING_TREE_UNSAFE` unless `--dry-run` is present. Reason codes are
defined in `ariadne doc reason-codes`.

## Execution

Preserve this exact bounded execution:

```text
PREFLIGHT → RESTORE → SELECT → RECONCILE → IMPLEMENT → VERIFY
→ COMMIT → REVIEW → FIX / RE-VERIFY / RE-REVIEW → HANDOFF → STOP
```

PREFLIGHT confirms reviewer capability before implementation and safe protected-path status. RESTORE uses the source-of-truth order. SELECT parses the repository's tasks file, validates the DAG, computes the ready frontier, removes blocked tasks, and applies Batch Policy. RECONCILE compares selected tasks with actual source/tests; never invents scope.

IMPLEMENT follows project architecture and candidate-save-then-commit rules. VERIFY runs project gates. COMMIT precedes review. REVIEW uses an independent host-native reviewer; each real finding gets a separate fix commit and complete re-verification. After PASS, update the durable handoff and stop. Never start the next batch automatically.

`--dry-run` is `PREFLIGHT → RESTORE → SELECT → RECONCILE → REPORT → STOP`; it does not invoke reviewers, tests/builds, task edits, commits, or product implementation. If context is unsafe, report `SESSION_BOUNDARY_REQUIRED` with the actual unfinished state.
