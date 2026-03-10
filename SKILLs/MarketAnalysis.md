# MarketAnalysis (시장 상황/리스크 분석) — SKILL

이 문서는 사용자가 **시장 상황 분석/리포트**(예: “오늘 시장 왜 이래?”, “리스크 온/오프 판단해줘”, “지금 위험 수준 어때?”)를 요청할 때,
본 프로젝트가 따를 “데이터 수집 절차 + 해석 체크리스트 + 출력 템플릿”을 정의한다.

---

## 1) 적용 조건
- 사용자가 시장의 **현재 상황/리스크 레짐/원인(드라이버)** 분석을 요청하면 이 지침을 따른다.
- 출력은 **한국어**로 한다.

## 2) Output 원칙 (필수)
- 시간 표기는 **KST(Asia/Seoul)** 기준으로 한다(특히 뉴스/이벤트).
- 시장 데이터는 “**as of (KST)**”를 명시하고, 데이터가 **실시간/지연/전일 종가** 중 무엇인지 한 줄로 고지한다.
- **파이썬은 데이터 정리 중심, 문장 생성 최소화**를 원칙으로 한다.
  - 파이썬 출력은 `Context Pack`(표/리스트/카드) 위주로 제한한다.
  - Flash Layer는 `Regime Score + Signals + Rule Hits` 형태의 데이터 블록만 출력한다.
  - 파이썬 출력에는 `결론` 섹션을 포함하지 않는다.
  - 최종 서술(문장 품질, 톤, 문단 흐름)은 이 `.md` 지침으로 통제한다.
- 결론은 단정 대신 **조건/트리거 기반**으로 쓴다(“만약 A면 B 가능성↑”).
- 정보 나열형 출력을 피하기 위해, **최종 섹션을 반드시 `결론`으로 종료**한다.
  - `결론`에는 현재 위험 레짐, 핵심 근거 3개 내외, 즉시 볼 트리거를 짧게 재요약한다.
- 결과물은 기본적으로 **두 겹 구조**로 출력한다.
  - **Flash Layer**: 의사결정용 20~40줄 요약
  - **Deep-Dive Layer**: 근거/표/시나리오/체크리스트
- 사용자가 `뉴스 지면 확대`, `뉴스레터 스타일`, `산문 브리핑`, `블룸버그 스타일`을 요청하면,
  Deep-Dive의 뉴스 파트를 **산문형 뉴스레터 모드**로 확장한다.
  - 권장 문단 수: **8~14문단**
  - 문단당 권장 길이: **3~5문장**
  - 단순 헤드라인 나열 대신 **맥락 → 시장 반응 → 다음 체크포인트** 흐름으로 쓴다.
- 산문 작성 상세 톤은 `SKILLs/MarketAnalysis_GPT_STYLE.md`를 우선 참조한다.

## 3) Data & Tools (우선순위)

### 3.1 기본(항상 우선)
- **yfinance**: 시장 데이터의 기본 소스 (`reference/yfinance_reference.md` 참고)
- **world_issue_log**: 관련성이 있을 때 최근 21~30일 로그를 먼저 읽어 현재 진행 중인 중기 내러티브를 파악한다.
  - 단, 월드 메모리와 직접 관련이 낮거나 데이터가 충분치 않으면 별도 섹션을 강제하지 않고 내부 참고용으로만 사용한다.
- **최신 뉴스/속보**: AGENTS.md의 뉴스 출처들을 사용한다.
- **크립토 변동성 텀스트럭처(BVIV/BVIV60D)**: Volmex API(`https://rest-v1.volmex.finance/v2/history`)를 사용한다.

### 3.2 조건부(필요할 때만)
- FEED로 뉴스 흐름을 잡은 뒤, **반드시 2차 오픈웹 재검증**을 수행한다.
- WSJ/Bloomberg/FT처럼 페이월 가능성이 높은 링크는 “헤드라인 신호”로만 사용하고,
  본문 근거는 가급적 **비페이월 소스**로 채운다.
- **오픈웹 재검증 우선 출처(비페이월):**
  1. `Reuters`, `AP`, `CNBC`, `Yahoo Finance`
  2. `MarketWatch`, `Investing.com`, `BBC`, `Guardian`
- 원칙: 같은 테마에서 최소 1~2개 비페이월 링크를 붙여 “재검증 완료”를 표시한다.
- 블로그/유튜브/검증 불가 출처는 검색되더라도 **인용하지 않는다**.
- 보강용 공개 지표(FRED 등)는 “3차 보강”으로만 사용한다.

## 4) 실행 전 확인(환경/설치)
- 코드 실행이 필요하면 Python/yfinance 설치 여부를 먼저 확인한다.
- 설치가 필요할 때는 사용자에게 설치 진행 여부를 확인한 뒤, 아래를 안내한다.
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install yfinance pandas numpy`

## 5) Input 파악(필수 질문)
- 대상 시장/자산: **미국 주식 중심인가?** (또는 금리/크레딧/FX/원자재/크립토 중심)
- 기간: **intraday / 1~2주 / 1~3개월** 중 무엇인가
- 목적: “상황 설명/리스크 체크/헤지 아이디어/이벤트 대비” 중 무엇인가
- 기준 시각: “지금(실시간)”인지 “전일 종가 기준”인지
- 출력 깊이: Flash만 / Flash+Deep-Dive
- 뉴스 출력 스타일: **요약형 리스트** vs **뉴스레터 산문형(블룸버그 톤)**

---

## 6) 분석 워크플로우 (권장)

### 6.1 5분 대시보드(가격/방향/급변) — yfinance
아래 티커를 우선으로 스냅샷을 만든다(1D/5D/1M 변화율 + 1Y 퍼센타일을 같이 보면 해석이 안정적).
VIX/옵션/뉴스는 아래 섹션(6.2~6.5)에서 별도로 다룬다.

#### 6.1.1 우선 벤치마크(권장)
| 테마 | 지표 | yfinance 티커(예) | 관찰 포인트 |
| --- | --- | --- | --- |
| Benchmark | SPX(표준) | `^SPX` | 모든 상대강도 비교의 기준 |
| Breadth | S&P500 Equal-weight | `RSP` | `RSP/SPY`(또는 `RSP` vs `^SPX`)로 폭/참여도 |
| Small | Russell 2000 | `^RUT` (또는 `IWM`) | `IWM/SPY`로 리스크 감수/금리 민감 |
| Tech | Nasdaq 100 | `QQQ` (또는 `^NDX`) | `QQQ/SPY`로 기술주 리더십 |
| Mega | NDX Mega | `^NDXMEGA` (또는 `QBIG`) | `QBIG/QQQ`, `^NDXMEGA/^NDX`로 “쏠림” |
| USD | DXY | `DX-Y.NYB` | 달러 강세=금융여건 타이트(주의: `^DXY`는 종종 불가) |
| Rates | 장기채(듀레이션) | `TLT` | `TLT↑`=수익률↓(완화/성장우려/리스크오프) |
| Oil | WTI Crude | `CL=F` | 수요/공급/지정학/인플레 재평가 |
| Gold | Gold | `GC=F` | 실질금리/달러/불확실성(헤지) |
| 소비 | Consumer Staples | `VDC` | `VDC/SPY`↑면 방어적(실물 우려/리스크오프) |
| 크립토 | Bitcoin | `BTC-USD` (또는 `IBIT`) | 24/7 위험선호/레버리지 변화 단서 |
| 투기 | MEME | `MEME` | 투기적 위험감수(유동성/심리) 단서 |

#### 6.1.2 보강(필요 시)
| 테마 | 지표 | yfinance 티커(예) | 관찰 포인트 |
| --- | --- | --- | --- |
| Credit | HY/IG ETF | `HYG`, `LQD` | `HYG/LQD` 하락=리스크오프(크레딧 스트레스) |
| Rates Vol | MOVE | `^MOVE` | 채권발 변동성 전이 |
| Equity Breadth(보조) | S&P500 ETF | `SPY` | 상대강도 계산용(프록시) |

**기본 해석 규칙**
- “주식↓ + VIX↑ + 크레딧 악화(HYG↓) + 달러↑” 조합이면 위험회피(리스크 오프) 가중.
- `RSP`가 `SPY`/`^SPX` 대비 강하면: 폭이 넓어지는 “건강한” 리스크온일 가능성.
- `IWM`이 `SPY` 대비 약하면: 고금리/금융여건/성장 우려가 중소형주에 부담일 수 있다.
- `QBIG`/`^NDXMEGA`가 `QQQ` 대비 강하면: “초대형 쏠림”이 심화(상승해도 내부는 취약할 수 있음).
- `VDC`가 `SPY` 대비 강하면: 방어 선호(경기 둔화/불확실성) 쪽으로 해석 가능.
- “주식↑ + VIX↓ + 금리↑(성장/인플레) vs 금리↓(완화/성장우려) 구분”처럼 **금리 방향의 의미**를 같이 해석한다.
- `DX-Y.NYB`(DXY)↑는 글로벌 금융여건을 타이트하게 만들 수 있다(특히 리스크자산/중소형/크립토에 불리하게 작동하기 쉬움).
- 주말/휴장 시에는 전일 종가 기준이므로 “데이터 컷오프”를 명시하고, 24/7 자산(BTC 등)은 별도 표기한다.

#### 6.1.3 상대강도(필수) 계산/표기 규칙
- 기본 표기는 “비율”로 한다: `RSP/SPY`, `IWM/SPY`, `QQQ/SPY`, `QBIG/QQQ`, `VDC/SPY`, `MEME/SPY` 등.
- 해석은 “레벨”보다 “방향(추세)”을 우선한다.
  - ratio가 5D/20D 기준으로 상승 추세면: 해당 팩터/바스켓의 상대강도↑
  - ratio가 하락 추세면: 상대강도↓

### 6.2 변동성/옵션(핵심)

#### 6.2.1 VIX 레벨 + term structure(반드시 계산)
- 대상:
  - 현물 VIX: `^VIX`
  - 1M 프록시: `^VFTW1`
  - 2M 프록시: `^VFTW2`

**체크 항목**
- **레벨**: `VIX`, `VIX1`, `VIX2`
- **스프레드(레벨)**:
  - `Spread(1M-Spot) = VIX1 - VIX`
  - `Spread(2M-1M) = VIX2 - VIX1`
  - `Spread(2M-Spot) = VIX2 - VIX`
- **스프레드(%)**:
  - `Pct(1M-Spot) = (VIX1/VIX - 1) * 100`
  - `Pct(2M-1M) = (VIX2/VIX1 - 1) * 100`

**해석 가이드(요약)**
- **선물 > 현물(컨탱고)**: 단기 공포가 상대적으로 완화(일반적/정상 구간 가능).
- **현물 > 선물(백워데이션)**: 단기 공포/스트레스가 강하고 즉시 헤지 수요가 큰 편.
- 1M-Spot이 급격히 뒤집히고 2M-1M도 동반되면: 위험 인식이 **단기 → 중기**로 확산 중일 수 있다.

#### 6.2.2 BVIV 레벨 + term structure(반드시 계산)
- 대상:
  - 30D IV: `BVIV` (차트: `https://charts.volmex.finance/symbol/BVIV`)
  - 60D IV: `BVIV60D` (차트: `https://charts.volmex.finance/symbol/BVIV60D`)

**API(공식)**
- 엔드포인트: `GET https://rest-v1.volmex.finance/v2/history`
- 파라미터:
  - `symbol`: `BVIV` 또는 `BVIV60D`
  - `resolution`: `1`, `5`, `15`, `30`, `60`, `D` 중 선택(일반적으로 `D`)
  - `from`, `to`: Unix epoch(초)
- 예시:
  - `https://rest-v1.volmex.finance/v2/history?symbol=BVIV&resolution=D&from=1735689600&to=1738291200`
  - `https://rest-v1.volmex.finance/v2/history?symbol=BVIV60D&resolution=D&from=1735689600&to=1738291200`

**체크 항목**
- **레벨**: `BVIV`, `BVIV60D`
- **스프레드(레벨)**:
  - `Spread(60D-30D) = BVIV60D - BVIV`
- **스프레드(%)**:
  - `Pct(60D-30D) = (BVIV60D/BVIV - 1) * 100`

**해석 가이드(요약)**
- `BVIV60D > BVIV`(우상향): 단기 급변 리스크보다 중기 불확실성 프리미엄이 큰 상태.
- `BVIV > BVIV60D`(역전): 단기 스트레스/이벤트 리스크가 더 급한 상태.
- 역전이 급격히 확대되면: 레버리지 청산/이벤트 충격의 단기 집중 가능성 가중.

**실무 규칙**
- BVIV 계열은 yfinance가 아니라 Volmex API 데이터임을 결과 표/주석에 명시한다.
- `BVIV`와 `BVIV60D`는 반드시 **동일 시각(as of)** 으로 맞춰 스프레드를 계산한다.
- API 장애(빈 배열, `s != ok`) 시:
  - 직전 유효값을 사용하고 “전 시점 값 사용”을 명시한다.
  - 차트 링크를 함께 제시해 수동 교차검증한다.

#### 6.2.3 SPX 옵션 체인(가능하면) → 실패 시 프록시
- 우선: `^SPX` 옵션 체인 분석을 시도한다.
- yfinance에서 지수 옵션이 막히거나 누락되면:
  1) **SPY 옵션**으로 프록시(`^SPX` vs `SPY`의 차이(배당/미세구조)를 1줄 고지)
  2) (필요 시) `QQQ`, `IWM` 옵션으로 리스크 전염 여부를 추가 확인

**분석 아이디어(가능한 범위에서)**
- **Put/Call 비율**: 거래량/미결제약정(OI) 기준으로 계산(가능하면 ATM 근처 vs 전체 분리)
- **IV 레벨/변화**: IV 수준과 최근 대비 변화(예: 5D/20D)
- **IV 스큐/스마일**: 하방 풋 IV 프리미엄(헤지 수요) 여부 요약
- **만기 구조(텀스트럭처)**: 단기 만기 IV 급등(이벤트 리스크) 여부
- **OI 분포**: 특정 스트라이크/만기에 OI 집중 시 “관심 구간/방어선” 단서

### 6.3 금리/유동성/크레딧(보강)
- 크레딧(프록시):
  - `HYG`(HY), `LQD`(IG)로 위험자산 스트레스를 체크한다.
  - 간단 프록시(예): `HYG/LQD` 비율 하락 = 위험회피 신호로 해석 가능.

#### 6.3.1 보강용 공개 지표(FRED) (선택)
- Economic Policy Uncertainty Index (US): `https://fred.stlouisfed.org/series/USEPUINDXD`
- ICE BofA US High Yield OAS: `https://fred.stlouisfed.org/series/BAMLH0A0HYM2`
- ON RRP: `https://fred.stlouisfed.org/series/RRPONTSYD`
- Standing Repo Facility Minimum Bid Rate: `https://fred.stlouisfed.org/series/SRFTSYD`

### 6.4 달러/원자재/크립토(보강)
- 달러: `DX-Y.NYB`(DXY)로 글로벌 금융여건을 요약한다.
- 원자재:
  - 유가 `CL=F`(성장/인플레/리스크),
  - 금 `GC=F`(위험회피/실질금리)로 보강한다.
- 크립토: `BTC-USD`(또는 `IBIT`)의 급락/급등을 “레버리지 청산/위험선호 변화” 힌트로 사용한다(24/7 거래임을 명시).
- 투기성 위험감수(프록시): `MEME`의 상대강도(`MEME/SPY`)로 “리스크 감수/유동성”의 온도를 보강한다.

### 6.5 뉴스 → 가격 연결(우선)
- `AGENTS.md의 뉴스 출처들을 사용하여`최신 소식을 확인한다.
- FEED 핵심 헤드라인(테마별 1~3개)을 먼저 선정한다.
- 선정된 헤드라인을 키워드화해 오픈웹(비페이월) 재검색을 수행한다.
- 파이썬 출력에는 “FEED 신호”와 “오픈웹 재검증”을 카드로 분리 표기한다.
- 최종 본문은 LLM이 카드를 읽고 **맥락형 문장으로 재작성**한다.
- 구현 원칙: 파이썬 스크립트에는 고정 문장 템플릿을 넣지 않고, 재검색/해석은 LLM 단계에서 수행한다.
- 중복 제거 후 “최신/심각도 가중치”로 정렬하고, 시장 움직임과 매핑한다.
  - 정책/금리/인플레 → 금리/달러/성장주
  - 지정학/원자재 → 유가/방산/리스크오프
  - 신용 이벤트 → 크레딧/금융주/리스크오프
  - 실적/가이던스 → 섹터/지수 리더십 변화

#### 6.5.0 작성 품질 규칙(강화)
- 단순 템플릿 문장 반복을 금지한다.
- 테마 카드형(`FEED 신호` / `오픈웹 재검증` / `시장 해석`) 또는 내러티브형 중 하나를 선택해,
  같은 문장 골격을 복붙하지 않는다.
- “오픈웹 보강 기사 없음”이면 그대로 명시하고 과도한 추정을 붙이지 않는다.
- 문장 생성은 가급적 LLM 단계에서 수행하고, 파이썬에는 문장 템플릿을 넣지 않는다.
- `결론` 섹션은 LLM 최종 답변에서만 작성한다.

#### 6.5.1 뉴스레터 산문형 모드(요청 시 필수)
- `News Tape` 요약 리스트 외에, **뉴스레터 본문 섹션**을 추가한다.
- 문단은 최소 8개 이상으로 구성하고, 아래 순서를 권장한다.
  1) 오프닝(오늘 뉴스 레짐 한 문장)
  2) 지정학/원자재 축
  3) 금리/유동성 축
  4) 거시/소비 축
  5) 기업/섹터 축
  6) 시장 가격과 연결되는 관찰 2~4문단
  7) 당일 해석 리스크(오보/발언 리스크/확증편향)
- 각 문단 말미 또는 중간에 **출처 링크를 자연스럽게 포함**한다.
- 톤은 “정보 밀도 높은 차분한 브리핑”을 유지한다(과장/선정 표현 금지).

#### 6.5.2 심리 해석 체크리스트
- 심리가 위축(공포)이라면:
  - “무엇이 트리거인가?”(물가/금리/정책/지정학/유동성/신용/실적/기술적 충격)
  - “왜 지금 공포가 커졌나?”(예상 대비 서프라이즈, 포지셔닝, 레버리지, 유동성 악화)
- 심리가 긍정(낙관)이라면:
  - “무엇이 낙관의 근거인가?”(연준/물가/성장/AI/실적/유동성)
  - “낙관이 가리는 잠재 리스크는?”(밸류에이션, 크레딧 스트레스, 옵션 포지셔닝, 이벤트 리스크)

### 6.6 결론(레짐 + 시나리오 + 트리거)
- 위험 레짐을 한 문장으로 선언한다(예: “단기 리스크 오프(중간 강도), 이벤트 리스크 우위”).
- **Baseline/Upside/Downside** 3가지 시나리오를 제시하고, 각 시나리오의 트리거를 불릿으로 적는다.
- “지켜볼 지표(Watchlist)”를 5~10개로 마무리한다(티커/수치 기준 포함).

---

## 7) 대체 루트(주말/휴장/데이터 공백)
- yfinance 데이터가 비거나(특히 옵션) 지연될 때는:
  - 마지막 유효 데이터(전일 종가/최근 체결)를 사용하고 “as of”를 명시한다.
  - 지수 옵션이 불가하면 ETF 옵션(SPY 등)으로 프록시한다.
- SPX/ETF 옵션 체인까지 모두 어려우면(또는 주말/휴장으로 옵션 데이터를 못 잡으면) 아래 체인을 사용해 “시장 공포/레버리지 청산 리스크”를 프록시할 수 있다(=yfinance 밖 데이터, 사용 사실을 명시).
  - `https://www.barchart.com/futures/quotes/BT*0/options?futuresOptionsView=merged`
  - `https://www.tradingview.com/symbols/CME-BTC1!/options-chain/`
- (필요 시) “SPX 대신 프록시로 분석했음”을 결론/표에 **명확히 표기**한다.

## 8) Output 템플릿 (Markdown)

### 8.1 Flash Layer (권장)
```
### 시장 상황 요약 (as of YYYY-MM-DD HH:MM KST)
**한 줄 결론:** …

| Bucket | Signal | 해석 |
| --- | --- | --- |
| Equity | … | … |
| Vol | … | … |
| Rates | … | … |
| Credit | … | … |
| USD/Commod | … | … |

**핵심 드라이버(3~7개)**
1) … ([출처](URL))
2) …

**시나리오/트리거**
- Baseline: …
- Upside: …
- Downside: …

**Watchlist (예)**
- `^VIX`, `^VFTW1-^VIX` …
- `BVIV`, `BVIV60D`, `BVIV60D-BVIV` …
- `^SPX` …
- `RSP/SPY`, `IWM/SPY`, `QQQ/SPY`, `QBIG/QQQ` …
- `DX-Y.NYB`, `TLT` …
- `CL=F`, `GC=F` …
- `VDC/SPY`, `BTC-USD`/`IBIT`, `MEME/SPY` …
```

### 8.2 Deep-Dive Layer (권장)
```
## 1. Market Regime
- Risk-on/off 판단과 근거(교차자산)

## 2. Vol/Options
- VIX term structure 표 + 해석
- (가능하면) SPX/SPY 옵션 P/C, IV, 스큐 요약

## 3. Rates/Credit/Liquidity
- 금리 방향/커브/ MOVE
- 크레딧 프록시(HYG/LQD)와 함의

## 4. News Tape (from FEED)
- 최신/중요 뉴스 10~20개 요약(중복 제거, KST)
- Open-Web Corroboration(비페이월 재검증 링크) 5~15개
- 요청 시: 8~14문단의 뉴스레터 산문 브리핑 추가

## 5. Scenarios & Triggers
- Baseline/Upside/Downside + 트리거 체크리스트

## 6. 결론
- 현재 위험 레짐 한 줄
- 근거 요약(3개 내외)
- 다음 액션/우선 모니터링 지표(3~5개)

## Appendix
- 데이터 컷오프(as of)
- 사용한 티커 목록
- (필요 시) 재현 가능한 코드/CLI 로그
```

### 8.3 News Letter Layer (요청 시 권장)
```
## News Letter Layer (Bloomberg-style, KST)
오늘 뉴스 플로우의 중심은 … 이다. … [출처](URL)

… (문단 2)
… (문단 3)
…
… (문단 8~14)
```

### 8.4 Context Pack (파이썬 출력 권장)
```
## News Context Cards (KST)
### 지정학·에너지
- FEED 신호: ...
- 오픈웹 재검증: ...

### 금리·유동성·채권
- FEED 신호: ...
- 오픈웹 재검증: ...
```

## 9) 근거 표기(Citation) 규칙
- yfinance 기반 수치: 숫자/표 하단에 다음처럼 표기한다.
  - 예: `(yfinance: ^VIX, Close, 2026-01-23)`
  - 예: `(yfinance: ^SPX options, 2026-01-23 expiry)`
- 뉴스/기사: 제목 또는 핵심 문장 옆에 `[매체명](URL)` 링크를 붙인다.
- 추정/가설은 “추정/가설”임을 명시하고, 근거(지표/뉴스)를 같이 적는다.

## 10) Safety & Limitations
- 투자 조언이 아니라 **정보 제공 목적**임을 명시한다.
- yfinance/FEED는 지연·누락·정의 차이가 있을 수 있다.
- 단일 지표로 결론을 고정하지 말고, 최소 2~3개 범주(주식/변동성/금리/크레딧/달러)로 교차검증한다.

## 11) Python 스냅샷 스켈레톤(필요 시)
```python
import yfinance as yf

TICKERS = [
    "^SPX", "SPY",
    "RSP", "^RUT", "IWM",
    "QQQ", "^NDX", "^NDXMEGA", "QBIG",
    "^VIX", "^VIX9D", "^VVIX", "^SKEW", "^VFTW1", "^VFTW2",
    "DX-Y.NYB",
    "TLT", "VDC",
    "HYG", "LQD",
    "CL=F", "GC=F",
    "BTC-USD", "IBIT", "MEME",
]

def fetch_snapshot(period="1mo"):
    df = yf.download(TICKERS, period=period, interval="1d", group_by="ticker", progress=False)
    closes = {}
    for t in TICKERS:
        if t in df.columns.get_level_values(0):
            s = df[t]["Close"].dropna()
            closes[t] = float(s.iloc[-1]) if not s.empty else None

    ratios = {
        "RSP/SPY": (closes["RSP"] / closes["SPY"]) if (closes.get("RSP") is not None and closes.get("SPY") is not None) else None,
        "IWM/SPY": (closes["IWM"] / closes["SPY"]) if (closes.get("IWM") is not None and closes.get("SPY") is not None) else None,
        "QQQ/SPY": (closes["QQQ"] / closes["SPY"]) if (closes.get("QQQ") is not None and closes.get("SPY") is not None) else None,
        "QBIG/QQQ": (closes["QBIG"] / closes["QQQ"]) if (closes.get("QBIG") is not None and closes.get("QQQ") is not None) else None,
        "^NDXMEGA/^NDX": (closes["^NDXMEGA"] / closes["^NDX"]) if (closes.get("^NDXMEGA") is not None and closes.get("^NDX") is not None) else None,
        "^RUT/^SPX": (closes["^RUT"] / closes["^SPX"]) if (closes.get("^RUT") is not None and closes.get("^SPX") is not None) else None,
        "VDC/SPY": (closes["VDC"] / closes["SPY"]) if (closes.get("VDC") is not None and closes.get("SPY") is not None) else None,
        "IBIT/SPY": (closes["IBIT"] / closes["SPY"]) if (closes.get("IBIT") is not None and closes.get("SPY") is not None) else None,
        "MEME/SPY": (closes["MEME"] / closes["SPY"]) if (closes.get("MEME") is not None and closes.get("SPY") is not None) else None,
    }

    vix = closes.get("^VIX")
    vix1 = closes.get("^VFTW1")
    vix2 = closes.get("^VFTW2")
    spreads = None
    if all(x is not None for x in (vix, vix1, vix2)):
        spreads = {
            "Spread(1M-Spot)": vix1 - vix,
            "Spread(2M-1M)": vix2 - vix1,
            "Spread(2M-Spot)": vix2 - vix,
            "Pct(1M-Spot)": (vix1 / vix - 1) * 100,
            "Pct(2M-1M)": (vix2 / vix1 - 1) * 100,
        }
    return closes, ratios, spreads
```
