# Template Registry

`lotus-render` keeps template compatibility and lifecycle truth in repo-authored manifest files under
`templates/registry/`.

## Current rules

- template selection is explicit by `template_id` and `template_version`
- render packages must carry a versioned render package contract and a versioned report-data
  contract
- compatibility is checked against:
  - report type
  - report-data contract version
  - locale
  - brand variant
  - output format
- lifecycle posture is explicit:
  - `active`
  - `deprecated_rerenderable`
  - `blocked_for_new_renders`
  - `blocked`
- publication posture is explicit and governed: `development` versions may change under
  re-approval; a `published` version's bytes never change (`published_at` and `published_by`
  are recorded in the manifest, and any further change creates the next version)
- every manifest pins its complete source dependency graph: `shared_design_version` names
  the shared design module (`templates/typst/_shared/<version>`) the version compiles
  against, and `template_digest` is a content hash of family bytes plus that pinned shared
  design -- the digest attests to the compiled dependency graph, not just one directory.
  The pin is Render-internal provenance: producers never see or choose it

## Operator guidance

- use `make template-registry-gate` after any manifest edit
- use `make check` before pushing branch updates
- re-approve changed development digests with
  `python scripts/validate_template_registry.py --write`; the command is atomic at the
  file level and refuses with zero writes if any published version's dependency graph
  would change
- create the next version of a family with `python scripts/create_template_version.py`
  (carries compatibility and the shared-design pin, resets publication to development,
  requires fresh approval facts; publishing, Report's version selection and golden
  re-pointing stay explicit decisions)
- do not treat `deprecated_rerenderable` as acceptable for new production renders
- do not bypass blocked posture with local edits outside governed PR review

## Adding or changing a template

A template is a governed artefact, so the work is not finished when it renders:

1. author the manifest under `templates/registry/<template_id>/<version>.manifest.json` with owner,
   approver, approval date, supported report types, contract versions, locales, brand variants,
   output formats and required disclosure fragments
2. register the template context explicitly for the report/template/version tuple — an unregistered
   combination fails rather than falling back to portfolio review
3. bank a golden sample at `tests/golden/<template>/<version>/` with `render-package.json` and
   `expected.pdf`, and record its provenance in `tests/golden/producer-fixtures.v1.json`
4. run `make template-registry-gate` after any manifest edit, and `make check` before pushing

Every active template must have golden proof, including nested producer variants such as reviewed
Idea evidence rendered through `proof-pack v1`. Mint it from the container-first Typst runtime so
the proof is stable across developer and CI hosts. See
[Development and Testing](Development-and-Testing#golden-proof).

Lifecycle changes are governed the same way: move a template to `deprecated_rerenderable`,
`blocked_for_new_renders` or `blocked` in the manifest through PR review, never by local edit.

## Current active templates

- `template_id`: `portfolio-review`
- `template_version`: `v1` -- **published 2026-09-04** (the #120 Archive-handoff go-live);
  bytes frozen with shared design `v1`
- `report_type`: `portfolio_review`
- `report_data_contract_version`: `portfolio_review.v1`
- `locale`: `en-SG`
- `brand_variant`: `private_banking`
- `output_format`: `pdf`

- `template_id`: `portfolio-review`
- `template_version`: `v2` -- **published 2026-09-04** (the rolling-risk trend release);
  bytes frozen with shared design `v1`. Adds the risk-trend band (source-owned unit
  semantics, observation-sequence strip, explicit source-stated gaps, stated coverage and
  scale conventions) and reserves the risk-attribution insertion point, which ships only
  in `v3`
- `report_type`: `portfolio_review`
- `report_data_contract_version`: `portfolio_review.v1` (the risk-trend block is additive;
  template version and data-contract version are independent axes)
- `locale`: `en-SG`
- `brand_variant`: `private_banking`
- `output_format`: `pdf`

- `template_id`: `outcome-review`
- `template_version`: `v1`
- `report_type`: `outcome_review`
- `report_data_contract_version`: `dpm_outcome_report_input.v1`
- `locale`: `en-SG`
- `brand_variant`: `private_banking`
- `output_format`: `pdf`

- `template_id`: `proof-pack`
- `template_version`: `v1`
- `report_type`: `proof_pack`
- `report_data_contract_version`: `dpm_proof_pack_report_input.v1`
- accepted nested source contract: `lotus_idea_evidence_pack_report_input.v1` when `lotus-report`
  adapts reviewed Idea evidence into the proof-pack report package
- `locale`: `en-SG`
- `brand_variant`: `private_banking`
- `output_format`: `pdf`

- `template_id`: `rebalance-wave`
- `template_version`: `v1`
- `report_type`: `rebalance_wave`
- `report_data_contract_version`: `dpm_wave_report_input.v1`
- `locale`: `en-SG`
- `brand_variant`: `private_banking`
- `output_format`: `pdf`

## Current first-wave contract shape

The active `portfolio-review v1` template now expects a richer governed `report_data` payload from
`lotus-report`, not just a summary paragraph and flat observation list.

Current document sections are sourced from render-package fields that include:

- client and portfolio identity
- review period label
- mandate context:
  - objective
  - risk exposure
  - booking center
  - advisor id
- portfolio metrics:
  - total value
  - invested value
  - cash balance
  - cash weight
- allocation summary
- performance periods
- performance highlight
- risk summary
- top holdings
- dense position detail
- dense transaction detail
- optional reviewed advisory narrative package:
  - proposal, narrative, review, policy, and source-hash lineage
  - approved advisor-use narrative sections
  - advisor-use disclosure text
- monthly and annual performance history
- governance summary
- review observations

This richer contract keeps business-data assembly in `lotus-report` and keeps `lotus-render`
responsible for deterministic presentation only.

The reviewed advisory narrative page is rendered only when
`report_data.reviewed_advisory_narrative.status == "included"`. The template presents the bounded
package supplied by `lotus-report`; it does not approve narrative content, rewrite advice, infer
suitability facts, or fetch additional advisory data. Packages may carry
`proposal_narrative.advisor_use_only.v1` in `disclosure_refs` when the advisor-use disclosure is
included.

## Outcome review contract shape

The active `outcome-review v1` template renders the RFC-0042 post-trade outcome-review artifact
from the bounded `DpmOutcomeReportInput` snapshot captured by `lotus-report`.

Current document sections are sourced from render-package fields that include:

- portfolio, outcome-review, proof-pack, rebalance-run, and wave identity
- review-window start and end
- outcome-review state and deterministic overall outcome
- expected, realized, variance, and explanation rows by outcome dimension
- source services and source hashes
- proof-pack section hashes
- report-input and outcome-review content hashes
- redaction policy and deterministic render metadata

This template must not fetch, infer, or recompute outcome truth. `lotus-manage` owns the
post-trade outcome authority; `lotus-report` snapshots the bounded handoff and `lotus-render`
presents it deterministically.

## Proof-pack contract shape

The active `proof-pack v1` template renders the RFC-0040 pre-trade proof-pack artifact from the
bounded `DpmProofPackReportInput` snapshot that `lotus-report` will materialize. It establishes the
render-service side of RFC40-WTBD-004 without making `lotus-render` a proof-pack or report-data
authority.

RFC-0002 Slice 13 uses the same render boundary for reviewed Idea evidence packs: `lotus-report`
materializes reviewed `lotus-idea` evidence into `dpm_proof_pack_report_input.v1`, preserves nested
`lotus_idea_evidence_pack_report_input.v1` source lineage, and submits a complete package for
rendering. `lotus-render` validates and presents the package deterministically; it does not
assemble report data, approve Idea evidence, create archive lifecycle records, or grant
client-publication authority.

Current document sections are sourced from render-package fields that include:

- portfolio, mandate, proof-pack, and as-of identity
- proof-pack state, supportability status, and supportability reason codes
- decision summary action and rationale
- report-safe proof-pack section summaries, section states, and reason codes
- source hashes
- nested source contract version and source-lineage rows when supplied by `lotus-report`
- explicit client-publication authority flag, expected to remain `false` for Idea evidence packs
- report-input and proof-pack content hashes
- redaction policy and deterministic render metadata

This template must not fetch, infer, or recompute proof-pack truth. `lotus-manage` owns the
proof-pack authority for DPM proof packs; `lotus-idea` owns reviewed Idea evidence; `lotus-report`
snapshots the bounded handoff and `lotus-render` presents it deterministically.

## Rebalance wave contract shape

The active `rebalance-wave v1` template renders the RFC-0041 wave evidence artifact from the
bounded `DpmWaveReportInput` snapshot materialized by `lotus-report`. It establishes the
render-service side of RFC41-WTBD-008 without making `lotus-render` a wave, proof-pack, or
report-data authority.

Current document sections are sourced from render-package fields that include:

- wave, trigger, and as-of identity
- aggregate item counts and supportability posture
- proof-pack readiness and degraded-count posture
- report-safe wave item rows with selected alternative and proof-pack linkage
- recent event timeline rows
- internal handoff count and explicit `external_execution_claimed=false` posture
- report-input and wave content hashes
- redaction policy and deterministic render metadata

This template must not fetch, infer, or recompute wave truth. `lotus-manage` owns wave state,
proof-pack linkage, supportability, source refs, and internal handoff evidence; `lotus-report`
snapshots the bounded handoff and `lotus-render` presents it deterministically.

## Portfolio review section configuration

`portfolio-review v1` renders the full client report by default. Callers can provide
`render_context.sections` to render a selected subset while preserving the same typography,
spacing, page setup, and component styling.

Supported section keys:

- `cover`
- `contents`
- `overview`
- `performance`
- `allocation`
- `positions`
- `transactions`
- `advisory_narrative` when the package includes reviewed advisor-use narrative content
- `appendix`

Common aliases such as `asset-allocation`, `detailed-positions`, `transaction-list`, and
`additional-information` are normalized by the renderer. `reviewed-advisory-narrative`,
`reviewed-advisory`, and `advisor-narrative` select the optional advisory page when the included
package is present. Unknown section keys are ignored; if no valid section remains, the renderer
falls back to the full report.

The maintainable design-system note for the Typst implementation is authored in
`docs/portfolio-review-typst-design-system.md`. It records the layout rhythm, typography scale,
component model, deterministic SVG chart pipeline, rendering command, and focused validation gate
used for this template.

The source-backed attribute inventory is authored in
`docs/portfolio-review-attribute-inventory.md`. It records every client-facing report attribute,
business meaning, source application, source object or endpoint where known, current placement
status, and source gaps. Desired report fields that are not yet source-backed must be added to that
inventory and the RFC before they appear in the template.

## Read next

1. [API Surface](API-Surface) — the package contract a template is selected by
2. [Architecture](Architecture) — where template selection sits in the render path
3. [Development and Testing](Development-and-Testing) — golden proof and the registry gate
