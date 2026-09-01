#import "_design.typ": accent, evidence-row, ink, key-value-row, key-value-rows, label, muted, rule, text-body, text-caption, text-document, text-lead, text-small, text-subhead, value
#set page(
  paper: "a4",
  margin: (x: 18mm, y: 16mm),
  footer: context [
    #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
    #v(5pt)
    #grid(
      columns: (1fr, auto),
      [#text(size: text-caption, fill: muted)[#"${PORTFOLIO_ID}" / #"${PROOF_PACK_ID}"]],
      [#text(size: text-caption, fill: ink)[#counter(page).display("1 / 1")]],
    )
  ],
  footer-descent: 38%,
)

#set text(size: text-body, fill: ink)
#set par(leading: 1.1em, spacing: 0.45em)

#let section-row(title, section-type, state, summary, reasons) = evidence-row((
  (name: "Section", share: 1.3, body: value(title)),
  (name: "Type", share: 0.9, body: value(section-type)),
  (name: "State", share: 1.0, body: value(state)),
  (name: "Summary", share: 2.2, body: [
    #summary #linebreak() #label("Reasons") #linebreak() #reasons
  ]),
))

#text(size: text-document, weight: "medium", fill: ink)[#"${TITLE}"]
#v(4pt)
#text(size: text-small, fill: muted)[Governed pre-trade proof-pack report / #"${STATE}"]

#v(10pt)
#grid(
  columns: (1fr, 1fr, 1fr),
  gutter: 7mm,
  [#label("Portfolio") #linebreak() #value[#"${PORTFOLIO_ID}"]],
  [#label("Proof pack") #linebreak() #value[#"${PROOF_PACK_ID}"]],
  [#label("As of") #linebreak() #value[#"${AS_OF_DATE}"]],
)

#v(8pt)
#grid(
  columns: (1fr, 1fr),
  gutter: 8mm,
  [
    #text(size: text-lead, weight: "medium")[Decision Summary]
    #v(3pt)
    #key-value-rows((
      ([Action], [#"${DECISION_ACTION}"]),
      ([Mandate], [#"${MANDATE_ID}"]),
    ))
    #v(3pt)
    #"${DECISION_RATIONALE}"
  ],
  [
    #text(size: text-lead, weight: "medium")[Supportability]
    #v(3pt)
    #key-value-rows((
      ([Status], [#"${SUPPORTABILITY_STATUS}"]),
      ([Reasons], [#"${SUPPORTABILITY_REASONS}"]),
      ([Redaction], [#"${REDACTION_POLICY}"]),
    ))
  ],
)

#v(8pt)
#text(size: text-subhead, weight: "medium")[Proof-Pack Sections]
#v(3pt)
${SECTION_ROWS}

#v(8pt)
#text(size: text-lead, weight: "medium")[Source Hashes]
#v(3pt)
${SOURCE_HASH_ROWS}

#v(6pt)
#text(size: text-lead, weight: "medium")[Source Authority Boundary]
#v(3pt)
#key-value-rows((
  ([Source contract], [#"${SOURCE_CONTRACT_VERSION}"]),
  ([Client publication authority], [#"${CLIENT_PUBLICATION_AUTHORITY}"]),
))
${SOURCE_LINEAGE_ROWS}

#v(6pt)
#text(size: text-lead, weight: "medium")[Report Lineage]
#v(3pt)
#key-value-rows((
  ([Report input], [#"${CONTENT_HASH}"]),
  ([Proof pack], [#"${PROOF_PACK_CONTENT_HASH}"]),
))

#v(10pt)
#line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
#v(4pt)
#text(size: text-caption, fill: muted)[Render #"${RENDER_JOB_ID}" / #"${TEMPLATE_ID}" #"${TEMPLATE_VERSION}" / #"${TIMEZONE}"]
#linebreak()
#text(size: text-caption, fill: muted)[#"${DETERMINISM_STATEMENT}"]
