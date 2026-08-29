"""Portfolio-review table and chart fragment emitters.

Pure functions that turn governed report data into Typst source fragments for
the performance, holdings, positions, transactions and allocation tables.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.services.portfolio_charts import (
    allocation_items_from_report_data,
    performance_series_from_report_data,
)
from app.services.typst_values import (
    escape_typst_text,
    parse_number,
    parse_percent,
    percent_width_token,
    performance_width_token,
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
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes, bytearray)):
        return "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed observations available.]"
    rendered: list[str] = []
    for item in observations:
        text = escape_typst_text(str(item))
        rendered.append(f'#review-note("{text}")')
    return "\n#v(8pt)\n".join(rendered)


def render_performance_period_rows(periods: object) -> str:
    empty_message = (
        "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed performance periods available.]"
    )
    if not isinstance(periods, Sequence) or isinstance(periods, (str, bytes, bytearray)):
        return empty_message
    rendered: list[str] = []
    for item in periods:
        if not isinstance(item, Mapping):
            continue
        rendered.append(
            '#period-row("'
            + escape_typst_text(str(item.get("period", "n/a")))
            + '", "'
            + escape_typst_text(str(item.get("net_return_pct", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("benchmark_return_pct", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("relative_return_pct", "Not available")))
            + '")'
        )
    if not rendered:
        return empty_message
    return "\n#v(8pt)\n".join(rendered)


def render_performance_bar_rows(periods: object) -> str:
    empty_message = (
        "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed performance bars available.]"
    )
    if not isinstance(periods, Sequence) or isinstance(periods, (str, bytes, bytearray)):
        return empty_message
    rendered: list[str] = []
    for item in periods:
        if not isinstance(item, Mapping):
            continue
        rendered.append(
            '#performance-bar-row("'
            + escape_typst_text(str(item.get("period", "n/a")))
            + '", "'
            + escape_typst_text(str(item.get("net_return_pct", "Not available")))
            + '", '
            + percent_width_token(item.get("net_return_pct"))
            + ")"
        )
    if not rendered:
        return empty_message
    return "\n#v(8pt)\n".join(rendered)


def render_performance_summary_table(rows: object) -> str:
    empty_message = (
        "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed performance summary available.]"
    )
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return empty_message
    rendered: list[str] = []
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        rendered.append(
            'performance-summary-cell("'
            + escape_typst_text(str(item.get("label", "Period")))
            + '", "'
            + escape_typst_text(str(item.get("net_return_pct", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("annualized_return_pct", "n/a")))
            + '")'
        )
    if not rendered:
        return empty_message
    return (
        "#grid(columns: (1fr, 1fr, 1fr, 1fr, 1fr), column-gutter: 7pt,\n"
        + ",\n".join(rendered)
        + "\n)"
    )


def render_performance_chart_rows(rows: object, *, two_column: bool = False) -> str:
    empty_message = "#text(size: 8pt, fill: rgb(104, 118, 132))[No performance history available.]"
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return empty_message
    rendered: list[str] = []
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        rendered.append(
            'performance-chart-row("'
            + escape_typst_text(str(item.get("period", "n/a")))
            + '", "'
            + escape_typst_text(str(item.get("twr_pct", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("cumulative_twr_pct", "Not available")))
            + '", '
            + performance_width_token(item.get("twr_pct"))
            + ")"
        )
    if not rendered:
        return empty_message
    if two_column:
        return (
            "#grid(columns: (1fr, 1fr), column-gutter: 12pt, row-gutter: 1.5pt,\n"
            + ",\n".join(rendered)
            + "\n)"
        )
    rendered = [f"#{row}" for row in rendered]
    return "\n#v(1.5pt)\n".join(rendered)


def render_performance_detail_rows(rows: object) -> str:
    empty_message = (
        "#text(size: 8pt, fill: rgb(104, 118, 132))[No monthly performance detail available.]"
    )
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return empty_message
    rendered: list[str] = []
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        rendered.append(
            '#performance-detail-row("'
            + escape_typst_text(str(item.get("period", "n/a")))
            + '", "'
            + escape_typst_text(str(item.get("final_value", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("inflows", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("outflows", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("performance_value", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("twr_pct", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("cumulative_performance_value", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("cumulative_twr_pct", "Not available")))
            + '")'
        )
    if not rendered:
        return empty_message
    return "\n#v(2pt)\n".join(rendered)


def render_holding_rows(holdings: object) -> str:
    if not isinstance(holdings, Sequence) or isinstance(holdings, (str, bytes, bytearray)):
        return "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed holdings available.]"
    rendered: list[str] = []
    for item in holdings:
        if not isinstance(item, Mapping):
            continue
        rendered.append(
            '#holding-row("'
            + escape_typst_text(str(item.get("security_name", "Unknown holding")))
            + '", "'
            + escape_typst_text(str(item.get("asset_class", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("weight_pct", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("market_value", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("unrealized_pnl", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("ytd_contribution_pct", "Not available")))
            + '")'
        )
    if not rendered:
        return "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed holdings available.]"
    return "\n#v(8pt)\n".join(rendered)


def render_holding_bar_rows(holdings: object) -> str:
    if not isinstance(holdings, Sequence) or isinstance(holdings, (str, bytes, bytearray)):
        return "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed allocation rows available.]"
    rendered: list[str] = []
    for item in holdings:
        if not isinstance(item, Mapping):
            continue
        rendered.append(
            '#allocation-row("'
            + escape_typst_text(str(item.get("security_name", "Unknown holding")))
            + '", "'
            + escape_typst_text(str(item.get("weight_pct", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("market_value", "Not available")))
            + '", '
            + percent_width_token(item.get("weight_pct"))
            + ")"
        )
    if not rendered:
        return "#text(size: 9pt, fill: rgb(104, 118, 132))[No governed allocation rows available.]"
    return "\n#v(8pt)\n".join(rendered)


def render_dense_position_rows(holdings: object) -> str:
    if not isinstance(holdings, Sequence) or isinstance(holdings, (str, bytes, bytearray)):
        return "#text(size: 8pt, fill: rgb(104, 118, 132))[No position detail available.]"
    rendered: list[str] = []
    for item in holdings:
        if not isinstance(item, Mapping):
            continue
        number_amount = (
            f"{item.get('quantity', 'Not available')} {item.get('currency', '')};"
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
            f"{item.get('duration', 'Not available')};"
            f"{item.get('yield_to_maturity', item.get('yield_pct', 'Not available'))}"
        )
        cost_basis = (
            f"{item.get('cost_price', item.get('average_cost_price', 'Not available'))};"
            f"{item.get('exchange_rate', 'Not available')};"
            f"{item.get('cost_basis_local', 'Not available')};"
            f"{item.get('held_since_date', 'Not available')}"
        )
        market_price_date = item.get(
            "market_price_date",
            item.get("price_date", item.get("position_date", "Not available")),
        )
        market_value = (
            f"{item.get('market_price', 'Not available')};"
            f"{item.get('exchange_rate', 'Not available')};"
            f"{market_price_date};"
            f"{item.get('ytd_total_return_pct', 'Not available')}"
        )
        gain_loss = (
            f"{item.get('unrealized_pnl_pct', 'Not available')};"
            f"{item.get('currency', 'Not available')};"
            f"{item.get('unrealized_pnl', 'Not available')}"
        )
        accrued_interest = item.get(
            "accrued_interest",
            item.get("accrued_interest_reporting_currency", "Not available"),
        )
        performance = f"{item.get('market_value', 'Not available')};{accrued_interest}"
        rendered.append(
            '#dense-position-row("'
            + escape_typst_text(str(item.get("asset_class", "Not available")))
            + '", "'
            + escape_typst_text(number_amount)
            + '", "'
            + escape_typst_text(description)
            + '", "'
            + escape_typst_text(classification)
            + '", "'
            + escape_typst_text(cost_basis)
            + '", "'
            + escape_typst_text(market_value)
            + '", "'
            + escape_typst_text(gain_loss)
            + '", "'
            + escape_typst_text(performance)
            + '", "'
            + escape_typst_text(str(item.get("weight_pct", "Not available")))
            + '")'
        )
    if not rendered:
        return "#text(size: 8pt, fill: rgb(104, 118, 132))[No position detail available.]"
    return "\n#v(4pt)\n".join(rendered)


def render_dense_transaction_rows(transactions: object) -> str:
    if not isinstance(transactions, Sequence) or isinstance(transactions, (str, bytes, bytearray)):
        return "#text(size: 8pt, fill: rgb(104, 118, 132))[No transaction detail available.]"
    rendered: list[str] = []
    for item in transactions:
        if not isinstance(item, Mapping):
            continue
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
            f"{item.get('price', 'Not available')};"
            f"{item.get('reporting_currency', '')};"
            f"{item.get('gross_amount_reporting_currency', 'Not available')};"
            f"{item.get('place_of_execution', '')}"
        )
        gain = (
            f"{item.get('price', 'Not available')};"
            f"{item.get('reporting_currency', '')};"
            f"{item.get('gain_loss', 'Not available')}"
        )
        settlement_amount = item.get(
            "settlement_amount_reporting_currency",
            item.get("settlement_amount", "Not available"),
        )
        value = (
            f"{item.get('transaction_value', 'Not available')};"
            f"{item.get('net_interest_amount_reporting_currency', 'Not available')};"
            f"{settlement_amount}"
        )
        rendered.append(
            '#dense-transaction-row("'
            + escape_typst_text(trade_date)
            + '", "'
            + escape_typst_text(booking_text)
            + '", "'
            + escape_typst_text(str(item.get("amount", "Not available")))
            + '", "'
            + escape_typst_text(str(item.get("description", "Not available")))
            + '", "'
            + escape_typst_text(detail_primary)
            + '", "'
            + escape_typst_text(detail_secondary)
            + '", "'
            + escape_typst_text(price)
            + '", "'
            + escape_typst_text(gain)
            + '", "'
            + escape_typst_text(value)
            + '")'
        )
    if not rendered:
        return "#text(size: 8pt, fill: rgb(104, 118, 132))[No transaction detail available.]"
    return "\n#v(4pt)\n".join(rendered)


def render_allocation_breakdown_rows(rows: object) -> str:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return "#text(size: 8pt, fill: rgb(104, 118, 132))[No allocation detail available.]"
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
    if not aggregates:
        return "#text(size: 8pt, fill: rgb(104, 118, 132))[No allocation detail available.]"
    ordered = sorted(aggregates.items(), key=lambda entry: entry[1]["weight"], reverse=True)
    rendered: list[str] = []
    for name, totals in ordered:
        rendered.append(
            '#compact-allocation-row("'
            + escape_typst_text(name)
            + '", "'
            + escape_typst_text(f"{totals['weight']:.2f}%")
            + '", "'
            + escape_typst_text(f"{totals['value']:.2f}")
            + '", '
            + f"{min(max(totals['weight'], 8.0), 100.0):.2f}%"
            + ")"
        )
    return "\n#v(4pt)\n".join(rendered)


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
