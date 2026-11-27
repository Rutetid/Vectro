from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PROFILE_FIELDS = ["age", "gender", "income", "state", "occupation", "caste", "residency"]

STATE_ALIASES = {
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chhattisgarh": "Chhattisgarh",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "orissa": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "west bengal": "West Bengal",
    "andaman and nicobar": "Andaman and Nicobar Islands",
    "andaman nicobar": "Andaman and Nicobar Islands",
    "chandigarh": "Chandigarh",
    "dadra and nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
    "delhi": "Delhi",
    "nct delhi": "Delhi",
    "jammu and kashmir": "Jammu and Kashmir",
    "jammu kashmir": "Jammu and Kashmir",
    "ladakh": "Ladakh",
    "lakshadweep": "Lakshadweep",
    "puducherry": "Puducherry",
    "pondicherry": "Puducherry",
}

CASTE_MAP = {
    "sc": "sc",
    "scheduled caste": "sc",
    "st": "st",
    "scheduled tribe": "st",
    "obc": "obc",
    "other backward class": "obc",
    "other backward classes": "obc",
    "general": "general",
    "gen": "general",
    "ews": "ews",
    "economically weaker section": "ews",
    "bpl": "bpl",
}

OCCUPATION_KEYWORDS = {
    "student": "student",
    "farmer": "agriculture",
    "agriculture": "agriculture",
    "agricultural": "agriculture",
    "unemployed": "unemployed",
    "self employed": "business",
    "self-employed": "business",
    "business": "business",
    "entrepreneur": "business",
    "private": "private",
    "private job": "private",
    "govt": "government",
    "government": "government",
    "government job": "government",
    "public sector": "government",
}


def _empty_profile() -> Dict[str, Any]:
    return {k: None for k in PROFILE_FIELDS}


def _norm_gender(v: Any) -> Optional[str]:
    t = str(v or "").strip().lower()
    if not t:
        return None
    if t in {"male", "m", "man", "boy"}:
        return "male"
    if t in {"female", "f", "woman", "girl"}:
        return "female"
    if t in {"other", "transgender", "non-binary", "nonbinary"}:
        return "other"
    return None


def _norm_caste(v: Any) -> Optional[str]:
    t = str(v or "").strip().lower()
    if not t:
        return None
    if t in CASTE_MAP:
        return CASTE_MAP[t]
    # check longer/specific aliases first with word boundaries
    for k in sorted(CASTE_MAP.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(k)}\b", t):
            return CASTE_MAP[k]
    return None


def _norm_residency(v: Any) -> Optional[str]:
    t = str(v or "").strip().lower()
    if not t:
        return None
    if "rural" in t or "village" in t:
        return "rural"
    if "urban" in t or "city" in t or "town" in t:
        return "urban"
    return None


def _norm_state(v: Any) -> Optional[str]:
    t = str(v or "").strip().lower()
    if not t:
        return None
    for k, canonical in STATE_ALIASES.items():
        if k in t:
            return canonical
    # fallback: title case if looks like a short name
    cleaned = re.sub(r"[^a-zA-Z ]", " ", str(v)).strip()
    if 3 <= len(cleaned) <= 40:
        return " ".join(w.capitalize() for w in cleaned.split())
    return None


def _parse_income(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        val = int(v)
        return val if val >= 0 else None
    t = str(v).lower().replace(",", "").replace("₹", " ").replace("rs.", " ").replace("inr", " ")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?|lakh|lac|l)\b", t)
    if m:
        amt = float(m.group(1))
        unit = m.group(2)
        if unit.startswith("cr"):
            amt *= 10_000_000
        else:
            amt *= 100_000
        return int(amt)
    m = re.search(r"\b(\d{4,9})\b", t)
    if m:
        return int(m.group(1))
    return None


def _norm_occupation(v: Any) -> Optional[str]:
    t = str(v or "").strip().lower()
    if not t:
        return None
    for k, canonical in OCCUPATION_KEYWORDS.items():
        if k in t:
            return canonical
    return t


def _normalize_profile(raw: Dict[str, Any]) -> Dict[str, Any]:
    p = _empty_profile()
    age = raw.get("age")
    if age is not None and age != "":
        try:
            age_i = int(float(age))
            if 0 <= age_i <= 120:
                p["age"] = age_i
        except Exception:
            pass
    p["gender"] = _norm_gender(raw.get("gender"))
    p["income"] = _parse_income(raw.get("income"))
    p["state"] = _norm_state(raw.get("state"))
    p["occupation"] = _norm_occupation(raw.get("occupation"))
    p["caste"] = _norm_caste(raw.get("caste"))
    p["residency"] = _norm_residency(raw.get("residency"))
    return p


def _heuristic_extract(message: str) -> Dict[str, Any]:
    text = " " + (message or "").lower() + " "
    p = _empty_profile()

    m = re.search(r"\b(\d{1,3})\s*(?:years?\s*old|year\s*old|yo|yrs|yr|y/o)\b", text)
    if not m:
        m = re.search(r"\b(?:age|aged)\s*(?:is|:)?\s*(\d{1,3})\b", text)
    if not m:
        m = re.search(r"\b(?:i\s*am|i'm|im)\s+(\d{1,3})\b", text)
    if not m:
        m = re.search(r"\b(\d{1,2})\s*(?:male|female|man|woman|boy|girl|m|f)\b", text)
    if m:
        age = int(m.group(1))
        if 0 <= age <= 120:
            p["age"] = age

    # gender
    if re.search(r"\b(female|woman|girl|she|her)\b", text):
        p["gender"] = "female"
    elif re.search(r"\b(male|man|boy|he|him)\b", text):
        p["gender"] = "male"

    p["residency"] = _norm_residency(message)
    # caste: avoid false positives from words like "education" containing "sc"
    caste_match = re.search(r"\b(sc|st|obc|ews|bpl|general|gen|scheduled caste|scheduled tribe|other backward class(?:es)?|economically weaker section)\b", text)
    if caste_match:
        p["caste"] = _norm_caste(caste_match.group(0))

    for k, canonical in STATE_ALIASES.items():
        if k in text:
            p["state"] = canonical
            break

    # income
    m = re.search(r"(?:income|earn|earning|salary|annual)[^\d]{0,25}(\d+(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?|lac|l)?\b", text)
    if m:
        p["income"] = _parse_income(m.group(0))
    else:
        m = re.search(r"\b(\d+(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?|lac|l)\b", text)
        if m:
            p["income"] = _parse_income(m.group(0))

    for k, canonical in OCCUPATION_KEYWORDS.items():
        if re.search(rf"\b{re.escape(k)}\b", text):
            p["occupation"] = canonical
            break

    return p


def _llm_extract(message: str) -> Optional[Dict[str, Any]]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        prompt = (
            "Extract user profile fields from the message. Return ONLY valid JSON object with keys: "
            "age, gender, income, state, occupation, caste, residency. "
            "Rules: use null for unknown/missing. Do not guess. "
            "age integer years. income annual INR integer (convert lakh/crore to rupees). "
            "gender male/female/other. caste sc/st/obc/general/ews/bpl or null. residency urban/rural or null. "
            "state Indian state/UT name or null. occupation short lowercase string or null.\n\n"
            f"Message: {message}"
        )
        resp = client.chat.completions.create(
            model=os.environ.get("PROFILE_EXTRACT_MODEL", "google/gemini-2.5-flash"),
            temperature=0,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        content = (resp.choices[0].message.content or "").strip()
        m = re.search(r"\{.*\}", content, re.DOTALL)
        raw = json.loads(m.group(0) if m else content)
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def extract_profile_from_message(message: str) -> Dict[str, Any]:
    heuristic = _heuristic_extract(message)
    llm_raw = _llm_extract(message)
    llm = _normalize_profile(llm_raw) if llm_raw else _empty_profile()

    merged = _empty_profile()
    for k in PROFILE_FIELDS:
        merged[k] = llm.get(k) if llm.get(k) is not None else heuristic.get(k)

    missing = [k for k, v in merged.items() if v is None]
    return {
        "profile": merged,
        "missing_fields": missing,
        "source": "llm+heuristic" if llm_raw else "heuristic",
    }
