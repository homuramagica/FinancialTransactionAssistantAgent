#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd


DEFAULT_BASE_DIR = "portfolio"
DEFAULT_LOG_FILE = "world_issue_log.jsonl"
DEFAULT_DB_FILE = "world_issue_log.sqlite3"
DEFAULT_TZ = "Asia/Seoul"

CATEGORY_CHOICES = ["stock_bond", "geopolitics", "emerging"]
REGION_CHOICES = ["US", "KR", "GLOBAL"]
IMPORTANCE_CHOICES = ["high", "medium", "low"]


def _kst_now() -> dt.datetime:
    return dt.datetime.now(tz=ZoneInfo(DEFAULT_TZ))


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date: {value} (expected YYYY-MM-DD)") from e


def _parse_datetime(value: str) -> dt.datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Invalid datetime: {value} (expected ISO 8601, e.g. 2026-02-16T08:30:00+09:00)"
        ) from e

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
    else:
        parsed = parsed.astimezone(ZoneInfo(DEFAULT_TZ))
    return parsed


def _parse_datetime_safe(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
    return parsed.astimezone(ZoneInfo(DEFAULT_TZ))


def _split_csv(text: str | None) -> list[str]:
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        token = item.strip()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _read_optional_text(text: str | None, file_path: str | None) -> str:
    if text and file_path:
        raise SystemExit("Choose one of --sources-json or --sources-file")
    if file_path:
        path = Path(file_path)
        if not path.exists():
            raise SystemExit(f"File not found: {path}")
        return path.read_text(encoding="utf-8")
    return text or ""


def _ensure_base_dir(base_dir: str) -> Path:
    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _ensure_log(base_dir: str) -> Path:
    base = _ensure_base_dir(base_dir)
    log_path = base / DEFAULT_LOG_FILE
    if not log_path.exists():
        log_path.touch()
    return log_path


def _resolve_db_path(base_dir: str, db_file: str) -> Path:
    base = _ensure_base_dir(base_dir)
    return base / db_file


def _connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS world_issue_entries (
            event_id TEXT PRIMARY KEY,
            as_of TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            category TEXT NOT NULL,
            region TEXT NOT NULL,
            importance TEXT NOT NULL,
            logged_at TEXT NOT NULL,
            title TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_entries_as_of ON world_issue_entries(as_of DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_entries_filters "
        "ON world_issue_entries(issue_date, category, region, importance)"
    )
    conn.commit()


def _ensure_db(base_dir: str, db_file: str) -> Path:
    db_path = _resolve_db_path(base_dir, db_file)
    with _connect_db(db_path) as conn:
        _init_db(conn)
    return db_path


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
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"JSONL parse error in {path}:{line_no}: {e.msg}") from e
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))
        f.write("\n")


def _emit_text(text: str, out_path: str | None) -> None:
    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        return

    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")


def _escape_md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "(no rows)\n"

    headers = [str(col) for col in df.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in df.to_dict(orient="records"):
        cells = [_escape_md_cell(row.get(col, "")) for col in headers]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _emit_dataframe(df: pd.DataFrame, fmt: str, out_path: str | None) -> None:
    if fmt == "md":
        _emit_text(_dataframe_to_markdown(df), out_path)
        return

    if fmt == "csv":
        _emit_text(df.to_csv(index=False), out_path)
        return

    if fmt == "pretty":
        _emit_text(df.to_string(index=False) + "\n", out_path)
        return

    if fmt == "json":
        _emit_text(df.to_json(orient="records", force_ascii=False, indent=2) + "\n", out_path)
        return

    raise SystemExit(f"Unsupported format: {fmt}")


def _normalize_region(value: str) -> str:
    token = value.strip().upper()
    mapping = {
        "US": "US",
        "USA": "US",
        "KR": "KR",
        "KOR": "KR",
        "KOREA": "KR",
        "GLOBAL": "GLOBAL",
        "WORLD": "GLOBAL",
    }
    normalized = mapping.get(token)
    if normalized is None:
        raise SystemExit(f"Invalid region: {value} (allowed: {', '.join(REGION_CHOICES)})")
    return normalized


def _normalize_category(value: str) -> str:
    token = value.strip().lower()
    mapping = {
        "stock_bond": "stock_bond",
        "stock": "stock_bond",
        "bond": "stock_bond",
        "stocks": "stock_bond",
        "geopolitics": "geopolitics",
        "geopolitical": "geopolitics",
        "politics": "geopolitics",
        "emerging": "emerging",
    }
    normalized = mapping.get(token)
    if normalized is None:
        raise SystemExit(f"Invalid category: {value} (allowed: {', '.join(CATEGORY_CHOICES)})")
    return normalized


def _normalize_importance(value: str) -> str:
    token = value.strip().lower()
    mapping = {
        "high": "high",
        "mid": "medium",
        "medium": "medium",
        "low": "low",
    }
    normalized = mapping.get(token)
    if normalized is None:
        raise SystemExit(f"Invalid importance: {value} (allowed: {', '.join(IMPORTANCE_CHOICES)})")
    return normalized


def _normalize_tickers(tickers: list[str]) -> list[str]:
    out: list[str] = []
    for raw in tickers:
        token = raw.strip().upper()
        if not token:
            continue
        out.append(token)
    return _unique_preserve_order(out)


def _normalize_sources_from_json(raw: str) -> list[dict[str, Any]]:
    if not raw.strip():
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"sources json parse error: {e.msg}") from e

    if not isinstance(data, list):
        raise SystemExit("sources json must be a list")

    out: list[dict[str, Any]] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"sources[{idx}] must be an object")

        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not url:
            raise SystemExit(f"sources[{idx}] requires name and url")

        source: dict[str, Any] = {
            "name": name,
            "url": url,
        }

        published_at = item.get("published_at")
        if published_at:
            source["published_at"] = _parse_datetime(str(published_at)).isoformat()

        note = str(item.get("note", "")).strip()
        if note:
            source["note"] = note

        out.append(source)
    return out


def _normalize_sources_from_shortcut(items: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(items, start=1):
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) < 2:
            raise SystemExit(
                f"Invalid --source at index {idx}. Expected '매체명|URL|게시시각(옵션)|메모(옵션)'"
            )

        name, url = parts[0], parts[1]
        if not name or not url:
            raise SystemExit(f"Invalid --source at index {idx}: name/url is required")

        source: dict[str, Any] = {
            "name": name,
            "url": url,
        }

        if len(parts) >= 3 and parts[2]:
            source["published_at"] = _parse_datetime(parts[2]).isoformat()
        if len(parts) >= 4 and parts[3]:
            source["note"] = parts[3]

        out.append(source)
    return out


def _parse_sources(args: argparse.Namespace) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    sources.extend(_normalize_sources_from_shortcut(args.source))

    raw_json = _read_optional_text(args.sources_json, args.sources_file)
    sources.extend(_normalize_sources_from_json(raw_json))

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for src in sources:
        key = (
            str(src.get("name", "")).strip(),
            str(src.get("url", "")).strip(),
            str(src.get("published_at", "")).strip(),
            str(src.get("note", "")).strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(src)
    return deduped


def _build_issue_payload(
    *,
    as_of: dt.datetime,
    category: str,
    region: str,
    importance: str,
    title: str,
    summary: str,
    why_it_matters: str,
    portfolio_link: str,
    horizon: str,
    tickers: list[str],
    tags: list[str],
    sources: list[dict[str, Any]],
    story: str,
    story_thesis: str,
    story_checkpoint: str,
) -> dict[str, Any]:
    now = _kst_now()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        "logged_at": now.isoformat(),
        "entry_type": "world_issue",
        "as_of": as_of.isoformat(),
        "date": as_of.date().isoformat(),
        "category": category,
        "region": region,
        "importance": importance,
        "horizon": horizon,
        "title": title,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "portfolio_link": portfolio_link,
        "tickers": tickers,
        "tags": tags,
        "sources": sources,
    }
    if story.strip():
        payload["story"] = story.strip()
    if story_thesis.strip():
        payload["story_thesis"] = story_thesis.strip()
    if story_checkpoint.strip():
        payload["story_checkpoint"] = story_checkpoint.strip()
    return payload


def _importance_rank(value: str) -> int:
    order = {"high": 0, "medium": 1, "low": 2}
    return order.get(value, 3)


def _issue_as_of(row: dict[str, Any]) -> dt.datetime:
    parsed = _parse_datetime_safe(row.get("as_of"))
    if parsed is not None:
        return parsed
    fallback = _parse_datetime_safe(row.get("logged_at"))
    if fallback is not None:
        return fallback
    return _kst_now()


def _issue_sort_key(row: dict[str, Any]) -> tuple[dt.datetime, int, str]:
    return (
        _issue_as_of(row),
        -_importance_rank(str(row.get("importance", ""))),
        str(row.get("event_id", "")),
    )


def _resolve_date_window(args: argparse.Namespace) -> tuple[dt.date, dt.date]:
    end_date = args.end or _kst_now().date()
    days = max(int(getattr(args, "days", 1)), 1)
    start_date = args.start or (end_date - dt.timedelta(days=days - 1))
    if start_date > end_date:
        raise SystemExit("Invalid range: --start is after --end")
    return start_date, end_date


def _resolve_filter_tokens(args: argparse.Namespace) -> tuple[str, str, str]:
    category_filter = str(getattr(args, "category", "all"))
    region_filter = str(getattr(args, "region", "all"))
    importance_filter = str(getattr(args, "importance", "all"))

    if category_filter != "all":
        category_filter = _normalize_category(category_filter)
    if region_filter != "all":
        region_filter = _normalize_region(region_filter)
    if importance_filter != "all":
        importance_filter = _normalize_importance(importance_filter)
    return category_filter, region_filter, importance_filter


def _normalize_sources_for_storage(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not url:
            continue

        source: dict[str, Any] = {"name": name, "url": url}

        published_at = _parse_datetime_safe(item.get("published_at"))
        if published_at is not None:
            source["published_at"] = published_at.isoformat()

        note = str(item.get("note", "")).strip()
        if note:
            source["note"] = note

        out.append(source)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for src in out:
        key = (
            str(src.get("name", "")).strip(),
            str(src.get("url", "")).strip(),
            str(src.get("published_at", "")).strip(),
            str(src.get("note", "")).strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(src)
    return deduped


def _normalize_payload_for_storage(raw_row: dict[str, Any]) -> dict[str, Any]:
    row = dict(raw_row)
    normalized = dict(row)

    event_id = str(normalized.get("event_id", "")).strip()
    if not event_id:
        event_id = str(uuid.uuid4())

    as_of = _issue_as_of(normalized)
    logged_at = _parse_datetime_safe(normalized.get("logged_at")) or _kst_now()

    category = _normalize_category(str(normalized.get("category", "stock_bond")))
    region = _normalize_region(str(normalized.get("region", "GLOBAL")))
    importance = _normalize_importance(str(normalized.get("importance", "medium")))

    title = str(normalized.get("title", "")).strip()
    summary = str(normalized.get("summary", "")).strip()
    if not title or not summary:
        raise ValueError("world issue payload requires title and summary")

    tickers_raw = normalized.get("tickers", [])
    if isinstance(tickers_raw, list):
        tickers = _normalize_tickers([str(item) for item in tickers_raw])
    elif isinstance(tickers_raw, str):
        tickers = _normalize_tickers(_split_csv(tickers_raw))
    else:
        tickers = []

    tags_raw = normalized.get("tags", [])
    if isinstance(tags_raw, list):
        tags = _unique_preserve_order([str(item).strip() for item in tags_raw if str(item).strip()])
    elif isinstance(tags_raw, str):
        tags = _unique_preserve_order(_split_csv(tags_raw))
    else:
        tags = []

    sources = _normalize_sources_for_storage(normalized.get("sources"))

    try:
        schema_version = int(normalized.get("schema_version", 1))
    except (TypeError, ValueError):
        schema_version = 1

    normalized["schema_version"] = schema_version
    normalized["entry_type"] = "world_issue"
    normalized["event_id"] = event_id
    normalized["as_of"] = as_of.isoformat()
    normalized["logged_at"] = logged_at.isoformat()
    normalized["date"] = as_of.date().isoformat()
    normalized["category"] = category
    normalized["region"] = region
    normalized["importance"] = importance
    normalized["title"] = title
    normalized["summary"] = summary
    normalized["tickers"] = tickers
    normalized["tags"] = tags
    normalized["sources"] = sources
    return normalized


def _upsert_sqlite_payload(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO world_issue_entries (
            event_id, as_of, issue_date, category, region, importance, logged_at, title, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            as_of=excluded.as_of,
            issue_date=excluded.issue_date,
            category=excluded.category,
            region=excluded.region,
            importance=excluded.importance,
            logged_at=excluded.logged_at,
            title=excluded.title,
            payload_json=excluded.payload_json
        """,
        (
            str(payload.get("event_id", "")),
            str(payload.get("as_of", "")),
            str(payload.get("date", "")),
            str(payload.get("category", "")),
            str(payload.get("region", "")),
            str(payload.get("importance", "")),
            str(payload.get("logged_at", "")),
            str(payload.get("title", "")),
            json.dumps(payload, ensure_ascii=False),
        ),
    )


def _count_sqlite_rows(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    with _connect_db(db_path) as conn:
        _init_db(conn)
        row = conn.execute("SELECT COUNT(*) AS cnt FROM world_issue_entries").fetchone()
        if row is None:
            return 0
        return int(row["cnt"])


def _read_filtered_rows_from_sqlite(
    *,
    db_path: Path,
    start_date: dt.date,
    end_date: dt.date,
    category_filter: str,
    region_filter: str,
    importance_filter: str,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    where = ["issue_date >= ?", "issue_date <= ?"]
    params: list[Any] = [start_date.isoformat(), end_date.isoformat()]

    if category_filter != "all":
        where.append("category = ?")
        params.append(category_filter)
    if region_filter != "all":
        where.append("region = ?")
        params.append(region_filter)
    if importance_filter != "all":
        where.append("importance = ?")
        params.append(importance_filter)

    query = (
        "SELECT payload_json FROM world_issue_entries "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY as_of DESC, logged_at DESC"
    )

    rows: list[dict[str, Any]] = []
    with _connect_db(db_path) as conn:
        _init_db(conn)
        result = conn.execute(query, params)
        for record in result:
            raw_payload = record["payload_json"]
            try:
                parsed = json.loads(str(raw_payload))
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            try:
                rows.append(_normalize_payload_for_storage(parsed))
            except ValueError:
                continue
    return rows


def _load_filtered_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], str, Path, Path, dt.date, dt.date]:
    start_date, end_date = _resolve_date_window(args)
    category_filter, region_filter, importance_filter = _resolve_filter_tokens(args)

    log_path = _ensure_log(args.base_dir)
    db_path = _resolve_db_path(args.base_dir, args.db_file)

    sqlite_rows = _read_filtered_rows_from_sqlite(
        db_path=db_path,
        start_date=start_date,
        end_date=end_date,
        category_filter=category_filter,
        region_filter=region_filter,
        importance_filter=importance_filter,
    )
    if sqlite_rows:
        return sqlite_rows, "sqlite", log_path, db_path, start_date, end_date

    json_rows = _filter_rows(_read_jsonl(log_path), args)
    return json_rows, "jsonl", log_path, db_path, start_date, end_date


def _migrate_jsonl_to_sqlite(log_path: Path, db_path: Path) -> tuple[int, int, int, int]:
    if not log_path.exists():
        return 0, 0, 0, _count_sqlite_rows(db_path)

    rows = _read_jsonl(log_path)
    total = len(rows)
    migrated = 0
    skipped = 0

    with _connect_db(db_path) as conn:
        _init_db(conn)
        for raw in rows:
            if not isinstance(raw, dict):
                skipped += 1
                continue
            try:
                payload = _normalize_payload_for_storage(raw)
            except ValueError:
                skipped += 1
                continue
            _upsert_sqlite_payload(conn, payload)
            migrated += 1
        conn.commit()

    total_after = _count_sqlite_rows(db_path)
    return total, migrated, skipped, total_after


def _filter_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    start_date, end_date = _resolve_date_window(args)
    category_filter, region_filter, importance_filter = _resolve_filter_tokens(args)

    filtered: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("entry_type", "world_issue")) != "world_issue":
            continue

        as_of = _issue_as_of(row)
        day = as_of.date()
        if day < start_date or day > end_date:
            continue

        category = _normalize_category(str(row.get("category", "stock_bond")))
        region = _normalize_region(str(row.get("region", "GLOBAL")))
        importance = _normalize_importance(str(row.get("importance", "medium")))

        if category_filter != "all" and category != category_filter:
            continue
        if region_filter != "all" and region != region_filter:
            continue
        if importance_filter != "all" and importance != importance_filter:
            continue

        normalized = dict(row)
        normalized["category"] = category
        normalized["region"] = region
        normalized["importance"] = importance
        normalized["as_of"] = as_of.isoformat()
        filtered.append(normalized)

    filtered.sort(
        key=lambda r: (
            _issue_as_of(r),
            -_importance_rank(str(r.get("importance", ""))),
            str(r.get("event_id", "")),
        ),
        reverse=True,
    )
    return filtered


def _label_region(region: str) -> str:
    return {
        "US": "미국",
        "KR": "한국",
        "GLOBAL": "글로벌",
    }.get(region, region)


def _label_category(category: str) -> str:
    return {
        "stock_bond": "주식/채권",
        "geopolitics": "정치/지정학",
        "emerging": "관심 이슈",
    }.get(category, category)


def _label_importance(importance: str) -> str:
    return {
        "high": "상",
        "medium": "중",
        "low": "하",
    }.get(importance, importance)


def _source_names(row: dict[str, Any]) -> str:
    sources = row.get("sources")
    if not isinstance(sources, list):
        return ""

    out: list[str] = []
    for item in sources:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name:
            out.append(name)
    return ", ".join(_unique_preserve_order(out))


def _format_as_of_text(row: dict[str, Any]) -> str:
    as_of = _issue_as_of(row)
    return as_of.strftime("%Y-%m-%d %H:%M KST")


def _rows_to_frame(rows: list[dict[str, Any]], *, limit: int) -> pd.DataFrame:
    view_rows: list[dict[str, Any]] = []
    for row in rows[: max(1, limit)]:
        view_rows.append(
            {
                "As Of (KST)": _format_as_of_text(row),
                "Category": _label_category(str(row.get("category", ""))),
                "Region": _label_region(str(row.get("region", ""))),
                "Importance": _label_importance(str(row.get("importance", ""))),
                "Title": str(row.get("title", "")),
                "Story": str(row.get("story", "")),
                "Summary": str(row.get("summary", "")),
                "Tickers": ", ".join([str(t) for t in row.get("tickers", []) if str(t).strip()]),
                "Tags": ", ".join([str(t) for t in row.get("tags", []) if str(t).strip()]),
                "Sources": _source_names(row),
            }
        )
    return pd.DataFrame(view_rows)


def _table_for_report(rows: list[dict[str, Any]], *, max_items: int) -> str:
    if not rows:
        return "해당 기간 이슈가 없습니다.\n"

    view_rows: list[dict[str, Any]] = []
    for row in rows[: max_items]:
        view_rows.append(
            {
                "시각(KST)": _format_as_of_text(row),
                "중요도": _label_importance(str(row.get("importance", ""))),
                "이슈": str(row.get("title", "")),
                "요약": str(row.get("summary", "")),
                "포트폴리오 반영": str(row.get("portfolio_link", "")),
                "출처": _source_names(row),
            }
        )

    df = pd.DataFrame(view_rows)
    return _dataframe_to_markdown(df)


def _humanize_story_tag(tag: str) -> str:
    return tag.strip().replace("_", " ").replace("-", " ")


def _story_candidates(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    story = str(row.get("story", "")).strip()
    if story:
        return [("story", story, story)]

    tags = [str(t).strip() for t in row.get("tags", []) if str(t).strip()]
    out: list[tuple[str, str, str]] = []
    for tag in tags[:2]:
        normalized = tag.lower()
        out.append(("tag", normalized, f"{_humanize_story_tag(tag)} 흐름"))
    return out


def _build_story_lens_rows(
    rows: list[dict[str, Any]],
    *,
    end_date: dt.date,
    recent_days: int,
    max_items: int,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    days = max(1, recent_days)
    recent_start = end_date - dt.timedelta(days=days - 1)
    prev_end = recent_start - dt.timedelta(days=1)
    prev_start = prev_end - dt.timedelta(days=days - 1)

    buckets: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        as_of = _issue_as_of(row)
        day = as_of.date()
        title = str(row.get("title", "")).strip()
        checkpoint = str(row.get("story_checkpoint", "")).strip()
        candidates = _story_candidates(row)
        if not candidates:
            continue

        for source_kind, key, label in candidates:
            bucket_key = (source_kind, key)
            bucket = buckets.get(bucket_key)
            if bucket is None:
                bucket = {
                    "kind": source_kind,
                    "label": label,
                    "count": 0,
                    "high": 0,
                    "recent": 0,
                    "prev": 0,
                    "regions": set(),
                    "categories": set(),
                    "titles": [],
                    "checkpoints": [],
                    "latest_as_of": as_of,
                }
                buckets[bucket_key] = bucket

            bucket["count"] += 1
            if str(row.get("importance", "")) == "high":
                bucket["high"] += 1

            bucket["regions"].add(str(row.get("region", "")))
            bucket["categories"].add(str(row.get("category", "")))

            if recent_start <= day <= end_date:
                bucket["recent"] += 1
            elif prev_start <= day <= prev_end:
                bucket["prev"] += 1

            if title and title not in bucket["titles"] and len(bucket["titles"]) < 2:
                bucket["titles"].append(title)
            if checkpoint and checkpoint not in bucket["checkpoints"] and len(bucket["checkpoints"]) < 1:
                bucket["checkpoints"].append(checkpoint)
            if as_of > bucket["latest_as_of"]:
                bucket["latest_as_of"] = as_of

    story_rows: list[dict[str, Any]] = []
    for bucket in buckets.values():
        momentum = int(bucket["recent"]) - int(bucket["prev"])
        spread = len(bucket["regions"]) + len(bucket["categories"])
        score = (
            float(bucket["count"])
            + float(bucket["high"]) * 1.5
            + float(spread) * 0.7
            + max(0, momentum) * 1.2
            + (1.0 if bucket["kind"] == "story" else 0.0)
        )
        trend = "확산" if momentum > 0 else ("둔화" if momentum < 0 else "유지")
        evidence = " / ".join(bucket["titles"]) if bucket["titles"] else "-"
        checkpoint = bucket["checkpoints"][0] if bucket["checkpoints"] else "-"
        story_rows.append(
            {
                "_score": score,
                "_latest_as_of": bucket["latest_as_of"],
                "스토리": bucket["label"],
                "강도": f"{bucket['count']}건 (high {bucket['high']})",
                "최근 변화": f"{trend} ({bucket['recent']} vs {bucket['prev']})",
                "확산": f"지역 {len(bucket['regions'])} · 분류 {len(bucket['categories'])}",
                "근거(최근)": evidence,
                "체크포인트": checkpoint,
            }
        )

    story_rows.sort(key=lambda r: (float(r["_score"]), r["_latest_as_of"]), reverse=True)
    out: list[dict[str, Any]] = []
    for row in story_rows[: max(1, max_items)]:
        normalized = dict(row)
        normalized.pop("_score", None)
        normalized.pop("_latest_as_of", None)
        out.append(normalized)
    return out


def _story_table_for_report(
    rows: list[dict[str, Any]],
    *,
    end_date: dt.date,
    max_items: int,
    recent_days: int,
) -> str:
    story_rows = _build_story_lens_rows(rows, end_date=end_date, recent_days=recent_days, max_items=max_items)
    if not story_rows:
        return "스토리 후보를 만들 데이터가 부족합니다.\n"
    return _dataframe_to_markdown(pd.DataFrame(story_rows))


def _count_by_importance(rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    high = 0
    medium = 0
    low = 0
    for row in rows:
        imp = str(row.get("importance", ""))
        if imp == "high":
            high += 1
        elif imp == "medium":
            medium += 1
        else:
            low += 1
    return high, medium, low


def _build_counsel_hooks(rows: list[dict[str, Any]]) -> list[str]:
    hooks: list[str] = []

    if any(str(r.get("category", "")) == "stock_bond" and str(r.get("region", "")) == "US" for r in rows):
        hooks.append("미국 비중이 높다면 성장주 집중도를 점검하고, 듀레이션/크레딧 민감도를 함께 확인한다.")

    if any(str(r.get("category", "")) == "stock_bond" and str(r.get("region", "")) == "KR" for r in rows):
        hooks.append("한국 자산은 원화 민감도와 대형주/중소형주 쏠림을 분리해 관리한다.")

    if any(str(r.get("category", "")) == "geopolitics" for r in rows):
        hooks.append("지정학 이슈가 이어지면 에너지/방어 자산의 완충 역할과 현금 비중 하한을 재점검한다.")

    if any(str(r.get("category", "")) == "emerging" for r in rows):
        hooks.append("비지배적 이슈는 즉시 비중 확대보다 관찰 목록에 두고 트리거 충족 시 단계적으로 반영한다.")

    if not hooks:
        hooks.append("이번 기간에는 구조적 리스크 변화가 제한적이므로 기존 리밸런싱 규칙을 유지한다.")

    return hooks[:5]


def _handle_init(args: argparse.Namespace) -> int:
    log_path = _ensure_log(args.base_dir)
    db_path = _ensure_db(args.base_dir, args.db_file)
    print(f"Initialized JSONL mirror: {log_path}")
    print(f"Initialized SQLite store: {db_path}")
    return 0


def _handle_add(args: argparse.Namespace) -> int:
    log_path = _ensure_log(args.base_dir)
    db_path = _ensure_db(args.base_dir, args.db_file)
    sources = _parse_sources(args)
    if not sources:
        raise SystemExit("At least one source is required. Use --source or --sources-json/--sources-file")

    as_of = args.as_of or _kst_now()
    payload = _build_issue_payload(
        as_of=as_of,
        category=_normalize_category(args.category),
        region=_normalize_region(args.region),
        importance=_normalize_importance(args.importance),
        title=args.title.strip(),
        summary=args.summary.strip(),
        why_it_matters=(args.why_it_matters or "").strip(),
        portfolio_link=(args.portfolio_link or "").strip(),
        horizon=(args.horizon or "").strip(),
        tickers=_normalize_tickers(_split_csv(args.tickers)),
        tags=_unique_preserve_order(_split_csv(args.tags)),
        sources=sources,
        story=(args.story or "").strip(),
        story_thesis=(args.story_thesis or "").strip(),
        story_checkpoint=(args.story_checkpoint or "").strip(),
    )

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    normalized_payload = _normalize_payload_for_storage(payload)
    with _connect_db(db_path) as conn:
        _init_db(conn)
        _upsert_sqlite_payload(conn, normalized_payload)
        conn.commit()

    if not args.no_jsonl_mirror:
        _append_jsonl(log_path, normalized_payload)
        print(f"Appended JSONL mirror: {log_path}")

    print(f"Upserted SQLite world issue: {db_path}")
    print(f"event_id={normalized_payload['event_id']}")
    return 0


def _handle_list(args: argparse.Namespace) -> int:
    filtered, backend, log_path, db_path, _, _ = _load_filtered_rows(args)

    if args.format == "json":
        payload = {
            "timezone": DEFAULT_TZ,
            "backend": backend,
            "log_path": str(log_path),
            "db_path": str(db_path),
            "count": len(filtered),
            "rows": filtered[: max(1, args.limit)],
        }
        _emit_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", args.out)
        return 0

    df = _rows_to_frame(filtered, limit=args.limit)
    _emit_dataframe(df, args.format, args.out)
    return 0


def _pick_non_dominant_rows(rows: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
    emerging_rows = [r for r in rows if str(r.get("category", "")) == "emerging"]
    if emerging_rows:
        return emerging_rows[:max_items]

    low_priority = [r for r in rows if str(r.get("importance", "")) == "low"]
    return low_priority[:max_items]


def _build_report_text(
    rows: list[dict[str, Any]],
    *,
    start_date: dt.date,
    end_date: dt.date,
    max_items: int,
    log_path: Path,
    title: str | None,
) -> str:
    now = _kst_now()

    stock_rows = [r for r in rows if str(r.get("category", "")) == "stock_bond"]
    us_rows = [r for r in stock_rows if str(r.get("region", "")) == "US"]
    kr_rows = [r for r in stock_rows if str(r.get("region", "")) == "KR"]
    gl_rows = [r for r in stock_rows if str(r.get("region", "")) == "GLOBAL"]

    geo_rows = [r for r in rows if str(r.get("category", "")) == "geopolitics"]
    non_dominant_rows = _pick_non_dominant_rows(rows, max_items=max_items)

    hooks = _build_counsel_hooks(rows)
    high, medium, low = _count_by_importance(rows)
    latest = _format_as_of_text(rows[0]) if rows else "-"

    lines: list[str] = []
    lines.append(f"# {title or '시장 동향 보고서'}")
    lines.append("")
    lines.append("## 메타")
    lines.append(f"- 작성 시각(KST): {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- 데이터 범위(KST): {start_date.isoformat()} ~ {end_date.isoformat()}")
    lines.append(f"- 최신 로그 시각(KST): {latest}")
    lines.append(f"- 원본 로그: `{log_path}`")
    lines.append("")

    lines.append("## 0) 시장을 주도하는 스토리 (Narrative Lens)")
    lines.append(
        _story_table_for_report(
            rows,
            end_date=end_date,
            max_items=min(5, max_items),
            recent_days=7,
        ).rstrip()
    )
    lines.append("")

    lines.append("## 1) 주식/채권시장의 현재 주요 이슈")
    lines.append("### 미국")
    lines.append(_table_for_report(us_rows, max_items=max_items).rstrip())
    lines.append("")
    lines.append("### 한국")
    lines.append(_table_for_report(kr_rows, max_items=max_items).rstrip())
    lines.append("")
    lines.append("### 글로벌")
    lines.append(_table_for_report(gl_rows, max_items=max_items).rstrip())
    lines.append("")

    lines.append("## 2) 투자에 영향을 미치는 글로벌 정치 이슈")
    lines.append(_table_for_report(geo_rows, max_items=max_items).rstrip())
    lines.append("")

    lines.append("## 3) 비지배적이지만 관심 둘 만한 이슈")
    lines.append(_table_for_report(non_dominant_rows, max_items=max_items).rstrip())
    lines.append("")

    lines.append("## 4) 포트폴리오 상담 반영 체크포인트")
    for idx, hook in enumerate(hooks, start=1):
        lines.append(f"{idx}. {hook}")
    lines.append("")

    lines.append("## 결론")
    lines.append(f"이번 구간 로그는 중요도 상/중/하 기준으로 각각 {high}/{medium}/{low}건이다.")
    lines.append("핵심 이슈는 단기 속보보다 중기 지속성 여부를 우선 확인하며, 지역별 전이를 함께 본다.")
    lines.append("포트폴리오 상담 시에는 주식/채권 신호와 지정학 신호를 분리해 비중 조정 속도를 결정한다.")
    lines.append("비지배적 이슈는 즉시 베팅보다 감시 목록으로 관리하고, 트리거 발생 시 단계적으로 반영한다.")
    lines.append("")

    return "\n".join(lines)


def _handle_report(args: argparse.Namespace) -> int:
    filtered, backend, log_path, db_path, start_date, end_date = _load_filtered_rows(args)
    source_path = db_path if backend == "sqlite" else log_path

    report_text = _build_report_text(
        filtered,
        start_date=start_date,
        end_date=end_date,
        max_items=max(1, args.max_items),
        log_path=source_path,
        title=args.title,
    )
    _emit_text(report_text + "\n", args.out)
    return 0


def _handle_migrate(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    log_path = Path(args.from_jsonl).expanduser() if args.from_jsonl else _ensure_log(args.base_dir)

    total, migrated, skipped, total_after = _migrate_jsonl_to_sqlite(log_path, db_path)
    print(f"Migration source JSONL: {log_path}")
    print(f"Migration target SQLite: {db_path}")
    print(f"processed={total} migrated={migrated} skipped={skipped} total_rows_in_sqlite={total_after}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="외부 세계 이슈 메모리 로그 도구")
    parser.add_argument("--base-dir", default=DEFAULT_BASE_DIR, help=f"로그 저장 경로 (기본: {DEFAULT_BASE_DIR})")
    parser.add_argument("--db-file", default=DEFAULT_DB_FILE, help=f"SQLite 파일명 (기본: {DEFAULT_DB_FILE})")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="외부 세계 이슈 로그 파일(JSONL+SQLite) 초기화")

    p_add = sub.add_parser("add", help="외부 세계 이슈 1건 기록")
    p_add.add_argument("--as-of", type=_parse_datetime, default=None, help="이슈 기준 시각 (ISO 8601, 기본: 현재 KST)")
    p_add.add_argument("--category", choices=CATEGORY_CHOICES, required=True, help="이슈 분류")
    p_add.add_argument("--region", choices=REGION_CHOICES, required=True, help="지역 분류")
    p_add.add_argument("--importance", choices=IMPORTANCE_CHOICES, default="medium", help="중요도")
    p_add.add_argument("--title", required=True, help="이슈 제목")
    p_add.add_argument("--summary", required=True, help="이슈 요약")
    p_add.add_argument("--why-it-matters", default="", help="왜 중요한지")
    p_add.add_argument("--portfolio-link", default="", help="포트폴리오 상담 반영 포인트")
    p_add.add_argument("--horizon", default="1~3개월", help="영향 기간")
    p_add.add_argument("--tickers", default="", help="관련 티커 (콤마 구분)")
    p_add.add_argument("--tags", default="", help="태그 (콤마 구분)")
    p_add.add_argument("--story", default="", help="시장 스토리 라벨 (예: 디스인플레이션+성장 둔화)")
    p_add.add_argument("--story-thesis", default="", help="스토리 핵심 테제 1문장")
    p_add.add_argument("--story-checkpoint", default="", help="스토리 체크포인트(무효화/확인 조건)")
    p_add.add_argument(
        "--source",
        action="append",
        default=[],
        help="출처 단축 입력: '매체명|URL|게시시각(옵션)|메모(옵션)'",
    )
    p_add.add_argument("--sources-json", default="", help="출처 JSON 문자열(배열)")
    p_add.add_argument("--sources-file", default=None, help="출처 JSON 파일 경로")
    p_add.add_argument(
        "--no-jsonl-mirror",
        action="store_true",
        help="JSONL 미러 파일 append를 생략하고 SQLite만 기록",
    )
    p_add.add_argument("--dry-run", action="store_true", help="저장 없이 payload 확인")

    p_list = sub.add_parser("list", help="이슈 로그 조회")
    p_list.add_argument("--start", type=_parse_date, default=None, help="시작일 (YYYY-MM-DD)")
    p_list.add_argument("--end", type=_parse_date, default=None, help="종료일 (YYYY-MM-DD, 기본: 오늘 KST)")
    p_list.add_argument("--days", type=int, default=30, help="start 미지정 시 최근 조회 기간(일)")
    p_list.add_argument("--category", choices=["all"] + CATEGORY_CHOICES, default="all", help="카테고리 필터")
    p_list.add_argument("--region", choices=["all"] + REGION_CHOICES, default="all", help="지역 필터")
    p_list.add_argument("--importance", choices=["all"] + IMPORTANCE_CHOICES, default="all", help="중요도 필터")
    p_list.add_argument("--limit", type=int, default=50, help="표시 건수")
    p_list.add_argument("--format", choices=["md", "csv", "json", "pretty"], default="md", help="출력 포맷")
    p_list.add_argument("--out", default=None, help="출력 파일 경로")

    p_report = sub.add_parser("report", help="시장 동향 보고서 생성")
    p_report.add_argument("--start", type=_parse_date, default=None, help="시작일 (YYYY-MM-DD)")
    p_report.add_argument("--end", type=_parse_date, default=None, help="종료일 (YYYY-MM-DD, 기본: 오늘 KST)")
    p_report.add_argument("--days", type=int, default=14, help="start 미지정 시 최근 조회 기간(일)")
    p_report.add_argument("--max-items", type=int, default=6, help="섹션별 최대 이슈 건수")
    p_report.add_argument("--title", default=None, help="보고서 제목")
    p_report.add_argument("--out", default=None, help="출력 파일 경로")

    p_migrate = sub.add_parser("migrate", help="기존 JSONL 로그를 SQLite로 이관")
    p_migrate.add_argument("--from-jsonl", default=None, help="마이그레이션할 JSONL 경로 (기본: base-dir/world_issue_log.jsonl)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "init":
        return _handle_init(args)
    if args.cmd == "add":
        return _handle_add(args)
    if args.cmd == "list":
        return _handle_list(args)
    if args.cmd == "report":
        return _handle_report(args)
    if args.cmd == "migrate":
        return _handle_migrate(args)

    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
