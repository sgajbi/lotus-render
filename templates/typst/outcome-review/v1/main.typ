#let ink = rgb("#18202f")
#let muted = rgb("#526071")
#let rule = rgb("#d7dde5")
#let accent = rgb("#21606f")

#set page(
  paper: "a4",
  margin: (x: 18mm, y: 16mm),
  footer: context [
    #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
    #v(5pt)
    #grid(
      columns: (1fr, auto),
      [#text(size: 6.6pt, fill: muted)[${PORTFOLIO_ID} / ${OUTCOME_REVIEW_ID}]],
      [#text(size: 6.8pt, fill: ink)[#counter(page).display("1 / 1")]],
    )
  ],
  footer-descent: 38%,
)

#set text(size: 9pt, fill: ink)
#set par(leading: 1.1em, spacing: 0.45em)

#let label(value) = text(size: 6.9pt, fill: muted, weight: "semibold", upper(value))
#let value(value) = text(size: 9.2pt, fill: ink, weight: "medium", value)

#let key-value-row(key, val) = grid(
  columns: (38mm, 1fr),
  gutter: 5mm,
  row-gutter: 2pt,
  key,
  val,
)

#let dimension-row(dimension, state, expected, realized, variance, explanation) = block(
  below: 5pt,
  stroke: (left: (paint: accent, thickness: 1.1pt)),
  inset: (left: 5pt, y: 3pt),
)[
  #grid(
    columns: (24mm, 18mm, 22mm, 22mm, 22mm, 1fr),
    gutter: 4mm,
    [#label("Dimension") #linebreak() #value(dimension)],
    [#label("State") #linebreak() #value(state)],
    [#label("Expected") #linebreak() #value(expected)],
    [#label("Realized") #linebreak() #value(realized)],
    [#label("Variance") #linebreak() #value(variance)],
    [#label("Explanation") #linebreak() #explanation],
  )
]

#text(size: 18pt, weight: "medium", fill: ink)[${TITLE}]
#v(4pt)
#text(size: 8pt, fill: muted)[Governed post-trade outcome-review report / ${STATE}]

#v(10pt)
#grid(
  columns: (1fr, 1fr, 1fr),
  gutter: 7mm,
  [#label("Portfolio") #linebreak() #value[${PORTFOLIO_ID}]],
  [#label("Review") #linebreak() #value[${OUTCOME_REVIEW_ID}]],
  [#label("Window") #linebreak() #value[${REVIEW_WINDOW_START} to ${REVIEW_WINDOW_END}]],
)

#v(8pt)
#text(size: 12pt, weight: "medium")[Outcome Summary]
#v(3pt)
${OVERALL_OUTCOME}

#v(8pt)
#text(size: 12pt, weight: "medium")[Dimension Evidence]
#v(3pt)
${DIMENSION_ROWS}

#v(8pt)
#grid(
  columns: (1fr, 1fr),
  gutter: 8mm,
  [
    #text(size: 11pt, weight: "medium")[Lineage]
    #v(3pt)
    #key-value-row([Source services], [${SOURCE_SERVICES}])
    #key-value-row([Proof pack], [${PROOF_PACK_ID}])
    #key-value-row([Rebalance run], [${REBALANCE_RUN_ID}])
    #key-value-row([Wave], [${WAVE_ID}])
    #key-value-row([Redaction], [${REDACTION_POLICY}])
  ],
  [
    #text(size: 11pt, weight: "medium")[Hashes]
    #v(3pt)
    #key-value-row([Report input], [${CONTENT_HASH}])
    #key-value-row([Outcome review], [${OUTCOME_REVIEW_CONTENT_HASH}])
  ],
)

#v(8pt)
#text(size: 11pt, weight: "medium")[Source Hashes]
#v(3pt)
${SOURCE_HASH_ROWS}

#v(6pt)
#text(size: 11pt, weight: "medium")[Proof-Pack Section Hashes]
#v(3pt)
${SECTION_HASH_ROWS}

#v(10pt)
#line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
#v(4pt)
#text(size: 6.8pt, fill: muted)[Render ${RENDER_JOB_ID} / ${TEMPLATE_ID} ${TEMPLATE_VERSION} / ${TIMEZONE}]
#linebreak()
#text(size: 6.8pt, fill: muted)[${DETERMINISM_STATEMENT}]
