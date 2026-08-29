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

// --- Direction ----------------------------------------------------------------
// Named for meaning, not hue. `gain` must mean "this number went up" everywhere, which
// it could not while #286446 was simultaneously proof-pack's brand accent; unifying
// `accent` frees the value for the one meaning it should have.
#let gain = rgb("#286446")
#let loss = rgb("#A6321F")
