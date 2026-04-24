#import "_theme.typ": accent, ink, rule, slate, soft-rule
#import "_appendix_text.typ": *

#let appendix-small = 6.65pt
#let appendix-body = 7.15pt
#let appendix-caption = 6.4pt

#let appendix-title() = [
  #grid(
    columns: (1.08fr, 0.72fr, 0.46fr),
    column-gutter: 22pt,
    [#text(size: 19.5pt, weight: 300, fill: ink)[Abbreviations and explanations]],
    [
      #set par(leading: 0.8em)
      #text(size: 6.8pt, fill: slate)[Statement of assets as of ${AS_OF_DATE}]
      #linebreak()
      #text(size: 6.8pt, fill: slate)[Produced for portfolio review]
    ],
    [
      #align(right)[
        #set par(leading: 0.84em)
        #text(size: 7.1pt, weight: 600, fill: ink)[Overview]
        #linebreak()
        #text(size: 7.1pt, weight: 600, fill: ink)[Asset evaluations]
        #linebreak()
        #text(size: 7.1pt, weight: 600, fill: ink)[Detailed positions]
        #linebreak()
        #text(size: 7.1pt, weight: 600, fill: ink)[Transactions]
        #linebreak()
        #text(size: 7.1pt, weight: 600, fill: accent)[Additional information]
      ]
    ],
  )
  #v(20pt)
]

#let appendix-section-title(title) = [
  #v(4pt)
  #text(size: 7.6pt, weight: 650, fill: ink)[#title]
  #v(2pt)
  #soft-rule()
  #v(4pt)
]

#let appendix-gap() = v(7pt)

#let appendix-def(title, body) = [
  #set par(justify: true, leading: 0.82em)
  #text(size: appendix-body, weight: 650, fill: ink)[#title]
  #text(size: appendix-body, fill: ink)[: #body]
]

#let appendix-compact-def(title, body) = [
  #set par(justify: true, leading: 0.78em)
  #text(size: 6.8pt, weight: 650, fill: ink)[#title]
  #text(size: 6.8pt, fill: ink)[: #body]
]

#let appendix-note(body) = [
  #set par(justify: true, leading: 0.84em)
  #text(size: appendix-body, fill: slate)[#body]
]

#let appendix-columns(left, middle, right) = [
  #grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 22pt,
    [
      #set par(justify: true, leading: 0.84em)
      #left
    ],
    [
      #set par(justify: true, leading: 0.84em)
      #middle
    ],
    [
      #set par(justify: true, leading: 0.84em)
      #right
    ],
  )
]

#let fx-cell(name, base, quote, rate, reverse) = [
  #text(size: 8.4pt, weight: 650, fill: ink)[#name]
  #v(2pt)
  #grid(
    columns: (0.34fr, 0.22fr, 0.34fr, 0.46fr),
    column-gutter: 5pt,
    row-gutter: 1pt,
    [#text(size: 8.1pt, fill: slate)[#base]],
    [#text(size: 8.1pt, fill: slate)[1 =]],
    [#text(size: 8.1pt, fill: slate)[#quote]],
    [#align(right)[#text(size: 8.1pt, fill: slate)[#rate]]],
    [#text(size: 8.1pt, fill: slate)[#quote]],
    [#text(size: 8.1pt, fill: slate)[1 =]],
    [#text(size: 8.1pt, fill: slate)[#base]],
    [#align(right)[#text(size: 8.1pt, fill: slate)[#reverse]]],
  )
]

#let abbreviation-grid() = [
  #grid(
    columns: (0.35fr, 1.65fr, 0.35fr, 1.65fr, 0.35fr, 1.65fr),
    column-gutter: 12pt,
    row-gutter: 2pt,
    [#text(size: appendix-small, fill: slate)[000]], [#text(size: appendix-small, fill: slate)[In thousands]],
    [#text(size: appendix-small, fill: slate)[MWR]], [#text(size: appendix-small, fill: slate)[Money weighted rate of return]],
    [#text(size: appendix-small, fill: slate)[n.a.]], [#text(size: appendix-small, fill: slate)[Not available]],
    [#text(size: appendix-small, fill: slate)[DY]], [#text(size: appendix-small, fill: slate)[Direct yield]],
    [#text(size: appendix-small, fill: slate)[Mio]], [#text(size: appendix-small, fill: slate)[In millions]],
    [#text(size: appendix-small, fill: slate)[p.m.]], [#text(size: appendix-small, fill: slate)[Pro memoria]],
    [#text(size: appendix-small, fill: slate)[E]], [#text(size: appendix-small, fill: slate)[Estimated rate]],
    [#text(size: appendix-small, fill: slate)[NA]], [#text(size: appendix-small, fill: slate)[Net assets]],
    [#text(size: appendix-small, fill: slate)[u]], [#text(size: appendix-small, fill: slate)[Position split up into the asset structure due to the investment structure]],
    [#text(size: appendix-small, fill: slate)[GA]], [#text(size: appendix-small, fill: slate)[Gross assets]],
    [#text(size: appendix-small, fill: slate)[Pp]], [#text(size: appendix-small, fill: slate)[Perpetual]],
    [#text(size: appendix-small, fill: slate)[z]], [#text(size: appendix-small, fill: slate)[Individual adjustment of cost price according to client order]],
    [#text(size: appendix-small, fill: slate)[GTY]], [#text(size: appendix-small, fill: slate)[Gross theoretical yield maturity]],
    [#text(size: appendix-small, fill: slate)[TWR]], [#text(size: appendix-small, fill: slate)[Time weighted rate of return]],
    [], [],
    [#text(size: appendix-small, fill: slate)[M]], [#text(size: appendix-small, fill: slate)[Middle rate]],
    [#text(size: appendix-small, fill: slate)[Y]], [#text(size: appendix-small, fill: slate)[Yield to end maturity]],
    [], [],
  )
]

#let risk-box(code, color, title, body, expected-return, volatility, drawdown, years) = [
  #grid(
    columns: (24pt, 1fr),
    column-gutter: 9pt,
    [#rect(width: 24pt, height: 24pt, radius: 1pt, fill: color)[#align(center + horizon)[#text(size: 9.5pt, weight: 700, fill: white)[#code]]]],
    [
      #set par(leading: 0.82em)
      #text(size: 7.45pt, weight: 700, fill: ink)[#title]
      #linebreak()
      #text(size: 6.55pt, fill: ink)[#body]
      #v(3pt)
      #grid(
        columns: (1fr, 70pt),
        row-gutter: 1pt,
        [#text(size: appendix-caption, fill: slate)[Expected annual return]],
        [#align(right)[#text(size: appendix-caption, fill: slate)[Approx. #expected-return]]],
        [#text(size: appendix-caption, fill: slate)[Expected annual volatility]],
        [#align(right)[#text(size: appendix-caption, fill: slate)[Approx. #volatility]]],
        [#text(size: appendix-caption, fill: slate)[Maximum historical drawdown]],
        [#align(right)[#text(size: appendix-caption, fill: slate)[Approx. #drawdown]]],
        [#text(size: appendix-caption, fill: slate)[Longest historical drawdown]],
        [#align(right)[#text(size: appendix-caption, fill: slate)[Approx. #years]]],
      )
    ],
  )
]

#let appendix-page-start() = [
  #appendix-title()
]

#let appendix-fx-and-abbreviations() = [
  #appendix-page-start()
  #appendix-section-title("Foreign exchange rates for market values in US Dollar (USD)")
  #grid(
    columns: (1fr, 1fr, 1fr),
    column-gutter: 48pt,
    [
      #fx-cell("Australian Dollar", "AUD", "USD", "0.667850", "1.497342")
      #v(12pt)
      #fx-cell("Pound Sterling", "GBP", "USD", "1.264100", "0.791077")
    ],
    [
      #fx-cell("Swiss Franc", "CHF", "USD", "1.112842", "0.898600")
      #v(12pt)
      #fx-cell("Hong Kong Dollar", "HKD", "USD", "0.128084", "7.807400")
    ],
    [
      #fx-cell("Euro", "EUR", "USD", "1.071750", "0.933053")
      #v(12pt)
      #fx-cell("Singapore Dollar", "SGD", "USD", "0.737871", "1.355250")
    ],
  )
  #v(14pt)
  #appendix-note(fx_rate_notice)
  #v(9pt)
  #appendix-section-title("Abbreviations")
  #abbreviation-grid()
]

#let appendix-risk-scale() = [
  #pagebreak()
  #appendix-page-start()
  #appendix-section-title("Overview of available risk tolerance levels in USD, valid from 29.12.2023 (previous values, valid from 30.12.2022)")
  #grid(
    columns: (1fr, 1fr),
    row-gutter: 13pt,
    column-gutter: 34pt,
    [#risk-box("A", rgb("#766f70"), "\"Very low\" / Fixed Income", risk_note_a, "4.5%   (4.5%)", "4%   (3.5%)", "-15%   (-10%)", "3 years   (2 years)")],
    [#risk-box("B", rgb("#d9b69f"), "\"Low\" / Income", risk_note_b, "5.5%   (5%)", "5.5%   (5%)", "-15%   (-15%)", "3 years   (2 years)")],
    [#risk-box("C", rgb("#bcb8b1"), "\"Moderate\" / Yield", risk_note_c, "6%   (6%)", "7%   (7%)", "-25%   (-25%)", "3 years   (3 years)")],
    [#risk-box("D", rgb("#f0bb42"), "\"Medium\" / Balanced", risk_note_d, "7%   (6.5%)", "9.5%   (9%)", "-35%   (-35%)", "4 years   (4 years)")],
    [#risk-box("E", rgb("#ea8578"), "\"Above average\" / Growth", risk_note_e, "8%   (7.5%)", "12%   (12%)", "-45%   (-45%)", "4 years   (4 years)")],
    [#risk-box("F", rgb("#b74d63"), "\"High\" / Equities", risk_note_f, "9%   (8.5%)", "15.5%   (15%)", "-55%   (-55%)", "6 years   (6 years)")],
  )
]

#let appendix-risk-and-allocation() = [
  #pagebreak()
  #appendix-page-start()
  #appendix-section-title("Risk tolerance")
  #appendix-columns(
    [
      #appendix-def("Risk tolerance", risk_tolerance)
      #appendix-gap()
      #appendix-def("Expected annual return", expected_annual_return)
    ],
    [
      #appendix-def("Expected annual volatility", expected_annual_volatility)
      #appendix-gap()
      #appendix-def("Maximum historical drawdown", maximum_historical_drawdown)
    ],
    [
      #appendix-def("Longest period of a historical drawdown", longest_historical_drawdown)
      #appendix-gap()
      #appendix-def("Risk information", risk_information)
    ],
  )
  #appendix-section-title("Asset allocation")
  #appendix-columns(
    [
      #appendix-def("General information", asset_allocation_general)
      #appendix-gap()
      #appendix-def("Unbundling", asset_allocation_unbundling)
      #appendix-gap()
      #appendix-def("Liquidity", liquidity_definition)
    ],
    [
      #appendix-def("Bonds by rating", bonds_by_rating)
      #appendix-gap()
      #appendix-def("Asset allocation", asset_allocation_definition)
      #appendix-gap()
      #appendix-def("Bonds", bonds_definition)
      #appendix-gap()
      #appendix-def("Equities", equities_definition)
    ],
    [
      #appendix-def("Hedge funds & private markets", hedge_funds_definition)
      #appendix-gap()
      #appendix-def("Real estate", real_estate_definition)
      #appendix-gap()
      #appendix-def("Others", others_definition)
    ],
  )
]

#let appendix-reporting-definitions() = [
  #pagebreak()
  #appendix-page-start()
  #appendix-section-title("Performance")
  #appendix-columns(
    [
      #appendix-def("Performance", performance_definition)
      #appendix-gap()
      #appendix-def("Net performance", net_performance_definition)
    ],
    [
      #appendix-def("Money weighted rate of return (MWR)", mwr_definition)
      #appendix-gap()
      #appendix-def("Time weighted rate of return (TWR)", twr_definition)
    ],
    [
      #appendix-def("Retroactive bookings", retroactive_bookings_performance)
    ],
  )
  #appendix-section-title("Overview of income")
  #appendix-columns(
    [
      #appendix-def("Source views", source_views)
      #appendix-gap()
      #appendix-def("Accrued interest", accrued_interest)
    ],
    [
      #appendix-def("Retroactive bookings", retroactive_bookings_income)
      #appendix-gap()
      #appendix-def("Detailed report", detailed_report)
    ],
    [
      #appendix-def("Positions overview", positions_unbundling)
    ],
  )
]

#let appendix-position-and-transaction-definitions() = [
  #pagebreak()
  #appendix-page-start()
  #appendix-section-title("Detailed positions")
  #appendix-columns(
    [
      #appendix-def("SI label", si_label)
      #appendix-gap()
      #appendix-def("ESG multiple approaches", esg_multiple_approaches)
      #appendix-gap()
      #appendix-def("ESG thematic", esg_thematic)
    ],
    [
      #appendix-def("Securities with ESG Leader attributes", esg_leader)
      #appendix-gap()
      #appendix-def("Securities with ESG Thematic attributes", esg_thematic_attributes)
      #appendix-gap()
      #appendix-def("Gross profit", gross_profit_calc)
      #appendix-gap()
      #appendix-def("Market gain", market_gain_definition)
    ],
    [
      #appendix-def("Exchange gain", exchange_gain_definition)
      #appendix-gap()
      #appendix-def("Unrealized P/L", unrealized_pl_definition)
      #appendix-gap()
      #appendix-def("Prepayment for fund subscription", prepayment_fund)
    ],
  )
  #appendix-section-title("Private Markets")
  #appendix-columns(
    [
      #appendix-def("Private Markets", private_markets)
    ],
    [],
    [],
  )
  #appendix-section-title("Transaction list")
  #appendix-columns(
    [
      #appendix-def("Content", transaction_content)
      #appendix-gap()
      #appendix-def("Transaction gain", transaction_gain_definition)
    ],
    [
      #appendix-def("Exchange gain", exchange_gain_definition)
      #appendix-gap()
      #appendix-def("Realized P/L", realized_pl_definition)
    ],
    [
      #appendix-def("Prepayment for fund subscription", prepayment_fund)
      #appendix-gap()
      #appendix-def("Pending bookings", pending_bookings)
      #appendix-gap()
      #appendix-def("Maturities", maturities_expected)
    ],
  )
]

#let appendix-health-check() = [
  #pagebreak()
  #appendix-page-start()
  #appendix-section-title("Portfolio Health Check")
  #appendix-columns(
    [
      #appendix-def("Analysis by asset class", phc_analysis_asset_class)
      #appendix-gap()
      #appendix-def("Risk/return analysis of the portfolio", phc_risk_return)
      #appendix-gap()
      #appendix-def("Instruments with negative view", phc_negative_view)
    ],
    [
      #appendix-def("Bonds with a low rating", phc_low_rating)
      #appendix-gap()
      #appendix-def("Not monitored instruments", phc_not_monitored)
      #appendix-gap()
      #appendix-compact-def("Risk analysis", phc_risk_analysis)
    ],
    [
      #appendix-def("Use of borrowed capital", phc_borrowed_capital)
      #appendix-gap()
      #appendix-def("Evaluation date", phc_evaluation_date)
      #appendix-gap()
      #appendix-def("Bulk risks", phc_bulk_risks)
      #appendix-gap()
      #appendix-def("Issuer concentrations", phc_issuer_concentrations)
    ],
  )
]

#let appendix-page() = [
  #set page(margin: (x: 11mm, y: 10mm))
  #appendix-fx-and-abbreviations()
  #appendix-risk-scale()
  #appendix-risk-and-allocation()
  #appendix-reporting-definitions()
  #appendix-position-and-transaction-definitions()
  #appendix-health-check()
]
