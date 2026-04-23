from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import research_archive_cli as archive


class ResearchArchiveCliTests(unittest.TestCase):
    def test_bloomberg_apps_news_canonical_url_preserves_sid(self) -> None:
        first = archive._canonicalize_url(
            "https://www.bloomberg.com/apps/news?pid=newsarchive&sid=a7LCp2Acv2aw&refer=home"
        )
        second = archive._canonicalize_url(
            "https://www.bloomberg.com/apps/news?pid=newsarchive&sid=amE9cvUPd30A"
        )
        self.assertNotEqual(first, second)
        self.assertEqual(
            first,
            "https://www.bloomberg.com/apps/news?pid=newsarchive&sid=a7LCp2Acv2aw",
        )

    def test_invalid_legacy_bloomberg_page_is_detected(self) -> None:
        self.assertTrue(
            archive._is_unusable_fetch_result(
                "https://www.bloomberg.com/apps/news?pid=newsarchive&sid=a7LCp2Acv2aw",
                "Politics - Bloomberg",
                "short body",
            )
        )

    def test_bloomberg_404_page_is_detected(self) -> None:
        self.assertTrue(
            archive._is_unusable_fetch_result(
                "https://www.bloomberg.com/news/articles/2008-09-18/putnam-closes-money-market-fund-after-withdrawals",
                "404. Page Not Found - Bloomberg",
                "Our apologies We're unable to find the page you're looking for. 404. Page Not Found.",
            )
        )

    def test_reuters_shell_page_is_detected(self) -> None:
        self.assertTrue(
            archive._is_unusable_fetch_result(
                "https://www.reuters.com/article/us-how-aig-fell-apart-idUSMAR85972720080918",
                "The Big Money: How AIG fell apart",
                (
                    "Skip to main content Exclusive news, data and analytics for financial market professionals "
                    "Learn more about Refinitiv World Browse World Browse Business Browse Markets"
                ),
            )
        )

    def test_infer_source_maps_reuters(self) -> None:
        self.assertEqual(
            archive._infer_source_from_url(
                "https://www.reuters.com/article/us-how-aig-fell-apart-idUSMAR85972720080918"
            ),
            "Reuters",
        )

    def test_extract_published_at_from_text_prefers_body_then_url(self) -> None:
        self.assertEqual(
            archive._extract_published_at_from_text(
                "Published 03/14/2024, 02:09 AM\nUpdated 03/14/2024, 02:35 AM",
                "https://www.investing.com/news/economy/private-credit-ties-to-banks-deepen-in-europe-as-default-risk-rises-3337161",
            ),
            "2024-03-14",
        )
        self.assertEqual(
            archive._extract_published_at_from_text(
                "Published Mon, Jun 25 20073:24 PM EDTUpdated Thu, Aug 5 20103:04 PM EDT",
                "https://www.cnbc.com/2007/06/25/subprime-concerns-push-abx-indexes-to-fresh-lows.html",
            ),
            "2007-06-25",
        )
        self.assertEqual(
            archive._extract_published_at_from_text(
                "Published Dec 31, 0000 07:00PM ET Updated Apr 02, 2026 12:00PM ET",
                "https://m.investing.com/news/stock-market-news/example",
            ),
            "2026-04-02",
        )

    def test_extract_title_from_text_handles_investing_shell(self) -> None:
        body = (
            "Get 50% Off\nMarkets\nPrivate credit ties to banks deepen in Europe as default risk rises\nBy\n"
            "Published 03/14/2024, 02:09 AM"
        )
        self.assertEqual(
            archive._extract_title_from_text(body),
            "Private credit ties to banks deepen in Europe as default risk rises",
        )

    def test_archive_article_writes_markdown_and_indexes_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            payload = archive.ArticlePayload(
                title="Lehman Bankruptcy Deepens Credit Freeze",
                source="Bloomberg",
                url="https://www.bloomberg.com/news/articles/2008-09-15/example",
                published_at="2008-09-15T00:00:00Z",
                retrieved_at_kst="2026-04-14T21:00:00+09:00",
                body=(
                    "Lehman Brothers filed for bankruptcy after rescue talks collapsed.\n\n"
                    "Money markets and repo funding channels seized as counterparties pulled back."
                ),
                tags=["2008_crisis", "lehman", "repo"],
            )

            result = archive.archive_article(payload, workspace=workspace)
            self.assertTrue(result["ok"])

            article_path = workspace / result["file_path"]
            db_path = workspace / result["db_path"]
            self.assertTrue(article_path.exists())
            self.assertTrue(db_path.exists())

            with archive._connect_db(db_path) as conn:
                article_row = conn.execute("SELECT COUNT(*) AS count FROM articles").fetchone()
                chunk_row = conn.execute("SELECT COUNT(*) AS count FROM article_chunks").fetchone()
                tag_row = conn.execute("SELECT COUNT(*) AS count FROM article_tags").fetchone()

            self.assertEqual(int(article_row["count"]), 1)
            self.assertGreaterEqual(int(chunk_row["count"]), 1)
            self.assertEqual(int(tag_row["count"]), 3)

    def test_archive_article_upserts_by_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            first = archive.ArticlePayload(
                title="Bear Stearns Funding Stress",
                source="WSJ",
                url="https://www.wsj.com/articles/example-bear",
                published_at="2008-03-14T00:00:00Z",
                retrieved_at_kst="2026-04-14T21:00:00+09:00",
                body="Bear Stearns scrambled for liquidity as repo lines tightened.",
                tags=["2008_crisis", "bear_stearns"],
            )
            second = archive.ArticlePayload(
                title="Bear Stearns Rescue Takes Shape",
                source="WSJ",
                url="https://www.wsj.com/articles/example-bear",
                published_at="2008-03-16T00:00:00Z",
                retrieved_at_kst="2026-04-14T21:10:00+09:00",
                body="JPMorgan and the Fed moved toward a rescue package for Bear Stearns.",
                tags=["2008_crisis", "bear_stearns", "fed"],
            )

            first_result = archive.archive_article(first, workspace=workspace)
            second_result = archive.archive_article(second, workspace=workspace)

            self.assertEqual(first_result["article_id"], second_result["article_id"])
            self.assertEqual(first_result["file_path"], second_result["file_path"])

            with archive._connect_db(workspace / second_result["db_path"]) as conn:
                row = conn.execute(
                    "SELECT title, published_at FROM articles WHERE article_id = ?",
                    (second_result["article_id"],),
                ).fetchone()
                tag_count = conn.execute("SELECT COUNT(*) AS count FROM article_tags").fetchone()

            self.assertEqual(str(row["title"]), "Bear Stearns Rescue Takes Shape")
            self.assertEqual(str(row["published_at"]), "2008-03-16T00:00:00Z")
            self.assertEqual(int(tag_count["count"]), 3)

    def test_search_archive_returns_best_matching_article(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            archive.archive_article(
                archive.ArticlePayload(
                    title="AIG's CDS Book Triggered Collateral Spiral",
                    source="Bloomberg",
                    url="https://www.bloomberg.com/news/articles/example-aig",
                    published_at="2008-09-17T00:00:00Z",
                    retrieved_at_kst="2026-04-14T21:00:00+09:00",
                    body=(
                        "AIG faced urgent collateral calls tied to credit default swaps.\n\n"
                        "The firm could not meet liquidity demands without federal support."
                    ),
                    tags=["2008_crisis", "aig", "cds"],
                ),
                workspace=workspace,
            )
            archive.archive_article(
                archive.ArticlePayload(
                    title="Basel III Pushes Banks Toward More Capital",
                    source="FT",
                    url="https://www.ft.com/content/example-basel",
                    published_at="2010-09-12T00:00:00Z",
                    retrieved_at_kst="2026-04-14T21:00:00+09:00",
                    body=(
                        "Basel III introduced tighter capital and liquidity requirements.\n\n"
                        "Regulators aimed to reduce leverage after the global financial crisis."
                    ),
                    tags=["basel_iii", "regulation"],
                ),
                workspace=workspace,
            )

            results = archive.search_archive(
                "AIG CDS collateral calls",
                workspace=workspace,
                limit=5,
            )

            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(results[0]["source"], "Bloomberg")
            self.assertIn("AIG", results[0]["title"])

    def test_fetch_and_archive_url_uses_research_site_throttle_and_restores_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            observed: dict[str, str] = {}

            def fake_fetch(*args, **kwargs):
                observed["during"] = os.environ.get("NEWS_FETCH_SITE_THROTTLE_INTERVAL_SECONDS", "")
                return {
                    "success": True,
                    "url": "https://www.bloomberg.com/news/articles/example-throttle",
                    "title": "Liquidity Freeze Hits Structured Credit",
                    "text": "Structured credit markets froze as dealers stepped back from risk.",
                    "html": "",
                    "error": None,
                    "paywall": False,
                }

            os.environ["NEWS_FETCH_SITE_THROTTLE_INTERVAL_SECONDS"] = "10"
            try:
                with mock.patch.object(archive.news_harness, "fetch_article_with_harness", side_effect=fake_fetch):
                    result = archive.fetch_and_archive_url(
                        "https://www.bloomberg.com/news/articles/example-throttle",
                        workspace=workspace,
                    )
                self.assertTrue(result["ok"])
                self.assertEqual(observed["during"], "15.0")
                self.assertEqual(os.environ.get("NEWS_FETCH_SITE_THROTTLE_INTERVAL_SECONDS"), "10")
            finally:
                os.environ.pop("NEWS_FETCH_SITE_THROTTLE_INTERVAL_SECONDS", None)


if __name__ == "__main__":
    unittest.main()
