# Ariadne

**A governed runtime for agentic software development.**

Ariadne answers one question, and refuses to let an agent answer it instead:

> **Does the agent have a legal next action right now — and if so, exactly one?**

An agent that decides for itself when it may merge will eventually decide wrongly.
Ariadne removes the choice. Repository facts go in, one decision comes out, and the
agent is handed exactly one phase — or none at all.

```text
Repository Evidence
     ↓
State Resolution
     ↓
Decision Engine
     ↓
DecisionEnvelope
     ↓
TerminalGate
     ↓
Router
     ↓
Workflow
```

Each layer answers one question and holds no other layer's policy. Evidence judges
nothing. The engine dispatches nothing. The gate maps nothing. The router decides
nothing.

## What it is

- A **decision runtime** for a fixed software lifecycle: prepare a feature, run one
  batch, close, merge. Given a repository and an intent, it returns one envelope.
- **A single decision policy.** The rules live in one engine (`decision_engine.py`);
  the Markdown contracts describe them and the suite fails if the two ever drift.
- **An enforcement boundary.** A `TerminalGate` owns dispatch, so a refusal does not
  depend on the agent choosing to obey it.
- **Host- and language-neutral.** Standard library only, no runtime dependencies. It
  reads a repository with `git` and never learns your language, build tool, or test
  runner.

## What it is not

- **Not an agent framework or orchestrator.** No async runtime, event bus, scheduler,
  database, or model calls. It decides control flow; the agent does the work.
- **Not a task runner.** It never executes your tests, linters, or build. It reads a
  recorded verdict — `test = PASS` — and cannot learn which command produced it.
- **Not a planner.** It does not generate specs or tasks. A planning provider only
  *reports* which feature is registered.
- **Not a policy you configure.** The kernel invariants below are not overridable by
  a config file, an adapter, or a prompt. Configuration answers *where and what*; the
  kernel answers *whether*.

## Install

```bash
pip install ariadne-sdlc      # or: pipx install ariadne-sdlc
```

Python 3.11+, standard library only, no runtime dependencies.

## Quickstart

```bash
cd your-repository
mkdir -p .ariadne
cat > .ariadne/project.toml <<'TOML'
[repository]
default_branch = "main"
spec_dir = "specs"
TOML

ariadne status          # what does this repository currently prove?
ariadne dev next        # what, if anything, may run right now?
```

`ariadne status` reports the facts behind a decision without granting a phase. A
repository with no `.ariadne/project.toml` is still legal — it gets generic defaults and
fails closed rather than guessing. For richer starting points, `examples/` in this repo
holds one configuration written three ways, for a Rust, a Python, and a generic project.

Non-zero exit from `dev` means the command already printed the one final report — that
report is the answer. Exit `0` prints the single granted phase and the path to its
workflow document.

## CLI

```bash
ariadne status                        # resolved state; decides no phase
ariadne inspect                       # entity, lifecycle, and the envelope — reports, never dispatches
ariadne validate tasks <path>         # resolve and report a task graph, deciding nothing
ariadne dev new                       # prepare exactly one feature, stop at the implementation gate
ariadne dev next                      # one dependency-coherent batch → gates → commit → review → handoff
ariadne dev close                     # final acceptance, stop at READY_TO_CLOSE
ariadne dev merge --human-gate APPROVED   # closure checkpoint → merge policy → post-merge verification
ariadne doc --list                    # the contracts and workflows Ariadne ships
```

| Exit | Meaning |
| --- | --- |
| `0` | `CONTINUE`, or a read-only command that answered |
| `1` | `validate`: the file was read and rejected |
| `2` | `TERMINAL_*` — final, no phase granted (or `validate`: file unreadable) |
| `64` | usage error — nothing was decided |

A misspelled flag can never return `2`: a host reading `2` must be able to conclude a
decision was made and was final.

## The four entry points

| Intent | Runs | Never |
| --- | --- | --- |
| `dev new` | prepare exactly one feature, stop at `READY_FOR_IMPLEMENTATION` | write product code |
| `dev next` | one dependency-coherent batch → gates → commit → independent review → handoff | start the next batch |
| `dev close` | final acceptance, scope and review audit, stop at `READY_TO_CLOSE` | merge |
| `dev merge` | closure checkpoint → merge policy → post-merge verification → `CLOSED` | delete branches, tags, or worktrees |

`dev merge` is not a generic Git merge. It first classifies what the current branch
*is*, from repository evidence rather than a branch-name guess — `PRODUCT_FEATURE`,
`NON_PRODUCT`, or `UNKNOWN` — and applies the terminal contract before any closure
phase:

```text
PRODUCT_FEATURE + READY_TO_CLOSE → CONTINUE
PRODUCT_FEATURE + IN_PROGRESS     → TERMINAL_BLOCKED
NON_PRODUCT                      → TERMINAL_NOT_APPLICABLE
UNKNOWN                          → TERMINAL_BLOCKED
```

`NOT_APPLICABLE` is a successful guard, not a failure. `UNKNOWN` is what insufficient
evidence produces, and it fails closed — absence of a feature registration is not proof
of anything. That table is stated once, in `ariadne doc terminal-contract`, and
`tests/test_decision_consistency.py` runs it row by row through the engine.

## Terminal semantics

The one guarantee everything else rests on:

```text
CONTINUE      → exactly one dispatch, through the router
TERMINAL_*    → zero dispatch; one final report; the gate is now settled
malformed     → fail closed to TERMINAL_BLOCKED / PROTOCOL_DECISION_INVALID
```

A malformed, unknown, or wrong-version envelope never becomes `CONTINUE`. Every
envelope is revalidated where it is used, so a producer cannot force a decision
through with a subclass, a lying comparison, an overridden method, or an object
mutated after construction.

## Kernel invariants

Not configurable. Not overridable by a host, an adapter, or a prompt.

- A `TERMINAL_*` decision never dispatches.
- `CONTINUE` is the only dispatchable state, and it dispatches exactly once.
- A malformed decision fails closed to `TERMINAL_BLOCKED` — it never becomes `CONTINUE`.
- One decision point settles once. The gate is the only path to dispatch.
- Lifecycle state is derived from evidence. No entry point accepts an injected one.
- The router holds no policy; it maps an intent to one dispatcher and refuses the rest.
- A host cannot change decision semantics. Same repository state and intent → same
  envelope on every host.

## What a consumer owns

Three seams, and no others:

```text
project configuration → repository facts       .ariadne/project.toml
planning provider     → where features live    directory | speckit | none
quality gate provider → structured verdicts    markers over recorded evidence
```

Quality gates, protected paths, spec directory, tasks file, branch conventions, merge
policy parameters, and repository layout are all yours. Ariadne reads `test = PASS` and
never learns which command produced it — see `examples/`, where one configuration is
written three ways for three toolchains and the runtime cannot tell them apart.

**Spec Kit is optional.** Planning arrives through a provider. The default needs only a
directory convention, so the kernel imports, runs, and passes its full suite with no
planning tool installed. Spec Kit is one provider among three, imported only when a
repository asks for it by name (`provider = "speckit"`).

## Host adapters

`adapters/` holds ready-made templates for Claude Code, Codex, OpenCode, and the
portable `AGENTS.md` convention. An adapter does one thing:

```text
host command → ariadne dev <phase> → obey the result
```

It holds no lifecycle policy, no decision table, no reason codes, no terminal semantics.
All twenty templates are generated from `adapters/generate.py` (`--check` fails on
staleness), and `tests/test_adapters.py` fails if one has been hand-edited — twenty
near-identical prompt files are exactly where a rogue rule would hide.

## Project status

Beta, protocol version `2.1`. The runtime is closed end to end
(`Evidence → State → Decision → TerminalGate → Router → Workflow`) and its semantics are
stable; this release cycle is projectization, not new runtime behavior. The full suite
(`python3 tests/run_all.py`) plus a mutation harness (`tests/mutate.py`) run on every
change, including hostile envelope shapes and an architecture-level wiring audit.

**tflow** — a Rust product repository — is the first real-world consumer and validated
the whole chain and all four workflows across every branch state and intent. It is a
*consumer*, not a dependency: Ariadne has zero knowledge of Rust, Cargo, or tflow, and
no code path that could acquire it. It is one data point, not a track record; the
adapter templates are also copied into each consumer rather than imported, so a consumer
can drift from an upgraded Ariadne until it re-copies.

## Layout

```text
src/ariadne/
  runtime/       evidence → state → decision → gate → router → api
  dag/           the one tasks-file parser and dependency resolver
  contracts/     the protocol, shipped so `ariadne doc` can print it
  workflows/     the four host-independent workflow definitions
  integrations/  planning providers, quality gate resolution
  config.py      the consumer seam (.ariadne/project.toml → ProjectConfig)
  cli.py         thin entry point over the runtime API
adapters/        host templates, generated
examples/        three consumer configurations for three different projects
docs/            architecture.md, design-principles.md, runtime.md
tests/           deterministic protocol checks + mutation harness
```

## Documentation

- `docs/architecture.md` — kernel, SDLC model, integration, consumer configuration
- `docs/design-principles.md` — the principles the code actually enforces
- `docs/runtime.md` — the runtime, module by module
- `ariadne doc --list` — the contracts and workflow documents, shipped in the package

## License

MIT — see [`LICENSE`](LICENSE).
