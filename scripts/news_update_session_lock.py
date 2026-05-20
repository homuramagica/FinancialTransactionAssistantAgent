from __future__ import annotations

import contextlib
import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any, Iterator


LOCK_PATH_ENV = "NEWS_UPDATE_SESSION_LOCK_PATH"
LOCK_TIMEOUT_ENV = "NEWS_UPDATE_SESSION_LOCK_TIMEOUT"
LOCK_HELD_ENV = "NEWS_UPDATE_SESSION_LOCK_HELD"

DEFAULT_LOCK_PATH = "/tmp/news_update_session.lock"
DEFAULT_LOCK_TIMEOUT = 0.0
POLL_INTERVAL_SECONDS = 0.25


class NewsUpdateSessionLockError(TimeoutError):
    def __init__(
        self,
        message: str,
        *,
        lock_path: str,
        timeout: float,
        holder: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.lock_path = lock_path
        self.timeout = timeout
        self.holder = holder or {}

    def to_report(self) -> dict[str, Any]:
        report: dict[str, Any] = {
            "locked": True,
            "lock_path": self.lock_path,
            "timeout": self.timeout,
            "detail": str(self),
        }
        if self.holder:
            report["holder"] = self.holder
        return report


def _lock_path() -> str:
    return os.environ.get(LOCK_PATH_ENV, DEFAULT_LOCK_PATH).strip() or DEFAULT_LOCK_PATH


def _default_timeout() -> float:
    raw = os.environ.get(LOCK_TIMEOUT_ENV, "").strip()
    if not raw:
        return DEFAULT_LOCK_TIMEOUT
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_LOCK_TIMEOUT


def _read_holder(lock_file: Any) -> dict[str, Any]:
    try:
        lock_file.seek(0)
        raw = lock_file.read().strip()
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw[:500]}
    return parsed if isinstance(parsed, dict) else {}


def _write_holder(lock_file: Any, *, reason: str) -> dict[str, Any]:
    holder = {
        "pid": os.getpid(),
        "reason": reason,
        "locked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(json.dumps(holder, ensure_ascii=False))
    lock_file.flush()
    return holder


def subprocess_env_with_session_lock_held(env: dict[str, str] | None = None) -> dict[str, str]:
    child_env = dict(os.environ if env is None else env)
    child_env[LOCK_HELD_ENV] = "1"
    return child_env


@contextlib.contextmanager
def news_update_session_lock(
    *,
    reason: str,
    lock_timeout: float | None = None,
    skip_if_parent_holds_lock: bool = True,
) -> Iterator[dict[str, Any]]:
    if skip_if_parent_holds_lock and os.environ.get(LOCK_HELD_ENV) == "1":
        yield {
            "acquired": False,
            "inherited": True,
            "lock_path": _lock_path(),
            "reason": reason,
        }
        return

    path = _lock_path()
    timeout = _default_timeout() if lock_timeout is None else max(0.0, float(lock_timeout))
    lock_dir = os.path.dirname(path)
    if lock_dir:
        os.makedirs(lock_dir, exist_ok=True)

    with open(path, "a+", encoding="utf-8") as lock_file:
        deadline = time.monotonic() + timeout
        acquired = False
        while True:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    holder = _read_holder(lock_file)
                    holder_text = ""
                    if holder:
                        holder_text = (
                            f" 현재 보유자: pid={holder.get('pid', '<unknown>')}, "
                            f"reason={holder.get('reason', '<unknown>')}, "
                            f"locked_at={holder.get('locked_at', '<unknown>')}."
                        )
                    raise NewsUpdateSessionLockError(
                        "다른 NewsCollector 세션이 아직 실행 중입니다. "
                        f"{timeout:g}초 동안 대기했지만 세션 락을 확보하지 못했습니다."
                        f"{holder_text}",
                        lock_path=path,
                        timeout=timeout,
                        holder=holder,
                    ) from exc
                time.sleep(POLL_INTERVAL_SECONDS)

        try:
            holder = _write_holder(lock_file, reason=reason)
            yield {
                "acquired": True,
                "inherited": False,
                "lock_path": path,
                "reason": reason,
                "holder": holder,
            }
        finally:
            if acquired:
                try:
                    lock_file.seek(0)
                    lock_file.truncate()
                    lock_file.flush()
                except Exception:
                    pass
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
