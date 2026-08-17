#!/usr/bin/env python3
"""Read-only contract checks for the bounded dev-new dry-run.

The entity mapping this workflow depends on used to be asserted as a Markdown
table. It is now asserted against the decision engine, because that is where the
mapping lives; the document is checked only for the sentence that explains it to a
reader. What is guarded has not changed: `/dev-new` treats a non-Product entity as
an error, and must not inherit `/dev-merge`'s no-op reading of the same fact.
"""
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts the package on sys.path)

ROOT = _bootstrap.ROOT
PACKAGE = _bootstrap.SRC / "ariadne"

import state_fixture as sf  # noqa: E402
from ariadne.runtime.classification import NON_PRODUCT, PRODUCT_FEATURE  # noqa: E402
from ariadne.runtime.classification import UNKNOWN as ENTITY_UNKNOWN  # noqa: E402
from ariadne.runtime.decision import (  # noqa: E402
    CONTINUE,
    STOP,
    TERMINAL_BLOCKED,
    TERMINAL_NOT_APPLICABLE,
)
from ariadne.runtime.decision_engine import decide  # noqa: E402
from ariadne.runtime.lifecycle import NEW  # noqa: E402
from ariadne.runtime.state import (  # noqa: E402
    DEV_MERGE,
    DEV_NEW,
    HUMAN_GATE_APPROVED,
    REVIEW_RESOLVED,
)

ADAPTERS = ROOT / "adapters"
workflow = (PACKAGE / "workflows" / "dev-new.md").read_text(encoding="utf-8")
portable = (ADAPTERS / "agents" / "skills" / "dev-new" / "SKILL.md").read_text(encoding="utf-8")
claude = (ADAPTERS / "claude" / "skills" / "dev-new" / "SKILL.md").read_text(encoding="utf-8")
merge = (PACKAGE / "workflows" / "dev-merge.md").read_text(encoding="utf-8")


def outcome(intent: str, entity: str):
    """The decision for one entity class, with every other fact permitting."""
    return decide(
        sf.state(
            workflow_intent=intent,
            entity=entity,
            lifecycle=NEW,
            review=REVIEW_RESOLVED,
            human_gate=HUMAN_GATE_APPROVED,
            dag=sf.dag_state(completed=True),
        )
    )

bounded = "PREFLIGHT → INTAKE → CLASSIFY → PREDICT SCOPE → REPORT → STOP"
assert bounded in workflow

# A non-Product entity is an error for /dev-new, reported as BLOCKED.
for entity, reason in ((NON_PRODUCT, "ENTITY_NOT_PRODUCT_FEATURE"), (ENTITY_UNKNOWN, "ENTITY_UNKNOWN")):
    decision = outcome(DEV_NEW, entity)
    assert decision.decision == TERMINAL_BLOCKED, (entity, decision.decision)
    assert decision.reason_code == reason, (entity, decision.reason_code)
    assert decision.status == "BLOCKED", (entity, decision.status)
    assert decision.next_legal_action == STOP, (entity, decision.next_legal_action)

# And /dev-new does not inherit /dev-merge's reading of the same classification.
merge_decision = outcome(DEV_MERGE, NON_PRODUCT)
assert merge_decision.decision == TERMINAL_NOT_APPLICABLE, merge_decision.decision
assert merge_decision.status == "NOT_APPLICABLE", merge_decision.status
assert outcome(DEV_NEW, NON_PRODUCT).status != merge_decision.status

# A proven Product Feature on a clean tree starts, so the block above is about the
# classification and not about some other unmet condition.
start = outcome(DEV_NEW, PRODUCT_FEATURE)
assert start.decision == CONTINUE, start.decision
assert start.next_legal_action == "PREFLIGHT", start.next_legal_action

# The document explains that distinction to a reader.
assert "does not reuse `/dev-merge`'s `NON_PRODUCT → TERMINAL_NOT_APPLICABLE` mapping" in workflow

for forbidden in (
    "must not invoke the planning provider",
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
assert "ariadne doc lifecycle-entity" in portable
assert "Preserve `$ARGUMENTS`" in portable
assert "ariadne doc lifecycle-entity" in claude
assert "requirement text exactly as supplied" in claude
assert "- `NON_PRODUCT`: report `STATUS = NOT_APPLICABLE`" in merge
print("dev-new bounded dry-run contract checks passed")
