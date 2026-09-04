// Palette and type scale come from the shared design system; this file holds only what
// is specific to the portfolio review -- its spacing scale and its text roles -- and
// re-exports exactly the shared tokens its own consumers import through it.
#import "_design.typ": TONE_PALETTE, accent, accent-soft, document-face, document-title, gain, ink, loss, mist, navy, rule, section-head, slate, text-body, text-body-strong, text-caption, text-cover, text-fine, text-head, text-lead, text-micro, text-section, text-small

#let page-margin-x = 16mm
#let page-margin-y = 16mm
#let grid-gap = 16pt
#let hairline = 0.45pt
#let panel-radius = 3pt

// The document's one H1: the cover names the document, and the heading gives the
// tag tree its root the H2 subtitles hang from. An adapter over the shared heading
// implementation -- this family's voice is its data.
#let cover-title(value) = document-title(value, size: text-cover, weight: 300, fill: navy)
#let section-title(value) = text(size: text-section, weight: 300, fill: navy)[#value]
// A real heading, styled as the subtitle always looked: the tag tree carried zero
// H tags (#246 phase 2), so assistive navigation had nothing to move by.
#let section-subtitle(value) = section-head(value, size: text-small, weight: 600, tracking: 0.12pt, fill: slate)
#let page-kicker(value) = text(size: text-small, fill: slate)[#value]
#let body-muted(value) = text(size: text-small, fill: slate)[#value]

// The message shown where governed data is absent. The emitters used to inline a
// colour of their own - rgb(104, 118, 132), matching no token here - so every
// "not available" line was an off-palette grey no template could restyle.
#let empty-state(message, size: text-body) = text(size: size, fill: slate)[#message]
#let body-strong(value) = text(size: text-body-strong, weight: 500, fill: ink)[#value]
#let small-caps(value) = text(size: text-caption, weight: 600, tracking: 0.22pt, fill: slate)[#value]

// Decorative: a rule says nothing a heading or table does not already say.
#let soft-rule() = pdf.artifact(line(length: 100%, stroke: (paint: rule, thickness: hairline)))
