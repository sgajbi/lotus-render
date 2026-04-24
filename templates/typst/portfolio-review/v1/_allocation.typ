#import "_theme.typ": rule, section-subtitle, small-caps, soft-rule
#import "_components.typ": compact-allocation-row, key-stat, note-panel, page-header

#let allocation-page() = [
  #page-header("Asset allocation")
  #v(10pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 18pt,
    [
      #section-subtitle("By asset class")
      #v(8pt)
      #grid(
        columns: (1.15fr, 1.15fr, 0.55fr, 0.75fr),
        column-gutter: 8pt,
        [#small-caps("Category")],
        [#small-caps("Proportion")],
        [#align(right)[#small-caps("Weight")]],
        [#align(right)[#small-caps("Value")]],
      )
      #v(4pt)
      #soft-rule()
      #v(8pt)
      #block(inset: 10pt, fill: white, stroke: (paint: rule, thickness: 0.5pt), radius: 8pt)[
        ${ASSET_CLASS_ROWS}
      ]
    ],
    [
      #section-subtitle("${SUPPLEMENTAL_ALLOCATION_TITLE}")
      #v(8pt)
      #grid(
        columns: (1.15fr, 1.15fr, 0.55fr, 0.75fr),
        column-gutter: 8pt,
        [#small-caps("Group")],
        [#small-caps("Proportion")],
        [#align(right)[#small-caps("Weight")]],
        [#align(right)[#small-caps("Value")]],
      )
      #v(4pt)
      #soft-rule()
      #v(8pt)
      #block(inset: 10pt, fill: white, stroke: (paint: rule, thickness: 0.5pt), radius: 8pt)[
        ${SUPPLEMENTAL_ALLOCATION_ROWS}
      ]
    ],
  )

  #v(14pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 18pt,
    [
      #section-subtitle("Portfolio summary")
      #v(8pt)
      #block(
        inset: 12pt,
        fill: rgb("#f4f9fd"),
        stroke: (paint: rgb("#dbe6ef"), thickness: 0.5pt),
        radius: 8pt,
      )[
        #grid(
          columns: (1fr, 1fr),
          row-gutter: 10pt,
          column-gutter: 12pt,
          [#key-stat("Largest asset class", "${ALLOCATION_LARGEST_NAME}")],
          [#key-stat("Position count", "${ALLOCATION_POSITION_COUNT}")],
          [#key-stat("Largest weight", "${ALLOCATION_LARGEST_WEIGHT}")],
          [#key-stat("Largest value", "${CURRENCY} ${ALLOCATION_LARGEST_VALUE}")],
          [#key-stat("Invested value", "${CURRENCY} ${INVESTED_VALUE}")],
          [#key-stat("Cash balance", "${CURRENCY} ${CASH_BALANCE}")],
        )
      ]
    ],
    [
      #section-subtitle("Risk profile")
      #v(8pt)
      #grid(
        columns: (1fr, 1fr),
        row-gutter: 10pt,
        column-gutter: 12pt,
        [#note-panel("Volatility", "${RISK_VOLATILITY}")],
        [#note-panel("Beta", "${RISK_BETA}")],
        [#note-panel("Tracking error", "${RISK_TRACKING_ERROR}")],
        [#note-panel("Information ratio", "${RISK_INFORMATION_RATIO}")],
        [#note-panel("Value at risk", "${RISK_VAR}")],
        [#note-panel("Review period", "${REVIEW_PERIOD_LABEL}")],
      )
    ],
  )
]
