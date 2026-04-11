import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import news_update_queue as queue


class NewsUpdateQueueTests(unittest.TestCase):
    def test_build_candidate_queue_slices_new_items_by_state(self) -> None:
        bloomberg_rows = [
            {
                "Link": "https://www.bloomberg.com/news/articles/new-1",
                "Title": "Bloomberg New 1",
                "Date": "2026-04-10 10:00:00",
                "Plain Description": "desc-1",
            },
            {
                "Link": "https://www.bloomberg.com/news/articles/seen",
                "Title": "Bloomberg Seen",
                "Date": "2026-04-10 09:00:00",
                "Plain Description": "desc-seen",
            },
        ]
        dow_rows = [
            {
                "Link": "https://www.wsj.com/articles/wsj-new",
                "Title": "WSJ New",
                "Date": "2026-04-10 08:00:00",
                "Plain Description": "wsj-desc",
            },
            {
                "Link": "https://www.wsj.com/articles/wsj-seen",
                "Title": "WSJ Seen",
                "Date": "2026-04-10 07:00:00",
                "Plain Description": "wsj-seen",
            },
            {
                "Link": "https://www.barrons.com/articles/barrons-new",
                "Title": "Barrons New",
                "Date": "2026-04-10 06:00:00",
                "Plain Description": "barrons-desc",
            },
        ]

        def fake_fetch(feed_url: str, timeout: int = 15) -> list[dict]:
            if feed_url == queue.sf.BLOOMBERG_RSS_CSV_URL:
                return bloomberg_rows
            if feed_url == queue.sf.DOW_JONES_RSS_CSV_URL:
                return dow_rows
            return []

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            news_dir = workspace / queue._nfd("NewsUpdate")
            news_dir.mkdir(parents=True, exist_ok=True)
            state = {
                "last_run_kst": "2026-04-10T10:30:00+09:00",
                "bloomberg": "https://www.bloomberg.com/news/articles/seen",
                "wsj": "https://www.wsj.com/articles/wsj-seen",
                "barrons": "",
            }
            (news_dir / ".state.json").write_text(
                json.dumps(state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            with mock.patch.object(queue.sf, "_fetch_rss_rows", side_effect=fake_fetch):
                payload = queue.build_candidate_queue(workspace=workspace)

        self.assertEqual(payload["state_last_run_kst"], state["last_run_kst"])
        self.assertEqual(payload["total_new_candidates"], 3)

        bloomberg = payload["sources"][0]
        self.assertEqual(bloomberg["source"], "bloomberg")
        self.assertTrue(bloomberg["boundary_found"])
        self.assertEqual([item["title"] for item in bloomberg["candidates"]], ["Bloomberg New 1"])

        wsj = payload["sources"][1]
        self.assertEqual(wsj["source"], "wsj")
        self.assertTrue(wsj["boundary_found"])
        self.assertEqual([item["title"] for item in wsj["candidates"]], ["WSJ New"])

        barrons = payload["sources"][2]
        self.assertEqual(barrons["source"], "barrons")
        self.assertIsNone(barrons["boundary_found"])
        self.assertEqual([item["title"] for item in barrons["candidates"]], ["Barrons New"])

    def test_build_candidate_queue_marks_missing_boundary_without_scoring(self) -> None:
        bloomberg_rows = [
            {
                "Link": "https://www.bloomberg.com/news/articles/new-1",
                "Title": "Bloomberg New 1",
                "Date": "2026-04-10 10:00:00",
                "Plain Description": "desc-1",
            },
            {
                "Link": "https://www.bloomberg.com/news/articles/new-2",
                "Title": "Bloomberg New 2",
                "Date": "2026-04-10 09:00:00",
                "Plain Description": "desc-2",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            news_dir = workspace / queue._nfd("NewsUpdate")
            news_dir.mkdir(parents=True, exist_ok=True)
            (news_dir / ".state.json").write_text(
                json.dumps(
                    {
                        "last_run_kst": "2026-04-10T10:30:00+09:00",
                        "bloomberg": "https://www.bloomberg.com/news/articles/not-in-feed",
                        "wsj": "",
                        "barrons": "",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(queue.sf, "_fetch_rss_rows", return_value=bloomberg_rows):
                payload = queue.build_candidate_queue(
                    workspace=workspace,
                    source="bloomberg",
                    limit_per_source=1,
                )

        source = payload["sources"][0]
        self.assertFalse(source["boundary_found"])
        self.assertEqual(source["new_count"], 1)
        self.assertEqual(source["candidates"][0]["title"], "Bloomberg New 1")


if __name__ == "__main__":
    unittest.main()
