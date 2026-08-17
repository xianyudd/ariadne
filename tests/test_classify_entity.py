#!/usr/bin/env python3
"""Fact-level classification checks (§A).

`test_evidence.py` classifies real repositories. This module covers the same rules
at the fact level, where combinations that are awkward to build on disk — a spec
that names one Feature while the handoff names another — are one dict away.

Two things are deliberately absent. There is no path literal: whether a changed
path is framework work is a consumer fact, resolved by the evidence layer and
handed in as `workflow_only_changes`, so classification never sees a filename.
And there is no decision: this module classifies, and a second decision table
living next to a classifier is the thing that was removed.
"""
from __future__ import annotations

import _bootstrap  # noqa: F401  (puts the package on sys.path)

from ariadne.runtime import classification  # noqa: E402
from ariadne.runtime.classification import (  # noqa: E402
    NON_PRODUCT,
    PRODUCT_FEATURE,
    UNKNOWN,
    classify_facts,
)

checks = 0


def check(condition: object, label: str) -> None:
    global checks
    assert condition, label
    checks += 1


def facts(**overrides: object) -> dict[str, object]:
    """A coherent Product Feature, before whatever the caller wants to break."""
    value: dict[str, object] = {
        "branch": "002-example",
        "registered_feature": "002-example",
        "feature_dir_exists": True,
        "required_artifacts": True,
        "spec_branch": "002-example",
        "current_state_branch": "002-example",
        "workflow_only_changes": False,
    }
    value.update(overrides)
    return value


# --- Agreement across every source is the only route to PRODUCT_FEATURE -----
check(classify_facts(facts()) == PRODUCT_FEATURE, "agreeing evidence is a Product Feature")
check(
    classify_facts(
        facts(
            branch="001-example",
            registered_feature="001-example",
            spec_branch="001-example",
            current_state_branch="001-example",
        )
    )
    == PRODUCT_FEATURE,
    "the Feature name is read, never matched against a pattern",
)

# One disagreement, or one missing source, and the answer is UNKNOWN — never a
# guess at which source was right.
for label, broken in (
    ("the handoff names another Feature", facts(current_state_branch="001-other")),
    ("the spec declares no branch", facts(spec_branch=None)),
    ("the handoff is absent", facts(current_state_branch=None)),
    ("nothing is registered", facts(registered_feature=None)),
    ("the Feature directory is missing", facts(feature_dir_exists=False)),
    ("a required artifact is missing", facts(required_artifacts=False)),
    ("Git reports no branch", facts(branch=None)),
):
    check(classify_facts(broken) == UNKNOWN, f"UNKNOWN when {label}")

# --- NON_PRODUCT needs proof, and the proof is not the branch name ----------
# Framework-only changes, plus historical evidence that consistently points at a
# Feature other than the current branch: work on the framework itself.
check(
    classify_facts(
        facts(
            branch="framework-branch",
            registered_feature="002-example",
            spec_branch="002-example",
            current_state_branch="002-example",
            workflow_only_changes=True,
        )
    )
    == NON_PRODUCT,
    "framework-only changes off the Feature branch are NON_PRODUCT",
)
# A repository with no historical evidence at all and framework-only changes is
# also NON_PRODUCT: there is no Feature to be working on.
check(
    classify_facts(
        facts(
            branch="framework-branch",
            registered_feature=None,
            spec_branch=None,
            current_state_branch=None,
            feature_dir_exists=False,
            required_artifacts=False,
            workflow_only_changes=True,
        )
    )
    == NON_PRODUCT,
    "framework-only changes with no Feature evidence are NON_PRODUCT",
)
# Inconsistent historical evidence cannot prove it, even framework-only.
for label, broken in (
    (
        "the sources disagree",
        facts(
            branch="framework-branch",
            registered_feature="001-example",
            spec_branch="002-example",
            current_state_branch="003-example",
            workflow_only_changes=True,
        ),
    ),
    (
        "part of the evidence is missing",
        facts(
            branch="framework-branch",
            registered_feature="002-example",
            spec_branch="001-other",
            current_state_branch=None,
            workflow_only_changes=True,
        ),
    ),
):
    check(classify_facts(broken) == UNKNOWN, f"framework-only is not enough when {label}")

# The one that matters most: a repository that declares no framework paths reports
# `workflow_only_changes=False`, so it can never prove NON_PRODUCT. Absence of a
# declaration is not permission.
check(
    classify_facts(
        facts(
            branch="framework-branch",
            registered_feature="002-example",
            spec_branch="002-example",
            current_state_branch="002-example",
        )
    )
    == UNKNOWN,
    "an undeclared framework path cannot prove NON_PRODUCT",
)
# And the fact simply being absent reads the same way, rather than falling back to
# a built-in list of paths.
check(
    classify_facts(
        {
            "branch": "framework-branch",
            "registered_feature": "002-example",
            "spec_branch": "002-example",
            "current_state_branch": "002-example",
        }
    )
    == UNKNOWN,
    "an omitted framework fact is false, not a built-in default",
)

# --- Mixed changes are the consumer's problem, reported as one fact ---------
# The evidence layer collapses "framework and product both changed" to False, so
# the classifier has nothing to weigh: UNKNOWN, by the same rule as above.
check(
    classify_facts(facts(branch="framework-branch", workflow_only_changes=False)) == UNKNOWN,
    "mixed changes classify UNKNOWN",
)

# --- No second decision policy lives here (INV-R1) --------------------------
check(
    not hasattr(classification, "decision_for_entity"),
    "the retired per-entity decision table has not reappeared",
)
check(
    classification.CLASSIFICATIONS == frozenset({PRODUCT_FEATURE, NON_PRODUCT, UNKNOWN}),
    "the classification vocabulary is exactly three values",
)
source = _bootstrap.SRC.joinpath("ariadne", "runtime", "classification.py").read_text(
    encoding="utf-8"
)
for token in ("CONTINUE", "TERMINAL_", "reason_code"):
    check(f'"{token}' not in source, f"the classifier declares no {token}")

print(f"lifecycle classification checks passed ({checks} assertions)")
