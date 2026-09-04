"""The shared reader-unit contract, tested where it lives.

Both risk galleries exercise these helpers through their panels, but the
helpers carry their own promises now that two consumers share them: the
digit-exact shift, the verbatim unitless rule, and refusal -- never a guess --
for anything else. A regression here would misprint every risk figure at once.
"""

from __future__ import annotations

from app.services.reader_units import (
    fraction_reader_value,
    metric_reader_value,
    period_caption,
    stated_text,
)


def test_a_decimal_ratio_shifts_exactly_two_places_no_float_ever() -> None:
    assert metric_reader_value("0.1374", "decimal_ratio") == "13.74%"
    assert metric_reader_value("-0.031", "decimal_ratio") == "-3.1%"
    assert fraction_reader_value("0.6258") == "62.58%"
    assert fraction_reader_value("0") == "0%"
    # Digits are preserved, not rounded: the source's precision is the answer's.
    assert fraction_reader_value("0.12345") == "12.345%"


def test_unitless_passes_the_source_string_verbatim() -> None:
    assert metric_reader_value("1.87", "unitless") == "1.87"


def test_an_unknown_unit_is_refused_not_guessed() -> None:
    """The drift backstop for a producer inventing a unit: no formatting rule
    means no statement, never a bare or misread number."""

    assert metric_reader_value("0.1374", "basis_points") is None
    assert metric_reader_value("0.1374", "") is None


def test_an_unparseable_fraction_is_refused() -> None:
    assert fraction_reader_value("not-a-number") is None
    assert fraction_reader_value("") is None


def test_period_caption_states_the_parts_the_source_stated() -> None:
    full = {"name": "YTD", "start_date": "2026-01-02", "end_date": "2026-08-31"}
    assert period_caption(full) == "YTD 2026-01-02 to 2026-08-31"
    assert period_caption({"name": "YTD"}) == "YTD"
    assert period_caption({"start_date": "2026-01-02"}) == "2026-01-02"
    assert period_caption({}) == ""
    assert period_caption(None) == ""
    assert period_caption("YTD") == ""


def test_stated_text_accepts_only_a_non_blank_string() -> None:
    assert stated_text("  YTD  ") == "YTD"
    assert stated_text("   ") == ""
    assert stated_text(2026) == ""
