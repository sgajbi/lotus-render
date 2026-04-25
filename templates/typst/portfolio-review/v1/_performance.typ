#import "_theme.typ": rule, section-subtitle, section-title, soft-rule
#import "_components.typ": chart-card, chart-placeholder, page-header, performance-chart-row, performance-detail-row, performance-summary-cell, report-panel, table-label

#let performance-page() = [
  #page-header("Performance")
  #v(8pt)
  #section-subtitle("Performance summary (TWR)")
  #v(7pt)
  ${PERFORMANCE_SUMMARY_TABLE}

  #v(15pt)
  ${PERFORMANCE_12M_CHART_SECTION}

  #pagebreak()
  #section-title("Performance")
  #v(8pt)
  #soft-rule()
  #v(10pt)
  #section-subtitle("Annual net performance (TWR)")
  #v(7pt)
  #report-panel([
    #grid(columns: (34pt, 1fr, 42pt, 42pt), column-gutter: 7pt,
      [#table-label("Year")],
      [#table-label("Performance")],
      [#table-label("TWR", placement: right)],
      [#table-label("Cum.", placement: right)],
    )
    #v(5pt)
    #soft-rule()
    #v(6pt)
    ${PERFORMANCE_ANNUAL_CHART_ROWS}
  ])

  #pagebreak()
  #section-title("Performance")
  #v(8pt)
  #soft-rule()
  #v(10pt)
  #section-subtitle("${AS_OF_DATE}: Monthly net performance valued in ${CURRENCY}")
  #v(7pt)
  #grid(
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
  )
  #v(5pt)
  #soft-rule()
  #v(6pt)
  #report-panel([
    ${PERFORMANCE_MONTHLY_TABLE_ROWS}
  ])

]
