#import "_theme.typ": accent, body-muted, body-strong, cover-title, ink, metric-value, mist, page-kicker, rule, section-subtitle, section-title, slate, small-caps, soft-rule
#import "_components.typ": allocation-row, appendix-section, appendix-term, compact-allocation-row, content-item, dense-position-row, dense-transaction-row, holding-row, key-stat, metric-card, note-panel, page-header, performance-bar-row, period-row, review-note, spotlight-panel

#let cover-page() = [
  #align(left)[#rect(width: 58pt, height: 1.4pt, fill: accent)]
  #v(18pt)
  #grid(
    columns: (1.25fr, 0.95fr),
    column-gutter: 30pt,
    [
      #cover-title("Portfolio Review")
      #v(22pt)
      #body-muted("Client")
      #v(2pt)
      #text(size: 17pt, weight: 500, fill: ink)[${CLIENT_NAME}]
      #v(11pt)
      #body-muted("Portfolio")
      #v(2pt)
      #text(size: 14pt, weight: 400, fill: ink)[${PORTFOLIO_NAME}]
      #v(11pt)
      #body-muted("Review period")
      #v(2pt)
      #text(size: 12pt, fill: ink)[1 Jan 2026 - ${AS_OF_DATE}]
      #v(18pt)
      #spotlight-panel(
        "Executive overview",
        "${SUMMARY_PARAGRAPH}",
      )
    ],
    [
      #metric-card("Total portfolio value", "${CURRENCY} ${TOTAL_VALUE}", detail: "Governed market value as of ${AS_OF_DATE}", tone: rgb("#f4f9fd"))
      #v(10pt)
      #metric-card("Invested value", "${CURRENCY} ${INVESTED_VALUE}")
      #v(10pt)
      #metric-card("Cash balance", "${CURRENCY} ${CASH_BALANCE}")
      #v(10pt)
      #metric-card("Cash weight", "${CASH_WEIGHT_PCT}", detail: "Available near-term liquidity")
    ],
  )

  #v(1fr)
  #soft-rule()
  #v(8pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 18pt,
    [
      #small-caps("Prepared for")
      #v(4pt)
      #body-muted("${CLIENT_NAME}")
      #linebreak()
      #body-muted("${PORTFOLIO_NAME}")
    ],
    [
      #align(right)[
        #small-caps("Relationship details")
        #v(4pt)
        #body-muted("Singapore booking center")
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
  #v(18pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 32pt,
    [
      #content-item("1", "Overview", "Client mandate, relationship context, and scope of analysis")
      #v(14pt)
      #content-item("2", "Performance", "Period returns, benchmark comparison, and trailing return profile")
      #v(14pt)
      #content-item("3", "Allocation", "Top exposures, asset mix, and portfolio risk snapshot")
    ],
    [
      #content-item("4", "Observations", "Advisory commentary and portfolio holdings detail")
      #v(14pt)
      #content-item("5", "Transactions", "Compact transaction activity across the review period")
      #v(14pt)
      #content-item("6", "Appendix", "Supporting information and portfolio reference details")
    ],
  )

  #v(22pt)
  #spotlight-panel(
    "Review summary",
    "This report brings together current portfolio positioning, performance, allocation, and relationship commentary as of the stated review date.",
  )
]

#let scope-page() = [
  #page-header("Scope of analysis")
  #v(10pt)
  #grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 10pt,
    [
      #metric-card("Risk posture", "${RISK_EXPOSURE}", detail: "Current mandate classification", tone: white)
    ],
    [
      #metric-card("Review label", "${REVIEW_PERIOD_LABEL}", detail: "Reporting lens", tone: white)
    ],
    [
      #metric-card("Invested value", "${CURRENCY} ${INVESTED_VALUE}", tone: white)
    ],
    [
      #metric-card("Cash balance", "${CURRENCY} ${CASH_BALANCE}", tone: white)
    ],
  )
  #v(14pt)
  #grid(
    columns: (1.25fr, 0.95fr),
    column-gutter: 22pt,
    [
      #section-subtitle("Mandate summary")
      #v(6pt)
      #text(size: 10pt, fill: ink)[${OBJECTIVE}]
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
      #note-panel("Scope of analysis", "This review assesses portfolio positioning, liquidity, relative performance, and risk posture against the current balanced mandate.")
      #v(10pt)
      #note-panel("Largest allocation", "${ALLOCATION_LARGEST_NAME} represents ${ALLOCATION_LARGEST_WEIGHT} of portfolio market value, equal to ${CURRENCY} ${ALLOCATION_LARGEST_VALUE}.")
      #v(10pt)
      #note-panel("Top contributor", "${TOP_CONTRIBUTOR_NAME} contributed ${TOP_CONTRIBUTOR_VALUE} through the current reporting period.")
      #v(10pt)
      #note-panel("Relationship context", "Booking center ${BOOKING_CENTER} under advisor ${ADVISOR_ID}.")
    ],
  )
]

#let performance-page() = [
  #page-header("Performance")
  #v(10pt)
  #grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 12pt,
    [#metric-card("Top contributor", "${TOP_CONTRIBUTOR_NAME}", detail: "${TOP_CONTRIBUTOR_VALUE} contribution", tone: white)],
    [#metric-card("Benchmark status", "${BENCHMARK_STATUS}", detail: "Comparison governance state", tone: white)],
    [#metric-card("Review period", "${REVIEW_PERIOD_LABEL}", detail: "Current management lens", tone: white)],
  )
  #v(14pt)
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
  #block(
    inset: 14pt,
    fill: white,
    stroke: (paint: rgb("#dbe6ef"), thickness: 0.5pt),
    radius: 8pt,
  )[
    ${PERFORMANCE_BAR_ROWS}
  ]

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
  #v(10pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 18pt,
    [
      #section-subtitle("By asset class")
      #v(8pt)
      #grid(
        columns: (1.15fr, 1.15fr, 0.55fr, 0.75fr),
        column-gutter: 8pt,
        [#small-caps("Category")],
        [#small-caps("Proportion")],
        [#align(right)[#small-caps("Weight")]],
        [#align(right)[#small-caps("Value")]],
      )
      #v(4pt)
      #soft-rule()
      #v(8pt)
      #block(
        inset: 10pt,
        fill: white,
        stroke: (paint: rule, thickness: 0.5pt),
        radius: 8pt,
      )[
        ${ASSET_CLASS_ROWS}
      ]
    ],
    [
      #section-subtitle("${SUPPLEMENTAL_ALLOCATION_TITLE}")
      #v(8pt)
      #grid(
        columns: (1.15fr, 1.15fr, 0.55fr, 0.75fr),
        column-gutter: 8pt,
        [#small-caps("Group")],
        [#small-caps("Proportion")],
        [#align(right)[#small-caps("Weight")]],
        [#align(right)[#small-caps("Value")]],
      )
      #v(4pt)
      #soft-rule()
      #v(8pt)
      #block(
        inset: 10pt,
        fill: white,
        stroke: (paint: rule, thickness: 0.5pt),
        radius: 8pt,
      )[
        ${SUPPLEMENTAL_ALLOCATION_ROWS}
      ]
    ],
  )

  #v(14pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 18pt,
    [
      #section-subtitle("Portfolio summary")
      #v(8pt)
      #block(
        inset: 12pt,
        fill: rgb("#f4f9fd"),
        stroke: (paint: rgb("#dbe6ef"), thickness: 0.5pt),
        radius: 8pt,
      )[
        #grid(
          columns: (1fr, 1fr),
          row-gutter: 10pt,
          column-gutter: 12pt,
          [#key-stat("Largest asset class", "${ALLOCATION_LARGEST_NAME}")],
          [#key-stat("Position count", "${ALLOCATION_POSITION_COUNT}")],
          [#key-stat("Largest weight", "${ALLOCATION_LARGEST_WEIGHT}")],
          [#key-stat("Largest value", "${CURRENCY} ${ALLOCATION_LARGEST_VALUE}")],
          [#key-stat("Invested value", "${CURRENCY} ${INVESTED_VALUE}")],
          [#key-stat("Cash balance", "${CURRENCY} ${CASH_BALANCE}")],
        )
      ]
    ],
    [
      #section-subtitle("Risk snapshot")
      #v(8pt)
      #grid(
        columns: (1fr, 1fr),
        row-gutter: 10pt,
        column-gutter: 12pt,
        [#note-panel("Volatility", "${RISK_VOLATILITY}")],
        [#note-panel("Beta", "${RISK_BETA}")],
        [#note-panel("Tracking error", "${RISK_TRACKING_ERROR}")],
        [#note-panel("Information ratio", "${RISK_INFORMATION_RATIO}")],
        [#note-panel("Value at risk", "${RISK_VAR}")],
        [#note-panel("Review label", "${REVIEW_PERIOD_LABEL}")],
      )
    ],
  )
]

#let observations-page() = [
  #page-header("Detailed positions")
  #v(6pt)
  #grid(
    columns: (1.25fr, 0.95fr),
    column-gutter: 18pt,
    [
      #section-subtitle("Position commentary")
      #v(6pt)
      ${OBSERVATION_NOTES}
    ],
    [
      #note-panel("Position view", "Detailed positions are shown in compact statement form to improve scan speed across holdings, weight, valuation, and contribution.")
      #v(10pt)
      #note-panel("Review context", "Figures are presented in ${CURRENCY} as of ${AS_OF_DATE}.")
    ],
  )

  #v(14pt)
  #section-subtitle("Positions")
  #v(6pt)
  #grid(
    columns: (1.05fr, 2.2fr, 0.6fr, 0.95fr, 0.85fr, 0.75fr),
    column-gutter: 8pt,
    [#small-caps("Category")],
    [#small-caps("Description")],
    [#align(right)[#small-caps("Weight")]],
    [#align(right)[#small-caps("Market value")]],
    [#align(right)[#small-caps("Unrealized")]],
    [#align(right)[#small-caps("YTD")]],
  )
  #v(3pt)
  #soft-rule()
  #v(6pt)
  ${DENSE_POSITION_ROWS}
]

#let transactions-page() = [
  #page-header("Transaction list")
  #v(4pt)
  #text(size: 9pt, fill: accent)[${TRANSACTION_PERIOD_LABEL}]
  #v(10pt)
  #grid(
    columns: (1.15fr, 0.85fr),
    column-gutter: 16pt,
    [
      #section-subtitle("Transactions by date")
    ],
    [
      #align(right)[
        #body-muted("Valued in ${CURRENCY}")
      ]
    ],
  )
  #v(6pt)
  #grid(
    columns: (0.85fr, 0.95fr, 0.9fr, 2.2fr, 0.95fr, 0.9fr, 0.95fr),
    column-gutter: 8pt,
    [#small-caps("Trade date")],
    [#small-caps("Booking text")],
    [#align(right)[#small-caps("Number/Amount")]],
    [#small-caps("Description")],
    [#align(right)[#small-caps("Price")]],
    [#align(right)[#small-caps("Gain/Loss")]],
    [#align(right)[#small-caps("Transaction value")]],
  )
  #v(3pt)
  #soft-rule()
  #v(6pt)
  ${DENSE_TRANSACTION_ROWS}
]

#let appendix-page() = [
  #page-header("Abbreviations and explanations")
  #v(8pt)
  #appendix-section(
    "Portfolio review",
    [
      #appendix-term("Risk posture", "The risk posture reflects the agreed mandate and indicates the level of market risk the portfolio is positioned to accept over time.")
      #v(8pt)
      #appendix-term("Expected return", "Expected return is an indicative long-term outcome derived from a combination of historical experience, current positioning, and capital market assumptions.")
      #v(8pt)
      #appendix-term("Volatility", "Volatility measures how widely returns may vary over time and should be read as an indicator of short-term fluctuation rather than a permanent loss expectation.")
    ],
    [
      #appendix-term("Maximum drawdown", "Maximum drawdown describes the largest historical peak-to-trough decline observed over a given period and provides a useful stress reference for portfolio behaviour.")
      #v(8pt)
      #appendix-term("Information ratio", "Information ratio compares excess return to active risk and helps assess whether benchmark-relative decisions were rewarded efficiently.")
      #v(8pt)
      #appendix-term("Tracking error", "Tracking error measures the degree to which portfolio returns differ from benchmark returns across time.")
    ],
    [
      #appendix-term("Value at risk", "Value at risk is an indicative downside estimate based on recent portfolio behaviour and should be treated as directional rather than predictive.")
      #v(8pt)
      #appendix-term("Data sources", "This review draws on portfolio, performance, and risk figures from ${SOURCE_SERVICES}.")
      #v(8pt)
      #appendix-term("Review status", "Current review readiness is ${READINESS_STATUS}, with completeness assessed as ${COMPLETENESS_STATUS} and data quality assessed as ${DATA_QUALITY_STATUS}.")
    ],
  )

  #v(16pt)
  #appendix-section(
    "Detailed positions",
    [
      #appendix-term("Market value", "Market value reflects the latest available valuation in ${CURRENCY} as of ${AS_OF_DATE}.")
      #v(8pt)
      #appendix-term("Unrealized P/L", "Unrealized profit or loss compares current market value to the average cost basis of the position.")
      #v(8pt)
      #appendix-term("YTD contribution", "Year-to-date contribution shows the estimated contribution of a position to portfolio return over the current reporting period.")
    ],
    [
      #appendix-term("Category", "Category identifies the primary asset class or exposure bucket used for internal portfolio grouping and review.")
      #v(8pt)
      #appendix-term("Weight", "Weight expresses the position size as a share of total portfolio market value.")
      #v(8pt)
      #appendix-term("Position detail", "Position rows are presented in a compact statement format to improve readability where portfolios hold multiple instruments.")
    ],
    [
      #appendix-term("Booking center", "Booking center for this relationship is ${BOOKING_CENTER}.")
      #v(8pt)
      #appendix-term("Advisor", "Relationship coverage is provided by advisor ${ADVISOR_ID}.")
      #v(8pt)
      #appendix-term("Review date", "All figures in this report are presented with an as-of date of ${AS_OF_DATE}.")
    ],
  )

  #v(16pt)
  #appendix-section(
    "Transaction list",
    [
      #appendix-term("Content", "The transaction list summarizes booking activity captured during ${TRANSACTION_PERIOD_LABEL}.")
      #v(8pt)
      #appendix-term("Booking text", "Booking text identifies the transaction type, such as purchase, sale, coupon, or other income event.")
      #v(8pt)
      #appendix-term("Number/Amount", "Number or amount reflects the principal cash movement or transaction amount recorded for the booking.")
    ],
    [
      #appendix-term("Transaction price", "Transaction price reflects the execution price, net asset value, or internal valuation reference available for the booking.")
      #v(8pt)
      #appendix-term("Gain/Loss", "Gain or loss shows the realized or transaction-related economic effect associated with the booking where available.")
      #v(8pt)
      #appendix-term("Transaction value", "Transaction value presents the booked amount in reporting currency.")
    ],
    [
      #appendix-term("Pending activity", "Recent activity may still be subject to settlement timing, pricing completion, or final booking confirmation.")
      #v(8pt)
      #appendix-term("Currency basis", "Transactions are displayed in reporting currency ${CURRENCY} unless otherwise noted in the booking description.")
      #v(8pt)
      #appendix-term("Statement usage", "Transaction views are intended to support review, reconciliation discussion, and advisory follow-up.")
    ],
  )
]
