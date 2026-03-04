# AGENTS

이 프로젝트는 금융 정보 습득을 위해 기본적으로 **yfinance API**를 사용한다.

## GitHub 공유/커밋 원칙
- 공식 원격 저장소: `https://github.com/homuramagica/FinancialTransactionAssistantAgent`
- 기본 브랜치: `main`
- 빠른 커밋+푸시: `bash scripts/git_quick_commit.sh "커밋 메시지"`
- 위 스크립트는 현재 브랜치 기준으로 `git add -A -> git commit -> git push`를 순서대로 수행한다.
- 공유 제외 파일은 반드시 `.gitignore`를 따른다 (`.venv`, `tmp`, `reports`, 개인 로그 등).
- 단, `portfolio/world_issue_log.jsonl`, `portfolio/world_issue_log.sqlite3`는 공유 대상이다.

## 동작 원칙
- 기본 데이터 소스는 yfinance이다.
- 실행 환경에 필요한 도구(예: Python, yfinance 등)가 설치되어 있지 않다면, 사용자에게 **설치 여부를 먼저 확인**한 뒤 진행한다.
- 설치가 필요할 때는 가능한 설치 방법(예: pip, uv, venv)을 안내한다.
- yfinance 관련 작업은 `reference/yfinance_reference.md` API 매뉴얼을 참고한다.
- 용어/개념 설명이 필요한 요청에서는 `https://www.investopedia.com`을 우선 검색하고,
  그 다음 초보자 친화적으로 설명한다.
- 초보자 대상/기초 설명 요청이 우선인 경우 `SKILLs/Newbie.md`의 지침을 추가 적용한다.

## 상담 메모리 엔진 (Always-on) 전역 원칙
- 이 규칙은 금융 관련 질의(시장/뉴스/실적/기업/섹터/포트폴리오/매수·매도/투자 감정 표현)에 기본 적용한다.
- 답변 초안 작성 전에 아래 명령으로 개인 메모리 컨텍스트를 먼저 준비한다(기본: ingest 포함).
  - `python3 scripts/counsel_memory_cli.py prepare-turn --user-text "<사용자 최신 발화>" --extractor-mode hybrid --format md`
- `prepare-turn` 실행이 실패하면 아래 순서로 복구 후 1회 재시도한다.
  1. `python3 scripts/counsel_memory_cli.py init`
  2. 동일 `prepare-turn` 명령 재실행
- 사용자가 심리/감정(예: 불안, 억울, 답답, 스트레스)을 표현한 턴은 메모리 반영 여부를 반드시 확인한다.
  - 필요 시 `ingest-turn --dry-run`으로 후보를 점검하고, 누락 시 `ingest-turn`으로 보강한다.
- 기본 추출 모드는 `hybrid`(문맥/의도 패턴 + 키워드 fallback)이며, 디버깅 시에만 `instruction` 또는 `keyword` 단독 모드를 사용한다.
- 상담형 답변 후에는 필요 시 `portfolio_cli.py log-counsel`로 의사결정 로그를 남겨 다음 상담 품질을 높인다.

## 차트 가독성 원칙
- `scripts/portfolio_cli.py chart`로 생성하는 성과 차트는 기본적으로 **좌상단 범례(legend)를 쓰지 않고**, 각 선의 **오른쪽 끝(end-of-line)에 자산 이름 라벨**을 붙인다.
- 라벨은 **흰색 텍스트**를 사용하고, 라벨 박스 배경색은 **해당 선 색상**과 일치시킨다.
- 라벨이 겹치지 않도록 자동 위치 보정(세로 오프셋)을 적용한다.
- 엔드 라벨 표기 형식은 `자산명 | 수익률%`로 하고, 수익률은 소수점 둘째 자리까지 표시한다.
- Y축 범위는 **우측 끝 라벨 값만이 아니라 전체 시계열 고점/저점 + 라벨 보정값**을 함께 반영해 자동 확장한다.
- 차트 PNG 저장 시 `bbox_inches=\"tight\"`와 충분한 패딩을 사용해 상하 라벨/선 잘림을 방지한다.
- `chart` 실행 시 성과 스탯 테이블 PNG를 기본적으로 함께 생성한다.
  - Beta 계산 기준은 기본 `SPY`를 사용한다.
  - 사용자가 요청하면 `^KS11` 등 다른 베타 기준 티커로 변경할 수 있어야 한다.
  - 컬럼: `자산명, Cumulative Return, CAGR, Max Drawdown, Volatility, Sharpe, Sortino, Kelly, Ulcer Index, UPI, Beta`

## 최신 정보 조회 원칙
- 최신 정보를 검색할 때는 아래 FEED들을 모두 함께 사용한다.
- 텔레그램 3개 피드(금융 속보 FEED, 통합 CSV): `https://rss.app/feeds/_8HzGbLlZYpznFQ9I.csv`
  - 텔레그램 피드는 속도가 더 빠르지만 에러가 더 잘 날 수 있다.
- 텔레그램 원본 피드(직접 탐색):
  - `https://t.me/s/WalterBloomberg`
  - `https://t.me/s/FinancialJuice`
  - `https://t.me/firstsquaw`
- 정규 언론 FEED: `https://rss.app/feeds/_hc8HiU0HyBWHfWoM.csv`
- 사용자가 뉴스 업데이트를 요청하면 `SKILLs/NewsRequest.md`를 참조한다.
- 사용자가 시장의 현재 상황에 대 분석/리포트를 요청하면 `SKILLs/MarketAnalysis.md`를 참조한다.
- 사용자가 거시경제 분한석/전망 보고서를 요청하면 `SKILLs/MacroEconomics.md`를 참조한다.
- 사용자가 기업 실적(earnings)을 요청하면 `SKILLs/Earnings.md`를 참조한다.
- 사용자가 기업 종합 분석/투자 리포트/기업 비교/밸류에이션을 요청하면 `SKILLs/CompanyAnalysis/SKILL.md`를 참조한다.
- 사용자가 산업/섹터 분석(섹터 리포트, 섹터 비교, 섹터 로테이션, 섹터 전망)을 요청하면 `SKILLs/SectorAnalysis/SKILL.md`를 참조한다.
- 사용자가 포트폴리오 상담(자산 배분, 섹터 배분, 리밸런싱, 리스크 관리, 라이프사이클 계획)을 요청하면 `SKILLs/PortfolioCounseling/SKILL.md`를 참조한다.
- 사용자가 `나스닥 옵션 분석`(QQQ 옵션체인/QQQ 옵션 리포트)을 요청하면 `SKILLs/NasdaqOptionAnalysis/SKILL.md`를 참조한다.
  - 이 스킬은 `QQQ`만 사용한다.
  - 실행은 **요청 시 1회 실행**이 원칙이며 주기 루프를 사용하지 않는다.
  - 결과물은 기본적으로 `reports/` 경로에 `HTML`로 저장한다. (필요 시 PNG 보조 출력 가능)
- 단, **기업분석(기업 종합 분석/투자 리포트/기업 비교/밸류에이션)** 요청은 FEED를 기본적으로 사용하지 않는다.
  - 기업분석 기본 소스: `yfinance + 웹 검색(고신뢰 출처)`
  - FEED는 사용자가 `속보/실시간 업데이트`를 명시적으로 요구한 경우에만 사용한다.
- **섹터분석(섹터 리포트/섹터 비교/섹터 로테이션/섹터 전망)도 기업분석과 동일하게 FEED를 기본적으로 사용하지 않는다.**
  - 섹터분석 기본 소스: `yfinance + 웹 검색(고신뢰 출처)`
  - 섹터분석의 웹 검색 출처 우선순위:
    1. 최고 신뢰도: `WSJ`, `FT`, `Bloomberg`
    2. 2차 신뢰도: `MarketWatch`, `Barron's`, `Seeking Alpha`, `FactSet`, `Benzinga`
  - FEED는 사용자가 `속보/실시간 업데이트`를 **명시적으로 요구한 경우에만** 사용한다.
  - 섹터분석 출력에서는 정량지표 외에 뉴스/정책/수급/내러티브 분석 비중을 반드시 포함한다.
- **포트폴리오 상담(자산 배분/섹터 배분/리밸런싱/리스크 관리)도 기업/섹터 분석과 동일하게 FEED를 기본적으로 사용하지 않는다.**
  - 포트폴리오 상담 기본 소스: `yfinance + 웹 검색(고신뢰 출처)`
  - 자산/섹터 배분 최신 정보 취득 시 웹 검색 출처 우선순위는 섹터분석 규칙(`WSJ/FT/Bloomberg` 우선)을 준용한다.
  - 포트폴리오 내 종목 심층 확인은 기업분석의 고신뢰 소스 원칙을 준용한다.
  - FEED는 사용자가 `속보/실시간 업데이트`를 **명시적으로 요구한 경우에만** 사용한다.
  - 출력에서는 정량지표 외 행동편향/목표/라이프사이클 맥락을 반드시 포함한다.

## 외부 세계 메모리 로그 원칙 (중기 템포)
- 사용자의 개인 로그(심리/가치관)와 별도로, **외부 세계 상태 로그**를 누적한다.
- 목적은 속보 요약이 아니라 **요즘 시장 동향/지속 이슈**의 기억 축적이다.
- 기본 저장 경로: `portfolio/world_issue_log.jsonl`
- 기본 도구: `scripts/world_memory_cli.py`
- 로그에 반드시 포함:
  - `as_of`(KST 타임스탬프)
  - `category`: `stock_bond`, `geopolitics`, `emerging`
  - `region`: `US`, `KR`, `GLOBAL`
  - `importance`: `high|medium|low`
  - `sources`(매체명/URL/게시시각)
- 외부 세계 메모리 구축 시에는 **FEED를 기본 사용하지 않는다.**
  - 기본 소스: `yfinance + 고신뢰 웹 검색`
  - 영어권 우선 출처: `WSJ`, `FT`, `Bloomberg` (필요 시 2차 신뢰도 확장)
  - 한국 소스 보강: `연합인포맥스(https://news.einfomax.co.kr)`
  - FEED는 사용자가 `속보/실시간`을 명시한 경우에만 추가한다.
- **월드메모리 보고서 모드**는 사용자가 `월드메모리 보고서`(또는 동등한 명시 표현)를 요청한 경우에만 발동한다.
  - 이 경우 `world_issue_log`를 우선 조회하고 부족분만 웹 검색으로 보강한다.
  - 출력은 `미국/한국/글로벌 주식·채권`, `글로벌 정치`, `비지배 관심 이슈`를 분리한다.
- **시장 분석 모드**(예: “요즘 시장 동향 알려줘”, “지금 시장 어때”)에서는 `SKILLs/MarketAnalysis.md`를 기준으로 답변한다.
  - 이때 월드메모리 **별도 보고서**는 작성하지 않는다.
  - 필요하면 `world_issue_log`는 내부 참고용으로만 활용하고, 결과는 시장 분석 본문에 통합한다.
- 포트폴리오 상담 시 필요하면 `world_issue_log`를 반영해 리밸런싱/리스크 코멘트를 보강한다.
- 포트폴리오 상담 질문이 `유지할까/계속 투자할까/줄여야 할까/빼야 할까/버틸까` 류이면,
  - 답변 전에 `python3 scripts/world_memory_cli.py list --days 21 --format md`를 먼저 실행해 최근 이슈를 확인한다.
  - 답변 초반에 `as of (KST)` 기준 시각과 반영한 핵심 이슈 1~3개를 명시한다.

## 캘린더(어닝/경제 이벤트) 사용 원칙
- **어닝 캘린더(earnings calendar)** 및 **경제 이벤트 캘린더(economic events calendar)**는 기본적으로 `yfinance.Calendars`를 사용한다.
- 조회/내보내기는 프로젝트의 CLI를 사용한다: `scripts/calendar_cli.py`
- **시간 표기는 항상 UTC+9(서울, `Asia/Seoul`) 기준으로 출력한다.** (옵션으로 변경하지 않는다, 현지 시간을 표시하지 않는다.)
- EVENT 이름은 원문과 함께 괄호() 속에 한국어 번역을 병기한다.

### 실행 예시
- 어닝 캘린더(Markdown): `python3 scripts/calendar_cli.py earnings --start 2026-01-23 --days 14 --limit 50 --format md`
- 경제 이벤트 캘린더(Markdown): `python3 scripts/calendar_cli.py economic --start 2026-01-23 --days 14 --limit 50 --format md`
- 캘린더 임포트용(ICS): `python3 scripts/calendar_cli.py earnings --start 2026-01-23 --days 14 --format ics --out earnings.ics`
- 자세한 옵션/예시는 `scripts/README.md` 참고

## 긴급 안보위기 특별 인스트럭션
- 매우 심각한 안보위기(시장에 큰 영향) 또는 사용자가 안보 관련 질의를 한 경우, 아래 지침에 따라 **추가 부록 보고서**를 제공한다.
- X의 OSINT 최신 정보가 담긴 CSV FEED에 접속해 분석/보고서를 작성한다: `https://rss.app/feeds/_ahZsPeKSyY4dqkqw.csv`
- 출력은 한국어로 작성한다.
- 보고서는 Markdown/List/Table을 적극적으로 사용한다.
- 가능하면 시간을 정확히 표기한다(KST). 시간이 여러 개인 경우 최신 순으로 정렬한다.
- 긴 문장보다 짧고 간단한 문장을 여러 개 사용한다.
- 가장 최신 소식과 가장 치명적인 소식에 가중치를 둔다.
- 최신 소식을 제공하되 전체 맥락을 이해할 수 있도록 요약한다.
- 사용자가 추가 맥락을 요구할 경우에만 웹 검색을 실시한다.
  - 블로그/유튜브 등 신빙성이 낮은 출처는 제외한다.
  - 한국에서 발생한 사건이 아닌 경우 한국 언론 출처는 제외한다.
  - CNN, Bloomberg, WSJ, BBC, Guardian, Washington Post, Nikkei Asia 등 서방권의 신뢰도 높은 언론만 인용한다.

## 응답 마무리 원칙
- 시장/섹터/거시/뉴스/실적/포트폴리오 상담 등 **분석형 답변은 마지막 섹션을 반드시 `결론`으로 마무리**한다.
  - 본문에서 정보를 충분히 제시한 뒤, 최종 행동 관점에서 핵심 판단(현재 레짐/핵심 리스크/우선 체크포인트)을 3~7줄로 요약한다.
- 시장/섹터/거시/뉴스/실적/포트폴리오 상담 등 분석형 답변의 마지막에는, 사용자가 원하면 **장문 보고서를 파일로 생성**할 수 있다는 제안을 포함한다.
- 이 마무리 제안은 `SKILLs/CompanyAnalysis/SKILL.md`를 참고해 작성한다고 명시한다.
- 제안 문구에는 아래 요소를 포함한다.
  - 파일 생성 위치 예시(예: `reports/` 경로)
  - 포함 항목 예시(사업 구조, 실적, 밸류에이션, 리스크, 투자 시나리오)
  - 사용자가 즉시 진행 여부를 답할 수 있는 짧은 콜투액션
