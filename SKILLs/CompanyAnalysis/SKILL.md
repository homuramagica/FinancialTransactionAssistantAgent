---
name: company-analysis
description: yfinance와 웹 검색(고신뢰 출처) 기반으로 상장/비상장 기업 분석, 투자 리포트, 밸류에이션, 피어 비교, 실적 프리뷰/리뷰, 리스크 진단을 수행하는 스킬. 사용자가 기업 종합 분석, 투자 아이디어 검토, 리서치 리포트 작성, 기업 비교, 실적 영향 분석, 초보자용 기업 설명을 요청할 때 사용한다.
---

# Company Analysis (기업 분석 메가 스킬)

## 1) 목표
- 기업 분석 요청을 빠르게 분류한다.
- `yfinance`를 기본 데이터 소스로 사용한다.
- 최신 이슈는 고신뢰 웹 검색으로 확인한다.
- 최신 이슈 누락 방지를 위해 `기업 검색`과 `섹터 검색`을 분리 수행한다.
- 사용자가 원할 때 **국내 증권사 PDF 스타일**(표지형 1페이지 + 본문 + 부록)로 작성한다.
- 결과는 `Flash` 또는 `Broker PDF Report`로 출력한다.

## 2) 절대 원칙
- MCP 연동 시나리오는 사용하지 않는다.
- 데이터 소스는 `yfinance + 고신뢰 웹 검색`으로 고정한다.
- 기업분석 작성 전 반드시 `기업 검색(회사/티커 중심)`과 `섹터 검색(산업/정책/수급 중심)`을 각각 수행한다.
- 기업 이슈와 섹터 이슈는 분리 기록 후 교차 검증해 본문/결론에 통합한다.
- 기업분석 요청에서는 FEED를 기본적으로 사용하지 않는다.
- FEED는 사용자가 `속보/실시간 업데이트`를 명시한 경우에만 보조적으로 사용한다.
- 실행 전 Python/yfinance 설치 여부를 먼저 확인한다.
- 설치 필요 시 사용자에게 설치 진행 의사를 먼저 묻는다.
- 개념 설명 요청이면 `Investopedia`를 먼저 확인한다.
- 초보자/기초 설명 요청이면 `SKILLs/Newbie.md`를 동시 적용한다.
- 샘플 보고서의 **문장 복사 금지**, 구조/정보 계층만 모사한다.

## 3) 출력 모드 라우팅
기본은 아래 2가지 모드다.

| 모드 | 트리거 | 기본 산출물 |
| --- | --- | --- |
| Flash Layer | 빠른 질문/짧은 판단 요청 | 1페이지 요약 |
| Broker PDF Report | `리포트/보고서/PDF/증권사 형식/애널리스트 형식` 요청 | 표지형 1페이지 + 본문 + 결론 + 컴플라이언스 |

`Broker PDF Report` 모드에서는 `references/korean_broker_pdf_style.md`를 우선 적용한다.

## 4) 인텐트 라우터
아래 중 하나로 먼저 분류한다.

| 인텐트 | 사용자 표현 예시 | 기본 산출물 |
| --- | --- | --- |
| Quick Brief | "애플 지금 살만해?" | Flash |
| Full Initiation | "테슬라 심층 리포트 써줘" | Broker PDF Report |
| Broker-style Note | "증권사 보고서처럼 써줘" | Broker PDF Report |
| Earnings Preview | "실적 전에 체크포인트" | 프리뷰 템플릿 |
| Earnings Review | "실적 반영해서 업데이트" | 리뷰 템플릿 |
| Valuation | "적정가 계산해줘" | 멀티플 + 시나리오 |
| Peer Comparison | "코카콜라 vs 펩시" | 피어 비교표 + 결론 |
| Risk Audit | "가장 큰 리스크 뭐야?" | Risk Radar |
| ESG Analysis | "ESG 관점으로 분석" | ESG Scorecard |
| Beginner Explain | "초보인데 쉽게 설명" | Newbie 템플릿 |

## 5) 데이터 소스 우선순위
1. `yfinance` (`reference/yfinance_reference.md`)
2. 웹 검색(필요 시)
   - 우선: SEC, FINRA, CFA Institute, Morningstar, Reuters, Bloomberg, FT, WSJ, Investopedia
   - 추가: 주요 증권사 리서치 노트, 공매도 리포트(접근 가능한 범위)
   - 원칙: `주장`과 `근거`를 분리하고 반대 근거를 병기
   - 제외: 블로그/유튜브/검증 불가 커뮤니티
3. 프로젝트 FEED (속보 요청 시에만)
   - `https://rss.app/feeds/_8HzGbLlZYpznFQ9I.csv`
   - `https://rss.app/feeds/_hc8HiU0HyBWHfWoM.csv`
   - `https://t.me/s/WalterBloomberg`
   - `https://t.me/s/FinancialJuice`
   - `https://t.me/firstsquaw`

## 6) 표준 워크플로우
1. 요청 목적 확정
   - 투자판단 보조인지 학습용인지 구분한다.
2. 범위 확정
   - 티커/시장/기간/깊이(요약 vs 심층)를 확정한다.
3. yfinance 팩 수집
   - `info`, `history`, `financials`, `estimates`, `revisions`, `recommendations`, `news`.
4. 기업 최신 이슈 검색
   - 회사명/티커/핵심 제품/실적/가이던스/소송·규제 키워드로 고신뢰 웹 검색을 수행한다.
   - 기업 고유 이슈(실적, 제품, 경영진, 공시, 개별 규제)를 우선 수집한다.
5. 섹터/산업 맥락 검색
   - 동일 기간 기준으로 섹터 수급, 정책 변화, 업황 사이클, 피어 멀티플 변화를 검색한다.
   - 섹터 공통 변수(금리/원자재/정책/공급망)가 해당 기업에 미치는 경로를 정리한다.
6. 최신 촉매 통합 검증
   - 기업 검색/섹터 검색 결과를 분리 표기한 뒤, 중복·상충 이슈를 교차 검증한다.
   - 속보 요청일 때만 FEED 5종을 추가 호출한다.
7. 분석
   - 비즈니스/성장/수익성/현금흐름/밸류/리스크/촉매를 분리한다.
   - 정량 60 + 정성 40을 기본으로 적용한다.
8. 시나리오화
   - `Baseline/Upside/Downside`와 무효화 조건을 명시한다.
9. 출력
   - Flash 또는 Broker PDF 템플릿으로 렌더링한다.
10. 마무리
   - 마지막 섹션을 반드시 `결론`으로 작성한다.
   - 응답 말미에 파일 출력 제안을 붙인다.

## 7) Broker PDF Report 강제 구조
`Broker PDF Report` 모드에서는 아래 순서를 고정한다.

1. 표지형 1페이지
   - 리포트 헤더(리포트 유형, as-of KST)
   - 종목 헤더(회사명/티커/핵심 테제)
   - 좌측 메타 패널(투자의견, 목표주가, 현재가, 상승여력, 수익률)
   - 우측 핵심 투자포인트 3~5개
   - 하단 실적 스냅샷 표(연도별)
2. 본문
   - `투자포인트 상세`(번호형)
   - `실적 전망`(연간 + 분기 표)
   - `밸류에이션`(Bear/Base/Bull)
   - `촉매/이벤트`
   - `리스크/반증조건`
3. 결론
   - 현재 레짐, 핵심 리스크, 우선 체크포인트를 3~7줄 요약
4. 부록
   - 차트 패널(가능한 범위)
   - 컴플라이언스/한계

상세 규칙은 `references/korean_broker_pdf_style.md`를 따른다.

## 8) yfinance 기본 수집 항목
- 기업 개요: `Ticker.info`
- 가격/반응: `Ticker.history`
- 실적 일정: `Ticker.calendar`, `Ticker.get_earnings_dates`
- 실적 히스토리: `Ticker.get_earnings_history`
- 컨센서스: `get_earnings_estimate`, `get_revenue_estimate`
- 리비전: `get_eps_trend`, `get_eps_revisions`, `get_growth_estimates`
- 재무제표: `get_income_stmt`, `quarterly_income_stmt`, `get_balance_sheet`, `get_cashflow`
- 애널리스트 변화: `get_recommendations`, `get_recommendations_summary`, `get_upgrades_downgrades`
- 보조 정보: `get_news`, `get_insider_transactions`, `get_sustainability`

## 9) 품질 게이트 (제출 전 체크)
- 숫자마다 출처가 있는가
- `as of (KST)` 시각이 있는가
- 기업 검색/섹터 검색 결과가 모두 본문(촉매/리스크/결론)에 반영됐는가
- 결론/근거/리스크가 모순되지 않는가
- 상승/하락 양방향 시나리오가 있는가
- 데이터 공백/가정이 명시됐는가
- 투자의견 변화/공매도 주장에 대한 반론이 포함됐는가
- 최종 섹션 제목이 `결론`인가

## 10) Citation 규칙
- yfinance 수치: `(yfinance: method_or_table, date)`
- 뉴스/기사: `[매체명](URL)`
- 규정/공식 문서: `[기관명](URL)`
- 추정치: `가정` 또는 `추정` 라벨을 반드시 표시

## 11) 능동 대응 규칙
- 질문이 모호해도 가정 2~3개를 명시하고 1차 분석을 제시한다.
- 티커가 없으면 회사명 후보를 제시하고 확인 질문 1개만 한다.
- 사용자가 "더 쉽게"라고 하면 Newbie 모드로 전환한다.
- 사용자가 "업데이트"라고 하면 웹 검색을 재호출한다.
- 사용자가 "속보/실시간"을 함께 요구하면 FEED를 추가한다.

## 12) 안전/한계
- 투자 자문이 아닌 정보 제공 목적임을 명시한다.
- yfinance/웹 검색/뉴스 피드는 지연/누락 가능성이 있음을 명시한다.
- 데이터 부재 시 추정으로 덮지 말고 `확인 불가`로 표시한다.

## 13) 참조 문서
- 형식별 상세 구조: `references/report_formats.md`
- 질의 패턴별 대응: `references/query_scenarios.md`
- 바로 쓰는 템플릿: `references/output_templates.md`
- 증권사 PDF 구조: `references/korean_broker_pdf_style.md`
