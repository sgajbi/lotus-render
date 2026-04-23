#set page(
  paper: "a4",
  margin: (top: 1.45cm, bottom: 1.7cm, x: 1.55cm),
  numbering: "1",
  number-align: right + bottom,
  header: [
    #set text(size: 8.5pt, fill: rgb(116, 129, 143))
    #align(right)[Portfolio Review]
  ],
)

#set text(size: 10pt, fill: rgb(28, 42, 58))
#set par(justify: false, leading: 0.72em)

#let navy = rgb(20, 43, 66)
#let blue = rgb(28, 92, 138)
#let blue-soft = rgb(235, 243, 250)
#let sand = rgb(248, 246, 241)
#let border = rgb(217, 225, 233)
#let muted = rgb(104, 118, 132)
#let line = rgb(229, 235, 241)

#let metric-card(label, value, tint: white) = box(
  width: 100%,
  fill: tint,
  stroke: border,
  radius: 8pt,
  inset: 12pt,
)[
  #text(size: 8pt, weight: "medium", fill: muted)[#label]
  #v(4pt)
  #text(size: 12pt, weight: "semibold", fill: navy)[#value]
]

#let detail-card(label, value) = box(
  width: 100%,
  fill: white,
  stroke: border,
  radius: 7pt,
  inset: 10pt,
)[
  #text(size: 7.8pt, weight: "medium", fill: muted)[#label]
  #v(3pt)
  #text(size: 10pt, fill: navy)[#value]
]

#let review-note(content) = box(
  width: 100%,
  fill: white,
  stroke: border,
  radius: 7pt,
  inset: 11pt,
)[
  #text(size: 9.5pt, fill: rgb(48, 65, 83))[#content]
]

#let period-row(period, net, benchmark, relative) = box(
  width: 100%,
  fill: white,
  stroke: border,
  radius: 7pt,
  inset: 10pt,
)[
  #grid(
    columns: (0.65fr, 1fr, 1fr, 1fr),
    column-gutter: 10pt,
    [
      #text(size: 9.4pt, weight: "bold", fill: navy)[#period]
    ],
    [
      #text(size: 7.6pt, weight: "medium", fill: muted)[Net]
      #v(2pt)
      #text(size: 9.2pt)[#net]
    ],
    [
      #text(size: 7.6pt, weight: "medium", fill: muted)[Benchmark]
      #v(2pt)
      #text(size: 9.2pt)[#benchmark]
    ],
    [
      #text(size: 7.6pt, weight: "medium", fill: muted)[Relative]
      #v(2pt)
      #text(size: 9.2pt)[#relative]
    ],
  )
]

#let holding-row(name, asset-class, weight, market-value, pnl, contribution) = box(
  width: 100%,
  fill: white,
  stroke: border,
  radius: 7pt,
  inset: 10pt,
)[
  #grid(
    columns: (1.4fr, 0.8fr, 0.7fr, 0.9fr, 0.9fr, 0.8fr),
    column-gutter: 9pt,
    [
      #text(size: 9.2pt, weight: "semibold", fill: navy)[#name]
    ],
    [
      #text(size: 7.5pt, weight: "medium", fill: muted)[Asset Class]
      #v(2pt)
      #text(size: 8.8pt)[#asset-class]
    ],
    [
      #text(size: 7.5pt, weight: "medium", fill: muted)[Weight]
      #v(2pt)
      #text(size: 8.8pt)[#weight]
    ],
    [
      #text(size: 7.5pt, weight: "medium", fill: muted)[Market Value]
      #v(2pt)
      #text(size: 8.8pt)[#market-value]
    ],
    [
      #text(size: 7.5pt, weight: "medium", fill: muted)[Unrealized PnL]
      #v(2pt)
      #text(size: 8.8pt)[#pnl]
    ],
    [
      #text(size: 7.5pt, weight: "medium", fill: muted)[YTD Contribution]
      #v(2pt)
      #text(size: 8.8pt)[#contribution]
    ],
  )
]

#box(
  width: 100%,
  fill: navy,
  radius: 10pt,
  inset: 18pt,
)[
  #grid(
    columns: (1.6fr, 1fr),
    column-gutter: 18pt,
    [
      #text(size: 8.2pt, weight: "medium", fill: rgb(188, 211, 232))[LOTUS PRIVATE BANKING]
      #v(7pt)
      #text(size: 22pt, weight: "bold", fill: white)[Portfolio Review]
      #v(6pt)
      #text(size: 10pt, fill: rgb(221, 232, 242))[
        Governed advisory review for ${REVIEW_PERIOD_LABEL} built from the lotus-report
        snapshot and rendered inside the lotus-render deterministic runtime envelope.
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
      #metric-card("As of", "${AS_OF_DATE}", tint: white)
      #v(8pt)
      #metric-card("Total Value", "${CURRENCY} ${TOTAL_VALUE}", tint: blue-soft)
      #v(8pt)
      #metric-card("Timezone", "${TIMEZONE}", tint: sand)
    ],
  )
]

#v(15pt)

#grid(
  columns: (1.2fr, 1fr),
  column-gutter: 14pt,
  [
    #text(size: 8pt, weight: "medium", fill: blue)[ADVISORY FRAME]
    #v(2pt)
    #text(size: 13pt, weight: "bold", fill: navy)[Executive Summary]
    #v(6pt)
    #rect(width: 100%, height: 0.8pt, fill: line)
    #v(8pt)
    #box(
      width: 100%,
      fill: blue-soft,
      stroke: border,
      radius: 8pt,
      inset: 14pt,
    )[
      #text(size: 10.5pt, fill: rgb(42, 61, 79))[${SUMMARY_PARAGRAPH}]
    ]
  ],
  [
    #text(size: 8pt, weight: "medium", fill: blue)[MANDATE]
    #v(2pt)
    #text(size: 13pt, weight: "bold", fill: navy)[Client Mandate Context]
    #v(6pt)
    #rect(width: 100%, height: 0.8pt, fill: line)
    #v(8pt)
    #detail-card("Objective", "${OBJECTIVE}")
    #v(8pt)
    #grid(
      columns: (1fr, 1fr),
      column-gutter: 8pt,
      row-gutter: 8pt,
      [
        #detail-card("Risk Exposure", "${RISK_EXPOSURE}")
      ],
      [
        #detail-card("Booking Center", "${BOOKING_CENTER}")
      ],
      [
        #detail-card("Advisor", "${ADVISOR_ID}")
      ],
      [
        #detail-card("Readiness", "${READINESS_STATUS}")
      ],
    )
  ],
)

#v(15pt)

#text(size: 8pt, weight: "medium", fill: blue)[PORTFOLIO STATE]
#v(2pt)
#text(size: 13pt, weight: "bold", fill: navy)[Portfolio Composition]
#v(6pt)
#rect(width: 100%, height: 0.8pt, fill: line)
#v(10pt)

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
  [
    #metric-card("Invested Value", "${CURRENCY} ${INVESTED_VALUE}", tint: white)
  ],
  [
    #metric-card("Cash Balance", "${CURRENCY} ${CASH_BALANCE}", tint: white)
  ],
  [
    #metric-card("Cash Weight", "${CASH_WEIGHT_PCT}", tint: white)
  ],
)

#v(10pt)

#grid(
  columns: (1fr, 1fr),
  column-gutter: 12pt,
  [
    #box(
      width: 100%,
      fill: sand,
      stroke: border,
      radius: 8pt,
      inset: 12pt,
    )[
      #text(size: 8pt, weight: "medium", fill: blue)[ALLOCATION]
      #v(4pt)
      #text(size: 12pt, weight: "bold", fill: navy)[${ALLOCATION_LARGEST_NAME}]
      #v(8pt)
      #grid(
        columns: (1fr, 1fr, 1fr),
        column-gutter: 8pt,
        [
          #detail-card("Weight", "${ALLOCATION_LARGEST_WEIGHT}")
        ],
        [
          #detail-card("Market Value", "${CURRENCY} ${ALLOCATION_LARGEST_VALUE}")
        ],
        [
          #detail-card("Positions", "${ALLOCATION_POSITION_COUNT}")
        ],
      )
    ]
  ],
  [
    #box(
      width: 100%,
      fill: white,
      stroke: border,
      radius: 8pt,
      inset: 12pt,
    )[
      #text(size: 8pt, weight: "medium", fill: blue)[PERFORMANCE HIGHLIGHT]
      #v(4pt)
      #text(size: 12pt, weight: "bold", fill: navy)[${TOP_CONTRIBUTOR_NAME}]
      #v(8pt)
      #grid(
        columns: (1fr, 1fr),
        column-gutter: 8pt,
        row-gutter: 8pt,
        [
          #detail-card("YTD Contribution", "${TOP_CONTRIBUTOR_VALUE}")
        ],
        [
          #detail-card("Benchmark Status", "${BENCHMARK_STATUS}")
        ],
      )
    ]
  ],
)

#v(15pt)

#grid(
  columns: (1.15fr, 0.95fr),
  column-gutter: 14pt,
  [
    #text(size: 8pt, weight: "medium", fill: blue)[PERFORMANCE]
    #v(2pt)
    #text(size: 13pt, weight: "bold", fill: navy)[Performance Periods]
    #v(6pt)
    #rect(width: 100%, height: 0.8pt, fill: line)
    #v(10pt)
    ${PERFORMANCE_PERIOD_ROWS}
  ],
  [
    #text(size: 8pt, weight: "medium", fill: blue)[RISK]
    #v(2pt)
    #text(size: 13pt, weight: "bold", fill: navy)[Risk Snapshot]
    #v(6pt)
    #rect(width: 100%, height: 0.8pt, fill: line)
    #v(10pt)
    #grid(
      columns: (1fr, 1fr),
      column-gutter: 8pt,
      row-gutter: 8pt,
      [
        #detail-card("Volatility", "${RISK_VOLATILITY}")
      ],
      [
        #detail-card("Beta", "${RISK_BETA}")
      ],
      [
        #detail-card("Tracking Error", "${RISK_TRACKING_ERROR}")
      ],
      [
        #detail-card("Information Ratio", "${RISK_INFORMATION_RATIO}")
      ],
      [
        #detail-card("Value at Risk", "${RISK_VAR}")
      ],
      [
        #detail-card("Review Period", "${REVIEW_PERIOD_LABEL}")
      ],
    )
  ],
)

#v(15pt)

#text(size: 8pt, weight: "medium", fill: blue)[ADVISOR BRIEFING]
#v(2pt)
#text(size: 13pt, weight: "bold", fill: navy)[Review Observations]
#v(6pt)
#rect(width: 100%, height: 0.8pt, fill: line)
#v(10pt)

${OBSERVATION_NOTES}

#v(15pt)

#text(size: 8pt, weight: "medium", fill: blue)[HOLDINGS]
#v(2pt)
#text(size: 13pt, weight: "bold", fill: navy)[Top Governed Holdings]
#v(6pt)
#rect(width: 100%, height: 0.8pt, fill: line)
#v(10pt)

${HOLDING_ROWS}

#v(15pt)

#text(size: 8pt, weight: "medium", fill: blue)[GOVERNANCE]
#v(2pt)
#text(size: 13pt, weight: "bold", fill: navy)[Lineage And Runtime Posture]
#v(6pt)
#rect(width: 100%, height: 0.8pt, fill: line)
#v(10pt)

#grid(
  columns: (1fr, 1fr, 1fr),
  column-gutter: 10pt,
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
    #metric-card("Source Services", "${SOURCE_SERVICES}", tint: white)
  ],
  [
    #metric-card("Completeness", "${COMPLETENESS_STATUS}", tint: white)
  ],
  [
    #metric-card("Data Quality", "${DATA_QUALITY_STATUS}", tint: white)
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
  #text(size: 8.2pt, fill: muted)[Governed output for advisory servicing. Not an archival record.]
]
