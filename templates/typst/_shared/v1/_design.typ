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

#let label(value) = text(size: 6.9pt, fill: muted, weight: "semibold", upper(value))
#let value(value) = text(size: 9.2pt, fill: ink, weight: "medium", value)

// --- Direction ----------------------------------------------------------------
// Named for meaning, not hue. `gain` must mean "this number went up" everywhere, which
// it could not while #286446 was simultaneously proof-pack's brand accent; unifying
// `accent` frees the value for the one meaning it should have.
#let gain = rgb("#286446")
#let loss = rgb("#A6321F")
