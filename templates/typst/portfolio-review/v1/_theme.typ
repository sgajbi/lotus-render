// Palette and type scale come from the shared design system; this file holds only what
// is specific to the portfolio review -- its spacing scale and its text roles -- and
// re-exports exactly the shared tokens its own consumers import through it.
#import "_design.typ": accent, accent-soft, gain, ink, loss, mist, navy, rule, slate, text-body, text-body-strong, text-caption, text-cover, text-fine, text-head, text-lead, text-micro, text-section, text-small

#let page-margin-x = 16mm
#let page-margin-y = 16mm
#let grid-gap = 16pt
#let hairline = 0.45pt
#let panel-radius = 3pt

#let cover-title(value) = text(size: text-cover, weight: 300, fill: navy)[#value]
#let section-title(value) = text(size: text-section, weight: 300, fill: navy)[#value]
#let section-subtitle(value) = text(size: text-small, weight: 600, tracking: 0.12pt, fill: slate)[#value]
#let page-kicker(value) = text(size: text-small, fill: slate)[#value]
#let body-muted(value) = text(size: text-small, fill: slate)[#value]

// The message shown where governed data is absent. The emitters used to inline a
// colour of their own - rgb(104, 118, 132), matching no token here - so every
// "not available" line was an off-palette grey no template could restyle.
#let empty-state(message, size: text-body) = text(size: size, fill: slate)[#message]
#let body-strong(value) = text(size: text-body-strong, weight: 500, fill: ink)[#value]
#let small-caps(value) = text(size: text-caption, weight: 600, tracking: 0.22pt, fill: slate)[#value]

#let soft-rule() = line(length: 100%, stroke: (paint: rule, thickness: hairline))
