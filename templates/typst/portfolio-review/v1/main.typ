#import "_theme.typ": empty-state, ink, page-margin-x, page-margin-y, rule, slate, text-body, text-caption, text-micro
#import "_components.typ": running-header

#set page(
  paper: "a4",
  flipped: true,
  margin: (x: page-margin-x, y: page-margin-y),
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
      columns: (1fr, auto),
      [#text(size: text-micro, fill: slate)[#"${PORTFOLIO_NAME}"]],
      [#text(size: text-caption, fill: ink)[#counter(page).display("1 / 1")]],
    )
  ],
  footer-descent: 38%,
)

#set text(size: text-body, fill: ink)
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
