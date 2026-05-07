#let ink = rgb("#18202f")
#let muted = rgb("#526071")
#let rule = rgb("#d7dde5")
#let accent = rgb("#315c8a")

#set page(
  paper: "a4",
  margin: (x: 18mm, y: 16mm),
  footer: context [
    #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
    #v(5pt)
    #grid(
      columns: (1fr, auto),
      [#text(size: 6.6pt, fill: muted)[${WAVE_ID} / ${WAVE_STATE}]],
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

#let wave-item-row(portfolio, state, proof-pack, proof-state, alternative, reasons) = block(
  below: 5pt,
  stroke: (left: (paint: accent, thickness: 1.1pt)),
  inset: (left: 5pt, y: 3pt),
)[
  #grid(
    columns: (30mm, 24mm, 26mm, 24mm, 1fr),
    gutter: 4mm,
    [#label("Portfolio") #linebreak() #value(portfolio)],
    [#label("State") #linebreak() #value(state)],
    [#label("Proof pack") #linebreak() #value(proof-pack)],
    [#label("Proof state") #linebreak() #value(proof-state)],
    [#label("Alternative") #linebreak() #value(alternative) #linebreak() #label("Reasons") #linebreak() #reasons],
  )
]

#text(size: 18pt, weight: "medium", fill: ink)[${TITLE}]
#v(4pt)
#text(size: 8pt, fill: muted)[Governed rebalance-wave evidence report / ${WAVE_STATE}]

#v(10pt)
#grid(
  columns: (1fr, 1fr, 1fr),
  gutter: 7mm,
  [#label("Wave") #linebreak() #value[${WAVE_ID}]],
  [#label("Trigger") #linebreak() #value[${TRIGGER_TYPE}]],
  [#label("As of") #linebreak() #value[${AS_OF_DATE}]],
)

#v(8pt)
#grid(
  columns: (1fr, 1fr),
  gutter: 8mm,
  [
    #text(size: 11pt, weight: "medium")[Wave Summary]
    #v(3pt)
    #key-value-row([Trigger id], [${TRIGGER_ID}])
    #key-value-row([Items], [${ITEM_COUNT}])
    #key-value-row([Ready items], [${READY_ITEM_COUNT}])
    #key-value-row([Blocked items], [${BLOCKED_ITEM_COUNT}])
    #v(3pt)
    ${TRIGGER_RATIONALE}
  ],
  [
    #text(size: 11pt, weight: "medium")[Supportability]
    #v(3pt)
    #key-value-row([Status], [${SUPPORTABILITY_STATUS}])
    #key-value-row([Reason], [${SUPPORTABILITY_REASON}])
    #key-value-row([Proof packs ready], [${PROOF_PACK_READY_COUNT}])
    #key-value-row([Proof packs degraded], [${PROOF_PACK_DEGRADED_COUNT}])
    #key-value-row([Handoffs], [${HANDOFF_COUNT}])
    #key-value-row([External execution], [${EXTERNAL_EXECUTION}])
  ],
)

#v(8pt)
#text(size: 12pt, weight: "medium")[Wave Items]
#v(3pt)
${ITEM_ROWS}

#v(8pt)
#text(size: 11pt, weight: "medium")[Recent Event Timeline]
#v(3pt)
${EVENT_ROWS}

#v(6pt)
#text(size: 11pt, weight: "medium")[Report Lineage]
#v(3pt)
#key-value-row([Report input], [${CONTENT_HASH}])
#key-value-row([Wave], [${WAVE_CONTENT_HASH}])
#key-value-row([Redaction], [${REDACTION_POLICY}])

#v(10pt)
#line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
#v(4pt)
#text(size: 6.8pt, fill: muted)[Render ${RENDER_JOB_ID} / ${TEMPLATE_ID} ${TEMPLATE_VERSION} / ${TIMEZONE}]
#linebreak()
#text(size: 6.8pt, fill: muted)[${DETERMINISM_STATEMENT}]
