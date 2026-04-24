#import "_theme.typ": accent, body-muted, cover-title, ink, small-caps, soft-rule
#import "_components.typ": content-item, metric-card, spotlight-panel

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
      #spotlight-panel("Executive overview", "${SUMMARY_PARAGRAPH}")
    ],
    [
      #metric-card("Total portfolio value", "${CURRENCY} ${TOTAL_VALUE}", detail: "Market value as of ${AS_OF_DATE}", tone: rgb("#f4f9fd"))
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
  #text(size: 17.2pt, weight: 300, fill: ink)[Contents]
  #v(18pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 32pt,
    [
      #content-item("1", "Overview", "Mandate, relationship context, and scope of analysis")
      #v(14pt)
      #content-item("2", "Performance", "Period returns, benchmark comparison, and trailing return profile")
      #v(14pt)
      #content-item("3", "Allocation", "Asset mix, exposure detail, and risk profile")
    ],
    [
      #content-item("4", "Detailed positions", "Statement-style holdings detail and position-level performance")
      #v(14pt)
      #content-item("5", "Transactions", "Transaction activity across the review period")
      #v(14pt)
      #content-item("6", "Appendix", "Definitions and explanatory notes")
    ],
  )

  #v(22pt)
  #spotlight-panel(
    "Review summary",
    "This report brings together current portfolio positioning, performance, allocation, positions, and transaction activity as of the stated review date.",
  )
]
