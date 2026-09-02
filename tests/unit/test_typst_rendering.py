import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from app.contracts.render_package import RenderPackage
from app.core.settings import Settings
from app.domain.render_attempts.models import RenderFailureCategory
from app.domain.templates.registry import TemplateRegistry
from app.services.compile_failures import classify_compile_failure
from app.services.render_intake import RenderIntakeService
from app.services.render_ports import RenderEngineTimeoutError
from app.services.section_selection import SectionSelectionError
from app.services.typst_contexts import (
    build_outcome_review_context,
    build_portfolio_review_context,
    build_proof_pack_context,
    build_wave_context,
    requested_section_keys,
)
from app.services.typst_fragments import (
    render_advisor_memo_section_blocks,
    render_advisory_disclosure_blocks,
    render_advisory_narrative_blocks,
    render_key_value_rows,
    render_outcome_dimension_rows,
    render_proof_pack_section_rows,
    render_source_lineage_rows,
    render_wave_event_rows,
    render_wave_item_rows,
)
from app.services.typst_rendering import (
    COMPILE_ADDRESS_SPACE_LIMIT_KB,
    COMPILE_CPU_SECONDS,
    DOCKER_CONTAINER_NAME_PREFIX,
    DOCKER_ISOLATION_FLAGS,
    DOCKER_TYPST_IMAGE,
    TypstRenderService,
    _bounded_local_command,
    ungoverned_runtime_reason,
)
from app.services.typst_tables import (
    render_allocation_breakdown_rows,
    render_allocation_chart_section,
    render_allocation_dimension_blocks,
    render_holding_bar_rows,
    render_observation_notes,
    render_performance_chart_rows,
    render_performance_chart_section,
    render_performance_detail_rows,
    render_performance_period_rows,
    render_performance_summary_table,
    render_position_table,
    render_transaction_table,
)
from app.services.typst_values import (
    escape_typst_text,
    mapping,
    parse_number,
    parse_percent,
    performance_bar_domain,
    performance_bar_geometry,
    string_list,
    weight_width_token,
)

GOLDEN_ROOT = Path("tests/golden")
GOLDEN_PRODUCER_FIXTURES = GOLDEN_ROOT / "producer-fixtures.v1.json"


def _golden_root(template_id: str, template_version: str = "v1") -> Path:
    return GOLDEN_ROOT / template_id / template_version


def _load_golden_package_for(template_id: str, template_version: str = "v1") -> RenderPackage:
    return RenderPackage.model_validate_json(
        (_golden_root(template_id, template_version) / "render-package.json").read_text(
            encoding="utf-8"
        )
    )


def _load_golden_fixture_packages() -> list[tuple[dict[str, str], RenderPackage]]:
    manifest = json.loads(GOLDEN_PRODUCER_FIXTURES.read_text(encoding="utf-8"))
    return [
        (
            fixture,
            RenderPackage.model_validate_json(
                Path(fixture["package_path"]).read_text(encoding="utf-8")
            ),
        )
        for fixture in manifest["fixtures"]
    ]


def _load_golden_package() -> RenderPackage:
    return _load_golden_package_for("portfolio-review")


def _portfolio_review_package_with_reviewed_advisory_narrative() -> RenderPackage:
    render_package = _load_golden_package()
    report_data = deepcopy(render_package.report_data)
    report_data["reviewed_advisory_narrative"] = {
        "status": "included",
        "package_status": "INCLUDED_REVIEWED_NARRATIVE",
        "usage": "advisor_report_package",
        "proposal_id": "adv_prop_001",
        "proposal_version_no": 3,
        "narrative_id": "adv_narrative_001",
        "narrative_status": "REVIEWED",
        "audience": "ADVISOR",
        "policy_version": "proposal-narrative-policy.v1",
        "review": {
            "review_id": "adv_review_001",
            "review_state": "APPROVED_FOR_ADVISOR_USE",
            "reviewed_at": "2026-05-21T09:15:00Z",
            "reviewed_by": "head-advisor.sg@example.com",
        },
        "source_lineage": {
            "source_narrative_hash": "sha256:reviewed-narrative",
            "proposal_hash": "sha256:proposal",
            "proposal_version_hash": "sha256:proposal-version",
        },
        "sections": [
            {
                "section_id": "suitability_summary",
                "title": "Suitability summary",
                "body": (
                    "The proposal keeps the balanced mandate within approved risk posture while "
                    "addressing liquidity and concentration observations."
                ),
                "source_refs": [{"source_id": "proposal-lineage-001"}],
            }
        ],
        "disclosures": [
            {
                "disclosure_id": "proposal_narrative.advisor_use_only.v1",
                "text": "Advisor use only. Client distribution requires separate approval.",
            }
        ],
    }
    return render_package.model_copy(
        update={
            "report_data": report_data,
            "disclosure_refs": [
                *render_package.disclosure_refs,
                "proposal_narrative.advisor_use_only.v1",
            ],
        }
    )


def _portfolio_review_package_with_advisor_proposal_memo() -> RenderPackage:
    render_package = _load_golden_package()
    report_data = deepcopy(render_package.report_data)
    report_data["advisor_proposal_memo"] = {
        "status": "included",
        "package_status": "INCLUDED_ADVISOR_PROPOSAL_MEMO",
        "usage": "REPORT_REQUEST_APPROVED_ADVISOR_MEMO",
        "proposal_id": "adv_prop_001",
        "proposal_version_no": 3,
        "memo_id": "memo_001",
        "memo_status": "READY",
        "memo_hash": "sha256:memo",
        "source_input_hash": "sha256:source",
        "client_ready_publication": "BLOCKED",
        "review": {
            "review_event_id": "pme_review_001",
            "review_action": "APPROVE_FOR_ADVISOR_USE",
            "reviewed_at": "2026-05-21T09:15:00Z",
            "reviewed_by": "head-advisor.sg@example.com",
        },
        "sections": [
            {
                "section_id": "EXECUTIVE_SUMMARY",
                "title": "Executive Summary",
                "status": "READY",
                "summary": "The advisor proposal memo is ready for advisor use.",
            }
        ],
        "disclosures": [
            {
                "disclosure_id": "memo.advisor_use_only.v1",
                "text": "Advisor use only. Client-ready memo publication remains blocked.",
            }
        ],
    }
    return render_package.model_copy(
        update={
            "report_data": report_data,
            "disclosure_refs": [*render_package.disclosure_refs, "memo.advisor_use_only.v1"],
        }
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


def _idea_evidence_proof_pack_package() -> RenderPackage:
    return RenderPackage.model_validate_json(
        (
            GOLDEN_ROOT / "proof-pack" / "v1" / "idea-evidence-pack" / "render-package.json"
        ).read_text(encoding="utf-8")
    )


def _wave_package() -> RenderPackage:
    return RenderPackage.model_validate(
        {
            "render_package_version": "render_package.v1",
            "render_job_id": "rdr_rebalance_wave_v1",
            "report_job_id": "rjob_rebalance_wave_v1",
            "snapshot_id": "rsnap_rebalance_wave_v1",
            "report_type": "rebalance_wave",
            "report_data_contract_version": "dpm_wave_report_input.v1",
            "template_id": "rebalance-wave",
            "template_version": "v1",
            "locale": "en-SG",
            "brand_variant": "private_banking",
            "output_format": "pdf",
            "render_context": {"timezone": "Asia/Singapore"},
            "report_data": {
                "title": "Rebalance Wave Evidence - dwv_001",
                "wave_id": "dwv_001",
                "wave_state": "HANDOFF_READY",
                "trigger_type": "EXPLICIT_PORTFOLIO_LIST",
                "trigger_id": "manual-wave-001",
                "trigger_rationale": "Review explicit affected portfolio list.",
                "as_of_date": "2026-05-03",
                "aggregate_metrics": {
                    "item_count": 1,
                    "ready_item_count": 1,
                    "blocked_item_count": 0,
                },
                "supportability": {
                    "supportability_state": "ready",
                    "reason": "wave_supportability_ready",
                },
                "proof_pack_posture": {
                    "ready_proof_pack_count": 1,
                    "degraded_proof_pack_count": 0,
                },
                "items": [
                    {
                        "wave_item_id": "dwi_001",
                        "portfolio_id": "PB_SG_GLOBAL_BAL_001",
                        "state": "HANDOFF_READY",
                        "selected_alternative_id": "alt_min_turnover",
                        "proof_pack_id": "dpp_001",
                        "proof_pack_state": "READY",
                        "reason_codes": ["WAVE_ITEM_HANDOFF_READY"],
                    }
                ],
                "events": [
                    {
                        "event_type": "STATE_TRANSITION",
                        "to_state": "HANDOFF_READY",
                        "actor_id": "pm_001",
                        "reason_code": "WAVE_HANDOFF_READY",
                        "created_at": "2026-05-03T09:00:00Z",
                    }
                ],
                "handoff_count": 1,
                "external_execution_claimed": False,
                "content_hash": "sha256:report-input",
                "wave_content_hash": "sha256:wave",
                "redaction_policy": "NO_RAW_PAYLOADS",
            },
            "lineage_refs": ["rjob_rebalance_wave_v1", "dwv_001", "sha256:report-input"],
            "disclosure_refs": ["rebalance-wave.standard-disclosures.v1"],
            "requested_by": "advisor-123",
            "correlation_id": "corr-wave-render",
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
        }
    )


def test_typst_render_service_escapes_hostile_report_text_without_breaking_compile() -> None:
    """A double-quote or markup token in report data must render, not break out.

    Regression for issue #103: string-literal emitters previously used the markup
    escaper, so a quote in a security name terminated the Typst string literal and
    the compile failed. This drives the real runtime end to end.
    """

    service = _build_service()
    package = _load_golden_package()
    hostile = r'Ac"me #1 [Gold] {Fund} $x @y \ end'
    holdings = [dict(row) for row in package.report_data["top_holdings"]]
    holdings[0] = {**holdings[0], "security_name": hostile, "instrument_name": hostile}
    package = package.model_copy(
        update={"report_data": {**package.report_data, "top_holdings": holdings}}
    )

    result = service.render(package)

    assert result.attempt.status.value == "rendered"
    assert result.artifact_bytes.startswith(b"%PDF")


def _build_service() -> TypstRenderService:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    return TypstRenderService(settings, RenderIntakeService(registry))


@pytest.mark.parametrize(
    ("fixture", "render_package"),
    _load_golden_fixture_packages(),
    ids=lambda value: value.get("golden_sample_id", "") if isinstance(value, dict) else "",
)
def test_typst_render_service_renders_golden_pdf(
    fixture: dict[str, str], render_package: RenderPackage
) -> None:
    service = _build_service()

    result = service.render(render_package)

    assert result.attempt.status.value == "rendered"
    assert result.artifact_bytes.startswith(b"%PDF")
    assert result.diagnostic.template_id == render_package.template_id
    assert render_package.report_data_contract_version == fixture["report_data_contract_version"]
    assert result.diagnostic.artifact_sha256 == hashlib.sha256(result.artifact_bytes).hexdigest()
    # Assert against the fingerprint banked in the manifest, not one recomputed by the
    # production function under test: a weakened fingerprint would move the render output
    # and a self-referential expected value together and pass silently (issue #108). The
    # banked literal is an independent oracle - only the real render can match it.
    assert (
        result.diagnostic.bounded_determinism_fingerprint
        == fixture["bounded_determinism_fingerprint"]
    )
    assert result.diagnostic.mime_type == "application/pdf"
    assert result.diagnostic.output_size_bytes == len(result.artifact_bytes)
    assert result.diagnostic.determinism_mode == "bounded_runtime_envelope"


def test_bounded_determinism_fingerprint_ignores_volatile_fields_but_not_content() -> None:
    """Prove the fingerprint discriminates: stable across timestamps/IDs, changed on content.

    Banking a literal (test_typst_render_service_renders_golden_pdf) proves the render still
    produces the banked bytes, but not that the fingerprint would notice if it did not. This
    pins both halves of the "bounded" contract so a weakened normaliser cannot pass unnoticed
    (issue #108).
    """

    fingerprint = TypstRenderService._compute_bounded_determinism_fingerprint
    base = (
        b"%PDF-1.7\n"
        b"/CreationDate (D:20260101000000Z)\n"
        b"/ModDate (D:20260101000000Z)\n"
        b"/ID [<AAAA1111> <BBBB2222>]\n"
        b"<xmp:CreateDate>2026-01-01T00:00:00Z</xmp:CreateDate>\n"
        b"<xmpMM:DocumentID>uuid:1111</xmpMM:DocumentID>\n"
        b"BT (Total portfolio value 1,234,567) Tj ET\n"
    )
    volatile_only = (
        b"%PDF-1.7\n"
        b"/CreationDate (D:20991231235959Z)\n"
        b"/ModDate (D:20991231235959Z)\n"
        b"/ID [<CCCC3333> <DDDD4444>]\n"
        b"<xmp:CreateDate>2099-12-31T23:59:59Z</xmp:CreateDate>\n"
        b"<xmpMM:DocumentID>uuid:9999</xmpMM:DocumentID>\n"
        b"BT (Total portfolio value 1,234,567) Tj ET\n"
    )
    changed_content = base.replace(b"1,234,567", b"9,999,999")

    # Volatile-only differences must collapse to the same fingerprint...
    assert fingerprint(base) == fingerprint(volatile_only)
    # ...but a one-figure change in the rendered content must not.
    assert fingerprint(base) != fingerprint(changed_content)


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


def _in_markup(value: str) -> str:
    r"""The form a value takes in a markup fragment: escaped, because markup is not text.

    These assertions used to spell the raw value, which held only while the escaper left
    most markup tokens live. It neutralises all of them now, so `dpp_001` is emitted
    `dpp\_001` -- and reaches the page as `dpp_001`, which is the point of the change.

    Only the values a report supplies. `wave-item-row(` next to these is the emitter's
    own call, and the emitter does not escape itself.
    """
    return escape_typst_text(value)


def test_typst_render_service_builds_richer_portfolio_review_context() -> None:
    template_context = build_portfolio_review_context(_load_golden_package())

    assert "#cover-page()" in template_context["REPORT_SECTIONS"]
    assert "#appendix-page()" in template_context["REPORT_SECTIONS"]
    assert template_context["REVIEW_PERIOD_LABEL"] == "YTD"
    assert template_context["TOP_CONTRIBUTOR_NAME"] == "Global Equity Sleeve"
    assert "lotus-core, lotus-performance, lotus-risk" in template_context["SOURCE_SERVICES"]
    assert "#period-row(" in template_context["PERFORMANCE_PERIOD_ROWS"]
    assert "performance-summary-cell(" in template_context["PERFORMANCE_SUMMARY_TABLE"]
    assert "#performance-chart-row(" in template_context["PERFORMANCE_ANNUAL_CHART_ROWS"]
    assert "performance-detail-row(" in template_context["PERFORMANCE_MONTHLY_TABLE_ROWS"]
    # Drawn natively rather than shipped as an SVG asset, so the section carries the
    # chart's geometry rather than a path to an image.
    assert "#line-chart(" in template_context["PERFORMANCE_12M_CHART_SECTION"]
    assert "assets/charts" not in template_context["PERFORMANCE_12M_CHART_SECTION"]
    assert "#allocation-row(" in template_context["HOLDING_BAR_ROWS"]
    assert "#compact-allocation-row(" in template_context["ALLOCATION_DIMENSION_BLOCKS"]
    donut = template_context["ALLOCATION_DONUT_CHART_SECTION"]
    assert "#donut-chart(" in donut
    assert "assets/charts" not in donut
    # Drawn, not merely declared: a donut with no curve commands is an empty card.
    assert 'kind: "cubic"' in donut
    # Rows are spread into a Typst table, so each is a tuple of cells in code context
    # rather than a markup block carrying a leading '#' (issue #138).
    for statement in ("POSITION", "TRANSACTION"):
        rows = template_context[f"DENSE_{statement}_ROWS"]
        header = template_context[f"{statement}_TABLE_HEADER"]
        assert rows.startswith("([#statement-cell("), rows[:40]
        assert not rows.startswith("#"), rows[:40]
        # Header and body come from one declaration, so every column is labelled and
        # every label has values under it.
        assert header.count("#stacked-table-label(") == rows.splitlines()[0].count(
            "#statement-cell("
        )
        assert "Not available" not in rows, (
            f"the {statement.lower()} table prints an absence for a field it labels"
        )
    # Report composes this label itself, in dotted dates; the document writes them
    # its own way so the page does not carry two forms (#150).
    assert template_context["TRANSACTION_PERIOD_LABEL"] == "From 1 Jan 2026 to 23 Apr 2026"
    blocks = template_context["ALLOCATION_DIMENSION_BLOCKS"]
    # The fixture presents asset class then currency, and the emitted order is the
    # package's order -- not a priority Render holds.
    assert blocks.index("By asset class") < blocks.index("By currency")
    assert "Equity" in blocks
    assert "USD" in blocks
    assert "EQ-1" in template_context["DENSE_POSITION_ROWS"]
    assert "US0000000001" in template_context["DENSE_POSITION_ROWS"]
    # This used to assert "Not available;Not available;8,118,290.51;2024-01-15" and
    # "9,140,740.73;Not available" -- it banked the absences as expected output, so the
    # thing that was wrong with the table was the thing the test held in place.
    assert "8,118,290.51" in template_context["DENSE_POSITION_ROWS"]
    assert "15 Jan 2024" in template_context["DENSE_POSITION_ROWS"]
    assert "9,140,740.73" in template_context["DENSE_POSITION_ROWS"]
    # Fields the golden holdings do carry and the old table ignored.
    assert "United States" in template_context["DENSE_POSITION_ROWS"]
    assert "Country of risk" in template_context["POSITION_TABLE_HEADER"]
    assert "TXN-20260109-BUY-001" in template_context["DENSE_TRANSACTION_ROWS"]
    assert "INST-EQ-1" in template_context["DENSE_TRANSACTION_ROWS"]
    assert "Reference TXN-20260109-BUY-001" in template_context["DENSE_TRANSACTION_ROWS"]
    assert "Instrument INST-EQ-1" in template_context["DENSE_TRANSACTION_ROWS"]
    # These asserted "09.01.2026;Not available" and "NAV 102.35;;450,000.00;" -- the
    # first banked a value date no transaction supplies, the second a pair of empty
    # lines where the reporting currency and place of execution would have gone. Both
    # held the defect in place. What matters is that the trade date and the price reach
    # the page and that nothing beside them is blank.
    assert "9 Jan 2026" in template_context["DENSE_TRANSACTION_ROWS"]
    assert "NAV 102.35" in template_context["DENSE_TRANSACTION_ROWS"]
    # A blank line inside a cell is not an absence any more: it is the place a field
    # this row does not supply would occupy, held open so the values below stay under
    # their own labels. A field *no* row supplies is removed by `live_columns` instead,
    # which is what this was reaching for.
    assert "Not available" not in template_context["DENSE_TRANSACTION_ROWS"]
    assert "#review-note(" in template_context["OBSERVATION_NOTES"]


def test_typst_render_service_builds_reviewed_advisory_narrative_context() -> None:
    template_context = build_portfolio_review_context(
        _portfolio_review_package_with_reviewed_advisory_narrative()
    )

    assert "#reviewed-advisory-narrative-page()" in template_context["REPORT_SECTIONS"]
    assert (
        _in_markup("INCLUDED_REVIEWED_NARRATIVE") in template_context["REVIEWED_ADVISORY_FACT_ROWS"]
    )
    assert _in_markup("APPROVED_FOR_ADVISOR_USE") in template_context["REVIEWED_ADVISORY_FACT_ROWS"]
    assert (
        _in_markup("sha256:reviewed-narrative") in template_context["REVIEWED_ADVISORY_FACT_ROWS"]
    )
    assert (
        "The proposal keeps the balanced mandate"
        in template_context["REVIEWED_ADVISORY_NARRATIVE_BLOCKS"]
    )
    assert (
        _in_markup("proposal_narrative.advisor_use_only.v1")
        in template_context["REVIEWED_ADVISORY_DISCLOSURE_BLOCKS"]
    )


def test_typst_render_service_omits_reviewed_advisory_page_when_not_supplied() -> None:
    template_context = build_portfolio_review_context(_load_golden_package())

    assert "#reviewed-advisory-narrative-page()" not in template_context["REPORT_SECTIONS"]
    assert template_context["REVIEWED_ADVISORY_FACT_ROWS"] == ""


def test_typst_render_service_builds_advisor_proposal_memo_context() -> None:
    template_context = build_portfolio_review_context(
        _portfolio_review_package_with_advisor_proposal_memo()
    )

    assert "#advisor-proposal-memo-page()" in template_context["REPORT_SECTIONS"]
    assert (
        _in_markup("INCLUDED_ADVISOR_PROPOSAL_MEMO") in template_context["ADVISOR_MEMO_FACT_ROWS"]
    )
    assert _in_markup("APPROVE_FOR_ADVISOR_USE") in template_context["ADVISOR_MEMO_FACT_ROWS"]
    assert "BLOCKED" in template_context["ADVISOR_MEMO_FACT_ROWS"]
    assert (
        "The advisor proposal memo is ready for advisor use."
        in template_context["ADVISOR_MEMO_SECTION_BLOCKS"]
    )
    assert (
        _in_markup("memo.advisor_use_only.v1") in template_context["ADVISOR_MEMO_DISCLOSURE_BLOCKS"]
    )


def test_typst_render_service_builds_outcome_review_context() -> None:
    template_context = build_outcome_review_context(_outcome_review_package())

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
    idea_evidence_context = service._build_template_context(_idea_evidence_proof_pack_package())
    wave_context = service._build_template_context(_wave_package())

    assert outcome_context["OUTCOME_REVIEW_ID"] == "dor_001"
    assert proof_pack_context["PROOF_PACK_ID"] == "dpp_001"
    assert idea_evidence_context["PROOF_PACK_ID"] == "irep_001"
    assert (
        idea_evidence_context["SOURCE_CONTRACT_VERSION"]
        == "lotus_idea_evidence_pack_report_input.v1"
    )
    assert wave_context["WAVE_ID"] == "dwv_001"


def test_typst_render_service_rejects_unregistered_template_context_without_fallback() -> None:
    service = _build_service()
    render_package = _load_golden_package().model_copy(
        update={"report_type": "unknown", "template_id": "unknown"}
    )

    with pytest.raises(ValueError, match="unsupported template context renderer"):
        service._build_template_context(render_package)


def test_typst_render_service_builds_proof_pack_context() -> None:
    template_context = build_proof_pack_context(_proof_pack_package())

    assert template_context["PORTFOLIO_ID"] == "PB_SG_GLOBAL_BAL_001"
    assert template_context["PROOF_PACK_ID"] == "dpp_001"
    assert template_context["SUPPORTABILITY_STATUS"] == "READY"
    assert "section-row(" in template_context["SECTION_ROWS"]
    assert "Mandate context" in template_context["SECTION_ROWS"]
    assert "sha256:report-input" in template_context["CONTENT_HASH"]


def test_typst_render_service_builds_idea_evidence_proof_pack_context() -> None:
    template_context = build_proof_pack_context(_idea_evidence_proof_pack_package())

    assert template_context["PORTFOLIO_ID"] == "PB_SG_GLOBAL_BAL_001"
    assert template_context["PROOF_PACK_ID"] == "irep_001"
    assert template_context["CLIENT_PUBLICATION_AUTHORITY"] == "false"
    assert (
        "lotus_idea_evidence_pack_report_input.v1" in (template_context["SOURCE_CONTRACT_VERSION"])
    )
    assert _in_markup("lotus-idea:IdeaEvidencePacket") in template_context["SOURCE_LINEAGE_ROWS"]
    assert (
        _in_markup("ievp_001 / sha256:idea-evidence-content")
        in template_context["SOURCE_LINEAGE_ROWS"]
    )


def test_typst_render_service_builds_wave_context() -> None:
    template_context = build_wave_context(_wave_package())

    assert template_context["WAVE_ID"] == "dwv_001"
    assert template_context["WAVE_STATE"] == "HANDOFF_READY"
    assert template_context["SUPPORTABILITY_STATUS"] == "ready"
    assert template_context["PROOF_PACK_READY_COUNT"] == "1"
    assert "wave-item-row(" in template_context["ITEM_ROWS"]
    assert _in_markup("dpp_001") in template_context["ITEM_ROWS"]
    assert _in_markup("STATE_TRANSITION") in template_context["EVENT_ROWS"]
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
    """An empty section says so in words, not in a sentinel.

    This asserted "not_available" was in the fallback row, which is how the sentinel
    reached a governed proof pack and every rebalance wave: the test held it there.
    """

    assert "No section evidence supplied." in render_proof_pack_section_rows([])
    assert "No source lineage supplied." in render_source_lineage_rows([])
    assert "Not available" in render_key_value_rows({})
    assert "not_available" not in render_key_value_rows({})


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


def test_template_registry_accepts_wave_template() -> None:
    settings = Settings()
    registry = TemplateRegistry.load_from_directory(Path(settings.template_registry_path))
    manifest = registry.resolve_for_new_render(_wave_package())

    assert manifest.template_id == "rebalance-wave"
    assert manifest.supported_report_types == ["rebalance_wave"]
    assert manifest.supported_report_data_contract_versions == ["dpm_wave_report_input.v1"]


def test_typst_render_service_builds_selected_section_sequence() -> None:
    render_package = _load_golden_package().model_copy(
        update={
            "render_context": {
                "timezone": "Asia/Singapore",
                "sections": ["performance", "asset-allocation", "transactions"],
            }
        }
    )

    template_context = build_portfolio_review_context(render_package)

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
    assert len(result.artifact_bytes) < len(
        (_golden_root("portfolio-review") / "expected.pdf").read_bytes()
    )


def test_typst_render_service_renders_reviewed_advisory_narrative_section() -> None:
    service = _build_service()
    render_package = _portfolio_review_package_with_reviewed_advisory_narrative().model_copy(
        update={
            "render_context": {
                "timezone": "Asia/Singapore",
                "sections": ["reviewed-advisory-narrative"],
            }
        }
    )

    result = service.render(render_package)

    assert result.artifact_bytes.startswith(b"%PDF")
    assert result.diagnostic.template_id == "portfolio-review"


def test_typst_render_service_renders_advisor_proposal_memo_section() -> None:
    service = _build_service()
    render_package = _portfolio_review_package_with_advisor_proposal_memo().model_copy(
        update={
            "render_context": {
                "timezone": "Asia/Singapore",
                "sections": ["advisor-proposal-memo"],
            }
        }
    )

    result = service.render(render_package)

    assert result.artifact_bytes.startswith(b"%PDF")
    assert result.diagnostic.template_id == "portfolio-review"


def test_typst_render_service_helper_fallbacks_cover_sparse_structures() -> None:
    assert string_list("not-a-list") == []
    assert string_list([" lot1 ", "", "lot2"]) == ["lot1", "lot2"]
    assert mapping("not-a-mapping") == {}
    with pytest.raises(ValueError, match="missing required report_data field: title"):
        build_outcome_review_context(
            _outcome_review_package().model_copy(update={"report_data": {}})
        )
    with pytest.raises(ValueError, match="dimensions must be a list"):
        outcome_package = _outcome_review_package()
        build_outcome_review_context(
            outcome_package.model_copy(
                update={"report_data": {**outcome_package.report_data, "dimensions": "bad"}}
            )
        )
    with pytest.raises(ValueError, match="missing required report_data field: title"):
        build_wave_context(_wave_package().model_copy(update={"report_data": {}}))
    with pytest.raises(ValueError, match="items must be a list"):
        wave_package = _wave_package()
        build_wave_context(
            wave_package.model_copy(
                update={"report_data": {**wave_package.report_data, "items": "bad"}}
            )
        )
    assert requested_section_keys(["detailed_positions"]) == ["positions"]
    base = [
        "cover",
        "contents",
        "overview",
        "performance",
        "allocation",
        "positions",
        "transactions",
    ]
    assert requested_section_keys(None, included={"advisory_narrative"}) == [
        *base,
        "advisory_narrative",
        "appendix",
    ]
    assert requested_section_keys(None, included={"advisor_memo"}) == [
        *base,
        "advisor_memo",
        "appendix",
    ]
    assert requested_section_keys(
        ["reviewed-advisory-narrative"],
        included={"advisory_narrative"},
    ) == ["advisory_narrative"]
    assert requested_section_keys(
        ["advisor-proposal-memo"],
        included={"advisor_memo"},
    ) == ["advisor_memo"]
    # An explicit selection that cannot be honoured refuses; it does not fall back to
    # the default report. The fallback these lines used to assert was the defect
    # (test_section_selection_fails_closed.py holds the full contract).
    with pytest.raises(SectionSelectionError):
        requested_section_keys(["detailed-positions", "asset-allocation", "unknown"])
    with pytest.raises(SectionSelectionError):
        requested_section_keys(["reviewed-advisory-narrative"], included=set())
    assert "No item evidence supplied." in render_wave_item_rows("bad")
    assert "No event evidence supplied." in render_wave_event_rows("bad")
    assert "No dimension evidence supplied." in render_outcome_dimension_rows("bad")
    assert "No 12-month performance series is available" in render_performance_chart_section({})
    # An empty package names no dimensions, so the donut says the report does not present
    # one -- which is a different statement from "the breakdown is empty", and the one
    # that is true.
    assert "does not present an asset-class breakdown" in render_allocation_chart_section({})
    assert "No governed observations available." in render_observation_notes("bad")
    assert "No governed performance periods available." in render_performance_period_rows(
        "bad", benchmarked=True
    )
    assert "No governed performance periods available." in render_performance_period_rows(
        [123], benchmarked=True
    )
    performance_summary_fallback = render_performance_summary_table("bad")
    assert "No governed performance summary available." in performance_summary_fallback
    assert "No governed performance summary available." in render_performance_summary_table([123])
    assert "No performance history available." in render_performance_chart_rows("bad")
    assert "No performance history available." in render_performance_chart_rows([123])
    # Unreadable monthly rows become one spanning cell stating so, inside the same
    # table -- inline, so the empty-block measurement still sees the placeholder.
    assert "table.cell(colspan: 8)" in render_performance_detail_rows("bad")
    assert "No monthly performance detail available." in render_performance_detail_rows([123])
    assert "No governed allocation rows available." in render_holding_bar_rows("bad")
    assert "No position detail available." in render_position_table("bad")[2]
    assert "No position detail available." in render_position_table([123])[2]
    assert "No transaction detail available." in render_transaction_table("bad")[2]
    assert "No transaction detail available." in render_transaction_table([123])[2]
    assert "No allocation detail available." in render_allocation_breakdown_rows("bad")
    assert "No allocation detail available." in render_allocation_breakdown_rows([123])
    assert "No approved narrative section supplied." in render_advisory_narrative_blocks("bad")
    assert "No approved narrative section supplied." in render_advisory_narrative_blocks(
        [{"title": "Empty", "body": ""}]
    )
    assert "No reviewed narrative disclosure text supplied." in (
        render_advisory_disclosure_blocks("bad")
    )
    assert "No reviewed narrative disclosure text supplied." in (
        render_advisory_disclosure_blocks([{"disclosure_id": "empty", "text": ""}])
    )
    assert "No advisor memo section supplied." in render_advisor_memo_section_blocks("bad")
    assert "No advisor memo section supplied." in render_advisor_memo_section_blocks(
        [{"title": "Empty", "summary": ""}]
    )


def test_a_dimension_the_package_did_not_name_is_not_presented() -> None:
    """The priority order this replaced drew a currency table for six of seven orders.

    `by_*` rows are shipped unconditionally as evidence, so presence cannot mean
    presentation. A dimension appears because `allocation_presentation` names it.
    """

    report_data = {
        "allocation_breakdowns": {
            "by_currency": [{"name": "USD", "weight_pct": "60.00%", "market_value": "600"}],
            "by_sector": [{"name": "Technology", "weight_pct": "40.00%", "market_value": "400"}],
        },
        "allocation_presentation": {
            "resolved_by": "caller_request",
            "dimensions": [{"dimension": "sector", "package_key": "by_sector", "posture": "ready"}],
        },
    }

    blocks = render_allocation_dimension_blocks(report_data)

    assert "By sector" in blocks
    assert "Technology" in blocks
    assert "By currency" not in blocks, "a dimension with rows was drawn without being named"
    assert "USD" not in blocks


def test_the_two_absent_postures_do_not_read_alike() -> None:
    """`empty` is a fact about the portfolio; `unavailable` is a fact about the data.

    A client with no fixed income legitimately has no rating buckets, and that is not the
    same statement as "we could not get this". Neither draws a column header over nothing.
    """

    report_data = {
        "allocation_presentation": {
            "resolved_by": "caller_request",
            "dimensions": [
                {"dimension": "rating", "package_key": "by_rating", "posture": "empty"},
                {"dimension": "country", "package_key": "by_country", "posture": "unavailable"},
            ],
        }
    }

    blocks = render_allocation_dimension_blocks(report_data)

    assert "No holdings fall into this grouping." in blocks
    assert "could not be retrieved" in blocks
    assert "allocation-dimension-block(" not in blocks, "a header was drawn over no rows"


def test_a_package_that_names_no_dimensions_says_so_on_the_page() -> None:
    """Fail closed and visibly. `allocation_presentation` is always sent, so its absence
    is a contract regression -- and a regression that empties a section silently is worse
    than one that says the section was never asked for."""

    blocks = render_allocation_dimension_blocks({})

    assert "No allocation dimensions were named for this report." in blocks


def test_typst_render_service_returns_empty_messages_when_sequences_have_no_mapping_rows() -> None:
    assert "No governed allocation rows available." in render_holding_bar_rows([123, 456])
    assert "No position detail available." in render_position_table([123, 456])[2]
    assert "No transaction detail available." in render_transaction_table([123, 456])[2]


def test_typst_render_service_maps_dense_position_lifecycle_fields() -> None:
    _, _, rows = render_position_table(
        [
            {
                "asset_class": "Fixed Income",
                "quantity": "100",
                "currency": "USD",
                "security_id": "SEC-1",
                "security_name": "Bond A",
                "instrument_name": "Senior bond",
                "isin": "SG0001",
                "rating": "A",
                "sector": "Financials",
                "duration": "4.20",
                "yield_to_maturity": "5.10%",
                "cost_price": "98.40",
                "exchange_rate": "1.3520",
                "cost_basis_local": "9840.00",
                "held_since_date": "2024-01-15",
                "market_price": "101.25",
                "market_price_date": "2026-04-23",
                "ytd_total_return_pct": "3.10%",
                "unrealized_pnl_pct": "2.90%",
                "unrealized_pnl": "285.00",
                "market_value": "10125.00",
                "accrued_interest": "42.25",
                "weight_pct": "6.20%",
            }
        ]
    )

    # The requirement is that every supplied field reaches the page, not that the row
    # spells them in one particular joined string: the previous form of this test
    # asserted the semicolon layout, which is why it could not see that five of the
    # labelled fields were never supplied by anything and printed "Not available".
    for supplied in (
        "Financials",
        "4.20",
        "5.10%",
        "98.40",
        "1.3520",
        "9,840.00",
        "15 Jan 2024",
        "101.25",
        "23 Apr 2026",
        "3.10%",
        "2.90%",
        "285.00",
        "10,125.00",
        "42.25",
        "6.20%",
    ):
        assert supplied in rows, f"{supplied} was supplied and does not reach the page"
    assert "Not available" not in rows, "a row that supplies every field still printed an absence"


def test_typst_render_service_maps_transaction_value_date_and_settlement_amount() -> None:
    _, _, rows = render_transaction_table(
        [
            {
                "display_label": "Buy Bond A",
                "transaction_type": "BUY",
                "transaction_category": "Trade",
                "asset_class": "Fixed Income",
                "transaction_id": "txn-1",
                "security_id": "SEC-1",
                "instrument_id": "INS-1",
                "trade_date": "2026-04-21",
                "value_date": "2026-04-23",
                "booking_text": "Purchase",
                "amount": "100",
                "description": "Bond purchase",
                "price": "101.25",
                "reporting_currency": "USD",
                "gross_amount_reporting_currency": "10125.00",
                "gain_loss": "0.00",
                "transaction_value": "10125.00",
                "net_interest_amount_reporting_currency": "42.25",
                "settlement_amount_reporting_currency": "10167.25",
            }
        ]
    )

    for supplied in ("21 Apr 2026", "23 Apr 2026", "10,125.00", "42.25", "10,167.25"):
        assert supplied in rows, f"{supplied} was supplied and does not reach the page"
    # The value date is its own field, not the trade date repeated, and the settlement
    # amount is its own figure, not the transaction value repeated.
    assert rows.count("21 Apr 2026") == 1
    assert rows.count("10,167.25") == 1
    assert "Not available" not in rows


def test_typst_render_service_numeric_fallback_helpers_cover_invalid_inputs() -> None:
    assert weight_width_token("bad") == "0%"
    assert parse_percent("bad") == 0.0
    assert parse_number("bad") == 0.0


def test_an_absent_return_draws_no_bar_rather_than_a_minimum_one() -> None:
    """ "No data" and "no movement" are different statements; neither is a gain."""

    geometry = performance_bar_geometry("bad", performance_bar_domain(["bad"]))
    assert geometry.magnitude == "0%"
    assert geometry.is_negative is False


def test_a_loss_and_a_gain_of_the_same_size_do_not_draw_the_same_bar() -> None:
    """The bar is what the eye reads. It has to carry the sign the number carries."""

    domain = performance_bar_domain(["-8.00%", "8.00%"])
    loss = performance_bar_geometry("-8.00%", domain)
    gain = performance_bar_geometry("8.00%", domain)

    assert loss.magnitude == gain.magnitude, "equal moves should reach equally far"
    assert loss.is_negative is True
    assert gain.is_negative is False


def test_bars_in_one_chart_stay_distinguishable_across_the_whole_series() -> None:
    """The annual series of the golden package, which the fixed scale flattened.

    `abs(value) * 8` clamped into [8%, 100%] drew +18.40%, -14.20% and -38.40% as
    three identical full-width bars, and a series of sub-1% months as a column of
    identical minimum-width ones. Scaled to the series, the worst year is the only
    bar that fills the track and every other bar is a readable fraction of it.
    """

    annual = ["18.40%", "-14.20%", "-38.40%", "12.80%", "3.70%", "7.08%"]
    domain = performance_bar_domain(annual)
    magnitudes = [performance_bar_geometry(value, domain).magnitude for value in annual]

    assert len(set(magnitudes)) == len(annual), f"bars collide: {magnitudes}"
    assert magnitudes[2] == "100.00%", "the largest absolute move should fill the track"

    monthly = ["0.44%", "-0.31%", "0.85%", "-0.43%", "1.18%", "0.61%"]
    monthly_magnitudes = [
        performance_bar_geometry(value, performance_bar_domain(monthly)).magnitude
        for value in monthly
    ]
    assert len(set(monthly_magnitudes)) == len(monthly), f"bars collide: {monthly_magnitudes}"


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


def test_typst_render_service_raises_typed_timeout_when_compile_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _build_service()
    render_package = _load_golden_package()

    monkeypatch.setattr(
        service,
        "_build_compile_command",
        lambda **_: ["typst", "compile", "render.typ", "rendered.pdf"],
    )

    def _raise_timeout(*_: object, **__: object) -> object:
        raise subprocess.TimeoutExpired(cmd=["typst"], timeout=1)

    monkeypatch.setattr("app.services.typst_rendering.subprocess.run", _raise_timeout)

    with pytest.raises(RenderEngineTimeoutError, match="render_timeout"):
        service.render(render_package)


def test_docker_user_flags_map_the_invoking_identity_where_the_platform_has_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On POSIX the compile runs as the invoking user; Windows has no uid to map.

    Without the flag the container runs as root and writes root-owned files into the
    bind-mounted workspace (issue #106). The helper is platform-dependent, so both
    shapes are pinned here rather than only the one this machine happens to be.
    """

    import app.services.typst_rendering as rendering

    class _Posix:
        @staticmethod
        def getuid() -> int:
            return 10001

        @staticmethod
        def getgid() -> int:
            return 10002

    monkeypatch.setattr(rendering, "os", _Posix)
    assert rendering._docker_user_flags() == ("--user", "10001:10002")

    class _NoIdentity:
        pass

    monkeypatch.setattr(rendering, "os", _NoIdentity)
    assert rendering._docker_user_flags() == ()


def test_typst_render_service_kills_the_compile_container_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timed-out `docker run` reaps only the client; the container must be stopped too.

    Otherwise it keeps compiling with the workspace bind-mounted while Python tears that
    directory down underneath it (issue #106).
    """

    service = _build_service()
    render_package = _load_golden_package()
    killed: list[list[str]] = []

    monkeypatch.setattr(
        service,
        "_build_compile_command",
        lambda **_: ["docker", "run", "--rm", DOCKER_TYPST_IMAGE],
    )
    monkeypatch.setattr(
        "app.services.typst_rendering.shutil.which",
        lambda binary: "/usr/bin/docker" if binary == "docker" else None,
    )

    def _fake_run(command: list[str], **kwargs: object) -> object:
        if command[1:2] == ["kill"]:
            killed.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr("app.services.typst_rendering.subprocess.run", _fake_run)

    with pytest.raises(RenderEngineTimeoutError, match="render_timeout"):
        service.render(render_package)

    assert killed, "the timed-out compile container was never killed"
    assert killed[0][:2] == ["/usr/bin/docker", "kill"]
    assert killed[0][2].startswith(DOCKER_CONTAINER_NAME_PREFIX)


def test_compile_container_kill_failure_does_not_mask_the_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The compile already failed; a docker kill that itself fails must not change that."""

    service = _build_service()
    render_package = _load_golden_package()

    monkeypatch.setattr(
        service,
        "_build_compile_command",
        lambda **_: ["docker", "run", "--rm", DOCKER_TYPST_IMAGE],
    )
    monkeypatch.setattr(
        "app.services.typst_rendering.shutil.which",
        lambda binary: "/usr/bin/docker" if binary == "docker" else None,
    )

    def _fake_run(command: list[str], **kwargs: object) -> object:
        if command[1:2] == ["kill"]:
            raise OSError("docker daemon unreachable")
        raise subprocess.TimeoutExpired(cmd=command, timeout=1)

    monkeypatch.setattr("app.services.typst_rendering.subprocess.run", _fake_run)

    with pytest.raises(RenderEngineTimeoutError, match="render_timeout"):
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

    assert command[:3] == ["/usr/bin/docker", "run", "--rm"]
    assert f"{tmp_path.resolve()}:/workspace" in command
    assert DOCKER_TYPST_IMAGE in command
    # The compile is confined: untrusted Typst source gets no network, no capabilities,
    # no privilege escalation and bounded memory/process count (issue #106). Asserting
    # the whole flag set means dropping one fails here rather than silently in production.
    for flag in DOCKER_ISOLATION_FLAGS:
        assert flag in command, f"missing isolation flag {flag!r}"
    # Named so a timed-out compile can stop the container rather than orphan it.
    assert "--name" in command
    assert f"{DOCKER_CONTAINER_NAME_PREFIX}{tmp_path.name}" in command


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


def test_the_in_process_compile_branch_is_resource_bounded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Production takes this branch, so it is the one that must carry a ceiling.

    The shipped image installs no Docker CLI, so DOCKER_ISOLATION_FLAGS -- including
    --memory 512m -- never apply. Without a bound here, a compile of untrusted report data
    is limited only by the container, and exceeding that kills the whole service instead
    of the offending render (issue #128).
    """

    service = _build_service()
    source_path = tmp_path / "main.typ"
    source_path.write_text("test", encoding="utf-8")

    # The shipped image is Linux, and the bound is a Linux `ulimit`. Pinning the platform
    # is what makes this test describe that image rather than whichever host runs it: on
    # Windows it used to pass only because Git Bash supplies an `sh` that cannot bound
    # anything, so the assertion held while the real behaviour was a failed compile.
    monkeypatch.setattr("app.services.typst_rendering.sys.platform", "linux")
    monkeypatch.setattr(
        "app.services.typst_rendering.shutil.which",
        lambda binary: {"typst": "/usr/local/bin/typst", "sh": "/bin/sh"}.get(binary),
    )

    command = service._build_compile_command(
        workspace=tmp_path, source_path=source_path, output_path=tmp_path / "out.pdf"
    )

    assert command[:2] == ["/bin/sh", "-c"], "the compile is not wrapped in a limited shell"
    assert f"ulimit -v {COMPILE_ADDRESS_SPACE_LIMIT_KB}" in command[2]
    assert f"ulimit -t {COMPILE_CPU_SECONDS}" in command[2]
    # exec so the shell is replaced: the timeout must kill typst, not a wrapper.
    assert 'exec "$0" "$@"' in command[2]
    assert "/usr/local/bin/typst" in command
    # The limits must match what the container branch already grants a compile.
    assert COMPILE_ADDRESS_SPACE_LIMIT_KB == 512 * 1024


def test_the_compile_falls_back_unwrapped_where_there_is_no_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows has no ulimit; the command must still be runnable there."""

    service = _build_service()
    source_path = tmp_path / "main.typ"
    source_path.write_text("test", encoding="utf-8")

    monkeypatch.setattr(
        "app.services.typst_rendering.shutil.which",
        lambda binary: "C:/typst.exe" if binary == "typst" else None,
    )

    command = service._build_compile_command(
        workspace=tmp_path, source_path=source_path, output_path=tmp_path / "out.pdf"
    )

    assert command[0] == "C:/typst.exe"
    assert command[1] == "compile"


def test_a_windows_host_does_not_wrap_the_compile_in_a_shell_that_cannot_bound_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bound is a Linux `ulimit`, and the test for it must be the platform.

    Git Bash puts an `sh` on PATH on Windows, so a shell-presence test wraps the
    compile in a shell that answers `ulimit: cpu time: cannot modify limit: Invalid
    argument` and fails the render outright instead of bounding it.
    """
    monkeypatch.setattr("app.services.typst_rendering.sys.platform", "win32")
    monkeypatch.setattr(
        "app.services.typst_rendering.shutil.which", lambda binary: "C:/Git/usr/bin/sh.exe"
    )

    command = ["typst", "compile", "render.typ", "rendered.pdf"]
    assert _bounded_local_command(command) == command


def test_a_linux_host_still_bounds_the_compile(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deployment that matters keeps the bound it was given in #128."""
    monkeypatch.setattr("app.services.typst_rendering.sys.platform", "linux")
    monkeypatch.setattr("app.services.typst_rendering.shutil.which", lambda binary: "/bin/sh")

    bounded = _bounded_local_command(["typst", "compile", "render.typ", "rendered.pdf"])

    assert bounded[0] == "/bin/sh"
    assert "ulimit -v" in bounded[2] and "ulimit -t" in bounded[2]


def test_golden_evidence_may_only_be_banked_from_a_runtime_that_renders_like_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fingerprint is a claim about the service, not about the machine that ran it.

    Measured: the same `main.typ` compiled by `ghcr.io/typst/typst:0.14.2` and by that
    image's binary copied into `python:3.12-slim` -- the shipped runtime -- both produce
    `e4fda81ba17e7577eb594d39145a152e0560e8aecfac86c529e012eea6a95ca6`, which is the
    banked golden. The same Typst 0.14.2 on Windows produces
    `ace7681ae6647db8b28e28057cb9bdefb47d0f241822831faf2fe01862d86ad4`. Banking the
    second would record evidence CI could never reproduce.
    """
    monkeypatch.setattr(
        "app.services.typst_rendering.shutil.which", lambda binary: "/usr/bin/docker"
    )
    assert ungoverned_runtime_reason() is None, "the pinned container is the governed runtime"

    monkeypatch.setattr("app.services.typst_rendering.shutil.which", lambda binary: None)
    monkeypatch.setattr("app.services.typst_rendering.sys.platform", "linux")
    assert ungoverned_runtime_reason() is None, "a local binary on Linux is what production runs"

    monkeypatch.setattr("app.services.typst_rendering.sys.platform", "win32")
    reason = ungoverned_runtime_reason()
    assert reason is not None and "Linux" in reason


def _completed(
    returncode: int, stderr: str = "", stdout: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["typst", "compile"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_a_document_too_large_to_compile_is_not_reported_as_a_broken_template() -> None:
    """A kill and a template error both arrive as a non-zero exit, and differ in response.

    Measured on a portfolio review: 1,000 positions and 1,000 transactions render in about
    four seconds; 2,500 of each exits **137 with completely empty stderr** -- the compile
    killed for exceeding the 512m bound before it could say anything. That used to be
    reported as `template_render_failed` with the summary "typst compile failed", which is
    what a genuinely broken template says too, so an operator could not tell a capacity
    problem from a correctness one.
    """

    category, summary = classify_compile_failure(_completed(137))

    assert category == RenderFailureCategory.RESOURCE_LIMIT_EXCEEDED
    assert "signal 9" in summary
    assert "too large" in summary


def test_a_template_error_keeps_its_diagnosis_and_its_category() -> None:
    """Whatever Typst actually said is the most useful thing to report."""

    category, summary = classify_compile_failure(
        _completed(1, stderr="error: unknown variable: period-row")
    )

    assert category == RenderFailureCategory.TEMPLATE_RENDER_FAILED
    assert summary == "error: unknown variable: period-row"


def test_a_silent_non_zero_exit_that_is_not_a_kill_stays_a_template_failure() -> None:
    """Only a signal exit is evidence of a kill; an ordinary failure is not reclassified."""

    category, summary = classify_compile_failure(_completed(1))

    assert category == RenderFailureCategory.TEMPLATE_RENDER_FAILED
    assert summary == "typst compile failed"


def test_a_negative_return_code_is_read_as_the_signal_it_is() -> None:
    """POSIX `subprocess` reports a killed child as a negative code, Docker as 128+n."""

    category, summary = classify_compile_failure(_completed(-9))

    assert category == RenderFailureCategory.RESOURCE_LIMIT_EXCEEDED
    assert "signal 9" in summary


def test_a_small_weight_draws_a_small_bar() -> None:
    """The bar must agree with the number printed beside it.

    `percent_width_token` floored at 8%, so the golden package's 1.64% liquidity sleeve
    drew the same bar as an 8% position -- five times its true length. A reader comparing
    bar lengths across the table was reading the floor rather than the portfolio.
    """

    assert weight_width_token("1.64%") == "1.64%"
    assert weight_width_token("60.00%") == "60.00%"
    assert weight_width_token("0.30%") == "0.30%"
    # Ordering is what a reader actually takes from a bar chart, and it must survive.
    widths = [float(weight_width_token(w).rstrip("%")) for w in ("60.00", "28.00", "1.64")]
    assert widths == sorted(widths, reverse=True)


def test_a_weight_that_is_absent_or_impossible_draws_no_bar() -> None:
    """A missing weight is not a small one, and nothing beyond the track is drawable."""

    assert weight_width_token("bad") == "0%"
    assert weight_width_token(None) == "0%"
    assert weight_width_token("-5") == "0.00%"
    assert weight_width_token("140") == "100.00%"


def test_hostile_report_text_in_a_markup_family_renders_rather_than_executes() -> None:
    """The other half of #103, driven through a real compile.

    The existing hostile-text test drives the *string-literal* path: a quote in a
    security name. The proof-pack, outcome-review and rebalance-wave families put their
    values into Typst **markup** instead, where the dangerous character is `#` rather
    than `"` -- and `escape_typst_string` leaves `#` untouched, so a value escaped for
    the wrong context there is live code supplied by the report producer.

    Verified by swapping the escaper: the emitted line becomes

        #section-row([#panic(\"owned\") [x] {y} $z$ @ref \\ \"quote\"], [MANDATE_CONTEXT], ...)

    and Typst refuses it with `error: unclosed delimiter` -- the brackets from report
    data restructured the argument list. A successful render is therefore evidence the
    value reached the page as text rather than as markup.
    """

    service = _build_service()
    package = _proof_pack_package()
    hostile = r'#panic("owned") [x] {y} $z$ @ref \ "quote"'
    sections = [dict(section) for section in package.report_data["sections"]]
    sections[0] = {**sections[0], "title": hostile, "summary": hostile}
    package = package.model_copy(
        update={"report_data": {**package.report_data, "sections": sections}}
    )

    result = service.render(package)

    assert result.attempt.status.value == "rendered"
    assert result.artifact_bytes.startswith(b"%PDF")


def test_a_donut_that_covers_the_whole_portfolio_carries_no_coverage_note() -> None:
    """The note explains a shortfall; with nothing to explain it would be noise.

    The complement of the golden package, whose slices cover 89.64% and so do carry it.
    """

    section = render_allocation_chart_section(
        {
            "allocation_breakdowns": {
                "by_asset_class": [
                    {"label": "Equity", "weight_pct": "60.00", "market_value": "600000"},
                    {"label": "Fixed Income", "weight_pct": "40.00", "market_value": "400000"},
                ]
            },
            # The donut is drawn because the package presents asset class, not because
            # its rows exist -- rows for every dimension ship either way.
            "allocation_presentation": {
                "resolved_by": "caller_request",
                "dimensions": [
                    {
                        "dimension": "asset_class",
                        "package_key": "by_asset_class",
                        "posture": "ready",
                    }
                ],
            },
        }
    )

    assert "coverage-note: none" in section
    assert "Chart covers" not in section


def test_a_failed_page_export_reports_why_rather_than_returning_no_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Page images are the visual-regression evidence, so a silent empty list is worse
    than a failure: a golden set that exports nothing compares clean against anything."""

    service = _build_service()
    render_package = _load_golden_package()

    monkeypatch.setattr(
        service,
        "_build_compile_command",
        lambda **_: ["docker", "run", "--rm", DOCKER_TYPST_IMAGE, "compile"],
    )

    def _fails(command: list[str], **kwargs: object) -> object:
        return subprocess.CompletedProcess(command, 1, "", "error: unknown variable `x`")

    monkeypatch.setattr("app.services.typst_rendering.subprocess.run", _fails)

    with pytest.raises(RuntimeError, match="page image export failed"):
        service.render_page_images(render_package)
