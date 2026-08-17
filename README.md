# Ariadne

**A governed runtime for agentic software development.**

An agent that decides for itself when it may merge will eventually decide wrongly.
Ariadne removes the choice. Repository facts go in, one decision comes out, and the
agent is handed exactly one phase or none at all:

```text
Repository → Evidence → State → Decision → TerminalGate → Router → Workflow
```

Each layer answers one question and holds no other layer's policy. Evidence judges
nothing. The engine dispatches nothing. The gate maps nothing. The router decides
nothing.

Ariadne knows nothing about your language, build tool, or test runner, and has no
code path that could ask.

## Install

```bash
pip install ariadne-sdlc
```

Python 3.11+, standard library only, no runtime dependencies.

## Quickstart

```bash
cd your-repository
mkdir -p .ariadne && cp examples/generic/project.toml .ariadne/project.toml
ariadne status
```

`ariadne status` reports what your repository currently proves. Then wire a host:

```bash
ariadne dev next            # what may run right now?
ariadne dev merge --human-gate APPROVED
ariadne doc --list          # the contracts Ariadne enforces
ariadne inspect             # the evidence behind the decision
ariadne validate tasks      # the task graph, without deciding anything
```

Non-zero exit means the command has already printed the one final report: that
report is the answer. Exit `0` prints the single phase that is granted, and the path
to that phase's workflow document.

## The four entry points

| Intent | Runs | Never |
| --- | --- | --- |
| `dev new` | prepare exactly one Feature, stop at `READY_FOR_IMPLEMENTATION` | write product code |
| `dev next` | one dependency-coherent batch → gates → commit → independent review → handoff | start the next batch |
| `dev close` | final acceptance, scope and review audit, stop at `READY_TO_CLOSE` | merge |
| `dev merge` | closure checkpoint → merge policy → post-merge verification → `CLOSED` | delete branches, tags, or worktrees |

## The managed entity

`dev merge` is not a generic Git merge command. It first classifies what the current
branch *is*, from repository evidence rather than a branch-name guess:

```text
PRODUCT_FEATURE | NON_PRODUCT | UNKNOWN
```

Then it applies the terminal decision contract, before any closure phase:

```text
PRODUCT_FEATURE + READY_TO_CLOSE → CONTINUE
PRODUCT_FEATURE + IN_PROGRESS     → TERMINAL_BLOCKED
NON_PRODUCT                      → TERMINAL_NOT_APPLICABLE
UNKNOWN                          → TERMINAL_BLOCKED
```

A terminal decision emits its status and stops; only `CONTINUE` enters the merge
flow. `NOT_APPLICABLE` is a successful guard, not a failure. `UNKNOWN` is what
insufficient evidence produces, and it fails closed — absence of a Feature
registration is not proof of anything.

That mapping is stated once, in `ariadne doc terminal-contract`, and
`tests/test_decision_consistency.py` runs this table row by row through the engine.
A document that drifts from the code fails the suite in either direction.

## Kernel invariants

Not configurable. Not overridable by a host, an adapter, or a prompt.

- A `TERMINAL_*` decision never dispatches.
- `CONTINUE` is the only dispatchable state, and it dispatches exactly once.
- A malformed, unknown, or wrong-version envelope fails closed to `TERMINAL_BLOCKED`
  with `PROTOCOL_DECISION_INVALID` — it never becomes `CONTINUE`.
- One decision point settles once. The gate is the only path to dispatch.
- Lifecycle state is derived from evidence. No entry point accepts an injected one.
- The router holds no policy; it maps an intent to one dispatcher and refuses
  everything else.
- A host cannot change decision semantics. Same repository state and intent → same
  envelope on every host.

Every envelope is revalidated where it is used, so a producer cannot force a
decision through with a subclass, a lying comparison, an overridden method, or an
object mutated after construction.

## What a consumer owns

Three seams, and no others:

```text
project configuration → repository facts        .ariadne/project.toml
planning provider     → where Features live     directory | speckit | none
quality gate provider → structured verdicts     markers over recorded evidence
```

Quality gates, protected paths, spec directory, tasks file, branch conventions,
merge policy parameters and repository layout are all yours. Ariadne reads
`test = PASS` and never learns which command produced it — see `examples/`, where
one configuration is written three ways for three toolchains and the runtime cannot
tell them apart.

Planning is optional. The default provider needs a directory convention and nothing
else, so the kernel imports, runs, and passes its full suite with no planning tool
installed. Spec Kit is one provider among three, imported only when a repository
asks for it by name.

## Host adapters

`adapters/` holds ready-made templates for Claude Code, Codex, OpenCode, and the
portable `AGENTS.md` convention. An adapter does one thing:

```text
host command → ariadne dev <phase> → obey the result
```

It holds no lifecycle policy, no decision table, no reason codes, and no terminal
semantics. All twenty templates are generated from `adapters/generate.py`, and
`tests/test_adapters.py` fails if one has been hand-edited — because twenty
near-identical prompt files are exactly where a rogue rule would hide.

## Layout

```text
src/ariadne/
  runtime/       evidence → state → decision → gate → router → api
  dag/           the one tasks-file parser and dependency resolver
  contracts/     the protocol, shipped so `ariadne doc` can print it
  workflows/     the four host-independent workflow definitions
  integrations/  planning providers, quality gate resolution
  config.py      the consumer seam
  cli.py         thin entry point over the runtime API
adapters/        host templates, generated
examples/        three consumer configurations of three different projects
tests/           deterministic protocol checks
docs/runtime.md  the runtime, module by module
```

## Validation

```bash
python3 tests/run_all.py
```

`tests/test_terminal_gate.py` proves the enforcement invariants against a spy
dispatcher with no agent involved, including hostile envelope shapes.
`tests/test_runtime_closure.py` proves the whole chain end to end against real
repository fixtures. `tests/audit_wiring.py` reads the repository as text to prove
nothing bypasses the gate: it fails if a second decision policy, a dispatch path
around the gate, or an adapter with decision semantics reappears.

## License

MIT.
