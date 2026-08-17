---
name: dev-next
description: Execute one dependency-coherent batch through verification, independent review, handoff, and stop.
user-invocable: true
---

# Portable adapter: `/dev-next`

## Runtime gate

Run this before loading the workflow or reading any repository evidence:

```bash
ariadne dev next [--dry-run]
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
- `ariadne doc state-contract`
- `ariadne doc task-dag`
- `ariadne doc batch-policy`
- `ariadne doc review-contract`
- `ariadne doc human-gates`
- `ariadne doc git-policy`
- `ariadne doc context-policy`

Then load your repository's own policies. Ariadne does not supply them and does
not read them: quality gates, protected paths, and architecture rules are the
consumer's, and this list is what an installer fills in.

<!-- ariadne:project-policies -->
- (your repository's own policy documents, one per line)
<!-- /ariadne:project-policies -->

Use an independent reviewer only after the implementation commit. If independent reviewer capability is unavailable, report `REVIEW CAPABILITY BLOCKED` rather than substituting a self-review.

Preserve `$ARGUMENTS` exactly as supplied.
