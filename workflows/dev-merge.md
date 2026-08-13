# Workflow: dev-merge

Load `core/lifecycle.md`, `core/lifecycle-entity.md`, `core/terminal-contract.md`, `core/state-contract.md`, `core/human-gates.md`, `core/git-policy.md`, `core/context-policy.md`, and all project policies.

## CLASSIFY → DECIDE

Before any Product Feature closure check, classify the current repository entity using the evidence rules in `core/lifecycle-entity.md`, then apply the terminal decision contract in `core/terminal-contract.md`:

```text
PRODUCT_FEATURE + READY_TO_CLOSE → DECISION CONTINUE
PRODUCT_FEATURE + IN_PROGRESS     → DECISION TERMINAL_BLOCKED
NON_PRODUCT                      → DECISION TERMINAL_NOT_APPLICABLE
UNKNOWN                          → DECISION TERMINAL_BLOCKED
```

- `PRODUCT_FEATURE`: if the current lifecycle state is `READY_TO_CLOSE`, emit `DECISION CONTINUE`, then enter the normal Product Feature workflow. If the state is `IN_PROGRESS` or otherwise not `READY_TO_CLOSE`, emit `DECISION TERMINAL_BLOCKED`, report `STATUS = BLOCKED`, and stop immediately.
- `NON_PRODUCT`: report `STATUS = NOT_APPLICABLE`; emit `DECISION TERMINAL_NOT_APPLICABLE` and stop immediately.
- `UNKNOWN`: emit `DECISION TERMINAL_BLOCKED`, report `STATUS = BLOCKED` with `Unable to establish that current branch is a managed Product Feature.`, and stop immediately.

For `NON_PRODUCT`, the report should identify the positive workflow/infrastructure evidence and state:

```text
Type        WORKFLOW / INFRASTRUCTURE
状态        NOT_APPLICABLE
/dev-merge 不适用于当前 branch
```

A `TERMINAL_*` decision is final for this invocation. The terminal branches MUST NOT enter `PREFLIGHT`, `RESTORE`, closure-record or closure-checkpoint lookup, Feature or alternate-path searches, quality evidence scans, reviewer work, Git merge preparation, or any other later phase. They MUST emit the result once and STOP without reading additional evidence to confirm it.

Classification must not rely only on `branch != main` or branch-name heuristics. The same repository state and Core rules produce the same classification on every host.

## Product Feature workflow

Only `DECISION CONTINUE` may enter the Product Feature workflow:

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
CLASSIFY → DECIDE CONTINUE → PREFLIGHT → RESTORE → CLOSURE RECORD
→ CLOSURE CHECKPOINT → MERGE → POST-MERGE VERIFY → STATE UPDATE
→ REPORT → STOP
```

Default target is `main`. Use the repository's verified merge policy: `git merge --no-ff <feature-branch>`. Merge conflicts, target drift, data-loss risk, or unexplained changes are Human Gates. After merge, run post-merge project verification and record `CLOSED` only after it passes.

Never squash, rebase, amend, push, delete a feature branch, delete a tag, create a release, clean/prune/delete/enter worktrees, or start a new Feature automatically.

`--dry-run` validates classification and, only after `DECISION CONTINUE`, all Product Feature preconditions, ancestry, and conflict/readiness information without checkout, merge, commit, cleanup, or state mutation.
