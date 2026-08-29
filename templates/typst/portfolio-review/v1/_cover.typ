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
          [#text(size: 13pt, weight: 600, fill: ink)[#"${CLIENT_NAME}"]],
          [#small-caps("Portfolio")],
          [#text(size: 11pt, weight: 500, fill: ink)[#"${PORTFOLIO_NAME}"]],
          [#small-caps("Review period")],
          [#text(size: 9.5pt, fill: ink)[1 Jan 2026 - #"${AS_OF_DATE}"]],
          [#small-caps("Reporting currency")],
          [#text(size: 9.5pt, fill: ink)[#"${CURRENCY}"]],
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
  // Computed from the sections this document actually contains, in the order they were
  // emitted. These were string literals, and they were already wrong in any document
  // carrying an advisory section: that section shifts every page after it, so a
  // 17-page render still claimed the appendix began on p. 11.
  #context {
    let entries = query(<lotus-section>)
    let half = int(calc.ceil(entries.len() / 2))
    let column(slice) = {
      for (offset, entry) in slice {
        content-row(
          str(offset + 1),
          entry.value.title,
          entry.value.detail,
          "p. " + str(counter(page).at(entry.location()).first()),
        )
        v(9pt)
      }
    }
    grid(
      columns: (1fr, 1fr),
      column-gutter: 32pt,
      column(entries.enumerate().slice(0, half)),
      column(entries.enumerate().slice(half)),
    )
  }

  #v(22pt)
  #section-lead(
    "Review summary",
    "This report brings together current portfolio positioning, performance, allocation, positions, and transaction activity as of the stated review date.",
  )
]
