#set page(
  paper: "a4",
  margin: (top: 1.6cm, bottom: 1.8cm, x: 1.65cm),
  numbering: "1",
  number-align: right + bottom,
  header: [
    #set text(size: 8.5pt, fill: rgb(116, 129, 143))
    #align(right)[Portfolio Review]
  ],
)

#set text(size: 10.5pt, fill: rgb(28, 42, 58))
#set par(justify: false, leading: 0.7em)
#set list(spacing: 0.45em)

#let navy = rgb(20, 43, 66)
#let blue = rgb(28, 92, 138)
#let blue-soft = rgb(235, 243, 250)
#let sand = rgb(248, 246, 241)
#let border = rgb(217, 225, 233)
#let muted = rgb(104, 118, 132)
#let page-line = rgb(229, 235, 241)

#let metric-card(label, value, tint: white) = box(
  width: 100%,
  fill: tint,
  stroke: border,
  radius: 8pt,
  inset: 12pt,
)[
  #text(size: 8.2pt, weight: "medium", fill: muted)[#label]
  #v(4pt)
  #text(size: 12pt, weight: "semibold", fill: navy)[#value]
]

#let review-note(text) = box(
  width: 100%,
  fill: white,
  stroke: border,
  radius: 7pt,
  inset: 11pt,
)[
  #text(size: 9.6pt, fill: rgb(48, 65, 83))[#text]
]

#box(
  width: 100%,
  fill: navy,
  radius: 10pt,
  inset: 18pt,
)[
  #grid(
    columns: (1.7fr, 0.95fr),
    column-gutter: 18pt,
    [
      #text(size: 8.4pt, weight: "medium", fill: rgb(188, 211, 232))[LOTUS PRIVATE BANKING]
      #v(7pt)
      #text(size: 22pt, weight: "bold", fill: white)[Portfolio Review]
      #v(6pt)
      #text(size: 10pt, fill: rgb(221, 232, 242))[
        Governed portfolio review rendered from the lotus-report snapshot and
        prepared for advisor-led client servicing.
      ]
      #v(16pt)
      #grid(
        columns: (1fr, 1fr),
        column-gutter: 14pt,
        row-gutter: 10pt,
        [
          #text(size: 8pt, weight: "medium", fill: rgb(188, 211, 232))[Client]
          #v(2pt)
          #text(size: 13pt, weight: "semibold", fill: white)[${CLIENT_NAME}]
        ],
        [
          #text(size: 8pt, weight: "medium", fill: rgb(188, 211, 232))[Portfolio]
          #v(2pt)
          #text(size: 13pt, weight: "semibold", fill: white)[${PORTFOLIO_NAME}]
        ],
      )
    ],
    [
      #box(
        fill: white,
        radius: 8pt,
        inset: 12pt,
        width: 100%,
      )[
        #metric-card("As of", "${AS_OF_DATE}", tint: white)
        #v(8pt)
        #metric-card("Total Value", "${CURRENCY} ${TOTAL_VALUE}", tint: blue-soft)
        #v(8pt)
        #metric-card("Timezone", "${TIMEZONE}", tint: sand)
      ]
    ],
  )
]

#v(16pt)

#grid(
  columns: (1.3fr, 0.95fr),
  column-gutter: 16pt,
  [
    #text(size: 8pt, weight: "medium", fill: blue)[PORTFOLIO POSITION]
    #v(2pt)
    #text(size: 13pt, weight: "bold", fill: navy)[Executive Summary]
    #v(6pt)
    #rect(width: 100%, height: 0.8pt, fill: page-line)
    #v(8pt)
    #box(
      width: 100%,
      fill: blue-soft,
      stroke: border,
      radius: 8pt,
      inset: 14pt,
    )[
      #text(size: 10.6pt, fill: rgb(42, 61, 79))[${SUMMARY_PARAGRAPH}]
    ]
  ],
  [
    #text(size: 8pt, weight: "medium", fill: blue)[DOCUMENT FRAME]
    #v(2pt)
    #text(size: 13pt, weight: "bold", fill: navy)[Review Scope]
    #v(6pt)
    #rect(width: 100%, height: 0.8pt, fill: page-line)
    #v(8pt)
    #box(
      width: 100%,
      fill: sand,
      stroke: border,
      radius: 8pt,
      inset: 14pt,
    )[
      #text(size: 9pt, weight: "medium", fill: blue)[Advisory Context]
      #v(4pt)
      #text(size: 9.6pt)[
        This review summarizes the governed portfolio snapshot for the requested
        valuation date and provides service-ready observations for client
        discussion.
      ]
    ]
  ],
)

#v(16pt)
#text(size: 8pt, weight: "medium", fill: blue)[ADVISOR BRIEFING]
#v(2pt)
#text(size: 13pt, weight: "bold", fill: navy)[Review Observations]
#v(6pt)
#rect(width: 100%, height: 0.8pt, fill: page-line)
#v(10pt)

#box(
  width: 100%,
  fill: white,
  stroke: border,
  radius: 8pt,
  inset: 12pt,
)[
  ${OBSERVATIONS}
]

#v(16pt)
#text(size: 8pt, weight: "medium", fill: blue)[CONTROL SURFACE]
#v(2pt)
#text(size: 13pt, weight: "bold", fill: navy)[Governance And Lineage]
#v(6pt)
#rect(width: 100%, height: 0.8pt, fill: page-line)
#v(10pt)

#grid(
  columns: (1fr, 1fr),
  column-gutter: 14pt,
  row-gutter: 10pt,
  [
    #metric-card("Template", "${TEMPLATE_ID} ${TEMPLATE_VERSION}", tint: white)
  ],
  [
    #metric-card("Render Job", "${RENDER_JOB_ID}", tint: white)
  ],
  [
    #metric-card("Requested By", "${REQUESTED_BY}", tint: white)
  ],
  [
    #metric-card("Correlation ID", "${CORRELATION_ID}", tint: white)
  ],
  [
    #metric-card("Trace ID", "${TRACE_ID}", tint: white)
  ],
  [
    #metric-card("Determinism", "${DETERMINISM_STATEMENT}", tint: blue-soft)
  ],
)

#v(18pt)
#align(center)[
  #text(size: 8.2pt, fill: muted)[Governed output for internal advisory servicing. Not an archival record.]
]
