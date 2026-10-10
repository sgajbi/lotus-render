"""Strict additive financial source context; original v1-v7 models stay frozen."""

from typing import Any, Literal

from pydantic import Field

from app.contracts.composite_products import CapturedReturnProduct
from app.contracts.composite_review import (
    CompositeCell,
    CompositeColumn,
    CompositeModel,
    CompositeReviewIdentity,
)
from app.contracts.composite_selection import Digest, Identifier


class DefinitionPin(CompositeModel):
    definition_version: Identifier
    content_hash: Digest
    response_digest: Digest


class MembershipPin(CompositeModel):
    membership_revision: Identifier
    content_hash: Digest
    response_digest: Digest


class SourceContextSelection(CompositeModel):
    definition: DefinitionPin
    since_inception: bool = False
    memberships: list[MembershipPin] = Field(default_factory=list, max_length=2)


class CapturedDefinition(CompositeModel):
    pin: DefinitionPin
    endpoint: str
    method: Literal["GET"]
    source_response_digest: Digest
    source_response: dict[str, Any]


class CapturedMembership(CompositeModel):
    pin: MembershipPin
    endpoint: str
    method: Literal["GET"]
    source_response_digest: Digest
    source_response: dict[str, Any]


class SourceContextCell(CompositeCell):
    source_pointer: str = Field(
        pattern=r"^/(source_response|selection|report_facts|source_products|definition|supplied_memberships)/"
    )


class SourceContextRow(CompositeModel):
    row_id: str = Field(min_length=1, max_length=256)
    cells: dict[str, SourceContextCell]


class SourceContextTable(CompositeModel):
    table_id: str = Field(min_length=1, max_length=31)
    title: str = Field(min_length=1, max_length=256)
    columns: list[CompositeColumn] = Field(min_length=1, max_length=32)
    rows: list[SourceContextRow] = Field(min_length=1, max_length=10_000)


class CompositeSourceContextContent(CompositeReviewIdentity):
    contract_version: Literal["composite_review.v8"]
    definition: CapturedDefinition
    source_context: SourceContextSelection
    source_products: list[CapturedReturnProduct] = Field(default_factory=list, max_length=8)
    supplied_memberships: list[CapturedMembership] = Field(max_length=2)
    tables: list[SourceContextTable] = Field(min_length=1, max_length=32)
