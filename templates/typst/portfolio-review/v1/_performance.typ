#import "_theme.typ": accent, section-subtitle, section-title, small-caps, soft-rule
#import "_components.typ": page-header, performance-chart-row, performance-detail-row, performance-summary-cell

#let performance-page() = [
  #page-header("Performance")
  #v(8pt)
  #section-subtitle("Performance summary (TWR)")
  #v(7pt)
  ${PERFORMANCE_SUMMARY_TABLE}

  #v(15pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 16pt,
    [
      #section-subtitle("Monthly net performance (TWR)")
      #v(7pt)
      #block(
        inset: 10pt,
        fill: white,
        stroke: (paint: rgb("#dbe6ef"), thickness: 0.45pt),
        radius: 6pt,
      )[
        #grid(columns: (34pt, 1fr, 42pt, 42pt), column-gutter: 7pt,
          [#small-caps("Month")],
          [#small-caps("Performance")],
          [#align(right)[#small-caps("TWR")]],
          [#align(right)[#small-caps("Cum.")]],
        )
        #v(5pt)
        #soft-rule()
        #v(6pt)
        ${PERFORMANCE_MONTHLY_CHART_ROWS}
      ]
    ],
    [
      #section-subtitle("Annual net performance (TWR)")
      #v(7pt)
      #block(
        inset: 10pt,
        fill: white,
        stroke: (paint: rgb("#dbe6ef"), thickness: 0.45pt),
        radius: 6pt,
      )[
        #grid(columns: (34pt, 1fr, 42pt, 42pt), column-gutter: 7pt,
          [#small-caps("Year")],
          [#small-caps("Performance")],
          [#align(right)[#small-caps("TWR")]],
          [#align(right)[#small-caps("Cum.")]],
        )
        #v(5pt)
        #soft-rule()
        #v(6pt)
        ${PERFORMANCE_ANNUAL_CHART_ROWS}
      ]
    ],
  )

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
    [#small-caps("Period")],
    [#align(right)[#small-caps("Final value")]],
    [#align(right)[#small-caps("Inflows")]],
    [#align(right)[#small-caps("Outflows")]],
    [#align(right)[#small-caps("Value")]],
    [#align(right)[#small-caps("TWR")]],
    [#align(right)[#small-caps("Cumulative")]],
    [#align(right)[#small-caps("TWR")]],
  )
  #v(5pt)
  #soft-rule()
  #v(6pt)
  ${PERFORMANCE_MONTHLY_TABLE_ROWS}

]
