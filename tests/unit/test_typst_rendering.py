import hashlib
from pathlib import Path

import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.templates.registry import TemplateRegistry
from app.services.render_intake import RenderIntakeService
from app.services.typst_rendering import DOCKER_TYPST_IMAGE, TypstRenderService

GOLDEN_ROOT = Path("tests/golden/portfolio-review/v1")


def _load_golden_package() -> RenderPackage:
    return RenderPackage.model_validate_json(
        (GOLDEN_ROOT / "render-package.json").read_text(encoding="utf-8")
    )


def _outcome_review_package() -> RenderPackage:
    return RenderPackage.model_validate(
        {
            "render_package_version": "render_package.v1",
            "render_job_id": "rdr_outcome_review_v1",
            "report_job_id": "rjob_outcome_review_v1",
            "snapshot_id": "rsnap_outcome_review_v1",
            "report_type": "outcome_review",
            "report_data_contract_version": "dpm_outcome_report_input.v1",
            "template_id": "outcome-review",
            "template_version": "v1",
            "locale": "en-SG",
            "brand_variant": "private_banking",
            "output_format": "pdf",
            "render_context": {"timezone": "Asia/Singapore"},
            "report_data": {
                "title": "Post-Trade Outcome Review - PB_SG_GLOBAL_BAL_001",
                "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                "outcome_review_id": "dor_001",
                "proof_pack_id": "dpp_001",
                "rebalance_run_id": "run_001",
                "wave_id": "wave_001",
                "state": "READY",
                "overall_outcome": "Execution outcome aligned with pre-trade proof.",
                "review_window_start": "2026-04-22",
                "review_window_end": "2026-04-23",
                "dimensions": [
                    {
                        "dimension": "PERFORMANCE",
                        "state": "READY",
                        "expected": "4.10",
                        "realized": "4.22",
                        "variance": "0.12",
                        "explanation": "Realized performance exceeded expected performance.",
                    }
                ],
                "source_services": ["lotus-manage"],
                "source_hashes": {"realized": "sha256:realized"},
                "section_hashes": {"proof_pack": "sha256:proof-pack"},
                "content_hash": "sha256:report-input",
                "outcome_review_content_hash": "sha256:outcome-review",
                "redaction_policy": "NO_RAW_PAYLOADS",
            },
            "lineage_refs": ["rjob_outcome_review_v1", "dor_001", "sha256:report-input"],
            "disclosure_refs": ["outcome-review.standard-disclosures.v1"],
            "requested_by": "advisor-123",
            "correlation_id": "corr-outcome-render",
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        }
    )


def _proof_pack_package() -> RenderPackage:
    return RenderPackage.model_validate(
        {
            "render_package_version": "render_package.v1",
            "render_job_id": "rdr_proof_pack_v1",
            "report_job_id": "rjob_proof_pack_v1",
            "snapshot_id": "rsnap_proof_pack_v1",
            "report_type": "proof_pack",
            "report_data_contract_version": "dpm_proof_pack_report_input.v1",
            "template_id": "proof-pack",
            "template_version": "v1",
            "locale": "en-SG",
            "brand_variant": "private_banking",
            "output_format": "pdf",
            "render_context": {"timezone": "Asia/Singapore"},
            "report_data": {
                "title": "Pre-Trade Proof Pack - PB_SG_GLOBAL_BAL_001",
                "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                "proof_pack_id": "dpp_001",
                "mandate_id": "MANDATE_PB_SG_GLOBAL_BAL_001",
                "as_of_date": "2026-05-03",
                "state": "READY",
                "decision_summary": {
                    "recommended_action": "approve_rebalance",
                    "rationale": "Mandate drift and source readiness support rebalance approval.",
                },
                "supportability": {
                    "status": "READY",
                    "reason_codes": ["proof_pack_ready"],
                },
                "sections": [
                    {
                        "section_id": "sec_mandate",
                        "section_type": "MANDATE_CONTEXT",
                        "state": "READY",
                        "title": "Mandate context",
                        "summary": "Mandate, model, and policy evidence are aligned.",
                        "reason_codes": ["mandate_context_ready"],
                    }
                ],
                "source_hashes": {"mandate": "sha256:mandate"},
                "content_hash": "sha256:report-input",
                "proof_pack_content_hash": "sha256:proof-pack",
                "redaction_policy": "NO_RAW_PAYLOADS",
            },
            "lineage_refs": ["rjob_proof_pack_v1", "dpp_001", "sha256:report-input"],
            "disclosure_refs": ["proof-pack.standard-disclosures.v1"],
            "requested_by": "advisor-123",
            "correlation_id": "corr-proof-pack-render",
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        }
    )


def _build_service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


def test_typst_render_service_renders_golden_portfolio_review_pdf() -> None:
    service = _build_service()
    expected_pdf = (GOLDEN_ROOT / "expected.pdf").read_bytes()

    result = service.render(_load_golden_package())

    assert result.attempt.status.value == "rendered"
    assert result.artifact_bytes.startswith(b"%PDF")
    assert result.diagnostic.artifact_sha256 == hashlib.sha256(result.artifact_bytes).hexdigest()
    assert (
        result.diagnostic.bounded_determinism_fingerprint
        == service._compute_bounded_determinism_fingerprint(expected_pdf)
    )
    assert result.diagnostic.mime_type == "application/pdf"
    assert result.diagnostic.output_size_bytes == len(result.artifact_bytes)
    assert result.diagnostic.determinism_mode == "bounded_runtime_envelope"


def test_typst_render_service_is_deterministic_within_runtime_envelope() -> None:
    service = _build_service()
    render_package = _load_golden_package()

    first = service.render(render_package)
    second = service.render(render_package)

    assert (
        first.diagnostic.bounded_determinism_fingerprint
        == second.diagnostic.bounded_determinism_fingerprint
    )


def test_typst_render_service_rejects_missing_required_report_data() -> None:
    service = _build_service()
    render_package = _load_golden_package()
    incomplete_report_data = dict(render_package.report_data)
    incomplete_report_data.pop("client_name")

    invalid_package = render_package.model_copy(update={"report_data": incomplete_report_data})

    with pytest.raises(ValueError, match="missing required report_data field: client_name"):
        service.render(invalid_package)


def test_typst_render_service_rejects_empty_review_observations() -> None:
    service = _build_service()
    render_package = _load_golden_package()
    invalid_package = render_package.model_copy(
        update={
            "report_data": {
                **render_package.report_data,
                "review_observations": [],
            }
        }
    )

    with pytest.raises(ValueError, match="review_observations must be a non-empty list"):
        service.render(invalid_package)


def test_typst_render_service_builds_richer_portfolio_review_context() -> None:
    service = _build_service()
    template_context = service._build_portfolio_review_context(_load_golden_package())

    assert "#cover-page()" in template_context["REPORT_SECTIONS"]
    assert "#appendix-page()" in template_context["REPORT_SECTIONS"]
    assert template_context["REVIEW_PERIOD_LABEL"] == "YTD"
    assert template_context["TOP_CONTRIBUTOR_NAME"] == "Global Equity Sleeve"
    assert "lotus-core, lotus-performance, lotus-risk" in template_context["SOURCE_SERVICES"]
    assert "#period-row(" in template_context["PERFORMANCE_PERIOD_ROWS"]
    assert "performance-summary-cell(" in template_context["PERFORMANCE_SUMMARY_TABLE"]
    assert "performance-chart-row(" in template_context["PERFORMANCE_MONTHLY_CHART_ROWS"]
    assert "#performance-chart-row(" in template_context["PERFORMANCE_ANNUAL_CHART_ROWS"]
    assert "#performance-detail-row(" in template_context["PERFORMANCE_MONTHLY_TABLE_ROWS"]
    assert "#performance-bar-row(" in template_context["PERFORMANCE_BAR_ROWS"]
    assert "assets/charts/performance_12m.svg" in template_context["PERFORMANCE_12M_CHART_SECTION"]
    assert "#holding-row(" in template_context["HOLDING_ROWS"]
    assert "#allocation-row(" in template_context["HOLDING_BAR_ROWS"]
    assert "#compact-allocation-row(" in template_context["ASSET_CLASS_ROWS"]
    assert (
        "assets/charts/allocation_asset_class.svg"
        in template_context["ALLOCATION_DONUT_CHART_SECTION"]
    )
    assert "#compact-allocation-row(" in template_context["SUPPLEMENTAL_ALLOCATION_ROWS"]
    assert "#dense-position-row(" in template_context["DENSE_POSITION_ROWS"]
    assert "#dense-transaction-row(" in template_context["DENSE_TRANSACTION_ROWS"]
    assert template_context["TRANSACTION_PERIOD_LABEL"] == "From 01.01.2026 to 23.04.2026"
    assert template_context["SUPPLEMENTAL_ALLOCATION_TITLE"] == "By currency"
    assert "Equity" in template_context["ASSET_CLASS_ROWS"]
    assert "USD" in template_context["SUPPLEMENTAL_ALLOCATION_ROWS"]
    assert "EQ-1" in template_context["DENSE_POSITION_ROWS"]
    assert "US0000000001" in template_context["DENSE_POSITION_ROWS"]
    assert "102.35;USD;8118290.51;2024-01-15" in template_context["DENSE_POSITION_ROWS"]
    assert "9140740.73;0.00" in template_context["DENSE_POSITION_ROWS"]
    assert "Cost value" not in template_context["DENSE_POSITION_ROWS"]
    assert "Average weight" not in template_context["DENSE_POSITION_ROWS"]
    assert "TXN-20260109-BUY-001" in template_context["DENSE_TRANSACTION_ROWS"]
    assert "INST-EQ-1" in template_context["DENSE_TRANSACTION_ROWS"]
    assert "Reference TXN-20260109-BUY-001" in template_context["DENSE_TRANSACTION_ROWS"]
    assert "Instrument INST-EQ-1" in template_context["DENSE_TRANSACTION_ROWS"]
    assert "09.01.2026;09.01.2026" in template_context["DENSE_TRANSACTION_ROWS"]
    assert "NAV 102.35;;450000.00;" in template_context["DENSE_TRANSACTION_ROWS"]
    assert "#review-note(" in template_context["OBSERVATION_NOTES"]


def test_typst_render_service_builds_outcome_review_context() -> None:
    service = _build_service()
    template_context = service._build_outcome_review_context(_outcome_review_package())

    assert template_context["PORTFOLIO_ID"] == "PB_SG_GLOBAL_BAL_001"
    assert template_context["OUTCOME_REVIEW_ID"] == "dor_001"
    assert "dimension-row(" in template_context["DIMENSION_ROWS"]
    assert "0.12" in template_context["DIMENSION_ROWS"]
    assert "lotus-manage" in template_context["SOURCE_SERVICES"]
    assert "sha256:report-input" in template_context["CONTENT_HASH"]


def test_typst_render_service_routes_template_context_by_report_type() -> None:
    service = _build_service()

    outcome_context = service._build_template_context(_outcome_review_package())
    proof_pack_context = service._build_template_context(_proof_pack_package())

    assert outcome_context["OUTCOME_REVIEW_ID"] == "dor_001"
    assert proof_pack_context["PROOF_PACK_ID"] == "dpp_001"


def test_typst_render_service_builds_proof_pack_context() -> None:
    service = _build_service()
    template_context = service._build_proof_pack_context(_proof_pack_package())

    assert template_context["PORTFOLIO_ID"] == "PB_SG_GLOBAL_BAL_001"
    assert template_context["PROOF_PACK_ID"] == "dpp_001"
    assert template_context["SUPPORTABILITY_STATUS"] == "READY"
    assert "section-row(" in template_context["SECTION_ROWS"]
    assert "Mandate context" in template_context["SECTION_ROWS"]
    assert "sha256:report-input" in template_context["CONTENT_HASH"]


def test_typst_render_service_rejects_missing_proof_pack_report_data() -> None:
    service = _build_service()
    render_package = _proof_pack_package()
    incomplete_report_data = dict(render_package.report_data)
    incomplete_report_data.pop("supportability")
    invalid_package = render_package.model_copy(update={"report_data": incomplete_report_data})

    with pytest.raises(ValueError, match="missing required report_data field: supportability"):
        service.render(invalid_package)


def test_typst_render_service_rejects_invalid_proof_pack_sections() -> None:
    service = _build_service()
    render_package = _proof_pack_package()
    invalid_package = render_package.model_copy(
        update={"report_data": {**render_package.report_data, "sections": "not-a-list"}}
    )

    with pytest.raises(ValueError, match="sections must be a list"):
        service.render(invalid_package)


def test_typst_render_service_uses_proof_pack_fallback_rows() -> None:
    service = _build_service()

    assert "No section evidence supplied." in service._render_proof_pack_section_rows([])
    assert "not_available" in service._render_key_value_rows({})


def test_typst_render_service_renders_proof_pack_pdf() -> None:
    service = _build_service()

    result = service.render(_proof_pack_package())

    assert result.attempt.status.value == "rendered"
    assert result.artifact_bytes.startswith(b"%PDF")
    assert result.diagnostic.template_id == "proof-pack"
    assert result.diagnostic.artifact_sha256 == hashlib.sha256(result.artifact_bytes).hexdigest()


def test_template_registry_accepts_outcome_review_template() -> None:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    manifest = registry.resolve_for_new_render(_outcome_review_package())

    assert manifest.template_id == "outcome-review"
    assert manifest.supported_report_types == ["outcome_review"]


def test_template_registry_accepts_proof_pack_template() -> None:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    manifest = registry.resolve_for_new_render(_proof_pack_package())

    assert manifest.template_id == "proof-pack"
    assert manifest.supported_report_types == ["proof_pack"]
    assert manifest.supported_report_data_contract_versions == ["dpm_proof_pack_report_input.v1"]


def test_typst_render_service_builds_selected_section_sequence() -> None:
    service = _build_service()
    render_package = _load_golden_package().model_copy(
        update={
            "render_context": {
                "timezone": "Asia/Singapore",
                "sections": ["performance", "asset-allocation", "transactions"],
            }
        }
    )

    template_context = service._build_portfolio_review_context(render_package)

    assert template_context["REPORT_SECTIONS"] == (
        "#performance-page()\n#pagebreak()\n#allocation-page()\n#pagebreak()\n#transactions-page()"
    )


def test_typst_render_service_renders_selected_sections_only() -> None:
    service = _build_service()
    render_package = _load_golden_package().model_copy(
        update={
            "render_context": {
                "timezone": "Asia/Singapore",
                "sections": ["performance"],
            }
        }
    )

    result = service.render(render_package)

    assert result.artifact_bytes.startswith(b"%PDF")
    assert result.diagnostic.output_size_bytes == len(result.artifact_bytes)
    assert len(result.artifact_bytes) < len((GOLDEN_ROOT / "expected.pdf").read_bytes())


def test_typst_render_service_helper_fallbacks_cover_sparse_structures() -> None:
    service = _build_service()

    assert service._string_list("not-a-list") == []
    assert service._string_list([" lot1 ", "", "lot2"]) == ["lot1", "lot2"]
    assert service._mapping("not-a-mapping") == {}
    assert service._requested_section_keys(
        ["detailed-positions", "asset-allocation", "unknown", "asset_allocation"]
    ) == ["positions", "allocation"]
    assert (
        "No 12-month performance series is available"
        in service._render_performance_chart_section({})
    )
    assert "No allocation breakdown is available" in service._render_allocation_chart_section({})
    assert "No governed observations available." in service._render_observation_notes("bad")
    assert "No governed performance periods available." in service._render_performance_period_rows(
        "bad"
    )
    assert "No governed performance periods available." in service._render_performance_period_rows(
        [123]
    )
    assert "No governed performance bars available." in service._render_performance_bar_rows("bad")
    assert "No governed performance bars available." in service._render_performance_bar_rows([123])
    performance_summary_fallback = service._render_performance_summary_table("bad")
    assert "No governed performance summary available." in performance_summary_fallback
    assert (
        "No governed performance summary available."
        in service._render_performance_summary_table([123])
    )
    assert "No performance history available." in service._render_performance_chart_rows("bad")
    assert "No performance history available." in service._render_performance_chart_rows([123])
    assert "No monthly performance detail available." in service._render_performance_detail_rows(
        "bad"
    )
    assert "No monthly performance detail available." in service._render_performance_detail_rows(
        [123]
    )
    assert "No governed holdings available." in service._render_holding_rows("bad")
    assert "No governed holdings available." in service._render_holding_rows([123])
    assert "No governed allocation rows available." in service._render_holding_bar_rows("bad")
    assert "No position detail available." in service._render_dense_position_rows("bad")
    assert "No position detail available." in service._render_dense_position_rows([123])
    assert "No transaction detail available." in service._render_dense_transaction_rows("bad")
    assert "No transaction detail available." in service._render_dense_transaction_rows([123])
    assert "No allocation detail available." in service._render_allocation_breakdown_rows("bad")
    assert "No allocation detail available." in service._render_allocation_breakdown_rows([123])


def test_typst_render_service_renders_supplemental_allocation_views_with_priority() -> None:
    service = _build_service()

    title, rows = service._supplemental_allocation_view(
        {
            "by_region": [
                {"name": "North America", "weight_pct": "62.00%", "market_value": "620000.00"}
            ],
            "by_currency": [],
        }
    )

    assert title == "By region"
    assert "#compact-allocation-row(" in rows
    assert "North America" in rows


def test_typst_render_service_allocation_view_falls_back_when_no_breakdowns_exist() -> None:
    service = _build_service()

    title, rows = service._supplemental_allocation_view({})

    assert title == "Allocation detail"
    assert "No allocation detail available." in rows


def test_typst_render_service_returns_empty_messages_when_sequences_have_no_mapping_rows() -> None:
    service = _build_service()

    assert "No governed holdings available." in service._render_holding_rows([123, 456])
    assert "No governed allocation rows available." in service._render_holding_bar_rows([123, 456])
    assert "No position detail available." in service._render_dense_position_rows([123, 456])
    assert "No transaction detail available." in service._render_dense_transaction_rows([123, 456])


def test_typst_render_service_numeric_fallback_helpers_cover_invalid_inputs() -> None:
    assert TypstRenderService._percent_width_token("bad") == "8%"
    assert TypstRenderService._performance_width_token("bad") == "8%"
    assert TypstRenderService._parse_percent("bad") == 0.0
    assert TypstRenderService._parse_number("bad") == 0.0


def test_typst_render_service_marks_template_failure_when_typst_compile_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_service()
    render_package = _load_golden_package()

    class _FailedProcess:
        returncode = 1
        stderr = "compile failed"
        stdout = ""

    monkeypatch.setattr(
        service,
        "_build_compile_command",
        lambda **_: ["typst", "compile", "render.typ", "rendered.pdf"],
    )
    monkeypatch.setattr(
        "app.services.typst_rendering.subprocess.run",
        lambda *_, **__: _FailedProcess(),
    )

    with pytest.raises(RuntimeError, match="compile failed"):
        service.render(render_package)


def test_typst_render_service_uses_docker_fallback_when_local_typst_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _build_service()
    source_path = tmp_path / "render.typ"
    output_path = tmp_path / "rendered.pdf"

    def _fake_which(binary: str) -> str | None:
        if binary == "typst":
            return None
        if binary == "docker":
            return "/usr/bin/docker"
        return None

    monkeypatch.setattr("app.services.typst_rendering.shutil.which", _fake_which)

    command = service._build_compile_command(
        workspace=tmp_path,
        source_path=source_path,
        output_path=output_path,
    )

    assert command[:5] == [
        "/usr/bin/docker",
        "run",
        "--rm",
        "-v",
        f"{tmp_path.resolve()}:/workspace",
    ]
    assert DOCKER_TYPST_IMAGE in command


def test_typst_render_service_uses_relative_source_path_for_nested_template_under_docker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _build_service()
    source_path = tmp_path / "template" / "main.typ"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("test", encoding="utf-8")
    output_path = tmp_path / "rendered.pdf"

    def _fake_which(binary: str) -> str | None:
        if binary == "typst":
            return None
        if binary == "docker":
            return "/usr/bin/docker"
        return None

    monkeypatch.setattr("app.services.typst_rendering.shutil.which", _fake_which)

    command = service._build_compile_command(
        workspace=tmp_path,
        source_path=source_path,
        output_path=output_path,
    )

    assert command[-2:] == ["template/main.typ", "rendered.pdf"]


def test_typst_render_service_prefers_docker_governed_runtime_when_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _build_service()
    source_path = tmp_path / "render.typ"
    output_path = tmp_path / "rendered.pdf"

    def _fake_which(binary: str) -> str | None:
        if binary == "docker":
            return "/usr/bin/docker"
        if binary == "typst":
            return "/usr/local/bin/typst"
        return None

    monkeypatch.setattr("app.services.typst_rendering.shutil.which", _fake_which)

    command = service._build_compile_command(
        workspace=tmp_path,
        source_path=source_path,
        output_path=output_path,
    )

    assert command[:2] == ["/usr/bin/docker", "run"]
    assert DOCKER_TYPST_IMAGE in command


def test_typst_render_service_uses_local_typst_when_docker_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _build_service()
    source_path = tmp_path / "render.typ"
    output_path = tmp_path / "rendered.pdf"

    def _fake_which(binary: str) -> str | None:
        if binary == "docker":
            return None
        if binary == "typst":
            return "/usr/local/bin/typst"
        return None

    monkeypatch.setattr("app.services.typst_rendering.shutil.which", _fake_which)

    command = service._build_compile_command(
        workspace=tmp_path,
        source_path=source_path,
        output_path=output_path,
    )

    assert command == [
        "/usr/local/bin/typst",
        "compile",
        str(source_path),
        str(output_path),
    ]


def test_typst_render_service_raises_when_no_runtime_is_available(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _build_service()

    monkeypatch.setattr("app.services.typst_rendering.shutil.which", lambda _: None)

    with pytest.raises(RuntimeError, match="Typst runtime is unavailable"):
        service._build_compile_command(
            workspace=tmp_path,
            source_path=tmp_path / "render.typ",
            output_path=tmp_path / "rendered.pdf",
        )


def test_typst_render_service_materializes_modular_template_directory(
    tmp_path: Path,
) -> None:
    service = _build_service()
    template_directory = tmp_path / "source-template"
    template_directory.mkdir()
    template_root = template_directory / "main.typ"
    partial = template_directory / "_partial.typ"
    template_root.write_text('#import "_partial.typ": payload\n#payload()', encoding="utf-8")
    partial.write_text("#let payload() = [${CLIENT_NAME}]", encoding="utf-8")

    render_package = _load_golden_package()
    source_path = service._materialize_template(
        template_root=template_root,
        workspace=tmp_path / "workspace",
        render_package=render_package,
        template_context={"CLIENT_NAME": "Alex Tan"},
        determinism_statement="deterministic",
    )

    materialized_partial = source_path.parent / "_partial.typ"
    assert source_path.exists()
    assert materialized_partial.exists()
    assert "Alex Tan" in materialized_partial.read_text(encoding="utf-8")
