#!/usr/bin/env python3
"""Static checks for the host-independent terminal decision contract.

The contract, the workflow document that applies it, and the fixtures that
illustrate it are read as text here. The rules themselves are checked against the
engine by `test_decision_consistency.py`; this file checks that the documents still
say what the engine enforces, and that no adapter has started saying it too.
"""
from __future__ import annotations

import re

import _bootstrap  # noqa: F401  (puts the package on sys.path)

ROOT = _bootstrap.ROOT
PACKAGE = _bootstrap.SRC / "ariadne"
CONTRACTS = PACKAGE / "contracts"
WORKFLOW = PACKAGE / "workflows" / "dev-merge.md"
ADAPTERS = ROOT / "adapters"
CLAUDE_ADAPTER = ADAPTERS / "claude" / "skills" / "dev-merge" / "SKILL.md"
PORTABLE_ADAPTER = ADAPTERS / "agents" / "skills" / "dev-merge" / "SKILL.md"
OPENCODE_ADAPTER = ADAPTERS / "opencode" / "commands" / "dev-merge.md"
CODEX_ADAPTER = ADAPTERS / "codex" / "prompts" / "dev-merge.md"

contract = (CONTRACTS / "terminal-contract.md").read_text(encoding="utf-8")
workflow = WORKFLOW.read_text(encoding="utf-8")
lifecycle = (CONTRACTS / "lifecycle.md").read_text(encoding="utf-8")
entity = (CONTRACTS / "lifecycle-entity.md").read_text(encoding="utf-8")

for token in ("CONTINUE", "TERMINAL_SUCCESS", "TERMINAL_BLOCKED", "TERMINAL_NOT_APPLICABLE"):
    assert token in contract
assert "MUST STOP immediately" in contract
assert "no legal successor phase" in contract
assert "PRODUCT_FEATURE + READY_TO_CLOSE → CONTINUE" in contract
assert "PRODUCT_FEATURE + IN_PROGRESS     → TERMINAL_BLOCKED" in contract
assert "NON_PRODUCT                      → TERMINAL_NOT_APPLICABLE" in contract
assert "UNKNOWN                          → TERMINAL_BLOCKED" in contract
assert "Only `CONTINUE` enters" in contract
assert "A Product Feature that is not yet `READY_TO_CLOSE` reports `STATUS = BLOCKED`" in contract

assert "ariadne doc terminal-contract" in workflow
assert workflow.index("## CLASSIFY → DECIDE") < workflow.index("## Product Feature workflow")
assert "PRODUCT_FEATURE + READY_TO_CLOSE → DECISION CONTINUE" in workflow
assert "PRODUCT_FEATURE + IN_PROGRESS     → DECISION TERMINAL_BLOCKED" in workflow
assert "NON_PRODUCT                      → DECISION TERMINAL_NOT_APPLICABLE" in workflow
assert "UNKNOWN                          → DECISION TERMINAL_BLOCKED" in workflow
assert "PREFLIGHT" in workflow and "RESTORE" in workflow and "CLOSURE CHECKPOINT" in workflow
assert "terminal branches MUST NOT enter" in workflow
assert "emit the result once and STOP" in workflow

# The two Core documents that must defer to the contract rather than restate it.
assert "terminal-contract.md" in lifecycle
assert "terminal-contract.md" in entity

# An adapter obeys terminality without describing it. The command is what it holds;
# the mapping is what it must not, so both are asserted rather than only the first.
MAPPING = re.compile(r"(PRODUCT_FEATURE|NON_PRODUCT|UNKNOWN)\s*(?:\+\s*[A-Z_]+\s*)?→")
for adapter in (CLAUDE_ADAPTER, PORTABLE_ADAPTER, OPENCODE_ADAPTER, CODEX_ADAPTER):
    text = adapter.read_text(encoding="utf-8")
    assert "ariadne dev merge" in text, adapter
    assert "non-zero exit" in text.lower(), adapter
    assert MAPPING.search(text) is None, f"{adapter} restates the decision mapping"
    for token in ("TERMINAL_BLOCKED", "TERMINAL_NOT_APPLICABLE", "READY_TO_CLOSE"):
        # `--human-gate APPROVED` is an argument, not a decision; a terminal decision
        # value or a lifecycle state appearing here would be a rule living in a prompt.
        assert token not in text, f"{adapter} names {token}"

expected = {
    "terminal-product-in-progress.md": ("PRODUCT_FEATURE", "TERMINAL_BLOCKED", "BLOCKED", "STOP"),
    "terminal-product-ready.md": ("PRODUCT_FEATURE", "CONTINUE", "READY", "NORMAL_FLOW"),
    "terminal-non-product.md": ("NON_PRODUCT", "TERMINAL_NOT_APPLICABLE", "NOT_APPLICABLE", "STOP"),
    "terminal-unknown.md": ("UNKNOWN", "TERMINAL_BLOCKED", "BLOCKED", "STOP"),
}
fixture_dir = _bootstrap.HERE / "fixtures"
for filename, values in expected.items():
    fixture = (fixture_dir / filename).read_text(encoding="utf-8")
    for value in values:
        assert value in fixture, (filename, value)

print("terminal decision contract checks passed")
