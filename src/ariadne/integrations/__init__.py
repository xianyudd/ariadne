"""Integrations: where a consumer's own tooling meets the Ariadne kernel.

Everything here answers a question about *this* repository — which planning tool
registers its Features, which quality gates it runs — and returns structured facts.
None of it decides anything, and the kernel never depends on a particular one being
present.

```text
consumer tooling → integration → structured evidence → kernel
```

Standard library only.
"""

from __future__ import annotations

from .gates import (
    EMPTY_GATES,
    GATE_PASS,
    GATE_STATUSES,
    GATE_UNKNOWN,
    GateResults,
    GateSpec,
    resolve_gates,
)
from .planning import (
    DIRECTORY,
    NONE,
    PROVIDERS,
    DirectoryPlanning,
    FeatureRegistration,
    NoPlanning,
    PlanningProvider,
    build_provider,
)

__all__ = [
    "DIRECTORY",
    "EMPTY_GATES",
    "GATE_PASS",
    "GATE_STATUSES",
    "GATE_UNKNOWN",
    "GateResults",
    "GateSpec",
    "DirectoryPlanning",
    "FeatureRegistration",
    "NONE",
    "NoPlanning",
    "PROVIDERS",
    "PlanningProvider",
    "build_provider",
    "resolve_gates",
]
