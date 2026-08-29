#import "_theme.typ": rule, section-subtitle, soft-rule
#import "_components.typ": dense-position-row, page-header, report-panel, section-marker, stacked-table-label, table-label

#let observations-page() = [
  #section-marker("Detailed positions", "Statement-style holdings detail and position-level performance")
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
    // A real table so the header repeats on every page the positions span, and the row
    // separator is the row's own stroke rather than a sibling that can drift away from
    // it (issue #138). A 500-row statement used to paginate into pages of eight
    // unlabelled numeric columns.
    #table(
      columns: (0.85fr, 1.9fr, 1.05fr, 1.02fr, 1.02fr, 1.02fr, 0.95fr, 0.52fr),
      column-gutter: 7pt,
      inset: (x: 0pt, y: 4.5pt),
      stroke: (x, y) => (bottom: (paint: rule, thickness: 0.25pt)),
      table.header(
        repeat: true,
        [#stacked-table-label(("Number/Amount", ""))],
        [#stacked-table-label(("Description", "Sustainability"))],
        [#stacked-table-label(("Rating", "Sector", "Duration", "Yield"), placement: right)],
        [#stacked-table-label(("Cost price", "Exchange rate", "Cost value", "Last purchase"), placement: right)],
        [#stacked-table-label(("Market price", "Exchange rate", "Market price date", "YTD performance"), placement: right)],
        [#stacked-table-label(("Market gain", "Exchange gain", "Unrealized P/L"), placement: right)],
        [#stacked-table-label(("Market value", "Accrued interest"), placement: right)],
        [#table-label("%", placement: right)],
      ),
      ..(
        ${DENSE_POSITION_ROWS}
      ).flatten(),
    )
  ])
]
