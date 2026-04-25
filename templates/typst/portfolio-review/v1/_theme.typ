#let ink = rgb("#16202A")
#let navy = rgb("#0B1F33")
#let slate = rgb("#5B6770")
#let mist = rgb("#F6F8FA")
#let rule = rgb("#D9E1E8")
#let accent = rgb("#1F5AA6")
#let accent-soft = rgb("#2C7A7B")
#let gold = rgb("#C38B2E")

#let page-margin-x = 16mm
#let page-margin-y = 16mm
#let grid-gap = 16pt
#let section-gap = 14pt
#let block-gap = 9pt
#let hairline = 0.45pt
#let panel-radius = 3pt

#let cover-title(value) = text(size: 28pt, weight: 300, fill: navy)[#value]
#let section-title(value) = text(size: 17pt, weight: 300, fill: navy)[#value]
#let section-subtitle(value) = text(size: 7.8pt, weight: 600, tracking: 0.12pt, fill: slate)[#value]
#let page-kicker(value) = text(size: 7.8pt, fill: slate)[#value]
#let metric-value(value) = text(size: 16pt, weight: 500, fill: ink)[#value]
#let body-muted(value) = text(size: 8.25pt, fill: slate)[#value]
#let body-strong(value) = text(size: 9.2pt, weight: 500, fill: ink)[#value]
#let small-caps(value) = text(size: 7pt, weight: 600, tracking: 0.22pt, fill: slate)[#value]

#let soft-rule() = line(length: 100%, stroke: (paint: rule, thickness: hairline))
