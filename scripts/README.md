# 시장 시황/뉴스레터 도구

`scripts/analyze_market.py`는 `yfinance + 지정 FEED(통합 CSV 2개 + 텔레그램 3개)`를 결합해
시황 Flash Layer와 **LLM 작성용 News Context Cards**를 생성한다.

- 원칙: 파이썬은 데이터 정리 중심(표/리스트/카드), 특히 Flash Layer는 `Score + Signals + Rule Hits`만 출력한다.
- 원칙: 파이썬 출력에는 `결론` 섹션을 넣지 않는다(결론 작성은 LLM 단계 담당).
- 최종 산문 작성은 `SKILLs/MarketAnalysis.md` 지침으로 수행한다.

## 실행 예시

```bash
python3 scripts/analyze_market.py --news-style bloomberg --news-paragraphs 10
python3 scripts/analyze_market.py --news-style bloomberg --news-paragraphs 12 --out reports/market_newsletter_brief.md
```

## 주요 옵션
- `--news-style`: `bloomberg|brief`
- `--news-paragraphs`: 출력할 뉴스 컨텍스트 카드 수 (기본 10)
- `--max-news-items`: 통합 후 분석에 쓰는 뉴스 최대 건수
- `--timeline-items`: 뉴스 테이프에 표시할 최신 뉴스 건수
- `--news-language`: 뉴스 제목 출력 언어 (`ko|original`, 기본 `ko`)
- `--show-original-title`: `--news-language ko`일 때 원문 제목을 괄호로 병기
- `--out`: 결과 Markdown 파일 경로

---

# 캘린더 도구

이 프로젝트는 `yfinance.Calendars`를 사용해서 **어닝 캘린더 / 경제 이벤트 캘린더**를 조회하고, Markdown/CSV/JSON/ICS로 내보낼 수 있다.

- 가상환경 미활성화 상태라면 `python3` 대신 `.venv/bin/python`으로 실행한다.

## 실행 예시

### 어닝 캘린더 (기본 7일, KST로 표시)
```bash
python3 scripts/calendar_cli.py earnings --start 2026-01-23 --limit 50 --format md
```

### 경제 이벤트 캘린더 (14일)
```bash
python3 scripts/calendar_cli.py economic --start 2026-01-23 --days 14 --format md
```

### ICS로 내보내기 (구글/애플 캘린더 임포트용)
```bash
python3 scripts/calendar_cli.py earnings --start 2026-01-23 --days 14 --format ics --out earnings.ics
python3 scripts/calendar_cli.py economic --start 2026-01-23 --days 14 --format ics --out economic.ics
```

## 옵션 메모
- `--format` : `md|csv|json|ics|pretty`
- `--duration-minutes` : `--format ics`일 때 이벤트 지속시간(분)

---

# 포트폴리오 도구

`scripts/portfolio_cli.py`는 사용자 포트폴리오 이력을 JSONL로 기록하고, 누적수익률을 계산/시각화한다.

## 초기화

```bash
python3 scripts/portfolio_cli.py init
```

## 의사결정 로그 추가 (가치관/컨디션/판단 근거)

```bash
python3 scripts/portfolio_cli.py add-decision \
  --date 2026-02-15 \
  --decision-type considering \
  --status planned \
  --summary "기술주 비중 5% 축소 고려" \
  --rationale "변동성 스트레스가 커짐" \
  --condition "수면 부족" \
  --tickers QQQ,NVDA \
  --values 안정성,현금흐름
```

## 상담 답변 종료 시 자동 decision append

`log-counsel`은 상담 답변 텍스트를 받아 요약/티커/태그를 자동 추출하고 `decision_log.jsonl`에 기록한다.

```bash
python3 scripts/portfolio_cli.py log-counsel \
  --query-text "기술주 비중을 줄일까?" \
  --response-file reports/portfolio_strategy_review_2026-02-15.md \
  --status considering
```

STDIN 파이프 입력도 가능:

```bash
cat reports/portfolio_strategy_review_2026-02-15.md | \
python3 scripts/portfolio_cli.py log-counsel \
  --query-text "기술주 비중을 줄일까?" \
  --status considering
```

## 거래/현금 로그 추가

```bash
python3 scripts/portfolio_cli.py add-cash --date 2026-02-14 --amount 10000 --category deposit --memo "초기 입금"
python3 scripts/portfolio_cli.py add-trade --date 2026-02-14 --symbol AAPL --side BUY --qty 10 --price 185.2 --fee 1.0
python3 scripts/portfolio_cli.py add-cash --date 2026-02-20 --amount 5.4 --category dividend --internal --memo "배당"
```

## 백테스트형 NAV 기록

```bash
python3 scripts/portfolio_cli.py add-nav --date 2026-01-31 --nav 100000 --source backtest
python3 scripts/portfolio_cli.py add-nav --date 2026-02-28 --nav 103500 --source backtest
```

## 포지션/성과 조회

```bash
python3 scripts/portfolio_cli.py positions --asof 2026-02-28 --format md
python3 scripts/portfolio_cli.py performance --start 2026-01-01 --end 2026-02-28 --method auto --format md
```

## 누적수익률 차트 저장 (벤치마크 비교 포함)

```bash
python3 scripts/portfolio_cli.py chart --start 2026-01-01 --end 2026-02-28 --benchmark SPY --benchmark QQQ
```

- 차트 라벨 기본값: 좌상단 범례 대신 각 선의 오른쪽 끝에 `자산명 | 수익률%`(소수점 둘째 자리) 형식으로 표시한다(End Label).
- 라벨 스타일 기본값: 흰색 텍스트 + 해당 선 색상 배경 박스.
- `chart` 실행 시 성과 스탯 테이블 PNG도 기본으로 함께 생성된다.
  - 기본 파일명: `차트파일명_stats.png`
  - 비활성화: `--no-stats-table`
  - 출력 경로 지정: `--stats-table-out <path>`
  - Beta 기준: 기본 `SPY`, 필요 시 `--beta-benchmark '^KS11'`처럼 변경
  - 컬럼: `자산명 | Cumulative Return | CAGR | Max Drawdown | Volatility | Sharpe | Sortino | Kelly | Ulcer Index | UPI | Beta`

## 포맷/출력 옵션
- `positions`, `performance`: `--format md|csv|json|pretty`, `--out`
- `chart`: `--out`, `--csv-out`, `--title`, `--width`, `--height`, `--dpi`

---

# 상담 메모리 엔진 (Always-on Memory)

`scripts/counsel_memory_cli.py`는 사용자 발화를 매 턴 단위로 받아
`의미 있는 메모리만` 자동 추출/업서트하고, 변경점(delta)을 이력으로 남긴다.

- 저장소(SQLite): `portfolio/counsel_memory.sqlite3`
- 이벤트 로그(JSONL): `portfolio/counsel_memory_log.jsonl`
- 검색 방식: 다국어 문자 n-gram 기반 벡터 + 키워드 하이브리드
- 메모리 타입 예시:
  - `goal`, `risk_tolerance`, `constraints`, `allocation_decision`, `regime_view`
  - `emotional_state`, `personal_context`, `interest_theme`, `interaction_preference`, `decision_rule`

## 초기화

```bash
python3 scripts/counsel_memory_cli.py init
```

## 턴 단위 자동 반영 (핵심)

```bash
python3 scripts/counsel_memory_cli.py ingest-turn \
  --user-text "포트폴리오가 흔들려서 불안해. 기술주 비중을 줄이는 게 좋을까?" \
  --assistant-text "변동성 상한을 두고 기술주 비중을 단계적으로 낮추자."
```

- 중요도 낮은 후보는 저장하지 않는다 (`--min-importance`, 기본 `0.65`)
- 추출 모드는 기본 `hybrid`(문맥 패턴 + 키워드 fallback)이며 `--extractor-mode instruction|keyword|hybrid`로 전환 가능
- 같은 의미는 `reinforce`, 방침 변화는 `update`로 자동 기록된다.
- 단기 심리/레짐 메모는 TTL 만료 시 `expire` 처리된다.

## 메모리 조회/검색/변경이력

```bash
python3 scripts/counsel_memory_cli.py list --status active --format md
python3 scripts/counsel_memory_cli.py search --query-text "요즘 변동성이 불안해" --format md
python3 scripts/counsel_memory_cli.py deltas --days 30 --format md
```

## 답변 준비팩 자동 생성 (추천)

`prepare-turn`은 가벼운 발화라도 금융 단서(경제/종목/섹터/티커/비중)가 잡히면
아래를 자동으로 묶어 **답변 직전 컨텍스트 팩**을 만든다.

1. 턴 메모리 업서트 (`new/reinforce/update/promote`)
2. 개인 메모리 히트(top-k)
3. 현재 활성 월드 상태(active/watch state snapshots)
4. 최근 월드메모리(기본 21일)
5. 포트폴리오 펄스(누적수익률/낙폭/상위 보유)

```bash
python3 scripts/counsel_memory_cli.py prepare-turn \
  --user-text "요즘 금리랑 관세가 찜찜한데 기술주 비중 유지할까?" \
  --extractor-mode hybrid \
  --format md \
  --out reports/counsel_prep_pack.md
```

- 기본값은 자동 ingest다. 저장 없이 준비만 하려면 `--no-ingest`.
- 금융 단서가 없으면 월드메모리/포트폴리오 조회는 건너뛰고 메모리 중심으로 가볍게 처리한다.

---

# 외부 세계 메모리 도구

`scripts/world_memory_cli.py`는 속보와 분리된 **중기 템포의 시장 동향 로그**를 누적 저장한다.

- 기본 저장소(SQLite): `portfolio/world_issue_log.sqlite3`
- 레거시 미러(JSONL): `portfolio/world_issue_log.jsonl`
- 기본 시간대: `KST(Asia/Seoul)`
- 기본 철학: raw article 전문보다 `summary`, `why_it_matters`, `portfolio_link`, `story`, `story_thesis`, `story_checkpoint`, `sources`, `tags`, `tickers` 중심의 summary-first memory
- 2.5 계층: append-only issue log 위에 `world_issue_states`를 얹어, 현재 유효한 상태(`active/watch`)를 별도로 읽는다.
- 기본 분류:
  - `category`: `stock_bond`, `geopolitics`, `emerging`
  - `region`: `US`, `KR`, `GLOBAL`
  - `importance`: `high`, `medium`, `low`
- `story`, `tags`, `tickers`는 기존 값을 우선 재사용하고, 기존 규격으로 설명이 어려울 때만 새 값을 최소 단위로 추가한다.
- `state_key`, `net_effect`도 기존 값을 우선 재사용하고, 꼭 필요한 경우에만 새 키를 추가한다.

## 초기화

```bash
python3 scripts/world_memory_cli.py init
```

## 기존 JSONL 이관

```bash
python3 scripts/world_memory_cli.py migrate
```

## 이슈 1건 저장

```bash
python3 scripts/world_memory_cli.py add \
  --as-of 2026-02-16T08:30:00+09:00 \
  --category stock_bond \
  --region US \
  --importance high \
  --title "US Treasury yield volatility persists" \
  --summary "장기 금리 변동성이 성장주 밸류에이션과 회사채 스프레드에 압박을 준다." \
  --story "디스인플레이션 기대 vs 성장 둔화 우려" \
  --story-thesis "소비 둔화가 이어지면 인하 기대가 커지지만 경기민감주 변동성이 커진다." \
  --story-checkpoint "미 고용/소비 재가속 여부와 10년물 금리 4.5% 재돌파" \
  --portfolio-link "미국 성장주 비중과 IG/HY 채권 비중의 동시 점검 필요" \
  --tickers QQQ,TLT,HYG \
  --tags rates,credit \
  --source "Bloomberg|https://www.bloomberg.com/markets|2026-02-16T07:00:00+09:00"
```

기본 동작은 SQLite 저장 + JSONL 미러 append다.
- SQLite만 저장하려면: `--no-jsonl-mirror`

출처는 최소 1개가 필요하며 아래 방식 중 하나를 사용한다.
- `--source "매체|URL|게시시각(옵션)|메모(옵션)"` (여러 번 지정 가능)
- `--sources-json '[{"name":"...","url":"..."}]'`
- `--sources-file sources.json`

스토리 중심 로그를 위해 아래 필드를 권장한다.
- `--story`: 이슈를 묶는 상위 내러티브 라벨
- `--story-thesis`: 핵심 테제 1문장
- `--story-checkpoint`: 스토리 유지/무효화 체크포인트

상태 전이까지 함께 저장하려면 아래 옵션을 추가한다.
- `--state-key`: 현재 상태를 묶는 canonical key
- `--state-label`: 읽기 좋은 상태 라벨
- `--state-status`: `active|watch|resolved|overridden`
- `--state-bias`: `bullish|bearish|neutral|mixed`
- `--net-effect`: `oil_up`, `usd_down` 같은 순효과
- `--supersedes-active`: 같은 `state_key`의 최신 active/watch 상태를 자동 대체

예시:

```bash
python3 scripts/world_memory_cli.py add \
  --as-of 2026-02-18T10:20:00+09:00 \
  --category geopolitics \
  --region GLOBAL \
  --importance high \
  --title "Hormuz disruption risk reprices oil volatility" \
  --summary "공급 잉여 baseline은 남아 있지만, 해협 리스크가 단기 유가 프리미엄을 다시 밀어 올린다." \
  --story "공급 여유 vs 지정학 프리미엄" \
  --story-thesis "평시에는 공급이 넉넉하지만, 충격 시에는 지정학 프리미엄이 가격결정을 덮는다." \
  --state-key oil_geopolitical_risk \
  --state-label "유가의 지정학 프리미엄 우위" \
  --state-status active \
  --state-bias bearish \
  --net-effect oil_up \
  --supersedes-active \
  --source "Reuters|https://www.reuters.com/world/|2026-02-18T09:45:00+09:00"
```

## taxonomy 조회 / 재색인

```bash
python3 scripts/world_memory_cli.py taxonomy --refresh --format md
python3 scripts/world_memory_cli.py taxonomy --type story --format pretty
python3 scripts/world_memory_cli.py taxonomy --type tag --limit 50 --format csv --out reports/world_memory_tags.csv
python3 scripts/world_memory_cli.py taxonomy --type state_key --format pretty
```

운영 원칙:
- 저장 전 기존 `story/tag/ticker`를 우선 재사용한다.
- 새로운 값은 기존 규격으로 의미를 담기 어려울 때만 추가한다.
- 동의어 중복, 일회성 라벨, 과도한 세분화는 피한다.

## 상태 스냅샷 조회 / 재구성

```bash
python3 scripts/world_memory_cli.py states --status active --format md
python3 scripts/world_memory_cli.py states --status all --state-key oil_geopolitical_risk --format pretty
python3 scripts/world_memory_cli.py state-sync
```

- `states`: 현재/과거 상태 스냅샷 조회
- `state-sync`: 기존 issue log에서 `story` 또는 `state_key`를 읽어 derived 상태를 재구성
- 일반 `add`도 `story`가 있으면 derived 상태를 자동 갱신한다. `state-sync`는 백필/재구성용이다.
- 수동 상태가 있는 `state_key`는 `state-sync`가 덮어쓰지 않는다.

## 로그 조회

```bash
python3 scripts/world_memory_cli.py list --days 14 --format md
python3 scripts/world_memory_cli.py list --days 30 --category stock_bond --region KR --importance high --format csv --out reports/world_issue_slice.csv
```

## 보고서 생성

```bash
python3 scripts/world_memory_cli.py report --days 14 --out reports/world_memory_report_$(date +%F).md
```

`report` 기본 섹션:
1. 현재 유효한 상태 (State Snapshots)
2. 시장을 주도하는 스토리 (Narrative Lens)
3. 주식/채권 주요 이슈 (미국/한국/글로벌 분리)
4. 글로벌 정치 이슈
5. 비지배적 관심 이슈
6. 포트폴리오 상담 반영 체크포인트
7. 결론

## 의존성 메모
- 필수: `yfinance`, `pandas`, `matplotlib`
- 설치 예시:
  - `uv pip install --python .venv/bin/python -r requirements.txt`
