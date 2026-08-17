# OpenCode command: `/dev-close`

Collect `$ARGUMENTS`, then execute `.agents/skills/dev-close/SKILL.md`.

Run this first, as that adapter requires:

```bash
ariadne dev close [--dry-run]
```

A non-zero exit is the final report: emit it and stop. Do not restate the decision
rules here, and do not copy the workflow into this command.
