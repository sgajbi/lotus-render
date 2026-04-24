#let ink = rgb("#16202A")
#let navy = rgb("#0B1F33")
#let slate = rgb("#5B6770")
#let mist = rgb("#F6F8FA")
#let rule = rgb("#D9E1E8")
#let accent = rgb("#1F5AA6")
#let accent-soft = rgb("#2C7A7B")
#let gold = rgb("#C38B2E")

#let cover-title(value) = text(size: 28pt, weight: 300, fill: navy)[#value]
#let section-title(value) = text(size: 17.2pt, weight: 300, fill: navy)[#value]
#let section-subtitle(value) = text(size: 8pt, weight: 500, tracking: 0.15pt, fill: slate)[#value]
#let page-kicker(value) = text(size: 7.8pt, fill: slate)[#value]
#let metric-value(value) = text(size: 16pt, weight: 500, fill: ink)[#value]
#let body-muted(value) = text(size: 8.5pt, fill: slate)[#value]
#let body-strong(value) = text(size: 9.2pt, weight: 500, fill: ink)[#value]
#let small-caps(value) = text(size: 7.2pt, weight: 500, tracking: 0.3pt, fill: slate)[#value]

#let soft-rule() = line(length: 100%, stroke: (paint: rule, thickness: 0.55pt))
