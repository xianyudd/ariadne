# OpenCode command: `/dev-merge`

Collect `$ARGUMENTS`, then execute `.agents/skills/dev-merge/SKILL.md`.

Run this first, as that adapter requires:

```bash
ariadne dev merge --human-gate APPROVED|NOT_APPROVED|UNKNOWN [--dry-run]
```

A non-zero exit is the final report: emit it and stop. Do not restate the decision
rules here, and do not copy the workflow into this command.
