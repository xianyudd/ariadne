#!/usr/bin/env python3
"""Consumer neutrality (INV-S9): one repository state, one decision, any consumer.

`test_runtime_closure.py` proves INV-S9 across *hosts* — two dispatchers, one
envelope. This module proves the other half, which the extraction created: two
*consumers*, one envelope.

The construction is a repository built twice. Same Git history, same lifecycle
position, same review and gate evidence, same task graph — described once as a
compiled-language project with an external planning tool, and once as a scripting
project with none. Different directory layout, different planning provider,
different words for a passing gate, different framework paths, different protected
path. Every field a consumer owns is different, and the envelope must be identical
apart from the paths the two repositories genuinely have.

If this ever fails, some consumer fact has leaked into the runtime, and the leak is
whatever field the diff shows.
"""
from __future__ import annotations

import sys

import _bootstrap  # noqa: F401  (puts the package on sys.path)

from repo_fixture import (  # noqa: E402
    CLOSURE_RECORDED,
    GATES_RECORDED,
    GENERIC,
    PYTHON,
    REVIEW_CLEAN,
    REVIEW_OUTSTANDING,
    RUST,
    TASKS_COMPLETE,
    TASKS_PARTIAL,
    TASKS_READY,
    make_repo,
)
from ariadne.runtime import (  # noqa: E402
    DEV_CLOSE,
    DEV_MERGE,
    DEV_NEW,
    DEV_NEXT,
    HUMAN_GATE_APPROVED,
    evaluate_workflow,
    resolve_repository_state,
)

checks = 0
failures: list[str] = []


def check(condition: object, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


# The four repository states worth comparing: one per workflow's interesting case.
STATES: dict[str, dict[str, object]] = {
    "merged": dict(
        tasks=TASKS_COMPLETE,
        handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
        merge_into_main=True,
    ),
    "ready": dict(tasks=TASKS_READY),
    "in-progress": dict(tasks=TASKS_PARTIAL, handoff_lines=(REVIEW_OUTSTANDING,)),
    "accepted": dict(
        tasks=TASKS_COMPLETE,
        handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
    ),
}

INTENTS = (DEV_NEW, DEV_NEXT, DEV_CLOSE, DEV_MERGE)

# Before comparing anything: every flavour's configuration must actually parse. An
# unparseable one is reported as a fact and not raised — correct fail-closed
# behaviour, and precisely why a broken fixture would otherwise degrade silently
# into "every consumer classifies UNKNOWN", which compares equal to itself.
for flavour in (RUST, PYTHON, GENERIC):
    with make_repo(flavour=flavour, tasks=TASKS_READY) as fixture:
        facts = resolve_repository_state(fixture.root, DEV_MERGE).evidence.facts()
    check(
        not any(fact.startswith("config_unparseable") for fact in facts),
        f"the {flavour.name} fixture writes a configuration the runtime can read",
    )
    check(
        (flavour is GENERIC) or "registered_feature=002-example" in facts,
        f"the {flavour.name} fixture registers its Feature where its layout says",
    )

# The envelope fields that are the decision. `evidence` is deliberately excluded and
# compared separately: it contains repository paths, which two different repositories
# are supposed to differ in. Comparing it verbatim would assert the wrong thing.
VERDICT = ("workflow", "phase", "classification", "decision", "status", "reason_code",
           "next_legal_action", "human_action_required", "protocol_version")


def verdict(decision: object) -> tuple[object, ...]:
    return tuple(getattr(decision, field) for field in VERDICT)


# The one evidence fact two honest consumers may differ in. `changed_paths` is a count
# of files, and the two repositories genuinely contain different files: the one with an
# external planning tool carries that tool's registration and the other does not. Every
# other fact is a judgement about the repository, and a judgement must not vary.
LAYOUT_DEPENDENT = {"changed_paths"}


def portable(facts: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(fact for fact in facts if fact.split("=", 1)[0] not in LAYOUT_DEPENDENT)


for name, knobs in STATES.items():
    for intent in INTENTS:
        envelopes = {}
        evidence = {}
        for flavour in (RUST, PYTHON):
            with make_repo(flavour=flavour, **knobs) as fixture:  # type: ignore[arg-type]
                decision = evaluate_workflow(
                    fixture.root, intent, human_gate=HUMAN_GATE_APPROVED
                )
                state = resolve_repository_state(
                    fixture.root, intent, human_gate=HUMAN_GATE_APPROVED
                )
                envelopes[flavour.name] = verdict(decision)
                evidence[flavour.name] = state.evidence.facts()
        check(
            envelopes[RUST.name] == envelopes[PYTHON.name],
            f"INV-S9 {name}/{intent}: {envelopes[RUST.name]} != {envelopes[PYTHON.name]}",
        )
        check(
            portable(evidence[RUST.name]) == portable(evidence[PYTHON.name]),
            f"INV-S9 {name}/{intent} evidence: "
            f"{portable(evidence[RUST.name])} != {portable(evidence[PYTHON.name])}",
        )

# --- The unconfigured consumer is a third data point ------------------------
# `GENERIC` has no `.ariadne/project.toml` at all. It must still be decided — and it
# must fail closed where a configured repository would have proven something, because
# a repository that declares no framework path cannot prove a change is non-product.
for intent in INTENTS:
    with make_repo(flavour=GENERIC, **STATES["accepted"]) as fixture:  # type: ignore[arg-type]
        bare = evaluate_workflow(fixture.root, intent, human_gate=HUMAN_GATE_APPROVED)
    check(bare.workflow == intent, f"INV-S9 an unconfigured repository still decides {intent}")
    check(
        bare.reason_code != "PROTOCOL_DECISION_INVALID",
        f"INV-S9 an unconfigured repository yields a well-formed envelope for {intent}",
    )

# A configured repository proves NON_PRODUCT on a framework branch; the same branch in
# an unconfigured one cannot. Same runtime, and the difference is entirely the
# consumer's declaration — which is what configurable means.
FRAMEWORK_BRANCH: dict[str, object] = dict(
    branch="framework-branch",
    spec_branch="002-example",
    state_branch="002-example",
    feature_on_main=True,
    workflow_change=True,
    tasks=TASKS_COMPLETE,
    handoff_lines=(REVIEW_CLEAN, GATES_RECORDED, CLOSURE_RECORDED),
)
declared = {}
for flavour in (RUST, PYTHON, GENERIC):
    with make_repo(flavour=flavour, **FRAMEWORK_BRANCH) as fixture:  # type: ignore[arg-type]
        declared[flavour.name] = evaluate_workflow(
            fixture.root, DEV_MERGE, human_gate=HUMAN_GATE_APPROVED
        )
check(
    declared[RUST.name].classification == declared[PYTHON.name].classification == "NON_PRODUCT",
    "INV-S9 two declared framework layouts prove the same classification",
)
check(
    verdict(declared[RUST.name]) == verdict(declared[PYTHON.name]),
    "INV-S9 and therefore reach the same decision",
)
check(
    declared[GENERIC.name].classification == "UNKNOWN",
    "INV-S9 an undeclared layout proves nothing and fails closed",
)

if failures:
    print(f"{len(failures)} FAILED:")
    for failure in failures:
        print(f"  ✗ {failure}")
    raise SystemExit(1)
print(f"consumer neutrality checks passed ({checks} assertions)")
print("INV-S9 verified across consumers; test_runtime_closure.py verifies it across hosts")
