---
name: nasdaq-option-analysis
description: QQQ 옵션체인과 가격 데이터를 yfinance로 분석해 요청 시 1회 실행 HTML 리포트를 만들고 reports/ 폴더에 저장하는 스킬. 사용자가 "나스닥 옵션 분석", "QQQ 옵션 분석", "QQQ 옵션체인 보고서"를 요청할 때 사용한다.
---

# 나스닥 옵션 분석 — SKILL

이 스킬은 `QQQ` 전용 옵션 분석 요청을 처리한다.

## 1) 적용 조건
- 사용자가 `나스닥 옵션 분석`, `QQQ 옵션`, `QQQ 옵션체인`, `QQQ 옵션 리포트`를 요청하면 적용한다.
- 출력은 한국어로 작성한다.

## 2) 절대 원칙
- 심볼은 `QQQ`만 사용한다.
- 실행 방식은 **요청 시 1회 실행**이다.
- `while True` 기반 주기 루프를 만들거나 유지하지 않는다.
- 분석 결과 파일은 기본적으로 `reports/`에 `HTML`로 저장한다.
- 보고서 제목은 반드시 `나스닥 옵션 분석`으로 시작한다.
- 시간 표기는 `KST(Asia/Seoul)` 기준으로 맞춘다.

## 3) 데이터 소스
- 기본 소스: `yfinance`
- 가격: `Ticker.history()` 또는 `yf.download("QQQ", ...)`
- 옵션: `Ticker("QQQ").options`, `Ticker("QQQ").option_chain(exp)`
- 필요 시 보조 지표: `^VIX`, `^TNX`, `DX-Y.NYB` (거시 맥락용)

## 4) 실행 워크플로우
1. 요청 확인
- 사용자가 원하는 기간/초점(만기 구조, Max Pain, OI 집중, IV 등)을 파악한다.
- 별도 지시가 없으면 최근 1~3개월 가격 + 최근 만기군 옵션체인을 기준으로 분석한다.

2. 데이터 수집
- `QQQ` 가격, 거래량, 기술 지표 계산에 필요한 시계열을 수집한다.
- 옵션 만기 리스트를 조회하고, 가까운 만기부터 지정 개수(기본 3~5개)를 수집한다.

3. 핵심 지표 계산
- 옵션: Put/Call 비율(Volume, OI), Max Pain, OI 집중 스트라이크, ATM 근처 IV 레벨
- 가격: 추세(이동평균), 변동성(ATR/실현변동성), 기준 레벨(최근 고저/매물대)
- 거시 보조: 필요할 때만 VIX/금리/달러 방향성을 한 줄로 연결

4. 보고서 작성
- 아래 6) 템플릿 구조로 Markdown 보고서를 만든다.
- 마지막 섹션 제목은 반드시 `결론`으로 종료한다.

5. 파일 저장
- 저장 경로: `reports/`
- 권장 파일명:
  - `reports/nasdaq_option_analysis_qqq_YYYYMMDD_HHMMSS_kst.html`
  - 필요 시 보조 이미지: `reports/nasdaq_option_analysis_qqq_YYYYMMDD_HHMMSS_kst.png`

## 5) 예외 처리
- 옵션체인이 비어 있거나 일부 만기가 누락되면:
  - 수집 성공한 만기만 사용한다.
  - 보고서에 `데이터 공백/제약` 항목으로 명시한다.
- 장마감/휴장 시간에는 최신 체결 시각과 데이터 지연 가능성을 같이 적는다.

## 6) 출력 템플릿 (HTML)

```html
<html>
  <head><meta charset="utf-8"><title>나스닥 옵션 분석 (QQQ)</title></head>
  <body>
    <h1>나스닥 옵션 분석 (QQQ)</h1>
    <p>as of (KST): YYYY-MM-DD HH:MM:SS</p>
    <p>데이터 상태: 실시간/지연/전일 종가</p>

    <h2>1. 시장 스냅샷</h2>
    <ul>
      <li>QQQ 현재가, 1D/5D/1M 변화율</li>
      <li>추세/변동성 요약</li>
    </ul>

    <h2>2. 옵션체인 핵심</h2>
    <ul>
      <li>만기별 Put/Call (Volume, OI)</li>
      <li>Max Pain</li>
      <li>OI 집중 스트라이크 상위 N개</li>
      <li>ATM 근처 IV 레벨과 만기 구조</li>
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
