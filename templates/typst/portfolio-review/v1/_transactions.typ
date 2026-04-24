#import "_theme.typ": accent, soft-rule
#import "_components.typ": dense-transaction-row, page-header, stacked-table-label, table-label

#let transactions-page() = [
  #page-header("Transaction list")
  #v(4pt)
  #text(size: 9pt, fill: accent)[${TRANSACTION_PERIOD_LABEL}]
  #v(10pt)
  #align(right)[#text(size: 8.5pt, fill: rgb("#66798d"))[Valued in ${CURRENCY}]]
  #v(6pt)
  #grid(
    columns: (0.78fr, 0.82fr, 0.88fr, 2.3fr, 0.95fr, 0.9fr, 0.95fr),
    column-gutter: 8pt,
    [#stacked-table-label(("Trade date", "Value date"))],
    [#stacked-table-label(("Booking text", "Brokerage"))],
    [#stacked-table-label(("Number/Amount", "Tax", "Account"), placement: right)],
    [#stacked-table-label(("Description", "Custody account", "Account"))],
    [#stacked-table-label(("Purchase price", "Exchange rate", "Cost value", "Place of execution"), placement: right)],
    [#stacked-table-label(("Transaction price", "Exchange rate", "Realized P/L"), placement: right)],
    [#stacked-table-label(("Transaction value", "Accrued interest", "Settlement amount"), placement: right)],
  )
  #v(3pt)
  #soft-rule()
  #v(6pt)
  ${DENSE_TRANSACTION_ROWS}
]
