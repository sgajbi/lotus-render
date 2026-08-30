#import "_charts.typ": line-chart
#import "_theme.typ": empty-state, rule, section-subtitle, section-title, soft-rule
#import "_components.typ": chart-card, chart-placeholder, chart-scale-note, labelled-table, performance-chart-row, performance-detail-row, performance-summary-cell, period-row, report-panel, section-marker, table-label

#let performance-page() = [
  #section-marker("Performance", "Period returns, benchmark comparison, and return history")
  #v(8pt)
  #section-subtitle("Performance summary (TWR)")
  #v(7pt)
  ${PERFORMANCE_SUMMARY_TABLE}

  // The section marker above promises a benchmark comparison. The render package has
  // carried benchmark and relative return per period all along; nothing drew them.
  #if "${HAS_PERFORMANCE_PERIODS}" == "yes" [
    #v(15pt)
    #labelled-table(
      "Performance against benchmark (TWR)",
      grid(columns: (0.9fr, 1fr, 1fr, 1fr), column-gutter: 12pt,
        [#table-label("Period")],
        [#table-label("Portfolio", placement: right)],
        [#table-label("Benchmark", placement: right)],
        [#table-label("Relative", placement: right)],
      ),
      [${PERFORMANCE_PERIOD_ROWS}],
    )
  ]

  #v(15pt)
  ${PERFORMANCE_12M_CHART_SECTION}

  // Guarded so an all-empty report does not ship a near-blank page (issue #138).
  #if "${HAS_ANNUAL_PERFORMANCE}" == "yes" [
    #v(16pt)
    #labelled-table(
      "Annual net performance (TWR)",
      grid(columns: (34pt, 1fr, 42pt, 42pt), column-gutter: 7pt,
        [#table-label("Year")],
        [#table-label("Performance")],
        [#table-label("TWR", placement: right)],
        [#table-label("Cum.", placement: right)],
      ),
      [${PERFORMANCE_ANNUAL_CHART_ROWS}],
    )
  ]
  #if "${HAS_MONTHLY_PERFORMANCE}" == "yes" [
    #v(16pt)
    #labelled-table(
      "${AS_OF_DATE}: Monthly net performance valued in ${CURRENCY}",
      grid(
        columns: (0.72fr, 1fr, 1fr, 1fr, 1fr, 0.7fr, 1fr, 0.7fr),
        column-gutter: 6pt,
        [#table-label("Period")],
        [#table-label("Final value", placement: right)],
        [#table-label("Inflows", placement: right)],
        [#table-label("Outflows", placement: right)],
        [#table-label("Value", placement: right)],
        [#table-label("TWR", placement: right)],
        [#table-label("Cumulative", placement: right)],
        [#table-label("TWR", placement: right)],
      ),
      [${PERFORMANCE_MONTHLY_TABLE_ROWS}],
    )
  ]
]
