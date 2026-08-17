# State Contract

## Durable truth

```text
actual Git and checked-out source
> the tasks file
> the Feature's specification artifacts
> the recorded state handoff
> chat or agent summary
```

`Repository = durable memory`; `Session = disposable worker`. A session must be restartable from repository state alone.

A handoff is `stale` only when product/task facts conflict with source, tests, Git, or task artifacts. A workflow/docs-only commit omitted from a handoff is `metadata-incomplete`, not product staleness.

## Batch FSM

The task DAG answers only what can be executed next. The batch FSM owns:

```text
SELECT → RECONCILE → IMPLEMENT → VERIFY → COMMIT
→ REVIEW → FIX / RE-VERIFY / RE-REVIEW → HANDOFF → STOP
```

The DAG does not manage review, fixes, commits, handoffs, or lifecycle state.

## Required records

A batch packet records the selected task IDs, dependency evidence, declared scope, acceptance evidence, implementation commit, verification results, review verdict/findings, fix commits, and handoff result. A closure record records the final task state, final gates, smoke evidence, review audit, source branch, target branch, and merge result.

Never mark a task complete from a title or summary alone. Require implementation and verification evidence at the appropriate boundary.
