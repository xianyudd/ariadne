# Context and Session Policy

```text
Repository = durable memory
Session    = disposable worker
```

A new session must restore from actual Git/source, tasks, spec/plan/contracts, and current-state. Chat summaries are lowest-priority evidence.

## Abstract state

```text
HEALTHY | PRESSURE | BOUNDARY_REQUIRED | UNKNOWN
```

Use host-provided context telemetry when it is reliable. If the effective context window cannot be measured, use `UNKNOWN`; never claim a precise limit or percentage, and never embed a provider/model name or token value in Core.

At `PRESSURE`, narrow reads to the current phase and selected batch. At `BOUNDARY_REQUIRED`, finish only a safe checkpoint if possible, record the real unfinished state, commit/handoff only when actually complete, and stop. On overflow, compaction failure, provider context error, or unreliable context:

```text
preserve repository state if safe
→ stop current execution
→ report SESSION_BOUNDARY_REQUIRED
```

Do not retry the same oversized request forever. Do not manufacture a completed handoff. If the batch has not reached a safe checkpoint, report its actual unfinished tasks and next recovery point.

`dev-next` always stops after resolved review and recorded handoff so the next session is independent of the old conversation.
