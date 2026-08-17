#!/usr/bin/env python3
"""Mutation checks: prove the suite would notice if the runtime broke.

A green suite is evidence only if it can go red. Every check in `tests/` asserts
that something is true today; this harness asserts that each of the load-bearing
ones would *fail* if the property it names stopped holding.

Each mutation below is a single edit that breaks exactly one invariant, paired with
the check module that must catch it. The edit is applied to a throwaway copy of the
repository — never to the working tree — and the named module is run there. A
mutation the module still passes is reported as SURVIVED, which means the check is
decorative and the invariant is unguarded.

```bash
python3 tests/mutate.py           # every mutation
python3 tests/mutate.py terminal  # only mutations whose name contains "terminal"
```

Not part of `run_all.py`: it runs the suite many times over and is a deliberate
step, not a per-commit one. Standard library only.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


@dataclass(frozen=True)
class Mutation:
    """One broken invariant and the check that must notice."""

    name: str
    target: str
    old: str
    new: str
    caught_by: tuple[str, ...]
    breaks: str


MUTATIONS = (
    # --- The terminal guarantees ---------------------------------------------
    Mutation(
        name="terminal-dispatches",
        target="src/ariadne/runtime/terminal_gate.py",
        old="if decision.decision in TERMINAL_DECISIONS:",
        new="if False and decision.decision in TERMINAL_DECISIONS:",
        caught_by=("test_terminal_gate.py", "test_runtime_closure.py", "test_standalone.py"),
        breaks="INV-S4: a terminal decision reaches the dispatcher",
    ),
    Mutation(
        name="terminal-gate-reusable",
        target="src/ariadne/runtime/terminal_gate.py",
        old="            if self._settled:",
        new="            if False:",
        caught_by=("test_terminal_gate.py",),
        breaks="a settled gate decides twice",
    ),
    Mutation(
        name="terminal-not-enforced",
        target="src/ariadne/runtime/terminal_gate.py",
        old="        self._settle()",
        new="        pass",
        caught_by=("test_terminal_gate.py",),
        breaks="the gate stops claiming its single decision",
    ),
    # --- The envelope ---------------------------------------------------------
    Mutation(
        name="reserved-prefix-allowed",
        target="src/ariadne/runtime/decision.py",
        old="and str.strip(reason_code).upper().startswith(RESERVED_REASON_PREFIX)",
        new="and False",
        caught_by=("test_terminal_gate.py",),
        breaks="a caller may forge a framework reason code",
    ),
    Mutation(
        name="malformed-envelope-passes",
        target="src/ariadne/runtime/terminal_gate.py",
        old="            decision = protocol_invalid(str(error))",
        new="            raise",
        caught_by=("test_terminal_gate.py", "test_runtime_closure.py"),
        breaks="a malformed envelope escapes instead of failing closed",
    ),
    # --- Classification and the consumer seam --------------------------------
    Mutation(
        name="framework-fact-defaults-true",
        target="src/ariadne/runtime/classification.py",
        old='workflow_only = facts.get("workflow_only_changes") is True',
        new='workflow_only = facts.get("workflow_only_changes") is not False',
        caught_by=("test_classify_entity.py",),
        breaks="an omitted framework fact reads as proven rather than absent",
    ),
    Mutation(
        name="unproven-gate-passes",
        target="src/ariadne/integrations/gates.py",
        old="        status = GATE_UNKNOWN",
        new="        status = GATE_PASS",
        caught_by=("test_standalone.py", "test_evidence.py"),
        breaks="INV-S8: an unproven quality gate reads as a pass",
    ),
    Mutation(
        name="malformed-marker-passes",
        target="src/ariadne/integrations/gates.py",
        old="                status = GATE_PASS\n                break",
        new="                status = GATE_PASS\n                break\n            status = GATE_PASS",
        caught_by=("test_standalone.py",),
        breaks="a marker that will not compile reads as a pass",
    ),
    # --- Lifecycle and the task graph ----------------------------------------
    Mutation(
        name="lifecycle-rollback-legal",
        target="src/ariadne/runtime/lifecycle.py",
        old="    CLOSED: frozenset(),",
        new="    CLOSED: frozenset({NEW, IN_PROGRESS}),",
        caught_by=("test_lifecycle.py",),
        breaks="a closed Feature may transition backwards",
    ),
    Mutation(
        name="cycle-accepted",
        target="src/ariadne/dag/tasks.py",
        old="        if task_id in visiting:",
        new="        if False:",
        caught_by=("test_task_dag.py",),
        breaks="a cyclic task graph validates",
    ),
    Mutation(
        name="blocked-frontier-ready",
        target="src/ariadne/dag/tasks.py",
        old="            and all(dependency in by_id and by_id[dependency].done for dependency in task.depends_on)",
        new="            and True",
        caught_by=("test_task_dag.py",),
        breaks="a task with incomplete dependencies enters the ready frontier",
    ),
    # --- Standalone isolation -------------------------------------------------
    Mutation(
        name="product-coupling-restored",
        target="src/ariadne/config.py",
        old='DEFAULT_SPEC_DIR = "specs"',
        new='DEFAULT_SPEC_DIR = "specs"\nDEFAULT_MANIFEST = "Cargo.toml"',
        caught_by=("test_standalone.py",),
        breaks="INV-S1: the kernel names the product it was extracted from",
    ),
    Mutation(
        name="host-coupling-restored",
        target="src/ariadne/cli.py",
        old="def main(",
        new='_HOST = ".claude/skills"\n\n\ndef main(',
        caught_by=("test_standalone.py",),
        breaks="INV-S2: the runtime names a host directory",
    ),
    Mutation(
        name="speckit-required",
        target="src/ariadne/runtime/evidence.py",
        old="from ..config import",
        new="from ..integrations.speckit import *  # noqa: F403\nfrom ..config import",
        caught_by=("test_standalone.py",),
        breaks="INV-S7: the kernel imports the planning integration",
    ),
    # --- Adapters -------------------------------------------------------------
    Mutation(
        name="adapter-holds-policy",
        target="adapters/claude/skills/dev-merge/SKILL.md",
        old="Never delete feature branches",
        new="If the lifecycle state is READY_TO_CLOSE the decision is CONTINUE.\n\nNever delete feature branches",
        caught_by=("test_adapters.py",),
        breaks="an adapter states a decision rule of its own",
    ),
    Mutation(
        name="adapter-hand-edited",
        target="adapters/codex/prompts/dev-next.md",
        old="# Codex adapter",
        new="# Codex adapter (locally tweaked)",
        caught_by=("test_adapters.py",),
        breaks="a template drifts from its generator",
    ),
    Mutation(
        name="adapter-ignores-exit-code",
        target="adapters/generate.py",
        old="- Non-zero exit: the command has already printed the one final report. That report\n  is the answer — emit it and stop.",
        new="- Non-zero exit: consider whether the report applies.",
        caught_by=("test_adapters.py",),
        breaks="an adapter may reinterpret a terminal decision",
    ),
    # --- Single-source policy -------------------------------------------------
    Mutation(
        name="second-decision-function",
        target="src/ariadne/runtime/decision_engine.py",
        old="def decide(",
        new="def decide_quickly(state):\n    return decide(state)\n\n\ndef decide(",
        caught_by=("test_standalone.py", "audit_wiring.py"),
        breaks="INV-S6: a second decision function becomes reachable",
    ),
)


def apply(mutation: Mutation, tree: Path) -> str | None:
    """Apply one mutation inside `tree`, or report why it could not be applied."""
    path = tree / mutation.target
    if not path.is_file():
        return f"no such file: {mutation.target}"
    text = path.read_text(encoding="utf-8")
    occurrences = text.count(mutation.old)
    if occurrences != 1:
        return f"{occurrences} occurrences of the mutated text in {mutation.target}"
    path.write_text(text.replace(mutation.old, mutation.new), encoding="utf-8")
    return None


def run_check(tree: Path, module: str) -> bool:
    """Run one check module inside the mutated tree; True if it passed."""
    completed = subprocess.run(
        [sys.executable, str(tree / "tests" / module)],
        cwd=tree,
        capture_output=True,
        text=True,
        env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin", "HOME": str(tree)},
        timeout=300,
    )
    return completed.returncode == 0


def copy_tree(destination: Path) -> None:
    """A working copy of the repository, without Git history or caches."""
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".venv"),
    )


def main(argv: list[str]) -> int:
    selected = [m for m in MUTATIONS if not argv or any(term in m.name for term in argv)]
    if not selected:
        print(f"usage: no mutation matches {argv}")
        return 64

    survived: list[str] = []
    unapplied: list[str] = []
    for mutation in selected:
        with tempfile.TemporaryDirectory(prefix="ariadne-mutate-") as raw:
            tree = Path(raw) / "repo"
            copy_tree(tree)
            problem = apply(mutation, tree)
            if problem:
                print(f"  ??  {mutation.name}: {problem}")
                unapplied.append(mutation.name)
                continue
            # The first module that catches it is enough: the claim is that the
            # invariant is guarded, not that every module guards it.
            catcher = next(
                (module for module in mutation.caught_by if not run_check(tree, module)),
                None,
            )
        if catcher is None:
            print(f"  ✗   {mutation.name} SURVIVED — {mutation.breaks}")
            survived.append(mutation.name)
        else:
            print(f"  ok  {mutation.name} caught by {catcher}")

    print(f"\n{len(selected) - len(survived) - len(unapplied)}/{len(selected)} mutations caught")
    if unapplied:
        print("could not be applied (the source moved; update tests/mutate.py):")
        for name in unapplied:
            print(f"  ??  {name}")
    if survived:
        print("SURVIVED (the invariant is unguarded):")
        for name in survived:
            print(f"  ✗   {name}")
    return 1 if survived or unapplied else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
