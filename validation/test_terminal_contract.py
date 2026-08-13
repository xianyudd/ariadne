#!/usr/bin/env python3
"""Static checks for the host-independent terminal decision contract."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]
CORE = ROOT / ".agent-sdlc" / "core"
WORKFLOW = ROOT / ".agent-sdlc" / "workflows" / "dev-merge.md"
CLAUDE_ADAPTER = ROOT / ".claude" / "skills" / "dev-merge" / "SKILL.md"
PORTABLE_ADAPTER = ROOT / ".agents" / "skills" / "dev-merge" / "SKILL.md"
OPENCODE_ADAPTER = ROOT / ".opencode" / "commands" / "dev-merge.md"

contract = (CORE / "terminal-contract.md").read_text(encoding="utf-8")
workflow = WORKFLOW.read_text(encoding="utf-8")
lifecycle = (CORE / "lifecycle.md").read_text(encoding="utf-8")
entity = (CORE / "lifecycle-entity.md").read_text(encoding="utf-8")

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

assert "core/terminal-contract.md" in workflow
assert workflow.index("## CLASSIFY → DECIDE") < workflow.index("## Product Feature workflow")
assert "PRODUCT_FEATURE + READY_TO_CLOSE → DECISION CONTINUE" in workflow
assert "PRODUCT_FEATURE + IN_PROGRESS     → DECISION TERMINAL_BLOCKED" in workflow
assert "NON_PRODUCT                      → DECISION TERMINAL_NOT_APPLICABLE" in workflow
assert "UNKNOWN                          → DECISION TERMINAL_BLOCKED" in workflow
assert "PREFLIGHT" in workflow and "RESTORE" in workflow and "CLOSURE CHECKPOINT" in workflow
assert "terminal branches MUST NOT enter" in workflow
assert "emit the result once and STOP" in workflow

assert "terminal-contract.md" in lifecycle
assert "terminal-contract.md" in entity
for adapter in (CLAUDE_ADAPTER, PORTABLE_ADAPTER):
    adapter_text = adapter.read_text(encoding="utf-8")
    assert "terminal-contract.md" in adapter_text
assert "Core terminal decision contract" in OPENCODE_ADAPTER.read_text(encoding="utf-8")

expected = {
    "terminal-product-in-progress.md": ("PRODUCT_FEATURE", "TERMINAL_BLOCKED", "BLOCKED", "STOP"),
    "terminal-product-ready.md": ("PRODUCT_FEATURE", "CONTINUE", "READY", "NORMAL_FLOW"),
    "terminal-non-product.md": ("NON_PRODUCT", "TERMINAL_NOT_APPLICABLE", "NOT_APPLICABLE", "STOP"),
    "terminal-unknown.md": ("UNKNOWN", "TERMINAL_BLOCKED", "BLOCKED", "STOP"),
}
fixture_dir = ROOT / ".agent-sdlc" / "validation" / "fixtures"
for filename, values in expected.items():
    fixture = (fixture_dir / filename).read_text(encoding="utf-8")
    for value in values:
        assert value in fixture, (filename, value)

print("terminal decision contract checks passed")
