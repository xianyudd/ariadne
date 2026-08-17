# Design Principles

These are not aspirations. Each principle below is one the code already enforces, stated
so the enforcement is visible and cited to where it lives. If a principle here were
removed from the code, a specific test would fail. For the structures themselves see
[`architecture.md`](architecture.md) and [`runtime.md`](runtime.md).

## 1. The repository is the only durable truth

A session is disposable; the repository is not. The runtime persists no decision, caches
no lifecycle state, and carries nothing between invocations. Every call recomputes the
answer from repository evidence, so there is no in-memory state to corrupt, disagree with
Git, or leak from one run into the next.

*In the code:* `ResolvedState` is built fresh per invocation from `runtime/evidence.py`;
`status`, `inspect`, and every `dev` phase recompute it. The declared `state_file` is read
as *evidence of what was recorded*, never as authority (`config.py`,
`ariadne doc state-contract`).

## 2. Deterministic evidence precedes any judgement

Before anything is decided, the facts are gathered deterministically: branch, registered
feature, recorded handoff, the task graph. Judgement runs only on those facts. The agent
never supplies the lifecycle state it is then judged against — no entry point accepts an
injected state, so an agent cannot assert its way into a phase.

*In the code:* `classification.py` and `lifecycle.py` derive state from evidence;
`decide()` is a pure function of `ResolvedState` that reads no repository. The CLI exposes
no flag to set lifecycle or classification.

## 3. A proposal is not an authorization

A workflow can propose anything; proposing does not make it permitted. Authorization is a
separate, validated artifact — the `Decision` envelope granted through the gate — and the
framework's own rejections cannot be forged by the thing being judged. The sharpest case
is merge: an intent to merge is a proposal, and only an explicit Human Gate turns it into
authorization.

*In the code:* the `PROTOCOL_` reason-code prefix is reserved, so a workflow cannot emit a
framework rejection (`decision.py`); a real merge requires `human_gate == APPROVED` or it
fails closed (`decision_engine.py`, `REASON_MERGE_AUTHORIZATION`).

## 4. Fail closed

The default answer is *no*. Missing, ambiguous, or malformed input never resolves to
permission. A payload that cannot be validated becomes a terminal block; evidence that
cannot be established becomes `UNKNOWN`; a config field that cannot be read becomes the
generic default with a note. Absence of proof is never read as proof.

*In the code:* `protocol_invalid()` → `TERMINAL_BLOCKED` / `PROTOCOL_DECISION_INVALID`
(`decision.py`); `UNKNOWN` classification and `GIT_STATE_UNAVAILABLE` block
(`classification.py`, `decision_engine.py`); the total config parser in `config.py`.

## 5. Deciding and enforcing are different jobs

The component that decides *what is permitted* is not the component that decides *whether
control flow proceeds*. The engine returns an envelope and dispatches nothing; the gate
acts on the envelope and decides nothing. Neither can quietly become the other, because
each is missing the other's inputs — the engine has no dispatcher, the gate has no policy.

*In the code:* `decision_engine.decide()` is pure and dispatch-free; `TerminalGate`
(`runtime/terminal_gate.py`) owns dispatch and branches only on the validated `decision`
field.

## 6. The router carries no policy

Dispatch is a lookup, not a judgement. By the time an envelope reaches the router,
everything has been decided; the router maps one granted intent to one registered
dispatcher and refuses the rest. Because its registry is fixed at construction and it is
reachable only as the gate's dispatcher, whole classes of error are structurally
impossible rather than merely tested against — "`dev close` never merges" holds because no
merge dispatcher exists for that intent.

*In the code:* `router.py` — `RouterRefused` for anything unmapped; the per-intent
registry is copied at construction; no merge dispatcher is registered for `DEV_CLOSE`.

## 7. One decision policy, stated once

The rules that say `CONTINUE` or `TERMINAL_*` live in exactly one executable place. The
Markdown contracts describe those rules for humans and agents, but description and code
are held in agreement by a test, not by discipline — and a second decision policy
appearing anywhere is itself a build failure.

*In the code:* `decision_engine.py` is the single policy; `tests/test_decision_consistency.py`
runs the contract tables through it row by row; the wiring audit fails if a second
decision point appears.

## 8. Termination is structural, not remembered

A terminal decision does not dispatch, and a decision point settles once — not because
callers remember to check, but because the structure allows nothing else. The gate claims
itself under a lock and refuses a second decision; a terminal branch never reaches the
dispatcher. Single settlement is a property of the runtime, which is why there is
deliberately no per-call convenience gate that would hand the guarantee back to callers.

*In the code:* `TerminalGate._settle()` under a `threading.Lock` (`GateAlreadySettled`);
dispatch reached only on the `CONTINUE` branch; no per-call gate constructor exists.

## 9. Envelopes are validated where they are used, not where they are made

Trust is never extended to a producer. Every envelope is re-validated at the point of use,
so a decision cannot be forced through with a subclass, an overridden property, a lying
comparison, or an object mutated after construction. Validity is checked by the consumer of
the envelope, every time.

*In the code:* `Decision.coerce()` re-reads an existing `Decision` field by field and
downgrades subclasses; membership tests branch on the validated field; validation uses the
unbound `str.strip` to defeat a lying `str` subclass (`decision.py`).

## 10. Host independence

The runtime does not know or care what is calling it. A host adapter translates a command
into `ariadne dev <phase>` and obeys the result; it holds no lifecycle policy, no decision
table, no reason codes, no terminal semantics. The same repository state and intent
produce the same envelope on every host — a host cannot change what a decision means.

*In the code:* adapters under `adapters/` are generated from one template
(`adapters/generate.py --check`); `tests/test_adapters.py` fails if a template was
hand-edited, since near-identical prompt files are exactly where a rogue rule would hide.

## 11. Product independence

The runtime governs a lifecycle without knowing the product inside it. It has no knowledge
of any language, build tool, or test runner, and no code path that could acquire one. What
counts as "framework work", where features live, and what a passing gate looks like are
all facts the consumer declares — never built-in lists, because a built-in list would put
one consumer's layout inside the kernel.

*In the code:* `classification.py` refuses to re-derive framework paths from a built-in
list; `integrations/gates.py` reads markers over recorded text and runs no command;
`integrations/planning.py` imports `speckit` lazily, only when a repository names it.

## 12. The runtime stays minimal

The system is a pure decision function, a gate, and a router. It adds no async runtime, no
event bus, no scheduler, no repository/service layer, no database, and no runtime
dependency. Standard library only. New machinery is a governance decision, not a
convenience — expanding the runtime is exactly what most changes must *not* do.

*In the code:* `pyproject.toml` declares `dependencies = []`; the only concurrency
primitive is a single `threading.Lock` in the gate; there is no framework source tree to
grow inside a consumer, because Ariadne is installed, not vendored.
