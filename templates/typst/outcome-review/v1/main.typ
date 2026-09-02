#import "_design.typ": accent, document-reference-mark, evidence-row, ink, key-value-row, key-value-rows, label, muted, rule, text-body, text-caption, text-document, text-lead, text-small, text-subhead, value

#set document(title: "Outcome review ${OUTCOME_REVIEW_ID}", author: "Lotus")

#set page(
  paper: "a4",
  margin: (x: 18mm, y: 16mm),
  footer: context [
    #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
    #v(5pt)
    #grid(
      columns: (1fr, auto),
      [#text(size: text-caption, fill: muted)[#"${PORTFOLIO_ID}" / #"${OUTCOME_REVIEW_ID}"]#document-reference-mark("${DOCUMENT_REFERENCE}")],
      [#text(size: text-caption, fill: ink)[#counter(page).display("1 / 1")]],
    )
  ],
  footer-descent: 38%,
)

#set text(size: text-body, fill: ink)
#set par(leading: 1.1em, spacing: 0.45em)

#let dimension-row(dimension, state, expected, realized, variance, explanation) = evidence-row((
  // The three measures hold a number or "Not available"; the explanation holds a
  // sentence, so it takes the width the measures do not need.
  (name: "Dimension", share: 1.15, body: value(dimension)),
  (name: "State", share: 1.15, body: value(state)),
  (name: "Expected", share: 0.85, body: value(expected)),
  (name: "Realized", share: 0.85, body: value(realized)),
  (name: "Variance", share: 0.85, body: value(variance)),
  (name: "Explanation", share: 2.15, body: explanation),
))

#text(size: text-document, weight: "medium", fill: ink)[#"${TITLE}"]
#v(4pt)
#text(size: text-small, fill: muted)[Governed post-trade outcome-review report / #"${STATE}"]

#v(10pt)
#grid(
  columns: (1fr, 1fr, 1fr),
  gutter: 7mm,
  [#label("Portfolio") #linebreak() #value[#"${PORTFOLIO_ID}"]],
  [#label("Review") #linebreak() #value[#"${OUTCOME_REVIEW_ID}"]],
  [#label("Window") #linebreak() #value[#"${REVIEW_WINDOW_START}" to #"${REVIEW_WINDOW_END}"]],
)

#v(8pt)
#text(size: text-subhead, weight: "medium")[Outcome Summary]
#v(3pt)
#"${OVERALL_OUTCOME}"

#v(8pt)
#text(size: text-subhead, weight: "medium")[Dimension Evidence]
#v(3pt)
${DIMENSION_ROWS}

#v(8pt)
#grid(
  columns: (1fr, 1fr),
  gutter: 8mm,
  [
    #text(size: text-lead, weight: "medium")[Lineage]
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
    #text(size: text-lead, weight: "medium")[Hashes]
    #v(3pt)
    #key-value-rows((
      ([Report input], [#"${CONTENT_HASH}"]),
      ([Outcome review], [#"${OUTCOME_REVIEW_CONTENT_HASH}"]),
    ))
  ],
)

#v(8pt)
#text(size: text-lead, weight: "medium")[Source Hashes]
#v(3pt)
${SOURCE_HASH_ROWS}

#v(6pt)
#text(size: text-lead, weight: "medium")[Proof-Pack Section Hashes]
#v(3pt)
${SECTION_HASH_ROWS}

#v(10pt)
#line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
#v(4pt)
#text(size: text-caption, fill: muted)[Render #"${RENDER_JOB_ID}" / #"${TEMPLATE_ID}" #"${TEMPLATE_VERSION}" / #"${TIMEZONE}"]
#linebreak()
#text(size: text-caption, fill: muted)[#"${DETERMINISM_STATEMENT}"]
