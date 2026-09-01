#import "_theme.typ": accent, empty-state, rule, slate, text-body
#import "_components.typ": report-panel, section-marker, stacked-table-label, statement-cell

#let transactions-page() = [
  #section-marker("Transactions", "Transaction activity across the review period", header: "Transaction list")
  #v(4pt)
  #text(size: text-body, fill: accent)[#"${TRANSACTION_PERIOD_LABEL}"]
  #v(10pt)
  #align(right)[#text(size: text-body, fill: slate)[Valued in #"${CURRENCY}"]]
  #v(6pt)
  #report-panel([
    // A real table so the header repeats on every page the transactions span, and the
    // separator is the row's own stroke rather than a sibling that can drift away from
    // it (issue #138).
    #table(
      columns: ${TRANSACTION_TABLE_WIDTHS},
      column-gutter: 8pt,
      inset: (x: 0pt, y: 4.5pt),
      stroke: (x, y) => (bottom: (paint: rule, thickness: 0.25pt)),
      table.header(
        repeat: true,
        ${TRANSACTION_TABLE_HEADER}
      ),
      ..(
        ${DENSE_TRANSACTION_ROWS}
      ).flatten(),
    )
  ])
]
