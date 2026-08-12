# tflow Quality Gates

Run from the repository root before every implementation or fix commit and at final acceptance:

```text
cargo test
cargo check
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
git diff --check
```

A failed gate is diagnosed and fixed within the selected scope. Never conceal a failure or claim a pass from an old snapshot.
