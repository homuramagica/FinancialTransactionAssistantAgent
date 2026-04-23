#!/usr/bin/env python3
"""
safari_fetch.py - RSS CSV로 기사 목록을 읽고 Chrome DevTools 기반으로 개별 기사 본문을 추출합니다.

WSJ/Barron's는 Dow Jones RSS CSV를 한 번 읽어 함께 처리할 수 있고,
Bloomberg는 전용 Bloomberg RSS CSV를 사용합니다.
파일명은 호환성을 위해 유지하지만 브라우저 수집 경로는 DevTools 전용입니다.

사용법:
  python3 scripts/safari_fetch.py <URL> --browser chrome
  python3 scripts/safari_fetch.py <URL> --links-only --source dow_jones
  python3 scripts/safari_fetch.py <URL> --load-more --source bloomberg
  python3 scripts/safari_fetch.py <URL> --reload --browser chrome
  python3 scripts/safari_fetch.py https://www.wsj.com --session-setup
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import csv
import fcntl
import io
import importlib.util
import json
import os
import plistlib
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlparse, urlunparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
DOW_JONES_RSS_CSV_URL = "https://rss.app/feeds/_m6HwVpkVbkV6H1V6.csv"
BLOOMBERG_RSS_CSV_URL = "https://rss.app/feeds/_t07deORnyZW90CjC.csv"
_BROWSER_CONFIG = {
    "chrome": {
        "display_name": "Chrome DevTools",
    },
}
_RSS_SOURCE_CONFIG = {
    "wsj": {
        "feed_url": DOW_JONES_RSS_CSV_URL,
        "hosts": ["wsj.com"],
    },
    "barrons": {
        "feed_url": DOW_JONES_RSS_CSV_URL,
        "hosts": ["barrons.com"],
    },
    "bloomberg": {
        "feed_url": BLOOMBERG_RSS_CSV_URL,
        "hosts": ["bloomberg.com"],
    },
}

_BROWSER_LOCK_PATH = os.environ.get("NEWS_FETCH_LOCK_PATH", "/tmp/safari_fetch_browser.lock")
_DEFAULT_BROWSER_LOCK_TIMEOUT = float(os.environ.get("NEWS_FETCH_LOCK_TIMEOUT", "90"))
_BROWSER_LOCK_POLL_INTERVAL = 0.25
_SITE_THROTTLE_STATE_PATH = os.environ.get("NEWS_FETCH_SITE_THROTTLE_STATE_PATH", "/tmp/safari_fetch_site_throttle.json")
_SITE_THROTTLE_INTERVAL_SECONDS = float(os.environ.get("NEWS_FETCH_SITE_THROTTLE_INTERVAL_SECONDS", "10"))
_BLOOMBERG_SITE_THROTTLE_INTERVAL_SECONDS = float(
    os.environ.get("NEWS_FETCH_BLOOMBERG_SITE_THROTTLE_INTERVAL_SECONDS", "20")
)
_DOW_JONES_SITE_THROTTLE_INTERVAL_SECONDS = float(
    os.environ.get("NEWS_FETCH_DOW_JONES_SITE_THROTTLE_INTERVAL_SECONDS", "10")
)
_HTML_SNIPPET_LIMIT = 60_000
_TEXT_HEALTHY_THRESHOLD = 200
_PAGE_SETTLE_DELAY_SECONDS = 0.8
_SESSION_SETUP_TIMEOUT_SECONDS = 300
_DEVTOOLS_LAUNCH_TIMEOUT = float(os.environ.get("NEWS_FETCH_DEVTOOLS_LAUNCH_TIMEOUT", "20"))
_DEVTOOLS_HOST = os.environ.get("NEWS_FETCH_DEVTOOLS_HOST", "127.0.0.1")
_DEVTOOLS_PORT = int(os.environ.get("NEWS_FETCH_DEVTOOLS_PORT", "9222"))
_BLOOMBERG_SESSION_SETTLE_SECONDS = float(
    os.environ.get("NEWS_FETCH_BLOOMBERG_SESSION_SETTLE_SECONDS", "3.0")
)
_BLOOMBERG_SHORT_TEXT_THRESHOLD = int(
    os.environ.get("NEWS_FETCH_BLOOMBERG_SHORT_TEXT_THRESHOLD", "1200")
)
_CHROME_APP_PATH = os.environ.get("NEWS_FETCH_CHROME_APP_PATH", "").strip()
_CHROME_APP_NAME = os.environ.get("NEWS_FETCH_CHROME_APP_NAME", "Google Chrome")
_CHROME_LAUNCH_MODE = os.environ.get("NEWS_FETCH_CHROME_LAUNCH_MODE", "auto").strip().lower()

_RETRY_ERROR_SIGNALS = (
    "about:blank",
    "timeout",
    "timed out",
    "connection refused",
    "closed unexpectedly",
    "세션이 예상치 않게 종료",
    "페이지 로드가 제한 시간 안에 끝나지 않았습니다",
    "탭이 중간에 닫혔습니다",
    "devtools",
    "websocket",
    "원격 디버깅",
)
_NON_RETRYABLE_ERROR_SIGNALS = (
    "python websockets 패키지가 설치되어 있지 않습니다",
    "chrome devtools 프로필 디렉터리를 준비하지 못했습니다",
    "google chrome 앱을 찾지 못했습니다",
    "session-setup은 대화형 터미널",
    "봇 차단 페이지가 반환되었습니다",
)
_BOT_BLOCK_SIGNALS = (
    "are you a robot",
    "verify you are human",
    "press & hold",
    "bot verification",
    "unusual activity",
    "temporarily limited",
    "액세스가 일시적으로 제한되었습니다",
)
_GENERIC_TITLE_SIGNALS = {
    "wsj.com",
    "barrons.com",
    "bloomberg.com",
}


@contextlib.contextmanager
def _browser_session_lock(
    lock_timeout: Optional[float] = None,
    reason: str = "browser_fetch",
):
    """
    브라우저 자동화는 항상 한 번에 하나의 프로세스만 수행하도록 직렬화합니다.

    DevTools 포트와 전용 Chrome 프로필을 동시에 건드리면 세션이 꼬일 수 있어
    공용 파일 락으로 보호합니다.
    """
    timeout = _DEFAULT_BROWSER_LOCK_TIMEOUT if lock_timeout is None else float(lock_timeout)
    os.makedirs(os.path.dirname(_BROWSER_LOCK_PATH), exist_ok=True)

    with open(_BROWSER_LOCK_PATH, "a+", encoding="utf-8") as lock_file:
        deadline = time.monotonic() + max(0.0, timeout)
        acquired = False

        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "다른 기사 연결 작업이 아직 실행 중입니다. "
                        f"{timeout:g}초 동안 대기했지만 브라우저 락을 확보하지 못했습니다. "
                        "기사 연결은 한 번에 하나씩만 수행되므로 앞선 작업이 끝난 뒤 다시 시도해 주세요."
                    )
                time.sleep(_BROWSER_LOCK_POLL_INTERVAL)

        try:
            try:
                lock_file.seek(0)
                lock_file.truncate()
                lock_file.write(
                    json.dumps(
                        {
                            "pid": os.getpid(),
                            "reason": reason,
                            "locked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        },
                        ensure_ascii=False,
                    )
                )
                lock_file.flush()
            except Exception:
                pass
            yield
        finally:
            if acquired:
                try:
                    lock_file.seek(0)
                    lock_file.truncate()
                    lock_file.flush()
                except Exception:
                    pass
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _browser_lock_error(url: str, exc: Exception) -> dict[str, Any]:
    return {
        "success": False,
        "url": url,
        "title": "",
        "text": "",
        "html": "",
        "error": str(exc),
        "paywall": False,
    }


def _site_access_key(url: str) -> str:
    canonical_url = _canonicalize_url(url)
    if any(_host_matches(canonical_url, host) for host in _RSS_SOURCE_CONFIG["wsj"]["hosts"]):
        return "dow_jones"
    if any(_host_matches(canonical_url, host) for host in _RSS_SOURCE_CONFIG["barrons"]["hosts"]):
        return "dow_jones"
    if any(_host_matches(canonical_url, host) for host in _RSS_SOURCE_CONFIG["bloomberg"]["hosts"]):
        return "bloomberg"

    try:
        host = urlparse(canonical_url).netloc.lower()
    except Exception:
        host = ""
    return host or "unknown"


def _load_site_throttle_state() -> dict[str, float]:
    path = Path(_SITE_THROTTLE_STATE_PATH)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}

    normalized: dict[str, float] = {}
    for key, value in payload.items():
        try:
            normalized[str(key)] = float(value)
        except Exception:
            continue
    return normalized


def _save_site_throttle_state(state: dict[str, float]) -> None:
    path = Path(_SITE_THROTTLE_STATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _site_throttle_interval_for(key: str) -> float:
    if key == "bloomberg":
        return max(0.0, float(_BLOOMBERG_SITE_THROTTLE_INTERVAL_SECONDS))
    if key == "dow_jones":
        return max(0.0, float(_DOW_JONES_SITE_THROTTLE_INTERVAL_SECONDS))
    return max(0.0, float(_SITE_THROTTLE_INTERVAL_SECONDS))


def _wait_for_site_access_slot(url: str) -> dict[str, Any]:
    key = _site_access_key(url)
    interval = _site_throttle_interval_for(key)
    if interval <= 0:
        return {"site": key, "wait_seconds": 0.0, "throttled": False}

    state = _load_site_throttle_state()
    now = time.time()
    last_access_at = float(state.get(key, 0.0) or 0.0)
    wait_seconds = max(0.0, (last_access_at + interval) - now) if last_access_at else 0.0
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    accessed_at = time.time()
    state[key] = accessed_at
    _save_site_throttle_state(state)
    return {
        "site": key,
        "wait_seconds": round(wait_seconds, 3),
        "throttled": wait_seconds > 0,
        "accessed_at": accessed_at,
    }


def _normalize_browser(browser: Optional[str] = None) -> str:
    raw = (browser or os.environ.get("NEWS_FETCH_BROWSER") or "chrome").strip().lower()
    aliases = {
        "google-chrome": "chrome",
        "google_chrome": "chrome",
        "chromium": "chrome",
        "safari": "chrome",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in _BROWSER_CONFIG else "chrome"


def _browser_config(browser: Optional[str] = None) -> dict[str, Any]:
    return _BROWSER_CONFIG[_normalize_browser(browser)]


def _browser_label(browser: Optional[str] = None) -> str:
    return _browser_config(browser)["display_name"]


def _default_devtools_profile_path() -> Path:
    explicit = os.environ.get("NEWS_FETCH_DEVTOOLS_PROFILE_PATH")
    if explicit:
        return Path(explicit).expanduser()

    # Chrome 136+ ignores remote-debugging flags for the default Chrome data
    # directory, so automation must keep using a non-standard user-data-dir.
    return (REPO_ROOT / "tmp" / "chrome_devtools_profile").expanduser()


_DEFAULT_PROFILE_PATH = _default_devtools_profile_path()


def _browser_profile_path(browser: Optional[str] = None) -> Path:
    del browser
    return _DEFAULT_PROFILE_PATH


def _chrome_app_candidate_paths() -> list[Path]:
    raw_name = (_CHROME_APP_NAME or "").strip()
    bundle_name = Path(raw_name).name if raw_name.endswith(".app") else f"{Path(raw_name).name}.app"

    candidates: list[Path] = []
    if _CHROME_APP_PATH:
        candidates.append(Path(_CHROME_APP_PATH).expanduser())
    if raw_name.startswith("/"):
        candidates.append(Path(raw_name).expanduser())

    candidates.extend(
        [
            Path("/Applications") / bundle_name,
            Path.home() / "Applications" / bundle_name,
        ]
    )

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(candidate)
    return deduped


def _resolve_chrome_app_path() -> Optional[Path]:
    for candidate in _chrome_app_candidate_paths():
        if candidate.exists():
            return candidate
    return None


def _chrome_info_plist_path(app_path: Path) -> Path:
    return app_path / "Contents" / "Info.plist"


def _read_chrome_info_plist(app_path: Path) -> dict[str, Any] | None:
    plist_path = _chrome_info_plist_path(app_path)
    try:
        with open(plist_path, "rb") as handle:
            payload = plistlib.load(handle)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_chrome_executable_path() -> Optional[Path]:
    app_path = _resolve_chrome_app_path()
    if app_path is None:
        return None

    info = _read_chrome_info_plist(app_path) or {}
    executable_name = str(info.get("CFBundleExecutable") or "").strip()

    candidates: list[Path] = []
    if executable_name:
        candidates.append(app_path / "Contents" / "MacOS" / executable_name)

    bundle_name = app_path.stem.strip()
    if bundle_name:
        candidates.append(app_path / "Contents" / "MacOS" / bundle_name)

    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _chrome_launch_target() -> str:
    app_path = _resolve_chrome_app_path()
    if app_path is not None:
        return str(app_path)
    return _CHROME_APP_NAME


def _chrome_application_name() -> str:
    app_path = _resolve_chrome_app_path()
    if app_path is not None:
        return app_path.stem
    raw_name = (_CHROME_APP_NAME or "Google Chrome").strip()
    return Path(raw_name).stem or "Google Chrome"


def _chrome_launch_mode() -> str:
    mode = (_CHROME_LAUNCH_MODE or "auto").strip().lower()
    return mode if mode in {"auto", "direct", "open"} else "auto"


def _chrome_launch_strategies() -> list[str]:
    mode = _chrome_launch_mode()
    if mode == "direct":
        return ["direct", "open"]
    if mode == "open":
        return ["open", "direct"]
    return ["open", "direct"]


def _chrome_open_command(launch_args: list[str]) -> list[str]:
    app_path = _resolve_chrome_app_path()
    if app_path is not None:
        # `open -a` expects an app name, not a bundle path.
        return ["open", "-n", str(app_path), "--args", *launch_args]
    return ["open", "-na", _chrome_application_name(), "--args", *launch_args]


def _chrome_devtools_args(start_url: str) -> list[str]:
    profile_path = _browser_profile_path()
    profile_path.mkdir(parents=True, exist_ok=True)
    return [
        f"--user-data-dir={profile_path}",
        f"--remote-debugging-port={_DEVTOOLS_PORT}",
        "--no-first-run",
        "--no-default-browser-check",
        start_url,
    ]


def _devtools_base_url() -> str:
    return f"http://{_DEVTOOLS_HOST}:{_DEVTOOLS_PORT}"


def _devtools_missing_dependency_message() -> str:
    return (
        "Python websockets 패키지가 설치되어 있지 않습니다. "
        "`python3 -m pip install websockets`로 설치한 뒤 다시 시도해 주세요."
    )


def _extend_sys_path_with_project_venv() -> None:
    venv_lib = REPO_ROOT / ".venv" / "lib"
    if not venv_lib.exists():
        return
    for candidate in sorted(venv_lib.glob("python*/site-packages")):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


def _load_websockets():
    try:
        import websockets  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised via caller behavior
        _extend_sys_path_with_project_venv()
        try:
            import websockets  # type: ignore
        except Exception:
            return None, exc
    return websockets, None


def _maybe_reexec_with_project_venv() -> None:
    if __name__ != "__main__":
        return
    if os.environ.get("NEWS_FETCH_SKIP_VENV_REEXEC") == "1":
        return

    project_python = REPO_ROOT / ".venv" / "bin" / "python"
    if not project_python.exists():
        return
    if Path(sys.executable).resolve() == project_python.resolve():
        return

    if importlib.util.find_spec("websockets") is not None:
        return

    probe = subprocess.run(
        [
            str(project_python),
            "-c",
            "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('websockets') else 1)",
        ],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        return

    os.execv(str(project_python), [str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]])


def _ensure_browser_available(browser: Optional[str] = None) -> Optional[str]:
    del browser
    if sys.platform != "darwin":
        return "Chrome DevTools 수집은 현재 macOS에서만 지원합니다."

    websockets_module, import_error = _load_websockets()
    if websockets_module is None or import_error is not None:
        return _devtools_missing_dependency_message()

    profile_path = _browser_profile_path()
    try:
        profile_path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return f"Chrome DevTools 프로필 디렉터리를 준비하지 못했습니다: {profile_path} ({exc})"

    app_path = _resolve_chrome_app_path()
    if app_path is not None:
        executable_path = _resolve_chrome_executable_path()
        if executable_path is None:
            plist_path = _chrome_info_plist_path(app_path)
            return (
                "Google Chrome 앱 번들은 찾았지만 실행 파일을 확인하지 못했습니다. "
                f"app={app_path} plist={plist_path}"
            )
        if not os.access(executable_path, os.X_OK):
            return (
                "Google Chrome 실행 파일이 실행 가능 상태가 아닙니다. "
                f"executable={executable_path}"
            )
        return None

    probe = subprocess.run(
        ["open", "-Ra", _CHROME_APP_NAME],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        stderr = (probe.stderr or "").strip()
        detail_parts = []
        if stderr:
            detail_parts.append(f"stderr: {stderr}")
        candidate_paths = [str(path) for path in _chrome_app_candidate_paths()]
        if candidate_paths:
            detail_parts.append(f"checked: {', '.join(candidate_paths)}")
        detail = f" {' '.join(detail_parts)}" if detail_parts else ""
        return f"Google Chrome 앱을 찾지 못했습니다.{detail}".strip()

    return None


def _humanize_browser_error(detail: str, browser: Optional[str] = None) -> str:
    browser_label = _browser_label(browser)
    normalized = (detail or "").strip()
    lowered = normalized.lower()
    if not normalized:
        return f"{browser_label} 브라우저 자동화 실행에 실패했습니다."

    if "websockets" in lowered and "no module named" in lowered:
        return _devtools_missing_dependency_message()

    if "connection refused" in lowered:
        return f"{browser_label} 원격 디버깅 포트에 연결하지 못했습니다. 원본 오류: {normalized}"

    if "timeout" in lowered or "timed out" in lowered:
        return (
            f"{browser_label} 페이지 로드가 제한 시간 안에 끝나지 않았습니다. "
            f"원본 오류: {normalized}"
        )

    if "closed" in lowered and "target" in lowered:
        return f"{browser_label} 탭이 중간에 닫혔습니다. 원본 오류: {normalized}"

    if "google chrome 앱을 찾지 못했습니다" in lowered:
        return normalized

    return normalized


def _detect_paywall(text: str, html: str) -> bool:
    """Paywall / 로그인 화면 감지"""
    signals = [
        "subscribe to continue",
        "subscription required",
        "sign in to read",
        "already a subscriber",
        "log in to continue",
        "access this article",
        "create a free account",
        "이미 구독자이신가요",
        "로그인이 필요합니다",
    ]
    combined = (text + html).lower()
    short_text = len(text.strip()) < 400
    has_signal = any(signal in combined for signal in signals)
    return short_text and has_signal


def _contains_login_prompt(text: str, html: str) -> bool:
    """짧은 본문 여부와 무관하게 로그인/구독 프롬프트 신호를 감지합니다."""
    signals = [
        "sign in",
        "log in",
        "subscribe",
        "already a subscriber",
        "create account",
        "create a free account",
        "subscription required",
        "로그인이 필요합니다",
        "구독",
        "구독자",
    ]
    combined = (text + html).lower()
    return any(signal in combined for signal in signals)


def _detect_bot_block(title: str, text: str, html: str) -> bool:
    title_text = "\n".join([title, text[:2_000]]).lower()
    html_lower = (html or "")[:5_000].lower()

    # 본문/제목에 노출되는 명시적 차단 문구를 우선 신뢰합니다.
    if any(signal in title_text for signal in _BOT_BLOCK_SIGNALS):
        return True

    # HTML에는 일반 위젯/폼 문자열이 많아서 `captcha-site-key` 같은 정상 코드로
    # 오탐이 발생할 수 있으므로, 더 강한 패턴만 허용합니다.
    if any(signal in html_lower for signal in _BOT_BLOCK_SIGNALS):
        return True

    captcha_markers = (
        r"\bg-recaptcha\b",
        r"\bhcaptcha\b",
        r"\bcf-turnstile\b",
        r"\bcaptcha\b(?!-site-key)",
    )
    return any(re.search(pattern, html_lower) for pattern in captcha_markers)


def _looks_like_empty_shell(title: str, text: str) -> bool:
    normalized_title = (title or "").strip().lower()
    normalized_text = (text or "").strip()
    if len(normalized_text) >= 80:
        return False
    return normalized_title in _GENERIC_TITLE_SIGNALS or not normalized_title


def _same_registered_host(left: str, right: str) -> bool:
    """요청 URL과 실제 반환 URL이 대체로 같은 호스트인지 확인합니다."""
    try:
        left_host = urlparse(left).netloc.lower()
        right_host = urlparse(right).netloc.lower()
    except Exception:
        return False

    if not left_host or not right_host:
        return False
    return left_host == right_host or left_host.endswith("." + right_host) or right_host.endswith("." + left_host)


def _host_matches(url: str, expected_host: str) -> bool:
    """URL 호스트가 특정 도메인과 일치하거나 그 하위 도메인인지 확인합니다."""
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False

    expected_host = expected_host.lower()
    return bool(host) and (host == expected_host or host.endswith("." + expected_host))


def _should_try_bloomberg_reload(
    url: str,
    result: dict[str, Any],
    close_after: bool,
    reload_used: bool,
) -> bool:
    """
    Bloomberg에서 로그인/쿠키 상태가 아직 적용되지 않은 흔적이 보이면
    자동으로 새로고침 1회를 시도합니다.
    """
    if reload_used or not close_after:
        return False
    if not _host_matches(url, "bloomberg.com"):
        return False
    if not result.get("success"):
        return False
    if result.get("paywall"):
        return True

    text = (result.get("text") or "")[:2500]
    html = (result.get("html") or "")[:2500]
    if _contains_login_prompt(text, html):
        return True
    return len((result.get("text") or "").strip()) < _BLOOMBERG_SHORT_TEXT_THRESHOLD


def _payload_best_text(payload: dict[str, Any]) -> str:
    article_text = str(payload.get("articleText") or "").strip()
    body_text = str(payload.get("bodyText") or "").strip()
    return article_text if len(article_text) >= _TEXT_HEALTHY_THRESHOLD else body_text


def _should_wait_for_bloomberg_session_settle(url: str, payload: dict[str, Any]) -> bool:
    """
    Bloomberg는 로그인 세션이 몇 초 늦게 붙거나, 로그인 후에도 미완성 paywall 뷰가
    잠깐 노출되는 경우가 있어 짧은 본문이면 한 번 더 대기 후 재평가합니다.
    """
    if not _host_matches(url, "bloomberg.com"):
        return False

    text = _payload_best_text(payload)
    html = str(payload.get("articleHtml") or payload.get("bodyHtml") or "")[:2500]
    if _contains_login_prompt(text[:2500], html):
        return True
    if _detect_paywall(text, html):
        return True
    return len(text.strip()) < _BLOOMBERG_SHORT_TEXT_THRESHOLD


def _refine_bloomberg_payload_if_needed(
    url: str,
    payload: dict[str, Any],
    *,
    websocket_url: str,
    timeout: float,
) -> dict[str, Any]:
    if not _should_wait_for_bloomberg_session_settle(url, payload):
        return payload

    wait_seconds = max(0.0, _BLOOMBERG_SESSION_SETTLE_SECONDS)
    if wait_seconds > 0:
        time.sleep(wait_seconds)

    refreshed = _wait_for_devtools_article_payload(
        websocket_url,
        timeout=timeout,
        reload_after_load=False,
    )
    if len(_payload_best_text(refreshed)) >= len(_payload_best_text(payload)):
        refreshed = dict(refreshed)
        refreshed["sessionSettleWaitSeconds"] = wait_seconds
        refreshed["sessionSettleRechecked"] = True
        return refreshed

    payload = dict(payload)
    payload["sessionSettleWaitSeconds"] = wait_seconds
    payload["sessionSettleRechecked"] = True
    payload["sessionSettleKeptOriginal"] = True
    return payload


def _canonicalize_url(url: str) -> str:
    """쿼리/프래그먼트를 제거한 canonical URL을 반환합니다."""
    try:
        parsed = urlparse(url)
    except Exception:
        return url

    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _dedupe_links(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out = []
    for item in items:
        href = item.get("href", "")
        title = item.get("title", "").strip()
        if not href or not title or href in seen:
            continue
        seen.add(href)
        normalized = dict(item)
        normalized["href"] = href
        normalized["title"] = title
        out.append(normalized)
    return out


def _fetch_rss_rows(feed_url: str, timeout: int = 15) -> list[dict[str, str]]:
    """RSS CSV를 읽어 row dict 목록으로 반환합니다."""
    try:
        request = Request(
            feed_url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.8",
            },
        )
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"[safari_fetch] RSS 조회 실패: {exc}", file=sys.stderr)
        return []

    try:
        return list(csv.DictReader(io.StringIO(raw)))
    except Exception as exc:
        print(f"[safari_fetch] RSS CSV 파싱 실패: {exc}", file=sys.stderr)
        return []


def _fetch_dow_jones_links(timeout: int = 15, source_filter: Optional[str] = None) -> list[dict[str, str]]:
    """Dow Jones RSS CSV를 한 번 읽어 WSJ/Barron's 링크를 함께 또는 개별로 반환합니다."""
    grouped: dict[str, list[dict[str, str]]] = {
        "wsj": [],
        "barrons": [],
    }

    for row in _fetch_rss_rows(DOW_JONES_RSS_CSV_URL, timeout=timeout):
        href = _canonicalize_url((row.get("Link") or "").strip())
        title = (row.get("Title") or "").strip()
        if not href or not title:
            continue

        matched_source = None
        if any(_host_matches(href, host) for host in _RSS_SOURCE_CONFIG["wsj"]["hosts"]):
            matched_source = "wsj"
        elif any(_host_matches(href, host) for host in _RSS_SOURCE_CONFIG["barrons"]["hosts"]):
            matched_source = "barrons"

        if not matched_source:
            continue

        grouped[matched_source].append(
            {
                "href": href,
                "title": title,
                "source": matched_source,
            }
        )

    if source_filter in grouped:
        return _dedupe_links(grouped[source_filter])

    combined = grouped["wsj"] + grouped["barrons"]
    return _dedupe_links(combined)


def _fetch_rss_links_for_source(source: str, timeout: int = 15) -> list[dict[str, str]]:
    """소스별 RSS CSV에서 기사 링크 목록을 추출합니다."""
    if source == "dow_jones":
        return _fetch_dow_jones_links(timeout=timeout)
    if source in {"wsj", "barrons"}:
        return _fetch_dow_jones_links(timeout=timeout, source_filter=source)

    config = _RSS_SOURCE_CONFIG.get(source)
    if not config:
        return []

    links = []
    for row in _fetch_rss_rows(config["feed_url"], timeout=timeout):
        href = (row.get("Link") or "").strip()
        title = (row.get("Title") or "").strip()
        if not href or not title:
            continue
        if not any(_host_matches(href, host) for host in config["hosts"]):
            continue
        links.append(
            {
                "href": _canonicalize_url(href),
                "title": title,
            }
        )

    return _dedupe_links(links)


def _lookup_rss_entry(url: str, timeout: int = 15) -> Optional[dict[str, str]]:
    """기사 URL에 대응하는 RSS row를 찾습니다."""
    canonical_url = _canonicalize_url(url)
    matched_sources = [
        source
        for source, config in _RSS_SOURCE_CONFIG.items()
        if any(_host_matches(canonical_url, host) for host in config["hosts"])
    ]
    if not matched_sources:
        return None

    for source in matched_sources:
        config = _RSS_SOURCE_CONFIG[source]
        for row in _fetch_rss_rows(config["feed_url"], timeout=timeout):
            href = _canonicalize_url((row.get("Link") or "").strip())
            if href == canonical_url:
                normalized = dict(row)
                normalized["_source"] = source
                normalized["_canonical_link"] = href
                return normalized
    return None


def _rss_row_to_fetch_result(row: dict[str, str], fallback_url: str) -> dict[str, Any]:
    """RSS row를 기존 fetch 응답 형식으로 변환합니다."""
    title = (row.get("Title") or "").strip()
    link = _canonicalize_url((row.get("Link") or "").strip() or fallback_url)
    author = (row.get("Author") or "").strip()
    published_at = (row.get("Date") or "").strip()
    description = (row.get("Plain Description") or "").strip() or (row.get("Description") or "").strip()
    image = (row.get("Image") or "").strip()
    source = row.get("_source") or ""

    text_parts = [
        part
        for part in [
            f"Title: {title}" if title else "",
            f"Source: {source}" if source else "",
            f"Author: {author}" if author else "",
            f"Date: {published_at}" if published_at else "",
            f"Summary: {description}" if description else "",
            f"Image: {image}" if image else "",
            f"Link: {link}" if link else "",
        ]
        if part
    ]

    return {
        "success": True,
        "url": link,
        "title": title,
        "text": "\n".join(text_parts),
        "html": "",
        "error": None,
        "paywall": False,
    }


def _failure_result(
    url: str,
    error: str,
    *,
    title: str = "",
    text: str = "",
    html: str = "",
    detail: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "success": False,
        "url": url,
        "title": title,
        "text": text,
        "html": html,
        "error": error,
        "paywall": False,
    }
    if detail:
        payload["detail"] = detail
    return payload


def _devtools_request(path: str, *, method: str = "GET", timeout: float = 5.0) -> Any:
    request = Request(f"{_devtools_base_url()}/{path.lstrip('/')}", method=method)
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    if not body:
        return None
    return json.loads(body)


def _devtools_version(timeout: float = 3.0) -> Optional[dict[str, Any]]:
    try:
        payload = _devtools_request("json/version", timeout=timeout)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _launch_devtools_browser(start_url: str = "about:blank") -> subprocess.Popen[str] | None:
    executable_path = _resolve_chrome_executable_path()
    launch_args = _chrome_devtools_args(start_url)
    errors: list[str] = []

    for strategy in _chrome_launch_strategies():
        if strategy == "direct":
            if executable_path is None:
                errors.append("direct: Chrome 실행 파일 경로를 찾지 못했습니다.")
                continue
            try:
                process = subprocess.Popen(
                    [str(executable_path), *launch_args],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
                return process
            except Exception as exc:
                errors.append(f"direct: {exc}")
                continue

        if strategy == "open":
            command = _chrome_open_command(launch_args)
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            if completed.returncode == 0:
                return None
            stderr = (completed.stderr or "").strip()
            detail = stderr or f"returncode={completed.returncode}"
            errors.append(f"open: {detail}")
            continue

        errors.append(f"{strategy}: 지원하지 않는 Chrome launch strategy")

    detail = "; ".join(errors) if errors else "실행 시도 정보가 비어 있습니다."
    raise RuntimeError(f"Chrome DevTools 브라우저를 실행하지 못했습니다. {detail}".strip())


def _quit_chrome() -> None:
    script = f"""
if application "{_chrome_application_name()}" is running then
    tell application "{_chrome_application_name()}" to quit
end if
"""
    completed = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Chrome 종료에 실패했습니다. {detail}".strip())


def _chrome_launch_crash_detail(
    context: str,
    *,
    returncode: int | None = None,
    extra: str | None = None,
) -> str:
    parts = [f"{context} 브라우저가 실행 직후 비정상 종료된 것으로 보입니다."]
    if returncode is not None:
        suffix = f"returncode={returncode}."
        if returncode in {-6, 134}:
            suffix = f"returncode={returncode} (SIGABRT 가능)."
        parts.append(suffix)
    parts.append("macOS AppKit 초기화 단계 충돌일 수 있습니다.")
    if extra:
        parts.append(extra.strip())
    return " ".join(part for part in parts if part).strip()


def _is_chrome_running() -> bool:
    completed = subprocess.run(
        ["osascript", "-e", f'return application "{_chrome_application_name()}" is running'],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        return False
    return (completed.stdout or "").strip().lower() == "true"


def _wait_for_devtools_ready(
    timeout: float = _DEVTOOLS_LAUNCH_TIMEOUT,
    *,
    launched_process: subprocess.Popen[str] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(1.0, timeout)
    crash_check_after = time.monotonic() + 1.5
    last_error = "Chrome DevTools 연결 정보를 아직 찾지 못했습니다."
    while time.monotonic() < deadline:
        if launched_process is not None:
            returncode = launched_process.poll()
            if returncode is not None:
                raise RuntimeError(
                    _chrome_launch_crash_detail("Chrome DevTools", returncode=returncode)
                )
        payload = _devtools_version(timeout=2.0)
        if payload and payload.get("webSocketDebuggerUrl"):
            return payload
        if time.monotonic() >= crash_check_after and not _is_chrome_running():
            raise RuntimeError(_chrome_launch_crash_detail("Chrome DevTools", extra=last_error))
        time.sleep(0.5)
    raise TimeoutError(last_error)


def _ensure_devtools_browser_running(
    *,
    start_url: str = "about:blank",
    launch_timeout: float = _DEVTOOLS_LAUNCH_TIMEOUT,
) -> dict[str, Any]:
    payload = _devtools_version(timeout=1.5)
    if payload and payload.get("webSocketDebuggerUrl"):
        return payload

    launched_process = _launch_devtools_browser(start_url=start_url)
    return _wait_for_devtools_ready(timeout=launch_timeout, launched_process=launched_process)


def _devtools_new_target(url: str, timeout: float = 10.0) -> dict[str, Any]:
    encoded_url = quote(url, safe=":/?&=%#")
    payload = _devtools_request(f"json/new?{encoded_url}", method="PUT", timeout=timeout)
    if not isinstance(payload, dict) or not payload.get("webSocketDebuggerUrl"):
        raise RuntimeError("Chrome DevTools가 새 탭을 열었지만 websocket 연결 정보를 반환하지 않았습니다.")
    return payload


def _devtools_close_target(target_id: str, timeout: float = 5.0) -> None:
    if not target_id:
        return
    try:
        _devtools_request(f"json/close/{target_id}", timeout=timeout)
    except Exception:
        pass


def _devtools_probe_expression() -> str:
    return (
        "JSON.stringify({"
        "readyState: document.readyState, "
        "bodyExists: !!document.body, "
        "title: document.title || '', "
        "href: location.href || ''"
        "})"
    )


def _devtools_article_expression() -> str:
    return f"""(() => {{
      const bodyText = (document.body && document.body.innerText || '').trim();
      const article = document.querySelector('article');
      const articleText = (article && article.innerText || '').trim();
      const bodyHtml = document.documentElement ? document.documentElement.outerHTML.slice(0, {_HTML_SNIPPET_LIMIT}) : '';
      const articleHtml = article ? article.outerHTML.slice(0, {_HTML_SNIPPET_LIMIT}) : '';
      return JSON.stringify({{
        title: document.title || '',
        href: location.href || '',
        readyState: document.readyState || '',
        bodyText,
        bodyLength: bodyText.length,
        articleText,
        articleLength: articleText.length,
        bodyHtml,
        articleHtml,
        articleCount: document.querySelectorAll('article').length,
        pCount: document.querySelectorAll('p').length
      }});
    }})()"""


async def _devtools_runtime_evaluate(
    websocket_url: str,
    expression: str,
    *,
    timeout: float,
    reload_after_load: bool = False,
) -> Any:
    websockets_module, import_error = _load_websockets()
    if websockets_module is None or import_error is not None:
        raise RuntimeError(_devtools_missing_dependency_message())

    async with websockets_module.connect(
        websocket_url,
        max_size=10_000_000,
        open_timeout=max(1.0, min(timeout, 10.0)),
    ) as websocket:
        request_id = 0

        async def send_command(method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
            nonlocal request_id
            request_id += 1
            payload = {"id": request_id, "method": method}
            if params:
                payload["params"] = params
            await websocket.send(json.dumps(payload))
            while True:
                raw_message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=max(1.0, min(timeout, 10.0)),
                )
                message = json.loads(raw_message)
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    raise RuntimeError(json.dumps(message["error"], ensure_ascii=False))
                return message.get("result", {})

        await send_command("Page.enable")
        await send_command("Runtime.enable")
        await send_command("Page.bringToFront")
        if reload_after_load:
            await send_command("Page.reload", {"ignoreCache": False})

        result = await send_command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
            },
        )
        return result.get("result", {}).get("value")


def _parse_devtools_json_string(raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(raw_value, dict):
        return raw_value
    return {}


def _devtools_probe_page(
    websocket_url: str,
    *,
    timeout: float,
    reload_after_load: bool = False,
) -> dict[str, Any]:
    raw_value = asyncio.run(
        _devtools_runtime_evaluate(
            websocket_url,
            _devtools_probe_expression(),
            timeout=timeout,
            reload_after_load=reload_after_load,
        )
    )
    return _parse_devtools_json_string(raw_value)


def _wait_for_devtools_article_payload(
    websocket_url: str,
    *,
    timeout: float,
    reload_after_load: bool = False,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(2.0, timeout)
    attempt = 0
    latest: dict[str, Any] = {}

    while time.monotonic() < deadline:
        attempt += 1
        raw_value = asyncio.run(
            _devtools_runtime_evaluate(
                websocket_url,
                _devtools_article_expression(),
                timeout=max(2.0, min(10.0, timeout)),
                reload_after_load=reload_after_load and attempt == 1,
            )
        )
        latest = _parse_devtools_json_string(raw_value)
        if not latest:
            time.sleep(_PAGE_SETTLE_DELAY_SECONDS)
            continue

        body_length = int(latest.get("bodyLength") or 0)
        article_length = int(latest.get("articleLength") or 0)
        if latest.get("readyState") == "complete" and (
            article_length >= _TEXT_HEALTHY_THRESHOLD or body_length >= _TEXT_HEALTHY_THRESHOLD
        ):
            return latest
        if body_length >= _TEXT_HEALTHY_THRESHOLD or article_length >= _TEXT_HEALTHY_THRESHOLD:
            return latest
        time.sleep(_PAGE_SETTLE_DELAY_SECONDS)

    return latest


def _extract_devtools_payload(
    payload: dict[str, Any],
    requested_url: str,
    browser: Optional[str],
) -> dict[str, Any]:
    actual_url = str(payload.get("href") or requested_url).strip() or requested_url
    title = str(payload.get("title") or "").strip()
    article_text = str(payload.get("articleText") or "").strip()
    body_text = str(payload.get("bodyText") or "").strip()
    text = article_text if len(article_text) >= _TEXT_HEALTHY_THRESHOLD else body_text
    html = str(payload.get("articleHtml") or payload.get("bodyHtml") or "")[:_HTML_SNIPPET_LIMIT]

    if _detect_bot_block(title, text, html):
        return _failure_result(
            actual_url,
            "봇 차단 페이지가 반환되었습니다. 로그인된 DevTools Chrome 세션인지 확인한 뒤 다시 시도해 주세요.",
            title=title,
            text=text,
            html=html,
        )

    if actual_url == "about:blank":
        return _failure_result(
            actual_url,
            f"{_browser_label(browser)}가 대상 URL로 이동하지 못하고 about:blank에 머물렀습니다.",
            title=title,
            text=text,
            html=html,
        )

    if not _same_registered_host(requested_url, actual_url):
        return _failure_result(
            actual_url,
            f"요청 URL과 다른 페이지가 반환되었습니다: requested={requested_url}, actual={actual_url}",
            title=title,
            text=text,
            html=html,
        )

    if _looks_like_empty_shell(title, text):
        return _failure_result(
            actual_url,
            "기사 본문이 비어 있습니다. 로그인 상태나 차단 페이지 여부를 확인해 주세요.",
            title=title,
            text=text,
            html=html,
        )

    return {
        "success": True,
        "url": actual_url,
        "title": title,
        "text": text,
        "html": html,
        "error": None,
        "paywall": _detect_paywall(text, html),
    }


def _fetch_via_devtools(
    url: str,
    *,
    timeout: int,
    browser: Optional[str],
    reload_after_load: bool,
    close_after: bool,
) -> dict[str, Any]:
    availability_error = _ensure_browser_available(browser)
    if availability_error:
        return _failure_result(url, availability_error)

    cleanup_error: str | None = None
    result: dict[str, Any] | None = None
    target_id = ""
    failure: Exception | None = None

    try:
        _ensure_devtools_browser_running(start_url="about:blank")
        throttle = _wait_for_site_access_slot(url)
        target = _devtools_new_target(url, timeout=max(5.0, timeout))
        target_id = str(target.get("id") or "")
        reload_throttle: Optional[dict[str, Any]] = None
        if reload_after_load:
            reload_throttle = _wait_for_site_access_slot(url)
        payload = _wait_for_devtools_article_payload(
            target["webSocketDebuggerUrl"],
            timeout=max(5.0, timeout),
            reload_after_load=reload_after_load,
        )
        payload = _refine_bloomberg_payload_if_needed(
            url,
            payload,
            websocket_url=target["webSocketDebuggerUrl"],
            timeout=max(5.0, timeout),
        )
        result = _extract_devtools_payload(payload, url, browser)
        if isinstance(result, dict):
            result["site_throttle"] = throttle
            if reload_throttle is not None:
                result["reload_site_throttle"] = reload_throttle
            if "sessionSettleWaitSeconds" in payload:
                result["session_settle_wait_seconds"] = payload["sessionSettleWaitSeconds"]
                result["session_settle_rechecked"] = bool(payload.get("sessionSettleRechecked"))
                if payload.get("sessionSettleKeptOriginal"):
                    result["session_settle_kept_original"] = True
    except Exception as exc:
        failure = exc
    finally:
        try:
            _devtools_close_target(target_id)
        finally:
            if close_after:
                try:
                    _quit_chrome()
                except Exception as cleanup_exc:
                    cleanup_error = str(cleanup_exc)

    if failure is not None:
        detail = _humanize_browser_error(str(failure), browser)
        if cleanup_error:
            detail = f"{detail} | {cleanup_error}"
        return _failure_result(url, detail, detail=str(failure))

    if result is None:
        result = _failure_result(url, f"{_browser_label(browser)} 본문 수집 결과가 비어 있습니다.")

    if cleanup_error:
        combined_error = cleanup_error
        existing_error = str(result.get("error") or "").strip()
        if existing_error:
            combined_error = f"{existing_error} | {cleanup_error}"
        return _failure_result(
            str(result.get("url") or url),
            combined_error,
            title=str(result.get("title") or ""),
            text=str(result.get("text") or ""),
            html=str(result.get("html") or ""),
        )

    return result


def _fetch_result_is_healthy(result: dict[str, Any]) -> bool:
    if not result.get("success"):
        return False
    title = (result.get("title") or "").strip()
    text = (result.get("text") or "").strip()
    if not title and len(text) < _TEXT_HEALTHY_THRESHOLD:
        return False
    return True


def _fetch_result_is_retryable(result: dict[str, Any]) -> bool:
    error_text = "\n".join(
        part.lower()
        for part in [
            str(result.get("error") or ""),
            str(result.get("detail") or ""),
            str(result.get("url") or ""),
        ]
        if part
    )
    if any(signal in error_text for signal in _NON_RETRYABLE_ERROR_SIGNALS):
        return False
    if "about:blank" in error_text:
        return True
    if not error_text:
        return not _fetch_result_is_healthy(result)
    return any(signal in error_text for signal in _RETRY_ERROR_SIGNALS)


def _fetch_once(
    url: str,
    timeout: int = 15,
    close_after: bool = True,
    browser: Optional[str] = None,
    lock_timeout: Optional[float] = None,
    reload_after_load: bool = False,
) -> dict[str, Any]:
    try:
        with _browser_session_lock(
            lock_timeout=lock_timeout,
            reason=f"fetch:{url}",
        ):
            return _fetch_via_devtools(
                url,
                timeout=timeout,
                browser=browser,
                reload_after_load=reload_after_load,
                close_after=close_after,
            )
    except TimeoutError as exc:
        return _browser_lock_error(url, exc)


def fetch(
    url: str,
    timeout: int = 15,
    close_after: bool = True,
    browser: Optional[str] = None,
    max_attempts: int = 2,
    retry_backoff: float = 1.0,
    lock_timeout: Optional[float] = None,
) -> dict[str, Any]:
    """
    URL을 로그인된 Chrome DevTools 세션의 새 탭에서 열고 페이지 콘텐츠를 반환합니다.

    디버그 포트 연결 실패, 빈 본문, about:blank 같은 회복 가능한 실패에 대해
    `max_attempts`만큼 자동 재시도합니다.
    """
    if max_attempts < 1:
        max_attempts = 1

    last_result: Optional[dict[str, Any]] = None
    auto_reload_used = False
    for attempt in range(1, max_attempts + 1):
        result = _fetch_once(
            url,
            timeout=timeout,
            close_after=close_after,
            browser=browser,
            lock_timeout=lock_timeout,
        )
        result["attempts"] = attempt
        if _should_try_bloomberg_reload(
            url,
            result,
            close_after=close_after,
            reload_used=auto_reload_used,
        ):
            auto_reload_used = True
            result = fetch_with_reload(
                url,
                timeout=timeout,
                browser=browser,
                lock_timeout=lock_timeout,
                close_after=close_after,
            )
            result["attempts"] = attempt
        if _fetch_result_is_healthy(result):
            return result
        last_result = result
        if attempt >= max_attempts:
            break
        if not _fetch_result_is_retryable(result):
            break
        time.sleep(max(0.0, retry_backoff))

    assert last_result is not None
    return last_result


def fetch_with_reload(
    url: str,
    timeout: int = 15,
    browser: Optional[str] = None,
    lock_timeout: Optional[float] = None,
    close_after: bool = True,
) -> dict[str, Any]:
    """
    페이지 로드 후 새로고침을 1회 수행합니다.
    Bloomberg paywall 또는 로그인/쿠키 미반영 상태가 보일 때 사용합니다.
    """
    return _fetch_once(
        url,
        timeout=timeout,
        close_after=close_after,
        browser=browser,
        lock_timeout=lock_timeout,
        reload_after_load=True,
    )


def prepare_session(
    url: str,
    *,
    browser: Optional[str] = None,
    lock_timeout: Optional[float] = None,
    timeout: int = _SESSION_SETUP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """
    DevTools용 Chrome 프로필에서 수동 로그인 세션을 준비합니다.
    """
    if not sys.stdin.isatty():
        return _failure_result(url, "session-setup은 대화형 터미널에서만 실행할 수 있습니다.")

    availability_error = _ensure_browser_available(browser)
    if availability_error:
        return _failure_result(url, availability_error)

    cleanup_error: str | None = None
    result: dict[str, Any] | None = None

    try:
        with _browser_session_lock(lock_timeout=lock_timeout, reason=f"session-setup:{url}"):
            _ensure_devtools_browser_running(start_url="about:blank", launch_timeout=max(10.0, timeout))
            target = _devtools_new_target(url, timeout=max(5.0, timeout))
            try:
                print(
                    "[session-setup] 디버그 Chrome 프로필에서 로그인/구독 인증을 완료한 뒤 Enter를 눌러 계속하세요. "
                    f"profile={_browser_profile_path(browser)} port={_DEVTOOLS_PORT}",
                    file=sys.stderr,
                )
                input()
                result = {
                    "success": True,
                    "url": url,
                    "profile_path": str(_browser_profile_path(browser)),
                    "devtools_port": _DEVTOOLS_PORT,
                    "error": None,
                }
            finally:
                _devtools_close_target(str(target.get("id") or ""))
                try:
                    _quit_chrome()
                except Exception as cleanup_exc:
                    cleanup_error = str(cleanup_exc)
    except Exception as exc:
        detail = _humanize_browser_error(str(exc), browser)
        if cleanup_error:
            detail = f"{detail} | {cleanup_error}"
        return _failure_result(url, detail, detail=str(exc))

    if cleanup_error:
        return _failure_result(url, cleanup_error)

    return result or _failure_result(url, "세션 준비 결과가 비어 있습니다.")


def get_article_links(url: str, source: str, timeout: int = 15) -> list[dict[str, str]]:
    """
    헤드라인 페이지에서 기사 링크 목록을 추출합니다.

    Args:
        source: "dow_jones" | "wsj" | "barrons" | "bloomberg"
    """
    del url
    return _fetch_rss_links_for_source(source, timeout=timeout)


def bloomberg_load_more(url: str, clicks: int = 2, timeout: int = 20) -> list[dict[str, str]]:
    """
    Bloomberg 기사 목록을 RSS CSV에서 반환합니다.

    기존 인터페이스 호환을 위해 함수명은 유지하지만,
    더 이상 브라우저에서 Load More를 클릭하지 않습니다.
    """
    del url
    del clicks
    return _fetch_rss_links_for_source("bloomberg", timeout=timeout)


def diagnose(
    browser: Optional[str] = None,
    lock_timeout: Optional[float] = None,
    close_after: bool = True,
) -> dict[str, Any]:
    """설정된 Chrome DevTools 세션 연결/페이지 로드 가능 여부를 진단합니다."""
    normalized = _normalize_browser(browser)
    browser_label = _browser_label(normalized)
    profile_path = _browser_profile_path(normalized)
    app_path = _resolve_chrome_app_path()
    executable_path = _resolve_chrome_executable_path()

    result: dict[str, Any] = {
        "browser": normalized,
        "browser_label": browser_label,
        "browser_engine": "chrome-devtools",
        "profile_path": str(profile_path),
        "chrome_app_name": _CHROME_APP_NAME,
        "chrome_app_path": str(app_path) if app_path is not None else None,
        "chrome_executable_path": str(executable_path) if executable_path is not None else None,
        "chrome_launch_target": _chrome_launch_target(),
        "chrome_launch_mode": _chrome_launch_mode(),
        "chrome_launch_strategies": _chrome_launch_strategies(),
        "devtools_port": _DEVTOOLS_PORT,
        "headless": False,
    }

    availability_error = _ensure_browser_available(normalized)
    result["availability"] = {
        "ok": availability_error is None,
        "detail": availability_error,
    }

    if availability_error is not None:
        detail = availability_error
        result["launch_probe"] = {"ok": False, "detail": detail}
        result["attach"] = {"ok": False, "stdout": "", "stderr": "", "detail": detail}
        result["javascript"] = {"ok": False, "stdout": "", "stderr": "", "detail": detail}
        result["cleanup"] = {"ok": True, "detail": None}
        result["ready"] = False
        return result

    cleanup_error: str | None = None
    try:
        with _browser_session_lock(
            lock_timeout=lock_timeout,
            reason=f"diagnose:{normalized}",
        ):
            version = _ensure_devtools_browser_running(start_url="about:blank")
            target = _devtools_new_target("about:blank", timeout=5.0)
            try:
                js_result = _devtools_probe_page(
                    target["webSocketDebuggerUrl"],
                    timeout=5.0,
                )
            finally:
                _devtools_close_target(str(target.get("id") or ""))
                if close_after:
                    try:
                        _quit_chrome()
                    except Exception as cleanup_exc:
                        cleanup_error = str(cleanup_exc)
    except TimeoutError as exc:
        detail = str(exc)
        if cleanup_error:
            detail = f"{detail} | {cleanup_error}"
        result["launch_probe"] = {"ok": False, "detail": detail}
        result["attach"] = {"ok": False, "stdout": "", "stderr": "", "detail": detail}
        result["javascript"] = {"ok": False, "stdout": "", "stderr": "", "detail": detail}
        result["cleanup"] = {"ok": cleanup_error is None, "detail": cleanup_error}
        result["ready"] = False
        return result
    except Exception as exc:
        detail = _humanize_browser_error(str(exc), normalized)
        if cleanup_error:
            detail = f"{detail} | {cleanup_error}"
        result["launch_probe"] = {"ok": False, "detail": detail}
        result["attach"] = {"ok": False, "stdout": "", "stderr": "", "detail": detail}
        result["javascript"] = {"ok": False, "stdout": "", "stderr": "", "detail": detail}
        result["cleanup"] = {"ok": cleanup_error is None, "detail": cleanup_error}
        result["ready"] = False
        return result

    result["launch_probe"] = {
        "ok": True,
        "detail": f"{browser_label} launch succeeded.",
    }
    result["attach"] = {
        "ok": True,
        "stdout": version.get("Browser", browser_label),
        "stderr": "",
        "detail": None,
    }
    result["javascript"] = {
        "ok": bool(js_result.get("bodyExists")) and js_result.get("readyState") == "complete",
        "stdout": json.dumps(js_result, ensure_ascii=False),
        "stderr": "",
        "detail": None,
    }
    result["cleanup"] = {"ok": cleanup_error is None, "detail": cleanup_error}
    result["ready"] = (
        result["availability"]["ok"]
        and result["attach"]["ok"]
        and result["javascript"]["ok"]
    )
    return result


def close_browser(
    browser: Optional[str] = None,
    lock_timeout: Optional[float] = None,
) -> dict[str, Any]:
    """배치 수집 뒤 남아 있는 Chrome DevTools 브라우저를 정리 종료합니다."""
    normalized = _normalize_browser(browser)

    try:
        with _browser_session_lock(
            lock_timeout=lock_timeout,
            reason=f"close-browser:{normalized}",
        ):
            _quit_chrome()
    except TimeoutError as exc:
        return {
            "ok": False,
            "browser": normalized,
            "closed": False,
            "detail": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "browser": normalized,
            "closed": False,
            "detail": _humanize_browser_error(str(exc), normalized),
        }

    return {
        "ok": True,
        "browser": normalized,
        "closed": True,
        "detail": None,
    }


if __name__ == "__main__":
    _maybe_reexec_with_project_venv()
    parser = argparse.ArgumentParser(description="Browser fetch utility for news articles")
    parser.add_argument("url", nargs="?", help="대상 URL")
    parser.add_argument(
        "--source",
        default="dow_jones",
        choices=["dow_jones", "wsj", "barrons", "bloomberg"],
        help="RSS 링크 목록 소스",
    )
    parser.add_argument(
        "--browser",
        default=_normalize_browser(),
        choices=["chrome"],
        help="본문 수집/진단에 사용할 브라우저 키 (현재 chrome만 지원)",
    )
    parser.add_argument("--links-only", action="store_true", help="RSS에서 기사 링크 목록만 추출")
    parser.add_argument(
        "--load-more",
        action="store_true",
        help="Bloomberg RSS에서 기사 링크 목록 추출 (기존 호환용 옵션)",
    )
    parser.add_argument("--reload", action="store_true", help="기사 페이지 새로고침 후 본문 재추출")
    parser.add_argument(
        "--session-setup",
        action="store_true",
        help="로그인/구독 세션을 수동으로 준비",
    )
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=2,
        help="fetch 실패 시 자동 재시도 횟수 (기본 2)",
    )
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=_DEFAULT_BROWSER_LOCK_TIMEOUT,
        help="다른 기사 연결 작업이 끝나기를 기다릴 최대 시간(초, 기본 90)",
    )
    parser.add_argument("--no-close", action="store_true", help="수집 후 Chrome 앱을 종료하지 않음")
    parser.add_argument(
        "--close-browser",
        action="store_true",
        help="남아 있는 Chrome 앱을 정리 종료하고 결과를 JSON으로 반환",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Chrome DevTools 연결/페이지 실행 상태 진단",
    )
    args = parser.parse_args()

    if args.close_browser:
        result = close_browser(
            args.browser,
            lock_timeout=args.lock_timeout,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("ok") else 1)
    elif args.diagnose:
        print(
            json.dumps(
                diagnose(
                    args.browser,
                    lock_timeout=args.lock_timeout,
                    close_after=not args.no_close,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.session_setup:
        if not args.url:
            parser.error("session-setup에는 URL이 필요합니다.")
        result = prepare_session(
            args.url,
            browser=args.browser,
            lock_timeout=args.lock_timeout,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not args.url:
        parser.error("URL이 필요합니다. 진단만 할 때는 --diagnose를 사용하세요.")
    elif args.links_only:
        links = get_article_links(args.url, args.source, args.timeout)
        print(json.dumps(links, ensure_ascii=False, indent=2))
    elif args.load_more:
        links = bloomberg_load_more(args.url, timeout=args.timeout)
        print(json.dumps(links, ensure_ascii=False, indent=2))
    elif args.reload:
        result = fetch_with_reload(
            args.url,
            args.timeout,
            browser=args.browser,
            lock_timeout=args.lock_timeout,
            close_after=not args.no_close,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        result = fetch(
            args.url,
            args.timeout,
            not args.no_close,
            browser=args.browser,
            max_attempts=args.max_attempts,
            lock_timeout=args.lock_timeout,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
