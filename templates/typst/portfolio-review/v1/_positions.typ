#import "_theme.typ": section-subtitle, soft-rule
#import "_components.typ": dense-position-row, page-header, report-panel, stacked-table-label, table-label

#let observations-page() = [
  #page-header("Detailed positions")
  #v(12pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 16pt,
    [#section-subtitle("By investment category")],
    [#align(right)[#section-subtitle("Net performance valued in ${CURRENCY}")]],
  )
  #v(8pt)
  #report-panel([
    #grid(
      columns: (0.85fr, 1.9fr, 1.05fr, 1.02fr, 1.02fr, 1.02fr, 0.95fr, 0.52fr),
      column-gutter: 7pt,
      [#stacked-table-label(("Number/Amount", ""))],
      [#stacked-table-label(("Description", "Sustainability"))],
      [#stacked-table-label(("Rating", "Sector", "Duration", "Yield"), placement: right)],
      [#stacked-table-label(("Cost price", "Exchange rate", "Cost value", "Last purchase"), placement: right)],
      [#stacked-table-label(("Market price", "Exchange rate", "Market price date", "YTD performance"), placement: right)],
      [#stacked-table-label(("Market gain", "Exchange gain", "Unrealized P/L"), placement: right)],
      [#stacked-table-label(("Market value", "Accrued interest"), placement: right)],
      [#table-label("%", placement: right)],
    )
    #v(3pt)
    #soft-rule()
    #v(6pt)
    ${DENSE_POSITION_ROWS}
  ])
]
