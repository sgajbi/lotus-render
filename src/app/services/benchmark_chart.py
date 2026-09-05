"""The benchmark posture's chart dressing (report#288).

The stated `benchmark_series` block decides what the 12-month cumulative
chart SAYS about the benchmark: `ready` names it in the card subtitle,
`unavailable` states the source's sentence under the chart, and
`unbenchmarked` changes nothing -- an unassigned benchmark is normal
state, not degradation. The line itself is paired and drawn from
`portfolio_charts`/`chart_geometry`; this module only words the card.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.services.portfolio_charts import benchmark_series_block
from app.services.typst_values import escape_typst_string

_CHART_SUBTITLE = "Net performance, valued in reporting currency"


def _benchmark_subtitle(block: Mapping[str, object], reporting_currency: str) -> str:
    """The ready posture names the benchmark in the card subtitle, with its
    currency only when it differs from the reporting currency."""

    benchmark_id = str(block.get("benchmark_id") or "").strip()
    if not benchmark_id:
        return _CHART_SUBTITLE
    subtitle = f"{_CHART_SUBTITLE} · Benchmark: {benchmark_id}"
    currency = str(block.get("benchmark_currency") or "").strip()
    if currency and reporting_currency and currency != reporting_currency:
        return f"{subtitle} ({currency})"
    return subtitle


def _benchmark_caption(block: Mapping[str, object]) -> str:
    """The unavailable posture's stated sentence, rendered under the chart --
    an expected-but-refused series is a fact the reader must see, never a
    silently thinner chart."""

    statement = str(block.get("source_statement") or "").strip()
    if not statement:
        return ""
    return f'\n#panel-note("{escape_typst_string(statement)}")'


def benchmark_chart_dressing(report_data: Mapping[str, object]) -> tuple[str, str]:
    """The card subtitle and any stated caption for the benchmark posture
    (report#288). `unbenchmarked` (and a package with no block) changes
    nothing -- an unassigned benchmark is normal state, not degradation."""

    block = benchmark_series_block(report_data)
    if block is None:
        return _CHART_SUBTITLE, ""
    posture = str(block.get("posture"))
    if posture == "ready":
        reporting = str(report_data.get("reporting_currency") or "").strip()
        return _benchmark_subtitle(block, reporting), ""
    if posture == "unavailable":
        return _CHART_SUBTITLE, _benchmark_caption(block)
    return _CHART_SUBTITLE, ""
