#!/usr/bin/env python3
"""Decision consistency: the Markdown, the fixtures, and the engine agree (§10).

There is one decision policy, and it is `runtime/decision_engine.py`. Markdown is
its specification and the fixtures are its examples — both are meant to describe
the same rules, and neither can be trusted to keep doing so on its own.

So this file does not restate the rules. It reads the tables out of the documents
and out of the fixture files, then runs each row through the engine. A document
that drifts from the code fails here, in either direction: a row the engine
contradicts, a reason code the engine cannot emit, or a lifecycle state the
document forgot.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import _bootstrap  # noqa: F401  (puts the package on sys.path)

ROOT = _bootstrap.ROOT
PACKAGE = _bootstrap.SRC / "ariadne"

import state_fixture as sf  # noqa: E402
from ariadne.runtime import decision_engine  # noqa: E402
from ariadne.runtime.classification import CLASSIFICATIONS  # noqa: E402
from ariadne.runtime.decision import (  # noqa: E402
    CONTINUE,
    DECISIONS,
    PROTOCOL_DECISION_INVALID,
    PROTOCOL_VERSION,
    STOP,
    TERMINAL_NOT_APPLICABLE,
)
from ariadne.runtime.decision_engine import decide  # noqa: E402
from ariadne.runtime.lifecycle import (  # noqa: E402
    LEGAL_TRANSITIONS,
    LIFECYCLE_STATES,
    READY_TO_CLOSE,
)
from ariadne.runtime.state import (  # noqa: E402
    DEV_MERGE,
    HUMAN_GATE_APPROVED,
    REVIEW_RESOLVED,
    WORKFLOW_INTENTS,
)

CONTRACTS = PACKAGE / "contracts"
WORKFLOWS = PACKAGE / "workflows"
FIXTURES = _bootstrap.HERE / "fixtures"
REASON_DOC = CONTRACTS / "reason-codes.md"

checks = 0


def check(condition: object, label: str) -> None:
    global checks
    assert condition, label
    checks += 1


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def blocks(text: str) -> list[str]:
    """Every fenced `text` block in a document."""
    return re.findall(r"```text\n(.*?)```", text, re.S)


def merge_state(classification: str, lifecycle: str):
    """The dev-merge state the documented tables are written about.

    Everything not named by a table row is set to its permitting value, so a row
    that fails here fails on the fact it names rather than on a side condition.
    """
    return sf.state(
        workflow_intent=DEV_MERGE,
        entity=classification,
        lifecycle=lifecycle,
        review=REVIEW_RESOLVED,
        human_gate=HUMAN_GATE_APPROVED,
        dag=sf.dag_state(completed=True),
    )


# --- 1: the `/dev-merge` mapping in Core -------------------------------------
# `CLASSIFICATION [+ LIFECYCLE] → [DECISION ]VALUE`, as written in the documents.
ROW = re.compile(
    r"^(?P<classification>[A-Z_]+)(?:\s*\+\s*(?P<lifecycle>[A-Z_]+))?"
    r"\s*→\s*(?:DECISION\s+)?(?P<decision>CONTINUE|TERMINAL_[A-Z_]+)\s*$"
)


def mapping_rows(text: str, source: str) -> dict[tuple[str, str | None], str]:
    """Parse every classification → decision row in a document."""
    rows: dict[tuple[str, str | None], str] = {}
    for block in blocks(text):
        for line in block.splitlines():
            match = ROW.match(line.strip())
            if match is None:
                continue
            classification = match["classification"]
            if classification not in CLASSIFICATIONS:
                continue
            key = (classification, match["lifecycle"])
            check(key not in rows, f"{source} states {key} once")
            rows[key] = match["decision"]
    return rows


def assert_rows(rows: dict[tuple[str, str | None], str], source: str) -> None:
    """Run every documented row through the engine."""
    check(len(rows) == 4, f"{source} declares the four documented rows, found {len(rows)}")
    for (classification, lifecycle), documented in sorted(rows.items()):
        # A row with no lifecycle is a claim about every lifecycle, so it is
        # checked against all of them rather than against a chosen one.
        states = [lifecycle] if lifecycle else list(LIFECYCLE_STATES)
        for state in states:
            decision = decide(merge_state(classification, state))
            check(
                decision.decision == documented,
                f"{source} {classification}+{state} → {documented}, engine says {decision.decision}",
            )
            check(
                (decision.next_legal_action == STOP) == (documented != CONTINUE),
                f"{source} {classification}+{state} successor agrees with its decision",
            )


contract = read(CONTRACTS / "terminal-contract.md")
assert_rows(mapping_rows(contract, "terminal-contract.md"), "terminal-contract.md")

merge_doc = read(WORKFLOWS / "dev-merge.md")
assert_rows(mapping_rows(merge_doc, "dev-merge.md"), "dev-merge.md")

# The overview restates the mapping for a reader; it is bound here so it cannot
# become a second, quietly different version of it.
overview = read(ROOT / "README.md")
assert_rows(mapping_rows(overview, "README.md"), "README.md")

tables = {
    "terminal-contract.md": mapping_rows(contract, "terminal-contract.md"),
    "dev-merge.md": mapping_rows(merge_doc, "dev-merge.md"),
    "README.md": mapping_rows(overview, "README.md"),
}
check(
    len({tuple(sorted(rows.items())) for rows in tables.values()}) == 1,
    f"every document states one table: {tables}",
)

# The documented status mapping is the engine's status mapping.
STATUS_ROW = re.compile(r"^(TERMINAL_[A-Z_]+)\s*→\s*status\s+([A-Z_]+)\s*$")
status_rows = {
    match[1]: match[2]
    for block in blocks(contract)
    for line in block.splitlines()
    if (match := STATUS_ROW.match(line.strip()))
}
check(len(status_rows) == 2, f"Core documents two terminal statuses, found {len(status_rows)}")
for decision_value, documented_status in sorted(status_rows.items()):
    classification = "NON_PRODUCT" if decision_value == TERMINAL_NOT_APPLICABLE else "UNKNOWN"
    produced = decide(merge_state(classification, READY_TO_CLOSE))
    check(produced.decision == decision_value, f"status row {decision_value} is reachable")
    check(
        produced.status == documented_status,
        f"status row {decision_value} → {documented_status}, engine says {produced.status}",
    )

# --- 2: the terminal-contract fixtures --------------------------------------
FIELD = re.compile(r"^(Classification|Lifecycle|Expected decision|Expected status|Expected next step):\s*(\S+)\s*$")

fixture_files = sorted(FIXTURES.glob("terminal-*.md"))
check(len(fixture_files) == 4, f"four terminal fixtures exist, found {len(fixture_files)}")
for path in fixture_files:
    fields = {
        match[1]: match[2]
        for line in read(path).splitlines()
        if (match := FIELD.match(line.strip()))
    }
    classification = fields["Classification"]
    lifecycle = fields.get("Lifecycle")
    check(classification in CLASSIFICATIONS, f"{path.name} names a real classification")
    check(fields["Expected decision"] in DECISIONS, f"{path.name} names a real decision")
    for state in [lifecycle] if lifecycle else list(LIFECYCLE_STATES):
        decision = decide(merge_state(classification, state))
        check(
            decision.decision == fields["Expected decision"],
            f"{path.name} expects {fields['Expected decision']}, engine says {decision.decision}",
        )
        check(
            decision.status == fields["Expected status"],
            f"{path.name} expects status {fields['Expected status']}, engine says {decision.status}",
        )
        # `NORMAL_FLOW` is the documents' word for "the workflow's own next phase".
        expected_stop = fields["Expected next step"] == STOP
        check(
            (decision.next_legal_action == STOP) == expected_stop,
            f"{path.name} next step disagrees with the engine",
        )
        if not expected_stop:
            check(
                fields["Expected next step"] == "NORMAL_FLOW",
                f"{path.name} non-stop successor is the documented token",
            )

# The one report sentence the workflow document quotes verbatim must be the one the
# engine actually emits, or the document is describing a report nobody produces.
unknown_evidence = decide(merge_state("UNKNOWN", READY_TO_CLOSE)).evidence
quoted = [line for line in unknown_evidence if line in merge_doc]
check(
    any(line.endswith("managed Product Feature.") for line in quoted),
    f"dev-merge.md quotes the engine's own UNKNOWN evidence line, found {quoted}",
)

# --- 2b: the scenario index --------------------------------------------------
# `lifecycle-scenarios.md` states each case's decision, status, and successor on one
# line. It is the same contract as the fixtures, written for a reader, so it is run
# through the engine too rather than trusted to have stayed in step.
SCENARIO = re.compile(
    r"^Case (?P<case>[A-Z]): (?P<classification>[A-Z_]+)(?:\s*\+\s*(?P<lifecycle>[A-Z_]+))?"
    r"\s*→\s*(?P<decision>CONTINUE|TERMINAL_[A-Z_]+)"
    r"\s*→\s*(?P<status>[A-Z_]+)\s*→\s*(?P<successor>[A-Z_]+)\s*$"
)
scenarios = [
    match
    for block in blocks(read(FIXTURES.parent / "lifecycle-scenarios.md"))
    for line in block.splitlines()
    if (match := SCENARIO.match(line.strip()))
]
check(len(scenarios) == 4, f"four scenarios are stated, found {len(scenarios)}")
check(len({match["case"] for match in scenarios}) == 4, "each scenario has its own label")
for match in scenarios:
    case = f"scenario {match['case']}"
    check(match["classification"] in CLASSIFICATIONS, f"{case} names a real classification")
    for state in [match["lifecycle"]] if match["lifecycle"] else list(LIFECYCLE_STATES):
        decision = decide(merge_state(match["classification"], state))
        check(
            decision.decision == match["decision"],
            f"{case} at {state} expects {match['decision']}, engine says {decision.decision}",
        )
        check(
            decision.status == match["status"],
            f"{case} at {state} expects status {match['status']}, engine says {decision.status}",
        )
        expected_stop = match["successor"] == STOP
        check(
            (decision.next_legal_action == STOP) == expected_stop,
            f"{case} at {state} successor disagrees with the engine",
        )
        if not expected_stop:
            check(match["successor"] == "NORMAL_FLOW", f"{case} uses the documented successor token")

# --- 3: the reason-code vocabulary -------------------------------------------
# The reason-code catalogue is a shipped contract, so a consumer can read it with
# `ariadne doc reason-codes` rather than needing this checkout. Every code the engine
# can emit is documented there, and the catalogue names nothing the engine cannot.
reason_doc = read(REASON_DOC)
catalogue = blocks(reason_doc)
check(len(catalogue) == 1, f"the catalogue is one block, found {len(catalogue)}")
declared = {
    token
    for line in catalogue[0].splitlines()
    if (token := line.strip().split()[0] if line.strip() else "")
    and re.fullmatch(r"[A-Z][A-Z_]{4,}", token)
}

missing = sorted(decision_engine.REASON_CODES - declared)
check(not missing, f"every reason code is documented: missing {missing}")

unknown = sorted(declared - decision_engine.REASON_CODES - {PROTOCOL_DECISION_INVALID})
check(not unknown, f"the catalogue declares no code the engine cannot emit: {unknown}")
check(
    not any(code.startswith("PROTOCOL_") for code in decision_engine.REASON_CODES),
    "no workflow reason code uses the reserved framework prefix",
)

# --- 4: the lifecycle state machine ----------------------------------------
lifecycle_doc = read(CONTRACTS / "lifecycle.md")
machine = None
for block in blocks(lifecycle_doc):
    line = block.strip()
    if "→" in line and line.split(" → ")[0] == LIFECYCLE_STATES[0]:
        machine = [state.strip() for state in line.split("→")]
        break
check(machine is not None, "Core documents the lifecycle state machine")
assert machine is not None
check(tuple(machine) == LIFECYCLE_STATES, f"documented states {machine} != {LIFECYCLE_STATES}")

documented_transitions = {
    (source, target) for source, target in zip(machine, machine[1:])
}
engine_transitions = {
    (source, target) for source, targets in LEGAL_TRANSITIONS.items() for target in targets
}
check(
    documented_transitions == engine_transitions,
    f"documented transitions {sorted(documented_transitions)} != {sorted(engine_transitions)}",
)
for state in LIFECYCLE_STATES:
    check(f"`{state}`" in lifecycle_doc, f"Core describes {state}")

# --- 5: the envelope vocabulary --------------------------------------------
envelope_doc = read(CONTRACTS / "decision-envelope.md")
declared_decisions = {
    line.strip()
    for block in blocks(envelope_doc)
    for line in block.splitlines()
    if line.strip() in DECISIONS
}
check(declared_decisions == set(DECISIONS), f"Core declares every decision value: {declared_decisions}")
check(f"`{PROTOCOL_VERSION}`" in envelope_doc, "Core states the current envelope version")
check(PROTOCOL_DECISION_INVALID in envelope_doc, "Core declares the reserved rejection code")

contract_decisions = {
    line.strip()
    for block in blocks(contract)
    for line in block.splitlines()
    if line.strip() in DECISIONS
}
check(contract_decisions == set(DECISIONS), "the terminal contract declares every decision value")

# --- 6: the per-workflow decision tables -----------------------------------
# Each workflow document states the outcomes its own entry point produces for a
# proven Product Feature. Rows are `LIFECYCLE → DECISION[:REASON_CODE]`, so a
# document cannot claim an outcome the engine will not produce.
#
# A table also declares which task graph it is about, because lifecycle alone does
# not determine every outcome: `/dev-next` has nothing to select from a complete
# graph, so a table written about one would say nothing about lifecycle at all.
WORKFLOW_ROW = re.compile(
    r"^(?P<lifecycle>[A-Z_]+)\s*→\s*(?P<decision>CONTINUE|TERMINAL_[A-Z_]+)"
    r"(?::(?P<reason>[A-Z_]+))?\s*$"
)
GRAPH_DECLARATION = re.compile(r"^Task graph:\s*(complete|unfinished)\s*$", re.M)
GRAPHS = {"complete": sf.dag_state(completed=True), "unfinished": sf.dag_state()}
INTENT_DOCS = {
    "DEV_NEW": "dev-new.md",
    "DEV_NEXT": "dev-next.md",
    "DEV_CLOSE": "dev-close.md",
    "DEV_MERGE": "dev-merge.md",
}
check(set(INTENT_DOCS) == set(WORKFLOW_INTENTS), "every workflow intent has a document")

for intent, filename in sorted(INTENT_DOCS.items()):
    text = read(WORKFLOWS / filename)
    section = re.search(r"## Decision table\n(.*?)(?=\n## |\Z)", text, re.S)
    check(section is not None, f"{filename} has a decision table")
    assert section is not None
    graph = GRAPH_DECLARATION.search(section[1])
    check(graph is not None, f"{filename} declares which task graph its table is about")
    assert graph is not None
    rows = [
        match
        for block in blocks(section[1])
        for line in block.splitlines()
        if (match := WORKFLOW_ROW.match(line.strip()))
    ]
    check(rows, f"{filename} decision table has rows")
    seen_states = set()
    for match in rows:
        lifecycle = match["lifecycle"]
        check(lifecycle in LIFECYCLE_STATES, f"{filename} row names a real state: {lifecycle}")
        seen_states.add(lifecycle)
        state = sf.state(
            workflow_intent=intent,
            entity="PRODUCT_FEATURE",
            lifecycle=lifecycle,
            review=REVIEW_RESOLVED,
            human_gate=HUMAN_GATE_APPROVED,
            dag=GRAPHS[graph[1]],
        )
        decision = decide(state)
        check(
            decision.decision == match["decision"],
            f"{filename} {lifecycle} → {match['decision']}, engine says {decision.decision}",
        )
        check(
            decision.reason_code == match["reason"],
            f"{filename} {lifecycle} reason {match['reason']}, engine says {decision.reason_code}",
        )
        if decision.decision != CONTINUE:
            check(match["reason"] is not None, f"{filename} {lifecycle} states its reason code")
    check(
        seen_states == set(LIFECYCLE_STATES),
        f"{filename} covers every lifecycle state, missing {sorted(set(LIFECYCLE_STATES) - seen_states)}",
    )

print(f"decision consistency checks passed ({checks} assertions)")
