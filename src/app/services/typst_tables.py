"""Portfolio-review table and chart fragment emitters.

Pure functions that turn governed report data into Typst source fragments for
the performance, holdings, positions, transactions and allocation tables.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal

from app.services.absence import supplied_text
from app.services.allocation_presentation import (
    EMPTY,
    READY,
    UNAVAILABLE,
    presented_dimension,
    presented_dimensions,
    presented_rows,
)
from app.services.appendix_glossary import applicable_glossary
from app.services.chart_geometry import (
    DonutSegment,
    donut_segments,
    performance_chart_geometry,
)
from app.services.number_format import format_money, format_percent, group_digits
from app.services.portfolio_charts import (
    AllocationSlice,
    allocation_items_from_rows,
    performance_series_from_report_data,
)
from app.services.statement_layouts import POSITION_COLUMNS, TRANSACTION_COLUMNS
from app.services.statement_tables import (
    StatementColumn,
    live_columns,
    render_header,
    render_rows,
    render_widths,
)
from app.services.typst_values import (
    escape_typst_string,
    mapping_entries,
    optional_percent,
    parse_number,
    parse_percent,
    performance_bar_domain,
    performance_bar_geometry,
    row_sequence,
    string_list,
    weight_width_token,
)

# Rounding means a complete breakdown can total 99.99% rather than exactly 100. The note
# is for a chart that is materially incomplete, not for a rounding remainder.
DONUT_FULL_COVERAGE_PCT = Decimal("99.5")


def _typst_dictionary(**fields: object) -> str:
    """A Typst dictionary literal. Numbers are emitted at fixed precision.

    Fixed precision rather than `repr`: a float rendered as `0.30000000000000004` is both
    unreadable in the generated source and a needless way for two equal geometries to
    produce different bytes.
    """
    parts = []
    for name, value in fields.items():
        key = name.replace("_", "-")
        if isinstance(value, bool):
            parts.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, float):
            parts.append(f"{key}: {value:.5f}")
        else:
            parts.append(f'{key}: "{escape_typst_string(str(value))}"')
    return "(" + ", ".join(parts) + ")"


def _typst_array(items: Iterable[str]) -> str:
    """A Typst array literal.

    The trailing comma that disambiguates a one-element array is a syntax error on an
    empty one -- `(,)` does not parse -- and an empty benchmark series is the ordinary
    case, not an edge case.
    """
    rendered = list(items)
    if not rendered:
        return "()"
    return "(" + ", ".join(rendered) + ",)"


def render_performance_chart_section(report_data: Mapping[str, object]) -> str:
    """The 12-month chart, drawn natively rather than shipped as an SVG.

    The geometry is computed in `chart_geometry`, where it is unit-tested; this only
    turns it into the arguments of a Typst call.
    """
    geometry = performance_chart_geometry(performance_series_from_report_data(report_data))
    if geometry is None:
        return (
            '#chart-placeholder("12-Month Cumulative Performance", '
            '"No 12-month performance series is available for this report.")'
        )

    gridlines = _typst_array(
        _typst_dictionary(label=line.label, at=line.at, zero=line.zero)
        for line in geometry.gridlines
    )
    points = _typst_array(
        _typst_dictionary(at=point.at, value=point.value) for point in geometry.points
    )
    labels = _typst_array(
        _typst_dictionary(text=label.text, at=label.at) for label in geometry.labels
    )
    benchmark = _typst_array(
        _typst_dictionary(at=point.at, value=point.value) for point in geometry.benchmark
    )
    benchmark_label = '"Benchmark"' if geometry.benchmark else "none"

    return (
        '#chart-card("12-Month Cumulative Performance", '
        'subtitle: "Net performance, valued in reporting currency")[\n'
        f"  #line-chart(\n"
        f"    gridlines: {gridlines},\n"
        f"    points: {points},\n"
        f"    labels: {labels},\n"
        f"    benchmark: {benchmark},\n"
        f"    benchmark-label: {benchmark_label},\n"
        f"  )\n"
        "]"
    )


def _donut_path_literal(segment: DonutSegment) -> str:
    """One slice as a Typst dictionary: its colour and its ordered curve commands."""
    commands = _typst_array(
        '(kind: "%s", values: %s)'
        % (kind, _typst_array(f"{coordinate:.5f}" for coordinate in values))
        for kind, values in segment.commands
    )
    return '(colour: "%s", commands: %s)' % (escape_typst_string(segment.colour), commands)


def _donut_coverage_note(items: list[AllocationSlice]) -> str:
    """What the chart says when its slices do not add up to the whole portfolio.

    A donut looks like a whole thing. When the slices cover less than all of it the chart
    says so, rather than leaving a reader to infer it from a total that disagrees with the
    invested value printed beside it. The golden package covers 89.64%.
    """
    coverage = sum((item.weight_pct for item in items), Decimal("0"))
    if coverage >= DONUT_FULL_COVERAGE_PCT:
        return "none"
    return f'"Chart covers {escape_typst_string(format_percent(coverage))} of portfolio value"'


def render_allocation_chart_section(report_data: Mapping[str, object]) -> str:
    """The allocation donut, drawn when the package says asset class is presented.

    Asset class is a dimension like any other in Report's catalogue -- its default is
    `asset_class_when_omitted`, which is a statement about silence, not a mandate. A
    caller who asked for sector allocation and received an asset-class donut they did not
    order is the same defect the supplemental slot had, one level up.
    """
    asset_class = presented_dimension(report_data, "asset_class")
    if asset_class is None or asset_class.posture != READY:
        return (
            '#chart-placeholder("Asset Allocation", '
            '"This report does not present an asset-class breakdown.")'
        )
    items = allocation_items_from_rows(presented_rows(report_data, asset_class))
    segments = donut_segments(items)
    if not segments:
        return (
            '#chart-placeholder("Asset Allocation", '
            '"No allocation breakdown is available for this report.")'
        )

    paths = _typst_array(_donut_path_literal(segment) for segment in segments)
    entries = _typst_array(
        _typst_dictionary(
            colour=item.color,
            label=item.label,
            weight=format_percent(item.weight_pct),
            value=format_money(item.market_value),
        )
        for item in items
    )
    total = sum((item.market_value for item in items), Decimal("0"))
    note = _donut_coverage_note(items)

    return (
        '#chart-card("Asset Allocation", '
        'subtitle: "Portfolio composition by market value")[\n'
        f"  #donut-chart(\n"
        f"    segments: {paths},\n"
        f"    entries: {entries},\n"
        f'    centre-value: "{escape_typst_string(format_money(total, decimals=0))}",\n'
        f"    coverage-note: {note},\n"
        f"  )\n"
        "]"
    )


def render_observation_notes(observations: object) -> str:
    """Observations are plain strings, so this takes the string sibling of the guard.

    It was also the one emitter where an empty list and an absent one disagreed: an
    absent list said "No governed observations available", and an empty list rendered
    nothing at all -- a blank region indistinguishable from a layout fault. Both now say
    the same thing, because to a reader they mean the same thing.
    """
    notes = string_list(observations)
    if not notes:
        return '#empty-state("No governed observations available.")'
    return "\n#v(8pt)\n".join(f'#review-note("{escape_typst_string(note)}")' for note in notes)


def render_performance_period_rows(periods: object, *, benchmarked: bool) -> str:
    """Period returns, with the benchmark comparison only where there is one.

    `benchmarked` comes from `benchmark_presentation`, which the appendix reads too, so a
    Benchmark column and a definition of "Benchmark" appear together or not at all. The
    table used to draw four columns whenever there were periods, so a package with no
    benchmark got two columns of "Not available" under a heading promising a comparison.
    """
    columns = 4 if benchmarked else 2
    # Inline so the empty-block measurement sees the placeholder a reader sees.
    empty_message = (
        f"(table.cell(colspan: {columns})"
        '[#empty-state("No governed performance periods available.")],)'
    )
    rendered: list[str] = []
    for item in mapping_entries(periods):
        period = escape_typst_string(str(item.get("period", "n/a")))
        net = escape_typst_string(group_digits(supplied_text(item.get("net_return_pct"))))
        if not benchmarked:
            rendered.append(f'period-return-row("{period}", "{net}")')
            continue
        relative = item.get("relative_return_pct")
        parsed_relative = optional_percent(relative)
        rendered.append(
            f'period-row("{period}", "{net}", "'
            + escape_typst_string(group_digits(supplied_text(item.get("benchmark_return_pct"))))
            + '", "'
            + escape_typst_string(str(relative if relative is not None else "Not available"))
            + '", '
            # Absent is not underperformance: without a number there is no sign to show.
            + ("true" if parsed_relative is not None and parsed_relative < 0 else "false")
            + ")"
        )
    if not rendered:
        return empty_message
    return "(\n" + ",\n".join(rendered) + ",\n)"


def render_performance_summary_table(rows: object) -> str:
    empty_message = '#empty-state("No governed performance summary available.")'
    rendered: list[str] = []
    for item in mapping_entries(rows):
        rendered.append(
            'performance-summary-cell("'
            + escape_typst_string(str(item.get("label", "Period")))
            + '", "'
            + escape_typst_string(group_digits(supplied_text(item.get("net_return_pct"))))
            + '", "'
            + escape_typst_string(group_digits(item.get("annualized_return_pct", "n/a")))
            + '")'
        )
    if not rendered:
        return empty_message
    return (
        "#grid(columns: (1fr, 1fr, 1fr, 1fr, 1fr), column-gutter: 7pt,\n"
        + ",\n".join(rendered)
        + "\n)"
    )


def _performance_chart_row(item: Mapping[str, object], domain: float) -> str:
    geometry = performance_bar_geometry(item.get("twr_pct"), domain)
    return (
        'performance-chart-row("'
        + escape_typst_string(str(item.get("period", "n/a")))
        + '", "'
        + escape_typst_string(group_digits(supplied_text(item.get("twr_pct"))))
        + '", "'
        + escape_typst_string(group_digits(supplied_text(item.get("cumulative_twr_pct"))))
        + '", '
        + geometry.magnitude
        + ", "
        + ("true" if geometry.is_negative else "false")
        + ")"
    )


def render_performance_chart_rows(rows: object) -> str:
    """The annual performance bars. The two-column variant went with its only caller.

    `PERFORMANCE_MONTHLY_CHART_ROWS` was the one key that passed `two_column=True`, and
    no template ever substituted it.
    """
    empty_message = '#empty-state("No performance history available.", size: 8pt)'
    entries = mapping_entries(rows)
    if not entries:
        return empty_message
    # One domain for the whole series: bars are only comparable to each other if
    # every bar in the chart is drawn against the same scale.
    domain = performance_bar_domain(item.get("twr_pct") for item in entries)
    rendered = [f"#{_performance_chart_row(item, domain)}" for item in entries]
    return "\n#v(1.5pt)\n".join(rendered) + f'\n#v(4pt)\n#chart-scale-note("{domain:.2f}%")'


def render_performance_detail_rows(rows: object) -> str:
    """Rows of the monthly table, as a Typst array the table spreads.

    Each row is a `performance-detail-row(...)` call returning eight cells, so the
    table -- not the row -- owns columns, separator strokes and the repeating header
    (#246 phase 3). Where no row can be read, one spanning cell states it inside the
    same table.
    """
    # Emitted inline rather than through a component: `count_empty_content_blocks`
    # counts the `empty-state(` calls in context values, and a placeholder a reader
    # sees must never hide from the measurement inside a component.
    empty_message = (
        "(table.cell(colspan: 8)"
        '[#empty-state("No monthly performance detail available.", size: text-small)],)'
    )
    rendered: list[str] = []
    for item in mapping_entries(rows):
        rendered.append(
            'performance-detail-row("'
            + escape_typst_string(str(item.get("period", "n/a")))
            + '", "'
            + escape_typst_string(group_digits(supplied_text(item.get("final_value"))))
            + '", "'
            + escape_typst_string(group_digits(supplied_text(item.get("inflows"))))
            + '", "'
            + escape_typst_string(group_digits(supplied_text(item.get("outflows"))))
            + '", "'
            + escape_typst_string(group_digits(supplied_text(item.get("performance_value"))))
            + '", "'
            + escape_typst_string(group_digits(supplied_text(item.get("twr_pct"))))
            + '", "'
            + escape_typst_string(
                group_digits(supplied_text(item.get("cumulative_performance_value")))
            )
            + '", "'
            + escape_typst_string(group_digits(supplied_text(item.get("cumulative_twr_pct"))))
            + '")'
        )
    if not rendered:
        return empty_message
    return "(\n" + ",\n".join(rendered) + ",\n)"


def render_holding_bar_rows(holdings: object) -> str:
    rendered: list[str] = []
    for item in mapping_entries(holdings):
        rendered.append(
            '#allocation-row("'
            + escape_typst_string(str(item.get("security_name", "Unknown holding")))
            + '", "'
            + escape_typst_string(group_digits(supplied_text(item.get("weight_pct"))))
            + '", "'
            + escape_typst_string(group_digits(supplied_text(item.get("market_value"))))
            + '", '
            + weight_width_token(item.get("weight_pct"))
            + ")"
        )
    if not rendered:
        return '#empty-state("No governed allocation rows available.")'
    return "\n#v(8pt)\n".join(rendered)


# A colspan cell so the empty state is a row of the table rather than a stray block
# outside it, which would sit above the repeating header on later pages. A table with
# no rows is drawn as a single column, so the message spans everything there is.
_NO_POSITIONS_CELL = '[#empty-state("No position detail available.", size: 8pt)],'
_NO_TRANSACTIONS_CELL = '[#empty-state("No transaction detail available.", size: 8pt)],'


def _statement_parts(
    columns: tuple[StatementColumn, ...], rows: object, empty: str
) -> tuple[str, str, str]:
    """Widths, header and body for one statement table, from one declaration."""
    entries = list(mapping_entries(rows))
    live = live_columns(columns, entries)
    if not entries or not live:
        # One column, no labels: there is nothing to label, and a blank header row
        # would draw a rule over the message.
        return "(1fr,)", "", empty
    return render_widths(live), render_header(live), render_rows(live, entries)


def render_position_table(holdings: object) -> tuple[str, str, str]:
    """The positions table, drawn only as wide as the holdings can fill it."""
    return _statement_parts(POSITION_COLUMNS, holdings, _NO_POSITIONS_CELL)


def render_transaction_table(transactions: object) -> tuple[str, str, str]:
    """The transaction list, drawn only as wide as the transactions can fill it."""
    return _statement_parts(TRANSACTION_COLUMNS, transactions, _NO_TRANSACTIONS_CELL)


# What the allocation page holds beside the donut, measured rather than chosen: the
# bucket rows sit at a uniform 26.9pt pitch and nine of them fit before the list runs onto
# the next page. A tenth bucket is not a design decision, it is a page.
MAX_COMPOSITION_ROWS = 9


def _folded_buckets(
    ordered: list[tuple[str, dict[str, float]]],
) -> tuple[list[tuple[str, dict[str, float]]], int]:
    """The buckets to draw, and how many were folded into the last of them.

    A country breakdown has thirty-odd buckets and a reader scans none of them. The tail
    becomes one row that says how many it stands for, because an "Other" indistinguishable
    from a real group is a bucket the reader will try to look up.
    """
    if len(ordered) <= MAX_COMPOSITION_ROWS:
        return ordered, 0
    kept = ordered[: MAX_COMPOSITION_ROWS - 1]
    folded = ordered[MAX_COMPOSITION_ROWS - 1 :]
    other = {
        "weight": sum(totals["weight"] for _, totals in folded),
        "value": sum(totals["value"] for _, totals in folded),
    }
    return [*kept, (f"Other ({len(folded)} groups)", other)], len(folded)


def composition_note(rows: object) -> str:
    """What this grouping does not say, or `none` when it says everything.

    Two separate facts, and a grouping can need either, both or neither: how much of the
    portfolio it covers, and how many groups were folded. Stated only where true -- a note
    that always appears is furniture a reader stops reading.
    """
    items = row_sequence(rows)
    aggregates = _aggregated_allocation_buckets(items) if items is not None else {}
    if not aggregates:
        return "none"
    coverage = sum(totals["weight"] for totals in aggregates.values())
    sentences = []
    if coverage < float(DONUT_FULL_COVERAGE_PCT):
        sentences.append(f"This grouping covers {format_percent(coverage)} of portfolio value.")
    if len(aggregates) > MAX_COMPOSITION_ROWS:
        folded = len(aggregates) - (MAX_COMPOSITION_ROWS - 1)
        sentences.append(f"The {folded} smallest groups are shown together as Other.")
    if not sentences:
        return "none"
    return f'"{escape_typst_string(" ".join(sentences))}"'


def render_allocation_breakdown_rows(rows: object) -> str:
    empty = (
        "(table.cell(colspan: 4)"
        '[#empty-state("No allocation detail available.", size: text-small)],)'
    )
    items = row_sequence(rows)
    if items is None:
        return empty
    aggregates = _aggregated_allocation_buckets(items)
    if not aggregates:
        return empty
    ordered, _ = _folded_buckets(
        sorted(aggregates.items(), key=lambda entry: entry[1]["weight"], reverse=True)
    )
    rendered = [
        'compact-allocation-row("'
        + escape_typst_string(name)
        + '", "'
        + escape_typst_string(format_percent(totals["weight"]))
        + '", "'
        + escape_typst_string(format_money(totals["value"]))
        + '", '
        # `weight_width_token` is the governed one and floors nothing; this site kept
        # its own `max(weight, 8.0)`, so Cash at 1.64% drew an 8% bar beside a donut
        # showing 1.64%.
        + weight_width_token(totals["weight"])
        + ")"
        for name, totals in ordered
    ]
    return "(\n" + ",\n".join(rendered) + ",\n)"


def _aggregated_allocation_buckets(rows: Sequence[object]) -> dict[str, dict[str, float]]:
    aggregates: dict[str, dict[str, float]] = {}
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        bucket_name = str(
            item.get("name") or item.get("asset_class") or item.get("currency") or "Not available"
        )
        weight = parse_percent(item.get("weight_pct") or item.get("weight"))
        value = parse_number(item.get("market_value"))
        bucket = aggregates.setdefault(bucket_name, {"weight": 0.0, "value": 0.0})
        bucket["weight"] += weight
        bucket["value"] += value
    return aggregates


# What a posture says, in the reader's terms. `empty` is a fact about the portfolio -- a
# client with no fixed income legitimately has no rating buckets -- and `unavailable` is a
# fact about the data. They must not read alike, which is why they are two sentences and
# not one, and why neither draws a column header over nothing.
_POSTURE_NOTES = {
    EMPTY: "No holdings fall into this grouping.",
    UNAVAILABLE: "This grouping could not be retrieved for this report.",
}


def render_allocation_dimension_blocks(report_data: Mapping[str, object]) -> str:
    """One block per presented dimension, in the order the package named them.

    Render used to choose: the first breakdown with rows, from a priority order of its
    own, in one slot. Because currency led that order and the package ships all seven
    dimensions unconditionally, six of the seven single-dimension orders drew a currency
    table -- and #211 had made the appendix agree with it, so the document was internally
    consistent about presenting the wrong analytic.
    """
    presented = presented_dimensions(report_data)
    if not presented:
        return '#empty-state("No allocation dimensions were named for this report.")'

    blocks: list[str] = []
    for item in presented:
        title = escape_typst_string(item.title)
        if item.posture == READY:
            source = presented_rows(report_data, item)
            rows = render_allocation_breakdown_rows(source)
            note = composition_note(source)
            blocks.append(f'[#allocation-dimension-block("{title}", {rows}, note: {note})]')
        else:
            note = escape_typst_string(_POSTURE_NOTES[item.posture])
            blocks.append(f'[#allocation-dimension-note("{title}", "{note}")]')

    return (
        "#grid(columns: (1fr, 1fr), column-gutter: 18pt, row-gutter: 16pt,\n"
        + ",\n".join(blocks)
        + "\n)"
    )


def render_appendix_glossary_groups(report_data: Mapping[str, object]) -> str:
    """The glossary groups this document needs, as Typst the appendix can iterate.

    Only the keys travel. The wording lives in the template beside the rest of the
    document's copy, so changing a definition moves the template digest.
    """
    return _typst_array(
        "(title: %s, keys: %s)"
        % (
            f'"{escape_typst_string(group.title)}"',
            _typst_array(f'"{entry.key}"' for entry in group.entries),
        )
        for group in applicable_glossary(report_data)
    )
