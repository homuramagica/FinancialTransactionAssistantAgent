# 금융 거래 어시스트

## 시장 시황 + 뉴스레터 브리핑
`yfinance`와 지정 FEED를 결합해 시황 분석과 뉴스레터 스타일 산문 브리핑을 생성할 수 있다.

- 실행: `python3 scripts/analyze_market.py --help`
- 추천: `python3 scripts/analyze_market.py --news-style bloomberg --news-paragraphs 10 --out reports/market_newsletter_brief.md`

## 나스닥 옵션 분석 (QQQ, HTML 리포트)
`QQQ` 가격 + 옵션체인을 결합해 요청형 1회 분석 리포트를 생성한다.
출력은 `reports/` 경로의 HTML 파일이며, 3D IV Surface(면), 거래량, MACD, 지표 요약, 용어 가이드를 포함한다.

- 실행: `.venv/bin/python scripts/nasdaq_option_analysis.py --help`
- 추천: `.venv/bin/python scripts/nasdaq_option_analysis.py --period 2y --max-exp 5 --outdir reports`
- 출력 예시: `reports/nasdaq_option_analysis_qqq_YYYYMMDD_HHMMSS_kst.html`
- 필요 패키지(예): `uv pip install --python .venv/bin/python plotly`

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

## 상담 메모리(Always-on)
상담 대화에서 의미 있는 발화(목표/리스크/제약/심리/관심테마)를 자동 추출해
업서트 기반 메모리와 변경 이력(delta)로 관리할 수 있다.

- 실행: `python3 scripts/counsel_memory_cli.py --help`
- 저장소: `portfolio/counsel_memory.sqlite3`, `portfolio/counsel_memory_log.jsonl`
- 답변 준비팩(권장): `python3 scripts/counsel_memory_cli.py prepare-turn --user-text "..."`
- 사용 예시는 `scripts/README.md` 참고

## 외부 세계 메모리(시장 동향 로그)
속보와 분리된 중기 템포의 시장/정치 이슈를 `portfolio/world_issue_log.sqlite3`(기본 저장소)에 누적하고, 필요 시 `world_issue_log.jsonl` 미러와 함께 운영할 수 있다.

- 실행: `python3 scripts/world_memory_cli.py --help`
- 기본 철학: raw article 전문보다 요약형 이슈 메모(`summary`, `story`, `sources`, `portfolio_link`)를 우선 저장
- taxonomy 확인: `python3 scripts/world_memory_cli.py taxonomy --refresh --format md`
- 로그/스키마 가이드: `portfolio/README.md`
- 사용 예시: `scripts/README.md`
