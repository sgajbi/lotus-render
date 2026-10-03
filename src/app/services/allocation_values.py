"""Qualified allocation figures shared by the table and numeric chart inputs.

Report owns the figures and presentation posture. A bucket total can be numeric only
when every contributor supplies that field; absence is never an additive zero.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.services.absence import is_supplied, supplied_text
from app.services.typst_values import mapping_entries


def allocation_number(value: object, *, percent: bool = False) -> Decimal | None:
    if not is_supplied(value) or isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "").removeprefix("USD").strip()
    if percent:
        text = text.removesuffix("%").strip()
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def qualified_sum(values: Iterable[Decimal | None]) -> Decimal | None:
    total = Decimal(0)
    for value in values:
        if value is None:
            return None
        total += value
    return total


@dataclass(frozen=True)
class AllocationBucket:
    label: str
    weight: Decimal | None
    value: Decimal | None

    @property
    def complete(self) -> bool:
        return self.weight is not None and self.value is not None


def allocation_buckets(rows: object) -> list[AllocationBucket]:
    buckets: dict[str, AllocationBucket] = {}
    for item in mapping_entries(rows):
        label = supplied_text(
            item.get("name") or item.get("label") or item.get("asset_class") or item.get("currency")
        )
        # Only an absent key permits the older spelling. An explicit zero or null
        # must not be overwritten by a second field.
        weight = allocation_number(item.get("weight_pct", item.get("weight")), percent=True)
        value = allocation_number(item.get("market_value"))
        previous = buckets.get(label)
        if previous is not None:
            weight = qualified_sum((previous.weight, weight))
            value = qualified_sum((previous.value, value))
        buckets[label] = AllocationBucket(label, weight, value)
    return list(buckets.values())


def folded_allocation_buckets(
    buckets: list[AllocationBucket], limit: int
) -> tuple[list[AllocationBucket], int]:
    """Keep every qualified-unknown identity; fold only fully supplied groups."""
    unknown = [bucket for bucket in buckets if not bucket.complete]
    known = sorted(
        (bucket for bucket in buckets if bucket.complete),
        key=lambda bucket: bucket.weight or Decimal(0),
        reverse=True,
    )
    if len(buckets) <= limit:
        return [*unknown, *known], 0
    kept = max(0, limit - len(unknown) - 1)
    folded = known[kept:]
    if not folded:
        return unknown, 0
    return [*unknown, *known[:kept], _folded_bucket(folded)], len(folded)


def _folded_bucket(folded: list[AllocationBucket]) -> AllocationBucket:
    return AllocationBucket(
        f"Other ({len(folded)} groups)",
        qualified_sum(bucket.weight for bucket in folded),
        qualified_sum(bucket.value for bucket in folded),
    )
