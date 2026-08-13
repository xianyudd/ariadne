#!/usr/bin/env python3
"""Classify the current repository entity for the dev-merge lifecycle guard."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

NON_PRODUCT_PREFIXES = (
    ".agent-sdlc/",
    ".agents/",
    ".claude/",
    ".codex/",
    ".opencode/",
    ".specify/templates/",
)
NON_PRODUCT_FILES = {"AGENTS.md", "CLAUDE.md"}
PROTECTED_PREFIX = ".claude/worktrees/"
TASK_FILES = ("spec.md", "plan.md", "tasks.md")
CHECKOUT_BRANCH_RE = re.compile(r"^\s*(?:[-*]\s*)?Branch:\s*`?([^`\s]+)")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def feature_registration(root: Path) -> tuple[str | None, Path | None]:
    registration = root / ".specify" / "feature.json"
    try:
        data = json.loads(registration.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    directory = data.get("feature_directory")
    if not isinstance(directory, str) or not directory:
        return None, None
    return Path(directory).name, root / directory


def changed_paths(root: Path) -> list[str]:
    """Collect committed, staged, unstaged, and untracked paths.

    Protected worktrees are reported by Git but are deliberately excluded from
    classification; their contents are never read.
    """
    commands = (
        ("diff", "--name-only", "main...HEAD"),
        ("diff", "--cached", "--name-only"),
        ("diff", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    paths: set[str] = set()
    for command in commands:
        try:
            paths.update(path for path in git(root, *command).splitlines() if path)
        except subprocess.CalledProcessError:
            continue
    return sorted(path for path in paths if not path.startswith(PROTECTED_PREFIX))


def active_state_branch(root: Path) -> str | None:
    state_path = root / ".specify" / "memory" / "current-state.md"
    try:
        lines = state_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    in_active_section = False
    for line in lines:
        if line.startswith("## "):
            in_active_section = line == "## Active Feature:"
            continue
        if in_active_section:
            match = CHECKOUT_BRANCH_RE.match(line)
            if match:
                return match.group(1)
    return None


def classify_facts(facts: dict[str, object]) -> str:
    branch = facts.get("branch")
    registered = facts.get("registered_feature")
    spec_branch = facts.get("spec_branch")
    feature_dir_exists = facts.get("feature_dir_exists") is True
    required_artifacts = facts.get("required_artifacts") is True
    current_state_branch = facts.get("current_state_branch")
    changed = facts.get("changed_paths", [])
    if (
        isinstance(branch, str)
        and isinstance(registered, str)
        and isinstance(spec_branch, str)
        and feature_dir_exists
        and required_artifacts
        and branch == registered == spec_branch == current_state_branch
    ):
        return "PRODUCT_FEATURE"

    evidence = [value for value in (registered, spec_branch, current_state_branch) if isinstance(value, str)]
    historical_evidence_is_consistent = bool(evidence) and len(set(evidence)) == 1
    workflow_only = (
        isinstance(changed, list)
        and bool(changed)
        and all(
            isinstance(path, str)
            and (path.startswith(NON_PRODUCT_PREFIXES) or path in NON_PRODUCT_FILES)
            for path in changed
        )
    )
    if (
        isinstance(branch, str)
        and workflow_only
        and historical_evidence_is_consistent
        and evidence[0] != branch
    ):
        return "NON_PRODUCT"
    if (
        isinstance(branch, str)
        and workflow_only
        and not evidence
    ):
        return "NON_PRODUCT"
    return "UNKNOWN"


def classify(root: Path) -> str:
    branch = git(root, "branch", "--show-current")
    registered_name, feature_dir = feature_registration(root)
    spec_branch = None
    if feature_dir is not None and (feature_dir / "spec.md").is_file():
        text = (feature_dir / "spec.md").read_text(encoding="utf-8")
        match = re.search(r"^\*\*Feature Branch\*\*:\s*`?([^`\s]+)", text, re.MULTILINE)
        spec_branch = match.group(1) if match else None
    required_artifacts = bool(
        feature_dir is not None
        and all((feature_dir / name).is_file() for name in TASK_FILES)
    )
    return classify_facts(
        {
            "branch": branch,
            "registered_feature": registered_name,
            "feature_dir_exists": feature_dir is not None and feature_dir.is_dir(),
            "required_artifacts": required_artifacts,
            "spec_branch": spec_branch,
            "current_state_branch": active_state_branch(root),
            "changed_paths": changed_paths(root),
        }
    )


def decision_for_entity(entity: str, lifecycle_state: str | None = None) -> str:
    """Map entity and lifecycle state to the host-independent decision."""
    if entity == "PRODUCT_FEATURE":
        return "CONTINUE" if lifecycle_state == "READY_TO_CLOSE" else "TERMINAL_BLOCKED"
    return {
        "NON_PRODUCT": "TERMINAL_NOT_APPLICABLE",
        "UNKNOWN": "TERMINAL_BLOCKED",
    }[entity]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--lifecycle-state", choices=("IN_PROGRESS", "READY_TO_CLOSE"))
    args = parser.parse_args()
    root = args.root.resolve()
    branch = git(root, "branch", "--show-current")
    entity = classify(root)
    decision = decision_for_entity(entity, args.lifecycle_state)
    status = {
        "PRODUCT_FEATURE": "READY_OR_BLOCKED",
        "NON_PRODUCT": "NOT_APPLICABLE",
        "UNKNOWN": "BLOCKED",
    }[entity]
    print(f"BRANCH {branch}\nCLASSIFICATION {entity}\nDECISION {decision}\nSTATUS {status}")
    if entity == "UNKNOWN":
        print("REASON Unable to establish that current branch is a managed Product Feature.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
