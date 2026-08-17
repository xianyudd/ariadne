#!/usr/bin/env python3
"""Generate the host adapter templates from one source of truth.

An adapter is the smallest possible thing: a host command that runs `ariadne dev`
and obeys the result. That makes sixteen files which are nearly the same file, and
the risk is not that one of them is badly written — it is that one of them drifts
and starts holding a rule of its own. So they are generated, from the table below,
and the generator is the only place their wording exists.

```bash
python3 adapters/generate.py          # rewrite every template
python3 adapters/generate.py --check  # fail if a template is stale
```

`tests/test_adapters.py` runs `--check`, so a hand-edited template fails the suite.
Edit this file instead.

What the table may contain: the host's own metadata, the phase, and which Ariadne
documents the executing agent should load. What it may not contain: a decision, a
reason code, a lifecycle mapping, or a condition under which a phase is permitted.
Those live in the runtime, which is the whole point of an adapter being this thin.

Standard library only.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Phase → (host-facing summary, extra `ariadne doc` documents beyond the common set,
# host-specific closing paragraphs). The workflow document itself is never listed:
# `ariadne dev` prints where it is, so no adapter has to know.
PHASES: dict[str, dict[str, object]] = {
    "dev-new": {
        "summary": "Prepare one Feature through the Ariadne contract; stop before product implementation.",
        "argument_hint": "[--dry-run] <requirement>",
        "docs": ("lifecycle", "lifecycle-entity", "state-contract", "task-dag", "human-gates", "git-policy", "context-policy"),
        "dry_run_docs": ("lifecycle-entity", "state-contract"),
        "notes": [
            "Parse the invocation arguments before entering any workflow phase. Preserve the requirement text exactly as supplied.",
            "With `--dry-run`, the workflow's bounded read-only path is the whole of it: no planning provider, reviewer, test, build, Git mutation, or worktree operation, no clarification questions, and no full-repository scan.",
        ],
    },
    "dev-next": {
        "summary": "Execute one dependency-coherent batch through verification, independent review, handoff, and stop.",
        "argument_hint": "[--dry-run] [optional task range]",
        "docs": ("lifecycle", "state-contract", "task-dag", "batch-policy", "review-contract", "human-gates", "git-policy", "context-policy"),
        "dry_run_docs": (),
        "notes": [
            "Use an independent reviewer only after the implementation commit. If independent reviewer capability is unavailable, report `REVIEW CAPABILITY BLOCKED` rather than substituting a self-review.",
        ],
    },
    "dev-close": {
        "summary": "Perform final acceptance checks and stop at the closure gate without merging.",
        "argument_hint": "[--dry-run]",
        "docs": ("lifecycle", "state-contract", "task-dag", "review-contract", "human-gates", "git-policy", "context-policy"),
        "dry_run_docs": (),
        "notes": [
            "This adapter must not merge, delete branches, clean worktrees, create releases, or create a new Feature.",
        ],
    },
    "dev-merge": {
        "summary": "Merge a Feature that Ariadne has cleared for merge, using the repository merge policy, and verify the result.",
        "argument_hint": "[--dry-run] [target branch]",
        "docs": ("lifecycle", "lifecycle-entity", "state-contract", "human-gates", "git-policy", "context-policy"),
        "dry_run_docs": (),
        "notes": [
            "Establishing the Human Gate state is this adapter's only judgement. Pass `--human-gate APPROVED` only with the user's explicit authorization for this merge, and `UNKNOWN` when unsure. Anything but `APPROVED` fails closed where a gate is required, and a `--dry-run` mutates nothing so it needs no authorization.",
            "Never delete feature branches, tags, releases, or worktrees.",
        ],
    },
}

# The paragraph every adapter shares. It describes how to obey a command's result,
# which is not a decision rule: it says nothing about which result to expect.
GATE = """## Runtime gate

Run this before loading the workflow or reading any repository evidence:

```bash
{command}
```

The command is the decision, not an advisory check: it collects repository
evidence, resolves state, decides what the protocol permits, and enforces the
result.

- Non-zero exit: the command has already printed the one final report. That report
  is the answer — emit it and stop. Do not load the workflow, read further
  evidence, retry with different arguments, or reinterpret the outcome.
- Exit `0`: the command prints the single phase that is granted, and the path to
  that phase's workflow document. Enter that phase and no other.

This adapter holds no decision semantics. Classification, lifecycle, task graph,
safety, and terminality belong to Ariadne, so the same repository state and intent
produce the same result on every host."""

POLICY_BLOCK = """<!-- ariadne:project-policies -->
- (your repository's own policy documents, one per line)
<!-- /ariadne:project-policies -->"""

POLICY_NOTE = """Then load your repository's own policies. Ariadne does not supply them and does
not read them: quality gates, protected paths, and architecture rules are the
consumer's, and this list is what an installer fills in."""


def command(phase: str, *, human_gate: bool) -> str:
    gate = " --human-gate APPROVED|NOT_APPROVED|UNKNOWN" if human_gate else ""
    return f"ariadne dev {phase.split('-', 1)[1]}{gate} [--dry-run]"


def doc_list(names: tuple[str, ...]) -> str:
    return "\n".join(f"- `ariadne doc {name}`" for name in names)


def body(phase: str, spec: dict[str, object]) -> str:
    """The part of an adapter that is the same on every host."""
    parts = [GATE.format(command=command(phase, human_gate=phase == "dev-merge"))]
    dry_run_docs = spec["dry_run_docs"]
    assert isinstance(dry_run_docs, tuple)
    docs = spec["docs"]
    assert isinstance(docs, tuple)

    parts.append(
        "## Documents\n\n"
        "Ariadne ships the contracts it enforces. Load them from the install rather\n"
        "than from a vendored copy:\n\n" + doc_list(docs)
    )
    if dry_run_docs:
        parts.append(
            "Under `--dry-run`, load only:\n\n" + doc_list(dry_run_docs)
        )
    parts.append(POLICY_NOTE + "\n\n" + POLICY_BLOCK)
    notes = spec["notes"]
    assert isinstance(notes, list)
    parts.extend(notes)
    return "\n\n".join(parts)


def claude(phase: str, spec: dict[str, object]) -> str:
    return f"""---
name: {phase}
description: {spec["summary"]}
argument-hint: "{spec["argument_hint"]}"
user-invocable: true
disable-model-invocation: true
---

# Claude adapter: `/{phase}`

{body(phase, spec)}
"""


def agents(phase: str, spec: dict[str, object]) -> str:
    return f"""---
name: {phase}
description: {spec["summary"]}
user-invocable: true
---

# Portable adapter: `/{phase}`

{body(phase, spec)}

Preserve `$ARGUMENTS` exactly as supplied.
"""


def opencode(phase: str, spec: dict[str, object]) -> str:
    """OpenCode delegates: its command routes to the portable adapter and adds nothing.

    A second full adapter here would be a second place for a rule to live, which is
    exactly what this whole directory exists to prevent.
    """
    return f"""# OpenCode command: `/{phase}`

Collect `$ARGUMENTS`, then execute `.agents/skills/{phase}/SKILL.md`.

Run this first, as that adapter requires:

```bash
{command(phase, human_gate=phase == "dev-merge")}
```

A non-zero exit is the final report: emit it and stop. Do not restate the decision
rules here, and do not copy the workflow into this command.
"""


def codex(phase: str, spec: dict[str, object]) -> str:
    return f"""# Codex adapter: `{phase}`

{body(phase, spec)}
"""


FAMILIES = {
    "claude": (claude, "claude/skills/{phase}/SKILL.md"),
    "agents": (agents, "agents/skills/{phase}/SKILL.md"),
    "opencode": (opencode, "opencode/commands/{phase}.md"),
    "codex": (codex, "codex/prompts/{phase}.md"),
}

# The reviewer is a review provider, not a workflow: `dev-next` and `dev-close` call
# for independent review and Ariadne states the contract, but performing one is the
# host's capability. Each family gets the same instruction in its own file format,
# and the instruction is to read `review-contract` — never to restate it.
REVIEWER_BODY = """Load `ariadne doc review-contract`, then your repository's own policies. Review the
supplied batch against actual source, tests, Git diff, and task artifacts, using
read-only inspection only.

Do not edit, commit, change task state, enter or clean worktrees, install
dependencies, or expand scope. Do not hard-code a model. If this host cannot
provide independent review, report `REVIEW CAPABILITY BLOCKED` rather than
substituting a self-review."""

REVIEWERS = {
    "claude/agents/reviewer.md": f"""---
name: reviewer
description: Independent read-only Ariadne reviewer
tools: Read, Grep, Glob, Bash
---

# Claude reviewer adapter

{REVIEWER_BODY}
""",
    "agents/agents/reviewer.md": f"""---
name: reviewer
description: Independent read-only Ariadne reviewer
mode: subagent
---

# Portable reviewer adapter

{REVIEWER_BODY}
""",
    "opencode/agents/reviewer.md": f"""---
description: Independent read-only Ariadne reviewer
mode: subagent
edit: deny
---

{REVIEWER_BODY}
""",
    "codex/agents/reviewer.toml": "# Codex reviewer adapter\n\n"
    'project_scoped = true\nsandbox = "read-only"\nrole = "independent reviewer"\n\n'
    + "\n".join(f"# {line}".rstrip() for line in REVIEWER_BODY.splitlines())
    + "\n",
}


def generate() -> dict[Path, str]:
    """Every template, as a path-to-contents mapping."""
    return {
        HERE / template.format(phase=phase): render(phase, spec)
        for render, template in FAMILIES.values()
        for phase, spec in PHASES.items()
    } | {HERE / name: text for name, text in REVIEWERS.items()}


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale: list[str] = []
    for path, text in generate().items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == text:
            continue
        if check:
            stale.append(str(path.relative_to(HERE.parent)))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if stale:
        print(f"{len(stale)} adapter template(s) do not match adapters/generate.py:")
        for name in stale:
            print(f"  ✗ {name}")
        print("run: python3 adapters/generate.py")
        return 1
    print(f"{len(generate())} adapter templates {'match' if check else 'written'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
