---
name: economics-research
description: 경제사/금융사 연구, 위기 타임라인 복원, 제도 변화 추적, 기사 원문 아카이브 구축을 위한 스킬. 사용자가 역사적 경제·금융 연구, 자료 조사, 참고 기사 수집, 특정 위기/규제/금융상품 관련 원문 아카이브, 장기 리서치용 자료 정리를 요청할 때 사용한다.
---

# EconomicsResearch (경제/금융 연구 아카이브 스킬)

## 1) 목표
- 장기 연구용 **원문 기사 아카이브**를 구축한다.
- 최신 뉴스 요약이 아니라, 나중에 집필과 비교 연구에 재사용할 수 있는 **자료 코퍼스**를 만든다.
- 기사, 규제 문서, 기관 보고서, 제도 변화 자료를 한 저장소로 묶고 검색 가능하게 만든다.
- 결과는 `/Research/`와 `Research/research_archive.sqlite3`에 축적한다.

## 2) 절대 원칙
- 이 스킬은 `FEED`와 `world_memory`를 기본 소스로 사용하지 않는다.
- 이 스킬의 기본 소스는 **직접 검색 + 아카이브 검색 + 공식 기관 자료**다.
- 최신 뉴스 요약용 `NewsCollector`와 목적이 다르므로 `Axios식 요약`을 만들지 않는다.
- 유료 매체 접근 방식만 `NewsCollector`에서 재사용한다.
  - 기본 경로: Chrome DevTools (`chrome`)
  - 1차 폴백: `chrome-visible`
  - 2차 폴백: `firefox-visible`
  - 브라우저 락, 로그인/페이월 감지 원칙을 그대로 준용한다.
  - 단, 연구 아카이브에서는 봇 탐지 회피를 위해 매체 bucket별 접근 간격 기본값을 **15초**로 둔다.
- 수집 산출물은 `reports/`나 `/NewsUpdate/`가 아니라 반드시 `/Research/`에 저장한다.
- `/Research/`는 공개 원격 저장소 푸시 대상에서 제외한다.
- `world_memory` DB와 연구 아카이브 DB는 섞지 않는다.
- 연구 아카이브의 검색 인덱스는 현 단계에서 **해시 기반 문자 n-gram 벡터**를 사용한다.

## 3) 언제 이 스킬을 쓰는가
아래 요청에서는 이 스킬을 우선 적용한다.

| 요청 유형 | 예시 |
| --- | --- |
| 경제사/금융사 연구 | "2008 금융위기 자료 모아줘", "대공황 리서치해줘" |
| 사건 타임라인 복원 | "베어스턴스부터 리먼까지 기사로 정리할 자료를 모아줘" |
| 제도 변화 추적 | "도드-프랭크, 바젤3 관련 기사와 자료를 모아줘" |
| 구조적 원인 분석 | "CDO, CDS, SIV, repo 자금조달 관련 옛 기사 모아줘" |
| 현재와의 연결 | "사모신용 위기와 2008년 공통점 자료를 찾고 싶어" |
| 원문 아카이브 구축 | "WSJ/Bloomberg 기사 전문을 모아서 보관해줘" |

## 4) 기본 저장소 구조
- 기사 Markdown: `/Research/`
- 카탈로그 DB: `Research/research_archive.sqlite3`
- 기사 1건 = Markdown 파일 1개
- 검색 단위 = 기사 청크(chunk)

각 기사 파일에는 최소한 아래 항목이 포함되어야 한다.

1. 기사 제목
2. 매체명
3. 게시 날짜
4. 기사 URL
5. 수집 시각(KST)
6. 기사 본문

## 5) 데이터 소스 우선순위
1. 직접 웹 검색
   - `WSJ`, `Bloomberg`, `Barron's`
   - 필요 시 `FT`, `Reuters`, `NYT`, `The Economist`
2. 공식 기관 자료
   - `Federal Reserve`
   - `U.S. Treasury`
   - `SEC`
   - `FDIC`
   - `BIS`
   - `Basel Committee`
   - `IMF`
   - `FOMC` 의사록/연설/보고서
3. 보조 소스
   - 학술 논문
   - 회고 인터뷰
   - 의회 청문회 자료

제외 또는 후순위 원칙:
- FEED 기반 속보
- `world_memory`
- 블로그/유튜브/출처 불명 커뮤니티

## 6) 연구 쿼리 설계 원칙
역사 연구는 한 번에 넓게 긁지 말고, 아래 축으로 쪼개서 직접 검색한다.

1. 메커니즘 축
   - `CDO`, `CDS`, `MBS`, `SIV`, `repo`, `haircut`, `liquidity backstop`
2. 기관 축
   - `Bear Stearns`, `Lehman Brothers`, `Merrill Lynch`, `AIG`, `Fannie Mae`, `Freddie Mac`, `Citigroup`
3. 정책 축
   - `TARP`, `QE`, `stress test`, `Volcker Rule`, `Dodd-Frank`, `Basel III`
4. 현재 연결 축
   - `private credit`, `direct lending`, `shadow banking`, `liquidity mismatch`, `covenant-lite`
5. 시기 축
   - `pre_crisis`
   - `early_cracks`
   - `acute_crisis`
   - `reform_period`
   - `current_echo`

## 7) 직접 검색 패턴
아래처럼 `매체 + 핵심 키워드 + 시기`를 묶는다.

- `site:wsj.com CDO 2005 structured finance`
- `site:bloomberg.com Bear Stearns repo funding 2008`
- `site:barrons.com Dodd-Frank bank regulation 2010`
- `site:bis.org Basel III liquidity coverage ratio pdf`
- `site:federalreserve.gov AIG Maiden Lane speech pdf`

검색은 보통 아래 4개 레인으로 분리하는 편이 좋다.

1. 사건 기사
2. 메커니즘 설명 기사
3. 정책/규제 기사
4. 현재와의 연결 기사

## 8) 수집 워크플로우
1. 연구 질문을 `사건/메커니즘/정책/현재 연결`로 분해한다.
2. 직접 검색으로 기사 후보를 찾는다.
3. 유료 매체 기사는 `NewsCollector`와 동일한 접근 경로로 본문을 확보한다.
4. 확보한 본문을 `/Research/`에 Markdown으로 저장한다.
5. `scripts/research_archive_cli.py`로 SQLite 카탈로그와 청크 인덱스를 갱신한다.
6. 같은 URL 또는 같은 사건의 중복 기사를 정리한다.
7. 쌓인 자료를 바탕으로 타임라인/주제별 검색을 반복한다.

## 9) CLI 사용 기본 예시
초기화:

```bash
python3 scripts/research_archive_cli.py init
```

유료 매체 기사 1건 수집 + 저장 + 인덱싱:

```bash
python3 scripts/research_archive_cli.py fetch-url \
  --url "https://www.bloomberg.com/..." \
  --tag 2008_crisis \
  --tag cdo \
  --tag pre_crisis
```

기존 Markdown 파일 인덱싱:

```bash
python3 scripts/research_archive_cli.py ingest-md \
  --file "Research/2008-09-15 Bloomberg ... .md" \
  --tag lehman
```

시맨틱 검색:

```bash
python3 scripts/research_archive_cli.py search \
  --query "AIG CDS collateral trigger" \
  --limit 10 \
  --format md
```

## 10) 출력 파일 형식
기본 형식은 아래와 같다.

```markdown
# 기사 제목

- Source: Bloomberg
- Published At: 2008-09-15T00:00:00Z
- Retrieved At (KST): 2026-04-14T22:10:00+09:00
- URL: https://...

## Article Body

기사 본문...
```

## 11) 태그/분류 원칙
기본 태그 축:
- 주제: `2008_crisis`, `private_credit`, `great_depression`
- 메커니즘: `cdo`, `cds`, `repo`, `liquidity`, `leverage`
- 기관: `bear_stearns`, `lehman`, `aig`, `fed`, `treasury`
- 시기: `pre_crisis`, `acute_crisis`, `post_crisis`, `current_echo`

처음부터 너무 세분화하지 말고, 재사용 가능한 태그만 남긴다.

## 12) 품질 게이트
- 기사 제목, 날짜, URL이 빠지지 않았는가
- 본문이 충분히 확보되었는가
- 유료 매체 접근 오류를 본문 부재와 구분했는가
- 같은 기사 URL이 중복 저장되지 않았는가
- 태그가 지나치게 일회성/임시적이지 않은가
- 연구 질문과 연결되는 축(사건/메커니즘/정책/현재 연결)이 명확한가

## 13) 2008 금융위기 연구에 특히 유용한 수집 레일
- 서브프라임 대출 확산
- 구조화금융(CDO, CDO-squared, CDS)
- SIV와 은행 바깥 위험 이전
- 베어스턴스 헤지펀드 붕괴
- 리먼 파산과 자금시장 경색
- AIG 구제금융과 담보 콜
- 메릴린치/BOA 거래
- 머니마켓펀드 흔들림과 상업어음 시장
- TARP, QE, 스트레스테스트
- 도드-프랭크와 바젤3
- 현재의 private credit / shadow banking과의 연결

## 14) 참조 문서
- 스키마/태그 설계: `references/archive_schema.md`
