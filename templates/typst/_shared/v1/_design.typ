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
#let gold = rgb("#C38B2E")

// --- Shared primitives ----------------------------------------------------------
// Defined once here because they were defined three times: proof-pack, outcome-review
// and rebalance-wave each carried their own byte-identical copy, with nothing keeping
// them in step. That is exactly the arrangement that let the palettes drift into four
// values of `accent`, so it is closed before it does the same again.

// A field and its value, side by side. The width is fixed so that stacked rows align
// down the page rather than each row finding its own column.
#let key-value-row(key, val) = grid(
  columns: (38mm, 1fr),
  gutter: 5mm,
  row-gutter: 2pt,
  key,
  val,
)

#let label(value) = text(size: 6.8pt, fill: muted, weight: "semibold", upper(value))
#let value(value) = text(size: 9.5pt, fill: ink, weight: "medium", value)

// --- Direction ----------------------------------------------------------------
// Named for meaning, not hue. `gain` must mean "this number went up" everywhere, which
// it could not while #286446 was simultaneously proof-pack's brand accent; unifying
// `accent` frees the value for the one meaning it should have.
#let gain = rgb("#286446")
#let loss = rgb("#A6321F")

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
// The display sizes are deliberately not on this scale: 16, 17, 18, 19, 20.5 and 28pt are
// eight declarations across cover titles and section headings, each chosen for a specific
// piece of furniture rather than drawn from a range, and forcing them onto shared steps
// would change the one thing on a page a reader looks at first.
#let text-micro = 6.1pt
#let text-caption = 6.8pt
#let text-fine = 7.4pt
#let text-small = 8.1pt
#let text-body = 8.8pt
#let text-body-strong = 9.5pt
#let text-lead = 11pt
#let text-subhead = 12pt
#let text-head = 13pt

#let TYPE_SCALE = (
  text-micro, text-caption, text-fine, text-small, text-body,
  text-body-strong, text-lead, text-subhead, text-head,
)
