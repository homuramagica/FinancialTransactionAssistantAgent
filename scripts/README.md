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

# RSS 목록 + 브라우저 본문 수집

`scripts/safari_fetch.py`는
- WSJ/Barron's 기사 목록: Dow Jones RSS CSV 1회 조회 후 동시 분기
- Bloomberg 기사 목록: Bloomberg RSS CSV
- 개별 기사 본문: Chrome DevTools remote debugging + 전용 Chrome 프로필
를 사용한다.

파일명은 호환성 때문에 유지하지만 브라우저 수집 경로는 DevTools 전용이다.
본문 수집이나 진단이 끝나면 탭을 닫고 Chrome 앱도 기본적으로 종료한다.
필요할 때만 `--no-close`로 Chrome 종료를 생략할 수 있다.

`scripts/firefox_visible_fetch.py`는
- Firefox 일반 모드를 보이는 창으로 직접 열고
- 기사 본문을 확보하면 탭을 닫고 Firefox 앱도 종료하고
- Bloomberg는 기본 20초, Dow Jones 계열은 기본 10초 간격을 두는
메인 수집 경로다.

이 경로는 `open -a Firefox ...` + macOS UI scripting만 사용하며,
Playwright / Firefox remote debugging / WebDriver / BiDi를 쓰지 않는다.

## 기본 설정

- 기본 브라우저는 `chrome`이다.
- 이전 `safari` 설정이나 `NEWS_FETCH_BROWSER=safari` 값이 남아 있어도 내부적으로 `chrome`으로 정규화된다.
- Python 패키지 `websockets`가 필요하다: `python3 -m pip install websockets`
- 기본 DevTools 프로필 경로는 `tmp/chrome_devtools_profile`이며 `NEWS_FETCH_DEVTOOLS_PROFILE_PATH`로 바꿀 수 있다.
- Chrome 136+ 보안 변경 때문에 기본 Chrome 사용자 데이터 폴더에는 원격 디버깅 포트를 붙일 수 없어, 비표준 사용자 데이터 폴더를 유지해야 한다.
- 기본 원격 디버깅 포트는 `9222`이며 `NEWS_FETCH_DEVTOOLS_PORT`로 바꿀 수 있다.
- `safari_fetch.py`는 필요한 경우 Chrome 번들 내부 실행 파일을 우선 직접 실행하고, 실패하면 `open -na Google Chrome.app`로 한 번 더 폴백한다.
- LaunchServices가 간헐적으로 깨지는 환경이면 `NEWS_FETCH_CHROME_LAUNCH_MODE=direct`로 강제할 수 있다. 기본값은 `auto`다.
- 브라우저 자동화는 공용 파일 락(`/tmp/safari_fetch_browser.lock`)으로 직렬화된다.
  동시에 여러 `safari_fetch.py` 프로세스를 띄워도 기사 본문 연결은 자동으로 한 건씩 순서대로 진행된다.
  필요하면 `--lock-timeout 180`처럼 대기 시간을 늘릴 수 있다.

## 빠른 진단

```bash
python3 scripts/safari_fetch.py --diagnose --browser chrome
```

- 이 진단은 `websockets` 패키지, Chrome 앱 번들/실행 파일 검증, DevTools 포트 연결, 전용 프로필 접근, 페이지 JavaScript 실행 여부를 한 번에 점검한다.

## 세션 준비

유료 기사 본문을 읽으려면 DevTools용 Chrome 프로필에 한 번 로그인해 두는 편이 좋다.

```bash
python3 scripts/safari_fetch.py https://www.wsj.com --session-setup
```

- 브라우저 창이 열리면 로그인/구독 인증을 완료한 뒤 Enter를 누른다.
- 완료되면 `tmp/chrome_devtools_profile` 아래의 Chrome 프로필에 세션이 유지된다.
- 다른 위치를 쓰고 싶다면 `NEWS_FETCH_DEVTOOLS_PROFILE_PATH`로 명시한 경로 아래에 세션이 유지된다.
- 이후 본문 수집은 이 로그인된 DevTools Chrome 세션의 새 탭에서 진행된다.

## 링크 수집 예시

```bash
python3 scripts/safari_fetch.py ignored --links-only --source dow_jones
python3 scripts/safari_fetch.py ignored --load-more --source bloomberg
```

- `--source dow_jones`는 Dow Jones RSS CSV를 한 번 읽어 WSJ와 Barron's 링크를 함께 반환한다.
- 반환 JSON의 각 항목에는 `source=wsj|barrons`가 함께 포함된다.

## 자동화에서만 실패할 때 체크할 것

- `python3 -m pip install websockets`가 끝났는지 확인
- `python3 scripts/safari_fetch.py --diagnose --browser chrome`가 통과하는지 확인
- `--session-setup`으로 WSJ/Barron's/Bloomberg 로그인 상태를 DevTools Chrome 프로필에 한 번 준비해 두기
- 다른 프로세스가 같은 수집 작업을 동시에 실행하고 있지 않은지 확인

## NewsUpdate 하네스

`scripts/news_update_harness.py`는 Axios식 기사 초안과 `.state.json` 갱신을 한 번에 검증하고,
검증을 통과한 배치만 `/NewsUpdate/`에 원자적으로 반영한다.
또한 기사 본문 수집을 브라우저별 subprocess로 감싸서,
Chrome DevTools 기본 경로와 visible 계열 폴백 경로를 함께 관리한다.

기본 브라우저는 `chrome`이다.
- 메인 경로: `chrome` (Chrome DevTools)
- 1차 폴백: `chrome-visible`
- 2차 폴백: `firefox-visible`
- visible 경로들은 원격 디버깅/Playwright를 사용하지 않는다.
- 매체별 접근 간격 기본값은 `bloomberg=20초`, `dow_jones=10초`다.

### 신규 기사 후보 큐 확인

`.state.json` 경계를 기준으로 소스별 신규 기사 후보만 잘라서 보고 싶다면 아래 명령을 사용한다.

```bash
python3 scripts/news_update_queue.py --workspace . --format md
```

- Bloomberg → WSJ → Barron's 순서로 현재 RSS 창의 신규 후보를 보여준다.
- 점수화나 키워드 랭킹은 하지 않고, `.state.json` 기준 경계만 잘라 준다.

### manifest 검증

```bash
python3 scripts/news_update_harness.py validate-manifest --manifest /tmp/news_batch.json
```

- `articles[]`: `filename`, `content`
- `errors[]`: `filename`, `content` (선택)
- `state`: `last_run_kst`, `bloomberg`, `wsj`, `barrons`

### manifest 반영

```bash
python3 scripts/news_update_harness.py apply-manifest --manifest /tmp/news_batch.json --workspace .
```

- 기사 본문은 기사 길이, Axios 전환구 형식, 리스트 밀도, 출처 링크, 금융 에이전트 표기를 검사한다.
- 검증이 실패하면 기사 파일도, `.state.json`도 쓰지 않는다.

### 이미 생성한 기사 빠른 검사

```bash
python3 scripts/news_update_harness.py validate-files \
  --workspace . \
  --files "26-04-10 20-08 예시 기사.md"
```

### 기사 본문 수집을 하네스로 감싸기

```bash
python3 scripts/news_update_harness.py fetch-article --url "https://www.wsj.com/articles/example"
python3 scripts/news_update_harness.py fetch-batch \
  --url "https://www.wsj.com/articles/example-1" \
  --url "https://www.barrons.com/articles/example-2"
python3 scripts/news_update_harness.py fetch-article \
  --browser chrome \
  --url "https://www.wsj.com/articles/example"
```

- 기본값인 `firefox-visible`은 Firefox 일반 모드를 눈에 보이는 창으로만 조작하고, 본문 확보 후 탭을 닫은 뒤 Firefox 앱도 종료한다.
- 기본값인 `chrome`은 `safari_fetch.py`의 Chrome DevTools 경로를 사용한다.
- `chrome-visible`과 `firefox-visible`은 눈에 보이는 창으로만 조작하고, 본문 확보 후 탭을 닫은 뒤 앱도 종료한다.
- `fetch-batch`는 URL별로 fetch subprocess를 새로 실행하지만, `chrome` 기본 경로와 `chrome-visible`/`firefox-visible` 명시 경로 모두 브라우저 세션 하나를 유지한 채 기사들을 순차 수집하고 배치 종료 직전에 한 번만 정리 종료한다.
- `fetch-batch`는 기본적으로 자동 브라우저 폴백을 끄고 진행해, 한 기사 실패 때문에 배치 전체가 오래 늘어지는 일을 줄인다. 필요할 때만 `--allow-chrome-fallback`을 명시한다.
- `chrome` 경로에서는 DevTools 불안정 신호가 나오면 `--diagnose`를 자동 실행하고, 하네스 차원에서 1회 더 재시도한다.
- 자동화에서는 Python 루프 안에서 `safari_fetch.py`나 `firefox_visible_fetch.py`를 직접 반복 호출하기보다 이 하네스를 우선 사용한다.

### NewsUpdate 디렉터리 일괄 검사

```bash
python3 scripts/news_update_harness.py validate-dir --workspace . --glob "*.md" --limit 20
```

- 최근 20개 기사/오류 보고서를 한 번에 검사한다.
- `--glob`으로 기사만(`26-*.md`) 또는 오류 보고서만(`ERROR-*.md`) 따로 볼 수 있다.

---

# Research 아카이브 도구

`scripts/research_archive_cli.py`는 장기 경제/금융 연구용 기사 원문 아카이브를 `/Research/`에 저장하고,
별도 SQLite 카탈로그(`Research/research_archive.sqlite3`)와 청크 검색 인덱스를 관리한다.

- 목적: `Axios식 요약`이 아니라 **기사 전문 보관 + 검색 가능 아카이브 구축**
- 저장 위치: `/Research/`
- 검색 인덱스: 해시 기반 문자 n-gram 임베딩 + SQLite 카탈로그
- 주의: 이 도구는 `FEED`나 `world_memory` 대신 **직접 검색으로 찾은 자료**를 쌓는 용도다.
- 유료 매체 본문 수집은 `scripts/news_update_harness.py fetch-article` 경로를 내부적으로 재사용한다.
- 연구 아카이브 수집은 봇 탐지 회피를 위해 매체 bucket별 접근 간격 기본값을 **15초**로 사용한다.

## 초기화

```bash
python3 scripts/research_archive_cli.py init
```

## 기사 1건 수집 + 저장 + 인덱싱

```bash
python3 scripts/research_archive_cli.py fetch-url \
  --url "https://www.bloomberg.com/..." \
  --tag 2008_crisis \
  --tag cdo \
  --tag pre_crisis
```

## 기존 Markdown 기사 인덱싱

```bash
python3 scripts/research_archive_cli.py ingest-md \
  --file "Research/2008-09-15 Bloomberg ... .md" \
  --tag lehman
```

## 시맨틱 검색

```bash
python3 scripts/research_archive_cli.py search \
  --query "AIG CDS collateral calls" \
  --limit 10 \
  --format md
```

## 최근 기사 목록

```bash
python3 scripts/research_archive_cli.py list --limit 20 --format md
```

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
- 기본 시간대: `KST(Asia/Seoul)`
- 기본 철학: raw article 전문보다 `summary`, `why_it_matters`, `portfolio_link`, `story`, `story_thesis`, `story_checkpoint`, `sources`, `tags`, `tickers` 중심의 summary-first memory
- 2.5 계층: append-only issue log 위에 `world_issue_states`를 얹어, 현재 유효한 상태(`active/watch`)를 별도로 읽는다.
- 엔트리 모드: `issue`(중기 이슈)와 `brief`(주체/산업 짧은 메모)
- `issue`/`brief` 공통으로 `dedupe_key`가 비어 있으면 자동 생성된다.
- `brief`와 메타데이터가 있는 `issue`는 저장 전에 story router가 기존 스토리/안정 패밀리에 자동 연결을 시도한다.
- `story_family`는 항상 **부모 family**를 canonical하게 저장하고, branch 분화는 `story-link` 메모/`story-family-review` 제안으로 분리해 본다.
- 기본 분류:
  - `category`: `stock_bond`, `geopolitics`, `emerging`
  - `region`: `US`, `KR`, `GLOBAL`
  - `importance`: `high`, `medium`, `low`
- 어닝(earnings) 우선순위 규칙:
  - `event_kind/tags/title/summary`에서 어닝 신호가 감지되면 `importance`를 최소 `medium`으로 자동 상향한다.
  - 가이던스 상·하향, beat/miss, 실적 서프라이즈/쇼크 등 강한 신호는 `importance=high`로 자동 상향한다.
  - `brief`에서 어닝 신호가 있고 `category=emerging`이면 `category=stock_bond`로 자동 보정한다.
- `story`, `tags`, `tickers`는 기존 값을 우선 재사용하고, 기존 규격으로 설명이 어려울 때만 새 값을 최소 단위로 추가한다.
- `state_key`, `net_effect`도 기존 값을 우선 재사용하고, 꼭 필요한 경우에만 새 키를 추가한다.
- `brief` 메모는 `subjects`, `industries`, `event_kind`, `dedupe_key`를 중심으로 저장하며 기본적으로 derived state를 만들지 않는다.

## 초기화

```bash
python3 scripts/world_memory_cli.py init
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

기본 동작은 SQLite 저장이다.
- 자동화 중복 제어가 필요하면 `--dedupe-key`, `--skip-if-duplicate`, `--dedupe-days`를 함께 사용한다.

출처는 최소 1개가 필요하며 아래 방식 중 하나를 사용한다.
- `--source "매체|URL|게시시각(옵션)|메모(옵션)"` (여러 번 지정 가능)
- `--sources-json '[{"name":"...","url":"..."}]'`
- `--sources-file sources.json`

스토리 중심 로그를 위해 아래 필드를 권장한다.
- `--story`: 이슈를 묶는 상위 내러티브 라벨
- `--story-thesis`: 핵심 테제 1문장
- `--story-checkpoint`: 스토리 유지/무효화 체크포인트
- 주체/산업 확장 필드:
  - `--subject "이름|type"`: `politician`, `business_leader`, `company`, `institution` 등
  - `--industries`: 관련 산업/업종 (콤마 구분)
  - `--event-kind`: `statement`, `regulation`, `industry_trend` 같은 canonical key

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
python3 scripts/world_memory_cli.py taxonomy --type subject --format pretty
```

운영 원칙:
- 저장 전 기존 `story/tag/ticker`를 우선 재사용한다.
- 새로운 값은 기존 규격으로 의미를 담기 어려울 때만 추가한다.
- 동의어 중복, 일회성 라벨, 과도한 세분화는 피한다.

## 품질 진단 / 정리

```bash
python3 scripts/world_memory_cli.py audit --format md
python3 scripts/world_memory_cli.py cleanup --dry-run
python3 scripts/world_memory_cli.py cleanup
```

- `audit`: 스토리 채움률, dedupe 커버리지, 레거시 공백, orphan brief, cleanup 대상 수를 한 번에 점검한다.
- `cleanup`: 정규화, 레거시 메타데이터 백필, story routing, canonical story family 정리, taxonomy/state/story-link 재생성을 묶어 실행한다.
- 운영 루틴은 보통 `audit -> cleanup --dry-run -> cleanup` 순서를 권장한다.

## 유지보수 하네스

```bash
python3 scripts/world_memory_harness.py
python3 scripts/world_memory_harness.py --strict
python3 scripts/world_memory_harness.py --format json --out reports/world_memory_harness.json
```

- `world_memory_harness.py`는 `audit` 지표를 읽어 유지보수 임계치를 빠르게 검사한다.
- 기본 점검 항목:
  - `Cleanup candidates` 최대치
  - `Legacy blank issues` 최대치
  - `Orphan briefs with metadata` 비율
  - `Issue/Brief dedupe fill rate` 최소치
  - 최근 기간 엔트리 최소 개수
- `--strict`를 켜면 경고(`warn`)가 하나라도 있을 때 종료코드 `1`로 반환한다.
- 운영 자동화에서는 하네스를 먼저 돌린 뒤, 경고가 있으면 `cleanup --dry-run`으로 원인 범위를 확인하는 흐름을 권장한다.

## 상태 스냅샷 조회 / 재구성

```bash
python3 scripts/world_memory_cli.py states --status active --format md
python3 scripts/world_memory_cli.py states --status all --state-key oil_geopolitical_risk --format pretty
python3 scripts/world_memory_cli.py state-sync
```

- `states`: 현재/과거 상태 스냅샷 조회
- `state-sync`: 기존 issue log에서 **반복 story** 또는 **명시적 `state_key`** 를 읽어 derived 상태를 재구성
- derived 상태는 모든 `story`에 대해 자동 생성하지 않는다. 기본적으로 동일 story가 `issue` 기준 2건 이상 누적되었거나, 명시적 `state_key`가 있을 때만 레짐 후보로 남긴다.
- 수동 상태가 있는 `state_key`는 `state-sync`가 덮어쓰지 않는다.
- `brief` 엔트리는 `derive_state=false`가 기본이라 `state-sync` 대상에서 제외된다.

## 주체/산업 브리프 저장

```bash
python3 scripts/world_memory_cli.py brief-add \
  --title "젠슨 황, AI 수요 발언 유지" \
  --summary "AI 서버 수요에 대한 자신감 유지 발언." \
  --subject "Jensen Huang|business_leader" \
  --subject "NVIDIA|company" \
  --industry semiconductors \
  --industry "ai infrastructure" \
  --event-kind statement \
  --source "Regular media feed|https://rss.app/feeds/_hc8HiU0HyBWHfWoM.csv|2026-03-10T08:35:00+09:00"
```

- `brief-add`는 `category=emerging`, `region=GLOBAL`, `importance=low`를 기본값으로 사용한다.
- 단, 어닝 신호가 감지되면 기본값보다 높은 우선순위 규칙(자동 중요도 상향/카테고리 보정)이 적용된다.
- 주체/산업/이벤트 중 최소 하나는 있어야 저장된다.
- 기본 `dedupe_key`는 제목/주체/산업/날짜를 바탕으로 자동 생성된다.
- 중동/관세/금리/AI 같은 대표 테마는 저장 시 안정적인 `story/story_family`로 자동 라우팅된다.

## 자동화용 브리프 배치 입력

```bash
python3 scripts/world_memory_cli.py brief-import \
  --from-file tmp/world_memory_briefs.json \
  --skip-if-duplicate
```

- 입력 파일은 `.json`만 지원한다.
- 저장소는 항상 `portfolio/world_issue_log.sqlite3`인 SQLite다.
- 각 row는 최소한 `title`, `summary`, `sources[]`를 가져야 한다.
- `entry_mode`는 자동으로 `brief`, `derive_state`는 자동으로 `false`로 강제된다.

## 로그 조회

```bash
python3 scripts/world_memory_cli.py list --days 14 --format md
python3 scripts/world_memory_cli.py list --days 30 --category stock_bond --region KR --importance high --format csv --out reports/world_issue_slice.csv
python3 scripts/world_memory_cli.py list --entry-mode brief --subject Jensen --days 30 --format md
```

## 보고서 생성

```bash
python3 scripts/world_memory_cli.py report --days 14 --out reports/world_memory_report_$(date +%F).md
python3 scripts/world_memory_cli.py report --preset recent_industry_trends --days 30 --out reports/recent_industry_trends_$(date +%F).md
python3 scripts/world_memory_cli.py report --preset "최근 산업계 동향" --days 30 --out reports/recent_industry_trends_$(date +%F).md
```

`report` 기본 섹션:
1. 현재 유효한 상태 (State Snapshots)
2. 시장을 주도하는 스토리 (Narrative Lens)
3. 주식/채권 주요 이슈 (미국/한국/글로벌 분리)
4. 글로벌 정치 이슈
5. 비지배적 관심 이슈
6. 포트폴리오 상담 반영 체크포인트
7. 결론

`report --preset recent_industry_trends` (또는 `--preset "최근 산업계 동향"`)은
- 보고서 제목 기본값을 `최근 산업계 동향`으로 사용하고,
- 매크로/메가톤 헤드라인보다 기업·산업 실행 신호를 우선 추출하며,
- `entry-mode` 기본 `issue`를 자동으로 `all`로 확장해 brief 로그까지 함께 반영한다.

## 의존성 메모
- 필수: `yfinance`, `pandas`, `matplotlib`
- 설치 예시:
  - `uv pip install --python .venv/bin/python -r requirements.txt`
