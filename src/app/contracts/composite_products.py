"""Bounded v2 consumer shapes; source products grant only explicit table authority."""

from typing import Annotated, Any, Literal

from pydantic import Field

from app.contracts.composite_linked import CompositeLinkedContent, LinkedTable
from app.contracts.composite_review import (
    CompositeCell,
    CompositeColumn,
    CompositeModel,
    CompositeReviewContent,
    CompositeReviewIdentity,
    CompositeTable,
)


class CalendarReturnPin(CompositeModel):
    kind: Literal["CALENDAR_RETURN"]
    product_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    year: int = Field(ge=1, le=9999)
    selection: dict[str, Any]


class TrailingReturnPin(CompositeModel):
    kind: Literal["TRAILING_RETURN"]
    product_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    months: int = Field(ge=1, le=120)
    selection: dict[str, Any]


class CapturedReturnProduct(CompositeModel):
    pin: Annotated[CalendarReturnPin | TrailingReturnPin, Field(discriminator="kind")]
    endpoint: Literal["/composites/twr"]
    method: Literal["POST"]
    source_response_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_response: dict[str, Any]


class ProductCell(CompositeCell):
    source_pointer: str = Field(
        pattern=r"^/(source_response|selection|report_facts|source_products)/"
    )


class ProductRow(CompositeModel):
    row_id: str = Field(min_length=1, max_length=256)
    cells: dict[str, ProductCell]


class ProductTable(CompositeModel):
    table_id: str = Field(min_length=1, max_length=31)
    title: str = Field(min_length=1, max_length=256)
    columns: list[CompositeColumn] = Field(min_length=1, max_length=32)
    rows: list[ProductRow] = Field(min_length=1, max_length=10_000)


class CompositeProductsContent(CompositeReviewIdentity):
    contract_version: Literal["composite_review.v2"]
    source_products: list[CapturedReturnProduct] = Field(min_length=1, max_length=8)
    tables: list[ProductTable] = Field(min_length=1, max_length=32)


CompositeContent = CompositeReviewContent | CompositeProductsContent | CompositeLinkedContent
CompositeOutputTable = CompositeTable | ProductTable | LinkedTable
