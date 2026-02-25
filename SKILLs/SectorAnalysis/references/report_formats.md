# 산업/섹터 분석 리포트 포맷 리서치 (실행 규칙)

원칙:
- 문장/표현 복제가 아니라 구조를 모사한다.
- 사용자가 `섹터 리포트/PDF/증권사 형식`을 요청하면 `KR Broker Sector PDF-style`을 기본 적용한다.

## 1) KR Broker Sector PDF-style (기본 리포트 포맷)
추천 상황:
- "증권사 섹터 보고서처럼"
- "Issue note 형식으로"
- "PDF로 내보내기 좋은 구조"

필수 섹션(순서 고정):
1. 표지형 1페이지
   - 리포트 헤더(유형, as-of KST)
   - 섹터 헤더(섹터명, 핵심 테제)
   - 좌측 메타 패널(섹터 의견, Top Picks, 성과)
   - 우측 핵심 드라이버 3개 + Why now
2. 산업 근거 상세
   - 공급/수요/가격/재고/CAPA
3. 비교 차트/표 패널
   - 하위산업, 대표 기업, 상대강도
4. 수급/정책/내러티브 분석
5. 시나리오(Baseline/Upside/Downside)
6. 리스크/체크포인트
7. 결론
8. 컴플라이언스/한계

참고:
- 내부 스타일 기준 `korean_broker_pdf_style.md`
- 샘플 레이아웃 `/Users/jundochang/Downloads/20260223_industry_248876000.pdf`

## 2) Balanced Sector Brief
추천 상황:
- 스타일 지정이 없고 균형형 보고가 필요한 경우

필수 섹션:
1. 한 줄 결론 + as-of
2. 섹터 성과/상대강도
3. 핵심 드라이버 3~5개
4. 밸류/실적 모멘텀
5. 리스크/촉매
6. 결론

## 3) Bloomberg-style Sector Outlook
추천 상황:
- "아웃룩 리포트처럼"

필수 섹션:
1. Key Calls 3개
2. Sector Dashboard
3. What Changed Since Last Update
4. 6~12개월 전망(조건부)
5. 유리/불리한 하위산업

## 4) WSJ-style Quick Thesis Note
추천 상황:
- "짧고 날카롭게"

필수 섹션:
1. Thesis
2. Why Now
3. What Market May Miss
4. 반대 논리
5. 트리거 기반 결론

## 5) FT Lex-style Valuation Note
추천 상황:
- "밸류 중심/역발상 관점"

필수 섹션:
1. 핵심 쟁점(Valuation First)
2. 멀티플-이익 사이클 점검
3. 대차대조표/자본배분
4. 컨센서스 vs Variant View
5. 결론(리레이팅/디레이팅)

## 6) FactSet-style Earnings Scoreboard
추천 상황:
- "실적 시즌 숫자 비교"

필수 섹션:
1. 섹터별 EPS/매출 성장률
2. Beat/Miss 비율
3. 가이던스 상향/하향 비율
4. Forward 밸류
5. 리비전 추세
