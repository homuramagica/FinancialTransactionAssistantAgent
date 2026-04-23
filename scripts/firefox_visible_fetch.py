#!/usr/bin/env python3
"""
firefox_visible_fetch.py - Firefox 일반 모드를 보이는 상태로만 조작해 기사 본문을 수집합니다.

원칙:
- Firefox 일반 모드를 보이는 상태로만 사용합니다.
- Playwright, Firefox remote debugging, WebDriver, BiDi는 사용하지 않습니다.
- 기본 동작은 기사 본문을 확보하면 탭을 닫고 Firefox 앱도 종료하지만, batch 수집에서는 세션을 재사용할 수 있습니다.
- Bloomberg는 기본 20초, Dow Jones 계열은 기본 10초 간격을 지킵니다.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import html
import json
import os
import plistlib
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse


REPO_ROOT = Path(__file__).resolve().parent.parent
_BROWSER_LOCK_PATH = os.environ.get("NEWS_FETCH_LOCK_PATH", "/tmp/safari_fetch_browser.lock")
_DEFAULT_BROWSER_LOCK_TIMEOUT = float(os.environ.get("NEWS_FETCH_LOCK_TIMEOUT", "90"))
_BROWSER_LOCK_POLL_INTERVAL = 0.25
_SITE_THROTTLE_STATE_PATH = os.environ.get(
    "NEWS_FETCH_SITE_THROTTLE_STATE_PATH",
    "/tmp/safari_fetch_site_throttle.json",
)
_SITE_THROTTLE_INTERVAL_SECONDS = float(
    os.environ.get("NEWS_FETCH_SITE_THROTTLE_INTERVAL_SECONDS", "10")
)
_BLOOMBERG_SITE_THROTTLE_INTERVAL_SECONDS = float(
    os.environ.get("NEWS_FETCH_BLOOMBERG_SITE_THROTTLE_INTERVAL_SECONDS", "20")
)
_DOW_JONES_SITE_THROTTLE_INTERVAL_SECONDS = float(
    os.environ.get("NEWS_FETCH_DOW_JONES_SITE_THROTTLE_INTERVAL_SECONDS", "10")
)
_PAGE_SETTLE_SECONDS = float(os.environ.get("NEWS_FETCH_FIREFOX_SETTLE_SECONDS", "6"))
_COPY_SETTLE_SECONDS = float(os.environ.get("NEWS_FETCH_FIREFOX_COPY_SECONDS", "0.4"))
_SOURCE_SETTLE_SECONDS = float(os.environ.get("NEWS_FETCH_FIREFOX_SOURCE_SECONDS", "1.2"))
_READY_POLL_SECONDS = float(os.environ.get("NEWS_FETCH_FIREFOX_READY_POLL_SECONDS", "0.25"))
_HTML_SNIPPET_LIMIT = 60_000
_TEXT_HEALTHY_THRESHOLD = 200
_EXECUTABLE_PROBE_TIMEOUT_SECONDS = float(
    os.environ.get("NEWS_FETCH_FIREFOX_EXECUTABLE_PROBE_TIMEOUT_SECONDS", "5")
)
_FIREFOX_APP_NAME = os.environ.get("NEWS_FETCH_FIREFOX_APP_NAME", "Firefox").strip() or "Firefox"
_FIREFOX_APP_PATH = os.environ.get("NEWS_FETCH_FIREFOX_APP_PATH", "").strip()
_FIREFOX_BUNDLE_ID = os.environ.get("NEWS_FETCH_FIREFOX_BUNDLE_ID", "org.mozilla.firefox").strip()
_FIREFOX_DIRECT_LAUNCH_SETTLE_SECONDS = float(
    os.environ.get("NEWS_FETCH_FIREFOX_DIRECT_LAUNCH_SETTLE_SECONDS", "1")
)
_COMMAND_KEY_CODES = {
    "a": 0,
    "c": 8,
    "w": 13,
    "u": 32,
    "l": 37,
}

_PAYWALL_SIGNALS = (
    "subscribe to continue",
    "subscription required",
    "sign in to read",
    "already a subscriber",
    "log in to continue",
    "access this article",
    "create a free account",
    "이미 구독자이신가요",
    "로그인이 필요합니다",
)
_LOGIN_PROMPT_SIGNALS = (
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


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _canonicalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if not parsed.scheme:
        raise ValueError("URL에 scheme이 없습니다.")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def _host_matches(url: str, host: str) -> bool:
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return False
    normalized_host = host.lower()
    return netloc == normalized_host or netloc.endswith("." + normalized_host)


def _site_access_key(url: str) -> str:
    canonical_url = _canonicalize_url(url)
    if _host_matches(canonical_url, "bloomberg.com"):
        return "bloomberg"
    if _host_matches(canonical_url, "wsj.com") or _host_matches(canonical_url, "barrons.com"):
        return "dow_jones"
    try:
        return urlparse(canonical_url).netloc.lower() or "unknown"
    except Exception:
        return "unknown"


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
    state: dict[str, float] = {}
    for key, value in payload.items():
        try:
            state[str(key)] = float(value)
        except Exception:
            continue
    return state


def _save_site_throttle_state(state: dict[str, float]) -> None:
    path = Path(_SITE_THROTTLE_STATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _site_throttle_interval_for(site: str) -> float:
    if site == "bloomberg":
        return max(0.0, float(_BLOOMBERG_SITE_THROTTLE_INTERVAL_SECONDS))
    if site == "dow_jones":
        return max(0.0, float(_DOW_JONES_SITE_THROTTLE_INTERVAL_SECONDS))
    return max(0.0, float(_SITE_THROTTLE_INTERVAL_SECONDS))


def _wait_for_site_access_slot(url: str) -> dict[str, Any]:
    site = _site_access_key(url)
    interval = _site_throttle_interval_for(site)
    if interval <= 0:
        return {"site": site, "wait_seconds": 0.0, "throttled": False}

    state = _load_site_throttle_state()
    now = time.time()
    last_access = float(state.get(site, 0.0) or 0.0)
    wait_seconds = max(0.0, (last_access + interval) - now) if last_access else 0.0
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    accessed_at = time.time()
    state[site] = accessed_at
    _save_site_throttle_state(state)
    return {
        "site": site,
        "wait_seconds": round(wait_seconds, 3),
        "throttled": wait_seconds > 0,
        "accessed_at": accessed_at,
    }


@contextlib.contextmanager
def _browser_session_lock(
    lock_timeout: Optional[float] = None,
    reason: str = "firefox_visible_fetch",
):
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
                        f"{timeout:g}초 동안 대기했지만 브라우저 락을 확보하지 못했습니다."
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


def _default_failure(url: str, error: str) -> dict[str, Any]:
    return {
        "success": False,
        "url": url,
        "title": "",
        "text": "",
        "html": "",
        "error": error,
        "paywall": False,
        "browser_engine": "firefox-visible",
    }


def _firefox_app_candidates() -> list[str]:
    candidates: list[str] = []
    if _FIREFOX_APP_PATH:
        candidates.append(_FIREFOX_APP_PATH)
    candidates.extend(
        [
            "/Applications/Firefox.app",
            str(Path.home() / "Applications" / "Firefox.app"),
            _FIREFOX_APP_NAME,
        ]
    )
    return _dedupe_preserve_order(candidates)


def _run_command(command: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _run_applescript(script: str) -> subprocess.CompletedProcess[str]:
    return _run_command(["osascript", "-"], input_text=script)


def _is_firefox_running() -> bool:
    completed = _run_applescript(f'return application "{_FIREFOX_APP_NAME}" is running')
    if completed.returncode != 0:
        return False
    return (completed.stdout or "").strip().lower() == "true"


def _compact_command_detail(detail: str, *, limit: int = 280) -> str:
    lines = [line.strip() for line in detail.splitlines() if line.strip()]
    filtered = [line for line in lines if not line.startswith("[WARN ")]
    chosen = filtered or lines
    compact = " | ".join(chosen[:2])
    if len(compact) > limit:
        return compact[: limit - 3].rstrip() + "..."
    return compact


def _firefox_bundle_path(candidate: str) -> Path | None:
    path = Path(candidate).expanduser()
    if path.suffix.lower() != ".app":
        return None
    return path


def _firefox_info_plist_path(bundle_path: Path) -> Path:
    return bundle_path / "Contents" / "Info.plist"


def _read_firefox_info_plist(bundle_path: Path) -> dict[str, Any] | None:
    plist_path = _firefox_info_plist_path(bundle_path)
    try:
        with open(plist_path, "rb") as handle:
            payload = plistlib.load(handle)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _firefox_bundle_executable_path(candidate: str) -> Path | None:
    bundle_path = _firefox_bundle_path(candidate)
    if bundle_path is None:
        return None

    info = _read_firefox_info_plist(bundle_path) or {}
    executable_name = str(info.get("CFBundleExecutable") or "").strip()

    candidates: list[Path] = []
    if executable_name:
        candidates.append(bundle_path / "Contents" / "MacOS" / executable_name)

    candidates.append(bundle_path / "Contents" / "MacOS" / "firefox")

    seen: set[str] = set()
    for executable_path in candidates:
        normalized = str(executable_path)
        if normalized in seen:
            continue
        seen.add(normalized)
        if executable_path.exists() and executable_path.is_file():
            return executable_path
    return None


def _probe_firefox_executable(executable: Path) -> str | None:
    try:
        completed = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=max(1.0, _EXECUTABLE_PROBE_TIMEOUT_SECONDS),
        )
    except subprocess.TimeoutExpired:
        timeout = max(1.0, _EXECUTABLE_PROBE_TIMEOUT_SECONDS)
        return (
            "Firefox 실행 파일 점검이 제한 시간을 넘겼습니다. "
            f"executable={executable} timeout={timeout:g}s"
        )
    except OSError as exc:
        return f"Firefox 실행 파일을 실행하지 못했습니다. executable={executable} error={exc}"

    if completed.returncode == 0:
        return None

    detail = (completed.stderr or completed.stdout or "").strip() or f"exit={completed.returncode}"
    detail = _compact_command_detail(detail)
    return (
        "Firefox 실행 파일이 정상 응답하지 않았습니다. "
        f"executable={executable} detail={detail}"
    )


def _probe_firefox_candidate(candidate: str) -> str | None:
    bundle_path = _firefox_bundle_path(candidate)
    if bundle_path is not None:
        if not bundle_path.exists():
            return f"{candidate}: app bundle not found"
        executable = _firefox_bundle_executable_path(candidate)
        if executable is None or not executable.exists():
            return f"{candidate}: executable missing ({executable})"
        if not os.access(executable, os.X_OK):
            return f"{candidate}: executable is not runnable ({executable})"
        executable_issue = _probe_firefox_executable(executable)
        if executable_issue is not None:
            return f"{candidate}: {executable_issue}"

    probe = _run_command(["open", "-Ra", candidate])
    if probe.returncode == 0:
        return None

    detail = (probe.stderr or probe.stdout or "").strip() or f"exit={probe.returncode}"
    return f"{candidate}: {detail}"


def _firefox_launch_attempts(
    url: str,
    *,
    prefer_reuse: bool = False,
) -> list[tuple[str, list[str]]]:
    attempts: list[tuple[str, list[str]]] = []
    candidates = _firefox_app_candidates()

    if prefer_reuse and _is_firefox_running():
        for candidate in candidates:
            attempts.append((f"open -a {candidate}", ["open", "-a", candidate, url]))
        if _FIREFOX_BUNDLE_ID:
            attempts.append((f"open -b {_FIREFOX_BUNDLE_ID}", ["open", "-b", _FIREFOX_BUNDLE_ID, url]))

    for candidate in candidates:
        attempts.append((f"open -na {candidate}", ["open", "-na", candidate, url]))
        attempts.append((f"open -a {candidate}", ["open", "-a", candidate, url]))

    if _FIREFOX_BUNDLE_ID:
        attempts.append((f"open -b {_FIREFOX_BUNDLE_ID}", ["open", "-b", _FIREFOX_BUNDLE_ID, url]))

    for candidate in candidates:
        executable = _firefox_bundle_executable_path(candidate)
        if executable is None or not executable.exists() or not os.access(executable, os.X_OK):
            continue
        attempts.append((f"{executable} -new-tab", [str(executable), "-new-tab", url]))

    deduped: list[tuple[str, list[str]]] = []
    seen_commands: set[tuple[str, ...]] = set()
    for label, command in attempts:
        key = tuple(command)
        if key in seen_commands:
            continue
        seen_commands.add(key)
        deduped.append((label, command))
    return deduped


def _launch_firefox_direct(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            start_new_session=True,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(command, 1, "", str(exc))

    time.sleep(max(0.0, _FIREFOX_DIRECT_LAUNCH_SETTLE_SECONDS))
    returncode = process.poll()

    stderr = ""
    if process.stderr is not None:
        try:
            if returncode is not None:
                stderr = process.stderr.read() or ""
        finally:
            process.stderr.close()

    if returncode not in (None, 0):
        return subprocess.CompletedProcess(command, returncode, "", stderr)

    return subprocess.CompletedProcess(command, 0, "", stderr)


def _run_firefox_launch_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    if command and command[0] == "open":
        return _run_command(command)
    return _launch_firefox_direct(command)


def _wait_for_firefox_ready(timeout: float | None = None) -> None:
    deadline = time.monotonic() + max(
        1.0,
        timeout or max(_FIREFOX_DIRECT_LAUNCH_SETTLE_SECONDS, 1.5),
    )
    last_detail = ""
    while time.monotonic() < deadline:
        completed = _run_applescript(
            f'''
if application "{_FIREFOX_APP_NAME}" is running then
    tell application "{_FIREFOX_APP_NAME}" to get name
end if
'''
        )
        if completed.returncode == 0 and (completed.stdout or "").strip():
            return

        last_detail = (completed.stderr or completed.stdout or "").strip()
        time.sleep(max(0.1, _READY_POLL_SECONDS))

    raise RuntimeError(last_detail or "Firefox가 AppleScript에 응답할 준비를 하지 못했습니다.")


def _ensure_firefox_available() -> str | None:
    if sys.platform != "darwin":
        return "Firefox 일반 모드 수집은 현재 macOS에서만 지원합니다."

    probe_osascript = _run_command(["osascript", "-e", 'return "ok"'])
    if probe_osascript.returncode != 0:
        stderr = (probe_osascript.stderr or "").strip()
        return f"osascript를 실행하지 못했습니다. {stderr}".strip()

    checked: list[str] = []
    for candidate in _firefox_app_candidates():
        issue = _probe_firefox_candidate(candidate)
        checked.append(issue or f"{candidate}: ok")
        if issue is None:
            return None

    checked_text = "; ".join(checked) if checked else "no candidates"
    return f"Firefox 앱을 찾지 못했습니다. checked: {checked_text}"


def _diagnose(
    *,
    lock_timeout: float = _DEFAULT_BROWSER_LOCK_TIMEOUT,
    close_after: bool = True,
) -> dict[str, Any]:
    availability = _ensure_firefox_available()
    launch_probe = {
        "ok": False,
        "detail": "Firefox launch probe는 availability 통과 후에만 실행합니다.",
    }
    if availability is None:
        launch_probe = _run_firefox_launch_probe(
            lock_timeout=lock_timeout,
            close_after=close_after,
        )
    return {
        "ready": availability is None and launch_probe.get("ok", False),
        "browser": "firefox-visible",
        "mode": "visible-ui-only",
        "remote_debugging": False,
        "playwright": False,
        "webdriver": False,
        "availability": {
            "ok": availability is None,
            "detail": availability or "Firefox 일반 모드와 osascript를 사용할 수 있습니다.",
        },
        "launch_probe": launch_probe,
    }


def _clear_clipboard() -> None:
    _run_command(["pbcopy"], input_text="")


def _read_clipboard() -> str:
    completed = _run_command(["pbpaste"])
    return completed.stdout or ""


def _open_url_in_firefox(url: str, *, prefer_reuse: bool = False) -> None:
    errors: list[str] = []
    for label, command in _firefox_launch_attempts(url, prefer_reuse=prefer_reuse):
        completed = _run_firefox_launch_command(command)
        if completed.returncode == 0:
            try:
                _wait_for_firefox_ready()
                return
            except RuntimeError as exc:
                errors.append(f"{label} ready-check: {exc}")
                continue

        detail = (completed.stderr or completed.stdout or "").strip() or f"exit={completed.returncode}"
        detail = _compact_command_detail(detail)
        errors.append(f"{label}: {detail}")

    joined = " | ".join(errors) if errors else "시도 가능한 Firefox launch target이 없습니다."
    raise RuntimeError(f"Firefox로 URL을 열지 못했습니다. {joined}".strip())


def _ui_script(lines: list[str]) -> str:
    body = "\n".join(lines)
    return f"""
tell application "{_FIREFOX_APP_NAME}" to activate
delay 0.25
tell application "System Events"
{body}
end tell
"""


def _command_key_code_line(key: str) -> str:
    normalized = (key or "").strip().lower()
    if normalized not in _COMMAND_KEY_CODES:
        raise ValueError(f"지원하지 않는 command key입니다: {key}")
    # `keystroke "a"` depends on the current keyboard layout / IME.
    # Use key codes so Firefox automation stays reliable on Korean input sources too.
    return f"    key code {_COMMAND_KEY_CODES[normalized]} using command down"


def _copy_visible_page_text() -> str:
    _clear_clipboard()
    script = _ui_script(
        [
            _command_key_code_line("a"),
            f"    delay {_COPY_SETTLE_SECONDS}",
            _command_key_code_line("c"),
            f"    delay {_COPY_SETTLE_SECONDS}",
        ]
    )
    completed = _run_applescript(script)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Firefox 화면 본문 복사에 실패했습니다. {detail}".strip())
    return _read_clipboard()


def _copy_view_source_html_and_close_tabs() -> str:
    _clear_clipboard()
    script = _ui_script(
        [
            _command_key_code_line("u"),
            f"    delay {_SOURCE_SETTLE_SECONDS}",
            _command_key_code_line("a"),
            f"    delay {_COPY_SETTLE_SECONDS}",
            _command_key_code_line("c"),
            f"    delay {_COPY_SETTLE_SECONDS}",
            _command_key_code_line("w"),
            "    delay 0.2",
            _command_key_code_line("w"),
            "    delay 0.2",
        ]
    )
    completed = _run_applescript(script)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Firefox 페이지 소스 복사에 실패했습니다. {detail}".strip())
    return _read_clipboard()


def _quit_firefox() -> None:
    script = f"""
if application "{_FIREFOX_APP_NAME}" is running then
    tell application "{_FIREFOX_APP_NAME}" to quit
end if
"""
    completed = _run_applescript(script)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Firefox 종료에 실패했습니다. {detail}".strip())


def _run_firefox_launch_probe(
    *,
    lock_timeout: float,
    close_after: bool = True,
) -> dict[str, Any]:
    try:
        with _browser_session_lock(
            lock_timeout=lock_timeout,
            reason="firefox_visible_fetch:diagnose",
        ):
            _open_url_in_firefox("about:blank", prefer_reuse=not close_after)
    except Exception as exc:
        try:
            _quit_firefox()
        except Exception:
            pass
        return {
            "ok": False,
            "detail": str(exc).strip() or "Firefox launch probe에 실패했습니다.",
        }

    if close_after:
        try:
            _quit_firefox()
        except Exception as exc:
            return {
                "ok": False,
                "detail": str(exc).strip() or "Firefox launch probe 뒤 종료에 실패했습니다.",
            }

    return {
        "ok": True,
        "detail": "Firefox launch probe가 성공했습니다.",
    }


def _normalize_lines(text: str) -> str:
    seen: set[str] = set()
    normalized: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        collapsed = re.sub(r"\s+", " ", line).strip()
        if not collapsed:
            continue
        if collapsed in seen:
            continue
        seen.add(collapsed)
        normalized.append(collapsed)
    return "\n".join(normalized)


def _fallback_strip_html(html_text: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript|svg|template).*?>.*?</\1>", " ", html_text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p\s*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return _normalize_lines(text)


def _decode_json_string_fragment(value: str) -> str:
    try:
        decoded = json.loads(f'"{value}"')
    except Exception:
        decoded = value
        decoded = decoded.replace("\\/", "/")
        decoded = decoded.replace("\\n", "\n")
        decoded = decoded.replace("\\r", "\n")
        decoded = decoded.replace("\\t", " ")
        decoded = decoded.replace('\\"', '"')
    if "<" in decoded and ">" in decoded:
        return _fallback_strip_html(decoded)
    return _normalize_lines(html.unescape(decoded))


def _extract_embedded_article_text(html_text: str) -> tuple[str, str]:
    title = ""
    best_text = ""
    script_blocks = re.findall(
        r'(?is)<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
    )
    candidate_blocks = script_blocks or [html_text]

    for block in candidate_blocks:
        if not title:
            title_matches = re.findall(
                r'"(?:headline|name|title)"\s*:\s*"((?:\\.|[^"\\]){3,})"',
                block,
                flags=re.IGNORECASE,
            )
            for candidate in title_matches:
                decoded_title = _decode_json_string_fragment(candidate)
                if len(decoded_title) >= 3:
                    title = decoded_title
                    break

        body_matches = re.findall(
            r'"(?:articleBody|article_body|articleText|text)"\s*:\s*"((?:\\.|[^"\\]){80,})"',
            block,
            flags=re.IGNORECASE,
        )
        for candidate in body_matches:
            decoded_body = _decode_json_string_fragment(candidate)
            if len(decoded_body) > len(best_text):
                best_text = decoded_body

    return title, best_text


def _extract_title_and_text(html_text: str, rendered_text: str) -> tuple[str, str]:
    if not html_text.strip():
        return "", _normalize_lines(rendered_text)

    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        title = ""
        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html_text)
        if title_match:
            title = html.unescape(re.sub(r"\s+", " ", title_match.group(1))).strip()
        text = _fallback_strip_html(html_text)
        embedded_title, embedded_text = _extract_embedded_article_text(html_text)
        if embedded_title and (not title or len(embedded_text) > len(text)):
            title = embedded_title
        if len(embedded_text) > len(text):
            text = embedded_text
        if len(text) < _TEXT_HEALTHY_THRESHOLD:
            text = _normalize_lines(rendered_text)
        return title, text

    soup = BeautifulSoup(html_text, "html.parser")
    for node in soup(["script", "style", "noscript", "svg", "template"]):
        node.decompose()

    title = ""
    meta_title = soup.find("meta", attrs={"property": "og:title"}) or soup.find(
        "meta",
        attrs={"name": "twitter:title"},
    )
    if meta_title and meta_title.get("content"):
        title = str(meta_title.get("content")).strip()
    elif soup.title and soup.title.string:
        title = str(soup.title.string).strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text(" ", strip=True)

    root = soup.find("article") or soup.find("main") or soup.body
    text = root.get_text("\n", strip=True) if root else ""
    text = _normalize_lines(text)
    embedded_title, embedded_text = _extract_embedded_article_text(html_text)
    if embedded_title and (not title or len(embedded_text) > len(text)):
        title = embedded_title
    if len(embedded_text) > len(text):
        text = embedded_text
    if len(text) < _TEXT_HEALTHY_THRESHOLD:
        text = _normalize_lines(rendered_text)
    return title, text


def _detect_paywall(text: str, html_text: str) -> bool:
    combined = (text + "\n" + html_text[:10_000]).lower()
    return len(text.strip()) < 400 and any(signal in combined for signal in _PAYWALL_SIGNALS)


def _contains_login_prompt(text: str, html_text: str) -> bool:
    combined = (text + "\n" + html_text[:10_000]).lower()
    return any(signal in combined for signal in _LOGIN_PROMPT_SIGNALS)


def _detect_bot_block(title: str, text: str, html_text: str) -> bool:
    combined = "\n".join([title, text[:2_000], html_text[:5_000]]).lower()
    return any(signal in combined for signal in _BOT_BLOCK_SIGNALS)


def fetch_article(
    url: str,
    *,
    timeout: float = 0.0,
    lock_timeout: float = _DEFAULT_BROWSER_LOCK_TIMEOUT,
    close_after: bool = True,
) -> dict[str, Any]:
    del timeout
    try:
        canonical_url = _canonicalize_url(url)
    except Exception as exc:
        return _default_failure(url, f"잘못된 URL입니다. {exc}")

    availability = _ensure_firefox_available()
    if availability is not None:
        return _default_failure(canonical_url, availability)

    throttle: dict[str, Any] = {}
    rendered_text = ""
    html_text = ""
    cleanup_error: str | None = None

    try:
        with _browser_session_lock(lock_timeout=lock_timeout):
            throttle = _wait_for_site_access_slot(canonical_url)
            try:
                _open_url_in_firefox(
                    canonical_url,
                    prefer_reuse=not close_after,
                )
                time.sleep(max(0.0, _PAGE_SETTLE_SECONDS))
                rendered_text = _copy_visible_page_text()
                html_text = _copy_view_source_html_and_close_tabs()
            finally:
                if close_after:
                    try:
                        _quit_firefox()
                    except Exception as cleanup_exc:
                        cleanup_error = str(cleanup_exc)
    except Exception as exc:
        detail = str(exc)
        if cleanup_error:
            detail = f"{detail} | {cleanup_error}"
        return _default_failure(canonical_url, detail)

    if cleanup_error:
        return _default_failure(canonical_url, cleanup_error)

    html_snippet = (html_text or "")[:_HTML_SNIPPET_LIMIT]
    title, extracted_text = _extract_title_and_text(html_snippet, rendered_text)

    if _detect_bot_block(title, extracted_text, html_snippet):
        return _default_failure(canonical_url, "봇 제한 페이지가 반환되었습니다.")

    paywall = _detect_paywall(extracted_text, html_snippet)
    if paywall and _contains_login_prompt(extracted_text, html_snippet):
        return {
            "success": False,
            "url": canonical_url,
            "title": title,
            "text": extracted_text,
            "html": html_snippet,
            "error": "로그인 또는 구독 확인이 필요한 화면이 반환되었습니다.",
            "paywall": True,
            "browser_engine": "firefox-visible",
            "throttle": throttle,
        }

    if len(extracted_text.strip()) < _TEXT_HEALTHY_THRESHOLD:
        return _default_failure(
            canonical_url,
            "Firefox 일반 모드에서 기사 본문을 충분히 확보하지 못했습니다.",
        )

    return {
        "success": True,
        "url": canonical_url,
        "title": title,
        "text": extracted_text,
        "html": html_snippet,
        "error": None,
        "paywall": paywall,
        "browser_engine": "firefox-visible",
        "throttle": throttle,
    }


def close_browser(
    *,
    lock_timeout: float = _DEFAULT_BROWSER_LOCK_TIMEOUT,
) -> dict[str, Any]:
    try:
        with _browser_session_lock(
            lock_timeout=lock_timeout,
            reason="firefox_visible_fetch:close-browser",
        ):
            _quit_firefox()
    except TimeoutError as exc:
        return {
            "ok": False,
            "browser": "firefox-visible",
            "closed": False,
            "detail": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "browser": "firefox-visible",
            "closed": False,
            "detail": str(exc),
        }

    return {
        "ok": True,
        "browser": "firefox-visible",
        "closed": True,
        "detail": None,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Firefox 일반 모드 UI 조작으로 기사 본문을 수집합니다.",
    )
    parser.add_argument("url", nargs="?", help="수집할 기사 URL")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Firefox 일반 모드 수집에 필요한 기본 준비 상태만 점검합니다.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.0,
        help="호환성용 인자입니다. 현재 Firefox visible 수집에서는 별도 timeout 제어를 쓰지 않습니다.",
    )
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=_DEFAULT_BROWSER_LOCK_TIMEOUT,
        help="브라우저 락 대기 시간(초)",
    )
    parser.add_argument("--no-close", action="store_true", help="수집 후 Firefox 앱을 종료하지 않음")
    parser.add_argument(
        "--close-browser",
        action="store_true",
        help="남아 있는 Firefox visible 앱을 정리 종료하고 결과를 JSON으로 반환",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.close_browser:
        report = close_browser(lock_timeout=max(0.0, args.lock_timeout))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1

    if args.diagnose:
        report = _diagnose(
            lock_timeout=max(0.0, args.lock_timeout),
            close_after=not args.no_close,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ready") else 1

    if not args.url:
        parser.error("URL이 필요합니다.")

    result = fetch_article(
        args.url,
        timeout=max(0.0, args.timeout),
        lock_timeout=max(0.0, args.lock_timeout),
        close_after=not args.no_close,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
