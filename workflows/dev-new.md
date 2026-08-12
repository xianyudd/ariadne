# Workflow: dev-new

Load `core/lifecycle.md`, `core/state-contract.md`, `core/task-dag.md`, `core/human-gates.md`, `core/git-policy.md`, `core/context-policy.md`, `project/protected-paths.md`, and the repository Spec Kit policy.

This workflow prepares exactly one Feature and does not implement product code.

```text
PREFLIGHT → INTAKE → SPECIFY → CLARIFY → PLAN → TASKS
→ DAG VALIDATE → ANALYZE → PREPARATION CHECKPOINT → HUMAN GATE → STOP
```

PREFLIGHT confirms the repository lifecycle allows a new Feature, no unexplained changes exist outside protected paths, and the current Feature is CLOSED/merged. INTAKE is limited to the user's requirements. Use the existing Spec Kit specify/clarify/plan/tasks commands; do not create a parallel specification system.

DAG VALIDATE confirms metadata, dependencies, cycles, frontier, acceptance reachability, and legacy-format status. ANALYZE confirms spec/plan/tasks/constitution consistency and acceptance coverage.

The preparation checkpoint records only Feature specification artifacts. It does not mean implementation is approved. Report `READY FOR IMPLEMENTATION`; the user's next explicit `dev-next` invocation is the approval. Stop. Never merge, create another Feature, create product code, tag/release, delete branches, or clean worktrees.

`--dry-run` performs only read-only preflight/intake/readiness reporting and never invokes Spec Kit or changes Git state.
