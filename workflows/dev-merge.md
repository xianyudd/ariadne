# Workflow: dev-merge

Load `core/lifecycle.md`, `core/lifecycle-entity.md`, `core/terminal-contract.md`, `core/decision-envelope.md`, `core/state-contract.md`, `core/human-gates.md`, `core/git-policy.md`, `core/context-policy.md`, and all project policies.

## Decision table

The strictest path. The runtime decides before any phase runs. For a proven
`PRODUCT_FEATURE` with resolved reviews, a clean tracked working tree, and an
`APPROVED` Human Gate:

Task graph: complete

```text
NEW                      → TERMINAL_BLOCKED:LIFECYCLE_NOT_READY_TO_CLOSE
READY_FOR_IMPLEMENTATION → TERMINAL_BLOCKED:LIFECYCLE_NOT_READY_TO_CLOSE
IN_PROGRESS              → TERMINAL_BLOCKED:LIFECYCLE_NOT_READY_TO_CLOSE
READY_TO_CLOSE           → CONTINUE
CLOSED                   → TERMINAL_NOT_APPLICABLE:FEATURE_ALREADY_CLOSED
```

`READY_TO_CLOSE` is the only lifecycle state that merges. An incomplete task graph
is `TERMINAL_BLOCKED:TASKS_INCOMPLETE` and an invalid one `DAG_INVALID`, checked
here as well as during lifecycle derivation — in a real repository `READY_TO_CLOSE`
already implies a valid, complete graph, so neither rule changes a real outcome.
They exist so the strictest path does not depend on one derivation being correct.

A merge is an outward-facing mutation, so it requires positive resolved-review
evidence (`REVIEW_UNRESOLVED` otherwise), a clean tracked working tree
(`WORKING_TREE_UNSAFE`), and an explicitly `APPROVED` Human Gate
(`MERGE_AUTHORIZATION_REQUIRED`). `NOT_APPROVED` and `UNKNOWN` both fail closed.
`--dry-run` mutates nothing, so it needs neither a clean tree nor authorisation.
Reason codes are defined in `../runtime/README.md`.

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

Express the decision as a Decision Envelope (`core/decision-envelope.md`): `workflow` is this workflow's name, `phase` is `CLASSIFY`, `classification` is the entity above, `evidence` records the classification facts that were already read, and `next_legal_action` is `STOP` for every terminal branch. The envelope is the value the runtime terminal gate enforces. A host adapter reaches this workflow through `.agent-sdlc/runtime/`, so a `TERMINAL_*` envelope produces one final report and no host dispatch: a later phase is unreachable rather than merely forbidden.

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
