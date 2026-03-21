#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


DEFAULT_BASE_DIR = "portfolio"
DEFAULT_TZ = "Asia/Seoul"
POSITION_LOG_FILE = "position_log.jsonl"
DECISION_LOG_FILE = "decision_log.jsonl"
WORLD_DB_FILE = "world_issue_log.sqlite3"

POSITION_EVENT_TRADE = "trade"
POSITION_EVENT_CASH = "cash"
POSITION_EVENT_NAV = "nav_snapshot"

AUTO_LOG_DEFAULT_TAGS = ["portfolio_counseling", "auto_logged"]
AUTO_TICKER_STOPWORDS = {
    "KST",
    "UTC",
    "USD",
    "KRW",
    "NAV",
    "ETF",
    "JSON",
    "CSV",
    "CLI",
    "API",
    "BUY",
    "SELL",
    "CASH",
    "DATE",
    "TRUE",
    "FALSE",
    "PNG",
    "ICS",
    "MD",
    "AND",
    "OR",
    "THE",
    "FOR",
    "WITH",
}
AUTO_DECISION_KEYWORDS: list[tuple[str, str]] = [
    ("considering", "consider"),
    ("considering", "고려"),
    ("considering", "검토"),
    ("goal_update", "goal"),
    ("goal_update", "목표"),
    ("goal_update", "라이프사이클"),
    ("rule", "rule"),
    ("rule", "규칙"),
    ("rule", "리밸런싱"),
    ("risk_note", "risk"),
    ("risk_note", "리스크"),
    ("risk_note", "변동성"),
    ("risk_note", "drawdown"),
]
AUTO_VALUE_RULES: list[tuple[str, list[str]]] = [
    ("안정성", ["안정", "방어", "risk", "volatility", "drawdown", "리스크", "변동성", "낙폭"]),
    ("성장성", ["성장", "growth", "upside", "alpha", "모멘텀"]),
    ("현금흐름", ["배당", "dividend", "income", "cash flow", "현금흐름"]),
    ("분산", ["분산", "상관", "집중", "correlation", "diversification"]),
    ("규율", ["규칙", "discipline", "리밸런싱", "원칙"]),
]
AUTO_TAG_RULES: list[tuple[str, list[str]]] = [
    ("rebalance", ["리밸런싱", "rebalance"]),
    ("risk", ["리스크", "risk", "변동성", "drawdown"]),
    ("goal", ["목표", "goal", "은퇴", "retirement"]),
    ("income", ["배당", "income", "현금흐름"]),
]


def _kst_now() -> dt.datetime:
    return dt.datetime.now(tz=ZoneInfo(DEFAULT_TZ))


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date: {value} (expected YYYY-MM-DD)") from e


def _split_csv(text: str | None) -> list[str]:
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _normalize_text_for_match(text: str) -> str:
    return text.lower().strip()


def _read_optional_text(text: str | None, file_path: str | None) -> str:
    if text and file_path:
        raise SystemExit("Choose one of --*-text or --*-file")
    if file_path:
        path = Path(file_path)
        if not path.exists():
            raise SystemExit(f"File not found: {path}")
        return path.read_text(encoding="utf-8")
    return text or ""


def _read_response_text_for_autolog(args: argparse.Namespace) -> str:
    body = _read_optional_text(args.response_text, args.response_file)
    if body:
        return body

    # 입력 인자가 없고 stdin이 파이프라면 자동 수집한다.
    if not sys.stdin.isatty():
        piped = sys.stdin.read()
        if piped.strip():
            return piped
    raise SystemExit("response text is required (--response-text / --response-file / piped stdin)")


def _clean_markdown_prefix(line: str) -> str:
    return re.sub(r"^\s*(#+|\-|\*|\d+\.)\s*", "", line).strip()


def _infer_summary_from_text(text: str) -> str:
    for raw_line in text.splitlines():
        line = _clean_markdown_prefix(raw_line)
        if not line:
            continue
        if line.startswith("```"):
            continue
        return line[:160]
    return "포트폴리오 상담 기록"


def _extract_tickers_from_text(text: str, limit: int = 12) -> list[str]:
    pattern = re.compile(r"(?:\^[A-Z]{2,5}|[A-Z]{2,5}(?:\.[A-Z])?)")
    found = pattern.findall(text)
    out: list[str] = []
    for token in found:
        t = token.upper()
        if t.startswith("^"):
            t = t[1:]
        if t in AUTO_TICKER_STOPWORDS:
            continue
        out.append(t)
    out = _unique_preserve_order(out)
    return out[:limit]


def _infer_decision_type(text: str) -> str:
    lowered = _normalize_text_for_match(text)
    for decision_type, keyword in AUTO_DECISION_KEYWORDS:
        if keyword in lowered:
            return decision_type
    return "reflection"


def _infer_values(text: str) -> list[str]:
    lowered = _normalize_text_for_match(text)
    values: list[str] = []
    for label, keys in AUTO_VALUE_RULES:
        if any(k in lowered for k in keys):
            values.append(label)
    return _unique_preserve_order(values)


def _infer_tags(text: str) -> list[str]:
    lowered = _normalize_text_for_match(text)
    tags: list[str] = []
    for tag, keys in AUTO_TAG_RULES:
        if any(k in lowered for k in keys):
            tags.append(tag)
    return _unique_preserve_order(tags)


def _clamp_confidence(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(num):
        return default
    return num


def _portfolio_paths(base_dir: str) -> tuple[Path, Path, Path]:
    base = Path(base_dir)
    return base, base / POSITION_LOG_FILE, base / DECISION_LOG_FILE


def _world_memory_db_path(base_dir: str) -> Path:
    return Path(base_dir) / WORLD_DB_FILE


def _ensure_logs(base_dir: str) -> tuple[Path, Path, Path]:
    base, position_log, decision_log = _portfolio_paths(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    if not position_log.exists():
        position_log.touch()
    if not decision_log.exists():
        decision_log.touch()
    return base, position_log, decision_log


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"JSONL parse error in {path}:{line_no}: {e.msg}") from e
    return rows


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))
        f.write("\n")


def _event_date(row: dict[str, Any]) -> dt.date:
    raw = row.get("date")
    if not isinstance(raw, str):
        raise SystemExit(f"Invalid event date in position log: {row}")
    try:
        return dt.date.fromisoformat(raw)
    except ValueError as e:
        raise SystemExit(f"Invalid event date format in position log: {raw}") from e


def _event_sort_key(row: dict[str, Any]) -> tuple[dt.date, str, str]:
    date_value = _event_date(row)
    logged_at = str(row.get("logged_at", ""))
    event_id = str(row.get("event_id", ""))
    return date_value, logged_at, event_id


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return value
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def _emit_text(text: str, out_path: str | None) -> None:
    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        return
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def _emit_dataframe(df: pd.DataFrame, fmt: str, out_path: str | None) -> None:
    if fmt == "md":
        if df.empty:
            _emit_text("(no rows)\n", out_path)
            return
        try:
            _emit_text(df.to_markdown(index=False) + "\n", out_path)
            return
        except Exception:
            _emit_text(df.to_string(index=False) + "\n", out_path)
            return
    if fmt == "csv":
        _emit_text(df.to_csv(index=False), out_path)
        return
    if fmt == "pretty":
        _emit_text(df.to_string(index=False) + "\n", out_path)
        return
    if fmt == "json":
        rows = [{k: _json_safe(v) for k, v in row.items()} for row in df.to_dict(orient="records")]
        _emit_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", out_path)
        return
    raise SystemExit(f"Unsupported format: {fmt}")


def _normalize_symbol(text: str) -> str:
    return text.strip().upper()


def _extract_close_prices(raw: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        level0 = set(raw.columns.get_level_values(0))
        if "Close" in level0:
            close = raw["Close"].copy()
        elif "Adj Close" in level0:
            close = raw["Adj Close"].copy()
        else:
            first_col = raw.columns.get_level_values(0)[0]
            close = raw[first_col].copy()
    else:
        if "Close" in raw.columns:
            base_col = "Close"
        elif "Adj Close" in raw.columns:
            base_col = "Adj Close"
        else:
            base_col = raw.columns[-1]
        single_symbol = symbols[0]
        close = raw[[base_col]].rename(columns={base_col: single_symbol})

    if isinstance(close, pd.Series):
        close = close.to_frame(name=symbols[0])

    close = close.copy()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = close.sort_index()

    normalized_cols = [_normalize_symbol(str(col)) for col in close.columns]
    close.columns = normalized_cols
    return close


def _download_close_prices(symbols: list[str], start: dt.date, end: dt.date) -> pd.DataFrame:
    unique_symbols = sorted({_normalize_symbol(s) for s in symbols if s})
    if not unique_symbols:
        return pd.DataFrame()

    # buffer를 주어 휴장일/첫 거래일 누락으로 인한 가격 공백을 줄인다.
    fetch_start = start - dt.timedelta(days=10)
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
    close = _extract_close_prices(raw, unique_symbols)
    if close.empty:
        return close

    idx = pd.date_range(start=start, end=end, freq="D")
    close = close.reindex(idx).ffill()
    return close


def _collect_trade_symbols(events: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for row in events:
        if row.get("event_type") != POSITION_EVENT_TRADE:
            continue
        symbol = row.get("symbol")
        if isinstance(symbol, str) and symbol.strip():
            out.append(_normalize_symbol(symbol))
    return sorted(set(out))


def _apply_event_to_state(
    row: dict[str, Any],
    *,
    positions: dict[str, float],
    cash: float,
) -> tuple[float, float]:
    event_type = row.get("event_type")

    if event_type == POSITION_EVENT_TRADE:
        symbol = _normalize_symbol(str(row.get("symbol", "")))
        side = str(row.get("side", "")).upper()
        qty = _safe_float(row.get("quantity"))
        price = _safe_float(row.get("price"))
        fee = _safe_float(row.get("fee"))

        if side not in {"BUY", "SELL"}:
            raise SystemExit(f"Invalid side in trade event: {row}")
        if qty <= 0:
            raise SystemExit(f"Quantity must be > 0 in trade event: {row}")
        if symbol == "":
            raise SystemExit(f"Empty symbol in trade event: {row}")

        signed_qty = qty if side == "BUY" else -qty
        positions[symbol] = positions.get(symbol, 0.0) + signed_qty
        if abs(positions[symbol]) < 1e-12:
            positions.pop(symbol, None)

        if side == "BUY":
            cash += -qty * price - fee
        else:
            cash += qty * price - fee
        return cash, 0.0

    if event_type == POSITION_EVENT_CASH:
        amount = _safe_float(row.get("amount"))
        external = bool(row.get("external", False))
        cash += amount
        external_flow = amount if external else 0.0
        return cash, external_flow

    # nav_snapshot은 포지션/현금 상태 변화 이벤트가 아니다.
    if event_type == POSITION_EVENT_NAV:
        return cash, 0.0

    raise SystemExit(f"Unknown position event_type: {event_type}")


def _state_as_of(events: list[dict[str, Any]], asof: dt.date) -> tuple[dict[str, float], float]:
    positions: dict[str, float] = {}
    cash = 0.0
    usable = [row for row in events if _event_date(row) <= asof]
    usable.sort(key=_event_sort_key)

    for row in usable:
        cash, _ = _apply_event_to_state(row, positions=positions, cash=cash)
    return positions, cash


def _performance_from_nav_snapshots(
    events: list[dict[str, Any]],
    start: dt.date | None,
    end: dt.date | None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in events:
        if row.get("event_type") != POSITION_EVENT_NAV:
            continue
        rows.append(
            {
                "Date": _event_date(row),
                "NAV": _safe_float(row.get("nav")),
                "Source": str(row.get("source", "manual")),
            }
        )

    if not rows:
        raise SystemExit("No nav_snapshot events found in position_log.jsonl")

    df = pd.DataFrame(rows).sort_values("Date")
    df = df.drop_duplicates(subset=["Date"], keep="last")

    first_date = df["Date"].min()
    last_date = df["Date"].max()
    start_date = start or first_date
    end_date = end or last_date

    if start_date > end_date:
        raise SystemExit("Invalid range: start date is after end date")

    idx = pd.date_range(start=start_date, end=end_date, freq="D")
    nav = df.set_index(pd.to_datetime(df["Date"]))["NAV"].reindex(idx).ffill().dropna()
    if nav.empty:
        raise SystemExit("No NAV points available in the requested range")

    out = pd.DataFrame(index=nav.index)
    out["Date"] = out.index.date
    out["NAV"] = nav.astype(float)
    out["Daily Return"] = out["NAV"].pct_change().fillna(0.0)
    out["Cumulative Return"] = out["NAV"] / out["NAV"].iloc[0] - 1.0
    out["Cash"] = float("nan")
    out["Market Value"] = float("nan")
    out["External Flow"] = float("nan")
    out["Method"] = "nav_snapshot"
    return out.reset_index(drop=True)


def _performance_from_transactions(
    events: list[dict[str, Any]],
    start: dt.date | None,
    end: dt.date | None,
) -> pd.DataFrame:
    tx_events = [row for row in events if row.get("event_type") in {POSITION_EVENT_TRADE, POSITION_EVENT_CASH}]
    if not tx_events:
        raise SystemExit("No trade/cash events found in position_log.jsonl")

    tx_events.sort(key=_event_sort_key)
    first_date = _event_date(tx_events[0])
    start_date = start or first_date
    end_date = end or _kst_now().date()
    if start_date > end_date:
        raise SystemExit("Invalid range: start date is after end date")

    symbols = _collect_trade_symbols(tx_events)
    prices = _download_close_prices(symbols, start_date, end_date)

    events_by_date: dict[dt.date, list[dict[str, Any]]] = defaultdict(list)
    for row in tx_events:
        event_day = _event_date(row)
        if start_date <= event_day <= end_date:
            events_by_date[event_day].append(row)

    positions: dict[str, float] = {}
    cash = 0.0
    prev_nav: float | None = None
    growth = 1.0
    rows: list[dict[str, Any]] = []

    for day in pd.date_range(start=start_date, end=end_date, freq="D"):
        day_date = day.date()
        external_flow = 0.0

        for row in sorted(events_by_date.get(day_date, []), key=_event_sort_key):
            cash, flow = _apply_event_to_state(row, positions=positions, cash=cash)
            external_flow += flow

        market_value = 0.0
        if symbols:
            day_prices = prices.loc[day] if day in prices.index else pd.Series(dtype=float)
            for symbol, qty in positions.items():
                px = _safe_float(day_prices.get(symbol), default=float("nan"))
                if math.isnan(px):
                    continue
                market_value += qty * px

        nav = cash + market_value
        if prev_nav is None or abs(prev_nav) < 1e-12:
            daily_ret = 0.0
        else:
            daily_ret = (nav - prev_nav - external_flow) / prev_nav
        growth *= 1.0 + daily_ret

        rows.append(
            {
                "Date": day_date,
                "NAV": nav,
                "Daily Return": daily_ret,
                "Cumulative Return": growth - 1.0,
                "Cash": cash,
                "Market Value": market_value,
                "External Flow": external_flow,
                "Method": "transactions",
            }
        )
        prev_nav = nav

    return pd.DataFrame(rows)


def _build_performance_df(
    events: list[dict[str, Any]],
    *,
    start: dt.date | None,
    end: dt.date | None,
    method: str,
) -> pd.DataFrame:
    if method == "nav":
        return _performance_from_nav_snapshots(events, start=start, end=end)
    if method == "transactions":
        return _performance_from_transactions(events, start=start, end=end)

    # auto: nav_snapshot이 2개 이상이면 nav 우선, 없으면 거래 기반 계산
    nav_count = sum(1 for row in events if row.get("event_type") == POSITION_EVENT_NAV)
    if nav_count >= 2:
        return _performance_from_nav_snapshots(events, start=start, end=end)
    return _performance_from_transactions(events, start=start, end=end)


def _fetch_benchmark_curves(
    tickers: list[str],
    start: dt.date,
    end: dt.date,
) -> pd.DataFrame:
    symbols = sorted({_normalize_symbol(t) for t in tickers if t.strip()})
    if not symbols:
        return pd.DataFrame()

    prices = _download_close_prices(symbols, start, end)
    if prices.empty:
        return pd.DataFrame()

    out = pd.DataFrame(index=prices.index)
    for symbol in symbols:
        series = prices[symbol].dropna()
        if series.empty:
            continue
        rebased = series / series.iloc[0] - 1.0
        out[symbol] = rebased
    return out


def _build_decision_payload(
    *,
    log_date: dt.date,
    decision_type: str,
    status: str,
    summary: str,
    detail: str,
    rationale: str,
    condition: str,
    horizon: str,
    confidence: float | None,
    tickers: list[str],
    values: list[str],
    tags: list[str],
    source: str,
    user_query: str = "",
) -> dict[str, Any]:
    now = _kst_now()
    return {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        "logged_at": now.isoformat(),
        "date": log_date.isoformat(),
        "entry_type": "decision",
        "decision_type": decision_type,
        "status": status,
        "summary": summary,
        "detail": detail,
        "rationale": rationale,
        "condition": condition,
        "horizon": horizon,
        "confidence": _clamp_confidence(confidence),
        "tickers": [_normalize_symbol(t) for t in tickers if t],
        "values": _unique_preserve_order(values),
        "tags": _unique_preserve_order(tags),
        "source": source,
        "user_query": user_query,
    }


def _handle_init(args: argparse.Namespace) -> int:
    base, position_log, decision_log = _ensure_logs(args.base_dir)
    world_db = _world_memory_db_path(args.base_dir)
    print(f"Initialized: {base}")
    print(f"- {position_log}")
    print(f"- {decision_log}")
    print(f"- {world_db} (world memory SQLite path)")
    return 0


def _handle_add_decision(args: argparse.Namespace) -> int:
    _, _, decision_log = _ensure_logs(args.base_dir)
    log_date = args.date or _kst_now().date()
    payload = _build_decision_payload(
        log_date=log_date,
        decision_type=args.decision_type,
        status=args.status,
        summary=args.summary,
        detail=args.detail or "",
        rationale=args.rationale or "",
        condition=args.condition or "",
        horizon=args.horizon or "",
        confidence=args.confidence,
        tickers=_split_csv(args.tickers),
        values=_split_csv(args.values),
        tags=_split_csv(args.tags),
        source="manual",
        user_query="",
    )
    _append_jsonl(decision_log, payload)
    print(f"Appended decision log: {decision_log}")
    print(f"event_id={payload['event_id']}")
    return 0


def _handle_log_counsel(args: argparse.Namespace) -> int:
    base, _, decision_log = _ensure_logs(args.base_dir)
    log_date = args.date or _kst_now().date()

    response_text = _read_response_text_for_autolog(args)
    query_text = _read_optional_text(args.query_text, args.query_file).strip()
    response_text = response_text.strip()

    if not response_text:
        raise SystemExit("response text is empty")

    summary = (args.summary or _infer_summary_from_text(response_text)).strip()
    decision_type = args.decision_type
    if decision_type == "auto":
        decision_type = _infer_decision_type(f"{query_text}\n{response_text}")

    extracted_text = f"{query_text}\n{response_text}"
    tickers = _split_csv(args.tickers)
    if not tickers and args.auto_extract:
        tickers = _extract_tickers_from_text(extracted_text)

    values = _split_csv(args.values)
    if not values and args.auto_extract:
        values = _infer_values(extracted_text)

    tags = _split_csv(args.tags)
    if args.auto_extract:
        tags = _unique_preserve_order(tags + _infer_tags(extracted_text))
    if args.default_tags:
        tags = _unique_preserve_order(tags + AUTO_LOG_DEFAULT_TAGS)

    detail_text = args.detail if args.detail else response_text
    if args.detail_max_chars > 0:
        detail_text = detail_text[: args.detail_max_chars]

    payload = _build_decision_payload(
        log_date=log_date,
        decision_type=decision_type,
        status=args.status,
        summary=summary,
        detail=detail_text,
        rationale=args.rationale or "",
        condition=args.condition or "",
        horizon=args.horizon or "",
        confidence=args.confidence,
        tickers=tickers,
        values=values,
        tags=tags,
        source="auto_counsel_end",
        user_query=query_text,
    )

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    _append_jsonl(decision_log, payload)
    print(f"Appended auto counsel decision log: {decision_log}")
    print(f"event_id={payload['event_id']}")

    if args.save_session:
        sessions_dir = base / "counsel_sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        session_path = sessions_dir / f"{log_date.isoformat()}_{payload['event_id'][:8]}.json"
        session_payload = {
            "logged_at": payload["logged_at"],
            "date": payload["date"],
            "query": query_text,
            "response": response_text,
            "decision_event": payload,
        }
        session_path.write_text(json.dumps(session_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Saved counsel session: {session_path}")

    return 0


def _handle_add_trade(args: argparse.Namespace) -> int:
    _, position_log, _ = _ensure_logs(args.base_dir)
    now = _kst_now()

    symbol = _normalize_symbol(args.symbol)
    if symbol == "":
        raise SystemExit("symbol is required")
    if args.qty <= 0:
        raise SystemExit("qty must be > 0")
    if args.price < 0:
        raise SystemExit("price must be >= 0")
    if args.fee < 0:
        raise SystemExit("fee must be >= 0")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        "logged_at": now.isoformat(),
        "date": args.date.isoformat(),
        "event_type": POSITION_EVENT_TRADE,
        "symbol": symbol,
        "side": args.side.upper(),
        "quantity": float(args.qty),
        "price": float(args.price),
        "fee": float(args.fee),
        "currency": args.currency.upper(),
        "memo": args.memo or "",
    }
    _append_jsonl(position_log, payload)
    print(f"Appended trade event: {position_log}")
    print(f"event_id={payload['event_id']}")
    return 0


def _default_external_for_category(category: str) -> bool:
    return category in {"deposit", "withdrawal", "adjustment"}


def _handle_add_cash(args: argparse.Namespace) -> int:
    _, position_log, _ = _ensure_logs(args.base_dir)
    now = _kst_now()

    if args.external and args.internal:
        raise SystemExit("Choose one of --external or --internal")

    external = _default_external_for_category(args.category)
    if args.external:
        external = True
    if args.internal:
        external = False

    payload: dict[str, Any] = {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        "logged_at": now.isoformat(),
        "date": args.date.isoformat(),
        "event_type": POSITION_EVENT_CASH,
        "amount": float(args.amount),
        "category": args.category,
        "external": external,
        "currency": args.currency.upper(),
        "memo": args.memo or "",
    }
    _append_jsonl(position_log, payload)
    print(f"Appended cash event: {position_log}")
    print(f"event_id={payload['event_id']}")
    return 0


def _handle_add_nav(args: argparse.Namespace) -> int:
    _, position_log, _ = _ensure_logs(args.base_dir)
    now = _kst_now()
    if args.nav <= 0:
        raise SystemExit("nav must be > 0")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        "logged_at": now.isoformat(),
        "date": args.date.isoformat(),
        "event_type": POSITION_EVENT_NAV,
        "nav": float(args.nav),
        "source": args.source,
        "memo": args.memo or "",
    }
    _append_jsonl(position_log, payload)
    print(f"Appended nav snapshot: {position_log}")
    print(f"event_id={payload['event_id']}")
    return 0


def _handle_positions(args: argparse.Namespace) -> int:
    _, position_log, _ = _ensure_logs(args.base_dir)
    events = _read_jsonl(position_log)
    asof = args.asof or _kst_now().date()

    positions, cash = _state_as_of(events, asof)
    symbols = sorted(positions.keys())
    prices = _download_close_prices(symbols, asof, asof) if symbols else pd.DataFrame()

    rows: list[dict[str, Any]] = []
    total_market = 0.0
    for symbol in symbols:
        qty = positions[symbol]
        px = float("nan")
        if symbol in prices.columns and not prices.empty:
            px = _safe_float(prices.iloc[-1].get(symbol), default=float("nan"))
        market_value = qty * px if not math.isnan(px) else float("nan")
        if not math.isnan(market_value):
            total_market += market_value

        rows.append(
            {
                "Symbol": symbol,
                "Quantity": qty,
                "Price": None if math.isnan(px) else px,
                "Market Value": None if math.isnan(market_value) else market_value,
            }
        )

    total_equity = cash + total_market
    rows.append(
        {
            "Symbol": "CASH",
            "Quantity": 1.0,
            "Price": cash,
            "Market Value": cash,
        }
    )

    for row in rows:
        mv = row.get("Market Value")
        if total_equity == 0 or mv is None:
            row["Weight %"] = None
        else:
            row["Weight %"] = 100.0 * float(mv) / total_equity

    df = pd.DataFrame(rows)
    df = df[["Symbol", "Quantity", "Price", "Market Value", "Weight %"]]

    header = (
        f"as_of={asof.isoformat()} ({DEFAULT_TZ})\n"
        f"total_equity={total_equity:.2f}\n"
        f"market_value={total_market:.2f}\n"
        f"cash={cash:.2f}\n"
    )

    if args.format == "json":
        payload = {
            "as_of": asof.isoformat(),
            "timezone": DEFAULT_TZ,
            "total_equity": total_equity,
            "market_value": total_market,
            "cash": cash,
            "rows": [{k: _json_safe(v) for k, v in row.items()} for row in df.to_dict(orient="records")],
        }
        _emit_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", args.out)
        return 0

    if args.out:
        body = ""
        if args.format == "md":
            try:
                body = df.to_markdown(index=False) + "\n"
            except Exception:
                body = df.to_string(index=False) + "\n"
        elif args.format == "csv":
            body = df.to_csv(index=False)
        else:
            body = df.to_string(index=False) + "\n"
        _emit_text(header + body, args.out)
        return 0

    sys.stdout.write(header)
    _emit_dataframe(df, args.format, out_path=None)
    return 0


def _handle_performance(args: argparse.Namespace) -> int:
    _, position_log, _ = _ensure_logs(args.base_dir)
    events = _read_jsonl(position_log)
    end = args.end or _kst_now().date()

    perf = _build_performance_df(
        events,
        start=args.start,
        end=end,
        method=args.method,
    )

    if args.format == "json":
        payload = {
            "method": args.method,
            "timezone": DEFAULT_TZ,
            "rows": [{k: _json_safe(v) for k, v in row.items()} for row in perf.to_dict(orient="records")],
        }
        _emit_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", args.out)
        return 0

    if args.format == "md":
        view = perf.copy()
        view["Date"] = view["Date"].map(lambda d: d.isoformat() if isinstance(d, dt.date) else str(d))
        _emit_dataframe(view, "md", args.out)
        return 0

    if args.format == "csv":
        view = perf.copy()
        view["Date"] = view["Date"].map(lambda d: d.isoformat() if isinstance(d, dt.date) else str(d))
        _emit_dataframe(view, "csv", args.out)
        return 0

    if args.format == "pretty":
        view = perf.copy()
        view["Date"] = view["Date"].map(lambda d: d.isoformat() if isinstance(d, dt.date) else str(d))
        _emit_dataframe(view, "pretty", args.out)
        return 0

    raise SystemExit(f"Unsupported format: {args.format}")


def _nan_if_invalid(value: float) -> float:
    if value is None:
        return float("nan")
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(out) or math.isinf(out):
        return float("nan")
    return out


def _calc_stats_row(rel: pd.Series, market_ret: pd.Series | None, *, periods_per_year: float = 365.0) -> dict[str, float]:
    rel = rel.dropna().astype(float)
    if rel.empty:
        return {
            "Cumulative Return": float("nan"),
            "CAGR": float("nan"),
            "Max Drawdown": float("nan"),
            "Volatility": float("nan"),
            "Sharpe": float("nan"),
            "Sortino": float("nan"),
            "Kelly": float("nan"),
            "Ulcer Index": float("nan"),
            "UPI": float("nan"),
            "Beta": float("nan"),
        }

    ret = rel.pct_change().dropna()
    cum_ret = rel.iloc[-1] / rel.iloc[0] - 1.0

    days = max(1, int((rel.index[-1] - rel.index[0]).days))
    years = max(days / 365.25, 1.0 / 365.25)
    cagr = math.pow(max(rel.iloc[-1] / rel.iloc[0], 1e-12), 1.0 / years) - 1.0

    run_peak = rel.cummax()
    dd_ratio = rel / run_peak - 1.0
    max_drawdown = float(dd_ratio.min())

    if ret.empty:
        vol = float("nan")
        ann_mean = float("nan")
        sharpe = float("nan")
        sortino = float("nan")
        kelly = float("nan")
    else:
        mean_bar = float(ret.mean())
        std_bar = float(ret.std(ddof=0))
        vol = std_bar * math.sqrt(periods_per_year)
        ann_mean = mean_bar * periods_per_year
        sharpe = ann_mean / vol if vol > 0 else float("nan")

        down = ret[ret < 0]
        if down.empty:
            sortino = float("nan")
        else:
            down_std = math.sqrt(float((down * down).mean())) * math.sqrt(periods_per_year)
            sortino = ann_mean / down_std if down_std > 0 else float("nan")

        var_bar = float(ret.var(ddof=0))
        kelly = mean_bar / var_bar if var_bar > 0 else float("nan")

    dd_pct = ((run_peak - rel) / run_peak) * 100.0
    ulcer = math.sqrt(float((dd_pct * dd_pct).mean())) if not dd_pct.empty else float("nan")
    upi = (cagr * 100.0) / ulcer if ulcer and not math.isnan(ulcer) and ulcer > 0 else float("nan")

    beta = float("nan")
    if market_ret is not None and not ret.empty:
        tmp = pd.concat([ret.rename("asset"), market_ret.rename("mkt")], axis=1).dropna()
        if not tmp.empty:
            var_m = float(tmp["mkt"].var(ddof=0))
            if var_m > 0:
                cov = float(((tmp["asset"] - tmp["asset"].mean()) * (tmp["mkt"] - tmp["mkt"].mean())).mean())
                beta = cov / var_m

    return {
        "Cumulative Return": _nan_if_invalid(cum_ret),
        "CAGR": _nan_if_invalid(cagr),
        "Max Drawdown": _nan_if_invalid(max_drawdown),
        "Volatility": _nan_if_invalid(vol),
        "Sharpe": _nan_if_invalid(sharpe),
        "Sortino": _nan_if_invalid(sortino),
        "Kelly": _nan_if_invalid(kelly),
        "Ulcer Index": _nan_if_invalid(ulcer),
        "UPI": _nan_if_invalid(upi),
        "Beta": _nan_if_invalid(beta),
    }


def _resolve_beta_market_return(
    curve: pd.DataFrame,
    *,
    beta_benchmark: str,
    start_date: dt.date,
    end_date: dt.date,
) -> tuple[pd.Series | None, str]:
    beta_symbol = _normalize_symbol(beta_benchmark) if beta_benchmark else "SPY"
    if beta_symbol == "":
        beta_symbol = "SPY"

    market_rel: pd.Series | None = None
    if beta_symbol in curve.columns:
        market_rel = curve[beta_symbol].astype(float) + 1.0
    else:
        fetched = _fetch_benchmark_curves([beta_symbol], start=start_date, end=end_date)
        if (not fetched.empty) and (beta_symbol in fetched.columns):
            ser = fetched[beta_symbol].copy()
            ser.index = pd.to_datetime(ser.index)
            market_rel = ser.reindex(curve.index).ffill().dropna().astype(float) + 1.0

    if market_rel is None or market_rel.empty:
        return None, beta_symbol
    return market_rel.pct_change().dropna(), beta_symbol


def _build_stats_table_df(
    curve: pd.DataFrame,
    *,
    beta_benchmark: str,
    start_date: dt.date,
    end_date: dt.date,
) -> pd.DataFrame:
    rel_curve = curve.copy().astype(float) + 1.0
    market_ret, beta_symbol = _resolve_beta_market_return(
        curve,
        beta_benchmark=beta_benchmark,
        start_date=start_date,
        end_date=end_date,
    )

    rows: list[dict[str, Any]] = []
    for col in rel_curve.columns:
        stats = _calc_stats_row(rel_curve[col], market_ret)
        row: dict[str, Any] = {"자산명": col}
        row.update(stats)
        rows.append(row)
    out = pd.DataFrame(rows)
    out = out[
        [
            "자산명",
            "Cumulative Return",
            "CAGR",
            "Max Drawdown",
            "Volatility",
            "Sharpe",
            "Sortino",
            "Kelly",
            "Ulcer Index",
            "UPI",
            "Beta",
        ]
    ]
    out.attrs["beta_benchmark"] = beta_symbol
    out.attrs["beta_available"] = market_ret is not None and (not market_ret.empty)
    return out


def _fmt_pct(value: float) -> str:
    return "—" if math.isnan(value) else f"{value * 100.0:.2f}%"


def _fmt_num(value: float, digits: int = 3) -> str:
    return "—" if math.isnan(value) else f"{value:.{digits}f}"


def _build_stats_display_df(stats_df: pd.DataFrame) -> pd.DataFrame:
    view = stats_df.copy()
    for col in ["Cumulative Return", "CAGR", "Max Drawdown", "Volatility"]:
        view[col] = view[col].map(_fmt_pct)
    for col in ["Sharpe", "Sortino", "Kelly", "Ulcer Index", "UPI", "Beta"]:
        view[col] = view[col].map(lambda x: _fmt_num(float(x), digits=3))
    return view


def _save_stats_table_png(stats_df: pd.DataFrame, out_path: Path, *, title: str) -> None:
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt

    for font_name in ["AppleGothic", "NanumGothic", "Malgun Gothic", "Noto Sans CJK KR"]:
        try:
            fm.findfont(font_name, fallback_to_default=False)
            plt.rcParams["font.family"] = font_name
            plt.rcParams["axes.unicode_minus"] = False
            break
        except Exception:
            continue

    view = _build_stats_display_df(stats_df)
    n_rows = len(view)
    n_cols = len(view.columns)

    fig_w = max(16.0, n_cols * 1.55)
    fig_h = max(2.3, 1.35 + n_rows * 0.55)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=170)
    ax.axis("off")

    table = ax.table(
        cellText=view.values,
        colLabels=view.columns,
        loc="center",
        cellLoc="center",
        colLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.33)

    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_text_props(weight="bold", color="white")
            cell.set_facecolor("#2f4f6f")
            cell.set_height(cell.get_height() * 1.15)
        else:
            cell.set_facecolor("white" if r % 2 else "#f7f9fc")
        cell.set_edgecolor("#d9dde5")
        cell.set_linewidth(0.6)
        if c == 0 and r > 0:
            cell.get_text().set_ha("left")

    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def _handle_chart(args: argparse.Namespace) -> int:
    try:
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as e:
        raise SystemExit(
            "Chart rendering requires matplotlib. "
            "설치 후 다시 실행해 주세요: "
            "uv pip install --python .venv/bin/python -r requirements.txt"
        ) from e

    base, position_log, _ = _ensure_logs(args.base_dir)
    events = _read_jsonl(position_log)
    end = args.end or _kst_now().date()

    perf = _build_performance_df(events, start=args.start, end=end, method=args.method)
    if perf.empty:
        raise SystemExit("No performance rows to chart")

    perf = perf.copy()
    perf["Date"] = pd.to_datetime(perf["Date"])
    perf = perf.sort_values("Date")
    start_date = perf["Date"].iloc[0].date()
    end_date = perf["Date"].iloc[-1].date()

    curve = pd.DataFrame(index=perf["Date"])
    curve["Portfolio"] = perf["Cumulative Return"].astype(float).values

    benchmark_tickers = _split_csv(",".join(args.benchmark)) if args.benchmark else []
    if benchmark_tickers:
        bench = _fetch_benchmark_curves(benchmark_tickers, start=start_date, end=end_date)
        if not bench.empty:
            bench = bench.copy()
            bench.index = pd.to_datetime(bench.index)
            curve = curve.join(bench, how="outer")

    curve = curve.sort_index().ffill().dropna(how="all")
    if curve.empty:
        raise SystemExit("No chart data available")

    fig, ax = plt.subplots(figsize=(args.width, args.height), dpi=args.dpi)
    lines: dict[str, Any] = {}
    for col in curve.columns:
        lw = 2.2 if col == "Portfolio" else 0.9
        (line,) = ax.plot(curve.index, curve[col] * 100.0, label=col, linewidth=lw)
        lines[col] = line

    ax.axhline(0.0, color="#999999", linewidth=1.0, linestyle="--")
    ax.set_ylabel("Cumulative Return (%)")
    ax.set_xlabel("Date")
    ax.grid(True, linestyle=":", linewidth=0.8, alpha=0.75)
    title = args.title or f"Portfolio Cumulative Return ({start_date} ~ {end_date})"
    ax.set_title(title)

    # 가독성을 위해 범례 대신 각 라인의 우측 끝에 자산명을 직접 라벨링한다.
    endpoints: list[dict[str, Any]] = []
    for col in curve.columns:
        raw_series = curve[col].astype(float).dropna()
        if raw_series.empty:
            continue
        last_cum_ret = float(raw_series.iloc[-1] * 100.0)
        if len(raw_series) >= 2:
            prev_cum_ret = float(raw_series.iloc[-2])
            prev_base = 1.0 + prev_cum_ret
            if abs(prev_base) < 1e-12:
                last_daily_ret = 0.0
            else:
                last_daily_ret = float(((1.0 + float(raw_series.iloc[-1])) / prev_base - 1.0) * 100.0)
        else:
            last_daily_ret = 0.0
        endpoints.append(
            {
                "name": col,
                "x": raw_series.index[-1],
                "y": last_cum_ret,
                "daily_return": last_daily_ret,
                "color": lines[col].get_color(),
            }
        )

    if endpoints:
        y_values = [float(e["y"]) for e in endpoints]
        y_min = min(y_values)
        y_max = max(y_values)
        y_span = max(1.0, y_max - y_min)
        min_gap = max(0.8, y_span * 0.045)

        sorted_ids = sorted(range(len(endpoints)), key=lambda i: float(endpoints[i]["y"]))
        adjusted_y: dict[int, float] = {}
        prev = -float("inf")
        for idx in sorted_ids:
            y = float(endpoints[idx]["y"])
            y_adj = max(y, prev + min_gap)
            adjusted_y[idx] = y_adj
            prev = y_adj

        desired_top = y_max + min_gap
        max_adj = max(adjusted_y.values())
        if max_adj > desired_top:
            shift = max_adj - desired_top
            for idx in adjusted_y:
                adjusted_y[idx] -= shift

        last_x = max(pd.to_datetime(e["x"]) for e in endpoints)
        span_days = max(1, int((last_x - curve.index.min()).days))
        x_pad_days = max(3, int(span_days * 0.08))
        label_x = last_x + pd.Timedelta(days=max(1, int(x_pad_days * 0.55)))

        for idx, point in enumerate(endpoints):
            y0 = float(point["y"])
            y1 = adjusted_y.get(idx, y0)
            x0 = pd.to_datetime(point["x"])
            color = str(point["color"])
            name = str(point["name"])
            daily_ret = float(point.get("daily_return", 0.0))
            ax.plot([x0, label_x], [y0, y1], color=color, linewidth=0.9, alpha=0.7, linestyle=":")
            label_txt = f"{name} {y0:.2f}% ({daily_ret:+.2f}%)"
            ax.text(
                label_x,
                y1,
                label_txt,
                color="white",
                fontsize=9,
                va="center",
                ha="left",
                clip_on=False,
                bbox=dict(facecolor=color, edgecolor=color, alpha=0.92, pad=0.2),
            )

        y_text_min = min(adjusted_y.values())
        y_text_max = max(adjusted_y.values())

        # 라벨 끝점뿐 아니라 전체 시계열의 고저점까지 포함해 축 잘림을 방지한다.
        curve_pct = curve.astype(float) * 100.0
        curve_min = float(curve_pct.min(numeric_only=True).min())
        curve_max = float(curve_pct.max(numeric_only=True).max())
        y_all_min = min(curve_min, y_text_min)
        y_all_max = max(curve_max, y_text_max)

        # 라벨 개수가 많을수록 여백을 조금 더 준다.
        pad_ratio = min(0.22, 0.1 + 0.01 * len(endpoints))
        y_pad = max(min_gap * 1.25, (y_all_max - y_all_min) * pad_ratio, 1.0)
        ax.set_ylim(y_all_min - y_pad, y_all_max + y_pad)
        ax.set_xlim(curve.index.min(), last_x + pd.Timedelta(days=x_pad_days))

    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    fig.tight_layout()

    out_path = Path(args.out) if args.out else base / f"performance_chart_{start_date}_{end_date}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)

    if args.csv_out:
        csv_out = Path(args.csv_out)
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        csv_df = curve.copy()
        csv_df.insert(0, "Date", csv_df.index.date)
        csv_df.to_csv(csv_out, index=False)
        print(f"Saved chart series csv: {csv_out}")

    if args.stats_table:
        stats_df = _build_stats_table_df(
            curve,
            beta_benchmark=args.beta_benchmark,
            start_date=start_date,
            end_date=end_date,
        )
        table_out = Path(args.stats_table_out) if args.stats_table_out else out_path.with_name(f"{out_path.stem}_stats.png")
        beta_symbol = str(stats_df.attrs.get("beta_benchmark", _normalize_symbol(args.beta_benchmark)))
        table_title = f"Performance Stats ({start_date} ~ {end_date}) | Beta vs {beta_symbol}"
        _save_stats_table_png(stats_df, table_out, title=table_title)
        print(f"Saved stats table: {table_out}")
        if not bool(stats_df.attrs.get("beta_available", False)):
            print(f"Beta benchmark data unavailable: {beta_symbol} (Beta values rendered as —)")

    print(f"Saved chart: {out_path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="포트폴리오 로그/누적수익률 관리 도구 (yfinance 기반)"
    )
    parser.add_argument("--base-dir", default=DEFAULT_BASE_DIR, help=f"로그 저장 경로 (기본: {DEFAULT_BASE_DIR})")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="portfolio 폴더와 기본 로그 파일 생성")

    p_dec = sub.add_parser("add-decision", help="투자 의사결정/가치관/심리 로그 추가")
    p_dec.add_argument("--date", type=_parse_date, default=None, help="의사결정 기준일 (YYYY-MM-DD)")
    p_dec.add_argument(
        "--decision-type",
        choices=["decision", "considering", "risk_note", "goal_update", "rule", "reflection"],
        default="decision",
        help="의사결정 로그 유형",
    )
    p_dec.add_argument(
        "--status",
        choices=["planned", "considering", "executed", "paused", "cancelled"],
        default="planned",
        help="현재 상태",
    )
    p_dec.add_argument("--summary", required=True, help="한 줄 요약")
    p_dec.add_argument("--detail", default="", help="상세 내용")
    p_dec.add_argument("--rationale", default="", help="판단 근거")
    p_dec.add_argument("--condition", default="", help="심리/컨디션 메모")
    p_dec.add_argument("--horizon", default="", help="투자 기간/타임프레임")
    p_dec.add_argument("--confidence", type=float, default=None, help="확신도 (0~1)")
    p_dec.add_argument("--tickers", default="", help="관련 티커 (예: AAPL,MSFT)")
    p_dec.add_argument("--values", default="", help="중요 가치/우선순위 (예: 안정성,현금흐름)")
    p_dec.add_argument("--tags", default="", help="태그 (콤마 구분)")

    p_log = sub.add_parser("log-counsel", help="상담 답변 종료 시 decision 로그 자동 append")
    p_log.add_argument("--date", type=_parse_date, default=None, help="상담 일자 (YYYY-MM-DD, 기본: 오늘 KST)")
    p_log.add_argument(
        "--decision-type",
        choices=["auto", "decision", "considering", "risk_note", "goal_update", "rule", "reflection"],
        default="auto",
        help="decision_type. auto면 답변 텍스트로 추론",
    )
    p_log.add_argument(
        "--status",
        choices=["planned", "considering", "executed", "paused", "cancelled"],
        default="considering",
        help="상담 종료 후 상태",
    )
    p_log.add_argument("--summary", default="", help="요약. 미지정 시 답변 첫 문장 자동 추출")
    p_log.add_argument("--query-text", default="", help="사용자 질문 원문")
    p_log.add_argument("--query-file", default=None, help="사용자 질문 파일 경로")
    p_log.add_argument("--response-text", default="", help="상담 답변 텍스트")
    p_log.add_argument("--response-file", default=None, help="상담 답변 파일 경로")
    p_log.add_argument("--detail", default="", help="detail로 저장할 텍스트(기본: 답변 전문)")
    p_log.add_argument("--rationale", default="", help="판단 근거")
    p_log.add_argument("--condition", default="", help="심리/컨디션 메모")
    p_log.add_argument("--horizon", default="", help="투자 기간/타임프레임")
    p_log.add_argument("--confidence", type=float, default=None, help="확신도 (0~1)")
    p_log.add_argument("--tickers", default="", help="관련 티커 수동 지정(콤마)")
    p_log.add_argument("--values", default="", help="가치/우선순위 수동 지정(콤마)")
    p_log.add_argument("--tags", default="", help="태그 수동 지정(콤마)")
    p_log.add_argument("--no-auto-extract", dest="auto_extract", action="store_false", help="자동 추출 비활성화")
    p_log.set_defaults(auto_extract=True)
    p_log.add_argument("--no-default-tags", dest="default_tags", action="store_false", help="기본 태그 자동 부착 비활성화")
    p_log.set_defaults(default_tags=True)
    p_log.add_argument("--no-save-session", dest="save_session", action="store_false", help="상담 질문/답변 원문 저장 비활성화")
    p_log.set_defaults(save_session=True)
    p_log.add_argument("--dry-run", action="store_true", help="실제 append 없이 payload 출력")
    p_log.add_argument("--detail-max-chars", type=int, default=4000, help="detail 최대 저장 길이")

    p_trade = sub.add_parser("add-trade", help="매수/매도 거래 로그 추가")
    p_trade.add_argument("--date", type=_parse_date, required=True, help="거래일 (YYYY-MM-DD)")
    p_trade.add_argument("--symbol", required=True, help="티커")
    p_trade.add_argument("--side", choices=["BUY", "SELL"], required=True, help="거래 방향")
    p_trade.add_argument("--qty", type=float, required=True, help="수량")
    p_trade.add_argument("--price", type=float, required=True, help="체결 단가")
    p_trade.add_argument("--fee", type=float, default=0.0, help="수수료")
    p_trade.add_argument("--currency", default="USD", help="통화")
    p_trade.add_argument("--memo", default="", help="메모")

    p_cash = sub.add_parser("add-cash", help="현금흐름 로그 추가 (입금/출금/배당/수수료)")
    p_cash.add_argument("--date", type=_parse_date, required=True, help="기준일 (YYYY-MM-DD)")
    p_cash.add_argument("--amount", type=float, required=True, help="+입금/-출금")
    p_cash.add_argument(
        "--category",
        choices=["deposit", "withdrawal", "dividend", "fee", "interest", "adjustment"],
        required=True,
        help="현금흐름 분류",
    )
    p_cash.add_argument("--currency", default="USD", help="통화")
    p_cash.add_argument("--external", action="store_true", help="외부 자금흐름으로 강제 지정")
    p_cash.add_argument("--internal", action="store_true", help="내부 성과흐름으로 강제 지정")
    p_cash.add_argument("--memo", default="", help="메모")

    p_nav = sub.add_parser("add-nav", help="백테스트형 NAV 스냅샷 추가")
    p_nav.add_argument("--date", type=_parse_date, required=True, help="기준일 (YYYY-MM-DD)")
    p_nav.add_argument("--nav", type=float, required=True, help="총자산(NAV)")
    p_nav.add_argument("--source", default="manual", help="값 출처 (manual/backtest 등)")
    p_nav.add_argument("--memo", default="", help="메모")

    p_pos = sub.add_parser("positions", help="특정 날짜 기준 포지션/현금/평가 금액 계산")
    p_pos.add_argument("--asof", type=_parse_date, default=None, help="기준일 (YYYY-MM-DD, 기본: 오늘 KST)")
    p_pos.add_argument("--format", choices=["md", "csv", "json", "pretty"], default="md", help="출력 포맷")
    p_pos.add_argument("--out", default=None, help="출력 파일 경로")

    p_perf = sub.add_parser("performance", help="누적수익률 시계열 계산")
    p_perf.add_argument("--start", type=_parse_date, default=None, help="시작일 (YYYY-MM-DD)")
    p_perf.add_argument("--end", type=_parse_date, default=None, help="종료일 (YYYY-MM-DD, 기본: 오늘 KST)")
    p_perf.add_argument(
        "--method",
        choices=["auto", "nav", "transactions"],
        default="auto",
        help="계산 방식: auto(기본), nav(NAV 스냅샷), transactions(거래 기반)",
    )
    p_perf.add_argument("--format", choices=["md", "csv", "json", "pretty"], default="md", help="출력 포맷")
    p_perf.add_argument("--out", default=None, help="출력 파일 경로")

    p_chart = sub.add_parser("chart", help="누적수익률 차트(PNG) 저장")
    p_chart.add_argument("--start", type=_parse_date, required=False, default=None, help="시작일 (YYYY-MM-DD)")
    p_chart.add_argument("--end", type=_parse_date, default=None, help="종료일 (YYYY-MM-DD, 기본: 오늘 KST)")
    p_chart.add_argument(
        "--method",
        choices=["auto", "nav", "transactions"],
        default="auto",
        help="계산 방식: auto(기본), nav, transactions",
    )
    p_chart.add_argument(
        "--benchmark",
        action="append",
        default=[],
        help="벤치마크 티커. 여러 번 지정 가능 (예: --benchmark SPY --benchmark QQQ)",
    )
    p_chart.add_argument("--out", default=None, help="PNG 출력 경로 (기본: portfolio/performance_chart_*.png)")
    p_chart.add_argument("--csv-out", default=None, help="그래프 원본 시계열 CSV 저장 경로")
    p_chart.add_argument("--beta-benchmark", default="SPY", help="Beta 계산 기준 티커 (기본: SPY, 예: ^KS11)")
    p_chart.add_argument("--stats-table-out", default=None, help="성과 지표 테이블 PNG 저장 경로 (기본: 차트파일명_stats.png)")
    p_chart.add_argument("--no-stats-table", dest="stats_table", action="store_false", help="성과 지표 테이블 PNG 생성을 비활성화")
    p_chart.set_defaults(stats_table=True)
    p_chart.add_argument("--title", default=None, help="차트 제목")
    p_chart.add_argument("--width", type=float, default=11.0, help="차트 너비(inch)")
    p_chart.add_argument("--height", type=float, default=6.0, help="차트 높이(inch)")
    p_chart.add_argument("--dpi", type=int, default=140, help="차트 DPI")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "init":
        return _handle_init(args)
    if args.cmd == "add-decision":
        return _handle_add_decision(args)
    if args.cmd == "log-counsel":
        return _handle_log_counsel(args)
    if args.cmd == "add-trade":
        return _handle_add_trade(args)
    if args.cmd == "add-cash":
        return _handle_add_cash(args)
    if args.cmd == "add-nav":
        return _handle_add_nav(args)
    if args.cmd == "positions":
        return _handle_positions(args)
    if args.cmd == "performance":
        return _handle_performance(args)
    if args.cmd == "chart":
        return _handle_chart(args)

    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
