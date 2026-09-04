# Gallery entry: risk-attribution decomposition

The v3 primitive for "what risk drove the result?" (report#254), following the
gallery shape #219 founded: canonical producer emissions faithful to the shipped
contract, assertions that fail on wrong results, and real-engine rendering on
the real v3 page. The `ready-both-sets` vectors are the exact values the
producer's pinned tests use.

## Intended usage

- One panel, both decompositions stacked -- total risk first, then active risk;
  a refused set is a stated row in place, never invisible.
- Contributor rows carry the source's own label and order (never re-ranked),
  a signed diverging-track bar normalised within the set, the component
  contribution formatted from the set's source-stated `unit`, and
  `percent_contribution` formatted by the STRUCTURAL fraction-of-one rule the
  contract defines. Optional stated facts (`weight_average`, fraction rule;
  `marginal_contribution`, metric unit) print on a secondary line -- a stated
  source fact never drops silently.
- The RESIDUAL is always its own labelled row with a value and no bar; a zero
  residual still prints. The stated reconciliation facts print beside it;
  Render performs no arithmetic.
- The scale convention is stated wherever a set draws.
- Bar colours follow the document's standing negative/positive number semantic
  (the same diverging-track the performance rows use); every figure prints, so
  the meaning never depends on colour alone.

## Prohibited or misleading usage

- **Never allocate the residual away, hide it, or draw it as a bar** -- as a
  bar it would visually rank against contributors, and it is precisely the
  part the decomposition does not explain.
- **Never re-rank, sum, verify, or otherwise derive** -- contributor order,
  the reconciliation triple, and every figure are source facts, printed.
- **Never print a financial number without its unit semantics** -- a ready set
  without `unit` is stated, not drawn (producer refuses upstream; this is the
  drift backstop).
- **Never part-draw**: an incomplete triple, a malformed contributor row, or
  an unformattable stated fact refuses the WHOLE set with a statement.
- **Not a chart for cross-set comparison** -- bars normalise within their own
  set, and the stated scale convention says so.
