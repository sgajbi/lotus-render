#import "_theme.typ": accent, small-caps, soft-rule
#import "_components.typ": dense-transaction-row, page-header

#let transactions-page() = [
  #page-header("Transaction list")
  #v(4pt)
  #text(size: 9pt, fill: accent)[${TRANSACTION_PERIOD_LABEL}]
  #v(10pt)
  #align(right)[#text(size: 8.5pt, fill: rgb("#66798d"))[Valued in ${CURRENCY}]]
  #v(6pt)
  #grid(
    columns: (0.85fr, 0.95fr, 0.9fr, 2.2fr, 0.95fr, 0.9fr, 0.95fr),
    column-gutter: 8pt,
    [#small-caps("Trade date")],
    [#small-caps("Booking text")],
    [#align(right)[#small-caps("Number/Amount")]],
    [#small-caps("Description")],
    [#align(right)[#small-caps("Price")]],
    [#align(right)[#small-caps("Gain/Loss")]],
    [#align(right)[#small-caps("Transaction value")]],
  )
  #v(3pt)
  #soft-rule()
  #v(6pt)
  ${DENSE_TRANSACTION_ROWS}
]
