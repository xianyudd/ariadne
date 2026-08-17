"""Repository Evidence layer for the Ariadne runtime.

This layer answers exactly one question: *what are the repository facts?* It reads
Git, the registered Feature, specification artifacts, the task graph, and the
recorded review/gate/closure evidence, and returns structured data.

It holds no policy. It does not classify an entity, resolve a lifecycle state,
decide anything, or know a workflow's name. Anything shaped like "therefore X is
allowed" belongs in `lifecycle.py` or `decision_engine.py`.

It also holds no repository. Which paths are framework rather than product, where
specifications live, which planning tool registers a Feature, and what a quality
gate is called are facts about a consumer, and they arrive through `ProjectConfig`
and the integrations it names. There is no path literal and no product vocabulary
in this file: given the same configuration, this collector reads a compiled-language
repository, a scripting-language one, and an empty one the same way.

Facts are collected once per invocation and consumed everywhere, so the classifier,
the lifecycle resolver, the decision engine and the gate cannot each read a
different version of the repository.

Standard library only; no host tool, model, provider, or product is referenced.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field, replace
from pathlib import Path

from ..config import DEFAULT_CONFIG, ProjectConfig, load_project_config
from ..dag.tasks import DagState, missing_dag, resolve_dag
from ..integrations.gates import GateResults, resolve_gates

_SPEC_BRANCH_RE = re.compile(r"^\*\*Feature Branch\*\*:\s*`?([^`\s]+)", re.MULTILINE)
_STATE_BRANCH_RE = re.compile(r"^\s*(?:[-*]\s*)?Branch:\s*`?([^`\s]+)")
_ACTIVE_HEADING = "## Active Feature:"

# Recorded-evidence markers in the durable handoff. These are Ariadne's own
# vocabulary — `BLOCKER` comes from the review contract, `READY_TO_CLOSE` from the
# lifecycle, `/dev-close` from the workflow set — so they belong to the framework,
# unlike a quality gate's markers, which belong to the consumer. The handoff is
# evidence, never authority (`contracts/state-contract.md`): these are read as
# facts about what was recorded, not as permission.
_REVIEW_RESOLVED_RE = re.compile(r"BLOCKER[:\s]+0", re.IGNORECASE)
_REVIEW_OUTSTANDING_RE = re.compile(r"BLOCKER[:\s]+([1-9]\d*)", re.IGNORECASE)
_CLOSURE_RE = re.compile(
    r"/dev-close.*(?:final acceptance passed|passed)|ready for formal closure|READY[ _]TO[ _]CLOSE",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GitEvidence:
    """Observed Git facts. `available` is false when Git could not be queried.

    Two merge facts are recorded because they answer different questions.
    `merged_into_default` is about the checked-out branch; `feature_merged_into_default`
    is about the registered Feature's own branch, which is what the Feature's
    lifecycle depends on and which may not be the branch in hand. Either is `None`
    when Git cannot answer it.
    """

    available: bool
    branch: str | None
    head: str | None
    changed_paths: tuple[str, ...]
    protected_paths: tuple[str, ...]
    tracked_dirty: bool
    merged_into_default: bool | None
    default_branch: str
    feature_branch: str | None = None
    feature_merged_into_default: bool | None = None


@dataclass(frozen=True)
class FeatureEvidence:
    """Observed Feature registration and specification artifacts."""

    registered_name: str | None
    directory: Path | None
    directory_exists: bool
    required_artifacts: bool
    spec_branch: str | None
    tasks_path: Path | None


@dataclass(frozen=True)
class RecordedEvidence:
    """Evidence recorded in the durable handoff, read as fact, not authority."""

    state_branch: str | None
    active_feature: str | None
    review_resolved: bool
    review_outstanding: bool
    gates: GateResults
    closure_recorded: bool

    @property
    def quality_gates_recorded(self) -> bool:
        """Whether recorded evidence proves a declared quality gate passed.

        The runtime asks this one question and never asks which gate, which command
        produced it, or what language it belongs to.
        """
        return self.gates.recorded


@dataclass(frozen=True)
class RepositoryEvidence:
    """Every repository fact the runtime is allowed to reason from."""

    root: Path
    git: GitEvidence
    feature: FeatureEvidence
    recorded: RecordedEvidence
    dag: DagState
    config: ProjectConfig = DEFAULT_CONFIG
    notes: tuple[str, ...] = field(default=())

    @property
    def branch(self) -> str | None:
        return self.git.branch

    def facts(self) -> tuple[str, ...]:
        """A deterministic, ordered rendering of the facts a decision may cite.

        The order is fixed so the same repository state produces byte-identical
        evidence on every host.
        """
        items = [
            f"branch={self.git.branch or '-'}",
            f"registered_feature={self.feature.registered_name or '-'}",
            f"feature_dir_exists={_flag(self.feature.directory_exists)}",
            f"required_artifacts={_flag(self.feature.required_artifacts)}",
            f"spec_branch={self.feature.spec_branch or '-'}",
            f"state_branch={self.recorded.state_branch or '-'}",
            f"changed_paths={len(self.git.changed_paths)}",
            f"protected_paths={len(self.git.protected_paths)}",
            f"dag_status={self.dag.status}",
            f"dag_tasks={self.dag.total}",
            f"dag_ready={','.join(self.dag.ready) or '-'}",
            f"dag_blocked={','.join(self.dag.blocked) or '-'}",
            f"dag_legacy={_flag(self.dag.legacy)}",
            f"review_resolved={_flag(self.recorded.review_resolved)}",
            f"review_outstanding={_flag(self.recorded.review_outstanding)}",
            f"quality_gates_recorded={_flag(self.recorded.quality_gates_recorded)}",
            f"closure_recorded={_flag(self.recorded.closure_recorded)}",
            f"merged_into_{self.git.default_branch}={_tristate(self.git.merged_into_default)}",
            f"feature_merged_into_{self.git.default_branch}="
            f"{_tristate(self.git.feature_merged_into_default)}",
        ]
        items.extend(self.notes)
        return tuple(items)

    def detail(self) -> tuple[str, ...]:
        """The facts, plus how this repository was configured and read.

        Reports show this; decisions cite `facts()`. Keeping them apart means adding
        an integration cannot change the evidence a decision rests on.
        """
        return (*self.facts(), *self.config.facts(), *self.recorded.gates.facts())


def _flag(value: bool) -> str:
    return "yes" if value else "no"


def _tristate(value: bool | None) -> str:
    return "unknown" if value is None else _flag(value)


def _git(root: Path, *args: str) -> str | None:
    """Run a read-only Git command, or return None when it cannot be answered."""
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, OSError):
        return None


def _is_ancestor(root: Path, ref: str, target: str) -> bool | None:
    """Whether `ref` is an ancestor of `target`, or None when unanswerable.

    Both refs must resolve. A deleted Feature branch is a normal post-merge state,
    so its absence is reported as unknown rather than as "not merged".
    """
    for name in (ref, target):
        if _git(root, "rev-parse", "--verify", name) is None:
            return None
    probe = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ref, target],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode in (0, 1):
        return probe.returncode == 0
    return None


def collect_git_evidence(
    root: Path,
    *,
    config: ProjectConfig = DEFAULT_CONFIG,
    feature_branch: str | None = None,
) -> GitEvidence:
    """Collect Git facts.

    Protected paths are separated out rather than dropped: a consumer declares them
    to be exempted *and reported* (`contracts/git-policy.md`), and their contents are
    never read. Which paths those are is the consumer's declaration, not this file's.
    """
    default_branch = config.default_branch
    protected_prefixes = tuple(config.protected_paths)
    branch = _git(root, "branch", "--show-current")
    if branch is None:
        return GitEvidence(
            available=False,
            branch=None,
            head=None,
            changed_paths=(),
            protected_paths=(),
            tracked_dirty=False,
            merged_into_default=None,
            default_branch=default_branch,
            feature_branch=feature_branch,
            feature_merged_into_default=None,
        )
    head = _git(root, "rev-parse", "HEAD")

    commands = (
        ("diff", "--name-only", f"{default_branch}...HEAD"),
        ("diff", "--cached", "--name-only"),
        ("diff", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    observed: set[str] = set()
    for command in commands:
        output = _git(root, *command)
        if output:
            observed.update(path for path in output.splitlines() if path)

    def is_protected(path: str) -> bool:
        return bool(protected_prefixes) and path.startswith(protected_prefixes)

    protected = sorted(path for path in observed if is_protected(path))
    changed = sorted(path for path in observed if not is_protected(path))

    tracked_status = _git(root, "status", "--porcelain", "--untracked-files=no")
    tracked_dirty = bool(tracked_status)

    merged: bool | None = None
    if branch and branch != default_branch:
        merged = _is_ancestor(root, branch, default_branch)

    feature_merged: bool | None = None
    if feature_branch:
        if feature_branch == default_branch:
            feature_merged = True
        elif feature_branch == branch:
            feature_merged = merged
        else:
            feature_merged = _is_ancestor(root, feature_branch, default_branch)

    return GitEvidence(
        available=True,
        branch=branch or None,
        head=head,
        changed_paths=tuple(changed),
        protected_paths=tuple(protected),
        tracked_dirty=tracked_dirty,
        merged_into_default=merged,
        default_branch=default_branch,
        feature_branch=feature_branch,
        feature_merged_into_default=feature_merged,
    )


def collect_feature_evidence(
    root: Path,
    *,
    config: ProjectConfig = DEFAULT_CONFIG,
    branch: str | None = None,
) -> FeatureEvidence:
    """Collect the registered Feature and its specification artifacts.

    Which registration to read is the planning provider's business; what the
    artifacts are called is configuration. This function knows only that a Feature
    is a directory containing declared artifacts.
    """
    registration = config.planning().registered_feature(root, branch)
    registered_name = registration.name if registration is not None else None
    directory = registration.directory if registration is not None else None

    spec_branch: str | None = None
    required = False
    tasks_path: Path | None = None
    if directory is not None:
        spec_path = directory / "spec.md"
        if spec_path.is_file():
            match = _SPEC_BRANCH_RE.search(spec_path.read_text(encoding="utf-8"))
            spec_branch = match.group(1) if match else None
        required = all((directory / name).is_file() for name in config.required_artifacts)
        candidate = directory / config.tasks_file
        tasks_path = candidate if candidate.is_file() else None

    return FeatureEvidence(
        registered_name=registered_name,
        directory=directory,
        directory_exists=directory is not None and directory.is_dir(),
        required_artifacts=required,
        spec_branch=spec_branch,
        tasks_path=tasks_path,
    )


def collect_recorded_evidence(
    root: Path,
    *,
    config: ProjectConfig = DEFAULT_CONFIG,
) -> RecordedEvidence:
    """Read the durable handoff for recorded review/gate/closure evidence.

    A repository that declares no handoff has no recorded evidence — which is not
    the same as recorded failure, and the runtime already fails closed on it.
    """
    empty = RecordedEvidence(
        state_branch=None,
        active_feature=None,
        review_resolved=False,
        review_outstanding=False,
        gates=resolve_gates(None, config.gates),
        closure_recorded=False,
    )
    if not config.state_file:
        return empty
    try:
        text = (root / config.state_file).read_text(encoding="utf-8")
    except OSError:
        return empty

    state_branch: str | None = None
    active_feature: str | None = None
    in_active_section = False
    for line in text.splitlines():
        if line.startswith("## "):
            in_active_section = line.startswith(_ACTIVE_HEADING)
            if in_active_section:
                label = line[len(_ACTIVE_HEADING) :].strip()
                active_feature = label or None
            continue
        if in_active_section and state_branch is None:
            match = _STATE_BRANCH_RE.match(line)
            if match:
                state_branch = match.group(1)

    return RecordedEvidence(
        state_branch=state_branch,
        active_feature=active_feature,
        review_resolved=bool(_REVIEW_RESOLVED_RE.search(text)),
        review_outstanding=bool(_REVIEW_OUTSTANDING_RE.search(text)),
        gates=resolve_gates(text, config.gates),
        closure_recorded=bool(_CLOSURE_RE.search(text)),
    )


def collect_repository_evidence(
    root: Path,
    *,
    config: ProjectConfig | None = None,
    default_branch: str | None = None,
) -> RepositoryEvidence:
    """Collect every repository fact once.

    The result is the sole input to state resolution and decision-making, so no
    later layer needs to re-read the repository. Configuration is loaded from the
    repository unless a caller supplies it, and is carried on the result so a report
    can show which configuration a decision was made under.
    """
    root = Path(root)
    if config is None:
        config = load_project_config(root)
    if default_branch is not None and default_branch != config.default_branch:
        config = replace(config, default_branch=default_branch)

    branch = _git(root, "branch", "--show-current") or None
    feature = collect_feature_evidence(root, config=config, branch=branch)
    # The Feature's own branch is what its lifecycle depends on, so it is resolved
    # before the remaining Git facts rather than inferred from the branch in hand.
    git = collect_git_evidence(
        root,
        config=config,
        feature_branch=feature.spec_branch or feature.registered_name,
    )
    recorded = collect_recorded_evidence(root, config=config)

    if feature.tasks_path is not None:
        dag = resolve_dag(feature.tasks_path)
    else:
        dag = missing_dag("no registered Feature tasks file")

    notes: list[str] = []
    if not git.available:
        notes.append("git_unavailable=yes")
    notes.extend(config.notes)
    # A gate the consumer declared but wrote unusably proves nothing, and a report
    # that hid it would look like a repository with no gates.
    if recorded.gates.errors:
        notes.append(f"gate_markers_unusable={len(recorded.gates.errors)}")
    return RepositoryEvidence(
        root=root,
        git=git,
        feature=feature,
        recorded=recorded,
        dag=dag,
        config=config,
        notes=tuple(notes),
    )


def workflow_only_changes(evidence: RepositoryEvidence) -> bool:
    """Whether every changed path is a declared framework path.

    This is a fact about paths, not a classification: the classifier decides what it
    means. With nothing declared, nothing qualifies — a repository that has not said
    which paths are framework work cannot have framework-only changes proven.
    """
    changed = evidence.git.changed_paths
    prefixes = tuple(evidence.config.framework_paths)
    files = frozenset(evidence.config.framework_files)
    if not changed or not (prefixes or files):
        return False
    return all(
        (bool(prefixes) and path.startswith(prefixes)) or path in files for path in changed
    )
