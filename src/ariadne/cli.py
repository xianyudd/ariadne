#!/usr/bin/env python3
"""Ariadne's command-line boundary, for hosts whose adapters are prompts.

A host adapter is a prompt file. It cannot import Python, so this is how it reaches
the runtime: it runs one command, and the command answers whether the workflow may
proceed at all.

```bash
ariadne dev merge --human-gate APPROVED
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

This module is a thin entry. Every command below reads the canonical runtime API and
renders it; none of them decides anything, and none of them can reach a workflow
without the gate.

```text
ariadne dev new|next|close|merge   decide and enforce one invocation
ariadne status                     what state the repository is in
ariadne inspect                    what entity the repository is, and the envelope
ariadne validate tasks <path>      the task graph, resolved and reported
ariadne doc <name>                 print one shipped contract or workflow document
```

Exit codes:

```text
0   CONTINUE, or a read-only command that answered
2   TERMINAL_* — final; no phase is granted
64  usage error — nothing was decided
```

`validate` reports the graph rather than a workflow, so it exits `1` for a file that
was read and rejected and `2` for one that could not be read at all.

Standard library only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):  # invoked as a script from a source checkout
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ariadne.config import load_project_config
    from ariadne.dag.tasks import DagState, resolve_dag
    from ariadne.documents import document_names, document_text
    from ariadne.runtime.api import evaluate_state, execute_workflow
    from ariadne.runtime.decision import Decision
    from ariadne.runtime.router import WorkflowRouter
    from ariadne.runtime.state import (
        HUMAN_GATE_STATES,
        HUMAN_GATE_UNKNOWN,
        WORKFLOW_INTENTS,
        resolve_repository_state,
    )
    from ariadne.workflows import WORKFLOWS, workflow_path
else:
    from .config import load_project_config
    from .dag.tasks import DagState, resolve_dag
    from .documents import document_names, document_text
    from .runtime.api import evaluate_state, execute_workflow
    from .runtime.decision import Decision
    from .runtime.router import WorkflowRouter
    from .runtime.state import (
        HUMAN_GATE_STATES,
        HUMAN_GATE_UNKNOWN,
        WORKFLOW_INTENTS,
        resolve_repository_state,
    )
    from .workflows import WORKFLOWS, workflow_path

EXIT_CONTINUE = 0
EXIT_REJECTED = 1
EXIT_TERMINAL = 2
EXIT_USAGE = 64

# Host-facing phase names, and the runtime intents they are. The mapping is here
# because command spelling is a host concern; the intents themselves belong to the
# runtime, and this table may not contain anything else.
PHASES = {
    "new": "DEV_NEW",
    "next": "DEV_NEXT",
    "close": "DEV_CLOSE",
    "merge": "DEV_MERGE",
}


def announce(decision: Decision) -> str:
    """Name the one phase the envelope grants, and where its document is.

    This is the dispatch. The phase comes from the envelope; the document is looked
    up from the granted workflow, so a prompt host does not have to know an install
    path to read what it was just permitted to do.
    """
    lines = [f"NEXT PHASE: {decision.next_legal_action}"]
    if decision.workflow in WORKFLOWS:
        lines.append(f"WORKFLOW DOCUMENT: {workflow_path(decision.workflow)}")
    return "\n".join(lines)


def render_dag(state: DagState) -> list[str]:
    """Render a resolved graph in the established report shape."""
    if not state.valid:
        # An unreadable file is reported as-is; graph diagnostics are bulleted.
        bullet = "" if not state.readable else "- "
        return ["DAG INVALID", *(f"{bullet}{error}" for error in state.errors)]
    lines: list[str] = []
    if state.legacy:
        lines.append("STATUS LEGACY_TASK_FORMAT")
    if state.completed or not state.tasks:
        return [*lines, "STATUS COMPLETE", f"TASKS {state.total}", "READY_FRONTIER empty", "BLOCKED 0"]
    lines.append("STATUS VALID")
    lines.append(f"TASKS {state.total}")
    lines.append("READY_FRONTIER " + (", ".join(state.ready) or "empty"))
    lines.append("BLOCKED " + (", ".join(state.blocked) or "0"))
    return lines


def add_repository_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo", default=".", type=Path, help="repository root (default: current directory)"
    )
    parser.add_argument(
        "--default-branch",
        default=None,
        help="merge target; overrides the repository's configuration",
    )


class Parser(argparse.ArgumentParser):
    """An argument parser whose usage errors are usage errors.

    `argparse` exits `2` by default, which is this command's terminal-decision code.
    A host reading `2` must be able to conclude that a decision was made and was
    final, so a misspelled flag may not produce it.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: usage: {message}", file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(
        prog="ariadne",
        description="A governed runtime for agentic software development.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    dev = commands.add_parser("dev", help="decide and enforce one workflow invocation")
    # Deliberately not a `choices` list. An unrecognised phase is a decision, not a
    # usage error: the engine has a fail-closed envelope for an unsupported intent,
    # and routing it there keeps every refusal in the same shape and the same report.
    dev.add_argument("phase", help=f"workflow phase: {', '.join(sorted(PHASES))}")
    add_repository_options(dev)
    dev.add_argument(
        "--human-gate",
        default=HUMAN_GATE_UNKNOWN,
        choices=sorted(HUMAN_GATE_STATES),
        help="recorded Human Gate state; anything but APPROVED fails closed where one is required",
    )
    dev.add_argument("--dry-run", action="store_true", help="the invocation mutates nothing")

    status = commands.add_parser("status", help="report resolved state without deciding a phase")
    add_repository_options(status)

    inspect = commands.add_parser("inspect", help="report the entity, lifecycle, and envelope")
    add_repository_options(inspect)
    inspect.add_argument("--phase", choices=sorted(PHASES), default="merge")
    inspect.add_argument("--dry-run", action="store_true")

    validate = commands.add_parser("validate", help="validate a repository artifact")
    validate_kind = validate.add_subparsers(dest="artifact", required=True)
    tasks = validate_kind.add_parser("tasks", help="resolve and report a task graph")
    tasks.add_argument("path", type=Path, help="path to the task file")

    doc = commands.add_parser("doc", help="print one shipped contract or workflow document")
    doc.add_argument("name", nargs="?", help="document name, without the .md suffix")
    doc.add_argument("--list", action="store_true", help="list every document instead")

    return parser


def resolve_repo(raw: Path) -> Path | None:
    repo = raw.expanduser()
    return repo if repo.is_dir() else None


def run_dev(args: argparse.Namespace) -> int:
    """Decide one invocation and enforce it."""
    repo = resolve_repo(args.repo)
    if repo is None:
        print(f"usage: repository path is not a directory: {args.repo}", file=sys.stderr)
        return EXIT_USAGE
    intent = PHASES.get(args.phase, args.phase)

    # The router is built here with one dispatcher for the requested intent, so this
    # invocation cannot reach another workflow's action even in principle. An intent
    # the runtime does not declare gets an empty registry: there is nothing to
    # dispatch to, and the engine's refusal is what the host sees.
    router = WorkflowRouter(
        {intent: lambda decision: print(announce(decision))}
        if intent in WORKFLOW_INTENTS
        else {}
    )

    result = execute_workflow(
        repo,
        intent,
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


def run_status(args: argparse.Namespace) -> int:
    """Report what the repository proves, without granting a phase."""
    repo = resolve_repo(args.repo)
    if repo is None:
        print(f"usage: repository path is not a directory: {args.repo}", file=sys.stderr)
        return EXIT_USAGE
    config = load_project_config(repo)
    if args.default_branch:
        from dataclasses import replace

        config = replace(config, default_branch=args.default_branch)
    state = resolve_repository_state(repo, PHASES["merge"], config=config)
    print(f"REPOSITORY {repo.resolve()}")
    for fact in state.evidence.detail():
        print(fact)
    return EXIT_CONTINUE


def run_inspect(args: argparse.Namespace) -> int:
    """Report the entity and the envelope the runtime would produce.

    Reporting only: this prints the envelope, it does not enforce it. Enforcement is
    `TerminalGate`, reached through `execute_workflow` — which is what `dev` does.
    """
    repo = resolve_repo(args.repo)
    if repo is None:
        print(f"usage: repository path is not a directory: {args.repo}", file=sys.stderr)
        return EXIT_USAGE
    state = resolve_repository_state(
        repo,
        PHASES[args.phase],
        dry_run=args.dry_run,
        default_branch=args.default_branch,
    )
    decision = evaluate_state(state)
    print(f"BRANCH {state.evidence.git.branch or 'unavailable'}")
    print(f"CLASSIFICATION {state.entity}")
    print(f"LIFECYCLE {state.lifecycle_state}")
    print(f"WORKFLOW {decision.workflow}")
    print(f"DECISION {decision.decision}")
    print(f"STATUS {decision.status}")
    if decision.reason_code:
        print(f"REASON_CODE {decision.reason_code}")
    return EXIT_CONTINUE


def run_validate(args: argparse.Namespace) -> int:
    state = resolve_dag(args.path)
    print("\n".join(render_dag(state)))
    if not state.valid:
        # 2 = the task file could not be read at all; 1 = it was read and rejected.
        return EXIT_TERMINAL if not state.readable else EXIT_REJECTED
    return EXIT_CONTINUE


def run_doc(args: argparse.Namespace) -> int:
    """Print one document Ariadne ships.

    A host adapter is a prompt file, so this is how it loads a contract or a workflow
    from an installed Ariadne without knowing where that install is. Printing only:
    a document read here has no more authority than the same document read anywhere,
    because the rules it describes are enforced by `dev`.
    """
    if args.list or not args.name:
        for name in document_names():
            print(name)
        return EXIT_CONTINUE if args.list else EXIT_USAGE
    try:
        print(document_text(args.name), end="")
    except KeyError:
        print(f"usage: no such document: {args.name}", file=sys.stderr)
        print("available: " + ", ".join(document_names()), file=sys.stderr)
        return EXIT_USAGE
    return EXIT_CONTINUE


COMMANDS = {
    "dev": run_dev,
    "status": run_status,
    "inspect": run_inspect,
    "validate": run_validate,
    "doc": run_doc,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command and report it. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
