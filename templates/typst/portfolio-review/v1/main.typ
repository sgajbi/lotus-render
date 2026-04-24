#set page(
  paper: "a4",
  flipped: true,
  margin: (x: 16mm, y: 16mm),
  numbering: "1 / 1",
  number-align: right + bottom,
)

#set text(font: ("Source Sans 3", "Arial", "Libertinus Sans"), size: 9.2pt, fill: rgb("#27374a"))
#set par(leading: 1.14em, spacing: 0.48em)

#import "_allocation.typ": allocation-page
#import "_appendix.typ": appendix-page
#import "_cover.typ": contents-page, cover-page
#import "_overview.typ": scope-page
#import "_performance.typ": performance-page
#import "_positions.typ": observations-page
#import "_transactions.typ": transactions-page

${REPORT_SECTIONS}
