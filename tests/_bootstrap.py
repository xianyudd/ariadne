"""Make Ariadne importable when a check runs from a source checkout.

Every check in this directory is a standalone script, so each one needs the package
on `sys.path` before it can import it. Importing this module is how: it puts `src/`
and this directory there, and nothing else.

```python
import _bootstrap  # noqa: F401
from ariadne.runtime.decision import CONTINUE
```

An installed Ariadne needs none of this — `sys.path` already has the package, and
inserting `src/` in front of it is harmless because it is the same code. What this
guarantees is that the suite runs against a checkout without being installed first.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src"

for entry in (str(HERE), str(SRC)):
    if entry not in sys.path:
        sys.path.insert(0, entry)
