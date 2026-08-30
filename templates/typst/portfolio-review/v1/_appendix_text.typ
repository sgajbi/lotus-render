// Reference copy for the appendix, keyed by the entries `appendix_glossary.py` selects.
//
// Each definition describes what Lotus computes, not a textbook. Where a figure has a
// method, the method is named: the volatility here is the annualised sample standard
// deviation lotus-risk calculates, and the time-weighted return is geometrically linked
// as lotus-performance links it. A document that defines a measure differently from the
// service that produced it is worse than one that defines nothing.
//
// The copy lives beside the rest of the document's words rather than in Python, so a
// change to a definition moves the template digest and has to be re-approved.

#let GLOSSARY = (
  //  Performance measurement
  net_performance: (
    term: "Net performance",
    body: "Performance after the fees and charges applied to the portfolio over the period. Fees are treated as a drag on performance rather than as money you added or withdrew, so they reduce the return rather than the measured cash flow.",
  ),
  time_weighted_return: (
    term: "Time-weighted return (TWR)",
    body: "The return on the portfolio with the effect of money moving in and out removed, so it measures how the investments performed rather than when you added to or drew from them. Returns for the sub-periods are linked geometrically, which is the basis on which portfolios are compared with each other and with a benchmark.",
  ),
  cumulative_return: (
    term: "Cumulative return",
    body: "The compounded return from the start of the series to the date shown, formed by linking each period geometrically. Because the periods compound rather than add, a cumulative figure is not the sum of the column above it.",
  ),
  inflows_and_outflows: (
    term: "Inflows and outflows",
    body: "Money paid into and taken out of the portfolio during the period. They change what the portfolio is worth but not its time-weighted return, which is calculated with their effect removed.",
  ),
  annualisation: (
    term: "Annualised figures",
    body: "A figure described as annualised is expressed as the equivalent rate for a full year, scaled by the number of observation periods in a year. Annualising a short window projects that window forward and will overstate both gains and losses.",
  ),
  benchmark: (
    term: "Benchmark",
    body: "The reference index or blend the mandate is measured against, valued on the same dates and stated in the same reporting currency as the portfolio so the comparison is like for like.",
  ),
  relative_return: (
    term: "Relative return",
    body: "The portfolio return less the benchmark return over the same period, also called active return. A positive figure means the portfolio finished ahead of its benchmark over that period.",
  ),

  //  Risk measures. Each is the calculation lotus-risk performs.
  volatility: (
    term: "Volatility",
    body: "The annualised standard deviation of the portfolio return series: the sample standard deviation of the periodic returns, scaled by the square root of the number of periods in a year. It describes how widely returns have varied around their average, and is not by itself a statement about the chance of a loss.",
  ),
  beta: (
    term: "Beta",
    body: "The portfolio return's sensitivity to the benchmark return, calculated as the covariance between the two divided by the variance of the benchmark. A beta of 1.0 has moved with the benchmark, below 1.0 has moved less than it, and above 1.0 has moved more.",
  ),
  tracking_error: (
    term: "Tracking error",
    body: "The annualised standard deviation of active return, the difference between the portfolio and benchmark returns in each period. It measures how closely the portfolio has followed its benchmark, and is low for a portfolio that stays near it whether it is ahead or behind.",
  ),
  information_ratio: (
    term: "Information ratio",
    body: "Annualised active return divided by annualised tracking error, so it states the active return earned for each unit of risk taken away from the benchmark. Steady outperformance produces a higher ratio than the same total gained unevenly.",
  ),
  value_at_risk: (
    term: "Value at risk (VaR)",
    body: "An estimate of the loss the portfolio would not be expected to exceed over the stated horizon at the stated confidence level, taken from the distribution of its observed returns and scaled to that horizon. It is an estimate of a threshold rather than a worst case: losses beyond it are possible, and their size is what the figure does not describe.",
  ),

  //  Asset allocation
  asset_class: (
    term: "Asset class",
    body: "The grouping used to describe what the portfolio is invested in. Each holding belongs to one class, so the classes together account for the invested portfolio.",
  ),
  market_value: (
    term: "Market value",
    body: "What a holding is worth at the prices used for this report, converted into the reporting currency at the exchange rates of the same valuation date.",
  ),
  weight: (
    term: "Weight",
    body: "A holding or group stated as a percentage of the portfolio value on the valuation date. Weights are calculated on market value, so they move with prices as well as with what is bought and sold.",
  ),
  invested_value: (
    term: "Invested value",
    body: "The total market value of the portfolio on the valuation date, in the reporting currency. Where a chart or table covers only part of it, that is stated with the chart.",
  ),
  currency_exposure: (
    term: "Currency exposure",
    body: "Holdings grouped by the currency they are denominated in. It shows where the portfolio value would move if exchange rates moved, before the effect of any hedging.",
  ),

  //  Positions
  cost_value: (
    term: "Cost value",
    body: "What was paid to acquire the holding, in the reporting currency. It is the basis against which unrealised profit or loss is measured.",
  ),
  unrealised_profit_and_loss: (
    term: "Unrealised profit and loss",
    body: "The difference between a holding's market value and its cost value while the holding is still owned. It changes with every valuation and is fixed only when the holding is sold.",
  ),
  market_gain: (
    term: "Market gain",
    body: "The part of a holding's profit or loss that comes from the price of the instrument moving, measured in the currency the instrument is denominated in.",
  ),
  exchange_gain: (
    term: "Exchange gain",
    body: "The part of a holding's profit or loss that comes from the exchange rate between its own currency and the reporting currency moving, rather than from its price. A holding whose price has not changed can still show a gain or a loss here.",
  ),
  accrued_interest: (
    term: "Accrued interest",
    body: "Interest a holding has earned but not yet paid at the valuation date. It is carried in the holding's value so the figure reflects what is owed to the portfolio as well as what it holds.",
  ),

  //  Transactions
  trade_and_value_date: (
    term: "Trade date and value date",
    body: "The trade date is when the transaction was agreed; the value date is when the cash and the securities actually change hands. A transaction agreed near the end of a period can settle in the following one, which is why the two dates are both shown.",
  ),
  transaction_value: (
    term: "Transaction value",
    body: "The consideration for the transaction at the transaction price, before brokerage, taxes and other charges.",
  ),
  settlement_amount: (
    term: "Settlement amount",
    body: "The amount that actually moved on the value date, after brokerage, taxes and other charges have been applied to the transaction value.",
  ),
  realised_profit_and_loss: (
    term: "Realised profit and loss",
    body: "Profit or loss fixed at the point of sale: the proceeds less the cost value of what was sold. It is what unrealised profit or loss becomes once a holding is disposed of.",
  ),
)
