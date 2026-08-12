#!/usr/bin/env python3
"""Read-only contract checks for the bounded dev-new dry-run."""
from pathlib import Path

ROOT = Path(__file__).parents[2]
workflow = (ROOT / ".agent-sdlc" / "workflows" / "dev-new.md").read_text(encoding="utf-8")
portable = (ROOT / ".agents" / "skills" / "dev-new" / "SKILL.md").read_text(encoding="utf-8")
claude = (ROOT / ".claude" / "skills" / "dev-new" / "SKILL.md").read_text(encoding="utf-8")
merge = (ROOT / ".agent-sdlc" / "workflows" / "dev-merge.md").read_text(encoding="utf-8")

bounded = "PREFLIGHT → INTAKE → CLASSIFY → PREDICT SCOPE → REPORT → STOP"
assert bounded in workflow
assert "NON_PRODUCT                                      → BLOCKED" in workflow
assert "UNKNOWN                                          → BLOCKED" in workflow
assert "Do not reuse `/dev-merge`'s `NON_PRODUCT → NOT_APPLICABLE` mapping" in workflow
for forbidden in (
    "must not invoke Spec Kit",
    "clarify loops",
    "plan/task generation",
    "reviewers",
    "tests",
    "builds",
    "branch creation",
    "handoff updates",
    "any worktree operation",
):
    assert forbidden in workflow
assert ".agent-sdlc/core/lifecycle-entity.md" in portable
assert "Preserve `$ARGUMENTS`" in portable
assert ".agent-sdlc/core/lifecycle-entity.md" in claude
assert "requirement text exactly as supplied" in claude
assert "- `NON_PRODUCT`: report `STATUS = NOT_APPLICABLE`" in merge
print("dev-new bounded dry-run contract checks passed")
