#import "_theme.typ": accent, accent-soft, body-muted, cover-title, empty-state, grid-gap, ink, mist, section-title, slate, small-caps, soft-rule, text-body-strong, text-caption, text-head, text-lead
#import "_components.typ": content-row, metric-card, report-panel, section-lead

#let cover-page() = [
  #align(left)[#pdf.artifact(rect(width: 58pt, height: 1.4pt, fill: accent))]
  #v(10pt)
  // The brand variant this document was rendered for, stated as the cover's
  // wordmark -- a supported_brand_variants fact, not decoration.
  #text(size: text-caption, weight: 600, tracking: 1.6pt, fill: slate)[PRIVATE BANKING]
  #v(14pt)
  #grid(
    columns: (1.22fr, 0.98fr),
    column-gutter: 30pt,
    [
      #cover-title("Portfolio Review")
      #v(6pt)
      #body-muted("${REVIEW_PERIOD_RANGE} · Reporting currency ${CURRENCY}")
      #v(16pt)
      #report-panel([
        #grid(
          columns: (0.9fr, 1.4fr),
          row-gutter: 8pt,
          column-gutter: grid-gap,
          [#small-caps("Client")],
          [#text(size: text-head, weight: 600, fill: ink)[#"${CLIENT_NAME}"]],
          [#small-caps("Portfolio")],
          [#text(size: text-lead, weight: 500, fill: ink)[#"${PORTFOLIO_NAME}"]],
          [#small-caps("Review period")],
          [#text(size: text-body-strong, fill: ink)[#"${REVIEW_PERIOD_RANGE}"]],
          [#small-caps("Reporting currency")],
          [#text(size: text-body-strong, fill: ink)[#"${CURRENCY}"]],
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
  // A quiet closing motif in the document's own palette; marked as an artifact
  // so assistive technology skips what a reader's eye merely rests on.
  #align(right)[#pdf.artifact(box[
    #place(right + bottom, dx: -60pt, circle(radius: 26pt, fill: mist))
    #place(right + bottom, dx: -22pt, dy: -10pt, circle(radius: 17pt, stroke: (paint: accent-soft, thickness: 1.1pt)))
    #place(right + bottom, circle(radius: 8pt, fill: accent))
    #box(width: 130pt, height: 54pt)
  ])]
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
