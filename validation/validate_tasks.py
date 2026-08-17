#!/usr/bin/env python3
"""Thin CLI over the canonical task DAG API.

The DAG algorithm lives in `.agent-sdlc/runtime/dag.py`, which is the single
executable implementation. This script only renders it. `tasks.md` remains the
sole task source of truth.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.dag import DagState, resolve_dag  # noqa: E402


def render(state: DagState) -> list[str]:
    """Render a resolved graph in the established CLI shape."""
    if not state.valid:
        # An unreadable file is reported as-is; graph diagnostics are bulleted.
        bullet = "" if not state.readable else "- "
        return ["DAG INVALID", *(f"{bullet}{error}" for error in state.errors)]
    lines: list[str] = []
    if state.legacy:
        lines.append("STATUS LEGACY_TASK_FORMAT")
    if state.completed or not state.tasks:
        lines.extend(
            [
                "STATUS COMPLETE",
                f"TASKS {state.total}",
                "READY_FRONTIER empty",
                "BLOCKED 0",
            ]
        )
        return lines
    lines.append("STATUS VALID")
    lines.append(f"TASKS {state.total}")
    lines.append("READY_FRONTIER " + (", ".join(state.ready) or "empty"))
    lines.append("BLOCKED " + (", ".join(state.blocked) or "0"))
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tasks", type=Path)
    args = parser.parse_args()
    state = resolve_dag(args.tasks)
    print("\n".join(render(state)))
    if not state.valid:
        # 2 = the task file could not be read at all; 1 = it was read and rejected.
        return 1 if state.readable else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
