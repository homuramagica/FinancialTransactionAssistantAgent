# 기업 분석/투자 보고서 포맷 리서치 (실행 규칙)

원칙:
- 문장/표현을 복제하지 않고, 구조와 정보 계층만 모사한다.
- 사용자가 `리포트/보고서/PDF/증권사 형식`을 요청하면 `KR Broker PDF-style`을 우선 적용한다.

## 1) KR Broker PDF-style (기본 리포트 포맷)
추천 상황:
- "증권사 보고서처럼 써줘"
- "PDF로 뽑기 좋은 형식으로"
- "애널리스트 리포트 스타일"

필수 섹션(순서 고정):
1. 표지형 1페이지
   - 리포트 헤더(as-of KST 포함)
   - 종목 헤더(회사명/티커/한 줄 테제)
   - 좌측 메타 패널(투자의견/목표가/현재가/상승여력/수익률)
   - 우측 핵심 투자포인트(3~5개)
   - 하단 실적 스냅샷 표(2024A~2027F)
2. 투자포인트 상세(번호형)
3. 실적 전망(연간/분기)
4. 밸류에이션(Bear/Base/Bull)
5. 촉매와 일정
6. 리스크/무효화 조건
7. 결론
8. 컴플라이언스/한계

참고:
- 내부 스타일 기준 `korean_broker_pdf_style.md`
- 샘플 레이아웃 `/Users/jundochang/Downloads/20260225_company_127775000.pdf`

## 2) Sell-side Equity Research Update (Global)
추천 상황:
- "목표주가/투자의견 포함 리포트"
- "매수/중립/매도 판단 근거"

필수 섹션:
1. 한 줄 결론(투자의견/목표가/상승여력)
2. 투자포인트 3개
3. 실적/컨센서스 변화
4. 밸류에이션(멀티플 + 보조 DCF)
5. 핵심 리스크
6. 디스클로저

## 3) 10-K/10-Q 기반 장기 펀더멘털 리포트
추천 상황:
- "본질가치/지속 가능성 중심"
- "리스크팩터와 MD&A 중심 정리"

필수 섹션:
1. Business 개요
2. Risk Factors
3. MD&A
4. 재무제표 핵심 라인/추세
5. 회계/비경상 항목 점검
6. 장기 시나리오와 트리거

## 4) Earnings Preview / Earnings Review
추천 상황:
- 실적 발표 전 체크리스트
- 발표 후 변화점 업데이트

필수 섹션:
1. 컨센서스(매출/EPS)와 기대치
2. 핵심 KPI 체크포인트
3. 가이던스 상향/하향 가능성
4. 발표 직후 주가 반응
5. 다음 분기 촉매

## 5) Quality/Moat 중심 리포트
추천 상황:
- "좋은 기업인지(해자/경쟁우위) 중심"

필수 섹션:
1. Economic Moat(없음/좁음/넓음)
2. Fair Value 범위
3. Uncertainty(낮음/중간/높음)
4. 장기 경쟁력 드라이버
5. 훼손 요인

## 6) Investment Committee Memo (VC/PE 스타일)
추천 상황:
- "투자위원회 제출용"

필수 섹션:
1. Team
2. Market
3. Product
4. Business Model
5. Investment Thesis
6. Risks
7. Decision / Conditions

## 7) 개념 설명형(초보자 대응)
추천 상황:
- "PER/EPS/DCF가 뭐야?"
- "기초부터 쉽게 설명"

필수 섹션:
1. 개념 1문장 정의
2. 숫자 해석 예시
3. 자주 틀리는 포인트
4. 한 줄 요약

## 8) ESG Due Diligence Format
추천 상황:
- "ESG 리스크를 투자 판단에 반영"

필수 섹션:
1. ESG 점수표(E/S/G/Controversy)
2. Governance 점검
3. Social 논란/규제 이벤트
4. Environment 노출 수준
5. 리스크 프리미엄 반영
