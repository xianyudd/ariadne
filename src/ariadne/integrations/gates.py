"""Quality gates as structured evidence.

Ariadne never runs a project's quality gates and never learns what they are. A
consumer declares its gates; this module turns the consumer's recorded evidence
into a structured result the runtime can read:

```text
Project Configuration
        ↓
Quality Gate Provider
        ↓
test = PASS   lint = PASS   format = PASS
        ↓
Ariadne Runtime
```

The runtime sees the right-hand column only. Which command produced `test`, or
whether a person produced it by working through a checklist, is a fact about the
consumer, and it stays there. `examples/` shows the same configuration written for
three different toolchains; nothing in this module can tell them apart.

A marker is a pattern the consumer supplies, because a durable handoff is prose.
Ariadne compiles it and searches recorded text with it. It never executes a
command, and an unusable pattern is reported rather than guessed at.

Standard library only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

GATE_PASS = "PASS"
GATE_UNKNOWN = "UNKNOWN"

GATE_STATUSES = frozenset({GATE_PASS, GATE_UNKNOWN})


@dataclass(frozen=True)
class GateSpec:
    """One quality gate a consumer declares.

    `name` is the consumer's own label for it — `test`, `lint`, `format`. `markers`
    are patterns that, when found in recorded evidence, prove that gate passed.
    """

    name: str
    markers: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateResults:
    """Per-gate status, and the one question the runtime asks of it.

    `recorded` is deliberately "some declared gate is proven", not "every declared
    gate is proven". Ariadne is reading a handoff, not running a build: the
    obligation that *all* gates pass belongs to the consumer's gate run, and
    reading a sentence cannot discharge it. Treating a partially-detailed handoff
    as a failed one would make the runtime's own reading a second quality gate.
    """

    results: Mapping[str, str]
    errors: tuple[str, ...] = ()

    @property
    def declared(self) -> tuple[str, ...]:
        return tuple(sorted(self.results))

    @property
    def passed(self) -> tuple[str, ...]:
        return tuple(name for name in self.declared if self.results[name] == GATE_PASS)

    @property
    def recorded(self) -> bool:
        """Whether recorded evidence proves a declared quality gate passed."""
        return bool(self.passed)

    @property
    def all_passed(self) -> bool:
        return bool(self.results) and len(self.passed) == len(self.results)

    def facts(self) -> tuple[str, ...]:
        """A deterministic rendering, for reports that show the gates themselves."""
        return tuple(f"gate_{name}={self.results[name]}" for name in self.declared)


EMPTY_GATES = GateResults(results={})


def resolve_gates(text: str | None, specs: Iterable[GateSpec]) -> GateResults:
    """Read recorded evidence once and report each declared gate's status.

    A gate whose markers do not appear is `UNKNOWN`, never `FAIL`: absence of a
    recorded pass is absence of evidence, and the runtime already fails closed on
    that. A marker that will not compile is reported as an error and proves
    nothing, so a malformed consumer pattern cannot read as a pass.
    """
    results: dict[str, str] = {}
    errors: list[str] = []
    for spec in specs:
        status = GATE_UNKNOWN
        for marker in spec.markers:
            try:
                pattern = re.compile(marker, re.IGNORECASE)
            except re.error as exc:
                errors.append(f"gate {spec.name}: unusable marker {marker!r}: {exc}")
                continue
            if text is not None and pattern.search(text):
                status = GATE_PASS
                break
        results[spec.name] = status
    return GateResults(results=results, errors=tuple(errors))
