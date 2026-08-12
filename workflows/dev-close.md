# Workflow: dev-close

Load `core/lifecycle.md`, `core/state-contract.md`, `core/task-dag.md`, `core/review-contract.md`, `core/human-gates.md`, `core/git-policy.md`, `core/context-policy.md`, and all project policies.

```text
PREFLIGHT → RESTORE → FINAL VERIFY → FINAL SMOKE → SCOPE AUDIT
→ REVIEW AUDIT → READY_TO_CLOSE → HUMAN GATE → STOP
```

Confirm every task is complete from `tasks.md`, final project gates and feature smoke evidence pass, scope matches the Feature artifacts, and every completed batch has resolved review findings. Reconcile handoff metadata against actual Git/source/tasks. Report metadata-incomplete separately from product staleness.

Stop at `READY TO CLOSE`. Do not merge, create a task or Feature, tag/release, delete a branch, or process protected worktrees.

`--dry-run` only plans final verification, scope audit, and review audit; it does not run product tests or mutate files.
