"""Entity classification for the Agent SDLC runtime.

This module answers exactly one question: *what kind of repository object is
this?* It maps `RepositoryEvidence` to one classification and stops there.

```text
PRODUCT_FEATURE | NON_PRODUCT | UNKNOWN
```

It deliberately holds no terminal-decision policy. Mapping a classification to
`CONTINUE`/`TERMINAL_*` belongs to `decision_engine.py`, which is the single
executable decision policy.

Evidence rules are declared in `contracts/lifecycle-entity.md`.
Standard library only.
"""

from __future__ import annotations

from .evidence import RepositoryEvidence, workflow_only_changes

PRODUCT_FEATURE = "PRODUCT_FEATURE"
NON_PRODUCT = "NON_PRODUCT"
UNKNOWN = "UNKNOWN"

CLASSIFICATIONS = frozenset({PRODUCT_FEATURE, NON_PRODUCT, UNKNOWN})


def classify_facts(facts: dict[str, object]) -> str:
    """Classify from compact facts.

    Kept as the pure, fact-level entry point so classification can be exercised
    without a repository. `classify_evidence` projects real evidence onto exactly
    these keys, so both paths run the same rules.

    `workflow_only_changes` is a fact like any other, and its absence means false.
    Whether a changed path is framework work depends on what the repository declares
    framework, which is not something this module can know: re-deriving it here from
    a built-in list of paths would put one consumer's layout inside the kernel.
    """
    branch = facts.get("branch")
    registered = facts.get("registered_feature")
    spec_branch = facts.get("spec_branch")
    feature_dir_exists = facts.get("feature_dir_exists") is True
    required_artifacts = facts.get("required_artifacts") is True
    current_state_branch = facts.get("current_state_branch")
    workflow_only = facts.get("workflow_only_changes") is True

    if (
        isinstance(branch, str)
        and isinstance(registered, str)
        and isinstance(spec_branch, str)
        and feature_dir_exists
        and required_artifacts
        and branch == registered == spec_branch == current_state_branch
    ):
        return PRODUCT_FEATURE

    evidence = [
        value
        for value in (registered, spec_branch, current_state_branch)
        if isinstance(value, str)
    ]
    historical_evidence_is_consistent = bool(evidence) and len(set(evidence)) == 1

    if (
        isinstance(branch, str)
        and workflow_only
        and historical_evidence_is_consistent
        and evidence[0] != branch
    ):
        return NON_PRODUCT
    if isinstance(branch, str) and workflow_only and not evidence:
        return NON_PRODUCT
    return UNKNOWN


def classify_evidence(evidence: RepositoryEvidence) -> str:
    """Classify collected repository evidence."""
    return classify_facts(
        {
            "branch": evidence.git.branch,
            "registered_feature": evidence.feature.registered_name,
            "feature_dir_exists": evidence.feature.directory_exists,
            "required_artifacts": evidence.feature.required_artifacts,
            "spec_branch": evidence.feature.spec_branch,
            "current_state_branch": evidence.recorded.state_branch,
            "workflow_only_changes": workflow_only_changes(evidence),
        }
    )
