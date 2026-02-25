# 출력 템플릿 모음 (산업/섹터 분석)

## 1) KR Broker Sector PDF-style Cover (표지형 1페이지)

```markdown
## [리포트 유형] [시장/섹터명] 섹터 리포트
as of YYYY-MM-DD HH:MM KST

### 한 줄 테제
- ...

| 구분 | 값 | 코멘트 |
| --- | ---: | --- |
| 섹터 의견 | Overweight/Neutral/Underweight | ... |
| 벤치마크 | SPY 또는 ... | ... |
| 핵심 기간 성과 | 1M/3M/6M/12M | ... |
| 상대강도 | ... | ... |

### Top Picks
| 종목 | 투자의견 | 목표가 | 핵심 이유 |
| --- | --- | ---: | --- |
| ... | Buy | ... | ... |
| ... | Buy | ... | ... |

### 핵심 드라이버 (3개)
1. 팩트: ... / 해석: ... / 영향: ...
2. 팩트: ... / 해석: ... / 영향: ...
3. 팩트: ... / 해석: ... / 영향: ...

### Why now
- 지금 레짐이 바뀌는 이유:
```

## 2) KR Broker Sector PDF-style Full Report

```markdown
## 1. 산업 근거 상세
### 1) 공급
- ...
### 2) 수요
- ...
### 3) 가격/재고/CAPA
- ...

## 2. 섹터 성과/상대강도
| 섹터 | 1M | 3M | YTD | SPY 대비 | 코멘트 |
| --- | ---: | ---: | ---: | ---: | --- |
| XLK | ... | ... | ... | ... | ... |
| XLE | ... | ... | ... | ... | ... |

## 3. 하위산업/대표기업 비교
| 구분 | 성장 | 수익성 | 밸류 | 모멘텀 | 코멘트 |
| --- | ---: | ---: | ---: | ---: | --- |
| 하위산업 A | ... | ... | ... | ... | ... |
| 하위산업 B | ... | ... | ... | ... | ... |

## 4. 수급/정책/내러티브
| 항목 | 현재 변화 | 섹터 영향 | 중요도 |
| --- | --- | --- | --- |
| 금리 | ... | ... | High/Med/Low |
| 정책 | ... | ... | High/Med/Low |
| 원자재 | ... | ... | High/Med/Low |

## 5. 시나리오
- Baseline: ... (조건: ...)
- Upside: ... (트리거: ...)
- Downside: ... (트리거: ...)

## 6. 리스크/체크포인트
| 리스크 | 확률 | 영향 | 대응/완화 조건 |
| --- | --- | --- | --- |
| ... | High/Med/Low | High/Med/Low | ... |

## 결론
- 현재 우위 섹터:
- 핵심 리스크:
- 우선 체크포인트:

## 부록: 데이터 한계/컴플라이언스
- 본 자료는 투자 자문이 아닌 정보 제공 목적.
- 데이터 소스 지연/누락 가능성 존재.
```

## 3) Flash Layer (기본)

```markdown
### [시장/국가] 섹터 분석 요약
as of YYYY-MM-DD HH:MM KST

**한 줄 결론**
- ...

| 섹터 | 1M | 3M | YTD | SPY 대비 | 코멘트 |
| --- | ---: | ---: | ---: | ---: | --- |
| XLK | ... | ... | ... | ... | ... |
| XLE | ... | ... | ... | ... | ... |

**핵심 드라이버(3~5개)**
1. ...
2. ...
3. ...

**시나리오**
- Baseline: ...
- Upside: ... (트리거: ...)
- Downside: ... (트리거: ...)

## 결론
- ...
```

## 4) WSJ-style Quick Note

```markdown
### Sector Quick Note (WSJ-style)
as of YYYY-MM-DD HH:MM KST

**Thesis**
- ...

**Why Now**
1. ...
2. ...
3. ...

**Counter-argument**
- ...

## 결론
- 강세/약세 전환 트리거:
```

## 5) FT-style Valuation Note

```markdown
### Sector Valuation Note (FT-style)
as of YYYY-MM-DD HH:MM KST

**핵심 쟁점**
- ...

| 항목 | 현재 | 역사범위 | 해석 |
| --- | ---: | ---: | --- |
| Forward P/E | ... | ... | ... |
| 마진 사이클 | ... | ... | ... |

**Consensus vs Variant**
- 컨센서스: ...
- 차별화 관점: ...

## 결론
- 리레이팅 조건:
- 디레이팅 조건:
```

## 6) FactSet-style Earnings Scoreboard

```markdown
### Earnings Scoreboard (FactSet-style)
as of YYYY-MM-DD HH:MM KST

| 섹터 | EPS 성장률 | 매출 성장률 | Beat 비율 | 가이던스 상향 비율 | 코멘트 |
| --- | ---: | ---: | ---: | ---: | --- |
| ... | ... | ... | ... | ... | ... |

**Top 3 Positive Revisions**
1. ...
2. ...
3. ...

**Top 3 Negative Revisions**
1. ...
2. ...
3. ...

## 결론
- 이번 시즌 승자/패자:
```

## 7) 공통 마무리 문구 (필수)

분석형 답변의 마지막에는 아래 제안을 붙인다.

```markdown
원하시면 `SKILLs/CompanyAnalysis/SKILL.md` 기준의 장문 보고서 구조를 준용해 파일로 생성해드릴 수 있습니다.
예: `reports/[섹터명]_sector_report_YYYYMMDD.md`
포함 항목: 섹터 구조, 실적, 밸류에이션, 리스크, 투자 시나리오
지금 바로 파일 생성할까요?
```
