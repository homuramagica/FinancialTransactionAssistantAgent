# Research Archive Schema

## 1) 저장 대상
- 기사 원문 Markdown 파일
- 기사 카탈로그(SQLite)
- 기사 청크별 검색 인덱스
- 태그

## 2) SQLite 기본 테이블
- `articles`
  - `article_id`
  - `source`
  - `title`
  - `url`
  - `published_at`
  - `retrieved_at_kst`
  - `file_path`
  - `content_hash`
  - `metadata_json`
- `article_chunks`
  - `chunk_id`
  - `article_id`
  - `chunk_index`
  - `text`
  - `embedding_json`
- `article_tags`
  - `article_id`
  - `tag`

## 3) 검색 방식
- 1차: SQLite 카탈로그 필터
- 2차: 기사 청크 단위 해시 기반 문자 n-gram 코사인 유사도
- 3차: 키워드 중첩 점수
- 가능하면 FTS5 보너스를 추가한다.

## 4) 파일 포맷
기본 Markdown 구조:

```markdown
# 기사 제목

- Source: ...
- Published At: ...
- Retrieved At (KST): ...
- URL: ...

## Article Body

...
```

## 5) 추천 태그 축
- 위기/시대: `2008_crisis`, `great_depression`, `eurozone_crisis`
- 메커니즘: `cdo`, `cds`, `repo`, `liquidity`, `funding`, `securitization`
- 기관: `lehman`, `bear_stearns`, `aig`, `fed`, `sec`
- 정책: `dodd_frank`, `basel_iii`, `volcker_rule`, `tarp`, `qe`
- 현재 연결: `private_credit`, `shadow_banking`, `covenant_lite`

## 6) 연구 프로젝트 예시
- `2008_crisis`
- `private_credit`
- `japan_bubble`
- `great_depression`
