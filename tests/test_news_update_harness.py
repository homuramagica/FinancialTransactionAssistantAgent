import json
import subprocess
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest import mock

from scripts import news_update_harness as harness


VALID_ARTICLE = """# 🏦 은행주, 최악의 1분기 뒤 실적이 반전의 시험대에 섰습니다

&nbsp;

월가 대형 은행주가 지역은행 위기 이후 가장 나쁜 1분기를 지나 상대적으로 싼 밸류에이션 구간에 들어서면서 다음 주 실적 발표가 주가 반전의 첫 시험대로 떠올랐습니다.

&nbsp;

⚡ **중요한 이유:** 시장은 지금 숫자 자체보다 대형 은행 경영진이 전쟁과 유가, 사모신용, 금리 경로를 어떻게 읽는지에 더 큰 돈을 걸고 있습니다.
- KBW 은행지수는 1분기에 6% 하락해 2023년 지역은행 혼란 이후 가장 약한 분기를 보냈습니다.
- 지수는 4월 들어 7.9% 반등했지만 여전히 선행 PER 12배 수준으로 S&P500보다 낮습니다.
- 투자자들은 은행주의 가이던스가 반전의 출발점이 될 수 있는지 보고 있습니다.

&nbsp;

📅 **현재 상황:** 실적 시즌은 곧바로 월가 핵심 은행들로 시작됩니다.
- Goldman Sachs(GS), JPMorgan Chase(JPM), Citigroup(C), Wells Fargo(WFC)가 줄줄이 대기하고 있습니다.
- 트레이딩 수익과 대손비용 전망이 이번 분기 해석의 핵심이 됩니다.
- 금융업종의 이익 증가율 예상치는 지수 평균보다 높게 잡혀 있습니다.

&nbsp;

🧩 **숨은 의미:** 이번 실적 시즌의 핵심은 은행이 미국 소비자와 기업 활동의 균열을 가장 먼저 드러내는 창구라는 점입니다.
- 경영진 발언은 소비자 건전성, 기업 지출, 딜메이킹 회복 여부를 함께 보여주는 간접 지표 역할을 합니다.
- 시장은 사모신용 노출과 금리 전망, 유가 충격의 2차 파급을 함께 들여다볼 예정입니다.
- 연간 가이던스를 유지하는 것만으로도 은행주에는 긍정적 신호가 될 수 있습니다.

&nbsp;

💼 이 문서는 금융 에이전트에서 작성됨.
[출처: 블룸버그 (Bloomberg.com)](https://www.bloomberg.com/news/articles/example)
"""


BROKEN_ARTICLE = """# ⛽ 유가 120달러 재시험 경고가 나왔습니다

&nbsp;

- 호르무즈 해협의 원유 흐름 정상화가 7월로 밀리면 브렌트유와 WTI는 전쟁기 고점인 배럴당 120달러 부근을 다시 시험할 수 있다는 경고가 나왔습니다.

&nbsp;

배경 설명 이번 경고의 핵심은 시장이 너무 빠른 정상화를 이미 가격에 넣고 있다는 점입니다.
- 시장은 6월 정상화를 가격에 반영하고 있습니다.
- 회복이 늦어지면 유가 상방 압력이 커질 수 있습니다.
"""


def _completed(stdout_payload: dict | None, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    stdout = ""
    if stdout_payload is not None:
        stdout = json.dumps(stdout_payload, ensure_ascii=False)
    return subprocess.CompletedProcess(
        args=["python3", "scripts/safari_fetch.py"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class NewsUpdateHarnessTests(unittest.TestCase):
    def test_validate_article_content_accepts_rich_axiostyle_output(self) -> None:
        issues = harness.validate_article_content(
            "26-04-10 20-08 은행주, 최악의 1분기 뒤 실적이 반전의 시험대에 섰습니다.md",
            VALID_ARTICLE,
        )

        self.assertEqual(issues, [])

    def test_validate_article_content_rejects_thin_output_without_footer(self) -> None:
        issues = harness.validate_article_content(
            "26-04-10 19-07 유가 120달러 재시험 경고가 나왔습니다.md",
            BROKEN_ARTICLE,
        )

        self.assertTrue(issues)
        self.assertIn("기사 본문이 너무 짧습니다.", issues)
        self.assertIn("허용된 Axios 전환구 섹션이 없습니다.", issues)
        self.assertIn("마지막 금융 에이전트 표기가 없습니다.", issues)
        self.assertIn("마지막 출처 링크가 없습니다.", issues)

    def test_apply_manifest_payload_writes_files_and_state_after_validation(self) -> None:
        payload = {
            "articles": [
                {
                    "filename": "26-04-10 20-08 은행주, 최악의 1분기 뒤 실적이 반전의 시험대에 섰습니다.md",
                    "content": VALID_ARTICLE,
                }
            ],
            "state": {
                "last_run_kst": "2026-04-10T20:08:00+09:00",
                "bloomberg": "https://www.bloomberg.com/news/articles/example",
                "wsj": "https://www.wsj.com/articles/example",
                "barrons": "https://www.barrons.com/articles/example",
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            result = harness.apply_manifest_payload(payload, workspace=workspace)

            self.assertTrue(result["ok"])
            article_path = workspace / harness._nfd("NewsUpdate") / harness._nfd(
                payload["articles"][0]["filename"]
            )
            state_path = workspace / harness._nfd("NewsUpdate") / ".state.json"

            self.assertTrue(article_path.exists())
            self.assertTrue(state_path.exists())

            with open(article_path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), VALID_ARTICLE)
            with open(state_path, "r", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), payload["state"])

    def test_apply_manifest_payload_keeps_state_unchanged_when_validation_fails(self) -> None:
        payload = {
            "articles": [
                {
                    "filename": "26-04-10 19-07 유가 120달러 재시험 경고가 나왔습니다.md",
                    "content": BROKEN_ARTICLE,
                }
            ],
            "state": {
                "last_run_kst": "2026-04-10T19:07:59+09:00",
                "bloomberg": "https://www.bloomberg.com/news/articles/new-head",
                "wsj": "https://www.wsj.com/articles/new-head",
                "barrons": "https://www.barrons.com/articles/new-head",
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            news_dir = workspace / harness._nfd("NewsUpdate")
            news_dir.mkdir(parents=True, exist_ok=True)
            state_path = news_dir / ".state.json"
            original_state = {
                "last_run_kst": "2026-04-10T18:04:00+09:00",
                "bloomberg": "https://www.bloomberg.com/news/articles/original",
                "wsj": "https://www.wsj.com/articles/original",
                "barrons": "https://www.barrons.com/articles/original",
            }
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump(original_state, handle, ensure_ascii=False, indent=2)

            with self.assertRaises(ValueError):
                harness.apply_manifest_payload(payload, workspace=workspace)

            with open(state_path, "r", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), original_state)

            article_path = news_dir / harness._nfd(payload["articles"][0]["filename"])
            self.assertFalse(article_path.exists())

    def test_resolve_existing_article_path_accepts_newsupdate_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            resolved = harness._resolve_existing_article_path(
                workspace,
                "NewsUpdate/26-04-10 19-07 유가 120달러 재시험 경고가 나왔습니다.md",
            )

            expected = (
                workspace
                / harness._nfd("NewsUpdate")
                / harness._nfd("26-04-10 19-07 유가 120달러 재시험 경고가 나왔습니다.md")
            )
            self.assertEqual(resolved, expected)

    def test_validate_dir_checks_articles_and_error_reports_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            news_dir = workspace / harness._nfd("NewsUpdate")
            news_dir.mkdir(parents=True, exist_ok=True)

            article_path = news_dir / harness._nfd(
                "26-04-10 20-08 은행주, 최악의 1분기 뒤 실적이 반전의 시험대에 섰습니다.md"
            )
            error_path = news_dir / "ERROR-26-04-10 20-09.md"

            article_path.write_text(VALID_ARTICLE, encoding="utf-8")
            error_path.write_text(
                "# 오류 보고서\n- 발생 시각 (KST): 2026-04-10 20:09\n- 소스: Bloomberg\n",
                encoding="utf-8",
            )

            stdout = StringIO()
            with mock.patch("sys.stdout", stdout):
                rc = harness.main(
                    [
                        "validate-dir",
                        "--workspace",
                        str(workspace),
                    ]
                )

            self.assertEqual(rc, 0)
            report = json.loads(stdout.getvalue())
            self.assertTrue(report["ok"])
            self.assertEqual(report["matched"], 2)
            self.assertEqual(len(report["files"]), 2)

    def test_fetch_article_with_harness_retries_browser_closed_once(self) -> None:
        first_failure = {
            "success": False,
            "url": "https://www.wsj.com/articles/example",
            "title": "",
            "text": "",
            "html": "",
            "error": "Google Chrome 브라우저 세션이 예상치 않게 종료되었습니다. 원본 오류: Target page, context or browser has been closed",
            "paywall": False,
        }
        diagnose = {
            "ready": True,
            "attach": {"ok": True},
            "javascript": {"ok": True},
        }
        second_success = {
            "success": True,
            "url": "https://www.wsj.com/articles/example",
            "title": "Recovered article",
            "text": "본문 " * 100,
            "html": "<html></html>",
            "error": None,
            "paywall": False,
        }

        with mock.patch(
            "scripts.news_update_harness.subprocess.run",
            side_effect=[
                _completed(first_failure),
                _completed(diagnose),
                _completed(second_success),
            ],
        ) as mock_run:
            result = harness.fetch_article_with_harness(
                "https://www.wsj.com/articles/example",
                recovery_wait=0,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["harness_attempts"], 2)
        self.assertIn("diagnose", result)
        self.assertEqual(mock_run.call_count, 3)

        first_command = mock_run.call_args_list[0].args[0]
        second_command = mock_run.call_args_list[1].args[0]
        self.assertIn("scripts/safari_fetch.py", first_command[1])
        self.assertNotIn("--diagnose", first_command)
        self.assertIn("--diagnose", second_command)

    def test_fetch_article_with_harness_does_not_retry_missing_devtools_dependency(self) -> None:
        permission_failure = {
            "success": False,
            "url": "https://www.wsj.com/articles/example",
            "title": "",
            "text": "",
            "html": "",
            "error": "Python websockets 패키지가 설치되어 있지 않습니다. `python3 -m pip install websockets`로 설치한 뒤 다시 시도해 주세요.",
            "paywall": False,
        }

        with mock.patch(
            "scripts.news_update_harness.subprocess.run",
            return_value=_completed(permission_failure),
        ) as mock_run:
            result = harness.fetch_article_with_harness(
                "https://www.wsj.com/articles/example",
                recovery_wait=0,
            )

        self.assertFalse(result["success"])
        self.assertEqual(result["harness_attempts"], 1)
        self.assertEqual(mock_run.call_count, 1)

    def test_fetch_batch_command_reports_mixed_results(self) -> None:
        stdout = StringIO()
        with mock.patch.object(
            harness,
            "fetch_article_with_harness",
            side_effect=[
                {"success": True, "url": "https://example.com/a"},
                {"success": False, "url": "https://example.com/b"},
            ],
        ), mock.patch.object(
            harness,
            "_run_fetch_diagnose",
            return_value={"ready": True, "browser": "chrome"},
        ):
            with mock.patch("sys.stdout", stdout):
                rc = harness.main(
                    [
                        "fetch-batch",
                        "--url",
                        "https://example.com/a",
                        "--url",
                        "https://example.com/b",
                    ]
                )

        self.assertEqual(rc, 1)
        report = json.loads(stdout.getvalue())
        self.assertFalse(report["ok"])
        self.assertEqual(report["requested"], 2)
        self.assertEqual(report["succeeded"], 1)
        self.assertEqual(report["failed"], 1)
        self.assertFalse(report["skipped_due_to_preflight"])
        self.assertEqual(report["preflight"]["browser"], "chrome")

    def test_fetch_batch_with_harness_short_circuits_on_preflight_failure(self) -> None:
        diagnose = {
            "ready": False,
            "availability": {
                "ok": False,
                "detail": "Google Chrome 앱을 찾지 못했습니다. checked: /Applications/Google Chrome.app",
            },
        }

        with mock.patch.object(harness, "_run_fetch_diagnose", return_value=diagnose), \
             mock.patch.object(harness, "fetch_article_with_harness") as mock_fetch:
            report = harness.fetch_batch_with_harness(
                [
                    "https://example.com/a",
                    "https://example.com/b",
                ]
            )

        self.assertFalse(report["ok"])
        self.assertTrue(report["skipped_due_to_preflight"])
        self.assertEqual(report["requested"], 2)
        self.assertEqual(report["failed"], 2)
        self.assertEqual(report["preflight"], diagnose)
        self.assertEqual(mock_fetch.call_count, 0)
        self.assertTrue(all(item["skipped_by_preflight"] for item in report["results"]))
        self.assertTrue(all(item["harness_attempts"] == 0 for item in report["results"]))
        self.assertTrue(
            all("Google Chrome 앱을 찾지 못했습니다" in item["error"] for item in report["results"])
        )


if __name__ == "__main__":
    unittest.main()
