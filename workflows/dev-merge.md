# Workflow: dev-merge

Load `core/lifecycle.md`, `core/state-contract.md`, `core/human-gates.md`, `core/git-policy.md`, `core/context-policy.md`, and all project policies.

## Preconditions

- current Feature is `READY_TO_CLOSE`;
- every task is complete;
- every review finding is resolved;
- final project quality gates and feature smoke pass;
- source and target branches are identified;
- tracked working tree is safe, with protected paths exempted and reported;
- closure checkpoint is fresh enough to detect target drift.

## Execution

```text
PREFLIGHT → RESTORE → CLOSURE RECORD → CLOSURE CHECKPOINT
→ MERGE → POST-MERGE VERIFY → STATE UPDATE → REPORT → STOP
```

Default target is `main`. Use the repository's verified merge policy: `git merge --no-ff <feature-branch>`. Merge conflicts, target drift, data-loss risk, or unexplained changes are Human Gates. After merge, run post-merge project verification and record `CLOSED` only after it passes.

Never squash, rebase, amend, push, delete a feature branch, delete a tag, create a release, clean/prune/delete/enter worktrees, or start a new Feature automatically.

`--dry-run` validates all preconditions, ancestry, and conflict/readiness information without checkout, merge, commit, cleanup, or state mutation. On a non-ready Feature it must refuse with the concrete missing condition.
