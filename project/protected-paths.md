# Protected Paths and Scope

## Protected

`.claude/worktrees/` is an active registered/locked worktree path. It is:

```text
protected · untouched · not implementation source · not stage
not commit · not clean · not prune · not delete · not enter
```

Generic clean checks must explicitly exempt and report this path. Never inspect its contents as product source.

## Workflow v2 boundary

This architecture refactor may change workflow documentation, adapters, Core policy, project policy, task-template guidance, and validation fixtures only. It must not modify `src/`, `tests/`, `Cargo.toml`, `Cargo.lock`, closed Feature product semantics, or dependencies. Do not install software, create Feature 003, or enable parallel writers.
