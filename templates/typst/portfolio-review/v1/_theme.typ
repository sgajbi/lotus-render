#let ink = rgb("#24364b")
#let slate = rgb("#607285")
#let mist = rgb("#eef3f8")
#let rule = rgb("#d6e0ea")
#let accent = rgb("#0b6aa2")
#let accent-soft = rgb("#6cb6d8")

#let cover-title(value) = text(size: 27pt, weight: 300, fill: ink)[#value]
#let section-title(value) = text(size: 18pt, weight: 300, fill: slate)[#value]
#let section-subtitle(value) = text(size: 8pt, fill: slate)[#value]
#let page-kicker(value) = text(size: 7.5pt, fill: slate)[#value]
#let metric-value(value) = text(size: 14pt, weight: 500, fill: ink)[#value]
#let body-muted(value) = text(size: 8pt, fill: slate)[#value]
#let body-strong(value) = text(size: 9pt, weight: 500, fill: ink)[#value]
#let small-caps(value) = text(size: 7pt, tracking: 0.8pt, fill: slate)[#value]

#let soft-rule() = line(length: 100%, stroke: (paint: rule, thickness: 0.55pt))
