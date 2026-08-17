"""The normative documents, resolved from wherever Ariadne is installed.

Ariadne's contracts are what the runtime implements, and its workflow documents are
what an agent executes once a phase is granted. Both are needed at run time, by a
host adapter that is a prompt file and has no import statement — so both ship inside
the package and are found here rather than at a path the consumer has to know.

```python
from ariadne import document_text

rules = document_text("terminal-contract")
```

That is also why they are not repository documentation: a consumer installs Ariadne
and vendors nothing, so a document reachable only from a source checkout would be
unreachable exactly when an agent needs it. `ariadne doc` is the same lookup for a
host that can only run a command.

This module resolves names to files. It reads no document's meaning.

Standard library only.
"""

from __future__ import annotations

from pathlib import Path

from .workflows import WORKFLOWS, workflow_path

HERE = Path(__file__).resolve().parent
CONTRACT_DIR = HERE / "contracts"

SUFFIX = ".md"


def contract_names() -> tuple[str, ...]:
    """Every contract, by the name `document_text` takes."""
    return tuple(sorted(path.stem for path in CONTRACT_DIR.glob(f"*{SUFFIX}")))


def workflow_names() -> tuple[str, ...]:
    """Every workflow document, by the name `document_text` takes."""
    return tuple(sorted(Path(name).stem for name in WORKFLOWS.values()))


def document_names() -> tuple[str, ...]:
    """Every document a host may ask for."""
    return tuple(sorted({*contract_names(), *workflow_names()}))


def document_path(name: str) -> Path:
    """Locate one document by name, contract or workflow.

    Raises `KeyError` for a name that is neither. A document Ariadne ships but
    cannot find is a packaging fault, so this never returns a path that is absent.
    """
    stem = name[: -len(SUFFIX)] if name.endswith(SUFFIX) else name
    contract = CONTRACT_DIR / f"{stem}{SUFFIX}"
    if contract.is_file():
        return contract
    for intent, filename in WORKFLOWS.items():
        if Path(filename).stem == stem:
            return workflow_path(intent)
    raise KeyError(name)


def document_text(name: str) -> str:
    """One document's contents."""
    return document_path(name).read_text(encoding="utf-8")
