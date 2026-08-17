"""Spec Kit as an optional planning provider.

Spec Kit is one way a repository can declare its active Feature. It is not part of
the Ariadne kernel: this module is imported only when a consumer configures
`provider = "speckit"`, and nothing in `ariadne.runtime` imports it. A repository
with no `.specify/` directory runs the full evidence → state → decision → gate
path with the kernel's own default provider.

The registration Spec Kit writes is `.specify/feature.json`:

```json
{"feature_directory": "specs/003-example"}
```

That single field is all Ariadne reads. Spec Kit's templates, memory layout, and
commands are its own business.

Standard library only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .planning import FeatureRegistration

SPECKIT = "speckit"
REGISTRATION = (".specify", "feature.json")
FEATURE_FIELD = "feature_directory"


@dataclass(frozen=True)
class SpecKitPlanning:
    """Reads the Feature registration Spec Kit maintains."""

    name: str = SPECKIT

    def registered_feature(self, root: Path, branch: str | None) -> FeatureRegistration | None:
        """Report the registered Feature, or `None` when Spec Kit has not registered one.

        An unreadable or malformed registration is `None` rather than an exception:
        a missing registration is an ordinary repository state that the runtime
        already fails closed on, and an integration must not be able to crash the
        decision path.
        """
        registration = root.joinpath(*REGISTRATION)
        try:
            data = json.loads(registration.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        declared = data.get(FEATURE_FIELD)
        if not isinstance(declared, str) or not declared:
            return None
        return FeatureRegistration(name=Path(declared).name, directory=root / declared)
