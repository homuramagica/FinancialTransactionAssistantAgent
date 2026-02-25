# 웹 리서치 소스 맵 (포트폴리오 상담)

업데이트 기준일: 2026-02-16

## 데이터/API 기준
- yfinance Ticker API  
  https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.html
- yfinance download API  
  https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html
- yfinance Sector API  
  https://ranaroussi.github.io/yfinance/reference/api/yfinance.Sector.html
- yfinance Industry API  
  https://ranaroussi.github.io/yfinance/reference/api/yfinance.Industry.html
- yfinance EquityQuery/screen  
  https://ranaroussi.github.io/yfinance/reference/api/yfinance.EquityQuery.html  
  https://ranaroussi.github.io/yfinance/reference/api/yfinance.screen.html

## 핵심 이론(개념 설명 우선: Investopedia)
- Modern Portfolio Theory (MPT)  
  https://www.investopedia.com/terms/m/modernportfoliotheory.asp
- Kelly Criterion  
  https://www.investopedia.com/terms/k/kellycriterion.asp
- Black-Litterman Model  
  https://www.investopedia.com/terms/b/black-litterman_model.asp
- Risk Parity  
  https://www.investopedia.com/terms/r/risk-parity.asp
- Conditional Value at Risk (CVaR)  
  https://www.investopedia.com/terms/c/conditional_value_at_risk.asp
- Behavioral Finance  
  https://www.investopedia.com/terms/b/behavioralfinance.asp
- Life-Cycle Funds / Life-Cycle Investing  
  https://www.investopedia.com/terms/l/lifecyclefund.asp

## 자산/섹터 배분용 고신뢰 소스 (웹 검색 우선순위)
- 최고 신뢰도:
  - Bloomberg Markets  
    https://www.bloomberg.com/markets
  - WSJ Markets  
    https://www.wsj.com/news/markets
  - FT Markets  
    https://www.ft.com/markets
- 2차 신뢰도:
  - MarketWatch  
    https://www.marketwatch.com/
  - Barron's  
    https://www.barrons.com/
  - Seeking Alpha (Market News)  
    https://seekingalpha.com/market-news
  - FactSet Insight  
    https://insight.factset.com/
  - Benzinga Markets  
    https://www.benzinga.com/markets

## 한국 보강 소스
- 연합인포맥스  
  https://news.einfomax.co.kr

## 외부 세계 메모리 로그 (중기 동향)
- 로그 파일: `portfolio/world_issue_log.jsonl`
- CLI: `scripts/world_memory_cli.py`
- 목적: 속보가 아닌 시장 동향/정치 이슈/관심 이슈의 누적 기억

## 속보/실시간 업데이트 FEED (명시 요청 시만)
- 통합 FEED:
  - https://rss.app/feeds/_8HzGbLlZYpznFQ9I.csv
  - https://rss.app/feeds/_hc8HiU0HyBWHfWoM.csv
- 텔레그램 원본:
  - https://t.me/s/WalterBloomberg
  - https://t.me/s/FinancialJuice
  - https://t.me/firstsquaw
