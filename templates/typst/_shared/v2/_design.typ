// The Lotus document design system: one palette, shared by every template family.
//
// Before this file, each family declared its own tokens and they had drifted. The same
// names carried different values -- `accent` was #1F5AA6, #286446, #21606f and #315c8a
// in the four families, `ink` and `rule` had two values each -- and the same role went
// under two names, `slate` in one family and `muted` in the other three. A client
// receiving a portfolio review and an outcome review received two different brands.
//
// This file is copied into every render workspace and is covered by every family's
// template digest, so a change here changes the digest of every document it can reach.
// That is deliberate: a palette edit is a change to every document, and the evidence
// chain should say so.
//
// What earns a component a place here: a second consumer, and nothing else. A component
// is promoted the moment a second family or file needs it -- the way `evidence-row`
// arrived, as three drifting copies of one implementation (#213) -- and not before: a
// shared module with one caller is speculative generality. The copy path is guarded:
// `test_component_promotion_guard.py` fails when two template files declare
// near-identical implementations under different names.

// --- Typeface -------------------------------------------------------------------
// The document face, vendored in fonts/ beside this file and reached only through
// the workspace --font-path -- never the host's font store, which would let an
// unpinned, undigested font restyle every document. One face for the same reason
// as one accent: a client receiving two Lotus documents receives one brand. The
// fallback list is deliberately empty-of-system-faces; if the vendored files are
// missing the compiler fails loudly rather than silently substituting a serif.
// Source Sans 3, SIL OFL 1.1 (fonts/LICENSE.md); Light carries display roles,
// Regular the body, Medium/Semibold emphasis -- the weights the type scale names.
#let document-face = "Source Sans 3"

// --- Neutrals -------------------------------------------------------------------
// The near-black used for figures and body text.
#let ink = rgb("#16202A")
// The deep tone reserved for titles and cover furniture.
#let navy = rgb("#0B1F33")
// Secondary text: labels, captions, and anything supporting a figure rather than
// being one. `muted` was the other families' name for this exact role.
#let slate = rgb("#5B6770")
#let muted = slate
// Hairlines, table rules and card borders.
#let rule = rgb("#D9E1E8")
// The quiet fill behind a track, a bar or an inset panel.
#let mist = rgb("#F6F8FA")

// --- Brand --------------------------------------------------------------------
// One accent. A document family is distinguished by what it says, not by having a
// different brand colour from its siblings.
#let accent = rgb("#1F5AA6")
#let accent-soft = rgb("#2C7A7B")

// --- Chart series ---------------------------------------------------------------
// The categorical palette, in the order a chart assigns it. The first two are the
// brand accents, so a single-series chart and a two-slice donut agree with the rest
// of the document; the remainder are chosen to stay distinguishable in greyscale and
// to a reader with colour vision deficiency.
//
// These lived as hex literals in `portfolio_charts.py`, which meant the design system
// could not restyle a chart and a token could drift from its own copy. The emitters
// name a series now; nothing outside this file decides what the colour is.
#let series-1 = accent
#let series-2 = accent-soft
// The six series are luminance-separated (#217): printed in monochrome, a donut's only
// key is its greyscale, and three of the six used to sit inside a 0.04 luminance band --
// identical keys to a printer. The gamma-space Rec.709 ladder is now 0.20 / 0.33 / 0.41
// / 0.55 / 0.67 / 0.76 (min pairwise delta 0.088, guarded by
// `test_series_survive_a_greyscale_printer`), with the two brand accents unmoved and
// every other hue kept -- only lightness moved. A greyscale copy loses richness, never
// which slice is which.
#let series-3 = rgb("#BE872D")
#let series-4 = rgb("#BFC2C9")
#let series-5 = rgb("#3D2D4C")
#let series-6 = rgb("#98B0AE")

// What a chart draws for the part of a total it is not showing. `rule`, so it reads as
// an absence against the palette rather than as one more series.
#let series-uncharted = rule

#let SERIES_PALETTE = (
  "series-1": series-1,
  "series-2": series-2,
  "series-3": series-3,
  "series-4": series-4,
  "series-5": series-5,
  "series-6": series-6,
  "series-uncharted": series-uncharted,
)

// --- Shared primitives ----------------------------------------------------------
// Defined once here because they were defined three times: proof-pack, outcome-review
// and rebalance-wave each carried their own byte-identical copy, with nothing keeping
// them in step. That is exactly the arrangement that let the palettes drift into four
// values of `accent`, so it is closed before it does the same again.

// A field and its value, side by side. The width is fixed so that stacked rows align
// down the page rather than each row finding its own column.
// A key column fixed at 38mm gave the value whatever was left, which inside a
// half-width block was 45mm -- narrower than the identifiers these documents carry.
// `auto` takes the width of the longest key instead, and the value takes the rest.
//
// Rows are grouped so their keys align: laid out one grid apiece, each row sized its
// own key column and the values stepped in and out down the page.
#let key-value-rows(pairs) = grid(
  columns: (auto, 1fr),
  column-gutter: 5mm,
  row-gutter: 2pt,
  ..pairs.map(pair => (pair.at(0), pair.at(1))).flatten(),
)

#let key-value-row(key, val) = key-value-rows(((key, val),))

// --- Type scale -----------------------------------------------------------------
// The templates carried 159 size declarations across 53 distinct values, many separated
// by less than a tenth of a point: 6.55, 6.6, 6.75, 6.8, 6.85, 6.9 all appeared, and no
// reader could tell them apart. That is not a scale, it is an accumulation, and it makes
// "make the small text slightly larger" a search across fifty numbers.
//
// Nine steps cover the body range, none closer than 0.6pt so each is a decision a reader
// could actually perceive. Snapping to them moved 80 of 146 declarations, by at most
// 0.5pt and usually less than 0.2pt.
//
// The display sizes are deliberately not on this scale, and that decision stands: each is
// chosen for a specific piece of furniture rather than drawn from a range, and forcing
// them onto shared steps would change the one thing on a page a reader looks at first.
//
// They are named all the same. When that decision was recorded there were six display
// values across eight declarations; there are now three across five, and one of them --
// the document title at 18pt -- is written out separately in all three governance
// families. That is the same furniture three times, which is how `evidence-row` came to
// be three copies of one component. Naming a role is not snapping it to a ladder.
//
// So: nine body steps below, three display roles after them, and no size literal anywhere
// outside this file. `test_no_template_spells_a_text_size` holds that.
#let text-micro = 6.1pt
#let text-caption = 6.8pt
#let text-fine = 7.4pt
#let text-small = 8.1pt
#let text-body = 8.8pt
#let text-body-strong = 9.5pt
#let text-lead = 11pt
#let text-subhead = 12pt
#let text-head = 13pt

// Display roles, off the body ladder by design. Named for the furniture they set,
// because that is what makes them roles rather than sizes: `text-document` is the title
// of a governed evidence document, and all three families set it the same way.
#let text-section = 17pt
#let text-document = 18pt
#let text-cover = 34pt
// The per-page display title of the #270 page architecture: the first thing a
// reader sees on every content page, sized for the A4-landscape frame the
// portfolio review carries. Off the body ladder like its display siblings.
#let text-page-title = 26pt

#let TYPE_SCALE = (
  text-micro, text-caption, text-fine, text-small, text-body,
  text-body-strong, text-lead, text-subhead, text-head,
)

#let label(value) = text(size: text-caption, fill: muted, weight: "semibold", upper(value))
#let value(value) = text(size: text-body-strong, fill: ink, weight: "medium", value)

// One row of governed evidence: a labelled field per column, laid out on shares of the
// line rather than on the row's own content.
//
// The three governance families each had their own copy of this with `auto` columns, so
// every row sized itself and a column landed somewhere different on each one -- the STATE
// label of a four-item rebalance wave spanned 55mm across four rows. Shares are the
// caller's, because the families carry different fields; the geometry is not, because
// alignment is not a per-family question.
//
// `fields` is a list of `(name, share, body)`.
// The governed document reference (#158): the one externally meaningful identity a
// client-facing artifact carries, placed the same way by every family -- no family
// invents its own provenance treatment. Report mints the reference before render and
// supplies it in the render context; Render places it verbatim and invents nothing.
// Internal trace and correlation ids are support evidence, not this. Drawn only when
// a reference was supplied.
// Semantic headings (#246 phase 2): the flow title is the document's H1 and section
// labels are H2, so the tag tree has structure assistive technology can navigate.
// One implementation of "a heading styled by its caller": every call site names its
// own scale step and tones, so the type-scale guard still sees each step asked for by
// a template, and a family with its own voice (the portfolio review's cover) adapts
// over these rather than copying the chrome.
#let document-title(value, size: none, weight: "medium", fill: ink) = heading(
  level: 1,
)[#text(size: size, weight: weight, fill: fill)[#value]]
#let section-head(value, size: none, weight: "medium", tracking: 0pt, fill: ink) = heading(
  level: 2,
)[#text(size: size, weight: weight, tracking: tracking, fill: fill)[#value]]

#let document-reference-mark(reference) = if reference != "" [
  #h(6pt)#text(size: text-caption, fill: muted)[#reference]
]


#let evidence-row(fields) = block(
  below: 5pt,
  stroke: (left: (paint: accent, thickness: 1.1pt)),
  inset: (left: 5pt, y: 3pt),
)[
  #grid(
    columns: fields.map(field => field.share * 1fr),
    gutter: 4mm,
    ..fields.map(field => [#label(field.name) #linebreak() #field.body]),
  )
]


// --- Direction ----------------------------------------------------------------
// Named for meaning, not hue. `gain` must mean "this number went up" everywhere, which
// it could not while #286446 was simultaneously proof-pack's brand accent; unifying
// `accent` frees the value for the one meaning it should have.
#let gain = rgb("#286446")
#let loss = rgb("#A6321F")

// --- Narrative tone -------------------------------------------------------------
// The tone a reviewer assigned to a governed talking point, which is not the direction
// of a number: `gain` means "this figure went up" everywhere, and a positive talking
// point is a judgement about a claim. Two meanings on one token is how `accent` came to
// carry four values, so tone gets its own names even where a value is shared.
//
// lotus-report normalises the vocabulary to exactly these three before the package is
// built, and anything it does not recognise arrives as `neutral` -- so an unknown tone
// here is a contract violation, not a colour to invent.
#let tone-positive = gain
#let tone-caution = rgb("#B4791C")
#let tone-neutral = slate

#let TONE_PALETTE = (
  "positive": tone-positive,
  "warning": tone-caution,
  "neutral": tone-neutral,
)

