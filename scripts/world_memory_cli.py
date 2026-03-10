#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd


DEFAULT_BASE_DIR = "portfolio"
DEFAULT_DB_FILE = "world_issue_log.sqlite3"
DEFAULT_TZ = "Asia/Seoul"

CATEGORY_CHOICES = ["stock_bond", "geopolitics", "emerging"]
REGION_CHOICES = ["US", "KR", "GLOBAL"]
IMPORTANCE_CHOICES = ["high", "medium", "low"]
ENTRY_MODE_CHOICES = ["issue", "brief"]
STATE_STATUS_CHOICES = ["active", "watch", "resolved", "overridden"]
STATE_BIAS_CHOICES = ["bullish", "bearish", "neutral", "mixed"]
SUBJECT_TYPE_CHOICES = [
    "person",
    "politician",
    "business_leader",
    "company",
    "institution",
    "industry",
    "market_actor",
    "other",
]
TAXONOMY_TYPE_CHOICES = [
    "category",
    "region",
    "importance",
    "entry_mode",
    "story",
    "tag",
    "ticker",
    "subject",
    "subject_type",
    "industry",
    "event_kind",
    "state_key",
    "net_effect",
]
SYSTEM_TAXONOMY_VALUES: dict[str, list[str]] = {
    "category": CATEGORY_CHOICES,
    "region": REGION_CHOICES,
    "importance": IMPORTANCE_CHOICES,
    "entry_mode": ENTRY_MODE_CHOICES,
    "subject_type": SUBJECT_TYPE_CHOICES,
}


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


def _slug_token(value: str) -> str:
    token = value.strip().lower()
    token = re.sub(r"[^\w가-힣]+", "_", token)
    return re.sub(r"_+", "_", token).strip("_")


def _normalize_state_key(value: str) -> str:
    token = _slug_token(value)
    if not token:
        raise SystemExit("state key is empty after normalization")
    return token


def _normalize_entry_mode(value: str) -> str:
    token = value.strip().lower()
    mapping = {
        "issue": "issue",
        "issues": "issue",
        "brief": "brief",
        "briefs": "brief",
        "signal": "brief",
        "signals": "brief",
    }
    normalized = mapping.get(token)
    if normalized is None:
        raise SystemExit(f"Invalid entry mode: {value} (allowed: {', '.join(ENTRY_MODE_CHOICES)})")
    return normalized


def _normalize_subject_type(value: str) -> str:
    token = value.strip().lower()
    mapping = {
        "person": "person",
        "people": "person",
        "human": "person",
        "politician": "politician",
        "political": "politician",
        "political_leader": "politician",
        "business": "business_leader",
        "business_leader": "business_leader",
        "businessperson": "business_leader",
        "businessman": "business_leader",
        "businesswoman": "business_leader",
        "executive": "business_leader",
        "ceo": "business_leader",
        "founder": "business_leader",
        "company": "company",
        "corp": "company",
        "corporation": "company",
        "firm": "company",
        "institution": "institution",
        "agency": "institution",
        "government": "institution",
        "regulator": "institution",
        "central_bank": "institution",
        "industry": "industry",
        "sector": "industry",
        "market_actor": "market_actor",
        "investor": "market_actor",
        "fund": "market_actor",
        "bank": "market_actor",
        "other": "other",
    }
    normalized = mapping.get(token)
    if normalized is None:
        raise SystemExit(f"Invalid subject type: {value} (allowed: {', '.join(SUBJECT_TYPE_CHOICES)})")
    return normalized


def _normalize_event_kind(value: str) -> str:
    token = _slug_token(value)
    return token


def _normalize_dedupe_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if not token:
            return default
        if token in {"1", "true", "yes", "y", "on"}:
            return True
        if token in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _parse_subject_item(raw: str) -> dict[str, str]:
    parts = [part.strip() for part in raw.split("|", 1)]
    name = parts[0]
    subject_type = parts[1] if len(parts) > 1 else "other"
    if not name:
        raise SystemExit("subject name is required")
    return {
        "name": name,
        "type": _normalize_subject_type(subject_type or "other"),
    }


def _normalize_subjects_for_storage(value: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = _split_csv(value)
    else:
        raw_items = []

    for raw in raw_items:
        if isinstance(raw, dict):
            name = str(raw.get("name", "")).strip()
            subject_type = str(raw.get("type", "")).strip() or "other"
            if not name:
                continue
            items.append(
                {
                    "name": name,
                    "type": _normalize_subject_type(subject_type),
                }
            )
            continue
        text = str(raw).strip()
        if not text:
            continue
        items.append(_parse_subject_item(text))

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        key = (
            str(item.get("name", "")).strip().casefold(),
            str(item.get("type", "")).strip().lower(),
        )
        if not key[0]:
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _normalize_industries_for_storage(value: Any) -> list[str]:
    if isinstance(value, list):
        return _unique_preserve_order([str(item).strip() for item in value if str(item).strip()])
    if isinstance(value, str):
        return _unique_preserve_order(_split_csv(value))
    return []


def _auto_dedupe_key(payload: dict[str, Any]) -> str:
    entry_mode = _normalize_entry_mode(str(payload.get("entry_mode", "issue")))
    if entry_mode != "brief":
        return ""

    parts: list[str] = [entry_mode, str(payload.get("date", "")).strip()]
    event_kind = str(payload.get("event_kind", "")).strip()
    if event_kind:
        parts.append(event_kind)

    subjects = [
        _slug_token(str(item.get("name", "")))
        for item in payload.get("subjects", [])
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    if subjects:
        parts.append("-".join(subjects[:3]))

    industries = [_slug_token(str(item)) for item in payload.get("industries", []) if str(item).strip()]
    if industries:
        parts.append("-".join(industries[:2]))

    title = _slug_token(str(payload.get("title", "")))
    if title:
        parts.append(title[:80])

    material = "__".join([part for part in parts if part])
    if not material:
        return ""
    if len(material) <= 180:
        return material
    digest = hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]
    return f"{material[:160]}__{digest}"


def _normalize_state_status(value: str) -> str:
    token = value.strip().lower()
    mapping = {
        "active": "active",
        "watch": "watch",
        "resolved": "resolved",
        "overridden": "overridden",
    }
    normalized = mapping.get(token)
    if normalized is None:
        raise SystemExit(f"Invalid state status: {value} (allowed: {', '.join(STATE_STATUS_CHOICES)})")
    return normalized


def _normalize_state_bias(value: str) -> str:
    token = value.strip().lower()
    mapping = {
        "bull": "bullish",
        "bullish": "bullish",
        "bear": "bearish",
        "bearish": "bearish",
        "neutral": "neutral",
        "mixed": "mixed",
    }
    normalized = mapping.get(token)
    if normalized is None:
        raise SystemExit(f"Invalid state bias: {value} (allowed: {', '.join(STATE_BIAS_CHOICES)})")
    return normalized


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
            entry_mode TEXT NOT NULL DEFAULT 'issue',
            dedupe_key TEXT NOT NULL DEFAULT '',
            logged_at TEXT NOT NULL,
            title TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    _ensure_world_issue_entry_columns(conn)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_entries_as_of ON world_issue_entries(as_of DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_entries_filters "
        "ON world_issue_entries(issue_date, category, region, importance)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_entries_entry_mode "
        "ON world_issue_entries(entry_mode, issue_date, category, region, importance)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_entries_dedupe_key "
        "ON world_issue_entries(dedupe_key, issue_date DESC)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS world_issue_taxonomy (
            taxonomy_type TEXT NOT NULL,
            value TEXT NOT NULL,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            usage_count INTEGER NOT NULL DEFAULT 0,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            PRIMARY KEY (taxonomy_type, value)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_taxonomy_type "
        "ON world_issue_taxonomy(taxonomy_type, usage_count DESC, value)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS world_issue_states (
            state_id TEXT PRIMARY KEY,
            state_key TEXT NOT NULL,
            state_label TEXT NOT NULL,
            state_status TEXT NOT NULL,
            state_bias TEXT NOT NULL,
            net_effect TEXT NOT NULL,
            summary TEXT NOT NULL,
            rationale TEXT NOT NULL,
            source_event_id TEXT NOT NULL,
            caused_by_event_id TEXT,
            supersedes_state_id TEXT,
            replaced_by_state_id TEXT,
            effective_from TEXT NOT NULL,
            effective_to TEXT,
            confidence REAL NOT NULL,
            source_kind TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            FOREIGN KEY (source_event_id) REFERENCES world_issue_entries(event_id),
            FOREIGN KEY (caused_by_event_id) REFERENCES world_issue_entries(event_id),
            FOREIGN KEY (supersedes_state_id) REFERENCES world_issue_states(state_id),
            FOREIGN KEY (replaced_by_state_id) REFERENCES world_issue_states(state_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_states_key_status "
        "ON world_issue_states(state_key, state_status, effective_from DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_states_source_event "
        "ON world_issue_states(source_event_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_states_effective_from "
        "ON world_issue_states(effective_from DESC)"
    )
    _seed_system_taxonomy(conn)
    conn.commit()


def _ensure_world_issue_entry_columns(conn: sqlite3.Connection) -> None:
    columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(world_issue_entries)")}
    if "entry_mode" not in columns:
        conn.execute("ALTER TABLE world_issue_entries ADD COLUMN entry_mode TEXT NOT NULL DEFAULT 'issue'")
    if "dedupe_key" not in columns:
        conn.execute("ALTER TABLE world_issue_entries ADD COLUMN dedupe_key TEXT NOT NULL DEFAULT ''")


def _seed_system_taxonomy(conn: sqlite3.Connection) -> None:
    now = _kst_now().isoformat()
    for taxonomy_type, values in SYSTEM_TAXONOMY_VALUES.items():
        for value in values:
            conn.execute(
                """
                INSERT OR IGNORE INTO world_issue_taxonomy (
                    taxonomy_type, value, status, source, usage_count, first_seen_at, last_seen_at
                ) VALUES (?, ?, 'active', 'system', 0, ?, ?)
                """,
                (taxonomy_type, value, now, now),
            )


def _ensure_db(base_dir: str, db_file: str) -> Path:
    db_path = _resolve_db_path(base_dir, db_file)
    with _connect_db(db_path) as conn:
        _init_db(conn)
    return db_path


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
    entry_mode: str,
    title: str,
    summary: str,
    why_it_matters: str,
    portfolio_link: str,
    horizon: str,
    tickers: list[str],
    tags: list[str],
    subjects: list[dict[str, str]],
    industries: list[str],
    event_kind: str,
    sources: list[dict[str, Any]],
    story: str,
    story_thesis: str,
    story_checkpoint: str,
    state_key: str,
    state_label: str,
    state_status: str,
    state_bias: str,
    net_effect: str,
    derive_state: bool,
    dedupe_key: str,
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
        "entry_mode": entry_mode,
        "horizon": horizon,
        "title": title,
        "summary": summary,
        "why_it_matters": why_it_matters,
        "portfolio_link": portfolio_link,
        "tickers": tickers,
        "tags": tags,
        "subjects": subjects,
        "industries": industries,
        "derive_state": derive_state,
        "sources": sources,
    }
    if event_kind.strip():
        payload["event_kind"] = event_kind.strip()
    if story.strip():
        payload["story"] = story.strip()
    if story_thesis.strip():
        payload["story_thesis"] = story_thesis.strip()
    if story_checkpoint.strip():
        payload["story_checkpoint"] = story_checkpoint.strip()
    if state_key.strip():
        payload["state_key"] = state_key.strip()
    if state_label.strip():
        payload["state_label"] = state_label.strip()
    if state_status.strip():
        payload["state_status"] = state_status.strip()
    if state_bias.strip():
        payload["state_bias"] = state_bias.strip()
    if net_effect.strip():
        payload["net_effect"] = net_effect.strip()
    if dedupe_key.strip():
        payload["dedupe_key"] = dedupe_key.strip()
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
    entry_mode = _normalize_entry_mode(str(normalized.get("entry_mode", "issue")))

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

    subjects = _normalize_subjects_for_storage(normalized.get("subjects", []))
    industries = _normalize_industries_for_storage(normalized.get("industries", []))
    event_kind = _normalize_event_kind(str(normalized.get("event_kind", "")))
    derive_state = _coerce_bool(normalized.get("derive_state"), default=(entry_mode == "issue"))
    dedupe_key = _normalize_dedupe_key(str(normalized.get("dedupe_key", "")))
    sources = _normalize_sources_for_storage(normalized.get("sources"))
    state_key_raw = str(normalized.get("state_key", "")).strip()
    state_label = str(normalized.get("state_label", "")).strip()
    state_status_raw = str(normalized.get("state_status", "")).strip()
    state_bias_raw = str(normalized.get("state_bias", "")).strip()
    net_effect = str(normalized.get("net_effect", "")).strip()

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
    normalized["entry_mode"] = entry_mode
    normalized["title"] = title
    normalized["summary"] = summary
    normalized["tickers"] = tickers
    normalized["tags"] = tags
    normalized["subjects"] = subjects
    normalized["industries"] = industries
    normalized["derive_state"] = derive_state
    normalized["sources"] = sources
    if event_kind:
        normalized["event_kind"] = event_kind
    elif "event_kind" in normalized:
        normalized.pop("event_kind", None)
    if dedupe_key:
        normalized["dedupe_key"] = dedupe_key
    elif "dedupe_key" in normalized:
        normalized.pop("dedupe_key", None)
    if state_key_raw:
        normalized["state_key"] = _normalize_state_key(state_key_raw)
    elif "state_key" in normalized:
        normalized.pop("state_key", None)
    if state_label:
        normalized["state_label"] = state_label
    if state_status_raw:
        normalized["state_status"] = _normalize_state_status(state_status_raw)
    if state_bias_raw:
        normalized["state_bias"] = _normalize_state_bias(state_bias_raw)
    if net_effect:
        normalized["net_effect"] = net_effect
    if entry_mode == "brief" and not subjects and not industries and not event_kind:
        raise ValueError("brief entry requires at least one of subjects, industries, or event_kind")
    if entry_mode == "brief" and "dedupe_key" not in normalized:
        auto_key = _auto_dedupe_key(normalized)
        if auto_key:
            normalized["dedupe_key"] = auto_key
    return normalized


def _upsert_sqlite_payload(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO world_issue_entries (
            event_id, as_of, issue_date, category, region, importance, entry_mode, dedupe_key, logged_at, title, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            as_of=excluded.as_of,
            issue_date=excluded.issue_date,
            category=excluded.category,
            region=excluded.region,
            importance=excluded.importance,
            entry_mode=excluded.entry_mode,
            dedupe_key=excluded.dedupe_key,
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
            str(payload.get("entry_mode", "issue")),
            str(payload.get("dedupe_key", "")),
            str(payload.get("logged_at", "")),
            str(payload.get("title", "")),
            json.dumps(payload, ensure_ascii=False),
        ),
    )


def _taxonomy_observed_at(payload: dict[str, Any]) -> str:
    observed_at = _parse_datetime_safe(payload.get("as_of")) or _parse_datetime_safe(payload.get("logged_at"))
    if observed_at is None:
        observed_at = _kst_now()
    return observed_at.isoformat()


def _taxonomy_entries_from_payload(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []

    category = str(payload.get("category", "")).strip()
    region = str(payload.get("region", "")).strip()
    importance = str(payload.get("importance", "")).strip()
    entry_mode = str(payload.get("entry_mode", "")).strip()
    story = str(payload.get("story", "")).strip()
    event_kind = str(payload.get("event_kind", "")).strip()
    state_key = str(payload.get("state_key", "")).strip()
    net_effect = str(payload.get("net_effect", "")).strip()

    if category:
        entries.append(("category", category, "system"))
    if region:
        entries.append(("region", region, "system"))
    if importance:
        entries.append(("importance", importance, "system"))
    if entry_mode:
        entries.append(("entry_mode", entry_mode, "system"))
    if story:
        entries.append(("story", story, "observed"))
    if event_kind:
        entries.append(("event_kind", event_kind, "observed"))
    if state_key:
        entries.append(("state_key", state_key, "observed"))
    if net_effect:
        entries.append(("net_effect", net_effect, "observed"))

    for tag in [str(item).strip() for item in payload.get("tags", []) if str(item).strip()]:
        entries.append(("tag", tag, "observed"))

    for ticker in [str(item).strip().upper() for item in payload.get("tickers", []) if str(item).strip()]:
        entries.append(("ticker", ticker, "observed"))

    for subject in payload.get("subjects", []):
        if not isinstance(subject, dict):
            continue
        name = str(subject.get("name", "")).strip()
        subject_type = str(subject.get("type", "")).strip()
        if name:
            entries.append(("subject", name, "observed"))
        if subject_type:
            entries.append(("subject_type", subject_type, "observed"))

    for industry in [str(item).strip() for item in payload.get("industries", []) if str(item).strip()]:
        entries.append(("industry", industry, "observed"))

    deduped: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for taxonomy_type, value, source in entries:
        key = (taxonomy_type, value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((taxonomy_type, value, source))
    return deduped


def _upsert_taxonomy_observation(
    conn: sqlite3.Connection,
    *,
    taxonomy_type: str,
    value: str,
    observed_at: str,
    source: str,
) -> None:
    conn.execute(
        """
        INSERT INTO world_issue_taxonomy (
            taxonomy_type, value, status, source, usage_count, first_seen_at, last_seen_at
        ) VALUES (?, ?, 'active', ?, 1, ?, ?)
        ON CONFLICT(taxonomy_type, value) DO UPDATE SET
            status='active',
            usage_count=world_issue_taxonomy.usage_count + 1,
            first_seen_at=MIN(world_issue_taxonomy.first_seen_at, excluded.first_seen_at),
            last_seen_at=MAX(world_issue_taxonomy.last_seen_at, excluded.last_seen_at)
        """,
        (taxonomy_type, value, source, observed_at, observed_at),
    )


def _upsert_taxonomy_for_payload(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    observed_at = _taxonomy_observed_at(payload)
    for taxonomy_type, value, source in _taxonomy_entries_from_payload(payload):
        _upsert_taxonomy_observation(
            conn,
            taxonomy_type=taxonomy_type,
            value=value,
            observed_at=observed_at,
            source=source,
        )


def _upsert_taxonomy_for_state(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    observed_at = str(row.get("effective_from", "")).strip() or _kst_now().isoformat()
    state_key = str(row.get("state_key", "")).strip()
    net_effect = str(row.get("net_effect", "")).strip()
    if state_key:
        _upsert_taxonomy_observation(
            conn,
            taxonomy_type="state_key",
            value=state_key,
            observed_at=observed_at,
            source="observed",
        )
    if net_effect:
        _upsert_taxonomy_observation(
            conn,
            taxonomy_type="net_effect",
            value=net_effect,
            observed_at=observed_at,
            source="observed",
        )


def _rebuild_taxonomy_index(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM world_issue_taxonomy")
    _seed_system_taxonomy(conn)

    processed = 0
    rows = conn.execute("SELECT payload_json FROM world_issue_entries ORDER BY as_of ASC, logged_at ASC")
    for record in rows:
        try:
            payload = json.loads(str(record["payload_json"]))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        try:
            normalized = _normalize_payload_for_storage(payload)
        except ValueError:
            continue
        _upsert_taxonomy_for_payload(conn, normalized)
        processed += 1

    state_rows = conn.execute(
        "SELECT state_key, net_effect, effective_from FROM world_issue_states"
    ).fetchall()
    for row in state_rows:
        _upsert_taxonomy_for_state(conn, dict(row))
    return processed


def _read_taxonomy_rows(
    *,
    db_path: Path,
    taxonomy_type: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    where = ""
    params: list[Any] = []
    if taxonomy_type != "all":
        where = "WHERE taxonomy_type = ?"
        params.append(taxonomy_type)
    params.append(max(1, limit))

    query = (
        "SELECT taxonomy_type, value, status, source, usage_count, first_seen_at, last_seen_at "
        "FROM world_issue_taxonomy "
        f"{where} "
        "ORDER BY usage_count DESC, last_seen_at DESC, value ASC "
        "LIMIT ?"
    )

    out: list[dict[str, Any]] = []
    with _connect_db(db_path) as conn:
        _init_db(conn)
        for row in conn.execute(query, params):
            out.append(dict(row))
    return out


def _taxonomy_type_label(value: str) -> str:
    labels = {
        "category": "분류",
        "region": "지역",
        "importance": "중요도",
        "entry_mode": "엔트리 모드",
        "story": "스토리",
        "tag": "태그",
        "ticker": "티커",
        "subject": "주체",
        "subject_type": "주체 유형",
        "industry": "산업",
        "event_kind": "이벤트 유형",
        "state_key": "상태 키",
        "net_effect": "순효과",
    }
    return labels.get(value, value)


def _taxonomy_rows_to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    view_rows: list[dict[str, Any]] = []
    for row in rows:
        first_seen = _parse_datetime_safe(row.get("first_seen_at"))
        last_seen = _parse_datetime_safe(row.get("last_seen_at"))
        view_rows.append(
            {
                "Type": _taxonomy_type_label(str(row.get("taxonomy_type", ""))),
                "Value": str(row.get("value", "")),
                "Source": str(row.get("source", "")),
                "Status": str(row.get("status", "")),
                "Usage Count": int(row.get("usage_count", 0)),
                "First Seen (KST)": first_seen.strftime("%Y-%m-%d %H:%M KST") if first_seen else "",
                "Last Seen (KST)": last_seen.strftime("%Y-%m-%d %H:%M KST") if last_seen else "",
            }
        )
    return pd.DataFrame(view_rows)


def _label_state_status(value: str) -> str:
    return {
        "active": "활성",
        "watch": "관찰",
        "resolved": "해소",
        "overridden": "대체됨",
    }.get(value, value)


def _label_state_bias(value: str) -> str:
    return {
        "bullish": "상방",
        "bearish": "하방",
        "neutral": "중립",
        "mixed": "혼합",
    }.get(value, value)


def _build_state_payload(
    *,
    state_key: str,
    state_label: str,
    state_status: str,
    state_bias: str,
    net_effect: str,
    summary: str,
    rationale: str,
    source_event_id: str,
    caused_by_event_id: str,
    supersedes_state_id: str,
    effective_from: str,
    effective_to: str,
    confidence: float,
    source_kind: str,
) -> dict[str, Any]:
    now = _kst_now().isoformat()
    payload = {
        "state_id": str(uuid.uuid4()),
        "state_key": _normalize_state_key(state_key),
        "state_label": state_label.strip() or state_key.strip(),
        "state_status": _normalize_state_status(state_status),
        "state_bias": _normalize_state_bias(state_bias),
        "net_effect": net_effect.strip(),
        "summary": summary.strip(),
        "rationale": rationale.strip(),
        "source_event_id": source_event_id.strip(),
        "caused_by_event_id": caused_by_event_id.strip(),
        "supersedes_state_id": supersedes_state_id.strip(),
        "effective_from": _parse_datetime(effective_from).isoformat(),
        "effective_to": _parse_datetime(effective_to).isoformat() if effective_to.strip() else "",
        "confidence": max(0.0, min(1.0, float(confidence))),
        "source_kind": source_kind.strip() or "manual",
        "created_at": now,
        "updated_at": now,
    }
    if not payload["summary"]:
        raise SystemExit("state summary is required")
    if not payload["source_event_id"]:
        raise SystemExit("state source_event_id is required")
    return payload


def _insert_sqlite_state(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO world_issue_states (
            state_id, state_key, state_label, state_status, state_bias, net_effect,
            summary, rationale, source_event_id, caused_by_event_id, supersedes_state_id,
            replaced_by_state_id, effective_from, effective_to, confidence, source_kind,
            created_at, updated_at, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(payload.get("state_id", "")),
            str(payload.get("state_key", "")),
            str(payload.get("state_label", "")),
            str(payload.get("state_status", "")),
            str(payload.get("state_bias", "")),
            str(payload.get("net_effect", "")),
            str(payload.get("summary", "")),
            str(payload.get("rationale", "")),
            str(payload.get("source_event_id", "")),
            str(payload.get("caused_by_event_id", "")) or None,
            str(payload.get("supersedes_state_id", "")) or None,
            str(payload.get("replaced_by_state_id", "")) or None,
            str(payload.get("effective_from", "")),
            str(payload.get("effective_to", "")) or None,
            float(payload.get("confidence", 0.0)),
            str(payload.get("source_kind", "manual")),
            str(payload.get("created_at", "")),
            str(payload.get("updated_at", "")),
            json.dumps(payload, ensure_ascii=False),
        ),
    )


def _refresh_state_row(conn: sqlite3.Connection, state_id: str) -> None:
    row = conn.execute("SELECT * FROM world_issue_states WHERE state_id = ?", (state_id,)).fetchone()
    if row is None:
        return
    payload = {
        "state_id": row["state_id"],
        "state_key": row["state_key"],
        "state_label": row["state_label"],
        "state_status": row["state_status"],
        "state_bias": row["state_bias"],
        "net_effect": row["net_effect"],
        "summary": row["summary"],
        "rationale": row["rationale"],
        "source_event_id": row["source_event_id"],
        "caused_by_event_id": row["caused_by_event_id"] or "",
        "supersedes_state_id": row["supersedes_state_id"] or "",
        "replaced_by_state_id": row["replaced_by_state_id"] or "",
        "effective_from": row["effective_from"],
        "effective_to": row["effective_to"] or "",
        "confidence": row["confidence"],
        "source_kind": row["source_kind"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    conn.execute(
        "UPDATE world_issue_states SET payload_json = ? WHERE state_id = ?",
        (json.dumps(payload, ensure_ascii=False), state_id),
    )


def _find_latest_state(
    conn: sqlite3.Connection,
    *,
    state_key: str,
    statuses: tuple[str, ...] = ("active", "watch"),
) -> sqlite3.Row | None:
    placeholders = ", ".join(["?"] * len(statuses))
    query = (
        "SELECT * FROM world_issue_states "
        f"WHERE state_key = ? AND state_status IN ({placeholders}) "
        "ORDER BY effective_from DESC, created_at DESC LIMIT 1"
    )
    params: list[Any] = [_normalize_state_key(state_key), *statuses]
    return conn.execute(query, params).fetchone()


def _mark_state_replaced(
    conn: sqlite3.Connection,
    *,
    state_id: str,
    replaced_by_state_id: str,
    effective_to: str,
) -> None:
    conn.execute(
        """
        UPDATE world_issue_states
        SET state_status = 'overridden',
            replaced_by_state_id = ?,
            effective_to = ?,
            updated_at = ?
        WHERE state_id = ?
        """,
        (replaced_by_state_id, effective_to, _kst_now().isoformat(), state_id),
    )
    _refresh_state_row(conn, state_id)


def _state_rows_to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    view_rows: list[dict[str, Any]] = []
    for row in rows:
        effective_from = _parse_datetime_safe(row.get("effective_from"))
        effective_to = _parse_datetime_safe(row.get("effective_to"))
        view_rows.append(
            {
                "Status": _label_state_status(str(row.get("state_status", ""))),
                "Bias": _label_state_bias(str(row.get("state_bias", ""))),
                "State Key": str(row.get("state_key", "")),
                "Label": str(row.get("state_label", "")),
                "Net Effect": str(row.get("net_effect", "")),
                "Summary": str(row.get("summary", "")),
                "Effective From (KST)": effective_from.strftime("%Y-%m-%d %H:%M KST") if effective_from else "",
                "Effective To (KST)": effective_to.strftime("%Y-%m-%d %H:%M KST") if effective_to else "",
                "Confidence": round(float(row.get("confidence", 0.0)), 2),
                "Source Event": str(row.get("source_event_id", "")),
                "Source Kind": str(row.get("source_kind", "")),
            }
        )
    return pd.DataFrame(view_rows)


def _read_state_rows(
    *,
    db_path: Path,
    state_status: str,
    state_key: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    where: list[str] = []
    params: list[Any] = []
    if state_status != "all":
        where.append("state_status = ?")
        params.append(_normalize_state_status(state_status))
    if state_key:
        where.append("state_key = ?")
        params.append(_normalize_state_key(state_key))
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    params.append(max(1, limit))

    query = (
        "SELECT state_id, state_key, state_label, state_status, state_bias, net_effect, "
        "summary, rationale, source_event_id, caused_by_event_id, supersedes_state_id, "
        "replaced_by_state_id, effective_from, effective_to, confidence, source_kind, created_at, updated_at "
        "FROM world_issue_states "
        f"{where_sql} "
        "ORDER BY effective_from DESC, created_at DESC LIMIT ?"
    )

    out: list[dict[str, Any]] = []
    with _connect_db(db_path) as conn:
        _init_db(conn)
        for row in conn.execute(query, params):
            out.append(dict(row))
    return out


def _read_current_state_rows(
    *,
    db_path: Path,
    limit: int,
    statuses: tuple[str, ...] = ("active", "watch"),
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    normalized_statuses = tuple(_normalize_state_status(status) for status in statuses)
    placeholders = ", ".join(["?"] * len(normalized_statuses))
    query = (
        "SELECT state_id, state_key, state_label, state_status, state_bias, net_effect, "
        "summary, rationale, source_event_id, caused_by_event_id, supersedes_state_id, "
        "replaced_by_state_id, effective_from, effective_to, confidence, source_kind, created_at, updated_at "
        "FROM world_issue_states "
        f"WHERE state_status IN ({placeholders}) "
        "ORDER BY effective_from DESC, created_at DESC LIMIT ?"
    )
    params: list[Any] = [*normalized_statuses, max(1, limit)]

    out: list[dict[str, Any]] = []
    with _connect_db(db_path) as conn:
        _init_db(conn)
        for row in conn.execute(query, params):
            out.append(dict(row))
    return out


def _state_key_from_issue(payload: dict[str, Any]) -> str:
    if not _coerce_bool(payload.get("derive_state"), default=True):
        return ""
    explicit = str(payload.get("state_key", "")).strip()
    if explicit:
        return _normalize_state_key(explicit)

    story = str(payload.get("story", "")).strip()
    if story:
        return _normalize_state_key(story)
    return ""


def _build_derived_state_payload_from_issue(payload: dict[str, Any]) -> dict[str, Any] | None:
    state_key = _state_key_from_issue(payload)
    if not state_key:
        return None

    label = (
        str(payload.get("state_label", "")).strip()
        or str(payload.get("story", "")).strip()
        or str(payload.get("title", "")).strip()
    )
    summary = str(payload.get("summary", "")).strip()
    rationale = str(payload.get("story_thesis", "")).strip() or str(payload.get("why_it_matters", "")).strip()
    net_effect = str(payload.get("net_effect", "")).strip()
    bias = str(payload.get("state_bias", "")).strip() or "mixed"
    status = str(payload.get("state_status", "")).strip() or "active"
    effective_from = str(payload.get("as_of", "")).strip() or _kst_now().isoformat()

    return _build_state_payload(
        state_key=state_key,
        state_label=label,
        state_status=status,
        state_bias=bias,
        net_effect=net_effect,
        summary=summary,
        rationale=rationale,
        source_event_id=str(payload.get("event_id", "")).strip(),
        caused_by_event_id=str(payload.get("event_id", "")).strip(),
        supersedes_state_id="",
        effective_from=effective_from,
        effective_to="",
        confidence=0.55,
        source_kind="derived",
    )


def _upsert_derived_state_for_issue(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    state_payload = _build_derived_state_payload_from_issue(payload)
    if state_payload is None:
        return None

    state_key = str(state_payload.get("state_key", "")).strip()
    manual_exists = conn.execute(
        """
        SELECT 1
        FROM world_issue_states
        WHERE state_key = ? AND source_kind != 'derived'
        LIMIT 1
        """,
        (state_key,),
    ).fetchone()
    if manual_exists is not None:
        return None

    previous = conn.execute(
        """
        SELECT *
        FROM world_issue_states
        WHERE state_key = ? AND source_kind = 'derived' AND state_status IN ('active', 'watch')
        ORDER BY effective_from DESC, created_at DESC
        LIMIT 1
        """,
        (state_key,),
    ).fetchone()
    if previous is not None:
        state_payload["supersedes_state_id"] = str(previous["state_id"])

    _insert_sqlite_state(conn, state_payload)
    if previous is not None:
        _mark_state_replaced(
            conn,
            state_id=str(previous["state_id"]),
            replaced_by_state_id=str(state_payload.get("state_id", "")),
            effective_to=str(state_payload.get("effective_from", "")),
        )
    _upsert_taxonomy_for_state(conn, state_payload)
    return state_payload


def _sync_derived_states(conn: sqlite3.Connection, *, replace_existing: bool) -> tuple[int, int]:
    if replace_existing:
        conn.execute("DELETE FROM world_issue_states WHERE source_kind = 'derived'")

    rows = conn.execute("SELECT payload_json FROM world_issue_entries ORDER BY as_of ASC, logged_at ASC").fetchall()
    latest_by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            payload = json.loads(str(row["payload_json"]))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        try:
            normalized = _normalize_payload_for_storage(payload)
        except ValueError:
            continue
        state_key = _state_key_from_issue(normalized)
        if not state_key:
            continue
        latest_by_key[state_key] = normalized

    inserted = 0
    skipped_manual = 0
    for state_key, payload in latest_by_key.items():
        manual_exists = conn.execute(
            """
            SELECT 1
            FROM world_issue_states
            WHERE state_key = ? AND source_kind != 'derived'
            LIMIT 1
            """,
            (state_key,),
        ).fetchone()
        if manual_exists is not None:
            skipped_manual += 1
            continue

        state_payload = _build_derived_state_payload_from_issue(payload)
        if state_payload is None:
            continue
        _insert_sqlite_state(conn, state_payload)
        _upsert_taxonomy_for_state(conn, state_payload)
        inserted += 1

    return inserted, skipped_manual


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
    entry_mode_filter: str,
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
    if entry_mode_filter != "all":
        where.append("entry_mode = ?")
        params.append(entry_mode_filter)

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


def _load_filtered_rows(args: argparse.Namespace) -> tuple[list[dict[str, Any]], str, Path, dt.date, dt.date]:
    start_date, end_date = _resolve_date_window(args)
    category_filter, region_filter, importance_filter = _resolve_filter_tokens(args)
    entry_mode_filter = str(getattr(args, "entry_mode", "issue")).strip().lower()
    if entry_mode_filter != "all":
        entry_mode_filter = _normalize_entry_mode(entry_mode_filter)

    db_path = _resolve_db_path(args.base_dir, args.db_file)

    sqlite_rows = _read_filtered_rows_from_sqlite(
        db_path=db_path,
        start_date=start_date,
        end_date=end_date,
        category_filter=category_filter,
        region_filter=region_filter,
        importance_filter=importance_filter,
        entry_mode_filter=entry_mode_filter,
    )
    return _filter_rows(sqlite_rows, args), "sqlite", db_path, start_date, end_date


def _filter_rows(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    start_date, end_date = _resolve_date_window(args)
    category_filter, region_filter, importance_filter = _resolve_filter_tokens(args)
    entry_mode_filter = str(getattr(args, "entry_mode", "issue")).strip().lower()
    if entry_mode_filter != "all":
        entry_mode_filter = _normalize_entry_mode(entry_mode_filter)
    subject_filter = str(getattr(args, "subject", "")).strip().casefold()
    industry_filter = str(getattr(args, "industry", "")).strip().casefold()
    event_kind_filter = _normalize_event_kind(str(getattr(args, "event_kind", "")).strip())

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
        entry_mode = _normalize_entry_mode(str(row.get("entry_mode", "issue")))

        if category_filter != "all" and category != category_filter:
            continue
        if region_filter != "all" and region != region_filter:
            continue
        if importance_filter != "all" and importance != importance_filter:
            continue
        if entry_mode_filter != "all" and entry_mode != entry_mode_filter:
            continue

        subjects = _normalize_subjects_for_storage(row.get("subjects", []))
        industries = _normalize_industries_for_storage(row.get("industries", []))
        event_kind = _normalize_event_kind(str(row.get("event_kind", "")))

        if subject_filter and not any(subject_filter in str(item.get("name", "")).casefold() for item in subjects):
            continue
        if industry_filter and not any(industry_filter in item.casefold() for item in industries):
            continue
        if event_kind_filter and event_kind != event_kind_filter:
            continue

        normalized = dict(row)
        normalized["category"] = category
        normalized["region"] = region
        normalized["importance"] = importance
        normalized["entry_mode"] = entry_mode
        normalized["as_of"] = as_of.isoformat()
        normalized["subjects"] = subjects
        normalized["industries"] = industries
        if event_kind:
            normalized["event_kind"] = event_kind
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


def _label_entry_mode(entry_mode: str) -> str:
    return {
        "issue": "이슈",
        "brief": "브리프",
    }.get(entry_mode, entry_mode)


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


def _subject_display(row: dict[str, Any]) -> str:
    out: list[str] = []
    for item in row.get("subjects", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        subject_type = str(item.get("type", "")).strip()
        if not name:
            continue
        if subject_type and subject_type != "other":
            out.append(f"{name} ({subject_type})")
        else:
            out.append(name)
    return ", ".join(out)


def _humanize_event_kind(value: str) -> str:
    return value.replace("_", " ").strip()


def _rows_to_frame(rows: list[dict[str, Any]], *, limit: int) -> pd.DataFrame:
    limited = rows[: max(1, limit)]
    has_brief_fields = any(
        str(row.get("entry_mode", "issue")) != "issue"
        or row.get("subjects")
        or row.get("industries")
        or str(row.get("event_kind", "")).strip()
        for row in limited
    )
    view_rows: list[dict[str, Any]] = []
    for row in limited:
        view_row = {
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
        if has_brief_fields:
            view_row["Entry Mode"] = _label_entry_mode(str(row.get("entry_mode", "issue")))
            view_row["Subjects"] = _subject_display(row)
            view_row["Industries"] = ", ".join(
                [str(item) for item in row.get("industries", []) if str(item).strip()]
            )
            view_row["Event Kind"] = _humanize_event_kind(str(row.get("event_kind", "")))
        view_rows.append(view_row)
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


def _state_table_for_report(rows: list[dict[str, Any]], *, max_items: int) -> str:
    if not rows:
        return "현재 활성 상태가 없습니다.\n"

    view_rows: list[dict[str, Any]] = []
    for row in rows[: max_items]:
        effective_from = _parse_datetime_safe(row.get("effective_from"))
        view_rows.append(
            {
                "시작(KST)": effective_from.strftime("%Y-%m-%d %H:%M KST") if effective_from else "",
                "상태": _label_state_status(str(row.get("state_status", ""))),
                "방향": _label_state_bias(str(row.get("state_bias", ""))),
                "state_key": str(row.get("state_key", "")),
                "라벨": str(row.get("state_label", "")),
                "요약": str(row.get("summary", "")),
                "net_effect": str(row.get("net_effect", "")),
            }
        )
    return _dataframe_to_markdown(pd.DataFrame(view_rows))


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


def _find_existing_event_by_dedupe_key(
    conn: sqlite3.Connection,
    *,
    dedupe_key: str,
    entry_mode: str,
    as_of: dt.datetime,
    dedupe_days: int,
) -> dict[str, Any] | None:
    token = _normalize_dedupe_key(dedupe_key)
    if not token:
        return None

    where = ["dedupe_key = ?", "entry_mode = ?"]
    params: list[Any] = [token, _normalize_entry_mode(entry_mode)]
    if dedupe_days > 0:
        start_date = (as_of.date() - dt.timedelta(days=max(1, dedupe_days) - 1)).isoformat()
        where.append("issue_date >= ?")
        params.append(start_date)

    row = conn.execute(
        f"""
        SELECT event_id, as_of, title
        FROM world_issue_entries
        WHERE {' AND '.join(where)}
        ORDER BY as_of DESC, logged_at DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def _save_payload_without_manual_state(
    *,
    db_path: Path,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    normalized_payload = _normalize_payload_for_storage(payload)
    with _connect_db(db_path) as conn:
        _init_db(conn)
        _upsert_sqlite_payload(conn, normalized_payload)
        state_payload = _upsert_derived_state_for_issue(conn, normalized_payload)
        _upsert_taxonomy_for_payload(conn, normalized_payload)
        conn.commit()

    print(f"Upserted SQLite world issue: {db_path}")
    print(f"event_id={normalized_payload['event_id']}")
    if state_payload is not None:
        print(f"state_id={state_payload['state_id']}")
        print(f"state_key={state_payload['state_key']}")
    return normalized_payload, state_payload


def _read_import_payloads(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if path.suffix.lower() == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line_no, raw in enumerate(text.splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"JSONL parse error in {path}:{line_no}: {e.msg}") from e
            if not isinstance(item, dict):
                raise SystemExit(f"JSONL row must be an object: {path}:{line_no}")
            rows.append(item)
        return rows

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise SystemExit(f"JSON parse error in {path}: {e.msg}") from e

    if isinstance(parsed, dict):
        return [parsed]
    if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
        return list(parsed)
    raise SystemExit(f"Unsupported import payload shape in {path}. Use JSON object, JSON array, or JSONL objects.")


def _handle_init(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    print(f"Initialized SQLite store: {db_path}")
    print("Initialized taxonomy index: world_issue_taxonomy")
    return 0


def _handle_add(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    sources = _parse_sources(args)
    if not sources:
        raise SystemExit("At least one source is required. Use --source or --sources-json/--sources-file")

    state_args_present = any(
        [
            str(args.state_label or "").strip(),
            str(args.state_status or "").strip(),
            str(args.state_bias or "").strip(),
            str(args.net_effect or "").strip(),
            str(args.state_summary or "").strip(),
            str(args.state_rationale or "").strip(),
            str(args.supersedes_state_id or "").strip(),
            str(args.caused_by_event_id or "").strip(),
            bool(args.supersedes_active),
            getattr(args, "state_effective_from", None) is not None,
            getattr(args, "state_effective_to", None) is not None,
        ]
    )
    if state_args_present and not str(args.state_key or "").strip():
        raise SystemExit("State metadata requires --state-key")

    as_of = args.as_of or _kst_now()
    payload = _build_issue_payload(
        as_of=as_of,
        category=_normalize_category(args.category),
        region=_normalize_region(args.region),
        importance=_normalize_importance(args.importance),
        entry_mode="issue",
        title=args.title.strip(),
        summary=args.summary.strip(),
        why_it_matters=(args.why_it_matters or "").strip(),
        portfolio_link=(args.portfolio_link or "").strip(),
        horizon=(args.horizon or "").strip(),
        tickers=_normalize_tickers(_split_csv(args.tickers)),
        tags=_unique_preserve_order(_split_csv(args.tags)),
        subjects=_normalize_subjects_for_storage(args.subject),
        industries=_normalize_industries_for_storage(args.industries),
        event_kind=_normalize_event_kind(args.event_kind or ""),
        sources=sources,
        story=(args.story or "").strip(),
        story_thesis=(args.story_thesis or "").strip(),
        story_checkpoint=(args.story_checkpoint or "").strip(),
        state_key=(args.state_key or "").strip(),
        state_label=(args.state_label or "").strip(),
        state_status=(args.state_status or "").strip(),
        state_bias=(args.state_bias or "").strip(),
        net_effect=(args.net_effect or "").strip(),
        derive_state=_coerce_bool(getattr(args, "derive_state", None), default=True),
        dedupe_key=_normalize_dedupe_key(args.dedupe_key or ""),
    )

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    normalized_payload = _normalize_payload_for_storage(payload)
    with _connect_db(db_path) as conn:
        _init_db(conn)
        if getattr(args, "skip_if_duplicate", False):
            existing = _find_existing_event_by_dedupe_key(
                conn,
                dedupe_key=str(normalized_payload.get("dedupe_key", "")).strip(),
                entry_mode=str(normalized_payload.get("entry_mode", "issue")).strip(),
                as_of=_issue_as_of(normalized_payload),
                dedupe_days=max(0, int(getattr(args, "dedupe_days", 0))),
            )
            if existing is not None:
                print(f"Skipped duplicate world issue: {db_path}")
                print(f"existing_event_id={existing['event_id']}")
                return 0
        _upsert_sqlite_payload(conn, normalized_payload)
        state_payload: dict[str, Any] | None = None
        state_key = str(normalized_payload.get("state_key", "")).strip()
        if state_key:
            supersedes_state_id = str(args.supersedes_state_id or "").strip()
            if args.supersedes_active and not supersedes_state_id:
                previous = _find_latest_state(conn, state_key=state_key)
                if previous is not None:
                    supersedes_state_id = str(previous["state_id"])

            effective_from = (
                args.state_effective_from.isoformat()
                if getattr(args, "state_effective_from", None) is not None
                else str(normalized_payload.get("as_of", ""))
            )
            effective_to = (
                args.state_effective_to.isoformat()
                if getattr(args, "state_effective_to", None) is not None
                else ""
            )

            state_payload = _build_state_payload(
                state_key=state_key,
                state_label=str(normalized_payload.get("state_label", "")).strip()
                or str(normalized_payload.get("story", "")).strip()
                or str(normalized_payload.get("title", "")).strip(),
                state_status=str(normalized_payload.get("state_status", "")).strip() or "active",
                state_bias=str(normalized_payload.get("state_bias", "")).strip() or "mixed",
                net_effect=str(normalized_payload.get("net_effect", "")).strip(),
                summary=(args.state_summary or "").strip() or str(normalized_payload.get("summary", "")).strip(),
                rationale=(args.state_rationale or "").strip()
                or str(normalized_payload.get("story_thesis", "")).strip()
                or str(normalized_payload.get("why_it_matters", "")).strip(),
                source_event_id=str(normalized_payload.get("event_id", "")).strip(),
                caused_by_event_id=(args.caused_by_event_id or "").strip() or str(normalized_payload.get("event_id", "")).strip(),
                supersedes_state_id=supersedes_state_id,
                effective_from=effective_from,
                effective_to=effective_to,
                confidence=float(args.state_confidence),
                source_kind="issue_add",
            )
            _insert_sqlite_state(conn, state_payload)
            if supersedes_state_id:
                _mark_state_replaced(
                    conn,
                    state_id=supersedes_state_id,
                    replaced_by_state_id=str(state_payload.get("state_id", "")),
                    effective_to=str(state_payload.get("effective_from", "")),
                )
            _upsert_taxonomy_for_state(conn, state_payload)
        else:
            state_payload = _upsert_derived_state_for_issue(conn, normalized_payload)
        _upsert_taxonomy_for_payload(conn, normalized_payload)
        conn.commit()

    print(f"Upserted SQLite world issue: {db_path}")
    print(f"event_id={normalized_payload['event_id']}")
    if state_payload is not None:
        print(f"state_id={state_payload['state_id']}")
        print(f"state_key={state_payload['state_key']}")
    return 0


def _handle_brief_add(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    sources = _parse_sources(args)
    if not sources:
        raise SystemExit("At least one source is required. Use --source or --sources-json/--sources-file")

    payload = _build_issue_payload(
        as_of=args.as_of or _kst_now(),
        category=_normalize_category(args.category),
        region=_normalize_region(args.region),
        importance=_normalize_importance(args.importance),
        entry_mode="brief",
        title=args.title.strip(),
        summary=args.summary.strip(),
        why_it_matters=(args.why_it_matters or "").strip(),
        portfolio_link=(args.portfolio_link or "").strip(),
        horizon=(args.horizon or "").strip(),
        tickers=_normalize_tickers(_split_csv(args.tickers)),
        tags=_unique_preserve_order(_split_csv(args.tags)),
        subjects=_normalize_subjects_for_storage(args.subject),
        industries=_normalize_industries_for_storage(args.industry),
        event_kind=_normalize_event_kind(args.event_kind or ""),
        sources=sources,
        story="",
        story_thesis="",
        story_checkpoint="",
        state_key="",
        state_label="",
        state_status="",
        state_bias="",
        net_effect="",
        derive_state=False,
        dedupe_key=_normalize_dedupe_key(args.dedupe_key or ""),
    )

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    normalized_payload = _normalize_payload_for_storage(payload)
    with _connect_db(db_path) as conn:
        _init_db(conn)
        if args.skip_if_duplicate:
            existing = _find_existing_event_by_dedupe_key(
                conn,
                dedupe_key=str(normalized_payload.get("dedupe_key", "")).strip(),
                entry_mode="brief",
                as_of=_issue_as_of(normalized_payload),
                dedupe_days=max(0, int(args.dedupe_days)),
            )
            if existing is not None:
                print(f"Skipped duplicate brief: {db_path}")
                print(f"existing_event_id={existing['event_id']}")
                return 0

    _save_payload_without_manual_state(
        db_path=db_path,
        payload=normalized_payload,
    )
    return 0


def _handle_brief_import(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    import_path = Path(args.from_file).expanduser()
    rows = _read_import_payloads(import_path)

    prepared: list[dict[str, Any]] = []
    for raw in rows:
        merged = dict(raw)
        merged.setdefault("category", args.category)
        merged.setdefault("region", args.region)
        merged.setdefault("importance", args.importance)
        merged.setdefault("horizon", args.horizon)
        merged["entry_mode"] = "brief"
        merged["derive_state"] = False
        normalized = _normalize_payload_for_storage(merged)
        if not normalized.get("sources"):
            raise SystemExit("brief-import rows require sources[]")
        prepared.append(normalized)

    if args.dry_run:
        print(json.dumps(prepared, ensure_ascii=False, indent=2))
        return 0

    inserted = 0
    skipped = 0
    with _connect_db(db_path) as conn:
        _init_db(conn)
        for payload in prepared:
            if args.skip_if_duplicate:
                existing = _find_existing_event_by_dedupe_key(
                    conn,
                    dedupe_key=str(payload.get("dedupe_key", "")).strip(),
                    entry_mode="brief",
                    as_of=_issue_as_of(payload),
                    dedupe_days=max(0, int(args.dedupe_days)),
                )
                if existing is not None:
                    skipped += 1
                    continue
            _upsert_sqlite_payload(conn, payload)
            _upsert_derived_state_for_issue(conn, payload)
            _upsert_taxonomy_for_payload(conn, payload)
            inserted += 1
        conn.commit()

    print(f"Imported brief rows into SQLite: {db_path}")
    print(f"inserted={inserted} skipped_duplicates={skipped} total_input={len(prepared)}")
    return 0


def _handle_list(args: argparse.Namespace) -> int:
    filtered, backend, db_path, _, _ = _load_filtered_rows(args)

    if args.format == "json":
        payload = {
            "timezone": DEFAULT_TZ,
            "backend": backend,
            "db_path": str(db_path),
            "count": len(filtered),
            "rows": filtered[: max(1, args.limit)],
        }
        _emit_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", args.out)
        return 0

    df = _rows_to_frame(filtered, limit=args.limit)
    _emit_dataframe(df, args.format, args.out)
    return 0


def _handle_taxonomy(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)

    if args.refresh:
        with _connect_db(db_path) as conn:
            _init_db(conn)
            processed = _rebuild_taxonomy_index(conn)
            conn.commit()
        print(f"Refreshed taxonomy index from {processed} world issue rows")

    rows = _read_taxonomy_rows(
        db_path=db_path,
        taxonomy_type=args.type,
        limit=args.limit,
    )

    if args.format == "json":
        payload = {
            "db_path": str(db_path),
            "count": len(rows),
            "rows": rows,
        }
        _emit_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", args.out)
        return 0

    df = _taxonomy_rows_to_frame(rows)
    _emit_dataframe(df, args.format, args.out)
    return 0


def _handle_states(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    rows = _read_state_rows(
        db_path=db_path,
        state_status=args.status,
        state_key=args.state_key,
        limit=args.limit,
    )

    if args.format == "json":
        payload = {
            "db_path": str(db_path),
            "count": len(rows),
            "rows": rows,
        }
        _emit_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", args.out)
        return 0

    df = _state_rows_to_frame(rows)
    _emit_dataframe(df, args.format, args.out)
    return 0


def _handle_state_sync(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    with _connect_db(db_path) as conn:
        _init_db(conn)
        inserted, skipped_manual = _sync_derived_states(conn, replace_existing=not args.keep_derived)
        _rebuild_taxonomy_index(conn)
        conn.commit()
    print(f"Synced derived states: inserted={inserted} skipped_manual={skipped_manual}")
    print(f"SQLite store: {db_path}")
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
    state_rows: list[dict[str, Any]],
    start_date: dt.date,
    end_date: dt.date,
    max_items: int,
    db_path: Path,
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
    lines.append(f"- 저장소(SQLite): `{db_path}`")
    lines.append("")

    lines.append("## 0) 현재 유효한 상태 (State Snapshots)")
    lines.append(_state_table_for_report(state_rows, max_items=min(6, max_items)).rstrip())
    lines.append("")

    lines.append("## 1) 시장을 주도하는 스토리 (Narrative Lens)")
    lines.append(
        _story_table_for_report(
            rows,
            end_date=end_date,
            max_items=min(5, max_items),
            recent_days=7,
        ).rstrip()
    )
    lines.append("")

    lines.append("## 2) 주식/채권시장의 현재 주요 이슈")
    lines.append("### 미국")
    lines.append(_table_for_report(us_rows, max_items=max_items).rstrip())
    lines.append("")
    lines.append("### 한국")
    lines.append(_table_for_report(kr_rows, max_items=max_items).rstrip())
    lines.append("")
    lines.append("### 글로벌")
    lines.append(_table_for_report(gl_rows, max_items=max_items).rstrip())
    lines.append("")

    lines.append("## 3) 투자에 영향을 미치는 글로벌 정치 이슈")
    lines.append(_table_for_report(geo_rows, max_items=max_items).rstrip())
    lines.append("")

    lines.append("## 4) 비지배적이지만 관심 둘 만한 이슈")
    lines.append(_table_for_report(non_dominant_rows, max_items=max_items).rstrip())
    lines.append("")

    lines.append("## 5) 포트폴리오 상담 반영 체크포인트")
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
    filtered, backend, db_path, start_date, end_date = _load_filtered_rows(args)
    filtered = [row for row in filtered if _normalize_entry_mode(str(row.get("entry_mode", "issue"))) == "issue"]
    state_rows = _read_current_state_rows(
        db_path=db_path,
        limit=max(1, args.max_items),
    )

    report_text = _build_report_text(
        filtered,
        state_rows=state_rows,
        start_date=start_date,
        end_date=end_date,
        max_items=max(1, args.max_items),
        db_path=db_path,
        title=args.title,
    )
    _emit_text(report_text + "\n", args.out)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="외부 세계 이슈 메모리 로그 도구")
    parser.add_argument("--base-dir", default=DEFAULT_BASE_DIR, help=f"로그 저장 경로 (기본: {DEFAULT_BASE_DIR})")
    parser.add_argument("--db-file", default=DEFAULT_DB_FILE, help=f"SQLite 파일명 (기본: {DEFAULT_DB_FILE})")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="외부 세계 이슈 SQLite 저장소 초기화")

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
    p_add.add_argument(
        "--subject",
        action="append",
        default=[],
        help="주체 입력: '이름|type' (예: Donald Trump|politician, Jensen Huang|business_leader)",
    )
    p_add.add_argument("--industries", default="", help="관련 산업/업종 (콤마 구분)")
    p_add.add_argument("--event-kind", default="", help="이벤트 유형 (예: regulation, statement, industry_trend)")
    p_add.add_argument("--story", default="", help="시장 스토리 라벨 (예: 디스인플레이션+성장 둔화)")
    p_add.add_argument("--story-thesis", default="", help="스토리 핵심 테제 1문장")
    p_add.add_argument("--story-checkpoint", default="", help="스토리 체크포인트(무효화/확인 조건)")
    p_add.add_argument(
        "--derive-state",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="story/state_key 기반 derived 상태 생성 여부 (기본: 켜짐)",
    )
    p_add.add_argument("--dedupe-key", default="", help="자동화 중복 방지 키")
    p_add.add_argument(
        "--skip-if-duplicate",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="같은 dedupe_key가 최근 기간에 있으면 저장 생략",
    )
    p_add.add_argument("--dedupe-days", type=int, default=7, help="중복 체크 기간(일)")
    p_add.add_argument("--state-key", default="", help="상태 스냅샷 키 (예: oil_geopolitical_risk)")
    p_add.add_argument("--state-label", default="", help="상태 스냅샷 라벨")
    p_add.add_argument(
        "--state-status",
        choices=STATE_STATUS_CHOICES,
        default="",
        help="상태 스냅샷 상태",
    )
    p_add.add_argument(
        "--state-bias",
        choices=STATE_BIAS_CHOICES,
        default="",
        help="상태 방향성",
    )
    p_add.add_argument("--net-effect", default="", help="자산/변수에 대한 순효과 (예: oil_up, usd_down)")
    p_add.add_argument("--state-summary", default="", help="현재 상태 요약")
    p_add.add_argument("--state-rationale", default="", help="현재 상태 판단 근거")
    p_add.add_argument(
        "--state-confidence",
        type=float,
        default=0.7,
        help="상태 스냅샷 신뢰도 (0~1, 기본 0.7)",
    )
    p_add.add_argument(
        "--state-effective-from",
        type=_parse_datetime,
        default=None,
        help="상태 유효 시작 시각 (기본: --as-of)",
    )
    p_add.add_argument(
        "--state-effective-to",
        type=_parse_datetime,
        default=None,
        help="상태 유효 종료 시각",
    )
    p_add.add_argument(
        "--supersedes-active",
        action="store_true",
        help="같은 state_key의 최신 active/watch 상태를 자동 대체",
    )
    p_add.add_argument("--supersedes-state-id", default="", help="명시적으로 대체할 이전 state_id")
    p_add.add_argument("--caused-by-event-id", default="", help="직접 원인으로 연결할 event_id")
    p_add.add_argument(
        "--source",
        action="append",
        default=[],
        help="출처 단축 입력: '매체명|URL|게시시각(옵션)|메모(옵션)'",
    )
    p_add.add_argument("--sources-json", default="", help="출처 JSON 문자열(배열)")
    p_add.add_argument("--sources-file", default=None, help="출처 JSON 파일 경로")
    p_add.add_argument("--dry-run", action="store_true", help="저장 없이 payload 확인")

    p_brief = sub.add_parser("brief-add", help="주체/산업 브리프 메모 1건 기록")
    p_brief.add_argument("--as-of", type=_parse_datetime, default=None, help="브리프 기준 시각 (ISO 8601, 기본: 현재 KST)")
    p_brief.add_argument("--category", choices=CATEGORY_CHOICES, default="emerging", help="이슈 분류")
    p_brief.add_argument("--region", choices=REGION_CHOICES, default="GLOBAL", help="지역 분류")
    p_brief.add_argument("--importance", choices=IMPORTANCE_CHOICES, default="low", help="중요도")
    p_brief.add_argument("--title", required=True, help="브리프 제목")
    p_brief.add_argument("--summary", required=True, help="짧은 코멘트")
    p_brief.add_argument("--why-it-matters", default="", help="왜 중요한지")
    p_brief.add_argument("--portfolio-link", default="", help="포트폴리오 상담 반영 포인트")
    p_brief.add_argument("--horizon", default="수일~수주", help="영향 기간")
    p_brief.add_argument("--tickers", default="", help="관련 티커 (콤마 구분)")
    p_brief.add_argument("--tags", default="", help="태그 (콤마 구분)")
    p_brief.add_argument(
        "--subject",
        action="append",
        default=[],
        help="주체 입력: '이름|type' (예: Donald Trump|politician)",
    )
    p_brief.add_argument("--industry", action="append", default=[], help="산업/업종 라벨 (여러 번 지정 가능)")
    p_brief.add_argument("--event-kind", default="", help="이벤트 유형 (예: statement, industry_trend)")
    p_brief.add_argument("--dedupe-key", default="", help="자동화 중복 방지 키")
    p_brief.add_argument(
        "--skip-if-duplicate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="같은 dedupe_key가 최근 기간에 있으면 저장 생략 (기본: 켜짐)",
    )
    p_brief.add_argument("--dedupe-days", type=int, default=7, help="중복 체크 기간(일)")
    p_brief.add_argument(
        "--source",
        action="append",
        default=[],
        help="출처 단축 입력: '매체명|URL|게시시각(옵션)|메모(옵션)'",
    )
    p_brief.add_argument("--sources-json", default="", help="출처 JSON 문자열(배열)")
    p_brief.add_argument("--sources-file", default=None, help="출처 JSON 파일 경로")
    p_brief.add_argument("--dry-run", action="store_true", help="저장 없이 payload 확인")

    p_brief_import = sub.add_parser("brief-import", help="주체/산업 브리프 JSON/JSONL 배치 입력")
    p_brief_import.add_argument("--from-file", required=True, help="입력 파일 경로 (.json/.jsonl)")
    p_brief_import.add_argument("--category", choices=CATEGORY_CHOICES, default="emerging", help="기본 분류")
    p_brief_import.add_argument("--region", choices=REGION_CHOICES, default="GLOBAL", help="기본 지역")
    p_brief_import.add_argument("--importance", choices=IMPORTANCE_CHOICES, default="low", help="기본 중요도")
    p_brief_import.add_argument("--horizon", default="수일~수주", help="기본 영향 기간")
    p_brief_import.add_argument(
        "--skip-if-duplicate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="같은 dedupe_key가 최근 기간에 있으면 저장 생략 (기본: 켜짐)",
    )
    p_brief_import.add_argument("--dedupe-days", type=int, default=7, help="중복 체크 기간(일)")
    p_brief_import.add_argument("--dry-run", action="store_true", help="저장 없이 정규화 payload 확인")

    p_list = sub.add_parser("list", help="이슈 로그 조회")
    p_list.add_argument("--start", type=_parse_date, default=None, help="시작일 (YYYY-MM-DD)")
    p_list.add_argument("--end", type=_parse_date, default=None, help="종료일 (YYYY-MM-DD, 기본: 오늘 KST)")
    p_list.add_argument("--days", type=int, default=30, help="start 미지정 시 최근 조회 기간(일)")
    p_list.add_argument("--category", choices=["all"] + CATEGORY_CHOICES, default="all", help="카테고리 필터")
    p_list.add_argument("--region", choices=["all"] + REGION_CHOICES, default="all", help="지역 필터")
    p_list.add_argument("--importance", choices=["all"] + IMPORTANCE_CHOICES, default="all", help="중요도 필터")
    p_list.add_argument("--entry-mode", choices=["all"] + ENTRY_MODE_CHOICES, default="issue", help="엔트리 모드 필터")
    p_list.add_argument("--subject", default="", help="주체명 부분일치 필터")
    p_list.add_argument("--industry", default="", help="산업명 부분일치 필터")
    p_list.add_argument("--event-kind", default="", help="이벤트 유형 필터")
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

    p_taxonomy = sub.add_parser("taxonomy", help="기존 분류/스토리/태그/티커 사용 현황 조회")
    p_taxonomy.add_argument(
        "--type",
        choices=["all"] + TAXONOMY_TYPE_CHOICES,
        default="all",
        help="taxonomy 유형 필터",
    )
    p_taxonomy.add_argument("--limit", type=int, default=200, help="표시 건수")
    p_taxonomy.add_argument("--format", choices=["md", "csv", "json", "pretty"], default="md", help="출력 포맷")
    p_taxonomy.add_argument("--out", default=None, help="출력 파일 경로")
    p_taxonomy.add_argument(
        "--refresh",
        action="store_true",
        help="SQLite 저장소를 기준으로 taxonomy 사용 횟수와 시각을 재계산",
    )

    p_states = sub.add_parser("states", help="현재/과거 상태 스냅샷 조회")
    p_states.add_argument(
        "--status",
        choices=["all"] + STATE_STATUS_CHOICES,
        default="active",
        help="상태 필터",
    )
    p_states.add_argument("--state-key", default="", help="특정 state_key만 조회")
    p_states.add_argument("--limit", type=int, default=50, help="표시 건수")
    p_states.add_argument("--format", choices=["md", "csv", "json", "pretty"], default="md", help="출력 포맷")
    p_states.add_argument("--out", default=None, help="출력 파일 경로")

    p_state_sync = sub.add_parser("state-sync", help="기존 이슈 로그에서 파생 상태 스냅샷 재구성")
    p_state_sync.add_argument(
        "--keep-derived",
        action="store_true",
        help="기존 derived 상태를 삭제하지 않고 추가만 수행",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "init":
        return _handle_init(args)
    if args.cmd == "add":
        return _handle_add(args)
    if args.cmd == "brief-add":
        return _handle_brief_add(args)
    if args.cmd == "brief-import":
        return _handle_brief_import(args)
    if args.cmd == "list":
        return _handle_list(args)
    if args.cmd == "report":
        return _handle_report(args)
    if args.cmd == "taxonomy":
        return _handle_taxonomy(args)
    if args.cmd == "states":
        return _handle_states(args)
    if args.cmd == "state-sync":
        return _handle_state_sync(args)
    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
