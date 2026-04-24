#let ink = rgb("#1f2f43")
#let slate = rgb("#66798d")
#let mist = rgb("#eef4f8")
#let rule = rgb("#d7e2ea")
#let accent = rgb("#166a9a")
#let accent-soft = rgb("#7cc4df")

#let cover-title(value) = text(size: 28pt, weight: 300, fill: ink)[#value]
#let section-title(value) = text(size: 17.2pt, weight: 300, fill: ink)[#value]
#let section-subtitle(value) = text(size: 8pt, weight: 500, tracking: 0.15pt, fill: slate)[#value]
#let page-kicker(value) = text(size: 7.8pt, fill: slate)[#value]
#let metric-value(value) = text(size: 16pt, weight: 500, fill: ink)[#value]
#let body-muted(value) = text(size: 8.5pt, fill: slate)[#value]
#let body-strong(value) = text(size: 9.2pt, weight: 500, fill: ink)[#value]
#let small-caps(value) = text(size: 7.2pt, weight: 500, tracking: 0.3pt, fill: slate)[#value]

#let soft-rule() = line(length: 100%, stroke: (paint: rule, thickness: 0.55pt))
