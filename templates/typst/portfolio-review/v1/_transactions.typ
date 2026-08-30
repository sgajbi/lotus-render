#import "_theme.typ": accent, empty-state, rule, slate
#import "_components.typ": dense-transaction-row, report-panel, section-marker, stacked-table-label

#let transactions-page() = [
  #section-marker("Transactions", "Transaction activity across the review period", header: "Transaction list")
  #v(4pt)
  #text(size: 8.8pt, fill: accent)[#"${TRANSACTION_PERIOD_LABEL}"]
  #v(10pt)
  #align(right)[#text(size: 8.8pt, fill: slate)[Valued in #"${CURRENCY}"]]
  #v(6pt)
  #report-panel([
    // A real table so the header repeats on every page the transactions span, and the
    // separator is the row's own stroke rather than a sibling that can drift away from
    // it (issue #138).
    #table(
      columns: (0.78fr, 0.82fr, 0.88fr, 2.3fr, 0.95fr, 0.9fr, 0.95fr),
      column-gutter: 8pt,
      inset: (x: 0pt, y: 4.5pt),
      stroke: (x, y) => (bottom: (paint: rule, thickness: 0.25pt)),
      table.header(
        repeat: true,
        [#stacked-table-label(("Trade date", "Value date"))],
        [#stacked-table-label(("Booking text", "Brokerage"))],
        [#stacked-table-label(("Number/Amount", "Tax", "Account"), placement: right)],
        [#stacked-table-label(("Description", "Custody account", "Account"))],
        [#stacked-table-label(("Purchase price", "Exchange rate", "Cost value", "Place of execution"), placement: right)],
        [#stacked-table-label(("Transaction price", "Exchange rate", "Realized P/L"), placement: right)],
        [#stacked-table-label(("Transaction value", "Accrued interest", "Settlement amount"), placement: right)],
      ),
      ..(
        ${DENSE_TRANSACTION_ROWS}
      ).flatten(),
    )
  ])
]
