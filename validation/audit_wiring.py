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
python3 .agent-sdlc/validation/audit_wiring.py
```
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SDLC = ROOT / ".agent-sdlc"
sys.path.insert(0, str(SDLC))
sys.path.insert(0, str(SDLC / "validation"))

from runtime.decision_engine import REASON_CODES  # noqa: E402
from runtime.state import WORKFLOW_INTENTS  # noqa: E402
from source_view import code_only  # noqa: E402

RUNTIME = SDLC / "runtime"
VALIDATION = SDLC / "validation"
WORKFLOWS = ("dev-new", "dev-next", "dev-close", "dev-merge")
SELF = Path(__file__).name

# Host adapter families. Prompt files, one per workflow, that must route through the
# runtime and decide nothing themselves.
ADAPTERS = [
    ROOT / ".claude" / "skills" / name / "SKILL.md" for name in WORKFLOWS
] + [
    ROOT / ".agents" / "skills" / name / "SKILL.md" for name in WORKFLOWS
] + [
    ROOT / ".opencode" / "commands" / f"{name}.md" for name in WORKFLOWS
]

# `.claude/worktrees/` is a protected registered-worktree path: never read as
# implementation source. Excluded from every sweep below by path prefix.
PROTECTED = (ROOT / ".claude" / "worktrees",)

failures: list[str] = []
checks = 0


def report(ok: object, label: str, detail: str = "") -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(f"{label}{f' — {detail}' if detail else ''}")


def protected(path: Path) -> bool:
    return any(root in path.parents or root == path for root in PROTECTED)


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


RUNTIME_SOURCES = {path.name: code_only(path) for path in python_sources(RUNTIME)}
VALIDATION_SOURCES = {path.name: code_only(path) for path in python_sources(VALIDATION)}
ALL_PYTHON = {**{f"runtime/{k}": v for k, v in RUNTIME_SOURCES.items()},
              **{f"validation/{k}": v for k, v in VALIDATION_SOURCES.items()}}

# A second view, as written. Claims about string literals must read this one:
# `code_only` drops the literals, so `CONTINUE = "CONTINUE"` is invisible there.
RAW = {
    f"runtime/{path.name}": path.read_text(encoding="utf-8") for path in python_sources(RUNTIME)
} | {
    f"validation/{path.name}": path.read_text(encoding="utf-8")
    for path in python_sources(VALIDATION)
}
RUNTIME_ONLY = {name: source for name, source in ALL_PYTHON.items() if name.startswith("runtime/")}
RAW_RUNTIME = {name: source for name, source in RAW.items() if name.startswith("runtime/")}


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
# The §25 sweep: any module that assigns a decision value or a reason code is
# declaring policy. In the runtime, only the engine and the envelope may. Tests
# reference both vocabularies by design — that is what a table-driven test is — so
# the claim is scoped to the runtime and stated as such.
DECISION_ASSIGNMENT = re.compile(
    r"^\s*[A-Z_]+\s*=\s*[\"'](?:CONTINUE|TERMINAL_SUCCESS|TERMINAL_BLOCKED|TERMINAL_NOT_APPLICABLE)[\"']",
    re.M,
)
only(RAW_RUNTIME, DECISION_ASSIGNMENT, ["runtime/decision.py"],
     "INV-R1 only the envelope declares decision values")

only(RUNTIME_ONLY, "reason_code=", ["runtime/decision.py", "runtime/decision_engine.py"],
     "INV-R1 only the engine populates a reason code")

REASON_ASSIGNMENT = re.compile(
    r"^\s*[A-Z_]+\s*=\s*\"(?:" + "|".join(sorted(REASON_CODES)) + r")\"", re.M
)
only(RAW_RUNTIME, REASON_ASSIGNMENT, ["runtime/decision_engine.py"],
     "INV-R1 only the engine declares reason codes")

# The retired second policy must be gone from code, not merely unused. The docs and
# test names that record its removal are prose, which `code_only` has already blanked.
only(ALL_PYTHON, "decision_for_entity", [], "INV-R1 the retired per-entity decision helper is gone")

# --- B: no dispatch path around the gate (INV-R2, INV-R3, INV-R6) -----------
only(RUNTIME_ONLY, re.compile(r"dispatcher\("), ["runtime/router.py", "runtime/terminal_gate.py"],
     "INV-R6 only the gate and the router call a dispatcher")

api_source = RUNTIME_SOURCES["api.py"]
report("TerminalGate(dispatcher" in api_source, "INV-R6 the entry point builds the gate")
report(".route(" not in api_source, "INV-R6 the entry point never routes directly")
report(
    "dispatcher" not in RUNTIME_SOURCES["decision_engine.py"],
    "INV-R7 the decision engine cannot dispatch",
)

cli_source = RUNTIME_SOURCES["cli.py"]
report("execute_workflow(" in cli_source, "INV-R6 the CLI goes through the enforced entry point")
report(
    "decide(" not in cli_source and "evaluate_workflow(" not in cli_source,
    "INV-R6 the CLI cannot decide without enforcing",
)

# --- C: the router holds no policy (INV-R7) ---------------------------------
router_source = RUNTIME_SOURCES["router.py"]
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
# Tests and fixtures write `tasks.md` text; only one module may read it back.
only(RAW_RUNTIME, re.compile(r"Depends:|- \[x\]|- \[ \]"), ["runtime/dag.py"],
     "INV-R9 one runtime module parses tasks.md")
only(ALL_PYTHON, re.compile(r"def resolve_dag"), ["runtime/dag.py"],
     "INV-R9 the graph resolver is defined once")
report(
    "resolve_dag" not in RAW["validation/repo_fixture.py"],
    "INV-R9 the fixture writes task files but resolves nothing",
)

# --- E: lifecycle is derived, never injected (INV-R5) -----------------------
# The flag itself, not a mention of it: `classify_entity.py` documents that the flag
# was removed, and that sentence must not read as the flag existing.
only(RAW, re.compile(r"add_argument\(\s*\"--lifecycle-state\""), [],
     "INV-R5 no CLI accepts an injected lifecycle state")
only(RUNTIME_ONLY, re.compile(r"LifecycleResolution\("), ["runtime/lifecycle.py"],
     "INV-R5 only the resolver can construct a lifecycle state")
only(RUNTIME_ONLY, re.compile(r"resolve_lifecycle\("), ["runtime/lifecycle.py", "runtime/state.py"],
     "INV-R5 the state resolver is the only runtime caller of the lifecycle resolver")
report(
    not any(
        "--lifecycle-state" in path.read_text(encoding="utf-8") for path in ADAPTERS if path.is_file()
    ),
    "INV-R5 no adapter injects a lifecycle state",
)

# --- F: host adapters hold no decision semantics (INV-R8, INV-R10) ----------
# A decision mapping, a reason code, or a status verdict in an adapter is a second
# policy. Naming a lifecycle state in help text is not, and is allowed.
MAPPING_ROW = re.compile(r"→\s*(?:DECISION\s+)?(?:CONTINUE|TERMINAL_[A-Z_]+)")
for path in ADAPTERS:
    label = str(path.relative_to(ROOT))
    if not path.is_file():
        report(False, f"INV-R8 {label} exists")
        continue
    text = path.read_text(encoding="utf-8")
    report(not MAPPING_ROW.search(text), f"INV-R8 {label} states no decision mapping")
    present = sorted(code for code in REASON_CODES if code in text)
    report(not present, f"INV-R8 {label} names no reason code", f"found {present}")
    report("runtime/cli.py" in text, f"INV-R10 {label} routes through the runtime")

# Every adapter family names the same intent for the same workflow, which is what
# makes the same repository state produce the same envelope on every host.
for name in WORKFLOWS:
    intent = f"DEV_{name.split('-', 1)[1].upper()}"
    report(intent in WORKFLOW_INTENTS, f"INV-R10 {intent} is a declared intent")
    naming = [
        path
        for path in ADAPTERS
        if path.is_file() and path.parent.name == name or path.stem == name
    ]
    report(
        all(intent in path.read_text(encoding="utf-8") for path in naming),
        f"INV-R10 every {name} adapter names {intent}",
    )

# --- G: Markdown owns no runtime decision semantics (§21) ------------------
# Core and the workflow documents may state the rules; they may not be the only
# place a rule exists. Every documented reason code must be one the engine emits —
# `test_decision_consistency.py` proves that binding, and this only checks it ran.
report(
    (VALIDATION / "test_decision_consistency.py").is_file(),
    "§10 the docs-to-engine consistency test exists",
)
report(
    "REASON_CODES" in (VALIDATION / "test_decision_consistency.py").read_text(encoding="utf-8"),
    "§10 the consistency test binds the reason-code vocabulary",
)

stale = re.compile(
    r"not yet (?:implemented|wired)|is not implemented|are not yet",
    re.I,
)
for path in sorted(SDLC.rglob("*.md")):
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
