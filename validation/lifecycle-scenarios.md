# Managed lifecycle scenarios

These fixtures exercise the classification/status contract without invoking Git or a host.

```text
Case A: PRODUCT_FEATURE + IN_PROGRESS → BLOCKED
Case B: PRODUCT_FEATURE + READY_TO_CLOSE + valid closure evidence → READY
Case C: NON_PRODUCT + positive workflow/infrastructure evidence → NOT_APPLICABLE
Case D: UNKNOWN + insufficient or mixed evidence → BLOCKED
```

The actual `agent-sdlc-v2` branch is Case C: its changed paths are workflow/infrastructure paths, it has no corresponding Product Feature registration or `specs/agent-sdlc-v2/`, and no Product Feature lifecycle state. The validator must never create metadata to change that result.
