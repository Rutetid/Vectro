from __future__ import annotations

import html as html_mod
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


WORD_RE = re.compile(r"\w+")
NUMBER_RE = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = "; ".join(str(item) for item in value if item is not None)
    elif isinstance(value, dict):
        value = "; ".join(f"{k}: {v}" for k, v in value.items())

    text = str(value).replace("\r", " ").replace("\n", " ")
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize_for_bm25(text: str) -> List[str]:
    return [token.lower() for token in WORD_RE.findall(text)]


def _split_words(text: str) -> List[str]:
    if not text:
        return []
    return text.split()


def _chunk_text_by_words(text: str, max_words: int, overlap_words: int) -> List[str]:
    words = _split_words(text)
    if not words:
        return []
    if len(words) <= max_words:
        return [" ".join(words)]

    chunks: List[str] = []
    start = 0
    step = max(1, max_words - overlap_words)
    while start < len(words):
        end = min(start + max_words, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
    return chunks


def _normalize_categories(value: str) -> List[str]:
    text = _clean_text(value)
    if not text:
        return []
    parts = [part.strip() for part in text.split(";")]
    return [part for part in parts if part]


def _parse_money_to_int(raw_value: str, unit_hint: str = "") -> Optional[int]:
    match = NUMBER_RE.search(raw_value or "")
    if not match:
        return None

    number_text = match.group(1).replace(",", "")
    try:
        amount = float(number_text)
    except ValueError:
        return None

    unit = (unit_hint or "").strip().lower()
    if "lakh" in unit:
        amount *= 100000
    elif "crore" in unit:
        amount *= 10000000

    return int(amount)


def _extract_age_bounds(text: str) -> Dict[str, Optional[int]]:
    lowered = text.lower()
    min_age: Optional[int] = None
    max_age: Optional[int] = None

    between_match = re.search(
        r"(?:aged?\s*)?(?:between|from)\s*(\d{1,2})\s*(?:to|and|-)\s*(\d{1,2})\s*(?:years?|yrs?)?",
        lowered,
    )
    if between_match:
        first = int(between_match.group(1))
        second = int(between_match.group(2))
        min_age, max_age = min(first, second), max(first, second)

    min_patterns = [
        ("above_before_number", r"(?:above|over|attained?)\s+(?:the\s+)?(?:age\s+of\s+)?(\d{1,2})\s*(?:years?|yrs?)\s*(?:of\s+age|old)?"),
        ("above_before_number", r"age(?:\s*should\s*be)?\s*(?:above|over|greater\s+than|more\s+than)\s*(\d{1,2})"),
        ("number_before_keyword", r"age(?:\s*should\s*be)?\s*(\d{1,2})\s*(?:years?|yrs?)\s*(?:or\s+)?(?:above|over|more)"),
        ("number_before_keyword", r"(\d{1,2})\s*(?:years?|yrs?)\s+(?:and\s+)?(?:above|over|or\s+more)"),
        ("number_before_keyword", r"(?:^|[.;])\s*(\d{1,2})\s*(?:years?|yrs?)\s*(?:of\s+)?age(?:\s*[;.]|$)"),
        ("number_before_keyword", r"not\s+(?:be\s+)?less\s+than\s+(\d{1,2})\s*(?:years?|yrs?)\s*(?:of\s+)?age"),
        ("inclusive_before_number", r"at least\s*(\d{1,2})\s*(?:years?|yrs?)"),
        ("inclusive_before_number", r"minimum age(?:\s*of)?\s*(\d{1,2})"),
        ("inclusive_before_number", r"minimum\s+(\d{1,2})\s*(?:years?|yrs?)(?:\s*of\s+age)?"),
        ("inclusive_before_number", r"(?:age|aged)\s+(?:should\s+)?(?:be\s+)?(?:minimum|at\s+least|not\s+(?:be\s+)?less\s+than)\s+(\d{1,2})"),
        ("inclusive_before_number", r"(?:should\s+)?(?:have\s+)?completed\s+(\d{1,2})\s*(?:years?|yrs?)\s*(?:of\s+)?age"),
        ("inclusive_before_number", r"(?:should\s+)?(?:have\s+)?completed\s+(\d{1,2})\s*(?:years?|yrs?)(?:\s+of\s+age)?"),
    ]
    for kind, pattern in min_patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        candidate = int(match.group(1))
        if kind == "above_before_number":
            candidate += 1
        min_age = candidate if min_age is None else max(min_age, candidate)

    max_patterns = [
        r"age(?:\s*should\s*be)?\s*(?:below|under|less\s+than)\s*(\d{1,2})",
        r"age(?:\s*should\s+not|shall\s+not|does\s+not)\s+exceed\s*(\d{1,2})",
        r"up to\s*(\d{1,2})\s*(?:years?|yrs?)",
        r"maximum age(?:\s*of)?\s*(\d{1,2})",
        r"not more than\s*(\d{1,2})\s*(?:years?|yrs?)",
        r"(?:should|shall|does)\s+not\s+exceed\s+(\d{1,2})\s*(?:years?|yrs?)",
        r"(?:not|neither)\s+(?:be\s+)?(?:more|greater)\s+than\s+(\d{1,2})\s*(?:years?|yrs?)",
        r"age\s+limit\s*[:\-]?\s*(\d{1,2})\s*(?:years?|yrs?)",
    ]
    for pattern in max_patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        candidate = int(match.group(1))
        if re.search(r'(?:below|under|less\s+than)', match.group(0)):
            candidate -= 1
        max_age = candidate if max_age is None else min(max_age, candidate)

    if min_age is not None and max_age is not None and min_age > max_age:
        min_age, max_age = max_age, min_age

    return {"min_age": min_age, "max_age": max_age}


def _normalize_income_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"rs\.?\s*", "₹", lowered)
    lowered = re.sub(r"inr\s*", "₹", lowered)
    lowered = re.sub(r"rupees?\s*", "₹", lowered)
    lowered = re.sub(r"/-", "", lowered)
    return lowered


_AMOUNT_RE = re.compile(
    r"₹?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakhs?|lakhs|crores?|crores)?"
)


def _find_all_amounts(text: str) -> List[tuple[int, str]]:
    results: List[tuple[int, str]] = []
    for match in _AMOUNT_RE.finditer(text):
        raw = match.group(0)
        amount = _parse_money_to_int(match.group(1), match.group(2) or "")
        if amount is not None:
            results.append((amount, raw))
    return results


def _extract_max_income(text: str) -> Optional[int]:
    normalized = _normalize_income_text(text)

    upper_keywords = [
        r"not\s+exceeding",
        r"less\s+than(?:\s+or\s+equal\s+to)?",
        r"(?:should|shall|does)\s+not\s+exceed",
        r"(?:should|shall|does)\s+not\s+(?:be\s+)?(?:more|greater)\s+than",
        r"not\s+(?:exceed|exceeding)",
        r"not\s+(?:be\s+)?(?:more|greater)\s+than",
        r"below",
        r"under",
        r"upto",
        r"up\s+to",
        r"maximum(?:\s+(?:is|of|should\s+be|limit\s+is|income\s+limit\s+is))?",
        r"income\s+ceiling",
        r"ceiling",
        r"not\s+more\s+than",
    ]
    upper_pat = re.compile(
        r"(?:" + "|".join(upper_keywords) + r")\s*₹?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakhs?|crores?)?",
        re.I,
    )

    candidates: List[int] = []
    for match in upper_pat.finditer(normalized):
        amount = _parse_money_to_int(match.group(1), match.group(2) or "")
        if amount is not None:
            candidates.append(amount)

    income_near_amount = re.compile(
        r"(?:income|annual|family\s+income|parental?\s+income)[^.;\n]{0,30}?(?:is|:)?\s*₹?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakhs?|crores?)?",
        re.I,
    )
    for match in income_near_amount.finditer(normalized):
        amount = _parse_money_to_int(match.group(1), match.group(2) or "")
        if amount is not None:
            candidates.append(amount)

    cat_pat = re.compile(
        r"(?:SC|ST|OBC|EWS|General|Gen)\s*[:]\s*₹?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakhs?|crores?)?",
        re.I,
    )
    for match in cat_pat.finditer(normalized):
        amount = _parse_money_to_int(match.group(1), match.group(2) or "")
        if amount is not None:
            candidates.append(amount)

    real_candidates = [c for c in candidates if c >= 1000]
    if not real_candidates:
        return None
    return min(real_candidates)


def _extract_gender_constraint(text: str) -> str:
    lowered = text.lower()
    padded = f" {lowered} "
    female_terms = [" female ", " women ", " woman ", " girl ", " girls ", " mother ", " mothers "]
    male_terms = [" male ", " men ", " man ", " boy ", " boys "]

    has_female = any(term in padded for term in female_terms)
    has_male = any(term in padded for term in male_terms)
    if has_female and not has_male:
        return "female"
    if has_male and not has_female:
        return "male"
    return "any"


def _extract_residency_constraints(text: str) -> List[str]:
    lowered = text.lower()
    values: List[str] = []
    if "rural" in lowered:
        values.append("rural")
    if "urban" in lowered:
        values.append("urban")
    return values


def _extract_caste_constraints(text: str) -> List[str]:
    lowered = text.lower()
    tags: List[str] = []
    mapping = {
        "sc": ["scheduled caste", " sc "],
        "st": ["scheduled tribe", " st "],
        "obc": ["obc", "other backward"],
        "general": ["general category", "general"],
        "bpl": ["bpl", "below poverty line"],
    }
    padded = f" {lowered} "
    for key, aliases in mapping.items():
        if any(alias in padded for alias in aliases):
            tags.append(key)
    return tags


_AGE_KEYWORD_RULES = [
    ({"children", "child", "minor", "below 18"}, None, 18),
    ({"student", "scholarship", "pursuing"}, 18, 30),
    ({"youth", "young adult", "unemployed youth"}, 18, 30),
    ({"graduate", "post graduate", "post-graduate", "degree holder", "bachelor"}, 21, None),
    ({"intermediate", "plus two", "higher secondary", "12th"}, 17, None),
    ({"senior citizen", "elderly", "old age", "super senior"}, 60, None),
    ({"widow", "widowed"}, 18, None),
    ({"farmer", "agricultur", "cultivator"}, 18, 60),
    ({"construction worker", "labourer", "laborer"}, 18, 60),
    ({"ex-serviceman", "ex serviceman", "retired"}, 18, 60),
]


def _infer_age_from_keywords(text: str) -> Dict[str, Any]:
    lowered = text.lower()
    for keywords, min_age, max_age in _AGE_KEYWORD_RULES:
        if any(kw in lowered for kw in keywords):
            return {"min_age": min_age, "max_age": max_age}
    return {"min_age": None, "max_age": None}


def _derive_eligibility_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    eligibility_text = _clean_text(record.get("eligibility"))
    combined_text = " ".join(
        part
        for part in [
            eligibility_text,
            _clean_text(record.get("brief_description")),
            _clean_text(record.get("detailed_description")),
        ]
        if part
    )

    age = _extract_age_bounds(combined_text)

    if age["min_age"] is None and age["max_age"] is None:
        age = _infer_age_from_keywords(combined_text)

    return {
        "eligibility_text": eligibility_text,
        "eligibility_min_age": age["min_age"],
        "eligibility_max_age": age["max_age"],
        "eligibility_max_income": _extract_max_income(combined_text),
        "eligibility_gender": _extract_gender_constraint(combined_text),
        "eligibility_residency": _extract_residency_constraints(combined_text),
        "eligibility_caste_tags": _extract_caste_constraints(combined_text),
    }


def _base_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    base = {
        "scheme_id": _clean_text(record.get("slug"))
        or _clean_text(record.get("short_title"))
        or _clean_text(record.get("scheme_name")),
        "scheme_name": _clean_text(record.get("scheme_name")),
        "short_title": _clean_text(record.get("short_title")),
        "state": _clean_text(record.get("state")),
        "level": _clean_text(record.get("level")),
        "ministry": _clean_text(record.get("ministry")),
        "department": _clean_text(record.get("department")),
        "beneficiary_type": _clean_text(record.get("beneficiary_type")),
        "target_beneficiaries": _clean_text(record.get("target_beneficiaries")),
        "benefit_type": _clean_text(record.get("benefit_type")),
        "categories": _normalize_categories(record.get("categories", "")),
        "sub_categories": _normalize_categories(record.get("sub_categories", "")),
        "source_url": _clean_text(record.get("source_url")),
    }
    base.update(_derive_eligibility_metadata(record))
    return base


def _summary_text(record: Dict[str, Any]) -> str:
    sections = [
        f"Scheme Name: {_clean_text(record.get('scheme_name'))}",
        f"State: {_clean_text(record.get('state'))}",
        f"Level: {_clean_text(record.get('level'))}",
        f"Categories: {_clean_text(record.get('categories'))}",
        f"Target Beneficiaries: {_clean_text(record.get('target_beneficiaries'))}",
        f"Brief Description: {_clean_text(record.get('brief_description'))}",
        f"Eligibility: {_clean_text(record.get('eligibility'))}",
        f"Benefits: {_clean_text(record.get('benefits'))}",
    ]
    return "\n".join(part for part in sections if not part.endswith(": "))


def _faq_chunks(record: Dict[str, Any]) -> List[str]:
    faqs = record.get("faqs")
    if not isinstance(faqs, list):
        return []

    results = []
    for item in faqs:
        if not isinstance(item, dict):
            continue
        question = _clean_text(item.get("question"))
        answer = _clean_text(item.get("answer"))
        if not question and not answer:
            continue
        results.append(f"FAQ Question: {question}\nFAQ Answer: {answer}".strip())
    return results


def load_jsonl(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_chunks_for_record(
    record: Dict[str, Any],
    max_words: int = 380,
    overlap_words: int = 70,
) -> List[Dict[str, Any]]:
    metadata = _base_metadata(record)
    scheme_id = metadata["scheme_id"]
    if not scheme_id:
        return []

    sections: List[Dict[str, str]] = [
        {"section": "summary", "text": _summary_text(record)},
        {"section": "benefits", "text": _clean_text(record.get("benefits"))},
        {"section": "eligibility", "text": _clean_text(record.get("eligibility"))},
        {
            "section": "documents_required",
            "text": _clean_text(record.get("documents_required")),
        },
        {
            "section": "application_process",
            "text": _clean_text(record.get("application_process")),
        },
        {
            "section": "detailed_description",
            "text": _clean_text(record.get("detailed_description")),
        },
    ]

    chunks: List[Dict[str, Any]] = []
    for section_block in sections:
        section_name = section_block["section"]
        text = section_block["text"]
        if not text:
            continue

        section_chunks = _chunk_text_by_words(
            text, max_words=max_words, overlap_words=overlap_words
        )
        for chunk_no, chunk_text in enumerate(section_chunks):
            chunk_id = f"{scheme_id}:{section_name}:{chunk_no}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "scheme_id": scheme_id,
                    "text": chunk_text,
                    "section": section_name,
                    "chunk_no": chunk_no,
                    "metadata": metadata,
                }
            )

    for faq_no, faq_text in enumerate(_faq_chunks(record)):
        faq_chunks = _chunk_text_by_words(
            faq_text, max_words=max_words, overlap_words=overlap_words
        )
        for chunk_no, chunk_text in enumerate(faq_chunks):
            chunk_id = f"{scheme_id}:faq_{faq_no}:{chunk_no}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "scheme_id": scheme_id,
                    "text": chunk_text,
                    "section": "faq",
                    "chunk_no": chunk_no,
                    "metadata": metadata,
                }
            )

    return chunks


def build_chunk_corpus(
    data_path: Path,
    limit: Optional[int] = None,
    max_words: int = 380,
    overlap_words: int = 70,
) -> List[Dict[str, Any]]:
    records = load_jsonl(data_path, limit=limit)
    all_chunks: List[Dict[str, Any]] = []
    for record in records:
        all_chunks.extend(
            build_chunks_for_record(
                record,
                max_words=max_words,
                overlap_words=overlap_words,
            )
        )
    return all_chunks
