#import "_theme.typ": accent, body-muted, cover-title, grid-gap, ink, mist, navy, section-title, small-caps, soft-rule
#import "_components.typ": content-row, metric-card, report-panel, section-lead, spotlight-panel

#let cover-page() = [
  #align(left)[#rect(width: 58pt, height: 1.4pt, fill: accent)]
  #v(16pt)
  #grid(
    columns: (1.22fr, 0.98fr),
    column-gutter: 30pt,
    [
      #cover-title("Portfolio Review")
      #v(18pt)
      #report-panel([
        #grid(
          columns: (0.9fr, 1.4fr),
          row-gutter: 8pt,
          column-gutter: grid-gap,
          [#small-caps("Client")],
          [#text(size: 13pt, weight: 600, fill: ink)[${CLIENT_NAME}]],
          [#small-caps("Portfolio")],
          [#text(size: 11pt, weight: 500, fill: ink)[${PORTFOLIO_NAME}]],
          [#small-caps("Review period")],
          [#text(size: 9.5pt, fill: ink)[1 Jan 2026 - ${AS_OF_DATE}]],
          [#small-caps("Reporting currency")],
          [#text(size: 9.5pt, fill: ink)[${CURRENCY}]],
        )
      ])
      #v(13pt)
      #section-lead("Executive overview", "${SUMMARY_PARAGRAPH}")
    ],
    [
      #metric-card("Total portfolio value", "${CURRENCY} ${TOTAL_VALUE}", detail: "Market value as of ${AS_OF_DATE}", tone: mist)
      #v(10pt)
      #metric-card("Invested value", "${CURRENCY} ${INVESTED_VALUE}", tone: white)
      #v(10pt)
      #metric-card("Cash balance", "${CURRENCY} ${CASH_BALANCE}", tone: white)
      #v(10pt)
      #metric-card("Cash weight", "${CASH_WEIGHT_PCT}", detail: "Available near-term liquidity", tone: white)
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
  #v(7pt)
  #soft-rule()
  #v(15pt)
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 32pt,
    [
      #content-row("1", "Overview", "Mandate, relationship context, and scope of analysis", "p. 3")
      #v(9pt)
      #content-row("2", "Performance", "Period returns, benchmark comparison, and return history", "p. 4")
      #v(9pt)
      #content-row("3", "Asset allocation", "Asset mix, exposure detail, and risk profile", "p. 7")
    ],
    [
      #content-row("4", "Detailed positions", "Statement-style holdings detail and position-level performance", "p. 9")
      #v(9pt)
      #content-row("5", "Transactions", "Transaction activity across the review period", "p. 10")
      #v(9pt)
      #content-row("6", "Appendix", "Definitions and explanatory notes", "p. 11")
    ],
  )

  #v(22pt)
  #section-lead(
    "Review summary",
    "This report brings together current portfolio positioning, performance, allocation, positions, and transaction activity as of the stated review date.",
  )
]
