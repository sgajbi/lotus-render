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
- **Template versions**: `v1` is `development` (#216); a published version's bytes never
  change, and `validate_template_registry.py --write` is the development-only affordance.
- Gates before push: `make lint typecheck code-health-gates openapi-gate
  template-registry-gate monetary-float-guard` and `make test-coverage`.
