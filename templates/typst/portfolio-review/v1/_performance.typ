#import "_charts.typ": line-chart
#import "_theme.typ": empty-state, rule, section-subtitle
#import "_components.typ": chart-card, chart-placeholder, chart-scale-note, contribution-reconciliation, contribution-row, labelled-table, performance-chart-row, performance-detail-row, performance-summary-cell, period-return-row, period-row, section-marker, table-label

#let performance-page() = [
  // The marker names what the page holds, so it stops promising a comparison the
  // package cannot make.
  #section-marker("Performance", if "${HAS_BENCHMARK}" == "yes" {
    "Period returns, benchmark comparison, and return history"
  } else {
    "Period returns and return history"
  })
  #v(8pt)
  #section-subtitle("Performance summary (TWR)")
  #v(7pt)
  ${PERFORMANCE_SUMMARY_TABLE}

  // The render package carried benchmark and relative return per period all along and
  // nothing drew them. Now they are drawn -- but only where they exist. Four columns
  // for a package with no benchmark meant two of them reading "Not available" on every
  // line, under a heading promising a comparison; the appendix, which asked the
  // stricter question, withheld the definitions for the same document.
  #if "${HAS_PERFORMANCE_PERIODS}" == "yes" [
    #v(15pt)
    #if "${HAS_BENCHMARK}" == "yes" [
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
    ] else [
      #labelled-table(
        "Period returns (TWR)",
        grid(columns: (0.9fr, 1fr), column-gutter: 12pt,
          [#table-label("Period")],
          [#table-label("Portfolio", placement: right)],
        ),
        [${PERFORMANCE_PERIOD_ROWS}],
      )
    ]
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

  // The ranking answers "which holdings made that line", so it sits under the line rather
  // than claiming a page. Drawn only when the package carries contribution.
  #if "${HAS_CONTRIBUTION_RANKING}" == "yes" [
    #v(14pt)
    #labelled-table(
      "Contribution to return",
      grid(columns: (1.5fr, 1.6fr, 0.62fr, 0.62fr, 0.62fr), column-gutter: 7pt,
        [#table-label("Holding")],
        [#table-label("Effect")],
        [#table-label("Contribution", placement: right)],
        [#table-label("Avg weight", placement: right)],
        [#table-label("Return", placement: right)],
      ),
      [${CONTRIBUTION_RANKING_ROWS}],
    )
  ]
]
