# Composite review workbook

Current scope: `composite-review v1` renders the first RPT01 XLSX supplier slice from Report-owned
`composite_review.v1`. The package qualification must be `EXPLICIT_RETAINED_CALCULATED_REPLAY`
and publication state `NOT_ATTESTED`. The manifest is `development`: a successful render or
verified Archive record does not confer official, attested or client publication authority.
This slice does not implement the remaining report families or complete the enterprise programme.

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
| `AnnualReturns`, `Risk`, `Members`, `EligibilityReasons`, `MembershipHistory`, `Attribution`, `Restatement` | explicit unavailable sections for facts absent from this source contract |
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
| aggregate data rows including evidence/dictionary | 20,000 |
| aggregate cells including headers | 200,000 |
| aggregate UTF-8 text including headers | 16 MiB |
| sheets / columns per sheet | 64 / 100 |
| literal cell size | 32,767 UTF-16 units |
| final XLSX bytes | 16 MiB |

Bounds apply to the expanded workbook, not just input tables. Refusal preserves truthful failed
job status without an artifact. The configured compile deadline is checked while writing and after
ZIP serialization; it is cooperative and cannot interrupt a running ZIP close. Bounds constrain
that finalization work. Writer workspace files are scoped to a context and removed on success or failure.
No claim is made that every input under the byte limit fits every deployment's deadline.

## Lifecycle and custody

The response retains the existing MIME/hash/runtime/attempt contract. XLSX MIME is
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`; SHA-256 covers the exact ZIP
bytes. Fixed workbook creation metadata supports byte equality within the pinned engine/source
envelope. A duplicate terminal submission returns existing evidence and no inline bytes. Render's
local SQLite persists lifecycle and custody evidence, not the workbook; Archive owns retrieval.

Report supplies `render_context.archive` with `portfolio_scope=composite`, null `portfolio_id`,
the real `composite_id`, and `composite_report_identity` containing the exact selection and
series/source-revision/factual-content digests. The existing handoff overlays Render's actual
job, snapshot, byte SHA, MIME, runtime and template provenance, then delivers those exact bytes to
Archive's single ingestion authority. Archive independently verifies checksum and exclusive scope.
`archive_pending`, `archive_failed`, `archived_verified` and template publication are distinct facts.
A prepared custody request proves no delivery or download.

## Reproducible verification

Run from the `lotus-render` repository root after `make install`. The commands work in PowerShell
and POSIX shells; use the respective interpreter path below:

```powershell
.venv/Scripts/python.exe -m pytest tests/unit/test_literal_workbook.py tests/unit/test_composite_source_cells.py tests/e2e/test_composite_workbook_journey.py
.venv/Scripts/python.exe scripts/regenerate_golden_fixtures.py --format xlsx
```

```bash
.venv/bin/python -m pytest tests/unit/test_literal_workbook.py tests/unit/test_composite_source_cells.py tests/e2e/test_composite_workbook_journey.py
.venv/bin/python scripts/regenerate_golden_fixtures.py --format xlsx
```

The committed golden retains the exact registered Report PostgreSQL worker/composer package,
with its producing package hash and explicit controlled source/admission boundary in the fixture
registry. Its financial source and test-only candidate family admission are synthetic; the real
Report lifecycle/package production stops at a captured Render503. It proves no production family
admission or Archive custody. The agreed semantic example is retained separately as report-data.json.
End-to-end tests execute the registered API and actual writer, reconcile source/canonical
cells with an independent workbook reader, and test refusal, tenant isolation, restart and replay.
Producer/consumer acceptance additionally requires actual Report-produced packages and real Archive
ingestion/download evidence with exact SHA reconciliation; those lifecycle and source boundaries
must remain explicit in delivery evidence.

See [Template Registry](Template-Registry), [API Surface](API-Surface),
[Configuration](Configuration) and [Operations](Operations) for the shared contracts.
