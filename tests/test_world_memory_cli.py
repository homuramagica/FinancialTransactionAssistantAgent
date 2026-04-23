import datetime as dt
import json
import argparse
import tempfile
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts import world_memory_cli as wm


class WorldMemoryCliTests(unittest.TestCase):
    def _sources(self) -> list[dict[str, str]]:
        return [{"name": "Test Source", "url": "https://example.com"}]

    def _make_issue_payload(
        self,
        *,
        as_of: dt.datetime,
        title: str,
        summary: str,
        story: str,
    ) -> dict:
        return wm._build_issue_payload(
            as_of=as_of,
            category="stock_bond",
            region="GLOBAL",
            importance="medium",
            entry_mode="issue",
            title=title,
            summary=summary,
            why_it_matters="",
            portfolio_link="",
            horizon="수일~수주",
            tickers=["SPY"],
            tags=["rates"],
            subjects=[],
            industries=["capital_markets"],
            event_kind="capital_markets",
            sources=self._sources(),
            story=story,
            story_key="",
            story_family="",
            story_thesis="",
            story_checkpoint="",
            story_relation="",
            related_story="",
            story_note="",
            story_confidence=0.55,
            state_key="",
            state_label="",
            state_status="",
            state_bias="",
            net_effect="",
            derive_state=True,
            dedupe_key="",
        )

    def _make_brief_payload(
        self,
        *,
        as_of: dt.datetime,
        title: str,
        summary: str,
        story: str,
        story_family: str = "",
        story_thesis: str = "",
        story_checkpoint: str = "",
        manual_story_override: bool = False,
        tags: list[str] | None = None,
        subjects: list[dict[str, str]] | None = None,
        industries: list[str] | None = None,
    ) -> dict:
        payload = wm._build_issue_payload(
            as_of=as_of,
            category="stock_bond",
            region="GLOBAL",
            importance="medium",
            entry_mode="brief",
            title=title,
            summary=summary,
            why_it_matters="",
            portfolio_link="",
            horizon="수일~수주",
            tickers=["ITA"],
            tags=tags or ["defense", "ipo", "europe"],
            subjects=subjects
            or [{"name": "European Defense Industry", "type": "market_actor"}],
            industries=industries or ["defense", "capital_markets", "manufacturing"],
            event_kind="industry_trend",
            sources=self._sources(),
            story=story,
            story_key="",
            story_family=story_family,
            story_thesis=story_thesis,
            story_checkpoint=story_checkpoint,
            story_relation="",
            related_story="",
            story_note="",
            story_confidence=0.55,
            state_key="",
            state_label="",
            state_status="",
            state_bias="",
            net_effect="",
            derive_state=False,
            dedupe_key="",
        )
        if manual_story_override:
            payload["manual_story_override"] = True
        return payload

    def test_treasury_story_rule_requires_us_signal(self) -> None:
        japan_story = wm._infer_story_metadata_by_rules(
            {
                "title": "장기 JGB 금리 급등으로 일본 금리 변동성 재상향",
                "summary": "일본 장기채 금리와 환율 변동성이 다시 확대됐다.",
                "tags": ["japan", "jgb", "rates", "duration", "volatility"],
                "subjects": [{"name": "Japanese Government", "type": "institution"}],
                "industries": ["public_finance", "capital_markets"],
                "tickers": ["EWJ", "TLT", "IEF"],
                "region": "GLOBAL",
                "event_kind": "capital_markets",
            }
        )
        self.assertIsNotNone(japan_story)
        self.assertEqual(japan_story["story"], "글로벌 금리·FX 방어")

        treasury_story = wm._infer_story_metadata_by_rules(
            {
                "title": "미국 3·6개월물 입찰에서 응찰 강도 유지",
                "summary": "미국 재무부 단기물 입찰 수요가 유지됐다.",
                "tags": ["treasury", "auction", "rates", "us"],
                "subjects": [{"name": "U.S. Treasury", "type": "institution"}],
                "industries": ["public_finance", "capital_markets"],
                "tickers": ["TLT", "IEF", "^TNX"],
                "region": "US",
                "event_kind": "capital_markets",
            }
        )
        self.assertIsNotNone(treasury_story)
        self.assertEqual(treasury_story["story"], "재무부 공급·바이백 조합")

    def test_derived_state_requires_repeated_issue_story(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "world_issue_log.sqlite3"
            as_of = dt.datetime(2026, 4, 9, 9, 0, tzinfo=ZoneInfo(wm.DEFAULT_TZ))
            with wm._connect_db(db_path) as conn:
                wm._init_db(conn)

                first_payload = wm._prepare_payload_for_storage(
                    conn,
                    self._make_issue_payload(
                        as_of=as_of,
                        title="첫 번째 스토리 이벤트",
                        summary="첫 번째 반복 전 이벤트",
                        story="반복 전 스토리",
                    ),
                    story_catalog=[],
                )
                wm._upsert_sqlite_payload(conn, first_payload)
                self.assertIsNone(wm._upsert_derived_state_for_issue(conn, first_payload))

                second_payload = wm._prepare_payload_for_storage(
                    conn,
                    self._make_issue_payload(
                        as_of=as_of + dt.timedelta(days=1),
                        title="두 번째 스토리 이벤트",
                        summary="두 번째 이벤트로 반복 스토리 성립",
                        story="반복 전 스토리",
                    ),
                    story_catalog=[],
                )
                wm._upsert_sqlite_payload(conn, second_payload)
                derived_state = wm._upsert_derived_state_for_issue(conn, second_payload)

                self.assertIsNotNone(derived_state)
                self.assertEqual(derived_state["state_key"], "반복_전_스토리")

    def test_normalize_story_links_canonicalizes_family_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "world_issue_log.sqlite3"
            now = dt.datetime(2026, 4, 9, 9, 0, tzinfo=ZoneInfo(wm.DEFAULT_TZ)).isoformat()
            payload_json = json.dumps(
                {
                    "link_id": "link-1",
                    "story_key": "유가_중심_금리_재가격",
                    "story_label": "유가 중심 금리 재가격",
                    "related_story_key": "중동_리스크와_에너지_가격",
                    "related_story_label": "중동 리스크와 에너지 가격",
                    "relation_type": "branches_from",
                    "story_family_key": "중동_에너지_충격_tlt_energy",
                    "story_family_label": "중동 에너지 충격 - TLT / energy",
                    "source_event_id": "",
                    "source_kind": "manual",
                    "note": "기존 branch 기록",
                    "confidence": 0.7,
                    "created_at": now,
                    "updated_at": now,
                },
                ensure_ascii=False,
            )
            with wm._connect_db(db_path) as conn:
                wm._init_db(conn)
                conn.execute(
                    """
                    INSERT INTO world_issue_story_links (
                        link_id, story_key, story_label, related_story_key, related_story_label,
                        relation_type, story_family_key, story_family_label, source_event_id,
                        source_kind, note, confidence, created_at, updated_at, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "link-1",
                        "유가_중심_금리_재가격",
                        "유가 중심 금리 재가격",
                        "중동_리스크와_에너지_가격",
                        "중동 리스크와 에너지 가격",
                        "branches_from",
                        "중동_에너지_충격_tlt_energy",
                        "중동 에너지 충격 - TLT / energy",
                        "",
                        "manual",
                        "기존 branch 기록",
                        0.7,
                        now,
                        now,
                        payload_json,
                    ),
                )

                updated = wm._normalize_story_links(conn)
                row = conn.execute(
                    "SELECT story_family_key, story_family_label FROM world_issue_story_links WHERE link_id = ?",
                    ("link-1",),
                ).fetchone()

                self.assertEqual(updated, 1)
                self.assertEqual(row["story_family_key"], "중동_리스크와_에너지_가격")
                self.assertEqual(row["story_family_label"], "중동 리스크와 에너지 가격")

    def test_cleanup_dry_run_rolls_back_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "world_issue_log.sqlite3"
            as_of = dt.datetime(2026, 4, 10, 9, 0, tzinfo=ZoneInfo(wm.DEFAULT_TZ))
            with wm._connect_db(db_path) as conn:
                wm._init_db(conn)
                payload = wm._prepare_payload_for_storage(
                    conn,
                    self._make_issue_payload(
                        as_of=as_of,
                        title="정상 제목",
                        summary="cleanup dry-run 롤백 검증",
                        story="테스트 스토리",
                    ),
                    story_catalog=[],
                )
                wm._upsert_sqlite_payload(conn, payload)
                conn.execute(
                    "UPDATE world_issue_entries SET title = ? WHERE event_id = ?",
                    ("BROKEN_TITLE", payload["event_id"]),
                )
                conn.commit()

            dry_run_args = argparse.Namespace(
                base_dir=tmpdir,
                db_file="world_issue_log.sqlite3",
                dry_run=True,
            )
            wm._handle_cleanup(dry_run_args)

            with wm._connect_db(db_path) as conn:
                row = conn.execute(
                    "SELECT title FROM world_issue_entries WHERE event_id = ?",
                    (payload["event_id"],),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["title"], "BROKEN_TITLE")

            run_args = argparse.Namespace(
                base_dir=tmpdir,
                db_file="world_issue_log.sqlite3",
                dry_run=False,
            )
            wm._handle_cleanup(run_args)

            with wm._connect_db(db_path) as conn:
                row = conn.execute(
                    "SELECT title FROM world_issue_entries WHERE event_id = ?",
                    (payload["event_id"],),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["title"], "정상 제목")

    def test_manual_story_override_preserves_brief_story_during_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "world_issue_log.sqlite3"
            as_of = dt.datetime(2026, 4, 20, 9, 0, tzinfo=ZoneInfo(wm.DEFAULT_TZ))
            with wm._connect_db(db_path) as conn:
                wm._init_db(conn)

                competing_issue = wm._prepare_payload_for_storage(
                    conn,
                    self._make_issue_payload(
                        as_of=as_of,
                        title="AI 인프라 자본조달 병목 심화",
                        summary="유사 태그가 있어도 manual brief story가 우선해야 한다.",
                        story="데이터센터 수요 → 전력 병목",
                    ),
                    story_catalog=[],
                )
                wm._upsert_sqlite_payload(conn, competing_issue)

                manual_brief = wm._prepare_payload_for_storage(
                    conn,
                    self._make_brief_payload(
                        as_of=as_of + dt.timedelta(hours=1),
                        title="유럽 방산 IPO 가속",
                        summary="manual story를 부여한 brief가 cleanup 후에도 유지돼야 한다.",
                        story="글로벌 방산 붐",
                        story_family="글로벌 방산 붐",
                        story_thesis="brief에는 저장되면 안 되는 issue용 필드",
                        story_checkpoint="cleanup 시 제거돼야 한다.",
                        manual_story_override=True,
                    ),
                )
                self.assertEqual(manual_brief["story"], "글로벌 방산 붐")
                self.assertEqual(manual_brief["story_family"], "글로벌 방산 붐")
                self.assertNotIn("story_thesis", manual_brief)
                self.assertNotIn("story_checkpoint", manual_brief)

                wm._upsert_sqlite_payload(conn, manual_brief)
                conn.commit()

            with wm._connect_db(db_path) as conn:
                wm._init_db(conn)
                scanned, updated, skipped = wm._cleanup_world_issue_entries(conn)
                self.assertEqual(scanned, 2)
                self.assertEqual(skipped, 0)
                self.assertEqual(updated, 0)

                row = conn.execute(
                    "SELECT payload_json FROM world_issue_entries WHERE event_id = ?",
                    (manual_brief["event_id"],),
                ).fetchone()
                self.assertIsNotNone(row)
                stored = json.loads(str(row["payload_json"]))
                self.assertEqual(stored["story"], "글로벌 방산 붐")
                self.assertEqual(stored["story_family"], "글로벌 방산 붐")

    def test_brief_import_skip_duplicate_by_dedupe_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "world_issue_log.sqlite3"
            with wm._connect_db(db_path) as conn:
                wm._init_db(conn)

            import_path = Path(tmpdir) / "brief_rows.json"
            import_payload = [
                {
                    "as_of": "2026-04-12T08:00:00+09:00",
                    "category": "stock_bond",
                    "region": "GLOBAL",
                    "importance": "medium",
                    "title": "중복 테스트 브리프",
                    "summary": "dedupe_key 중복 방지 검증",
                    "horizon": "수일~수주",
                    "tickers": ["SPY"],
                    "tags": ["test"],
                    "subjects": [{"name": "Test Subject", "type": "institution"}],
                    "industries": ["capital_markets"],
                    "event_kind": "capital_markets",
                    "dedupe_key": "brief_duplicate_case",
                    "sources": [{"name": "Test Source", "url": "https://example.com"}],
                }
            ]
            import_path.write_text(json.dumps(import_payload, ensure_ascii=False), encoding="utf-8")

            args = argparse.Namespace(
                base_dir=tmpdir,
                db_file="world_issue_log.sqlite3",
                from_file=str(import_path),
                category="emerging",
                region="GLOBAL",
                importance="low",
                horizon="수일~수주",
                skip_if_duplicate=True,
                dedupe_days=30,
                dry_run=False,
            )
            first_code = wm._handle_brief_import(args)
            second_code = wm._handle_brief_import(args)

            self.assertEqual(first_code, 0)
            self.assertEqual(second_code, 0)
            self.assertEqual(wm._count_sqlite_rows(db_path), 1)


if __name__ == "__main__":
    unittest.main()
