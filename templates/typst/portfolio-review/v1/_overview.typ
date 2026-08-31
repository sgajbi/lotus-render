#import "_theme.typ": empty-state, section-subtitle, small-caps, soft-rule
#import "_components.typ": allocation-row, metric-card, note-panel, report-panel, review-note, section-lead, section-marker

#let scope-page() = [
  #section-marker("Overview", "Mandate, relationship context, and scope of analysis", header: "Scope of analysis")
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
      #section-lead("Mandate summary", "${OBJECTIVE}")
      #v(12pt)
      #report-panel([
        #section-subtitle("Portfolio scope")
        #v(7pt)
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
      ])
    ],
    [
      #note-panel("Scope of analysis", "This review assesses portfolio positioning, liquidity, relative performance, and risk posture against the current mandate.")
      #v(10pt)
      #note-panel("Largest allocation", "${ALLOCATION_LARGEST_NAME} represents ${ALLOCATION_LARGEST_WEIGHT} of portfolio market value, equal to ${CURRENCY} ${ALLOCATION_LARGEST_VALUE}.")
      #v(10pt)
      #note-panel("Top contributor", "${TOP_CONTRIBUTOR_NAME} contributed ${TOP_CONTRIBUTOR_VALUE} through the current reporting period.")
      #v(10pt)
      #note-panel("Relationship context", "Booking center ${BOOKING_CENTER} under advisor ${ADVISOR_ID}.")
    ],
  )

  // What the review found, in the reviewer's own words. The package cannot be accepted
  // without at least one of these, and the service has built the markup for them on
  // every render since April while no template drew it.
  #v(16pt)
  #block(sticky: true, width: 100%)[
    #section-subtitle("Review observations")
    #v(5pt)
    #soft-rule()
  ]
  #v(9pt)
  ${OBSERVATION_NOTES}
]
