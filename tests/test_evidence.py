#!/usr/bin/env python3
"""Evidence layer checks (§A).

Every assertion here runs against a real repository built by `repo_fixture.py`:
real Git history, a real registration, real artifacts, a real handoff. Nothing is
injected, because the point of this layer is that it reads facts.

The evidence layer must also hold no policy, so these tests assert what it
reports, never what it permits.
"""
from __future__ import annotations

import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts the package on sys.path)

from repo_fixture import (  # noqa: E402
    CLOSURE_RECORDED,
    GATES_RECORDED,
    GENERIC,
    REVIEW_CLEAN,
    REVIEW_OUTSTANDING,
    TASKS_COMPLETE,
    TASKS_CYCLE,
    TASKS_PARTIAL,
    TASKS_READY,
    make_repo,
)
from ariadne.runtime.classification import (  # noqa: E402
    NON_PRODUCT,
    PRODUCT_FEATURE,
    UNKNOWN,
    classify_evidence,
)
from ariadne.runtime.evidence import collect_repository_evidence, workflow_only_changes  # noqa: E402

checks = 0


def check(condition: object, label: str) -> None:
    global checks
    assert condition, label
    checks += 1


# --- A1: a proven Product Feature -------------------------------------------
# Every path here comes from the flavour, never from a literal: a test that named
# `src/lib.rs` would be asserting about a language the runtime cannot see.
with make_repo(tasks=TASKS_READY, product_change=True) as fixture:
    flavour = fixture.flavour
    evidence = collect_repository_evidence(fixture.root)
    check(evidence.git.available, "A1 git available")
    check(evidence.git.branch == "002-example", "A1 branch observed")
    check(evidence.feature.registered_name == "002-example", "A1 registration read")
    check(evidence.feature.required_artifacts, "A1 spec/plan/tasks present")
    check(evidence.feature.spec_branch == "002-example", "A1 spec Feature Branch parsed")
    check(evidence.recorded.state_branch == "002-example", "A1 handoff branch parsed")
    check(evidence.dag.valid and not evidence.dag.completed, "A1 graph valid and unfinished")
    check(classify_evidence(evidence) == PRODUCT_FEATURE, "A1 classified PRODUCT_FEATURE")
    check(flavour.source not in evidence.git.changed_paths, "A1 changed paths are real")
    check(flavour.added_source in evidence.git.changed_paths, "A1 product change observed")
    check(not workflow_only_changes(evidence), "A1 not workflow-only")

# --- A2: a non-product workflow branch --------------------------------------
with make_repo(
    branch="agent-sdlc-v2",
    spec_branch="002-example",
    state_branch="002-example",
    feature_on_main=True,
    workflow_change=True,
    tasks=TASKS_COMPLETE,
    handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(
        evidence.git.changed_paths == (fixture.flavour.framework_change,),
        "A2 only workflow paths",
    )
    check(workflow_only_changes(evidence), "A2 workflow-only is a path fact")
    check(classify_evidence(evidence) == NON_PRODUCT, "A2 classified NON_PRODUCT")

# --- A3: mixed evidence is UNKNOWN, never a guess ---------------------------
with make_repo(
    branch="agent-sdlc-v2",
    spec_branch="002-example",
    state_branch="002-example",
    feature_on_main=True,
    workflow_change=True,
    product_change=True,
) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(not workflow_only_changes(evidence), "A3 product change breaks workflow-only")
    check(classify_evidence(evidence) == UNKNOWN, "A3 mixed changes classify UNKNOWN")

# --- A4: an ambiguous branch (branch disagrees with recorded evidence) ------
with make_repo(branch="random-branch", spec_branch="002-example", state_branch="002-example") as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(evidence.git.branch == "random-branch", "A4 branch observed")
    check(classify_evidence(evidence) == UNKNOWN, "A4 branch disagreement classifies UNKNOWN")

with make_repo(state_branch="001-other") as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(classify_evidence(evidence) == UNKNOWN, "A4 handoff disagreement classifies UNKNOWN")

# --- A5: a protected path is exempted and still reported --------------------
with make_repo(tasks=TASKS_READY, protected_change=True) as fixture:
    prefix = fixture.flavour.protected_paths[0]
    evidence = collect_repository_evidence(fixture.root)
    check(len(evidence.git.protected_paths) == 1, "A5 protected path reported")
    check(
        all(path.startswith(prefix) for path in evidence.git.protected_paths),
        "A5 protected path identified by prefix",
    )
    check(
        not any(path.startswith(prefix) for path in evidence.git.changed_paths),
        "A5 protected path excluded from classification input",
    )
    check(classify_evidence(evidence) == PRODUCT_FEATURE, "A5 exemption does not change entity")
    facts = evidence.facts()
    check(any(fact == "protected_paths=1" for fact in facts), "A5 exemption is in the record")

# --- A6: missing specification artifacts ------------------------------------
with make_repo(include_spec=False) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(not evidence.feature.required_artifacts, "A6 missing spec.md detected")
    check(evidence.feature.spec_branch is None, "A6 no spec branch to read")
    check(classify_evidence(evidence) == UNKNOWN, "A6 missing artifacts classify UNKNOWN")

with make_repo(tasks=None) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(evidence.feature.tasks_path is None, "A6 missing tasks.md detected")
    check(not evidence.dag.valid and not evidence.dag.readable, "A6 absent graph is not valid")

with make_repo(feature_dir_exists=False) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(not evidence.feature.directory_exists, "A6 dangling registration detected")

with make_repo(feature=None) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(evidence.feature.registered_name is None, "A6 no registration detected")

# --- A7: Git unavailable ----------------------------------------------------
with make_repo(git=False) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(not evidence.git.available, "A7 unavailable Git is reported, not raised")
    check(evidence.git.branch is None, "A7 no branch invented")
    check("git_unavailable=yes" in evidence.facts(), "A7 unavailability is in the record")
    check(classify_evidence(evidence) == UNKNOWN, "A7 no Git means UNKNOWN entity")

# --- A8: recorded review/gate/closure evidence ------------------------------
with make_repo(tasks=TASKS_PARTIAL, handoff_lines=(REVIEW_OUTSTANDING,)) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(evidence.recorded.review_outstanding, "A8 outstanding BLOCKER count read")
    check(not evidence.recorded.review_resolved, "A8 outstanding is not resolved")

with make_repo(
    tasks=TASKS_COMPLETE,
    handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(evidence.recorded.review_resolved, "A8 BLOCKER: 0 read as resolved")
    check(evidence.recorded.quality_gates_recorded, "A8 gate evidence read")
    check(evidence.recorded.closure_recorded, "A8 closure evidence read")
    # The gate is proven by the consumer's own words, matched by the consumer's own
    # markers. The runtime learns `test = PASS` and nothing about what produced it.
    check(evidence.recorded.gates.passed == ("test",), "A8 the declared gate is the one proven")
    check(not evidence.recorded.gates.errors, "A8 the consumer's markers are usable")

# A repository that declares no gates cannot prove one, and that is not an error.
with make_repo(
    flavour=GENERIC,
    tasks=TASKS_COMPLETE,
    handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(evidence.recorded.gates.declared == (), "A8 an unconfigured repository declares no gate")
    check(not evidence.recorded.quality_gates_recorded, "A8 no declared gate proves nothing")
    check(not evidence.recorded.gates.errors, "A8 declaring no gate is not an error")

# --- A9: merge facts distinguish branch from Feature ------------------------
with make_repo(tasks=TASKS_COMPLETE, merge_into_main=True) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(evidence.git.merged_into_default is True, "A9 merged branch observed")
    check(evidence.git.feature_merged_into_default is True, "A9 merged Feature observed")

with make_repo(tasks=TASKS_COMPLETE) as fixture:
    evidence = collect_repository_evidence(fixture.root)
    check(evidence.git.merged_into_default is False, "A9 unmerged branch observed")

# --- A10: facts are deterministic and ordered -------------------------------
with make_repo(tasks=TASKS_CYCLE) as fixture:
    first = collect_repository_evidence(fixture.root)
    second = collect_repository_evidence(fixture.root)
    check(first.facts() == second.facts(), "A10 identical repository yields identical facts")
    check(first.facts()[0].startswith("branch="), "A10 fact order is fixed")
    check("dag_status=DAG_INVALID" in first.facts(), "A10 invalid graph is a reported fact")

print(f"evidence layer checks passed ({checks} assertions)")
