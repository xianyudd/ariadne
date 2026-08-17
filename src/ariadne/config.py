"""Consumer configuration: the facts about *this* repository, and nothing else.

Ariadne's kernel is a set of invariants; a repository is a set of facts. This module
is the boundary between them. Everything here is something only the consumer can
know — where its specifications live, which paths are framework rather than product,
what its quality gates are called — and none of it is decision policy.

```text
.ariadne/project.toml   →   ProjectConfig   →   evidence   →   state   →   decision
```

What may never appear here:

```text
what TERMINAL_* means            what may be dispatched
lifecycle transition legality    when a Human Gate is required
decision tables                  reason codes
```

Those are kernel invariants. A consumer that could override them would be a second
decision policy, which is the thing this framework exists to prevent. Configuration
answers *where and what*; the kernel answers *whether*.

A missing configuration file is legal and yields the generic defaults. It is not a
silent free pass: with no framework paths declared, no change can be proven to be
non-product, so classification stays `UNKNOWN` and the runtime fails closed. A
malformed file is recorded as a note on the evidence rather than raised, for the
same reason — the report should say why the repository could not be read.

Standard library only (`tomllib` is in the standard library from Python 3.11).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

from .integrations.gates import GateSpec
from .integrations.planning import DIRECTORY, PlanningProvider, build_provider

CONFIG_DIR = ".ariadne"
CONFIG_FILE = "project.toml"

DEFAULT_BRANCH = "main"
DEFAULT_SPEC_DIR = "specs"
DEFAULT_TASKS_FILE = "tasks.md"
DEFAULT_REQUIRED_ARTIFACTS = ("spec.md", "plan.md", "tasks.md")


@dataclass(frozen=True)
class ProjectConfig:
    """Every repository-specific fact the runtime is allowed to depend on.

    Defaults are generic on purpose: the kernel must run against a repository that
    has never heard of Ariadne, and must not carry any consumer's paths as
    fallbacks.
    """

    default_branch: str = DEFAULT_BRANCH
    spec_dir: str = DEFAULT_SPEC_DIR
    tasks_file: str = DEFAULT_TASKS_FILE
    required_artifacts: tuple[str, ...] = DEFAULT_REQUIRED_ARTIFACTS
    # The durable handoff. `None` means this repository records none, and recorded
    # evidence is then empty rather than assumed.
    state_file: str | None = None
    # Paths whose change is framework or process work rather than product work.
    # Empty by default: nothing is non-product until a consumer says so.
    framework_paths: tuple[str, ...] = ()
    framework_files: tuple[str, ...] = ()
    # Paths exempted from safety judgement but always reported.
    protected_paths: tuple[str, ...] = ()
    planning_provider: str = DIRECTORY
    gates: tuple[GateSpec, ...] = ()
    source: Path | None = None
    notes: tuple[str, ...] = field(default=())

    def planning(self) -> PlanningProvider:
        """Build the configured planning provider."""
        return build_provider(self.planning_provider, spec_dir=self.spec_dir)

    def facts(self) -> tuple[str, ...]:
        """How the configuration itself is reported, so a decision can be audited."""
        return (
            f"config={self.source.name if self.source is not None else '-'}",
            f"default_branch={self.default_branch}",
            f"planning_provider={self.planning_provider}",
            f"framework_paths={len(self.framework_paths)}",
            f"protected_paths_declared={len(self.protected_paths)}",
            f"gates_declared={','.join(spec.name for spec in self.gates) or '-'}",
        )


DEFAULT_CONFIG = ProjectConfig()


def config_path(root: Path) -> Path:
    """Where a consumer's configuration lives."""
    return Path(root) / CONFIG_DIR / CONFIG_FILE


def _strings(value: object, label: str, notes: list[str]) -> tuple[str, ...]:
    """Read a list-of-strings field, recording anything unusable rather than guessing."""
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        notes.append(f"config_invalid_{label}=yes")
        return ()
    return tuple(item for item in value if item)


def _text(value: object, label: str, fallback: str, notes: list[str]) -> str:
    if value is None:
        return fallback
    if not isinstance(value, str) or not value:
        notes.append(f"config_invalid_{label}=yes")
        return fallback
    return value


def _table(value: object, label: str, notes: list[str]) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        notes.append(f"config_invalid_{label}=yes")
        return {}
    return value


def _gates(value: object, notes: list[str]) -> tuple[GateSpec, ...]:
    """Read the declared quality gates.

    A gate with no name is dropped: an anonymous gate could not be reported, and a
    gate nobody can name is not evidence of anything.
    """
    if value is None:
        return ()
    if not isinstance(value, list):
        notes.append("config_invalid_gates=yes")
        return ()
    specs: list[GateSpec] = []
    for entry in value:
        if not isinstance(entry, dict):
            notes.append("config_invalid_gates=yes")
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            notes.append("config_invalid_gates=yes")
            continue
        specs.append(GateSpec(name=name, markers=_strings(entry.get("markers"), "gates", notes)))
    return tuple(specs)


def parse_project_config(text: str, *, source: Path | None = None) -> ProjectConfig:
    """Parse configuration text into a `ProjectConfig`.

    Unreadable fields fall back to the generic default and are recorded as notes.
    The result is always usable, and always says what it could not read.
    """
    notes: list[str] = []
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return replace(
            DEFAULT_CONFIG,
            source=source,
            notes=("config_unparseable=yes", f"config_error={type(exc).__name__}"),
        )

    repository = _table(data.get("repository"), "repository", notes)
    framework = _table(repository.get("framework"), "framework", notes)
    protected = _table(repository.get("protected"), "protected", notes)
    planning = _table(data.get("planning"), "planning", notes)

    state_file = repository.get("state_file")
    if state_file is not None and not isinstance(state_file, str):
        notes.append("config_invalid_state_file=yes")
        state_file = None

    required = _strings(repository.get("required_artifacts"), "required_artifacts", notes)
    return ProjectConfig(
        default_branch=_text(repository.get("default_branch"), "default_branch", DEFAULT_BRANCH, notes),
        spec_dir=_text(repository.get("spec_dir"), "spec_dir", DEFAULT_SPEC_DIR, notes),
        tasks_file=_text(repository.get("tasks_file"), "tasks_file", DEFAULT_TASKS_FILE, notes),
        required_artifacts=required or DEFAULT_REQUIRED_ARTIFACTS,
        state_file=state_file or None,
        framework_paths=_strings(framework.get("paths"), "framework_paths", notes),
        framework_files=_strings(framework.get("files"), "framework_files", notes),
        protected_paths=_strings(protected.get("paths"), "protected_paths", notes),
        planning_provider=_text(planning.get("provider"), "planning_provider", DIRECTORY, notes),
        gates=_gates(data.get("gates"), notes),
        source=source,
        notes=tuple(notes),
    )


def load_project_config(root: Path) -> ProjectConfig:
    """Load a repository's configuration, or the generic defaults when it has none."""
    path = config_path(root)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return replace(DEFAULT_CONFIG, notes=("config_absent=yes",))
    return parse_project_config(text, source=path)
