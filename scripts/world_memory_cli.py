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
STORY_RELATION_CHOICES = [
    "evolves_from",
    "branches_from",
    "confirms",
    "conflicts_with",
    "replaces",
    "same_family",
]
SUGGESTION_STATUS_CHOICES = ["suggested", "accepted", "rejected"]
EARNINGS_EVENT_KIND_HINTS = {
    "earnings",
    "earnings_preview",
    "earnings_review",
    "earnings_result",
    "quarterly_results",
    "financial_results",
    "guidance",
    "profit_warning",
}
EARNINGS_TAG_HINTS = {
    "earnings",
    "earning",
    "earnings_season",
    "guidance",
    "eps",
    "revenue",
    "beat",
    "miss",
    "실적",
    "어닝",
    "가이던스",
}
EARNINGS_TEXT_HINTS = (
    "earnings",
    "guidance",
    "eps",
    "revenue",
    "beat",
    "miss",
    "profit warning",
    "results",
    "실적",
    "어닝",
    "가이던스",
    "매출",
    "영업이익",
    "순이익",
)
HIGH_IMPACT_EARNINGS_HINTS = (
    "guidance cut",
    "guidance raise",
    "profit warning",
    "earnings beat",
    "earnings miss",
    "earnings surprise",
    "실적 쇼크",
    "실적 서프라이즈",
    "어닝 쇼크",
    "어닝 서프라이즈",
    "가이던스 상향",
    "가이던스 하향",
)
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
    "story_family",
    "story_relation",
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
TAG_ALIASES: dict[str, str] = {
    "data_center": "data_centers",
    "data_centers": "data_centers",
    "foreign_flow": "foreign_flows",
    "foreign_flows": "foreign_flows",
    "section122": "section_122",
    "section_122": "section_122",
}
INDUSTRY_ALIASES: dict[str, str] = {
    "ai": "artificial_intelligence",
}
DISPLAY_LABELS: dict[str, str] = {
    "ai": "AI",
    "boe": "BoE",
    "bok": "BOK",
    "cpi": "CPI",
    "etf": "ETF",
    "fed": "Fed",
    "fomc": "FOMC",
    "fx": "FX",
    "iea": "IEA",
    "ieepa": "IEEPA",
    "ipo": "IPO",
    "krw": "KRW",
    "ktb": "KTB",
    "pce": "PCE",
    "red_sea": "Red Sea",
    "middle_east": "Middle East",
    "section_122": "Section 122",
    "uk": "UK",
    "us": "US",
}
STORY_RELATION_LABELS: dict[str, str] = {
    "evolves_from": "evolves from",
    "branches_from": "branches from",
    "confirms": "confirms",
    "conflicts_with": "conflicts with",
    "replaces": "replaces",
    "same_family": "same family",
}
REPORT_PRESET_CHOICES = ["default", "recent_industry_trends"]
INDUSTRY_REPORT_EVENT_KINDS = {
    "industry_trend",
    "capital_markets",
    "supply_chain",
    "earnings_review",
    "earnings_result",
    "earnings",
    "earnings_preview",
    "guidance",
    "statement",
    "regulation",
    "litigation",
}
INDUSTRY_REPORT_TAG_HINTS = {
    "ai",
    "artificial_intelligence",
    "semiconductors",
    "semiconductor",
    "software",
    "data_centers",
    "cloud",
    "capex",
    "supply_chain",
    "manufacturing",
    "aerospace",
    "utilities",
    "power",
    "buyback",
    "capital_allocation",
    "capital_markets",
    "productivity",
    "labor",
    "credit",
    "bond_issuance",
}
INDUSTRY_REPORT_TEXT_HINTS = (
    "industry",
    "supply chain",
    "capital spending",
    "capex",
    "factory",
    "shipment",
    "guidance",
    "earnings",
    "data center",
    "cloud",
    "semiconductor",
    "power grid",
    "utilities",
    "labor",
    "production",
    "buyback",
    "capital allocation",
    "산업",
    "공급망",
    "설비투자",
    "반도체",
    "데이터센터",
    "전력망",
    "유틸리티",
    "자사주",
    "주주환원",
    "가이던스",
    "실적",
)
INDUSTRY_REPORT_MACRO_EVENT_KINDS = {
    "macro_data",
}
INDUSTRY_REPORT_MACRO_TAG_HINTS = {
    "tariff",
    "tariffs",
    "trade",
    "trade_policy",
    "section_122",
    "section_301",
    "ieepa",
    "geopolitics",
    "middle_east",
    "iran",
    "war",
    "gdp",
    "cpi",
    "pce",
    "fomc",
    "fed",
    "bok",
    "bo_e",
    "rates",
    "treasury",
    "fx",
    "krw",
    "ndf",
}
INDUSTRY_REPORT_MACRO_TEXT_HINTS = (
    "section 122",
    "section 301",
    "ieepa",
    "global tariff",
    "risk off",
    "hormuz",
    "middle east",
    "gdp",
    "cpi",
    "pce",
    "fomc",
    "fed",
    "boe",
    "bok",
    "금리",
    "관세",
    "지정학",
    "중동",
    "환율",
)


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


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _slug_token(value: str) -> str:
    token = value.strip().lower()
    token = re.sub(r"[^\w가-힣]+", "_", token)
    return re.sub(r"_+", "_", token).strip("_")


def _slug_token_canonical(value: str) -> str:
    token = _normalize_whitespace(value)
    token = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", token)
    token = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", token)
    token = re.sub(r"([A-Za-z])(\d)", r"\1_\2", token)
    token = re.sub(r"(\d)([A-Za-z])", r"\1_\2", token)
    token = token.lower()
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


def _normalize_subject_name(value: str) -> str:
    return _normalize_whitespace(value)


def _normalize_event_kind(value: str) -> str:
    token = _slug_token_canonical(value)
    return token


def _normalize_report_preset(value: str | None) -> str:
    token = _slug_token_canonical(str(value or "").strip())
    if not token:
        return "default"

    mapping = {
        "default": "default",
        "market": "default",
        "market_report": "default",
        "recent_industry_trends": "recent_industry_trends",
        "industry_trends": "recent_industry_trends",
        "industry_under_the_radar": "recent_industry_trends",
        "under_the_radar_industry": "recent_industry_trends",
        "최근_산업계_동향": "recent_industry_trends",
        "최근산업계동향": "recent_industry_trends",
    }
    normalized = mapping.get(token)
    if normalized is None:
        allowed = ", ".join(REPORT_PRESET_CHOICES + ["industry_under_the_radar", "최근 산업계 동향"])
        raise SystemExit(f"Invalid report preset: {value} (allowed: {allowed})")
    return normalized


def _normalize_dedupe_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _normalize_story_label(value: str) -> str:
    return _normalize_whitespace(value)


def _normalize_net_effect(value: str) -> str:
    return _slug_token_canonical(value)


def _normalize_tag(value: str) -> str:
    token = _slug_token_canonical(value)
    if not token:
        return ""
    return TAG_ALIASES.get(token, token)


def _normalize_tags_for_storage(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = _split_csv(value)
    else:
        raw_items = []

    out: list[str] = []
    for raw in raw_items:
        token = _normalize_tag(str(raw))
        if token:
            out.append(token)
    return _unique_preserve_order(out)


def _normalize_industry(value: str) -> str:
    token = _slug_token_canonical(value)
    if not token:
        return ""
    return INDUSTRY_ALIASES.get(token, token)


def _display_token(value: str) -> str:
    token = _normalize_whitespace(value)
    if not token:
        return ""
    return DISPLAY_LABELS.get(token, token.replace("_", " "))


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
    name = _normalize_subject_name(parts[0])
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
            name = _normalize_subject_name(str(raw.get("name", "")))
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
        raw_items = value
    elif isinstance(value, str):
        raw_items = _split_csv(value)
    else:
        raw_items = []

    out: list[str] = []
    for raw in raw_items:
        token = _normalize_industry(str(raw))
        if token:
            out.append(token)
    return _unique_preserve_order(out)


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


def _normalize_story_key(value: str) -> str:
    return _normalize_state_key(value)


def _normalize_story_family_key(value: str) -> str:
    return _normalize_state_key(value)


def _normalize_story_relation(value: str) -> str:
    token = _slug_token_canonical(value)
    mapping = {
        "evolves_from": "evolves_from",
        "evolved_from": "evolves_from",
        "evolves": "evolves_from",
        "branches_from": "branches_from",
        "branched_from": "branches_from",
        "branch": "branches_from",
        "confirms": "confirms",
        "confirm": "confirms",
        "conflicts_with": "conflicts_with",
        "conflicts": "conflicts_with",
        "conflict": "conflicts_with",
        "replaces": "replaces",
        "replace": "replaces",
        "same_family": "same_family",
        "family": "same_family",
        "same": "same_family",
    }
    normalized = mapping.get(token)
    if normalized is None:
        raise SystemExit(
            f"Invalid story relation: {value} (allowed: {', '.join(STORY_RELATION_CHOICES)})"
        )
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS world_issue_story_links (
            link_id TEXT PRIMARY KEY,
            story_key TEXT NOT NULL,
            story_label TEXT NOT NULL,
            related_story_key TEXT NOT NULL,
            related_story_label TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            story_family_key TEXT NOT NULL,
            story_family_label TEXT NOT NULL,
            source_event_id TEXT NOT NULL DEFAULT '',
            source_kind TEXT NOT NULL,
            note TEXT NOT NULL,
            confidence REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (story_key, related_story_key, relation_type, source_event_id, source_kind)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_story_links_story "
        "ON world_issue_story_links(story_key, relation_type, updated_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_story_links_related "
        "ON world_issue_story_links(related_story_key, relation_type, updated_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_story_links_family "
        "ON world_issue_story_links(story_family_key, updated_at DESC)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS world_issue_story_family_suggestions (
            suggestion_id TEXT PRIMARY KEY,
            parent_family_key TEXT NOT NULL,
            parent_family_label TEXT NOT NULL,
            proposed_family_key TEXT NOT NULL,
            proposed_family_label TEXT NOT NULL,
            member_story_keys_json TEXT NOT NULL,
            member_story_labels_json TEXT NOT NULL,
            rationale TEXT NOT NULL,
            confidence REAL NOT NULL,
            status TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            UNIQUE (parent_family_key, proposed_family_key, source_kind, status)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_world_issue_story_family_suggestions_parent "
        "ON world_issue_story_family_suggestions(parent_family_key, status, updated_at DESC)"
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


def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(keyword in lowered for keyword in keywords)


def _has_earnings_signal(*, event_kind: str, tags: list[str], title: str, summary: str) -> bool:
    kind = event_kind.casefold()
    if kind in EARNINGS_EVENT_KIND_HINTS or kind.startswith("earnings"):
        return True

    for tag in tags:
        token = tag.strip().casefold()
        if not token:
            continue
        if token in EARNINGS_TAG_HINTS:
            return True
        if _slug_token(token) in EARNINGS_TAG_HINTS:
            return True

    return _contains_any_keyword(f"{title} {summary}", EARNINGS_TEXT_HINTS)


def _apply_earnings_priority_rules(
    *,
    category: str,
    importance: str,
    entry_mode: str,
    event_kind: str,
    tags: list[str],
    title: str,
    summary: str,
) -> tuple[str, str]:
    if not _has_earnings_signal(event_kind=event_kind, tags=tags, title=title, summary=summary):
        return category, importance

    adjusted_category = category
    if entry_mode == "brief" and category == "emerging":
        adjusted_category = "stock_bond"

    if importance == "high":
        return adjusted_category, importance

    strong_signal = event_kind in EARNINGS_EVENT_KIND_HINTS or _contains_any_keyword(
        f"{title} {summary}",
        HIGH_IMPACT_EARNINGS_HINTS,
    )
    if strong_signal:
        return adjusted_category, "high"
    if importance == "low":
        return adjusted_category, "medium"
    return adjusted_category, importance


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
    story_key: str,
    story_family: str,
    story_thesis: str,
    story_checkpoint: str,
    story_relation: str,
    related_story: str,
    story_note: str,
    story_confidence: float,
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
    if story_key.strip():
        payload["story_key"] = story_key.strip()
    if story_family.strip():
        payload["story_family"] = story_family.strip()
    if story_thesis.strip():
        payload["story_thesis"] = story_thesis.strip()
    if story_checkpoint.strip():
        payload["story_checkpoint"] = story_checkpoint.strip()
    if story_relation.strip():
        payload["story_relation"] = story_relation.strip()
    if related_story.strip():
        payload["related_story"] = related_story.strip()
    if story_note.strip():
        payload["story_note"] = story_note.strip()
    if 0.0 <= float(story_confidence) <= 1.0:
        payload["story_confidence"] = float(story_confidence)
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

    tags = _normalize_tags_for_storage(normalized.get("tags", []))
    subjects = _normalize_subjects_for_storage(normalized.get("subjects", []))
    industries = _normalize_industries_for_storage(normalized.get("industries", []))
    event_kind = _normalize_event_kind(str(normalized.get("event_kind", "")))
    story = _normalize_story_label(str(normalized.get("story", "")))
    story_key_raw = _normalize_whitespace(str(normalized.get("story_key", "")))
    story_family = _normalize_story_label(str(normalized.get("story_family", "")))
    story_thesis = _normalize_whitespace(str(normalized.get("story_thesis", "")))
    story_checkpoint = _normalize_whitespace(str(normalized.get("story_checkpoint", "")))
    story_relation_raw = _normalize_whitespace(str(normalized.get("story_relation", "")))
    related_story = _normalize_story_label(str(normalized.get("related_story", "")))
    story_note = _normalize_whitespace(str(normalized.get("story_note", "")))
    raw_story_confidence = normalized.get("story_confidence")
    why_it_matters = _normalize_whitespace(str(normalized.get("why_it_matters", "")))
    portfolio_link = _normalize_whitespace(str(normalized.get("portfolio_link", "")))
    horizon = _normalize_whitespace(str(normalized.get("horizon", "")))
    story_key = ""
    story_family_key = ""
    story_relation = ""
    related_story_key = ""
    if story:
        if story_key_raw:
            story_key = _normalize_story_key(story_key_raw)
        else:
            story_key = _normalize_story_key(story)
        if story_family:
            story_family_key = _normalize_story_family_key(story_family)
        else:
            story_family = story
            story_family_key = story_key
    elif story_key_raw or story_family or story_relation_raw or related_story or story_note:
        raise ValueError("story lineage metadata requires story")

    if related_story:
        related_story_key = _normalize_story_key(related_story)
    if story_relation_raw:
        story_relation = _normalize_story_relation(story_relation_raw)
    if bool(related_story) != bool(story_relation):
        raise ValueError("story relation requires both related_story and story_relation")
    try:
        story_confidence = float(raw_story_confidence) if raw_story_confidence not in (None, "") else 0.55
    except (TypeError, ValueError):
        story_confidence = 0.55
    story_confidence = min(1.0, max(0.0, story_confidence))
    category, importance = _apply_earnings_priority_rules(
        category=category,
        importance=importance,
        entry_mode=entry_mode,
        event_kind=event_kind,
        tags=tags,
        title=title,
        summary=summary,
    )
    derive_state = _coerce_bool(normalized.get("derive_state"), default=(entry_mode == "issue"))
    dedupe_key = _normalize_dedupe_key(str(normalized.get("dedupe_key", "")))
    sources = _normalize_sources_for_storage(normalized.get("sources"))
    state_key_raw = str(normalized.get("state_key", "")).strip()
    state_label = _normalize_story_label(str(normalized.get("state_label", "")))
    state_status_raw = str(normalized.get("state_status", "")).strip()
    state_bias_raw = str(normalized.get("state_bias", "")).strip()
    net_effect = _normalize_net_effect(str(normalized.get("net_effect", "")))

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
    normalized["why_it_matters"] = why_it_matters
    normalized["portfolio_link"] = portfolio_link
    normalized["horizon"] = horizon
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
    if story:
        normalized["story"] = story
    elif "story" in normalized:
        normalized.pop("story", None)
    if story_key:
        normalized["story_key"] = story_key
    elif "story_key" in normalized:
        normalized.pop("story_key", None)
    if story_family:
        normalized["story_family"] = story_family
        normalized["story_family_key"] = story_family_key
    else:
        normalized.pop("story_family", None)
        normalized.pop("story_family_key", None)
    if story_thesis:
        normalized["story_thesis"] = story_thesis
    elif "story_thesis" in normalized:
        normalized.pop("story_thesis", None)
    if story_checkpoint:
        normalized["story_checkpoint"] = story_checkpoint
    elif "story_checkpoint" in normalized:
        normalized.pop("story_checkpoint", None)
    if story_relation:
        normalized["story_relation"] = story_relation
        normalized["related_story"] = related_story
        normalized["related_story_key"] = related_story_key
        normalized["story_confidence"] = story_confidence
    else:
        normalized.pop("story_relation", None)
        normalized.pop("related_story", None)
        normalized.pop("related_story_key", None)
        normalized.pop("story_confidence", None)
    if story_note:
        normalized["story_note"] = story_note
    elif "story_note" in normalized:
        normalized.pop("story_note", None)
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
    story_family = str(payload.get("story_family_key", "")).strip() or str(payload.get("story_family", "")).strip()
    story_relation = str(payload.get("story_relation", "")).strip()
    related_story = str(payload.get("related_story", "")).strip()
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
    if story_family:
        entries.append(("story_family", story_family, "observed"))
    if story_relation:
        entries.append(("story_relation", story_relation, "observed"))
    if related_story:
        entries.append(("story", related_story, "observed"))
    if event_kind:
        entries.append(("event_kind", event_kind, "observed"))
    if state_key:
        entries.append(("state_key", state_key, "observed"))
    if net_effect:
        entries.append(("net_effect", net_effect, "observed"))

    for tag in [str(item).strip() for item in (payload.get("tags") or []) if str(item).strip()]:
        entries.append(("tag", tag, "observed"))

    for ticker in [str(item).strip().upper() for item in (payload.get("tickers") or []) if str(item).strip()]:
        entries.append(("ticker", ticker, "observed"))

    for subject in payload.get("subjects") or []:
        if not isinstance(subject, dict):
            continue
        name = str(subject.get("name", "")).strip()
        subject_type = str(subject.get("type", "")).strip()
        if name:
            entries.append(("subject", name, "observed"))
        if subject_type:
            entries.append(("subject_type", subject_type, "observed"))

    for industry in [str(item).strip() for item in (payload.get("industries") or []) if str(item).strip()]:
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

    story_link_rows = conn.execute(
        """
        SELECT story_label, related_story_label, story_family_key, story_family_label,
               relation_type, created_at, updated_at
        FROM world_issue_story_links
        """
    ).fetchall()
    for row in story_link_rows:
        _upsert_taxonomy_for_story_link(conn, dict(row))
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
        "story_family": "스토리 패밀리",
        "story_relation": "스토리 관계",
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


def _entry_row_matches_payload(row: sqlite3.Row, payload: dict[str, Any]) -> bool:
    return (
        str(row["event_id"]) == str(payload.get("event_id", ""))
        and str(row["as_of"]) == str(payload.get("as_of", ""))
        and str(row["issue_date"]) == str(payload.get("date", ""))
        and str(row["category"]) == str(payload.get("category", ""))
        and str(row["region"]) == str(payload.get("region", ""))
        and str(row["importance"]) == str(payload.get("importance", ""))
        and str(row["entry_mode"]) == str(payload.get("entry_mode", "issue"))
        and str(row["dedupe_key"]) == str(payload.get("dedupe_key", ""))
        and str(row["logged_at"]) == str(payload.get("logged_at", ""))
        and str(row["title"]) == str(payload.get("title", ""))
    )


def _cleanup_world_issue_entries(conn: sqlite3.Connection) -> tuple[int, int, int]:
    rows = conn.execute(
        """
        SELECT event_id, as_of, issue_date, category, region, importance, entry_mode, dedupe_key,
               logged_at, title, payload_json
        FROM world_issue_entries
        ORDER BY as_of ASC, logged_at ASC
        """
    ).fetchall()

    scanned = 0
    updated = 0
    skipped = 0
    for row in rows:
        scanned += 1
        try:
            parsed = json.loads(str(row["payload_json"]))
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(parsed, dict):
            skipped += 1
            continue
        try:
            normalized = _normalize_payload_for_storage(parsed)
        except ValueError:
            skipped += 1
            continue

        normalized["event_id"] = str(row["event_id"])
        changed = normalized != parsed or not _entry_row_matches_payload(row, normalized)
        if not changed:
            continue
        _upsert_sqlite_payload(conn, normalized)
        updated += 1
    return scanned, updated, skipped


def _build_story_link_payload(
    *,
    story_key: str,
    story_label: str,
    related_story_key: str,
    related_story_label: str,
    relation_type: str,
    story_family_key: str,
    story_family_label: str,
    source_event_id: str,
    source_kind: str,
    note: str,
    confidence: float,
) -> dict[str, Any]:
    now = _kst_now().isoformat()
    return {
        "link_id": str(uuid.uuid4()),
        "story_key": story_key,
        "story_label": story_label,
        "related_story_key": related_story_key,
        "related_story_label": related_story_label,
        "relation_type": relation_type,
        "story_family_key": story_family_key,
        "story_family_label": story_family_label,
        "source_event_id": source_event_id,
        "source_kind": source_kind,
        "note": note,
        "confidence": min(1.0, max(0.0, float(confidence))),
        "created_at": now,
        "updated_at": now,
    }


def _insert_story_link(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    persisted = dict(payload)
    persisted["payload_json"] = json.dumps(payload, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO world_issue_story_links (
            link_id, story_key, story_label, related_story_key, related_story_label,
            relation_type, story_family_key, story_family_label, source_event_id,
            source_kind, note, confidence, created_at, updated_at, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(story_key, related_story_key, relation_type, source_event_id, source_kind) DO UPDATE SET
            story_label=excluded.story_label,
            related_story_label=excluded.related_story_label,
            story_family_key=excluded.story_family_key,
            story_family_label=excluded.story_family_label,
            note=excluded.note,
            confidence=excluded.confidence,
            updated_at=excluded.updated_at,
            payload_json=excluded.payload_json
        """,
        (
            str(payload.get("link_id", "")),
            str(payload.get("story_key", "")),
            str(payload.get("story_label", "")),
            str(payload.get("related_story_key", "")),
            str(payload.get("related_story_label", "")),
            str(payload.get("relation_type", "")),
            str(payload.get("story_family_key", "")),
            str(payload.get("story_family_label", "")),
            str(payload.get("source_event_id", "")),
            str(payload.get("source_kind", "")),
            str(payload.get("note", "")),
            float(payload.get("confidence", 0.55)),
            str(payload.get("created_at", "")),
            str(payload.get("updated_at", "")),
            persisted["payload_json"],
        ),
    )


def _story_link_from_issue_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    story_label = str(payload.get("story", "")).strip()
    related_story_label = str(payload.get("related_story", "")).strip()
    relation_type = str(payload.get("story_relation", "")).strip()
    if not story_label or not related_story_label or not relation_type:
        return None

    story_key = str(payload.get("story_key", "")).strip() or _normalize_story_key(story_label)
    related_story_key = str(payload.get("related_story_key", "")).strip() or _normalize_story_key(related_story_label)
    story_family_label = str(payload.get("story_family", "")).strip() or story_label
    story_family_key = str(payload.get("story_family_key", "")).strip() or _normalize_story_family_key(
        story_family_label
    )
    note = str(payload.get("story_note", "")).strip()
    try:
        confidence = float(payload.get("story_confidence", 0.55))
    except (TypeError, ValueError):
        confidence = 0.55

    return _build_story_link_payload(
        story_key=story_key,
        story_label=story_label,
        related_story_key=related_story_key,
        related_story_label=related_story_label,
        relation_type=relation_type,
        story_family_key=story_family_key,
        story_family_label=story_family_label,
        source_event_id=str(payload.get("event_id", "")).strip(),
        source_kind="issue",
        note=note,
        confidence=confidence,
    )


def _upsert_story_link_for_issue(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any] | None:
    story_link = _story_link_from_issue_payload(payload)
    if story_link is None:
        return None
    _insert_story_link(conn, story_link)
    return story_link


def _sync_story_links(conn: sqlite3.Connection, *, replace_existing: bool) -> int:
    if replace_existing:
        conn.execute("DELETE FROM world_issue_story_links WHERE source_kind = 'issue'")

    rows = conn.execute("SELECT payload_json FROM world_issue_entries ORDER BY as_of ASC, logged_at ASC").fetchall()
    upserted = 0
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
        if _upsert_story_link_for_issue(conn, normalized) is not None:
            upserted += 1
    return upserted


def _story_family_choices_from_links(conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
    rows = conn.execute(
        """
        SELECT story_key, story_label, related_story_key, related_story_label,
               story_family_key, story_family_label, updated_at
        FROM world_issue_story_links
        ORDER BY updated_at DESC, created_at DESC
        """
    ).fetchall()

    votes: dict[str, dict[str, dict[str, Any]]] = {}

    def add_vote(story_key: str, family_key: str, family_label: str, updated_at: str) -> None:
        if not story_key or not family_key:
            return
        family_votes = votes.setdefault(story_key, {})
        bucket = family_votes.setdefault(
            family_key,
            {
                "count": 0,
                "latest": "",
                "family_label": family_label,
            },
        )
        bucket["count"] += 1
        if updated_at >= str(bucket.get("latest", "")):
            bucket["latest"] = updated_at
            bucket["family_label"] = family_label or str(bucket.get("family_label", ""))

    for row in rows:
        family_key = str(row["story_family_key"])
        family_label = str(row["story_family_label"])
        updated_at = str(row["updated_at"])
        add_vote(str(row["story_key"]), family_key, family_label, updated_at)
        add_vote(str(row["related_story_key"]), family_key, family_label, updated_at)

    out: dict[str, dict[str, str]] = {}
    for story_key, family_votes in votes.items():
        best_key = ""
        best_meta: dict[str, Any] | None = None
        for family_key, meta in family_votes.items():
            if best_meta is None:
                best_key = family_key
                best_meta = meta
                continue
            if (
                int(meta.get("count", 0)),
                str(meta.get("latest", "")),
                family_key,
            ) > (
                int(best_meta.get("count", 0)),
                str(best_meta.get("latest", "")),
                best_key,
            ):
                best_key = family_key
                best_meta = meta
        if best_meta is None:
            continue
        out[story_key] = {
            "story_family_key": best_key,
            "story_family_label": str(best_meta.get("family_label", "")) or best_key,
        }
    return out


def _backfill_story_families(conn: sqlite3.Connection) -> tuple[int, int]:
    family_choices = _story_family_choices_from_links(conn)
    if not family_choices:
        return 0, 0

    rows = conn.execute(
        """
        SELECT event_id, payload_json
        FROM world_issue_entries
        ORDER BY as_of ASC, logged_at ASC
        """
    ).fetchall()

    scanned = 0
    updated = 0
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

        story_label = str(normalized.get("story", "")).strip()
        if not story_label:
            continue

        scanned += 1
        story_key = str(normalized.get("story_key", "")).strip() or _normalize_story_key(story_label)
        family = family_choices.get(story_key)
        if family is None:
            continue

        desired_family_key = str(family.get("story_family_key", "")).strip()
        desired_family_label = str(family.get("story_family_label", "")).strip() or story_label
        current_family_key = str(normalized.get("story_family_key", "")).strip()
        current_family_label = str(normalized.get("story_family", "")).strip()
        if current_family_key == desired_family_key and current_family_label == desired_family_label:
            continue

        normalized["event_id"] = str(row["event_id"])
        normalized["story_family_key"] = desired_family_key
        normalized["story_family"] = desired_family_label
        _upsert_sqlite_payload(conn, normalized)
        updated += 1

    return scanned, updated


def _load_story_nodes_for_analysis(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT payload_json
        FROM world_issue_entries
        ORDER BY as_of ASC, logged_at ASC
        """
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
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
        story_label = str(normalized.get("story", "")).strip()
        if not story_label:
            continue
        story_key = str(normalized.get("story_key", "")).strip() or _normalize_story_key(story_label)
        family_label = str(normalized.get("story_family", "")).strip() or story_label
        family_key = str(normalized.get("story_family_key", "")).strip() or story_key
        node = out.get(story_key)
        if node is None:
            node = {
                "story_key": story_key,
                "story_label": story_label,
                "family_key": family_key,
                "family_label": family_label,
                "event_count": 0,
                "latest_as_of": "",
                "tags": set(),
                "industries": set(),
                "tickers": set(),
            }
            out[story_key] = node
        node["event_count"] += 1
        node["tags"].update(str(item).strip() for item in normalized.get("tags", []) if str(item).strip())
        node["industries"].update(
            str(item).strip() for item in normalized.get("industries", []) if str(item).strip()
        )
        node["tickers"].update(str(item).strip() for item in normalized.get("tickers", []) if str(item).strip())
        as_of = str(normalized.get("as_of", ""))
        if as_of >= str(node.get("latest_as_of", "")):
            node["latest_as_of"] = as_of
            node["story_label"] = story_label
            node["family_key"] = family_key
            node["family_label"] = family_label
    return out


def _load_story_links_for_analysis(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT story_key, story_label, related_story_key, related_story_label,
               relation_type, story_family_key, story_family_label, updated_at
        FROM world_issue_story_links
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _story_feature_tokens(node: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    out.update(f"tag:{item}" for item in node.get("tags", set()))
    out.update(f"industry:{item}" for item in node.get("industries", set()))
    out.update(f"ticker:{item}" for item in node.get("tickers", set()))
    return out


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _connected_story_components(
    story_keys: set[str],
    adjacency: dict[str, set[str]],
) -> list[set[str]]:
    remaining = set(story_keys)
    components: list[set[str]] = []
    while remaining:
        root = remaining.pop()
        stack = [root]
        component = {root}
        while stack:
            current = stack.pop()
            for neighbor in adjacency.get(current, set()):
                if neighbor not in remaining:
                    continue
                remaining.remove(neighbor)
                component.add(neighbor)
                stack.append(neighbor)
        components.append(component)
    return components


def _build_story_family_suggestion_payload(
    *,
    parent_family_key: str,
    parent_family_label: str,
    proposed_family_key: str,
    proposed_family_label: str,
    member_story_keys: list[str],
    member_story_labels: list[str],
    rationale: str,
    confidence: float,
    source_kind: str,
) -> dict[str, Any]:
    now = _kst_now().isoformat()
    return {
        "suggestion_id": str(uuid.uuid4()),
        "parent_family_key": parent_family_key,
        "parent_family_label": parent_family_label,
        "proposed_family_key": proposed_family_key,
        "proposed_family_label": proposed_family_label,
        "member_story_keys": member_story_keys,
        "member_story_labels": member_story_labels,
        "rationale": rationale,
        "confidence": min(1.0, max(0.0, float(confidence))),
        "status": "suggested",
        "source_kind": source_kind,
        "created_at": now,
        "updated_at": now,
    }


def _insert_story_family_suggestion(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    persisted = dict(payload)
    persisted["payload_json"] = json.dumps(payload, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO world_issue_story_family_suggestions (
            suggestion_id, parent_family_key, parent_family_label, proposed_family_key,
            proposed_family_label, member_story_keys_json, member_story_labels_json, rationale,
            confidence, status, source_kind, created_at, updated_at, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(parent_family_key, proposed_family_key, source_kind, status) DO UPDATE SET
            parent_family_label=excluded.parent_family_label,
            proposed_family_label=excluded.proposed_family_label,
            member_story_keys_json=excluded.member_story_keys_json,
            member_story_labels_json=excluded.member_story_labels_json,
            rationale=excluded.rationale,
            confidence=excluded.confidence,
            updated_at=excluded.updated_at,
            payload_json=excluded.payload_json
        """,
        (
            str(payload.get("suggestion_id", "")),
            str(payload.get("parent_family_key", "")),
            str(payload.get("parent_family_label", "")),
            str(payload.get("proposed_family_key", "")),
            str(payload.get("proposed_family_label", "")),
            json.dumps(payload.get("member_story_keys", []), ensure_ascii=False),
            json.dumps(payload.get("member_story_labels", []), ensure_ascii=False),
            str(payload.get("rationale", "")),
            float(payload.get("confidence", 0.55)),
            str(payload.get("status", "suggested")),
            str(payload.get("source_kind", "")),
            str(payload.get("created_at", "")),
            str(payload.get("updated_at", "")),
            persisted["payload_json"],
        ),
    )




def _refresh_story_family_split_suggestions(
    conn: sqlite3.Connection, *, replace_existing: bool = True
) -> int:
    def _ensure_list(value):
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [item for item in value if item not in (None, "")]
        return [value]

    def _normalize_token(value: str) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        pieces = []
        last_sep = False
        for ch in text:
            if ch.isalnum() or ord(ch) > 127:
                pieces.append(ch)
                last_sep = False
            else:
                if not last_sep:
                    pieces.append("_")
                    last_sep = True
        return "".join(pieces).strip("_")

    def _make_key(label: str) -> str:
        return _normalize_token(label) or "story_family_branch"

    def _feature_sort_key(token: str):
        prefix, _, _ = token.partition(":")
        order = {
            "industry": 0,
            "tag": 1,
            "event_kind": 2,
            "ticker": 3,
            "region": 4,
            "category": 5,
        }
        return (order.get(prefix, 9), token)

    def _feature_label(token: str, labels: dict) -> str:
        label = labels.get(token) or token.split(":", 1)[-1]
        if token.startswith(("tag:", "industry:", "event_kind:", "region:", "category:")):
            return str(label).replace("_", " ")
        return str(label)

    def _story_features(payload: dict, row: dict):
        tokens = set()
        labels = {}

        for raw in _ensure_list(payload.get("tags")):
            token = _normalize_token(raw)
            if token:
                key = f"tag:{token}"
                tokens.add(key)
                labels[key] = str(raw).strip()

        for raw in _ensure_list(payload.get("tickers")):
            label = str(raw or "").strip().upper()
            if label:
                key = f"ticker:{label}"
                tokens.add(key)
                labels[key] = label

        industry_values = payload.get("industries")
        if industry_values is None:
            industry_values = payload.get("industry")
        for raw in _ensure_list(industry_values):
            token = _normalize_token(raw)
            if token:
                key = f"industry:{token}"
                tokens.add(key)
                labels[key] = str(raw).strip()

        event_values = payload.get("event_kinds")
        if event_values is None:
            event_values = payload.get("event_kind")
        for raw in _ensure_list(event_values):
            token = _normalize_token(raw)
            if token:
                key = f"event_kind:{token}"
                tokens.add(key)
                labels[key] = str(raw).strip()

        region = str(row["region"] if "region" in row.keys() else "").strip()
        if region:
            key = f"region:{_normalize_token(region)}"
            tokens.add(key)
            labels[key] = region

        category = str(row["category"] if "category" in row.keys() else "").strip()
        if category:
            key = f"category:{_normalize_token(category)}"
            tokens.add(key)
            labels[key] = category

        return tokens, labels

    def _connected_components(nodes, adjacency):
        components = []
        seen = set()
        for node in nodes:
            if node in seen:
                continue
            stack = [node]
            component = []
            seen.add(node)
            while stack:
                current = stack.pop()
                component.append(current)
                for neighbor in adjacency.get(current, set()):
                    if neighbor in seen:
                        continue
                    seen.add(neighbor)
                    stack.append(neighbor)
            components.append(sorted(component))
        components.sort(key=lambda item: (-len(item), item))
        return components

    def _branch_cluster(root_key, child_map):
        cluster = {root_key}
        stack = [root_key]
        max_depth = 0
        depth_map = {root_key: 0}
        while stack:
            current = stack.pop()
            depth = depth_map[current]
            max_depth = max(max_depth, depth)
            for child in child_map.get(current, set()):
                if child in cluster:
                    continue
                cluster.add(child)
                depth_map[child] = depth + 1
                stack.append(child)
        return cluster, max_depth

    def _union_features(story_keys, story_data):
        tokens = set()
        for story_key in story_keys:
            tokens.update(story_data[story_key]["features"])
        return tokens

    def _feature_overlap(left_keys, right_keys, story_data):
        left_features = _union_features(left_keys, story_data)
        right_features = _union_features(right_keys, story_data)
        union = left_features | right_features
        if not union:
            return 1.0
        return len(left_features & right_features) / len(union)

    def _top_distinguishing_labels(member_keys, remainder_keys, story_data, limit=3):
        remainder_features = _union_features(remainder_keys, story_data)
        counts = {}
        labels = {}
        for story_key in member_keys:
            info = story_data[story_key]
            for token in info["features"]:
                if token in remainder_features:
                    continue
                counts[token] = counts.get(token, 0) + 1
                labels[token] = _feature_label(token, info["feature_labels"])
        ranked = sorted(counts, key=lambda token: (-counts[token], _feature_sort_key(token)))
        return [labels[token] for token in ranked[:limit]]

    def _proposed_family_label(parent_label, member_keys, remainder_keys, story_data):
        distinguishing = _top_distinguishing_labels(member_keys, remainder_keys, story_data, limit=2)
        if distinguishing:
            suffix = " / ".join(distinguishing)
            return f"{parent_label} - {suffix}"
        lead_label = story_data[member_keys[0]]["label"]
        return f"{parent_label} - {lead_label}"

    rows = conn.execute(
        """
        SELECT title, category, region, payload_json
        FROM world_issue_entries
        WHERE entry_mode = 'issue'
        ORDER BY issue_date ASC, logged_at ASC, as_of ASC
        """
    ).fetchall()

    families = {}
    story_to_family = {}
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except Exception:
            payload = {}
        story_key = str(payload.get("story_key") or "").strip()
        if not story_key:
            continue
        story_label = str(payload.get("story") or row["title"] or story_key).strip()
        family_key = str(payload.get("story_family_key") or story_key).strip() or story_key
        family_label = str(payload.get("story_family") or story_label).strip() or story_label
        family_bucket = families.setdefault(
            family_key,
            {
                "label": family_label,
                "stories": {},
            },
        )
        story_bucket = family_bucket["stories"].setdefault(
            story_key,
            {
                "label": story_label,
                "features": set(),
                "feature_labels": {},
            },
        )
        features, feature_labels = _story_features(payload, row)
        story_bucket["features"].update(features)
        story_bucket["feature_labels"].update(feature_labels)
        story_to_family[story_key] = family_key

    adjacency = {}
    branch_children = {}
    link_rows = conn.execute(
        """
        SELECT story_key, related_story_key, relation_type
        FROM world_issue_story_links
        ORDER BY created_at ASC, updated_at ASC
        """
    ).fetchall()
    for row in link_rows:
        story_key = str(row["story_key"] or "").strip()
        related_key = str(row["related_story_key"] or "").strip()
        if not story_key or not related_key:
            continue
        family_key = story_to_family.get(story_key)
        if not family_key or story_to_family.get(related_key) != family_key:
            continue
        family_stories = families.get(family_key, {}).get("stories", {})
        if story_key not in family_stories or related_key not in family_stories:
            continue
        family_adj = adjacency.setdefault(family_key, {})
        family_adj.setdefault(story_key, set()).add(related_key)
        family_adj.setdefault(related_key, set()).add(story_key)
        if row["relation_type"] == "branches_from":
            family_children = branch_children.setdefault(family_key, {})
            family_children.setdefault(related_key, set()).add(story_key)

    if replace_existing:
        conn.execute("DELETE FROM world_issue_story_family_suggestions WHERE status = 'suggested'")

    refreshed_at = conn.execute(
        "SELECT strftime('%Y-%m-%dT%H:%M:%S', 'now', '+9 hours')"
    ).fetchone()[0]
    stamp_key = conn.execute(
        "SELECT replace(strftime('%Y%m%dT%H%M%f', 'now', '+9 hours'), '.', '')"
    ).fetchone()[0]

    suggestions = {}

    def _register_suggestion(
        family_key,
        family_label,
        member_keys,
        source_kind,
        confidence,
        rationale,
        story_data,
        extra_payload,
    ):
        member_keys = tuple(sorted(set(member_keys)))
        if not member_keys:
            return
        all_story_keys = set(story_data)
        member_key_set = set(member_keys)
        if member_key_set == all_story_keys:
            return
        remainder_keys = tuple(sorted(all_story_keys - member_key_set))
        if not remainder_keys:
            return
        if source_kind == "branch_divergence" and len(member_keys) == 1:
            overlap = _feature_overlap(member_keys, remainder_keys, story_data)
            if (1.0 - overlap) < 0.82:
                return
        proposed_label = _proposed_family_label(family_label, member_keys, remainder_keys, story_data)
        proposed_key = _make_key(proposed_label)
        distinguishing = _top_distinguishing_labels(member_keys, remainder_keys, story_data)
        payload = {
            "member_story_keys": list(member_keys),
            "member_story_labels": [story_data[key]["label"] for key in member_keys],
            "remainder_story_keys": list(remainder_keys),
            "remainder_story_labels": [story_data[key]["label"] for key in remainder_keys],
            "distinguishing_signals": distinguishing,
            **extra_payload,
        }
        suggestion_key = (family_key, member_keys)
        existing = suggestions.get(suggestion_key)
        if existing and existing["confidence"] >= confidence:
            return
        suggestions[suggestion_key] = {
            "parent_family_key": family_key,
            "parent_family_label": family_label,
            "proposed_family_key": proposed_key,
            "proposed_family_label": proposed_label,
            "member_story_keys_json": json.dumps(list(member_keys), ensure_ascii=False),
            "member_story_labels_json": json.dumps([story_data[key]["label"] for key in member_keys], ensure_ascii=False),
            "rationale": rationale,
            "confidence": round(float(confidence), 4),
            "status": "suggested",
            "source_kind": source_kind,
            "created_at": refreshed_at,
            "updated_at": refreshed_at,
            "payload_json": json.dumps(payload, ensure_ascii=False),
        }

    for family_key, family_info in families.items():
        story_data = family_info["stories"]
        if len(story_data) < 3:
            continue
        family_label = family_info["label"]
        story_keys = sorted(story_data)
        family_adj = adjacency.setdefault(family_key, {})
        for story_key in story_keys:
            family_adj.setdefault(story_key, set())
        components = _connected_components(story_keys, family_adj)
        main_component = components[0]
        if len(components) > 1:
            for component in components[1:]:
                if len(component) < 2:
                    continue
                overlap = _feature_overlap(component, main_component, story_data)
                divergence = 1.0 - overlap
                if divergence < 0.35:
                    continue
                distinguishing = _top_distinguishing_labels(component, main_component, story_data)
                rationale = (
                    f"같은 family 안에서 링크 그래프가 분리된 군집으로 끊어져 있습니다. "
                    f"분리 군집 {len(component)}개 스토리의 feature overlap은 {overlap:.2f} 수준이며, "
                    f"주요 분리 신호는 {', '.join(distinguishing) if distinguishing else '별도 신호 누적'}입니다."
                )
                confidence = min(0.92, 0.58 + divergence * 0.25 + min(0.09, max(0, len(component) - 2) * 0.03))
                _register_suggestion(
                    family_key,
                    family_label,
                    component,
                    "disconnected_component",
                    confidence,
                    rationale,
                    story_data,
                    {
                        "overlap": round(overlap, 4),
                        "divergence": round(divergence, 4),
                        "cluster_size": len(component),
                        "main_cluster_size": len(main_component),
                    },
                )

        family_children = branch_children.get(family_key, {})
        for root_key in story_keys:
            cluster, branch_depth = _branch_cluster(root_key, family_children)
            if len(cluster) == 1 and root_key not in family_children:
                continue
            if len(cluster) >= len(story_keys):
                continue
            remainder = sorted(set(story_keys) - cluster)
            if len(remainder) < 2:
                continue
            cluster_keys = sorted(cluster)
            overlap = _feature_overlap(cluster_keys, remainder, story_data)
            divergence = 1.0 - overlap
            distinguishing = _top_distinguishing_labels(cluster_keys, remainder, story_data)
            bridge_edges = 0
            for member_key in cluster_keys:
                bridge_edges += len([neighbor for neighbor in family_adj.get(member_key, set()) if neighbor not in cluster])
            unique_signal_count = len(distinguishing)
            if len(cluster_keys) >= 2:
                if divergence < 0.62 or unique_signal_count < 2 or bridge_edges > max(3, len(cluster_keys) + 1):
                    continue
            else:
                if divergence < 0.84 or unique_signal_count < 3 or bridge_edges > 2:
                    continue
            rationale = (
                f"family 그래프는 아직 연결돼 있지만, 이 branch는 나머지 스토리와 다른 신호로 움직이고 있습니다. "
                f"branch depth {branch_depth}, feature overlap {overlap:.2f}, "
                f"구분 신호는 {', '.join(distinguishing) if distinguishing else '별도 신호 누적'}입니다."
            )
            confidence = min(
                0.84,
                0.42
                + divergence * 0.32
                + min(0.08, unique_signal_count * 0.02)
                + (0.04 if len(cluster_keys) >= 2 else 0.0)
                + min(0.04, branch_depth * 0.02),
            )
            _register_suggestion(
                family_key,
                family_label,
                cluster_keys,
                "branch_divergence",
                confidence,
                rationale,
                story_data,
                {
                    "overlap": round(overlap, 4),
                    "divergence": round(divergence, 4),
                    "branch_depth": branch_depth,
                    "bridge_edges": bridge_edges,
                    "cluster_size": len(cluster_keys),
                },
            )

    inserted = 0
    for index, suggestion in enumerate(sorted(suggestions.values(), key=lambda item: (-item["confidence"], item["parent_family_key"], item["proposed_family_key"])), start=1):
        suggestion_id = f"{stamp_key}:{index}:{suggestion['parent_family_key']}:{suggestion['proposed_family_key']}"
        conn.execute(
            """
            INSERT INTO world_issue_story_family_suggestions (
                suggestion_id,
                parent_family_key,
                parent_family_label,
                proposed_family_key,
                proposed_family_label,
                member_story_keys_json,
                member_story_labels_json,
                rationale,
                confidence,
                status,
                source_kind,
                created_at,
                updated_at,
                payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                suggestion_id,
                suggestion["parent_family_key"],
                suggestion["parent_family_label"],
                suggestion["proposed_family_key"],
                suggestion["proposed_family_label"],
                suggestion["member_story_keys_json"],
                suggestion["member_story_labels_json"],
                suggestion["rationale"],
                suggestion["confidence"],
                suggestion["status"],
                suggestion["source_kind"],
                suggestion["created_at"],
                suggestion["updated_at"],
                suggestion["payload_json"],
            ),
        )
        inserted += 1
    return inserted
def _read_story_family_suggestion_rows(
    *,
    db_path: Path,
    status: str,
    family_filter: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    where: list[str] = []
    params: list[Any] = []
    if status != "all":
        where.append("status = ?")
        params.append(status)
    if family_filter:
        where.append("parent_family_key = ?")
        params.append(_normalize_story_family_key(family_filter))
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    params.append(max(1, limit))
    query = (
        "SELECT suggestion_id, parent_family_key, parent_family_label, proposed_family_key, proposed_family_label, "
        "member_story_keys_json, member_story_labels_json, rationale, confidence, status, source_kind, created_at, updated_at "
        "FROM world_issue_story_family_suggestions "
        f"{where_sql} "
        "ORDER BY updated_at DESC, created_at DESC LIMIT ?"
    )

    out: list[dict[str, Any]] = []
    with _connect_db(db_path) as conn:
        _init_db(conn)
        for row in conn.execute(query, params):
            item = dict(row)
            try:
                item["member_story_keys"] = json.loads(str(item.pop("member_story_keys_json", "[]")))
            except json.JSONDecodeError:
                item["member_story_keys"] = []
            try:
                item["member_story_labels"] = json.loads(str(item.pop("member_story_labels_json", "[]")))
            except json.JSONDecodeError:
                item["member_story_labels"] = []
            out.append(item)
    return out


def _story_family_suggestion_rows_to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    view_rows: list[dict[str, Any]] = []
    for row in rows:
        updated_at = _parse_datetime_safe(row.get("updated_at"))
        members = ", ".join(str(item) for item in row.get("member_story_labels", []) if str(item).strip())
        view_rows.append(
            {
                "Updated (KST)": updated_at.strftime("%Y-%m-%d %H:%M KST") if updated_at else "",
                "Parent Family": str(row.get("parent_family_label", "")),
                "Proposed Family": str(row.get("proposed_family_label", "")),
                "Members": members,
                "Confidence": round(float(row.get("confidence", 0.0)), 2),
                "Status": str(row.get("status", "")),
                "Source Kind": str(row.get("source_kind", "")),
                "Rationale": str(row.get("rationale", "")),
            }
        )
    return pd.DataFrame(view_rows)


def _upsert_taxonomy_for_story_link(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    observed_at = str(row.get("updated_at", "")).strip() or str(row.get("created_at", "")).strip() or _kst_now().isoformat()
    for taxonomy_type, value in (
        ("story", str(row.get("story_label", "")).strip()),
        ("story", str(row.get("related_story_label", "")).strip()),
        ("story_family", str(row.get("story_family_key", "")).strip() or str(row.get("story_family_label", "")).strip()),
        ("story_relation", str(row.get("relation_type", "")).strip()),
    ):
        if not value:
            continue
        _upsert_taxonomy_observation(
            conn,
            taxonomy_type=taxonomy_type,
            value=value,
            observed_at=observed_at,
            source="observed",
        )


def _read_story_link_rows(
    *,
    db_path: Path,
    family_filter: str,
    story_filter: str,
    relation_filter: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    where: list[str] = []
    params: list[Any] = []
    if family_filter:
        where.append("story_family_key = ?")
        params.append(_normalize_story_family_key(family_filter))
    if story_filter:
        story_key = _normalize_story_key(story_filter)
        where.append("(story_key = ? OR related_story_key = ?)")
        params.extend([story_key, story_key])
    if relation_filter and relation_filter != "all":
        where.append("relation_type = ?")
        params.append(_normalize_story_relation(relation_filter))

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    params.append(max(1, limit))
    query = (
        "SELECT link_id, story_key, story_label, related_story_key, related_story_label, relation_type, "
        "story_family_key, story_family_label, source_event_id, source_kind, note, confidence, created_at, updated_at "
        "FROM world_issue_story_links "
        f"{where_sql} "
        "ORDER BY updated_at DESC, created_at DESC LIMIT ?"
    )

    out: list[dict[str, Any]] = []
    with _connect_db(db_path) as conn:
        _init_db(conn)
        for row in conn.execute(query, params):
            out.append(dict(row))
    return out


def _story_link_rows_to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    view_rows: list[dict[str, Any]] = []
    for row in rows:
        updated_at = _parse_datetime_safe(row.get("updated_at"))
        view_rows.append(
            {
                "Updated (KST)": updated_at.strftime("%Y-%m-%d %H:%M KST") if updated_at else "",
                "Family": str(row.get("story_family_label", "")),
                "Story": str(row.get("story_label", "")),
                "Relation": STORY_RELATION_LABELS.get(str(row.get("relation_type", "")), str(row.get("relation_type", ""))),
                "Related Story": str(row.get("related_story_label", "")),
                "Confidence": round(float(row.get("confidence", 0.0)), 2),
                "Source Kind": str(row.get("source_kind", "")),
                "Source Event": str(row.get("source_event_id", "")),
                "Note": str(row.get("note", "")),
            }
        )
    return pd.DataFrame(view_rows)


def _read_story_node_rows(
    *,
    db_path: Path,
    start_date: dt.date,
    end_date: dt.date,
    family_filter: str,
    story_filter: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    query = (
        "SELECT payload_json FROM world_issue_entries "
        "WHERE issue_date >= ? AND issue_date <= ? "
        "ORDER BY as_of DESC, logged_at DESC"
    )
    family_key_filter = _normalize_story_family_key(family_filter) if family_filter else ""
    story_key_filter = _normalize_story_key(story_filter) if story_filter else ""
    nodes: dict[str, dict[str, Any]] = {}
    with _connect_db(db_path) as conn:
        _init_db(conn)
        for record in conn.execute(query, (start_date.isoformat(), end_date.isoformat())):
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
            story_label = str(normalized.get("story", "")).strip()
            if not story_label:
                continue
            story_key = str(normalized.get("story_key", "")).strip() or _normalize_story_key(story_label)
            story_family_label = str(normalized.get("story_family", "")).strip() or story_label
            story_family_key = str(normalized.get("story_family_key", "")).strip() or story_key
            if family_key_filter and story_family_key != family_key_filter:
                continue
            if story_key_filter and story_key != story_key_filter:
                continue

            row = nodes.get(story_key)
            if row is None:
                row = {
                    "story_key": story_key,
                    "story_label": story_label,
                    "story_family_key": story_family_key,
                    "story_family_label": story_family_label,
                    "event_count": 0,
                    "latest_as_of": str(normalized.get("as_of", "")),
                    "latest_title": str(normalized.get("title", "")),
                    "latest_summary": str(normalized.get("summary", "")),
                }
                nodes[story_key] = row
            row["event_count"] += 1
            if str(normalized.get("as_of", "")) >= str(row.get("latest_as_of", "")):
                row["latest_as_of"] = str(normalized.get("as_of", ""))
                row["latest_title"] = str(normalized.get("title", ""))
                row["latest_summary"] = str(normalized.get("summary", ""))

        links = conn.execute(
            "SELECT story_key, related_story_key FROM world_issue_story_links"
        ).fetchall()
        link_counts: dict[str, int] = {}
        for link in links:
            for key in (str(link["story_key"]), str(link["related_story_key"])):
                if not key:
                    continue
                link_counts[key] = link_counts.get(key, 0) + 1

    out = list(nodes.values())
    for row in out:
        row["link_count"] = link_counts.get(str(row.get("story_key", "")), 0)
    out.sort(key=lambda item: (str(item.get("latest_as_of", "")), int(item.get("event_count", 0))), reverse=True)
    return out[: max(1, limit)]


def _story_node_rows_to_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    view_rows: list[dict[str, Any]] = []
    for row in rows:
        latest_as_of = _parse_datetime_safe(row.get("latest_as_of"))
        view_rows.append(
            {
                "Latest (KST)": latest_as_of.strftime("%Y-%m-%d %H:%M KST") if latest_as_of else "",
                "Story": str(row.get("story_label", "")),
                "Story Key": str(row.get("story_key", "")),
                "Family": str(row.get("story_family_label", "")),
                "Events": int(row.get("event_count", 0)),
                "Links": int(row.get("link_count", 0)),
                "Latest Issue": str(row.get("latest_title", "")),
                "Summary": str(row.get("latest_summary", "")),
            }
        )
    return pd.DataFrame(view_rows)


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
    industry_filter = _normalize_industry(str(getattr(args, "industry", "")).strip())
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
        if industry_filter and not any(industry_filter in _normalize_industry(item) for item in industries):
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
            "Tags": ", ".join([_display_token(str(t)) for t in row.get("tags", []) if str(t).strip()]),
            "Sources": _source_names(row),
        }
        if has_brief_fields:
            view_row["Entry Mode"] = _label_entry_mode(str(row.get("entry_mode", "issue")))
            view_row["Subjects"] = _subject_display(row)
            view_row["Industries"] = ", ".join(
                [_display_token(str(item)) for item in row.get("industries", []) if str(item).strip()]
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
    return _display_token(_normalize_tag(tag))


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
        story_key=(args.story_key or "").strip(),
        story_family=(args.story_family or "").strip(),
        story_thesis=(args.story_thesis or "").strip(),
        story_checkpoint=(args.story_checkpoint or "").strip(),
        story_relation=(args.story_relation or "").strip(),
        related_story=(args.related_story or "").strip(),
        story_note=(args.story_note or "").strip(),
        story_confidence=float(getattr(args, "story_confidence", 0.55)),
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
        story_link_payload = _upsert_story_link_for_issue(conn, normalized_payload)
        _upsert_taxonomy_for_payload(conn, normalized_payload)
        if story_link_payload is not None:
            _upsert_taxonomy_for_story_link(conn, story_link_payload)
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
        story_key="",
        story_family="",
        story_thesis="",
        story_checkpoint="",
        story_relation="",
        related_story="",
        story_note="",
        story_confidence=0.55,
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
            story_link_payload = _upsert_story_link_for_issue(conn, payload)
            _upsert_taxonomy_for_payload(conn, payload)
            if story_link_payload is not None:
                _upsert_taxonomy_for_story_link(conn, story_link_payload)
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


def _handle_cleanup(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    with _connect_db(db_path) as conn:
        _init_db(conn)
        scanned, updated, skipped = _cleanup_world_issue_entries(conn)
        inserted, skipped_manual = _sync_derived_states(conn, replace_existing=True)
        story_links_upserted = _sync_story_links(conn, replace_existing=True)
        family_scanned, family_updated = _backfill_story_families(conn)
        story_links_upserted = _sync_story_links(conn, replace_existing=True)
        family_split_suggestions = _refresh_story_family_split_suggestions(conn, replace_existing=True)
        processed = _rebuild_taxonomy_index(conn)
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()

    mode = "Dry run" if args.dry_run else "Cleanup completed"
    print(f"{mode}: scanned={scanned} updated={updated} skipped={skipped}")
    print(f"Derived states synced: inserted={inserted} skipped_manual={skipped_manual}")
    print(f"Story links synced: upserted={story_links_upserted}")
    print(f"Story families backfilled: scanned={family_scanned} updated={family_updated}")
    print(f"Story family split suggestions: suggested={family_split_suggestions}")
    print(f"Refreshed taxonomy index from {processed} world issue rows")
    print(f"SQLite store: {db_path}")
    return 0


def _handle_story_link(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    story_label = _normalize_story_label(args.story or "")
    related_story_label = _normalize_story_label(args.related_story or "")
    if not story_label or not related_story_label:
        raise SystemExit("story-link requires --story and --related-story")

    story_key = _normalize_story_key(args.story_key or story_label)
    related_story_key = _normalize_story_key(args.related_story_key or related_story_label)
    family_label = _normalize_story_label(args.story_family or story_label)
    family_key = _normalize_story_family_key(args.story_family or story_label)
    relation_type = _normalize_story_relation(args.relation)
    try:
        confidence = float(args.confidence)
    except (TypeError, ValueError):
        confidence = 0.55
    confidence = min(1.0, max(0.0, confidence))

    payload = _build_story_link_payload(
        story_key=story_key,
        story_label=story_label,
        related_story_key=related_story_key,
        related_story_label=related_story_label,
        relation_type=relation_type,
        story_family_key=family_key,
        story_family_label=family_label,
        source_event_id=str(args.source_event_id or "").strip(),
        source_kind="manual",
        note=_normalize_whitespace(args.note or ""),
        confidence=confidence,
    )
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    with _connect_db(db_path) as conn:
        _init_db(conn)
        _insert_story_link(conn, payload)
        family_scanned, family_updated = _backfill_story_families(conn)
        _sync_story_links(conn, replace_existing=True)
        _upsert_taxonomy_for_story_link(conn, payload)
        _rebuild_taxonomy_index(conn)
        conn.commit()

    print(f"Upserted story link: {db_path}")
    print(f"story={payload['story_label']}")
    print(f"relation={payload['relation_type']}")
    print(f"related_story={payload['related_story_label']}")
    print(f"story_families_backfilled={family_updated}/{family_scanned}")
    return 0


def _handle_story_map(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    start_date, end_date = _resolve_date_window(args)
    if args.view == "links":
        rows = _read_story_link_rows(
            db_path=db_path,
            family_filter=str(args.family or "").strip(),
            story_filter=str(args.story or "").strip(),
            relation_filter=str(args.relation or "all").strip(),
            limit=max(1, args.limit),
        )
        if args.format == "json":
            payload = {"db_path": str(db_path), "count": len(rows), "rows": rows}
            _emit_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", args.out)
            return 0
        _emit_dataframe(_story_link_rows_to_frame(rows), args.format, args.out)
        return 0

    rows = _read_story_node_rows(
        db_path=db_path,
        start_date=start_date,
        end_date=end_date,
        family_filter=str(args.family or "").strip(),
        story_filter=str(args.story or "").strip(),
        limit=max(1, args.limit),
    )
    if args.format == "json":
        payload = {"db_path": str(db_path), "count": len(rows), "rows": rows}
        _emit_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", args.out)
        return 0
    _emit_dataframe(_story_node_rows_to_frame(rows), args.format, args.out)
    return 0


def _handle_story_family_review(args: argparse.Namespace) -> int:
    db_path = _ensure_db(args.base_dir, args.db_file)
    if args.refresh:
        with _connect_db(db_path) as conn:
            _init_db(conn)
            _refresh_story_family_split_suggestions(conn, replace_existing=True)
            conn.commit()

    rows = _read_story_family_suggestion_rows(
        db_path=db_path,
        status=str(args.status or "suggested"),
        family_filter=str(args.family or "").strip(),
        limit=max(1, int(args.limit)),
    )
    if args.format == "json":
        payload = {"db_path": str(db_path), "count": len(rows), "rows": rows}
        _emit_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", args.out)
        return 0
    _emit_dataframe(_story_family_suggestion_rows_to_frame(rows), args.format, args.out)
    return 0


def _pick_non_dominant_rows(rows: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
    emerging_rows = [r for r in rows if str(r.get("category", "")) == "emerging"]
    if emerging_rows:
        return emerging_rows[:max_items]

    low_priority = [r for r in rows if str(r.get("importance", "")) == "low"]
    return low_priority[:max_items]


def _row_text_blob(row: dict[str, Any]) -> str:
    fields = [
        str(row.get("title", "")).strip(),
        str(row.get("summary", "")).strip(),
        str(row.get("why_it_matters", "")).strip(),
        str(row.get("portfolio_link", "")).strip(),
        str(row.get("story", "")).strip(),
        str(row.get("story_thesis", "")).strip(),
        str(row.get("story_checkpoint", "")).strip(),
    ]
    return " ".join([item for item in fields if item]).casefold()


def _has_industry_subject(row: dict[str, Any]) -> bool:
    for item in row.get("subjects", []):
        if not isinstance(item, dict):
            continue
        subject_type = str(item.get("type", "")).strip().lower()
        if subject_type in {"company", "business_leader", "industry", "market_actor"}:
            return True
    return False


def _is_industry_report_candidate(row: dict[str, Any]) -> bool:
    category = str(row.get("category", "")).strip()
    event_kind = _normalize_event_kind(str(row.get("event_kind", "")))
    tags = [_normalize_tag(str(item)) for item in row.get("tags", []) if str(item).strip()]
    industries = _normalize_industries_for_storage(row.get("industries", []))
    text_blob = _row_text_blob(row)

    has_industry = bool(industries)
    has_subject = _has_industry_subject(row)
    has_event = event_kind in INDUSTRY_REPORT_EVENT_KINDS
    has_tag = any(tag in INDUSTRY_REPORT_TAG_HINTS for tag in tags)
    has_text = _contains_any_keyword(text_blob, INDUSTRY_REPORT_TEXT_HINTS)

    if not (has_industry or has_subject or has_event or has_tag or has_text):
        return False

    macro_event = event_kind in INDUSTRY_REPORT_MACRO_EVENT_KINDS
    macro_tag = any(tag in INDUSTRY_REPORT_MACRO_TAG_HINTS for tag in tags)
    macro_text = _contains_any_keyword(text_blob, INDUSTRY_REPORT_MACRO_TEXT_HINTS)

    # 지정학/매크로 헤드라인만 있는 행은 제외하고 산업 실행 신호를 우선 포착한다.
    if category == "geopolitics" and not (has_industry or has_subject):
        return False
    if macro_event and not (has_industry or has_subject or has_event):
        return False
    if macro_tag and not (has_industry or has_subject or has_event):
        return False
    if macro_text and not (has_industry or has_subject or has_event):
        return False

    return True


def _industry_row_score(row: dict[str, Any], *, end_date: dt.date) -> float:
    as_of = _issue_as_of(row)
    days_old = max(0, (end_date - as_of.date()).days)
    recency_score = max(0.0, 30.0 - float(days_old)) / 5.0

    importance = str(row.get("importance", "medium")).strip()
    importance_score = {
        "high": 2.2,
        "medium": 1.8,
        "low": 1.2,
    }.get(importance, 1.0)

    entry_mode = str(row.get("entry_mode", "issue")).strip()
    entry_mode_score = 1.0 if entry_mode == "brief" else 0.45

    category = str(row.get("category", "")).strip()
    category_score = {
        "stock_bond": 0.5,
        "emerging": 0.8,
        "geopolitics": -0.3,
    }.get(category, 0.0)

    event_kind = _normalize_event_kind(str(row.get("event_kind", "")))
    event_score = 0.0
    if event_kind in {"industry_trend", "capital_markets", "supply_chain"}:
        event_score += 1.2
    elif event_kind in {"earnings", "earnings_review", "earnings_result", "guidance"}:
        event_score += 0.9
    elif event_kind in {"statement", "regulation", "litigation"}:
        event_score += 0.6

    industries = _normalize_industries_for_storage(row.get("industries", []))
    if industries:
        event_score += 0.9
    if _has_industry_subject(row):
        event_score += 0.4

    return recency_score + importance_score + entry_mode_score + category_score + event_score


def _select_recent_industry_rows(
    rows: list[dict[str, Any]],
    *,
    end_date: dt.date,
    max_items: int,
) -> list[dict[str, Any]]:
    scored_rows: list[tuple[float, dt.datetime, dict[str, Any]]] = []
    for row in rows:
        if not _is_industry_report_candidate(row):
            continue
        score = _industry_row_score(row, end_date=end_date)
        scored_rows.append((score, _issue_as_of(row), row))

    scored_rows.sort(key=lambda item: (item[0], item[1]), reverse=True)

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, _, row in scored_rows:
        story_key = str(row.get("story_key", "")).strip()
        story_label = str(row.get("story", "")).strip()
        title_key = _normalize_dedupe_key(str(row.get("title", "")))
        dedupe_key = story_key or story_label or title_key
        if dedupe_key and dedupe_key in seen:
            continue
        if dedupe_key:
            seen.add(dedupe_key)
        out.append(row)
        if len(out) >= max(1, max_items * 3):
            break
    return out


def _industry_focus_label(row: dict[str, Any]) -> str:
    industries = [
        _display_token(str(item))
        for item in row.get("industries", [])
        if str(item).strip()
    ]
    industries = _unique_preserve_order(industries)
    subjects = _subject_display(row)
    if industries and subjects:
        return f"{', '.join(industries[:2])} / {subjects}"
    if industries:
        return ", ".join(industries[:2])
    if subjects:
        return subjects

    tags = [
        _display_token(_normalize_tag(str(item)))
        for item in row.get("tags", [])
        if str(item).strip()
    ]
    tags = [tag for tag in _unique_preserve_order(tags) if tag]
    if tags:
        return ", ".join(tags[:2])
    return "-"


def _industry_table_for_report(rows: list[dict[str, Any]], *, max_items: int) -> str:
    if not rows:
        return "해당 기간 산업계 동향 후보가 충분하지 않습니다.\n"

    view_rows: list[dict[str, Any]] = []
    for row in rows[: max(1, max_items)]:
        why = str(row.get("why_it_matters", "")).strip() or str(row.get("summary", "")).strip()
        if not why:
            why = str(row.get("portfolio_link", "")).strip()
        view_rows.append(
            {
                "시각(KST)": _format_as_of_text(row),
                "산업/주체": _industry_focus_label(row),
                "관찰 포인트": str(row.get("title", "")).strip(),
                "왜 중요한가": why,
                "출처": _source_names(row),
            }
        )
    return _dataframe_to_markdown(pd.DataFrame(view_rows))


def _collect_industry_checkpoints(rows: list[dict[str, Any]], *, max_items: int) -> list[str]:
    checkpoints: list[str] = []
    seen: set[str] = set()
    for row in rows:
        checkpoint = str(row.get("story_checkpoint", "")).strip()
        if not checkpoint:
            focus = _industry_focus_label(row)
            title = str(row.get("title", "")).strip()
            if focus != "-":
                checkpoint = f"{focus}: {title}의 후속 지표/공시 확인"
            else:
                checkpoint = f"{title}의 후속 지표/공시 확인"
        key = _normalize_dedupe_key(checkpoint)
        if not key or key in seen:
            continue
        seen.add(key)
        checkpoints.append(checkpoint)
        if len(checkpoints) >= max(1, max_items):
            break
    return checkpoints


def _build_recent_industry_report_text(
    rows: list[dict[str, Any]],
    *,
    start_date: dt.date,
    end_date: dt.date,
    max_items: int,
    db_path: Path,
    title: str | None,
) -> str:
    now = _kst_now()
    candidate_rows = _select_recent_industry_rows(rows, end_date=end_date, max_items=max_items)

    primary_rows = candidate_rows[: max(1, max_items)]
    under_radar_rows = [row for row in candidate_rows if str(row.get("importance", "")) != "high"]
    if not under_radar_rows:
        under_radar_rows = candidate_rows[max_items : max_items * 2]
    under_radar_rows = under_radar_rows[: max(1, max_items)]

    latest = _format_as_of_text(candidate_rows[0]) if candidate_rows else "-"
    high, medium, low = _count_by_importance(candidate_rows)
    checkpoints = _collect_industry_checkpoints(
        primary_rows + under_radar_rows,
        max_items=max(4, min(8, max_items + 2)),
    )

    lines: list[str] = []
    lines.append(f"# {title or '최근 산업계 동향'}")
    lines.append("")
    lines.append("## 메타")
    lines.append(f"- 작성 시각(KST): {now.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- 데이터 범위(KST): {start_date.isoformat()} ~ {end_date.isoformat()}")
    lines.append(f"- 최신 로그 시각(KST): {latest}")
    lines.append(f"- 저장소(SQLite): `{db_path}`")
    lines.append("")

    lines.append("## 1) 흐름 요약")
    if candidate_rows:
        lines.append(f"- 산업 동향 후보: 총 {len(candidate_rows)}건 (상/중/하 = {high}/{medium}/{low})")
        lines.append("- 매크로/메가톤 헤드라인은 줄이고, 기업·산업 실행 신호를 우선 반영했다.")
    else:
        lines.append("- 해당 기간에 산업 동향 후보가 충분하지 않았다.")
        lines.append("- 조회 기간을 늘리거나 brief 로그를 보강하면 더 안정적으로 추출할 수 있다.")
    lines.append("")

    lines.append("## 2) 최근 산업계 동향 핵심 축")
    lines.append(
        _story_table_for_report(
            candidate_rows,
            end_date=end_date,
            max_items=min(5, max_items),
            recent_days=min(14, max(7, (end_date - start_date).days + 1)),
        ).rstrip()
    )
    lines.append("")

    lines.append("## 3) 최근 산업계 동향 (핵심 사례)")
    lines.append(_industry_table_for_report(primary_rows, max_items=max_items).rstrip())
    lines.append("")

    lines.append("## 4) 메가뉴스에 가려지기 쉬운 신호")
    lines.append(_industry_table_for_report(under_radar_rows, max_items=max_items).rstrip())
    lines.append("")

    lines.append("## 5) 다음 체크포인트")
    if checkpoints:
        for idx, checkpoint in enumerate(checkpoints, start=1):
            lines.append(f"{idx}. {checkpoint}")
    else:
        lines.append("1. 산업계 동향 후보가 부족해 추가 체크포인트를 생성하지 못했다.")
    lines.append("")

    lines.append("## 결론")
    if candidate_rows:
        lines.append("거시 헤드라인과 별개로 산업계에서는 투자·생산·자금조달 같은 실행 지표가 계속 갱신되고 있다.")
        lines.append("특히 산업/주체가 명확한 브리프와 자본시장 이벤트가 동시 관찰될 때 흐름의 지속 확률이 높아진다.")
        lines.append("다음 액션은 뉴스 자체보다 후속 공시·가이던스·수급 지표로 검증 강도를 높이는 것이다.")
    else:
        lines.append("현재 데이터만으로는 산업계 독립 흐름을 충분히 분리하기 어렵다.")
        lines.append("brief 로그 보강과 기간 확장 후 재생성해 노이즈를 줄이는 접근이 필요하다.")
    lines.append("")

    return "\n".join(lines)


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
    preset = _normalize_report_preset(getattr(args, "preset", None))
    if preset == "recent_industry_trends" and str(getattr(args, "entry_mode", "issue")).strip() == "issue":
        # 산업 동향 프리셋은 brief까지 함께 보는 편이 유리해 기본 issue 필터를 확장한다.
        setattr(args, "entry_mode", "all")

    filtered, _backend, db_path, start_date, end_date = _load_filtered_rows(args)
    max_items = max(1, args.max_items)

    if preset == "recent_industry_trends":
        report_text = _build_recent_industry_report_text(
            filtered,
            start_date=start_date,
            end_date=end_date,
            max_items=max_items,
            db_path=db_path,
            title=args.title or "최근 산업계 동향",
        )
    else:
        filtered = [
            row for row in filtered if _normalize_entry_mode(str(row.get("entry_mode", "issue"))) == "issue"
        ]
        state_rows = _read_current_state_rows(
            db_path=db_path,
            limit=max_items,
        )

        report_text = _build_report_text(
            filtered,
            state_rows=state_rows,
            start_date=start_date,
            end_date=end_date,
            max_items=max_items,
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
    p_add.add_argument("--event-kind", default="", help="이벤트 유형 (예: earnings_review, regulation, statement, industry_trend)")
    p_add.add_argument("--story", default="", help="시장 스토리 라벨 (예: 디스인플레이션+성장 둔화)")
    p_add.add_argument("--story-key", default="", help="스토리 안정 키(옵션, 기본: story 라벨에서 자동 생성)")
    p_add.add_argument("--story-family", default="", help="스토리 패밀리 라벨(옵션, 기본: story)")
    p_add.add_argument("--story-thesis", default="", help="스토리 핵심 테제 1문장")
    p_add.add_argument("--story-checkpoint", default="", help="스토리 체크포인트(무효화/확인 조건)")
    p_add.add_argument(
        "--story-relation",
        choices=STORY_RELATION_CHOICES,
        default="",
        help="이전/인접 스토리와의 관계",
    )
    p_add.add_argument("--related-story", default="", help="연결할 다른 스토리 라벨")
    p_add.add_argument("--story-note", default="", help="스토리 관계에 대한 메모")
    p_add.add_argument("--story-confidence", type=float, default=0.55, help="스토리 관계 신뢰도 (0~1)")
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
    p_brief.add_argument("--event-kind", default="", help="이벤트 유형 (예: earnings, earnings_review, statement, industry_trend)")
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

    p_report = sub.add_parser("report", help="시장/산업 동향 보고서 생성")
    p_report.add_argument("--start", type=_parse_date, default=None, help="시작일 (YYYY-MM-DD)")
    p_report.add_argument("--end", type=_parse_date, default=None, help="종료일 (YYYY-MM-DD, 기본: 오늘 KST)")
    p_report.add_argument("--days", type=int, default=14, help="start 미지정 시 최근 조회 기간(일)")
    p_report.add_argument(
        "--entry-mode",
        choices=["all"] + ENTRY_MODE_CHOICES,
        default="issue",
        help="엔트리 모드 필터 (preset=recent_industry_trends에서는 issue 기본값을 all로 자동 확장)",
    )
    p_report.add_argument("--max-items", type=int, default=6, help="섹션별 최대 이슈 건수")
    p_report.add_argument(
        "--preset",
        default="default",
        help="보고서 프리셋 (default | recent_industry_trends | industry_under_the_radar | 최근 산업계 동향)",
    )
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

    p_cleanup = sub.add_parser("cleanup", help="저장된 월드 메모리 payload와 taxonomy/state 인덱스를 정리")
    p_cleanup.add_argument(
        "--dry-run",
        action="store_true",
        help="변경 예정 건수만 계산하고 SQLite에는 반영하지 않음",
    )

    p_story_link = sub.add_parser("story-link", help="스토리 간 수동 관계를 기록")
    p_story_link.add_argument("--story", required=True, help="현재 스토리 라벨")
    p_story_link.add_argument("--story-key", default="", help="현재 스토리 안정 키(옵션)")
    p_story_link.add_argument("--related-story", required=True, help="연결 대상 스토리 라벨")
    p_story_link.add_argument("--related-story-key", default="", help="연결 대상 스토리 안정 키(옵션)")
    p_story_link.add_argument("--relation", choices=STORY_RELATION_CHOICES, required=True, help="스토리 관계 타입")
    p_story_link.add_argument("--story-family", default="", help="스토리 패밀리 라벨(옵션, 기본: story)")
    p_story_link.add_argument("--source-event-id", default="", help="관련 event_id가 있으면 연결")
    p_story_link.add_argument("--note", default="", help="관계 메모")
    p_story_link.add_argument("--confidence", type=float, default=0.7, help="관계 신뢰도 (0~1)")
    p_story_link.add_argument("--dry-run", action="store_true", help="저장 없이 payload 확인")

    p_story_map = sub.add_parser("story-map", help="스토리 노드/링크 맵 조회")
    p_story_map.add_argument("--view", choices=["nodes", "links"], default="nodes", help="조회 뷰")
    p_story_map.add_argument("--start", type=_parse_date, default=None, help="시작일 (YYYY-MM-DD)")
    p_story_map.add_argument("--end", type=_parse_date, default=None, help="종료일 (YYYY-MM-DD, 기본: 오늘 KST)")
    p_story_map.add_argument("--days", type=int, default=90, help="start 미지정 시 최근 조회 기간(일)")
    p_story_map.add_argument("--family", default="", help="스토리 패밀리 필터")
    p_story_map.add_argument("--story", default="", help="스토리 필터")
    p_story_map.add_argument(
        "--relation",
        choices=["all"] + STORY_RELATION_CHOICES,
        default="all",
        help="links 뷰용 관계 필터",
    )
    p_story_map.add_argument("--limit", type=int, default=50, help="표시 건수")
    p_story_map.add_argument("--format", choices=["md", "csv", "json", "pretty"], default="md", help="출력 포맷")
    p_story_map.add_argument("--out", default=None, help="출력 파일 경로")

    p_story_family_review = sub.add_parser("story-family-review", help="패밀리 분가 제안 조회")
    p_story_family_review.add_argument(
        "--status",
        choices=["all"] + SUGGESTION_STATUS_CHOICES,
        default="suggested",
        help="제안 상태 필터",
    )
    p_story_family_review.add_argument("--family", default="", help="상위 패밀리 필터")
    p_story_family_review.add_argument("--limit", type=int, default=50, help="표시 건수")
    p_story_family_review.add_argument("--format", choices=["md", "csv", "json", "pretty"], default="md", help="출력 포맷")
    p_story_family_review.add_argument("--out", default=None, help="출력 파일 경로")
    p_story_family_review.add_argument(
        "--refresh",
        action="store_true",
        help="현재 DB를 기준으로 분가 제안을 재계산",
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
    if args.cmd == "cleanup":
        return _handle_cleanup(args)
    if args.cmd == "story-link":
        return _handle_story_link(args)
    if args.cmd == "story-map":
        return _handle_story_map(args)
    if args.cmd == "story-family-review":
        return _handle_story_family_review(args)
    if args.cmd == "states":
        return _handle_states(args)
    if args.cmd == "state-sync":
        return _handle_state_sync(args)
    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
