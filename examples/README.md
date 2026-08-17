# Examples

Three consumer configurations, of three different projects, running one runtime.

| Example | Planning | Gates come from |
| --- | --- | --- |
| `generic/` | `directory` — no external tool | your own conventions |
| `rust/` | `speckit` | `cargo test`, `cargo clippy`, `cargo fmt` |
| `python/` | `directory` | `pytest`, `ruff` |

Read them side by side. They differ only in strings, and that is the claim being
made: nothing inside Ariadne branches on which one it is looking at.

```text
project configuration → quality gate provider → structured evidence → Ariadne runtime
```

Ariadne sees `test = PASS`, `lint = PASS`. It never runs a gate, never learns which
tool produced one, and has no code path that could ask. `tests/test_consumer_neutral.py`
proves it: the same repository, described by two of these configurations, resolves to
the same decision.

## Using one

```bash
cp examples/generic/project.toml .ariadne/project.toml
$EDITOR .ariadne/project.toml
ariadne status
```

`ariadne status` reports what the repository proves, so it is the fastest way to see
whether a configuration reads the way you meant. Every key is optional; with no file
at all Ariadne still runs on generic defaults, and fails closed rather than guessing
— an undeclared framework path means a change cannot be *proven* non-product, so
classification stays `UNKNOWN`.
