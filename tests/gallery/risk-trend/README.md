# Gallery entry: risk-trend dot strip

The first entry of the primitive gallery (#219), and the shape later primitives
reuse: **one JSON input per interesting shape, faithful to the real
producer/source contract; semantic assertions that fail on a wrong result rather
than a changed one; and this statement of intended and prohibited usage.** The
whole-document goldens stay the banked integration evidence; this entry answers
the question they cannot: is the primitive *correct* at its edges?

Each `*.json` here is a canonical `report_data.risk_trend` block as lotus-report
emits it. Values are source-shaped: rolling volatility and tracking error arrive
as annualized **decimal ratios** (`0.1374` means 13.74%) with
`unit: "decimal_ratio"`; beta is `unit: "unitless"`. The assertions live in
`tests/unit/test_risk_trend_gallery.py`; real-engine tests compile cases through
the actual v2 template page.

## Intended usage

- "Is this portfolio's risk changing?" — a compact per-metric trend beside the
  point-in-time risk summary, from **source-owned series only**.
- The strip is the **ordered observation sequence**: dots are placed by
  observation index, and nothing connects them. Calendar distance is not
  data-quality evidence — a Friday-to-Monday interval is market cadence, not a
  gap — so it does not shape the strip.
- Coverage is stated as facts: each drawn strip prints its observation count and
  observed first/last dates beside the window caption, so warm-up or partial
  coverage is explicit without spatial guessing.
- Endpoints are formatted from the source's stated unit — an exact decimal
  shift for `decimal_ratio` (never a float, never rounding), verbatim for
  `unitless` — so `0.1374 → 0.141` reaches the reader as `13.74% → 14.1%`. The
  raw source strings stay untouched for lineage and geometry.
- Each strip is independently scaled to its own observed range, and the band
  **says so** where any strip is drawn: endpoint figures show the actual level.
- Posture is stated per metric in the source's words (`unavailable` prints the
  source's note in the #241 voice; `empty` prints why the source excluded it).

## Prohibited or misleading usage

- **Never connect the dots, smooth the strip, or invent missing dates.**
  Interpolation is derivation.
- **Never infer missingness from calendar time.** If genuine gap evidence
  matters, the source states it (notes, quality flags, or explicit gap facts) —
  weekends and warm-up are not evidence of absence.
- **Never print a financial number without its unit semantics.** A ready series
  arriving without `unit` is stated as unstatable, not printed bare — `0.1374`
  where the reader means 13.74% is confidently wrong.
- **Never print a min/max, delta, or trend verdict.** Verdicts are source-owned
  (`trend_statement`, which no source states today) or absent.
- **Never draw a benchmark-relative series whose posture is not `ready`**, and
  never draw a `ready` series that cannot be honestly placed (fewer than two
  points, unparseable or non-finite values, dates out of order). Both are
  *stated*, not approximated.
- **Never let strips imply cross-metric comparability of magnitude.** The scale
  convention statement is mandatory wherever a strip is drawn; Render owns no
  thresholds and no reference levels.
- **Never rely on colour**: monochrome ink on a neutral band; the numbers carry
  the meaning in print and in the tag tree (the strip is a PDF artifact per the
  #246 discipline).
- **Not a chart for dense analysis.** Axis ticks, gridlines, and per-point
  labels belong to a full chart primitive; adding them here would misstate the
  strip's precision.
