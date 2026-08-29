#import "_theme.typ": accent, accent-soft, body-muted, body-strong, empty-state, gain, grid-gap, hairline, ink, loss, mist, navy, page-kicker, panel-radius, rule, section-subtitle, section-title, slate, small-caps, soft-rule

#let page-header(title) = [
  #grid(
    columns: (1fr, auto),
    column-gutter: grid-gap,
    [#section-title(title)],
    [
      #align(right)[
        #set par(leading: 0.86em)
        #page-kicker("Reporting period 1 Jan 2026 - ${AS_OF_DATE}")
        #linebreak()
        #page-kicker("Reporting currency ${CURRENCY}")
      ]
    ],
  )
  #v(7pt)
  #soft-rule()
]

#let page-meta() = [
  #set par(leading: 0.86em)
  #page-kicker("Statement of assets as of ${AS_OF_DATE}")
  #linebreak()
  #page-kicker("Produced for portfolio review")
]

#let report-panel(body, fill: white, inset: 11pt) = block(
  inset: inset,
  fill: fill,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
)[#body]

#let section-lead(title, body) = report-panel([
  #section-subtitle(title)
  #v(5pt)
  #text(size: 8.8pt, fill: ink)[#body]
], fill: mist)

#let metric-card(label, value, detail: none, tone: mist) = block(
  breakable: false,
  inset: 10pt,
  fill: tone,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
)[
  #small-caps(label)
  #v(4pt)
  #text(size: 11pt, weight: 650, fill: ink)[#value]
  #if detail != none [
    #v(3pt)
    #body-muted(detail)
  ]
]

// Small bordered cards: a card split across a page break shows a stroke with no
// bottom, or a label with its value on the next page. Typst 0.14.2 has no widow or
// orphan control -- `#set par(widows:)` is rejected -- so `breakable: false` on the
// units that are always wrong to split is the mechanism the engine does offer
// (issue #138). It is applied only to short fixed-size blocks; the panels that wrap
// long tables stay breakable or they could not paginate at all.
#let note-panel(title, body) = block(
  breakable: false,
  inset: 10pt,
  fill: white,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
)[
  #small-caps(title)
  #v(4pt)
  #text(size: 8.1pt, fill: ink)[#body]
]

#let spotlight-panel(title, body) = block(
  inset: 12pt,
  fill: mist,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
)[
  #small-caps(title)
  #v(5pt)
  #text(size: 8.8pt, fill: ink)[#body]
]

#let content-item(index, title, detail) = [
  #grid(
    columns: (24pt, 1fr),
    column-gutter: 11pt,
    [#text(size: 19pt, weight: 300, fill: accent)[#index]],
    [
      #text(size: 9.5pt, weight: 600, fill: ink)[#title]
      #v(2pt)
      #body-muted(detail)
    ],
  )
]

// Planted at the top of each section page so the contents page can compute the page a
// section truly starts on. The references used to be string literals, and were already
// wrong in documents carrying an advisory section, which shifts everything after it.
#let section-marker(title, detail) = [
  #metadata((title: title, detail: detail)) <lotus-section>
]

#let content-row(index, title, detail, ref) = [
  #grid(
    columns: (28pt, 1fr, 28pt),
    column-gutter: 10pt,
    [#text(size: 13pt, weight: 300, fill: accent)[#index]],
    [
      #text(size: 9.5pt, weight: 600, fill: ink)[#title]
      #linebreak()
      #body-muted(detail)
    ],
    [#align(right)[#small-caps(ref)]],
  )
  #v(8pt)
  #soft-rule()
]

#let key-stat(label, value) = [
  #small-caps(label)
  #v(3pt)
  #body-strong(value)
]

// A chart and the words naming it are one unit. Left breakable, this card split at a
// page boundary and stranded "12-Month Cumulative Performance" at the foot of one page
// with an unlabelled plot at the top of the next -- a chart of nothing in particular.
#let chart-card(title, chart-path, subtitle: none, note: none) = block(
  inset: 12pt,
  fill: white,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
  breakable: false,
)[
  #text(size: 11pt, weight: 700, fill: navy)[#title]
  #if subtitle != none [
    #v(2pt)
    #text(size: 8.1pt, fill: slate)[#subtitle]
  ]
  #v(8pt)
  #image(chart-path, width: 100%)
  #if note != none [
    #v(6pt)
    #text(size: 7.4pt, fill: slate)[#note]
  ]
]

#let chart-placeholder(title, message) = block(
  inset: 12pt,
  fill: mist,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
  breakable: false,
)[
  #text(size: 11pt, weight: 700, fill: navy)[#title]
  #v(8pt)
  #text(size: 8.8pt, fill: slate)[#message]
]

#let table-label(value, placement: left) = align(placement)[#small-caps(value)]

#let stacked-table-label(values, placement: left) = align(placement)[
  #set par(leading: 0.82em)
  #for value in values [
    #small-caps(value)
    #linebreak()
  ]
]

#let stacked-cell(values, placement: right, size: 7.4pt, fill: slate, weight: 400) = align(placement)[
  #set par(leading: 0.86em)
  #for value in values.split(";") [
    #text(size: size, weight: weight, fill: fill)[#value]
    #linebreak()
  ]
]

#let review-note(body) = block(
  breakable: false,
  inset: 12pt,
  fill: white,
  stroke: (paint: rule, thickness: 0.5pt),
  radius: 8pt,
)[
  #grid(
    columns: (10pt, 1fr),
    column-gutter: 8pt,
    [#rect(width: 6pt, height: 6pt, radius: 2pt, fill: accent)],
    [#text(size: 8.8pt, fill: ink)[#body]],
  )
]

// Relative return is the answer to "did we beat the benchmark", so it is the one
// figure on the row that carries its sign in colour rather than only in a minus.
#let period-row(period, net, benchmark, relative, relative-negative) = [
  #grid(
    columns: (0.9fr, 1fr, 1fr, 1fr),
    column-gutter: 12pt,
    [#text(size: 8.8pt, fill: ink)[#period]],
    [#align(right)[#text(size: 8.8pt, fill: ink)[#net]]],
    [#align(right)[#text(size: 8.8pt, fill: slate)[#benchmark]]],
    [#align(right)[#text(
      size: 8.8pt,
      weight: 500,
      fill: if relative-negative { loss } else { gain },
    )[#relative]]],
  )
  #v(6pt)
  #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
]

#let performance-summary-cell(label, value, annualized) = block(
  inset: 9pt,
  fill: white,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
)[
  #text(size: 7.4pt, fill: slate)[#label]
  #linebreak()
  #text(size: 9.5pt, weight: 600, fill: ink)[#value]
  #linebreak()
  #text(size: 6.8pt, fill: slate)[Ann. #annualized]
]

// A return runs either side of zero, so the track it is drawn on has a middle.
// `magnitude` is the share of the half-track the bar fills; the caller scales it
// against the series, so bar length is comparable within one chart.
#let diverging-track(magnitude, negative, bar-height: 4.5pt) = block(
  width: 100%,
  inset: (y: 2pt),
  fill: mist,
  radius: 2pt,
)[
  #grid(
    // The middle column is the zero baseline. Without a drawn zero, a reader has to
    // guess where the bars start from, and a short loss looks like a short gain.
    columns: (1fr, 0.6pt, 1fr),
    [#align(right)[#if negative [
      #rect(width: magnitude, height: bar-height, radius: (left: 99pt), fill: loss)
    ] else [
      #box(height: bar-height)
    ]]],
    [#rect(width: 0.6pt, height: bar-height + 3pt, fill: slate)],
    [#align(left)[#if negative [
      #box(height: bar-height)
    ] else [
      #rect(width: magnitude, height: bar-height, radius: (right: 99pt), fill: gain)
    ]]],
  )
]

// An auto-scaled bar with an unstated domain is only half-honest: two charts in one
// document can share a visual language and not share a scale. Say what the track means.
#let chart-scale-note(domain) = text(size: 6.1pt, fill: slate)[
  Bars scaled to #sym.plus.minus#domain, the largest move in this series
]

#let performance-chart-row(period, value, cumulative, magnitude, negative) = [
  #grid(
    columns: (34pt, 1fr, 42pt, 42pt),
    column-gutter: 7pt,
    [#text(size: 6.1pt, fill: slate)[#period]],
    [#diverging-track(magnitude, negative)],
    [#align(right)[#text(size: 6.1pt, weight: 500, fill: if negative { loss } else { ink })[#value]]],
    [#align(right)[#text(size: 6.1pt, fill: slate)[#cumulative]]],
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
    [#text(size: 8.8pt, fill: ink)[#name]],
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
    [#align(right)[#text(size: 8.8pt, fill: ink)[#weight]]],
    [#align(right)[#text(size: 8.8pt, fill: slate)[#value]]],
  )
]

#let compact-allocation-row(name, weight, value, width) = [
  #grid(
    columns: (1.15fr, 1.15fr, 0.55fr, 0.75fr),
    column-gutter: 8pt,
    [#text(size: 8.1pt, fill: ink)[#name]],
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
    [#align(right)[#text(size: 7.4pt, fill: ink)[#weight]]],
    [#align(right)[#text(size: 7.4pt, fill: slate)[#value]]],
  )
  #v(3.5pt)
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

// Returns table cells rather than a self-contained grid, so the positions table can be a
// real #table with a repeating header and a stroke that belongs to the row (issue #138).
#let dense-position-row(category, number_amount, description, classification, cost_basis, market_value, gain_loss, performance, weight) = (
  [
    #text(size: 7.4pt, fill: slate)[#category]
    #linebreak()
    #stacked-cell(number_amount, placement: left, size: 7.4pt, fill: ink)
  ],
  [
    #text(size: 8.1pt, fill: ink)[#description]
    #linebreak()
    #text(size: 6.8pt, fill: slate)[Sustainability / instrument details]
  ],
  [#stacked-cell(classification)],
  [#stacked-cell(cost_basis, fill: ink)],
  [#stacked-cell(market_value, fill: ink)],
  [#stacked-cell(gain_loss)],
  [#stacked-cell(performance, fill: accent, weight: 500)],
  [#align(right)[#text(size: 7.4pt, fill: ink)[#weight]]],
)

// Table cells rather than a self-contained grid, so the transaction table can repeat its
// header and own its row separator (issue #138), matching the positions table.
#let dense-transaction-row(trade_date, booking_text, amount, description, detail_primary, detail_secondary, price, gain, value) = (
  [
    #stacked-cell(trade_date, placement: left, size: 7.4pt, fill: ink)
  ],
  [
    #stacked-cell(booking_text, placement: left, size: 7.4pt, fill: ink)
  ],
  [#stacked-cell(amount, fill: ink)],
  [
    #text(size: 8.1pt, fill: ink)[#description]
    #linebreak()
    #stacked-cell(detail_primary, placement: left, size: 6.8pt, fill: slate)
    #linebreak()
    #stacked-cell(detail_secondary, placement: left, size: 6.8pt, fill: slate)
  ],
  [#stacked-cell(price, fill: ink)],
  [#stacked-cell(gain)],
  [#stacked-cell(value, fill: accent, weight: 500)],
)

#let appendix-term(title, body) = [
  #text(size: 8.1pt, weight: 500, fill: ink)[#title]
  #text(size: 8.1pt, fill: ink)[[: #body]]
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
