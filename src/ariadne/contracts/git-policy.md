# Git Policy

Use repository state as durable checkpoints. Before implementation, preserve the prepared specification checkpoint. Before review, commit implementation changes. Each verified review fix gets a separate fix commit; never amend an earlier checkpoint.

A repository may declare its own persistence commit point — the moment its work becomes durable — in its project policy. That is a product rule; generic Core does not infer one and does not need to know it.

For merge, use the repository's verified normal policy: target its configured default branch, `--no-ff`, no squash, rebase, or amend. Require a fresh closure checkpoint and explicit user authorization where the host requires it. On conflict, stop at a Human Gate.

Never automatically delete feature branches, tags, releases, or worktrees. Never clean, prune, reset, or stage protected paths. Stage explicit paths only; do not use broad staging that could include protected content. A safe status may exempt project-declared protected untracked paths, but must report them.
