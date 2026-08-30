#import "_theme.typ": empty-state, rule, section-subtitle
#import "_components.typ": report-panel, section-marker, stacked-table-label, statement-cell

#let observations-page() = [
  #section-marker("Detailed positions", "Statement-style holdings detail and position-level performance")
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
      columns: ${POSITION_TABLE_WIDTHS},
      column-gutter: 7pt,
      inset: (x: 0pt, y: 4.5pt),
      stroke: (x, y) => (bottom: (paint: rule, thickness: 0.25pt)),
      table.header(
        repeat: true,
        ${POSITION_TABLE_HEADER}
      ),
      ..(
        ${DENSE_POSITION_ROWS}
      ).flatten(),
    )
  ])
]
