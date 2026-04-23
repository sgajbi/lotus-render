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
