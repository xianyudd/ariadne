# Review Contract

## Independent Reviewer

**Input**

- selected batch and acceptance criteria;
- implementation and any fix commits;
- actual diff, source, tests, and verification evidence;
- applicable project policy.

**Output**

```text
PASS
```

or:

```text
NEEDS_FIX
BLOCKER: N
MAJOR: N
MINOR: N
Findings: evidence-based, actionable items
```

Severity is `BLOCKER`, `MAJOR`, or `MINOR`. Findings require a concrete state/input, wrong result or risk, repository location, violated contract, smallest fix, and verification needed.

The reviewer considers correctness, regression, acceptance coverage, persistence/data semantics, missing tests, architecture boundaries, release/debug seam leakage, and scope creep. It does not report style-only preferences.

## Boundaries

The reviewer is read-only: no product edits, task edits, commits, branch/worktree operations, dependency installation, or scope expansion. It builds a checklist from the selected batch rather than using an unrelated fixed checklist.

The host requests an independent reviewer using its native mechanism. If the host cannot provide independent review, report `REVIEW CAPABILITY BLOCKED`; never claim independence. A PASS requires zero unresolved findings.
