#!/usr/bin/env python3
"""Thin CLI over the canonical runtime's classification and decision path.

Everything this script prints comes from `.agent-sdlc/runtime/`: evidence is
collected once, the state is resolved once, and the decision comes from the one
decision engine.

This script holds no rules of its own. It used to carry a second decision table
(`decision_for_entity`) and a `--lifecycle-state` flag that let a caller inject
the lifecycle state by hand; both are gone. The lifecycle state is derived from
repository evidence, so there is no longer a way to talk the runtime into a
decision the repository does not support.

Reporting only: this prints the envelope, it does not enforce it. Enforcement is
`runtime.TerminalGate`, reached through `runtime.execute_workflow`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.api import evaluate_state  # noqa: E402
from runtime.classification import classify_evidence, classify_facts  # noqa: E402
from runtime.evidence import collect_repository_evidence  # noqa: E402
from runtime.state import DEV_MERGE, WORKFLOW_INTENTS, resolve_repository_state  # noqa: E402

__all__ = ["classify", "classify_facts", "classify_evidence"]


def classify(root: Path) -> str:
    """Classify a repository. Compatibility entry point over the runtime."""
    return classify_evidence(collect_repository_evidence(root))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--workflow", choices=sorted(WORKFLOW_INTENTS), default=DEV_MERGE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state = resolve_repository_state(args.root.resolve(), args.workflow, dry_run=args.dry_run)
    decision = evaluate_state(state)

    print(f"BRANCH {state.evidence.git.branch or 'unavailable'}")
    print(f"CLASSIFICATION {state.entity}")
    print(f"LIFECYCLE {state.lifecycle_state}")
    print(f"WORKFLOW {decision.workflow}")
    print(f"DECISION {decision.decision}")
    print(f"STATUS {decision.status}")
    if decision.reason_code:
        print(f"REASON_CODE {decision.reason_code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
