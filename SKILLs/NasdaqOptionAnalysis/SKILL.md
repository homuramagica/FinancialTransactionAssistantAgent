---
name: nasdaq-option-analysis
description: NDX 옵션체인과 가격 데이터를 yfinance로 분석해 요청 시 1회 실행 HTML 리포트를 만들고 reports/ 폴더에 저장하는 스킬. 사용자가 "나스닥 옵션 분석", "NDX 옵션 분석", "NDX 옵션체인 보고서"를 요청할 때 사용한다.
---

# 나스닥 옵션 분석 — SKILL

이 스킬은 Nasdaq 100 원지수인 `^NDX` 전용 옵션 분석 요청을 처리한다.

## 1) 적용 조건
- 사용자가 `나스닥 옵션 분석`, `NDX 옵션`, `NDX 옵션체인`, `NDX 옵션 리포트`를 요청하면 적용한다.
- 출력은 한국어로 작성한다.

## 2) 절대 원칙
- yfinance 심볼은 반드시 `^NDX`를 사용한다.
- 보고서 표기명은 `NDX`로 쓴다.
- 실행 방식은 **요청 시 1회 실행**이다.
- `while True` 기반 주기 루프를 만들거나 유지하지 않는다.
- 분석 결과 파일은 기본적으로 `reports/`에 `HTML`로 저장한다.
- 보고서 제목은 반드시 `나스닥 옵션 분석`으로 시작한다.
- 시간 표기는 `KST(Asia/Seoul)` 기준으로 맞춘다.
- 보고서 문체는 모든 보고서 공통 규칙인 `SKILLs/ReportWritingStyle.md`를 적용한다.

## 3) 데이터 소스
- 기본 소스: `yfinance`
- 가격: `Ticker.history()` 또는 `yf.download("^NDX", ...)`
- 옵션: `Ticker("^NDX").options`, `Ticker("^NDX").option_chain(exp)`
- 필요 시 보조 지표: `^VIX`, `^VFTW1`, `^VFTW2`, `VIXY`, `VIXM`, `^TNX`, `DX-Y.NYB` (거시/변동성 맥락용)

## 4) 실행 워크플로우
1. 요청 확인
- 사용자가 원하는 기간/초점(만기 구조, Max Pain, OI 집중, IV 등)을 파악한다.
- 별도 지시가 없으면 최근 1~3개월 가격 + 최근 만기군 옵션체인을 기준으로 분석한다.

2. 데이터 수집
- `NDX` 가격, 거래량, 기술 지표 계산에 필요한 시계열을 수집한다.
- 옵션 만기 리스트를 조회하고, 30D 분석이 가능하도록 가까운 만기부터 지정 개수(기본 20개)를 수집한다.

3. 핵심 지표 계산
- 옵션: Put/Call 비율(Volume, OI), Max Pain, 30D 근접 만기 OI 집중 스트라이크, 30D IV, IV-RV Spread, 30D 변동성 스큐
- 가격: 120일 이동평균, 120일 평균 대비 Z-Score, ±1/2/3σ 밴드, Volatility, 기준 레벨(최근 고저/매물대)
- 시장 스냅샷 차트는 일반 20/50/200 이평선과 MACD 대신 120일 Z-Score 밴드, 거래액(Close×Volume), Z-Score 오실레이터, VX 곡선 모멘텀을 사용한다.
- VX 곡선 모멘텀은 `VX1!`/`VX2!`의 yfinance 최신 스냅샷 프록시인 `^VFTW1`/`^VFTW2`를 카드로 표시하고, 라인차트는 과거 일봉이 안정적으로 수집되는 `VIXY`/`VIXM` 프록시로 대체한다.
- `VIXY`/`VIXM` 라인차트는 `auto_adjust=False`로 받아 `((VIXY / VIXM) - 1) * -100` 원시값을 가격 차트와 같은 최근 120거래일 구간으로 표시한다. 스무딩과 백어드저스트는 적용하지 않고, ETF 프록시 특성상 장기 감쇠가 차트 의미를 흐리지 않도록 0선 강조도 넣지 않는다.
- 모멘텀 점검에는 Z-Score 다이버전스와 Supertrend(ATR 10, multiplier 3)를 함께 표시한다.
- Volatility는 포트폴리오 분석과 같은 방식으로 일간 수익률 표준편차(`ddof=0`)를 `sqrt(365)`로 연율화해 계산한다.
- 거시 보조: 필요할 때만 VIX/금리/달러 방향성을 한 줄로 연결

4. 보고서 작성
- 아래 6) 템플릿 구조로 Markdown 보고서를 만든다.
- 마지막 섹션 제목은 반드시 `결론`으로 종료한다.

5. 파일 저장
- 저장 경로: `reports/`
- 권장 파일명:
  - `reports/nasdaq_option_analysis_ndx_YYYYMMDD_HHMMSS_kst.html`
  - 필요 시 보조 이미지: `reports/nasdaq_option_analysis_ndx_YYYYMMDD_HHMMSS_kst.png`

## 5) 예외 처리
- 옵션체인이 비어 있거나 일부 만기가 누락되면:
  - 수집 성공한 만기만 사용한다.
  - 보고서에 `데이터 공백/제약` 항목으로 명시한다.
- 장마감/휴장 시간에는 최신 체결 시각과 데이터 지연 가능성을 같이 적는다.

## 6) 출력 템플릿 (HTML)

```html
<html>
  <head><meta charset="utf-8"><title>나스닥 옵션 분석 (NDX)</title></head>
  <body>
    <h1>나스닥 옵션 분석 (NDX)</h1>
    <p>as of (KST): YYYY-MM-DD HH:MM:SS</p>
    <p>데이터 상태: 실시간/지연/전일 종가</p>

    <h2>1. 시장 스냅샷</h2>
    <ul>
      <li>NDX 현재가, 1D/5D/1M 변화율</li>
      <li>120일 평균선과 ±1/2/3σ Z-Score 밴드</li>
      <li>거래액(Close×Volume) 추이</li>
      <li>Z-Score 오실레이터와 과열/초과열 구간</li>
      <li>^VFTW1/^VFTW2 최신 스냅샷과 VIXY/VIXM 기반 VX 곡선 모멘텀 프록시</li>
      <li>Volatility 요약</li>
    </ul>

    <h2>2. 옵션체인 핵심</h2>
    <ul>
      <li>만기별 Put/Call (Volume, OI)</li>
      <li>Max Pain</li>
      <li>30D 근접 만기 OI 집중 스트라이크 상위 N개</li>
      <li>30D IV, IV-RV Spread, ATM IV 만기 구조</li>
      <li>30D 근접 만기 풋/콜 변동성 스큐 2D 차트</li>
    </ul>

    <h2>3. 해석 포인트</h2>
    <ul>
      <li>수급/심리 시사점</li>
      <li>가격 레벨(지지/저항)과 옵션 포지셔닝 연결</li>
      <li>단기 리스크 시그널</li>
    </ul>

    <h2>결론</h2>
    <ul>
      <li>현재 레짐 한 줄</li>
      <li>핵심 근거 3개</li>
      <li>다음 체크포인트 3개</li>
    </ul>
  </body>
</html>
```

## 7) 보고서 전달 방식
- 대화창에는 핵심 요약만 짧게 전달한다.
- 상세 내용은 `reports/`에 저장한 파일 경로를 함께 안내한다.
- 사용자가 원하면 장문형 확장 보고서도 같은 `reports/`에 `HTML`로 추가 생성한다.
