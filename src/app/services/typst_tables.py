"""Portfolio-review table and chart fragment emitters.

Pure functions that turn governed report data into Typst source fragments for
the performance, holdings, positions, transactions and allocation tables.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.services.number_format import format_money, format_percent, group_digits
from app.services.portfolio_charts import (
    allocation_items_from_report_data,
    performance_series_from_report_data,
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


def render_performance_chart_section(report_data: Mapping[str, object]) -> str:
    if not performance_series_from_report_data(report_data):
        return (
            '#chart-placeholder("12-Month Cumulative Performance", '
            '"No 12-month performance series is available for this report.")'
        )
    return (
        '#chart-card("12-Month Cumulative Performance", '
        '"assets/charts/performance_12m.svg", '
        'subtitle: "Net performance, valued in reporting currency")'
    )


def render_allocation_chart_section(report_data: Mapping[str, object]) -> str:
    if not allocation_items_from_report_data(report_data):
        return (
            '#chart-placeholder("Asset Allocation", '
            '"No allocation breakdown is available for this report.")'
        )
    return (
        '#chart-card("Asset Allocation", '
        '"assets/charts/allocation_asset_class.svg", '
        'subtitle: "Portfolio composition by market value")'
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


def render_performance_period_rows(periods: object) -> str:
    empty_message = '#empty-state("No governed performance periods available.")'
    rendered: list[str] = []
    for item in mapping_entries(periods):
        relative = item.get("relative_return_pct")
        parsed_relative = optional_percent(relative)
        rendered.append(
            '#period-row("'
            + escape_typst_string(str(item.get("period", "n/a")))
            + '", "'
            + escape_typst_string(group_digits(item.get("net_return_pct", "Not available")))
            + '", "'
            + escape_typst_string(group_digits(item.get("benchmark_return_pct", "Not available")))
            + '", "'
            + escape_typst_string(str(relative if relative is not None else "Not available"))
            + '", '
            # Absent is not underperformance: without a number there is no sign to show.
            + ("true" if parsed_relative is not None and parsed_relative < 0 else "false")
            + ")"
        )
    if not rendered:
        return empty_message
    return "\n#v(8pt)\n".join(rendered)


def render_performance_summary_table(rows: object) -> str:
    empty_message = '#empty-state("No governed performance summary available.")'
    rendered: list[str] = []
    for item in mapping_entries(rows):
        rendered.append(
            'performance-summary-cell("'
            + escape_typst_string(str(item.get("label", "Period")))
            + '", "'
            + escape_typst_string(group_digits(item.get("net_return_pct", "Not available")))
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
        + escape_typst_string(group_digits(item.get("twr_pct", "Not available")))
        + '", "'
        + escape_typst_string(group_digits(item.get("cumulative_twr_pct", "Not available")))
        + '", '
        + geometry.magnitude
        + ", "
        + ("true" if geometry.is_negative else "false")
        + ")"
    )


def render_performance_chart_rows(rows: object, *, two_column: bool = False) -> str:
    empty_message = '#empty-state("No performance history available.", size: 8pt)'
    entries = mapping_entries(rows)
    if not entries:
        return empty_message
    # One domain for the whole series: bars are only comparable to each other if
    # every bar in the chart is drawn against the same scale.
    domain = performance_bar_domain(item.get("twr_pct") for item in entries)
    rendered = [_performance_chart_row(item, domain) for item in entries]
    scale_note = f'\n#v(4pt)\n#chart-scale-note("{domain:.2f}%")'
    if two_column:
        return (
            "#grid(columns: (1fr, 1fr), column-gutter: 12pt, row-gutter: 1.5pt,\n"
            + ",\n".join(rendered)
            + "\n)"
            + scale_note
        )
    rendered = [f"#{row}" for row in rendered]
    return "\n#v(1.5pt)\n".join(rendered) + scale_note


def render_performance_detail_rows(rows: object) -> str:
    empty_message = '#empty-state("No monthly performance detail available.", size: 8pt)'
    rendered: list[str] = []
    for item in mapping_entries(rows):
        rendered.append(
            '#performance-detail-row("'
            + escape_typst_string(str(item.get("period", "n/a")))
            + '", "'
            + escape_typst_string(group_digits(item.get("final_value", "Not available")))
            + '", "'
            + escape_typst_string(group_digits(item.get("inflows", "Not available")))
            + '", "'
            + escape_typst_string(group_digits(item.get("outflows", "Not available")))
            + '", "'
            + escape_typst_string(group_digits(item.get("performance_value", "Not available")))
            + '", "'
            + escape_typst_string(group_digits(item.get("twr_pct", "Not available")))
            + '", "'
            + escape_typst_string(
                group_digits(item.get("cumulative_performance_value", "Not available"))
            )
            + '", "'
            + escape_typst_string(group_digits(item.get("cumulative_twr_pct", "Not available")))
            + '")'
        )
    if not rendered:
        return empty_message
    return "\n#v(2pt)\n".join(rendered)


def render_holding_rows(holdings: object) -> str:
    rendered: list[str] = []
    for item in mapping_entries(holdings):
        rendered.append(
            '#holding-row("'
            + escape_typst_string(str(item.get("security_name", "Unknown holding")))
            + '", "'
            + escape_typst_string(str(item.get("asset_class", "Not available")))
            + '", "'
            + escape_typst_string(group_digits(item.get("weight_pct", "Not available")))
            + '", "'
            + escape_typst_string(group_digits(item.get("market_value", "Not available")))
            + '", "'
            + escape_typst_string(group_digits(item.get("unrealized_pnl", "Not available")))
            + '", "'
            + escape_typst_string(group_digits(item.get("ytd_contribution_pct", "Not available")))
            + '")'
        )
    if not rendered:
        return '#empty-state("No governed holdings available.")'
    return "\n#v(8pt)\n".join(rendered)


def render_holding_bar_rows(holdings: object) -> str:
    rendered: list[str] = []
    for item in mapping_entries(holdings):
        rendered.append(
            '#allocation-row("'
            + escape_typst_string(str(item.get("security_name", "Unknown holding")))
            + '", "'
            + escape_typst_string(group_digits(item.get("weight_pct", "Not available")))
            + '", "'
            + escape_typst_string(group_digits(item.get("market_value", "Not available")))
            + '", '
            + weight_width_token(item.get("weight_pct"))
            + ")"
        )
    if not rendered:
        return '#empty-state("No governed allocation rows available.")'
    return "\n#v(8pt)\n".join(rendered)


# A colspan cell so the empty state is a row of the table rather than a stray block
# outside it, which would sit above the repeating header on later pages.
DENSE_POSITION_COLUMNS = 8
_NO_POSITIONS_CELL = (
    f"table.cell(colspan: {DENSE_POSITION_COLUMNS})"
    '[#empty-state("No position detail available.", size: 8pt)],'
)


DENSE_TRANSACTION_COLUMNS = 7
_NO_TRANSACTIONS_CELL = (
    f"table.cell(colspan: {DENSE_TRANSACTION_COLUMNS})"
    '[#empty-state("No transaction detail available.", size: 8pt)],'
)


def render_dense_position_rows(holdings: object) -> str:
    """Rows for a Typst ``table``: comma-terminated calls the template spreads.

    They used to be standalone ``#grid`` blocks, each drawing its own rule, so nothing
    could repeat a header on page 2 and a rule could land alone at the top of a page
    (issue #138). As table rows the header repeats by construction and the separator
    belongs to the row.
    """
    rendered: list[str] = []
    for item in mapping_entries(holdings):
        number_amount = (
            f"{group_digits(item.get('quantity', 'Not available'))} {item.get('currency', '')};"
            f"{item.get('security_id', 'Not available')}"
        )
        description = (
            f"{item.get('security_name', 'Unknown holding')}; "
            f"{item.get('instrument_name', 'Not available')}; "
            f"ISIN {item.get('isin', 'Not available')}"
        )
        classification = (
            f"{item.get('rating', 'Not available')};"
            f"{item.get('sector', 'Not available')};"
            f"{group_digits(item.get('duration', 'Not available'))};"
            f"{item.get('yield_to_maturity', item.get('yield_pct', 'Not available'))}"
        )
        cost_basis = (
            f"{item.get('cost_price', item.get('average_cost_price', 'Not available'))};"
            f"{group_digits(item.get('exchange_rate', 'Not available'))};"
            f"{group_digits(item.get('cost_basis_local', 'Not available'))};"
            f"{item.get('held_since_date', 'Not available')}"
        )
        market_price_date = item.get(
            "market_price_date",
            item.get("price_date", item.get("position_date", "Not available")),
        )
        market_value = (
            f"{group_digits(item.get('market_price', 'Not available'))};"
            f"{group_digits(item.get('exchange_rate', 'Not available'))};"
            f"{market_price_date};"
            f"{group_digits(item.get('ytd_total_return_pct', 'Not available'))}"
        )
        gain_loss = (
            f"{group_digits(item.get('unrealized_pnl_pct', 'Not available'))};"
            f"{item.get('currency', 'Not available')};"
            f"{group_digits(item.get('unrealized_pnl', 'Not available'))}"
        )
        accrued_interest = item.get(
            "accrued_interest",
            item.get("accrued_interest_reporting_currency", "Not available"),
        )
        performance = (
            f"{group_digits(item.get('market_value', 'Not available'))};{accrued_interest}"
        )
        rendered.append(
            'dense-position-row("'
            + escape_typst_string(str(item.get("asset_class", "Not available")))
            + '", "'
            + escape_typst_string(number_amount)
            + '", "'
            + escape_typst_string(description)
            + '", "'
            + escape_typst_string(classification)
            + '", "'
            + escape_typst_string(cost_basis)
            + '", "'
            + escape_typst_string(market_value)
            + '", "'
            + escape_typst_string(gain_loss)
            + '", "'
            + escape_typst_string(performance)
            + '", "'
            + escape_typst_string(group_digits(item.get("weight_pct", "Not available")))
            + '"),'
        )
    if not rendered:
        return _NO_POSITIONS_CELL
    return "\n".join(rendered)


def render_dense_transaction_rows(transactions: object) -> str:
    rendered: list[str] = []
    for item in mapping_entries(transactions):
        detail_primary = (
            f"{item.get('display_label', 'Transaction')}  |  "
            f"{item.get('transaction_type', 'Not available')}  |  "
            f"Category {item.get('transaction_category', 'Not available')}  |  "
            f"Asset class {item.get('asset_class', 'Not available')}"
        )
        detail_secondary = (
            f"Reference {item.get('transaction_id', 'Not available')}  |  "
            f"Security {item.get('security_id', 'Not available')}  |  "
            f"Instrument {item.get('instrument_id', 'Not available')}"
        )
        trade_date = (
            f"{item.get('trade_date', 'Not available')};"
            f"{item.get('value_date', item.get('settlement_date', 'Not available'))}"
        )
        booking_text = (
            f"{item.get('booking_text', 'Not available')};"
            f"{item.get('display_label', 'Not available')}"
        )
        price = (
            f"{group_digits(item.get('price', 'Not available'))};"
            f"{item.get('reporting_currency', '')};"
            f"{group_digits(item.get('gross_amount_reporting_currency', 'Not available'))};"
            f"{item.get('place_of_execution', '')}"
        )
        gain = (
            f"{group_digits(item.get('price', 'Not available'))};"
            f"{item.get('reporting_currency', '')};"
            f"{group_digits(item.get('gain_loss', 'Not available'))}"
        )
        settlement_amount = item.get(
            "settlement_amount_reporting_currency",
            item.get("settlement_amount", "Not available"),
        )
        value = (
            f"{group_digits(item.get('transaction_value', 'Not available'))};"
            f"{group_digits(item.get('net_interest_amount_reporting_currency', 'Not available'))};"
            f"{group_digits(settlement_amount)}"
        )
        rendered.append(
            'dense-transaction-row("'
            + escape_typst_string(trade_date)
            + '", "'
            + escape_typst_string(booking_text)
            + '", "'
            + escape_typst_string(group_digits(item.get("amount", "Not available")))
            + '", "'
            + escape_typst_string(str(item.get("description", "Not available")))
            + '", "'
            + escape_typst_string(detail_primary)
            + '", "'
            + escape_typst_string(detail_secondary)
            + '", "'
            + escape_typst_string(price)
            + '", "'
            + escape_typst_string(gain)
            + '", "'
            + escape_typst_string(value)
            + '"),'
        )
    if not rendered:
        return _NO_TRANSACTIONS_CELL
    return "\n".join(rendered)


def render_allocation_breakdown_rows(rows: object) -> str:
    empty = '#empty-state("No allocation detail available.", size: 8pt)'
    items = row_sequence(rows)
    if items is None:
        return empty
    aggregates = _aggregated_allocation_buckets(items)
    if not aggregates:
        return empty
    ordered = sorted(aggregates.items(), key=lambda entry: entry[1]["weight"], reverse=True)
    rendered = [
        '#compact-allocation-row("'
        + escape_typst_string(name)
        + '", "'
        + escape_typst_string(format_percent(totals["weight"]))
        + '", "'
        + escape_typst_string(format_money(totals["value"]))
        + '", '
        + f"{min(max(totals['weight'], 8.0), 100.0):.2f}%"
        + ")"
        for name, totals in ordered
    ]
    return "\n#v(4pt)\n".join(rendered)


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


def supplemental_allocation_view(
    allocation_breakdowns: Mapping[str, object],
) -> tuple[str, str]:
    candidate_views = [
        ("By currency", allocation_breakdowns.get("by_currency")),
        ("By region", allocation_breakdowns.get("by_region")),
        ("By sector", allocation_breakdowns.get("by_sector")),
        ("By country", allocation_breakdowns.get("by_country")),
        ("By product type", allocation_breakdowns.get("by_product_type")),
        ("By rating", allocation_breakdowns.get("by_rating")),
    ]
    for title, rows in candidate_views:
        rendered = render_allocation_breakdown_rows(rows)
        if "No allocation detail available." not in rendered:
            return title, rendered
    return "Allocation detail", render_allocation_breakdown_rows([])
