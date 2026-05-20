#!/usr/bin/env python3
"""Smoke-test a project-local BrowserMCP server.

The test covers three layers:
1. stdio MCP initialize
2. tools/list
3. browser_snapshot against the connected Chrome extension tab
"""

from __future__ import annotations

import argparse
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOCAL_SERVER = ROOT / "tools" / "browsermcp" / "node_modules" / ".bin" / "mcp-server-browsermcp"


def _json_line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"


class BrowserMcpProbe:
    def __init__(self, command: list[str]) -> None:
        self.command = command
        self.proc: subprocess.Popen[str] | None = None
        self._stderr_tail: list[str] = []

    def __enter__(self) -> "BrowserMcpProbe":
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(ROOT),
        )
        return self

    def __exit__(self, *_exc: object) -> None:
        if not self.proc:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def send(self, payload: dict[str, Any]) -> None:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("BrowserMCP process is not running")
        self.proc.stdin.write(_json_line(payload))
        self.proc.stdin.flush()

    def read_for_id(self, message_id: int, timeout: float) -> dict[str, Any] | None:
        if not self.proc or not self.proc.stdout or not self.proc.stderr:
            raise RuntimeError("BrowserMCP process is not running")

        deadline = time.time() + timeout
        while time.time() < deadline:
            ready, _, _ = select.select([self.proc.stdout, self.proc.stderr], [], [], 0.2)
            for stream in ready:
                line = stream.readline()
                if not line:
                    continue
                if stream is self.proc.stderr:
                    self._stderr_tail.append(line.rstrip("\n"))
                    self._stderr_tail = self._stderr_tail[-20:]
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if message.get("id") == message_id:
                    return message
            if self.proc.poll() is not None:
                return None
        return None

    @property
    def stderr_tail(self) -> list[str]:
        return self._stderr_tail


def _text_from_tool_response(response: dict[str, Any]) -> str:
    result = response.get("result") or {}
    chunks = result.get("content") or []
    texts = [chunk.get("text", "") for chunk in chunks if chunk.get("type") == "text"]
    return "\n".join(texts)


def _tool_failed(response: dict[str, Any]) -> bool:
    return bool((response.get("result") or {}).get("isError"))


def _call_tool(probe: BrowserMcpProbe, message_id: int, name: str, arguments: dict[str, Any], timeout: float) -> dict[str, Any] | None:
    probe.send(
        {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    return probe.read_for_id(message_id, timeout)


def run(command: list[str], wait_seconds: float, navigate_url: str | None) -> int:
    with BrowserMcpProbe(command) as probe:
        probe.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "codex-browsermcp-smoke-test", "version": "0.1.0"},
                },
            }
        )
        init = probe.read_for_id(1, 8)
        if not init or "result" not in init:
            print("BrowserMCP initialize failed.")
            if probe.stderr_tail:
                print("\n".join(probe.stderr_tail[-8:]))
            return 1

        server_info = init["result"].get("serverInfo", {})
        print(f"initialize: ok ({server_info.get('name')} {server_info.get('version')})")

        probe.send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        probe.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tools = probe.read_for_id(2, 8)
        if not tools or "result" not in tools:
            print("tools/list failed.")
            return 1

        tool_names = [tool.get("name") for tool in tools["result"].get("tools", [])]
        print("tools:", ", ".join(name for name in tool_names if name))

        deadline = time.time() + max(wait_seconds, 0)
        attempt = 0
        last_response: dict[str, Any] | None = None
        while True:
            attempt += 1
            if navigate_url:
                last_response = _call_tool(probe, 100 + attempt * 2, "browser_navigate", {"url": navigate_url}, 10)
            else:
                last_response = _call_tool(probe, 100 + attempt * 2, "browser_snapshot", {}, 10)

            if not last_response:
                print("browser tool call timed out.")
                return 1

            text = _text_from_tool_response(last_response)
            if not _tool_failed(last_response):
                print("browser connection: ok")
                if text:
                    print("snapshot preview:")
                    print(text[:2000])
                return 0

            if "No connection to browser extension" not in text or time.time() >= deadline:
                print("browser connection: failed")
                print(text[:2000] if text else json.dumps(last_response, ensure_ascii=False)[:2000])
                return 2

            print("waiting for BrowserMCP extension tab connection...")
            time.sleep(2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-seconds", type=float, default=20.0)
    parser.add_argument("--navigate-url", default=os.environ.get("BROWSERMCP_TEST_URL"))
    parser.add_argument("--command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if args.command:
        command = args.command
    elif LOCAL_SERVER.exists():
        command = [str(LOCAL_SERVER)]
    else:
        command = ["npx", "-y", "@browsermcp/mcp@latest"]

    print("command:", " ".join(command))
    return run(command, args.wait_seconds, args.navigate_url)


if __name__ == "__main__":
    raise SystemExit(main())
