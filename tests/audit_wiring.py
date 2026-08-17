#!/usr/bin/env python3
"""Architecture-level wiring audit.

Unit tests prove the runtime behaves correctly where it is called. They cannot
prove it is the only thing being called. This audit is the complement: it reads the
repository as text and fails if a second decision policy, a dispatch path around
the gate, or a host adapter with decision semantics has reappeared.

It is deliberately a static sweep rather than a set of imports — the failure mode
it exists to catch is code that the runtime never imports.

Run it after the test suite:

```bash
python3 tests/audit_wiring.py
```
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts the package on sys.path)

sys.dont_write_bytecode = True

from ariadne.config import load_project_config  # noqa: E402
from ariadne.runtime.decision_engine import REASON_CODES  # noqa: E402
from ariadne.runtime.state import WORKFLOW_INTENTS  # noqa: E402
from source_view import code_only  # noqa: E402

ROOT = _bootstrap.ROOT
TESTS = _bootstrap.HERE
PACKAGE = _bootstrap.SRC / "ariadne"
ADAPTER_ROOT = ROOT / "adapters"
WORKFLOWS = ("dev-new", "dev-next", "dev-close", "dev-merge")
SELF = Path(__file__).name

# Host adapter families. Prompt files, one per workflow, that must route through the
# runtime and decide nothing themselves. They are generated, so the generator is
# audited alongside them: it is where a rule would have to be written to reach all
# sixteen at once.
ADAPTERS = [
    ADAPTER_ROOT / "claude" / "skills" / name / "SKILL.md" for name in WORKFLOWS
] + [
    ADAPTER_ROOT / "agents" / "skills" / name / "SKILL.md" for name in WORKFLOWS
] + [
    ADAPTER_ROOT / "opencode" / "commands" / f"{name}.md" for name in WORKFLOWS
] + [
    ADAPTER_ROOT / "codex" / "prompts" / f"{name}.md" for name in WORKFLOWS
]
GENERATOR = ADAPTER_ROOT / "generate.py"

# Whatever this repository declares protected is never read as implementation source.
# Read from its own configuration rather than hardcoded, so the audit obeys the same
# seam every consumer uses.
PROTECTED = tuple(
    (ROOT / relative).resolve() for relative in load_project_config(ROOT).protected_paths
) + ((ROOT / ".git").resolve(),)

failures: list[str] = []
checks = 0


def report(ok: object, label: str, detail: str = "") -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(f"{label}{f' — {detail}' if detail else ''}")


def protected(path: Path) -> bool:
    resolved = path.resolve()
    return any(root in resolved.parents or root == resolved for root in PROTECTED)


def python_sources(directory: Path) -> list[Path]:
    """Every Python module under `directory`, except this audit itself.

    The audit necessarily names every token it forbids, so scanning itself would
    report a violation in every sweep.
    """
    return sorted(
        path
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts and not protected(path) and path.name != SELF
    )


def keyed(directory: Path, prefix: str) -> dict[str, Path]:
    """Modules keyed by their path inside `directory`, so subpackages stay distinct."""
    return {
        f"{prefix}{path.relative_to(directory).as_posix()}": path
        for path in python_sources(directory)
    }


PACKAGE_FILES = keyed(PACKAGE, "")
TEST_FILES = keyed(TESTS, "tests/")

# Two views of the same code. `code_only` blanks comments and string literals, so a
# claim about *what the code does* reads this one; a claim about a string literal must
# read `RAW`, where `CONTINUE = "CONTINUE"` is still visible.
PACKAGE_CODE = {name: code_only(path) for name, path in PACKAGE_FILES.items()}
RAW_PACKAGE = {name: path.read_text(encoding="utf-8") for name, path in PACKAGE_FILES.items()}
ALL_PYTHON = PACKAGE_CODE | {name: code_only(path) for name, path in TEST_FILES.items()}
RAW = RAW_PACKAGE | {
    name: path.read_text(encoding="utf-8") for name, path in TEST_FILES.items()
}


def only(sources: dict[str, str], needle: str | re.Pattern[str], expected: list[str], label: str) -> None:
    """Assert that exactly `expected` modules contain `needle`."""
    matcher = needle.search if isinstance(needle, re.Pattern) else lambda text: needle in text
    found = sorted(name for name, source in sources.items() if matcher(source))
    report(
        found == expected,
        label,
        f"expected {expected}, found {found}" if found != expected else "",
    )


# --- A: exactly one decision policy (INV-R1) --------------------------------
# Any module that assigns a decision value or a reason code is declaring policy. In
# the package, only the engine and the envelope may. Tests reference both
# vocabularies by design — that is what a table-driven test is — so the claim is
# scoped to the installable package and stated as such.
DECISION_ASSIGNMENT = re.compile(
    r"^\s*[A-Z_]+\s*=\s*[\"'](?:CONTINUE|TERMINAL_SUCCESS|TERMINAL_BLOCKED|TERMINAL_NOT_APPLICABLE)[\"']",
    re.M,
)
only(RAW_PACKAGE, DECISION_ASSIGNMENT, ["runtime/decision.py"],
     "INV-R1 only the envelope declares decision values")

only(PACKAGE_CODE, "reason_code=", ["runtime/decision.py", "runtime/decision_engine.py"],
     "INV-R1 only the engine populates a reason code")

REASON_ASSIGNMENT = re.compile(
    r"^\s*[A-Z_]+\s*=\s*\"(?:" + "|".join(sorted(REASON_CODES)) + r")\"", re.M
)
only(RAW_PACKAGE, REASON_ASSIGNMENT, ["runtime/decision_engine.py"],
     "INV-R1 only the engine declares reason codes")

# The retired second policy must be gone from code, not merely unused. The docs and
# test names that record its removal are prose, which `code_only` has already blanked.
only(ALL_PYTHON, "decision_for_entity", [], "INV-R1 the retired per-entity decision helper is gone")

# --- B: no dispatch path around the gate (INV-R2, INV-R3, INV-R6) -----------
only(PACKAGE_CODE, re.compile(r"dispatcher\("), ["runtime/router.py", "runtime/terminal_gate.py"],
     "INV-R6 only the gate and the router call a dispatcher")

api_source = PACKAGE_CODE["runtime/api.py"]
report("TerminalGate(dispatcher" in api_source, "INV-R6 the entry point builds the gate")
report(".route(" not in api_source, "INV-R6 the entry point never routes directly")
report(
    "dispatcher" not in PACKAGE_CODE["runtime/decision_engine.py"],
    "INV-R7 the decision engine cannot dispatch",
)

cli_source = PACKAGE_CODE["cli.py"]
report("execute_workflow(" in cli_source, "INV-R6 the CLI goes through the enforced entry point")
report(
    "decide(" not in cli_source,
    "INV-R6 the CLI cannot decide without enforcing",
)

# --- C: the router holds no policy (INV-R7) ---------------------------------
router_source = PACKAGE_CODE["runtime/router.py"]
for forbidden in (
    *(code for code in REASON_CODES),
    "lifecycle",
    "PRODUCT_FEATURE",
    "NON_PRODUCT",
    "safety",
    "dry_run",
    "TERMINAL_",
):
    report(forbidden not in router_source, f"INV-R7 the router does not mention {forbidden}")
report(
    router_source.count("CONTINUE") == 2,
    "INV-R7 the router reads exactly one decision value",
    f"count={router_source.count('CONTINUE')}",
)

# --- D: one canonical task-graph implementation (INV-R9) --------------------
# Tests and fixtures write task-file text; only one module may read it back.
only(RAW_PACKAGE, re.compile(r"Depends:|- \[x\]|- \[ \]"), ["dag/tasks.py"],
     "INV-R9 one package module parses the tasks file")
only(ALL_PYTHON, re.compile(r"def resolve_dag"), ["dag/tasks.py"],
     "INV-R9 the graph resolver is defined once")
report(
    "resolve_dag" not in RAW["tests/repo_fixture.py"],
    "INV-R9 the fixture writes task files but resolves nothing",
)

# --- E: lifecycle is derived, never injected (INV-R5) -----------------------
only(RAW, re.compile(r"add_argument\(\s*\"--lifecycle-state\""), [],
     "INV-R5 no CLI accepts an injected lifecycle state")
only(PACKAGE_CODE, re.compile(r"LifecycleResolution\("), ["runtime/lifecycle.py"],
     "INV-R5 only the resolver can construct a lifecycle state")
only(PACKAGE_CODE, re.compile(r"resolve_lifecycle\("), ["runtime/lifecycle.py", "runtime/state.py"],
     "INV-R5 the state resolver is the only package caller of the lifecycle resolver")
report(
    not any(
        "--lifecycle-state" in path.read_text(encoding="utf-8") for path in ADAPTERS if path.is_file()
    ),
    "INV-R5 no adapter injects a lifecycle state",
)

# --- F: host adapters hold no decision semantics (INV-R8, INV-R10) ----------
# A decision mapping, a reason code, or a status verdict in an adapter is a second
# policy. An adapter's whole content is a command and how to obey its result.
MAPPING_ROW = re.compile(r"→\s*(?:DECISION\s+)?(?:CONTINUE|TERMINAL_[A-Z_]+)")
for path in ADAPTERS + [GENERATOR]:
    label = str(path.relative_to(ROOT))
    if not path.is_file():
        report(False, f"INV-R8 {label} exists")
        continue
    text = path.read_text(encoding="utf-8")
    report(not MAPPING_ROW.search(text), f"INV-R8 {label} states no decision mapping")
    present = sorted(code for code in REASON_CODES if code in text)
    report(not present, f"INV-R8 {label} names no reason code", f"found {present}")

# Every family routes the same workflow through the same command, which is what makes
# the same repository state produce the same envelope on every host.
for name in WORKFLOWS:
    intent = f"DEV_{name.split('-', 1)[1].upper()}"
    report(intent in WORKFLOW_INTENTS, f"INV-R10 {intent} is a declared intent")
    command = f"ariadne dev {name.split('-', 1)[1]}"
    family = [
        path
        for path in ADAPTERS
        if path.is_file() and (path.parent.name == name or path.stem == name)
    ]
    report(len(family) == 4, f"INV-R10 {name} has an adapter in every family", f"found {len(family)}")
    report(
        all(command in path.read_text(encoding="utf-8") for path in family),
        f"INV-R10 every {name} adapter runs `{command}`",
    )

# --- G: Markdown owns no runtime decision semantics (§21) ------------------
# The contracts and the workflow documents may state the rules; they may not be the
# only place a rule exists. Every documented reason code must be one the engine emits
# — `test_decision_consistency.py` proves that binding, and this only checks it ran.
consistency = TESTS / "test_decision_consistency.py"
report(consistency.is_file(), "§10 the docs-to-engine consistency test exists")
report(
    "REASON_CODES" in consistency.read_text(encoding="utf-8"),
    "§10 the consistency test binds the reason-code vocabulary",
)

stale = re.compile(
    r"not yet (?:implemented|wired)|is not implemented|are not yet",
    re.I,
)
for path in sorted(ROOT.rglob("*.md")):
    if protected(path):
        continue
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if stale.search(line):
            report(False, f"§28 {path.relative_to(ROOT)}:{number} claims something is unimplemented")

print(f"wiring audit: {checks} checks")
if failures:
    print(f"\n{len(failures)} FAILED:")
    for failure in failures:
        print(f"  ✗ {failure}")
    raise SystemExit(1)
# Which invariants this audit is the evidence for. The rest are behavioural and
# proven by `test_runtime_closure.py` and `test_terminal_gate.py`.
print("INV-R1 INV-R5 INV-R6 INV-R7 INV-R8 INV-R9 INV-R10 audited")
print("wiring audit passed")
