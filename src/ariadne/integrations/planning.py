"""Planning providers: how a repository declares which Feature is active.

Ariadne needs one fact from planning — *is a Feature registered, and where are its
artifacts?* Different repositories answer that differently, so the answer arrives
through a provider rather than from a path literal in the runtime:

```text
Ariadne dev-new
      ↓
PlanningProvider
      ↓
directory convention | Spec Kit | none
```

`DirectoryPlanning` is the built-in default and needs nothing but a spec directory
and a branch name, so the kernel has a working planning path with no integration
installed. `Spec Kit` lives in `speckit.py` and is imported only when a consumer
asks for it by name.

A provider reports facts. It classifies nothing, resolves no lifecycle, and
decides nothing: an absent registration is `None`, and what that means is the
runtime's judgement.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

DIRECTORY = "directory"
NONE = "none"


@dataclass(frozen=True)
class FeatureRegistration:
    """The registered Feature a planning provider found."""

    name: str
    directory: Path


@runtime_checkable
class PlanningProvider(Protocol):
    """Reports the registered Feature, or `None` when nothing is registered."""

    name: str

    def registered_feature(self, root: Path, branch: str | None) -> FeatureRegistration | None:
        ...


@dataclass(frozen=True)
class DirectoryPlanning:
    """The convention default: `<spec_dir>/<branch>/` is the Feature directory.

    This is what makes planning optional. A repository that keeps its
    specifications beside its branch name needs no integration at all, and a
    repository with no such directory simply has no registration — which the
    runtime already handles by failing closed.
    """

    spec_dir: str = "specs"
    name: str = DIRECTORY

    def registered_feature(self, root: Path, branch: str | None) -> FeatureRegistration | None:
        if not branch or not self.spec_dir:
            return None
        # A branch name is untrusted input from Git, so it is used as one path
        # segment and never allowed to walk out of the spec directory.
        if "/" in branch or "\\" in branch or branch in (".", ".."):
            return None
        candidate = root / self.spec_dir / branch
        if not candidate.is_dir():
            return None
        return FeatureRegistration(name=branch, directory=candidate)


@dataclass(frozen=True)
class NoPlanning:
    """No planning integration: nothing is ever registered."""

    name: str = NONE

    def registered_feature(self, root: Path, branch: str | None) -> FeatureRegistration | None:
        return None


def build_provider(name: str, *, spec_dir: str = "specs") -> PlanningProvider:
    """Resolve a provider by the name a consumer configured.

    Optional integrations are imported here and only here, so the kernel neither
    imports them nor requires them to exist. An unknown name yields `NoPlanning`
    rather than a guess, and the caller reports it: the runtime then behaves as a
    repository with no registration, which fails closed.
    """
    if name == DIRECTORY:
        return DirectoryPlanning(spec_dir=spec_dir)
    if name == NONE:
        return NoPlanning()
    if name == "speckit":
        from .speckit import SpecKitPlanning

        return SpecKitPlanning()
    return NoPlanning()


PROVIDERS = (DIRECTORY, NONE, "speckit")
