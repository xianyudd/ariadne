# OpenCode command: `/dev-next`

Collect `$ARGUMENTS`, then execute `.agents/skills/dev-next/SKILL.md`.

Run this first, as that adapter requires:

```bash
ariadne dev next [--dry-run]
```

A non-zero exit is the final report: emit it and stop. Do not restate the decision
rules here, and do not copy the workflow into this command.
