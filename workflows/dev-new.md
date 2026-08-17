# Workflow: dev-new

Load `core/lifecycle.md`, `core/lifecycle-entity.md`, `core/state-contract.md`, `core/task-dag.md`, `core/human-gates.md`, `core/git-policy.md`, `core/context-policy.md`, `project/protected-paths.md`, and the repository Spec Kit policy.

This workflow prepares exactly one Feature and does not implement product code.

## Decision table

The runtime decides before any phase runs. For a proven `PRODUCT_FEATURE` with a
clean tracked working tree:

Task graph: complete

```text
NEW                      → CONTINUE
READY_FOR_IMPLEMENTATION → TERMINAL_BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED
IN_PROGRESS              → TERMINAL_BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED
READY_TO_CLOSE           → TERMINAL_BLOCKED:LIFECYCLE_BASE_STATE_NOT_ALLOWED
CLOSED                   → CONTINUE
```

A new Feature may start only from `NEW` — nothing prepared yet — or from `CLOSED`,
where the previous Feature is finished and merged. Every state in between means a
Feature is already in flight.

`NON_PRODUCT` and `UNKNOWN` are both `TERMINAL_BLOCKED`, with
`ENTITY_NOT_PRODUCT_FEATURE` and `ENTITY_UNKNOWN` respectively. This entry point
does not reuse `/dev-merge`'s `NON_PRODUCT → TERMINAL_NOT_APPLICABLE` mapping:
attempting to start a Product Feature from a workflow branch is an error, not a
no-op. `LIFECYCLE_UNKNOWN` blocks, and a dirty tracked working tree blocks unless
`--dry-run` is present. Reason codes are defined in `../runtime/README.md`.

## Bounded dry-run

When `--dry-run` is present, execute only:

```text
PREFLIGHT → INTAKE → CLASSIFY → PREDICT SCOPE → REPORT → STOP
```

Read only the minimum facts needed to decide whether preparation could start: current branch and HEAD, tracked status, Feature registration and artifacts, active lifecycle state, the supplied requirement, and these Core/project policies. Classification uses the evidence rules in `core/lifecycle-entity.md`; it must occur before any readiness claim.

A dry-run reaches its decision at `CLASSIFY`, from the same decision table above —
the table is not restated here, because there is one table. `CONTINUE` reports
`READY` and proceeds to `PREDICT SCOPE`; a terminal decision reports its own status
and stops. The only difference from a normal run is that a dry-run mutates nothing,
so a dirty tracked working tree does not block it.

A dry-run must not invoke Spec Kit, clarify loops, plan/task generation, DAG file creation, analysis that writes artifacts, reviewers, tests, builds, commits, branch creation, handoff updates, configuration changes, or any worktree operation. It must not perform a full-repository exploration. Preserve the supplied requirement only as read-only intake context.

## Normal run

Without `--dry-run`, execute:

```text
PREFLIGHT → INTAKE → SPECIFY → CLARIFY → PLAN → TASKS
→ DAG VALIDATE → ANALYZE → PREPARATION CHECKPOINT → HUMAN GATE → STOP
```

PREFLIGHT confirms the repository lifecycle allows a new Feature, no unexplained changes exist outside protected paths, and the current Feature is CLOSED/merged. INTAKE is limited to the user's requirements. Use the existing Spec Kit specify/clarify/plan/tasks commands; do not create a parallel specification system.

DAG VALIDATE confirms metadata, dependencies, cycles, frontier, acceptance reachability, and legacy-format status. ANALYZE confirms spec/plan/tasks/constitution consistency and acceptance coverage.

The preparation checkpoint records only Feature specification artifacts. It does not mean implementation is approved. Report `READY FOR IMPLEMENTATION`; the user's next explicit `dev-next` invocation is the approval. Stop. Never merge, create another Feature, create product code, tag/release, delete branches, or clean worktrees.
