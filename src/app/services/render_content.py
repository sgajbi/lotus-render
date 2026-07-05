from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.contracts.render_package import RenderPackage


class RenderContentValidationError(ValueError):
    pass


class _RenderContentModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    def as_report_data(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


class PortfolioReviewRenderContent(_RenderContentModel):
    client_name: str
    portfolio_name: str
    as_of_date: str
    currency: str
    total_value: str
    summary_paragraph: str
    review_observations: list[Any] = Field(min_length=1)

    @field_validator("review_observations")
    @classmethod
    def _review_observations_non_empty(cls, value: list[Any]) -> list[Any]:
        if not value:
            raise ValueError("review_observations must be a non-empty list")
        return value


class ProofPackRenderContent(_RenderContentModel):
    title: str
    portfolio_id: str
    proof_pack_id: str
    state: str
    decision_summary: dict[str, Any]
    supportability: dict[str, Any]
    sections: list[Any]
    content_hash: str
    proof_pack_content_hash: str


class OutcomeReviewRenderContent(_RenderContentModel):
    title: str
    portfolio_id: str
    outcome_review_id: str
    state: str
    overall_outcome: str
    dimensions: list[Any]
    content_hash: str


class RebalanceWaveRenderContent(_RenderContentModel):
    title: str
    wave_id: str
    wave_state: str
    trigger_type: str
    aggregate_metrics: dict[str, Any]
    supportability: dict[str, Any]
    proof_pack_posture: dict[str, Any]
    items: list[Any]
    content_hash: str
    wave_content_hash: str


ContentModel = TypeVar("ContentModel", bound=_RenderContentModel)


def parse_portfolio_review_content(render_package: RenderPackage) -> PortfolioReviewRenderContent:
    return _parse_content(
        render_package,
        expected_contract_version="portfolio_review.v1",
        model=PortfolioReviewRenderContent,
    )


def parse_proof_pack_content(render_package: RenderPackage) -> ProofPackRenderContent:
    return _parse_content(
        render_package,
        expected_contract_version="dpm_proof_pack_report_input.v1",
        model=ProofPackRenderContent,
    )


def parse_outcome_review_content(render_package: RenderPackage) -> OutcomeReviewRenderContent:
    return _parse_content(
        render_package,
        expected_contract_version="dpm_outcome_report_input.v1",
        model=OutcomeReviewRenderContent,
    )


def parse_rebalance_wave_content(render_package: RenderPackage) -> RebalanceWaveRenderContent:
    return _parse_content(
        render_package,
        expected_contract_version="dpm_wave_report_input.v1",
        model=RebalanceWaveRenderContent,
    )


def _parse_content(
    render_package: RenderPackage,
    *,
    expected_contract_version: str,
    model: type[ContentModel],
) -> ContentModel:
    if render_package.report_data_contract_version != expected_contract_version:
        raise RenderContentValidationError(
            "unsupported report_data_contract_version for render content adapter"
        )
    try:
        return model.model_validate(render_package.report_data)
    except ValidationError as exc:
        raise RenderContentValidationError(_validation_message(exc)) from exc


def _validation_message(exc: ValidationError) -> str:
    first_error = exc.errors(include_input=False)[0]
    loc = ".".join(str(part) for part in first_error.get("loc", ()))
    error_type = str(first_error.get("type", ""))
    if error_type == "missing":
        return f"missing required report_data field: {loc}"
    if error_type == "list_type":
        return f"{loc} must be a list"
    message = str(first_error.get("msg", "invalid value"))
    if loc == "review_observations" and "at least 1 item" in message:
        return "review_observations must be a non-empty list"
    return f"invalid report_data field: {loc}"
