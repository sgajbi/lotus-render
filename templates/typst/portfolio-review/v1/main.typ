#set page(
  paper: "a4",
  flipped: true,
  margin: (x: 16mm, y: 16mm),
  footer: context [
    #line(length: 100%, stroke: (paint: rgb("#d7e2ea"), thickness: 0.35pt))
    #v(5pt)
    #grid(
      columns: (1fr, auto),
      [#text(size: 6.4pt, fill: rgb("#66798d"))[${PORTFOLIO_NAME}]],
      [#text(size: 6.8pt, fill: rgb("#1f2f43"))[#counter(page).display("1 / 1")]],
    )
  ],
  footer-descent: 38%,
)

#set text(size: 9.2pt, fill: rgb("#27374a"))
#set par(leading: 1.14em, spacing: 0.48em)

#import "_allocation.typ": allocation-page
#import "_appendix.typ": appendix-page
#import "_cover.typ": contents-page, cover-page
#import "_overview.typ": scope-page
#import "_performance.typ": performance-page
#import "_positions.typ": observations-page
#import "_transactions.typ": transactions-page

${REPORT_SECTIONS}
