#!/usr/bin/env python3
"""Source views for structural claims about code.

Test support. A claim like "the router never mentions a lifecycle state" is a claim
about code, but a docstring saying *the router must not judge lifecycle* would make
the naive text search fail. `code_only` gives the view that answers the question:
the module's code with comments and string literals blanked out.

Positions are preserved rather than tokens concatenated. Concatenation glues
adjacent identifiers together — `return dispatcher(` becomes `returndispatcher(`,
which silently breaks any word-boundary search and makes such a claim pass
vacuously. Blanking in place keeps every boundary intact.
"""
from __future__ import annotations

import tokenize
from pathlib import Path

# String literals are dropped alongside comments: a claim about code should not be
# satisfied or defeated by prose. F-string literal segments go too, while the
# expressions interpolated into them survive, because those are code.
_DROPPED = {tokenize.COMMENT, tokenize.STRING}
for _name in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END"):
    _type = getattr(tokenize, _name, None)
    if _type is not None:
        _DROPPED.add(_type)


def code_only(path: Path) -> str:
    """The module's source with comments and string literals blanked out.

    Line and column positions are unchanged, so a match's location in the result is
    its location in the file.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    blanked = [list(line) for line in lines]
    with tokenize.open(path) as handle:
        for token in tokenize.generate_tokens(handle.readline):
            if token.type not in _DROPPED:
                continue
            (start_row, start_col), (end_row, end_col) = token.start, token.end
            for row in range(start_row, end_row + 1):
                if row - 1 >= len(blanked):
                    break
                characters = blanked[row - 1]
                first = start_col if row == start_row else 0
                last = end_col if row == end_row else len(characters)
                for column in range(first, min(last, len(characters))):
                    if characters[column] != "\n":
                        characters[column] = " "
    return "".join("".join(characters) for characters in blanked)
