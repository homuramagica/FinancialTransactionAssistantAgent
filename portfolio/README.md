# portfolio 폴더 운영 가이드

이 폴더는 **사용자 투자 이력 + 외부 세계 이슈 메모리**를 시계열로 기록하기 위한 저장소입니다.

- `decision_log.jsonl`: 투자 판단/가치관/심리/고민 로그
- `position_log.jsonl`: 거래/현금흐름/NAV 스냅샷 로그
- `world_issue_log.sqlite3`: 시장 동향/정치 이슈/관심 이슈 기본 저장소
- `world_issue_log.jsonl`: 외부 세계 로그 레거시 미러
- `counsel_sessions/`: (기본) 상담 질문/답변 원문 백업 JSON

JSONL은 한 줄이 하나의 JSON 레코드입니다.

## 1) `decision_log.jsonl` 용도

포트폴리오 상담(`PortfolioCounseling`) 품질을 높이기 위한 정성 데이터 로그입니다.

기록 예시:

```json
{"schema_version":1,"event_id":"...","logged_at":"2026-02-15T10:00:00+09:00","date":"2026-02-15","entry_type":"decision","decision_type":"considering","status":"planned","summary":"기술주 비중 5% 축소 고려","detail":"","rationale":"변동성 스트레스 증가","condition":"수면부족","horizon":"3M","confidence":0.6,"tickers":["QQQ"],"values":["안정성"],"tags":["rebalance"]}
```

## 2) `position_log.jsonl` 용도

### 2-1. 상세 체결형 기록
- `trade`: 매수/매도 체결
- `cash`: 입출금/배당/수수료 등 현금 이벤트

### 2-2. 백테스트형 기록
- `nav_snapshot`: 날짜별 총자산(NAV) 스냅샷

기록 예시:

```json
{"schema_version":1,"event_id":"...","logged_at":"2026-02-15T10:00:00+09:00","date":"2026-02-14","event_type":"trade","symbol":"AAPL","side":"BUY","quantity":10.0,"price":185.2,"fee":1.0,"currency":"USD","memo":""}
{"schema_version":1,"event_id":"...","logged_at":"2026-02-15T10:01:00+09:00","date":"2026-02-14","event_type":"cash","amount":5000.0,"category":"deposit","external":true,"currency":"USD","memo":"초기 입금"}
{"schema_version":1,"event_id":"...","logged_at":"2026-02-15T10:02:00+09:00","date":"2026-02-14","event_type":"nav_snapshot","nav":100000.0,"source":"backtest","memo":"전략 백테스트"}
```

## 3) `world_issue_log.sqlite3` 용도

속보 중심이 아니라 **중기 템포(요즘 시장 동향)**를 누적하기 위한 외부 세계 로그입니다.

- 운영 방식:
  - 기본 조회/리포트 소스: `world_issue_log.sqlite3`
  - 호환용 append 미러: `world_issue_log.jsonl`

- 분류:
  - `category`: `stock_bond`(주식/채권), `geopolitics`(정치/지정학), `emerging`(비지배 관심 이슈)
  - `region`: `US`, `KR`, `GLOBAL`
  - `importance`: `high`, `medium`, `low`
- 시간:
  - `as_of`, `logged_at` 모두 KST 기준 ISO 8601
- 출처:
  - `sources[]`에 매체명/URL/게시시각을 보존

기록 예시:

```json
{"schema_version":1,"event_id":"...","logged_at":"2026-02-16T16:40:00+09:00","entry_type":"world_issue","as_of":"2026-02-16T09:10:00+09:00","date":"2026-02-16","category":"geopolitics","region":"GLOBAL","importance":"medium","horizon":"1~3개월","title":"Energy corridor disruption risk resurfacing","summary":"에너지 수송 차질 리스크가 원자재 변동성을 키울 가능성.","portfolio_link":"원자재/방어 섹터 헷지 여부 점검","tickers":[],"tags":["energy","geopolitics"],"sources":[{"name":"Reuters","url":"https://www.reuters.com/world/","published_at":"2026-02-16T08:50:00+09:00"}]}
```

## 4) 계산 로직 요약

- `performance --method auto`
  - `nav_snapshot`이 2개 이상이면 NAV 기반 누적수익률 계산
  - 없으면 `trade + cash + yfinance 가격`으로 계산
- `positions`
  - 거래/현금 이벤트를 누적해 특정 날짜 포지션과 현금 계산

## 5) 차트 출력

- `chart` 명령으로 PNG 저장
- `--benchmark SPY --benchmark QQQ`로 비교 곡선 추가
- 차트는 `matplotlib` 필수

## 6) 상담 답변 종료 자동 로그

`log-counsel` 명령은 상담 답변 텍스트를 입력받아 `decision_log.jsonl`에 자동 append합니다.

```bash
python3 scripts/portfolio_cli.py log-counsel \
  --query-text "기술주 비중 줄이는게 맞을까?" \
  --response-file reports/portfolio_strategy_review_2026-02-15.md
```

기본 동작:
- 요약 문장 자동 추출
- 답변 내 티커/가치/태그 자동 추출
- `counsel_sessions/`에 질문/답변 원문 저장

## 7) 외부 세계 메모리 CLI

```bash
python3 scripts/world_memory_cli.py init
python3 scripts/world_memory_cli.py add \
  --category stock_bond --region US --importance high \
  --title "US Treasury yield volatility persists" \
  --summary "장기 금리 변동성이 성장주 밸류에이션과 회사채 스프레드에 압박을 준다." \
  --portfolio-link "미국 성장주 비중과 IG/HY 채권 비중의 동시 점검 필요" \
  --source "Bloomberg|https://www.bloomberg.com/markets|2026-02-16T07:00:00+09:00"

python3 scripts/world_memory_cli.py list --days 14 --format md
python3 scripts/world_memory_cli.py report --days 14 --out reports/world_memory_report_$(date +%F).md
```
