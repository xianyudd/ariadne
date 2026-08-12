# Workflow: dev-new

Load `core/lifecycle.md`, `core/lifecycle-entity.md`, `core/state-contract.md`, `core/task-dag.md`, `core/human-gates.md`, `core/git-policy.md`, `core/context-policy.md`, `project/protected-paths.md`, and the repository Spec Kit policy.

This workflow prepares exactly one Feature and does not implement product code.

## Bounded dry-run

When `--dry-run` is present, execute only:

```text
PREFLIGHT → INTAKE → CLASSIFY → PREDICT SCOPE → REPORT → STOP
```

Read only the minimum facts needed to decide whether preparation could start: current branch and HEAD, tracked status, Feature registration and artifacts, active lifecycle state, the supplied requirement, and these Core/project policies. Classification uses the evidence rules in `core/lifecycle-entity.md`; it must occur before any readiness claim.

For `dev-new --dry-run`, the canonical decision mapping is:

```text
PRODUCT_FEATURE with an allowed base lifecycle state → READY
NON_PRODUCT                                      → BLOCKED
UNKNOWN                                          → BLOCKED
```

On `NON_PRODUCT` or `UNKNOWN`, report the blocking reason and stop. In particular, a workflow/infrastructure branch such as `agent-sdlc-v2` cannot start a Product Feature from its current lifecycle state. Do not reuse `/dev-merge`'s `NON_PRODUCT → NOT_APPLICABLE` mapping for this entrypoint.

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
