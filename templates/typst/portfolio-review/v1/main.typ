#set page(
  paper: "a4",
  flipped: true,
  margin: (x: 18mm, y: 18mm),
  numbering: "1 / 1",
  number-align: right + bottom,
)

#set text(size: 9.8pt, fill: rgb("#27374a"))

#import "_pages.typ": appendix-page, allocation-page, contents-page, cover-page, observations-page, performance-page, scope-page, transactions-page

#cover-page()
#pagebreak()
#contents-page()
#pagebreak()
#scope-page()
#pagebreak()
#performance-page()
#pagebreak()
#allocation-page()
#pagebreak()
#observations-page()
#pagebreak()
#transactions-page()
#pagebreak()
#appendix-page()
