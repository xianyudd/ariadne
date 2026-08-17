---
name: dev-new
description: Prepare one Feature through the Ariadne contract; stop before product implementation.
user-invocable: true
---

# Portable adapter: `/dev-new`

## Runtime gate

Run this before loading the workflow or reading any repository evidence:

```bash
ariadne dev new [--dry-run]
```

The command is the decision, not an advisory check: it collects repository
evidence, resolves state, decides what the protocol permits, and enforces the
result.

- Non-zero exit: the command has already printed the one final report. That report
  is the answer — emit it and stop. Do not load the workflow, read further
  evidence, retry with different arguments, or reinterpret the outcome.
- Exit `0`: the command prints the single phase that is granted, and the path to
  that phase's workflow document. Enter that phase and no other.

This adapter holds no decision semantics. Classification, lifecycle, task graph,
safety, and terminality belong to Ariadne, so the same repository state and intent
produce the same result on every host.

## Documents

Ariadne ships the contracts it enforces. Load them from the install rather
than from a vendored copy:

- `ariadne doc lifecycle`
- `ariadne doc lifecycle-entity`
- `ariadne doc state-contract`
- `ariadne doc task-dag`
- `ariadne doc human-gates`
- `ariadne doc git-policy`
- `ariadne doc context-policy`

Under `--dry-run`, load only:

- `ariadne doc lifecycle-entity`
- `ariadne doc state-contract`

Then load your repository's own policies. Ariadne does not supply them and does
not read them: quality gates, protected paths, and architecture rules are the
consumer's, and this list is what an installer fills in.

<!-- ariadne:project-policies -->
- (your repository's own policy documents, one per line)
<!-- /ariadne:project-policies -->

Parse the invocation arguments before entering any workflow phase. Preserve the requirement text exactly as supplied.

With `--dry-run`, the workflow's bounded read-only path is the whole of it: no planning provider, reviewer, test, build, Git mutation, or worktree operation, no clarification questions, and no full-repository scan.

Preserve `$ARGUMENTS` exactly as supplied.
