#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import safari_fetch as sf  # noqa: E402


SOURCE_ORDER = ("bloomberg", "wsj", "barrons")


def _nfd(value: str) -> str:
    return unicodedata.normalize("NFD", value)


def _newsupdate_dir(workspace: str | Path) -> Path:
    return Path(workspace) / _nfd("NewsUpdate")


def _state_path(workspace: str | Path) -> Path:
    return _newsupdate_dir(workspace) / ".state.json"


def _load_state(workspace: str | Path) -> dict[str, Any]:
    path = _state_path(workspace)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _candidate_from_row(row: dict[str, Any], source: str) -> dict[str, str]:
    href = sf._canonicalize_url((row.get("Link") or "").strip())
    return {
        "source": source,
        "title": (row.get("Title") or "").strip(),
        "url": href,
        "published_at": (row.get("Date") or "").strip(),
        "description": (row.get("Plain Description") or "").strip()
        or (row.get("Description") or "").strip(),
        "author": (row.get("Author") or "").strip(),
    }


def _dedupe_candidates(rows: list[dict[str, Any]], source: str) -> list[dict[str, str]]:
    seen: set[str] = set()
    items: list[dict[str, str]] = []
    config = sf._RSS_SOURCE_CONFIG[source]
    for row in rows:
        candidate = _candidate_from_row(row, source)
        url = candidate["url"]
        if not url or not candidate["title"]:
            continue
        if not any(sf._host_matches(url, host) for host in config["hosts"]):
            continue
        if url in seen:
            continue
        seen.add(url)
        items.append(candidate)
    return items


def _fetch_source_candidates(source: str, timeout: int) -> list[dict[str, str]]:
    if source == "bloomberg":
        rows = sf._fetch_rss_rows(sf.BLOOMBERG_RSS_CSV_URL, timeout=timeout)
        return _dedupe_candidates(rows, source)

    rows = sf._fetch_rss_rows(sf.DOW_JONES_RSS_CSV_URL, timeout=timeout)
    return _dedupe_candidates(rows, source)


def _slice_since_last(
    candidates: list[dict[str, str]],
    last_seen_url: str,
) -> tuple[list[dict[str, str]], bool | None]:
    if not last_seen_url:
        return list(candidates), None

    normalized_last = sf._canonicalize_url(last_seen_url)
    for index, item in enumerate(candidates):
        if item["url"] == normalized_last:
            return candidates[:index], True
    return list(candidates), False


def build_candidate_queue(
    *,
    workspace: str | Path,
    timeout: int = 15,
    source: str = "all",
    limit_per_source: int = 0,
) -> dict[str, Any]:
    state = _load_state(workspace)
    selected_sources = SOURCE_ORDER if source == "all" else (source,)
    result_sources: list[dict[str, Any]] = []
    total = 0

    for source_name in selected_sources:
        candidates = _fetch_source_candidates(source_name, timeout=timeout)
        last_seen_url = str(state.get(source_name, "") or "").strip()
        new_candidates, boundary_found = _slice_since_last(candidates, last_seen_url)
        if limit_per_source > 0:
            new_candidates = new_candidates[:limit_per_source]
        total += len(new_candidates)
        result_sources.append(
            {
                "source": source_name,
                "last_seen_url": last_seen_url,
                "boundary_found": boundary_found,
                "new_count": len(new_candidates),
                "candidates": new_candidates,
            }
        )

    return {
        "state_last_run_kst": state.get("last_run_kst", ""),
        "total_new_candidates": total,
        "sources": result_sources,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# NewsUpdate 후보 큐", ""]
    last_run = str(payload.get("state_last_run_kst", "") or "").strip()
    if last_run:
        lines.append(f"- 마지막 실행 시각(KST): `{last_run}`")
        lines.append("")

    for source in payload.get("sources", []):
        source_name = str(source.get("source", "")).strip()
        lines.append(f"## {source_name}")
        last_seen_url = str(source.get("last_seen_url", "") or "").strip()
        boundary_found = source.get("boundary_found")
        if last_seen_url:
            lines.append(f"- 마지막 처리 URL: {last_seen_url}")
            if boundary_found is True:
                lines.append("- state 경계: RSS 안에서 찾았습니다.")
            elif boundary_found is False:
                lines.append("- state 경계: RSS 안에서 찾지 못했습니다. 현재 창 전체를 후보로 봅니다.")
        else:
            lines.append("- 마지막 처리 URL: 없음")
        lines.append(f"- 신규 후보 수: {int(source.get('new_count', 0))}")
        lines.append("")

        candidates = source.get("candidates", [])
        if not candidates:
            lines.append("업데이트 할 후보 없음")
            lines.append("")
            continue

        for index, item in enumerate(candidates, start=1):
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()
            published_at = item.get("published_at", "").strip()
            description = item.get("description", "").strip()
            lines.append(f"{index}. {title}")
            if published_at:
                lines.append(f"   - 게시 시각: {published_at}")
            lines.append(f"   - URL: {url}")
            if description:
                lines.append(f"   - 설명: {description}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NewsUpdate용 신규 기사 후보를 state 경계 기준으로 잘라 보여줍니다."
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="프로젝트 워크스페이스 루트 경로 (기본값: 현재 디렉터리)",
    )
    parser.add_argument(
        "--source",
        default="all",
        choices=["all", "bloomberg", "wsj", "barrons"],
        help="확인할 소스 (기본값: all)",
    )
    parser.add_argument("--timeout", type=int, default=15, help="RSS 조회 타임아웃(초)")
    parser.add_argument(
        "--limit-per-source",
        type=int,
        default=0,
        help="소스별 최대 출력 개수 (기본값: 0 = 전체)",
    )
    parser.add_argument(
        "--format",
        default="md",
        choices=["md", "json"],
        help="출력 형식 (기본값: md)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = build_candidate_queue(
        workspace=args.workspace,
        timeout=args.timeout,
        source=args.source,
        limit_per_source=max(0, args.limit_per_source),
    )
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_render_markdown(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
