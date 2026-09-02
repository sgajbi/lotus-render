# Portfolio Review Typst Design System

## Layout System

The portfolio review template is assembled from modular Typst pages under `templates/typst/portfolio-review/v1/`. The entry template owns page setup, typography defaults, footer furniture, and section assembly. The renderer injects `REPORT_SECTIONS`, so callers can render the full report or a selected subset through `render_context.sections` without changing page modules.

The report uses A4 landscape for statement-grade portfolio reporting. Section pages use a consistent
rhythm: page title, reporting context, thin rule, section body, and a quiet footer with portfolio
name and page numbering. Dense sections use aligned grid structures and reusable row components so
positions, transactions, and performance tables keep the same measurement and hierarchy. Main-body
sections and appendix sections share the same page furniture, color tokens, panel rhythm, table
rules, and label treatment so the report reads as one coherent product rather than separate page
experiments.

## Typography System

The template uses the governed Typst runtime font fallback with restrained sizes for private-banking PDF density. Titles are light-weight and editorial; labels use a compact small-label style; values use medium weight only where scan priority is needed. The system avoids oversized hero treatment after the cover page so the report remains useful as a client review document.

## Component Model

Core reusable primitives live in `_theme.typ` and `_components.typ`:

- page furniture: `page-header`
- chart cards: `chart-card`, `chart-placeholder`
- headline metrics: `metric-card`, `key-stat`
- narrative blocks: `spotlight-panel`, `note-panel`, `review-note`
- table labels: `table-label`
- dense statement rows: `dense-position-row`, `dense-transaction-row`, `performance-detail-row`
- visual rows: `compact-allocation-row`, `performance-chart-row`
- appendix definitions: `appendix-term`, `appendix-section`

Page modules compose these primitives instead of hardcoding local styling. This keeps spacing, color, label treatment, and table rhythm consistent across sections.

## Section Families

The report is organized into section families that share the same foundation:

- front matter: cover and contents
- executive briefing: overview and mandate context
- analytics: performance, allocation, charts, and risk profile
- statement detail: detailed positions and transactions
- advisor-use narrative: reviewed advisory package content supplied by `lotus-report`
- appendix: definitions, methodology notes, abbreviations, and disclosures

Each family may tune density and emphasis, but it must use the shared tokens and component grammar.
New sections should start from the closest family pattern instead of defining local page furniture.

## Source-Backed Attribute Model

The template renders only attributes provided by the governed render package. Business data
ownership remains upstream in Lotus domain applications and render-package assembly remains owned by
`lotus-report`. The maintained inventory is
`docs/portfolio-review-attribute-inventory.md`; it records each client-facing attribute, business
meaning, source application, source object or endpoint where known, status, and required action.

When a desired report attribute is not source-backed, it must be recorded as a source gap instead of
being invented in the template. When an attribute exists but its client-facing placement is unclear,
it must be recorded as a placement or semantic decision before the report starts rendering it.

The reviewed advisory narrative section is optional and advisor-use scoped. It appears only when the
render package includes `report_data.reviewed_advisory_narrative.status == "included"`. The section
renders the package lineage, review state, source narrative hash, approved section text, and
advisor-use disclosure text supplied by `lotus-report`; it does not approve, rewrite, infer, or
source additional advisory facts.

The advisor proposal memo section is optional and advisor-use scoped. It appears only when the
render package includes `report_data.advisor_proposal_memo.status == "included"`. The section
renders memo lineage, approved advisor-use review posture, memo/source hashes, memo section
summaries, and disclosure text supplied by `lotus-report`; client-ready memo publication remains
blocked by upstream Advise policy.

## Chart Pipeline

Charts are drawn natively in Typst; no image assets are generated. Python owns the semantic
half and Typst owns the visual half:

- `portfolio_charts.py` reads a chart's inputs out of governed report data (series, slices,
  sorting, small-slice grouping) and chooses an axis whose ticks a reader can trust.
- `chart_geometry.py` turns those into positions: gridlines, points, labels, donut arc
  commands -- unit-tested geometry, computed in Python.
- `_charts.typ` and the family components draw the geometry with native `grid`/`rect`/`place`
  primitives, using the shared design tokens in `_shared/v1/_design.typ`. The six chart series
  are a luminance ladder (min pairwise gamma-space Rec.709 delta 0.088, guarded), so a
  greyscale print loses richness but never which slice is which.

Per-analytic emitters (contribution ranking, attribution bridge, earnings statement) follow the
same split: one Python module per analytic composes invoked Typst component calls; the
components own the visual treatment. If chart data is absent, the section renders a quiet
placeholder instead of failing or showing an empty frame.

## Configuration Model

The full report renders when `sections` is omitted. An explicit `render_context.sections` list is honoured exactly or refused at admission -- an explicit scope can narrow a document or fail; it never silently widens (`section_selection.py`). Section keys include `cover`, `contents`, `overview`, `performance`, `allocation`, `positions`, `transactions`, and `appendix`; common aliases are normalized, duplicates draw once at first position, and caller order is preserved. When an included reviewed advisory narrative package is present, the default composition inserts `advisory_narrative` before the appendix, and callers can request it directly with `reviewed-advisory-narrative`; likewise `advisor_memo` via `advisor-proposal-memo` and `advisor_commentary`. Unknown or unavailable requested sections refuse the whole selection with a typed validation problem naming the tokens; an explicit empty list is refused. The one documented narrowing: an explicitly requested appendix is dropped when the document uses no term it would explain.

## Rendering

From `lotus-render`:

```powershell
$env:PYTHONPATH='src'
@'
from pathlib import Path
from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import TypstRenderService

settings = Settings()
registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
service = TypstRenderService(settings, RenderIntakeService(registry))

for package_path in sorted(Path("tests/golden").glob("*/v1/**/render-package.json")):
    root = package_path.parent
    package = RenderPackage.model_validate_json(package_path.read_text(encoding="utf-8"))
    result = service.render(package)
    (root / "expected.pdf").write_bytes(result.artifact_bytes)
    print(package.template_id, len(result.artifact_bytes))
'@ | python -
```

## Validation

Run the focused render proof:

```powershell
python -m pytest tests/unit/test_typst_rendering.py tests/integration/test_render_api.py -q
```

The test suite verifies deterministic PDF rendering, selected-section rendering, chart data
transformation, chart geometry, client-facing text hygiene, and template context generation.
