import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import chrome_visible_fetch as cvf


class ChromeVisibleFetchTests(unittest.TestCase):
    def test_chrome_launch_strategies_prefers_open_in_auto_mode(self) -> None:
        with mock.patch.object(cvf, "_chrome_launch_mode", return_value="auto"):
            self.assertEqual(cvf._chrome_launch_strategies(), ["applescript", "open", "direct"])

    def test_parser_accepts_ignored_browser_flag(self) -> None:
        parser = cvf._build_parser()
        args = parser.parse_args(
            ["https://example.com/article", "--browser", "chrome", "--max-attempts", "2"]
        )
        self.assertEqual(args.url, "https://example.com/article")
        self.assertEqual(args.browser, "chrome")
        self.assertEqual(args.max_attempts, 2)

    def test_launch_args_omit_remote_debugging_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "profile"
            with mock.patch.object(cvf, "_profile_path", return_value=profile_path):
                args = cvf._launch_args("https://example.com/article")

        self.assertIn(f"--user-data-dir={profile_path}", args)
        self.assertIn("--new-window", args)
        self.assertNotIn("--remote-debugging-port=9222", args)

    def test_diagnose_requires_launch_probe_success(self) -> None:
        with mock.patch.object(cvf, "_ensure_chrome_available", return_value=None), \
             mock.patch.object(
                 cvf,
                 "_run_chrome_launch_probe",
                 return_value={"ok": False, "detail": "launch failed"},
             ) as mock_probe:
            report = cvf.diagnose(lock_timeout=0.1)

        self.assertFalse(report["ready"])
        self.assertEqual(report["browser"], "chrome")
        self.assertEqual(report["browser_engine"], "chrome-visible")
        self.assertFalse(report["remote_debugging"])
        self.assertEqual(report["launch_probe"]["detail"], "launch failed")
        mock_probe.assert_called_once_with(lock_timeout=0.1, close_after=True)

    def test_wait_for_chrome_front_window_reports_early_browser_crash(self) -> None:
        process = mock.Mock()
        process.poll.return_value = -6

        with self.assertRaisesRegex(RuntimeError, "SIGABRT"):
            cvf._wait_for_chrome_front_window(timeout=0.2, launched_process=process)

    def test_ensure_apple_events_javascript_enabled_toggles_once(self) -> None:
        disabled_error = RuntimeError(
            "Chrome javascript 실행에 실패했습니다. Apple Events의 자바스크립트 허용"
        )
        with mock.patch.object(
            cvf,
            "_execute_javascript",
            side_effect=[disabled_error, "Example title"],
        ) as mock_exec, \
             mock.patch.object(cvf, "_enable_apple_events_javascript") as mock_enable, \
             mock.patch.object(cvf, "_front_window_id", return_value=456):
            window_id = cvf._ensure_apple_events_javascript_enabled(123)

        self.assertEqual(mock_exec.call_count, 2)
        self.assertEqual(window_id, 456)
        mock_enable.assert_called_once_with()

    def test_fetch_article_uses_visible_payload_and_quits_chrome(self) -> None:
        extracted = {
            "success": True,
            "url": "https://www.wsj.com/articles/example",
            "title": "Example headline",
            "text": "본문 " * 100,
            "html": "<article>본문</article>",
            "error": None,
            "paywall": False,
            "browser_engine": "chrome-visible",
            "throttle": {"site": "dow_jones"},
        }

        with mock.patch.object(cvf.shared, "_canonicalize_url", return_value="https://www.wsj.com/articles/example"), \
             mock.patch.object(cvf, "_ensure_chrome_available", return_value=None), \
             mock.patch.object(cvf.shared, "_browser_session_lock", return_value=mock.MagicMock(__enter__=lambda s: None, __exit__=lambda s, a, b, c: None)), \
             mock.patch.object(cvf.shared, "_wait_for_site_access_slot", return_value={"site": "dow_jones"}), \
             mock.patch.object(cvf, "_launch_chrome"), \
             mock.patch.object(cvf, "_front_window_id", return_value=123), \
             mock.patch.object(cvf, "_navigate_tab"), \
             mock.patch.object(cvf, "_wait_for_page_ready", return_value="https://www.wsj.com/articles/example"), \
             mock.patch.object(cvf, "_copy_visible_page_text", return_value="본문 " * 120), \
             mock.patch.object(cvf, "_copy_view_source_html_and_close_tabs", return_value="<article>본문</article>"), \
             mock.patch.object(cvf, "_build_result_from_copied_content", return_value=dict(extracted)), \
             mock.patch.object(cvf.shared, "_should_try_bloomberg_reload", return_value=False), \
             mock.patch.object(cvf, "_quit_chrome") as mock_quit:
            result = cvf.fetch_article("https://www.wsj.com/articles/example", timeout=5, lock_timeout=0.1)

        self.assertTrue(result["success"])
        self.assertEqual(result["browser_engine"], "chrome-visible")
        self.assertEqual(result["throttle"]["site"], "dow_jones")
        mock_quit.assert_called_once_with()

    def test_fetch_article_can_keep_chrome_open_for_batch(self) -> None:
        extracted = {
            "success": True,
            "url": "https://www.wsj.com/articles/example",
            "title": "Example headline",
            "text": "본문 " * 100,
            "html": "<article>본문</article>",
            "error": None,
            "paywall": False,
            "browser_engine": "chrome-visible",
            "throttle": {"site": "dow_jones"},
        }

        with mock.patch.object(cvf.shared, "_canonicalize_url", return_value="https://www.wsj.com/articles/example"), \
             mock.patch.object(cvf, "_ensure_chrome_available", return_value=None), \
             mock.patch.object(cvf.shared, "_browser_session_lock", return_value=mock.MagicMock(__enter__=lambda s: None, __exit__=lambda s, a, b, c: None)), \
             mock.patch.object(cvf.shared, "_wait_for_site_access_slot", return_value={"site": "dow_jones"}), \
             mock.patch.object(cvf, "_ensure_chrome_window", return_value=123) as mock_window, \
             mock.patch.object(cvf, "_navigate_tab"), \
             mock.patch.object(cvf, "_wait_for_page_ready", return_value="https://www.wsj.com/articles/example"), \
             mock.patch.object(cvf, "_copy_visible_page_text", return_value="본문 " * 120), \
             mock.patch.object(cvf, "_copy_view_source_html_and_close_tabs", return_value="<article>본문</article>"), \
             mock.patch.object(cvf, "_build_result_from_copied_content", return_value=dict(extracted)), \
             mock.patch.object(cvf.shared, "_should_try_bloomberg_reload", return_value=False), \
             mock.patch.object(cvf, "_quit_chrome") as mock_quit:
            result = cvf.fetch_article(
                "https://www.wsj.com/articles/example",
                timeout=5,
                lock_timeout=0.1,
                close_after=False,
            )

        self.assertTrue(result["success"])
        mock_window.assert_called_once_with("about:blank", reuse_existing=True)
        mock_quit.assert_not_called()

    def test_close_browser_quits_chrome_once(self) -> None:
        with mock.patch.object(
            cvf.shared,
            "_browser_session_lock",
            return_value=mock.MagicMock(__enter__=lambda s: None, __exit__=lambda s, a, b, c: None),
        ), mock.patch.object(cvf, "_quit_chrome") as mock_quit:
            result = cvf.close_browser(lock_timeout=0.1)

        self.assertTrue(result["ok"])
        self.assertTrue(result["closed"])
        mock_quit.assert_called_once_with()

    def test_launch_chrome_falls_back_when_direct_launch_is_not_scriptable(self) -> None:
        app_path = Path("/Applications/Google Chrome.app")
        executable_path = app_path / "Contents" / "MacOS" / "Google Chrome"

        with mock.patch.object(cvf, "_resolve_chrome_app_path", return_value=app_path), \
             mock.patch.object(cvf, "_resolve_chrome_executable_path", return_value=executable_path), \
             mock.patch.object(cvf, "_chrome_launch_strategies", return_value=["direct", "open"]), \
             mock.patch.object(cvf.subprocess, "Popen") as mock_popen, \
             mock.patch.object(cvf, "_run_command", return_value=mock.Mock(returncode=0, stdout="", stderr="")) as mock_run, \
             mock.patch.object(
                 cvf,
                 "_wait_for_chrome_front_window",
                 side_effect=[RuntimeError("응용 프로그램이 실행 중이 아닙니다."), 123],
             ) as mock_wait, \
             mock.patch.object(cvf, "_quit_chrome") as mock_quit:
            cvf._launch_chrome("https://example.com/article")

        mock_popen.assert_called_once()
        mock_run.assert_called_once_with(
            [
                "open",
                "-n",
                str(app_path),
                "--args",
                *cvf._launch_args("https://example.com/article"),
            ]
        )
        self.assertEqual(mock_wait.call_count, 2)
        mock_quit.assert_any_call(ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
