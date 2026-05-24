#import "_theme.typ": accent, ink, mist, navy, rule, slate, soft-rule
#import "_components.typ": page-header, report-panel, section-lead

#let advisory-fact-row(label, value) = [
  #grid(
    columns: (0.42fr, 0.58fr),
    column-gutter: 9pt,
    [#text(size: 6.9pt, fill: slate)[#label]],
    [#text(size: 6.9pt, weight: 520, fill: ink)[#value]],
  )
  #v(3pt)
]

#let advisory-narrative-block(title, body) = report-panel([
  #text(size: 9.4pt, weight: 650, fill: navy)[#title]
  #v(5pt)
  #set par(justify: true, leading: 0.94em)
  #text(size: 8.15pt, fill: ink)[#body]
], inset: 10pt)

#let advisory-disclosure-block(disclosure-id, body) = [
  #text(size: 6.8pt, weight: 650, fill: ink)[#disclosure-id]
  #linebreak()
  #set par(justify: true, leading: 0.82em)
  #text(size: 6.75pt, fill: slate)[#body]
]

#let advisory-boundary-panel() = block(
  inset: 10pt,
  fill: mist,
  stroke: (paint: rule, thickness: 0.45pt),
  radius: 4pt,
)[
  #text(size: 7.4pt, weight: 700, fill: accent)[Advisor-use boundary]
  #v(4pt)
  #set par(justify: true, leading: 0.86em)
  #text(size: 7.2pt, fill: ink)[
    This page presents a reviewed advisory narrative package supplied by lotus-advise through
    lotus-report. lotus-render does not approve, rewrite, infer, or source additional advice
    facts; it renders only the bounded package carried in the render request.
  ]
]

#let reviewed-advisory-narrative-page() = [
  #page-header("Reviewed advisory narrative")
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
      #advisory-boundary-panel()
      #v(10pt)
      #report-panel([
        #text(size: 8.2pt, weight: 650, fill: navy)[Package lineage]
        #v(7pt)
        ${REVIEWED_ADVISORY_FACT_ROWS}
      ], inset: 10pt)
    ],
    [
      #text(size: 11.5pt, weight: 700, fill: navy)[Approved narrative sections]
      #v(8pt)
      ${REVIEWED_ADVISORY_NARRATIVE_BLOCKS}
      #v(12pt)
      #text(size: 8.5pt, weight: 650, fill: navy)[Disclosures]
      #v(6pt)
      ${REVIEWED_ADVISORY_DISCLOSURE_BLOCKS}
    ],
  )
]

#let advisor-proposal-memo-page() = [
  #page-header("Advisor proposal memo")
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
      #advisory-boundary-panel()
      #v(10pt)
      #report-panel([
        #text(size: 8.2pt, weight: 650, fill: navy)[Memo lineage]
        #v(7pt)
        ${ADVISOR_MEMO_FACT_ROWS}
      ], inset: 10pt)
    ],
    [
      #text(size: 11.5pt, weight: 700, fill: navy)[Memo sections]
      #v(8pt)
      ${ADVISOR_MEMO_SECTION_BLOCKS}
      #v(12pt)
      #text(size: 8.5pt, weight: 650, fill: navy)[Disclosures]
      #v(6pt)
      ${ADVISOR_MEMO_DISCLOSURE_BLOCKS}
    ],
  )
]
