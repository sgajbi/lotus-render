#import "_theme.typ": accent, body-muted, cover-title, ink, slate, section-subtitle, section-title, small-caps, soft-rule
#import "_components.typ": allocation-row, holding-row, key-stat, note-panel, page-header, performance-bar-row, period-row, review-note

#let cover-page() = [
  #align(left)[#rect(width: 52pt, height: 1.2pt, fill: accent)]
  #v(16pt)
  #cover-title("Portfolio Review")
  #v(6pt)
  #text(size: 11pt, fill: slate)[Private Banking Portfolio Review]

  #v(20pt)
  #grid(
    columns: (1.2fr, 1fr),
    column-gutter: 26pt,
    [
      #body-muted("Client")
      #v(2pt)
      #text(size: 16pt, weight: 500, fill: ink)[${CLIENT_NAME}]
      #v(9pt)
      #body-muted("Portfolio")
      #v(2pt)
      #text(size: 14pt, weight: 400, fill: ink)[${PORTFOLIO_NAME}]
      #v(9pt)
      #body-muted("Review period")
      #v(2pt)
      #text(size: 12pt, fill: ink)[1 Jan 2026 - ${AS_OF_DATE}]
      #v(9pt)
      #body-muted("Executive overview")
      #v(4pt)
      #text(size: 10.5pt, fill: ink)[${SUMMARY_PARAGRAPH}]
    ],
    [
      #block(
        inset: 16pt,
        fill: rgb("#f3f8fc"),
        stroke: (paint: rgb("#dbe6ef"), thickness: 0.5pt),
        radius: 7pt,
      )[
        #small-caps("Portfolio metrics")
        #v(9pt)
        #key-stat("Total portfolio value", "${CURRENCY} ${TOTAL_VALUE}")
        #v(12pt)
        #key-stat("Invested value", "${CURRENCY} ${INVESTED_VALUE}")
        #v(12pt)
        #key-stat("Cash balance", "${CURRENCY} ${CASH_BALANCE}")
        #v(12pt)
        #key-stat("Cash weight", "${CASH_WEIGHT_PCT}")
      ]
    ],
  )

  #v(1fr)
  #soft-rule()
  #v(8pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 18pt,
    [
      #small-caps("Governance")
      #v(4pt)
      #body-muted("Template ${TEMPLATE_ID} ${TEMPLATE_VERSION}")
      #linebreak()
      #body-muted("Requested by ${REQUESTED_BY}")
      #linebreak()
      #body-muted("Trace ${TRACE_ID}")
    ],
    [
      #align(right)[
        #small-caps("Lotus Render")
        #v(4pt)
        #body-muted("Singapore booking center ${BOOKING_CENTER}")
        #linebreak()
        #body-muted("Advisor ${ADVISOR_ID}")
        #linebreak()
        #body-muted("${TIMEZONE}")
      ]
    ],
  )
]

#let contents-page() = [
  #section-title("Contents")
  #v(14pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 28pt,
    [
      #grid(
        columns: (18pt, 1fr),
        row-gutter: 12pt,
        [#text(size: 20pt, weight: 300, fill: accent)[1]],
        [#text(weight: 500, fill: ink)[Overview] #linebreak() #body-muted("Client mandate and scope of analysis")],
        [#text(size: 20pt, weight: 300, fill: accent)[2]],
        [#text(weight: 500, fill: ink)[Performance] #linebreak() #body-muted("Period return summary and review bars")],
        [#text(size: 20pt, weight: 300, fill: accent)[3]],
        [#text(weight: 500, fill: ink)[Allocation] #linebreak() #body-muted("Top holdings, risk posture, and portfolio mix")],
      )
    ],
    [
      #grid(
        columns: (18pt, 1fr),
        row-gutter: 12pt,
        [#text(size: 20pt, weight: 300, fill: accent)[4]],
        [#text(weight: 500, fill: ink)[Observations] #linebreak() #body-muted("Advisory review commentary")],
        [#text(size: 20pt, weight: 300, fill: accent)[5]],
        [#text(weight: 500, fill: ink)[Appendix] #linebreak() #body-muted("Governance, lineage, and runtime evidence")],
      )
    ],
  )

  #v(16pt)
  #soft-rule()
  #v(10pt)
  #body-muted("This report is generated from governed render packages and deterministic Lotus render templates.")
]

#let scope-page() = [
  #page-header("Scope of analysis")
  #grid(
    columns: (1.2fr, 0.9fr),
    column-gutter: 20pt,
    [
      #section-subtitle("Mandate summary")
      #v(6pt)
      #text(size: 10pt, fill: ink)[${OBJECTIVE}]
      #v(12pt)
      #grid(
        columns: (1fr, 1fr),
        column-gutter: 14pt,
        [#key-stat("Risk exposure", "${RISK_EXPOSURE}")],
        [#key-stat("Review label", "${REVIEW_PERIOD_LABEL}")],
      )
      #v(12pt)
      #soft-rule()
      #v(8pt)
      #grid(
        columns: (1.2fr, 0.8fr, 0.8fr),
        column-gutter: 10pt,
        [#small-caps("Portfolio")],
        [#align(right)[#small-caps("Weight")]],
        [#align(right)[#small-caps("Value")]],
      )
      #v(4pt)
      #soft-rule()
      #v(8pt)
      ${HOLDING_BAR_ROWS}
    ],
    [
      #note-panel("Scope of analysis", "This review assesses portfolio positioning, liquidity, relative performance, and risk posture against the governed balanced mandate.")
      #v(10pt)
      #note-panel("Largest allocation", "${ALLOCATION_LARGEST_NAME} represents ${ALLOCATION_LARGEST_WEIGHT} of portfolio market value, equal to ${CURRENCY} ${ALLOCATION_LARGEST_VALUE}.")
      #v(10pt)
      #note-panel("Top contributor", "${TOP_CONTRIBUTOR_NAME} contributed ${TOP_CONTRIBUTOR_VALUE} through the current reporting period.")
    ],
  )
]

#let performance-page() = [
  #page-header("Performance")
  #section-subtitle("Period return summary")
  #v(7pt)
  #grid(
    columns: (0.9fr, 1fr, 1fr, 1fr),
    column-gutter: 12pt,
    [#small-caps("Period")],
    [#align(right)[#small-caps("Portfolio")]],
    [#align(right)[#small-caps("Benchmark")]],
    [#align(right)[#small-caps("Relative")]],
  )
  #v(4pt)
  #soft-rule()
  #v(8pt)
  ${PERFORMANCE_PERIOD_ROWS}

  #v(16pt)
  #section-subtitle("Trailing performance profile")
  #v(8pt)
  ${PERFORMANCE_BAR_ROWS}

  #v(16pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 18pt,
    [#note-panel("Benchmark status", "${BENCHMARK_STATUS}")],
    [#note-panel("Largest positive contributor", "${TOP_CONTRIBUTOR_NAME} remained the strongest positive performance driver.")],
  )
]

#let allocation-page() = [
  #page-header("Asset allocation")
  #grid(
    columns: (1.2fr, 0.9fr),
    column-gutter: 20pt,
    [
      #section-subtitle("Allocation by top governed holdings")
      #v(8pt)
      #grid(
        columns: (1.3fr, 2fr, 0.7fr, 0.8fr),
        column-gutter: 10pt,
        [#small-caps("Holding")],
        [#small-caps("Exposure")],
        [#align(right)[#small-caps("Weight")]],
        [#align(right)[#small-caps("Value")]],
      )
      #v(4pt)
      #soft-rule()
      #v(8pt)
      ${HOLDING_BAR_ROWS}
    ],
    [
      #section-subtitle("Portfolio mix")
      #v(8pt)
      #block(
        inset: 12pt,
        fill: rgb("#f3f8fc"),
        stroke: (paint: rgb("#dbe6ef"), thickness: 0.5pt),
        radius: 6pt,
      )[
        #grid(
          columns: (1fr, 1fr),
          row-gutter: 10pt,
          column-gutter: 12pt,
          [#key-stat("Largest asset class", "${ALLOCATION_LARGEST_NAME}")],
          [#key-stat("Position count", "${ALLOCATION_POSITION_COUNT}")],
          [#key-stat("Largest weight", "${ALLOCATION_LARGEST_WEIGHT}")],
          [#key-stat("Largest value", "${CURRENCY} ${ALLOCATION_LARGEST_VALUE}")],
        )
      ]
      #v(12pt)
      #section-subtitle("Risk snapshot")
      #v(6pt)
      #grid(
        columns: (1fr, 1fr),
        row-gutter: 10pt,
        column-gutter: 12pt,
        [#note-panel("Volatility", "${RISK_VOLATILITY}")],
        [#note-panel("Beta", "${RISK_BETA}")],
        [#note-panel("Tracking error", "${RISK_TRACKING_ERROR}")],
        [#note-panel("Information ratio", "${RISK_INFORMATION_RATIO}")],
        [#note-panel("Value at risk", "${RISK_VAR}")],
        [#note-panel("Cash balance", "${CURRENCY} ${CASH_BALANCE}")],
      )
    ],
  )
]

#let observations-page() = [
  #page-header("Review observations")
  #section-subtitle("Relationship manager commentary")
  #v(8pt)
  ${OBSERVATION_NOTES}

  #v(16pt)
  #section-subtitle("Governed top holdings detail")
  #v(7pt)
  #grid(
    columns: (2.1fr, 1.1fr, 0.8fr, 1fr, 1fr, 0.9fr),
    column-gutter: 10pt,
    [#small-caps("Holding")],
    [#small-caps("Asset class")],
    [#align(right)[#small-caps("Weight")]],
    [#align(right)[#small-caps("Value")]],
    [#align(right)[#small-caps("PnL")]],
    [#align(right)[#small-caps("Contribution")]],
  )
  #v(4pt)
  #soft-rule()
  #v(8pt)
  ${HOLDING_ROWS}
]

#let appendix-page() = [
  #page-header("Appendix")
  #section-subtitle("Governance and lineage")
  #v(8pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 18pt,
    [
      #note-panel("Source services", "${SOURCE_SERVICES}")
      #v(10pt)
      #note-panel("Completeness", "${COMPLETENESS_STATUS}")
      #v(10pt)
      #note-panel("Data quality", "${DATA_QUALITY_STATUS}")
    ],
    [
      #note-panel("Render readiness", "${READINESS_STATUS}")
      #v(10pt)
      #note-panel("Render job", "${RENDER_JOB_ID}")
      #v(10pt)
      #note-panel("Determinism posture", "${DETERMINISM_STATEMENT}")
    ],
  )

  #v(14pt)
  #soft-rule()
  #v(8pt)
  #body-muted("Correlation ID ${CORRELATION_ID}")
  #linebreak()
  #body-muted("Trace ID ${TRACE_ID}")
]
