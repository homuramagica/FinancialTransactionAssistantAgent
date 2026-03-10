#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_TZ = "Asia/Seoul"
DEFAULT_DB_PATH = "portfolio/counsel_memory.sqlite3"
DEFAULT_JSONL_LOG_PATH = "portfolio/counsel_memory_log.jsonl"

EMBED_DIM = 384
SIM_REINFORCE = 0.88
SIM_UPDATE = 0.72
SIM_KEY_STANCE_REINFORCE = 0.35
SIM_KEY_REINFORCE = 0.45
HIGH_IMPORTANCE = 0.82
PROMOTE_AFTER = 2

TOKEN_RE = re.compile(r"[A-Za-z0-9가-힣]{2,}")
TICKER_RE = re.compile(r"(?:\^[A-Z]{2,6}|[A-Z]{1,5}(?:\.[A-Z])?)")

TICKER_STOPWORDS = {
    "USD",
    "KRW",
    "KST",
    "UTC",
    "ETF",
    "CLI",
    "JSON",
    "CSV",
    "NAV",
    "BUY",
    "SELL",
    "AND",
    "THE",
    "FOR",
    "WITH",
}

GOAL_KEYWORDS = [
    "목표",
    "은퇴",
    "노후",
    "학비",
    "주택",
    "내 집",
    "goal",
    "retire",
    "retirement",
    "financial freedom",
]

RISK_KEYWORDS = [
    "리스크",
    "위험",
    "변동성",
    "낙폭",
    "손실",
    "drawdown",
    "risk",
    "volatility",
]

CONSTRAINT_KEYWORDS = [
    "세금",
    "tax",
    "유동성",
    "현금",
    "cash need",
    "대출",
    "부채",
    "기간",
    "time horizon",
    "생활비",
    "원금",
    "제약",
]

ALLOCATION_KEYWORDS = [
    "비중",
    "리밸런싱",
    "리밸런스",
    "매수",
    "매도",
    "유지",
    "줄여",
    "늘려",
    "축소",
    "확대",
    "편입",
    "제외",
    "교체",
    "rebalance",
    "allocation",
    "increase",
    "decrease",
    "hold",
]

REGIME_KEYWORDS = [
    "시장",
    "레짐",
    "금리",
    "물가",
    "경기",
    "risk-on",
    "risk-off",
    "bull",
    "bear",
    "관세",
    "fomc",
    "cpi",
    "pce",
]

EMOTION_KEYWORDS = [
    "불안",
    "걱정",
    "무섭",
    "답답",
    "스트레스",
    "억울",
    "속상",
    "서운",
    "짜증",
    "화나",
    "열받",
    "빡치",
    "우울",
    "기분",
    "감정",
    "멘탈",
    "지친",
    "anxious",
    "nervous",
    "frustrated",
    "stressed",
    "confident",
    "확신",
]

PERSONAL_CONTEXT_KEYWORDS = [
    "가족",
    "아이",
    "육아",
    "결혼",
    "이사",
    "직장",
    "퇴사",
    "사업",
    "건강",
    "병원",
    "월급",
    "보너스",
    "연봉",
]

PREFERENCE_KEYWORDS = [
    "쉽게",
    "초보",
    "짧게",
    "길게",
    "표로",
    "차트로",
    "한국어",
    "영어",
    "핵심만",
    "디테일",
    "추천",
    "뭐 하는게 좋",
    "뭐가 좋",
    "what should i do",
    "how should i",
]

RULE_KEYWORDS = [
    "기준",
    "트리거",
    "룰",
    "원칙",
    "규칙",
    "if ",
    " then ",
    "손절",
    "익절",
]

THEME_KEYWORDS: dict[str, list[str]] = {
    "ai": ["ai", "인공지능", "llm", "gpu", "nvda", "amd"],
    "semiconductors": ["반도체", "semiconductor", "chip", "tsm", "avgo"],
    "software": ["software", "saas", "클라우드", "cloud"],
    "healthcare": ["헬스케어", "healthcare", "바이오", "pharma", "제약"],
    "dividend": ["배당", "dividend", "schd", "vym", "jepi"],
    "rates_macro": ["금리", "채권", "fomc", "cpi", "pce", "duration"],
    "geopolitics": ["지정학", "중동", "관세", "미중", "전쟁", "geopolitic", "tariff"],
}

FINANCE_KEYWORDS = [
    "주식",
    "종목",
    "포트폴리오",
    "비중",
    "리밸런싱",
    "금리",
    "채권",
    "환율",
    "인플레이션",
    "cpi",
    "pce",
    "fomc",
    "earnings",
    "valuation",
    "sector",
    "economy",
    "macro",
    "risk-on",
    "risk-off",
    "시장",
    "섹터",
    "경제",
    "거시",
    "투자",
    "매수",
    "매도",
]

EXTRACTOR_MODE_DEFAULT = "hybrid"
EXTRACTOR_MODES = {"hybrid", "instruction", "keyword"}

INSTRUCTION_RISK_PATTERNS = [
    r"-?\d+%?.{0,8}(하락|낙폭|손실).{0,12}(못\s*버티|버틸|감당)",
    r"(변동성|리스크|위험).{0,12}(부담|힘들|싫|낮추|줄이)",
]

INSTRUCTION_CONSTRAINT_PATTERNS = [
    r"(현금|생활비|세금|대출|부채|유동성|원금).{0,16}(필요|부담|제약|문제|우선)",
    r"(기간|시간).{0,12}(제약|부족|없|짧)",
]

INSTRUCTION_ALLOCATION_PATTERNS = [
    r"(비중|포지션|보유).{0,16}(유지|줄|늘|축소|확대|리밸런싱)",
    r"(들고\s*가|계속\s*보유|홀드|hold|trim|reduce|add)",
]

INSTRUCTION_REGIME_PATTERNS = [
    r"(시장|레짐|거시|매크로).{0,20}(상황|분위기|전망|흐름)",
    r"(금리|물가|관세|경기).{0,20}(영향|걱정|우려|불확실)",
]

INSTRUCTION_EMOTION_PATTERNS = [
    r"(감정|기분).{0,12}(들|드|난|나|느껴|이다|이야|임)",
    r"(마음|멘탈).{0,12}(흔들|힘들|버겁|지치|복잡)",
    r"(불안|걱정|무섭|스트레스|anxious|nervous|frustrated|stressed)",
    r"(억울|속상|서운|답답|짜증|화나|열받|빡치|우울)",
]

INSTRUCTION_PERSONAL_CONTEXT_PATTERNS = [
    r"(가족|아이|육아|결혼|이사|직장|퇴사|사업|건강|병원|월급|보너스|연봉).{0,16}(때문|영향|문제|계획)",
]

INSTRUCTION_PREFERENCE_PATTERNS = [
    r"(쉽게|짧게|길게|표로|차트로|핵심만|디테일).{0,12}(설명|정리|알려)",
    r"(한국어|영어).{0,12}(설명|답변|정리)",
]

INSTRUCTION_ADVISORY_PATTERNS = [
    r"(해야\s*되나|해야\s*하나|해도\s*될까|맞나|맞아\?|어떻게\s*하지|어떡하)",
    r"(keep|hold|sell|trim|reduce|add).{0,20}\?",
]

INSTRUCTION_RULE_PATTERNS = [
    r"(기준|원칙|룰|트리거).{0,16}(은|는|:)",
    r"(하면|되면).{0,16}(하겠|줄이겠|늘리겠|판다|산다|매도|매수)",
    r"(분기|월|주).{0,12}(리밸런싱|점검)",
]

INSTRUCTION_STYLE_PATTERNS = [
    r"\d+\s*종목.{0,20}(패시브|분산|인덱스|장기)",
    r"(패시브|인덱스).{0,20}(투자|전략|운용)",
    r"(장기|분산).{0,20}(투자|보유|전략)",
]


@dataclass(frozen=True)
class MemoryCandidate:
    memory_type: str
    memory_key: str
    text: str
    importance: float
    confidence: float
    stance: str
    tickers: list[str]
    ttl_days: int | None
    metadata: dict[str, Any]


def _kst_now() -> dt.datetime:
    return dt.datetime.now(tz=ZoneInfo(DEFAULT_TZ))


def _read_optional_text(text: str | None, file_path: str | None, *, required: bool = False) -> str:
    if text and file_path:
        raise SystemExit("Choose one of --*-text or --*-file")
    if file_path:
        path = Path(file_path)
        if not path.exists():
            raise SystemExit(f"File not found: {path}")
        return path.read_text(encoding="utf-8")
    out = text or ""
    if required and not out.strip():
        raise SystemExit("Required text is empty")
    return out


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_lower(text: str) -> str:
    return _normalize_spaces(text).lower()


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        token = str(item).strip()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _contains_any(text_lower: str, keywords: list[str]) -> bool:
    return any(k.lower() in text_lower for k in keywords)


def _extract_tickers(text: str, *, limit: int = 8) -> list[str]:
    found = TICKER_RE.findall(text.upper())
    out: list[str] = []
    for raw in found:
        token = raw[1:] if raw.startswith("^") else raw
        if token in TICKER_STOPWORDS:
            continue
        if len(token) < 1:
            continue
        out.append(token)
    dedup = []
    seen: set[str] = set()
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        dedup.append(t)
    return dedup[:limit]


def _token_set(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text)}


def _keyword_overlap_score(query: str, memory: str) -> float:
    qa = _token_set(query)
    mb = _token_set(memory)
    if not qa or not mb:
        return 0.0
    inter = len(qa & mb)
    denom = max(1, min(len(qa), len(mb)))
    return inter / float(denom)


def _char_ngrams(text: str, min_n: int = 2, max_n: int = 4) -> list[str]:
    normalized = _normalize_lower(text)
    if not normalized:
        return []
    chars = list(normalized)
    out: list[str] = []
    for n in range(min_n, max_n + 1):
        if len(chars) < n:
            continue
        for i in range(0, len(chars) - n + 1):
            ngram = "".join(chars[i : i + n])
            if ngram.strip():
                out.append(ngram)
    return out


def _stable_hash_index(token: str, dim: int) -> tuple[int, float]:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, "big", signed=False)
    idx = value % dim
    sign = -1.0 if (value & 1) else 1.0
    return idx, sign


def _embed_text(text: str, *, dim: int = EMBED_DIM) -> list[float]:
    vec = [0.0] * dim
    for token in _char_ngrams(text):
        idx, sign = _stable_hash_index(token, dim)
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0:
        return vec
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def _best_sentence(text: str, keywords: list[str], *, default_len: int = 180) -> str:
    cleaned = _normalize_spaces(text)
    if not cleaned:
        return ""
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", cleaned) if s.strip()]
    lowered = [s.lower() for s in sentences]
    for kw in keywords:
        kw_low = kw.lower()
        for idx, s in enumerate(lowered):
            if kw_low in s:
                return sentences[idx][:default_len]
    return cleaned[:default_len]


def _matches_any_pattern(text_lower: str, patterns: list[str]) -> bool:
    return any(re.search(p, text_lower) for p in patterns)


def _best_sentence_by_patterns(text: str, patterns: list[str], *, default_len: int = 180) -> str:
    cleaned = _normalize_spaces(text)
    if not cleaned:
        return ""
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", cleaned) if s.strip()]
    if not sentences:
        return cleaned[:default_len]
    for p in patterns:
        rx = re.compile(p)
        for sent in sentences:
            if rx.search(sent.lower()):
                return sent[:default_len]
    return cleaned[:default_len]


def _extractors_from_metadata(metadata: dict[str, Any]) -> list[str]:
    raw_many = metadata.get("extractors")
    out: list[str] = []
    if isinstance(raw_many, list):
        for item in raw_many:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
    if out:
        return _unique_preserve_order(out)
    raw_one = metadata.get("extractor")
    if isinstance(raw_one, str) and raw_one.strip():
        token = raw_one.strip()
        if token != "hybrid":
            out.append(token)
    return _unique_preserve_order(out)


def _set_candidate_extractors(cand: MemoryCandidate, extractors: list[str]) -> MemoryCandidate:
    ex = _unique_preserve_order([e for e in extractors if e])
    metadata = dict(cand.metadata)
    if ex:
        metadata["extractors"] = ex
        metadata["extractor"] = "hybrid" if len(ex) > 1 else ex[0]
    return MemoryCandidate(
        memory_type=cand.memory_type,
        memory_key=cand.memory_key,
        text=cand.text,
        importance=cand.importance,
        confidence=cand.confidence,
        stance=cand.stance,
        tickers=list(cand.tickers),
        ttl_days=cand.ttl_days,
        metadata=metadata,
    )


def _merge_candidates(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
    merged: dict[tuple[str, str, str], MemoryCandidate] = {}
    for cand in candidates:
        if not cand.text:
            continue
        key = (cand.memory_type, cand.memory_key, cand.stance)
        cand_extractors = _extractors_from_metadata(cand.metadata)
        if not cand_extractors:
            cand_extractors = ["keyword"]
            cand = _set_candidate_extractors(cand, cand_extractors)

        prev = merged.get(key)
        if prev is None:
            merged[key] = cand
            continue

        prev_extractors = _extractors_from_metadata(prev.metadata)
        merged_extractors = _unique_preserve_order(prev_extractors + cand_extractors)

        choose_cand = False
        if cand.importance > prev.importance:
            choose_cand = True
        elif cand.importance == prev.importance and cand.confidence > prev.confidence:
            choose_cand = True
        elif cand.importance == prev.importance and cand.confidence == prev.confidence and len(cand.text) > len(prev.text):
            choose_cand = True

        primary = cand if choose_cand else prev
        secondary = prev if choose_cand else cand
        metadata = dict(primary.metadata)
        if "theme" not in metadata and "theme" in secondary.metadata:
            metadata["theme"] = secondary.metadata["theme"]

        merged[key] = _set_candidate_extractors(
            MemoryCandidate(
                memory_type=primary.memory_type,
                memory_key=primary.memory_key,
                text=primary.text,
                importance=primary.importance,
                confidence=primary.confidence,
                stance=primary.stance,
                tickers=_unique_preserve_order(primary.tickers + secondary.tickers),
                ttl_days=primary.ttl_days if primary.ttl_days is not None else secondary.ttl_days,
                metadata=metadata,
            ),
            merged_extractors,
        )

    return list(merged.values())


def _infer_risk_stance(text_lower: str) -> str:
    conservative = ["보수", "안정", "방어", "리스크 줄", "위험 줄", "변동성 줄", "conservative", "defensive"]
    aggressive = ["공격", "리스크 감수", "고위험", "leverage", "high beta", "aggressive"]
    c = any(k in text_lower for k in conservative)
    a = any(k in text_lower for k in aggressive)
    if c and not a:
        return "conservative"
    if a and not c:
        return "aggressive"
    if c and a:
        return "balanced"
    return "unspecified"


def _infer_allocation_stance(text_lower: str) -> str:
    exit_words = ["빼", "청산", "exit", "sell all", "전량"]
    down_words = ["줄", "축소", "감축", "decrease", "trim", "underweight", "매도"]
    up_words = ["늘", "확대", "추가", "increase", "add", "overweight", "매수"]
    hold_words = ["유지", "hold", "keep", "버티", "계속"]
    if any(k in text_lower for k in exit_words):
        return "exit"
    if any(k in text_lower for k in down_words):
        return "decrease"
    if any(k in text_lower for k in up_words):
        return "increase"
    if any(k in text_lower for k in hold_words):
        return "hold"
    return "unspecified"


def _infer_regime_stance(text_lower: str) -> str:
    bear_words = ["약세", "하락", "침체", "둔화", "risk-off", "bear", "불안"]
    bull_words = ["강세", "상승", "회복", "risk-on", "bull", "낙관"]
    b0 = any(k in text_lower for k in bear_words)
    b1 = any(k in text_lower for k in bull_words)
    if b0 and not b1:
        return "bearish"
    if b1 and not b0:
        return "bullish"
    if b0 and b1:
        return "mixed"
    return "uncertain"


def _infer_emotion_stance(text_lower: str) -> str:
    anxious = ["불안", "걱정", "무섭", "anxious", "nervous", "fear"]
    frustrated = [
        "답답",
        "지친",
        "스트레스",
        "억울",
        "속상",
        "서운",
        "짜증",
        "화나",
        "열받",
        "빡치",
        "frustrated",
        "stressed",
    ]
    distressed = ["우울", "무기력", "멘붕", "burnout"]
    confident = ["확신", "자신", "괜찮", "confident"]
    if any(k in text_lower for k in anxious):
        return "anxious"
    if any(k in text_lower for k in frustrated):
        return "frustrated"
    if any(k in text_lower for k in distressed):
        return "distressed"
    if any(k in text_lower for k in confident):
        return "confident"
    return "neutral"


def _collect_theme_tags(text_lower: str) -> list[str]:
    out: list[str] = []
    for theme, words in THEME_KEYWORDS.items():
        if any(w.lower() in text_lower for w in words):
            out.append(theme)
    return out


def _is_guidance_preference(text_lower: str) -> bool:
    patterns = [
        r"뭐.*좋을까",
        r"어떻게.*좋을까",
        r"should i",
        r"what should i do",
        r"how should i",
    ]
    return any(re.search(p, text_lower) for p in patterns)


def _candidate(
    *,
    memory_type: str,
    key: str,
    text: str,
    importance: float,
    confidence: float,
    stance: str = "",
    tickers: list[str] | None = None,
    ttl_days: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> MemoryCandidate:
    return MemoryCandidate(
        memory_type=memory_type,
        memory_key=key,
        text=_normalize_spaces(text),
        importance=float(max(0.0, min(1.0, importance))),
        confidence=float(max(0.0, min(1.0, confidence))),
        stance=(stance or "").strip(),
        tickers=tickers or [],
        ttl_days=ttl_days,
        metadata=metadata or {},
    )


def _extract_candidates_instruction(user_text: str, assistant_text: str) -> list[MemoryCandidate]:
    text = _normalize_spaces(user_text)
    text_lower = text.lower()
    tickers = _extract_tickers(text)

    out: list[MemoryCandidate] = []

    if _matches_any_pattern(text_lower, INSTRUCTION_STYLE_PATTERNS):
        out.append(
            _candidate(
                memory_type="decision_rule",
                key="decision_rule::portfolio_style",
                text=_best_sentence_by_patterns(text, INSTRUCTION_STYLE_PATTERNS),
                importance=0.90,
                confidence=0.85,
                stance="style",
                tickers=tickers,
                ttl_days=None,
                metadata={"extractor": "instruction"},
            )
        )

    if _matches_any_pattern(text_lower, INSTRUCTION_RISK_PATTERNS):
        out.append(
            _candidate(
                memory_type="risk_tolerance",
                key="risk_tolerance::portfolio",
                text=_best_sentence_by_patterns(text, INSTRUCTION_RISK_PATTERNS),
                importance=0.90,
                confidence=0.84,
                stance=_infer_risk_stance(text_lower),
                tickers=tickers,
                ttl_days=None,
                metadata={"extractor": "instruction"},
            )
        )

    if _matches_any_pattern(text_lower, INSTRUCTION_CONSTRAINT_PATTERNS):
        out.append(
            _candidate(
                memory_type="constraints",
                key="constraints::portfolio",
                text=_best_sentence_by_patterns(text, INSTRUCTION_CONSTRAINT_PATTERNS),
                importance=0.88,
                confidence=0.81,
                stance="",
                tickers=tickers,
                ttl_days=None,
                metadata={"extractor": "instruction"},
            )
        )

    if _matches_any_pattern(text_lower, INSTRUCTION_ALLOCATION_PATTERNS):
        alloc_stance = _infer_allocation_stance(text_lower)
        targets = tickers[:3] if tickers else ["PORTFOLIO"]
        for target in targets:
            out.append(
                _candidate(
                    memory_type="allocation_decision",
                    key=f"allocation_decision::{target}",
                    text=_best_sentence_by_patterns(text, INSTRUCTION_ALLOCATION_PATTERNS),
                    importance=0.86,
                    confidence=0.81,
                    stance=alloc_stance,
                    tickers=[target] if target != "PORTFOLIO" else [],
                    ttl_days=120,
                    metadata={"extractor": "instruction"},
                )
            )

    if _matches_any_pattern(text_lower, INSTRUCTION_REGIME_PATTERNS):
        out.append(
            _candidate(
                memory_type="regime_view",
                key="regime_view::macro",
                text=_best_sentence_by_patterns(text, INSTRUCTION_REGIME_PATTERNS),
                importance=0.83,
                confidence=0.78,
                stance=_infer_regime_stance(text_lower),
                tickers=tickers,
                ttl_days=45,
                metadata={"extractor": "instruction"},
            )
        )

    if _matches_any_pattern(text_lower, INSTRUCTION_EMOTION_PATTERNS):
        out.append(
            _candidate(
                memory_type="emotional_state",
                key="emotional_state::user",
                text=_best_sentence_by_patterns(text, INSTRUCTION_EMOTION_PATTERNS),
                importance=0.82,
                confidence=0.81,
                stance=_infer_emotion_stance(text_lower),
                tickers=[],
                ttl_days=21,
                metadata={"extractor": "instruction"},
            )
        )

    if _matches_any_pattern(text_lower, INSTRUCTION_PERSONAL_CONTEXT_PATTERNS):
        out.append(
            _candidate(
                memory_type="personal_context",
                key="personal_context::life",
                text=_best_sentence_by_patterns(text, INSTRUCTION_PERSONAL_CONTEXT_PATTERNS),
                importance=0.79,
                confidence=0.75,
                stance="",
                tickers=[],
                ttl_days=180,
                metadata={"extractor": "instruction"},
            )
        )

    if _matches_any_pattern(text_lower, INSTRUCTION_PREFERENCE_PATTERNS):
        out.append(
            _candidate(
                memory_type="interaction_preference",
                key="interaction_preference::format",
                text=_best_sentence_by_patterns(text, INSTRUCTION_PREFERENCE_PATTERNS),
                importance=0.76,
                confidence=0.74,
                stance="",
                tickers=[],
                ttl_days=180,
                metadata={"extractor": "instruction"},
            )
        )

    if _matches_any_pattern(text_lower, INSTRUCTION_ADVISORY_PATTERNS):
        out.append(
            _candidate(
                memory_type="interaction_preference",
                key="interaction_preference::advisory",
                text=_best_sentence_by_patterns(text, INSTRUCTION_ADVISORY_PATTERNS),
                importance=0.81,
                confidence=0.82,
                stance="guidance_needed",
                tickers=tickers,
                ttl_days=180,
                metadata={"extractor": "instruction"},
            )
        )

    if _matches_any_pattern(text_lower, INSTRUCTION_RULE_PATTERNS):
        out.append(
            _candidate(
                memory_type="decision_rule",
                key="decision_rule::portfolio",
                text=_best_sentence_by_patterns(text, INSTRUCTION_RULE_PATTERNS),
                importance=0.89,
                confidence=0.80,
                stance="",
                tickers=tickers,
                ttl_days=None,
                metadata={"extractor": "instruction"},
            )
        )

    # Assistant response can include explicit rules worth retaining.
    a_text = _normalize_spaces(assistant_text)
    a_lower = a_text.lower()
    if a_text and _matches_any_pattern(text_lower, INSTRUCTION_ADVISORY_PATTERNS) and _contains_any(a_lower, RULE_KEYWORDS):
        out.append(
            _candidate(
                memory_type="decision_rule",
                key="decision_rule::assistant_proposal",
                text=_best_sentence(a_text, RULE_KEYWORDS),
                importance=0.76,
                confidence=0.66,
                stance="proposal",
                tickers=_extract_tickers(a_text),
                ttl_days=45,
                metadata={"extractor": "instruction"},
            )
        )

    return out


def _extract_candidates_keyword(user_text: str, assistant_text: str) -> list[MemoryCandidate]:
    text = _normalize_spaces(user_text)
    text_lower = text.lower()
    tickers = _extract_tickers(text)

    out: list[MemoryCandidate] = []

    if _contains_any(text_lower, GOAL_KEYWORDS):
        out.append(
            _candidate(
                memory_type="goal",
                key="goal::portfolio",
                text=_best_sentence(text, GOAL_KEYWORDS),
                importance=0.93,
                confidence=0.84,
                stance="",
                tickers=tickers,
                ttl_days=None,
                metadata={"extractor": "keyword"},
            )
        )

    if _contains_any(text_lower, RISK_KEYWORDS):
        stance = _infer_risk_stance(text_lower)
        out.append(
            _candidate(
                memory_type="risk_tolerance",
                key="risk_tolerance::portfolio",
                text=_best_sentence(text, RISK_KEYWORDS),
                importance=0.90,
                confidence=0.82,
                stance=stance,
                tickers=tickers,
                ttl_days=None,
                metadata={"extractor": "keyword"},
            )
        )

    if _contains_any(text_lower, CONSTRAINT_KEYWORDS):
        out.append(
            _candidate(
                memory_type="constraints",
                key="constraints::portfolio",
                text=_best_sentence(text, CONSTRAINT_KEYWORDS),
                importance=0.90,
                confidence=0.80,
                stance="",
                tickers=tickers,
                ttl_days=None,
                metadata={"extractor": "keyword"},
            )
        )

    if _contains_any(text_lower, ALLOCATION_KEYWORDS) or bool(tickers):
        alloc_stance = _infer_allocation_stance(text_lower)
        targets = tickers[:3] if tickers else ["PORTFOLIO"]
        for t in targets:
            out.append(
                _candidate(
                    memory_type="allocation_decision",
                    key=f"allocation_decision::{t}",
                    text=_best_sentence(text, ALLOCATION_KEYWORDS),
                    importance=0.84,
                    confidence=0.78,
                    stance=alloc_stance,
                    tickers=[t] if t != "PORTFOLIO" else [],
                    ttl_days=120,
                    metadata={"extractor": "keyword"},
                )
            )

    if _contains_any(text_lower, REGIME_KEYWORDS):
        out.append(
            _candidate(
                memory_type="regime_view",
                key="regime_view::macro",
                text=_best_sentence(text, REGIME_KEYWORDS),
                importance=0.82,
                confidence=0.75,
                stance=_infer_regime_stance(text_lower),
                tickers=tickers,
                ttl_days=45,
                metadata={"extractor": "keyword"},
            )
        )

    emotion_signal = _contains_any(text_lower, EMOTION_KEYWORDS) or bool(
        re.search(r"(감정|기분).{0,8}(들|드|나|남|난|임|이다|이야|느껴)", text_lower)
    )
    if emotion_signal:
        out.append(
            _candidate(
                memory_type="emotional_state",
                key="emotional_state::user",
                text=_best_sentence(text, EMOTION_KEYWORDS + ["감정", "기분"]),
                importance=0.80,
                confidence=0.77,
                stance=_infer_emotion_stance(text_lower),
                tickers=[],
                ttl_days=21,
                metadata={"extractor": "keyword"},
            )
        )

    if _contains_any(text_lower, PERSONAL_CONTEXT_KEYWORDS):
        out.append(
            _candidate(
                memory_type="personal_context",
                key="personal_context::life",
                text=_best_sentence(text, PERSONAL_CONTEXT_KEYWORDS),
                importance=0.78,
                confidence=0.73,
                stance="",
                tickers=[],
                ttl_days=180,
                metadata={"extractor": "keyword"},
            )
        )

    if _contains_any(text_lower, PREFERENCE_KEYWORDS):
        out.append(
            _candidate(
                memory_type="interaction_preference",
                key="interaction_preference::format",
                text=_best_sentence(text, PREFERENCE_KEYWORDS),
                importance=0.75,
                confidence=0.73,
                stance="",
                tickers=[],
                ttl_days=180,
                metadata={"extractor": "keyword"},
            )
        )

    if _is_guidance_preference(text_lower):
        out.append(
            _candidate(
                memory_type="interaction_preference",
                key="interaction_preference::advisory",
                text=_best_sentence(text, ["좋을까", "should i", "what should i do"]),
                importance=0.79,
                confidence=0.80,
                stance="guidance_needed",
                tickers=tickers,
                ttl_days=180,
                metadata={"extractor": "keyword"},
            )
        )

    if _contains_any(text_lower, RULE_KEYWORDS):
        out.append(
            _candidate(
                memory_type="decision_rule",
                key="decision_rule::portfolio",
                text=_best_sentence(text, RULE_KEYWORDS),
                importance=0.88,
                confidence=0.79,
                stance="",
                tickers=tickers,
                ttl_days=None,
                metadata={"extractor": "keyword"},
            )
        )

    for theme in _collect_theme_tags(text_lower):
        out.append(
            _candidate(
                memory_type="interest_theme",
                key=f"interest_theme::{theme}",
                text=_best_sentence(text, THEME_KEYWORDS.get(theme, [])),
                importance=0.72,
                confidence=0.70,
                stance="",
                tickers=tickers,
                ttl_days=120,
                metadata={"theme": theme, "extractor": "keyword"},
            )
        )

    # Assistant response can contain concrete rules to retain if user asked for guidance.
    a_text = _normalize_spaces(assistant_text)
    a_lower = a_text.lower()
    if a_text and _is_guidance_preference(text_lower) and _contains_any(a_lower, RULE_KEYWORDS):
        out.append(
            _candidate(
                memory_type="decision_rule",
                key="decision_rule::assistant_proposal",
                text=_best_sentence(a_text, RULE_KEYWORDS),
                importance=0.76,
                confidence=0.66,
                stance="proposal",
                tickers=_extract_tickers(a_text),
                ttl_days=45,
                metadata={"extractor": "keyword"},
            )
        )

    return out


def _extract_candidates(
    user_text: str,
    assistant_text: str,
    *,
    extractor_mode: str = EXTRACTOR_MODE_DEFAULT,
) -> list[MemoryCandidate]:
    mode = (extractor_mode or EXTRACTOR_MODE_DEFAULT).strip().lower()
    if mode not in EXTRACTOR_MODES:
        mode = EXTRACTOR_MODE_DEFAULT

    out: list[MemoryCandidate] = []
    if mode in {"hybrid", "instruction"}:
        out.extend(_extract_candidates_instruction(user_text, assistant_text))
    if mode in {"hybrid", "keyword"}:
        out.extend(_extract_candidates_keyword(user_text, assistant_text))
    return _merge_candidates(out)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            memory_id TEXT PRIMARY KEY,
            memory_type TEXT NOT NULL,
            memory_key TEXT NOT NULL,
            canonical_text TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            language_hint TEXT NOT NULL DEFAULT '',
            stance TEXT NOT NULL DEFAULT '',
            importance REAL NOT NULL DEFAULT 0.0,
            confidence REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            reinforce_count INTEGER NOT NULL DEFAULT 1,
            ttl_days INTEGER,
            expires_at TEXT,
            tickers_json TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            source_user_text TEXT NOT NULL DEFAULT '',
            source_assistant_text TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_type_key ON memories(memory_type, memory_key)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_last_seen ON memories(last_seen_at DESC)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_deltas (
            delta_id TEXT PRIMARY KEY,
            logged_at TEXT NOT NULL,
            memory_id TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            memory_key TEXT NOT NULL,
            change_type TEXT NOT NULL,
            reason TEXT NOT NULL,
            similarity REAL,
            prev_text TEXT,
            new_text TEXT,
            prev_stance TEXT,
            new_stance TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deltas_logged_at ON memory_deltas(logged_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deltas_memory_id ON memory_deltas(memory_id)")


def _expires_at_iso(now: dt.datetime, ttl_days: int | None) -> str | None:
    if ttl_days is None or ttl_days <= 0:
        return None
    return (now + dt.timedelta(days=int(ttl_days))).isoformat()


def _log_delta(
    conn: sqlite3.Connection,
    *,
    now_iso: str,
    memory_id: str,
    memory_type: str,
    memory_key: str,
    change_type: str,
    reason: str,
    similarity: float | None,
    prev_text: str = "",
    new_text: str = "",
    prev_stance: str = "",
    new_stance: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO memory_deltas (
            delta_id, logged_at, memory_id, memory_type, memory_key,
            change_type, reason, similarity, prev_text, new_text,
            prev_stance, new_stance, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            now_iso,
            memory_id,
            memory_type,
            memory_key,
            change_type,
            reason,
            similarity,
            prev_text,
            new_text,
            prev_stance,
            new_stance,
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )


def _parse_embedding(raw: str) -> list[float]:
    try:
        arr = json.loads(raw)
    except json.JSONDecodeError:
        return [0.0] * EMBED_DIM
    if not isinstance(arr, list):
        return [0.0] * EMBED_DIM
    out = []
    for x in arr:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            out.append(0.0)
    if len(out) != EMBED_DIM:
        if len(out) < EMBED_DIM:
            out.extend([0.0] * (EMBED_DIM - len(out)))
        else:
            out = out[:EMBED_DIM]
    return out


def _is_stance_changed(prev: str, cur: str) -> bool:
    if not prev or not cur:
        return False
    return prev != cur


def _load_key_memories(conn: sqlite3.Connection, memory_type: str, memory_key: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT * FROM memories
            WHERE memory_type = ? AND memory_key = ? AND status IN ('ACTIVE', 'PROVISIONAL')
            ORDER BY last_seen_at DESC
            """,
            (memory_type, memory_key),
        ).fetchall()
    )


def _insert_memory(
    conn: sqlite3.Connection,
    *,
    now: dt.datetime,
    cand: MemoryCandidate,
    user_text: str,
    assistant_text: str,
) -> dict[str, Any]:
    memory_id = str(uuid.uuid4())
    status = "ACTIVE" if cand.importance >= HIGH_IMPORTANCE else "PROVISIONAL"
    now_iso = now.isoformat()
    expires_at = _expires_at_iso(now, cand.ttl_days)
    embedding = _embed_text(cand.text)

    conn.execute(
        """
        INSERT INTO memories (
            memory_id, memory_type, memory_key, canonical_text, embedding_json,
            language_hint, stance, importance, confidence, status, first_seen_at, last_seen_at,
            reinforce_count, ttl_days, expires_at, tickers_json, metadata_json,
            source_user_text, source_assistant_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            memory_id,
            cand.memory_type,
            cand.memory_key,
            cand.text,
            json.dumps(embedding, ensure_ascii=False),
            "mixed",
            cand.stance,
            cand.importance,
            cand.confidence,
            status,
            now_iso,
            now_iso,
            1,
            cand.ttl_days,
            expires_at,
            json.dumps(cand.tickers, ensure_ascii=False),
            json.dumps(cand.metadata, ensure_ascii=False),
            user_text,
            assistant_text,
        ),
    )
    _log_delta(
        conn,
        now_iso=now_iso,
        memory_id=memory_id,
        memory_type=cand.memory_type,
        memory_key=cand.memory_key,
        change_type="new",
        reason="new_candidate",
        similarity=None,
        new_text=cand.text,
        new_stance=cand.stance,
        metadata={"status": status},
    )
    return {
        "action": "new",
        "memory_id": memory_id,
        "memory_type": cand.memory_type,
        "memory_key": cand.memory_key,
        "status": status,
        "similarity": None,
    }


def _upsert_candidate(
    conn: sqlite3.Connection,
    *,
    now: dt.datetime,
    cand: MemoryCandidate,
    user_text: str,
    assistant_text: str,
) -> dict[str, Any]:
    rows = _load_key_memories(conn, cand.memory_type, cand.memory_key)
    if not rows:
        return _insert_memory(conn, now=now, cand=cand, user_text=user_text, assistant_text=assistant_text)

    cand_vec = _embed_text(cand.text)
    best_row = None
    best_sim = -1.0
    for row in rows:
        sim = _cosine(cand_vec, _parse_embedding(str(row["embedding_json"])))
        if sim > best_sim:
            best_sim = sim
            best_row = row

    if best_row is None:
        return _insert_memory(conn, now=now, cand=cand, user_text=user_text, assistant_text=assistant_text)

    memory_id = str(best_row["memory_id"])
    prev_status = str(best_row["status"])
    prev_text = str(best_row["canonical_text"])
    prev_stance = str(best_row["stance"])
    prev_importance = float(best_row["importance"])
    prev_reinforce = int(best_row["reinforce_count"])
    now_iso = now.isoformat()
    new_expires_at = _expires_at_iso(now, cand.ttl_days)

    if _is_stance_changed(prev_stance, cand.stance):
        conn.execute(
            """
            UPDATE memories
            SET canonical_text = ?, embedding_json = ?, stance = ?, importance = ?, confidence = ?,
                status = 'ACTIVE', last_seen_at = ?, reinforce_count = ?,
                ttl_days = ?, expires_at = ?, tickers_json = ?, metadata_json = ?,
                source_user_text = ?, source_assistant_text = ?
            WHERE memory_id = ?
            """,
            (
                cand.text,
                json.dumps(cand_vec, ensure_ascii=False),
                cand.stance,
                cand.importance,
                cand.confidence,
                now_iso,
                prev_reinforce + 1,
                cand.ttl_days,
                new_expires_at,
                json.dumps(cand.tickers, ensure_ascii=False),
                json.dumps(cand.metadata, ensure_ascii=False),
                user_text,
                assistant_text,
                memory_id,
            ),
        )
        _log_delta(
            conn,
            now_iso=now_iso,
            memory_id=memory_id,
            memory_type=cand.memory_type,
            memory_key=cand.memory_key,
            change_type="update",
            reason="stance_changed",
            similarity=best_sim,
            prev_text=prev_text,
            new_text=cand.text,
            prev_stance=prev_stance,
            new_stance=cand.stance,
        )
        return {
            "action": "update",
            "memory_id": memory_id,
            "memory_type": cand.memory_type,
            "memory_key": cand.memory_key,
            "status": "ACTIVE",
            "similarity": round(best_sim, 4),
        }

    same_stance = bool(cand.stance) and cand.stance == prev_stance
    relaxed_reinforce = same_stance and best_sim >= SIM_KEY_STANCE_REINFORCE
    relaxed_reinforce = relaxed_reinforce or (
        (not cand.stance and not prev_stance and best_sim >= SIM_KEY_REINFORCE)
    )

    if best_sim >= SIM_REINFORCE or relaxed_reinforce:
        new_reinforce = prev_reinforce + 1
        new_status = prev_status
        action = "reinforce"
        reason = "similar_statement"
        if prev_status == "PROVISIONAL" and new_reinforce >= PROMOTE_AFTER:
            new_status = "ACTIVE"
            action = "promote"
            reason = "repeated_signal"

        canonical = prev_text
        if cand.importance >= prev_importance and len(cand.text) > len(prev_text):
            canonical = cand.text

        conn.execute(
            """
            UPDATE memories
            SET canonical_text = ?, embedding_json = ?, importance = ?, confidence = ?,
                stance = ?, status = ?, last_seen_at = ?, reinforce_count = ?,
                ttl_days = ?, expires_at = ?, tickers_json = ?, metadata_json = ?,
                source_user_text = ?, source_assistant_text = ?
            WHERE memory_id = ?
            """,
            (
                canonical,
                json.dumps(cand_vec, ensure_ascii=False),
                max(prev_importance, cand.importance),
                max(float(best_row["confidence"]), cand.confidence),
                cand.stance or prev_stance,
                new_status,
                now_iso,
                new_reinforce,
                cand.ttl_days,
                new_expires_at,
                json.dumps(cand.tickers, ensure_ascii=False),
                json.dumps(cand.metadata, ensure_ascii=False),
                user_text,
                assistant_text,
                memory_id,
            ),
        )
        _log_delta(
            conn,
            now_iso=now_iso,
            memory_id=memory_id,
            memory_type=cand.memory_type,
            memory_key=cand.memory_key,
            change_type=action,
            reason=reason,
            similarity=best_sim,
            prev_text=prev_text,
            new_text=canonical,
            prev_stance=prev_stance,
            new_stance=cand.stance or prev_stance,
        )
        return {
            "action": action,
            "memory_id": memory_id,
            "memory_type": cand.memory_type,
            "memory_key": cand.memory_key,
            "status": new_status,
            "similarity": round(best_sim, 4),
        }

    if best_sim >= SIM_UPDATE and cand.importance >= prev_importance:
        new_status = "ACTIVE" if cand.importance >= HIGH_IMPORTANCE else prev_status
        conn.execute(
            """
            UPDATE memories
            SET canonical_text = ?, embedding_json = ?, importance = ?, confidence = ?,
                stance = ?, status = ?, last_seen_at = ?, reinforce_count = ?,
                ttl_days = ?, expires_at = ?, tickers_json = ?, metadata_json = ?,
                source_user_text = ?, source_assistant_text = ?
            WHERE memory_id = ?
            """,
            (
                cand.text,
                json.dumps(cand_vec, ensure_ascii=False),
                cand.importance,
                cand.confidence,
                cand.stance or prev_stance,
                new_status,
                now_iso,
                prev_reinforce + 1,
                cand.ttl_days,
                new_expires_at,
                json.dumps(cand.tickers, ensure_ascii=False),
                json.dumps(cand.metadata, ensure_ascii=False),
                user_text,
                assistant_text,
                memory_id,
            ),
        )
        _log_delta(
            conn,
            now_iso=now_iso,
            memory_id=memory_id,
            memory_type=cand.memory_type,
            memory_key=cand.memory_key,
            change_type="update",
            reason="new_detail",
            similarity=best_sim,
            prev_text=prev_text,
            new_text=cand.text,
            prev_stance=prev_stance,
            new_stance=cand.stance or prev_stance,
        )
        return {
            "action": "update",
            "memory_id": memory_id,
            "memory_type": cand.memory_type,
            "memory_key": cand.memory_key,
            "status": new_status,
            "similarity": round(best_sim, 4),
        }

    return _insert_memory(conn, now=now, cand=cand, user_text=user_text, assistant_text=assistant_text)


def _expire_memories(conn: sqlite3.Connection, *, now: dt.datetime) -> int:
    now_iso = now.isoformat()
    rows = list(
        conn.execute(
            """
            SELECT memory_id, memory_type, memory_key, canonical_text, stance
            FROM memories
            WHERE status IN ('ACTIVE', 'PROVISIONAL')
              AND expires_at IS NOT NULL
              AND expires_at < ?
            """,
            (now_iso,),
        ).fetchall()
    )
    if not rows:
        return 0

    for row in rows:
        memory_id = str(row["memory_id"])
        conn.execute("UPDATE memories SET status = 'EXPIRED' WHERE memory_id = ?", (memory_id,))
        _log_delta(
            conn,
            now_iso=now_iso,
            memory_id=memory_id,
            memory_type=str(row["memory_type"]),
            memory_key=str(row["memory_key"]),
            change_type="expire",
            reason="ttl_expired",
            similarity=None,
            prev_text=str(row["canonical_text"]),
            prev_stance=str(row["stance"]),
        )
    return len(rows)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False))
        f.write("\n")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    for k in ["tickers_json", "metadata_json"]:
        raw = out.get(k)
        if isinstance(raw, str):
            try:
                out[k] = json.loads(raw)
            except json.JSONDecodeError:
                pass
    return out


def _fmt_table_md(rows: list[dict[str, Any]], headers: list[str]) -> str:
    if not rows:
        return "(empty)"
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    lines = [head, sep]
    for row in rows:
        vals = []
        for h in headers:
            val = row.get(h, "")
            if isinstance(val, float):
                vals.append(f"{val:.4f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _parse_datetime_safe(text: Any) -> dt.datetime | None:
    if not isinstance(text, str) or not text.strip():
        return None
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo(DEFAULT_TZ))
    return parsed.astimezone(ZoneInfo(DEFAULT_TZ))


def _read_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _importance_rank(value: str) -> int:
    order = {"high": 0, "medium": 1, "low": 2}
    return order.get(value, 3)


def _detect_finance_signal(user_text: str) -> dict[str, Any]:
    lower = _normalize_lower(user_text)
    matched_keywords = [kw for kw in FINANCE_KEYWORDS if kw.lower() in lower]
    themes = _collect_theme_tags(lower)
    tickers = _extract_tickers(user_text)
    finance_related = bool(matched_keywords or tickers or themes)
    return {
        "is_finance_related": finance_related,
        "matched_keywords": _unique_preserve_order(matched_keywords)[:12],
        "matched_themes": _unique_preserve_order(themes),
        "tickers": tickers,
    }


def _search_memories_raw(
    conn: sqlite3.Connection,
    *,
    query: str,
    top_k: int,
    include_provisional: bool,
) -> list[dict[str, Any]]:
    q_vec = _embed_text(query)
    status_filter = "('ACTIVE', 'PROVISIONAL')" if include_provisional else "('ACTIVE')"
    rows = list(
        conn.execute(
            f"""
            SELECT memory_id, memory_type, memory_key, stance, importance, confidence, status,
                   reinforce_count, last_seen_at, canonical_text, embedding_json
            FROM memories
            WHERE status IN {status_filter}
            """
        ).fetchall()
    )

    scored: list[dict[str, Any]] = []
    for row in rows:
        row_d = dict(row)
        mem_text = str(row_d.get("canonical_text", ""))
        mem_vec = _parse_embedding(str(row_d.get("embedding_json", "[]")))
        cos = _cosine(q_vec, mem_vec)
        kw = _keyword_overlap_score(query, mem_text)
        score = 0.75 * cos + 0.25 * kw
        row_d["score"] = score
        row_d["cosine"] = cos
        row_d["keyword_overlap"] = kw
        scored.append(row_d)
    scored.sort(key=lambda x: (float(x["score"]), float(x["importance"]), str(x["last_seen_at"])), reverse=True)
    return scored[:top_k]


def _extract_close_prices(raw: Any, symbols: list[str]) -> dict[str, float]:
    if raw is None:
        return {}
    try:
        import pandas as pd  # local import to keep startup light
    except ModuleNotFoundError:
        return {}

    if getattr(raw, "empty", True):
        return {}
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if "Close" in raw.columns.get_level_values(0):
                close = raw["Close"].copy()
            elif "Adj Close" in raw.columns.get_level_values(0):
                close = raw["Adj Close"].copy()
            else:
                close = raw[raw.columns.get_level_values(0)[0]].copy()
        else:
            col = "Close" if "Close" in raw.columns else ("Adj Close" if "Adj Close" in raw.columns else raw.columns[-1])
            close = raw[[col]].rename(columns={col: symbols[0] if symbols else "UNKNOWN"})
    except Exception:
        return {}

    if isinstance(close, pd.Series):
        close = close.to_frame(name=symbols[0] if symbols else "UNKNOWN")

    close = close.copy()
    try:
        close.columns = [str(c).upper() for c in close.columns]
        close = close.ffill()
    except Exception:
        return {}

    out: dict[str, float] = {}
    for sym in symbols:
        if sym not in close.columns:
            continue
        series = close[sym].dropna()
        if series.empty:
            continue
        try:
            px = float(series.iloc[-1])
        except (TypeError, ValueError):
            continue
        if px > 0:
            out[sym] = px
    return out


def _load_world_context(db_path: Path, *, days: int, limit: int) -> dict[str, Any]:
    now = _kst_now()
    if not db_path.exists():
        return {
            "available": False,
            "db_path": str(db_path),
            "count": 0,
            "items": [],
            "active_states": [],
        }

    since = (now - dt.timedelta(days=max(1, days))).isoformat()
    items: list[dict[str, Any]] = []
    active_states: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        try:
            rows = list(
                conn.execute(
                    """
                    SELECT as_of, category, region, importance, title, payload_json
                    FROM world_issue_entries
                    WHERE as_of >= ?
                    ORDER BY as_of DESC
                    LIMIT 500
                    """,
                    (since,),
                ).fetchall()
            )
        except sqlite3.Error:
            rows = []
        try:
            state_rows = list(
                conn.execute(
                    """
                    SELECT effective_from, state_key, state_label, state_status, state_bias,
                           net_effect, summary, confidence
                    FROM world_issue_states
                    WHERE state_status IN ('active', 'watch')
                    ORDER BY effective_from DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (max(1, limit),),
                ).fetchall()
            )
        except sqlite3.Error:
            state_rows = []

    for row in rows:
        payload = {}
        try:
            payload = json.loads(str(row["payload_json"]))
        except (TypeError, json.JSONDecodeError):
            payload = {}
        as_of = _parse_datetime_safe(payload.get("as_of") or row["as_of"]) or now
        age_hours = max(0.0, (now - as_of).total_seconds() / 3600.0)
        imp = str(payload.get("importance", row["importance"]) or "medium").lower()
        score = (3 - _importance_rank(imp)) * 10.0 - min(age_hours / 24.0, 10.0)
        items.append(
            {
                "as_of": as_of.isoformat(),
                "category": str(payload.get("category", row["category"])),
                "region": str(payload.get("region", row["region"])),
                "importance": imp,
                "title": str(payload.get("title", row["title"])),
                "summary": str(payload.get("summary", "")),
                "tickers": payload.get("tickers", []),
                "_score": score,
            }
        )

    items.sort(key=lambda x: (float(x["_score"]), x["as_of"]), reverse=True)
    top = items[: max(1, limit)]
    for row in top:
        row.pop("_score", None)

    for row in state_rows:
        effective_from = _parse_datetime_safe(row["effective_from"]) or now
        active_states.append(
            {
                "effective_from": effective_from.isoformat(),
                "state_key": str(row["state_key"] or ""),
                "state_label": str(row["state_label"] or ""),
                "state_status": str(row["state_status"] or ""),
                "state_bias": str(row["state_bias"] or ""),
                "net_effect": str(row["net_effect"] or ""),
                "summary": str(row["summary"] or ""),
                "confidence": float(row["confidence"] or 0.0),
            }
        )

    return {
        "available": bool(top or active_states),
        "db_path": str(db_path),
        "count": len(items),
        "items": top,
        "active_states": active_states,
        "latest_as_of": top[0]["as_of"] if top else "",
        "latest_state_at": active_states[0]["effective_from"] if active_states else "",
    }


def _load_portfolio_context(position_log: Path, *, lookback_days: int, include_prices: bool) -> dict[str, Any]:
    rows = _read_jsonl_rows(position_log)
    if not rows:
        return {"available": False, "position_log": str(position_log)}

    rows.sort(key=lambda r: (str(r.get("date", "")), str(r.get("logged_at", ""))))
    nav_rows = [r for r in rows if str(r.get("event_type", "")) == "nav_snapshot"]
    trade_rows = [r for r in rows if str(r.get("event_type", "")) == "trade"]

    nav_info: dict[str, Any] = {}
    if nav_rows:
        series = []
        for row in nav_rows:
            d = _parse_datetime_safe(str(row.get("date", "") + "T00:00:00+09:00"))
            if d is None:
                continue
            try:
                nav = float(row.get("nav"))
            except (TypeError, ValueError):
                continue
            series.append((d, nav))
        series.sort(key=lambda x: x[0])
        if series:
            end_dt, end_nav = series[-1]
            start_dt = end_dt - dt.timedelta(days=max(1, lookback_days))
            window = [(d, v) for d, v in series if d >= start_dt]
            if len(window) < 2:
                window = series
            begin_dt, begin_nav = window[0]
            total_return = (end_nav / begin_nav - 1.0) if begin_nav else 0.0
            peak = -float("inf")
            mdd = 0.0
            for _, value in window:
                peak = max(peak, value)
                if peak > 0:
                    dd = value / peak - 1.0
                    mdd = min(mdd, dd)
            nav_info = {
                "as_of": end_dt.isoformat(),
                "lookback_start": begin_dt.isoformat(),
                "lookback_days": lookback_days,
                "nav_start": begin_nav,
                "nav_end": end_nav,
                "return_pct": total_return * 100.0,
                "max_drawdown_pct": mdd * 100.0,
            }

    holdings_qty: dict[str, float] = {}
    for row in trade_rows:
        symbol = str(row.get("symbol", "")).upper().strip()
        if not symbol:
            continue
        try:
            qty = float(row.get("quantity"))
        except (TypeError, ValueError):
            continue
        side = str(row.get("side", "")).upper()
        if side == "BUY":
            holdings_qty[symbol] = holdings_qty.get(symbol, 0.0) + qty
        elif side == "SELL":
            holdings_qty[symbol] = holdings_qty.get(symbol, 0.0) - qty

    holdings_qty = {s: q for s, q in holdings_qty.items() if abs(q) > 1e-12}
    symbols = sorted(holdings_qty.keys())
    holdings_view: list[dict[str, Any]] = []

    prices: dict[str, float] = {}
    if include_prices and symbols:
        try:
            import yfinance as yf

            raw = yf.download(
                tickers=" ".join(symbols),
                period="10d",
                auto_adjust=True,
                progress=False,
                threads=True,
                group_by="column",
            )
            prices = _extract_close_prices(raw, symbols)
        except Exception:
            prices = {}

    if prices:
        total_mv = 0.0
        mv_map: dict[str, float] = {}
        for sym, qty in holdings_qty.items():
            px = prices.get(sym)
            if px is None:
                continue
            mv = qty * px
            mv_map[sym] = mv
            total_mv += mv
        for sym, mv in sorted(mv_map.items(), key=lambda x: x[1], reverse=True)[:10]:
            weight = (mv / total_mv * 100.0) if total_mv > 0 else 0.0
            holdings_view.append(
                {
                    "symbol": sym,
                    "weight_pct": round(weight, 2),
                    "market_value": round(mv, 2),
                }
            )
    else:
        for sym, qty in sorted(holdings_qty.items(), key=lambda x: abs(x[1]), reverse=True)[:10]:
            holdings_view.append({"symbol": sym, "quantity": round(qty, 6)})

    return {
        "available": True,
        "position_log": str(position_log),
        "event_count": len(rows),
        "nav": nav_info,
        "holdings": holdings_view,
    }


def _render_prepare_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Counsel Prep Pack")
    lines.append("")
    lines.append(f"- as_of: {payload.get('as_of', '')}")
    sig = payload.get("finance_signal", {})
    lines.append(f"- finance_related: {sig.get('is_finance_related', False)}")
    if sig.get("matched_keywords"):
        lines.append("- matched_keywords: " + ", ".join(sig.get("matched_keywords", [])))
    if sig.get("tickers"):
        lines.append("- tickers: " + ", ".join(sig.get("tickers", [])))
    if sig.get("matched_themes"):
        lines.append("- themes: " + ", ".join(sig.get("matched_themes", [])))
    lines.append("")

    ingest = payload.get("ingest", {})
    lines.append("## Memory Actions")
    lines.append("")
    lines.append(
        f"- candidates_kept: {ingest.get('candidates_kept', 0)} / extracted: {ingest.get('candidates_extracted', 0)}"
    )
    lines.append(f"- extractor_mode: {ingest.get('extractor_mode', EXTRACTOR_MODE_DEFAULT)}")
    if ingest.get("by_extractor"):
        lines.append(f"- by_extractor: {ingest.get('by_extractor', {})}")
    lines.append(f"- action_counts: {ingest.get('action_counts', {})}")
    lines.append("")

    mem_hits = payload.get("memory_hits", [])
    lines.append("## Personal Memory Hits")
    lines.append("")
    if mem_hits:
        rows = []
        for row in mem_hits:
            rows.append(
                {
                    "score": round(float(row.get("score", 0.0)), 4),
                    "type": row.get("memory_type", ""),
                    "key": row.get("memory_key", ""),
                    "stance": row.get("stance", "") or "-",
                    "text": str(row.get("canonical_text", ""))[:120],
                }
            )
        lines.append(_fmt_table_md(rows, ["score", "type", "key", "stance", "text"]))
    else:
        lines.append("(empty)")
    lines.append("")

    world = payload.get("world_context", {})
    lines.append("## Active World States")
    lines.append("")
    if world.get("available") and world.get("active_states"):
        rows = []
        for row in world.get("active_states", []):
            effective_from = _parse_datetime_safe(row.get("effective_from"))
            rows.append(
                {
                    "effective_from": effective_from.strftime("%Y-%m-%d %H:%M KST") if effective_from else "",
                    "status": row.get("state_status", ""),
                    "bias": row.get("state_bias", ""),
                    "state_key": row.get("state_key", ""),
                    "net_effect": row.get("net_effect", ""),
                    "label": str(row.get("state_label", ""))[:60],
                    "summary": str(row.get("summary", ""))[:100],
                }
            )
        lines.append(
            _fmt_table_md(
                rows,
                ["effective_from", "status", "bias", "state_key", "net_effect", "label", "summary"],
            )
        )
    else:
        lines.append("(not loaded or empty)")
    lines.append("")

    lines.append("## Recent World Memory")
    lines.append("")
    if world.get("available") and world.get("items"):
        rows = []
        for row in world.get("items", []):
            rows.append(
                {
                    "as_of": row.get("as_of", ""),
                    "importance": row.get("importance", ""),
                    "region": row.get("region", ""),
                    "category": row.get("category", ""),
                    "title": str(row.get("title", ""))[:80],
                }
            )
        lines.append(_fmt_table_md(rows, ["as_of", "importance", "region", "category", "title"]))
    else:
        lines.append("(not loaded or empty)")
    lines.append("")

    port = payload.get("portfolio_context", {})
    lines.append("## Portfolio Pulse")
    lines.append("")
    if port.get("available"):
        nav = port.get("nav", {})
        if nav:
            lines.append(
                f"- return({nav.get('lookback_days', '?')}d): {float(nav.get('return_pct', 0.0)):.2f}%"
            )
            lines.append(f"- max_drawdown: {float(nav.get('max_drawdown_pct', 0.0)):.2f}%")
            lines.append(f"- nav_end: {float(nav.get('nav_end', 0.0)):.4f}")
        holdings = port.get("holdings", [])
        if holdings:
            headers = list(holdings[0].keys())
            lines.append("")
            lines.append(_fmt_table_md(holdings, headers))
    else:
        lines.append("(position log unavailable)")
    lines.append("")

    lines.append("## Ready State")
    lines.append("")
    lines.append(f"- ready: {payload.get('ready', False)}")
    lines.append(f"- rationale: {payload.get('ready_reason', '')}")
    return "\n".join(lines).rstrip() + "\n"


def _handle_init(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    with _connect(db_path) as conn:
        _init_db(conn)
        conn.commit()
    print(f"Initialized memory DB: {db_path}")
    return 0


def _handle_ingest_turn(args: argparse.Namespace) -> int:
    user_text = _read_optional_text(args.user_text, args.user_file, required=True).strip()
    assistant_text = _read_optional_text(args.assistant_text, args.assistant_file, required=False).strip()

    now = _kst_now()
    db_path = Path(args.db)
    jsonl_path = Path(args.jsonl_log)

    with _connect(db_path) as conn:
        _init_db(conn)
        expired = _expire_memories(conn, now=now)

        candidates = _extract_candidates(
            user_text,
            assistant_text,
            extractor_mode=args.extractor_mode,
        )
        filtered = [c for c in candidates if c.importance >= args.min_importance]

        by_extractor: dict[str, int] = {}
        for c in filtered:
            for ex in _extractors_from_metadata(c.metadata):
                by_extractor[ex] = by_extractor.get(ex, 0) + 1

        if args.dry_run:
            payload = {
                "as_of": now.isoformat(),
                "extractor_mode": args.extractor_mode,
                "candidate_count": len(filtered),
                "by_extractor": by_extractor,
                "candidates": [
                    {
                        "memory_type": c.memory_type,
                        "memory_key": c.memory_key,
                        "importance": c.importance,
                        "confidence": c.confidence,
                        "stance": c.stance,
                        "ttl_days": c.ttl_days,
                        "tickers": c.tickers,
                        "text": c.text,
                        "metadata": c.metadata,
                    }
                    for c in filtered
                ],
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        actions: list[dict[str, Any]] = []
        for cand in filtered:
            action = _upsert_candidate(
                conn,
                now=now,
                cand=cand,
                user_text=user_text,
                assistant_text=assistant_text,
            )
            actions.append(action)

        conn.commit()

    counts: dict[str, int] = {}
    for a in actions:
        counts[a["action"]] = counts.get(a["action"], 0) + 1

    event = {
        "schema_version": 1,
        "event_id": str(uuid.uuid4()),
        "as_of": now.isoformat(),
        "source": args.source,
        "extractor_mode": args.extractor_mode,
        "user_text": user_text,
        "assistant_text": assistant_text,
        "candidate_count": len(filtered),
        "by_extractor": by_extractor,
        "expired_count": expired,
        "actions": actions,
        "counts": counts,
    }
    _append_jsonl(jsonl_path, event)

    print(f"Ingested turn: {db_path}")
    print(f"Candidates kept: {len(filtered)} / extracted: {len(candidates)}")
    if expired:
        print(f"Expired memories: {expired}")
    print("Actions:", ", ".join([f"{k}={v}" for k, v in sorted(counts.items())]) if counts else "none")
    print(f"Saved event log: {jsonl_path}")
    return 0


def _status_sql_filter(status: str) -> tuple[str, tuple[Any, ...]]:
    if status == "all":
        return "", ()
    return "WHERE status = ?", (status.upper(),)


def _handle_list(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    with _connect(db_path) as conn:
        _init_db(conn)
        where_sql, where_args = _status_sql_filter(args.status)
        rows = list(
            conn.execute(
                f"""
                SELECT memory_id, memory_type, memory_key, stance, importance, confidence, status,
                       reinforce_count, first_seen_at, last_seen_at, expires_at, canonical_text
                FROM memories
                {where_sql}
                ORDER BY last_seen_at DESC
                LIMIT ?
                """,
                (*where_args, args.limit),
            ).fetchall()
        )

    data = [_row_to_dict(r) for r in rows]
    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.format == "md":
        headers = [
            "memory_type",
            "memory_key",
            "stance",
            "importance",
            "status",
            "reinforce_count",
            "last_seen_at",
            "canonical_text",
        ]
        view = []
        for row in data:
            view.append(
                {
                    "memory_type": row["memory_type"],
                    "memory_key": row["memory_key"],
                    "stance": row["stance"],
                    "importance": round(float(row["importance"]), 3),
                    "status": row["status"],
                    "reinforce_count": row["reinforce_count"],
                    "last_seen_at": row["last_seen_at"],
                    "canonical_text": str(row["canonical_text"])[:140],
                }
            )
        print(_fmt_table_md(view, headers))
        return 0

    print(f"Memories: {len(data)}")
    for i, row in enumerate(data, start=1):
        print(
            f"{i:>3}. [{row['status']}] {row['memory_type']} / {row['memory_key']} "
            f"(stance={row['stance'] or '-'}, imp={float(row['importance']):.2f}, seen={row['last_seen_at']})"
        )
        print(f"     {str(row['canonical_text'])[:180]}")
    return 0


def _handle_search(args: argparse.Namespace) -> int:
    query = _read_optional_text(args.query_text, args.query_file, required=True).strip()

    db_path = Path(args.db)
    with _connect(db_path) as conn:
        _init_db(conn)
        top = _search_memories_raw(
            conn,
            query=query,
            top_k=args.top_k,
            include_provisional=bool(args.include_provisional),
        )

    if args.format == "json":
        print(json.dumps(top, ensure_ascii=False, indent=2))
        return 0

    if args.format == "md":
        view = []
        for row in top:
            view.append(
                {
                    "score": round(float(row["score"]), 4),
                    "memory_type": row["memory_type"],
                    "memory_key": row["memory_key"],
                    "stance": row["stance"] or "-",
                    "importance": round(float(row["importance"]), 3),
                    "last_seen_at": row["last_seen_at"],
                    "canonical_text": str(row["canonical_text"])[:140],
                }
            )
        headers = ["score", "memory_type", "memory_key", "stance", "importance", "last_seen_at", "canonical_text"]
        print(_fmt_table_md(view, headers))
        return 0

    print(f"Search results: {len(top)}")
    for i, row in enumerate(top, start=1):
        print(
            f"{i:>3}. score={float(row['score']):.4f} cos={float(row['cosine']):.4f} kw={float(row['keyword_overlap']):.4f} "
            f"[{row['memory_type']}] {row['memory_key']}"
        )
        print(f"     {str(row['canonical_text'])[:180]}")
    return 0


def _handle_prepare_turn(args: argparse.Namespace) -> int:
    user_text = _read_optional_text(args.user_text, args.user_file, required=True).strip()
    assistant_text = _read_optional_text(args.assistant_text, args.assistant_file, required=False).strip()
    now = _kst_now()

    db_path = Path(args.db)
    jsonl_path = Path(args.jsonl_log)

    candidates = _extract_candidates(
        user_text,
        assistant_text,
        extractor_mode=args.extractor_mode,
    )
    filtered = [c for c in candidates if c.importance >= args.min_importance]

    by_extractor: dict[str, int] = {}
    for c in filtered:
        for ex in _extractors_from_metadata(c.metadata):
            by_extractor[ex] = by_extractor.get(ex, 0) + 1

    actions: list[dict[str, Any]] = []
    expired = 0
    if args.ingest:
        with _connect(db_path) as conn:
            _init_db(conn)
            expired = _expire_memories(conn, now=now)
            for cand in filtered:
                action = _upsert_candidate(
                    conn,
                    now=now,
                    cand=cand,
                    user_text=user_text,
                    assistant_text=assistant_text,
                )
                actions.append(action)
            conn.commit()

        counts: dict[str, int] = {}
        for a in actions:
            counts[a["action"]] = counts.get(a["action"], 0) + 1
        event = {
            "schema_version": 1,
            "event_id": str(uuid.uuid4()),
            "as_of": now.isoformat(),
            "source": args.source,
            "event_type": "prepare_turn",
            "extractor_mode": args.extractor_mode,
            "user_text": user_text,
            "assistant_text": assistant_text,
            "candidate_count": len(filtered),
            "by_extractor": by_extractor,
            "expired_count": expired,
            "actions": actions,
            "counts": counts,
        }
        _append_jsonl(jsonl_path, event)

    finance_signal = _detect_finance_signal(user_text)

    memory_hits: list[dict[str, Any]] = []
    with _connect(db_path) as conn:
        _init_db(conn)
        memory_hits = _search_memories_raw(
            conn,
            query=user_text,
            top_k=args.memory_top_k,
            include_provisional=True,
        )
    for row in memory_hits:
        row.pop("embedding_json", None)

    world_context = {"available": False, "items": []}
    portfolio_context = {"available": False}
    if finance_signal.get("is_finance_related"):
        world_context = _load_world_context(
            Path(args.world_db),
            days=args.world_days,
            limit=args.world_limit,
        )
        portfolio_context = _load_portfolio_context(
            Path(args.position_log),
            lookback_days=args.portfolio_lookback_days,
            include_prices=not args.no_prices,
        )

    ready = bool(
        finance_signal.get("is_finance_related")
        and (
            memory_hits
            or world_context.get("items")
            or world_context.get("active_states")
            or portfolio_context.get("available")
        )
    )
    if ready:
        ready_reason = "Finance signal detected and context pack loaded."
    elif finance_signal.get("is_finance_related"):
        ready_reason = "Finance signal detected but context sources are sparse."
    else:
        ready_reason = "No finance signal in the turn; kept lightweight memory-only prep."

    action_counts: dict[str, int] = {}
    for a in actions:
        action_counts[a["action"]] = action_counts.get(a["action"], 0) + 1

    payload = {
        "as_of": now.isoformat(),
        "user_text": user_text,
        "finance_signal": finance_signal,
        "ingest": {
            "enabled": bool(args.ingest),
            "extractor_mode": args.extractor_mode,
            "candidates_extracted": len(candidates),
            "candidates_kept": len(filtered),
            "by_extractor": by_extractor,
            "expired": expired,
            "action_counts": action_counts,
            "actions": actions,
        },
        "memory_hits": memory_hits,
        "world_context": world_context,
        "portfolio_context": portfolio_context,
        "ready": ready,
        "ready_reason": ready_reason,
    }

    if args.format == "json":
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    elif args.format == "md":
        text = _render_prepare_markdown(payload)
    else:
        text = (
            f"as_of={payload['as_of']}\n"
            f"finance_related={finance_signal.get('is_finance_related', False)}\n"
            f"memory_hits={len(memory_hits)} world_items={len(world_context.get('items', []))} "
            f"world_states={len(world_context.get('active_states', []))} "
            f"portfolio_available={portfolio_context.get('available', False)}\n"
            f"ready={ready} reason={ready_reason}\n"
        )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"Saved prep pack: {out_path}")
    else:
        print(text, end="" if text.endswith("\n") else "\n")
    return 0


def _handle_deltas(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    since = (_kst_now() - dt.timedelta(days=args.days)).isoformat()
    with _connect(db_path) as conn:
        _init_db(conn)
        rows = list(
            conn.execute(
                """
                SELECT logged_at, memory_type, memory_key, change_type, reason, similarity,
                       prev_stance, new_stance, prev_text, new_text
                FROM memory_deltas
                WHERE logged_at >= ?
                ORDER BY logged_at DESC
                LIMIT ?
                """,
                (since, args.limit),
            ).fetchall()
        )

    data = [dict(r) for r in rows]
    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.format == "md":
        view = []
        for row in data:
            view.append(
                {
                    "logged_at": row["logged_at"],
                    "change_type": row["change_type"],
                    "memory_type": row["memory_type"],
                    "memory_key": row["memory_key"],
                    "reason": row["reason"],
                    "similarity": "-" if row["similarity"] is None else f"{float(row['similarity']):.3f}",
                    "new_stance": row["new_stance"] or "-",
                    "new_text": str(row["new_text"] or "")[:120],
                }
            )
        headers = ["logged_at", "change_type", "memory_type", "memory_key", "reason", "similarity", "new_stance", "new_text"]
        print(_fmt_table_md(view, headers))
        return 0

    print(f"Deltas: {len(data)}")
    for i, row in enumerate(data, start=1):
        sim = "-" if row["similarity"] is None else f"{float(row['similarity']):.3f}"
        print(
            f"{i:>3}. {row['logged_at']} [{row['change_type']}] {row['memory_type']} / {row['memory_key']} "
            f"(reason={row['reason']}, sim={sim})"
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Counsel memory engine: extract meaningful utterances, upsert memories, and search with multilingual vectors."
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help=f"SQLite path (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--jsonl-log", default=DEFAULT_JSONL_LOG_PATH, help=f"Event JSONL path (default: {DEFAULT_JSONL_LOG_PATH})")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Initialize memory DB")

    p_ingest = sub.add_parser("ingest-turn", help="Ingest a single chat turn and upsert meaningful memories")
    p_ingest.add_argument("--user-text", default="", help="User utterance text")
    p_ingest.add_argument("--user-file", default=None, help="User utterance file path")
    p_ingest.add_argument("--assistant-text", default="", help="Assistant response text (optional)")
    p_ingest.add_argument("--assistant-file", default=None, help="Assistant response file path")
    p_ingest.add_argument("--source", default="chat_turn", help="Event source label")
    p_ingest.add_argument("--min-importance", type=float, default=0.65, help="Minimum importance threshold (0~1)")
    p_ingest.add_argument(
        "--extractor-mode",
        choices=sorted(EXTRACTOR_MODES),
        default=EXTRACTOR_MODE_DEFAULT,
        help=f"Candidate extraction mode (default: {EXTRACTOR_MODE_DEFAULT})",
    )
    p_ingest.add_argument("--dry-run", action="store_true", help="Show extracted candidates only")

    p_list = sub.add_parser("list", help="List memories")
    p_list.add_argument("--status", choices=["active", "provisional", "expired", "all"], default="active", help="Memory status filter")
    p_list.add_argument("--limit", type=int, default=50, help="Max rows")
    p_list.add_argument("--format", choices=["pretty", "md", "json"], default="pretty", help="Output format")

    p_search = sub.add_parser("search", help="Search memories with hybrid multilingual vector + keyword scoring")
    p_search.add_argument("--query-text", default="", help="Search query text")
    p_search.add_argument("--query-file", default=None, help="Search query file path")
    p_search.add_argument("--top-k", type=int, default=12, help="Top-k results")
    p_search.add_argument("--include-provisional", action="store_true", help="Include provisional memories")
    p_search.add_argument("--format", choices=["pretty", "md", "json"], default="pretty", help="Output format")

    p_delta = sub.add_parser("deltas", help="Show memory update history")
    p_delta.add_argument("--days", type=int, default=30, help="Lookback days")
    p_delta.add_argument("--limit", type=int, default=100, help="Max rows")
    p_delta.add_argument("--format", choices=["pretty", "md", "json"], default="pretty", help="Output format")

    p_prepare = sub.add_parser(
        "prepare-turn",
        help="Ingest turn and auto-prepare reply context (memory + world context + portfolio pulse)",
    )
    p_prepare.add_argument("--user-text", default="", help="User utterance text")
    p_prepare.add_argument("--user-file", default=None, help="User utterance file path")
    p_prepare.add_argument("--assistant-text", default="", help="Assistant response text (optional)")
    p_prepare.add_argument("--assistant-file", default=None, help="Assistant response file path")
    p_prepare.add_argument("--source", default="chat_turn_prepare", help="Event source label")
    p_prepare.add_argument("--min-importance", type=float, default=0.65, help="Minimum importance threshold (0~1)")
    p_prepare.add_argument(
        "--extractor-mode",
        choices=sorted(EXTRACTOR_MODES),
        default=EXTRACTOR_MODE_DEFAULT,
        help=f"Candidate extraction mode (default: {EXTRACTOR_MODE_DEFAULT})",
    )
    p_prepare.add_argument("--no-ingest", dest="ingest", action="store_false", help="Do not persist extracted memories")
    p_prepare.set_defaults(ingest=True)
    p_prepare.add_argument("--memory-top-k", type=int, default=8, help="Top-k personal memory hits")
    p_prepare.add_argument("--world-db", default="portfolio/world_issue_log.sqlite3", help="World memory SQLite path")
    p_prepare.add_argument("--world-days", type=int, default=21, help="World memory lookback days")
    p_prepare.add_argument("--world-limit", type=int, default=8, help="Max world context rows")
    p_prepare.add_argument("--position-log", default="portfolio/position_log.jsonl", help="Portfolio position log JSONL path")
    p_prepare.add_argument("--portfolio-lookback-days", type=int, default=90, help="Portfolio lookback days for pulse stats")
    p_prepare.add_argument("--no-prices", action="store_true", help="Skip live price lookup for holdings weights")
    p_prepare.add_argument("--format", choices=["pretty", "md", "json"], default="md", help="Output format")
    p_prepare.add_argument("--out", default=None, help="Output file path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "init":
        return _handle_init(args)
    if args.cmd == "ingest-turn":
        return _handle_ingest_turn(args)
    if args.cmd == "list":
        return _handle_list(args)
    if args.cmd == "search":
        return _handle_search(args)
    if args.cmd == "prepare-turn":
        return _handle_prepare_turn(args)
    if args.cmd == "deltas":
        return _handle_deltas(args)
    raise SystemExit(f"Unknown command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
