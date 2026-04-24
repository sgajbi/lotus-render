#import "_theme.typ": ink, section-subtitle, small-caps, soft-rule
#import "_components.typ": allocation-row, metric-card, note-panel, page-header

#let scope-page() = [
  #page-header("Scope of analysis")
  #v(10pt)
  #grid(
    columns: (1fr, 1fr, 1fr, 1fr),
    column-gutter: 10pt,
    [#metric-card("Risk posture", "${RISK_EXPOSURE}", detail: "Mandate classification", tone: white)],
    [#metric-card("Review period", "${REVIEW_PERIOD_LABEL}", detail: "Reporting period", tone: white)],
    [#metric-card("Invested value", "${CURRENCY} ${INVESTED_VALUE}", tone: white)],
    [#metric-card("Cash balance", "${CURRENCY} ${CASH_BALANCE}", tone: white)],
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
