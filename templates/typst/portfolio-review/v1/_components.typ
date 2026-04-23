#import "_theme.typ": accent, accent-soft, body-muted, body-strong, metric-value, mist, rule, section-title, page-kicker, small-caps, soft-rule

#let page-header(title) = [
  #grid(
    columns: (1fr, 1fr),
    align(left)[#section-title(title)],
    align(right)[
      #page-kicker("Reporting period 1 Jan 2026 - ${AS_OF_DATE}")
      #linebreak()
      #page-kicker("Reporting currency ${CURRENCY}")
    ],
  )
  #v(8pt)
  #soft-rule()
  #v(10pt)
]

#let key-stat(label, value) = [
  #small-caps(label)
  #v(3pt)
  #metric-value(value)
]

#let note-panel(title, body) = block(
  inset: 12pt,
  fill: mist,
  radius: 6pt,
  stroke: (paint: rule, thickness: 0.5pt),
)[
  #body-strong(title)
  #v(5pt)
  #body-muted(body)
]

#let review-note(value) = block(
  inset: 10pt,
  fill: white,
  stroke: (paint: rule, thickness: 0.5pt),
  radius: 5pt,
)[
  #grid(
    columns: (10pt, 1fr),
    fill: (x, y) => none,
    [#text(fill: accent)[•]],
    [#body-muted(value)],
  )
]

#let period-row(period, net, benchmark, relative) = [
  #grid(
    columns: (0.9fr, 1fr, 1fr, 1fr),
    column-gutter: 12pt,
    [#body-strong(period)],
    [#align(right)[#body-muted(net)]],
    [#align(right)[#body-muted(benchmark)]],
    [#align(right)[#body-muted(relative)]],
  )
  #v(4pt)
  #soft-rule()
]

#let performance-bar-row(period, value, width) = [
  #grid(
    columns: (0.8fr, 2.1fr, 0.7fr),
    column-gutter: 12pt,
    [#body-muted(period)],
    [
      #rect(width: 100%, height: 7pt, fill: rgb("#edf3f7"), radius: 3pt)
      #move(dy: -7pt)[#rect(width: width, height: 7pt, fill: accent, radius: 3pt)]
    ],
    [#align(right)[#body-muted(value)]],
  )
]

#let holding-row(name, asset, weight, value, pnl, contribution) = [
  #grid(
    columns: (2.1fr, 1.1fr, 0.8fr, 1fr, 1fr, 0.9fr),
    column-gutter: 10pt,
    [#body-strong(name)],
    [#body-muted(asset)],
    [#align(right)[#body-muted(weight)]],
    [#align(right)[#body-muted(value)]],
    [#align(right)[#body-muted(pnl)]],
    [#align(right)[#body-muted(contribution)]],
  )
  #v(4pt)
  #soft-rule()
]

#let allocation-row(name, weight, value, width) = [
  #grid(
    columns: (1.3fr, 2fr, 0.7fr, 0.8fr),
    column-gutter: 10pt,
    [#body-muted(name)],
    [
      #rect(width: 100%, height: 8pt, fill: rgb("#edf3f7"), radius: 3pt)
      #move(dy: -8pt)[#rect(width: width, height: 8pt, fill: accent-soft, radius: 3pt)]
    ],
    [#align(right)[#body-muted(weight)]],
    [#align(right)[#body-muted(value)]],
  )
]
