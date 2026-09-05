#import "_theme.typ": document-face, empty-state, ink, page-margin-top, page-margin-x, page-margin-y, rule, slate, text-body, text-caption, text-micro
#import "_components.typ": running-header
#import "_design.typ": document-reference-mark


#set document(title: "${PORTFOLIO_NAME} - Portfolio review", author: "Lotus")

#set page(
  paper: "a4",
  flipped: true,
  margin: (x: page-margin-x, top: page-margin-top, bottom: page-margin-y),
  header: running-header(),
  // The header sits in the top margin rather than above it, so the body starts where
  // the old in-flow header used to leave it. Content that opens a page keeps clear of
  // the rule with its own padding, which a page break cannot collapse the way it
  // collapses spacing between blocks.
  header-ascent: 0pt,
  footer: context [
    #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
    #v(5pt)
    #grid(
      columns: (1fr, auto, 1fr),
      [#text(size: text-micro, fill: slate)[Private & confidential  |  Portfolio review  |  #"${CLIENT_NAME}", #"${PORTFOLIO_NAME}"]#document-reference-mark("${DOCUMENT_REFERENCE}")],
      [#text(size: text-micro, fill: slate)[As of ${AS_OF_DATE}]],
      [#align(right)[#text(size: text-caption, fill: ink)[#counter(page).display("1") / #counter(page).final().first()]]],
    )
  ],
  footer-descent: 38%,
)

// Headings carry structure (H tags, bookmarks); they space exactly as the plain
// paragraphs they used to be (0.42em x 8.8pt body paragraph spacing, absolute so the
// heading's own text size cannot re-scale it).
#show heading: set block(above: 3.7pt, below: 3.7pt)
#show figure: set block(above: 0pt, below: 0pt)
#show figure: set align(start)
#set text(font: document-face, size: text-body, fill: ink)
#set par(leading: 1.08em, spacing: 0.42em)

#import "_allocation.typ": allocation-page
${OPTIONAL_ADVISORY_IMPORT}
#import "_appendix.typ": appendix-page
#import "_cover.typ": contents-page, cover-page
#import "_overview.typ": scope-page
#import "_performance.typ": performance-page
#import "_positions.typ": observations-page
#import "_transactions.typ": transactions-page

${REPORT_SECTIONS}
