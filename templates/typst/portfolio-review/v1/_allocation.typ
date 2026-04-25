#import "_theme.typ": mist, rule, section-subtitle, soft-rule
#import "_components.typ": chart-card, chart-placeholder, compact-allocation-row, key-stat, note-panel, page-header, report-panel, table-label

#let allocation-page() = [
  #page-header("Asset allocation")
  #v(10pt)
  #grid(
    columns: (1.45fr, 1fr),
    column-gutter: 18pt,
    [
      ${ALLOCATION_DONUT_CHART_SECTION}
    ],
    [
      #section-subtitle("Portfolio summary")
      #v(8pt)
      #report-panel([
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
      ], fill: mist)
    ],
  )

  #v(14pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 18pt,
    [
      #section-subtitle("By asset class")
      #v(8pt)
      #grid(
        columns: (1.15fr, 1.15fr, 0.55fr, 0.75fr),
        column-gutter: 8pt,
        [#table-label("Category")],
        [#table-label("Proportion")],
        [#table-label("Weight", placement: right)],
        [#table-label("Value", placement: right)],
      )
      #v(4pt)
      #soft-rule()
      #v(8pt)
      #report-panel([
        ${ASSET_CLASS_ROWS}
      ])
    ],
    [
      #section-subtitle("${SUPPLEMENTAL_ALLOCATION_TITLE}")
      #v(8pt)
      #grid(
        columns: (1.15fr, 1.15fr, 0.55fr, 0.75fr),
        column-gutter: 8pt,
        [#table-label("Group")],
        [#table-label("Proportion")],
        [#table-label("Weight", placement: right)],
        [#table-label("Value", placement: right)],
      )
      #v(4pt)
      #soft-rule()
      #v(8pt)
      #report-panel([
        ${SUPPLEMENTAL_ALLOCATION_ROWS}
      ])
    ],
  )
  #pagebreak()
  #page-header("Asset allocation")
  #v(10pt)
  #section-subtitle("Risk profile")
  #v(8pt)
  #grid(
    columns: (1fr, 1fr, 1fr),
    row-gutter: 10pt,
    column-gutter: 12pt,
    [#note-panel("Volatility", "${RISK_VOLATILITY}")],
    [#note-panel("Beta", "${RISK_BETA}")],
    [#note-panel("Tracking error", "${RISK_TRACKING_ERROR}")],
    [#note-panel("Information ratio", "${RISK_INFORMATION_RATIO}")],
    [#note-panel("Value at risk", "${RISK_VAR}")],
    [#note-panel("Review period", "${REVIEW_PERIOD_LABEL}")],
  )
]
