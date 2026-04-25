#import "_theme.typ": ink, page-margin-x, page-margin-y, rule, slate

#set page(
  paper: "a4",
  flipped: true,
  margin: (x: page-margin-x, y: page-margin-y),
  footer: context [
    #line(length: 100%, stroke: (paint: rule, thickness: 0.35pt))
    #v(5pt)
    #grid(
      columns: (1fr, auto),
      [#text(size: 6.4pt, fill: slate)[${PORTFOLIO_NAME}]],
      [#text(size: 6.8pt, fill: ink)[#counter(page).display("1 / 1")]],
    )
  ],
  footer-descent: 38%,
)

#set text(size: 8.9pt, fill: ink)
#set par(leading: 1.08em, spacing: 0.42em)

#import "_allocation.typ": allocation-page
#import "_appendix.typ": appendix-page
#import "_cover.typ": contents-page, cover-page
#import "_overview.typ": scope-page
#import "_performance.typ": performance-page
#import "_positions.typ": observations-page
#import "_transactions.typ": transactions-page

${REPORT_SECTIONS}
