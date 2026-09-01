#import "_theme.typ": TONE_PALETTE, accent, empty-state, ink, mist, navy, rule, slate, text-body, text-body-strong, text-caption, text-fine, text-lead, text-micro, text-small
#import "_components.typ": report-panel, section-lead, section-marker

#let advisory-fact-row(label, value) = [
  #grid(
    columns: (0.42fr, 0.58fr),
    column-gutter: 9pt,
    [#text(size: text-caption, fill: slate)[#label]],
    [#text(size: text-caption, weight: 520, fill: ink)[#value]],
  )
  #v(3pt)
]

#let advisory-narrative-block(title, body) = report-panel([
  #text(size: text-body-strong, weight: 650, fill: navy)[#title]
  #v(5pt)
  #set par(justify: true, leading: 0.94em)
  #text(size: text-small, fill: ink)[#body]
], inset: 10pt)

#let advisory-disclosure-block(disclosure-id, body) = [
  #text(size: text-caption, weight: 650, fill: ink)[#disclosure-id]
  #linebreak()
  #set par(justify: true, leading: 0.82em)
  #text(size: text-caption, fill: slate)[#body]
]

// The first sentence names where this page's content came from; the second states what
// Render does with it and is the same everywhere. Only the first differs, and reusing the
// narrative panel verbatim told a reader that AI-assisted commentary came from
// lotus-advise.
#let advisory-boundary-panel(provenance) = block(
  inset: 10pt,
  fill: mist,
  stroke: (paint: rule, thickness: 0.45pt),
  radius: 4pt,
)[
  #text(size: text-fine, weight: 700, fill: accent)[Advisor-use boundary]
  #v(4pt)
  #set par(justify: true, leading: 0.86em)
  #text(size: text-fine, fill: ink)[
    #provenance lotus-render does not approve, rewrite, infer, or source additional advice
    facts; it renders only the bounded package carried in the render request.
  ]
]

// One governed talking point. The tone marker is a word as well as a colour, because
// these documents are printed and a colour-only encoding says nothing in monochrome.
#let commentary-point(headline, detail, tone, evidence) = block(
  breakable: false,
  width: 100%,
  below: 9pt,
  // A left rule rather than a rect in a grid column. `height: 100%` on that rect
  // resolved against the page, so every talking point took a page of its own -- six
  // pages for one section, one of them holding a heading and nothing else. The stroke
  // sizes itself to the block, which is what `evidence-row` already does for the same
  // reason.
  stroke: (left: (paint: TONE_PALETTE.at(tone), thickness: 2.2pt)),
  inset: (left: 7pt, y: 1pt),
)[
  #grid(
    columns: (1fr, auto),
    column-gutter: 6pt,
    [#text(size: text-small, weight: 650, fill: navy)[#headline]],
    [#align(right)[#text(size: text-micro, weight: 700, fill: TONE_PALETTE.at(tone))[#upper(tone)]]],
  )
  #v(3pt)
  #set par(justify: true, leading: 0.9em)
  #text(size: text-fine, fill: ink)[#detail]
  #evidence
]

// What a claim was grounded on. lotus-ai supplies metric, value and source for each, all
// required, and lotus-report drops any ref that is not complete -- so a ref that reaches
// here is whole, and printing a partial one is not a case that needs handling.
#let commentary-evidence(refs) = [
  #v(3pt)
  #text(size: text-micro, fill: slate)[#refs]
]

// The provenance sentence lotus-report composes, placed where it cannot be separated
// from the commentary it describes. A provenance line orphaned onto the next page
// silently attributes narrative to whatever precedes it there.
#let commentary-provenance(text-body-line) = block(
  breakable: false,
  width: 100%,
  inset: 8pt,
  fill: mist,
  stroke: (paint: rule, thickness: 0.45pt),
  radius: 3pt,
)[
  #text(size: text-micro, weight: 700, fill: accent)[Provenance]
  #v(3pt)
  #set par(justify: false, leading: 0.86em)
  #text(size: text-fine, fill: ink)[#text-body-line]
]

#let reviewed-advisory-narrative-page() = [
  #section-marker("Advisory narrative", "Reviewed advisory narrative approved for advisor use", header: "Reviewed advisory narrative")
  #v(10pt)
  #grid(
    columns: (0.76fr, 1.24fr),
    column-gutter: 18pt,
    [
      #section-lead(
        "Advisor-approved package",
        "Optional advisor-use narrative content is rendered only when the upstream package is approved for advisor use and included by lotus-report.",
      )
      #v(10pt)
      #advisory-boundary-panel([This page presents a reviewed advisory narrative package supplied by lotus-advise through lotus-report.])
      #v(10pt)
      #report-panel([
        #text(size: text-small, weight: 650, fill: navy)[Package lineage]
        #v(7pt)
        ${REVIEWED_ADVISORY_FACT_ROWS}
      ], inset: 10pt)
    ],
    [
      #text(size: text-lead, weight: 700, fill: navy)[Approved narrative sections]
      #v(8pt)
      ${REVIEWED_ADVISORY_NARRATIVE_BLOCKS}
      #v(12pt)
      #text(size: text-body, weight: 650, fill: navy)[Disclosures]
      #v(6pt)
      ${REVIEWED_ADVISORY_DISCLOSURE_BLOCKS}
    ],
  )
]

#let advisor-proposal-memo-page() = [
  #section-marker("Advisor memo", "Approved advisor proposal memo", header: "Advisor proposal memo")
  #v(10pt)
  #grid(
    columns: (0.76fr, 1.24fr),
    column-gutter: 18pt,
    [
      #section-lead(
        "Advisor-use memo package",
        "The proposal memo is rendered only when lotus-advise supplies an advisor-use reviewed package through lotus-report.",
      )
      #v(10pt)
      #advisory-boundary-panel([This page presents a reviewed advisor proposal memo supplied by lotus-advise through lotus-report.])
      #v(10pt)
      #report-panel([
        #text(size: text-small, weight: 650, fill: navy)[Memo lineage]
        #v(7pt)
        ${ADVISOR_MEMO_FACT_ROWS}
      ], inset: 10pt)
    ],
    [
      #text(size: text-lead, weight: 700, fill: navy)[Memo sections]
      #v(8pt)
      ${ADVISOR_MEMO_SECTION_BLOCKS}
      #v(12pt)
      #text(size: text-body, weight: 650, fill: navy)[Disclosures]
      #v(6pt)
      ${ADVISOR_MEMO_DISCLOSURE_BLOCKS}
    ],
  )
]


#let advisor-commentary-page() = [
  #section-marker(
    "Advisor commentary",
    "AI-assisted commentary, reviewed and accepted for advisor use",
    header: "Advisor commentary",
  )
  #v(10pt)
  #grid(
    columns: (0.76fr, 1.24fr),
    column-gutter: 18pt,
    [
      #section-lead(
        "Reviewed commentary package",
        "Commentary is drafted with AI assistance and rendered only after a named reviewer has accepted it. lotus-render places the accepted text and does not rewrite, summarise or extend it.",
      )
      #v(10pt)
      #advisory-boundary-panel([This page presents AI-assisted commentary accepted by a named reviewer, supplied by lotus-ai through lotus-report.])
      #v(10pt)
      #report-panel([
        #text(size: text-small, weight: 650, fill: navy)[Commentary lineage]
        #v(7pt)
        ${ADVISOR_COMMENTARY_FACT_ROWS}
      ], inset: 10pt)
      #v(10pt)
      #commentary-provenance([${ADVISOR_COMMENTARY_PROVENANCE}])
    ],
    [
      #text(size: text-lead, weight: 700, fill: navy)[Summary]
      #v(6pt)
      #report-panel([
        #set par(justify: true, leading: 0.94em)
        #text(size: text-small, fill: ink)[${ADVISOR_COMMENTARY_SUMMARY}]
      ], inset: 10pt)

      #v(12pt)
      #text(size: text-body, weight: 650, fill: navy)[Talking points]
      #v(7pt)
      ${ADVISOR_COMMENTARY_TALKING_POINTS}

      #v(10pt)
      #text(size: text-body, weight: 650, fill: navy)[Risks and exceptions]
      #v(7pt)
      ${ADVISOR_COMMENTARY_RISKS}
    ],
  )
]
