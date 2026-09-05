"""The drawdown panel renders the stated block and nothing else (report#289).

Vectors mirror lotus-report's shipped emission authority
(tests/unit/reporting_render/test_drawdown_section.py): verbatim
decimal-fraction strings, complete episodes, open episodes stated open.
"""

from __future__ import annotations

from app.services.drawdown_panel import render_drawdown_panel


def _ready_block(episodes: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "posture": "ready",
        "value_unit": "decimal_fraction",
        "duration_unit": "BUSINESS_DAYS",
        "methodology_version": "drawdown.v1",
        "underwater": [
            {"date": "2026-01-13", "drawdown": "-0.0121"},
            {"date": "2026-02-03", "drawdown": "-0.124533"},
        ],
        "episodes": episodes
        if episodes is not None
        else [
            {
                "episode_id": "dd_0001",
                "peak_date": "2025-04-01",
                "trough_date": "2025-04-20",
                "recovery_date": "2025-05-11",
                "depth": "-0.0612",
                "days_to_trough": 13,
            },
            {
                "episode_id": "dd_0002",
                "peak_date": "2026-01-12",
                "trough_date": "2026-02-03",
                "recovery_date": None,
                "depth": "-0.124533",
                "days_to_trough": 16,
            },
        ],
        "summary": {
            "max_drawdown": "-0.124533",
            "max_drawdown_peak_date": "2026-01-12",
            "max_drawdown_trough_date": "2026-02-03",
            "max_drawdown_recovery_date": None,
        },
    }


def test_a_package_without_the_block_makes_no_panel_claim() -> None:
    assert render_drawdown_panel({}) == ""
    assert render_drawdown_panel({"drawdown": {}}) == ""


def test_ready_draws_the_chart_and_states_summary_and_episodes() -> None:
    panel = render_drawdown_panel({"drawdown": _ready_block()})

    assert '#section-subtitle("Drawdown (1Y)")' in panel
    assert '#chart-card("Underwater profile"' in panel
    # The zero gridline never reads negative zero.
    assert '"0.00%"' in panel and '"-0.00%"' not in panel
    # The stated decimal fractions present as percents, grounded in the
    # stated value_unit -- never a 100x lie.
    assert "Maximum drawdown -12.45% (peak 12 Jan 2026, trough 3 Feb 2026" in panel
    # An open episode is worded open, never closed-looking.
    assert "not yet recovered" in panel
    assert "recovered 11 May 2025" in panel
    # Durations carry their stated unit.
    assert "16 business days to trough" in panel
    # Deepest first: the open -12.45% episode precedes the recovered -6.12%.
    assert panel.index("-12.45% · 16 business days") < panel.index("-6.12% · 13 business days")


def test_more_than_three_episodes_states_the_drop_count() -> None:
    episodes = [
        {
            "episode_id": f"dd_{index}",
            "peak_date": "2025-04-01",
            "trough_date": "2025-04-20",
            "recovery_date": "2025-05-11",
            "depth": f"-0.0{index + 1}",
            "days_to_trough": 5,
        }
        for index in range(5)
    ]
    panel = render_drawdown_panel({"drawdown": _ready_block(episodes)})

    assert "Showing the 3 deepest of 5 episodes." in panel
    # The two shallowest are not presented.
    assert "-1.00%" not in panel


def test_calm_ready_draws_the_chart_with_no_episode_rows() -> None:
    block = _ready_block([])
    block["summary"] = None
    panel = render_drawdown_panel({"drawdown": block})

    assert '#chart-card("Underwater profile"' in panel
    assert "Maximum drawdown" not in panel
    assert "recovered" not in panel


def test_empty_states_the_document_fact() -> None:
    panel = render_drawdown_panel(
        {"drawdown": {"posture": "empty", "underwater": [], "episodes": [], "summary": None}}
    )

    assert "No drawdown recorded for the period." in panel
    assert "#chart-card" not in panel


def test_unavailable_states_the_sources_sentence() -> None:
    panel = render_drawdown_panel(
        {
            "drawdown": {
                "posture": "unavailable",
                "source_statement": "Drawdown analytics were not sourced for this report.",
            }
        }
    )

    assert '#panel-note("Drawdown analytics were not sourced for this report.")' in panel
    assert "#chart-card" not in panel


def test_positive_values_are_never_drawn_as_drawdown() -> None:
    block = _ready_block()
    block["underwater"] = [
        {"date": "2026-01-13", "drawdown": "0.05"},
        {"date": "2026-02-03", "drawdown": "-0.124533"},
    ]
    panel = render_drawdown_panel({"drawdown": block})

    # One valid point cannot make a line; the chart is withheld while the
    # summary and episodes still state their facts.
    assert "#chart-card" not in panel
    assert "Maximum drawdown -12.45%" in panel
