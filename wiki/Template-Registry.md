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

## Operator guidance

- use `make template-registry-gate` after any manifest edit
- use `make check` before pushing branch updates
- do not treat `deprecated_rerenderable` as acceptable for new production renders
- do not bypass blocked posture with local edits outside governed PR review

## Current first-wave template

- `template_id`: `portfolio-review`
- `template_version`: `v1`
- `report_type`: `portfolio_review`
- `report_data_contract_version`: `portfolio_review.v1`
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
- governance summary
- review observations

This richer contract keeps business-data assembly in `lotus-report` and keeps `lotus-render`
responsible for deterministic presentation only.
