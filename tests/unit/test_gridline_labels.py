"""A gridline is labelled with the value it is drawn at.

`_nice_step` returns 1, 2, 2.5, 5 or 10 times a power of ten, so a step of 2.5 or 0.5 is
ordinary rather than exceptional. The label was `f"{tick:.0f}%"`, so on a 2.5 step the
lines at -2.5, 2.5 and 7.5 were labelled -2%, 2% and 8%: three of five gridlines naming
a value they were not drawn at, on a performance chart.

Near zero it was worse. A 0.5 step produced two lines both labelled "0%", only one of
which is the zero line, and a third labelled "-0%".

`_nice_ticks`'s docstring says the rework removed exactly this. It removed the arbitrary
tick *positions*; the labels went on rounding. The golden series happens to land on an
integer step, so nothing banked could see it.

The assertion is the property, not the strings: read each label back as a number and
check the line is drawn where that number belongs.
"""

from __future__ import annotations

import pytest

from app.services.chart_geometry import _fraction_down, performance_chart_geometry
from app.services.portfolio_charts import PerformancePoint, _chart_axis

# Series chosen to drive `_nice_step` onto each shape it can return.
SERIES = {
    "half step near zero": [0.05, -0.05, 0.02],
    "two-and-a-half step": [0.0, 2.0, 4.0, 6.5],
    "unit step": [0.0, 0.4, 1.0],
    "ten step": [0.0, 5.0, 10.0, 18.0],
    "wide": [-12.0, 5.0, 45.0],
    "all negative": [-1.0, -3.0, -6.5],
}


def _points(values: list[float]) -> list[PerformancePoint]:
    return [
        PerformancePoint(month=f"2026-{index + 1:02d}", cumulative_twr=value)
        for index, value in enumerate(values)
    ]


@pytest.mark.parametrize("name", sorted(SERIES))
def test_every_label_names_the_value_its_line_is_drawn_at(name: str) -> None:
    """Read the label back as a number; the line must be where that number belongs."""

    points = _points(SERIES[name])
    geometry = performance_chart_geometry(points)
    assert geometry is not None
    low, high, _ = _chart_axis(points)

    for gridline in geometry.gridlines:
        stated = float(gridline.label.removesuffix("%"))
        assert gridline.at == pytest.approx(_fraction_down(stated, low, high), abs=1e-9), (
            f"{name}: a line labelled {gridline.label} is drawn where "
            f"{high - gridline.at * (high - low):.4f}% belongs"
        )


@pytest.mark.parametrize("name", sorted(SERIES))
def test_no_two_gridlines_carry_the_same_label(name: str) -> None:
    """Two lines reading "0%" tell a reader nothing about either of them."""

    geometry = performance_chart_geometry(_points(SERIES[name]))
    assert geometry is not None
    labels = [gridline.label for gridline in geometry.gridlines]

    assert len(labels) == len(set(labels)), f"{name}: repeated gridline labels {labels}"


@pytest.mark.parametrize("name", sorted(SERIES))
def test_zero_is_written_as_zero(name: str) -> None:
    """A tick rounding to nothing was written "-0%", which is not a number a reader
    recognises and is not the zero line either."""

    geometry = performance_chart_geometry(_points(SERIES[name]))
    assert geometry is not None

    assert not [g.label for g in geometry.gridlines if g.label.startswith("-0%")]
    assert not [g.label for g in geometry.gridlines if g.label.startswith("-0.0")]


@pytest.mark.parametrize(("name", "expected"), [("unit step", "0%"), ("ten step", "0%")])
def test_a_whole_number_step_keeps_whole_number_labels(name: str, expected: str) -> None:
    """The fix must not put a decimal on every axis that never needed one."""

    geometry = performance_chart_geometry(_points(SERIES[name]))
    assert geometry is not None

    assert expected in [gridline.label for gridline in geometry.gridlines]


def test_exactly_one_gridline_is_the_zero_line() -> None:
    """The flag and the label have to agree about which line is zero."""

    for name, values in SERIES.items():
        geometry = performance_chart_geometry(_points(values))
        assert geometry is not None
        zero_flagged = [gridline for gridline in geometry.gridlines if gridline.zero]

        assert len(zero_flagged) == 1, f"{name}: {len(zero_flagged)} lines flagged as zero"
        assert float(zero_flagged[0].label.removesuffix("%")) == 0.0
