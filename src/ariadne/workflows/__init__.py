"""Workflow definitions, shipped with the package so an adapter can always load them.

A workflow document says *how* a granted phase is carried out. It no longer says what
is permitted: that is the decision engine's, and `tests/test_decision_consistency.py`
reads the tables in these documents and runs every row through it, so a document that
drifts from the code fails.

They live inside the package rather than beside it because a host adapter must be able
to load them from an installed Ariadne, not only from a source checkout.

```python
from ariadne import workflow_text

prompt = workflow_text("DEV_NEXT")
```

Standard library only.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

# Intent → document. The intents are the runtime's (`ariadne.runtime.state`); this
# table only says which file describes each one.
WORKFLOWS = {
    "DEV_NEW": "dev-new.md",
    "DEV_NEXT": "dev-next.md",
    "DEV_CLOSE": "dev-close.md",
    "DEV_MERGE": "dev-merge.md",
}


def workflow_path(intent: str) -> Path:
    """The document describing one workflow intent.

    Raises `KeyError` for an intent with no document, rather than returning a path
    that does not exist: a missing workflow is a packaging fault, not a decision.
    """
    return HERE / WORKFLOWS[intent]


def workflow_text(intent: str) -> str:
    """The workflow document's contents."""
    return workflow_path(intent).read_text(encoding="utf-8")
