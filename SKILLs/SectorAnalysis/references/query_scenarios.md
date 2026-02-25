# 사용자 질의 시나리오 맵 (산업/섹터 분석)

목표:
- 섹터 관련 질문을 빠르게 인텐트로 분류한다.
- 인텐트별 기본 출력 형식과 최소 데이터 요건을 고정한다.
- 모호한 요청도 가정 기반 1차 답변으로 즉시 대응한다.

## 1) 빠른 판단형

| 사용자 질문 패턴 | 분류 | 기본 출력 | 최소 데이터 |
| --- | --- | --- | --- |
| "지금 가장 강한 섹터 뭐야?" | Sector Pulse | Flash | 섹터 ETF 수익률, SPY 대비 상대강도 |
| "방어주로 피신 중이야?" | Rotation Check | 로테이션 비교표 | XLY/XLP, XLK/XLU 비율 |
| "이번 주 섹터 포지션 어떻게?" | Weekly Rotation | 주간 대시보드 | 1W 수익률, 거래량, 촉매 |
| "한 줄로만 결론" | Quick Thesis | 3불릿 결론 | 상대강도 + 촉매 1~2개 |

## 2) 증권사 리포트형

| 사용자 질문 패턴 | 분류 | 기본 출력 | 최소 데이터 |
| --- | --- | --- | --- |
| "증권사 섹터 보고서처럼" | Broker-style Sector Note | KR Broker Sector PDF-style | 의견, Top picks, 드라이버 |
| "PDF 리포트 포맷으로 정리" | Broker-style Sector Note | KR Broker Sector PDF-style | 표지형 메타 + 본문 |
| "Issue note 형식으로" | Broker-style Sector Note | KR Broker Sector PDF-style | Why now + 시나리오 |
| "산업 섹터 리포트 써줘" | Full Sector Report | KR Broker Sector PDF-style | 성과/밸류/실적/리스크 |

## 3) 실적 시즌형

| 사용자 질문 패턴 | 분류 | 기본 출력 | 최소 데이터 |
| --- | --- | --- | --- |
| "실적 시즌에서 어느 섹터가 좋았어?" | Earnings Breadth | 실적 스코어보드 | EPS/매출 성장, Beat 비율 |
| "가이던스 기준으로 섹터 정리" | Guidance Map | 상향/하향 지도 | 가이던스 변화, 리비전 |
| "팩트셋 스타일로 숫자만" | FactSet-style | 정량 중심 표 | 성장률/서프라이즈/밸류 |
| "이번 분기 승자·패자만" | Winners/Losers | 상/하위 섹터 리스트 | 섹터별 핵심 지표 |

## 4) 비교형

| 사용자 질문 패턴 | 분류 | 기본 출력 | 최소 데이터 |
| --- | --- | --- | --- |
| "기술 vs 에너지 뭐가 유리?" | Sector vs Sector | 2섹터 비교표 | 수익률/밸류/모멘텀 |
| "미국/유럽 같은 섹터 비교" | Cross-region Sector | 지역간 비교표 | 지역 ETF/통화/정책 변수 |
| "반도체 vs 소프트웨어" | Industry vs Industry | 산업 비교표 | 성장/마진/밸류/촉매 |
| "섹터 내 대체 종목 추천" | Intra-sector Picks | 후보 3~5개 | 스크리너 + 재무/밸류 |

## 5) 리스크형

| 사용자 질문 패턴 | 분류 | 기본 출력 | 최소 데이터 |
| --- | --- | --- | --- |
| "어느 섹터가 제일 위험해?" | Risk Ranking | 리스크 랭킹 | 변동성/낙폭/부채 민감도 |
| "금리 오르면 타격 큰 섹터?" | Macro Sensitivity | 민감도 분석 | 금리/달러/원자재 연동 |
| "규제 리스크 큰 산업?" | Regulatory Risk | 규제 이벤트 맵 | 정책 뉴스 + 산업 구조 |
| "충격 시 방어 섹터는?" | Stress Playbook | 시나리오 대응표 | 과거 유사국면 성과 |

## 6) 초보자형

| 사용자 질문 패턴 | 분류 | 기본 출력 | 최소 데이터 |
| --- | --- | --- | --- |
| "섹터가 뭔지부터 알려줘" | Beginner Explain | 3단계 쉬운 설명 | 기본 정의(Investopedia) |
| "표가 어려워" | Simplified View | 3~5행 미니표 | 핵심 지표 단순화 |
| "왜 섹터 로테이션이 생겨?" | Concept Explain | 원리 + 사례 | 금리/경기/밸류 연결 |
| "초등학생도 이해하게" | Re-teach | 쉬운 비유형 설명 | 핵심 개념 재구성 |

## 7) 모호한 질문 대응 규칙
- 섹터 미지정: 미국 11개 섹터 전체를 기본 분석.
- 기간 미지정: `1M + 3M + YTD` 기본 적용.
- 출력 깊이 미지정: `Flash`부터 시작.
- 스타일 미지정: `Balanced Sector Brief`.
- `리포트/PDF/증권사` 키워드 존재: `KR Broker Sector PDF-style` 우선.
