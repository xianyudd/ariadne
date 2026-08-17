#!/usr/bin/env python3
"""The runtime's command-line boundary, for hosts whose adapters are prompts.

A host adapter is a prompt file. It cannot import Python, so this is how it reaches
the runtime: it runs one command, and the command answers whether the workflow may
proceed at all.

```bash
python3 .agent-sdlc/runtime/cli.py DEV_MERGE --human-gate APPROVED
```

The command is the decision point, not an advisory check. It collects evidence,
resolves state, decides, and applies the terminal gate. For a terminal decision it
prints one final report, dispatches nothing, and exits non-zero — so the adapter has
no next phase to enter and no envelope to reinterpret. For `CONTINUE` it prints the
one phase the protocol permits, and that phase is the only thing the agent may do
next.

The dispatcher here prints the granted phase. That is the whole of it: naming the
next legal action is what dispatch means for a prompt host, and the name comes from
the envelope rather than from this file.

Exit codes:

```text
0   CONTINUE — the printed phase is granted
2   TERMINAL_* — final; no phase is granted
64  usage error — nothing was decided
```

Standard library only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):  # invoked as a script, which is the normal case here
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from runtime.api import execute_workflow
    from runtime.decision import Decision
    from runtime.router import WorkflowRouter
    from runtime.state import HUMAN_GATE_STATES, HUMAN_GATE_UNKNOWN, WORKFLOW_INTENTS
else:  # pragma: no cover - importable form, used by the validation suite
    from .api import execute_workflow
    from .decision import Decision
    from .router import WorkflowRouter
    from .state import HUMAN_GATE_STATES, HUMAN_GATE_UNKNOWN, WORKFLOW_INTENTS

EXIT_CONTINUE = 0
EXIT_TERMINAL = 2
EXIT_USAGE = 64


def announce(decision: Decision) -> str:
    """Name the one phase the envelope grants. This is the dispatch."""
    return f"NEXT PHASE: {decision.next_legal_action}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-sdlc-runtime",
        description="Decide and enforce one AGENT-SDLC workflow invocation.",
    )
    parser.add_argument("intent", help=f"workflow intent: {', '.join(sorted(WORKFLOW_INTENTS))}")
    parser.add_argument(
        "--repo", default=".", type=Path, help="repository root (default: current directory)"
    )
    parser.add_argument(
        "--human-gate",
        default=HUMAN_GATE_UNKNOWN,
        choices=sorted(HUMAN_GATE_STATES),
        help="recorded Human Gate state; anything but APPROVED fails closed where one is required",
    )
    parser.add_argument("--dry-run", action="store_true", help="the invocation mutates nothing")
    parser.add_argument("--default-branch", default="main", help="merge target (default: main)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Decide one invocation and report it. Returns the process exit code."""
    args = build_parser().parse_args(argv)

    # An unsupported intent is a decision, not a usage error: the engine has a
    # fail-closed envelope for it, and reporting it as one keeps every refusal in
    # the same shape. Only an unreadable repository path is a usage error.
    repo = args.repo.expanduser()
    if not repo.is_dir():
        print(f"usage: repository path is not a directory: {repo}", file=sys.stderr)
        return EXIT_USAGE

    # The router is built here with one dispatcher for the requested intent, so
    # this invocation cannot reach another workflow's action even in principle.
    router = WorkflowRouter(
        {args.intent: lambda decision: print(announce(decision))}
        if args.intent in WORKFLOW_INTENTS
        else {}
    )

    result = execute_workflow(
        repo,
        args.intent,
        router,
        human_gate=args.human_gate,
        dry_run=args.dry_run,
        default_branch=args.default_branch,
        emit=print,
    )

    if result.emit_error is not None:  # the report is authoritative, so say it was lost
        print(f"report emission failed: {result.emit_error}", file=sys.stderr)
        print(result.final_report or "", file=sys.stderr)
    return EXIT_TERMINAL if result.terminal else EXIT_CONTINUE


if __name__ == "__main__":
    raise SystemExit(main())
