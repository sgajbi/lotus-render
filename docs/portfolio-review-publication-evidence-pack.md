# Portfolio-review v3/v4 publication evidence pack

## Status and decision boundary

This is a **review probe**, not a publication request or production acceptance.
`portfolio-review/v1` and `v2` remain published and immutable. `v3` and `v4` remain
development versions. No manifest publication field, template source, consumer default, or
deployment changes in this pack.

The owner decides whether either candidate is published only after reviewing this pack and the
separate empirical-content gates: Report #254 and Risk #291. A successful render proves the
governed Typst container can set the supplied package; it does not make a document client-ready.

## What is executable

`tests/unit/test_v4_adversarial_matrix.py` renders real PDFs through the governed runtime.
The matrix checks every applicable v4 page independently for brand, client/report identity,
as-of statement, reporting currency, classified footer, and its own pagination. It includes a
negative control that removes a later-page footer and proves the frame checker fails.

The pack adds these review cases to the existing advisory, degraded, benchmarked, and refusal
cases:

| Case | Evidence | Truth it protects |
| --- | --- | --- |
| long reader-facing identities | client, portfolio, currency, period, mandate objective and benchmark code all survive extraction and the page-frame check | a wrapped identity cannot silently disappear from a later page |
| withheld allocation, benchmark, risk, holdings, contribution and earnings | each posture is made unavailable while ordinary source-shaped rows stay present | presentation remains Report's explicit authority; Render never derives it from row shape |
| v3/v4 candidate parity | each package's identifying business facts is extracted from both candidate PDFs | v4's page architecture does not alter v3 content facts |
| v2 compatibility | v2 facts are rendered from the same package through v2 and v3 | v3 is additive; v2 bytes are not altered |

Run the matrix from the `lotus-render` repository root:

```powershell
$env:LOTUS_RENDER_DIAGNOSTIC_OUTPUT = 'output/diagnostic-portfolio-review-c6'
.\.venv\Scripts\python.exe -m pytest tests\unit\test_v4_adversarial_matrix.py -q
Remove-Item Env:LOTUS_RENDER_DIAGNOSTIC_OUTPUT
```

The opt-in capture path writes `diagnostic-*.pdf` and matching text-layer files only. They are
diagnostic review material, not golden samples or demo captures. Render the PDF pages to images
and inspect every page frame and every long/wide table page before a decision; text extraction is
an additional clipping signal, not a substitute for that inspection.

## In-flight render and Report activation/reversal

`tests/integration/test_render_api.py::test_accepted_render_keeps_its_template_across_report_activation_and_replay`
is a real route and SQLite-store proof. It submits v2 against a v2-only registry fixture, restarts
against a registry fixture that also exposes v4, replays the exact v2 package, and submits a new
v4 package. The replay remains v2 in the persisted status and retains the identical immutable
artifact metadata; the new job is v4 and has a different template digest.

The only coordinated consumer action is Report configuration after an owner publication decision:

1. Render owner records the candidate's publication decision. Both frozen versions stay registered.
2. Report changes the template version it places on **new** packages.
3. Accepted jobs and exact replays retain the template/version they submitted; no Render deploy or
   data migration is part of activation.
4. Rollback is the inverse Report configuration change for new packages. It does not rewrite prior
   jobs or their artifacts.

Report #375's receiver acceptance is complete: its production `RenderClient` exercised two
tenants against Render `849eeeaa62a0cd4b46e1624319e71cd28504f687` in an isolated Docker image,
and proved own reads, foreign/absent equivalence, cross-tenant key conflict, and invalid authority
handling. This is registered-route Render SQLite evidence, not a deployed-production claim.

## Capacity and identity limits

Run the final-tree governed-runtime measurement from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\capacity_probe.py --verify-model
```

The rows at `CEILING_POSITIONS` / `CEILING_TRANSACTIONS` must render and a one-row-over package
must fail at admission with `resource_limit_exceeded`; it must not take a render slot or rely on a
runtime kill. Record the final command's page-time and artifact-size output with the reviewing PR.

### 2026-09-13 v4 governed-runtime measurement

The final-tree command was run in Docker Desktop's `desktop-linux` context through the pinned
`ghcr.io/typst/typst:0.14.2` container, with no host ports. Its diagnostic-only stdout capture is
`output/diagnostic-portfolio-review-c6/capacity-v4-final.txt` (stderr was empty).

| Shape | Largest rendered | First observed failure | Rendered time / PDF size |
| --- | ---: | ---: | --- |
| positions | 2,750 | 2,875 | 41.0 s / 10,677 KB |
| transactions | 4,500 | 4,625 | 35.1 s / 9,240 KB |
| both | 1,750 | 1,875 | 28.9 s / 10,380 KB |

The historical raw `3125/4875` reciprocal model did **not** hold for v4: `500/4000` and
`2800/300` were predicted to render at raw costs 0.98 and 0.96 but were killed. The production
admission threshold is 0.85, so it already rejects both shapes before a render slot is acquired;
this probe does not identify a live admission escape. It does identify a publication blocker:
v4 cannot inherit the historical raw capacity evidence. The owner must choose either a new
candidate-specific, remeasured and re-banked envelope with compatibility review, or a v4 design
change followed by a clean remeasurement. Until then, v4 stays development and must not become
Report's selected version.

There is one explicit blocker to a truthful **maximum-length identity** verdict. Render's package
contract has a generic `MAX_PAYLOAD_STRING_LENGTH = 100000`, but the Report-owned report-data
contract declares no separate maximum for client, portfolio, mandate, benchmark, currency, or
period labels. A generic payload safety ceiling is not an approved reader-facing identity limit.
The matrix therefore proves long observed reader-facing values without falsely calling them a
contract maximum. Owner: `lotus-report`; required prerequisite: versioned field limits plus
admission behavior for the reader-facing identity fields. Recheck trigger: a Report contract PR
that supplies those limits. Until then #270 cannot claim a complete maximum-length visual verdict.
