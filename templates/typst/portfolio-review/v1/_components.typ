// Components of the portfolio review family. One family, one file: a component here
// has exactly one consumer, and it moves to `_shared/_design.typ` the moment a second
// family or file needs it -- never before (a shared module with one caller is
// speculative generality), and never by copying (the pre-#213 governance rows drifted
// as three copies of one implementation for months, found only by a shared defect).
// The copy path is guarded: `test_component_promotion_guard.py` fails when two
// template files declare near-identical implementations under different names.

#import "_theme.typ": accent, accent-soft, body-muted, body-strong, empty-state, gain, grid-gap, hairline, ink, loss, mist, navy, page-kicker, panel-radius, rule, section-subtitle, section-title, slate, small-caps, soft-rule, text-body, text-body-strong, text-caption, text-fine, text-head, text-lead, text-micro, text-small

// Laid out by `set page(header:)` in main.typ rather than emitted into the flow, so a
// section that spills onto another page is still headed there. While this was an
// in-flow element the only way to head a page was to force one, which is how a
// six-value section came to own a full landscape page (#184).
#let page-header(title) = [
  #grid(
    columns: (1fr, auto),
    column-gutter: grid-gap,
    [#section-title(title)],
    [
      #align(right)[
        #set par(leading: 0.86em)
        #page-kicker("${REPORTING_PERIOD_LABEL}")
        #linebreak()
        #page-kicker("Reporting currency ${CURRENCY}")
      ]
    ],
  )
  #v(7pt)
  #soft-rule()
]

// The header for whichever section the current page belongs to, or nothing on the
// pages before the first section. Read from the same `<lotus-section>` markers the
// contents page counts, so the two cannot disagree about where a section begins.
#let running-header() = context {
  let current = counter(page).get().first()
  let started = query(<lotus-section>).filter(marker => (
    counter(page).at(marker.location()).first() <= current
  ))
  if started.len() > 0 {
    page-header(started.last().value.header)
  }
}

#let report-panel(body, fill: white, inset: 11pt) = block(
  inset: inset,
  fill: fill,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
)[#body]

#let section-lead(title, body) = report-panel([
  #section-subtitle(title)
  #v(5pt)
  #text(size: text-body, fill: ink)[#body]
], fill: mist)

// Fills its container, for the reason note-panel does: without a width the block hugs
// its own text, and the four cards down the side of the cover rendered at four
// different widths (#150).
#let metric-card(label, value, detail: none, tone: mist) = block(
  breakable: false,
  width: 100%,
  inset: 10pt,
  fill: tone,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
)[
  #small-caps(label)
  #v(4pt)
  #text(size: text-lead, weight: 650, fill: ink)[#value]
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
// Fills its container. Without a width the block hugs its own text, which is invisible
// where the body is a sentence and stark where it is a short value: the six risk cards
// on the allocation page rendered as three narrow islands in a three-column grid, with
// the columns' width left as dead space between them (#184).
#let note-panel(title, body) = block(
  breakable: false,
  width: 100%,
  inset: 10pt,
  fill: white,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
)[
  #small-caps(title)
  #v(4pt)
  #text(size: text-small, fill: ink)[#body]
]

// Planted at the top of each section page so the contents page can compute the page a
// section truly starts on. The references used to be string literals, and were already
// wrong in documents carrying an advisory section, which shifts everything after it.
// `header` is the title the running header shows, which is not always the title the
// contents shows: the overview is listed as "Overview" and headed "Scope of analysis".
// A table and everything that names it, as one unit that cannot be split. Apart they
// produce both defects #138 named: a subtitle stranded at the foot of a page, and rows
// continuing under no column labels, because the row grids are not `table()` elements
// and a header does not repeat on a continuation page (#184).
#let labelled-table(subtitle, labels, rows) = [
  // Sticky rather than one unbreakable block around the whole table. Unbreakable kept
  // the subtitle with its rows and also made a table taller than a page undrawable:
  // Typst put what fitted on the page and dropped the rest without a word. Sixty
  // monthly rows drew thirty-one. The contract admits 10,000 and the fixture has 12.
  #block(sticky: true, breakable: false, width: 100%)[
    #section-subtitle(subtitle)
    #v(7pt)
  ]
  #report-panel([
    #block(sticky: true, breakable: false, width: 100%)[
      #labels
      #v(5pt)
      #soft-rule()
    ]
    #v(6pt)
    #rows
  ])
]

#let section-marker(title, detail, header: none) = [
  #metadata((
    title: title,
    detail: detail,
    header: if header == none { title } else { header },
  )) <lotus-section>
]

#let content-row(index, title, detail, ref) = [
  #grid(
    columns: (28pt, 1fr, 28pt),
    column-gutter: 10pt,
    [#text(size: text-head, weight: 300, fill: accent)[#index]],
    [
      #text(size: text-body-strong, weight: 600, fill: ink)[#title]
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
// Takes the chart as content rather than as an image path, so a chart drawn with the
// document's own primitives inherits its fonts, colours and type scale. An SVG carries
// private copies of all three, which is one of the ways the palette drifted.
#let chart-card(title, body, subtitle: none, note: none) = block(
  inset: 12pt,
  fill: white,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
  breakable: false,
)[
  #text(size: text-lead, weight: 700, fill: navy)[#title]
  #if subtitle != none [
    #v(2pt)
    #text(size: text-small, fill: slate)[#subtitle]
  ]
  #v(8pt)
  #body
  #if note != none [
    #v(6pt)
    #text(size: text-fine, fill: slate)[#note]
  ]
]

#let chart-placeholder(title, message) = block(
  inset: 12pt,
  fill: mist,
  stroke: (paint: rule, thickness: hairline),
  radius: panel-radius,
  breakable: false,
)[
  #text(size: text-lead, weight: 700, fill: navy)[#title]
  #v(8pt)
  #text(size: text-body, fill: slate)[#message]
]

#let table-label(value, placement: left) = align(placement)[#small-caps(value)]

#let stacked-table-label(values, placement: left) = align(placement)[
  #set par(leading: 0.82em)
  #for value in values [
    #small-caps(value)
    #linebreak()
  ]
]

// A statement cell, built from the fields the row actually supplies. Where
// `stacked-cell` took one size and colour for a whole stack and a semicolon-joined
// string that had to line up with a header written somewhere else, each line here
// carries its own style and the header is emitted from the same declaration.
#let _statement-tone = (slate: slate, ink: ink, accent: accent)

#let statement-cell(lines, placement: right) = align(placement)[
  #set par(leading: 0.86em)
  #for line in lines [
    #text(
      size: line.size,
      weight: line.weight,
      fill: _statement-tone.at(line.tone),
    )[#line.value]
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
    [#text(size: text-body, fill: ink)[#body]],
  )
]

// Relative return is the answer to "did we beat the benchmark", so it is the one
// figure on the row that carries its sign in colour rather than only in a minus.
#let period-row(period, net, benchmark, relative, relative-negative) = [
  #grid(
    columns: (0.9fr, 1fr, 1fr, 1fr),
    column-gutter: 12pt,
    [#text(size: text-body, fill: ink)[#period]],
    [#align(right)[#text(size: text-body, fill: ink)[#net]]],
    [#align(right)[#text(size: text-body, fill: slate)[#benchmark]]],
    [#align(right)[#text(
      size: text-body,
      weight: 500,
      fill: if relative-negative { loss } else { gain },
    )[#relative]]],
  )
  #v(6pt)
  #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
]

// The same row for a portfolio with no benchmark to compare against. Drawing the four
// columns anyway gave two of them "Not available" on every line, under a heading that
// promised a comparison the package could not make.
#let period-return-row(period, net) = [
  #grid(
    columns: (0.9fr, 1fr),
    column-gutter: 12pt,
    [#text(size: text-body, fill: ink)[#period]],
    [#align(right)[#text(size: text-body, fill: ink)[#net]]],
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
  #text(size: text-fine, fill: slate)[#label]
  #linebreak()
  #text(size: text-body-strong, weight: 600, fill: ink)[#value]
  #linebreak()
  #text(size: text-caption, fill: slate)[Ann. #annualized]
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
#let chart-scale-note(domain) = text(size: text-micro, fill: slate)[
  Bars scaled to #sym.plus.minus#domain, the largest move in this series
]

#let performance-chart-row(period, value, cumulative, magnitude, negative) = [
  #grid(
    columns: (34pt, 1fr, 42pt, 42pt),
    column-gutter: 7pt,
    [#text(size: text-micro, fill: slate)[#period]],
    [#diverging-track(magnitude, negative)],
    [#align(right)[#text(size: text-micro, weight: 500, fill: if negative { loss } else { ink })[#value]]],
    [#align(right)[#text(size: text-micro, fill: slate)[#cumulative]]],
  )
]

#let performance-detail-row(period, final_value, inflows, outflows, value, twr, cumulative_value, cumulative_twr) = [
  #grid(
    columns: (0.72fr, 1fr, 1fr, 1fr, 1fr, 0.7fr, 1fr, 0.7fr),
    column-gutter: 6pt,
    [#text(size: text-micro, fill: ink)[#period]],
    [#align(right)[#text(size: text-micro, fill: slate)[#final_value]]],
    [#align(right)[#text(size: text-micro, fill: slate)[#inflows]]],
    [#align(right)[#text(size: text-micro, fill: slate)[#outflows]]],
    [#align(right)[#text(size: text-micro, fill: ink)[#value]]],
    [#align(right)[#text(size: text-micro, weight: 500, fill: accent)[#twr]]],
    [#align(right)[#text(size: text-micro, fill: ink)[#cumulative_value]]],
    [#align(right)[#text(size: text-micro, weight: 500, fill: accent)[#cumulative_twr]]],
  )
  #v(1.6pt)
  #line(length: 100%, stroke: (paint: rule, thickness: 0.22pt))
]

#let allocation-row(name, weight, value, width) = [
  #grid(
    columns: (1.25fr, 1.4fr, 0.6fr, 0.75fr),
    column-gutter: 10pt,
    [#text(size: text-body, fill: ink)[#name]],
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
    [#align(right)[#text(size: text-body, fill: ink)[#weight]]],
    [#align(right)[#text(size: text-body, fill: slate)[#value]]],
  )
]

#let compact-allocation-row(name, weight, value, width) = [
  #grid(
    columns: (1.15fr, 1.15fr, 0.55fr, 0.75fr),
    column-gutter: 8pt,
    [#text(size: text-small, fill: ink)[#name]],
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
    [#align(right)[#text(size: text-fine, fill: ink)[#weight]]],
    [#align(right)[#text(size: text-fine, fill: slate)[#value]]],
  )
  #v(3.5pt)
  #line(length: 100%, stroke: (paint: rule, thickness: 0.25pt))
]

// One allocation dimension the package asked for. The column headings live with the rows
// they label, so a dimension that has no rows to show does not get a header over nothing
// -- that is `allocation-dimension-note` below, and the two look different on purpose.
// Unbreakable as a whole, which the row bound is what makes safe. `labelled-table` had to
// stay breakable because a table taller than a page is undrawable -- Typst puts what fits
// and drops the rest without a word, which is how sixty monthly rows drew thirty-one. A
// composition is capped at nine rows and cannot outgrow a page, so it moves whole instead
// of leaving its column headings on the previous one.
#let allocation-dimension-block(title, rows, note: none) = block(breakable: false, width: 100%)[
  #block(width: 100%)[
    #section-subtitle(title)
    #v(8pt)
    #grid(
      columns: (1.15fr, 1.15fr, 0.55fr, 0.75fr),
      column-gutter: 8pt,
      [#table-label("Group")],
      [#table-label("Proportion")],
      [#table-label("Weight", placement: right)],
      [#table-label("Value", placement: right)],
    )
    #v(4pt)
    #soft-rule()
  ]
  #v(8pt)
  #report-panel([#rows])
  // What this grouping does not say. A composition looks like a whole thing, so a table
  // covering 62% of the portfolio has to say so -- the donut beside it already does, and
  // one coverage statement on a page with two compositions reads as covering both.
  #if note != none [
    #v(4pt)
    #text(size: text-micro, fill: slate)[#note]
  ]
]

// A dimension the document presents and has nothing to draw for. The heading stays,
// because the reader asked for this grouping and is owed an answer about it; the table
// furniture does not, because there is no table.
#let allocation-dimension-note(title, message) = [
  #section-subtitle(title)
  #v(8pt)
  #report-panel([#empty-state(message)])
]


// One contributor, on the same signed track the annual return bars use: a shared domain
// and a drawn zero, because without a zero a short loss looks like a short gain. The name
// takes the place the period label takes there -- the primitive is the same one.
#let contribution-row(name, contribution, weight, return-pct, magnitude, negative) = [
  #grid(
    columns: (1.5fr, 1.6fr, 0.62fr, 0.62fr, 0.62fr),
    column-gutter: 7pt,
    [#text(size: text-micro, fill: ink)[#name]],
    [#diverging-track(magnitude, negative)],
    [#align(right)[#text(size: text-micro, weight: 500, fill: if negative { loss } else { gain })[#contribution]]],
    [#align(right)[#text(size: text-micro, fill: slate)[#weight]]],
    [#align(right)[#text(size: text-micro, fill: slate)[#return-pct]]],
  )
]

// What the ranking does not say. Both lines are required output: the reconciliation
// because a top-N presented without it invites a reader to think the list is the whole
// story, and the methodology because NET versus GROSS changes what every number means.
#let contribution-reconciliation(reconciliation, methodology) = block(
  breakable: false,
  width: 100%,
)[
  #text(size: text-micro, fill: slate)[#reconciliation]
  #linebreak()
  #text(size: text-micro, fill: slate)[#methodology]
]

// What a panel cannot say for itself: one explanatory line beneath it, drawn only when
// there is something true to say, because a note that is always there is furniture.
// Started life as `benchmark-note`; renamed when the risk panel became its second
// consumer -- the promote-on-second-consumer rule (#150) applied at the first chance.
#let panel-note(message) = [
  #v(4pt)
  #text(size: text-micro, fill: slate)[#message]
]

// One row of the earnings statement: a label and a money amount, compact enough that the
// whole statement fits the transaction page's measured empty half (#233).
#let earnings-line(label, amount) = grid(
  columns: (1fr, auto),
  column-gutter: 8pt,
  [#text(size: text-micro, fill: slate)[#label]],
  [#align(right)[#text(size: text-micro, weight: 500, fill: ink)[#amount]]],
)

// What the transaction table adds up to, beside the table it summarises. Two compact
// blocks -- income and realized -- designed to a 12-14 line budget, because the slot is
// the bottom of a page the table is already on, not a page of its own.
#let earnings-statement(income-title, realized-title, income, realized) = block(
  breakable: false,
  width: 100%,
)[
  #v(10pt)
  #section-subtitle("Period earnings")
  #v(6pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 18pt,
    [
      #report-panel([
        #text(size: text-caption, weight: 650, fill: navy)[#income-title]
        #v(4pt)
        #income
      ], inset: 9pt)
    ],
    [
      #report-panel([
        #text(size: text-caption, weight: 650, fill: navy)[#realized-title]
        #v(4pt)
        #realized
      ], inset: 9pt)
    ],
  )
]

// One row of the attribution bridge (#160): a segment floating at its cumulative
// position on a shared track, with the zero line drawn where zero falls in the shared
// span. `kind` decides the fill: parts are gain/loss, the residual is slate (the
// source's verdict on its size is prose, never colour), and the total is accent -- the
// authoritative destination the parts explain, drawn from its own stated figure so a
// gap between the parts' endpoint and the total stays visible.
#let bridge-row(label-text, amount, offset, width, negative, kind, zero) = [
  #grid(
    columns: (1.5fr, 1.6fr, 0.62fr),
    column-gutter: 7pt,
    [#text(size: text-micro, fill: ink)[#label-text]],
    [#block(width: 100%, height: 9.5pt, fill: mist, radius: 2pt)[
      #place(left + horizon, dx: zero, rect(width: 0.6pt, height: 12.5pt, fill: slate))
      #place(left + horizon, dx: offset, rect(
        width: width,
        height: 4.5pt,
        radius: 1pt,
        fill: if kind == "total" { accent } else if kind == "residual" { slate } else if negative { loss } else { gain },
      ))
    ]],
    [#align(right)[#text(size: text-micro, weight: 500, fill: ink)[#amount]]],
  )
]
