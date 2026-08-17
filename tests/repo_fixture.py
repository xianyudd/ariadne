#!/usr/bin/env python3
"""Real repository fixtures for runtime tests.

Test support, not runtime code. The runtime derives every state from repository
evidence, so testing it honestly means building actual repositories: real Git
history, a real planning registration, real specification artifacts, and a real
handoff. Nothing here injects a lifecycle state or a decision.

Every fixture has a *flavour*, and that is the load-bearing part. A flavour is a
consumer: its own directory layout, its own planning provider, its own words for a
quality gate having passed. `RUST` keeps its features in `specs/` and records
`cargo test`; `PYTHON` keeps them in `docs/features/` and records `pytest`; `GENERIC`
declares no configuration at all. The runtime is handed no flavour and has no
parameter that could receive one — `tests/test_consumer_neutral.py` runs the same
repository under two flavours and asserts one decision, which is the property the
whole seam exists for.

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

# Review and closure are Ariadne's own vocabulary, recorded the same way by every
# consumer, so these are literal text.
REVIEW_CLEAN = "Review: PASS. BLOCKER: 0. MAJOR: 0. MINOR: 0."
REVIEW_OUTSTANDING = "Review: NEEDS_FIX. BLOCKER: 2. MAJOR: 1. MINOR: 0."
CLOSURE_RECORDED = "/dev-close final acceptance passed; ready for formal closure."


@dataclass(frozen=True)
class GateEvidence:
    """A request for "this repository recorded that its quality gates passed".

    Not a sentence, because there is no such sentence: it is `cargo test passed` in
    one repository and `42 passed` in another, and a test that hardcoded either one
    would be asserting against a consumer instead of against the runtime. A test asks
    for the fact; the flavour supplies its own words for it.
    """

    def __str__(self) -> str:
        return "<gates recorded>"


GATES_RECORDED = GateEvidence()

HandoffLine = str | GateEvidence


@dataclass(frozen=True)
class Flavour:
    """One consumer's facts. Every field here is something only a consumer knows."""

    name: str
    # Planning provider, and where feature directories live.
    planning: str
    spec_dir: str
    # The durable handoff file, and whether the repository declares one at all.
    state_file: str | None
    # A product source file, and one added later to make a product change.
    source: str
    added_source: str
    # Framework paths, and one file under them to touch for a workflow-only change.
    framework_paths: tuple[str, ...]
    framework_files: tuple[str, ...]
    framework_change: str
    # A protected path, exempt from safety judgement but always reported.
    protected_paths: tuple[str, ...]
    protected_change: str
    # What a passing quality gate looks like here, and the markers that find it.
    gate_evidence: str
    gate_markers: tuple[str, ...]
    # Whether the repository has an `.ariadne/project.toml` at all.
    configured: bool = True


RUST = Flavour(
    name="rust",
    planning="speckit",
    spec_dir="specs",
    state_file=".specify/memory/current-state.md",
    source="src/lib.rs",
    added_source="src/feature.rs",
    framework_paths=(".ariadne/", ".claude/", ".agents/", ".specify/templates/"),
    framework_files=("AGENTS.md", "CLAUDE.md"),
    framework_change=".ariadne/notes.md",
    protected_paths=(".claude/worktrees/",),
    protected_change=".claude/worktrees/scratch/notes.txt",
    gate_evidence="cargo test passed; quality gate passed.",
    gate_markers=("cargo test",),
)

PYTHON = Flavour(
    name="python",
    planning="directory",
    spec_dir="docs/features",
    state_file="docs/state.md",
    source="package/core.py",
    added_source="package/feature.py",
    framework_paths=(".ariadne/", ".github/workflows/"),
    framework_files=("AGENTS.md", "CONTRIBUTING.md"),
    framework_change=".ariadne/notes.md",
    protected_paths=(".venv/",),
    protected_change=".venv/scratch/notes.txt",
    gate_evidence="pytest: 42 passed in 1.2s",
    gate_markers=(r"\d+ passed",),
)

# A repository that has never heard of Ariadne. It declares nothing, so nothing can
# be proven non-product and the runtime must fail closed rather than assume.
GENERIC = Flavour(
    name="generic",
    planning="directory",
    spec_dir="specs",
    state_file=None,
    source="main.txt",
    added_source="feature.txt",
    framework_paths=(),
    framework_files=(),
    framework_change="notes.md",
    protected_paths=(),
    protected_change="scratch/notes.txt",
    gate_evidence="gates passed",
    gate_markers=(),
    configured=False,
)

FLAVOURS = {flavour.name: flavour for flavour in (RUST, PYTHON, GENERIC)}


def _quote(items: tuple[str, ...]) -> str:
    """Render a string list as TOML.

    Literal strings, because a gate marker is a regular expression: `\\d+ passed` in a
    basic string is an invalid TOML escape, and a fixture that wrote one would produce
    an unparseable configuration — which the runtime reports as a fact rather than
    raising, so the whole flavour would quietly degrade instead of failing.
    """
    return "[" + ", ".join(f"'{item}'" for item in items) + "]"


def project_toml(flavour: Flavour) -> str:
    """The consumer configuration a flavour describes."""
    state = f'state_file = "{flavour.state_file}"\n' if flavour.state_file else ""
    gates = ""
    if flavour.gate_markers:
        gates = f'\n[[gates]]\nname = "test"\nmarkers = {_quote(flavour.gate_markers)}\n'
    return (
        "[repository]\n"
        f'default_branch = "{DEFAULT_BRANCH}"\n'
        f'spec_dir = "{flavour.spec_dir}"\n'
        f"{state}"
        "\n[repository.framework]\n"
        f"paths = {_quote(flavour.framework_paths)}\n"
        f"files = {_quote(flavour.framework_files)}\n"
        "\n[repository.protected]\n"
        f"paths = {_quote(flavour.protected_paths)}\n"
        "\n[planning]\n"
        f'provider = "{flavour.planning}"\n'
        f"{gates}"
    )


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
    flavour: Flavour = RUST
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


def _handoff(flavour: Flavour, feature: str, branch: str, *lines: HandoffLine) -> str:
    body = "\n".join(
        flavour.gate_evidence if isinstance(line, GateEvidence) else line for line in lines
    )
    return (
        f"# Current state\n\n## Active Feature: {feature}\n\n"
        f"- Branch: `{branch}`\n- Directory: `{flavour.spec_dir}/{feature}`\n\n"
        f"## Evidence\n\n{body}\n"
    )


def make_repo(
    *,
    flavour: Flavour = RUST,
    branch: str = "002-example",
    feature: str | None = "002-example",
    spec_branch: str | None = None,
    state_branch: str | None = None,
    tasks: str | None = TASKS_READY,
    include_plan: bool = True,
    include_spec: bool = True,
    feature_dir_exists: bool = True,
    handoff: bool = True,
    handoff_lines: tuple[HandoffLine, ...] = (),
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
    root = Path(tempfile.mkdtemp(prefix="ariadne-fixture-"))
    fixture = RepoFixture(root=root, branch=branch, feature=feature, flavour=flavour)

    if not git:
        # No repository at all: Git evidence must come back unavailable.
        (root / "README.md").write_text("no git here\n", encoding="utf-8")
        return fixture

    _run(root, "init", "-b", DEFAULT_BRANCH)
    _run(root, "config", "user.email", "fixture@example.invalid")
    _run(root, "config", "user.name", "Fixture")
    _run(root, "config", "commit.gpgsign", "false")

    fixture.write("README.md", "# fixture\n")
    fixture.write(flavour.source, "the original\n")
    if flavour.configured:
        fixture.write(".ariadne/project.toml", project_toml(flavour))

    resolved_spec_branch = branch if spec_branch is None else spec_branch
    resolved_state_branch = branch if state_branch is None else state_branch

    def write_feature() -> None:
        if feature is None:
            return
        directory = f"{flavour.spec_dir}/{feature}"
        if flavour.planning == "speckit":
            fixture.write(".specify/feature.json", '{"feature_directory": "%s"}\n' % directory)
        if feature_dir_exists:
            if include_spec:
                fixture.write(
                    f"{directory}/spec.md",
                    f"# {feature}\n\n**Feature Branch**: `{resolved_spec_branch}`\n",
                )
            if include_plan:
                fixture.write(f"{directory}/plan.md", "# Plan\n")
            if tasks is not None:
                fixture.write(f"{directory}/tasks.md", tasks)
        if handoff and flavour.state_file:
            fixture.write(
                flavour.state_file,
                _handoff(flavour, feature, resolved_state_branch, *handoff_lines),
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
        fixture.write(flavour.added_source, "the addition\n")
    if workflow_change:
        fixture.write(flavour.framework_change, "# workflow change\n")

    fixture.commit("feat: feature artifacts")

    if merge_into_main and branch != DEFAULT_BRANCH:
        _run(root, "switch", DEFAULT_BRANCH)
        _run(root, "merge", "--no-ff", "-m", f"merge {branch}", branch)
        _run(root, "switch", branch)

    if protected_change:
        # A protected path must be exempted from classification and still reported.
        # Created after the commit so it appears as an untracked path.
        path = root / flavour.protected_change
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ignored by policy\n", encoding="utf-8")

    return fixture
