# Portfolio Review Typst Design System

## Layout System

The portfolio review template is assembled from modular Typst pages under `templates/typst/portfolio-review/v1/`. The entry template owns page setup, typography defaults, footer furniture, and section assembly. The renderer injects `REPORT_SECTIONS`, so callers can render the full report or a selected subset through `render_context.sections` without changing page modules.

The report uses A4 landscape for statement-grade portfolio reporting. Section pages use a consistent rhythm: page title, reporting context, thin rule, section body, and a quiet footer with portfolio name and page numbering. Dense sections use aligned grid structures and reusable row components so positions, transactions, and performance tables keep the same measurement and hierarchy.

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

## Chart Pipeline

Charts are generated as deterministic SVG assets before Typst compilation. `portfolio_charts.py`
prepares the 12-month cumulative performance series and allocation breakdown from structured
report data, writes SVG assets under `assets/charts/` in the temporary Typst workspace, and the
Typst template includes those assets with `image(...)`.

Typst remains responsible for page composition and chart card layout. The chart generator owns
coordinate calculation, donut geometry, enterprise palette, line/marker treatment, sorting, and
small-slice grouping. If chart data is absent, the section renders a quiet placeholder instead of
failing or showing an empty frame.

## Configuration Model

The full report renders by default. `render_context.sections` accepts section keys such as `cover`, `contents`, `overview`, `performance`, `allocation`, `positions`, `transactions`, and `appendix`. Common aliases are normalized by the renderer. Unknown keys are ignored; if no valid section remains, the renderer falls back to the full report.

## Rendering

From `lotus-render`:

```powershell
$env:PYTHONPATH='src'
python -c "from pathlib import Path; from app.contracts.render_package import RenderPackage; from app.core.settings import Settings; from app.domain.templates.registry import TemplateRegistry; from app.services.render_intake import RenderIntakeService; from app.services.typst_rendering import TypstRenderService; root=Path('tests/golden/portfolio-review/v1'); pkg=RenderPackage.model_validate_json((root/'render-package.json').read_text(encoding='utf-8')); settings=Settings(); registry=TemplateRegistry.load_from_directory(Path(settings.template_registry_path)); service=TypstRenderService(settings, RenderIntakeService(registry)); result=service.render(pkg); (root/'expected.pdf').write_bytes(result.artifact_bytes); print(len(result.artifact_bytes))"
```

## Validation

Run the focused render proof:

```powershell
python -m pytest tests/unit/test_typst_rendering.py tests/integration/test_render_api.py -q
```

The test suite verifies deterministic PDF rendering, selected-section rendering, chart data
transformation, SVG asset generation, client-facing text hygiene, and template context generation.
