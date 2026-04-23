# AGENTS

이 프로젝트는 금융 정보 습득을 위해 기본적으로 **yfinance API**를 사용한다.

## 문서 미러링 원칙
- `AGENTS.md`와 `CLAUDE.md`는 항상 동일한 내용으로 유지한다.
- 둘 중 하나를 수정할 때는 다른 파일에도 같은 변경을 즉시 반영해 미러링 상태를 유지한다.
- 동기화가 어긋났다면 `CLAUDE.md`를 삭제한 뒤 최신 `AGENTS.md` 전체 내용을 복제해 재생성하는 것을 기본 복구 절차로 사용한다.

## GitHub 공유/커밋 원칙
- 공식 원격 저장소: `https://github.com/homuramagica/FinancialTransactionAssistantAgent`
- 기본 브랜치: `main`
- 빠른 커밋+푸시: `bash scripts/git_quick_commit.sh "커밋 메시지"`
- 위 스크립트는 현재 브랜치 기준으로 `git add -A -> git commit -> git push`를 순서대로 수행한다.
- 공유 제외 파일은 반드시 `.gitignore`를 따른다 (`.venv`, `tmp`, `reports`, `Research`, 개인 로그 등).
- 단, `portfolio/world_issue_log.sqlite3`는 공유 대상이다.

## 동작 원칙
- 기본 데이터 소스는 yfinance이다.
- 실행 환경에 필요한 도구(예: Python, yfinance 등)가 설치되어 있지 않다면, 사용자에게 **설치 여부를 먼저 확인**한 뒤 진행한다.
- 설치가 필요할 때는 가능한 설치 방법(예: pip, uv, venv)을 안내한다.
- yfinance 관련 작업은 `reference/yfinance_reference.md` API 매뉴얼을 참고한다.
- 용어/개념 설명이 필요한 요청에서는 `https://www.investopedia.com`을 우선 검색하고,
  그 다음 초보자 친화적으로 설명한다.
- 초보자 대상/기초 설명 요청이 우선인 경우 `SKILLs/Newbie.md`의 지침을 추가 적용한다.

## 상담 메모리 엔진 (Always-on) 전역 원칙
- 이 규칙은 금융 관련 질의(시장/뉴스/실적/기업/섹터/포트폴리오/매수·매도/투자 감정 표현)에 기본 적용한다.
- 답변 초안 작성 전에 아래 명령으로 개인 메모리 컨텍스트를 먼저 준비한다(기본: ingest 포함).
  - `python3 scripts/counsel_memory_cli.py prepare-turn --user-text "<사용자 최신 발화>" --extractor-mode hybrid --format md`
- `prepare-turn` 실행이 실패하면 아래 순서로 복구 후 1회 재시도한다.
  1. `python3 scripts/counsel_memory_cli.py init`
  2. 동일 `prepare-turn` 명령 재실행
- 사용자가 심리/감정(예: 불안, 억울, 답답, 스트레스)을 표현한 턴은 메모리 반영 여부를 반드시 확인한다.
  - 필요 시 `ingest-turn --dry-run`으로 후보를 점검하고, 누락 시 `ingest-turn`으로 보강한다.
- 기본 추출 모드는 `hybrid`(문맥/의도 패턴 + 키워드 fallback)이며, 디버깅 시에만 `instruction` 또는 `keyword` 단독 모드를 사용한다.
- 상담형 답변 후에는 필요 시 `portfolio_cli.py log-counsel`로 의사결정 로그를 남겨 다음 상담 품질을 높인다.

## 차트 가독성 원칙
- `scripts/portfolio_cli.py chart`로 생성하는 성과 차트는 기본적으로 **좌상단 범례(legend)를 쓰지 않고**, 각 선의 **오른쪽 끝(end-of-line)에 자산 이름 라벨**을 붙인다.
- 라벨은 **흰색 텍스트**를 사용하고, 라벨 박스 배경색은 **해당 선 색상**과 일치시킨다.
- 라벨이 겹치지 않도록 자동 위치 보정(세로 오프셋)을 적용한다.
- 엔드 라벨 표기 형식은 `자산명 (오늘 수익률%) | 총 수익률%`로 하고, 각 수익률은 소수점 둘째 자리까지 표시한다.
- 포트폴리오 본선은 벤치마크보다 두껍게, 벤치마크 자산 선은 더 가는 굵기로 표시한다.
- Y축 범위는 **우측 끝 라벨 값만이 아니라 전체 시계열 고점/저점 + 라벨 보정값**을 함께 반영해 자동 확장한다.
- 차트 PNG 저장 시 `bbox_inches=\"tight\"`와 충분한 패딩을 사용해 상하 라벨/선 잘림을 방지한다.
- `chart` 실행 시 성과 스탯 테이블 PNG를 기본적으로 함께 생성한다.
  - Beta 계산 기준은 기본 `SPY`를 사용한다.
  - 사용자가 요청하면 `^KS11` 등 다른 베타 기준 티커로 변경할 수 있어야 한다.
  - 컬럼: `자산명, Cumulative Return, CAGR, Max Drawdown, Volatility, Sharpe, Sortino, Kelly, Ulcer Index, UPI, Beta`

## 최신 정보 조회 원칙
- 최신 정보를 검색할 때는 아래 FEED들을 모두 함께 사용한다.
- 텔레그램 3개 피드(금융 속보 FEED, 통합 CSV): `https://rss.app/feeds/_8HzGbLlZYpznFQ9I.csv`
  - 텔레그램 피드는 속도가 더 빠르지만 에러가 더 잘 날 수 있다.
- 텔레그램 원본 피드(직접 탐색):
  - `https://t.me/s/WalterBloomberg`
  - `https://t.me/s/FinancialJuice`
  - `https://t.me/firstsquaw`
- 정규 언론 FEED: `https://rss.app/feeds/_hc8HiU0HyBWHfWoM.csv`
- 사용자가 뉴스 업데이트를 요청하면 `SKILLs/NewsRequest.md`를 참조한다.
  - 단, `Axios`, `악시오스`, `Axios식`, `악시오스식` 표현이 함께 포함된 경우에만 아래 `뉴스 기사 수집·요약 원칙 (NewsCollector)`를 우선 적용한다.
- 사용자가 역사적 경제/금융 연구, 장기 시계열 맥락 정리, 자료 조사, 기사 원문 아카이브 구축, 특정 위기/제도/기업 사건 관련 자료 수집을 요청하면 `SKILLs/EconomicsResearch/SKILL.md`를 참조한다.
- 사용자가 시장의 현재 상황에 대 분석/리포트를 요청하면 `SKILLs/MarketAnalysis.md`를 참조한다.
- 사용자가 거시경제 분한석/전망 보고서를 요청하면 `SKILLs/MacroEconomics.md`를 참조한다.
- 사용자가 기업 실적(earnings)을 요청하면 `SKILLs/Earnings.md`를 참조한다.
- 사용자가 기업 종합 분석/투자 리포트/기업 비교/밸류에이션을 요청하면 `SKILLs/CompanyAnalysis/SKILL.md`를 참조한다.
- 사용자가 산업/섹터 분석(섹터 리포트, 섹터 비교, 섹터 로테이션, 섹터 전망)을 요청하면 `SKILLs/SectorAnalysis/SKILL.md`를 참조한다.
- 사용자가 포트폴리오 상담(자산 배분, 섹터 배분, 리밸런싱, 리스크 관리, 라이프사이클 계획)을 요청하면 `SKILLs/PortfolioCounseling/SKILL.md`를 참조한다.
- 사용자가 `나스닥 옵션 분석`(QQQ 옵션체인/QQQ 옵션 리포트)을 요청하면 `SKILLs/NasdaqOptionAnalysis/SKILL.md`를 참조한다.
  - 이 스킬은 `QQQ`만 사용한다.
  - 실행은 **요청 시 1회 실행**이 원칙이며 주기 루프를 사용하지 않는다.
  - 결과물은 기본적으로 `reports/` 경로에 `HTML`로 저장한다. (필요 시 PNG 보조 출력 가능)
- 시장/거시/섹터/기업/포트폴리오 분석형 보고서를 작성할 때는, 관련성이 있는 경우 `python3 scripts/world_memory_cli.py list --days 21 --format md` 또는 `--days 30`을 먼저 조회해 현재 진행 중인 중기 맥락을 내부적으로 파악한다.
  - 단, 월드 메모리와 관련성이 낮은 개별 기업/마이너 업종 분석에서는 이를 본문에 억지로 포함하지 않는다.
  - 월드 메모리는 배경 맥락 파악용으로만 사용하고, 최신 사실 판단과 핵심 근거는 반드시 yfinance, 고신뢰 웹 검색, 공식 자료로 재확인한다.
- **거시경제 분석/전망 보고서도 FEED를 기본적으로 사용한다.**
  - 거시 보고서 기본 소스: `world_issue_log + FEED + yfinance + 웹 검색(고신뢰 출처) + 공식 기관 자료`
  - 보고서 작성 전 `python3 scripts/world_memory_cli.py list --days 30 --format md`를 먼저 실행해 최근 누적 이슈를 확인한다.
  - `world_issue_log`는 성장/물가/고용/정책/금융여건/지정학의 **중기 맥락을 잡는 내부 컨텍스트**로 사용하고, FEED는 최신 변화 탐지에 사용한다. 핵심 사실과 최종 판단은 고신뢰 웹 검색과 1차 자료로 재검증한다.
- 단, **기업분석(기업 종합 분석/투자 리포트/기업 비교/밸류에이션)** 요청도 FEED를 기본적으로 사용한다.
  - 기업분석 기본 소스: `yfinance + FEED + 웹 검색(고신뢰 출처)`
  - 기업분석 보고서 작성 전 `기업 검색(회사/티커/실적/규제)`과 `섹터 검색(업황/정책/수급)`을 각각 수행하고, 두 결과를 통합해 본문을 작성한다.
  - FEED는 최신 헤드라인 탐지용으로 기본 호출하되, 본문 반영 전 고신뢰 웹 검색과 공식 자료로 재확인한다.
- **섹터분석(섹터 리포트/섹터 비교/섹터 로테이션/섹터 전망)도 기업분석과 동일하게 FEED를 기본적으로 사용한다.**
  - 섹터분석 기본 소스: `yfinance + FEED + 웹 검색(고신뢰 출처)`
  - 섹터분석의 웹 검색 출처 우선순위:
    1. 최고 신뢰도: `WSJ`, `FT`, `Bloomberg`
    2. 2차 신뢰도: `MarketWatch`, `Barron's`, `Seeking Alpha`, `FactSet`, `Benzinga`
  - FEED는 최신 흐름 탐지용으로 기본 호출하되, 저장/결론에 반영할 때는 고신뢰 웹 검색으로 재검증한다.
  - 섹터분석 출력에서는 정량지표 외에 뉴스/정책/수급/내러티브 분석 비중을 반드시 포함한다.
- **포트폴리오 상담(자산 배분/섹터 배분/리밸런싱/리스크 관리)도 기업/섹터 분석과 동일하게 FEED를 기본적으로 사용한다.**
  - 포트폴리오 상담 기본 소스: `yfinance + FEED + 웹 검색(고신뢰 출처)`
  - 자산/섹터 배분 최신 정보 취득 시 웹 검색 출처 우선순위는 섹터분석 규칙(`WSJ/FT/Bloomberg` 우선)을 준용한다.
  - 포트폴리오 내 종목 심층 확인은 기업분석의 고신뢰 소스 원칙을 준용한다.
  - FEED는 최신 변화 탐지용으로 기본 호출하되, 핵심 사실과 행동 제안은 고신뢰 웹 검색 및 공식 자료로 재검증한다.
  - 출력에서는 정량지표 외 행동편향/목표/라이프사이클 맥락을 반드시 포함한다.


## 뉴스 기사 수집·요약 원칙 (NewsCollector)
- 이 기능은 일반 최신정보 FEED와 분리된 **전용 수집 경로**로 작동한다.
- 사용자의 요청문에 `Axios`, `악시오스`, `Axios식`, `악시오스식` 중 하나가 포함된 경우에만 이 기능을 발동한다.
- 위 키워드가 없는 일반 뉴스 요청은 기본적으로 `SKILLs/NewsRequest.md` 또는 일반 뉴스/시장 분석 흐름으로 처리한다.
- 출력은 `/NewsUpdate/` 폴더를 사용하며, 일반 보고서처럼 `reports/`에 저장하지 않는다.
- 기사 선별 기준, 오피니언/칼럼 취급, 사용자 취향 가중치, RSS 소스, 본문 수집 방식, 상태 파일, 오류 보고서 형식 등 **운영 상세는 `SKILLs/NewsCollector/SKILL.md`를 단일 기준(source of truth)으로 따른다.**
- 이 문서에는 NewsCollector의 상위 정책만 유지하고, 세부 절차·예시·운영 판단은 `SKILLs/NewsCollector/SKILL.md`에만 둔다.

## 경제/금융 연구 아카이브 원칙 (EconomicsResearch)
- 이 기능은 최신 뉴스 요약과 분리된 **장기 연구용 원문 아카이브 경로**로 작동한다.
- 사용자가 역사적 경제/금융 연구, 자료 조사, 참고문헌/기사 수집, 특정 사건 타임라인 복원, 위기 비교, 제도 변화 추적을 요청하면 이 기능을 우선 적용한다.
- 운영 상세는 `SKILLs/EconomicsResearch/SKILL.md`를 단일 기준(source of truth)으로 따른다.
- 원문 기사 수집 시 유료 매체 접근 방식은 기본적으로 `NewsCollector`의 브라우저 접속 방식을 재사용한다.
  - 기본 경로: `firefox-visible`
  - 폴백 경로: visible Chrome (`chrome`)
  - 브라우저 락, 로그인/페이월 감지 원칙을 그대로 준용한다.
  - 단, 연구 아카이브는 최신 뉴스 요약보다 더 보수적으로 접근하므로 매체 bucket별 접근 간격 기본값을 **15초**로 사용한다.
- 단, 이 기능은 `Axios식 요약`을 만들지 않는다.
  - 출력은 기사 요약본이 아니라 **기사 전문 아카이브용 Markdown 파일**이다.
  - 각 파일에는 최소한 `기사 제목`, `매체명`, `게시 날짜`, `기사 URL`, `수집 시각(KST)`, `본문`이 포함되어야 한다.
- 저장 경로는 `/Research/`다.
  - `/Research/`는 공개 원격 저장소 푸시 대상에서 제외한다.
  - 연구 아카이브 결과물을 `reports/`나 `/NewsUpdate/`에 저장하지 않는다.
- 연구 아카이브는 `world_memory`와 별도 저장소를 사용한다.
  - `world_memory`는 summary-first 중기 메모리다.
  - `EconomicsResearch`는 raw article 중심의 장기 연구 아카이브다.
  - 두 저장소를 섞지 않는다.
  - `EconomicsResearch`에서는 `world_memory`를 기본 소스로 사용하지 않는다.
- 연구 아카이브의 기본 저장소는 `Research/research_archive.sqlite3`다.
  - 기사 카탈로그, 청크 인덱스, 태그, 검색용 임베딩을 별도 관리한다.
  - 임베딩은 현 단계에서 **해시 기반 문자 n-gram 벡터**를 사용한다.
  - 시맨틱 검색은 SQLite 카탈로그와 청크 임베딩을 함께 사용한다.
- 연구 아카이브 구축 시 기본 분류 축은 아래를 우선 사용한다.
  - `topic`: 예) `2008_crisis`, `private_credit`, `great_depression`
  - `theme`: 예) `cdo`, `cds`, `repo`, `liquidity`, `regulation`
  - `entity`: 예) `Bear Stearns`, `Lehman Brothers`, `AIG`, `Basel III`, `Dodd-Frank`
  - `period`: 예) `pre_crisis`, `acute_crisis`, `post_crisis`, `current_echo`
- 장기 연구에서는 FEED와 `world_memory`를 사용하지 않는다.
  - 이 스킬의 기본 소스는 **직접 검색 + 아카이브 검색 + 공식 기관 자료**다.
  - 특히 역사 연구는 `WSJ`, `Bloomberg`, `Barron's`, 공식 기관 자료(Fed, BIS, SEC, Treasury 등)를 함께 사용한다.

## 집필 원고 저장 원칙
- 사용자가 책, 연재물, 에세이, 칼럼, 챕터 초안, 서문/프롤로그, 에필로그, 장별 시놉시스, 문장 중심의 서사형 원고 작성을 요청하면 산출물은 기본적으로 `/Writing/` 경로에 저장한다.
- `/Writing/`은 분석 보고서(`reports/`)나 원문 기사 아카이브(`Research/`)와 구분되는 **저자 작성 원고 전용 폴더**다.
- 경제사·세계사 원고를 집필할 때는 `/Writing/README.md`를 먼저 확인해, 이 시리즈가 반복해 다루는 공통 주제의식과 서술 원칙을 맞춘다.
- 주제별 장기 집필 프로젝트는 `/Writing/` 아래에 별도 하위 폴더를 두고 관리한다.
  - 예: `Writing/Global Financial Crisis/`
- 원고형 산출물은 가능하면 아래 구분을 유지한다.
  - 책 전체 목차/기획안
  - 서문/프롤로그/에필로그 초안
  - 장별 시놉시스
  - 본문 챕터 초안
  - 집필 메모/구성 메모
- `/Writing/`에는 **사용자가 실제로 읽고 다듬을 집필 결과물**을 저장하고, raw article 아카이브나 검색용 DB는 저장하지 않는다.
- 원고 작성 시 참고용 기사·자료 수집은 `EconomicsResearch`를 사용하되, 최종 작성물은 `/Research/`가 아니라 `/Writing/`에 둔다.
  - 최신 FEED 헤드라인이나 월드 메모리 요약만으로 연구 방향을 정하거나 결론을 내리지 않는다.

## 군사 충돌/전쟁 이슈 분류 원칙
- **카테고리 자동 지정**: 군사 충돌 키워드(war, military, strike, attack, missile, drone attack, airstrike, bombing, troops, retaliation, 전쟁, 공격, 폭격, 미사일, 피격, 파병, 증파 등)가 감지되면 `category=geopolitics`로 자동 분류한다.
- **중요도(importance) 판단 기준**:
  - 글로벌 에너지·금융 시스템에 직접 충격을 줄 수 있는 **고강도 분쟁**이 확인되면 `importance=high`로 지정한다.
  - 대표적 고영향 분쟁축(예시): 중동(미-이란, 이스라엘-이란, 걸프), 인도-파키스탄, 중국-대만 등
  - 단, 위 세 축은 예시일 뿐이다. **예상 밖의 충돌**(예: 러시아-나토 직접 교전, 핵 위협 고조 등)이라도 시장 충격 강도가 높으면 `importance=high`로 지정한다.
  - 시장 충격이 제한적이거나 아직 불확실한 분쟁은 `importance=medium`을 기본값으로 하고, 충격이 확인되면 high로 상향한다.
- **스토리 분리 원칙**: 군사 작전·전쟁 자체는 에너지/해운 등 파생 이슈와 **별도의 독립 스토리**로 관리한다.
  - 예: '미-이란 전쟁'(군사 작전·외교·전황)과 '중동 리스크와 에너지 가격'(유가·해운·공급충격)은 각각 독립 스토리로 유지한다.
  - 하나의 엔트리가 양쪽 성격을 모두 가질 경우, **군사 작전이 주된 내용이면 전쟁 스토리에**, 에너지 공급 영향이 주된 내용이면 에너지 스토리에 배정한다.

## 외부 세계 메모리 로그 원칙 (중기 템포)
- 사용자의 개인 로그(심리/가치관)와 별도로, **외부 세계 상태 로그**를 누적한다.
- 목적은 속보 요약이 아니라 **요즘 시장 동향/지속 이슈**의 기억 축적이다.
- 사용자가 `월드 메모리 업데이트 해 줘`, `월드 메모리 업데이트`, `월드 메모리 확보 작업`처럼 짧게 요청하면, 아래 월드 메모리 업데이트 절차 전체를 수행하라는 뜻으로 해석한다.
- `world_memory`는 raw article 전문 저장소가 아니라 **summary-first memory**다.
- 저장 단위는 기본적으로 이슈 요약본(1~2문단)이며, `summary`, `why_it_matters`, `portfolio_link`, `story`, `story_thesis`, `story_checkpoint`, `sources`, `tags`, `tickers`를 우선 채운다.
- raw article 전문은 접근 가능할 때만 선택적으로 보조 저장하며, `world_memory`의 기본 필수값으로 취급하지 않는다.
- 기본 저장 경로: `portfolio/world_issue_log.sqlite3`
- 기본 도구: `scripts/world_memory_cli.py`
- 기존 분류/스토리/태그/티커 사용 현황을 확인할 때는 `python3 scripts/world_memory_cli.py taxonomy --refresh --format md`를 사용한다.
- 로그에 반드시 포함:
  - `as_of`(KST 타임스탬프)
  - `category`: `stock_bond`, `geopolitics`, `emerging`
  - `region`: `US`, `KR`, `GLOBAL`
  - `importance`: `high|medium|low`
  - `sources`(매체명/URL/게시시각)
- **어닝(earnings) 이벤트는 고우선순위로 취급한다.**
  - `event_kind/tags/title/summary`에서 어닝 신호가 감지되면 `importance`는 최소 `medium`으로 상향한다.
  - 가이던스 상·하향, beat/miss, 실적 서프라이즈/쇼크 등 강한 신호는 `importance=high`로 우선 저장한다.
  - `brief` 엔트리에서 어닝 신호가 있고 `category=emerging`인 경우 `category=stock_bond`로 보정해 기업 동향으로 집계한다.
- 외부 세계 메모리 구축 시에는 **FEED를 기본 사용한다.**
  - 기본 소스: `yfinance + FEED + 고신뢰 웹 검색`
  - 영어권 우선 출처: `WSJ`, `FT`, `Bloomberg` (필요 시 2차 신뢰도 확장)
  - 한국 소스 보강: `연합인포맥스(https://news.einfomax.co.kr)`
  - FEED는 빠른 탐지 레이어로 사용하고, 저장 전에는 가능한 한 고신뢰 원출처 또는 정규 언론으로 재확인한다.
  - FEED 단독 헤드라인만으로 저장하거나 결론을 내리지 않는다.
- 분류는 기존 규격(`category`, `region`, `importance`, 기존 `story/tags/tickers`)을 우선 재사용한다.
- 기존 규격으로 의미를 담기 어려울 때만 신규 분류를 최소 단위로 추가하며, 동의어 중복, 일회성 라벨, 과도한 세분화는 지양한다.
- 향후 뉴스 메모리 DB의 entity/event/relation/type/tag 설계에서도 초기 설정된 타입과 사전을 우선 사용하고, 신규 타입은 꼭 필요할 때만 제한적으로 추가한다.
- **월드 메모리 업데이트 절차**:
  - 시작 전에 `python3 scripts/world_memory_cli.py list --days 30 --format md`, `python3 scripts/world_memory_cli.py states --status active --format md`, `python3 scripts/world_memory_cli.py taxonomy --refresh --format md`, `python3 scripts/world_memory_cli.py taxonomy --type state_key --format md`, `python3 scripts/world_memory_cli.py taxonomy --type subject --format md`를 먼저 실행해 최근 로그와 taxonomy를 확인한다.
  - 저장소는 기본적으로 `portfolio/world_issue_log.sqlite3`만 사용한다.
  - 한 번 실행할 때 가장 중요한 1건만 고르지 말고, 의미 있는 `brief`가 여러 개 있으면 가능한 범위에서 `3~8건` 정도 함께 적재한다.
  - 같은 실행에서 동일 `subject`에 과도하게 쏠리지 않도록 하고, 같은 주체는 기본적으로 `최대 2건` 정도로 제한한다.
  - `brief`는 정책 주체, 기업, 기관, 산업 동향이 균형 있게 섞이도록 우선순위를 조정한다.
  - `brief-add` 또는 `brief-import`를 사용할 때는 `subjects`, `industries`, `event_kind`, `dedupe_key`, `sources`를 붙이고 derived state를 만들지 않는다.
  - `brief-import`를 사용할 때는 항상 `.json` 입력만 사용하고 `.jsonl`은 사용하지 않는다.
  - 현재 레짐의 상태 변화나 우세 해석 변화가 확인되면 `add`에 `--state-key`, `--state-label`, `--state-status`, `--state-bias`, `--net-effect`를 함께 사용한다.
  - 같은 `state_key`의 기존 `active/watch` 상태를 명확히 대체하는 경우 `--supersedes-active`를 사용한다.
  - derived state는 모든 `story`에 대해 자동 생성하지 않는다. 기본적으로 동일 story가 `issue` 기준 2건 이상 누적되었거나, 명시적 `state_key`가 있을 때만 레짐 후보로 유지한다.
  - `story_family`는 부모 family를 canonical하게 유지하고, branch 분화는 `story-link` 메모 또는 `story-family-review` 제안으로 별도 관리한다.
  - 트럼프 같은 단일 인물 헤드라인만 반복 저장하지 말고, 정책 주체, 기업, 산업 동향이 균형 있게 섞이도록 유지한다.
- **월드메모리 보고서 모드**는 사용자가 `월드메모리 보고서`(또는 동등한 명시 표현)를 요청한 경우에만 발동한다.
  - 이 경우 `world_issue_log`를 우선 조회하고 부족분만 웹 검색으로 보강한다.
  - 출력은 `미국/한국/글로벌 주식·채권`, `글로벌 정치`, `비지배 관심 이슈`를 분리한다.
- **최근 산업계 동향 모드**는 사용자가 `최근 산업계 동향`(또는 “메가뉴스에 가려진 산업 흐름” 동등 표현)을 요청한 경우 발동한다.
  - 기본 실행 명령: `python3 scripts/world_memory_cli.py report --preset "최근 산업계 동향" --days 30 --out reports/recent_industry_trends_$(date +%F).md`
  - 이 모드는 매크로/메가톤 헤드라인보다 기업·산업의 실행 신호(투자, 생산, 공급망, 자본배분, 조달)를 우선 반영한다.
  - 보고서 제목은 항상 괄호 없이 `최근 산업계 동향`으로 사용한다.
  - 기본 응답은 본문 장문 출력 대신 `reports/` 저장 경로와 핵심 요약만 간단히 안내한다.
- **시장 분석 모드**(예: “요즘 시장 동향 알려줘”, “지금 시장 어때”)에서는 `SKILLs/MarketAnalysis.md`를 기준으로 답변한다.
  - 이때 월드메모리 **별도 보고서**는 작성하지 않는다.
  - 필요하면 `world_issue_log`는 내부 참고용으로만 활용하고, 결과는 시장 분석 본문에 통합한다.
- **거시경제 보고서 모드**(예: “미국 거시경제 보고서”, “유로존 전망 보고서”)에서는 본문 작성 전에 `python3 scripts/world_memory_cli.py list --days 30 --format md`를 먼저 실행한다.
  - 최근 누적 이슈를 성장/물가/고용/정책/금융여건/지정학 축으로 재분류해 거시 본문에 통합한다.
  - 이때 월드메모리 **별도 보고서**는 작성하지 않고, 부족한 부분만 고신뢰 웹 검색과 공식 자료로 보강한다.
- 포트폴리오 상담 시 필요하면 `world_issue_log`를 반영해 리밸런싱/리스크 코멘트를 보강한다.
- 포트폴리오 상담 질문이 `유지할까/계속 투자할까/줄여야 할까/빼야 할까/버틸까` 류이면,
  - 답변 전에 `python3 scripts/world_memory_cli.py list --days 21 --format md`를 먼저 실행해 최근 이슈를 확인한다.
  - 답변 초반에 `as of (KST)` 기준 시각과 반영한 핵심 이슈 1~3개를 명시한다.

## 캘린더(어닝/경제 이벤트) 사용 원칙
- **어닝 캘린더(earnings calendar)** 및 **경제 이벤트 캘린더(economic events calendar)**는 기본적으로 `yfinance.Calendars`를 사용한다.
- 조회/내보내기는 프로젝트의 CLI를 사용한다: `scripts/calendar_cli.py`
- **시간 표기는 항상 UTC+9(서울, `Asia/Seoul`) 기준으로 출력한다.** (옵션으로 변경하지 않는다, 현지 시간을 표시하지 않는다.)
- EVENT 이름은 원문과 함께 괄호() 속에 한국어 번역을 병기한다.

### 실행 예시
- 어닝 캘린더(Markdown): `python3 scripts/calendar_cli.py earnings --start 2026-01-23 --days 14 --limit 50 --format md`
- 경제 이벤트 캘린더(Markdown): `python3 scripts/calendar_cli.py economic --start 2026-01-23 --days 14 --limit 50 --format md`
- 캘린더 임포트용(ICS): `python3 scripts/calendar_cli.py earnings --start 2026-01-23 --days 14 --format ics --out earnings.ics`
- 자세한 옵션/예시는 `scripts/README.md` 참고

## 긴급 안보위기 특별 인스트럭션
- 매우 심각한 안보위기(시장에 큰 영향) 또는 사용자가 안보 관련 질의를 한 경우, 아래 지침에 따라 **추가 부록 보고서**를 제공한다.
- X의 OSINT 최신 정보가 담긴 CSV FEED에 접속해 분석/보고서를 작성한다: `https://rss.app/feeds/_ahZsPeKSyY4dqkqw.csv`
- 출력은 한국어로 작성한다.
- 보고서는 Markdown/List/Table을 적극적으로 사용한다.
- 가능하면 시간을 정확히 표기한다(KST). 시간이 여러 개인 경우 최신 순으로 정렬한다.
- 긴 문장보다 짧고 간단한 문장을 여러 개 사용한다.
- 가장 최신 소식과 가장 치명적인 소식에 가중치를 둔다.
- 최신 소식을 제공하되 전체 맥락을 이해할 수 있도록 요약한다.
- 사용자가 추가 맥락을 요구할 경우에만 웹 검색을 실시한다.
  - 블로그/유튜브 등 신빙성이 낮은 출처는 제외한다.
  - 한국에서 발생한 사건이 아닌 경우 한국 언론 출처는 제외한다.
  - CNN, Bloomberg, WSJ, BBC, Guardian, Washington Post, Nikkei Asia 등 서방권의 신뢰도 높은 언론만 인용한다.


## MacOS에서 작동될 경우 파일 경로 원칙 (macOS NFD 인코딩): 현재 작동환경을 확인하세요.
- macOS는 한글 파일/폴더명을 **NFD(Unicode Normalization Form D, 자모 분해형)**로 저장한다.
- Cowork Linux VM은 파일 접근 시 **NFC(합성형)**로 경로를 처리하므로, 같은 이름처럼 보이지만 **서로 다른 폴더**가 만들어져 사용자 Mac에서 파일이 보이지 않는 문제가 발생한다.
- **읽기·쓰기·복사·이동 등 모든 파일 작업에서 한글 경로는 반드시 NFD로 변환 후 Python으로 처리한다.**
- `Read` / `Write` 도구나 `Bash`의 `cp`/`mv`/`cat` 등으로 직접 한글 경로를 사용하면 NFC로 해석되어 파일을 찾지 못하거나 엉뚱한 위치에 저장될 수 있다.

### 워크스페이스 경로 구하기 (공통 헬퍼)

```python
import os, unicodedata

def get_workspace(session_id: str) -> str:
    """macOS NFD 기준 워크스페이스 절대경로 반환"""
    mnt = f'/sessions/{session_id}/mnt'
    workspace_name = '금융 거래 어시스트'
    for entry in os.listdir(mnt):
        full = os.path.join(mnt, entry)
        # .DS_Store 가 있는 폴더 = macOS 실제 폴더(NFD)
        if os.path.isdir(full) and '.DS_Store' in os.listdir(full):
            if unicodedata.normalize('NFC', entry) == workspace_name:
                return full
    # fallback: 명시적 NFD 변환
    return os.path.join(mnt, unicodedata.normalize('NFD', workspace_name))
```

### 파일 쓰기

```python
import shutil

workspace = get_workspace('세션-ID')  # 위 헬퍼 사용
output_path = os.path.join(workspace, 'reports', '파일명.md')

# 방법 A — 직접 쓰기
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(content)

# 방법 B — 임시 경로에서 복사
shutil.copy2('/sessions/세션-ID/tmp/파일명.md', output_path)
```

### 파일 읽기

```python
workspace = get_workspace('세션-ID')
target = os.path.join(workspace, 'reports', '읽을파일.md')

with open(target, 'r', encoding='utf-8') as f:
    content = f.read()
```

### 폴더 내 파일 목록 조회

```python
workspace = get_workspace('세션-ID')
reports_dir = os.path.join(workspace, 'reports')
files = os.listdir(reports_dir)
```

- **결론: 한글 경로가 포함된 모든 파일 작업(읽기/쓰기/목록 조회/복사/이동)은 반드시 위 헬퍼로 NFD 경로를 구한 뒤 Python으로 처리한다.**
## 응답 마무리 원칙
- 시장/섹터/거시/뉴스/실적/포트폴리오 상담 등 **분석형 답변은 마지막 섹션을 반드시 `결론`으로 마무리**한다.
  - 본문에서 정보를 충분히 제시한 뒤, 최종 행동 관점에서 핵심 판단(현재 레짐/핵심 리스크/우선 체크포인트)을 3~7줄로 요약한다.
- 시장/섹터/거시/뉴스/실적/포트폴리오 상담 등 **보고서 작성 요청은 기본적으로 `reports/` 경로에 `.md` 파일로 생성**한다.
  - **단, `SKILLs/NewsCollector/SKILL.md`를 통해 수집·요약된 뉴스 기사 파일은 예외이며, 반드시 `/NewsUpdate/` 폴더에 저장한다.**
  - **단, `SKILLs/EconomicsResearch/SKILL.md`를 통해 수집된 원문 기사/연구 아카이브는 예외이며, 반드시 `/Research/` 경로에 저장한다.**
  - **단, 책/연재/에세이/챕터/서문/에필로그 등 집필 원고는 예외이며, 반드시 `/Writing/` 경로에 저장한다.**
  - NewsCollector 결과물을 `reports/`에 저장하거나, 반대로 일반 보고서를 `/NewsUpdate/`에 저장해서는 안 된다.
  - EconomicsResearch 결과물을 `reports/`나 `/NewsUpdate/`에 저장해서는 안 된다.
  - 집필 원고를 `reports/`, `/NewsUpdate/`, `/Research/`에 저장해서는 안 된다.
  - 기본 응답은 파일 저장 경로, 핵심 요약, 필요 시 다음 액션만 짧게 안내한다.
  - 사용자가 명시적으로 원할 때만 일반 채팅 본문으로 장문 보고서를 직접 출력한다.
  - 다른 스킬/도구가 HTML, PNG, PDF 등 별도 산출물을 필수로 요구하는 경우에는 그 형식을 우선하되, 가능하면 함께 `.md` 요약본도 제공한다.
- 보고서 생성/제안 문구는 `SKILLs/CompanyAnalysis/SKILL.md`를 참고해 작성한다고 명시한다.
- 보고서 생성 또는 마무리 제안 문구에는 아래 요소를 포함한다.
  - 파일 생성 위치 예시(예: `reports/` 경로)
  - 포함 항목 예시(사업 구조, 실적, 밸류에이션, 리스크, 투자 시나리오)
  - 사용자가 즉시 진행 여부를 답할 수 있는 짧은 콜투액션
