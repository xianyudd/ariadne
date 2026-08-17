#!/usr/bin/env python3
"""Host adapter isolation (INV-S2, second half).

`test_standalone.py` proves the runtime cannot see a host. This module proves the
other direction: a host adapter cannot see a decision.

An adapter is allowed to be exactly one thing — a host command that runs `ariadne
dev` and obeys the exit code. The failure mode it exists to prevent is drift: one
adapter grows a condition, and two hosts stop agreeing about the same repository.
So the checks here are about absence. No adapter may name a lifecycle state, a
decision, a classification, or a reason code, because naming one is how an adapter
starts deciding.

The templates are generated (`adapters/generate.py`). That is itself an isolation
property, so it is checked first: a hand-edited template is a second place a rule
can live, and this suite fails on one.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts the package on sys.path)

from ariadne.documents import document_names, document_text  # noqa: E402
from ariadne.runtime import (  # noqa: E402
    CLASSIFICATIONS,
    DECISIONS,
    LIFECYCLE_STATES,
    PROTOCOL_DECISION_INVALID,
)
from ariadne.runtime import decision_engine  # noqa: E402

ROOT = _bootstrap.ROOT
ADAPTERS = ROOT / "adapters"

PHASES = ("dev-new", "dev-next", "dev-close", "dev-merge")
FAMILIES = ("claude", "agents", "opencode", "codex")

checks = 0
failures: list[str] = []


def check(condition: object, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def adapter_files() -> dict[str, str]:
    """Every generated template, keyed by its path relative to `adapters/`."""
    return {
        path.relative_to(ADAPTERS).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(ADAPTERS.rglob("*"))
        if path.is_file() and path.name not in {"generate.py", "README.md"}
    }


TEMPLATES = adapter_files()

# --- The templates are generated, not written --------------------------------
generated = subprocess.run(
    [sys.executable, str(ADAPTERS / "generate.py"), "--check"],
    cwd=ROOT,
    capture_output=True,
    text=True,
)
check(
    generated.returncode == 0,
    f"every template matches its generator — {generated.stdout.strip()}",
)
check(
    len(TEMPLATES) == len(PHASES) * len(FAMILIES) + len(FAMILIES),
    f"four hosts carry four phases and one reviewer each — found {len(TEMPLATES)}",
)
for family in FAMILIES:
    present = [name for name in TEMPLATES if name.startswith(f"{family}/")]
    check(len(present) == len(PHASES) + 1, f"{family} carries every phase — found {present}")

# --- No adapter holds decision policy ----------------------------------------
# The vocabulary an adapter is permitted to contain, in full. A whitelist rather
# than a blacklist: a new protocol token leaking into a template fails here without
# anyone having to remember to add it to a list of things to look for.
#
# `APPROVED`, `NOT_APPROVED`, and `UNKNOWN` are the `--human-gate` argument values.
# Establishing that gate is the one judgement an adapter makes, so it must be able
# to name what it is passing. `REVIEW CAPABILITY BLOCKED` is a report an adapter
# emits when the host cannot provide an independent reviewer — a statement about the
# host's own capability, which is the only subject an adapter is authoritative on.
# `ARGUMENTS` is the host's argument variable and `SKILL` a host file name.
ALLOWED_TOKENS = {
    "APPROVED",
    "NOT_APPROVED",
    "UNKNOWN",
    "REVIEW",
    "CAPABILITY",
    "BLOCKED",
    "ARGUMENTS",
    "SKILL",
}

TOKEN_RE = re.compile(r"[A-Z][A-Z_]{2,}")
for name, text in TEMPLATES.items():
    found = set(TOKEN_RE.findall(text)) - ALLOWED_TOKENS
    check(not found, f"{name} names no protocol token beyond its own vocabulary — {sorted(found)}")

# The same claim stated the way a reader will want to check it, and derived from the
# runtime rather than typed out: adding a decision value or a reason code extends
# this sweep automatically. `UNKNOWN` and `BLOCKED` are subtracted because they
# collide with the argument and report vocabulary above; the whitelist sweep is what
# covers them, since nothing uppercase can appear that is not on that list.
REASON_CODES = frozenset(
    value
    for name in dir(decision_engine)
    if name.startswith("REASON_")
    for value in ([getattr(decision_engine, name)] if isinstance(getattr(decision_engine, name), str) else [])
)
POLICY_TOKENS = (
    (
        frozenset(DECISIONS)
        | frozenset(CLASSIFICATIONS)
        | frozenset(LIFECYCLE_STATES)
        | REASON_CODES
        | {PROTOCOL_DECISION_INVALID}
    )
    - ALLOWED_TOKENS
)
check(REASON_CODES, "the reason codes were found to sweep for")
check(len(POLICY_TOKENS) > 20, f"the sweep covers the protocol vocabulary — {len(POLICY_TOKENS)} tokens")
for name, text in TEMPLATES.items():
    leaked = sorted(token for token in POLICY_TOKENS if token in text)
    check(not leaked, f"{name} states no decision, state, or reason code — {leaked}")

# Nor in prose. An adapter that explained when a phase is permitted would be holding
# the rule even without naming a constant.
for name, text in TEMPLATES.items():
    lowered = text.lower()
    for phrase in ("if the feature is", "when the branch", "only if the tasks", "unless the review"):
        check(phrase not in lowered, f"{name} states no condition of its own ({phrase})")

# --- Every adapter runs the runtime before doing anything else ----------------
for phase in PHASES:
    intent = phase.split("-", 1)[1]
    for name, text in TEMPLATES.items():
        if f"/{phase}" not in name and not name.endswith(f"{phase}.md"):
            continue
        check(
            f"ariadne dev {intent}" in text,
            f"{name} runs the runtime for its phase",
        )
        check(
            ("--human-gate" in text) == (phase == "dev-merge"),
            f"{name} declares a Human Gate argument only where one is required",
        )

# Non-zero exit is final. Every adapter must say so, because that sentence is the
# whole of the enforcement on a prompt host: nothing else stops a model from reading
# on past a terminal decision.
for name, text in TEMPLATES.items():
    if "reviewer" in name:
        continue
    check("non-zero exit" in text.lower(), f"{name} treats a non-zero exit as the final report")
    check(
        "emit it and stop" in text.lower(),
        f"{name} stops on a terminal decision rather than reinterpreting it",
    )

# --- Adapters reference documents through the install, never by path ----------
DOC_RE = re.compile(r"ariadne doc ([a-z-]+)")
KNOWN = frozenset(document_names())
for name, text in TEMPLATES.items():
    for referenced in DOC_RE.findall(text):
        check(referenced in KNOWN, f"{name} loads a document Ariadne ships ({referenced})")

# An adapter names no filesystem path into the install. A consumer has a wheel, not
# a source tree, so a path here would be a reference to something that is not there.
for name, text in TEMPLATES.items():
    for forbidden in ("src/ariadne", ".agent-sdlc", "site-packages", "workflows/dev-"):
        check(forbidden not in text, f"{name} reaches into no install path ({forbidden})")

# The documents an adapter asks for must be ones its workflow wants: the workflow
# document is authoritative about what a phase reads, and an adapter that loaded
# something extra would be preparing for work the workflow never asked for.
for phase in PHASES:
    wanted = frozenset(DOC_RE.findall(document_text(phase)))
    check(wanted, f"the {phase} workflow names the documents it loads")
    for name, text in TEMPLATES.items():
        if f"/{phase}" not in name and not name.endswith(f"{phase}.md"):
            continue
        asked = frozenset(DOC_RE.findall(text))
        check(
            asked <= wanted,
            f"{name} loads only what its workflow loads — extra {sorted(asked - wanted)}",
        )

# --- The installer seam ------------------------------------------------------
# Project policies are the consumer's and Ariadne neither ships nor reads them, so
# every adapter carries an empty block for an installer to fill in. An adapter that
# named a concrete policy file would have a consumer's layout baked into it.
for name, text in TEMPLATES.items():
    if "reviewer" in name or name.startswith("opencode/"):
        continue
    check(
        "<!-- ariadne:project-policies -->" in text
        and "<!-- /ariadne:project-policies -->" in text,
        f"{name} carries the project-policy block an installer fills in",
    )
    between = text.split("<!-- ariadne:project-policies -->")[1].split("<!-- /")[0]
    check(
        ".md" not in between,
        f"{name} ships the block empty rather than naming a consumer's file",
    )

# The delegating host is allowed to be shorter, but not to be a second adapter.
for phase in PHASES:
    delegating = TEMPLATES[f"opencode/commands/{phase}.md"]
    check(
        f"skills/{phase}/SKILL.md" in delegating,
        f"the opencode {phase} command delegates rather than restating",
    )
    check(
        len(delegating.splitlines()) < 20,
        f"the opencode {phase} command stays a delegation ({len(delegating.splitlines())} lines)",
    )

# --- The reviewer is a capability, not a workflow -----------------------------
for family in FAMILIES:
    reviewer = next(name for name in TEMPLATES if name.startswith(family) and "reviewer" in name)
    text = TEMPLATES[reviewer]
    check("ariadne doc review-contract" in text, f"{reviewer} reads the contract rather than restating it")
    check("read-only" in text.lower(), f"{reviewer} is read-only")
    check("ariadne dev" not in text, f"{reviewer} runs no workflow phase")
    for forbidden in ("claude-", "gpt-", "opus", "sonnet"):
        check(forbidden not in text.lower(), f"{reviewer} hard-codes no model ({forbidden})")

if failures:
    print(f"{len(failures)} FAILED:")
    for failure in failures:
        print(f"  ✗ {failure}")
    raise SystemExit(1)
print(f"host adapter checks passed ({checks} assertions)")
print(f"INV-S2 verified in both directions across {len(TEMPLATES)} templates")
