// Palette comes from the shared design system; this file holds only what is specific
// to the portfolio review: its spacing scale and its text roles.
#import "_design.typ": accent, accent-soft, gain, gold, ink, loss, mist, navy, rule, slate

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

// The message shown where governed data is absent. The emitters used to inline a
// colour of their own - rgb(104, 118, 132), matching no token here - so every
// "not available" line was an off-palette grey no template could restyle.
#let empty-state(message, size: 9pt) = text(size: size, fill: slate)[#message]
#let body-strong(value) = text(size: 9.2pt, weight: 500, fill: ink)[#value]
#let small-caps(value) = text(size: 7pt, weight: 600, tracking: 0.22pt, fill: slate)[#value]

#let soft-rule() = line(length: 100%, stroke: (paint: rule, thickness: hairline))
