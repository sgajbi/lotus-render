"""What the positions and transactions tables show, declared once each.

Every field here reads something a render package actually carries. Fields that read
nothing are removed from the table before it is drawn, so this declaration describes the
most a document can show rather than what every document will show.

Everything the contract supports stays declared, including the fields the banked
fixtures happen not to carry -- cost price, exchange rate, duration, yield and accrued
interest on positions; value date, settlement amount and place of execution on
transactions. Declaring them costs nothing when they are absent, because a field no row
supplies is removed before the table is drawn. That is the difference from what this
replaces: those fields were labelled in the header and printed as "Not available" on
every row of every document, whether the data existed or not.

Two things stay deleted rather than declared: the positions table's "Sustainability"
line, whose value was the literal string "Sustainability / instrument details", and the
transactions table's "Brokerage", "Tax", "Custody account" and "Account" labels, which
had no accessor at all behind them. They were labels for figures that were never going
to arrive from anywhere.
"""

from __future__ import annotations

from app.services.statement_tables import (
    Row,
    StatementColumn,
    StatementField,
    joined,
    text_of,
)

_security_name = text_of("security_name")
_instrument_name = text_of("instrument_name")


def _description(row: Row) -> str | None:
    """What the holding is, preferring the name the client would recognise."""
    return _security_name(row) or _instrument_name(row)


def _instrument_when_distinct(row: Row) -> str | None:
    """The instrument name, only where it says something the description does not.

    Every fixture carries the same string in both, so this line printed the holding's
    name twice on every row.
    """
    instrument = _instrument_name(row)
    return None if instrument is None or instrument == _description(row) else instrument


_booking_text = text_of("booking_text")
_display_label = text_of("display_label")


def _booking(row: Row) -> str | None:
    """The booking narrative. `display_label` repeats it in every fixture."""
    return _booking_text(row) or _display_label(row)


POSITION_COLUMNS: tuple[StatementColumn, ...] = (
    StatementColumn(
        width="0.9fr",
        placement="left",
        fields=(
            StatementField("Category", text_of("asset_class")),
            StatementField(
                "Number/Amount",
                joined(
                    (("", text_of("quantity", money=True)), ("", text_of("currency"))),
                    separator=" ",
                ),
                tone="ink",
            ),
            StatementField("Reference", text_of("security_id")),
        ),
    ),
    StatementColumn(
        width="2.0fr",
        placement="left",
        fields=(
            StatementField("Description", _description, tone="ink", size="8.1pt"),
            StatementField("Instrument", _instrument_when_distinct),
            StatementField("ISIN", text_of("isin", prefix="ISIN ")),
        ),
    ),
    StatementColumn(
        width="1.05fr",
        fields=(
            StatementField("Rating", text_of("rating")),
            StatementField("Sector", text_of("sector")),
            StatementField("Duration", text_of("duration", money=True)),
            StatementField("Yield", text_of("yield_to_maturity", "yield_pct")),
            StatementField("Country of risk", text_of("country_of_risk")),
            StatementField("Liquidity", text_of("liquidity_tier")),
        ),
    ),
    StatementColumn(
        width="1.05fr",
        fields=(
            StatementField("Cost price", text_of("cost_price", "average_cost_price", money=True)),
            StatementField(
                "Cost value",
                text_of("cost_basis_reporting_currency", "cost_basis_local", money=True),
            ),
            StatementField("Exchange rate", text_of("exchange_rate", money=True)),
            StatementField("Held since", text_of("held_since_date", date=True)),
            StatementField("Product type", text_of("product_type")),
        ),
    ),
    StatementColumn(
        width="1.05fr",
        fields=(
            StatementField("Market price", text_of("market_price", money=True), tone="ink"),
            StatementField(
                "Market price date",
                text_of("market_price_date", "price_date", "position_date", date=True),
            ),
            StatementField(
                "YTD performance", text_of("ytd_total_return_pct"), tone="accent", weight=500
            ),
        ),
    ),
    StatementColumn(
        width="1.05fr",
        fields=(
            StatementField("Unrealized P/L", text_of("unrealized_pnl", money=True), tone="ink"),
            StatementField("Unrealized P/L %", text_of("unrealized_pnl_pct")),
            StatementField("Contribution", text_of("ytd_contribution_pct")),
        ),
    ),
    StatementColumn(
        width="1.0fr",
        fields=(
            StatementField("Market value", text_of("market_value", money=True), tone="ink"),
            StatementField(
                "Accrued interest",
                text_of("accrued_interest", "accrued_interest_reporting_currency", money=True),
            ),
            StatementField("Average weight", text_of("ytd_average_weight_pct")),
        ),
    ),
    StatementColumn(
        width="0.55fr",
        fields=(StatementField("%", text_of("weight_pct"), tone="ink"),),
    ),
)

TRANSACTION_COLUMNS: tuple[StatementColumn, ...] = (
    StatementColumn(
        width="0.8fr",
        placement="left",
        fields=(
            StatementField("Trade date", text_of("trade_date", date=True), tone="ink"),
            StatementField("Value date", text_of("value_date", "settlement_date", date=True)),
            StatementField("Category", text_of("transaction_category")),
        ),
    ),
    StatementColumn(
        width="0.9fr",
        placement="left",
        fields=(
            StatementField("Booking text", _booking, tone="ink"),
            StatementField("Type", text_of("transaction_type")),
        ),
    ),
    StatementColumn(
        width="0.9fr",
        fields=(StatementField("Number/Amount", text_of("amount", money=True), tone="ink"),),
    ),
    StatementColumn(
        width="2.4fr",
        placement="left",
        fields=(
            StatementField("Description", text_of("description"), tone="ink", size="8.1pt"),
            StatementField(
                "Reference",
                joined(
                    (
                        ("Reference", text_of("transaction_id")),
                        ("Security", text_of("security_id")),
                        ("Instrument", text_of("instrument_id")),
                    )
                ),
                size="6.8pt",
            ),
        ),
    ),
    StatementColumn(
        width="0.95fr",
        fields=(
            StatementField("Transaction price", text_of("price", money=True), tone="ink"),
            StatementField("Gross amount", text_of("gross_amount_reporting_currency", money=True)),
            StatementField("Place of execution", text_of("place_of_execution")),
        ),
    ),
    StatementColumn(
        width="0.95fr",
        fields=(
            StatementField("Realized P/L", text_of("realized_pnl_reporting_currency", money=True)),
            StatementField("Gain/loss", text_of("gain_loss", money=True)),
        ),
    ),
    StatementColumn(
        width="1.0fr",
        fields=(
            StatementField(
                "Transaction value",
                text_of("transaction_value", money=True),
                tone="accent",
                weight=500,
            ),
            StatementField(
                "Net interest", text_of("net_interest_amount_reporting_currency", money=True)
            ),
            StatementField(
                "Settlement amount",
                text_of("settlement_amount_reporting_currency", "settlement_amount", money=True),
            ),
            StatementField(
                "Withholding tax", text_of("withholding_tax_amount_reporting_currency", money=True)
            ),
        ),
    ),
)
