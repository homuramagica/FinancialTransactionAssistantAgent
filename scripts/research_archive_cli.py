#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import news_update_harness as news_harness  # noqa: E402
from scripts import safari_fetch as safari_fetch  # noqa: E402


DEFAULT_TZ = "Asia/Seoul"
DEFAULT_WORKSPACE = "."
DEFAULT_RESEARCH_DIRNAME = "Research"
DEFAULT_DB_NAME = "research_archive.sqlite3"
EMBED_DIM = 384
DEFAULT_CHUNK_TARGET_CHARS = 1200
DEFAULT_CHUNK_OVERLAP_CHARS = 200
DEFAULT_RESEARCH_SITE_THROTTLE_SECONDS = 15.0

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")
MD_META_RE = re.compile(r"^- (?P<key>[^:]+): (?P<value>.*)$")
WHITESPACE_RE = re.compile(r"\s+")
PUBLISHED_PATTERNS = (
    re.compile(
        r'<meta[^>]+(?:property|name)=["\'](?:article:published_time|og:article:published_time|parsely-pub-date|date)["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(r'"datePublished"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"dateCreated"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'<time[^>]+datetime=["\']([^"\']+)["\']', re.IGNORECASE),
)
TITLE_PATTERNS = (
    re.compile(
        r'<meta[^>]+(?:property|name)=["\'](?:og:title|twitter:title)["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL),
)
URL_DATE_RE = re.compile(r"/((?:19|20)\d{2})/(\d{2})/(\d{2})(?:/|$)")
TEXT_TITLE_PATTERNS = (
    re.compile(r"\n([^\n]{10,180})\nBy\s*\nPublished\b", re.IGNORECASE),
    re.compile(r"\n([^\n]{10,180})\nPublished\b", re.IGNORECASE),
    re.compile(r"\n([^\n]{10,180})\nBloomberg News\s*\n[A-Z][a-z]+ \d{1,2}, \d{4}\b", re.IGNORECASE),
)
TEXT_PUBLISHED_PATTERNS = (
    re.compile(r"\bPublished\s+(\d{2}/\d{2}/\d{4}),\s*\d{1,2}:\d{2}\s*[AP]M\b", re.IGNORECASE),
    re.compile(r"\bPublished\s+[A-Za-z]{3},\s+([A-Za-z]{3}\s+\d{1,2}\s+\d{4})\d{1,2}:\d{2}\s*[AP]M\b"),
    re.compile(r"\bPublished\s+[A-Za-z]{3},\s+([A-Za-z]{3}\s+\d{1,2}\s+\d{4})\s+\d{1,2}:\d{2}\s*[AP]M\b"),
    re.compile(r"\bUpdated\s+([A-Za-z]{3}\s+\d{1,2},\s+\d{4})\s+\d{1,2}:\d{2}[AP]M\b", re.IGNORECASE),
    re.compile(r"\b([A-Z][a-z]+ \d{1,2}, \d{4})\b"),
)


@dataclass
class ArticlePayload:
    title: str
    source: str
    url: str
    published_at: str
    retrieved_at_kst: str
    body: str
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    file_path: str = ""


def _research_dir(workspace: str | Path) -> Path:
    return Path(workspace).resolve() / DEFAULT_RESEARCH_DIRNAME


def _default_db_path(workspace: str | Path) -> Path:
    return _research_dir(workspace) / DEFAULT_DB_NAME


def _kst_now() -> dt.datetime:
    return dt.datetime.now(tz=ZoneInfo(DEFAULT_TZ))


def _normalize_spaces(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def _normalize_lower(text: str) -> str:
    return _normalize_spaces(text).lower()


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        token = str(item).strip()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _normalize_tag(tag: str) -> str:
    raw = unicodedata.normalize("NFC", tag).strip().lower()
    raw = re.sub(r"[^0-9a-z가-힣]+", "_", raw)
    return raw.strip("_")


def _token_set(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def _keyword_overlap_score(query: str, candidate: str) -> float:
    query_tokens = _token_set(query)
    candidate_tokens = _token_set(candidate)
    if not query_tokens or not candidate_tokens:
        return 0.0
    overlap = len(query_tokens & candidate_tokens)
    denom = max(1, min(len(query_tokens), len(candidate_tokens)))
    return overlap / float(denom)


def _char_ngrams(text: str, min_n: int = 2, max_n: int = 4) -> list[str]:
    normalized = _normalize_lower(text)
    if not normalized:
        return []
    chars = list(normalized)
    out: list[str] = []
    for n in range(min_n, max_n + 1):
        if len(chars) < n:
            continue
        for idx in range(0, len(chars) - n + 1):
            ngram = "".join(chars[idx : idx + n])
            if ngram.strip():
                out.append(ngram)
    return out


def _stable_hash_index(token: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big", signed=False)
    idx = value % dim
    sign = -1.0 if (value & 1) else 1.0
    return idx, sign


def _embed_text(text: str, *, dim: int = EMBED_DIM) -> list[float]:
    vec = [0.0] * dim
    for token in _char_ngrams(text):
        idx, sign = _stable_hash_index(token, dim)
        vec[idx] += sign
    norm = math.sqrt(sum(value * value for value in vec))
    if norm <= 0:
        return vec
    return [value / norm for value in vec]


def _parse_embedding(raw: str) -> list[float]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return [0.0] * EMBED_DIM
    if not isinstance(payload, list):
        return [0.0] * EMBED_DIM
    values: list[float] = []
    for item in payload[:EMBED_DIM]:
        try:
            values.append(float(item))
        except Exception:
            values.append(0.0)
    if len(values) < EMBED_DIM:
        values.extend([0.0] * (EMBED_DIM - len(values)))
    return values


def _cosine(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    size = min(len(vec_a), len(vec_b))
    return sum(vec_a[idx] * vec_b[idx] for idx in range(size))


def _connect_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextlib.contextmanager
def _temporary_site_throttle(interval_seconds: float):
    key = "NEWS_FETCH_SITE_THROTTLE_INTERVAL_SECONDS"
    previous = os.environ.get(key)
    os.environ[key] = str(float(interval_seconds))
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            article_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            published_at TEXT,
            retrieved_at_kst TEXT NOT NULL,
            file_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS article_chunks (
            chunk_id TEXT PRIMARY KEY,
            article_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            FOREIGN KEY(article_id) REFERENCES articles(article_id) ON DELETE CASCADE,
            UNIQUE(article_id, chunk_index)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS article_tags (
            article_id TEXT NOT NULL,
            tag TEXT NOT NULL,
            FOREIGN KEY(article_id) REFERENCES articles(article_id) ON DELETE CASCADE,
            UNIQUE(article_id, tag)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_article_chunks_article_id ON article_chunks(article_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_article_tags_tag ON article_tags(tag)")
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS article_chunks_fts
            USING fts5(
                chunk_id UNINDEXED,
                article_id UNINDEXED,
                title,
                source,
                text,
                tokenize = 'unicode61'
            )
            """
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()


def init_archive_db(workspace: str | Path, db_path: str | Path | None = None) -> Path:
    resolved_db_path = Path(db_path).resolve() if db_path else _default_db_path(workspace)
    with _connect_db(resolved_db_path) as conn:
        _init_db(conn)
    return resolved_db_path


def _fts_available(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table') AND name = 'article_chunks_fts'"
    ).fetchone()
    return row is not None


def _canonicalize_url(url: str) -> str:
    raw = url.strip()
    try:
        parsed = urlparse(raw)
    except Exception:
        return raw

    host = parsed.netloc.lower()
    path = parsed.path or ""
    if host.endswith("bloomberg.com") and path == "/apps/news":
        query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
        filtered = [(key, value) for key, value in query_pairs if key in {"pid", "sid"} and value]
        if filtered:
            return urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    "",
                    urlencode(filtered),
                    "",
                )
            )
    return safari_fetch._canonicalize_url(raw)


def _article_id_from_url(url: str) -> str:
    return hashlib.blake2b(_canonicalize_url(url).encode("utf-8"), digest_size=10).hexdigest()


def _content_hash(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()


def _infer_source_from_url(url: str) -> str:
    canonical = _canonicalize_url(url)
    if safari_fetch._host_matches(canonical, "bloomberg.com"):
        return "Bloomberg"
    if safari_fetch._host_matches(canonical, "wsj.com"):
        return "WSJ"
    if safari_fetch._host_matches(canonical, "barrons.com"):
        return "Barron's"
    if safari_fetch._host_matches(canonical, "reuters.com"):
        return "Reuters"
    host = urlparse(canonical).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or "unknown"


def _is_unusable_fetch_result(url: str, title: str, body: str) -> bool:
    normalized_title = _normalize_spaces(title).lower()
    normalized_body = _normalize_spaces(body).lower()
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = parsed.netloc.lower()
    if host.endswith("bloomberg.com"):
        if normalized_title in {"404. page not found - bloomberg", "page not found - bloomberg"}:
            return True
        if "our apologies we're unable to find the page you're looking for" in normalized_body:
            return True
        if parsed.path == "/apps/news":
            if normalized_title in {"politics - bloomberg", "business - bloomberg", "markets - bloomberg", "bloomberg"}:
                return True
            if len(normalized_body) < 700:
                return True
    if host.endswith("reuters.com"):
        if (
            normalized_body.startswith(
                "skip to main content exclusive news, data and analytics for financial market professionals"
            )
            and "browse world" in normalized_body
            and "browse business" in normalized_body
            and "browse markets" in normalized_body
            and len(normalized_body) < 1800
        ):
            return True
    return False


def _extract_first_match(patterns: tuple[re.Pattern[str], ...], text: str) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return html.unescape(_normalize_spaces(match.group(1)))
    return ""


def _extract_published_at_from_html(markup: str) -> str:
    return _extract_first_match(PUBLISHED_PATTERNS, markup)


def _clean_title(title: str) -> str:
    cleaned = _normalize_spaces(title)
    cleaned = re.sub(r"\s+By Reuters$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _extract_title_from_html(markup: str) -> str:
    title = _extract_first_match(TITLE_PATTERNS, markup)
    title = title.replace(" - Bloomberg", "").replace(" - WSJ", "").strip()
    return _clean_title(title)


def _extract_title_from_text(text: str) -> str:
    probe = f"\n{text.strip()}\n"
    for pattern in TEXT_TITLE_PATTERNS:
        match = pattern.search(probe)
        if match:
            candidate = _clean_title(match.group(1))
            if candidate:
                return candidate
    return ""


def _extract_date_from_url(url: str) -> str:
    match = URL_DATE_RE.search(urlparse(url).path)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{year}-{month}-{day}"


def _parse_human_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%m/%d/%Y", "%b %d %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def _extract_published_at_from_text(text: str, url: str) -> str:
    probe = _normalize_article_body(text)
    for pattern in TEXT_PUBLISHED_PATTERNS:
        match = pattern.search(probe)
        if not match:
            continue
        value = _parse_human_date(match.group(1))
        if value:
            return value
    return _extract_date_from_url(url)


def _looks_like_slug_title(title: str, url: str) -> bool:
    cleaned = _normalize_spaces(title)
    if not cleaned:
        return True
    slug = urlparse(url).path.strip("/").split("/")[-1]
    slug = slug.replace(".html", "")
    if slug and cleaned.lower() == slug.lower():
        return True
    if "-" in cleaned and " " not in cleaned:
        return True
    return False


def _strip_html(markup: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", markup, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return _normalize_spaces(html.unescape(text))


def _normalize_article_body(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = normalized.strip()
    return normalized


def _slice_long_paragraph(text: str, *, target_chars: int, overlap_chars: int) -> list[str]:
    text = _normalize_spaces(text)
    if not text:
        return []
    if len(text) <= target_chars:
        return [text]
    out: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + target_chars)
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start + max(80, target_chars // 3):
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            out.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)
    return out


def _chunk_text(
    text: str,
    *,
    target_chars: int = DEFAULT_CHUNK_TARGET_CHARS,
    overlap_chars: int = DEFAULT_CHUNK_OVERLAP_CHARS,
) -> list[str]:
    paragraphs = [_normalize_spaces(item) for item in re.split(r"\n\s*\n", text) if item.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n\n".join(current).strip())
        current = []
        current_len = 0

    for paragraph in paragraphs:
        parts = _slice_long_paragraph(paragraph, target_chars=target_chars, overlap_chars=overlap_chars)
        for part in parts:
            part_len = len(part)
            projected = current_len + part_len + (2 if current else 0)
            if current and projected > target_chars:
                flush()
            current.append(part)
            current_len += part_len + (2 if len(current) > 1 else 0)
    flush()
    return [chunk for chunk in chunks if chunk.strip()]


def _safe_filename_piece(value: str, *, limit: int = 80) -> str:
    text = unicodedata.normalize("NFC", value).strip()
    text = re.sub(r'[\\/:*?"<>|]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip() or "article"


def _published_date_prefix(published_at: str, retrieved_at_kst: str) -> str:
    source = (published_at or "").strip() or retrieved_at_kst
    if len(source) >= 10:
        return source[:10]
    return _kst_now().date().isoformat()


def _relative_path(path: Path, workspace: str | Path) -> str:
    try:
        return path.resolve().relative_to(Path(workspace).resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _build_markdown(payload: ArticlePayload) -> str:
    lines = [
        f"# {payload.title}",
        "",
        f"- Source: {payload.source}",
        f"- Published At: {payload.published_at or 'unknown'}",
        f"- Retrieved At (KST): {payload.retrieved_at_kst}",
        f"- URL: {payload.url}",
    ]
    if payload.tags:
        lines.append(f"- Tags: {', '.join(payload.tags)}")
    if payload.notes.strip():
        lines.append(f"- Notes: {payload.notes.strip()}")
    lines.extend(["", "## Article Body", "", payload.body.strip(), ""])
    return "\n".join(lines)


def _parse_markdown_article(path: Path) -> ArticlePayload:
    text = path.read_text(encoding="utf-8")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not lines or not lines[0].startswith("# "):
        raise SystemExit(f"Markdown article title line is missing: {path}")
    title = lines[0][2:].strip()

    source = ""
    published_at = ""
    retrieved_at_kst = ""
    url = ""
    tags: list[str] = []
    notes = ""

    body_start = None
    for idx, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped == "## Article Body":
            body_start = idx + 1
            break
        match = MD_META_RE.match(stripped)
        if not match:
            continue
        key = match.group("key").strip().lower()
        value = match.group("value").strip()
        if key == "source":
            source = value
        elif key == "published at":
            published_at = value if value != "unknown" else ""
        elif key == "retrieved at (kst)":
            retrieved_at_kst = value
        elif key == "url":
            url = value
        elif key == "tags":
            tags = [_normalize_tag(item) for item in value.split(",") if _normalize_tag(item)]
        elif key == "notes":
            notes = value

    if body_start is None:
        raise SystemExit(f"`## Article Body` section is missing: {path}")

    body = "\n".join(lines[body_start:]).strip()
    if not source or not url:
        raise SystemExit(f"Required metadata is missing in article markdown: {path}")

    return ArticlePayload(
        title=title,
        source=source,
        url=_canonicalize_url(url),
        published_at=published_at,
        retrieved_at_kst=retrieved_at_kst or _kst_now().isoformat(),
        body=_normalize_article_body(body),
        tags=_unique_preserve_order([tag for tag in tags if tag]),
        notes=notes,
        metadata={},
        file_path=path.as_posix(),
    )


def archive_article(
    payload: ArticlePayload,
    *,
    workspace: str | Path = DEFAULT_WORKSPACE,
    db_path: str | Path | None = None,
    write_markdown: bool = True,
) -> dict[str, Any]:
    workspace_path = Path(workspace).resolve()
    research_dir = _research_dir(workspace_path)
    research_dir.mkdir(parents=True, exist_ok=True)
    resolved_db_path = Path(db_path).resolve() if db_path else _default_db_path(workspace_path)

    article_id = _article_id_from_url(payload.url)
    normalized_tags = _unique_preserve_order(
        [_normalize_tag(tag) for tag in payload.tags if _normalize_tag(tag)]
    )
    payload.tags = normalized_tags
    payload.title = _normalize_spaces(payload.title)
    payload.source = _normalize_spaces(payload.source)
    payload.body = _normalize_article_body(payload.body)
    payload.url = _canonicalize_url(payload.url)
    payload.retrieved_at_kst = payload.retrieved_at_kst or _kst_now().isoformat()

    with _connect_db(resolved_db_path) as conn:
        _init_db(conn)
        existing = conn.execute(
            "SELECT file_path FROM articles WHERE article_id = ? OR url = ?",
            (article_id, payload.url),
        ).fetchone()

        target_path: Path
        if existing and str(existing["file_path"]).strip():
            target_path = workspace_path / str(existing["file_path"])
        elif payload.file_path:
            target_path = Path(payload.file_path)
            if not target_path.is_absolute():
                target_path = workspace_path / payload.file_path
        else:
            date_prefix = _published_date_prefix(payload.published_at, payload.retrieved_at_kst)
            filename = (
                f"{date_prefix} "
                f"{_safe_filename_piece(payload.source, limit=24)} "
                f"{article_id[:8]} "
                f"{_safe_filename_piece(payload.title, limit=72)}.md"
            )
            target_path = research_dir / filename

        target_path.parent.mkdir(parents=True, exist_ok=True)
        relative_file_path = _relative_path(target_path, workspace_path)
        payload.file_path = relative_file_path

        if write_markdown:
            target_path.write_text(_build_markdown(payload), encoding="utf-8")

        metadata_json = json.dumps(payload.metadata or {}, ensure_ascii=False, sort_keys=True)
        content_hash = _content_hash(payload.body)

        conn.execute(
            """
            INSERT INTO articles (
                article_id, source, title, url, published_at, retrieved_at_kst,
                file_path, content_hash, notes, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(article_id) DO UPDATE SET
                source = excluded.source,
                title = excluded.title,
                url = excluded.url,
                published_at = excluded.published_at,
                retrieved_at_kst = excluded.retrieved_at_kst,
                file_path = excluded.file_path,
                content_hash = excluded.content_hash,
                notes = excluded.notes,
                metadata_json = excluded.metadata_json
            """,
            (
                article_id,
                payload.source,
                payload.title,
                payload.url,
                payload.published_at,
                payload.retrieved_at_kst,
                relative_file_path,
                content_hash,
                payload.notes.strip(),
                metadata_json,
            ),
        )

        conn.execute("DELETE FROM article_chunks WHERE article_id = ?", (article_id,))
        conn.execute("DELETE FROM article_tags WHERE article_id = ?", (article_id,))
        if _fts_available(conn):
            conn.execute("DELETE FROM article_chunks_fts WHERE article_id = ?", (article_id,))

        chunks = _chunk_text(payload.body)
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{article_id}:{idx:04d}"
            embedding_json = json.dumps(_embed_text(chunk), ensure_ascii=False)
            conn.execute(
                """
                INSERT INTO article_chunks (chunk_id, article_id, chunk_index, text, embedding_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (chunk_id, article_id, idx, chunk, embedding_json),
            )
            if _fts_available(conn):
                conn.execute(
                    """
                    INSERT INTO article_chunks_fts (chunk_id, article_id, title, source, text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (chunk_id, article_id, payload.title, payload.source, chunk),
                )

        for tag in normalized_tags:
            conn.execute(
                "INSERT OR IGNORE INTO article_tags (article_id, tag) VALUES (?, ?)",
                (article_id, tag),
            )
        conn.commit()

    return {
        "ok": True,
        "article_id": article_id,
        "title": payload.title,
        "source": payload.source,
        "url": payload.url,
        "published_at": payload.published_at,
        "file_path": relative_file_path,
        "db_path": _relative_path(resolved_db_path, workspace_path),
        "chunks_indexed": len(chunks),
        "tags": normalized_tags,
    }


def fetch_and_archive_url(
    url: str,
    *,
    workspace: str | Path = DEFAULT_WORKSPACE,
    db_path: str | Path | None = None,
    browser: str = news_harness._DEFAULT_FETCH_BROWSER,
    timeout: int = 15,
    max_attempts: int = 2,
    lock_timeout: float = 90.0,
    harness_retries: int = 1,
    recovery_wait: float = 1.5,
    site_throttle_seconds: float = DEFAULT_RESEARCH_SITE_THROTTLE_SECONDS,
    tags: list[str] | None = None,
    source: str | None = None,
    published_at: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    with _temporary_site_throttle(site_throttle_seconds):
        result = news_harness.fetch_article_with_harness(
            url,
            browser=browser,
            timeout=timeout,
            max_attempts=max_attempts,
            lock_timeout=lock_timeout,
            harness_retries=harness_retries,
            recovery_wait=recovery_wait,
        )
    if not result.get("success"):
        return {
            "ok": False,
            "url": url,
            "error": str(result.get("error") or "fetch failed"),
            "result": result,
        }

    markup = str(result.get("html") or "")
    title = _clean_title(str(result.get("title") or "")) or _extract_title_from_html(markup)
    article_source = source or _infer_source_from_url(url)
    article_body = _normalize_article_body(str(result.get("text") or ""))
    if not article_body and markup:
        article_body = _normalize_article_body(_strip_html(markup))
    if article_body and (not title or _looks_like_slug_title(title, url)):
        title = _extract_title_from_text(article_body) or title
    article_published_at = (published_at or "").strip() or _extract_published_at_from_html(markup)
    if not article_published_at:
        article_published_at = _extract_published_at_from_text(article_body, url)

    if not title:
        title = _safe_filename_piece(urlparse(url).path.strip("/").split("/")[-1] or "Untitled")
    if not article_body:
        return {
            "ok": False,
            "url": url,
            "error": "본문 텍스트를 충분히 확보하지 못했습니다.",
            "result": result,
        }
    if _is_unusable_fetch_result(url, title, article_body):
        return {
            "ok": False,
            "url": url,
            "error": "기사 본문 대신 일반 셸/오류 페이지가 반환되었습니다.",
            "result": result,
        }

    payload = ArticlePayload(
        title=title,
        source=article_source,
        url=url,
        published_at=article_published_at,
        retrieved_at_kst=_kst_now().isoformat(),
        body=article_body,
        tags=tags or [],
        notes=notes,
        metadata={
            "browser": browser,
            "fetch_success": True,
            "paywall": bool(result.get("paywall")),
            "title_from_html": title == _extract_title_from_html(markup) if markup else False,
        },
    )
    archived = archive_article(payload, workspace=workspace, db_path=db_path, write_markdown=True)
    archived["fetch_browser"] = browser
    archived["site_throttle_seconds"] = float(site_throttle_seconds)
    return archived


def _tag_filter_article_ids(conn: sqlite3.Connection, tags: list[str]) -> set[str] | None:
    normalized = [_normalize_tag(tag) for tag in tags if _normalize_tag(tag)]
    if not normalized:
        return None
    placeholders = ", ".join("?" for _ in normalized)
    rows = conn.execute(
        f"""
        SELECT article_id
        FROM article_tags
        WHERE tag IN ({placeholders})
        GROUP BY article_id
        HAVING COUNT(DISTINCT tag) = ?
        """,
        (*normalized, len(normalized)),
    ).fetchall()
    return {str(row["article_id"]) for row in rows}


def search_archive(
    query: str,
    *,
    workspace: str | Path = DEFAULT_WORKSPACE,
    db_path: str | Path | None = None,
    limit: int = 10,
    source: str | None = None,
    tags: list[str] | None = None,
    from_year: int | None = None,
    to_year: int | None = None,
) -> list[dict[str, Any]]:
    workspace_path = Path(workspace).resolve()
    resolved_db_path = Path(db_path).resolve() if db_path else _default_db_path(workspace_path)
    if not resolved_db_path.exists():
        raise SystemExit(f"Research archive DB not found: {resolved_db_path}")

    query_vec = _embed_text(query)
    query_tokens = [token.lower() for token in TOKEN_RE.findall(query)]

    with _connect_db(resolved_db_path) as conn:
        allowed_article_ids = _tag_filter_article_ids(conn, tags or [])
        rows = conn.execute(
            """
            SELECT
                c.chunk_id,
                c.article_id,
                c.chunk_index,
                c.text,
                c.embedding_json,
                a.source,
                a.title,
                a.url,
                a.published_at,
                a.retrieved_at_kst,
                a.file_path
            FROM article_chunks c
            JOIN articles a ON a.article_id = c.article_id
            """
        ).fetchall()

        fts_scores: dict[str, float] = {}
        if _fts_available(conn) and query_tokens:
            fts_query = " OR ".join(_unique_preserve_order(query_tokens))
            try:
                fts_rows = conn.execute(
                    """
                    SELECT chunk_id, bm25(article_chunks_fts) AS bm25_score
                    FROM article_chunks_fts
                    WHERE article_chunks_fts MATCH ?
                    LIMIT 200
                    """,
                    (fts_query,),
                ).fetchall()
                for row in fts_rows:
                    raw = float(row["bm25_score"])
                    fts_scores[str(row["chunk_id"])] = 1.0 / (1.0 + abs(raw))
            except sqlite3.OperationalError:
                fts_scores = {}

    article_best: dict[str, dict[str, Any]] = {}
    for row in rows:
        article_id = str(row["article_id"])
        if allowed_article_ids is not None and article_id not in allowed_article_ids:
            continue
        published_at = str(row["published_at"] or "")
        if from_year and (not published_at or published_at[:4].isdigit() and int(published_at[:4]) < from_year):
            continue
        if to_year and (not published_at or published_at[:4].isdigit() and int(published_at[:4]) > to_year):
            continue
        if source and str(row["source"]).lower() != source.lower():
            continue

        candidate_text = f"{row['title']} {row['source']} {row['text']}"
        vector_score = _cosine(query_vec, _parse_embedding(str(row["embedding_json"])))
        keyword_score = _keyword_overlap_score(query, candidate_text)
        fts_bonus = fts_scores.get(str(row["chunk_id"]), 0.0)
        score = (0.62 * vector_score) + (0.28 * keyword_score) + (0.10 * fts_bonus)

        tags_for_article: list[str] = []
        if article_id not in article_best:
            tags_for_article = []
        current = article_best.get(article_id)
        if current is None or score > current["score"]:
            article_best[article_id] = {
                "article_id": article_id,
                "title": str(row["title"]),
                "source": str(row["source"]),
                "url": str(row["url"]),
                "published_at": published_at,
                "retrieved_at_kst": str(row["retrieved_at_kst"]),
                "file_path": str(row["file_path"]),
                "chunk_index": int(row["chunk_index"]),
                "score": round(score, 6),
                "vector_score": round(vector_score, 6),
                "keyword_score": round(keyword_score, 6),
                "fts_bonus": round(fts_bonus, 6),
                "snippet": _normalize_spaces(str(row["text"]))[:320],
                "tags": tags_for_article,
            }

    ranked = sorted(article_best.values(), key=lambda item: item["score"], reverse=True)

    if ranked:
        with _connect_db(resolved_db_path) as conn:
            for item in ranked[: max(limit, 20)]:
                tag_rows = conn.execute(
                    "SELECT tag FROM article_tags WHERE article_id = ? ORDER BY tag",
                    (item["article_id"],),
                ).fetchall()
                item["tags"] = [str(row["tag"]) for row in tag_rows]

    return ranked[:limit]


def list_articles(
    *,
    workspace: str | Path = DEFAULT_WORKSPACE,
    db_path: str | Path | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    workspace_path = Path(workspace).resolve()
    resolved_db_path = Path(db_path).resolve() if db_path else _default_db_path(workspace_path)
    if not resolved_db_path.exists():
        return []

    with _connect_db(resolved_db_path) as conn:
        rows = conn.execute(
            """
            SELECT article_id, source, title, url, published_at, retrieved_at_kst, file_path
            FROM articles
            ORDER BY COALESCE(NULLIF(published_at, ''), retrieved_at_kst) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            tag_rows = conn.execute(
                "SELECT tag FROM article_tags WHERE article_id = ? ORDER BY tag",
                (str(row["article_id"]),),
            ).fetchall()
            out.append(
                {
                    "article_id": str(row["article_id"]),
                    "source": str(row["source"]),
                    "title": str(row["title"]),
                    "url": str(row["url"]),
                    "published_at": str(row["published_at"] or ""),
                    "retrieved_at_kst": str(row["retrieved_at_kst"]),
                    "file_path": str(row["file_path"]),
                    "tags": [str(tag_row["tag"]) for tag_row in tag_rows],
                }
            )
        return out


def _render_search_markdown(query: str, items: list[dict[str, Any]]) -> str:
    lines = ["# Research Search Results", "", f"- Query: `{query}`", f"- Hits: {len(items)}", ""]
    if not items:
        lines.append("검색 결과가 없습니다.")
        lines.append("")
        return "\n".join(lines)

    for idx, item in enumerate(items, start=1):
        lines.append(f"{idx}. [{item['source']}] {item['title']}")
        lines.append(f"   - Score: {item['score']:.4f}")
        if item.get("published_at"):
            lines.append(f"   - Published At: {item['published_at']}")
        lines.append(f"   - URL: {item['url']}")
        lines.append(f"   - File: {item['file_path']}")
        if item.get("tags"):
            lines.append(f"   - Tags: {', '.join(item['tags'])}")
        if item.get("snippet"):
            lines.append(f"   - Snippet: {item['snippet']}")
    lines.append("")
    return "\n".join(lines)


def _render_list_markdown(items: list[dict[str, Any]]) -> str:
    lines = ["# Research Archive", "", f"- Articles: {len(items)}", ""]
    if not items:
        lines.append("저장된 기사가 없습니다.")
        lines.append("")
        return "\n".join(lines)

    for idx, item in enumerate(items, start=1):
        lines.append(f"{idx}. [{item['source']}] {item['title']}")
        if item.get("published_at"):
            lines.append(f"   - Published At: {item['published_at']}")
        lines.append(f"   - URL: {item['url']}")
        lines.append(f"   - File: {item['file_path']}")
        if item.get("tags"):
            lines.append(f"   - Tags: {', '.join(item['tags'])}")
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="경제/금융 연구용 기사 원문 아카이브와 SQLite 검색 인덱스를 관리합니다."
    )
    parser.add_argument(
        "--workspace",
        default=DEFAULT_WORKSPACE,
        help="프로젝트 워크스페이스 루트 경로 (기본값: 현재 디렉터리)",
    )
    parser.add_argument(
        "--db",
        default="",
        help="Research SQLite 경로 (기본값: Research/research_archive.sqlite3)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Research SQLite 저장소를 초기화합니다.")

    fetch_url = sub.add_parser("fetch-url", help="기사 URL을 수집해 /Research/와 SQLite에 저장합니다.")
    fetch_url.add_argument("--url", required=True, help="수집할 기사 URL")
    fetch_url.add_argument("--source", default="", help="매체명을 수동 지정")
    fetch_url.add_argument("--published-at", default="", help="게시 날짜를 수동 지정")
    fetch_url.add_argument("--note", default="", help="기사 메모")
    fetch_url.add_argument("--tag", action="append", default=[], help="기사 태그. 여러 번 지정 가능")
    fetch_url.add_argument(
        "--browser",
        default=news_harness._DEFAULT_FETCH_BROWSER,
        choices=list(news_harness._SUPPORTED_FETCH_BROWSERS),
        help="본문 수집에 사용할 브라우저",
    )
    fetch_url.add_argument("--timeout", type=int, default=15, help="기사 본문 수집 타임아웃(초)")
    fetch_url.add_argument("--max-attempts", type=int, default=2, help="fetch CLI 내부 재시도 횟수")
    fetch_url.add_argument("--lock-timeout", type=float, default=90.0, help="브라우저 락 대기 시간(초)")
    fetch_url.add_argument("--harness-retries", type=int, default=1, help="하네스 차원의 추가 재시도 횟수")
    fetch_url.add_argument("--recovery-wait", type=float, default=1.5, help="복구 진단 뒤 대기 시간(초)")
    fetch_url.add_argument(
        "--site-throttle-seconds",
        type=float,
        default=DEFAULT_RESEARCH_SITE_THROTTLE_SECONDS,
        help="연구 아카이브 수집 시 매체 bucket별 최소 대기 시간(초). 기본값 15",
    )

    ingest_md = sub.add_parser("ingest-md", help="이미 저장된 Markdown 기사 파일을 인덱싱합니다.")
    ingest_md.add_argument("--file", required=True, help="인덱싱할 Markdown 기사 경로")
    ingest_md.add_argument("--tag", action="append", default=[], help="추가 태그. 여러 번 지정 가능")

    search = sub.add_parser("search", help="기사 아카이브를 하이브리드 시맨틱 검색합니다.")
    search.add_argument("--query", required=True, help="검색 질의")
    search.add_argument("--limit", type=int, default=10, help="반환할 최대 결과 수")
    search.add_argument("--source", default="", help="매체명 필터")
    search.add_argument("--tag", action="append", default=[], help="필수 태그. 여러 번 지정 가능")
    search.add_argument("--from-year", type=int, default=0, help="시작 연도 필터")
    search.add_argument("--to-year", type=int, default=0, help="종료 연도 필터")
    search.add_argument("--format", default="md", choices=["md", "json"], help="출력 형식")

    list_cmd = sub.add_parser("list", help="최근 저장된 기사 목록을 확인합니다.")
    list_cmd.add_argument("--limit", type=int, default=20, help="반환할 최대 기사 수")
    list_cmd.add_argument("--format", default="md", choices=["md", "json"], help="출력 형식")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    db_path = Path(args.db).resolve() if args.db else None

    if args.command == "init":
        resolved = init_archive_db(workspace, db_path)
        payload = {
            "ok": True,
            "db_path": _relative_path(resolved, workspace),
            "research_dir": _relative_path(_research_dir(workspace), workspace),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.command == "fetch-url":
        payload = fetch_and_archive_url(
            args.url,
            workspace=workspace,
            db_path=db_path,
            browser=args.browser,
            timeout=args.timeout,
            max_attempts=args.max_attempts,
            lock_timeout=args.lock_timeout,
            harness_retries=args.harness_retries,
            recovery_wait=args.recovery_wait,
            site_throttle_seconds=args.site_throttle_seconds,
            tags=args.tag,
            source=args.source or None,
            published_at=args.published_at or None,
            notes=args.note,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload.get("ok") else 1

    if args.command == "ingest-md":
        payload = _parse_markdown_article(Path(args.file))
        payload.tags = _unique_preserve_order(payload.tags + args.tag)
        archived = archive_article(payload, workspace=workspace, db_path=db_path, write_markdown=False)
        print(json.dumps(archived, ensure_ascii=False, indent=2))
        return 0

    if args.command == "search":
        items = search_archive(
            args.query,
            workspace=workspace,
            db_path=db_path,
            limit=max(1, args.limit),
            source=args.source or None,
            tags=args.tag,
            from_year=args.from_year or None,
            to_year=args.to_year or None,
        )
        if args.format == "json":
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            print(_render_search_markdown(args.query, items), end="")
        return 0

    if args.command == "list":
        items = list_articles(workspace=workspace, db_path=db_path, limit=max(1, args.limit))
        if args.format == "json":
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            print(_render_list_markdown(items), end="")
        return 0

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
