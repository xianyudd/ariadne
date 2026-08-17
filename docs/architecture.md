# Architecture

Ariadne is a host-independent runtime that governs a fixed software lifecycle. This
document explains the shape of the system: the **kernel** and its invariants, the
**SDLC model** the kernel enforces, the **integration** seams a consumer plugs into, and
the **consumer configuration** that drives them.

For the runtime module by module, see [`runtime.md`](runtime.md). For the reasoning
behind these choices, see [`design-principles.md`](design-principles.md).

## The pipeline is five distinct concerns

The whole runtime is one ordered pipeline, and its correctness comes from keeping five
concerns *separate*. They are not synonyms; each is a different kind of thing, and each
may read only what precedes it:

```text
Evidence     ≠  State      ≠  Decision   ≠  Enforcement  ≠  Execution
what is true    what state    what the      may control     which one
in the repo     that implies  protocol      flow continue?  action runs
(facts)         (derived)     permits       (gate)          (router →
                              (envelope)                     workflow)
```

- **Evidence** is repository fact: branch, registered feature, recorded handoff, the
  task graph. It judges nothing (`runtime/evidence.py`, `dag/tasks.py`).
- **State** is what those facts *imply*: entity classification, lifecycle state, review
  status, working-tree safety. Derived, never injected (`runtime/state.py`,
  `classification.py`, `lifecycle.py`).
- **Decision** is what the protocol *permits* for that state: one `Decision` envelope,
  `CONTINUE` or `TERMINAL_*` (`runtime/decision_engine.py`, `decision.py`).
- **Enforcement** is whether control flow may proceed: the `TerminalGate` dispatches for
  `CONTINUE` and terminates otherwise (`runtime/terminal_gate.py`).
- **Execution** is which single action runs: the router maps the granted intent to one
  dispatcher (`runtime/router.py`).

Collapsing any two of these is how governance is normally lost — a check that also acts,
a policy that also reads the repository, an enforcer that also decides. Ariadne keeps
them apart structurally, so no layer can quietly acquire another's authority.

## The kernel

The kernel is the part that a consumer, a host, or a prompt **cannot** change. It is not
a config schema; it is a small set of guarantees enforced in code and re-proven by the
suite on every change.

### The Decision Envelope

Every decision is a frozen, keyword-only `Decision` (`decision.py`), validated on
construction and re-validated wherever it is used. Validity is not a courtesy the
producer extends; it is checked by the consumer of the envelope:

- Every field is required and explicit. An omitted field is a protocol error, not a
  default.
- `protocol_version` must equal `2.1`; a `TERMINAL_*` decision must carry
  `next_legal_action = STOP`; a `CONTINUE` must carry a real next phase.
- The `PROTOCOL_` reason-code prefix is reserved, so a workflow cannot forge a framework
  rejection.
- `coerce()` re-reads even an existing `Decision` field by field, which downgrades a
  subclass that overrode `is_terminal` or a property, and rejects an object mutated
  after construction. Membership tests branch on the validated `decision` field, never
  on an overridable attribute, and validation uses the unbound `str.strip` so a lying
  `str` subclass cannot slip a fake value past a check and into dispatch.

### Fail closed

`protocol_invalid()` is the framework's own envelope: `TERMINAL_BLOCKED` with
`PROTOCOL_DECISION_INVALID`, carrying only a bounded description of what was rejected. A
malformed, unknown, or wrong-version payload becomes this — it never becomes `CONTINUE`.
The same instinct runs through the rest of the runtime: absent evidence classifies as
`UNKNOWN`, an unknown planning provider becomes "no registration", a malformed config
field falls back to the generic default with a recorded note. Absence of proof is never
read as proof.

### The Terminal Gate

The `TerminalGate` is the only path to dispatch. It is single-use: `_settle()` claims
the gate under a lock and refuses a second decision (`GateAlreadySettled`). For a
`TERMINAL_*` decision it renders one final report and calls the dispatcher **zero**
times; for `CONTINUE` it dispatches **exactly once**. There is deliberately no
convenience constructor that builds a gate per call — a per-call gate would make single
settlement a caller convention again instead of a runtime guarantee.

### The Router

The router (`router.py`) maps a granted `CONTINUE` to exactly one registered dispatcher
and refuses everything else (`RouterRefused`). It holds no policy: it does not classify,
resolve lifecycle, check safety, or judge terminality — those are settled before an
envelope reaches it. Two structural facts matter: it is reachable *only* as the gate's
dispatcher (so nothing routes for a terminal decision), and its registry is fixed at
construction (so one workflow's envelope can never reach another's dispatcher). That is
why "`dev close` never merges" is structural, not a prompt: no merge dispatcher is
registered for `DEV_CLOSE`.

### One decision policy

`decision_engine.decide()` is the single executable source of `CONTINUE`/`TERMINAL_*`.
It is a pure function of `ResolvedState`: it reads no repository and dispatches nothing.
The Markdown contracts (`ariadne doc --list`) describe these rules for humans and
agents; `tests/test_decision_consistency.py` runs the contract's tables through the
engine row by row and fails if code and document drift in either direction.

## Framework invariant vs project configuration

This is the line the whole design defends. **Configuration answers *where and what*; the
kernel answers *whether*.**

Never configurable — enforced in code, re-proven by the suite:

| Invariant | Enforced by |
| --- | --- |
| A terminal decision never dispatches | `TerminalGate.apply` branches on the validated field |
| A malformed decision fails closed | `coerce` → `protocol_invalid` → `TERMINAL_BLOCKED` |
| `CONTINUE` is the only dispatchable state | the gate dispatches only for `CONTINUE` |
| One decision point settles once | `TerminalGate._settle` under a lock, single-use |
| The router contains no policy | maps intent → dispatcher; `RouterRefused` otherwise |
| Decision policy is single-source | one `decide()`; the wiring audit fails on a second |
| A host cannot change decision semantics | same state + intent → same envelope everywhere |

Configurable — facts only a consumer knows, none of them decision policy:

| Configuration | Where |
| --- | --- |
| default branch, spec directory, tasks file, required artifacts | `[repository]` |
| which paths/files are framework (process) work | `[repository.framework]` |
| protected paths | `[repository.protected]` |
| planning provider (`directory`/`speckit`/`none`) | `[planning]` |
| quality gate names and evidence markers | `[[gates]]` |

A consumer that could set what `TERMINAL_*` means, when a Human Gate is required, or the
reason codes would be a *second decision policy* — the exact thing this runtime exists to
prevent. Those never appear in configuration, by construction (`config.py`).

## The SDLC model

The lifecycle is small and fixed. State is always **derived** from evidence; no entry
point accepts an injected lifecycle state.

```text
NEW → READY_FOR_IMPLEMENTATION → IN_PROGRESS → READY_TO_CLOSE → CLOSED
```

Insufficient or contradictory evidence resolves to `UNKNOWN`, which fails closed.
`CLOSED` has no legal successor.

Before lifecycle, the runtime classifies **what the branch is**, from evidence rather
than its name (`classification.py`):

- `PRODUCT_FEATURE` — branch, registered feature, spec branch, and recorded-state branch
  all agree, the feature directory exists, and required artifacts are present.
- `NON_PRODUCT` — changes are confined to declared framework paths, and any historical
  evidence consistently names a *different* feature (or there is none).
- `UNKNOWN` — anything else. Whether a path is "framework" depends on what the
  repository declares; re-deriving that from a built-in list would put one consumer's
  layout inside the kernel, so the kernel refuses to guess.

The four intents are permitted only from the states that make sense for them, and each
is bounded by what it must *never* do:

| Intent | Permitted from | Stops at / bounded by |
| --- | --- | --- |
| `dev new` | `CLOSED` or `NEW` base state | `READY_FOR_IMPLEMENTATION`; writes no product code |
| `dev next` | `READY_FOR_IMPLEMENTATION`, `IN_PROGRESS` | one dependency-coherent batch; no second batch |
| `dev close` | `IN_PROGRESS`, `READY_TO_CLOSE` | `READY_TO_CLOSE`; never merges (structural) |
| `dev merge` | `READY_TO_CLOSE` only, Human Gate `APPROVED` for a real merge | `CLOSED`; no branch/tag/worktree deletion |

`dev merge` is the strictest path: a merge is an outward-facing mutation, so an
unapproved or unknown Human Gate fails closed, while `--dry-run` mutates nothing and does
not require one.

## Integration

A consumer plugs into three seams — and no others.

```text
project configuration → repository facts       .ariadne/project.toml → ProjectConfig
planning provider     → where features live     integrations/planning.py
quality gate provider → structured verdicts     integrations/gates.py
```

**Planning** answers one fact — *is a feature registered, and where?* — through a
provider, so no path literal lives in the runtime. `DirectoryPlanning` is the built-in
default (`<spec_dir>/<branch>/`), which is what makes planning optional: the kernel has a
working planning path with nothing installed. `speckit` is imported lazily, only when a
repository names it, so the kernel never imports it and does not require it to exist.

**Quality gates** are structured evidence, never execution:

```text
Project Configuration → Quality Gate Provider → test = PASS  lint = PASS → Ariadne Runtime
```

Ariadne compiles the consumer's markers and searches recorded handoff text with them. It
never runs a command. A gate whose markers are absent is `UNKNOWN`, never `FAIL` — absence
of a recorded pass is absence of evidence, and the runtime already fails closed on that.
`recorded` means "some declared gate is proven", not "all"; the obligation that every
gate passed belongs to the consumer's gate run, and reading a sentence cannot discharge
it. Treating a partial handoff as failed would make the runtime's own reading a second
quality gate.

## Consumer configuration

`.ariadne/project.toml` is parsed into a frozen `ProjectConfig` (`config.py`). The
parser is total: unreadable fields fall back to the generic default and are recorded as
notes, so the result is always usable and always says what it could not read. A missing
file is legal and yields defaults — but not a free pass: with no framework paths
declared, no change can be proven non-product, so classification stays `UNKNOWN` and the
runtime fails closed.

```toml
[repository]
default_branch = "main"
spec_dir = "specs"
state_file = ".specify/memory/current-state.md"   # the durable handoff; omit if none

[repository.framework]
paths = [".ariadne/", ".github/"]   # changes here are process work, not a feature
files = ["AGENTS.md"]

[repository.protected]
paths = [".git/"]                   # exempt from safety judgement, always reported

[planning]
provider = "speckit"                # directory (default) | speckit | none

[[gates]]
name = "test"
markers = ['tests? pass', 'quality gate passed']   # patterns over recorded evidence
```

The defaults are deliberately generic: the kernel must run against a repository that has
never heard of Ariadne, and must not carry any consumer's paths as fallbacks. See
`examples/` for the same configuration written for a Rust, a Python, and a generic
project — three toolchains the runtime cannot tell apart.
