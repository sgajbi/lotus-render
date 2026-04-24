#import "_theme.typ": accent, accent-soft, body-muted, body-strong, ink, metric-value, mist, page-kicker, rule, section-subtitle, section-title, slate, small-caps, soft-rule

#let page-header(title) = [
  #align(right)[
    #page-kicker("Reporting period 1 Jan 2026 - ${AS_OF_DATE}")
    #linebreak()
    #page-kicker("Reporting currency ${CURRENCY}")
  ]
  #v(10pt)
  #section-title(title)
  #v(6pt)
  #soft-rule()
]

#let metric-card(label, value, detail: none, tone: mist) = block(
  inset: 12pt,
  fill: tone,
  stroke: (paint: rule, thickness: 0.5pt),
  radius: 8pt,
)[
  #small-caps(label)
  #v(5pt)
  #metric-value(value)
  #if detail != none [
    #v(4pt)
    #body-muted(detail)
  ]
]

#let note-panel(title, body) = block(
  inset: 12pt,
  fill: white,
  stroke: (paint: rule, thickness: 0.5pt),
  radius: 8pt,
)[
  #small-caps(title)
  #v(5pt)
  #text(size: 9pt, fill: ink)[#body]
]

#let spotlight-panel(title, body) = block(
  inset: 14pt,
  fill: rgb("#f4f9fd"),
  stroke: (paint: accent-soft, thickness: 0.7pt),
  radius: 10pt,
)[
  #small-caps(title)
  #v(5pt)
  #text(size: 9.8pt, fill: ink)[#body]
]

#let content-item(index, title, detail) = [
  #grid(
    columns: (22pt, 1fr),
    column-gutter: 10pt,
    [#text(size: 22pt, weight: 300, fill: accent)[#index]],
    [
      #text(size: 11pt, weight: 500, fill: ink)[#title]
      #v(2pt)
      #body-muted(detail)
    ],
  )
]

#let key-stat(label, value) = [
  #small-caps(label)
  #v(3pt)
  #body-strong(value)
]

#let review-note(body) = block(
  inset: 12pt,
  fill: white,
  stroke: (paint: rule, thickness: 0.5pt),
  radius: 8pt,
)[
  #grid(
    columns: (10pt, 1fr),
    column-gutter: 8pt,
    [#rect(width: 6pt, height: 6pt, radius: 2pt, fill: accent)],
    [#text(size: 9pt, fill: ink)[#body]],
  )
]

#let period-row(period, net, benchmark, relative) = [
  #grid(
    columns: (0.9fr, 1fr, 1fr, 1fr),
    column-gutter: 12pt,
    [#text(size: 9pt, fill: ink)[#period]],
    [#align(right)[#text(size: 9pt, fill: ink)[#net]]],
    [#align(right)[#text(size: 9pt, fill: slate)[#benchmark]]],
    [#align(right)[#text(size: 9pt, weight: 500, fill: accent)[#relative]]],
  )
  #v(6pt)
  #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
]

#let performance-bar-row(period, value, width) = [
  #grid(
    columns: (34pt, 1fr, 44pt),
    column-gutter: 10pt,
    [#body-muted(period)],
    [
      #block(
        width: 100%,
        inset: (y: 4pt),
        fill: mist,
        radius: 99pt,
      )[
        #rect(width: width, height: 8pt, radius: 99pt, fill: accent)
      ]
    ],
    [#align(right)[#text(size: 8.8pt, weight: 500, fill: ink)[#value]]],
  )
]

#let performance-summary-cell(label, value, annualized) = block(
  inset: 8pt,
  fill: white,
  stroke: (paint: rule, thickness: 0.35pt),
  radius: 4pt,
)[
  #text(size: 7.3pt, fill: slate)[#label]
  #linebreak()
  #text(size: 10pt, weight: 600, fill: ink)[#value]
  #linebreak()
  #text(size: 6.8pt, fill: slate)[Ann. #annualized]
]

#let performance-chart-row(period, value, cumulative, width) = [
  #grid(
    columns: (34pt, 1fr, 42pt, 42pt),
    column-gutter: 7pt,
    [#text(size: 6.2pt, fill: slate)[#period]],
    [
      #block(width: 100%, inset: (y: 2pt), fill: mist, radius: 99pt)[
        #rect(width: width, height: 4.5pt, radius: 99pt, fill: accent)
      ]
    ],
    [#align(right)[#text(size: 6.2pt, weight: 500, fill: ink)[#value]]],
    [#align(right)[#text(size: 6.2pt, fill: slate)[#cumulative]]],
  )
]

#let performance-detail-row(period, final_value, inflows, outflows, value, twr, cumulative_value, cumulative_twr) = [
  #grid(
    columns: (0.72fr, 1fr, 1fr, 1fr, 1fr, 0.7fr, 1fr, 0.7fr),
    column-gutter: 6pt,
    [#text(size: 6.1pt, fill: ink)[#period]],
    [#align(right)[#text(size: 6.1pt, fill: slate)[#final_value]]],
    [#align(right)[#text(size: 6.1pt, fill: slate)[#inflows]]],
    [#align(right)[#text(size: 6.1pt, fill: slate)[#outflows]]],
    [#align(right)[#text(size: 6.1pt, fill: ink)[#value]]],
    [#align(right)[#text(size: 6.1pt, weight: 500, fill: accent)[#twr]]],
    [#align(right)[#text(size: 6.1pt, fill: ink)[#cumulative_value]]],
    [#align(right)[#text(size: 6.1pt, weight: 500, fill: accent)[#cumulative_twr]]],
  )
  #v(1.6pt)
  #line(length: 100%, stroke: (paint: rule, thickness: 0.22pt))
]

#let allocation-row(name, weight, value, width) = [
  #grid(
    columns: (1.25fr, 1.4fr, 0.6fr, 0.75fr),
    column-gutter: 10pt,
    [#text(size: 8.7pt, fill: ink)[#name]],
    [
      #block(
        width: 100%,
        inset: (y: 4pt),
        fill: mist,
        radius: 99pt,
      )[
        #rect(width: width, height: 8pt, radius: 99pt, fill: accent-soft)
      ]
    ],
    [#align(right)[#text(size: 8.6pt, fill: ink)[#weight]]],
    [#align(right)[#text(size: 8.6pt, fill: slate)[#value]]],
  )
]

#let compact-allocation-row(name, weight, value, width) = [
  #grid(
    columns: (1.15fr, 1.15fr, 0.55fr, 0.75fr),
    column-gutter: 8pt,
    [#text(size: 8pt, fill: ink)[#name]],
    [
      #block(
        width: 100%,
        inset: (y: 3pt),
        fill: mist,
        radius: 99pt,
      )[
        #rect(width: width, height: 6pt, radius: 99pt, fill: accent-soft)
      ]
    ],
    [#align(right)[#text(size: 7.75pt, fill: ink)[#weight]]],
    [#align(right)[#text(size: 7.75pt, fill: slate)[#value]]],
  )
  #v(4pt)
  #line(length: 100%, stroke: (paint: rule, thickness: 0.25pt))
]

#let holding-row(name, asset_class, weight, value, pnl, contribution) = [
  #grid(
    columns: (2.1fr, 1.1fr, 0.8fr, 1fr, 1fr, 0.9fr),
    column-gutter: 10pt,
    [#text(size: 8.8pt, fill: ink)[#name]],
    [#text(size: 8.8pt, fill: slate)[#asset_class]],
    [#align(right)[#text(size: 8.8pt, fill: ink)[#weight]]],
    [#align(right)[#text(size: 8.8pt, fill: slate)[#value]]],
    [#align(right)[#text(size: 8.8pt, fill: slate)[#pnl]]],
    [#align(right)[#text(size: 8.8pt, weight: 500, fill: accent)[#contribution]]],
  )
  #v(6pt)
  #line(length: 100%, stroke: (paint: rule, thickness: 0.3pt))
]

#let dense-position-row(category, number_amount, description, classification, cost_basis, market_value, gain_loss, performance, weight) = [
  #grid(
    columns: (0.85fr, 1.9fr, 1.1fr, 1.05fr, 1.05fr, 1.05fr, 0.95fr, 0.52fr),
    column-gutter: 7pt,
    [
      #text(size: 7.5pt, fill: slate)[#category]
      #linebreak()
      #text(size: 7.15pt, fill: ink)[#number_amount]
    ],
    [
      #text(size: 8.1pt, fill: ink)[#description]
      #linebreak()
      #text(size: 7pt, fill: slate)[Sustainability / instrument details]
    ],
    [#align(right)[#text(size: 7.35pt, fill: slate)[#classification]]],
    [#align(right)[#text(size: 7.35pt, fill: ink)[#cost_basis]]],
    [#align(right)[#text(size: 7.35pt, fill: ink)[#market_value]]],
    [#align(right)[#text(size: 7.35pt, fill: slate)[#gain_loss]]],
    [#align(right)[#text(size: 7.35pt, weight: 500, fill: accent)[#performance]]],
    [#align(right)[#text(size: 7.35pt, fill: ink)[#weight]]],
  )
  #v(4.5pt)
  #line(length: 100%, stroke: (paint: rule, thickness: 0.25pt))
]

#let dense-transaction-row(trade_date, booking_text, amount, description, detail_primary, detail_secondary, price, gain, value) = [
  #grid(
    columns: (0.85fr, 0.95fr, 0.9fr, 2.2fr, 0.95fr, 0.9fr, 0.95fr),
    column-gutter: 8pt,
    [
      #text(size: 7.55pt, fill: ink)[#trade_date]
      #linebreak()
      #text(size: 7pt, fill: slate)[Value date]
    ],
    [
      #text(size: 7.55pt, fill: ink)[#booking_text]
      #linebreak()
      #text(size: 7pt, fill: slate)[Booking]
    ],
    [#align(right)[#text(size: 7.55pt, fill: ink)[#amount]]],
    [
      #text(size: 8pt, fill: ink)[#description]
      #linebreak()
      #text(size: 7.15pt, fill: slate)[#detail_primary]
      #linebreak()
      #text(size: 6.95pt, fill: slate)[#detail_secondary]
    ],
    [#align(right)[#text(size: 7.55pt, fill: ink)[#price]]],
    [#align(right)[#text(size: 7.55pt, fill: slate)[#gain]]],
    [#align(right)[#text(size: 7.55pt, weight: 500, fill: accent)[#value]]],
  )
  #v(4.5pt)
  #line(length: 100%, stroke: (paint: rule, thickness: 0.25pt))
]

#let appendix-term(title, body) = [
  #text(size: 8.1pt, weight: 500, fill: ink)[#title]
  #text(size: 7.9pt, fill: ink)[[: #body]]
]

#let appendix-section(title, left, middle, right) = [
  #text(size: 8.8pt, weight: 500, fill: ink)[#title]
  #v(4pt)
  #soft-rule()
  #v(8pt)
  #grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 16pt,
    [
      #set par(justify: true, leading: 0.9em)
      #left
    ],
    [
      #set par(justify: true, leading: 0.9em)
      #middle
    ],
    [
      #set par(justify: true, leading: 0.9em)
      #right
    ],
  )
]
