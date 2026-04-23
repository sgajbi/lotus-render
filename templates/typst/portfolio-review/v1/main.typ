#set page(
  paper: "a4",
  margin: (top: 1.8cm, bottom: 1.8cm, x: 1.75cm),
)

#set text(size: 10.5pt)
#set par(justify: false, leading: 0.65em)

#let ink = rgb(23, 50, 77)
#let ink-muted = rgb(93, 111, 130)
#let accent = rgb(30, 92, 138)
#let panel = rgb(245, 248, 251)
#let border = rgb(214, 224, 234)

#let fact(label, value) = box(
  fill: white,
  stroke: border,
  inset: 10pt,
  radius: 6pt,
  width: 100%,
)[
  #text(size: 8.5pt, weight: "medium", fill: ink-muted)[#label]
  #v(3pt)
  #text(size: 11pt, weight: "semibold", fill: ink)[#value]
]

#box(
  fill: panel,
  inset: 16pt,
  radius: 8pt,
  width: 100%,
)[
  #grid(
    columns: (1.55fr, 1fr),
    column-gutter: 16pt,
    [
      #text(size: 22pt, weight: "bold", fill: ink)[Portfolio Review]
      #v(4pt)
      #text(size: 10pt, fill: ink-muted)[
        Governed private banking portfolio review rendered by lotus-render.
      ]
      #v(12pt)
      #text(size: 8.5pt, weight: "medium", fill: accent)[Client]
      #v(2pt)
      #text(size: 13pt, weight: "semibold", fill: ink)[${CLIENT_NAME}]
      #v(10pt)
      #text(size: 8.5pt, weight: "medium", fill: accent)[Portfolio]
      #v(2pt)
      #text(size: 13pt, weight: "semibold", fill: ink)[${PORTFOLIO_NAME}]
    ],
    [
      #fact("As of", "${AS_OF_DATE}")
      #v(8pt)
      #fact("Total Value", "${CURRENCY} ${TOTAL_VALUE}")
      #v(8pt)
      #fact("Timezone", "${TIMEZONE}")
    ],
  )
]

#v(16pt)
#text(size: 13pt, weight: "semibold", fill: ink)[Executive Summary]
#v(4pt)
#rect(width: 100%, height: 0.7pt, fill: border)
#v(8pt)
${SUMMARY_PARAGRAPH}

#v(16pt)
#text(size: 13pt, weight: "semibold", fill: ink)[Review Observations]
#v(4pt)
#rect(width: 100%, height: 0.7pt, fill: border)
#v(8pt)
${OBSERVATIONS}

#v(16pt)
#text(size: 13pt, weight: "semibold", fill: ink)[Governance]
#v(4pt)
#rect(width: 100%, height: 0.7pt, fill: border)
#v(8pt)
#box(
  fill: panel,
  stroke: border,
  inset: 12pt,
  radius: 6pt,
  width: 100%,
)[
  #grid(
    columns: (2.8cm, 1fr),
    column-gutter: 10pt,
    row-gutter: 6pt,
    [
      #text(size: 8.5pt, weight: "medium", fill: ink-muted)[Template]
    ],
    [
      #text(fill: ink)[${TEMPLATE_ID} ${TEMPLATE_VERSION}]
    ],
    [
      #text(size: 8.5pt, weight: "medium", fill: ink-muted)[Render Job]
    ],
    [
      #text(fill: ink)[${RENDER_JOB_ID}]
    ],
    [
      #text(size: 8.5pt, weight: "medium", fill: ink-muted)[Requested By]
    ],
    [
      #text(fill: ink)[${REQUESTED_BY}]
    ],
    [
      #text(size: 8.5pt, weight: "medium", fill: ink-muted)[Correlation ID]
    ],
    [
      #text(fill: ink)[${CORRELATION_ID}]
    ],
    [
      #text(size: 8.5pt, weight: "medium", fill: ink-muted)[Trace ID]
    ],
    [
      #text(fill: ink)[${TRACE_ID}]
    ],
    [
      #text(size: 8.5pt, weight: "medium", fill: ink-muted)[Determinism]
    ],
    [
      #text(fill: ink)[${DETERMINISM_STATEMENT}]
    ],
  )
]
