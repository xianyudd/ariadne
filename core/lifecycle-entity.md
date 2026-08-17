# Managed Lifecycle Entity

Agent SDLC manages only a repository object that can be proven to be a current Product Feature. Classification is evidence-based and host-independent:

```text
PRODUCT_FEATURE | NON_PRODUCT | UNKNOWN
```

Every workflow entry point classifies before it decides, and each reads the result for its own purpose: `/dev-merge` treats a non-Product entity as nothing to merge, while `/dev-new` treats it as an error. The classification itself is the same fact in both cases, and `../runtime/classification.py` is its executable form — `RepositoryEvidence` in, one of these three values out, and nothing else. It judges no lifecycle and decides no workflow.

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

A classification is not by itself a decision. What each entry point does with it, the reportable status it carries, and where control flow may go next belong to `.agent-sdlc/core/terminal-contract.md` and the engine it specifies; the status is a projection of that one decision rather than a second mapping evaluated alongside it. This document is therefore the last word on *what the entity is*, and never on *what happens next*.

`NOT_APPLICABLE` is a successful lifecycle guard: `/dev-merge` correctly rejected an unsupported entity. It is not a merge failure.
