---
name: dev-merge
description: Merge a Feature that Ariadne has cleared for merge, using the repository merge policy, and verify the result.
argument-hint: "[--dry-run] [target branch]"
user-invocable: true
disable-model-invocation: true
---

# Claude adapter: `/dev-merge`

## Runtime gate

Run this before loading the workflow or reading any repository evidence:

```bash
ariadne dev merge --human-gate APPROVED|NOT_APPROVED|UNKNOWN [--dry-run]
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
- `ariadne doc human-gates`
- `ariadne doc git-policy`
- `ariadne doc context-policy`

Then load your repository's own policies. Ariadne does not supply them and does
not read them: quality gates, protected paths, and architecture rules are the
consumer's, and this list is what an installer fills in.

<!-- ariadne:project-policies -->
- (your repository's own policy documents, one per line)
<!-- /ariadne:project-policies -->

Establishing the Human Gate state is this adapter's only judgement. Pass `--human-gate APPROVED` only with the user's explicit authorization for this merge, and `UNKNOWN` when unsure. Anything but `APPROVED` fails closed where a gate is required, and a `--dry-run` mutates nothing so it needs no authorization.

Never delete feature branches, tags, releases, or worktrees.
