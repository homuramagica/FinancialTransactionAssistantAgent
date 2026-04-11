import datetime as dt
import json
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


if __name__ == "__main__":
    unittest.main()
