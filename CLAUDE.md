# lotus-render — working norms

- **Envelope model**: any PR that adds a template section or materially changes a row
  emitter runs `python scripts/capacity_probe.py --verify-model` and, if the additive
  cost rule no longer holds, re-measures and re-banks `CEILING_POSITIONS` /
  `CEILING_TRANSACTIONS` (src/app/services/render_envelope.py) in the same change.
  The ceilings carry their provenance beside their values.
- **Report owns why, Render owns how it is communicated.** Postures
  (`allocation_presentation`, `benchmark_presentation`, `risk_posture`,
  `holdings_presentation`, `contribution_ranking`, `earnings_statement`) are read,
  never inferred from value presence or list length.
- **Promote on second consumer**: a template component moves to a shared module when a
  second family (or page) needs it — never on appearance of generality (#150).
- **Template versions**: measured, not remembered — `v1` and `v2` are `published`
  (2026-09-04), `v3` and `v4` are `development`. A published version's bytes never
  change; `validate_template_registry.py --write` re-approves development digests only
  and refuses with zero writes if a published version's dependency graph would move.
  Read the manifests before relying on this line: publication is a user decision and
  this file is a copy of it, not the source.
- Gates before push: `make lint typecheck code-health-gates openapi-gate
  template-registry-gate monetary-float-guard` and `make test-coverage`.
- **Never write file content through a shell heredoc.** The shell eats backslash
  escapes before the file exists, so `\b` in a regex becomes a literal `0x08`. It is
  invisible to terminals, diffs and re-reading. `CALL_SYNTAX` shipped that way and its
  guard could never fire. Write the script to a file and run it by path;
  `make test-unit` now byte-scans the tree for the class.
- **Prove a guard can fail** — on the instance that motivated it, after every edit
  including cosmetic ones — and test it against two different shapes of the class it
  names, asserting what it must ACCEPT as well as reject.
- **Workflow PRs land single-commit.** The merged-PR dispatcher tags each revision, and
  a tag write is refused when the tagged commit's workflow tree differs from `main`'s
  tip, so a multi-commit PR touching `.github/workflows` silently loses per-commit
  gating for its ancestors.
- **Lifted files stay byte-identical**: `scripts/check_branch_protection_policy.py` and
  its test are the canonical from `lotus-gateway`; verify with
  `git rev-parse <ref>:<path>` against gateway's merged main, never a working-tree hash.
  `quality/branch_protection_policy.v1.json` is this repo's own and must not be copied.
- Post issue evidence with `gh issue comment`; `gh issue close --comment` on an issue a
  PR already closed discards the comment silently.
