from contextlib import nullcontext
import unittest
from unittest import mock

from scripts import firefox_visible_fetch as fetch


SAMPLE_HTML = """
<html>
  <head>
    <title>Example Headline - Bloomberg</title>
    <meta property="og:title" content="Example Headline" />
  </head>
  <body>
    <header>Navigation</header>
    <article>
      <h1>Example Headline</h1>
      <p>Paragraph one with actual article context and enough detail to matter.</p>
      <p>Paragraph two continues the story with more detail and a market angle.</p>
      <p>Paragraph three adds numbers, reactions, and next steps for investors.</p>
      <p>Paragraph four makes the extracted text comfortably longer than the threshold.</p>
      <p>Paragraph five keeps it well above any fallback boundary for parser tests.</p>
    </article>
  </body>
</html>
"""

STRUCTURED_ONLY_HTML = """
<html>
  <head>
    <title>Shell Page</title>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": "Structured Headline",
        "articleBody": "Paragraph one with article body content encoded in JSON-LD. Paragraph two keeps the text comfortably above the parser threshold. Paragraph three adds a market angle and specific numbers so the fallback path has enough substance to be useful even when the visible DOM is thin."
      }
    </script>
  </head>
  <body>
    <div id="app">Loading shell only</div>
  </body>
</html>
"""


class FirefoxVisibleFetchTests(unittest.TestCase):
    def test_diagnose_requires_launch_probe_success(self) -> None:
        with mock.patch.object(fetch, "_ensure_firefox_available", return_value=None), \
             mock.patch.object(
                 fetch,
                 "_run_firefox_launch_probe",
                 return_value={"ok": False, "detail": "launch failed"},
             ) as mock_probe:
            report = fetch._diagnose(lock_timeout=0.1)

        self.assertFalse(report["ready"])
        self.assertEqual(report["launch_probe"]["detail"], "launch failed")
        mock_probe.assert_called_once_with(lock_timeout=0.1, close_after=True)

    def test_firefox_launch_attempts_prefer_open_new_instance(self) -> None:
        with mock.patch.object(
            fetch,
            "_firefox_app_candidates",
            return_value=["/Applications/Firefox.app", "Firefox"],
        ):
            attempts = fetch._firefox_launch_attempts("https://example.com")

        labels = [label for label, _ in attempts[:5]]
        self.assertEqual(
            labels[:4],
            [
                "open -na /Applications/Firefox.app",
                "open -a /Applications/Firefox.app",
                "open -na Firefox",
                "open -a Firefox",
            ],
        )
        self.assertEqual(labels[4], "open -b org.mozilla.firefox")

    def test_firefox_launch_attempts_prefer_existing_instance_when_reusing(self) -> None:
        with mock.patch.object(
            fetch,
            "_firefox_app_candidates",
            return_value=["/Applications/Firefox.app", "Firefox"],
        ), mock.patch.object(fetch, "_is_firefox_running", return_value=True):
            attempts = fetch._firefox_launch_attempts(
                "https://example.com",
                prefer_reuse=True,
            )

        labels = [label for label, _ in attempts[:3]]
        self.assertEqual(
            labels,
            [
                "open -a /Applications/Firefox.app",
                "open -a Firefox",
                "open -b org.mozilla.firefox",
            ],
        )

    def test_site_access_key_groups_dow_jones_hosts(self) -> None:
        self.assertEqual(fetch._site_access_key("https://www.wsj.com/articles/example"), "dow_jones")
        self.assertEqual(fetch._site_access_key("https://www.barrons.com/articles/example"), "dow_jones")
        self.assertEqual(fetch._site_access_key("https://www.bloomberg.com/news/articles/example"), "bloomberg")

    def test_command_key_code_line_uses_layout_independent_shortcuts(self) -> None:
        self.assertEqual(fetch._command_key_code_line("a"), "    key code 0 using command down")
        self.assertEqual(fetch._command_key_code_line("c"), "    key code 8 using command down")
        self.assertEqual(fetch._command_key_code_line("w"), "    key code 13 using command down")
        self.assertEqual(fetch._command_key_code_line("u"), "    key code 32 using command down")

    def test_command_key_code_line_rejects_unknown_keys(self) -> None:
        with self.assertRaises(ValueError):
            fetch._command_key_code_line("x")

    def test_extract_title_and_text_prefers_article_content(self) -> None:
        title, text = fetch._extract_title_and_text(SAMPLE_HTML, "fallback text")

        self.assertEqual(title, "Example Headline")
        self.assertIn("Paragraph one with actual article context", text)
        self.assertIn("Paragraph five keeps it well above any fallback boundary", text)

    def test_extract_title_and_text_uses_embedded_json_article_body(self) -> None:
        title, text = fetch._extract_title_and_text(STRUCTURED_ONLY_HTML, "")

        self.assertEqual(title, "Structured Headline")
        self.assertIn("article body content encoded in JSON-LD", text)
        self.assertIn("market angle and specific numbers", text)

    def test_detect_paywall_requires_short_text_and_login_signal(self) -> None:
        short_text = "Sign in to read"
        html = "<html><body>Subscribe to continue</body></html>"
        self.assertTrue(fetch._detect_paywall(short_text, html))
        self.assertFalse(fetch._detect_paywall("본문 " * 300, html))

    def test_fetch_article_quits_firefox_after_success(self) -> None:
        with mock.patch.object(fetch, "_ensure_firefox_available", return_value=None), \
             mock.patch.object(fetch, "_browser_session_lock", return_value=nullcontext()), \
             mock.patch.object(fetch, "_wait_for_site_access_slot", return_value={"site": "bloomberg"}), \
             mock.patch.object(fetch, "_open_url_in_firefox"), \
             mock.patch.object(fetch.time, "sleep"), \
             mock.patch.object(fetch, "_copy_visible_page_text", return_value="fallback text"), \
             mock.patch.object(fetch, "_copy_view_source_html_and_close_tabs", return_value=SAMPLE_HTML), \
             mock.patch.object(fetch, "_quit_firefox") as quit_firefox:
            result = fetch.fetch_article("https://www.bloomberg.com/news/articles/example")

        self.assertTrue(result["success"])
        quit_firefox.assert_called_once_with()

    def test_fetch_article_can_keep_firefox_open_for_batch(self) -> None:
        with mock.patch.object(fetch, "_ensure_firefox_available", return_value=None), \
             mock.patch.object(fetch, "_browser_session_lock", return_value=nullcontext()), \
             mock.patch.object(fetch, "_wait_for_site_access_slot", return_value={"site": "bloomberg"}), \
             mock.patch.object(fetch, "_open_url_in_firefox") as open_firefox, \
             mock.patch.object(fetch.time, "sleep"), \
             mock.patch.object(fetch, "_copy_visible_page_text", return_value="fallback text"), \
             mock.patch.object(fetch, "_copy_view_source_html_and_close_tabs", return_value=SAMPLE_HTML), \
             mock.patch.object(fetch, "_quit_firefox") as quit_firefox:
            result = fetch.fetch_article(
                "https://www.bloomberg.com/news/articles/example",
                close_after=False,
            )

        self.assertTrue(result["success"])
        open_firefox.assert_called_once_with(
            "https://www.bloomberg.com/news/articles/example",
            prefer_reuse=True,
        )
        quit_firefox.assert_not_called()

    def test_fetch_article_quits_firefox_after_capture_failure(self) -> None:
        with mock.patch.object(fetch, "_ensure_firefox_available", return_value=None), \
             mock.patch.object(fetch, "_browser_session_lock", return_value=nullcontext()), \
             mock.patch.object(fetch, "_wait_for_site_access_slot", return_value={"site": "bloomberg"}), \
             mock.patch.object(fetch, "_open_url_in_firefox"), \
             mock.patch.object(fetch.time, "sleep"), \
             mock.patch.object(fetch, "_copy_visible_page_text", side_effect=RuntimeError("copy failed")), \
             mock.patch.object(fetch, "_quit_firefox") as quit_firefox:
            result = fetch.fetch_article("https://www.bloomberg.com/news/articles/example")

        self.assertFalse(result["success"])
        self.assertIn("copy failed", result["error"])
        quit_firefox.assert_called_once_with()

    def test_fetch_article_fails_if_firefox_quit_fails(self) -> None:
        with mock.patch.object(fetch, "_ensure_firefox_available", return_value=None), \
             mock.patch.object(fetch, "_browser_session_lock", return_value=nullcontext()), \
             mock.patch.object(fetch, "_wait_for_site_access_slot", return_value={"site": "bloomberg"}), \
             mock.patch.object(fetch, "_open_url_in_firefox"), \
             mock.patch.object(fetch.time, "sleep"), \
             mock.patch.object(fetch, "_copy_visible_page_text", return_value="fallback text"), \
             mock.patch.object(fetch, "_copy_view_source_html_and_close_tabs", return_value=SAMPLE_HTML), \
             mock.patch.object(fetch, "_quit_firefox", side_effect=RuntimeError("quit failed")):
            result = fetch.fetch_article("https://www.bloomberg.com/news/articles/example")

        self.assertFalse(result["success"])
        self.assertIn("quit failed", result["error"])

    def test_close_browser_quits_firefox_once(self) -> None:
        with mock.patch.object(fetch, "_browser_session_lock", return_value=nullcontext()), \
             mock.patch.object(fetch, "_quit_firefox") as quit_firefox:
            result = fetch.close_browser(lock_timeout=0.1)

        self.assertTrue(result["ok"])
        self.assertTrue(result["closed"])
        quit_firefox.assert_called_once_with()

    def test_open_url_in_firefox_retries_alternative_launch_targets(self) -> None:
        attempts = [
            ("open -a /Applications/Firefox.app", ["open", "-a", "/Applications/Firefox.app", "https://example.com"]),
            ("open -b org.mozilla.firefox", ["open", "-b", "org.mozilla.firefox", "https://example.com"]),
        ]

        with mock.patch.object(fetch, "_firefox_launch_attempts", return_value=attempts), \
             mock.patch.object(
                 fetch,
                 "_run_firefox_launch_command",
                 side_effect=[
                     mock.Mock(returncode=1, stderr='kLSNoExecutableErr'),
                     mock.Mock(returncode=0, stderr=""),
                 ],
             ) as run_launch, \
             mock.patch.object(fetch, "_wait_for_firefox_ready", return_value=None):
            fetch._open_url_in_firefox("https://example.com")

        self.assertEqual(run_launch.call_count, 2)

    def test_open_url_in_firefox_compacts_noisy_direct_launch_stderr(self) -> None:
        attempts = [
            (
                "/Applications/Firefox.app/Contents/MacOS/firefox -new-tab",
                ["/Applications/Firefox.app/Contents/MacOS/firefox", "-new-tab", "https://example.com"],
            ),
        ]
        noisy_stderr = "\n".join(
            [
                "[WARN  minidump_unwind::symbols::debuginfo] failed to open /usr/lib/libc++.1.dylib",
                "[ERROR crashreporter::logging] failed to retarget log to submit.log: Operation not permitted",
                "[ERROR crashreporter] exiting with error: pending directory creation failed",
            ]
        )

        with mock.patch.object(fetch, "_firefox_launch_attempts", return_value=attempts), \
             mock.patch.object(
                 fetch,
                 "_run_firefox_launch_command",
                 return_value=mock.Mock(returncode=1, stderr=noisy_stderr, stdout=""),
             ):
            with self.assertRaises(RuntimeError) as ctx:
                fetch._open_url_in_firefox("https://example.com")

        message = str(ctx.exception)
        self.assertIn("failed to retarget log", message)
        self.assertIn("pending directory creation failed", message)
        self.assertNotIn("minidump_unwind", message)

    def test_open_url_in_firefox_retries_if_launch_target_never_becomes_scriptable(self) -> None:
        attempts = [
            ("open -na /Applications/Firefox.app", ["open", "-na", "/Applications/Firefox.app", "https://example.com"]),
            ("open -b org.mozilla.firefox", ["open", "-b", "org.mozilla.firefox", "https://example.com"]),
        ]

        with mock.patch.object(fetch, "_firefox_launch_attempts", return_value=attempts), \
             mock.patch.object(
                 fetch,
                 "_run_firefox_launch_command",
                 side_effect=[
                     mock.Mock(returncode=0, stderr=""),
                     mock.Mock(returncode=0, stderr=""),
                 ],
             ) as run_launch, \
             mock.patch.object(
                 fetch,
                 "_wait_for_firefox_ready",
                 side_effect=[RuntimeError("not ready"), None],
             ) as wait_ready:
            fetch._open_url_in_firefox("https://example.com")

        self.assertEqual(run_launch.call_count, 2)
        self.assertEqual(wait_ready.call_count, 2)

    def test_ensure_firefox_available_rejects_bundle_without_executable(self) -> None:
        with mock.patch.object(fetch, "_firefox_app_candidates", return_value=["/Applications/Firefox.app"]), \
             mock.patch.object(fetch, "_run_command", return_value=mock.Mock(returncode=0, stderr="", stdout="")), \
             mock.patch.object(
                 fetch,
                 "_probe_firefox_candidate",
                 return_value="/Applications/Firefox.app: executable missing (/Applications/Firefox.app/Contents/MacOS/firefox)",
             ):
            detail = fetch._ensure_firefox_available()

        self.assertIsNotNone(detail)
        self.assertIn("executable missing", detail)


if __name__ == "__main__":
    unittest.main()
