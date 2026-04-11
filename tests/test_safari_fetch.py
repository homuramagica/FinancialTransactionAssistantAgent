import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import safari_fetch as sf


class SafariFetchTests(unittest.TestCase):
    def test_normalize_browser_defaults_to_chrome(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(sf._normalize_browser(), "chrome")

        with mock.patch.dict(os.environ, {"NEWS_FETCH_BROWSER": "safari"}, clear=True):
            self.assertEqual(sf._normalize_browser(), "chrome")

        with mock.patch.dict(os.environ, {"NEWS_FETCH_BROWSER": "invalid-browser"}, clear=True):
            self.assertEqual(sf._normalize_browser(), "chrome")

    def test_get_article_links_dow_jones_combines_sources(self) -> None:
        rows = [
            {"Link": "https://www.wsj.com/articles/example-wsj", "Title": "WSJ headline"},
            {"Link": "https://www.barrons.com/articles/example-barrons", "Title": "Barrons headline"},
            {"Link": "https://www.wsj.com/articles/example-wsj", "Title": "WSJ headline"},
            {"Link": "https://www.example.com/articles/ignore-me", "Title": "Ignore me"},
        ]

        with mock.patch.object(sf, "_fetch_rss_rows", return_value=rows):
            links = sf.get_article_links("ignored", "dow_jones")

        self.assertEqual(
            links,
            [
                {
                    "href": "https://www.wsj.com/articles/example-wsj",
                    "title": "WSJ headline",
                    "source": "wsj",
                },
                {
                    "href": "https://www.barrons.com/articles/example-barrons",
                    "title": "Barrons headline",
                    "source": "barrons",
                },
            ],
        )

    def test_get_article_links_single_source_still_uses_shared_feed(self) -> None:
        rows = [
            {"Link": "https://www.wsj.com/articles/example-wsj", "Title": "WSJ headline"},
            {"Link": "https://www.barrons.com/articles/example-barrons", "Title": "Barrons headline"},
        ]

        with mock.patch.object(sf, "_fetch_rss_rows", return_value=rows):
            wsj_links = sf.get_article_links("ignored", "wsj")
            barrons_links = sf.get_article_links("ignored", "barrons")

        self.assertEqual(
            wsj_links,
            [
                {
                    "href": "https://www.wsj.com/articles/example-wsj",
                    "title": "WSJ headline",
                    "source": "wsj",
                }
            ],
        )
        self.assertEqual(
            barrons_links,
            [
                {
                    "href": "https://www.barrons.com/articles/example-barrons",
                    "title": "Barrons headline",
                    "source": "barrons",
                }
            ],
        )

    def test_browser_session_lock_times_out_cleanly(self) -> None:
        fake_file = mock.MagicMock()

        with mock.patch("builtins.open", mock.mock_open()) as mocked_open, \
             mock.patch.object(sf.os, "makedirs"), \
             mock.patch.object(sf.time, "monotonic", side_effect=[0.0, 0.3]), \
             mock.patch.object(sf.time, "sleep"), \
             mock.patch.object(sf.fcntl, "flock", side_effect=BlockingIOError):
            mocked_open.return_value.__enter__.return_value = fake_file

            with self.assertRaises(TimeoutError):
                with sf._browser_session_lock(lock_timeout=0.2, reason="test"):
                    pass

    def test_fetch_propagates_browser_lock_timeout_as_structured_error(self) -> None:
        with mock.patch.object(sf, "_browser_session_lock", side_effect=TimeoutError("lock busy")):
            result = sf._fetch_once("https://example.com/article", lock_timeout=0.1)

        self.assertFalse(result["success"])
        self.assertEqual(result["url"], "https://example.com/article")
        self.assertEqual(result["error"], "lock busy")

    def test_detect_bot_block_matches_robot_challenge(self) -> None:
        self.assertTrue(
            sf._detect_bot_block(
                "Bloomberg - Are you a robot?",
                "Verify you are human to continue.",
                "",
            )
        )

    def test_detect_bot_block_ignores_captcha_site_key_widget(self) -> None:
        self.assertFalse(
            sf._detect_bot_block(
                "The Surprising Source of North Korea’s Enduring Power - WSJ",
                "In the short history of world Communism, North Korea has always stood apart."
                * 5,
                '<ufc-follow-author-widget captcha-site-key=""></ufc-follow-author-widget>',
            )
        )

    def test_looks_like_empty_shell_matches_domain_only_page(self) -> None:
        self.assertTrue(sf._looks_like_empty_shell("wsj.com", ""))

    def test_extract_devtools_payload_prefers_article_text(self) -> None:
        payload = {
            "title": "Exclusive | White House Races to Head Off Threats From Powerful AI Tools - WSJ",
            "href": "https://www.wsj.com/tech/ai/white-house-races-to-head-off-threats-from-powerful-ai-tools-5c6f22e2",
            "articleText": "기사 본문 " * 80,
            "bodyText": "전체 페이지 본문 " * 120,
            "articleHtml": "<article>body</article>",
            "bodyHtml": "<html>shell</html>",
        }

        result = sf._extract_devtools_payload(
            payload,
            "https://www.wsj.com/tech/ai/white-house-races-to-head-off-threats-from-powerful-ai-tools-5c6f22e2",
            "chrome",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["text"], payload["articleText"].strip())
        self.assertEqual(result["html"], payload["articleHtml"])

    def test_extract_devtools_payload_flags_bot_block(self) -> None:
        payload = {
            "title": "Bloomberg - Are you a robot?",
            "href": "https://www.bloomberg.com/news/articles/example",
            "articleText": "",
            "bodyText": "Verify you are human to continue.",
            "articleHtml": "",
            "bodyHtml": "<html><div class='g-recaptcha'>captcha</div></html>",
        }

        result = sf._extract_devtools_payload(
            payload,
            "https://www.bloomberg.com/news/articles/example",
            "chrome",
        )

        self.assertFalse(result["success"])
        self.assertIn("봇 차단 페이지가 반환되었습니다", result["error"])

    def test_ensure_browser_available_accepts_existing_app_bundle_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "profile"
            app_path = Path(tmpdir) / "Google Chrome.app"
            app_path.mkdir()

            with mock.patch.object(sf, "_load_websockets", return_value=(object(), None)), \
                 mock.patch.object(sf, "_browser_profile_path", return_value=profile_path), \
                 mock.patch.object(sf, "_resolve_chrome_app_path", return_value=app_path), \
                 mock.patch("scripts.safari_fetch.subprocess.run") as mock_run:
                error = sf._ensure_browser_available("chrome")

        self.assertIsNone(error)
        mock_run.assert_not_called()

    def test_launch_devtools_browser_uses_resolved_app_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_path = Path(tmpdir) / "profile"
            app_path = Path(tmpdir) / "Google Chrome.app"
            app_path.mkdir()

            completed = mock.Mock(returncode=0, stderr="", stdout="")
            with mock.patch.object(sf, "_browser_profile_path", return_value=profile_path), \
                 mock.patch.object(sf, "_resolve_chrome_app_path", return_value=app_path), \
                 mock.patch("scripts.safari_fetch.subprocess.run", return_value=completed) as mock_run:
                sf._launch_devtools_browser()

        command = mock_run.call_args.args[0]
        self.assertEqual(command[:3], ["open", "-na", str(app_path)])

    def test_wait_for_site_access_slot_throttles_same_source_for_10_seconds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            throttle_path = Path(tmpdir) / "site_throttle.json"
            with mock.patch.object(sf, "_SITE_THROTTLE_STATE_PATH", str(throttle_path)), \
                 mock.patch.object(sf, "_SITE_THROTTLE_INTERVAL_SECONDS", 10.0), \
                 mock.patch.object(sf.time, "time", side_effect=[100.0, 100.0, 103.0, 113.0]), \
                 mock.patch.object(sf.time, "sleep") as mock_sleep:
                first = sf._wait_for_site_access_slot("https://www.bloomberg.com/news/articles/example")
                second = sf._wait_for_site_access_slot("https://www.bloomberg.com/news/articles/another")

        self.assertFalse(first["throttled"])
        self.assertEqual(first["site"], "bloomberg")
        self.assertTrue(second["throttled"])
        self.assertEqual(second["site"], "bloomberg")
        mock_sleep.assert_called_once_with(7.0)

    def test_site_access_key_groups_wsj_and_barrons_as_dow_jones(self) -> None:
        self.assertEqual(
            sf._site_access_key("https://www.wsj.com/tech/ai/example"),
            "dow_jones",
        )
        self.assertEqual(
            sf._site_access_key("https://www.barrons.com/articles/example"),
            "dow_jones",
        )
        self.assertEqual(
            sf._site_access_key("https://www.bloomberg.com/news/articles/example"),
            "bloomberg",
        )


if __name__ == "__main__":
    unittest.main()
