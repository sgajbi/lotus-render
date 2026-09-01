"""Which allocation dimensions the document presents, and in what order.

Report decides this. It is a statement about what the report communicates -- the caller
asked for sector allocation, or asked for nothing and took the default -- and Render's
part is to draw what it is told.

Render used to infer it. `allocation_breakdowns` ships all seven `by_*` dimensions
unconditionally, and the renderer picked the first with rows from a priority order of its
own. Because currency led that order and the package always carries it, **six of the seven
single-dimension orders drew a currency table**: an advisor who asked for sector exposure
received currency exposure, with a currency definition in the appendix agreeing with it,
and nothing on the page saying the request had not been honoured.

So presence stops meaning anything. A dimension is presented because
`allocation_presentation.dimensions` names it, never because its rows are non-empty, and
this module is the only place that reads a `by_*` key --
`test_no_emitter_reads_a_breakdown_key_directly` holds that.

The three postures are Report's, and are authoritative rather than derivable:

``ready``
    Draw it.
``empty``
    The source answered and the portfolio has no buckets in this dimension. Draw the
    statement: a client with no fixed income legitimately has an empty rating breakdown,
    and that is a fact about the portfolio.
``unavailable``
    The source did not answer. Say so and draw nothing -- a fact about the data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

READY = "ready"
EMPTY = "empty"
UNAVAILABLE = "unavailable"
POSTURES = frozenset({READY, EMPTY, UNAVAILABLE})

# The heading a reader sees, and the glossary subject that defines it. Both are Render's:
# the package sends a dimension identifier and no labels, so a supplied title could not
# disagree with the appendix's governed wording -- there is only one name to agree with.
DIMENSION_TITLES: dict[str, str] = {
    "asset_class": "By asset class",
    "currency": "By currency",
    "region": "By region",
    "sector": "By sector",
    "country": "By country",
    "product_type": "By product type",
    "rating": "By rating",
}
DIMENSION_SUBJECTS: dict[str, str] = {
    "asset_class": "allocation",
    "currency": "allocation.currency",
    "region": "allocation.region",
    "sector": "allocation.sector",
    "country": "allocation.country",
    "product_type": "allocation.product_type",
    "rating": "allocation.rating",
}


@dataclass(frozen=True)
class PresentedDimension:
    """One dimension the document presents, with the posture Report resolved for it."""

    dimension: str
    package_key: str
    posture: str

    @property
    def title(self) -> str:
        return DIMENSION_TITLES.get(self.dimension, "Allocation detail")

    @property
    def subject(self) -> str | None:
        return DIMENSION_SUBJECTS.get(self.dimension)


def presented_dimensions(report_data: Mapping[str, object]) -> list[PresentedDimension]:
    """The dimensions to present, in the order Report resolved them.

    An entry Render cannot draw -- an unknown posture, a missing key, a dimension with no
    heading -- is dropped rather than guessed at. Dropping is visible: the block is absent
    and `test_every_presented_dimension_reaches_the_page` compares what was named against
    what was drawn.
    """
    presentation = report_data.get("allocation_presentation")
    if not isinstance(presentation, Mapping):
        return []
    entries = presentation.get("dimensions")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes, bytearray)):
        return []

    return [item for entry in entries if (item := _presented_dimension(entry)) is not None]


def _presented_dimension(entry: object) -> PresentedDimension | None:
    """One entry, or None when Render could not draw what it describes."""
    if not isinstance(entry, Mapping):
        return None
    dimension = str(entry.get("dimension") or "")
    package_key = str(entry.get("package_key") or "")
    posture = str(entry.get("posture") or "")
    if dimension not in DIMENSION_TITLES or not package_key or posture not in POSTURES:
        return None
    return PresentedDimension(dimension=dimension, package_key=package_key, posture=posture)


def presented_dimension(
    report_data: Mapping[str, object], dimension: str
) -> PresentedDimension | None:
    """The named dimension as this document presents it, or None if it does not."""
    return next(
        (item for item in presented_dimensions(report_data) if item.dimension == dimension),
        None,
    )


def presented_rows(report_data: Mapping[str, object], item: PresentedDimension) -> object:
    """The rows behind one presented dimension.

    The single place a `by_*` key is read, and only for a dimension the package named.
    """
    breakdowns = report_data.get("allocation_breakdowns")
    if not isinstance(breakdowns, Mapping):
        return None
    return breakdowns.get(item.package_key)
