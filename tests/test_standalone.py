#!/usr/bin/env python3
"""Standalone invariants (INV-S1 … INV-S10).

This module is the evidence that Ariadne is a runtime rather than one repository's
tooling. Everything else in the suite asks whether the runtime is correct; these
checks ask whether it is *free* — of the product it was extracted from, of the
hosts that invoke it, and of the planning tool it was originally written against.

The three that are not provable from inside this repository are named where they
are proven: INV-S3 and INV-S10 are properties of a consumer, checked by that
consumer's own suite, and INV-S4/INV-S5 are behavioural and proven by
`test_terminal_gate.py` and `test_runtime_closure.py`. The checks below re-assert
S4/S5 through the public entry point anyway, because "terminal never dispatches"
is the invariant a reader of this file will most want to see standing on its own.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401  (puts the package on sys.path)

from repo_fixture import (  # noqa: E402
    CLOSURE_RECORDED,
    GATES_RECORDED,
    GENERIC,
    PYTHON,
    REVIEW_CLEAN,
    RUST,
    TASKS_COMPLETE,
    make_repo,
)
from ariadne.config import load_project_config  # noqa: E402
from ariadne.integrations import GATE_PASS, GATE_UNKNOWN, GateSpec, resolve_gates  # noqa: E402
from ariadne.runtime import (  # noqa: E402
    CONTINUE,
    DEV_MERGE,
    HUMAN_GATE_APPROVED,
    TERMINAL_DECISIONS,
    Decision,
    evaluate_workflow,
    execute_workflow,
)

ROOT = _bootstrap.ROOT
PACKAGE = _bootstrap.SRC / "ariadne"

checks = 0


def check(condition: object, label: str) -> None:
    global checks
    assert condition, label
    checks += 1


def package_files() -> dict[str, str]:
    """Everything that ships in the wheel: code, contracts, and workflow documents."""
    return {
        path.relative_to(PACKAGE).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(PACKAGE.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


SHIPPED = package_files()


def forbid(patterns: dict[str, str], label: str, allow: tuple[str, ...] = ()) -> None:
    """Assert no shipped file matches any pattern, except in `allow`ed files."""
    for description, pattern in patterns.items():
        matcher = re.compile(pattern, re.IGNORECASE)
        found = sorted(
            f"{name}:{number}"
            for name, text in SHIPPED.items()
            if name not in allow
            for number, line in enumerate(text.splitlines(), 1)
            if matcher.search(line)
        )
        check(not found, f"{label} names no {description} — found {found[:4]}")


# --- INV-S1: zero product dependency ----------------------------------------
# The runtime was extracted from a Rust project. If a single one of these words
# survived anywhere in the wheel, the extraction produced a differently-located
# copy of that project's tooling rather than a runtime.
forbid(
    {
        "build tool": r"\bcargo\b",
        "language": r"\brust\b|\bgolang\b",
        "source project": r"\btflow\b",
        "manifest": r"Cargo\.(toml|lock)",
        "source extension": r"\.(rs|go|java|ts)\b",
        "test command": r"\bpytest\b|\bnpm (test|run)\b|\bgo test\b|\bmix test\b",
    },
    "INV-S1 the wheel",
)
# Nor may it assume a repository layout. `src/` and `tests/` are this repository's
# own directories and one consumer's; a runtime that hardcoded either would be
# reading a project it does not know.
forbid(
    {
        "hardcoded source directory": r"[\"'](?:\./)?src/[\"']|[\"']src/[a-z]",
        "hardcoded test directory": r"[\"'](?:\./)?tests?/[\"']",
        "hardcoded feature directory": r"[\"']specs?/[\"']",
    },
    "INV-S1 the wheel",
)

# Nor may a shipped file point at a path inside the install. A consumer has a wheel
# and no source tree, so a contract that named `src/ariadne/...` would be citing
# something the reader cannot open; every cross-reference goes through `ariadne doc`.
forbid(
    {
        "install path": r"src/ariadne|site-packages|runtime/README",
        "predecessor layout": r"\.agent-sdlc",
    },
    "INV-S1 the wheel",
)
# And every `ariadne doc` reference in a shipped file must name a document that
# actually ships — the idiom is only better than a path if it resolves.
from ariadne.documents import document_names  # noqa: E402

SHIPPED_DOCS = frozenset(document_names())
for name, text in SHIPPED.items():
    for referenced in re.findall(r"ariadne doc ([a-z][a-z-]+)", text):
        check(
            referenced in SHIPPED_DOCS,
            f"INV-S1 {name} cross-references a document that ships ({referenced})",
        )

# --- INV-S2: zero host dependency -------------------------------------------
# A host is a way of invoking the runtime. The runtime must not be able to tell
# which one did: no host name, no host file format, no host directory.
#
# `/dev-merge` and friends are *not* on this list. They are Ariadne's own names for
# its four workflows — the same tokens the CLI accepts as `ariadne dev merge` — so a
# contract naming the phase it governs is naming itself, not a host's command.
forbid(
    {
        "host": r"\bclaude\b|\bcodex\b|\bopencode\b|\bcopilot\b",
        "host file": r"SKILL\.md|AGENTS\.md",
        "host directory": r"\.claude/|\.agents/|\.codex/",
    },
    "INV-S2 the wheel",
)
# The adapter templates live outside the package and are not data the runtime reads.
# A module that opened one would be a runtime that knows what a host looks like.
check(
    not any(
        re.search(r"adapters?[/\\]", text)
        for name, text in SHIPPED.items()
        if name.endswith(".py")
    ),
    "INV-S2 no runtime module reads the adapter templates",
)

# --- INV-S6: the decision policy is single-source ----------------------------
# One callable decides, and the package exports exactly one of it. `audit_wiring.py`
# proves no second policy exists as text; this proves no second one is reachable.
from ariadne.runtime import api, decision_engine  # noqa: E402

check(api.evaluate_state.__module__ == "ariadne.runtime.api", "INV-S6 one reporting entry point")
check(
    api.decide is decision_engine.decide,
    "INV-S6 the entry point calls the one engine",
)
check(
    sum(1 for name in dir(decision_engine) if name.startswith("decide")) == 1,
    "INV-S6 the engine exposes exactly one decision function",
)

# --- INV-S4 / INV-S5: terminal never dispatches, CONTINUE dispatches once ----
# A Feature that has passed final acceptance and is not yet merged: the one state
# from which `/dev-merge` proceeds.
ACCEPTED = dict(
    tasks=TASKS_COMPLETE,
    handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
)

dispatched: list[Decision] = []
with make_repo(flavour=RUST, **ACCEPTED) as fixture:  # type: ignore[arg-type]
    granted = execute_workflow(
        fixture.root, DEV_MERGE, dispatched.append,
        human_gate=HUMAN_GATE_APPROVED, emit=lambda _r: None,
    )
check(granted.decision.decision == CONTINUE, "INV-S5 the case under test continues")
check(len(dispatched) == 1, "INV-S5 CONTINUE dispatches exactly once")

refused: list[Decision] = []
with make_repo(flavour=RUST, branch="random-branch", state_branch="002-example") as fixture:
    settled = execute_workflow(
        fixture.root, DEV_MERGE, refused.append,
        human_gate=HUMAN_GATE_APPROVED, emit=lambda _r: None,
    )
check(settled.decision.decision in TERMINAL_DECISIONS, "INV-S4 the case under test is terminal")
check(not refused, "INV-S4 a terminal decision dispatches zero times")

# --- INV-S7: Spec Kit is not required by the kernel --------------------------
# Two independent claims. First: the kernel does not import the integration.
kernel = {name: text for name, text in SHIPPED.items() if name.startswith("runtime/")}
check(kernel, "INV-S7 the kernel has modules to check")
for name, text in kernel.items():
    check("speckit" not in text, f"INV-S7 {name} does not import the Spec Kit integration")
check(
    "speckit" not in SHIPPED["config.py"],
    "INV-S7 configuration names no planning tool",
)
provider_module = SHIPPED["integrations/planning.py"]
check(
    "import" in provider_module.split("def build_provider")[1].split("\n\n\n")[0],
    "INV-S7 the Spec Kit provider is imported lazily, inside the factory",
)

# Second, and the one that matters: a repository with no `.specify/` at all runs the
# whole chain. `PYTHON` configures the directory provider; `GENERIC` configures
# nothing whatsoever and has never heard of Ariadne.
for flavour in (PYTHON, GENERIC):
    with make_repo(flavour=flavour, tasks=TASKS_COMPLETE) as fixture:
        check(
            not (fixture.root / ".specify").exists(),
            f"INV-S7 the {flavour.name} fixture has no Spec Kit directory",
        )
        decision = evaluate_workflow(fixture.root, DEV_MERGE, human_gate=HUMAN_GATE_APPROVED)
        check(
            decision.reason_code != "PROTOCOL_DECISION_INVALID",
            f"INV-S7 the {flavour.name} repository produced a well-formed envelope",
        )
        check(
            decision.decision in TERMINAL_DECISIONS or decision.decision == CONTINUE,
            f"INV-S7 the {flavour.name} repository was decided, not crashed",
        )

# A repository with no configuration file still loads: absence is a default, not an
# error, so nothing about installing Ariadne requires touching the repository first.
with tempfile.TemporaryDirectory(prefix="ariadne-bare-") as raw:
    bare = load_project_config(Path(raw))
    check(bare.planning_provider == "directory", "INV-S7 an unconfigured repository has a default")
    check(bare.framework_paths == (), "INV-S7 an unconfigured repository declares no framework path")
    check(bare.gates == (), "INV-S7 an unconfigured repository declares no gate")

# --- INV-S8: quality gates enter through configuration ----------------------
# The same recorded sentence proves a gate under one repository's markers and
# nothing under another's. That asymmetry *is* the seam: the runtime learns
# `test = PASS` and cannot learn what produced it.
recorded = "cargo test passed; 3 tests, 0 failures."
compiled = resolve_gates(recorded, (GateSpec("test", RUST.gate_markers),))
scripted = resolve_gates(recorded, (GateSpec("test", PYTHON.gate_markers),))
check(compiled.results["test"] == GATE_PASS, "INV-S8 the consumer's marker proves its own gate")
check(scripted.results["test"] == GATE_UNKNOWN, "INV-S8 another consumer's marker proves nothing")
check(compiled.facts() == ("gate_test=PASS",), "INV-S8 the runtime sees a status, not a command")
check(
    resolve_gates(recorded, ()).declared == (),
    "INV-S8 a repository that declares no gate has none to prove",
)
# A gate is named by the consumer too, not chosen from a fixed vocabulary.
custom = resolve_gates("acceptance suite: green", (GateSpec("acceptance", ("suite: green",)),))
check(custom.passed == ("acceptance",), "INV-S8 the gate vocabulary is the consumer's")
# And an unusable marker proves nothing rather than reading as a pass.
broken = resolve_gates(recorded, (GateSpec("test", ("(unclosed",)),))
check(broken.results["test"] == GATE_UNKNOWN, "INV-S8 a malformed marker fails closed")
check(broken.errors, "INV-S8 a malformed marker is reported")

# --- Installability: the package is self-contained --------------------------
manifest = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
check("[project]" in manifest, "the project declares itself installable")
check(
    re.search(r"^dependencies\s*=\s*\[\s*\]", manifest, re.M) is not None,
    "INV-S1 the package declares zero runtime dependencies",
)
check('requires-python = ">=3.11"' in manifest, "the interpreter floor is declared")
check("ariadne = " in manifest, "the console entry point is declared")

# `import ariadne` from outside this repository, in a fresh interpreter whose working
# directory is not the source tree — the check that the package is a package.
with tempfile.TemporaryDirectory(prefix="ariadne-outside-") as elsewhere:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import ariadne, ariadne.cli;"
            "print(ariadne.__name__, ariadne.cli.main(['doc', '--list']) == 0)",
        ],
        cwd=elsewhere,
        env={"PYTHONPATH": str(_bootstrap.SRC), "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
check(completed.returncode == 0, f"INV-S1 the package imports outside its repository — {completed.stderr[-300:]}")
check("ariadne True" in completed.stdout, "INV-S1 the shipped documents are readable from an import")

print(f"standalone invariant checks passed ({checks} assertions)")
print("INV-S1 INV-S2 INV-S4 INV-S5 INV-S6 INV-S7 INV-S8 verified")
print("INV-S3 INV-S10 are consumer properties, proven by the consumer's own suite")
