"""Enforce the agreed v2 product table identities and exact source-pointer matrix."""

from app.contracts.composite_products import (
    CapturedReturnProduct,
    CompositeProductsContent,
    ProductRow,
    ProductTable,
)
from app.contracts.composite_review import CompositeCell

PRODUCT_COLUMNS = (
    ("product", "Product key", "pin/product_key"),
    ("kind", "Horizon kind", "pin/kind"),
    ("period_start", "Inclusive start", "pin/selection/period_start"),
    ("period_end", "Inclusive end", "pin/selection/period_end"),
    ("return_view", "Fee view", "pin/selection/return_view"),
    ("currency", "Currency", "pin/selection/reporting_currency"),
    ("return", "Source horizon return", "source_response/cumulative_return"),
    ("status", "Source status", "source_response/status"),
    ("methodology", "Source methodology", "source_response/methodology"),
    ("engine_version", "Source engine", "pin/selection/engine_version"),
    ("response_digest", "Captured response digest", "source_response_digest"),
)


def validate_product_tables(content: CompositeProductsContent) -> None:
    tables = {table.table_id: table for table in content.tables}
    for name, kind in (
        ("AnnualReturns", "CALENDAR_RETURN"),
        ("TrailingReturns", "TRAILING_RETURN"),
    ):
        products = [(i, p) for i, p in enumerate(content.source_products) if p.pin.kind == kind]
        table = tables.get(name)
        _validate_kind_table(name, table, products)


def _validate_kind_table(
    name: str, table: ProductTable | None, products: list[tuple[int, CapturedReturnProduct]]
) -> None:
    if not products:
        _validate_absent_product_table(name, table)
        return
    if table is None:
        raise ValueError("composite_product_table_missing")
    _validate_product_columns(table)
    if [row.row_id for row in table.rows] != [p.pin.product_key for _, p in products]:
        raise ValueError("composite_product_table_population_conflict")
    for row, (index, product) in zip(table.rows, products, strict=True):
        _validate_product_row(row, index, product)


def _validate_product_row(row: ProductRow, index: int, product: CapturedReturnProduct) -> None:
    expected = {key: f"/source_products/{index}/{path}" for key, _, path in PRODUCT_COLUMNS}
    if {key: cell.source_pointer for key, cell in row.cells.items()} != expected:
        raise ValueError("composite_product_table_pointer_conflict")
    for cell in row.cells.values():
        _validate_product_availability(cell, product)


def _validate_product_availability(cell: CompositeCell, product: CapturedReturnProduct) -> None:
    availability = "UNAVAILABLE" if cell.canonical_value is None else "AVAILABLE"
    reasons = (
        (product.source_response.get("reason_codes") or ["SOURCE_VALUE_UNAVAILABLE"])
        if cell.canonical_value is None
        else []
    )
    if cell.availability != availability or cell.reason_codes != reasons:
        raise ValueError("composite_product_table_availability_conflict")


def _validate_product_columns(table: ProductTable) -> None:
    if [(column.column_id, column.label) for column in table.columns] != [
        (key, label) for key, label, _ in PRODUCT_COLUMNS
    ]:
        raise ValueError("composite_product_table_columns_conflict")
    for column in table.columns:
        financial = column.column_id == "return"
        if (column.value_type, column.display_decimal_places) != (
            "DECIMAL_RETURN" if financial else "TEXT",
            2 if financial else None,
        ):
            raise ValueError("composite_product_table_policy_conflict")


def _validate_absent_product_table(name: str, table: ProductTable | None) -> None:
    if name == "TrailingReturns":
        if table is not None:
            raise ValueError("composite_product_table_unrequested")
        return
    _validate_uncaptured_annual(table)


def _validate_uncaptured_annual(table: ProductTable | None) -> None:
    if table is None or len(table.rows) != 1:
        raise ValueError("composite_product_uncaptured_table_missing")
    row = table.rows[0]
    if row.row_id != "unavailable" or set(row.cells) != {"metric", "value", "reason_code"}:
        raise ValueError("composite_product_uncaptured_table_conflict")
    if any(
        cell.source_pointer != f"/report_facts/uncaptured/AnnualReturns/{key}"
        for key, cell in row.cells.items()
    ):
        raise ValueError("composite_product_uncaptured_table_conflict")
    value = row.cells["value"]
    if (value.canonical_value, value.availability, value.reason_codes) != (
        None,
        "UNAVAILABLE",
        ["SOURCE_PRODUCT_NOT_CAPTURED"],
    ):
        raise ValueError("composite_product_uncaptured_table_conflict")
