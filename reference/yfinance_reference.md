# yfinance API Reference (Combined)
Generated: 2026-01-22 18:19 UTC
Source root: https://ranaroussi.github.io/yfinance/reference/

## API Reference
Source: https://ranaroussi.github.io/yfinance/reference/index.html

### Overview

 The yfinance package provides easy access to Yahoo! Finances API to retrieve market data. It includes classes and functions for downloading historical market data, accessing ticker information, managing cache, and more.

  #### Public API

 The following are the publicly available classes, and functions exposed by the yfinance package:

 - [`Ticker`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html): Class for accessing single ticker data.
- [`Tickers`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Tickers.html): Class for handling multiple tickers.
- [`Market`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Market.html): Class for accessing market summary.
- [`Calendars`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Calendars.html): Class for accessing calendar events data.
- [`download`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html): Function to download market data for multiple tickers.
- [`Search`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Search.html): Class for accessing search results.
- [`Lookup`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Lookup.html): Class for looking up tickers.
- [`WebSocket`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.WebSocket.html): Class for synchronously streaming live market data.
- [`AsyncWebSocket`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.AsyncWebSocket.html): Class for asynchronously streaming live market data.
- [`Sector`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Sector.html): Domain class for accessing sector information.
- [`Industry`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Industry.html): Domain class for accessing industry information.
- [`EquityQuery`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.EquityQuery.html): Class to build equity query filters.
- [`FundQuery`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.FundQuery.html): Class to build fund query filters.
- [`screen`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.screen.html): Run equity/fund queries.
- [`enable_debug_mode`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.enable_debug_mode.html): Function to enable debug mode for logging.
- [`set_tz_cache_location`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.set_tz_cache_location.html): Function to set the timezone cache location.

## yfinance.Ticker.get_growth_estimates
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_growth_estimates.html

- **Ticker.get_growth_estimates(*as_dict=False*)**: Index: 0q +1q 0y +1y +5y -5y Columns: stock industry sector index

## yfinance.Ticker.get_splits
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_splits.html

- **Ticker.get_splits(*period='max'*)  Series**

## Calendars
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Calendars.html

- ***class*yfinance.Calendars(*start: str | datetime | date | None = None*, *end: str | datetime | date | None = None*, *session: Session | None = None*)**: Get economic calendars, for example, Earnings, IPO, Economic Events, Splits

 ### Simple example default params: ``python
import yfinance as yf
calendars = yf.Calendars()
earnings_calendar = calendars.get_earnings_calendar(limit=50)
print(earnings_calendar)
``

 - **Parameters:**: - **start** (*str**|**datetime**|**date*)  start date (default today) eg. start=2025-11-08
- **end** (*str**|**datetime**|**date*)  end date (default start + 7 days) eg. end=2025-11-08
- **session**  requests.Session object, optional

 Attributes

 - **earnings_calendar**: Earnings calendar with default settings.

 - **economic_events_calendar**: Economic events calendar with default settings.

 - **ipo_info_calendar**: IPOs calendar with default settings.

 - **splits_calendar**: Splits calendar with default settings.

 Methods

 - **__init__(*start: str | datetime | date | None = None*, *end: str | datetime | date | None = None*, *session: Session | None = None*)**: - **Parameters:**: - **start** (*str**|**datetime**|**date*)  start date (default today) eg. start=2025-11-08
- **end** (*str**|**datetime**|**date*)  end date (default start + 7 days) eg. end=2025-11-08
- **session**  requests.Session object, optional

 - **get_earnings_calendar(*market_cap: float | None = None*, *filter_most_active: bool = True*, *start=None*, *end=None*, *limit=12*, *offset=0*, *force=False*)  DataFrame**: Retrieve earnings calendar from YF as a DataFrame. Will re-query every time it is called, overwriting previous data.

 - **Parameters:**: - **market_cap**  market cap cutoff in USD, default None
- **filter_most_active**  will filter for actively traded stocks (default True)
- **start** (*str**|**datetime**|**date*)  overwrite start date (default set by __init__) eg. start=2025-11-08
- **end** (*str**|**datetime**|**date*)  overwrite end date (default set by __init__) eg. end=2025-11-08
- **limit**  maximum number of results to return (YF caps at 100)
- **offset**  offsets the results for pagination. YF default 0
- **force**  if True, will re-query even if cache already exists
- **Returns:**: DataFrame with earnings calendar

 - **get_economic_events_calendar(*start=None*, *end=None*, *limit=12*, *offset=0*, *force=False*)  DataFrame**: Retrieve Economic Events calendar from YF as a DataFrame.

 - **Parameters:**: - **start** (*str**|**datetime**|**date*)  overwrite start date (default set by __init__) eg. start=2025-11-08
- **end** (*str**|**datetime**|**date*)  overwrite end date (default set by __init__) eg. end=2025-11-08
- **limit**  maximum number of results to return (YF caps at 100)
- **offset**  offsets the results for pagination. YF default 0
- **force**  if True, will re-query even if cache already exists
- **Returns:**: DataFrame with Economic Events calendar

 - **get_ipo_info_calendar(*start=None*, *end=None*, *limit=12*, *offset=0*, *force=False*)  DataFrame**: Retrieve IPOs calendar from YF as a Dataframe.

 - **Parameters:**: - **start** (*str**|**datetime**|**date*)  overwrite start date (default set by __init__) eg. start=2025-11-08
- **end** (*str**|**datetime**|**date*)  overwrite end date (default set by __init__) eg. end=2025-11-08
- **limit**  maximum number of results to return (YF caps at 100)
- **offset**  offsets the results for pagination. YF default 0
- **force**  if True, will re-query even if cache already exists
- **Returns:**: DataFrame with IPOs calendar

 - **get_splits_calendar(*start=None*, *end=None*, *limit=12*, *offset=0*, *force=False*)  DataFrame**: Retrieve Splits calendar from YF as a DataFrame.

 - **Parameters:**: - **start** (*str**|**datetime**|**date*)  overwrite start date (default set by __init__) eg. start=2025-11-08
- **end** (*str**|**datetime**|**date*)  overwrite end date (default set by __init__) eg. end=2025-11-08
- **limit**  maximum number of results to return (YF caps at 100)
- **offset**  offsets the results for pagination. YF default 0
- **force**  if True, will re-query even if cache already exists
- **Returns:**: DataFrame with Splits calendar

 - **get_earnings_calendar(*market_cap: float | None = None*, *filter_most_active: bool = True*, *start=None*, *end=None*, *limit=12*, *offset=0*, *force=False*)  DataFrame**: Retrieve earnings calendar from YF as a DataFrame. Will re-query every time it is called, overwriting previous data.

 - **Parameters:**: - **market_cap**  market cap cutoff in USD, default None
- **filter_most_active**  will filter for actively traded stocks (default True)
- **start** (*str**|**datetime**|**date*)  overwrite start date (default set by __init__) eg. start=2025-11-08
- **end** (*str**|**datetime**|**date*)  overwrite end date (default set by __init__) eg. end=2025-11-08
- **limit**  maximum number of results to return (YF caps at 100)
- **offset**  offsets the results for pagination. YF default 0
- **force**  if True, will re-query even if cache already exists
- **Returns:**: DataFrame with earnings calendar

 - **get_economic_events_calendar(*start=None*, *end=None*, *limit=12*, *offset=0*, *force=False*)  DataFrame**: Retrieve Economic Events calendar from YF as a DataFrame.

 - **Parameters:**: - **start** (*str**|**datetime**|**date*)  overwrite start date (default set by __init__) eg. start=2025-11-08
- **end** (*str**|**datetime**|**date*)  overwrite end date (default set by __init__) eg. end=2025-11-08
- **limit**  maximum number of results to return (YF caps at 100)
- **offset**  offsets the results for pagination. YF default 0
- **force**  if True, will re-query even if cache already exists
- **Returns:**: DataFrame with Economic Events calendar

 - **get_ipo_info_calendar(*start=None*, *end=None*, *limit=12*, *offset=0*, *force=False*)  DataFrame**: Retrieve IPOs calendar from YF as a Dataframe.

 - **Parameters:**: - **start** (*str**|**datetime**|**date*)  overwrite start date (default set by __init__) eg. start=2025-11-08
- **end** (*str**|**datetime**|**date*)  overwrite end date (default set by __init__) eg. end=2025-11-08
- **limit**  maximum number of results to return (YF caps at 100)
- **offset**  offsets the results for pagination. YF default 0
- **force**  if True, will re-query even if cache already exists
- **Returns:**: DataFrame with IPOs calendar

 - **get_splits_calendar(*start=None*, *end=None*, *limit=12*, *offset=0*, *force=False*)  DataFrame**: Retrieve Splits calendar from YF as a DataFrame.

 - **Parameters:**: - **start** (*str**|**datetime**|**date*)  overwrite start date (default set by __init__) eg. start=2025-11-08
- **end** (*str**|**datetime**|**date*)  overwrite end date (default set by __init__) eg. end=2025-11-08
- **limit**  maximum number of results to return (YF caps at 100)
- **offset**  offsets the results for pagination. YF default 0
- **force**  if True, will re-query even if cache already exists
- **Returns:**: DataFrame with Splits calendar

## PriceHistory class
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html

- ***class*yfinance.scrapers.history.PriceHistory(*data*, *ticker*, *tz*, *session=None*)**: - **get_actions(*period='max'*)  Series**

 - **get_capital_gains(*period='max'*)  Series**

 - **get_dividends(*period='max'*)  Series**

 - **get_history_metadata()  dict**

 - **get_splits(*period='max'*)  Series**

 - **history(*period=None*, *interval='1d'*, *start=None*, *end=None*, *prepost=False*, *actions=True*, *auto_adjust=True*, *back_adjust=False*, *repair=False*, *keepna=False*, *rounding=False*, *timeout=10*, *raise_errors=False*)  DataFrame**: - **Parameters:**: - **periodstr**: Valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max Default: 1mo Can combine with start/end e.g. end = start + period
- **intervalstr**: Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo Intraday data cannot extend last 60 days
- **startstr**: Download start date string (YYYY-MM-DD) or _datetime, inclusive. Default: 99 years ago E.g. for start=2020-01-01, first data point = 2020-01-01
- **endstr**: Download end date string (YYYY-MM-DD) or _datetime, exclusive. Default: now E.g. for end=2023-01-01, last data point = 2022-12-31
- **prepostbool**: Include Pre and Post market data in results? Default: False
- **auto_adjustbool**: Adjust all OHLC automatically? Default: True
- **back_adjustbool**: Back-adjusted data to mimic true historical prices
- **repairbool**: Fixes price errors in Yahoo data: 100x, missing, bad dividend adjust. Default: False Full details at: [Price Repair](https://ranaroussi.github.io/yfinance/advanced/price_repair.html).
- **keepnabool**: Keep NaN rows returned by Yahoo? Default: False
- **roundingbool**: Optional: Round values to 2 decimal places? Default: False = use precision suggested by Yahoo!
- **timeoutNone or float**: Optional: timeout fetches after N seconds Default: 10 seconds
- **raise_errorsbool**: If True, then raise errors as Exceptions instead of logging.

## yfinance.Ticker.get_info
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_info.html

- **Ticker.get_info()  dict**

## yfinance.screen
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.screen.html

- **yfinance.screen(*query: str | [EquityQuery](https://ranaroussi.github.io/yfinance/reference/api/yfinance.EquityQuery.html) | [FundQuery](https://ranaroussi.github.io/yfinance/reference/api/yfinance.FundQuery.html)*, *offset: int = None*, *size: int = None*, *count: int = None*, *sortField: str = None*, *sortAsc: bool = None*, *userId: str = None*, *userIdType: str = None*, *session=None*)**: Run a screen: predefined query, or custom query.

 - **Parameters:**: - Defaults only apply if query = EquityQuery or FundQuery

 - **querystr | Query:**: The query to execute, either name of predefined or custom query. For predefined list run yf.PREDEFINED_SCREENER_QUERIES.keys()
- **offsetint**: The offset for the results. Default 0.
- **sizeint**: number of results to return. Default 100, maximum 250 (Yahoo) Use count instead for predefined queries.
- **countint**: number of results to return. Default 25, maximum 250 (Yahoo) Use size instead for custom queries.
- **sortFieldstr**: field to sort by. Default ticker
- **sortAscbool**: Sort ascending? Default False
- **userIdstr**: The user ID. Default empty.
- **userIdTypestr**: Type of user ID (e.g., guid). Default guid.

 - **Example: predefined query**: ```
import yfinance as yf
response = yf.screen("aggressive_small_caps")
```
- **Example: custom query**: ```
import yfinance as yf
from yfinance import EquityQuery
q = EquityQuery('and', [
       EquityQuery('gt', ['percentchange', 3]),
       EquityQuery('eq', ['region', 'us'])
])
response = yf.screen(q, sortField = 'percentchange', sortAsc = True)
```
- **To access predefineds query code**: ```
import yfinance as yf
query = yf.PREDEFINED_SCREENER_QUERIES['aggressive_small_caps']
```

 | Key | Values |
| --- | --- |
| aggressive_small_caps | query:  EquityQuery(AND, [  EquityQuery(IS-IN, [exchange, NMS, NYQ]), EquityQuery(LT, [epsgrowth.lasttwelvemonths, 15])  ])  sortField: eodvolume sortType: desc |
| day_gainers | query:  EquityQuery(AND, [  EquityQuery(GT, [percentchange, 3]), EquityQuery(EQ, [region, us]), EquityQuery(GTE, [intradaymarketcap, 2000000000]), EquityQuery(GTE, [intradayprice, 5]), EquityQuery(GT, [dayvolume, 15000])  ])  sortField: percentchange sortType: DESC |
| day_losers | query:  EquityQuery(AND, [  EquityQuery(LT, [percentchange, -2.5]), EquityQuery(EQ, [region, us]), EquityQuery(GTE, [intradaymarketcap, 2000000000]), EquityQuery(GTE, [intradayprice, 5]), EquityQuery(GT, [dayvolume, 20000])  ])  sortField: percentchange sortType: ASC |
| growth_technology_stocks | query:  EquityQuery(AND, [  EquityQuery(GTE, [quarterlyrevenuegrowth.quarterly, 25]), EquityQuery(GTE, [epsgrowth.lasttwelvemonths, 25]), EquityQuery(EQ, [sector, Technology]), EquityQuery(IS-IN, [exchange, NMS, NYQ])  ])  sortField: eodvolume sortType: desc |
| most_actives | query:  EquityQuery(AND, [  EquityQuery(EQ, [region, us]), EquityQuery(GTE, [intradaymarketcap, 2000000000]), EquityQuery(GT, [dayvolume, 5000000])  ])  sortField: dayvolume sortType: DESC |
| most_shorted_stocks | count: 25 offset: 0 query:  EquityQuery(AND, [  EquityQuery(EQ, [region, us]), EquityQuery(GT, [intradayprice, 1]), EquityQuery(GT, [avgdailyvol3m, 200000])  ])  sortField: short_percentage_of_shares_outstanding.value sortType: DESC |
| small_cap_gainers | query:  EquityQuery(AND, [  EquityQuery(LT, [intradaymarketcap, 2000000000]), EquityQuery(IS-IN, [exchange, NMS, NYQ])  ])  sortField: eodvolume sortType: desc |
| undervalued_growth_stocks | query:  EquityQuery(AND, [  EquityQuery(BTWN, [peratio.lasttwelvemonths, 0, 20]), EquityQuery(LT, [pegratio_5y, 1]), EquityQuery(GTE, [epsgrowth.lasttwelvemonths, 25]), EquityQuery(IS-IN, [exchange, NMS, NYQ])  ])  sortField: eodvolume sortType: DESC |
| undervalued_large_caps | query:  EquityQuery(AND, [  EquityQuery(BTWN, [peratio.lasttwelvemonths, 0, 20]), EquityQuery(LT, [pegratio_5y, 1]), EquityQuery(BTWN, [intradaymarketcap, 10000000000, 100000000000]), EquityQuery(IS-IN, [exchange, NMS, NYQ])  ])  sortField: eodvolume sortType: desc |
| conservative_foreign_funds | query:  FundQuery(AND, [  FundQuery(IS-IN, [categoryname, Foreign Large Value, Foreign Large Blend, Foreign Large Growth, Foreign Small/Mid Growth, Foreign Small/Mid Blend, Foreign Small/Mid Value]), FundQuery(IS-IN, [performanceratingoverall, 4, 5]), FundQuery(LT, [initialinvestment, 100001]), FundQuery(LT, [annualreturnnavy1categoryrank, 50]), FundQuery(IS-IN, [riskratingoverall, 1, 2, 3]), FundQuery(EQ, [exchange, NAS])  ])  sortField: fundnetassets sortType: DESC |
| high_yield_bond | query:  FundQuery(AND, [  FundQuery(IS-IN, [performanceratingoverall, 4, 5]), FundQuery(LT, [initialinvestment, 100001]), FundQuery(LT, [annualreturnnavy1categoryrank, 50]), FundQuery(IS-IN, [riskratingoverall, 1, 2, 3]), FundQuery(EQ, [categoryname, High Yield Bond]), FundQuery(EQ, [exchange, NAS])  ])  sortField: fundnetassets sortType: DESC |
| portfolio_anchors | query:  FundQuery(AND, [  FundQuery(EQ, [categoryname, Large Blend]), FundQuery(IS-IN, [performanceratingoverall, 4, 5]), FundQuery(LT, [initialinvestment, 100001]), FundQuery(LT, [annualreturnnavy1categoryrank, 50]), FundQuery(EQ, [exchange, NAS])  ])  sortField: fundnetassets sortType: DESC |
| solid_large_growth_funds | query:  FundQuery(AND, [  FundQuery(EQ, [categoryname, Large Growth]), FundQuery(IS-IN, [performanceratingoverall, 4, 5]), FundQuery(LT, [initialinvestment, 100001]), FundQuery(LT, [annualreturnnavy1categoryrank, 50]), FundQuery(EQ, [exchange, NAS])  ])  sortField: fundnetassets sortType: DESC |
| solid_midcap_growth_funds | query:  FundQuery(AND, [  FundQuery(EQ, [categoryname, Mid-Cap Growth]), FundQuery(IS-IN, [performanceratingoverall, 4, 5]), FundQuery(LT, [initialinvestment, 100001]), FundQuery(LT, [annualreturnnavy1categoryrank, 50]), FundQuery(EQ, [exchange, NAS])  ])  sortField: fundnetassets sortType: DESC |
| top_mutual_funds | query:  FundQuery(AND, [  FundQuery(GT, [intradayprice, 15]), FundQuery(IS-IN, [performanceratingoverall, 4, 5]), FundQuery(GT, [initialinvestment, 1000]), FundQuery(EQ, [exchange, NAS])  ])  sortField: percentchange sortType: DESC |

## yfinance.Ticker.earnings_estimate
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.earnings_estimate.html

- ***property*Ticker.earnings_estimate*: DataFrame***

## yfinance.Ticker.info
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.info.html

- ***property*Ticker.info*: dict***

## yfinance.Ticker.get_eps_revisions
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_eps_revisions.html

- **Ticker.get_eps_revisions(*as_dict=False*)**: Index: 0q +1q 0y +1y Columns: upLast7days upLast30days downLast7days downLast30days

## yfinance.Ticker.institutional_holders
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.institutional_holders.html

- ***property*Ticker.institutional_holders*: DataFrame***

## yfinance.Ticker.get_upgrades_downgrades
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_upgrades_downgrades.html

- **Ticker.get_upgrades_downgrades(*as_dict=False*)**: Returns a DataFrame with the recommendations changes (upgrades/downgrades) Index: date of grade Columns: firm toGrade fromGrade action

## Lookup
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Lookup.html

- ***class*yfinance.Lookup(*query: str*, *session=None*, *timeout=30*, *raise_errors=True*)**: Fetches quote (ticker) lookups from Yahoo Finance.

 - **Parameters:**: - **query** (*str*)  The search query for financial data lookup.
- **session**  Custom HTTP session for requests (default None).
- **timeout**  Request timeout in seconds (default 30).
- **raise_errors**  Raise exceptions on error (default True).

 Attributes

 - **all**: Returns all available financial instruments.

 - **cryptocurrency**: Returns Cryptocurrencies related financial instruments.

 - **currency**: Returns Currencies related financial instruments.

 - **etf**: Returns ETFs related financial instruments.

 - **future**: Returns Futures related financial instruments.

 - **index**: Returns Indices related financial instruments.

 - **mutualfund**: Returns mutual funds related financial instruments.

 - **stock**: Returns stock related financial instruments.

 Methods

 - **__init__(*query: str*, *session=None*, *timeout=30*, *raise_errors=True*)**

 - **get_all(*count=25*)  DataFrame**: Returns all available financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_cryptocurrency(*count=25*)  DataFrame**: Returns Cryptocurrencies related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_currency(*count=25*)  DataFrame**: Returns Currencies related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_etf(*count=25*)  DataFrame**: Returns ETFs related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_future(*count=25*)  DataFrame**: Returns Futures related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_index(*count=25*)  DataFrame**: Returns Indices related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_mutualfund(*count=25*)  DataFrame**: Returns mutual funds related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_stock(*count=25*)  DataFrame**: Returns stock related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_all(*count=25*)  DataFrame**: Returns all available financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_cryptocurrency(*count=25*)  DataFrame**: Returns Cryptocurrencies related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_currency(*count=25*)  DataFrame**: Returns Currencies related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_etf(*count=25*)  DataFrame**: Returns ETFs related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_future(*count=25*)  DataFrame**: Returns Futures related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_index(*count=25*)  DataFrame**: Returns Indices related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_mutualfund(*count=25*)  DataFrame**: Returns mutual funds related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

 - **get_stock(*count=25*)  DataFrame**: Returns stock related financial instruments.

 - **Parameters:**: **count** (*int*)  The number of results to retrieve.

## yfinance.Ticker.get_earnings_history
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_earnings_history.html

- **Ticker.get_earnings_history(*as_dict=False*)**: Index: pd.DatetimeIndex Columns: epsEstimate epsActual epsDifference surprisePercent

## yfinance.set_tz_cache_location
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.set_tz_cache_location.html

- **yfinance.set_tz_cache_location(*cache_dir: str*)**

## yfinance.Ticker.get_history_metadata
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_history_metadata.html

- **Ticker.get_history_metadata()  dict**

## yfinance.Ticker.get_analyst_price_targets
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_analyst_price_targets.html

- **Ticker.get_analyst_price_targets()  dict**: Keys: current low high mean median

## yfinance.Ticker.dividends
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.dividends.html

- ***property*Ticker.dividends*: Series***

## WebSocket
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.WebSocket.html

- ***class*yfinance.WebSocket(*url: str = 'wss://streamer.finance.yahoo.com/?version=2'*, *verbose=True*)**: Synchronous WebSocket client for streaming real time pricing data.

 Initialize the WebSocket client.

 - **Parameters:**: - **url** (*str*)  The WebSocket server URL. Defaults to Yahoo Finances WebSocket URL.
- **verbose** (*bool*)  Flag to enable or disable print statements. Defaults to True.

 Methods

 - **__init__(*url: str = 'wss://streamer.finance.yahoo.com/?version=2'*, *verbose=True*)**: Initialize the WebSocket client.

 - **Parameters:**: - **url** (*str*)  The WebSocket server URL. Defaults to Yahoo Finances WebSocket URL.
- **verbose** (*bool*)  Flag to enable or disable print statements. Defaults to True.

 - **close()**: Close the WebSocket connection.

 - **listen(*message_handler: Callable[[dict], None] | None = None*)**: Start listening to messages from the WebSocket server.

 - **Parameters:**: **message_handler** (*Optional**[**Callable**[**[**dict**]**,**None**]**]*)  Optional function to handle received messages.

 - **subscribe(*symbols: str | List[str]*)**: Subscribe to a stock symbol or a list of stock symbols.

 - **Parameters:**: **symbols** (*Union**[**str**,**List**[**str**]**]*)  Stock symbol(s) to subscribe to.

 - **unsubscribe(*symbols: str | List[str]*)**: Unsubscribe from a stock symbol or a list of stock symbols.

 - **Parameters:**: **symbols** (*Union**[**str**,**List**[**str**]**]*)  Stock symbol(s) to unsubscribe from.

 - **close()**: Close the WebSocket connection.

 - **listen(*message_handler: Callable[[dict], None] | None = None*)**: Start listening to messages from the WebSocket server.

 - **Parameters:**: **message_handler** (*Optional**[**Callable**[**[**dict**]**,**None**]**]*)  Optional function to handle received messages.

 - **subscribe(*symbols: str | List[str]*)**: Subscribe to a stock symbol or a list of stock symbols.

 - **Parameters:**: **symbols** (*Union**[**str**,**List**[**str**]**]*)  Stock symbol(s) to subscribe to.

 - **unsubscribe(*symbols: str | List[str]*)**: Unsubscribe from a stock symbol or a list of stock symbols.

 - **Parameters:**: **symbols** (*Union**[**str**,**List**[**str**]**]*)  Stock symbol(s) to unsubscribe from.

## Industry
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Industry.html

- ***class*yfinance.Industry(*key*, *session=None*)**: Represents an industry within a sector.

 - **Parameters:**: - **key** (*str*)  The key identifier for the industry.
- **session** (*optional*)  The session to use for requests.

 Attributes

 - **key**: Retrieves the key of the domain entity.

 - **Returns:**: The unique key of the domain entity.
- **Return type:**: str

 - **name**: Retrieves the name of the domain entity.

 - **Returns:**: The name of the domain entity.
- **Return type:**: str

 - **overview**: Retrieves the overview information of the domain entity.

 - **Returns:**: A dictionary containing an overview of the domain entity.
- **Return type:**: Dict

 - **research_reports**: Retrieves research reports related to the domain entity.

 - **Returns:**: A list of research reports, where each report is a dictionary with metadata.
- **Return type:**: List[Dict[str, str]]

 - **sector_key**: Returns the sector key of the industry.

 - **Returns:**: The sector key.
- **Return type:**: str

 - **sector_name**: Returns the sector name of the industry.

 - **Returns:**: The sector name.
- **Return type:**: str

 - **symbol**: Retrieves the symbol of the domain entity.

 - **Returns:**: The symbol representing the domain entity.
- **Return type:**: str

 - **ticker**: Retrieves a Ticker object based on the domain entitys symbol.

 - **Returns:**: A Ticker object associated with the domain entity.
- **Return type:**: [Ticker](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html)

 - **top_companies**: Retrieves the top companies within the domain entity.

 - **Returns:**: A DataFrame containing the top companies in the domain.
- **Return type:**: pandas.DataFrame

 - **top_growth_companies**: Returns the top growth companies in the industry.

 - **Returns:**: DataFrame containing top growth companies.
- **Return type:**: Optional[pd.DataFrame]

 - **top_performing_companies**: Returns the top performing companies in the industry.

 - **Returns:**: DataFrame containing top performing companies.
- **Return type:**: Optional[pd.DataFrame]

 Methods

 - **__init__(*key*, *session=None*)**: - **Parameters:**: - **key** (*str*)  The key identifier for the industry.
- **session** (*optional*)  The session to use for requests.

## WebSocket
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.websocket.html

The WebSocket module allows you to stream live price data from Yahoo Finance using both synchronous and asynchronous clients.

  ### Classes

 | [`WebSocket`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.WebSocket.html)([url, verbose]) | Synchronous WebSocket client for streaming real time pricing data. |
| --- | --- |
| [`AsyncWebSocket`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.AsyncWebSocket.html)([url, verbose]) | Asynchronous WebSocket client for streaming real time pricing data. |

    ### Synchronous WebSocket

 The WebSocket class provides a synchronous interface for subscribing to price updates.

 Sample Code:

 ```
import yfinance as yf

# define your message callback
def message_handler(message):
    print("Received message:", message)

# =======================
# With Context Manager
# =======================
with yf.WebSocket() as ws:
    ws.subscribe(["AAPL", "BTC-USD"])
    ws.listen(message_handler)

# =======================
# Without Context Manager
# =======================
ws = yf.WebSocket()
ws.subscribe(["AAPL", "BTC-USD"])
ws.listen(message_handler)
```

    ### Asynchronous WebSocket

 The AsyncWebSocket class provides an asynchronous interface for subscribing to price updates.

 Sample Code:

 ```
import asyncio
import yfinance as yf

# define your message callback
def message_handler(message):
    print("Received message:", message)

async def main():
    # =======================
    # With Context Manager
    # =======================
    async with yf.AsyncWebSocket() as ws:
        await ws.subscribe(["AAPL", "BTC-USD"])
        await ws.listen()

    # =======================
    # Without Context Manager
    # =======================
    ws = yf.AsyncWebSocket()
    await ws.subscribe(["AAPL", "BTC-USD"])
    await ws.listen()

asyncio.run(main())
```

  > **Note**
> 
> If youre running asynchronous code in a Jupyter notebook, you may encounter issues with event loops. To resolve this, you need to import and apply nest_asyncio to allow nested event loops.
> 
>  Add the following code before running asynchronous operations:
> 
>  ```
> import nest_asyncio
> nest_asyncio.apply()
> ```

## yfinance.Ticker.major_holders
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.major_holders.html

- ***property*Ticker.major_holders*: DataFrame***

## Search
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Search.html

- ***class*yfinance.Search(*query*, *max_results=8*, *news_count=8*, *lists_count=8*, *include_cb=True*, *include_nav_links=False*, *include_research=False*, *include_cultural_assets=False*, *enable_fuzzy_query=False*, *recommended=8*, *session=None*, *timeout=30*, *raise_errors=True*)**: Fetches and organizes search results from Yahoo Finance, including stock quotes and news articles.

 - **Parameters:**: - **query**  The search query (ticker symbol or company name).
- **max_results**  Maximum number of stock quotes to return (default 8).
- **news_count**  Number of news articles to include (default 8).
- **lists_count**  Number of lists to include (default 8).
- **include_cb**  Include the company breakdown (default True).
- **include_nav_links**  Include the navigation links (default False).
- **include_research**  Include the research reports (default False).
- **include_cultural_assets**  Include the cultural assets (default False).
- **enable_fuzzy_query**  Enable fuzzy search for typos (default False).
- **recommended**  Recommended number of results to return (default 8).
- **session**  Custom HTTP session for requests (default None).
- **timeout**  Request timeout in seconds (default 30).
- **raise_errors**  Raise exceptions on error (default True).

 Attributes

 - **all**: filtered down version of response.

 - **Type:**: Get all the results from the search results

 - **lists**: Get the lists from the search results.

 - **nav**: Get the navigation links from the search results.

 - **news**: Get the news from the search results.

 - **quotes**: Get the quotes from the search results.

 - **research**: Get the research reports from the search results.

 - **response**: Get the raw response from the search results.

 Methods

 - **__init__(*query*, *max_results=8*, *news_count=8*, *lists_count=8*, *include_cb=True*, *include_nav_links=False*, *include_research=False*, *include_cultural_assets=False*, *enable_fuzzy_query=False*, *recommended=8*, *session=None*, *timeout=30*, *raise_errors=True*)**: Fetches and organizes search results from Yahoo Finance, including stock quotes and news articles.

 - **Parameters:**: - **query**  The search query (ticker symbol or company name).
- **max_results**  Maximum number of stock quotes to return (default 8).
- **news_count**  Number of news articles to include (default 8).
- **lists_count**  Number of lists to include (default 8).
- **include_cb**  Include the company breakdown (default True).
- **include_nav_links**  Include the navigation links (default False).
- **include_research**  Include the research reports (default False).
- **include_cultural_assets**  Include the cultural assets (default False).
- **enable_fuzzy_query**  Enable fuzzy search for typos (default False).
- **recommended**  Recommended number of results to return (default 8).
- **session**  Custom HTTP session for requests (default None).
- **timeout**  Request timeout in seconds (default 30).
- **raise_errors**  Raise exceptions on error (default True).

 - **search()  [Search](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Search.html)**: Search using the query parameters defined in the constructor.

 - **search()  [Search](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Search.html)**: Search using the query parameters defined in the constructor.

## yfinance.Ticker.get_insider_transactions
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_insider_transactions.html

- **Ticker.get_insider_transactions(*as_dict=False*)**

## FundsData class
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.funds_data.html

| [`FundsData`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.scrapers.funds.FundsData.html)(data, symbol) | ETF and Mutual Funds Data Queried Modules: quoteType, summaryProfile, fundProfile, topHoldings |
| --- | --- |

## Sector
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Sector.html

- ***class*yfinance.Sector(*key*, *session=None*)**: Represents a financial market sector and allows retrieval of sector-related data such as top ETFs, top mutual funds, and industry data.

 - **Parameters:**: - **key** (*str*)  The key representing the sector.
- **session** (*requests.Session**,**optional*)  A session for making requests. Defaults to None.

 > **See also**
> 
> - **`Sector.industries`**: Map of sector and industry

 Attributes

 - **industries**: Gets the industries within the sector.

 - **Returns:**: A DataFrame with industries key, name, symbol, and market weight.
- **Return type:**: pandas.DataFrame

 | Key | Values |
| --- | --- |
| basic-materials | - agricultural-inputs
- aluminum
- building-materials
- chemicals
- coking-coal
- copper
- gold
- lumber-wood-production
- other-industrial-metals-mining
- other-precious-metals-mining
- paper-paper-products
- silver
- specialty-chemicals
- steel |
| communication-services | - advertising-agencies
- broadcasting
- electronic-gaming-multimedia
- entertainment
- internet-content-information
- publishing
- telecom-services |
| consumer-cyclical | - apparel-manufacturing
- apparel-retail
- auto-manufacturers
- auto-parts
- auto-truck-dealerships
- department-stores
- footwear-accessories
- furnishings-fixtures-appliances
- gambling
- home-improvement-retail
- internet-retail
- leisure
- lodging
- luxury-goods
- packaging-containers
- personal-services
- recreational-vehicles
- residential-construction
- resorts-casinos
- restaurants
- specialty-retail
- textile-manufacturing
- travel-services |
| consumer-defensive | - beveragesbrewers
- beveragesnon-alcoholic
- beverageswineries-distilleries
- confectioners
- discount-stores
- education-training-services
- farm-products
- food-distribution
- grocery-stores
- household-personal-products
- packaged-foods
- tobacco |
| energy | - oil-gas-drilling
- oil-gas-e&p
- oil-gas-equipment-services
- oil-gas-integrated
- oil-gas-midstream
- oil-gas-refining-marketing
- thermal-coal
- uranium |
| financial-services | - asset-management
- banksdiversified
- banksregional
- capital-markets
- credit-services
- financial-conglomerates
- financial-data-stock-exchanges
- insurance-brokers
- insurancediversified
- insurancelife
- insuranceproperty-casualty
- insurancereinsurance
- insurancespecialty
- mortgage-finance
- shell-companies |
| healthcare | - biotechnology
- diagnostics-research
- drug-manufacturersgeneral
- drug-manufacturersspecialty-generic
- health-information-services
- healthcare-plans
- medical-care-facilities
- medical-devices
- medical-distribution
- medical-instruments-supplies
- pharmaceutical-retailers |
| industrials | - aerospace-defense
- airlines
- airports-air-services
- building-products-equipment
- business-equipment-supplies
- conglomerates
- consulting-services
- electrical-equipment-parts
- engineering-construction
- farm-heavy-construction-machinery
- industrial-distribution
- infrastructure-operations
- integrated-freight-logistics
- marine-shipping
- metal-fabrication
- pollution-treatment-controls
- railroads
- rental-leasing-services
- security-protection-services
- specialty-business-services
- specialty-industrial-machinery
- staffing-employment-services
- tools-accessories
- trucking
- waste-management |
| real-estate | - real-estate-services
- real-estatedevelopment
- real-estatediversified
- reitdiversified
- reithealthcare-facilities
- reithotel-motel
- reitindustrial
- reitmortgage
- reitoffice
- reitresidential
- reitretail
- reitspecialty |
| technology | - communication-equipment
- computer-hardware
- consumer-electronics
- electronic-components
- electronics-computer-distribution
- information-technology-services
- scientific-technical-instruments
- semiconductor-equipment-materials
- semiconductors
- softwareapplication
- softwareinfrastructure
- solar |
| utilities | - utilitiesdiversified
- utilitiesindependent-power-producers
- utilitiesregulated-electric
- utilitiesregulated-gas
- utilitiesregulated-water
- utilitiesrenewable |

 - **key**: Retrieves the key of the domain entity.

 - **Returns:**: The unique key of the domain entity.
- **Return type:**: str

 - **name**: Retrieves the name of the domain entity.

 - **Returns:**: The name of the domain entity.
- **Return type:**: str

 - **overview**: Retrieves the overview information of the domain entity.

 - **Returns:**: A dictionary containing an overview of the domain entity.
- **Return type:**: Dict

 - **research_reports**: Retrieves research reports related to the domain entity.

 - **Returns:**: A list of research reports, where each report is a dictionary with metadata.
- **Return type:**: List[Dict[str, str]]

 - **symbol**: Retrieves the symbol of the domain entity.

 - **Returns:**: The symbol representing the domain entity.
- **Return type:**: str

 - **ticker**: Retrieves a Ticker object based on the domain entitys symbol.

 - **Returns:**: A Ticker object associated with the domain entity.
- **Return type:**: [Ticker](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html)

 - **top_companies**: Retrieves the top companies within the domain entity.

 - **Returns:**: A DataFrame containing the top companies in the domain.
- **Return type:**: pandas.DataFrame

 - **top_etfs**: Gets the top ETFs for the sector.

 - **Returns:**: A dictionary of ETF symbols and names.
- **Return type:**: Dict[str, str]

 - **top_mutual_funds**: Gets the top mutual funds for the sector.

 - **Returns:**: A dictionary of mutual fund symbols and names.
- **Return type:**: Dict[str, str]

 Methods

 - **__init__(*key*, *session=None*)**: - **Parameters:**: - **key** (*str*)  The key representing the sector.
- **session** (*requests.Session**,**optional*)  A session for making requests. Defaults to None.

 > **See also**
> 
> - **`Sector.industries`**: Map of sector and industry

## yfinance.Ticker.get_income_stmt
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_income_stmt.html

- **Ticker.get_income_stmt(*as_dict=False*, *pretty=False*, *freq='yearly'*)**: - **Parameters:**: - **as_dict: bool**: Return table as Python dict Default is False
- **pretty: bool**: Format row names nicely for readability Default is False
- **freq: str**: yearly or quarterly or trailing Default is yearly

## Financials
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.financials.html

| [`get_income_stmt`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_income_stmt.html)([as_dict, pretty, freq]) |  |
| --- | --- |
| [`income_stmt`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.income_stmt.html) |  |
| [`quarterly_income_stmt`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.quarterly_income_stmt.html) |  |
| [`ttm_income_stmt`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.ttm_income_stmt.html) |  |
| [`get_balance_sheet`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_balance_sheet.html)([as_dict, pretty, freq]) |  |
| [`balance_sheet`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.balance_sheet.html) |  |
| [`get_cashflow`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_cashflow.html)([as_dict, pretty, freq]) |  |
| [`cashflow`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.cashflow.html) |  |
| [`quarterly_cashflow`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.quarterly_cashflow.html) |  |
| [`ttm_cashflow`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.ttm_cashflow.html) |  |
| [`get_earnings`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_earnings.html)([as_dict, freq]) |  |
| [`earnings`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.earnings.html) |  |
| [`calendar`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.calendar.html) | Returns a dictionary of events, earnings, and dividends for the ticker |
| [`get_earnings_dates`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_earnings_dates.html)([limit, offset]) |  |
| [`earnings_dates`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.earnings_dates.html) |  |
| [`get_sec_filings`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_sec_filings.html)() |  |
| [`sec_filings`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.sec_filings.html) |  |

## Market
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Market.html

- ***class*yfinance.Market(*market: str*, *session=None*, *timeout=30*)**: Attributes

 - **status**

 - **summary**

 Methods

 - **__init__(*market: str*, *session=None*, *timeout=30*)**

## yfinance.Ticker.analyst_price_targets
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.analyst_price_targets.html

- ***property*Ticker.analyst_price_targets*: dict***

## yfinance.Ticker.get_mutualfund_holders
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_mutualfund_holders.html

- **Ticker.get_mutualfund_holders(*as_dict=False*)**

## yfinance.Ticker.growth_estimates
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.growth_estimates.html

- ***property*Ticker.growth_estimates*: DataFrame***

## Ticker and Tickers
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.ticker_tickers.html

### Class

 The Ticker module, allows you to access ticker data in a Pythonic way.

 | [`Ticker`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html)(ticker[, session]) | Initialize a Yahoo Finance Ticker object. |
| --- | --- |
| [`Tickers`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Tickers.html)(tickers[, session]) |  |

    ### Ticker Sample Code

 The Ticker module, allows you to access ticker data in a Pythonic way.

 ```
import yfinance as yf

dat = yf.Ticker("MSFT")

# get historical market data
dat.history(period='1mo')

# options
dat.option_chain(dat.options[0]).calls

# get financials
dat.balance_sheet
dat.quarterly_income_stmt

# dates
dat.calendar

# general info
dat.info

# analysis
dat.analyst_price_targets

# websocket
dat.live()
```

  To initialize multiple Ticker objects, use

 ```
import yfinance as yf

tickers = yf.Tickers('msft aapl goog')

# access each ticker using (example)
tickers.tickers['MSFT'].info
tickers.tickers['AAPL'].history(period="1mo")
tickers.tickers['GOOG'].actions

# websocket
tickers.live()
```

  For tickers that are ETFs/Mutual Funds, Ticker.funds_data provides access to fund related data.

 Funds Top Holdings and other data with category average is returned as pd.DataFrame.

 ```
import yfinance as yf
spy = yf.Ticker('SPY')
data = spy.funds_data

# show fund description
data.description

# show operational information
data.fund_overview
data.fund_operations

# show holdings related information
data.asset_classes
data.top_holdings
data.equity_holdings
data.bond_holdings
data.bond_ratings
data.sector_weightings
```

  If you want to use a proxy server for downloading data, use:

 ```
import yfinance as yf

msft = yf.Ticker("MSFT")

msft.history(..., proxy="PROXY_SERVER")
msft.get_actions(proxy="PROXY_SERVER")
msft.get_dividends(proxy="PROXY_SERVER")
msft.get_splits(proxy="PROXY_SERVER")
msft.get_capital_gains(proxy="PROXY_SERVER")
msft.get_balance_sheet(proxy="PROXY_SERVER")
msft.get_cashflow(proxy="PROXY_SERVER")
msft.option_chain(..., proxy="PROXY_SERVER")
...
```

  To initialize multiple Ticker objects, use Tickers module

 ```
import yfinance as yf

tickers = yf.Tickers('msft aapl goog')

# access each ticker using (example)
tickers.tickers['MSFT'].info
tickers.tickers['AAPL'].history(period="1mo")
tickers.tickers['GOOG'].actions

# websocket
tickers.live()
```

## yfinance.Ticker.income_stmt
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.income_stmt.html

- ***property*Ticker.income_stmt*: DataFrame***

## yfinance.Ticker.get_actions
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_actions.html

- **Ticker.get_actions(*period='max'*)  Series**

## yfinance.Ticker.earnings_dates
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.earnings_dates.html

- ***property*Ticker.earnings_dates*: DataFrame***

## Analysis & Holdings
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.analysis.html

### Analysis

 | [`get_recommendations`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_recommendations.html)([as_dict]) | Returns a DataFrame with the recommendations Columns: period strongBuy buy hold sell strongSell |
| --- | --- |
| [`recommendations`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.recommendations.html) |  |
| [`get_recommendations_summary`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_recommendations_summary.html)([as_dict]) |  |
| [`recommendations_summary`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.recommendations_summary.html) |  |
| [`get_upgrades_downgrades`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_upgrades_downgrades.html)([as_dict]) | Returns a DataFrame with the recommendations changes (upgrades/downgrades) Index: date of grade Columns: firm toGrade fromGrade action |
| [`upgrades_downgrades`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.upgrades_downgrades.html) |  |
| [`get_sustainability`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_sustainability.html)([as_dict]) |  |
| [`sustainability`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.sustainability.html) |  |
| [`get_analyst_price_targets`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_analyst_price_targets.html)() | Keys: current low high mean median |
| [`analyst_price_targets`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.analyst_price_targets.html) |  |
| [`get_earnings_estimate`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_earnings_estimate.html)([as_dict]) | Index: 0q +1q 0y +1y Columns: numberOfAnalysts avg low high yearAgoEps growth |
| [`earnings_estimate`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.earnings_estimate.html) |  |
| [`get_revenue_estimate`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_revenue_estimate.html)([as_dict]) | Index: 0q +1q 0y +1y Columns: numberOfAnalysts avg low high yearAgoRevenue growth |
| [`revenue_estimate`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.revenue_estimate.html) |  |
| [`get_earnings_history`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_earnings_history.html)([as_dict]) | Index: pd.DatetimeIndex Columns: epsEstimate epsActual epsDifference surprisePercent |
| [`earnings_history`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.earnings_history.html) |  |
| [`get_eps_trend`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_eps_trend.html)([as_dict]) | Index: 0q +1q 0y +1y Columns: current 7daysAgo 30daysAgo 60daysAgo 90daysAgo |
| [`eps_trend`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.eps_trend.html) |  |
| [`get_eps_revisions`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_eps_revisions.html)([as_dict]) | Index: 0q +1q 0y +1y Columns: upLast7days upLast30days downLast7days downLast30days |
| [`eps_revisions`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.eps_revisions.html) |  |
| [`get_growth_estimates`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_growth_estimates.html)([as_dict]) | Index: 0q +1q 0y +1y +5y -5y Columns: stock industry sector index |
| [`growth_estimates`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.growth_estimates.html) |  |

    ### Holdings

 | [`get_funds_data`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_funds_data.html)() |  |
| --- | --- |
| [`funds_data`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.funds_data.html) |  |

  > **See also**
> 
> [`yfinance.scrapers.funds.FundsData()`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.scrapers.funds.FundsData.html)

 | [`get_insider_purchases`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_insider_purchases.html)([as_dict]) |  |
| --- | --- |
| [`insider_purchases`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.insider_purchases.html) |  |
| [`get_insider_transactions`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_insider_transactions.html)([as_dict]) |  |
| [`insider_transactions`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.insider_transactions.html) |  |
| [`get_insider_roster_holders`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_insider_roster_holders.html)([as_dict]) |  |
| [`insider_roster_holders`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.insider_roster_holders.html) |  |
| [`get_major_holders`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_major_holders.html)([as_dict]) |  |
| [`major_holders`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.major_holders.html) |  |
| [`get_institutional_holders`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_institutional_holders.html)([as_dict]) |  |
| [`institutional_holders`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.institutional_holders.html) |  |
| [`get_mutualfund_holders`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_mutualfund_holders.html)([as_dict]) |  |
| [`mutualfund_holders`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.mutualfund_holders.html) |  |

## yfinance.Ticker.get_eps_trend
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_eps_trend.html

- **Ticker.get_eps_trend(*as_dict=False*)**: Index: 0q +1q 0y +1y Columns: current 7daysAgo 30daysAgo 60daysAgo 90daysAgo

## yfinance.Ticker.get_isin
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_isin.html

- **Ticker.get_isin()  str | None**

## yfinance.Ticker.news
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.news.html

- ***property*Ticker.news*: list***

## yfinance.Ticker.get_dividends
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_dividends.html

- **Ticker.get_dividends(*period='max'*)  Series**

## yfinance.Ticker.get_capital_gains
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_capital_gains.html

- **Ticker.get_capital_gains(*period='max'*)  Series**

## yfinance.Ticker.get_cashflow
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_cashflow.html

- **Ticker.get_cashflow(*as_dict=False*, *pretty=False*, *freq='yearly'*)**

## yfinance.Ticker.ttm_income_stmt
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.ttm_income_stmt.html

- ***property*Ticker.ttm_income_stmt*: DataFrame***

## yfinance.Ticker.get_major_holders
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_major_holders.html

- **Ticker.get_major_holders(*as_dict=False*)**

## yfinance.Ticker.recommendations
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.recommendations.html

- ***property*Ticker.recommendations**

## yfinance.Ticker.eps_revisions
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.eps_revisions.html

- ***property*Ticker.eps_revisions*: DataFrame***

## AsyncWebSocket
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.AsyncWebSocket.html

- ***class*yfinance.AsyncWebSocket(*url: str = 'wss://streamer.finance.yahoo.com/?version=2'*, *verbose=True*)**: Asynchronous WebSocket client for streaming real time pricing data.

 Initialize the AsyncWebSocket client.

 - **Parameters:**: - **url** (*str*)  The WebSocket server URL. Defaults to Yahoo Finances WebSocket URL.
- **verbose** (*bool*)  Flag to enable or disable print statements. Defaults to True.

 Methods

 - **__init__(*url: str = 'wss://streamer.finance.yahoo.com/?version=2'*, *verbose=True*)**: Initialize the AsyncWebSocket client.

 - **Parameters:**: - **url** (*str*)  The WebSocket server URL. Defaults to Yahoo Finances WebSocket URL.
- **verbose** (*bool*)  Flag to enable or disable print statements. Defaults to True.

 - ***async*close()**: Close the WebSocket connection.

 - ***async*listen(*message_handler=None*)**: Start listening to messages from the WebSocket server.

 - **Parameters:**: **message_handler** (*Optional**[**Callable**[**[**dict**]**,**None**]**]*)  Optional function to handle received messages.

 - ***async*subscribe(*symbols: str | List[str]*)**: Subscribe to a stock symbol or a list of stock symbols.

 - **Parameters:**: **symbols** (*Union**[**str**,**List**[**str**]**]*)  Stock symbol(s) to subscribe to.

 - ***async*unsubscribe(*symbols: str | List[str]*)**: Unsubscribe from a stock symbol or a list of stock symbols.

 - **Parameters:**: **symbols** (*Union**[**str**,**List**[**str**]**]*)  Stock symbol(s) to unsubscribe from.

 - ***async*close()**: Close the WebSocket connection.

 - ***async*listen(*message_handler=None*)**: Start listening to messages from the WebSocket server.

 - **Parameters:**: **message_handler** (*Optional**[**Callable**[**[**dict**]**,**None**]**]*)  Optional function to handle received messages.

 - ***async*subscribe(*symbols: str | List[str]*)**: Subscribe to a stock symbol or a list of stock symbols.

 - **Parameters:**: **symbols** (*Union**[**str**,**List**[**str**]**]*)  Stock symbol(s) to subscribe to.

 - ***async*unsubscribe(*symbols: str | List[str]*)**: Unsubscribe from a stock symbol or a list of stock symbols.

 - **Parameters:**: **symbols** (*Union**[**str**,**List**[**str**]**]*)  Stock symbol(s) to unsubscribe from.

## yfinance.Ticker.revenue_estimate
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.revenue_estimate.html

- ***property*Ticker.revenue_estimate*: DataFrame***

## yfinance.Ticker.insider_transactions
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.insider_transactions.html

- ***property*Ticker.insider_transactions*: DataFrame***

## yfinance.Ticker.earnings
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.earnings.html

- ***property*Ticker.earnings*: DataFrame***

## yfinance.Ticker.get_shares_full
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_shares_full.html

- **Ticker.get_shares_full(*start=None*, *end=None*)**

## yfinance.Ticker.get_sec_filings
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_sec_filings.html

- **Ticker.get_sec_filings()  dict**

## yfinance.Ticker.get_earnings_estimate
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_earnings_estimate.html

- **Ticker.get_earnings_estimate(*as_dict=False*)**: Index: 0q +1q 0y +1y Columns: numberOfAnalysts avg low high yearAgoEps growth

## Calendars
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.calendars.html

### Class

 The Calendars class allows you to get information about upcoming events, for example, earning events.

 | [`Calendars`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Calendars.html)([start, end, session]) | Get economic calendars, for example, Earnings, IPO, Economic Events, Splits |
| --- | --- |

    ### Sample Code

 ```
import yfinance as yf
from datetime import datetime, timedelta

# Default init (today + 7 days)
calendar = yf.Calendars()

# Today's events: calendar of 1 day
tomorrow = datetime.now() + timedelta(days=1)
calendar = yf.Calendars(end=tomorrow)

# Default calendar queries - accessing the properties will fetch the data from YF
calendar.earnings_calendar
calendar.ipo_info_calendar
calendar.splits_calendar
calendar.economic_events_calendar

# Manual queries
calendar.get_earnings_calendar()
calendar.get_ipo_info_calendar()
calendar.get_splits_calendar()
calendar.get_economic_events_calendar()

# Earnings calendar custom filters
calendar.get_earnings_calendar(
    market_cap=100_000_000,  # filter out small-cap 
    filter_most_active=True,  # show only actively traded. Uses: `screen(query="MOST_ACTIVES")`
)

# Example of real use case:
# Get inminent unreported earnings events
today = datetime.now()
is_friday = today.weekday() == 4
day_after_tomorrow = today + timedelta(days=4 if is_friday else 2)

calendar = yf.Calendars(today, day_after_tomorrow)
df = calendar.get_earnings_calendar(limit=100)

unreported_df = df[df["Reported EPS"].isnull()]
```

## yfinance.Ticker.cashflow
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.cashflow.html

- ***property*Ticker.cashflow*: DataFrame***

## yfinance.Ticker.get_insider_roster_holders
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_insider_roster_holders.html

- **Ticker.get_insider_roster_holders(*as_dict=False*)**

## yfinance.Ticker.upgrades_downgrades
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.upgrades_downgrades.html

- ***property*Ticker.upgrades_downgrades**

## yfinance.Ticker.get_recommendations
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_recommendations.html

- **Ticker.get_recommendations(*as_dict=False*)**: Returns a DataFrame with the recommendations Columns: period strongBuy buy hold sell strongSell

## Sector and Industry
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.sector_industry.html

### Sector class

 The Sector and Industry modules provide access to the Sector and Industry information.

 | [`Sector`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Sector.html)(key[, session]) | Represents a financial market sector and allows retrieval of sector-related data such as top ETFs, top mutual funds, and industry data. |
| --- | --- |
| [`Industry`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Industry.html)(key[, session]) | Represents an industry within a sector. |

  > **See also**
> 
> - **`Sector.industries`**: Map of sector and industry

   ### Sample Code

 To initialize, use the relevant sector or industry key as below.

 ```
import yfinance as yf

tech = yf.Sector('technology')
software = yf.Industry('software-infrastructure')

# Common information
tech.key
tech.name
tech.symbol
tech.ticker
tech.overview
tech.top_companies
tech.research_reports

# Sector information
tech.top_etfs
tech.top_mutual_funds
tech.industries

# Industry information
software.sector_key
software.sector_name
software.top_performing_companies
software.top_growth_companies
```

  The modules can be chained with Ticker as below.

 ```
import yfinance as yf
# Ticker to Sector and Industry
msft = yf.Ticker('MSFT')
tech = yf.Sector(msft.info.get('sectorKey'))
software = yf.Industry(msft.info.get('industryKey'))

# Sector and Industry to Ticker
tech_ticker = tech.ticker
tech_ticker.info
software_ticker = software.ticker
software_ticker.history()
```

## yfinance.Ticker.get_sustainability
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_sustainability.html

- **Ticker.get_sustainability(*as_dict=False*)**

## yfinance.Ticker.get_news
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_news.html

- **Ticker.get_news(*count=10*, *tab='news'*)  list**: Allowed options for tab: news, all, press releases

## yfinance.enable_debug_mode
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.enable_debug_mode.html

- **yfinance.enable_debug_mode()**

## yfinance.Ticker.calendar
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.calendar.html

- ***property*Ticker.calendar*: dict***: Returns a dictionary of events, earnings, and dividends for the ticker

## yfinance.Ticker.insider_purchases
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.insider_purchases.html

- ***property*Ticker.insider_purchases*: DataFrame***

## Tickers
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Tickers.html

- ***class*yfinance.Tickers(*tickers*, *session=None*)**: Methods

 - **__init__(*tickers*, *session=None*)**

 - **download(*period=None*, *interval='1d'*, *start=None*, *end=None*, *prepost=False*, *actions=True*, *auto_adjust=True*, *repair=False*, *threads=True*, *group_by='column'*, *progress=True*, *timeout=10*, ***kwargs*)**

 - **history(*period=None*, *interval='1d'*, *start=None*, *end=None*, *prepost=False*, *actions=True*, *auto_adjust=True*, *repair=False*, *threads=True*, *group_by='column'*, *progress=True*, *timeout=10*, ***kwargs*)**

 - **live(*message_handler=None*, *verbose=True*)**

 - **news()**

## yfinance.Ticker.insider_roster_holders
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.insider_roster_holders.html

- ***property*Ticker.insider_roster_holders*: DataFrame***

## FundsData
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.scrapers.funds.FundsData.html

- ***class*yfinance.scrapers.funds.FundsData(*data: YfData*, *symbol: str*)**: ETF and Mutual Funds Data Queried Modules: quoteType, summaryProfile, fundProfile, topHoldings

 Notes: - fundPerformance module is not implemented as better data is queryable using history

 - **Parameters:**: - **data** (*YfData*)  The YfData object for fetching data.
- **symbol** (*str*)  The symbol of the fund.

 Attributes

 - **asset_classes**: Returns the asset classes of the fund.

 - **Returns:**: The asset classes.
- **Return type:**: Dict[str, float]

 - **bond_holdings**: Returns the bond holdings of the fund.

 - **Returns:**: The bond holdings.
- **Return type:**: pd.DataFrame

 - **bond_ratings**: Returns the bond ratings of the fund.

 - **Returns:**: The bond ratings.
- **Return type:**: Dict[str, float]

 - **description**: Returns the description of the fund.

 - **Returns:**: The description.
- **Return type:**: str

 - **equity_holdings**: Returns the equity holdings of the fund.

 - **Returns:**: The equity holdings.
- **Return type:**: pd.DataFrame

 - **fund_operations**: Returns the fund operations.

 - **Returns:**: The fund operations.
- **Return type:**: pd.DataFrame

 - **fund_overview**: Returns the fund overview.

 - **Returns:**: The fund overview.
- **Return type:**: Dict[str, Optional[str]]

 - **sector_weightings**: Returns the sector weightings of the fund.

 - **Returns:**: The sector weightings.
- **Return type:**: Dict[str, float]

 - **top_holdings**: Returns the top holdings of the fund.

 - **Returns:**: The top holdings.
- **Return type:**: pd.DataFrame

 Methods

 - **__init__(*data: YfData*, *symbol: str*)**: - **Parameters:**: - **data** (*YfData*)  The YfData object for fetching data.
- **symbol** (*str*)  The symbol of the fund.

 - **quote_type()  str**: Returns the quote type of the fund.

 - **Returns:**: The quote type.
- **Return type:**: str

 - **quote_type()  str**: Returns the quote type of the fund.

 - **Returns:**: The quote type.
- **Return type:**: str

## yfinance.Ticker.capital_gains
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.capital_gains.html

- ***property*Ticker.capital_gains*: Series***

## EquityQuery
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.EquityQuery.html

- ***class*yfinance.EquityQuery(*operator: str*, *operand: List[QueryBase] | Tuple[str, Tuple[str | Real, ...]]*)**: The EquityQuery class constructs filters for stocks based on specific criteria such as region, sector, exchange, and peer group.

 Start with value operations: EQ (equals), IS-IN (is in), BTWN (between), GT (greater than), LT (less than), GTE (greater or equal), LTE (less or equal).

 Combine them with logical operations: AND, OR.

 Example

 Predefined Yahoo query aggressive_small_caps:

 ```
from yfinance import EquityQuery

EquityQuery('and', [
    EquityQuery('is-in', ['exchange', 'NMS', 'NYQ']),
    EquityQuery('lt', ["epsgrowth.lasttwelvemonths", 15])
])
```

  Attributes

 - **valid_fields**: Valid operands, grouped by category.

 | Key | Values |
| --- | --- |
| eq_fields | - exchange
- industry
- peer_group
- region
- sector |
| price | - eodprice
- fiftytwowkpercentchange
- intradaymarketcap
- intradayprice
- intradaypricechange
- lastclose52weekhigh.lasttwelvemonths
- lastclose52weeklow.lasttwelvemonths
- lastclosemarketcap.lasttwelvemonths
- percentchange |
| trading | - avgdailyvol3m
- beta
- dayvolume
- eodvolume
- pctheldinsider
- pctheldinst |
| short_interest | - days_to_cover_short.value
- short_interest.value
- short_interest_percentage_change.value
- short_percentage_of_float.value
- short_percentage_of_shares_outstanding.value |
| valuation | - bookvalueshare.lasttwelvemonths
- lastclosemarketcaptotalrevenue.lasttwelvemonths
- lastclosepriceearnings.lasttwelvemonths
- lastclosepricetangiblebookvalue.lasttwelvemonths
- lastclosetevtotalrevenue.lasttwelvemonths
- pegratio_5y
- peratio.lasttwelvemonths
- pricebookratio.quarterly |
| profitability | - consecutive_years_of_dividend_growth_count
- forward_dividend_per_share
- forward_dividend_yield
- returnonassets.lasttwelvemonths
- returnonequity.lasttwelvemonths
- returnontotalcapital.lasttwelvemonths |
| leverage | - ebitdainterestexpense.lasttwelvemonths
- ebitinterestexpense.lasttwelvemonths
- lastclosetevebit.lasttwelvemonths
- lastclosetevebitda.lasttwelvemonths
- ltdebtequity.lasttwelvemonths
- netdebtebitda.lasttwelvemonths
- totaldebtebitda.lasttwelvemonths
- totaldebtequity.lasttwelvemonths |
| liquidity | - altmanzscoreusingtheaveragestockinformationforaperiod.lasttwelvemonths
- currentratio.lasttwelvemonths
- operatingcashflowtocurrentliabilities.lasttwelvemonths
- quickratio.lasttwelvemonths |
| income_statement | - basicepscontinuingoperations.lasttwelvemonths
- dilutedeps1yrgrowth.lasttwelvemonths
- dilutedepscontinuingoperations.lasttwelvemonths
- ebit.lasttwelvemonths
- ebitda.lasttwelvemonths
- ebitda1yrgrowth.lasttwelvemonths
- ebitdamargin.lasttwelvemonths
- epsgrowth.lasttwelvemonths
- grossprofit.lasttwelvemonths
- grossprofitmargin.lasttwelvemonths
- netepsbasic.lasttwelvemonthsnetepsdiluted.lasttwelvemonths
- netincome1yrgrowth.lasttwelvemonths
- netincomeis.lasttwelvemonths
- netincomemargin.lasttwelvemonths
- operatingincome.lasttwelvemonths
- quarterlyrevenuegrowth.quarterly
- totalrevenues.lasttwelvemonths
- totalrevenues1yrgrowth.lasttwelvemonths |
| balance_sheet | - totalassets.lasttwelvemonths
- totalcashandshortterminvestments.lasttwelvemonths
- totalcommonequity.lasttwelvemonths
- totalcommonsharesoutstanding.lasttwelvemonths
- totalcurrentassets.lasttwelvemonths
- totalcurrentliabilities.lasttwelvemonths
- totaldebt.lasttwelvemonths
- totalequity.lasttwelvemonths
- totalsharesoutstanding |
| cash_flow | - capitalexpenditure.lasttwelvemonths
- cashfromoperations.lasttwelvemonths
- cashfromoperations1yrgrowth.lasttwelvemonths
- forward_dividend_yield
- leveredfreecashflow.lasttwelvemonths
- leveredfreecashflow1yrgrowth.lasttwelvemonths
- unleveredfreecashflow.lasttwelvemonths |
| esg | - environmental_score
- esg_score
- governance_score
- highest_controversy
- social_score |

 - **valid_values**: Most operands take number values, but some have a restricted set of valid values.

 | Key | Values |
| --- | --- |
| region | ar, at, au, be, br, ca, ch, cl, cn, co, cz, de, dk, ee, eg, es, fi, fr, gb, gr, hk, hu, id, ie, il, in, is, it, jp, kr, kw, lk, lt, lv, mx, my, nl, no, nz, pe, ph, pk, pl, pt, qa, ro, ru, sa, se, sg, sr, sw, th, tr, tw, us, ve, vn, za |
| exchange | ar: BUE. at: VIE. au: ASX. be: BRU br: SAO. ca: CNQ, NEO, TOR, VAN ch: EBS. cl: SGO. cn: SHH, SHZ co: BVC. cz: PRA de: BER, DUS, FRA, GER, HAM, MUN, STU dk: CPH. ee: TAL. eg: CAI. es: MCE fi: HEL. fr: PAR. gb: AQS, IOB, LSE gr: ATH. hk: HKG. hu: BUD. id: JKT ie: ISE. il: TLV. in: BSE, NSI is: ICE. it: MIL. jp: FKA, JPX, SAP kr: KOE, KSC. kw: KUW. lk: lt: LIT. lv: RIS. mx: MEX. my: KLS nl: AMS. no: OSL. nz: NZE. pe: ph: PHP, PHS. pk: . pl: WSE pt: LIS. qa: DOH. ro: BVB. ru: sa: SAU. se: STO. sg: SES. sr: sw: EBS. th: SET. tr: IST tw: TAI, TWO us: ASE, BTS, CXI, NCM, NGM, NMS, NYQ, OEM, OQB, OQX, PCX, PNK, YHD ve: CCS. vn: . za: JNB |
| sector | - Basic Materials
- Communication Services
- Consumer Cyclical
- Consumer Defensive
- Energy
- Financial Services
- Healthcare
- Industrials
- Real Estate
- Technology
- Utilities |
| industry | Basic Materials: Agricultural Inputs, Aluminum, Building Materials, Chemicals, Coking Coal, Copper, Gold, Lumber & Wood Production, Other Industrial Metals & Mining, Other Precious Metals & Mining, Paper & Paper Products, Silver, Specialty Chemicals, Steel Communication Services: Advertising Agencies, Broadcasting, Electronic Gaming & Multimedia, Entertainment, Internet Content & Information, Publishing, Telecom Services Consumer Cyclical: Apparel Manufacturing, Apparel Retail, Auto & Truck Dealerships, Auto Manufacturers, Auto Parts, Department Stores, Footwear & Accessories, Furnishings, Fixtures & Appliances, Gambling, Home Improvement Retail, Internet Retail, Leisure, Lodging, Luxury Goods, Packaging & Containers, Personal Services, Recreational Vehicles, Residential Construction, Resorts & Casinos, Restaurants, Specialty Retail, Textile Manufacturing, Travel Services Consumer Defensive: BeveragesBrewers, BeveragesNon-Alcoholic, BeveragesWineries & Distilleries, Confectioners, Discount Stores, Education & Training Services, Farm Products, Food Distribution, Grocery Stores, Household & Personal Products, Packaged Foods, Tobacco Energy: Oil & Gas Drilling, Oil & Gas E&P, Oil & Gas Equipment & Services, Oil & Gas Integrated, Oil & Gas Midstream, Oil & Gas Refining & Marketing, Thermal Coal, Uranium Financial Services: Asset Management, BanksDiversified, BanksRegional, Capital Markets, Credit Services, Financial Conglomerates, Financial Data & Stock Exchanges, Insurance Brokers, InsuranceDiversified, InsuranceLife, InsuranceProperty & Casualty, InsuranceReinsurance, InsuranceSpecialty, Mortgage Finance, Shell Companies Healthcare: Biotechnology, Diagnostics & Research, Drug ManufacturersGeneral, Drug ManufacturersSpecialty & Generic, Health Information Services, Healthcare Plans, Medical Care Facilities, Medical Devices, Medical Distribution, Medical Instruments & Supplies, Pharmaceutical Retailers Industrials: Aerospace & Defense, Airlines, Airports & Air Services, Building Products & Equipment, Business Equipment & Supplies, Conglomerates, Consulting Services, Electrical Equipment & Parts, Engineering & Construction, Farm & Heavy Construction Machinery, Industrial Distribution, Infrastructure Operations, Integrated Freight & Logistics, Marine Shipping, Metal Fabrication, Pollution & Treatment Controls, Railroads, Rental & Leasing Services, Security & Protection Services, Specialty Business Services, Specialty Industrial Machinery, Staffing & Employment Services, Tools & Accessories, Trucking, Waste Management Real Estate: REITDiversified, REITHealthcare Facilities, REITHotel & Motel, REITIndustrial, REITMortgage, REITOffice, REITResidential, REITRetail, REITSpecialty, Real Estate Services, Real EstateDevelopment, Real EstateDiversified Technology: Communication Equipment, Computer Hardware, Consumer Electronics, Electronic Components, Electronics & Computer Distribution, Information Technology Services, Scientific & Technical Instruments, Semiconductor Equipment & Materials, Semiconductors, SoftwareApplication, SoftwareInfrastructure, Solar Utilities: UtilitiesDiversified, UtilitiesIndependent Power Producers, UtilitiesRegulated Electric, UtilitiesRegulated Gas, UtilitiesRegulated Water, UtilitiesRenewable |
| peer_group | - Aerospace & Defense
- Auto Components
- Automobiles
- Banks
- Building Products
- Chemicals
- China Fund Aggressive Allocation Fund
- China Fund Equity Funds
- China Fund QDII Greater China Equity
- China Fund QDII Sector Equity
- China Fund Sector Equity Financial and Real Estate
- Commercial Services
- Construction & Engineering
- Construction Materials
- Consumer Durables
- Consumer Services
- Containers & Packaging
- Diversified Financials
- Diversified Metals
- EAA CE Global Large-Cap Blend Equity
- EAA CE Other
- EAA CE Sector Equity Biotechnology
- EAA CE UK Large-Cap Equity
- EAA CE UK Small-Cap Equity
- EAA Fund Asia ex-Japan Equity
- EAA Fund China Equity
- EAA Fund China Equity - A Shares
- EAA Fund Denmark Equity
- EAA Fund EUR Aggressive Allocation - Global
- EAA Fund EUR Corporate Bond
- EAA Fund EUR Moderate Allocation - Global
- EAA Fund Emerging Europe ex-Russia Equity
- EAA Fund Europe Large-Cap Blend Equity
- EAA Fund Eurozone Large-Cap Equity
- EAA Fund Germany Equity
- EAA Fund Global Emerging Markets Equity
- EAA Fund Global Equity Income
- EAA Fund Global Flex-Cap Equity
- EAA Fund Global Large-Cap Blend Equity
- EAA Fund Global Large-Cap Growth Equity
- EAA Fund Hong Kong Equity
- EAA Fund Japan Large-Cap Equity
- EAA Fund Other Bond
- EAA Fund Other Equity
- EAA Fund RMB Bond - Onshore
- EAA Fund Sector Equity Consumer Goods & Services
- EAA Fund Sector Equity Financial Services
- EAA Fund Sector Equity Industrial Materials
- EAA Fund Sector Equity Technology
- EAA Fund South Africa & Namibia Equity
- EAA Fund Switzerland Equity
- EAA Fund US Large-Cap Blend Equity
- EAA Fund USD Corporate Bond
- Electrical Equipment
- Energy Services
- Food Products
- Food Retailers
- Healthcare
- Homebuilders
- Household Products
- India CE Multi-Cap
- India Fund Large-Cap
- India Fund Sector - Financial Services
- Industrial Conglomerates
- Insurance
- Machinery
- Media
- Mexico Fund Mexico Equity
- Oil & Gas Producers
- Paper & Forestry
- Pharmaceuticals
- Precious Metals
- Real Estate
- Refiners & Pipelines
- Retailing
- Semiconductors
- Software & Services
- Steel
- Technology Hardware
- Telecommunication Services
- Textiles & Apparel
- Traders & Distributors
- Transportation
- Transportation Infrastructure
- US CE Convertibles
- US CE Options-based
- US CE Preferred Stock
- US Fund China Region
- US Fund Consumer Cyclical
- US Fund Diversified Emerging Mkts
- US Fund Equity Energy
- US Fund Equity Precious Metals
- US Fund Financial
- US Fund Foreign Large Blend
- US Fund Health
- US Fund Large Blend
- US Fund Large Growth
- US Fund Large Value
- US Fund Miscellaneous Region
- US Fund Natural Resources
- US Fund Technology
- US Fund TradingLeveraged Equity
- Utilities |

 Methods

 - **__init__(*operator: str*, *operand: List[QueryBase] | Tuple[str, Tuple[str | Real, ...]]*)**

 - **to_dict()  Dict**

## Ticker
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html

- ***class*yfinance.Ticker(*ticker*, *session=None*)**: Initialize a Yahoo Finance Ticker object.

 - **Parameters:**: - **ticker** (*str**|**tuple**[**str**,**str**]*)  Yahoo Finance symbol (e.g. AAPL) or a tuple of (symbol, MIC) e.g. (OR,XPAR) (MIC = market identifier code)
- **session** (*requests.Session**,**optional*)  Custom requests session.

 Attributes

 - **actions**

 - **analyst_price_targets**

 - **balance_sheet**

 - **balancesheet**

 - **calendar**: Returns a dictionary of events, earnings, and dividends for the ticker

 - **capital_gains**

 - **cash_flow**

 - **cashflow**

 - **dividends**

 - **earnings**

 - **earnings_dates**

 - **earnings_estimate**

 - **earnings_history**

 - **eps_revisions**

 - **eps_trend**

 - **fast_info**

 - **financials**

 - **funds_data**

 - **growth_estimates**

 - **history_metadata**

 - **income_stmt**

 - **incomestmt**

 - **info**

 - **insider_purchases**

 - **insider_roster_holders**

 - **insider_transactions**

 - **institutional_holders**

 - **isin**

 - **major_holders**

 - **mutualfund_holders**

 - **news**

 - **options**

 - **quarterly_balance_sheet**

 - **quarterly_balancesheet**

 - **quarterly_cash_flow**

 - **quarterly_cashflow**

 - **quarterly_earnings**

 - **quarterly_financials**

 - **quarterly_income_stmt**

 - **quarterly_incomestmt**

 - **recommendations**

 - **recommendations_summary**

 - **revenue_estimate**

 - **sec_filings**

 - **shares**

 - **splits**

 - **sustainability**

 - **ttm_cash_flow**

 - **ttm_cashflow**

 - **ttm_financials**

 - **ttm_income_stmt**

 - **ttm_incomestmt**

 - **upgrades_downgrades**

 Methods

 - **__init__(*ticker*, *session=None*)**: Initialize a Yahoo Finance Ticker object.

 - **Parameters:**: - **ticker** (*str**|**tuple**[**str**,**str**]*)  Yahoo Finance symbol (e.g. AAPL) or a tuple of (symbol, MIC) e.g. (OR,XPAR) (MIC = market identifier code)
- **session** (*requests.Session**,**optional*)  Custom requests session.

 - **get_actions(*period='max'*)  Series**

 - **get_analyst_price_targets()  dict**: Keys: current low high mean median

 - **get_balance_sheet(*as_dict=False*, *pretty=False*, *freq='yearly'*)**: - **Parameters:**: - **as_dict: bool**: Return table as Python dict Default is False
- **pretty: bool**: Format row names nicely for readability Default is False
- **freq: str**: yearly or quarterly Default is yearly

 - **get_balancesheet(*as_dict=False*, *pretty=False*, *freq='yearly'*)**

 - **get_calendar()  dict**

 - **get_capital_gains(*period='max'*)  Series**

 - **get_cash_flow(*as_dict=False*, *pretty=False*, *freq='yearly'*)  DataFrame | dict**: - **Parameters:**: - **as_dict: bool**: Return table as Python dict Default is False
- **pretty: bool**: Format row names nicely for readability Default is False
- **freq: str**: yearly or quarterly Default is yearly

 - **get_cashflow(*as_dict=False*, *pretty=False*, *freq='yearly'*)**

 - **get_dividends(*period='max'*)  Series**

 - **get_earnings(*as_dict=False*, *freq='yearly'*)**: - **Parameters:**: - **as_dict: bool**: Return table as Python dict Default is False
- **freq: str**: yearly or quarterly or trailing Default is yearly

 - **get_earnings_dates(*limit=12*, *offset=0*)  DataFrame | None**

 - **get_earnings_estimate(*as_dict=False*)**: Index: 0q +1q 0y +1y Columns: numberOfAnalysts avg low high yearAgoEps growth

 - **get_earnings_history(*as_dict=False*)**: Index: pd.DatetimeIndex Columns: epsEstimate epsActual epsDifference surprisePercent

 - **get_eps_revisions(*as_dict=False*)**: Index: 0q +1q 0y +1y Columns: upLast7days upLast30days downLast7days downLast30days

 - **get_eps_trend(*as_dict=False*)**: Index: 0q +1q 0y +1y Columns: current 7daysAgo 30daysAgo 60daysAgo 90daysAgo

 - **get_fast_info()**

 - **get_financials(*as_dict=False*, *pretty=False*, *freq='yearly'*)**

 - **get_funds_data()  [FundsData](https://ranaroussi.github.io/yfinance/reference/api/yfinance.scrapers.funds.FundsData.html) | None**

 - **get_growth_estimates(*as_dict=False*)**: Index: 0q +1q 0y +1y +5y -5y Columns: stock industry sector index

 - **get_history_metadata()  dict**

 - **get_income_stmt(*as_dict=False*, *pretty=False*, *freq='yearly'*)**: - **Parameters:**: - **as_dict: bool**: Return table as Python dict Default is False
- **pretty: bool**: Format row names nicely for readability Default is False
- **freq: str**: yearly or quarterly or trailing Default is yearly

 - **get_incomestmt(*as_dict=False*, *pretty=False*, *freq='yearly'*)**

 - **get_info()  dict**

 - **get_insider_purchases(*as_dict=False*)**

 - **get_insider_roster_holders(*as_dict=False*)**

 - **get_insider_transactions(*as_dict=False*)**

 - **get_institutional_holders(*as_dict=False*)**

 - **get_isin()  str | None**

 - **get_major_holders(*as_dict=False*)**

 - **get_mutualfund_holders(*as_dict=False*)**

 - **get_news(*count=10*, *tab='news'*)  list**: Allowed options for tab: news, all, press releases

 - **get_recommendations(*as_dict=False*)**: Returns a DataFrame with the recommendations Columns: period strongBuy buy hold sell strongSell

 - **get_recommendations_summary(*as_dict=False*)**

 - **get_revenue_estimate(*as_dict=False*)**: Index: 0q +1q 0y +1y Columns: numberOfAnalysts avg low high yearAgoRevenue growth

 - **get_sec_filings()  dict**

 - **get_shares(*as_dict=False*)  DataFrame | dict**

 - **get_shares_full(*start=None*, *end=None*)**

 - **get_splits(*period='max'*)  Series**

 - **get_sustainability(*as_dict=False*)**

 - **get_upgrades_downgrades(*as_dict=False*)**: Returns a DataFrame with the recommendations changes (upgrades/downgrades) Index: date of grade Columns: firm toGrade fromGrade action

 - **history(**args*, ***kwargs*)  DataFrame**

 - **live(*message_handler=None*, *verbose=True*)**

 - **option_chain(*date=None*, *tz=None*)**

## yfinance.Ticker.eps_trend
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.eps_trend.html

- ***property*Ticker.eps_trend*: DataFrame***

## yfinance.Ticker.earnings_history
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.earnings_history.html

- ***property*Ticker.earnings_history*: DataFrame***

## FundQuery
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.FundQuery.html

- ***class*yfinance.FundQuery(*operator: str*, *operand: List[QueryBase] | Tuple[str, Tuple[str | Real, ...]]*)**: The FundQuery class constructs filters for mutual funds based on specific criteria such as region, sector, exchange, and peer group.

 Start with value operations: EQ (equals), IS-IN (is in), BTWN (between), GT (greater than), LT (less than), GTE (greater or equal), LTE (less or equal).

 Combine them with logical operations: AND, OR.

 Example

 Predefined Yahoo query solid_large_growth_funds:

 ```
from yfinance import FundQuery

FundQuery('and', [
    FundQuery('eq', ['categoryname', 'Large Growth']),
    FundQuery('is-in', ['performanceratingoverall', 4, 5]),
    FundQuery('lt', ['initialinvestment', 100001]),
    FundQuery('lt', ['annualreturnnavy1categoryrank', 50]),
    FundQuery('eq', ['exchange', 'NAS'])
])
```

  Attributes

 - **valid_fields**: Valid operands, grouped by category.

 | Key | Values |
| --- | --- |
| eq_fields | - annualreturnnavy1categoryrank
- categoryname
- exchange
- initialinvestment
- performanceratingoverall
- riskratingoverall |
| price | - eodprice
- intradayprice
- intradaypricechange |

 - **valid_values**: Most operands take number values, but some have a restricted set of valid values.

 | Key | Values |
| --- | --- |
| exchange | - us: NAS |

 Methods

 - **__init__(*operator: str*, *operand: List[QueryBase] | Tuple[str, Tuple[str | Real, ...]]*)**

 - **to_dict()  Dict**

## yfinance.download
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html

- **yfinance.download(*tickers*, *start=None*, *end=None*, *actions=False*, *threads=True*, *ignore_tz=None*, *group_by='column'*, *auto_adjust=True*, *back_adjust=False*, *repair=False*, *keepna=False*, *progress=True*, *period=None*, *interval='1d'*, *prepost=False*, *rounding=False*, *timeout=10*, *session=None*, *multi_level_index=True*)  DataFrame | None**: Download yahoo tickers :Parameters:

 > - **tickersstr, list**: List of tickers to download
> - **periodstr**: Valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max Default: 1mo Either Use period parameter or use start and end
> - **intervalstr**: Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo Intraday data cannot extend last 60 days
> - **start: str**: Download start date string (YYYY-MM-DD) or _datetime, inclusive. Default is 99 years ago E.g. for start=2020-01-01, the first data point will be on 2020-01-01
> - **end: str**: Download end date string (YYYY-MM-DD) or _datetime, exclusive. Default is now E.g. for end=2023-01-01, the last data point will be on 2022-12-31
> - **group_bystr**: Group by ticker or column (default)
> - **prepostbool**: Include Pre and Post market data in results? Default is False
> - **auto_adjust: bool**: Adjust all OHLC automatically? Default is True
> - **repair: bool**: Detect currency unit 100x mixups and attempt repair Default is False
> - **keepna: bool**: Keep NaN rows returned by Yahoo? Default is False
> - **actions: bool**: Download dividend + stock splits data. Default is False
> - **threads: bool / int**: How many threads to use for mass downloading. Default is True
> - **ignore_tz: bool**: When combining from different timezones, ignore that part of datetime. Default depends on interval. Intraday = False. Day+ = True.
> - **rounding: bool**: Optional. Round values to 2 decimal places?
> - **timeout: None or float**: If not None stops waiting for a response after given number of seconds. (Can also be a fraction of a second e.g. 0.01)
> - **session: None or Session**: Optional. Pass your own session object to be used for all requests
> - **multi_level_index: bool**: Optional. Always return a MultiIndex DataFrame? Default is True

## yfinance.Ticker.get_fast_info
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_fast_info.html

- **Ticker.get_fast_info()**

## Functions and Utilities
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.functions.html

### Download Market Data

 The download function allows you to retrieve market data for multiple tickers at once.

 | [`download`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html)(tickers[, start, end, actions, ...]) | Download yahoo tickers :Parameters: tickers : str, list List of tickers to download period : str Valid periods: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max Default: 1mo Either Use period parameter or use start and end interval : str Valid intervals: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo Intraday data cannot extend last 60 days start: str Download start date string (YYYY-MM-DD) or _datetime, inclusive. Default is 99 years ago E.g. for start="2020-01-01", the first data point will be on "2020-01-01" end: str Download end date string (YYYY-MM-DD) or _datetime, exclusive. Default is now E.g. for end="2023-01-01", the last data point will be on "2022-12-31" group_by : str Group by 'ticker' or 'column' (default) prepost : bool Include Pre and Post market data in results? Default is False auto_adjust: bool Adjust all OHLC automatically? Default is True repair: bool Detect currency unit 100x mixups and attempt repair Default is False keepna: bool Keep NaN rows returned by Yahoo? Default is False actions: bool Download dividend + stock splits data. Default is False threads: bool / int How many threads to use for mass downloading. Default is True ignore_tz: bool When combining from different timezones, ignore that part of datetime. Default depends on interval. Intraday = False. Day+ = True. rounding: bool Optional. Round values to 2 decimal places? timeout: None or float If not None stops waiting for a response after given number of seconds. (Can also be a fraction of a second e.g. 0.01) session: None or Session Optional. Pass your own session object to be used for all requests multi_level_index: bool Optional. Always return a MultiIndex DataFrame? Default is True. |
| --- | --- |

    ### Enable Debug Mode

 Enables logging of debug information for the yfinance package.

 | [`enable_debug_mode`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.enable_debug_mode.html)() |  |
| --- | --- |

    ### Set Timezone Cache Location

 Sets the cache location for timezone data.

 | [`set_tz_cache_location`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.set_tz_cache_location.html)(cache_dir) |  |
| --- | --- |

## yfinance.Ticker.sec_filings
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.sec_filings.html

- ***property*Ticker.sec_filings*: dict***

## yfinance.Ticker.get_insider_purchases
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_insider_purchases.html

- **Ticker.get_insider_purchases(*as_dict=False*)**

## yfinance.Ticker.ttm_cashflow
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.ttm_cashflow.html

- ***property*Ticker.ttm_cashflow*: DataFrame***

## yfinance.Ticker.actions
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.actions.html

- ***property*Ticker.actions*: DataFrame***

## yfinance.Ticker.get_institutional_holders
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_institutional_holders.html

- **Ticker.get_institutional_holders(*as_dict=False*)**

## yfinance.Ticker.get_balance_sheet
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_balance_sheet.html

- **Ticker.get_balance_sheet(*as_dict=False*, *pretty=False*, *freq='yearly'*)**: - **Parameters:**: - **as_dict: bool**: Return table as Python dict Default is False
- **pretty: bool**: Format row names nicely for readability Default is False
- **freq: str**: yearly or quarterly Default is yearly

## Market
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.market.html

### Class

 The Market class, allows you to access market data in a Pythonic way.

 | [`Market`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Market.html)(market[, session, timeout]) |  |
| --- | --- |

    ### Market Sample Code

 ```
import yfinance as yf

EUROPE = yf.Market("EUROPE")

status = EUROPE.status
summary = EUROPE.summary
```

    ### Markets

 There are 8 different markets available in Yahoo Finance.

 - US
- GB

  - ASIA
- EUROPE

  - RATES
- COMMODITIES
- CURRENCIES
- CRYPTOCURRENCIES

## yfinance.Ticker.get_recommendations_summary
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_recommendations_summary.html

- **Ticker.get_recommendations_summary(*as_dict=False*)**

## yfinance.Ticker.sustainability
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.sustainability.html

- ***property*Ticker.sustainability*: DataFrame***

## yfinance.Ticker.isin
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.isin.html

- ***property*Ticker.isin**

## Search & Lookup
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.search.html

### Class

 The Search module, allows you to access search data in a Pythonic way.

 | [`Search`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Search.html)(query[, max_results, news_count, ...]) | Fetches and organizes search results from Yahoo Finance, including stock quotes and news articles. |
| --- | --- |

  The Lookup module, allows you to look up tickers in a Pythonic way.

 | [`Lookup`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Lookup.html)(query[, session, timeout, raise_errors]) | Fetches quote (ticker) lookups from Yahoo Finance. |
| --- | --- |

    ### Sample Code

 The Search module, allows you to access search data in a Pythonic way.

 ```
import yfinance as yf

# get list of quotes
quotes = yf.Search("AAPL", max_results=10).quotes

# get list of news
news = yf.Search("Google", news_count=10).news

# get list of related research
research = yf.Search("apple", include_research=True).research
```

  The Lookup module, allows you to look up tickers in a Pythonic way.

 ```
import yfinance as yf

# Get All
all = yf.Lookup("AAPL").all
all = yf.Lookup("AAPL").get_all(count=100)

# Get Stocks
stock = yf.Lookup("AAPL").stock
stock = yf.Lookup("AAPL").get_stock(count=100)

# Get Mutual Funds
mutualfund = yf.Lookup("AAPL").mutualfund
mutualfund = yf.Lookup("AAPL").get_mutualfund(count=100)

# Get ETFs
etf = yf.Lookup("AAPL").etf
etf = yf.Lookup("AAPL").get_etf(count=100)

# Get Indices
index = yf.Lookup("AAPL").index
index = yf.Lookup("AAPL").get_index(count=100)

# Get Futures
future = yf.Lookup("AAPL").future
future = yf.Lookup("AAPL").get_future(count=100)

# Get Currencies
currency = yf.Lookup("AAPL").currency
currency = yf.Lookup("AAPL").get_currency(count=100)

# Get Cryptocurrencies
cryptocurrency = yf.Lookup("AAPL").cryptocurrency
cryptocurrency = yf.Lookup("AAPL").get_cryptocurrency(count=100)
```

## yfinance.Ticker.get_earnings
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_earnings.html

- **Ticker.get_earnings(*as_dict=False*, *freq='yearly'*)**: - **Parameters:**: - **as_dict: bool**: Return table as Python dict Default is False
- **freq: str**: yearly or quarterly or trailing Default is yearly

## yfinance.Ticker.get_funds_data
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_funds_data.html

- **Ticker.get_funds_data()  [FundsData](https://ranaroussi.github.io/yfinance/reference/api/yfinance.scrapers.funds.FundsData.html) | None**

## yfinance.Ticker.get_revenue_estimate
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_revenue_estimate.html

- **Ticker.get_revenue_estimate(*as_dict=False*)**: Index: 0q +1q 0y +1y Columns: numberOfAnalysts avg low high yearAgoRevenue growth

## yfinance.Ticker.fast_info
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.fast_info.html

- ***property*Ticker.fast_info**

## yfinance.Ticker.history
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html

- **Ticker.history(**args*, ***kwargs*)  DataFrame**

## yfinance.Ticker.funds_data
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.funds_data.html

- ***property*Ticker.funds_data*: [FundsData](https://ranaroussi.github.io/yfinance/reference/api/yfinance.scrapers.funds.FundsData.html)***

## yfinance.Ticker.quarterly_income_stmt
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.quarterly_income_stmt.html

- ***property*Ticker.quarterly_income_stmt*: DataFrame***

## yfinance.Ticker.splits
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.splits.html

- ***property*Ticker.splits*: Series***

## yfinance.Ticker.mutualfund_holders
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.mutualfund_holders.html

- ***property*Ticker.mutualfund_holders*: DataFrame***

## Screener & Query
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.screener.html

### Query Market Data

 The Sector and Industry modules allow you to access the sector and industry information.

 | [`EquityQuery`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.EquityQuery.html)(operator, operand) | The EquityQuery class constructs filters for stocks based on specific criteria such as region, sector, exchange, and peer group. |
| --- | --- |
| [`FundQuery`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.FundQuery.html)(operator, operand) | The FundQuery class constructs filters for mutual funds based on specific criteria such as region, sector, exchange, and peer group. |
| [`screen`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.screen.html)(query[, offset, size, count, ...]) | Run a screen: predefined query, or custom query. |

  > **See also**
> 
> - **`EquityQuery.valid_fields`**: supported operand values for query
> - **`EquityQuery.valid_values`**: supported EQ query operand parameters
> - **`FundQuery.valid_fields`**: supported operand values for query
> - **`FundQuery.valid_values`**: supported EQ query operand parameters

## Stock
Source: https://ranaroussi.github.io/yfinance/reference/yfinance.stock.html

### Ticker stock methods

 | [`get_isin`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_isin.html)() |  |
| --- | --- |
| [`isin`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.isin.html) |  |
| [`history`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html)(*args, **kwargs) |  |

  > **See also**
> 
> - **[`yfinance.scrapers.history.PriceHistory.history()`](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html)**: Documentation for history
> - **[Price Repair](https://ranaroussi.github.io/yfinance/advanced/price_repair.html)**: Documentation for price repair

 | [`get_history_metadata`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_history_metadata.html)() |  |
| --- | --- |
| [`get_dividends`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_dividends.html)([period]) |  |
| [`dividends`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.dividends.html) |  |
| [`get_splits`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_splits.html)([period]) |  |
| [`splits`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.splits.html) |  |
| [`get_actions`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_actions.html)([period]) |  |
| [`actions`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.actions.html) |  |
| [`get_capital_gains`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_capital_gains.html)([period]) |  |
| [`capital_gains`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.capital_gains.html) |  |
| [`get_shares_full`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_shares_full.html)([start, end]) |  |
| [`get_info`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_info.html)() |  |
| [`info`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.info.html) |  |
| [`get_fast_info`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_fast_info.html)() |  |
| [`fast_info`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.fast_info.html) |  |
| [`get_news`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_news.html)([count, tab]) | Allowed options for tab: "news", "all", "press releases |
| [`news`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.news.html) |  |

## yfinance.Ticker.balance_sheet
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.balance_sheet.html

- ***property*Ticker.balance_sheet*: DataFrame***

## yfinance.Ticker.quarterly_cashflow
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.quarterly_cashflow.html

- ***property*Ticker.quarterly_cashflow*: DataFrame***

## yfinance.Ticker.recommendations_summary
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.recommendations_summary.html

- ***property*Ticker.recommendations_summary**

## yfinance.Ticker.get_earnings_dates
Source: https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.get_earnings_dates.html

- **Ticker.get_earnings_dates(*limit=12*, *offset=0*)  DataFrame | None**

