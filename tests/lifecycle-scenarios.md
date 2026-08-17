# Managed lifecycle scenarios

These scenarios exercise the classification/status contract for `/dev-merge` without invoking Git or a host. Each row is `classification [+ lifecycle] → decision → status → next legal action`; a row with no lifecycle is a claim about every lifecycle state. The decision itself is defined by `contracts/terminal-contract.md` and produced by `../runtime/decision_engine.py`; these rows are read and run against it by `test_decision_consistency.py`, so they cannot drift from it.

```text
Case A: PRODUCT_FEATURE + IN_PROGRESS    → TERMINAL_BLOCKED        → BLOCKED        → STOP
Case B: PRODUCT_FEATURE + READY_TO_CLOSE → CONTINUE                → READY          → NORMAL_FLOW
Case C: NON_PRODUCT                      → TERMINAL_NOT_APPLICABLE → NOT_APPLICABLE → STOP
Case D: UNKNOWN                          → TERMINAL_BLOCKED        → BLOCKED        → STOP
```

`NORMAL_FLOW` means the workflow's own next phase, whatever the envelope names it. Every other successor is `STOP`.

What makes each classification the right one is evidence, and `contracts/lifecycle-entity.md` owns those rules: Case B additionally requires valid closure evidence, Case C requires positive workflow/infrastructure evidence, and Case D is what insufficient or mixed evidence produces. Case B's `CONTINUE` also assumes the remaining gates are satisfied — a resolved review and an approved Human Gate — because a single row names only the fact it is about.

The explicit terminal fixtures are `terminal-product-in-progress.md`, `terminal-product-ready.md`, `terminal-non-product.md`, and `terminal-unknown.md`. The actual `agent-sdlc-v2` branch is Case C: its changed paths are workflow/infrastructure paths, it has no corresponding Product Feature registration or `specs/agent-sdlc-v2/`, and no Product Feature lifecycle state. The validator must never create metadata to change that result.
