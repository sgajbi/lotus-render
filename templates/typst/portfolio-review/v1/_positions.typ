#import "_theme.typ": section-subtitle, small-caps, soft-rule
#import "_components.typ": dense-position-row, page-header

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
  #grid(
    columns: (0.85fr, 1.9fr, 1.1fr, 1.05fr, 1.05fr, 1.05fr, 0.95fr, 0.52fr),
    column-gutter: 7pt,
    [#small-caps("Number / Amount")],
    [#small-caps("Description")],
    [#align(right)[#small-caps("Rating / sector")]],
    [#align(right)[#small-caps("Cost basis")]],
    [#align(right)[#small-caps("Market value")]],
    [#align(right)[#small-caps("Market gain")]],
    [#align(right)[#small-caps("Net performance")]],
    [#align(right)[#small-caps("%")]],
  )
  #v(3pt)
  #soft-rule()
  #v(6pt)
  ${DENSE_POSITION_ROWS}
]
