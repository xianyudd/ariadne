# Host adapters

An adapter is how a host's own command reaches Ariadne. It is deliberately the
thinnest possible file:

```text
host command → ariadne dev <phase> → obey the result
```

That is all an adapter may be. It holds no lifecycle policy, no decision table, no
terminal semantics, and no rule about when a workflow applies — those are Ariadne's,
enforced in code, which is why the same repository state and intent produce the same
`DecisionEnvelope` on every host. An adapter that decides anything has stopped being
an adapter, and `tests/test_adapters.py` fails when one starts to.

## Families

| Family | Install to | Files |
| --- | --- | --- |
| `claude/` | `.claude/` | `skills/dev-*/SKILL.md`, `agents/reviewer.md` |
| `agents/` | `.agents/` | `skills/dev-*/SKILL.md`, `agents/reviewer.md` |
| `opencode/` | `.opencode/` | `commands/dev-*.md`, `agents/reviewer.md` |
| `codex/` | `.codex/` | `prompts/dev-*.md`, `agents/reviewer.toml` |

The OpenCode command routes to the portable adapter rather than restating it, so a
repository installing OpenCode installs `agents/` too.

## Installing

Copy the family your host reads into the repository, then fill in the one block a
template leaves blank:

```markdown
<!-- ariadne:project-policies -->
- docs/quality-gates.md
- docs/protected-paths.md
<!-- /ariadne:project-policies -->
```

Those are your documents, not Ariadne's. Ariadne neither supplies nor reads them: a
project's quality gates, protected paths, and architecture rules are the consumer's,
and they reach the runtime as configuration in `.ariadne/project.toml` rather than as
prose an agent interprets.

Everything else an adapter needs is already resolved:

- `ariadne dev <phase>` prints the granted phase **and** the path to its workflow
  document, so no adapter hardcodes an install path.
- `ariadne doc <name>` prints any contract Ariadne ships. Run `ariadne doc --list`
  for the set.

## Editing

Do not edit a template. They are generated:

```bash
python3 adapters/generate.py          # rewrite every template
python3 adapters/generate.py --check  # fail if one is stale
```

Sixteen workflow adapters and four reviewer adapters are nearly the same file, and
the failure mode worth preventing is not a badly written one — it is one that drifts
and grows a rule of its own. `adapters/generate.py` is the only place their wording
exists; the suite runs `--check`.
