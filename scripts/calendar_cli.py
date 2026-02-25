#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


DEFAULT_TZ = "Asia/Seoul"


@dataclass(frozen=True)
class CalendarQuery:
    start: dt.date | None
    end: dt.date | None
    limit: int
    offset: int
    tz: str
    duration_minutes: int


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date: {value} (expected YYYY-MM-DD)") from e


def _resolve_dates(start: dt.date | None, end: dt.date | None, days: int | None) -> tuple[dt.date | None, dt.date | None]:
    if start is None and (end is not None or days is not None):
        raise SystemExit("Error: --end/--days requires --start")
    if start is None:
        return None, None
    if end is not None and days is not None:
        raise SystemExit("Error: choose one of --end or --days")
    if end is not None:
        return start, end
    if days is not None:
        return start, start + dt.timedelta(days=days)
    return start, start + dt.timedelta(days=7)


def _to_tz(value: Any, tz: ZoneInfo) -> Any:
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            return value.tz_localize("UTC").tz_convert(tz)
        return value.tz_convert(tz)
    return value


def _df_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "(no results)"
    try:
        return df.to_markdown(index=True)
    except Exception:
        return df.to_string()


def _ics_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _dt_to_ics_utc(ts: pd.Timestamp) -> str:
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").strftime("%Y%m%dT%H%M%SZ")


def _dt_to_ics_kst(ts: pd.Timestamp) -> str:
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(DEFAULT_TZ).strftime("%Y%m%dT%H%M%S")


def _vtimezone_asia_seoul() -> list[str]:
    return [
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Seoul",
        "BEGIN:STANDARD",
        "TZOFFSETFROM:+0900",
        "TZOFFSETTO:+0900",
        "TZNAME:KST",
        "DTSTART:19700101T000000",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]


def _events_to_ics(events: Iterable[dict[str, Any]], duration_minutes: int) -> str:
    now_kst = pd.Timestamp.now(tz=DEFAULT_TZ)
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//finance-assistant//yfinance-calendars//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    lines.extend(_vtimezone_asia_seoul())
    for event in events:
        start: pd.Timestamp | None = event.get("start")
        if start is None or pd.isna(start):
            continue
        end = start + pd.Timedelta(minutes=duration_minutes)
        summary = str(event.get("summary") or "Event")
        description = str(event.get("description") or "")
        uid = str(event.get("uid") or f"{summary}-{start.isoformat()}").replace(" ", "-")

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{_ics_escape(uid)}",
                f"DTSTAMP:{_dt_to_ics_kst(now_kst)}",
                f"DTSTART;TZID=Asia/Seoul:{_dt_to_ics_kst(start)}",
                f"DTEND;TZID=Asia/Seoul:{_dt_to_ics_kst(end)}",
                f"SUMMARY:{_ics_escape(summary)}",
                f"DESCRIPTION:{_ics_escape(description)}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _print_or_write(text: str, out_path: str | None) -> None:
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        return
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def _earnings(cal: yf.Calendars, query: CalendarQuery, market_cap: float | None, filter_most_active: bool) -> pd.DataFrame:
    df = cal.get_earnings_calendar(
        market_cap=market_cap,
        filter_most_active=filter_most_active,
        start=query.start,
        end=query.end,
        limit=query.limit,
        offset=query.offset,
        force=True,
    )
    if df.empty:
        return df

    tz = ZoneInfo(query.tz)
    df = df.copy()
    if "Event Start Date" in df.columns:
        df["Event Start Date"] = df["Event Start Date"].map(lambda v: _to_tz(v, tz))
        df = df.sort_values("Event Start Date")

    keep = [c for c in ["Company", "Event Start Date", "Timing", "EPS Estimate", "Reported EPS", "Surprise(%)", "Marketcap"] if c in df.columns]
    return df[keep]


def _economic(cal: yf.Calendars, query: CalendarQuery) -> pd.DataFrame:
    df = cal.get_economic_events_calendar(
        start=query.start,
        end=query.end,
        limit=query.limit,
        offset=query.offset,
        force=True,
    )
    if df.empty:
        return df

    tz = ZoneInfo(query.tz)
    df = df.copy()
    if "Event Time" in df.columns:
        df["Event Time"] = df["Event Time"].map(lambda v: _to_tz(v, tz))
        df = df.sort_values("Event Time")
    return df


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        if value.tzinfo is None:
            value = value.tz_localize("UTC")
        return value.tz_convert(DEFAULT_TZ).isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _df_records_for_json(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{k: _json_safe(v) for k, v in row.items()} for row in df.reset_index().to_dict(orient="records")]


def _to_events_for_ics(kind: str, df: pd.DataFrame) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if df.empty:
        return events

    if kind == "earnings":
        for symbol, row in df.reset_index().iterrows():
            symbol_value = row.get("Symbol") if "Symbol" in row else row.get("index")
            start = row.get("Event Start Date")
            company = row.get("Company")
            timing = row.get("Timing")
            eps_est = row.get("EPS Estimate")
            summary = f"Earnings: {symbol_value}"
            description = f"Company: {company}\nTiming: {timing}\nEPS Est: {eps_est}"
            events.append(
                {
                    "uid": f"earnings-{symbol_value}-{start}",
                    "start": start,
                    "summary": summary,
                    "description": description,
                }
            )
        return events

    if kind == "economic":
        for event_name, row in df.iterrows():
            start = row.get("Event Time")
            region = row.get("Region")
            period_for = row.get("For")
            expected = row.get("Expected")
            last = row.get("Last")
            summary = f"Econ ({region}): {event_name}"
            description = f"For: {period_for}\nExpected: {expected}\nLast: {last}"
            events.append(
                {
                    "uid": f"econ-{region}-{event_name}-{start}",
                    "start": start,
                    "summary": summary,
                    "description": description,
                }
            )
        return events

    raise SystemExit(f"Unknown kind: {kind}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="yfinance 기반 어닝/경제 이벤트 캘린더 조회 도구")

    output = argparse.ArgumentParser(add_help=False)
    output.add_argument("--format", choices=["md", "csv", "json", "ics", "pretty"], default="md", help="출력 포맷")
    output.add_argument("--out", default=None, help="출력 파일 경로(미지정 시 stdout)")
    output.add_argument("--duration-minutes", type=int, default=60, help="ICS 이벤트 길이(분)")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--start", type=_parse_date, default=None, help="시작일 (YYYY-MM-DD)")
    common.add_argument("--end", type=_parse_date, default=None, help="종료일 (YYYY-MM-DD)")
    common.add_argument("--days", type=int, default=None, help="start 기준 기간(일), end 대신 사용")
    common.add_argument("--limit", type=int, default=50, help="조회 개수 상한")
    common.add_argument("--offset", type=int, default=0, help="페이지네이션 오프셋")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_e = sub.add_parser("earnings", parents=[common, output], help="어닝 캘린더")
    p_e.add_argument("--market-cap", type=float, default=None, help="시총 컷오프(USD)")
    p_e.add_argument("--no-filter-most-active", action="store_true", help="most active 필터 비활성화")

    sub.add_parser("economic", parents=[common, output], help="경제 이벤트 캘린더")

    args = parser.parse_args(argv)
    start, end = _resolve_dates(args.start, args.end, args.days)
    query = CalendarQuery(
        start=start,
        end=end,
        limit=args.limit,
        offset=args.offset,
        tz=DEFAULT_TZ,
        duration_minutes=args.duration_minutes,
    )

    cal = yf.Calendars(start=query.start, end=query.end)

    if args.cmd == "earnings":
        df = _earnings(cal, query, market_cap=args.market_cap, filter_most_active=not args.no_filter_most_active)
        kind = "earnings"
    elif args.cmd == "economic":
        df = _economic(cal, query)
        kind = "economic"
    else:
        raise SystemExit(f"Unknown command: {args.cmd}")

    if args.format == "pretty":
        _print_or_write(df.to_string(), args.out)
        return 0

    if args.format == "md":
        _print_or_write(_df_to_markdown(df), args.out)
        return 0

    if args.format == "csv":
        _print_or_write(df.to_csv(index=True), args.out)
        return 0

    if args.format == "json":
        out: dict[str, Any] = {
            "kind": kind,
            "start": str(query.start) if query.start else None,
            "end": str(query.end) if query.end else None,
            "tz": DEFAULT_TZ,
            "rows": _df_records_for_json(df),
        }
        _print_or_write(json.dumps(out, ensure_ascii=False, indent=2) + "\n", args.out)
        return 0

    if args.format == "ics":
        events = _to_events_for_ics(kind, df)
        _print_or_write(_events_to_ics(events, duration_minutes=query.duration_minutes), args.out)
        return 0

    raise SystemExit(f"Unknown format: {args.format}")


if __name__ == "__main__":
    raise SystemExit(main())
