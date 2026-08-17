# Core reason codes

Every terminal decision carries a reason code. These are the only codes the engine
emits; `runtime.decision_engine.REASON_CODES` is the enumerable form, and
`tests/test_decision_consistency.py` fails if this document and that set disagree in
either direction.

The `PROTOCOL_` prefix is reserved for the framework (`decision-envelope.md`), so no
workflow reason code uses it.

```text
GIT_STATE_UNAVAILABLE             Repository Git state could not be read. Blocks every workflow.
ENTITY_UNKNOWN                    Entity evidence is insufficient or mixed. Blocks every workflow.
ENTITY_NOT_PRODUCT_FEATURE        The branch is workflow/infrastructure, not a Product Feature.
LIFECYCLE_UNKNOWN                 Lifecycle evidence explains no declared position.
LIFECYCLE_NOT_READY_TO_CLOSE      /dev-merge requires READY_TO_CLOSE.
LIFECYCLE_BASE_STATE_NOT_ALLOWED  The workflow does not run from this lifecycle state.
TASKS_INCOMPLETE                  Final acceptance requires every task complete.
DAG_INVALID                       The task graph does not validate; no workflow proceeds on its authority.
NO_READY_FRONTIER                 Every unfinished task is blocked; no batch can be selected.
REVIEW_UNRESOLVED                 Recorded review findings are unresolved, or no resolved-review evidence exists.
WORKING_TREE_UNSAFE               The tracked working tree has changes outside protected paths.
MERGE_AUTHORIZATION_REQUIRED      A real merge needs an APPROVED Human Gate; NOT_APPROVED and UNKNOWN both fail closed.
FEATURE_ALREADY_CLOSED            There is no remaining work for this entry point. Reported NOT_APPLICABLE, not BLOCKED.
WORKFLOW_INTENT_UNSUPPORTED       The declared intent is not one of the four workflows.
PROTOCOL_DECISION_INVALID         Framework-reserved. A malformed, unknown, or wrong-version envelope, coerced to TERMINAL_BLOCKED.
```

`ENTITY_NOT_PRODUCT_FEATURE` and `FEATURE_ALREADY_CLOSED` are the two codes whose
decision depends on the entry point. `/dev-new` blocks on a non-Product-Feature
branch, because starting a Feature there is an error; the other three workflows
report `TERMINAL_NOT_APPLICABLE`, because there is simply nothing of theirs to do.
Each workflow's document states its own table.

A reason code explains a decision. It never becomes one: an agent that reads
`REVIEW_UNRESOLVED` has learned why the runtime stopped, not been granted a phase in
which to fix it.
