# Managed Lifecycle Entity

Ariadne manages only a repository object that can be proven to be a current Product Feature. Classification is evidence-based and host-independent:

```text
PRODUCT_FEATURE | NON_PRODUCT | UNKNOWN
```

Every workflow entry point classifies before it decides, and each reads the result for its own purpose: `/dev-merge` treats a non-Product entity as nothing to merge, while `/dev-new` treats it as an error. The classification itself is the same fact in both cases, and `runtime/classification.py` is its executable form — `RepositoryEvidence` in, one of these three values out, and nothing else. It judges no lifecycle and decides no workflow.

## Evidence

Use the current repository facts, not a branch-name guess:

- current branch;
- the Feature registration reported by the configured planning provider;
- the Feature's required artifacts in its registered directory;
- the feature branch recorded by the specification;
- the active branch/feature in the recorded state file;
- changed paths and their framework/product scope.

Which planning provider reports the registration, where Feature directories live, which artifacts are required, and which file records state are all consumer configuration. Classification reads the facts, never the paths: a repository that keeps Features somewhere else is classified by the same rules.

`PRODUCT_FEATURE` requires these facts to correspond: registration points to an existing Feature directory, the Feature documents exist, and the current branch matches the Feature branch evidence. A completed feature's lifecycle evidence may then be evaluated by `dev-merge`.

`NON_PRODUCT` requires positive evidence that the current branch is infrastructure, workflow, tooling, or maintenance work: its registration does not correspond to the current branch, its lifecycle state does not identify it as the active Product Feature, and its changed paths are confined to the framework paths and files the repository declares. A repository that declares none cannot prove `NON_PRODUCT`, which is why an undeclared change is `UNKNOWN` rather than assumed harmless.

`UNKNOWN` is the safe result when the evidence is insufficient or mixed. Absence of Product Feature evidence alone is not proof of `NON_PRODUCT`.

Do not create Feature metadata, tasks, closure records, or lifecycle state to make a branch mergeable.

A classification is not by itself a decision. What each entry point does with it, the reportable status it carries, and where control flow may go next belong to `terminal-contract.md` and the engine it specifies; the status is a projection of that one decision rather than a second mapping evaluated alongside it. This document is therefore the last word on *what the entity is*, and never on *what happens next*.

`NOT_APPLICABLE` is a successful lifecycle guard: `/dev-merge` correctly rejected an unsupported entity. It is not a merge failure.
