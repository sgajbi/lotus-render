# Repository Engineering Context

## Historical policy evidence consumer practice (#352)

Additive `composite-review v7` consumes only `composite_review.v7` and selection v3:
ordinary monthly evidence v3 and correction evidence v4, with policy proposal/approval v2.
Definition v1/v2 is an independent axis. `composite_historical.py` and adjacent
`composite_workbook/historical_*` modules own the typed selector, producer-namespaced schema,
proof bindings, ordered lineage, ten exact tables and custody identity. The producer schema is
also packaged under `app.contracts/historical_schemas` for installed distributions; its committed
blob must equal the public contract. Common eligibility/amendment helpers supply version-independent
hash/scope/link checks; frozen v4/v6 admission remains unchanged.

PolicyAdmission retains all scalar proof leaves, original base64 bytes and credentials, with
lexical object keys, original array order, RFC6901 escaping and null leaves. Amendments and
PolicyAdmission row ordinals continue globally across selected months. Missing applicable data
remains UNAVAILABLE; root amendment and policy run ID nulls have explicit NOT_APPLICABLE reasons.
The literal writer, physical capacity limits and existing persistence/replay lifecycle are reused.

Render checks recorded producer schema, hashes, scope, actor, intent, versions and custody.
Manage alone verifies actual original source format and current trust/revocation admission.
An embedded key, signature or rehashed envelope is not institutional acceptance or a fresh grant.
No consumer cryptography, calculator, trust service, ledger or runtime split is introduced.
Qualification is CONTROLLED_HISTORICAL_POLICY_EVIDENCE_REPLAY / NOT_ATTESTED / development.
Fixtures preserve exact Report fit r3 package bytes and r4 schema corrections around controlled
Manage graphs. Job/snapshot IDs are authored transport fixtures, not durable capture evidence.
Producer main/gates, consumer main/wiki and joined custody acceptance remain release conditions.
Use `tests/unit/test_composite_historical_*.py` and
`tests/e2e/test_composite_historical_journey.py`; retain all v1-v6 assets and banked workbooks.

## Monthly source-amendment consumer practice (#352)

`composite-review v6` admits only `composite_review.v6` with `selection_version=v2`.
Source proposal/approval/receipt version v2 is independent of CompositeDefinition v1/v2.
`composite_amendment.py` and `composite_workbook/amendment_*` own the additive consumer.
Shared eligibility binding checks receive a projection of common selector pins; retained source
products are never relabelled or rewritten. The ordered predecessor chain must terminate at the
original v1 receipt. Current and retained corrections preserve the approved policy and expected
population; published corrections bind the parent publication and its full response digest.
Amendment row order follows the frozen DTO field order, not JSON insertion order, so sorted
PinnedData reconstruction remains admissible. Row IDs retain the month index and the global
Amendments table row ordinal; the ordinal continues across months. Whole retained products and
extra approved source metadata remain in PinnedData under the existing physical limits and literal writer.

V6 is eligibility evidence only: it supplies no TWR, MWR, dispersion, contribution or model-fee
calculation and cannot inherit v5 financial authority. The golden/client envelope is explicitly
Render-authored component data around hash-pinned controlled Report examples. Opaque unit custody
digests are placeholders, not Report-produced revision identities. Actual emitted Report packages
and joined Archive acceptance are separate integration gates. Preserve all v1-v5 asset blobs.
Use `tests/unit/test_composite_amendment*.py` and the registered HTTP/SQLite component journey.
See `docs/composite-review-qualification-ledger.md` for pinned provenance and authority limits.

## Pooled composite consumer practice

Separate `composite-review v5` consumes only `composite_review.v5`. The `composite_pooled*`
contracts and `pooled_*` workbook modules independently validate retained source selection,
population, raw bodies, outcomes, exact table recipe and correction predecessor. They never run
XIRR, Modified Dietz, fee or amendment calculations. Full source evidence includes additive JSON
leaves. `capacity.py`, `custody.py` and `numeric_display.py` are shared with v4 after their second
consumer; the literal writer, finite resource limits and v1-v4 assets remain fixed.

Seven immutable producer packages under `tests/fixtures/composite-pooled-v5/` preserve candidate
`de686fd67e3582934c851cd371e28c7c8c68d88d`, qualified packet and byte provenance. Report implementation
merged at `4af947726dab91adec94b098fa9985d5bd6f15f6`; that does not repin historical fixtures.
Use `tests/unit/test_composite_pooled*.py` and `tests/e2e/test_composite_pooled_journey.py` for bounded
consumer proof. See `docs/composite-review-qualification-ledger.md` for authority limits.

## Repository Role

`lotus-render` is the Lotus document rendering service. It owns deterministic report rendering from
governed render packages into supported output artifacts and exposes only support-safe render
diagnostics and metadata.

## Business And Domain Responsibility

`lotus-render` owns rendering execution, template registry governance, render-attempt diagnostics,
artifact hashing, and render-engine runtime posture for enterprise reporting. It does not own
report-data assembly, upstream domain data retrieval, archive lifecycle, or replay/rerender
operator workflows beyond the render-stage contract defined by RFC-0102.

## Current-State Summary

Separate `composite-review v4` consumes only `composite_review.v4` through the same registered
XLSX engine and existing Render/Archive lifecycle. Its eight exact tables retain complete monthly
eligibility members, three ordered assessments, all failure/unknown reason occurrences, original
parent/current membership intervals, policy, lineage and six controlled Report disclosures.
`composite_eligibility*` contracts and adjacent `eligibility_*` workbook modules independently
validate the frozen producer schema, hash policies, population, pointers, cells and custody scope.
R3 keeps the r2 schemas unchanged and corrects cut semantics: selector source_cut_id binds
observations/evaluation; published receipt/membership/universe/publication bind the input-universe
cut. Other retained source locators are not rewritten. No eligibility evaluator, Report revision
calculator, new API, runtime split or Archive store is introduced. Operational ratios use IDENTITY
and twelve places; money, portfolio/event counts and booleans have distinct exact policies.
Known empty reasons and rule-unused null fields remain NOT_APPLICABLE; genuinely missing source
values remain UNAVAILABLE. No null becomes zero. The existing literal writer stays unchanged.
V4 preflight measures complete physical output including every row identity, CellEvidence,
ColumnPolicy, partition header, ArtifactIdentity fragment and compact ASCII PinnedData chunk;
all original limits remain fixed. Frozen authored Report r2 unit packages exercise registered
HTTP/SQLite idempotence and reopened-store reads plus independent complete Excel reconciliation.
Those authored inputs are UNIT_FIXTURE_NOT_SOURCE_CAPTURE. Separate actual controlled Manage
captures, emitted through Report's registered worker with offline replay transport, cover both
definition products and complete three-month source history. Their unchanged packages back the
v4 client/OpenAPI example and additive golden. Registered in-process Render/SQLite consumer proof
and complete independent Excel reconciliation do not establish authenticated joined network or
Archive acceptance. Measured actual packages use 601/602 physical data rows, 4574/4576 cells,
255163/266382 UTF-8 text bytes and twelve sheets; request sizes are 177244/188461 bytes.
Qualification remains CONTROLLED_ELIGIBILITY_SOURCE_REPLAY / NOT_ATTESTED / development.
Existing v1/v2/v3 schemas, layouts, manifests, retained bytes and qualification evidence stay fixed.

RPT01 composite-review XLSX is an additional bounded supplier slice: `composite_review.v1`
is the Report-owned immutable dataset, `composite-review v1` is an active development template,
and the registered `FormatRenderService` dispatches XLSX to pinned XlsxWriter 3.2.9 after exact
registry admission. PDF remains the required default and its Typst runtime governs readiness.
`src/app/services/composite_workbook/` separates retained identity/source reconciliation, exact
decimal display, evidence projection and literal XLSX writing. No investment calculation occurs
in Render. The authoritative consumer dictionary and limits are authored in
`wiki/Composite-Review-Workbook.md`; schema and exact source ownership are recorded in the source
contracts. The golden retains the exact registered Report PostgreSQL worker/composer package
with controlled synthetic source and test-only candidate family admission; Report's original
Render503 boundary remains explicit. It must not be described as production family admission
or custody proof. XLSX requires actual independent
workbook parsing and source/canonical/display reconciliation, rather than PDF image checks.
Qualification remains `EXPLICIT_RETAINED_CALCULATED_REPLAY`, `NOT_ATTESTED`; active/development
does not imply client publication. Archive's existing handoff receives exact bytes and exclusive
composite scope; Archive owns custody and download validation.
Separate `composite-review v3` admits only `composite_review.v3`, with the linked-only CARINO:v1
selector and exact seven-table matrix. `contracts/composite_linked.py`, `linked_source.py`,
`linked_tables.py` and `linked_custody.py` enforce typed source authority, complete populations,
canonical pointers, distinct DECIMAL_FACTOR/PERIOD_COUNT units and package/custody bindings.
Raw selected request identity preserves absent versus present-null restatement_sequence; all
non-null request sequences refuse. Uncaptured values retain SOURCE_PRODUCT_NOT_CAPTURED while
nullable source calculation IDs retain SOURCE_IDENTITY_NOT_PROVIDED. No financial linking or
revision-identity calculator is introduced. Exact sealed Report r4 PostgreSQL original/corrected
packages drive API/store/restart and full independent workbook reconciliation; the retained original
reproduces exact bytes. These controlled synthetic fixtures retain their Render503 producer boundary
and do not claim joined HTTP or institutional qualification. V1/v2 bytes and semantics stay fixed.
Separate R6 actual joined evidence uses Render runtime main
`535d0d5f87fd2f8bd701ba8707b343022060d030`, qualified in all eight natural release jobs, with the
registered Report PostgreSQL producer and actual Render/Archive HTTP clients. All three original,
financial-correction and retained-original workbooks independently reconcile 115 canonical cells,
115 display cells, 40 column policies, complete pinned datasets and job/snapshot/revision identity.
The retained original preserves original facts and revision while its new technical render identity
produces a distinct truthful artifact hash. Root independently accepts the three artifacts and
explicit O-to-T-to-C custody relationships. A fresh process restores an integrity-checked SQLite
backup into an isolated file, verifies all three jobs through the registered app and rejects foreign
tenants; every value in all 37 persisted columns and the complete schema match the backup.
The live database/WAL and recorded Render process remain unchanged. No live Render restart is
claimed. The qualification ledger records exact source, artifact and acceptance receipt hashes;
closure documentation is a successor to the tested runtime. Controlled frozen source replay,
`NOT_ATTESTED`, development publication and local trusted headers confer no institutional,
production authentication, RTO or enterprise certificate. Sealed R5/v1/v2 evidence stays fixed.
After Root independently accepts all restored-store comparisons and releases owned retirement,
Render retains a final integrity-checked consistent backup and all three actual artifacts/packages,
then stops only its recorded phase processes and verifies listener 55888 is absent. R5 and foreign
resources are untouched. The ledger distinguishes this resource disposition from the earlier
fixture and live acceptance receipts.
Separate `composite-review v2` admits only `composite_review.v2`, with 1–8 captured calendar/trailing
TWR source products, complete monthly selectors and exact primary-subvector pins. Typed product
shapes live in `contracts/composite_products.py`; `services/composite_workbook/source_products.py`
reuses existing digest/source-pin validation, while `product_tables.py` enforces the frozen eleven
column pointer/row matrix. Only product cumulative return gains financial table authority.
AnnualReturns always remains present (calendar source rows or its legacy uncaptured row), and
TrailingReturns is conditional on selected trailing products. Full raw products use existing
PinnedData/evidence/identity projection; there is no second renderer, serializer, calculator or
source client. Outer/embedded contract and template versions must agree. V1 manifest/layout/digest
and golden bytes stay unchanged. The copied v2 schema/layout agreement and genuine compressed
original/corrected six-year regression fixtures record exact Report provenance. Existing schema,
structural and physical limits remain fixed; additional raw products consume current headroom.
XLSX bounded determinism uses the versioned `composite-xlsx-members/v1` domain and unambiguous
sorted member-name/payload length framing. Raw ZIP SHA/size remains truthful custody identity;
container host metadata/compression may differ across platforms. The writer uses bounded in-memory
XML serialization to avoid platform line-ending drift without normalizing any source/cell content.
The default request envelope is bounded at 8 MiB. The XLSX writer permits 30,000 aggregate data
rows and 210,000 physical cells including partition headers; the independent 16 MiB text/output,
64-sheet, 1,000-row partition, 32,767 UTF-16-unit cell and execution controls remain enforced.
Oversized identity JSON uses `ordered_json_text_v1` descriptor and ordered JSON-string fragments;
ordinary identity cells and financial cells retain their literal representation. The wiki specifies
strict external reconstruction. A compressed genuine controlled 72-month Report package exercises
all 24,604 semantic cells and complete context/pins through the registered writer on CI hosts.

Controlled R5 v2 custody was exercised through the normal Report PostgreSQL worker and actual
Render/Archive HTTP clients at Render runtime main `383126231bb7744d6b4f3f60436ded86da5f0085`.
Root independently reconciled every 24,623 semantic canonical/display cells and 81 policies in
each original/correction/retained-original artifact, complete products/pins/context and current
correction chain, then repeated actual metadata/download/foreign-tenant reads after Archive
reopened the same PostgreSQL/object store in a new HTTP process. Render sealed three terminal
archived jobs into a consistent integrity-checked SQLite backup and retired only its recorded
processes/listener. The wiki records exact runtime heads, artifact hashes and acceptance receipts.
Closure documentation is a successor to the tested runtime commit; its validation must not be
represented as a new live source campaign. Source remains frozen accepted Performance capture
replay, controlled/NOT_ATTESTED. V1 semantics, finite limits, PDF behavior and runtime blobs remain
unchanged; annual member dispersion refusal and broader Report/enterprise gaps remain open.

`lotus-render` implements the RFC-0102 render-service side for the first-wave portfolio review PDF
flow. The repository contains the dedicated render-service runtime baseline, explicit render-attempt
domain models, structured request logging, support-safe system metadata, versioned render package
validation, source-controlled template registry enforcement, native Typst chart primitives
over Python-computed geometry, modular Typst templates, producer-backed golden PDF proof, and the first
store-backed internal render API. RFC-0105 first-wave render metrics now expose bounded render
submission, status lookup, diagnostics lookup, artifact metadata lookup, latency,
failure-category, artifact-size, and source-backed stale in-flight render signals without
high-cardinality or sensitive labels. RFC-0108 render supportability now publishes
`render.observability.render_supportability` through `/metadata` and
`lotus_render_supportability_total`, backed by drain state, render-store readiness,
template-registry availability, executable Typst/Docker runtime configuration, and aggregate
`accepted`/`rendering` stale posture. HTTP boundary configuration is explicit through the
`LOTUS_RENDER_` settings contract, including trusted hosts, CORS allow-listing, bounded streamed request body
limits, persistent-store enforcement, compile timeouts, bounded render-execution concurrency, and
stale in-flight thresholds.
The render store now uses versioned SQLite migrations, readiness-time schema validation, and
support-safe source evidence persistence for snapshot identity, lineage refs, disclosure refs,
caller identity, and package correlation/trace identifiers. Local Docker Compose mounts the store
on a named volume so render-job state survives container recreation in the supported local runtime.
Consumer-facing governance is declared in `contracts/render-supported-features.v1.json`,
`contracts/render-source-contracts.v1.json`, and `contracts/render-data-product-trust.v1.json`;
unit tests validate those contracts against the live template registry, OpenAPI paths, and metric
contracts. Active report-data contract versions are parsed through typed render content adapters
before Typst context generation, and active report/template/version tuples are routed through an
explicit template-context registry instead of a fallback report-type switch. Every active template
advertised through the registry now has a committed golden render package, expected PDF artifact,
and producer-provenance fixture under `tests/golden/`; governance tests fail when template manifests,
source contracts, nested source-contract variants, or golden sample evidence drift.
RFC40-WTBD-004 Slice 1 adds the
first-wave `proof-pack v1` template and registry manifest for
`dpm_proof_pack_report_input.v1`, establishing deterministic render-service support for
pre-trade proof-pack artifacts while keeping proof-pack truth and report-data assembly outside
`lotus-render`. RFC-0002 Slice 13 reviewed Idea evidence rendering is supported as a
`lotus-report`-produced proof-pack package with nested
`lotus_idea_evidence_pack_report_input.v1` source lineage, explicit
`client_publication_authority_granted=false`, and a committed producer-backed golden PDF proof;
Render does not own Idea evidence, report materialization, archive lifecycle, or client-publication
authority. RFC-0042 outcome-review support is active through the `outcome-review v1` template
and `dpm_outcome_report_input.v1` render package contract, establishing post-trade outcome-review
artifact rendering while keeping outcome truth and report-data assembly upstream. RFC41-WTBD-008
adds the first-wave `rebalance-wave v1` template and registry
manifest for `dpm_wave_report_input.v1`, establishing deterministic render-service support for
wave evidence artifacts while keeping wave state, proof-pack linkage, internal handoff evidence,
and report-data assembly outside `lotus-render`. The companion `lotus-report` implementation
submits complete render packages and records render outcomes while keeping business-data assembly
outside `lotus-render`. RFC-0023 Slice 11C adds optional `portfolio-review v1` rendering for
reviewed advisor-use narrative packages emitted by `lotus-report` from `lotus-advise`; the renderer
presents package lineage, review state, source hash, approved narrative text, and disclosure text
without approving, rewriting, inferring, or fetching advisory facts. RFC-0024 Slice 9 adds optional
`portfolio-review v1` rendering for advisor proposal memo packages emitted by `lotus-report` from
`lotus-advise`; the renderer presents memo lineage, advisor-use review posture, memo/source hashes,
section summaries, and disclosure text while keeping client-ready memo publication blocked upstream.

## Architecture And Module Map

Current repository baseline:

1. `src/app/main.py`: FastAPI application factory and lifespan wiring.
2. `src/app/api/routes/`: system routes and internal render APIs.
3. `src/app/contracts/`: OpenAPI-facing response models and render package contracts.
4. `src/app/core/`: settings and logging configuration.
5. `src/app/domain/render_attempts/`: render-attempt lifecycle models.
6. `src/app/domain/templates/`: template manifest models and registry compatibility rules.
7. `src/app/services/`: foundation services, package intake, render submission use case, Typst
   orchestration, and render-engine ports.
8. `src/app/dependencies/`: typed FastAPI dependency providers and the route-facing application
   container.
9. `src/app/infrastructure/`: concrete persistence adapters, including the sqlite-backed governed
   render job state for the first-wave synchronous render lifecycle.
10. `src/app/observability/`: RFC-0105 and RFC-0108 render metrics contracts and bounded
    Prometheus metric emitters.
11. `src/app/middleware/`: correlation, HTTP-boundary, and structured request logging middleware.
12. `templates/registry/`: PR-governed template source truth.
13. `templates/typst/`: governed Typst template source.
14. `tests/golden/`: golden render package, expected PDF, and producer-provenance proof inputs.
15. `tests/unit`, `tests/integration`, `tests/e2e`: test pyramid baseline.
16. `contracts/`: supported-feature, source-contract, and data-product trust declarations.

## Active Template Inventory

Template lifecycle, report-data contract versions, and disclosure fragments are governed by
`templates/registry/` and documented in `wiki/Template-Registry.md`. Keep this inventory aligned
whenever a template is added, deprecated, blocked, or moved across ownership boundaries.

`GET /system/templates` projects the exact manifest's nonempty `supported_output_formats`
alongside version identity, report types/data contracts and lifecycle/publication posture.
The projection copies the registry list and never inherits runtime or another version's formats.
Producers also require `/metadata` runtime capability/supportability and normal contract/lifecycle
admission; publication/distribution authority remains separate. Keep the response model, route,
OpenAPI examples and authored `wiki/API-Surface.md` consistent when this additive shape changes.

| Template | Version | Report data contract | Upstream package owner | Render boundary |
| --- | --- | --- | --- | --- |
| `portfolio-review` | `v1` (published 2026-09-04) | `portfolio_review.v1` | `lotus-report` | Client/advisor portfolio review presentation only. |
| `portfolio-review` | `v2` (published 2026-09-04; adds the rolling-risk trend band) | `portfolio_review.v1` (risk-trend block additive) | `lotus-report` | Client/advisor portfolio review presentation only; risk attribution ships in `v3`. |
| `portfolio-review` | `v3` (development; shared design `v1`) | `portfolio_review.v1` | `lotus-report` | Adds the report#254 risk-attribution decomposition in the slot `v2` reserved. |
| `portfolio-review` | `v4` (development; shared design `v2` -- vendored document face, #270 page frame) | `portfolio_review.v1` | `lotus-report` | The #270 design overhaul; content is `v3`'s verbatim. |
| `outcome-review` | `v1` | `dpm_outcome_report_input.v1` | `lotus-report` with outcome evidence from `lotus-manage` | Post-trade outcome-review artifact rendering only. |
| `proof-pack` | `v1` | `dpm_proof_pack_report_input.v1`; accepts nested `lotus_idea_evidence_pack_report_input.v1` source lineage | `lotus-report` with proof-pack evidence from `lotus-manage` or reviewed Idea evidence from `lotus-idea` | Deterministic proof-pack presentation only; no report-data assembly, archive lifecycle, or client-publication authority. |
| `rebalance-wave` | `v1` | `dpm_wave_report_input.v1` | `lotus-report` with wave evidence from `lotus-manage` | Rebalance wave evidence artifact rendering only. |

## Runtime And Integration Boundaries

1. Runtime model: standalone backend service with its own Docker image and independently scalable
   runtime.
2. Upstream dependencies: `lotus-report` submits complete render packages through the internal
   render API; future platform ingress and service-to-service auth flow through Lotus platform
   conventions.
3. Downstream consumers: `lotus-report` first; `lotus-gateway` only if support-safe operator
   surfaces are later added through governed APIs.
4. Boundary rules:
   - `lotus-render` must not fetch business data directly from domain services.
   - `lotus-render` consumes complete render packages only.
   - advisor-use narrative rendering is presentation-only and must be backed by the
     `reviewed_advisory_narrative` package in `report_data`.
   - `lotus-render` delivers the exact rendered bytes to the configured `lotus-archive` authority
     and persists Archive's returned custody identifiers and state. It does not infer or own
     archive lifecycle, retention, legal-hold, retrieval, or publication truth.
   - `lotus-render` owns render-engine/runtime posture, template compatibility, and artifact hash
     generation.
   - developer and CI proof should prefer the governed Typst container runtime when Docker is
     available; local Typst is fallback only when Docker is unavailable.
   - direct service HTTP access is bounded by trusted-host and request-body-size controls; browser
     access and authentication remain platform-ingress responsibilities until governed otherwise.
   - the tenant a job belongs to is the admitted `X-Tenant-Id` transport context (C6-REN-02,
     lotus-report#375): bound at create, scoping every read, carried into Archive custody, and
     never taken from the package's custody block, which is a claim that may only agree with it.
     Header absence/blankness now refuses before I/O; an unattributed legacy job is quarantined
     from tenant-scoped reads and is never backfilled or adopted on replay.
     The receiver counts raw ASGI tenant fields case-insensitively before scalar value admission:
     duplicates, including equal values, return `400 INVALID_TENANT_AUTHORITY` on all four render
     routes before job/store/engine/Archive effects. Single-header semantics remain unchanged.
     Registered HTTP/SQLite tests prove receiver admission; authenticated ingress forwarding
     remains a separate platform-owned qualification requirement.

## Repo-Native Commands

1. Install/bootstrap: `make install`
2. Lint: `make lint`
3. Typecheck: `make typecheck`
4. Template registry validation: `make template-registry-gate`
5. Unit tests: `make test-unit`
6. Integration tests: `make test-integration`
7. Code health gates: `make code-health-gates` (complexity, source size, dead code,
   dependency hygiene)
8. OpenAPI quality gate: `make openapi-gate`
9. Coverage gate: `make test-coverage`
10. Envelope capacity probe: `make capacity-probe`
11. CI parity: `make check` and `make ci`
12. Local runtime: `uvicorn app.main:app --reload --port 8310`
13. Image provenance: `make docker-build && make image-provenance-check` — starts the built
    image and compares its own `/version` against the variables that built it
14. Runtime inventory: `make runtime-sbom` — generates the SBOM inside an ephemeral container
    of the image; covers Python distributions only, not OS packages or the Typst binary

`make lint` also runs `monetary-float-guard`, so the float guard is reachable from
`make check` and `make ci` through lint rather than as a separate entry.

## Validation And CI Expectations

`lotus-render` follows the standard Lotus backend lane model scaffolded by
`automation/New-Lotus-Service.ps1`.

Key expectations:

1. local fast gate: `make check`
2. repo-native full gate: `make ci`
3. feature, pull-request, and exact-main workflows explicitly run `make code-health-gates`; unit
   fitness tests reject any gate advertised by `make check` / `make ci` but unreachable from GitHub
   Actions, and complexity/dead-code scanners fail closed on empty governed input
4. Docker build must stay green because the service is independently deployable
5. OpenAPI quality, strict typing, coverage gate, and security audit are all part of baseline CI
6. `main` branch protection requires strict PR Merge Gate status checks, conversation resolution,
   linear history, and admin enforcement. Human approval is optional in the solo-developer baseline;
   required GitHub checks and truthful PR evidence are the merge control.
7. Protection is asserted against a declared table, not assumed:
   `quality/branch_protection_policy.v1.json` states the governed posture field by field, the
   offline shape check is blocking in every lane, and the daily audit compares it to LIVE
   protection. Two measured gaps are open and neither can be closed from a session: `main` carries
   no `required_pull_request_reviews` block at all, so `dismiss_stale_reviews` is absent rather
   than false (issue #66), and no repository in the estate holds a secret with
   `administration: read`, so the live comparison fails closed on authentication until an operator
   provisions one. Read the daily job's result rather than this paragraph — the table is the claim,
   the job is the evidence.

## Standards And RFCs That Govern This Repository

Primary governing artifacts:

1. `lotus-platform/rfcs/RFC-0102-render-package-template-registry-and-render-service.md`
2. `lotus-platform/rfcs/RFC-0099-enterprise-reporting-and-document-archive-target-architecture.md`
3. `lotus-platform/rfcs/RFC-0072-platform-wide-multi-lane-ci-validation-and-release-governance.md`
4. `lotus-platform/rfcs/RFC-0084-mesh-governance.md`
5. `lotus-platform/rfcs/RFC-0091-enterprise-data-mesh-maturity-and-production-readiness.md`

## Known Constraints And Implementation Notes

1. The repository owns only render-stage behavior. `POST /renders`, render status,
   artifact-metadata reads, template compatibility, bounded-determinism diagnostics, and governed
   portfolio-review template rendering are in scope; report package assembly remains in
   `lotus-report`.
2. Keep render/data/archive boundaries strict from the start. Do not let `lotus-render` become a
   business-data authority.
3. Update repo-local wiki source and platform RFC/context truth when service ownership or runtime
   contracts change.
4. Determinism is currently bounded to the governed Typst `0.14.2` runtime envelope; raw artifact
   hashes remain truthful, while bounded-determinism proof normalizes volatile PDF metadata fields.
5. Committed golden PDFs for active templates are minted from the governed container-first Typst
   envelope so CI, local proof, and the future service image stay aligned; do not add an active
   template or additional producer/source-contract sample without a committed
   `render-package.json`, `expected.pdf`, and `tests/golden/producer-fixtures.v1.json` provenance.
6. `/health/ready` should remain truthful for both runtime posture and render-store availability,
   because the first-wave render APIs depend on persisted render-job state.
7. Render metrics must remain bounded to operation, status, failure category, artifact-size,
   supportability/stale in-flight posture, and envelope-refusal stage. Do not add render job,
   report job, portfolio, tenant, trace, correlation, raw package, or storage labels. The
   `stage` label admits exactly `admission` and `runtime`, and belongs only to
   `lotus_render_envelope_limit_refusals_total`: it separates a refusal the envelope model made
   correctly from a document it admitted and could not render, so a non-zero `runtime` count is
   the signal to re-measure the ceilings. Putting it on `lotus_render_operations_total` would
   multiply every series that counter carries for a signal specific to one failure category.
8. HTTP routes should consume typed dependencies from `src/app/dependencies/` rather than reading
   concrete adapters from raw `app.state`; route tests should use app-factory instances and
   dependency overrides instead of the module-level singleton app.
9. Persisted render job lifecycle updates are compare-and-set transitions fenced by a durable
   `claim_generation`: every successful claim increments it in the claiming UPDATE, and terminal
   and Archive-custody writes land only under the generation the caller holds, so a stale
   attempt that lost its job to takeover cannot commit output, return its bytes as the winning
   artifact, or overwrite the winner's custody (#313). Same-package `accepted`, `rendering`,
   `rendered`, and `failed` replays return prior truth without rerunning the renderer; terminal
   states are immutable unless a future governed recovery workflow changes that contract. A
   losing completion adopts stored truth and returns bytes only when they hash to the stored
   winning digest.
10. Settings live behind the `LOTUS_RENDER_` contract catalogued in `wiki/Configuration.md`.
    Required invalid configuration fails at service startup; runtime unavailability reports as
    `runtime_configuration_unavailable`; Typst/Docker compile timeouts persist as failed render
    jobs with category `timeout`; render execution capacity exhaustion returns
    `429 render_execution_capacity_exhausted`.
11. Render-store migrations are applied on startup and validated by readiness. The render store owns
    render-stage lifecycle, idempotency, support-safe evidence, diagnostics, and artifact hashes;
    archive retention, legal hold, retrieval, and distribution remain out of scope for
    `lotus-render`.
12. Persisted non-terminal render states require source-backed aggregate visibility and a typed
    diagnostics handoff. Keep stale classification in store/service policy, expose only bounded
    aggregate metrics, and use `/renders/{render_job_id}/diagnostics` for recovery decisions rather
    than raw logs or raw engine output.
13. Report-data contract interpretation belongs in `src/app/services/render_content.py`, not in
    routers, submission orchestration, or ad hoc Typst formatting code. Add a typed content adapter
    and focused contract-shape tests whenever a new active render data contract is introduced.
14. Template context routing belongs in `src/app/services/template_context.py`. Register each
    active report/template/version tuple explicitly and fail unknown combinations rather than
    falling back to another template's context builder.
15. Presentation postures are READ, never inferred. `allocation_presentation`,
    `benchmark_presentation`, `risk_posture`, `holdings_presentation`, `contribution_ranking`
    and `earnings_statement` are decided by `lotus-report`; `lotus-render` must not derive a
    posture from value presence, list length, or any other shape of the data. Report owns why a
    thing is shown, render owns how it is communicated.
16. The envelope cost model is measured, not assumed. Any PR that adds a template section or
    materially changes a row emitter runs `python scripts/capacity_probe.py --verify-model`, and
    if the additive cost rule no longer holds it re-measures and re-banks `CEILING_POSITIONS` and
    `CEILING_TRANSACTIONS` in `src/app/services/render_envelope.py` in the same change. The
    ceilings carry their provenance beside their values so a later reader can tell a measurement
    from a guess.
    Run from the repository root in the governed compile envelope. `--verify-model` runs only
    the five asymmetric mixes: exit zero means genuine model agreement, and nonzero means
    disagreement or an unqualified failure. Only a typed runtime `resource_limit_exceeded`
    counts as the predicted memory refusal; template/configuration/timeout failures cannot
    validate the model. A plain `make capacity-probe` remains the separate ceiling search (#332).
17. Promote a template component to a shared module on the SECOND consumer, not on the appearance
    of generality (#150). A component used once stays where it is used, however general it looks.
18. Tenant scope and claim ownership are orthogonal predicates in the same conditional writes:
    `tenant_id` decides what a caller may see, `claim_generation` decides which attempt may write
    (#313). `RenderStore.get` and `create_or_get_with_outcome` take the tenant as a REQUIRED
    keyword so a new caller cannot forget the scope; the service's post-admission re-reads of a
    row the same request already admitted pass `tenant_id=None` and say so at the call site.
    Foreign and absent must stay indistinguishable at every read surface.

## Working Practices That Cost Us Something To Learn

Allocation numeric qualification belongs in `src/app/services/allocation_values.py`.
Missing/null/sentinel/malformed/non-finite figures are unavailable, never additive zero.
Each bucket field stays unavailable if any contributor lacks that field; supplied zero
remains numeric. Tables preserve unknown bucket identity and fold only complete groups.
Charts use only positive supplied weights and supplied market values, with a visible
exclusion note; grouping coverage is unavailable if any weight is unknown. These rules
interpret supplied figures and do not change Report-owned presentation posture (#331).

Each of these was a live defect in this repository, not a precaution.

1. **Never write file content through a shell heredoc.** The shell interprets backslash escapes
    before the file exists, so `\b` in a regex becomes a literal `0x08`, `\t` a tab, `\n` a
    newline. It is invisible: terminals do not render `0x08`, diffs show nothing unusual, and
    re-reading the source cannot see it. `CALL_SYNTAX` in
    `tests/unit/test_no_machine_values_reach_a_page.py` shipped this way and could match only text
    containing a backspace, so the guard against Typst call syntax reaching a client page was inert
    and passed for that reason. Write the script to a file with an editor and run it by path.
    `tests/unit/test_sources_carry_no_corrupted_escapes.py` now scans the tree for the class.
2. **A guard must be proven able to fail, on the instance that motivated it, after every edit —
    including refactors that look cosmetic.** Falsifying once when written is not enough; the
    corruption above entered a file that had been correct.
3. **Test a guard against at least two different shapes of the class it names.** Three separate
    narrowings across the estate, each added for a measured reason and correct about its own case,
    left holes of identical shape. Also assert what the classifier must ACCEPT: a check widened
    until it rejects everything still passes its rejection tests.
4. **A workflow-touching merge used to lose per-commit gating, and showed no run rather than a
    red one.** Settled, not hypothesised: `GITHUB_TOKEN` cannot create a ref pointing at a commit
    whose tree contains workflow changes — it lacks the `workflows` scope — so the merged-PR
    dispatcher's per-revision tag write was refused with `POST .../git/refs` →
    `403 Resource not accessible by integration` while enumeration itself succeeded. Reproduced in
    lotus-gateway (run `34040043355`); control run `34025292627` dispatched a non-workflow revision
    and succeeded. The predicate is workflow-touching alone; multi-commit was a correlate.

    Since #310 the dispatcher tolerates exactly that refusal and nothing else: it dispatches
    `main`'s gate definition with `expected_sha=<revision>`, and every checkout in
    `main-releasability.yml` is pinned to `inputs.expected_sha`, so the tree under test is still
    the revision. Two consequences to plan for:

    - **Attribution.** A fallback run's `headSha` is main's tip, so `gh run list --commit
      <revision>` cannot find it. The gate's `run-name` carries the tested revision and
      `scripts/audit_main_gate_coverage.py` matches on it, time-bounded from the window's oldest
      commit; `release-evidence.json` records `commit_sha` as the TESTED revision beside a
      `workflow_definition_sha`. When looking a run up by hand, search the run title as well as
      `--commit`.
    - **The refusal is about the TIP, not about touching workflows.** `GITHUB_TOKEN` is refused
      only when the tagged commit's workflow tree differs from main's tip. A single-commit
      workflow-touching merge is therefore tagged fine — measured on #315's own merge
      (`eefbc4f`): `pull_request_target` read the dispatcher from post-merge `main`, so the NEW
      dispatcher ran, and its tag write succeeded because the commit was the tip. What the 403
      hits is an interior workflow-touching revision of a multi-commit merge (#308's case), or a
      tip that main has already moved past. The fallback exists for exactly those and is proven
      only when one occurs: after any merge under `.github/workflows`, resolve `main`'s SHA, look
      the run up by `--commit` and by title, and treat absence as the finding. If a revision is
      ever left with no run, the manual backfill is
      `gh workflow run main-releasability.yml --ref main -f expected_sha=<sha>
      -f triggering_pr=backfill` — no tag required.
    - **Classify GitHub's answer before acting on it, and classify the answer, not gh's prose.**
      The dispatcher first shipped reading any failed ref lookup as "the tag is absent" and any
      HTTP 403 on the create as the permitted refusal; a rate-limited lookup would have led to a
      create, and a rate-limited create would have become a fallback. `gh api` leaves GitHub's
      own answer on stdout either way — the ref object, or the refusal body with `status` (a
      JSON string) and `message` — and only that body is classified, through
      `scripts/read_github_api_answer.py`; gh's stderr line `gh: Not Found (HTTP 404)` is shown
      to the reader and read by nothing. Absence is `status` `404` alone and every other lookup
      answer is fatal (`lookup-failed status=…`, `none` when GitHub never answered); the fallback
      fires only on `status` `403` **and** `message` exactly `Resource not accessible by
      integration` (`fallback-permitted`), and every other create answer is fatal
      (`create-refused status=…`). Each dispatch emits one `dispatch-outcome` line naming
      `tested_source` (the tree the gate tests, its `expected_sha`) and `workflow_definition`
      (the ref whose workflow text runs: the tag, or `main` under the fallback) — the two
      identities Platform #772 asks to keep explicit. `tests/unit/test_dispatch_step_classifies_
      github_answers.py` executes the shipped step text against real temporary Git history with
      a recording `gh` on PATH that speaks the measured body contract; assert on the recorded
      calls and the parsed outcome lines, never on prose.

    The enumeration is the landed interval `base.sha..merge_commit_sha`, never the count-bounded
    `rev-list -n`: `pull_request.commits` describes the branch when the event fired, and after a
    rebase drops a commit already on main the count walks off the end of the PR's history into
    earlier merges' commits (lotus-platform#859). The count survives only as a cross-check whose
    two directions mean opposite things — fewer is a stale count, more is over-claiming and is
    refused.
5. **The branch-protection checker and its tests are lifted verbatim and must stay byte-identical**
    to the canonical in `lotus-gateway`; `quality/branch_protection_policy.v1.json` is the file that
    must NOT be, because it carries this repository's own posture. Verify parity by comparing git
    blob SHAs of committed refs (`git rev-parse <ref>:<path>`), never working-tree hashes, and lift
    only from the canonical's MERGED state. A local edit — even two type annotations — forks the
    copy on arrival and silently stops later canonical fixes reaching it; this repository's copy
    once sat 102 lines behind for exactly that reason.
6. **Post issue evidence with `gh issue comment`, not `gh issue close --comment`.** On an issue a
    PR's `Closes` keyword already closed, the close command aborts and the comment is silently
    discarded.
7. **An inventory tool reports on the environment it runs in, not the artifact you mean.**
    `python -m cyclonedx_py environment` with no argument inventories its own interpreter, so the
    release SBOM described the CI runner that `make install` had filled with dev extras, and never
    opened the image. It is the hard case because the wrong document looks entirely right: well
    formed, licensed, and containing every declared runtime dependency, because the runner installs
    those too. Generate from an ephemeral container of the image, and check the property that
    separates the two environments — the image cannot contain `pytest` or `ruff`. Asking only
    "does it list `fastapi`" passes on both.
8. **A build argument that is passed is not a build argument that arrived.** Every CI image
    reported `ci_pipeline_run_id=local` and `git_branch=HEAD` because nothing overrode the Makefile
    defaults, and no lane failed: an image asserting it was not a CI build is a green build. Verify
    provenance by starting the image and reading its own `/version` (`make image-provenance-check`),
    which also catches a dropped `ARG` or an `ENV` overwritten later in the Dockerfile — both
    invisible from the workflow side.
9. **Make re-expands environment-supplied values.** An imported variable is recursively expanded,
    so a branch named `feat/$(shell ...)` — which `git` permits — is executed rather than passed
    through. Measured here: `feat/$(shell echo PWNED)` became `feat/PWNED`. `shellquote` does not
    help; it protects the shell layer, and this happens in Make first. Read such values through
    `$(call raw_environment_value,NAME,default)`, which uses `$(value)` under an `$(origin)`
    guard.

## Context Maintenance Rule

Update this document when:

1. repository ownership changes,
2. repo-native commands or CI gates change,
3. runtime or integration boundaries change,
4. dominant local implementation patterns change,
5. current-state rollout or product posture materially changes.

## Cross-Links

1. `lotus-platform/context/LOTUS-QUICKSTART-CONTEXT.md`
2. `lotus-platform/context/LOTUS-ENGINEERING-CONTEXT.md`
3. `lotus-platform/context/CONTEXT-REFERENCE-MAP.md`
