#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


KST = ZoneInfo("Asia/Seoul")

DEFAULT_SYMBOLS = [
    "MSFT",
    "MU",
    "META",
    "AVGO",
    "AMZN",
    "GOOG",
    "NVDA",
    "UBER",
    "WMT",
    "UNH",
    "LLY",
    "COST",
    "PLTR",
    "AMD",
    "MCK",
]

DEFAULT_SWAPS = [
    ("2026-01-08", "MCK", "CVNA"),
    ("2026-01-15", "PLTR", "MS"),
    ("2026-01-27", "UNH", "COF"),
    ("2026-01-27", "META", "MELI"),
    ("2026-01-28", "CVNA", "NFLX"),
    ("2026-02-04", "UBER", "META"),
    ("2026-02-24", "WMT", "AAPL"),
    ("2026-02-24", "MELI", "IBM"),
]


@dataclass(frozen=True)
class SwapRule:
    date: dt.date
    from_symbol: str
    to_symbol: str


class EventFactory:
    def __init__(self) -> None:
        self._base = dt.datetime.now(tz=KST)
        self._offset = 0

    def _logged_at(self) -> str:
        ts = self._base + dt.timedelta(seconds=self._offset)
        self._offset += 1
        return ts.isoformat()

    def cash(
        self,
        date: dt.date,
        amount: float,
        *,
        category: str,
        memo: str,
        external: bool = True,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event_id": str(uuid.uuid4()),
            "logged_at": self._logged_at(),
            "date": date.isoformat(),
            "event_type": "cash",
            "amount": float(amount),
            "category": category,
            "external": external,
            "currency": "USD",
            "memo": memo,
        }

    def trade(
        self,
        date: dt.date,
        symbol: str,
        *,
        side: str,
        quantity: float,
        price: float,
        memo: str,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event_id": str(uuid.uuid4()),
            "logged_at": self._logged_at(),
            "date": date.isoformat(),
            "event_type": "trade",
            "symbol": symbol,
            "side": side,
            "quantity": float(quantity),
            "price": float(price),
            "fee": 0.0,
            "currency": "USD",
            "memo": memo,
        }

    def nav(self, date: dt.date, nav: float, *, source: str, memo: str) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "event_id": str(uuid.uuid4()),
            "logged_at": self._logged_at(),
            "date": date.isoformat(),
            "event_type": "nav_snapshot",
            "nav": float(nav),
            "source": source,
            "memo": memo,
        }


def parse_date(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


def split_csv(text: str) -> list[str]:
    return [item.strip().upper() for item in text.split(",") if item.strip()]


def extract_close_prices(raw: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            close = raw["Close"].copy()
        elif "Adj Close" in raw.columns.get_level_values(0):
            close = raw["Adj Close"].copy()
        else:
            close = raw[raw.columns.get_level_values(0)[0]].copy()
    else:
        col = "Close" if "Close" in raw.columns else ("Adj Close" if "Adj Close" in raw.columns else raw.columns[-1])
        close = raw[[col]].rename(columns={col: symbols[0]})

    if isinstance(close, pd.Series):
        close = close.to_frame(name=symbols[0])

    close = close.copy()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close.columns = [str(c).upper() for c in close.columns]
    close = close.sort_index().ffill()
    return close


def download_close_prices(symbols: list[str], start: dt.date, end: dt.date) -> pd.DataFrame:
    unique_symbols = sorted({s.upper() for s in symbols if s})
    if not unique_symbols:
        return pd.DataFrame()

    fetch_start = start - dt.timedelta(days=14)
    fetch_end = end + dt.timedelta(days=1)
    raw = yf.download(
        tickers=" ".join(unique_symbols),
        start=fetch_start.isoformat(),
        end=fetch_end.isoformat(),
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )
    close = extract_close_prices(raw, unique_symbols)
    if close.empty:
        return close
    return close[(close.index.date >= start) & (close.index.date <= end)]


def safe_price(row: pd.Series, symbol: str) -> float:
    value = row.get(symbol)
    if value is None:
        return float("nan")
    try:
        px = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(px) or px <= 0:
        return float("nan")
    return px


def portfolio_value(symbols: list[str], units: list[float], px_row: pd.Series) -> float:
    total = 0.0
    for symbol, qty in zip(symbols, units):
        px = safe_price(px_row, symbol)
        if math.isnan(px):
            continue
        total += qty * px
    return total


def write_jsonl(path: Path, rows: list[dict[str, Any]], *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0 and not overwrite:
        raise SystemExit(f"{path} already has data. Use --overwrite to replace it.")
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def build_swap_rules() -> list[SwapRule]:
    out: list[SwapRule] = []
    for d, from_symbol, to_symbol in DEFAULT_SWAPS:
        out.append(SwapRule(date=parse_date(d), from_symbol=from_symbol.upper(), to_symbol=to_symbol.upper()))
    return out


def run(
    *,
    start: dt.date,
    end: dt.date,
    out_path: Path,
    initial_capital: float,
    rebalance_dates: list[dt.date],
    overwrite: bool,
) -> None:
    if start > end:
        raise SystemExit("start date must be <= end date")
    if initial_capital <= 0:
        raise SystemExit("initial capital must be > 0")

    swaps = build_swap_rules()
    all_symbols = sorted(set(DEFAULT_SYMBOLS + [s.from_symbol for s in swaps] + [s.to_symbol for s in swaps]))
    close = download_close_prices(all_symbols, start=start, end=end)
    if close.empty:
        raise SystemExit("No price data downloaded from yfinance")

    trading_days = [d for d in close.index if start <= d.date() <= end]
    if not trading_days:
        raise SystemExit("No trading days in the requested date range")

    factory = EventFactory()
    events: list[dict[str, Any]] = []

    symbols = [s.upper() for s in DEFAULT_SYMBOLS]
    n = len(symbols)
    weight = 1.0 / n
    units = [0.0 for _ in range(n)]

    inited = False
    init_date: dt.date | None = None
    swap_applied = [False for _ in swaps]
    rebalance_dates_sorted = sorted(set(rebalance_dates))
    rebalance_done: set[dt.date] = set()

    prev_trade_day: dt.date | None = None

    for ts in trading_days:
        day = ts.date()
        row = close.loc[ts]

        if (not inited) and day >= start:
            init_date = day
            events.append(
                factory.cash(
                    day,
                    initial_capital,
                    category="deposit",
                    memo="Pine strategy initial funding",
                    external=True,
                )
            )
            for i, symbol in enumerate(symbols):
                px = safe_price(row, symbol)
                qty = (initial_capital * weight / px) if not math.isnan(px) else 0.0
                units[i] = qty
                if qty > 0:
                    events.append(
                        factory.trade(
                            day,
                            symbol,
                            side="BUY",
                            quantity=qty,
                            price=px,
                            memo="Initial equal-weight allocation",
                        )
                    )
            inited = True

        if not inited:
            prev_trade_day = day
            continue

        for i, rule in enumerate(swaps):
            if swap_applied[i]:
                continue
            if day < rule.date:
                continue
            if rule.from_symbol not in symbols:
                swap_applied[i] = True
                continue

            pos = symbols.index(rule.from_symbol)
            old_qty = units[pos]
            old_px = safe_price(row, rule.from_symbol)
            new_px = safe_price(row, rule.to_symbol)
            if math.isnan(old_px) or math.isnan(new_px) or new_px <= 0:
                continue

            slot_value = old_qty * old_px
            new_qty = slot_value / new_px

            if old_qty > 0:
                events.append(
                    factory.trade(
                        day,
                        rule.from_symbol,
                        side="SELL",
                        quantity=old_qty,
                        price=old_px,
                        memo=f"Swap out to {rule.to_symbol}",
                    )
                )
            if new_qty > 0:
                events.append(
                    factory.trade(
                        day,
                        rule.to_symbol,
                        side="BUY",
                        quantity=new_qty,
                        price=new_px,
                        memo=f"Swap in from {rule.from_symbol}",
                    )
                )

            symbols[pos] = rule.to_symbol
            units[pos] = new_qty
            swap_applied[i] = True

        rebalance_hit = False
        for reb_date in rebalance_dates_sorted:
            crossed = day >= reb_date and (prev_trade_day is None or prev_trade_day < reb_date)
            if crossed and reb_date not in rebalance_done:
                rebalance_hit = True
                rebalance_done.add(reb_date)

        if rebalance_hit:
            cur_value = portfolio_value(symbols, units, row)
            target_value = cur_value * weight
            for i, symbol in enumerate(symbols):
                px = safe_price(row, symbol)
                if math.isnan(px):
                    continue
                new_qty = target_value / px
                delta = new_qty - units[i]
                if abs(delta) > 1e-12:
                    events.append(
                        factory.trade(
                            day,
                            symbol,
                            side="BUY" if delta > 0 else "SELL",
                            quantity=abs(delta),
                            price=px,
                            memo="One-time rebalance",
                        )
                    )
                units[i] = new_qty

        nav = portfolio_value(symbols, units, row)
        if nav > 0:
            events.append(
                factory.nav(
                    day,
                    nav,
                    source="backtest_pine_equal_weight",
                    memo="Daily close NAV snapshot",
                )
            )

        prev_trade_day = day

    write_jsonl(out_path, events, overwrite=overwrite)

    nav_values = [row["nav"] for row in events if row.get("event_type") == "nav_snapshot"]
    if not nav_values:
        raise SystemExit("Built events but no nav_snapshot rows were generated")

    ret = nav_values[-1] / nav_values[0] - 1.0
    print(f"wrote={out_path}")
    print(f"start={start.isoformat()} end={end.isoformat()}")
    print(f"init_date={init_date.isoformat() if init_date else 'N/A'}")
    print(f"events_total={len(events)} nav_points={len(nav_values)}")
    print(f"nav_start={nav_values[0]:.6f} nav_end={nav_values[-1]:.6f} return={ret*100:.4f}%")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build position_log.jsonl from Pine strategy assumptions (equal weight, swaps, one-time rebalance)."
    )
    parser.add_argument("--start", type=parse_date, default=parse_date("2026-01-01"), help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=parse_date, default=dt.date.today(), help="End date (YYYY-MM-DD)")
    parser.add_argument("--initial-capital", type=float, default=100.0, help="Initial portfolio capital")
    parser.add_argument(
        "--rebalance-dates",
        default="2026-02-01",
        help="Comma-separated rebalance dates (YYYY-MM-DD). Default is one-time rebalance on 2026-02-01.",
    )
    parser.add_argument("--out", default="portfolio/position_log.jsonl", help="Output JSONL path")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output file if it already has data")
    args = parser.parse_args()

    rebalance_dates = [parse_date(x) for x in split_csv(args.rebalance_dates)] if args.rebalance_dates else []
    run(
        start=args.start,
        end=args.end,
        out_path=Path(args.out),
        initial_capital=args.initial_capital,
        rebalance_dates=rebalance_dates,
        overwrite=args.overwrite,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
