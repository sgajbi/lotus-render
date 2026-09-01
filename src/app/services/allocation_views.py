"""Which allocation breakdown the document draws beside the asset-class one.

A report package can carry several; the page has room for one, so it takes the first of
these that has rows. That decision is read twice -- once to draw the table and once to
decide which definition the appendix needs -- and it used to be made twice, so a document
could draw a sector table and define currency exposure.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.services.typst_values import row_sequence

# Priority order, most useful to a private-banking reader first. Currency leads because
# it is the exposure a reporting-currency valuation hides.
SUPPLEMENTAL_VIEWS: tuple[tuple[str, str], ...] = (
    ("by_currency", "By currency"),
    ("by_region", "By region"),
    ("by_sector", "By sector"),
    ("by_country", "By country"),
    ("by_product_type", "By product type"),
    ("by_rating", "By rating"),
)

# What the appendix has to explain once that view is on the page. One per view, because
# a table a reader cannot interpret is not reference material.
SUPPLEMENTAL_SUBJECTS: dict[str, str] = {
    key: f"allocation.{key.removeprefix('by_')}" for key, _ in SUPPLEMENTAL_VIEWS
}


def supplemental_allocation_choice(
    allocation_breakdowns: Mapping[str, object],
) -> tuple[str, str] | None:
    """The (key, title) of the view the document draws, or None if it draws none."""
    for key, title in SUPPLEMENTAL_VIEWS:
        if row_sequence(allocation_breakdowns.get(key)):
            return key, title
    return None
