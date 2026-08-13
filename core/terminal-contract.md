# Terminal Decision Contract

This is the host-independent short-circuit contract for workflow decisions. Adapters expose workflows; they do not redefine these decisions.

## Decision values

```text
CONTINUE
TERMINAL_SUCCESS
TERMINAL_BLOCKED
TERMINAL_NOT_APPLICABLE
```

`CONTINUE` means the current decision permits the next declared workflow phase. A `TERMINAL_*` value means the current invocation has reached its final decision. Terminal decisions are distinct from lifecycle entity classification and from the final reported status.

## Invariant

Once a workflow produces any `TERMINAL_*` decision:

1. The current invocation decision is final.
2. The workflow MUST emit the result exactly once.
3. The workflow MUST NOT enter a later phase.
4. The workflow MUST NOT read additional evidence to "confirm" the same decision.
5. The workflow MUST NOT search other Features, paths, closure records, or alternate evidence.
6. The workflow MUST STOP immediately.

Only `CONTINUE` permits transition to the next declared phase. A terminal decision has no legal successor phase.

## `/dev-merge` mapping

Classification and the minimum lifecycle gate decision are performed before Product Feature closure phases:

```text
PRODUCT_FEATURE + READY_TO_CLOSE → CONTINUE
PRODUCT_FEATURE + IN_PROGRESS     → TERMINAL_BLOCKED
NON_PRODUCT                      → TERMINAL_NOT_APPLICABLE
UNKNOWN                          → TERMINAL_BLOCKED
```

Only `CONTINUE` enters the normal Product Feature merge workflow. A Product Feature that is not yet `READY_TO_CLOSE` reports `STATUS = BLOCKED` and stops; it does not enter merge preparation.

For terminal branches:

```text
TERMINAL_NOT_APPLICABLE → status NOT_APPLICABLE
TERMINAL_BLOCKED        → status BLOCKED
```

`TERMINAL_SUCCESS` is reserved for a workflow that has completed its own successful final operation. It is not used to turn Product Feature classification into a merge result; Product Feature classification remains `CONTINUE` until the normal merge workflow reaches its final report.
