# Composite review workbook

Current scope: RPT01 XLSX v1, v2 captured calendar/trailing returns and v3 pinned linked analysis. Qualification is
`EXPLICIT_RETAINED_CALCULATED_REPLAY`, publication `NOT_ATTESTED`, manifest `development`.
Archive custody does not confer official or client-publication authority. Remaining report families
and enterprise qualification stay open.

Use the version/pointer dictionary below, [R5 custody evidence](#controlled-r5-custody-qualification),
[R6 linked-analysis evidence](#controlled-r6-linked-analysis-qualification), and
[verification](#reproducible-verification) for checks
and the separate fixture/profile boundaries.

## Versioned calendar and trailing products

The existing `render_package.v1` envelope, `POST /renders`, literal writer and Archive lifecycle
serve both versions. Select the exact tuple advertised by `GET /system/templates`:

| Template | Outer and embedded report-data contract | Format |
|---|---|---|
| `composite-review v1` | `composite_review.v1` | `xlsx` |
| `composite-review v2` | `composite_review.v2` | `xlsx` |
| `composite-review v3` | `composite_review.v3` | `xlsx` |

Mixed versions fail closed. Retained v1 packages keep their original manifest/layout/digest and
golden semantics; adding v2 never reinterprets their source snapshot. The named v2 OpenAPI example
`composite_products_xlsx_package` is an exact small registered Report producer package using a full
retained two-month source response and trailing-two response. Its controlled replay and Render503
profile boundary is recorded in the golden producer proof; the example is not custody evidence.

V2 requires 1–8 uniquely keyed `source_products`. Each contains a strict calendar-year or trailing
month selector, fixed `POST /composites/twr` provenance, the full raw captured source response and
its canonical SHA256. The response digest must match both capture and selector; tenant, composite,
fee view, currency and methodology match the primary capture. Source-stated calculation, engine,
fingerprint, statuses and complete monthly windows are reconciled. Product windows must be an
ordered, deep-equal subvector of this version's primary pins. Calendar selections cover exactly
January–December of the declared year; trailing selections contain exactly the declared months and
end at the primary as-of date. A recomputed digest cannot excuse changed or stale pins.

`AnnualReturns` is always present: selected calendar products replace its old unavailable row with
source-backed return rows. With no calendar products its unchanged three-column unavailable
section remains. `TrailingReturns` exists only when trailing products are selected. All legacy
table identities remain; no `CalendarReturns` alias is supported. Rows are exactly the matching
product keys in source-array order, retaining their original array indexes. Both return tables use
the agreed eleven columns and pointers below; each prefix is `/source_products/<canonical-index>/`.

| Column | Exact relative source pointer | Type |
|---|---|---|
| `product` | `pin/product_key` | TEXT |
| `kind` | `pin/kind` | TEXT |
| `period_start`, `period_end` | `pin/selection/period_start`, `pin/selection/period_end` | TEXT |
| `return_view` | `pin/selection/return_view` | TEXT |
| `currency` | `pin/selection/reporting_currency` | TEXT |
| `return` | `source_response/cumulative_return` | DECIMAL_RETURN / DECIMAL_RATIO / PERCENT |
| `status` | `source_response/status` | TEXT |
| `methodology` | `source_response/methodology` | TEXT |
| `engine_version` | `pin/selection/engine_version` | TEXT |
| `response_digest` | `source_response_digest` | TEXT |

The only new financial path is the exact admitted-index cumulative return. It remains literal
canonical source text and displays ratio-to-percent once at two decimal places with HALF_UP.
Product period/member/additive financial paths, noncanonical indexes, TEXT relabelling, financial
facts placed in `report_facts`, mismatched product rows and fabricated availability/reasons refuse.
The ten named text paths form an explicit allowlist. Extra raw source fields are retained in
`PinnedData`; retention does not grant table authority. Full CellEvidence, ColumnPolicy, source
products and context remain reconstructible with the existing strict identity codec.

The exact Report-owned schema and frozen shared table agreement are copied to
`contracts/report-data/composite_review.v2.schema.json` and `composite_review.v2.layout.json`.
The consumed schema artifact SHA256 is
`f7b25c9f7054c20e568a451ee193ec16c5123b36d474409c648461689394f2de`.
The separately reviewed Report PR #423 revision `6f6380e5ba7bf3b0087fa416d93bdbb608eea458`
commits schema bytes with SHA256 `0239fca6616e43c63b209071fbdd5c919a13e5c062b78c2cbf71a6f484de2269`.
Their parsed JSON is exactly equal; their raw bytes differ. The source-contract inventory records
both provenances. The agreed artifact hash identifies the retained supplier artifact and does not
claim byte equality with the producer commit or qualification of its eventual merged main.
Narrow Git attributes preserve the hash-bound supplier files across host checkouts.

Consumer limits remain 32 tables, 32 columns, 10,000 rows per logical table, table IDs of 31
characters, row IDs/titles/labels of 256, column IDs of 128 and 32 reason codes. Existing structural,
physical, tenant, literal and execution controls below remain unchanged. Raw financial authority
belongs to Performance; Report owns capture/revision vectors and immutable rerender identity.
Render performs no financial calculation or upstream request.

Calendar-year cumulative **return** is distinct from annual member **dispersion**. A source
`POLICY_BASIS_MISMATCH` refusal supplies no dispersion value and remains explicitly unavailable;
capturing calendar returns confers no authority over that statistic or other uncaptured products.

## Pinned linked analysis v3

V3 uses the same package, registered API, literal writer, persistence and custody pipeline. Its
exclusive selector supplies `LINKED_MEMBER_CONTRIBUTION`, `CARINO:v1`, exact materialization UUIDs,
ordered contiguous windows, full nested method/authority pins, engine, calculation fingerprint and
canonical response digest. The optional request `restatement_sequence` is null-only; absent and
present-null requests retain their original identity. V1/v2 selectors and captured products cannot
be mixed into v3. Render checks every member, participating-period count and selected window,
including source values not selected for display. It never derives a Carino factor, contribution,
return, sum or reconciliation residual.

The complete table set is `Summary`, `LinkedContribution`, `LinkedPeriods`, `Methods`, `Lineage`,
`Disclosures`, `UncapturedProducts`. Exact ordered columns, rows and canonical pointers are
mandatory. Removing a row or column fails even when surviving cells are valid. `PinnedData` retains
the complete response, nested source authorities and raw decimal text, including scientific zeros
and negative values; `CellEvidence`, `ColumnPolicy` and `ArtifactIdentity` remain reconstructible.

| Source value | Canonical unit | Presentation |
|---|---|---|
| Return, weight | DECIMAL_RATIO | Percent, ratio converted once |
| Contribution | DECIMAL_RATIO | Percentage points, ratio converted once |
| Linking factor | DECIMAL_RATIO | Decimal factor, identity conversion |
| Beginning market value | CURRENCY_UNITS | Supplied currency, identity conversion |
| Participating periods | PERIOD_COUNT | Integer count, identity conversion |

Finite decimal strings retain their spelling and use declared HALF_UP display precision. Every
financial value remains literal text; formulas and automatic hyperlinks are disabled. Uncaptured
products carry null value, `UNAVAILABLE` and `SOURCE_PRODUCT_NOT_CAPTURED`; null source calculation
IDs carry the distinct `SOURCE_IDENTITY_NOT_PROVIDED` reason. Neither becomes zero.

The v3 custody identity must match the raw dataset selector and its qualification. Archive tenant,
composite and horizon must match the selected request; the context and Archive revision and exact
snapshot/revision lineage must agree. Report owns revision digest derivation. Render validates and
preserves those digests without inventing an independent revision calculator.

The copied Report schema SHA256 is
`c81dce9accd3721931663f40d160b282eafcf039191d2d649be9698e7a9c4237`, from sealed candidate r4
manifest `036a775cdc0ac6dcc1533211fa80b6a9d6f2413f2397be2a931cbf9cb17a6c72`.
The named `composite_linked_xlsx_package` OpenAPI example and v3 golden preserve the exact registered
Report PostgreSQL original package; the corrected package comes from the same lifecycle. Their
controlled synthetic source, v3 capability and captured Render503 boundary are explicit in producer
proof. Registered Render API tests independently reconcile both workbooks and reproduce the retained
original byte-for-byte; this fixture evidence does not claim actual joined HTTP or institutional
qualification. Existing R5 evidence below remains the separate v1/v2 campaign.

## Controlled R6 linked-analysis qualification

Phase `composite-linked-http-20261009-r6` uses the registered Report PostgreSQL producer and actual
Render/Archive HTTP clients with the accepted frozen Performance original/corrected pair. Render
runtime main `535d0d5f87fd2f8bd701ba8707b343022060d030` passed all eight natural release jobs in
run `37921433994`. Its committed tree matches signed source `05d527f85a2385aab08484d26580b7a38eb5f467`;
normal protected rebase main remains unsigned. The exact runtime and receipt identities are in the
[qualification ledger](https://github.com/sgajbi/lotus-render/blob/main/docs/composite-review-qualification-ledger.md#controlled-r6-linked-analysis-qualification).

The 52-file producer collector and all three actual workbook/package pairs are sealed by raw hash.
Each original, financial-correction and retained-original workbook independently reconciles all
115 canonical cells, 115 display cells, 40 column policies, full pinned source and exact
job/snapshot/revision/lineage/disclosure/context identity. No formulas or hyperlinks occur. The
original and retained display 3.02%; the correction displays 4.04%. Retained-original facts and
revision remain equal to the original; its new technical render identity yields a distinct artifact
hash. These actual HTTP artifacts are separate from the earlier Render503 producer fixtures.

Root's independent raw OOXML checks and actual Archive metadata/download/foreign-tenant reads
accept the three artifacts and explicit original-to-technical-to-financial correction chain.
Authorized reads append access audit while retained financial and relationship rows stay fixed.
Native live acceptance is `4dd41e/0`, receipt SHA256
`fa1e344096e6fdc0aac094b0caa724bfac7a7e77323608016cfce8b32c322822`.
The [public producer evidence](https://github.com/sgajbi/lotus-report/issues/417#issuecomment-6080034790)
records the actual chain. Existing client/OpenAPI/golden examples keep their hash-bound fixture
provenance and bytes; this campaign does not relabel them as its actual HTTP inputs.

Render's consistent SQLite backup has integrity `ok`. A fresh process restores it into a separate
file and the registered app reads all three status/hash identities and artifact metadata, with three
foreign-tenant 404s and zero Archive connections. Every value in all 37 persisted columns and the
full schema match the backup after those reads. Primary database/WAL hashes and the live Render
process remain unchanged; no live Render restart or overwrite is claimed. The ledger records the
isolated restore, full-store comparison and network-guard premise receipts.
Root post-restore acceptance `f6f8eb/0`, receipt SHA256
`373a5aa3f8acc99ff5751a5b50fea7232dade84cfb63c18e53d0f16bab65dffc`, independently accepts the
isolated retained-store comparisons. Following its exact owned-process retirement release,
Render takes a final integrity-checked backup and stops only recorded PIDs `39788`, `122816`,
`126776`; all are absent and port `55888` has no listener. Native `24c730/0` retains the three
actual artifacts/packages, backup/restore copies, logs and failed diagnostics. No foreign or R5
resources change; full receipts and hashes are in the ledger.

Qualification remains calculated replay, `NOT_ATTESTED`, development template publication and
local trusted headers. The documentation successor is distinct from the tested runtime. No new
financial capture, source calculation, bank authority, enterprise authentication, RTO certification
or full Report #417 / Platform #923 closure is conferred. Existing R5 and v1/v2 evidence stays fixed.

## Admission and ownership

Submit the existing `POST /renders` envelope with `report_type=composite_review`,
`report_data_contract_version=composite_review.v1`, `template_id=composite-review`,
`template_version=v1`, `output_format=xlsx`, `locale=en-SG`, and `brand_variant=private_banking`.
The named OpenAPI example is available in `/docs`. Tenant admission must match the dataset tenant.
Unsupported formats, combinations, engine versions and template source drift fail closed.

Report owns report selection, semantic tables, availability and the immutable source snapshot.
Render validates and presents that supplied evidence; it performs no investment calculation and
fetches no source data. The copied consumer schema is
`contracts/report-data/composite_review.v1.schema.json`; its authoritative supplier is
`lotus-report/contracts/composite_review.v1.schema.json`. Changes require coordinated exact-version
contract review rather than an inferred fallback. The package includes the raw source response,
its SHA-256 digest, selection and ordered retained window pins, report facts and semantic tables.

Render verifies source digest, tenant, composite and calculation identity, engine and receipt
fingerprints, ordered materialization pins, member identity, dates, source readiness and currency.
Every canonical cell must resolve to the exact scalar at its RFC 6901 source pointer. Financial
columns require a supported financial source path and matching type, units and currency; relabeling
a financial source as text cannot bypass this validation. Duplicate rows/columns, malformed
pointers, nonfinite values, fabricated authority and unavailable values represented as zero refuse.

## Workbook dictionary

| Sheet | Meaning |
|---|---|
| `Summary` | supplied composite selection, calculated result and availability |
| `MonthlyReturns` or `PeriodReturns` | exactly one supplied period series; monthly naming is Report's decision |
| `Contribution` | supplied member result, weighting and contribution |
| `Methods`, `Lineage`, `Disclosures` | supplied method, retained provenance and qualification |
| `AnnualReturns` | v1 unavailable; v2 selected captured calendar returns or unchanged unavailable section |
| `TrailingReturns` | v2 selected captured trailing cumulative returns only |
| `Risk`, `Members`, `EligibilityReasons`, `MembershipHistory`, `Attribution`, `Restatement` | explicit unavailable sections for facts absent from this source contract |
| `CellEvidence` | every table/row/column identity, exact canonical JSON scalar, availability, reasons and source pointer |
| `ColumnPolicy` | type, canonical unit, display unit/conversion, decimal places, HALF_UP mode, currency, scale and literal storage |
| `ArtifactIdentity` | job/snapshot/template, source selection, lineage/disclosures and render context |
| `PinnedData` | ordered JSON chunks reconstructing the complete original dataset without truncation |

Sheet names have a deterministic `_1` suffix; tables exceeding 1,000 data rows partition into
`_2`, etc., with repeated headers. Canonical identity and order remain intact. Unavailable cells
display their availability and supplied reason codes; their canonical evidence is JSON `null`.
Null, unknown and zero remain distinct. Unsupported sections carry no invented calculations.

All cells are literal Excel text. This preserves long identifiers and financial decimal strings
outside Excel's numeric precision. Formulas, hyperlinks, external links and macros are never
created from supplied text. Canonical text is always retained separately from rounded display.
Users needing numeric analysis must import canonical values into a tool supporting decimal
precision and use the column dictionary; Excel arithmetic on the display strings is unsupported.

| Column policy | Display example |
|---|---|
| decimal ratio → percent, two places | canonical `0.010000` → `1.00%` |
| decimal ratio → percentage points, two places | canonical `-0.015` → `-1.50 pp` |
| money, currency USD, two places | canonical `100.00` → `100.00 USD` |
| count | exact integral text, with no ratio conversion |

Ratio conversion multiplies by 100 exactly once. Display quantization uses decimal `HALF_UP`
at the declared 0–12 places. No binary float, new return calculation, source rounding or
double conversion is introduced. `scale` is exactly `1`.

## Runtime and limits

The registered execution path selects XlsxWriter **3.2.9** after registry admission, within the
existing bounded execution limiter and durable render-job lifecycle. PDF remains the default;
`SUPPORTED_OUTPUT_FORMATS` defaults to `("pdf", "xlsx")`, requires PDF and permits only those
two implemented formats. An operator may disable XLSX with `("pdf",)`. Service readiness still
checks the required Typst runtime as well as the local store; XLSX execution itself uses Python.

| Bound | Limit |
|---|---:|
| data rows per sheet partition | 1,000 |
| aggregate data rows including evidence/dictionary | 30,000 |
| aggregate cells including headers | 210,000 |
| aggregate UTF-8 text including headers | 16 MiB |
| sheets / columns per sheet | 64 / 100 |
| literal cell size | 32,767 UTF-16 units |
| final XLSX bytes | 16 MiB |

The default HTTP envelope limit is 8 MiB and applies to all submitted render packages. PDF remains
the required default with its existing template, execution and output controls. These workbook
budgets admit the controlled 72-month, 28-member source package, including its 24,604 semantic cells
and every evidence, policy, identity and pinned-data row. The expanded fixture has 27,939 data rows,
201,586 cells including headers and 43 sheets. Workbook budgets remain independent: fitting the
HTTP envelope alone does not establish that a package fits the writer.

### Large identity JSON

Layout policy `identity_storage=ordered_json_text_v1` preserves the two-column `ArtifactIdentity`
schema. Ordinary values remain a field name and exact ASCII-escaped, sorted-key JSON value. When
that canonical JSON exceeds 32,767 characters, the base field row is replaced by a descriptor row
`<field>__chunks`, immediately followed by `<field>__chunk_000000` through the last zero-based chunk.
Each chunk cell contains a JSON **string**, whose decoded value is at most 16,000 ASCII characters
of the original canonical JSON. This bounds even maximally escaped physical cells below Excel's
32,767 UTF-16-unit limit. Only identity metadata uses this encoding; financial cells are never split.
Caller keys inside `render_context` remain intact; top-level identity field names belong to Render
and reserve the `__chunks` and `__chunk_` suffix namespaces.

The descriptor has exactly four members: `encoding` (`ordered_json_text_v1`), `count` (positive
integer), `utf8_bytes` (original canonical JSON byte length), and `sha256` (lowercase unprefixed
SHA-256 of those exact bytes). A consumer must validate the exact schema and version before decoding.
Reject Boolean/noninteger counts or lengths, unknown members, and lengths above the 16 MiB text
budget. Require `count=ceil(utf8_bytes/16000)`, at most 1,049 chunks and no more than the remaining
worksheet rows before allocating or consuming fragments. Preserve worksheet order; do not sort
chunks into an apparently valid sequence. Require consecutive exact names, unique fields, absence
of the logical base row, JSON-string values, ASCII fragment text, exactly 16,000 characters in every
nonfinal chunk and the declared remainder in the last chunk. Reject missing, duplicate, reordered,
noncontiguous, extra or orphan reserved rows and conflicting base/descriptor fields. Join the decoded
strings, check the exact byte length and SHA-256, then parse the reconstructed JSON as the logical
field value. Reject malformed descriptors and fragments; do not fall back to trusting marker-shaped
data. Small values need no reconstruction, while consumers of large contexts must implement this
additive storage policy to retain complete source identity.

Bounds apply to the expanded workbook, not just input tables. Refusal preserves truthful failed
job status without an artifact. The configured compile deadline is checked while writing and after
ZIP serialization; it is cooperative and cannot interrupt a running ZIP close. Bounds constrain
that finalization work. Writer workspace files are scoped to a context and removed on success or failure.
No claim is made that every input under the byte limit fits every deployment's deadline.

## Lifecycle and custody

The response retains the existing MIME/hash/runtime/attempt contract. XLSX MIME is
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`; SHA-256 covers the exact ZIP
bytes. `bounded_determinism_fingerprint` uses `composite-xlsx-members/v1`: a SHA-256 domain marker,
member count and sorted UTF-8 member names and exact payloads, each framed by an eight-byte big-endian
length. XML payloads are serialized consistently on Windows and Linux; no XML content is normalized
or omitted. ZIP container ordering, compression, permissions and host attributes are excluded from
this content fingerprint. Any member name, membership, value, formula, pin or XML byte change moves
it. Raw artifact checksums and sizes remain the actual ZIP bytes used for transport and custody;
they may differ across hosts. Same-runtime byte equality is tested separately. A duplicate terminal
submission returns existing evidence and no inline bytes. Render's
local SQLite persists lifecycle and custody evidence, not the workbook; Archive owns retrieval.

Report supplies `render_context.archive` with `portfolio_scope=composite`, null `portfolio_id`,
the real `composite_id`, and `composite_report_identity` containing the exact selection and
series/source-revision/factual-content digests. The existing handoff overlays Render's actual
job, snapshot, byte SHA, MIME, runtime and template provenance, then delivers those exact bytes to
Archive's single ingestion authority. Archive independently verifies checksum and exclusive scope.
`archive_pending`, `archive_failed`, `archived_verified` and template publication are distinct facts.
A prepared custody request proves no delivery or download.

## Controlled R5 custody qualification

Phase `composite-source-products-http-20261009-r5` completed actual registered HTTP custody for
original, financial correction and retained-original rerender artifacts on 2026-10-09. Source
and resource disposition are recorded in the
[qualification ledger](https://github.com/sgajbi/lotus-render/blob/main/docs/composite-review-qualification-ledger.md).
Runtime heads were Report `89b4fa0dfae10b26ae20f16727dccff36a069a49`, Render
`383126231bb7744d6b4f3f60436ded86da5f0085` and Archive
`280f6d8d8b0ea47be3e35cbcb25b4347280c5920`. Report used its normal PostgreSQL worker and the
unmodified Render/Archive HTTP clients. Performance inputs were frozen accepted `75f` genuine
captures replayed through the registered source boundary: controlled calculated replay,
**NOT_ATTESTED**, with no institutional or client-publication authority.

Root independently checked all 24,623 canonical/display semantic cells, 81 column policies,
complete raw source products/pins/context/identity and unavailable reasons in each downloaded
workbook. Each contains 44 sheets, 28,020 data rows and 202,071 physical cells under unchanged
limits. Retained-original rerender preserved the original dataset without a source refetch; its
new render identity contributes to its own artifact hash.

| Actual artifact | Bytes | SHA256 |
|---|---:|---|
| Original | 1,318,499 | `e6d552ff1c3c61a66db0058f2ec35d188be210dd13d4ba1bbdde1a5e5b9a6a7f` |
| Financial correction | 1,319,433 | `1efcaf0b5e1faf5b0d4dcce83d7df4bfc9b9407c924335e9e46092983cc2d686` |
| Retained original rerender | 1,318,533 | `33f88c9e229351594ff79ecb098813e519c65d3bd6c43c852baaf2241572936c` |

Ten independent reads before and after Archive's HTTP restart preserved full metadata and exact
download bytes, foreign-download refusal with 403 and the current financial-correction chain.
The same PostgreSQL container and object storage were reopened by a new HTTP process. Root's
pre-restart receipt SHA256 is
`61996f8de6788bedd058a862ba4dbfcee173f9416652ea2d6aa803e54e729797`;
post-restart receipt SHA256 is
`bb63dc7c82a4b6d3b4ac2cfc080ab392ada0badd2fc75ff812261c99eab1b515`.

After reader release, Render's SQLite backup API sealed all three terminal `rendered` /
`archived_verified` jobs into a 24,576-byte backup with integrity `ok`, SHA256
`288d17a58e27132c167fad8de9d5489b3e93dcd35c99c6022b1b359d0ee95692`.
All actual workbooks, row bindings, logs and acceptance receipts were retained before the exact
owned Render processes and listener were retired. Foreign resources and retired R4 evidence were
untouched. [The issue evidence](https://github.com/sgajbi/lotus-render/issues/344#issuecomment-6077310252)
records producing native commands and source/receipt bindings.

Root's final custody/retirement acceptance independently rehashed Archive and Report PostgreSQL
dumps, the Render SQLite backup and all retained object/workbook copies; the sealed 28-file
producer manifest remained unchanged. Both owned containers/volumes, all seven recorded HTTP/
wrapper/console processes and all four reserved ports were absent or closed. Final receipt SHA256:
`f1ac36ca73ed66a8d24062c0d8c79f6718353a9c9b20dfc9b3868b399c8b68d5`.
Dump contents were listed; no full restore rehearsal or enterprise certificate was claimed.

This closure documentation succeeds the tested Render runtime commit named above; subsequent
documentation-main checks do not constitute another live producer campaign. Runtime, template,
contract and finite-limit blobs retain that implementation. Calendar return remains distinct
from the refused annual member dispersion statistic. This evidence closes only the bounded Render
v2 seam after final issue reconciliation; Report #417, Platform #923, all twelve products and
enterprise qualification remain open.

## Reproducible verification

Run from the `lotus-render` repository root after `make install`. The commands work in PowerShell
and POSIX shells; use the respective interpreter path below:

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_literal_workbook.py tests/unit/test_composite_source_cells.py tests/unit/test_composite_products.py tests/unit/test_composite_capacity.py tests/e2e/test_composite_workbook_journey.py
.venv/Scripts/python.exe scripts/regenerate_golden_fixtures.py --format xlsx
```

```bash
.venv/bin/python -m pytest tests/unit/test_literal_workbook.py tests/unit/test_composite_source_cells.py tests/unit/test_composite_products.py tests/unit/test_composite_capacity.py tests/e2e/test_composite_workbook_journey.py
.venv/bin/python scripts/regenerate_golden_fixtures.py --format xlsx
```

The committed golden retains the exact registered Report PostgreSQL worker/composer package,
with its producing package hash and explicit controlled source/admission boundary in the fixture
registry. Its financial source and test-only candidate family admission are synthetic; the real
Report lifecycle/package production stops at a captured Render503. It proves no production family
admission or Archive custody. The agreed semantic example is retained separately as report-data.json.
End-to-end tests execute the registered API and actual writer, reconcile source/canonical
cells with an independent workbook reader, and test refusal, tenant isolation, restart and replay.
The separate deterministic-gzip six-year fixture retains the actual normal Report worker package
that Render initially refused with HTTP413 before job admission. `six-year-provenance.json` records
its exact hashes and controlled source boundary. `tests/unit/test_composite_capacity.py` exercises
the registered writer and independently recovers every evidence cell, full pinned data and large
context on each CI host. This fixture proves writer support, without claiming HTTP or Archive custody.
Producer/consumer acceptance additionally requires actual Report-produced packages and real Archive
ingestion/download evidence with exact SHA reconciliation; those lifecycle and source boundaries
must remain explicit in delivery evidence.

Separate v2 original/corrected deterministic-gzip fixtures retain full genuine 72-month primary
responses plus Root-accepted calendar-2020 and trailing-12 captures through the registered Report
worker. Their provenance names the exact shared manifest, raw package hashes and controlled
Render503 profile boundary. Each expands to 28,020 data rows, 202,071 physical cells and 44 sheets;
serialized request measurements are 7,565,462 / 7,566,158 bytes and UTF8 workbook text is below
11.41 MB. These measurements establish this selected cohort, not every eight-product combination.
Operators must measure the complete actual package against every current limit, including full raw
products and identity context. Refuse excess; never discard raw data or mandatory evidence to fit.
Writer profiles, snapshots and local registered tests do not substitute for actual HTTP custody,
current-main qualification or enterprise scale/SLO evidence.

See [Template Registry](Template-Registry), [API Surface](API-Surface),
[Configuration](Configuration) and [Operations](Operations) for the shared contracts.
