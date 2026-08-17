# Batch Policy

The DAG decides whether a task is executable; this policy decides which ready tasks form one safe batch.

Select the first deterministic ready task, then expand only when the candidate remains a coherent execution slice:

1. same explicit checkpoint or User Story;
2. same acceptance path and substantially related area;
3. dependency-complete, with no skipped prerequisite;
4. natural shared verification;
5. no unreviewed architecture or persistence boundary crossed.

Usually prefer 2–5 tasks, but this is a heuristic. Do not split a natural unit to hit the number or merge unrelated tasks to fill it. Shrink a batch when persistence risk, scope uncertainty, or conflicting files makes review less local.

A user-supplied range is valid only if every dependency is already complete or included in the range and the range does not cross a checkpoint without evidence. Record selected, blocked, and deferred tasks.

One selected batch uses one implementation path. Do not automatically launch parallel writers; `[P]` is planning metadata, not permission to bypass the batch FSM.
