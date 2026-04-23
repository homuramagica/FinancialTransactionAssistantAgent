#!/usr/bin/env python3
"""
chrome_visible_fetch.py - Google Chrome을 보이는 일반 창으로만 조작해 기사 본문을 수집합니다.

원칙:
- Chrome DevTools, remote debugging port, Playwright, WebDriver를 사용하지 않습니다.
- AppleScript와 Chrome 내장 `execute javascript`만 사용합니다.
- 기본 프로필은 기존 인증을 재사용할 수 있도록 `tmp/chrome_devtools_profile`을 그대로 사용합니다.
- 기본 동작은 기사 본문을 확보하면 Chrome 앱을 종료하지만, batch 수집에서는 세션을 재사용할 수 있습니다.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import firefox_visible_fetch as ff_shared  # noqa: E402
from scripts import safari_fetch as shared  # noqa: E402


_DEFAULT_BROWSER_LOCK_TIMEOUT = float(os.environ.get("NEWS_FETCH_LOCK_TIMEOUT", "90"))
_DEFAULT_FETCH_TIMEOUT = float(os.environ.get("NEWS_FETCH_CHROME_VISIBLE_TIMEOUT", "20"))
_LAUNCH_SETTLE_SECONDS = float(os.environ.get("NEWS_FETCH_CHROME_VISIBLE_LAUNCH_SECONDS", "1.2"))
_NAV_POLL_SECONDS = float(os.environ.get("NEWS_FETCH_CHROME_VISIBLE_POLL_SECONDS", "0.5"))
_PAGE_SETTLE_SECONDS = float(os.environ.get("NEWS_FETCH_CHROME_VISIBLE_PAGE_SECONDS", "5"))
_POST_LOAD_SETTLE_SECONDS = float(os.environ.get("NEWS_FETCH_CHROME_VISIBLE_SETTLE_SECONDS", "0.8"))
_COPY_SETTLE_SECONDS = float(os.environ.get("NEWS_FETCH_CHROME_VISIBLE_COPY_SECONDS", "0.4"))
_SOURCE_SETTLE_SECONDS = float(os.environ.get("NEWS_FETCH_CHROME_VISIBLE_SOURCE_SECONDS", "1.2"))
_READY_POLL_SECONDS = float(os.environ.get("NEWS_FETCH_CHROME_VISIBLE_READY_POLL_SECONDS", "0.25"))
_APPLE_EVENTS_ENABLE_TIMEOUT = float(os.environ.get("NEWS_FETCH_CHROME_VISIBLE_ENABLE_TIMEOUT", "8"))
_APPLE_EVENTS_ENABLE_POLL_SECONDS = float(os.environ.get("NEWS_FETCH_CHROME_VISIBLE_ENABLE_POLL_SECONDS", "0.6"))
_CHROME_APP_NAME = os.environ.get("NEWS_FETCH_CHROME_APP_NAME", "Google Chrome").strip() or "Google Chrome"
_CHROME_APP_PATH = os.environ.get("NEWS_FETCH_CHROME_APP_PATH", "").strip()
_CHROME_LAUNCH_MODE = os.environ.get("NEWS_FETCH_CHROME_LAUNCH_MODE", "").strip()
_APPLE_EVENTS_DISABLED_SIGNALS = (
    "apple events의 자바스크립트 허용",
    "allow javascript from apple events",
    "applescript를 통한 자바스크립트 실행 기능이 꺼져",
)
_APPLE_EVENTS_ENABLE_RETRY_SIGNALS = (
    "menu bar 1",
    "menu item",
    "메뉴",
    "가져올 수 없습니다",
    "유효하지 않은 인덱스",
    "invalid index",
    "application process",
)
_APPLE_EVENTS_MENU_CANDIDATES = (
    ("보기", "개발자 정보", "Apple Events의 자바스크립트 허용"),
    ("View", "Developer", "Allow JavaScript from Apple Events"),
)


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


def _apple_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _profile_path() -> Path:
    explicit = (
        os.environ.get("NEWS_FETCH_CHROME_VISIBLE_PROFILE_PATH")
        or os.environ.get("NEWS_FETCH_DEVTOOLS_PROFILE_PATH")
    )
    if explicit:
        return Path(explicit).expanduser()
    return (REPO_ROOT / "tmp" / "chrome_devtools_profile").expanduser()


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
    return shared._read_chrome_info_plist(app_path)


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
        return ["applescript", "direct", "open"]
    if mode == "open":
        return ["applescript", "open", "direct"]
    return ["applescript", "open", "direct"]


def _chrome_open_command(launch_args: list[str]) -> list[str]:
    app_path = _resolve_chrome_app_path()
    if app_path is not None:
        # `open -a` expects an app name, not a bundle path.
        return ["open", "-n", str(app_path), "--args", *launch_args]
    return ["open", "-na", _chrome_application_name(), "--args", *launch_args]


def _launch_chrome_via_applescript(start_url: str) -> None:
    script = f"""
tell application "{_chrome_application_name()}"
    activate
    set targetWindow to make new window
    set activeTab to active tab of targetWindow
    set URL of activeTab to {_apple_string(start_url)}
end tell
"""
    completed = _run_applescript(script)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip() or f"returncode={completed.returncode}"
        raise RuntimeError(f"applescript: {detail}")


def _launch_args(start_url: str) -> list[str]:
    profile_path = _profile_path()
    profile_path.mkdir(parents=True, exist_ok=True)
    return [
        f"--user-data-dir={profile_path}",
        "--no-first-run",
        "--no-default-browser-check",
        "--new-window",
        start_url,
    ]


def _wait_for_chrome_front_window(
    timeout: float | None = None,
    *,
    launched_process: subprocess.Popen[str] | None = None,
) -> int:
    deadline = time.monotonic() + max(1.0, timeout or max(_LAUNCH_SETTLE_SECONDS, 1.5))
    crash_check_after = time.monotonic() + 1.5
    last_error = ""
    while time.monotonic() < deadline:
        if launched_process is not None:
            returncode = launched_process.poll()
            if returncode is not None:
                raise RuntimeError(
                    shared._chrome_launch_crash_detail(
                        "Chrome Visible",
                        returncode=returncode,
                    )
                )
        try:
            return _front_window_id()
        except RuntimeError as exc:
            last_error = str(exc)
            if time.monotonic() >= crash_check_after and not shared._is_chrome_running():
                raise RuntimeError(
                    shared._chrome_launch_crash_detail("Chrome Visible", extra=last_error)
                )
            time.sleep(max(0.1, _READY_POLL_SECONDS))
    raise RuntimeError(last_error or "Chrome front window가 준비되지 않았습니다.")


def _ensure_chrome_available() -> str | None:
    if sys.platform != "darwin":
        return "Chrome visible 수집은 현재 macOS에서만 지원합니다."

    probe_osascript = _run_command(["osascript", "-e", 'return "ok"'])
    if probe_osascript.returncode != 0:
        stderr = (probe_osascript.stderr or "").strip()
        return f"osascript를 실행하지 못했습니다. {stderr}".strip()

    profile_path = _profile_path()
    try:
        profile_path.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        return f"Chrome visible 프로필 디렉터리를 준비하지 못했습니다: {profile_path} ({exc})"

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
            return f"Google Chrome 실행 파일이 실행 가능 상태가 아닙니다. executable={executable_path}"
        return None

    probe = _run_command(["open", "-Ra", _CHROME_APP_NAME])
    if probe.returncode != 0:
        stderr = (probe.stderr or probe.stdout or "").strip()
        checked = ", ".join(str(path) for path in _chrome_app_candidate_paths())
        suffix = f" stderr: {stderr}" if stderr else ""
        if checked:
            suffix = f"{suffix} checked: {checked}".strip()
        return f"Google Chrome 앱을 찾지 못했습니다. {suffix}".strip()

    return None


def _activate_chrome() -> None:
    _run_applescript(f'tell application "{_chrome_application_name()}" to activate')


def _ensure_chrome_window(
    start_url: str = "about:blank",
    *,
    reuse_existing: bool = False,
) -> int:
    if reuse_existing and shared._is_chrome_running():
        _activate_chrome()
        try:
            return _front_window_id()
        except RuntimeError:
            pass

    _launch_chrome(start_url)
    return _front_window_id()


def _run_chrome_launch_probe(
    *,
    lock_timeout: float,
    close_after: bool = True,
) -> dict[str, Any]:
    try:
        with shared._browser_session_lock(
            lock_timeout=lock_timeout,
            reason="chrome_visible_fetch:diagnose",
        ):
            _ensure_chrome_window("about:blank", reuse_existing=not close_after)
    except Exception as exc:
        try:
            _quit_chrome(ignore_errors=True)
        except Exception:
            pass
        return {
            "ok": False,
            "detail": str(exc).strip() or "Chrome launch probe에 실패했습니다.",
        }

    if close_after:
        try:
            _quit_chrome(ignore_errors=True)
        except Exception as exc:
            return {
                "ok": False,
                "detail": str(exc).strip() or "Chrome launch probe 뒤 종료에 실패했습니다.",
            }

    return {
        "ok": True,
        "detail": "Chrome launch probe가 성공했습니다.",
    }


def _quit_chrome(*, ignore_errors: bool = False) -> None:
    script = f"""
if application "{_chrome_application_name()}" is running then
    tell application "{_chrome_application_name()}" to quit
end if
"""
    completed = _run_applescript(script)
    if completed.returncode == 0:
        return
    if ignore_errors:
        return
    detail = (completed.stderr or completed.stdout or "").strip()
    raise RuntimeError(f"Chrome 종료에 실패했습니다. {detail}".strip())


def _launch_chrome(start_url: str = "about:blank") -> None:
    _quit_chrome(ignore_errors=True)

    executable_path = _resolve_chrome_executable_path()
    launch_args = _launch_args(start_url)
    errors: list[str] = []

    for strategy in _chrome_launch_strategies():
        if strategy == "applescript":
            try:
                _launch_chrome_via_applescript(start_url)
                _wait_for_chrome_front_window()
                return
            except RuntimeError as exc:
                errors.append(str(exc))
                _quit_chrome(ignore_errors=True)
                continue

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
            except Exception as exc:
                errors.append(f"direct: {exc}")
                continue
            try:
                _wait_for_chrome_front_window(launched_process=process)
                return
            except RuntimeError as exc:
                errors.append(f"direct ready-check: {exc}")
                _quit_chrome(ignore_errors=True)
                continue

        if strategy == "open":
            command = _chrome_open_command(launch_args)
            completed = _run_command(command)
            if completed.returncode == 0:
                try:
                    _wait_for_chrome_front_window()
                    return
                except RuntimeError as exc:
                    errors.append(f"open ready-check: {exc}")
                    _quit_chrome(ignore_errors=True)
                    continue
            detail = (completed.stderr or completed.stdout or "").strip() or f"returncode={completed.returncode}"
            errors.append(f"open: {detail}")
            continue

        errors.append(f"{strategy}: 지원하지 않는 Chrome launch strategy")

    detail = "; ".join(errors) if errors else "실행 시도 정보가 비어 있습니다."
    raise RuntimeError(f"Chrome visible 브라우저를 실행하지 못했습니다. {detail}".strip())


def _front_window_id() -> int:
    script = f'tell application "{_chrome_application_name()}" to get id of front window'
    completed = _run_applescript(script)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Chrome front window 확인에 실패했습니다. {detail}".strip())
    return int((completed.stdout or "").strip())


def _execute_javascript(window_id: int, script_body: str) -> str:
    script = (
        f'tell application "{_chrome_application_name()}" '
        f'to execute active tab of window id {window_id} javascript {_apple_string(script_body)}'
    )
    completed = _run_applescript(script)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Chrome javascript 실행에 실패했습니다. {detail}".strip())
    return (completed.stdout or "").strip()


def _apple_events_javascript_disabled(detail: str) -> bool:
    normalized = (detail or "").strip().lower()
    return any(signal in normalized for signal in _APPLE_EVENTS_DISABLED_SIGNALS)


def _apple_events_mark(
    *,
    view_label: str,
    developer_label: str,
    item_label: str,
) -> subprocess.CompletedProcess[str]:
    script = f"""
tell application "{_chrome_application_name()}" to activate
delay 0.8
tell application "System Events"
    tell process "{_chrome_application_name()}"
        return value of attribute "AXMenuItemMarkChar" of menu item {_apple_string(item_label)} of menu 1 of menu item {_apple_string(developer_label)} of menu 1 of menu bar item {_apple_string(view_label)} of menu bar 1
    end tell
end tell
"""
    return _run_applescript(script)


def _click_apple_events_menu(
    *,
    view_label: str,
    developer_label: str,
    item_label: str,
) -> subprocess.CompletedProcess[str]:
    script = f"""
tell application "{_chrome_application_name()}" to activate
delay 0.8
tell application "System Events"
    tell process "{_chrome_application_name()}"
        click menu item {_apple_string(item_label)} of menu 1 of menu item {_apple_string(developer_label)} of menu 1 of menu bar item {_apple_string(view_label)} of menu bar 1
    end tell
end tell
"""
    return _run_applescript(script)


def _enable_apple_events_javascript() -> None:
    deadline = time.monotonic() + max(1.0, _APPLE_EVENTS_ENABLE_TIMEOUT)
    last_detail = ""
    while time.monotonic() < deadline:
        for view_label, developer_label, item_label in _APPLE_EVENTS_MENU_CANDIDATES:
            mark_completed = _apple_events_mark(
                view_label=view_label,
                developer_label=developer_label,
                item_label=item_label,
            )
            output = (mark_completed.stdout or "").strip()
            if mark_completed.returncode == 0 and output and output != "missing value":
                time.sleep(max(0.2, _APPLE_EVENTS_ENABLE_POLL_SECONDS))
                return

            detail = (mark_completed.stderr or mark_completed.stdout or "").strip()
            if detail:
                last_detail = detail
            normalized = detail.lower()

            if mark_completed.returncode == 0 and output == "missing value":
                click_completed = _click_apple_events_menu(
                    view_label=view_label,
                    developer_label=developer_label,
                    item_label=item_label,
                )
                click_detail = (click_completed.stderr or click_completed.stdout or "").strip()
                if click_detail:
                    last_detail = click_detail
                normalized_click = click_detail.lower()
                if click_completed.returncode != 0 and not any(
                    signal in normalized_click for signal in _APPLE_EVENTS_ENABLE_RETRY_SIGNALS
                ):
                    continue

                time.sleep(max(0.2, _APPLE_EVENTS_ENABLE_POLL_SECONDS))
                verify_completed = _apple_events_mark(
                    view_label=view_label,
                    developer_label=developer_label,
                    item_label=item_label,
                )
                verify_output = (verify_completed.stdout or "").strip()
                if verify_completed.returncode == 0 and verify_output and verify_output != "missing value":
                    time.sleep(max(0.2, _APPLE_EVENTS_ENABLE_POLL_SECONDS))
                    return
                verify_detail = (verify_completed.stderr or verify_completed.stdout or "").strip()
                if verify_detail:
                    last_detail = verify_detail
                continue

            if any(signal in normalized for signal in _APPLE_EVENTS_ENABLE_RETRY_SIGNALS):
                continue

        time.sleep(max(0.2, _APPLE_EVENTS_ENABLE_POLL_SECONDS))

    raise RuntimeError(
        "Chrome Apple Events 자바스크립트 허용 설정에 실패했습니다. "
        f"메뉴 준비가 제한 시간 안에 완료되지 않았습니다. {last_detail}".strip()
    )


def _ensure_apple_events_javascript_enabled(window_id: int) -> int:
    try:
        _execute_javascript(window_id, "document.title")
        return window_id
    except RuntimeError as exc:
        detail = str(exc)
        if not _apple_events_javascript_disabled(detail):
            raise

    _enable_apple_events_javascript()
    refreshed_window_id = window_id
    deadline = time.monotonic() + max(1.5, _APPLE_EVENTS_ENABLE_TIMEOUT)
    last_error = ""
    while time.monotonic() < deadline:
        try:
            refreshed_window_id = _front_window_id()
            _execute_javascript(refreshed_window_id, "document.title")
            return refreshed_window_id
        except RuntimeError as exc:
            last_error = str(exc)
            if not _apple_events_javascript_disabled(last_error):
                raise
            time.sleep(max(0.2, _APPLE_EVENTS_ENABLE_POLL_SECONDS))

    raise RuntimeError(last_error or "Chrome Apple Events 자바스크립트 허용 설정이 반영되지 않았습니다.")


def _reload_tab(window_id: int) -> None:
    script = f'tell application "{_chrome_application_name()}" to reload active tab of window id {window_id}'
    completed = _run_applescript(script)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Chrome 탭 새로고침에 실패했습니다. {detail}".strip())


def _navigate_tab(window_id: int, url: str) -> None:
    script = (
        f'tell application "{_chrome_application_name()}" '
        f'to set URL of active tab of window id {window_id} to {_apple_string(url)}'
    )
    completed = _run_applescript(script)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Chrome 탭 URL 설정에 실패했습니다. {detail}".strip())


def _tab_property(window_id: int, property_name: str) -> str:
    script = (
        f'tell application "{_chrome_application_name()}" '
        f'to get {property_name} of active tab of window id {window_id}'
    )
    completed = _run_applescript(script)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Chrome 탭 속성 조회에 실패했습니다. property={property_name} {detail}".strip())
    return (completed.stdout or "").strip()


def _wait_for_page_ready(window_id: int, requested_url: str, timeout: float) -> str:
    deadline = time.monotonic() + max(_PAGE_SETTLE_SECONDS, timeout)
    last_url = ""
    last_loading = ""

    while time.monotonic() < deadline:
        current_url = _tab_property(window_id, "URL")
        loading = _tab_property(window_id, "loading").strip().lower()
        last_url = current_url
        last_loading = loading

        if current_url and current_url not in {"about:blank", "chrome://newtab/", "chrome://new-tab-page/"}:
            parsed = urlparse(current_url)
            if parsed.scheme in {"http", "https"} and loading == "false":
                time.sleep(max(0.0, _POST_LOAD_SETTLE_SECONDS))
                return current_url

        time.sleep(max(0.1, _NAV_POLL_SECONDS))

    raise TimeoutError(
        "Chrome visible 페이지 로드가 제한 시간 안에 끝나지 않았습니다. "
        f"requested={requested_url} actual={last_url or '<empty>'} loading={last_loading or '<empty>'}"
    )


def _clear_clipboard() -> None:
    ff_shared._clear_clipboard()


def _read_clipboard() -> str:
    return ff_shared._read_clipboard()


def _run_tab_command(window_id: int, command_name: str) -> None:
    script = (
        f'tell application "{_chrome_application_name()}" '
        f'to {command_name} active tab of window id {window_id}'
    )
    completed = _run_applescript(script)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"Chrome 탭 명령 실행에 실패했습니다. command={command_name} {detail}".strip())


def _copy_visible_page_text(window_id: int) -> str:
    _clear_clipboard()
    _run_tab_command(window_id, "select all")
    time.sleep(max(0.1, _COPY_SETTLE_SECONDS))
    _run_tab_command(window_id, "copy selection")
    time.sleep(max(0.1, _COPY_SETTLE_SECONDS))
    return _read_clipboard()


def _close_active_tab(window_id: int, *, ignore_errors: bool = False) -> None:
    try:
        _run_tab_command(window_id, "close")
    except Exception:
        if not ignore_errors:
            raise


def _copy_view_source_html_and_close_tabs(window_id: int) -> str:
    _clear_clipboard()
    _run_tab_command(window_id, "view source")
    time.sleep(max(0.2, _SOURCE_SETTLE_SECONDS))
    source_window_id = _front_window_id()
    _run_tab_command(source_window_id, "select all")
    time.sleep(max(0.1, _COPY_SETTLE_SECONDS))
    _run_tab_command(source_window_id, "copy selection")
    time.sleep(max(0.1, _COPY_SETTLE_SECONDS))
    html_text = _read_clipboard()
    _close_active_tab(source_window_id, ignore_errors=True)
    return html_text


def _build_result_from_copied_content(
    *,
    requested_url: str,
    actual_url: str,
    rendered_text: str,
    html_text: str,
    throttle: dict[str, Any],
) -> dict[str, Any]:
    html_snippet = (html_text or "")[:ff_shared._HTML_SNIPPET_LIMIT]
    title, extracted_text = ff_shared._extract_title_and_text(html_snippet, rendered_text)

    if ff_shared._detect_bot_block(title, extracted_text, html_snippet):
        return shared._failure_result(
            requested_url,
            "봇 제한 페이지가 반환되었습니다.",
            title=title,
            text=extracted_text,
            html=html_snippet,
        ) | {"browser_engine": "chrome-visible", "throttle": throttle}

    paywall = ff_shared._detect_paywall(extracted_text, html_snippet)
    if paywall and ff_shared._contains_login_prompt(extracted_text, html_snippet):
        return {
            "success": False,
            "url": actual_url,
            "title": title,
            "text": extracted_text,
            "html": html_snippet,
            "error": "로그인 또는 구독 확인이 필요한 화면이 반환되었습니다.",
            "paywall": True,
            "browser_engine": "chrome-visible",
            "throttle": throttle,
        }

    if len(extracted_text.strip()) < ff_shared._TEXT_HEALTHY_THRESHOLD:
        return shared._failure_result(
            actual_url,
            "Chrome 일반 모드에서 기사 본문을 충분히 확보하지 못했습니다.",
            title=title,
            text=extracted_text,
            html=html_snippet,
        ) | {"browser_engine": "chrome-visible", "throttle": throttle}

    return {
        "success": True,
        "url": actual_url,
        "title": title,
        "text": extracted_text,
        "html": html_snippet,
        "error": None,
        "paywall": paywall,
        "browser_engine": "chrome-visible",
        "throttle": throttle,
    }


def _probe_script() -> str:
    return (
        "JSON.stringify({"
        "readyState: document.readyState || '', "
        "title: document.title || '', "
        "href: location.href || '', "
        "bodyExists: !!document.body, "
        "bodyLength: ((document.body && document.body.innerText) || '').trim().length"
        "})"
    )


def _article_script() -> str:
    limit = shared._HTML_SNIPPET_LIMIT
    return f"""(() => {{
      const bodyText = ((document.body && document.body.innerText) || '').trim();
      const article = document.querySelector('article');
      const articleText = ((article && article.innerText) || '').trim();
      const bodyHtml = document.documentElement ? document.documentElement.outerHTML.slice(0, {limit}) : '';
      const articleHtml = article ? article.outerHTML.slice(0, {limit}) : '';
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


def _parse_json_result(raw_value: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_value)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _wait_for_page_payload(window_id: int, requested_url: str, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + max(5.0, timeout)
    last_payload: dict[str, Any] = {}

    while time.monotonic() < deadline:
        probe = _parse_json_result(_execute_javascript(window_id, _probe_script()))
        if probe:
            last_payload = probe
            ready_state = str(probe.get("readyState") or "").strip().lower()
            href = str(probe.get("href") or "").strip()
            body_length = int(probe.get("bodyLength") or 0)

            if href and href != "about:blank" and ready_state in {"interactive", "complete"}:
                if body_length > 0 or not shared._same_registered_host(requested_url, href):
                    time.sleep(max(0.0, _POST_LOAD_SETTLE_SECONDS))
                    payload = _parse_json_result(_execute_javascript(window_id, _article_script()))
                    if payload:
                        return payload

        time.sleep(max(0.1, _NAV_POLL_SECONDS))

    if last_payload:
        payload = _parse_json_result(_execute_javascript(window_id, _article_script()))
        if payload:
            return payload

    raise TimeoutError("Chrome visible 페이지 로드가 제한 시간 안에 끝나지 않았습니다.")


def diagnose(
    *,
    lock_timeout: float = _DEFAULT_BROWSER_LOCK_TIMEOUT,
    close_after: bool = True,
) -> dict[str, Any]:
    availability = _ensure_chrome_available()
    launch_probe = {
        "ok": False,
        "detail": "Chrome launch probe는 availability 통과 후에만 실행합니다.",
    }
    if availability is None:
        launch_probe = _run_chrome_launch_probe(
            lock_timeout=lock_timeout,
            close_after=close_after,
        )
    return {
        "ready": availability is None and launch_probe.get("ok", False),
        "browser": "chrome",
        "browser_label": "Chrome Visible",
        "browser_engine": "chrome-visible",
        "profile_path": str(_profile_path()),
        "remote_debugging": False,
        "playwright": False,
        "webdriver": False,
        "availability": {
            "ok": availability is None,
            "detail": availability or "Chrome visible 수집에 필요한 기본 준비 상태를 확인했습니다.",
        },
        "launch_probe": launch_probe,
        "lock_timeout": lock_timeout,
    }


def fetch_article(
    url: str,
    *,
    timeout: float = _DEFAULT_FETCH_TIMEOUT,
    lock_timeout: float = _DEFAULT_BROWSER_LOCK_TIMEOUT,
    close_after: bool = True,
) -> dict[str, Any]:
    try:
        canonical_url = shared._canonicalize_url(url)
    except Exception as exc:
        return shared._failure_result(url, f"잘못된 URL입니다. {exc}")

    availability = _ensure_chrome_available()
    if availability is not None:
        return shared._failure_result(canonical_url, availability)

    result: dict[str, Any] | None = None
    cleanup_error: str | None = None

    try:
        with shared._browser_session_lock(lock_timeout=lock_timeout, reason=f"chrome_visible_fetch:{canonical_url}"):
            throttle = shared._wait_for_site_access_slot(canonical_url)
            window_id = _ensure_chrome_window(
                "about:blank",
                reuse_existing=not close_after,
            )
            _navigate_tab(window_id, canonical_url)
            actual_url = _wait_for_page_ready(window_id, canonical_url, timeout)
            rendered_text = _copy_visible_page_text(window_id)
            html_text = _copy_view_source_html_and_close_tabs(window_id)
            result = _build_result_from_copied_content(
                requested_url=canonical_url,
                actual_url=actual_url,
                rendered_text=rendered_text,
                html_text=html_text,
                throttle=throttle,
            )

            if shared._should_try_bloomberg_reload(
                canonical_url,
                result,
                close_after=close_after,
                reload_used=False,
            ):
                _reload_tab(window_id)
                actual_url = _wait_for_page_ready(window_id, canonical_url, timeout)
                rendered_text = _copy_visible_page_text(window_id)
                html_text = _copy_view_source_html_and_close_tabs(window_id)
                result = _build_result_from_copied_content(
                    requested_url=canonical_url,
                    actual_url=actual_url,
                    rendered_text=rendered_text,
                    html_text=html_text,
                    throttle=throttle,
                )
                result["reloaded_once"] = True
    except Exception as exc:
        result = shared._failure_result(canonical_url, str(exc), detail=str(exc))
        result["browser_engine"] = "chrome-visible"
    finally:
        if close_after:
            try:
                _quit_chrome()
            except Exception as cleanup_exc:
                cleanup_error = str(cleanup_exc)

    if cleanup_error:
        if result is None:
            result = shared._failure_result(canonical_url, cleanup_error, detail=cleanup_error)
            result["browser_engine"] = "chrome-visible"
        elif result.get("success"):
            result = shared._failure_result(
                str(result.get("url") or canonical_url),
                cleanup_error,
                title=str(result.get("title") or ""),
                text=str(result.get("text") or ""),
                html=str(result.get("html") or ""),
                detail=cleanup_error,
            )
            result["browser_engine"] = "chrome-visible"
        else:
            detail = str(result.get("detail") or result.get("error") or "").strip()
            merged = cleanup_error if not detail else f"{detail} | {cleanup_error}"
            result["detail"] = merged
            result["error"] = merged

    assert result is not None
    return result


def close_browser(
    *,
    lock_timeout: float = _DEFAULT_BROWSER_LOCK_TIMEOUT,
) -> dict[str, Any]:
    try:
        with shared._browser_session_lock(
            lock_timeout=lock_timeout,
            reason="chrome_visible_fetch:close-browser",
        ):
            _quit_chrome()
    except TimeoutError as exc:
        return {
            "ok": False,
            "browser": "chrome-visible",
            "closed": False,
            "detail": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "browser": "chrome-visible",
            "closed": False,
            "detail": str(exc),
        }

    return {
        "ok": True,
        "browser": "chrome-visible",
        "closed": True,
        "detail": None,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Chrome visible + AppleScript 방식으로 기사 본문을 수집합니다.",
    )
    parser.add_argument("url", nargs="?", help="수집할 기사 URL")
    parser.add_argument(
        "--browser",
        default="chrome",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Chrome visible 수집에 필요한 기본 준비 상태만 점검합니다.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=_DEFAULT_FETCH_TIMEOUT,
        help="페이지 로드 대기 시간(초)",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=1,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--lock-timeout",
        type=float,
        default=_DEFAULT_BROWSER_LOCK_TIMEOUT,
        help="브라우저 락 대기 시간(초)",
    )
    parser.add_argument("--no-close", action="store_true", help="수집 후 Chrome 앱을 종료하지 않음")
    parser.add_argument(
        "--close-browser",
        action="store_true",
        help="남아 있는 Chrome visible 앱을 정리 종료하고 결과를 JSON으로 반환",
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
        report = diagnose(
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
