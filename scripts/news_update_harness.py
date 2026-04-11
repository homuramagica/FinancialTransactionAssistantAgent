from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any


ARTICLE_FILENAME_RE = re.compile(r"^\d{2}-\d{2}-\d{2} \d{2}-\d{2} .+\.md$")
ERROR_FILENAME_RE = re.compile(r"^ERROR-\d{2}-\d{2}-\d{2} \d{2}-\d{2}\.md$")
SOURCE_LINE_RE = re.compile(r"^\[출처: .+\]\(https?://.+\)$")
SECTION_LINE_RE = re.compile(r"^(?P<emoji>\S+)\s+\*\*(?P<label>[^*]+):\*\*\s+.+$")
TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$"
)

ALLOWED_TRANSITIONS = {
    "배경 설명",
    "무대 뒤 이야기",
    "숨은 의미",
    "숫자로 보는 현황",
    "대표적 사례",
    "빠른 요약",
    "맥락",
    "주요 뉴스",
    "과거 회상",
    "자금 흐름 추적",
    "작동 원리",
    "우리의 생각",
    "현장에서",
    "주목할 점",
    "현실 점검",
    "현재 상황",
    "전체 그림",
    "결론",
    "문제점",
    "세부사항",
    "최종 결과",
    "흥미로운 점",
    "반대편 시각",
    "최신 상황",
    "위험 수준",
    "그가 말하기를",
    "내부 들여다보기",
    "다음 단계",
    "그녀가 말하기를",
    "그들이 말하기를",
    "우리가 듣는 소식",
    "우리가 주목하는 것",
    "중요한 이유",
    "이 소식의 중요성",
    "이 주장의 중요성",
    "하지만",
    "자세히 보기",
    "멀리서 보기",
}

REQUIRED_STATE_KEYS = ("last_run_kst", "bloomberg", "wsj", "barrons")

_FETCH_SCRIPT = Path(__file__).resolve().with_name("safari_fetch.py")
_DEFAULT_FETCH_TIMEOUT = 15
_DEFAULT_FETCH_MAX_ATTEMPTS = 2
_DEFAULT_BROWSER_LOCK_TIMEOUT = 90.0
_DEFAULT_HARNESS_RECOVERY_WAIT = 1.5

BROWSER_INSTABILITY_SIGNALS = (
    "target page, context or browser has been closed",
    "browser has been closed",
    "closed unexpectedly",
    "net::err_",
    "connection refused",
    "devtools",
    "websocket",
    "원격 디버깅",
    "페이지 로드가 제한 시간 안에 끝나지 않았습니다",
    "브라우저 세션이 예상치 않게 종료되었습니다",
    "탭이 중간에 닫혔습니다",
)

MANUAL_BROWSER_ACTION_SIGNALS = (
    "python websockets 패키지가 설치되어 있지 않습니다",
    "google chrome 앱을 찾지 못했습니다",
    "chrome devtools 프로필 디렉터리를 준비하지 못했습니다",
    "봇 차단 페이지가 반환되었습니다",
    "session-setup은 대화형 터미널",
)


def _nfd(value: str) -> str:
    return unicodedata.normalize("NFD", value)


def _newsupdate_dir(workspace: str | Path) -> Path:
    return Path(workspace) / _nfd("NewsUpdate")


def _resolve_existing_article_path(workspace: str | Path, filename: str) -> Path:
    raw_path = Path(_nfd(filename))
    news_dir = _newsupdate_dir(workspace)

    if raw_path.is_absolute():
        return raw_path

    if raw_path.parts:
        first_part = unicodedata.normalize("NFC", raw_path.parts[0])
        if first_part == "NewsUpdate":
            return Path(workspace) / raw_path

    if raw_path.parent != Path("."):
        return Path(workspace) / raw_path

    return news_dir / raw_path


def _normalize_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in _normalize_lines(text) if line.strip()]


def _find_intro_line(lines: list[str]) -> str | None:
    title_seen = False
    spacer_seen = False
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if not title_seen:
            title_seen = True
            continue
        if not spacer_seen and line == "&nbsp;":
            spacer_seen = True
            continue
        if spacer_seen:
            return line
    return None


def validate_article_content(filename: str, content: str) -> list[str]:
    issues: list[str] = []

    if not ARTICLE_FILENAME_RE.match(filename):
        issues.append("기사 파일명이 `YY-MM-DD HH-MM 제목.md` 형식을 따르지 않습니다.")

    stripped = content.strip()
    if not stripped:
        return ["기사 본문이 비어 있습니다."]

    lines = _normalize_lines(stripped)
    non_empty = [line.strip() for line in lines if line.strip()]
    if not non_empty:
        return ["기사 본문이 비어 있습니다."]

    if not non_empty[0].startswith("# "):
        issues.append("첫 줄이 `# 제목` 형식이 아닙니다.")

    if content.count("&nbsp;") < 3:
        issues.append("Axios 간격용 `&nbsp;` 구분이 부족합니다.")

    if len(stripped) < 900:
        issues.append("기사 본문이 너무 짧습니다.")

    intro_line = _find_intro_line(lines)
    if not intro_line:
        issues.append("제목 뒤 핵심 요약 문장이 없습니다.")
    elif intro_line.startswith(("-", "*", "•", "#")):
        issues.append("제목 아래 핵심 요약이 리스트가 아니라 한 문장이어야 합니다.")

    section_labels: list[str] = []
    for line in non_empty:
        if line.startswith("# "):
            continue
        match = SECTION_LINE_RE.match(line)
        if match:
            section_labels.append(match.group("label").strip())

    allowed_section_count = sum(1 for label in section_labels if label in ALLOWED_TRANSITIONS)
    if allowed_section_count == 0:
        issues.append("허용된 Axios 전환구 섹션이 없습니다.")

    bullet_lines = [line for line in non_empty if line.startswith("- ") or line.startswith("* ")]
    if len(bullet_lines) < 8:
        issues.append("세부 설명 리스트가 너무 적습니다.")

    if "이 문서는 금융 에이전트에서 작성됨." not in stripped:
        issues.append("마지막 금융 에이전트 표기가 없습니다.")

    if not any(SOURCE_LINE_RE.match(line) for line in non_empty[-3:]):
        issues.append("마지막 출처 링크가 없습니다.")

    last_line = non_empty[-1]
    if not SOURCE_LINE_RE.match(last_line):
        issues.append("마지막 줄이 출처 링크로 끝나지 않습니다.")

    return issues


def validate_error_content(filename: str, content: str) -> list[str]:
    issues: list[str] = []
    if not ERROR_FILENAME_RE.match(filename):
        issues.append("오류 보고서 파일명이 `ERROR-YY-MM-DD HH-MM.md` 형식을 따르지 않습니다.")
    if not content.strip():
        issues.append("오류 보고서 본문이 비어 있습니다.")
    elif not content.lstrip().startswith("# 오류 보고서"):
        issues.append("오류 보고서는 `# 오류 보고서`로 시작해야 합니다.")
    return issues


def validate_state_payload(state: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(state, dict):
        return ["state가 JSON 객체가 아닙니다."]

    for key in REQUIRED_STATE_KEYS:
        if key not in state:
            issues.append(f"state에 `{key}` 키가 없습니다.")

    timestamp = state.get("last_run_kst")
    if timestamp is not None and not isinstance(timestamp, str):
        issues.append("`last_run_kst`는 문자열이어야 합니다.")
    elif isinstance(timestamp, str) and not TIMESTAMP_RE.match(timestamp):
        issues.append("`last_run_kst`가 ISO-8601 형식이 아닙니다.")

    for key in ("bloomberg", "wsj", "barrons"):
        value = state.get(key)
        if value is not None and not isinstance(value, str):
            issues.append(f"`{key}` 값이 문자열이 아닙니다.")
        elif isinstance(value, str) and value and not value.startswith("https://"):
            issues.append(f"`{key}` 값이 https URL이 아닙니다.")

    return issues


def validate_manifest_payload(payload: Any, *, allow_empty: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "issues": [],
        "articles": [],
        "errors": [],
        "state": [],
    }

    if not isinstance(payload, dict):
        report["issues"].append("manifest 최상위 구조가 JSON 객체가 아닙니다.")
        return report

    articles = payload.get("articles", [])
    errors = payload.get("errors", [])
    state = payload.get("state")

    if not isinstance(articles, list):
        report["issues"].append("`articles`는 배열이어야 합니다.")
        articles = []
    if not isinstance(errors, list):
        report["issues"].append("`errors`는 배열이어야 합니다.")
        errors = []

    if not articles and not allow_empty:
        report["issues"].append("검증 가능한 기사 초안이 최소 1건은 필요합니다.")

    seen_filenames: set[str] = set()

    for entry in articles:
        filename = entry.get("filename") if isinstance(entry, dict) else None
        content = entry.get("content") if isinstance(entry, dict) else None
        entry_report = {"filename": filename or "", "issues": []}
        if not isinstance(entry, dict):
            entry_report["issues"].append("기사 항목이 JSON 객체가 아닙니다.")
        else:
            if not isinstance(filename, str) or not filename:
                entry_report["issues"].append("기사 파일명이 비어 있습니다.")
            if not isinstance(content, str):
                entry_report["issues"].append("기사 본문이 문자열이 아닙니다.")
            if isinstance(filename, str) and filename:
                if filename in seen_filenames:
                    entry_report["issues"].append("중복된 기사 파일명입니다.")
                seen_filenames.add(filename)
            if isinstance(filename, str) and isinstance(content, str):
                entry_report["issues"].extend(validate_article_content(filename, content))
        report["articles"].append(entry_report)

    for entry in errors:
        filename = entry.get("filename") if isinstance(entry, dict) else None
        content = entry.get("content") if isinstance(entry, dict) else None
        entry_report = {"filename": filename or "", "issues": []}
        if not isinstance(entry, dict):
            entry_report["issues"].append("오류 보고서 항목이 JSON 객체가 아닙니다.")
        else:
            if not isinstance(filename, str) or not filename:
                entry_report["issues"].append("오류 보고서 파일명이 비어 있습니다.")
            if not isinstance(content, str):
                entry_report["issues"].append("오류 보고서 본문이 문자열이 아닙니다.")
            if isinstance(filename, str) and filename:
                if filename in seen_filenames:
                    entry_report["issues"].append("중복된 파일명입니다.")
                seen_filenames.add(filename)
            if isinstance(filename, str) and isinstance(content, str):
                entry_report["issues"].extend(validate_error_content(filename, content))
        report["errors"].append(entry_report)

    report["state"] = validate_state_payload(state)

    report["ok"] = not (
        report["issues"]
        or report["state"]
        or any(entry["issues"] for entry in report["articles"])
        or any(entry["issues"] for entry in report["errors"])
    )
    return report


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=path.parent,
        prefix=".tmp_news_update_",
    ) as temp_file:
        temp_file.write(content)
        temp_name = temp_file.name
    os.replace(temp_name, path)


def apply_manifest_payload(
    payload: dict[str, Any],
    *,
    workspace: str | Path,
    allow_empty: bool = False,
) -> dict[str, Any]:
    report = validate_manifest_payload(payload, allow_empty=allow_empty)
    if not report["ok"]:
        raise ValueError(json.dumps(report, ensure_ascii=False, indent=2))

    news_dir = _newsupdate_dir(workspace)
    articles = payload.get("articles", [])
    errors = payload.get("errors", [])
    state = payload.get("state", {})

    for entry in articles:
        filename = _nfd(entry["filename"])
        path = news_dir / filename
        _atomic_write_text(path, entry["content"])

    for entry in errors:
        filename = _nfd(entry["filename"])
        path = news_dir / filename
        _atomic_write_text(path, entry["content"])

    state_path = news_dir / ".state.json"
    state_text = json.dumps(state, ensure_ascii=False, indent=2)
    _atomic_write_text(state_path, state_text)

    return {
        "ok": True,
        "written_articles": [entry["filename"] for entry in articles],
        "written_errors": [entry["filename"] for entry in errors],
        "state_path": str(state_path),
    }


def _load_manifest(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("manifest 최상위 구조가 JSON 객체가 아닙니다.")
    return data


def _default_fetch_failure(url: str, error: str) -> dict[str, Any]:
    return {
        "success": False,
        "url": url,
        "title": "",
        "text": "",
        "html": "",
        "error": error,
        "paywall": False,
    }


def _run_json_subprocess(command: list[str]) -> tuple[subprocess.CompletedProcess[str] | None, dict[str, Any] | None]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except Exception as exc:
        return None, {"error": str(exc)}

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return completed, None

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return completed, None
    if not isinstance(payload, dict):
        return completed, None
    return completed, payload


def _browser_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _combined_browser_text(payload: dict[str, Any]) -> str:
    parts = [
        _browser_text(payload.get("error")),
        _browser_text(payload.get("stderr")),
        _browser_text(payload.get("detail")),
        _browser_text(payload.get("availability")),
        _browser_text(payload.get("attach")),
        _browser_text(payload.get("javascript")),
        _browser_text(payload.get("launch_probe")),
    ]
    return "\n".join(part for part in parts if part).lower()


def _has_signal(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)


def _needs_manual_browser_action(payload: dict[str, Any]) -> bool:
    return _has_signal(_combined_browser_text(payload), MANUAL_BROWSER_ACTION_SIGNALS)


def _has_browser_instability(payload: dict[str, Any]) -> bool:
    return _has_signal(_combined_browser_text(payload), BROWSER_INSTABILITY_SIGNALS)


def _run_fetch_cli(
    url: str,
    *,
    browser: str,
    timeout: int,
    max_attempts: int,
    lock_timeout: float,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(_FETCH_SCRIPT),
        url,
        "--browser",
        browser,
        "--timeout",
        str(timeout),
        "--max-attempts",
        str(max_attempts),
        "--lock-timeout",
        str(lock_timeout),
    ]
    completed, payload = _run_json_subprocess(command)
    if completed is None:
        error = f"fetch CLI 실행에 실패했습니다. {payload.get('error', '')}".strip()
        return _default_fetch_failure(url, error)

    if payload is None:
        stderr = (completed.stderr or "").strip()
        error = "fetch CLI가 JSON을 반환하지 않았습니다."
        if stderr:
            error = f"{error} stderr: {stderr}"
        result = _default_fetch_failure(url, error)
    else:
        result = dict(payload)
        result.setdefault("success", False)
        result.setdefault("url", url)
        result.setdefault("title", "")
        result.setdefault("text", "")
        result.setdefault("html", "")
        result.setdefault("error", None)
        result.setdefault("paywall", False)

    result["cli_returncode"] = completed.returncode
    stderr = (completed.stderr or "").strip()
    if stderr and "stderr" not in result:
        result["stderr"] = stderr
    return result


def _run_fetch_diagnose(*, browser: str, lock_timeout: float) -> dict[str, Any]:
    command = [
        sys.executable,
        str(_FETCH_SCRIPT),
        "--diagnose",
        "--browser",
        browser,
        "--lock-timeout",
        str(lock_timeout),
    ]
    completed, payload = _run_json_subprocess(command)
    if completed is None:
        return {"ready": False, "error": f"browser diagnose 실행에 실패했습니다. {payload.get('error', '')}".strip()}

    if payload is None:
        stderr = (completed.stderr or "").strip()
        detail = "browser diagnose가 JSON을 반환하지 않았습니다."
        if stderr:
            detail = f"{detail} stderr: {stderr}"
        payload = {"ready": False, "error": detail}
    else:
        payload = dict(payload)

    payload["cli_returncode"] = completed.returncode
    return payload


def _diagnose_failure_detail(payload: dict[str, Any]) -> str:
    candidates: list[Any] = [
        payload.get("error"),
        payload.get("detail"),
    ]

    for key in ("availability", "launch_probe", "attach", "javascript"):
        section = payload.get(key)
        if isinstance(section, dict):
            candidates.append(section.get("detail"))

    for candidate in candidates:
        text = _browser_text(candidate).strip()
        if text:
            return text

    return "브라우저 preflight 진단이 실패했습니다."


def _preflight_failure_result(url: str, diagnose: dict[str, Any]) -> dict[str, Any]:
    result = _default_fetch_failure(url, _diagnose_failure_detail(diagnose))
    result["harness_attempts"] = 0
    result["skipped_by_preflight"] = True
    result["diagnose"] = diagnose
    return result


def fetch_article_with_harness(
    url: str,
    *,
    browser: str = "chrome",
    timeout: int = _DEFAULT_FETCH_TIMEOUT,
    max_attempts: int = _DEFAULT_FETCH_MAX_ATTEMPTS,
    lock_timeout: float = _DEFAULT_BROWSER_LOCK_TIMEOUT,
    harness_retries: int = 1,
    recovery_wait: float = _DEFAULT_HARNESS_RECOVERY_WAIT,
) -> dict[str, Any]:
    total_rounds = max(1, harness_retries + 1)
    latest_diagnose: dict[str, Any] | None = None
    last_result = _default_fetch_failure(url, "fetch가 시작되지 않았습니다.")

    for round_index in range(1, total_rounds + 1):
        result = _run_fetch_cli(
            url,
            browser=browser,
            timeout=timeout,
            max_attempts=max_attempts,
            lock_timeout=lock_timeout,
        )
        result["harness_attempts"] = round_index
        if latest_diagnose is not None and "diagnose" not in result:
            result["diagnose"] = latest_diagnose
        if result.get("success"):
            return result

        last_result = result
        if round_index >= total_rounds:
            break
        if _needs_manual_browser_action(result):
            break
        if not _has_browser_instability(result):
            break

        latest_diagnose = _run_fetch_diagnose(browser=browser, lock_timeout=lock_timeout)
        last_result["diagnose"] = latest_diagnose
        if _needs_manual_browser_action(latest_diagnose):
            break

        if recovery_wait > 0:
            time.sleep(recovery_wait)

    return last_result


def fetch_batch_with_harness(
    urls: list[str],
    *,
    browser: str = "chrome",
    timeout: int = _DEFAULT_FETCH_TIMEOUT,
    max_attempts: int = _DEFAULT_FETCH_MAX_ATTEMPTS,
    lock_timeout: float = _DEFAULT_BROWSER_LOCK_TIMEOUT,
    harness_retries: int = 1,
    recovery_wait: float = _DEFAULT_HARNESS_RECOVERY_WAIT,
) -> dict[str, Any]:
    preflight = _run_fetch_diagnose(browser=browser, lock_timeout=lock_timeout)
    if not preflight.get("ready"):
        results = [_preflight_failure_result(url, preflight) for url in urls]
        requested = len(results)
        return {
            "ok": False,
            "requested": requested,
            "succeeded": 0,
            "failed": requested,
            "skipped_due_to_preflight": True,
            "preflight": preflight,
            "results": results,
        }

    results: list[dict[str, Any]] = []
    for url in urls:
        results.append(
            fetch_article_with_harness(
                url,
                browser=browser,
                timeout=timeout,
                max_attempts=max_attempts,
                lock_timeout=lock_timeout,
                harness_retries=harness_retries,
                recovery_wait=recovery_wait,
            )
        )

    succeeded = sum(1 for item in results if item.get("success"))
    requested = len(results)
    failed = requested - succeeded
    return {
        "ok": failed == 0,
        "requested": requested,
        "succeeded": succeeded,
        "failed": failed,
        "skipped_due_to_preflight": False,
        "preflight": preflight,
        "results": results,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NewsUpdate 기사 배치를 검증하고, 통과한 배치만 원자적으로 반영합니다."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_manifest = subparsers.add_parser(
        "validate-manifest",
        help="manifest의 기사 품질과 state 구조를 검증합니다.",
    )
    validate_manifest.add_argument("--manifest", required=True, help="검증할 manifest JSON 경로")
    validate_manifest.add_argument(
        "--allow-empty",
        action="store_true",
        help="기사 없이 state만 반영하는 배치도 허용합니다.",
    )

    apply_manifest = subparsers.add_parser(
        "apply-manifest",
        help="manifest를 검증하고 통과 시에만 NewsUpdate와 state를 반영합니다.",
    )
    apply_manifest.add_argument("--manifest", required=True, help="반영할 manifest JSON 경로")
    apply_manifest.add_argument(
        "--workspace",
        default=".",
        help="프로젝트 워크스페이스 루트 경로 (기본값: 현재 디렉터리)",
    )
    apply_manifest.add_argument(
        "--allow-empty",
        action="store_true",
        help="기사 없이 state만 반영하는 배치도 허용합니다.",
    )

    validate_files = subparsers.add_parser(
        "validate-files",
        help="이미 작성된 기사 파일을 빠르게 검사합니다.",
    )
    validate_files.add_argument(
        "--workspace",
        default=".",
        help="프로젝트 워크스페이스 루트 경로 (기본값: 현재 디렉터리)",
    )
    validate_files.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="기사 파일명 또는 `NewsUpdate/...` 상대 경로 목록",
    )

    validate_dir = subparsers.add_parser(
        "validate-dir",
        help="NewsUpdate 디렉터리 안의 기사/오류 보고서를 일괄 검사합니다.",
    )
    validate_dir.add_argument(
        "--workspace",
        default=".",
        help="프로젝트 워크스페이스 루트 경로 (기본값: 현재 디렉터리)",
    )
    validate_dir.add_argument(
        "--glob",
        default="*.md",
        help="검사할 파일 glob 패턴 (기본값: *.md)",
    )
    validate_dir.add_argument(
        "--limit",
        type=int,
        default=0,
        help="최근 N개 파일만 검사 (기본값: 0 = 전체)",
    )

    fetch_article = subparsers.add_parser(
        "fetch-article",
        help="기사 본문 수집을 하네스로 감싸서 실행합니다.",
    )
    fetch_article.add_argument("--url", required=True, help="수집할 기사 URL")
    fetch_article.add_argument(
        "--browser",
        default="chrome",
        choices=["chrome"],
        help="본문 수집에 사용할 브라우저 (기본값: chrome)",
    )
    fetch_article.add_argument(
        "--timeout",
        type=int,
        default=_DEFAULT_FETCH_TIMEOUT,
        help="기사 본문 수집 타임아웃(초)",
    )
    fetch_article.add_argument(
        "--max-attempts",
        type=int,
        default=_DEFAULT_FETCH_MAX_ATTEMPTS,
        help="fetch CLI 내부 재시도 횟수",
    )
    fetch_article.add_argument(
        "--lock-timeout",
        type=float,
        default=_DEFAULT_BROWSER_LOCK_TIMEOUT,
        help="브라우저 락 대기 시간(초)",
    )
    fetch_article.add_argument(
        "--harness-retries",
        type=int,
        default=1,
        help="브라우저 연결 불안정 감지 시 하네스 차원의 추가 재시도 횟수",
    )
    fetch_article.add_argument(
        "--recovery-wait",
        type=float,
        default=_DEFAULT_HARNESS_RECOVERY_WAIT,
        help="복구 진단 뒤 다음 재시도 전 대기 시간(초)",
    )

    fetch_batch = subparsers.add_parser(
        "fetch-batch",
        help="여러 기사 URL을 순차 수집하며 브라우저 불안정 복구를 함께 처리합니다.",
    )
    fetch_batch.add_argument(
        "--url",
        action="append",
        required=True,
        help="수집할 기사 URL. 여러 번 지정할 수 있습니다.",
    )
    fetch_batch.add_argument(
        "--browser",
        default="chrome",
        choices=["chrome"],
        help="본문 수집에 사용할 브라우저 (기본값: chrome)",
    )
    fetch_batch.add_argument(
        "--timeout",
        type=int,
        default=_DEFAULT_FETCH_TIMEOUT,
        help="기사 본문 수집 타임아웃(초)",
    )
    fetch_batch.add_argument(
        "--max-attempts",
        type=int,
        default=_DEFAULT_FETCH_MAX_ATTEMPTS,
        help="fetch CLI 내부 재시도 횟수",
    )
    fetch_batch.add_argument(
        "--lock-timeout",
        type=float,
        default=_DEFAULT_BROWSER_LOCK_TIMEOUT,
        help="브라우저 락 대기 시간(초)",
    )
    fetch_batch.add_argument(
        "--harness-retries",
        type=int,
        default=1,
        help="브라우저 연결 불안정 감지 시 하네스 차원의 추가 재시도 횟수",
    )
    fetch_batch.add_argument(
        "--recovery-wait",
        type=float,
        default=_DEFAULT_HARNESS_RECOVERY_WAIT,
        help="복구 진단 뒤 다음 재시도 전 대기 시간(초)",
    )

    return parser


def _cmd_validate_manifest(args: argparse.Namespace) -> int:
    payload = _load_manifest(args.manifest)
    report = validate_manifest_payload(payload, allow_empty=args.allow_empty)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def _cmd_apply_manifest(args: argparse.Namespace) -> int:
    payload = _load_manifest(args.manifest)
    try:
        result = apply_manifest_payload(
            payload,
            workspace=args.workspace,
            allow_empty=args.allow_empty,
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_validate_files(args: argparse.Namespace) -> int:
    report: dict[str, Any] = {"ok": True, "files": []}

    for filename in args.files:
        path = _resolve_existing_article_path(args.workspace, filename)
        article_name = path.name
        entry = {"filename": filename, "issues": []}
        if not path.exists():
            entry["issues"].append("파일이 존재하지 않습니다.")
        else:
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()
            entry["issues"].extend(validate_article_content(article_name, content))
        if entry["issues"]:
            report["ok"] = False
        report["files"].append(entry)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def _cmd_validate_dir(args: argparse.Namespace) -> int:
    news_dir = _newsupdate_dir(args.workspace)
    report: dict[str, Any] = {
        "ok": True,
        "news_dir": str(news_dir),
        "matched": 0,
        "files": [],
    }

    if not news_dir.exists():
        report["ok"] = False
        report["files"].append(
            {
                "filename": "",
                "issues": ["NewsUpdate 디렉터리가 존재하지 않습니다."],
            }
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    matched_paths = sorted(path for path in news_dir.glob(args.glob) if path.is_file())
    if args.limit and args.limit > 0:
        matched_paths = matched_paths[-args.limit :]

    report["matched"] = len(matched_paths)

    for path in matched_paths:
        filename = unicodedata.normalize("NFC", path.name)
        entry = {"filename": filename, "issues": []}
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
        if filename.startswith("ERROR-"):
            entry["issues"].extend(validate_error_content(filename, content))
        else:
            entry["issues"].extend(validate_article_content(filename, content))
        if entry["issues"]:
            report["ok"] = False
        report["files"].append(entry)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def _cmd_fetch_article(args: argparse.Namespace) -> int:
    result = fetch_article_with_harness(
        args.url,
        browser=args.browser,
        timeout=args.timeout,
        max_attempts=max(1, args.max_attempts),
        lock_timeout=max(0.0, args.lock_timeout),
        harness_retries=max(0, args.harness_retries),
        recovery_wait=max(0.0, args.recovery_wait),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


def _cmd_fetch_batch(args: argparse.Namespace) -> int:
    result = fetch_batch_with_harness(
        list(args.url),
        browser=args.browser,
        timeout=args.timeout,
        max_attempts=max(1, args.max_attempts),
        lock_timeout=max(0.0, args.lock_timeout),
        harness_retries=max(0, args.harness_retries),
        recovery_wait=max(0.0, args.recovery_wait),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-manifest":
        return _cmd_validate_manifest(args)
    if args.command == "apply-manifest":
        return _cmd_apply_manifest(args)
    if args.command == "validate-files":
        return _cmd_validate_files(args)
    if args.command == "validate-dir":
        return _cmd_validate_dir(args)
    if args.command == "fetch-article":
        return _cmd_fetch_article(args)
    if args.command == "fetch-batch":
        return _cmd_fetch_batch(args)

    parser.error(f"지원하지 않는 명령입니다: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
