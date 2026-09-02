#import "_design.typ": accent, document-reference-mark, evidence-row, ink, key-value-row, key-value-rows, label, muted, rule, text-body, text-caption, text-document, text-lead, text-small, text-subhead, value

#set document(title: "Rebalance wave ${WAVE_ID}", author: "Lotus")

#set page(
  paper: "a4",
  margin: (x: 18mm, y: 16mm),
  footer: context [
    #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
    #v(5pt)
    #grid(
      columns: (1fr, auto),
      [#text(size: text-caption, fill: muted)[#"${WAVE_ID}" / #"${WAVE_STATE}"]#document-reference-mark("${DOCUMENT_REFERENCE}")],
      [#text(size: text-caption, fill: ink)[#counter(page).display("1 / 1")]],
    )
  ],
  footer-descent: 38%,
)

#set text(size: text-body, fill: ink)
#set par(leading: 1.1em, spacing: 0.45em)

#let wave-item-row(portfolio, state, proof-pack, proof-state, alternative, reasons) = evidence-row((
  (name: "Portfolio", share: 1.2, body: value(portfolio)),
  (name: "State", share: 1.1, body: value(state)),
  (name: "Proof pack", share: 0.85, body: value(proof-pack)),
  (name: "Proof state", share: 0.85, body: value(proof-state)),
  (name: "Alternative", share: 1.5, body: [
    #value(alternative) #linebreak() #label("Reasons") #linebreak() #reasons
  ]),
))

#text(size: text-document, weight: "medium", fill: ink)[#"${TITLE}"]
#v(4pt)
#text(size: text-small, fill: muted)[Governed rebalance-wave evidence report / #"${WAVE_STATE}"]

#v(10pt)
#grid(
  columns: (1fr, 1fr, 1fr),
  gutter: 7mm,
  [#label("Wave") #linebreak() #value[#"${WAVE_ID}"]],
  [#label("Trigger") #linebreak() #value[#"${TRIGGER_TYPE}"]],
  [#label("As of") #linebreak() #value[#"${AS_OF_DATE}"]],
)

#v(8pt)
#grid(
  columns: (1fr, 1fr),
  gutter: 8mm,
  [
    #text(size: text-lead, weight: "medium")[Wave Summary]
    #v(3pt)
    #key-value-rows((
      ([Trigger id], [#"${TRIGGER_ID}"]),
      ([Items], [#"${ITEM_COUNT}"]),
      ([Ready items], [#"${READY_ITEM_COUNT}"]),
      ([Blocked items], [#"${BLOCKED_ITEM_COUNT}"]),
    ))
    #v(3pt)
    #"${TRIGGER_RATIONALE}"
  ],
  [
    #text(size: text-lead, weight: "medium")[Supportability]
    #v(3pt)
    #key-value-rows((
      ([Status], [#"${SUPPORTABILITY_STATUS}"]),
      ([Reason], [#"${SUPPORTABILITY_REASON}"]),
      ([Proof packs ready], [#"${PROOF_PACK_READY_COUNT}"]),
      ([Proof packs degraded], [#"${PROOF_PACK_DEGRADED_COUNT}"]),
      ([Handoffs], [#"${HANDOFF_COUNT}"]),
      ([External execution], [#"${EXTERNAL_EXECUTION}"]),
    ))
  ],
)

#v(8pt)
#text(size: text-subhead, weight: "medium")[Wave Items]
#v(3pt)
${ITEM_ROWS}

#v(8pt)
#text(size: text-lead, weight: "medium")[Recent Event Timeline]
#v(3pt)
${EVENT_ROWS}

#v(6pt)
#text(size: text-lead, weight: "medium")[Report Lineage]
#v(3pt)
#key-value-rows((
  ([Report input], [#"${CONTENT_HASH}"]),
  ([Wave], [#"${WAVE_CONTENT_HASH}"]),
  ([Redaction], [#"${REDACTION_POLICY}"]),
))

#v(10pt)
#line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
#v(4pt)
#text(size: text-caption, fill: muted)[Render #"${RENDER_JOB_ID}" / #"${TEMPLATE_ID}" #"${TEMPLATE_VERSION}" / #"${TIMEZONE}"]
#linebreak()
#text(size: text-caption, fill: muted)[#"${DETERMINISM_STATEMENT}"]
