"""Reconcile admitted calendar/trailing captures to the retained primary pin vector."""

import calendar
import hashlib
import json
import re
from datetime import date
from typing import Any

from app.contracts.composite_products import CapturedReturnProduct, CompositeProductsContent
from app.contracts.composite_selection import CompositePinnedSelection, CompositeWindowPin
from app.services.composite_workbook.pinned_identity import validate_source_identity

PRODUCT_RETURN_POINTER = re.compile(
    r"^/source_products/(?:0|[1-9]\d*)/source_response/cumulative_return$"
)
_PRODUCT_TEXT_POINTER = re.compile(
    r"^/source_products/(?:0|[1-9]\d*)/(?:source_response_digest|source_response/(?:status|"
    r"methodology)|pin/(?:product_key|kind|selection/(?:period_start|period_end|"
    r"reporting_currency|return_view|engine_version)))$"
)


def response_digest(source: dict[str, Any]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(source, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )


def validate_response_digest(
    selection: dict[str, Any], source: dict[str, Any], digest: str
) -> None:
    if response_digest(source) != digest or digest != selection.get("response_digest"):
        raise ValueError("composite_source_digest_conflict")


def validate_product_pointer(pointer: str, value_type: str) -> None:
    if not pointer.startswith("/source_products/"):
        return
    allowed = _PRODUCT_TEXT_POINTER if value_type == "TEXT" else PRODUCT_RETURN_POINTER
    if allowed.fullmatch(pointer) is None:
        raise ValueError("composite_product_pointer_not_authorized")


def validate_source_products(content: CompositeProductsContent) -> None:
    products = content.source_products
    keys = [product.pin.product_key for product in products]
    if len(keys) != len(set(keys)):
        raise ValueError("composite_product_identity_duplicated")
    for product in products:
        selection = product.pin.selection
        typed = CompositePinnedSelection.model_validate_json(json.dumps(selection))
        validate_response_digest(selection, product.source_response, product.source_response_digest)
        validate_source_identity(selection, product.source_response, content.qualification)
        _validate_product_return(product.source_response)
        _validate_product_context(content.selection, selection)
        _validate_product_windows(content.selection, product, typed)


def _validate_product_return(source: dict[str, Any]) -> None:
    value = source.get("cumulative_return")
    if value is not None and not isinstance(value, str):
        raise ValueError("composite_product_return_not_literal")
    if source.get("status") == "READY" and value is None:
        raise ValueError("composite_product_ready_return_missing")


def _validate_product_context(primary: dict[str, Any], selection: dict[str, Any]) -> None:
    keys = ("tenant_id", "composite_id", "reporting_currency", "return_view", "methodology")
    if any(primary[key] != selection[key] for key in keys):
        raise ValueError("composite_product_context_conflict")


def _validate_product_windows(
    primary: dict[str, Any], product: CapturedReturnProduct, selection: CompositePinnedSelection
) -> None:
    _require_complete_months(selection.windows)
    _require_product_horizon(primary, product, selection)
    _require_primary_subvector(primary["windows"], product.pin.selection["windows"])


def _require_complete_months(windows: list[CompositeWindowPin]) -> None:
    for window in windows:
        end = calendar.monthrange(window.period_start.year, window.period_start.month)[1]
        if window.period_start.day != 1 or window.period_end != date(
            window.period_start.year, window.period_start.month, end
        ):
            raise ValueError("composite_product_month_incomplete")


def _require_product_horizon(
    primary: dict[str, Any], product: CapturedReturnProduct, selection: CompositePinnedSelection
) -> None:
    pin, windows = product.pin, selection.windows
    if pin.kind == "CALENDAR_RETURN":
        if (selection.period_start, selection.period_end, len(windows)) != (
            date(pin.year, 1, 1),
            date(pin.year, 12, 31),
            12,
        ):
            raise ValueError("composite_product_calendar_horizon_conflict")
    elif len(windows) != pin.months or selection.period_end.isoformat() != primary["period_end"]:
        raise ValueError("composite_product_trailing_horizon_conflict")


def _require_primary_subvector(
    primary_windows: list[dict[str, Any]], raw_windows: list[dict[str, Any]]
) -> None:
    starts = [index for index, window in enumerate(primary_windows) if window == raw_windows[0]]
    if not starts or primary_windows[starts[0] : starts[0] + len(raw_windows)] != raw_windows:
        raise ValueError("composite_product_primary_vector_conflict")
