# Gallery entry: risk-trend dot strip

The first entry of the primitive gallery (#219), and the shape later primitives
reuse: **one JSON input per interesting shape, semantic assertions that fail on a
wrong result rather than a changed one, and this statement of intended and
prohibited usage.** The whole-document goldens stay load-bearing for determinism;
this entry answers the question they cannot: is the primitive *correct* at its
edges?

Each `*.json` here is a canonical `report_data.risk_trend` block exactly as
lotus-report emits it (report#255's shipped contract). The assertions live in
`tests/unit/test_risk_trend_gallery.py`; one test also compiles the primitive
through the real engine inside the v2 template, so the evidence covers both the
emitted markup and a really-rendered page.

## Intended usage

- "Is this portfolio's risk changing?" — a compact per-metric trend beside the
  point-in-time risk summary, from **source-owned series only**.
- Every dot is a source point placed by its own date and value; the printed
  first → last values are the quotable facts and are verbatim source strings.
- Gaps in the source series appear as horizontal empty space, in proportion to
  their duration (date-proportional x axis). Nothing connects the dots.
- Posture is stated per metric in the source's words: `unavailable` prints the
  source's note (the #241 voice for benchmark-relative series), `empty` prints
  why the source excluded the series.

## Prohibited or misleading usage

- **Never connect the dots or smooth the strip.** A line bridges holes the
  source stated; interpolation is derivation.
- **Never print a min/max, delta, or trend verdict.** Verdicts are source-owned
  (`trend_statement`, which no source states today) or absent. The endpoints
  are selected points, not computed statistics.
- **Never draw a benchmark-relative series whose posture is not `ready`**, and
  never draw a `ready` series this module cannot honestly place — fewer than
  two points, a value that does not parse or is non-finite, dates out of order.
  Both are *stated*, not approximated.
- **Never rely on colour**: the strip is monochrome ink on a neutral band and
  the numbers carry the meaning in print and in the tag tree (the strip itself
  is a PDF artifact per the #246 discipline).
- **Not a chart for dense analysis.** Axis ticks, gridlines, and value labels
  per point belong to a full chart primitive; adding them here would misstate
  the strip's precision.
