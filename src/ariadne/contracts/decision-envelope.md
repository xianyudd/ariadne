# Decision Envelope

A Decision Envelope is the structured value produced at a decision point. It is the only input the runtime terminal gate accepts, and it is the whole basis on which continuation is granted or refused. On every runtime path it is produced by one decision engine from resolved repository state — never assembled by hand, and never by the agent whose continuation it governs.

Core owns the envelope's shape and the meaning of each field. Core does not own control flow: enforcement lives in the runtime. Core also does not own any workflow's classification or reason-code vocabulary, and it never names a host tool, model, provider, or invocation syntax.

## Schema

`protocol_version` — required, non-empty string. The envelope schema version, currently `2.1`. The envelope is versioned independently of the framework release, so this value does not track the framework's own version number. The runtime accepts only its own version; an envelope from another version is invalid rather than best-effort adapted.

`workflow` — required, non-empty string. Identifier of the workflow that produced the decision. Core treats it as an opaque label.

`phase` — required, non-empty string. The declared phase that produced the decision.

`classification` — required key, nullable, non-empty string when present. The producing workflow's own entity classification. Core does not enumerate the permitted values and does not interpret them.

`decision` — required. Exactly one of the values declared in `contracts/terminal-contract.md`:

```text
CONTINUE
TERMINAL_SUCCESS
TERMINAL_BLOCKED
TERMINAL_NOT_APPLICABLE
```

`status` — required, non-empty string. The status reported to the caller. The status is reported; the decision is enforced. They are separate fields because a workflow may report several statuses under one decision.

`reason_code` — required key, nullable, non-empty string when present. A machine-stable reason owned by the producing workflow. It is mandatory when `decision` is `TERMINAL_BLOCKED`. The `PROTOCOL_` prefix is reserved for the framework; a workflow must not define its own `PROTOCOL_*` code.

`evidence` — required, ordered sequence of non-empty strings; may be empty. The deterministic facts the decision was derived from, in a stable order. Evidence is recorded, not re-derived: a terminal decision must not read further evidence to confirm itself.

`next_legal_action` — required, non-empty string. `STOP` for every `TERMINAL_*` decision. The next declared phase for `CONTINUE`. A `CONTINUE` whose next legal action is `STOP` is self-contradictory and therefore invalid.

`human_action_required` — required boolean. Whether a Human Gate decision is needed before any further action. Only a real boolean is accepted; a truthy string or integer is invalid.

## Reserved framework reason codes

```text
PROTOCOL_DECISION_INVALID
```

## Validity

An envelope is valid only when every required key is present, no unknown key is present, every field satisfies its declared type, the protocol version matches the runtime's own, `decision` is a declared value, `reason_code` is present for `TERMINAL_BLOCKED` and does not use the reserved `PROTOCOL_` prefix, and `next_legal_action` agrees with `decision`.

Normalisation happens before judgement, and only where it cannot change which decision is read: surrounding whitespace is stripped from every text field, so a padded value is read as its unpadded form rather than rejected; the reserved `STOP` token is canonicalised, so no casing of it can disagree with the decision it accompanies; and the reserved reason-code prefix is matched case-insensitively. Case is not normalised anywhere else, so `continue` is not `CONTINUE`. Normalisation uses the declared type's own operations rather than the supplied value's, so a value cannot exempt itself from being normalised.

Validity is decided by the runtime, not asserted by the producer. Every envelope is validated at the moment it is used, including one already presented as a structured envelope object: a producer's claim about its own envelope — a type it supplies, a value it computes, a method it overrides, a field it changes after construction — is never taken as evidence. The declared field wins. Each field is read once, so a value that changes between reads cannot show one form to validation and another to the envelope that gets enforced.

Anything else is invalid. The runtime replaces an invalid envelope with a framework-authored terminal envelope:

```text
decision    TERMINAL_BLOCKED
status      BLOCKED
reason_code PROTOCOL_DECISION_INVALID
```

Invalid input fails closed. It never resolves to `CONTINUE`, and no field of a rejected envelope is trusted or carried forward.

That framework-authored envelope is itself valid input. It is the one shape allowed to carry a reserved `PROTOCOL_` reason code on ingestion, so a rejection survives serialisation and re-reading with its evidence intact. Reproducing the shape gains a producer nothing, because the shape is terminal.

## Ownership boundary

```text
Core      defines envelope shape and decision semantics
Runtime   derives the envelope and enforces control flow over it
Workflow  executes the phase the envelope grants
Adapter   may dispatch an agent only after the runtime returns CONTINUE
```

A component that produces an envelope does not also decide whether the host may proceed, and a component that executes a phase does not produce the envelope that granted it. The runtime decides continuation from the envelope alone, so the same envelope produces the same control-flow outcome on every host.
