#!/usr/bin/env python3
"""Real repository fixtures for runtime tests.

Test support, not runtime code. The runtime derives every state from repository
evidence, so testing it honestly means building actual repositories: real Git
history, a real `.specify/feature.json`, real `spec.md`/`plan.md`/`tasks.md`, and a
real handoff. Nothing here injects a lifecycle state or a decision.

Each fixture lives in a fresh temporary directory and is removed by `cleanup()`.
No fixture touches the repository under test.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BRANCH = "main"

TASKS_READY = """# Tasks

- [ ] T001 Add the model
  Depends:
- [ ] T002 Add the view
  Depends: T001
- [ ] T003 Wire it up
  Depends: T002
"""

TASKS_PARTIAL = """# Tasks

- [x] T001 Add the model
  Depends:
- [ ] T002 Add the view
  Depends: T001
- [ ] T003 Wire it up
  Depends: T002
"""

TASKS_COMPLETE = """# Tasks

- [x] T001 Add the model
  Depends:
- [x] T002 Add the view
  Depends: T001
- [x] T003 Wire it up
  Depends: T002
"""

TASKS_CYCLE = """# Tasks

- [ ] T001 First
  Depends: T002
- [ ] T002 Second
  Depends: T001
"""

TASKS_LEGACY = """# Tasks

- [ ] T001 First
- [ ] T002 Second
"""

REVIEW_CLEAN = "Review: PASS. BLOCKER: 0. MAJOR: 0. MINOR: 0."
REVIEW_OUTSTANDING = "Review: NEEDS_FIX. BLOCKER: 2. MAJOR: 1. MINOR: 0."
GATES_RECORDED = "cargo test passed; quality gate passed."
CLOSURE_RECORDED = "/dev-close final acceptance passed; ready for formal closure."


def _run(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@dataclass
class RepoFixture:
    """A disposable repository on disk."""

    root: Path
    branch: str
    feature: str | None
    created: list[str] = field(default_factory=list)

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.created.append(relative)
        return path

    def commit(self, message: str) -> None:
        """Commit whatever is present. A clean tree is left alone."""
        _run(self.root, "add", "-A")
        staged = subprocess.run(
            ["git", "-C", str(self.root), "diff", "--cached", "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if staged.returncode != 0:
            _run(self.root, "commit", "-m", message)

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> RepoFixture:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.cleanup()


def _handoff(feature: str, branch: str, *lines: str) -> str:
    body = "\n".join(lines)
    return (
        f"# Current state\n\n## Active Feature: {feature}\n\n"
        f"- Branch: `{branch}`\n- Directory: `specs/{feature}`\n\n"
        f"## Evidence\n\n{body}\n"
    )


def make_repo(
    *,
    branch: str = "002-example",
    feature: str | None = "002-example",
    spec_branch: str | None = None,
    state_branch: str | None = None,
    tasks: str | None = TASKS_READY,
    include_plan: bool = True,
    include_spec: bool = True,
    feature_dir_exists: bool = True,
    handoff: bool = True,
    handoff_lines: tuple[str, ...] = (),
    feature_on_main: bool = False,
    product_change: bool = False,
    workflow_change: bool = False,
    protected_change: bool = False,
    merge_into_main: bool = False,
    git: bool = True,
) -> RepoFixture:
    """Build a repository whose evidence produces a specific real state.

    Every knob here is a repository fact. There is deliberately no parameter for a
    lifecycle state, a classification, or a decision: those are derived.
    """
    root = Path(tempfile.mkdtemp(prefix="agent-sdlc-fixture-"))
    fixture = RepoFixture(root=root, branch=branch, feature=feature)

    if not git:
        # No repository at all: Git evidence must come back unavailable.
        (root / "README.md").write_text("no git here\n", encoding="utf-8")
        return fixture

    _run(root, "init", "-b", DEFAULT_BRANCH)
    _run(root, "config", "user.email", "fixture@example.invalid")
    _run(root, "config", "user.name", "Fixture")
    _run(root, "config", "commit.gpgsign", "false")

    fixture.write("README.md", "# fixture\n")
    fixture.write("src/lib.rs", "pub fn base() {}\n")

    resolved_spec_branch = branch if spec_branch is None else spec_branch
    resolved_state_branch = branch if state_branch is None else state_branch

    def write_feature() -> None:
        if feature is None:
            return
        fixture.write(".specify/feature.json", '{"feature_directory": "specs/%s"}\n' % feature)
        if feature_dir_exists:
            if include_spec:
                fixture.write(
                    f"specs/{feature}/spec.md",
                    f"# {feature}\n\n**Feature Branch**: `{resolved_spec_branch}`\n",
                )
            if include_plan:
                fixture.write(f"specs/{feature}/plan.md", "# Plan\n")
            if tasks is not None:
                fixture.write(f"specs/{feature}/tasks.md", tasks)
        if handoff:
            fixture.write(
                ".specify/memory/current-state.md",
                _handoff(feature, resolved_state_branch, *handoff_lines),
            )

    if feature_on_main:
        # The Feature already exists on the default branch, so a later branch that
        # only touches workflow paths carries no Product Feature changes of its own.
        write_feature()
    fixture.commit("chore: base")

    if branch != DEFAULT_BRANCH:
        _run(root, "switch", "-c", branch)

    if not feature_on_main:
        write_feature()

    if product_change:
        fixture.write("src/feature.rs", "pub fn added() {}\n")
    if workflow_change:
        fixture.write(".agent-sdlc/core/notes.md", "# workflow change\n")

    fixture.commit("feat: feature artifacts")

    if merge_into_main and branch != DEFAULT_BRANCH:
        _run(root, "switch", DEFAULT_BRANCH)
        _run(root, "merge", "--no-ff", "-m", f"merge {branch}", branch)
        _run(root, "switch", branch)

    if protected_change:
        # A protected worktree path must be exempted from classification and still
        # reported. Created after the commit so it appears as an untracked path.
        protected = root / ".claude" / "worktrees" / "scratch"
        protected.mkdir(parents=True, exist_ok=True)
        (protected / "notes.txt").write_text("ignored by policy\n", encoding="utf-8")

    return fixture
