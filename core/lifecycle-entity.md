# Managed Lifecycle Entity

`/dev-merge` manages only a repository object that can be proven to be a current Agent SDLC Product Feature. Classification is evidence-based and host-independent:

```text
PRODUCT_FEATURE | NON_PRODUCT | UNKNOWN
```

## Evidence

Use the current repository facts, not a branch-name guess:

- current branch;
- `.specify/feature.json` registration;
- `specs/<feature>/spec.md`, `plan.md`, and `tasks.md`;
- the feature branch recorded by the specification;
- the active branch/feature in `current-state.md`;
- changed paths and their workflow/project scope.

`PRODUCT_FEATURE` requires these facts to correspond: registration points to an existing Feature directory, the Feature documents exist, and the current branch matches the Feature branch evidence. A completed feature's lifecycle evidence may then be evaluated by `dev-merge`.

`NON_PRODUCT` requires positive evidence that the current branch is infrastructure, workflow, tooling, or maintenance work: its registration does not correspond to the current branch, its lifecycle state does not identify it as the active Product Feature, and its changed paths are confined to declared non-product areas such as `.agent-sdlc/`, `.claude/`, `.agents/`, `.codex/`, `.opencode/`, `AGENTS.md`, `CLAUDE.md`, and workflow/project documentation.

`UNKNOWN` is the safe result when the evidence is insufficient or mixed. Absence of Product Feature evidence alone is not proof of `NON_PRODUCT`.

Do not create Feature metadata, tasks, closure records, or lifecycle state to make a branch mergeable.

`/dev-merge` status mapping is separate from the execution decision. Use `.agent-sdlc/core/terminal-contract.md` for the host-independent `CONTINUE`/`TERMINAL_*` short-circuit semantics.

```text
PRODUCT_FEATURE + all READY_TO_CLOSE gates → READY
PRODUCT_FEATURE + missing/failed gate    → BLOCKED
NON_PRODUCT                              → NOT_APPLICABLE
UNKNOWN                                  → BLOCKED
```

`NOT_APPLICABLE` is a successful lifecycle guard: `/dev-merge` correctly rejected an unsupported entity. It is not a merge failure.
