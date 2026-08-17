# Human Gates

Stop and ask the user when:

- spec, plan, tasks, contract, or closure evidence has a substantive conflict;
- an architecture boundary, dependency, tool, plugin, MCP, or installation is needed;
- an operation could overwrite data or requires destructive Git/worktree behavior;
- scope would expand or a new Feature would be invented;
- merge conflicts or target drift occur;
- a host cannot provide the required independent review;
- context state is unsafe or unknown at a safety checkpoint;
- three review/fix cycles fail to converge.

A Human Gate is a stop condition, not permission to silently choose a risky default. Report the exact decision, evidence, and safe options. Running the next `dev-next` after a successful preparation checkpoint is the defined implementation approval and does not require an extra confirmation question.
