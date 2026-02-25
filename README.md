# 금융 거래 어시스트

## 시장 시황 + 뉴스레터 브리핑
`yfinance`와 지정 FEED를 결합해 시황 분석과 뉴스레터 스타일 산문 브리핑을 생성할 수 있다.

- 실행: `python3 scripts/analyze_market.py --help`
- 추천: `python3 scripts/analyze_market.py --news-style bloomberg --news-paragraphs 10 --out reports/market_newsletter_brief.md`

## 캘린더(어닝/경제 이벤트)
`yfinance.Calendars` 기반으로 **어닝 캘린더 / 경제 이벤트 캘린더**를 조회하고 내보낼 수 있다.

- 가상환경 미활성화 상태에서는 `python3` 대신 `.venv/bin/python` 사용 권장
- 실행: `python3 scripts/calendar_cli.py --help`
- 사용 예시는 `scripts/README.md` 참고

## 포트폴리오 관리
`portfolio/` 폴더에 사용자 포트폴리오 이력을 기록하고, 누적수익률을 계산/시각화할 수 있다.

- 실행: `python3 scripts/portfolio_cli.py --help`
- 로그 가이드: `portfolio/README.md`
- 필수 패키지: `yfinance`, `pandas`, `matplotlib` (`requirements.txt`)

## 외부 세계 메모리(시장 동향 로그)
속보와 분리된 중기 템포의 시장/정치 이슈를 `portfolio/world_issue_log.sqlite3`(기본 저장소)에 누적하고, 필요 시 `world_issue_log.jsonl` 미러와 함께 운영할 수 있다.

- 실행: `python3 scripts/world_memory_cli.py --help`
- 로그/스키마 가이드: `portfolio/README.md`
- 사용 예시: `scripts/README.md`
