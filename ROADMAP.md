# Roadmap

This roadmap is deliberately short. Ariadne is a governance runtime, and the burden of
proof for adding to it is high: most proposals below are candidates to be *justified or
dropped*, not commitments. A feature earns a place here only when it strengthens the core
question — *does the agent have exactly one legal next action?* — without turning the
runtime into an orchestrator, a planner, or a second decision policy.

**A note on version numbers.** `pip show ariadne-sdlc` reports `2.1`, and the decision
envelope's `PROTOCOL_VERSION` is `2.1`. That number tracks the *decision protocol*, whose
semantics matured to 2.x while the framework was still embedded in its first consumer. The
milestones below track the *standalone project* instead — its first independent release is
"v0.1 Standalone Foundation." The two are intentionally decoupled: the protocol is stable
and the standalone project is young, and pretending either fact away with a shared number
would mislead.

## v0.1 — Standalone Foundation — shipped

The runtime is a self-contained, host-independent package. This milestone is done.

- **Closed runtime chain.** `Repository → Evidence → State → Decision → TerminalGate →
  Router → Workflow`, with the layering enforced in code: evidence judges nothing, the
  engine dispatches nothing, the gate maps nothing, the router decides nothing.
- **One decision policy.** A single pure `decide()`; Markdown contracts describe it and a
  consistency test fails on any drift between the two.
- **Fail-closed envelope.** Frozen, revalidated-on-use `Decision`; malformed input becomes
  `TERMINAL_BLOCKED` / `PROTOCOL_DECISION_INVALID`; single-settlement `TerminalGate`.
- **Consumer seams.** `ProjectConfig` (`.ariadne/project.toml`), a planning provider
  (`directory` / `speckit` / `none`), and marker-based quality-gate evidence — no product
  knowledge in the kernel.
- **Host independence.** Generated, drift-checked adapter templates for Claude Code, Codex,
  OpenCode, and `AGENTS.md`.
- **Zero runtime dependencies**, Python 3.11+, standard library only; installed via pip /
  pipx, not vendored.
- **Deterministic test suite** plus a mutation harness exercising hostile envelope shapes
  and an architecture-level wiring audit.
- **First real-world consumer validated.** tflow (a Rust product repository) exercised all
  four workflows across every branch state and intent. It is one data point, not yet a
  track record.

## Next — candidates under consideration

Each of these is a *candidate*. None is committed, and each must pass the same test: does
it make the single legal next action clearer or its enforcement stronger, without
expanding the runtime's job?

- **A capability / authorization model.** Today authorization is effectively one bit — the
  Human Gate on merge. A first-class model would let a consumer declare *which* actions
  require which authorization, without moving decision semantics into configuration. This
  is the groundwork everything speculative below depends on.
- **Stronger review and Human-Gate enforcement.** Review status and the Human Gate are read
  as recorded evidence. Tightening how that evidence is proven — and making the gate harder
  to satisfy by accident — is a natural next increment.
- **Project-integration ergonomics.** Lower the cost of onboarding a new consumer:
  configuration validation, clearer diagnostics from `status` / `inspect`, a scaffolding
  path that does not depend on reading `examples/` by hand.
- **Adapter drift detection.** Adapters are copied into each consumer, so a consumer can
  drift from an upgraded Ariadne until it re-copies. A supported way to detect and report
  that drift from the consumer side would close a known gap noted in the README.
- **Governance hooks for procedural evolution.** *Not* skill evolution itself — the
  enforcement primitives (authorization, provenance, audit) that would have to exist
  *before* any self-modifying behavior could be governed rather than merely permitted.

## Future / Research — not yet a runtime concern

This layer is exploratory. It is recorded so the direction is legible, and fenced off so no
one mistakes it for a missing piece of the current runtime.

- **Skill evolution (SkillOpt-style).** Agents proposing improvements to their own
  procedural skills, evaluated and admitted under governance.
- **Procedural memory.** Durable, repository-anchored memory of how work was done, usable
  as evidence without becoming authority.
- **Multi-objective validation.** Deciding under several graded objectives at once, rather
  than a single pass/block verdict.
- **A governed self-evolving Agent SDLC.** The union of the above: a lifecycle that can
  improve its own procedures while every change still passes through the same fail-closed,
  single-settlement decision boundary.

**Skill evolution is not a gap in the runtime core.** The runtime is complete for what it
governs today: deciding the one legal next action and enforcing it. Skill evolution is a
research layer that would be *built on top of* a proven governance boundary — and it earns
its place only after the capability and authorization groundwork under "Next" exists to
govern it. Until then, adding it would mean shipping self-modification without the means to
govern it, which is the opposite of what this project is for.
