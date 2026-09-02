#import "_charts.typ": donut-chart
#import "_theme.typ": empty-state, mist, rule, section-subtitle
#import "_components.typ": allocation-dimension-block, allocation-dimension-note, chart-card, chart-placeholder, compact-allocation-row, key-stat, note-panel, panel-note, report-panel, section-marker

#let allocation-page() = [
  #section-marker("Asset allocation", "Asset mix, exposure detail, and risk profile")
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
  ${ALLOCATION_DIMENSION_BLOCKS}

  // #138 guarded this against an absent risk summary; the break that remained gave six
  // values a full landscape page, 68% of it blank, under a third consecutive "Asset
  // allocation" header. It flows into the section it belongs to now (#184).
  #if "${HAS_RISK_PROFILE}" == "yes" [
    #v(16pt)
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
    // Why a measure is missing, in Report's words. "Not available" alone stood for five
    // different facts, two of which point a reader in opposite directions (#227).
    ${RISK_SUPPORTABILITY_NOTES}
  ]
]
