#import "_design.typ": accent, ink, key-value-row, key-value-rows, label, muted, rule, value
#set page(
  paper: "a4",
  margin: (x: 18mm, y: 16mm),
  footer: context [
    #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
    #v(5pt)
    #grid(
      columns: (1fr, auto),
      [#text(size: 6.8pt, fill: muted)[#"${PORTFOLIO_ID}" / #"${OUTCOME_REVIEW_ID}"]],
      [#text(size: 6.8pt, fill: ink)[#counter(page).display("1 / 1")]],
    )
  ],
  footer-descent: 38%,
)

#set text(size: 8.8pt, fill: ink)
#set par(leading: 1.1em, spacing: 0.45em)

#let dimension-row(dimension, state, expected, realized, variance, explanation) = block(
  below: 5pt,
  stroke: (left: (paint: accent, thickness: 1.1pt)),
  inset: (left: 5pt, y: 3pt),
)[
  #grid(
    columns: (auto, auto, auto, auto, auto, 1fr),
    gutter: 4mm,
    [#label("Dimension") #linebreak() #value(dimension)],
    [#label("State") #linebreak() #value(state)],
    [#label("Expected") #linebreak() #value(expected)],
    [#label("Realized") #linebreak() #value(realized)],
    [#label("Variance") #linebreak() #value(variance)],
    [#label("Explanation") #linebreak() #explanation],
  )
]

#text(size: 18pt, weight: "medium", fill: ink)[#"${TITLE}"]
#v(4pt)
#text(size: 8.1pt, fill: muted)[Governed post-trade outcome-review report / #"${STATE}"]

#v(10pt)
#grid(
  columns: (1fr, 1fr, 1fr),
  gutter: 7mm,
  [#label("Portfolio") #linebreak() #value[#"${PORTFOLIO_ID}"]],
  [#label("Review") #linebreak() #value[#"${OUTCOME_REVIEW_ID}"]],
  [#label("Window") #linebreak() #value[#"${REVIEW_WINDOW_START}" to #"${REVIEW_WINDOW_END}"]],
)

#v(8pt)
#text(size: 12pt, weight: "medium")[Outcome Summary]
#v(3pt)
#"${OVERALL_OUTCOME}"

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
    #key-value-rows((
      ([Source services], [#"${SOURCE_SERVICES}"]),
      ([Proof pack], [#"${PROOF_PACK_ID}"]),
      ([Rebalance run], [#"${REBALANCE_RUN_ID}"]),
      ([Wave], [#"${WAVE_ID}"]),
      ([Redaction], [#"${REDACTION_POLICY}"]),
    ))
  ],
  [
    #text(size: 11pt, weight: "medium")[Hashes]
    #v(3pt)
    #key-value-rows((
      ([Report input], [#"${CONTENT_HASH}"]),
      ([Outcome review], [#"${OUTCOME_REVIEW_CONTENT_HASH}"]),
    ))
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
#text(size: 6.8pt, fill: muted)[Render #"${RENDER_JOB_ID}" / #"${TEMPLATE_ID}" #"${TEMPLATE_VERSION}" / #"${TIMEZONE}"]
#linebreak()
#text(size: 6.8pt, fill: muted)[#"${DETERMINISM_STATEMENT}"]
