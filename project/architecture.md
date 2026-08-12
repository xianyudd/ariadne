# tflow Architecture Policy

This project targets Rust 2024 and prefers the smallest design that satisfies the requirement. Do not add an async runtime, event bus, repository/service layer, database, or dependency without an approved Human Gate.

- `model.rs` owns task invariants and `TaskId`.
- `storage.rs` / `JsonStore` owns filesystem persistence mechanics.
- `app.rs` owns state transitions and selection identity; selection is `TaskId`, never a row index.
- `terminal.rs` normalizes terminal events and owns lifecycle cleanup; it does not interpret business shortcuts.
- `main.rs` owns runtime dispatch and continuous production event processing; test processing is bounded by an explicit budget.
- `ui.rs` reads `AppState` and has no persistence side effects.

Persistent mutations use candidate-save-then-commit: build and validate a candidate document and candidate selection, save it, then adopt it only after the save outcome. A pre-commit failure must not mutate live state or selection. `CommittedWithWarning` means the candidate was committed and must be adopted while preserving the warning. The successful target-file rename is the persistence commit point.
