#import "_appendix_text.typ": GLOSSARY
#import "_theme.typ": accent, body-muted, empty-state, ink, section-subtitle, slate, soft-rule, text-fine, text-small
#import "_components.typ": section-marker

// The appendix was a six-page statement spread: its own title block, its own navigation
// list, its own margins and 6.95pt type, printed identically in every document. It
// defined ESG attributes, private markets, hedge funds, real estate, an income overview
// and a portfolio health check, none of which this report renders, and defined none of
// the risk measures it does. It also published six exchange rates and a table of
// expected returns and drawdowns that appear nowhere in the render package -- figures
// no one supplied, dated two years before the reports carrying them (#184).
//
// What is left is the part that was worth keeping: the terms this document uses, in
// this document's own typography, chosen by what it contains.

#let glossary-entry(number, entry) = block(breakable: false, width: 100%)[
  #grid(
    columns: (13pt, 1fr),
    column-gutter: 5pt,
    // Numbered within its group, the way a reader cites a definition back to
    // an advisor -- "under Positions, point 03".
    [#text(size: text-fine, weight: 600, fill: accent)[#number]],
    [
      #text(size: text-small, weight: 600, fill: ink)[#entry.term]
      #v(2.5pt)
      #text(size: text-fine, fill: slate)[#entry.body]
    ],
  )
]

// `sticky` keeps the heading with the entries beneath it. Without it the heading is a
// block like any other and lands alone at the foot of a page -- which is what happened
// the first time this rendered, and is the same widow `labelled-table` exists to stop.
#let entry-number(index) = {
  let n = index + 1
  if n < 10 { "0" + str(n) } else { str(n) }
}

#let glossary-column(keys, start) = [
  #set par(leading: 0.62em, spacing: 0.62em)
  #for (offset, key) in keys.enumerate() [
    #glossary-entry(entry-number(start + offset), GLOSSARY.at(key))
    #v(9pt)
  ]
]

// Entries are split down the middle rather than dealt across a grid row by row: a grid
// makes every row as tall as its tallest cell, so a two-line definition beside a
// five-line one leaves three lines of nothing. `columns()` is not the answer either --
// it fills to the height of the page before wrapping, so a group that fits leaves the
// second column empty. The contents page splits its entries the same way.
#let glossary-group(group) = [
  // The gap above a group is padding inside the block, not spacing before it: spacing
  // between blocks is collapsed at a page boundary, so a group that opens a page had
  // its heading pressed against the running header's rule.
  #block(sticky: true, breakable: false, width: 100%, inset: (top: 17pt))[
    #section-subtitle(group.title)
    #v(5pt)
    #soft-rule()
  ]
  #v(9pt)
  #let half = int(calc.ceil(group.keys.len() / 2))
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 26pt,
    glossary-column(group.keys.slice(0, half), 0),
    glossary-column(group.keys.slice(half), half),
  )
]

#let appendix-page() = [
  #section-marker("Appendix", "Definitions and explanatory notes")
  #v(8pt)
  #body-muted(
    "These notes explain the terms used in this report. They cover what this document shows and nothing else.",
  )
  #v(14pt)
  #let groups = ${APPENDIX_GLOSSARY_GROUPS}
  #if groups.len() == 0 [
    #empty-state("No explanatory notes apply to the contents of this report.")
  ] else [
    #for group in groups [
      #glossary-group(group)
    ]
  ]
]
