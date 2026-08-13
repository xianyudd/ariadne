# Managed lifecycle scenarios

These fixtures exercise the classification/status contract without invoking Git or a host. The execution decision is defined by `.agent-sdlc/core/terminal-contract.md`.

```text
Case A: PRODUCT_FEATURE + IN_PROGRESS → TERMINAL_BLOCKED → BLOCKED → STOP
Case B: PRODUCT_FEATURE + READY_TO_CLOSE + valid closure evidence → DECISION CONTINUE → STATUS READY → NORMAL_FLOW
Case C: NON_PRODUCT + positive workflow/infrastructure evidence → TERMINAL_NOT_APPLICABLE → NOT_APPLICABLE → STOP
Case D: UNKNOWN + insufficient or mixed evidence → TERMINAL_BLOCKED → BLOCKED → STOP
```

The explicit terminal fixtures are `terminal-product-in-progress.md`, `terminal-product-ready.md`, `terminal-non-product.md`, and `terminal-unknown.md`. The actual `agent-sdlc-v2` branch is Case C: its changed paths are workflow/infrastructure paths, it has no corresponding Product Feature registration or `specs/agent-sdlc-v2/`, and no Product Feature lifecycle state. The validator must never create metadata to change that result.
