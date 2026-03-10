---
name: sector-analysis
description: yfinance와 고신뢰 웹 검색 기반으로 산업/섹터 분석, 섹터 로테이션, 상대강도, 밸류에이션, 실적 모멘텀, 촉매/리스크를 통합해 투자 의사결정을 돕는 스킬. 사용자가 섹터 분석 보고서, 산업 전망, 섹터 비교, 섹터 내 종목 발굴, 섹터 업데이트를 요청할 때 사용한다.
---

# Sector Analysis (산업/섹터 분석 메가 스킬)

## 1) 목표
- 산업/섹터 질문을 빠르게 분류한다.
- `yfinance` 기반 정량 데이터로 분석의 뼈대를 만든다.
- 뉴스/정책/수급/내러티브를 정량 지표와 연결한다.
- 사용자가 원할 때 **국내 증권사 섹터 PDF 스타일**로 작성한다.
- 결과를 `Flash` 또는 `Broker PDF Report`로 출력한다.

## 2) 절대 원칙
- MCP 연동 시나리오는 사용하지 않는다.
- 데이터 소스는 기본적으로 `yfinance + FEED + 고신뢰 웹 검색`으로 사용한다.
- 관련성이 높다고 판단되면 `python3 scripts/world_memory_cli.py list --days 21 --format md` 또는 `--days 30`을 먼저 조회해 현재 진행 중인 중기 스토리를 확인한다.
- 월드 메모리는 배경 맥락용이며, 별도 섹션을 강제하지 않고 관련성이 높을 때만 본문에 자연스럽게 통합한다.
- 실행 전 Python/yfinance 설치 여부를 먼저 확인한다.
- 설치 필요 시 사용자에게 설치 진행 의사를 먼저 묻는다.
- 용어/개념 설명 요청이면 `Investopedia`를 먼저 확인한다.
- 초보자/기초 설명 요청이면 `SKILLs/Newbie.md`를 동시 적용한다.
- 섹터 분석도 FEED를 기본 호출한다.
- FEED는 최신 흐름 탐지용으로 사용하고, 저장/결론 반영 전에는 고신뢰 웹 검색과 공식 자료로 재검증한다.
- 시간 표기는 항상 `KST(Asia/Seoul)`로 맞춘다.
- 결론은 단정 대신 `조건 + 트리거` 기반으로 작성한다.
- 샘플 PDF의 문장을 복사하지 않고 구조만 모사한다.

## 3) 출력 모드 라우팅

| 모드 | 트리거 | 기본 산출물 |
| --- | --- | --- |
| Flash Layer | 빠른 섹터 질문 | 1페이지 스냅샷 |
| Broker PDF Report | `섹터 리포트/PDF/증권사 형식/애널리스트 형식` 요청 | 표지형 1페이지 + 본문 + 결론 + 컴플라이언스 |

`Broker PDF Report` 모드에서는 `references/korean_broker_pdf_style.md`를 우선 적용한다.

## 4) 인텐트 라우터
아래 중 하나로 먼저 분류한다.

| 인텐트 | 사용자 표현 예시 | 기본 산출물 |
| --- | --- | --- |
| Sector Pulse | "지금 어떤 섹터가 강해?" | Flash |
| Rotation Check | "방어주에서 경기민감주로 돌고 있나?" | 로테이션 표 |
| Industry Deep Dive | "반도체 산업 구조 분석해줘" | Broker PDF Report |
| Broker-style Sector Note | "증권사 섹터 보고서처럼 써줘" | Broker PDF Report |
| Sector vs Sector | "에너지 vs 기술 어디가 유리?" | 2섹터 비교 보고서 |
| Earnings Breadth | "이번 시즌 어느 섹터 실적이 좋았어?" | 실적 스코어보드 |
| Valuation Heatmap | "섹터별 밸류 싸고 비싼 곳?" | 밸류 히트맵 |
| Risk Stress Test | "헬스케어 리스크만" | 리스크 레이더 |
| Beginner Explain | "섹터 분석 쉽게 설명" | Newbie 템플릿 |

## 5) 데이터 소스 우선순위
1. `yfinance` (`reference/yfinance_reference.md`)
   - `Sector`, `Industry`, `Ticker`, `download`, `screen(EquityQuery)`
   - `get_growth_estimates`, `get_earnings_estimate`, `get_revenue_estimate`
   - `get_eps_trend`, `get_eps_revisions`
2. 웹 검색(필요 시)
   - 최고 신뢰도: Bloomberg, WSJ, FT
   - 2차 신뢰도: MarketWatch, Barron's, Seeking Alpha, FactSet, Benzinga
   - 필요 시 공식 문서: SEC, IMF/World Bank
   - 제외: 블로그/유튜브/검증 불가 커뮤니티
3. 프로젝트 FEED (기본 탐지 레이어)
   - `https://rss.app/feeds/_8HzGbLlZYpznFQ9I.csv`
   - `https://rss.app/feeds/_hc8HiU0HyBWHfWoM.csv`
   - `https://t.me/s/WalterBloomberg`
   - `https://t.me/s/FinancialJuice`
   - `https://t.me/firstsquaw`

## 6) 섹터/산업 기본 프레임
- 기본 시장: 미국(명시 없으면 US 기준)
- 기본 벤치마크: `SPY` (또는 `^SPX`)
- 기본 기간: `1M / 3M / YTD / 1Y`
- 기본 섹터 프록시 ETF:
  - `XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLK, XLU`

## 7) 표준 워크플로우
1. 목적 확정
   - 학습용/투자판단 보조/리밸런싱 목적을 구분한다.
2. 범위 확정
   - 지역, 섹터/산업 단위, 기간, 출력 깊이를 확정한다.
3. yfinance 팩 수집
   - 가격/수익률/변동성/최대낙폭
   - 성장/컨센서스/리비전
   - 구성 파악(`Sector.industries`, `screen`)
4. 중기 맥락 확인(조건부)
   - 섹터 로테이션, 정책 변화, 지정학, 금융여건이 실제로 섹터에 영향을 주는 구간이면 `world_issue_log`를 조회해 현재 스토리를 먼저 정리한다.
   - 월드 메모리는 내러티브 방향만 잡고, 실제 근거는 최신 웹 검색과 yfinance 데이터로 재확인한다.
5. 핵심 지표 계산
   - 상대강도(`Sector ETF / SPY`)
   - 성과(1M/3M/YTD/1Y)
   - 밸류(대표 종목군 멀티플)
   - 실적 모멘텀(EPS 상향-하향)
6. 촉매/뉴스 수집
   - WSJ/FT/Bloomberg 우선
   - 정책/규제/공급망/원자재/수요/수급 내러티브 연결
   - FEED 5종으로 최신 변화를 먼저 스캔하고, 중요 이슈는 정규 언론/공식 자료로 재검증
7. 시나리오화
   - `Baseline/Upside/Downside + 무효화 조건`
8. 출력
   - Flash 또는 Broker PDF 템플릿으로 렌더링
9. 마무리
   - 마지막 섹션을 반드시 `결론`으로 작성
   - 파일 출력 제안 문구 추가

## 8) Broker PDF Report 강제 구조
`Broker PDF Report` 모드에서는 아래 순서를 고정한다.

1. 표지형 1페이지
   - 리포트 헤더(유형, as-of KST)
   - 섹터 헤더(섹터명/한 줄 테제)
   - 좌측 메타 패널(섹터 의견, Top Picks, 성과)
   - 우측 핵심 드라이버 3개 + Why now
2. 본문
   - `산업 근거 상세`(공급/수요/가격/재고/CAPA)
   - `비교 차트/표`(하위산업/대표기업/상대강도)
   - `수급/정책/내러티브 분석`
   - `섹터 시나리오`(Baseline/Upside/Downside)
   - `리스크/체크포인트`
3. 결론
   - 현재 우위 섹터, 핵심 리스크, 우선 체크포인트를 3~7줄로 요약
4. 부록
   - 컴플라이언스/한계

상세 규칙은 `references/korean_broker_pdf_style.md`를 따른다.

## 9) 품질 게이트 (제출 전 체크)
- `as of (KST)` 시각이 있는가
- 핵심 숫자에 출처가 있는가
- 벤치마크 대비 상대성과 절대성과를 함께 제시했는가
- 상승/하락 양방향 시나리오가 있는가
- 데이터 공백/가정이 명시됐는가
- Why now 촉매가 포함됐는가
- 결론과 근거가 모순되지 않는가

## 10) Citation 규칙
- yfinance 수치: `(yfinance: method_or_table, date)`
- 뉴스/기사: `[매체명](URL)`
- 공식 문서: `[기관명](URL)`
- 추정치는 `가정` 또는 `추정` 라벨을 붙인다.

## 11) 능동 대응 규칙
- 질문이 모호해도 가정 2~3개를 명시한 1차 분석을 먼저 제시한다.
- 섹터 범주가 모호하면 후보 2~3개를 제시하고 확인 질문 1개만 한다.
- 사용자가 "더 쉽게"라고 하면 Newbie 모드로 전환한다.
- 사용자가 "업데이트"라고 하면 웹 검색을 재호출한다.
- 사용자가 "속보/실시간"을 함께 말하면 FEED 5종의 최신 항목 비중을 더 높게 둔다.

## 12) 안전/한계
- 투자 자문이 아닌 정보 제공 목적임을 명시한다.
- yfinance/뉴스/웹 데이터는 지연/누락 가능성이 있음을 명시한다.
- 확인 불가 데이터를 임의 추정으로 채우지 않는다.

## 13) 참조 문서
- 형식별 상세 구조: `references/report_formats.md`
- 질의 패턴별 대응: `references/query_scenarios.md`
- 바로 쓰는 템플릿: `references/output_templates.md`
- 증권사 PDF 구조: `references/korean_broker_pdf_style.md`
