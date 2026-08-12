# Workflow: dev-merge

Load `core/lifecycle.md`, `core/lifecycle-entity.md`, `core/state-contract.md`, `core/human-gates.md`, `core/git-policy.md`, `core/context-policy.md`, and all project policies.

## CLASSIFY

Before Product Feature closure checks, classify the current repository entity using the evidence rules in `core/lifecycle-entity.md`:

```text
PRODUCT_FEATURE | NON_PRODUCT | UNKNOWN
```

- `PRODUCT_FEATURE`: continue with the normal workflow.
- `NON_PRODUCT`: report `STATUS = NOT_APPLICABLE` and stop immediately. Do not check `READY_TO_CLOSE`, closure record, or closure checkpoint.
- `UNKNOWN`: report `STATUS = BLOCKED` with `Unable to establish that current branch is a managed Product Feature.` Stop without creating metadata.

For `NON_PRODUCT`, the report should identify the positive workflow/infrastructure evidence and state:

```text
Type        WORKFLOW / INFRASTRUCTURE
状态        NOT_APPLICABLE
/dev-merge 不适用于当前 branch
```

It must not suggest creating closure evidence. The ordinary repository merge policy remains outside the Product Feature lifecycle.

Classification must not rely only on `branch != main` or branch-name heuristics. The same repository state and Core rules produce the same classification on every host.

## Product Feature workflow

For `PRODUCT_FEATURE` only:

### Preconditions

- current Feature is `READY_TO_CLOSE`;
- every task is complete;
- every review finding is resolved;
- final project quality gates and feature smoke pass;
- source and target branches are identified;
- tracked working tree is safe, with protected paths exempted and reported;
- closure checkpoint is fresh enough to detect target drift.

### Execution

```text
CLASSIFY → PREFLIGHT → RESTORE → CLOSURE RECORD → CLOSURE CHECKPOINT
→ MERGE → POST-MERGE VERIFY → STATE UPDATE → REPORT → STOP
```

Default target is `main`. Use the repository's verified merge policy: `git merge --no-ff <feature-branch>`. Merge conflicts, target drift, data-loss risk, or unexplained changes are Human Gates. After merge, run post-merge project verification and record `CLOSED` only after it passes.

Never squash, rebase, amend, push, delete a feature branch, delete a tag, create a release, clean/prune/delete/enter worktrees, or start a new Feature automatically.

`--dry-run` validates classification, all Product Feature preconditions, ancestry, and conflict/readiness information without checkout, merge, commit, cleanup, or state mutation.
