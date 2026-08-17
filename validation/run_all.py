#!/usr/bin/env python3
"""Run every protocol check, then the architecture-level wiring audit.

Two kinds of check live here and both are required. The `test_*.py` modules prove
the runtime behaves correctly where it is called; `audit_wiring.py` proves it is
the only thing being called. A green test suite with a failed audit means the
runtime works and something bypasses it, so this runner reports them separately
and fails on either.

Each check is a standalone script run in its own interpreter: they are meant to be
runnable one at a time, and a module that crashes the interpreter must not take the
rest of the suite with it.

```bash
python3 .agent-sdlc/validation/run_all.py            # everything
python3 .agent-sdlc/validation/run_all.py --quiet    # one line per check
```
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SELF = Path(__file__).name

# The audit runs last: reading it before the tests pass tells you nothing useful.
AUDIT = "audit_wiring.py"


def suite() -> list[Path]:
    """Every check module, tests first and the wiring audit last."""
    tests = sorted(path for path in HERE.glob("test_*.py"))
    return tests + [HERE / AUDIT]


def run(path: Path, quiet: bool) -> tuple[bool, str]:
    """Run one check module, returning whether it passed and its last output line."""
    completed = subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        # The suite must leave the working tree exactly as it found it, whether or
        # not an individual module remembers to set `sys.dont_write_bytecode`.
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    ok = completed.returncode == 0
    output = (completed.stdout + completed.stderr).rstrip()
    if not quiet and output:
        print(output)
    lines = [line for line in output.splitlines() if line.strip()]
    return ok, lines[-1] if lines else f"exit {completed.returncode}, no output"


def main(argv: list[str]) -> int:
    quiet = "--quiet" in argv
    failed: list[tuple[str, str]] = []
    for path in suite():
        label = path.name
        if not quiet:
            print(f"\n=== {label} ===")
        ok, summary = run(path, quiet)
        if quiet:
            print(f"{'ok  ' if ok else 'FAIL'} {label}: {summary}")
        if not ok:
            failed.append((label, summary))

    total = len(suite())
    print(f"\n{total - len(failed)}/{total} checks passed")
    if failed:
        print("\nFAILED:")
        for label, summary in failed:
            print(f"  ✗ {label}: {summary}")
        return 1
    print("protocol validation and wiring audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
