# 2024년 8월 블랙 먼데이 -- 리서치 파일
**최초 작성**: 2026-04-18  
**증보 갱신**: 2026-04-26
**용도**: 집필 전 사실 확인 및 검증된 데이터 정리. 본문 집필 전에는 이 파일의 수치와 출처를 우선 확인한다.

---

## 0. 이번 재집필의 기준

- 서문(`00_preface`)과 프롤로그(`01_prologue`)는 이미 연재되어 잠금 상태로 둔다.
- 1장 이후 본문은 `/Writing/README.md`의 새 지침에 맞춰, 공식 자료와 시장 데이터가 장면 안에 자연스럽게 들어가도록 증보한다.
- 이 사건은 "경기침체가 시작된 위기"가 아니라 "낮은 변동성, 한쪽으로 쏠린 엔화 포지션, BOJ 커뮤니케이션, 약한 고용 지표가 겹친 급격한 포지션 청산"으로 본다.
- 단정이 위험한 부분은 본문에서 `추정된다`, `시장 참가자들은 그렇게 읽었다`, `공식 자료와는 다르게 당일 시장은 이렇게 해석했다`처럼 사실과 해석을 분리한다.

---

## 1. 공식 자료로 확정한 핵심 사실

### 2024년 6월 CPI, 7월 11일 발표

- 발표 시각: 2024년 7월 11일 목요일 08:30 ET.
- CPI-U: 전월 대비 -0.1%, 전년 대비 3.0%.
- 근원 CPI: 전월 대비 +0.1%, 전년 대비 3.3%.
- BLS는 휘발유가 3.8% 하락했고 주거비 상승을 상쇄했다고 설명했다.
- 근원 CPI의 12개월 상승률 3.3%는 2021년 4월 이후 가장 낮은 수준이었다.
- 출처: BLS CPI June 2024 release, https://www.bls.gov/news.release/archives/cpi_07112024.htm

### 2024년 7월 고용, 8월 2일 발표

- 발표 시각: 2024년 8월 2일 금요일 08:30 ET.
- 비농업 취업자 수: +114,000명.
- 실업률: 4.3%.
- 12개월 평균 취업자 증가 속도: +215,000명. 따라서 114,000명은 단순한 미스가 아니라 추세 대비 급한 냉각으로 읽혔다.
- BLS는 허리케인 베릴이 7월 전국 고용·실업 통계에 식별 가능한 영향을 주지 않았다고 명시했다. 본문에서는 "당일 일부 시장 참가자들이 일시 요인을 찾았지만, BLS 공식 문구는 더 신중했다"는 식으로 처리한다.
- 출처: BLS Employment Situation July 2024 release, https://www.bls.gov/news.release/archives/empsit_08022024.htm

### 2024년 7월 31일 FOMC

- 연준은 기준금리 목표 범위를 5.25~5.50%로 동결했다.
- 성명서는 경제활동이 견조하게 확장되고, 고용 증가가 완만해졌으며, 실업률은 올라갔지만 낮은 상태라고 표현했다.
- 인플레이션은 완화됐지만 아직 다소 높고, 최근 몇 달간 2% 목표를 향한 추가 진전이 있었다고 밝혔다.
- 출처: Federal Reserve FOMC Statement, 2024-07-31, https://www.federalreserve.gov/newsevents/pressreleases/monetary20240731a.htm

### 2024년 9월 18일 FOMC

- 연준은 기준금리 목표 범위를 0.50%포인트 낮춰 4.75~5.00%로 조정했다.
- 7월 말에는 "확신이 더 필요하다"였고, 9월에는 "더 큰 확신을 얻었다"로 문구가 바뀌었다. 8월의 폭락은 그 문구 변화 사이에 끼어 있다.
- 출처: Federal Reserve FOMC Statement, 2024-09-18, https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm

### 2024년 7월 31일 BOJ

- 일본은행은 무담보 콜금리 유도 목표를 약 0.25%로 올렸다.
- 결정은 7대 2였다.
- 동시에 장기국채 월간 매입액을 2026년 1~3월 약 3조 엔까지 줄이는 계획을 발표했다.
- 성명은 경제와 물가 전망이 실현된다면 정책금리를 계속 올리고 완화 정도를 조정하겠다고 했다. 이 문장이 캐리 포지션에는 "다음 인상도 올 수 있다"는 신호로 읽혔다.
- 출처: BOJ, Change in Guideline for Money Market Operations, 2024-07-31, https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2024/k240731a.pdf

### 2024년 8월 7일 우치다 신이치 연설

- 장소: 하코다테.
- 우치다는 7월 MPM의 인상 배경을 설명하면서도, 금융·자본시장이 국내외에서 극도로 불안정해진 상황에서는 당분간 현재 정책금리 수준의 완화를 유지할 필요가 있다고 말했다.
- 핵심 문장: BOJ will not raise its policy interest rate when financial and capital markets are unstable.
- 우치다는 대규모 약엔 포지션이 풀리면서 엔화가 크게 절상됐다고 직접 설명했다.
- 출처: BOJ, Speech by Deputy Governor Uchida, 2024-08-07, https://www.boj.or.jp/en/about/press/koen_2024/ko240807a.htm

---

## 2. yfinance로 검산한 시장 수치

검산일: 2026-04-26.
사용 티커: `^GSPC`, `^IXIC`, `^DJI`, `^RUT`, `^N225`, `^KS11`, `^KQ11`, `^VIX`, `JPY=X`, `NVDA`, `CRWD`, `DJT`, `AAPL`, `BRK-B`.

| 날짜 | 항목 | 종가/저가/고가 | 전일 대비 |
|------|------|----------------|-----------|
| 2024-07-11 | Russell 2000 | 2,125.04 | +3.57% |
| 2024-07-11 | Nasdaq Composite | 18,283.41 | -1.95% |
| 2024-07-11 | NVIDIA | 127.40 | -5.57% |
| 2024-07-15 | DJT | 40.58 | +31.37% |
| 2024-07-19 | CrowdStrike | 304.96 | -11.10% |
| 2024-07-19 | VIX | 16.52 종가, 17.19 고가 | +3.70% |
| 2024-07-31 | USD/JPY | 152.67 종가, 149.66 저가 | - |
| 2024-08-02 | S&P 500 | 5,346.56 | -1.84% |
| 2024-08-02 | Nasdaq Composite | 16,776.16 | -2.43% |
| 2024-08-02 | VIX | 23.39 종가, 29.66 고가 | +25.82% |
| 2024-08-05 | Nikkei 225 | 31,458.42 | -12.40% |
| 2024-08-05 | S&P 500 | 5,186.33 | -3.00% |
| 2024-08-05 | Nasdaq Composite | 16,200.08 | -3.43% |
| 2024-08-05 | Dow Jones | 38,703.27 | -2.60% |
| 2024-08-05 | KOSPI | 2,441.55 | -8.77% |
| 2024-08-05 | KOSDAQ | 691.28 | -11.30% |
| 2024-08-05 | VIX | 38.57 종가, 65.73 고가 | +64.90% |
| 2024-08-05 | USD/JPY | 145.58 종가, 141.70 저가 | -2.42% |
| 2024-08-06 | Nikkei 225 | 34,675.46 | +10.23% |
| 2024-08-08 | S&P 500 | 5,319.31 | +2.30% |
| 2024-08-22 | S&P 500 | 5,570.64 | 8월 5일 이전 수준 근접 회복 |

주의: 일본·한국 지수는 현지 거래일, 미국 지수는 미국 거래일 기준이다. 닛케이 225의 8월 5일 종가는 31,458.42이고, 전일 종가 35,909.70에서 4,451.28포인트 하락했다.

---

## 3. 개별 사건별 보강 메모

### 1~3장: 낮은 변동성의 세계

- 2024년 상반기 시장은 단순한 낙관이 아니라 "정당화된 낙관"이었다. 엔비디아의 실적과 주식 분할, AI 데이터센터 투자, 2023년부터 이어진 디스인플레이션이 함께 있었다.
- NVIDIA는 2024년 5월 22일 1분기 실적 발표에서 매출 260억 달러, 전년 대비 +262%, 데이터센터 매출 226억 달러, 전년 대비 +427%를 발표했고, 10대 1 주식분할을 6월 7일 장마감 후 시행한다고 밝혔다.
- 출처: NVIDIA Newsroom, 2024-05-22, https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-first-quarter-fiscal-2025
- VIX 12는 "평온"일 뿐 아니라 "보험료가 싸고 레버리지가 편한 상태"라는 점을 강조한다.

### 4장: 7월 11일 CPI와 로테이션

- 기존 원고의 "수요일"은 오류. 2024년 7월 11일은 목요일.
- 기존 원고의 Russell 2000 +5.3%는 종가 기준으로 과장. yfinance 검산 기준 +3.57%. 장중 또는 특정 ETF/구간 수익률과 혼동 가능성이 있으므로 본문은 +3.6%로 수정한다.
- 같은 날 Nasdaq Composite -1.95%, NVIDIA -5.57%. "인플레이션 호재인데 AI 대장주가 급락하고 소형주가 급등한 날"로 묘사한다.
- CPI의 세부 구성은 중요하다. 근원 +0.1%, 주거비 +0.2%, 에너지 -2.0%, 휘발유 -3.8%. 시장은 "라스트 마일"이 갑자기 쉬워질 수 있다고 읽었다.

### 5장: 트럼프 피격과 트럼프 트레이드

- 2024년 7월 13일 피격 이후 첫 거래일인 7월 15일 DJT는 +31.37%.
- 이 사건은 정치적 공포가 시장에서는 "당선 확률 재가격화"로 처리된 사례다.
- 본문에서는 총격 자체의 자극적 묘사를 늘리기보다, 위험 이벤트가 어떻게 포트폴리오 내러티브로 흡수되는지에 초점을 둔다.

### 6장: CrowdStrike와 7월 OpEx

- Microsoft 공식 블로그는 CrowdStrike 업데이트가 850만 대의 Windows 장치에 영향을 줬고, 이는 전체 Windows 기기의 1% 미만이지만 핵심 서비스 기업에 집중되어 경제·사회적 파장이 컸다고 설명했다.
- CrowdStrike 주가는 7월 19일 -11.10%.
- 출처: Microsoft Official Blog, 2024-07-20, https://blogs.microsoft.com/blog/2024/07/20/helping-our-customers-through-the-crowdstrike-outage/
- 이 장의 핵심은 "사이버 공격이 아닌 정상 업데이트가 세계를 멈췄다"는 점이다. 이는 블랙 먼데이와 같은 구조다. 악의적 충격이 아니라 정상 작동하던 시스템 내부의 연결성이 문제를 증폭했다.

### 9~10장: 엔화 160엔, BOJ, 캐리 트레이드

- USD/JPY는 7월 10일 yfinance 기준 161.74 고가, 7월 11일에도 161.75 고가를 기록한 뒤 157.49 저가까지 밀렸다. CPI 호재가 달러 약세로 연결되며 엔화 숏 포지션을 흔들기 시작한 날이다.
- CFTC CME futures-only COT 보고서(2024-07-09)는 Japanese Yen 비상업 포지션을 Long 41,521, Short 223,554로 제시한다. 비상업 순숏은 182,033계약이다.
- 출처: CFTC COT Futures Only, 2024-07-09, https://www.cftc.gov/files/dea/cotarchives/2024/futures/deacmesf070924.htm
- 본문에서는 "18만 계약대 순숏"으로 쓴다. 이 수치는 모든 OTC·스왑·은행 장부를 포함한 전체 캐리 트레이드 규모가 아니라, 공개 선물시장의 대표 온도계다.

### 11~12장: 고용 쇼크와 샴 룰

- Sahm Rule은 "실업률 3개월 평균이 직전 12개월의 최저 3개월 평균보다 0.5%포인트 이상 높아질 때" 발동한다.
- 2024년 7월 고용보고서 직후 실시간 추정치는 대략 0.53%포인트로 회자됐다.
- 본문에서 "허리케인 베릴 때문에 고용 쇼크가 나왔다"라고 쓰면 안 된다. BLS 공식 문구는 `no discernible effect`였다.
- 더 안전한 서술: "당일 시장은 일시 요인을 찾으려 했고, 일부 해석은 베릴과 계절 조정을 언급했다. 그러나 BLS는 전국 통계에 식별 가능한 영향은 없었다고 적었다. 그러니 핵심은 베릴 하나가 아니라, 시장이 이미 BOJ와 엔화 청산으로 흔들리는 상태에서 약한 고용 숫자를 받았다는 점이다."

### 13장: 8월 5일

- 기존 원고의 닛케이 종가 수치가 잘못 들어가 있다. 35,909.70은 전 거래일 종가이고, 8월 5일 종가는 31,458.42.
- 올바른 문장: "닛케이 225는 35,909.70에서 31,458.42로 내려앉았다. 하락폭은 4,451.28포인트, 하락률은 -12.40%였다."
- VIX 고가 65.73은 yfinance 검산과 주요 보도에서 일치한다.
- 미국 시장 종가 기준: S&P 500 -3.00%, Nasdaq Composite -3.43%, Dow -2.60%.
- 한국 시장 종가 기준: KOSPI -8.77%, KOSDAQ -11.30%.

### 14장: 버핏과 버크셔

- 기존 원고의 "애플 지분 약 510만 주"는 오류. 버크셔의 2분기 10-Q만으로는 주식 수를 직접 쓰기보다 공정가치 변화를 쓰는 편이 안전하다.
- Berkshire 10-Q 기준 Apple 공정가치: 2023년 말 1,743억 달러, 2024년 6월 말 842억 달러.
- 버크셔의 보험·기타 사업 현금, 현금성 자산, 미국 T-bill: 2,715억 달러.
- 전체 연결 대차대조표에서 Insurance and Other 현금성 자산 368.84억 달러, T-bills 2,346.18억 달러. Railroad/Utilities/Energy 현금 54.40억 달러까지 합치면 현금성은 더 커진다. 언론에서 흔히 쓴 "약 2770억 달러"는 더 넓은 범위의 현금·T-bill 집계다.
- 출처: Berkshire Hathaway 2024 Q2 Form 10-Q, https://www.berkshirehathaway.com/qtrly/2ndqtr24.pdf

### 16~17장: 우치다와 회복

- 우치다 발언은 8월 7일이지만, 닛케이의 +10.23% 급반등은 8월 6일에 발생했다. 본문은 "8월 6일 기술적 반등 후, 8월 7일 우치다가 회복의 논리를 제공했다"로 정리한다.
- 우치다의 말은 단순 진정 발언이 아니라 포지션 청산의 조건을 바꾼 발언이었다. BOJ가 연쇄 인상을 계속 밀어붙이지 않는다는 신호가 달러/엔에 가장 중요했다.
- 8월 8일 S&P 500 +2.30%, Nasdaq +2.87%, VIX는 종가 23.79까지 내려왔다.

### 18장과 에필로그: 교훈과 HALO

- "HALO 거래"는 기존 원고의 `Henious AI Leveling Out`이 아니라, Artisan Partners 자료 기준으로 "asset-light 기업을 팔고 hard assets with low obsolescence exposure를 사는 자본 회전"으로 설명된다.
- Artisan Partners 2026년 1분기 코멘터리는 AI가 소프트웨어의 장기 경제성과 내구성에 대한 불확실성을 키웠고, 시장이 asset-light 소프트웨어에서 hard assets/low obsolescence 쪽으로 자본을 돌리는 현상을 HALO라고 설명한다.
- 출처: Artisan Focus Fund Q1 2026 Commentary, https://www.artisanpartners.com/content/dam/documents/quarterly-commentary/vr/2026/1q/ARTTX-APDTX-APHTX-QCommentary-1Q26-vR.pdf
- "Claude Cowork", "SaaSpocalypse", "2조 달러 증발", "솔로몬의 2026년 2월 발언"은 현재 1차 출처가 충분하지 않거나 용어가 불안정하다. 에필로그에서는 구체명사를 줄이고, "AI가 소프트웨어의 미래 현금흐름을 덜 측정 가능하게 만들었다"는 구조적 비교로 재작성한다.

---

## 4. 집필용 한 문장 테제

2024년 8월의 블랙 먼데이는 경기침체가 시작됐다는 증거가 아니라, 낮은 변동성의 세계에서 한쪽으로 쌓인 포지션이 중앙은행의 작은 문장과 약한 경제지표를 만나 얼마나 빠르게 무너질 수 있는지를 보여 준 사건이었다.

---

## 5. 출처 목록

- BLS, Consumer Price Index -- June 2024: https://www.bls.gov/news.release/archives/cpi_07112024.htm
- BLS, Employment Situation -- July 2024: https://www.bls.gov/news.release/archives/empsit_08022024.htm
- Federal Reserve, FOMC Statement, 2024-07-31: https://www.federalreserve.gov/newsevents/pressreleases/monetary20240731a.htm
- Federal Reserve, FOMC Statement, 2024-09-18: https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm
- Bank of Japan, July 31 2024 policy decision: https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2024/k240731a.pdf
- Bank of Japan, Uchida speech, 2024-08-07: https://www.boj.or.jp/en/about/press/koen_2024/ko240807a.htm
- Microsoft Official Blog, CrowdStrike outage, 2024-07-20: https://blogs.microsoft.com/blog/2024/07/20/helping-our-customers-through-the-crowdstrike-outage/
- NVIDIA Newsroom, Q1 FY2025 results and 10-for-1 split: https://nvidianews.nvidia.com/news/nvidia-announces-financial-results-for-first-quarter-fiscal-2025
- Berkshire Hathaway 2024 Q2 Form 10-Q: https://www.berkshirehathaway.com/qtrly/2ndqtr24.pdf
- CFTC, CME Futures Only Commitments of Traders, 2024-07-09: https://www.cftc.gov/files/dea/cotarchives/2024/futures/deacmesf070924.htm
- Artisan Partners, Artisan Focus Fund Q1 2026 Commentary: https://www.artisanpartners.com/content/dam/documents/quarterly-commentary/vr/2026/1q/ARTTX-APDTX-APHTX-QCommentary-1Q26-vR.pdf
- 시장 수치 검산: yfinance historical download, 2026-04-26 실행.
