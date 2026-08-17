#!/usr/bin/env python3
"""Read-only regression checks for managed lifecycle classification."""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("classify_entity.py")
spec = importlib.util.spec_from_file_location("classify_entity", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def facts(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "branch": "002-example",
        "registered_feature": "002-example",
        "feature_dir_exists": True,
        "required_artifacts": True,
        "spec_branch": "002-example",
        "current_state_branch": "002-example",
        "changed_paths": ["src/example.rs"],
    }
    value.update(overrides)
    return value


assert module.classify_facts(
    facts(
        branch="001-example",
        registered_feature="001-example",
        spec_branch="001-example",
        current_state_branch="001-example",
        changed_paths=["src/example.rs"],
    )
) == "PRODUCT_FEATURE"
assert module.classify_facts(facts(current_state_branch="001-other")) == "UNKNOWN"
assert module.classify_facts(facts(spec_branch=None)) == "UNKNOWN"
assert module.classify_facts(
    facts(
        registered_feature="002-example",
        spec_branch=None,
        current_state_branch=None,
        changed_paths=[".agent-sdlc/core/lifecycle-entity.md"],
    )
) == "UNKNOWN"
assert module.classify_facts(
    facts(
        registered_feature="002-example",
        spec_branch="001-other",
        current_state_branch=None,
        changed_paths=[".agent-sdlc/core/lifecycle-entity.md"],
    )
) == "UNKNOWN"
assert module.classify_facts(
    facts(
        registered_feature="001-example",
        spec_branch="002-example",
        current_state_branch="003-example",
        changed_paths=[".agent-sdlc/core/lifecycle-entity.md"],
    )
) == "UNKNOWN"
assert module.classify_facts(
    facts(
        branch="agent-sdlc-v2",
        registered_feature="002-example",
        spec_branch="002-example",
        current_state_branch=None,
        changed_paths=[".agent-sdlc/core/lifecycle-entity.md", "src/uncommitted.rs"],
    )
) == "UNKNOWN"
assert module.classify_facts(
    facts(
        branch="some-random-branch",
        registered_feature=None,
        feature_dir_exists=False,
        required_artifacts=False,
        spec_branch=None,
        current_state_branch=None,
        changed_paths=["src/example.rs"],
    )
) == "UNKNOWN"
# This module classifies and nothing else. It used to also own
# `decision_for_entity`, a second decision table; the entity/lifecycle → decision
# mapping now lives only in `runtime/decision_engine.py` and is asserted by
# `test_decision_engine.py`. Assert the second policy stays gone.
assert not hasattr(module, "decision_for_entity"), "second decision policy reappeared"
assert module.classify_facts is __import__("runtime.classification", fromlist=["x"]).classify_facts

print("lifecycle classification checks passed")
