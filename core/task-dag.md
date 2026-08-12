# Task DAG

`tasks.md` remains the only task source of truth. Do not create or maintain a parallel `tasks.json`.

## Task metadata

New task files should retain the existing checkbox and story labels and add compact metadata near each task:

```text
- [ ] T007 [US1] Implement the edit path in src/app.rs
  Depends: T003, T004
  Story: US1
  Area: app,persistence
  Risk: normal
```

`Depends:` is the only scheduling field. `Story`, `Area`, and `Risk` guide batch policy and review. Optional `Acceptance: yes` marks an acceptance implementation node and optional `Terminal: yes` marks a required leaf/checkpoint node; when either marker is used, the validator checks reachability from a dependency root and rejects a terminal node that has dependents. These markers are not required for legacy files. Empty dependencies mean an initial node. Historical task files without this metadata are `LEGACY_TASK_FORMAT`; do not rewrite them during compatibility migration.

## Validation

Reject the graph when:

- a task ID is duplicated or malformed;
- a dependency is unknown;
- a task depends on itself;
- a cycle exists;
- an unfinished graph has no initial ready node;
- a completed task has an incomplete dependency, unless the file is explicitly accepted as a historical legacy snapshot;
- acceptance work is unreachable from all initial nodes;
- a terminal task is impossible because its dependency chain cannot complete.

Use actionable diagnostics, for example:

```text
DAG INVALID
cycle: T004 → T006 → T004
```

## Ready frontier

```text
READY(task) = unfinished(task)
  AND every declared dependency is completed
```

Blocked tasks are unfinished tasks with at least one incomplete dependency. Sort a valid frontier deterministically by phase/checkpoint, story priority, then numeric Task ID. If all tasks are complete, report `COMPLETE`, not an empty unexplained frontier.

## Compatibility mode

For legacy `tasks.md`, parse checkbox state and use explicit dependency prose only when it can be proven. Report missing per-task metadata. Never treat every unchecked task as ready. An unprovable legacy frontier requires a Human Gate before implementation.

## Scope

DAG validation and frontier calculation do not run product code, do not edit task checkboxes, and do not select parallel writers. Future parallel execution is documentation-only.
