#import "_theme.typ": accent, body-muted, cover-title, empty-state, hairline, ink, mist, panel-radius, rule, section-title, slate, small-caps, soft-rule, text-body-strong, text-caption, text-head, text-lead, text-page-title
#import "_components.typ": brand-block, content-row, metric-card, section-lead

#let cover-fact(label, value) = [
  #small-caps(label)
  #v(3pt)
  #text(size: text-body-strong, weight: 600, fill: ink)[#value]
]

#let cover-page() = [
  #grid(
    columns: (1.18fr, 0.82fr),
    column-gutter: 34pt,
    [
      // The classification eyebrow: presentation furniture for the
      // private_banking brand variant this document is rendered for.
      #v(4pt)
      #text(size: text-caption, weight: 700, tracking: 1.4pt, fill: accent)[CLIENT REPORT]
      #text(size: text-caption, weight: 600, tracking: 1.4pt, fill: slate)[#h(6pt)\/#h(6pt)PRIVATE & CONFIDENTIAL]
      #v(14pt)
      // The title block sits beside a strong vertical accent bar -- the
      // cover's one gesture, the way every content page carries its tick.
      #grid(
        columns: (4pt, 1fr),
        column-gutter: 16pt,
        [#pdf.artifact(rect(width: 3pt, height: 118pt, fill: accent))],
        [
          #cover-title("Portfolio Review")
          #v(10pt)
          #text(size: text-lead, fill: ink)[#"${REVIEW_PERIOD_RANGE}"]
          #v(8pt)
          #text(size: text-head, weight: 600, fill: ink)[#"${CLIENT_NAME}"]
          #linebreak()
          #text(size: text-body-strong, fill: slate)[#"${PORTFOLIO_NAME}"]
        ],
      )
      #v(18pt)
      #section-lead("Executive overview", "${SUMMARY_PARAGRAPH}")
    ],
    [
      // The side panel: the cover's headline facts, set apart on their own
      // quiet ground the way the gold standard reserves its right rail.
      #block(fill: mist, inset: 16pt, radius: 3pt, width: 100%)[
        #brand-block()
        #v(14pt)
        #if "${HAS_TOTAL_VALUE}" == "yes" [
          // The document's one headline figure at display size -- the third
          // benchmark's hero number, kept inside the governed card frame.
          #block(
            width: 100%,
            fill: white,
            inset: 12pt,
            radius: (bottom: panel-radius),
            stroke: (
              top: (paint: accent, thickness: 2.2pt),
              bottom: (paint: rule, thickness: hairline),
              left: (paint: rule, thickness: hairline),
              right: (paint: rule, thickness: hairline),
            ),
          )[
            #small-caps("Total portfolio value")
            #v(5pt)
            #text(size: text-page-title, weight: 300, fill: ink)[#"${CURRENCY} ${TOTAL_VALUE}"]
            #v(4pt)
            #body-muted("Market value as of ${AS_OF_DATE}")
          ]
        ] else [
          #metric-card("Total portfolio value", "${CURRENCY} ${TOTAL_VALUE}", detail: "Market value as of ${AS_OF_DATE}", tone: white)
        ]
        #v(9pt)
        #metric-card("Invested value", "${CURRENCY} ${INVESTED_VALUE}", tone: white)
        #v(9pt)
        #metric-card("Cash balance", "${CURRENCY} ${CASH_BALANCE}", tone: white)
        #v(9pt)
        #metric-card("Cash weight", "${CASH_WEIGHT_PCT}", detail: "Available near-term liquidity", tone: white)
      ]
    ],
  )

  #v(1fr)
  // The key-facts strip: the report's own registration line, over a heavy
  // rule -- what this document is, as of when, in what currency, by whom.
  #block(width: 100%)[
    #line(length: 100%, stroke: (paint: ink, thickness: 1.1pt))
    #v(8pt)
    #grid(
      columns: (1fr, 1fr, 1fr, 1fr),
      column-gutter: 18pt,
      cover-fact("Report date", "${AS_OF_DATE}"),
      cover-fact("Reporting currency", "${CURRENCY}"),
      cover-fact("Report type", "Portfolio review"),
      cover-fact("Advisor", "${ADVISOR_ID}"),
    )
  ]
  #v(10pt)
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
    let starts = entries.map(entry => counter(page).at(entry.location()).first())
    let final = counter(page).final().first()
    // A section's range runs to the page before the next section starts -- the
    // same marker arithmetic that places the start, so the range cannot lie.
    let page-ref(index) = {
      let start = starts.at(index)
      let end = if index + 1 < starts.len() { starts.at(index + 1) - 1 } else { final }
      if end <= start { "p. " + str(start) } else { "pp. " + str(start) + "-" + str(end) }
    }
    let half = int(calc.ceil(entries.len() / 2))
    let column(slice) = {
      for (offset, entry) in slice {
        content-row(
          str(offset + 1),
          entry.value.title,
          entry.value.detail,
          page-ref(offset),
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
  #if "${HAS_AT_A_GLANCE}" == "yes" [
    #grid(
      columns: (1.4fr, 0.6fr),
      column-gutter: 18pt,
      [
        #section-lead(
          "Review summary",
          "This report brings together current portfolio positioning, performance, allocation, positions, and transaction activity as of the stated review date.",
        )
      ],
      [
        // The reader's landing figures, stated only where supplied -- the
        // third benchmark's "at a glance" rail, built from governed scalars.
        #block(
          width: 100%,
          fill: mist,
          inset: 12pt,
          radius: (bottom: panel-radius),
          stroke: (
            top: (paint: accent, thickness: 2.2pt),
            bottom: (paint: rule, thickness: hairline),
            left: (paint: rule, thickness: hairline),
            right: (paint: rule, thickness: hairline),
          ),
        )[
          #small-caps("At a glance")
          #if "${HAS_TOTAL_VALUE}" == "yes" [
            #v(7pt)
            #body-muted("Total portfolio value")
            #linebreak()
            #text(size: text-lead, weight: 600, fill: ink)[#"${CURRENCY} ${TOTAL_VALUE}"]
          ]
          #if "${HAS_GLANCE_VOLATILITY}" == "yes" [
            #v(7pt)
            #body-muted("Expected volatility")
            #linebreak()
            #text(size: text-lead, weight: 600, fill: ink)[#"${RISK_VOLATILITY}"]
          ]
          #if "${HAS_GLANCE_RISK_POSTURE}" == "yes" [
            #v(7pt)
            #body-muted("Risk posture")
            #linebreak()
            #text(size: text-lead, weight: 600, fill: ink)[#"${RISK_EXPOSURE}"]
          ]
        ]
      ],
    )
  ] else [
    #section-lead(
      "Review summary",
      "This report brings together current portfolio positioning, performance, allocation, positions, and transaction activity as of the stated review date.",
    )
  ]
]
