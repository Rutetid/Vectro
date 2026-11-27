from __future__ import annotations

from typing import Any, Dict, List


def _norm(v: Any) -> str:
    return str(v or "").strip().lower()


def _is_all_state(v: Any) -> bool:
    t = _norm(v)
    return t in {"", "all", "all states", "all india", "india", "central", "national"}


def evaluate_scheme_eligibility(profile: Dict[str, Any], scheme_meta: Dict[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    unknowns: List[str] = []
    hard_fail = False

    age = profile.get("age")
    min_age = scheme_meta.get("eligibility_min_age")
    max_age = scheme_meta.get("eligibility_max_age")
    if min_age is not None or max_age is not None:
        if age is None:
            unknowns.append("age missing for age eligibility rule")
        else:
            age = int(age)
            if min_age is not None and age < int(min_age):
                hard_fail = True
                reasons.append(f"Age {age} is below minimum {int(min_age)}")
            if max_age is not None and age > int(max_age):
                hard_fail = True
                reasons.append(f"Age {age} is above maximum {int(max_age)}")
            if not hard_fail:
                reasons.append("Age satisfies eligibility rule")

    income = profile.get("income")
    max_income = scheme_meta.get("eligibility_max_income")
    if max_income is not None:
        if income is None:
            unknowns.append("income missing for income eligibility rule")
        else:
            income = int(income)
            if income > int(max_income):
                hard_fail = True
                reasons.append(f"Income {income} exceeds limit {int(max_income)}")
            else:
                reasons.append(f"Income within limit {int(max_income)}")

    req_gender = _norm(scheme_meta.get("eligibility_gender") or "any")
    user_gender = _norm(profile.get("gender"))
    if req_gender in {"male", "female"}:
        if not user_gender:
            unknowns.append("gender missing for gender eligibility rule")
        elif user_gender != req_gender:
            hard_fail = True
            reasons.append(f"Gender must be {req_gender}")
        else:
            reasons.append(f"Gender matches ({req_gender})")

    caste_tags = [_norm(x) for x in (scheme_meta.get("eligibility_caste_tags") or []) if str(x).strip()]
    user_caste = _norm(profile.get("caste"))
    if caste_tags:
        if not user_caste:
            unknowns.append("caste/category missing for caste eligibility rule")
        elif user_caste not in caste_tags:
            hard_fail = True
            reasons.append(f"Caste/category '{user_caste}' not in allowed {caste_tags}")
        else:
            reasons.append("Caste/category matches eligibility rule")

    res_tags = [_norm(x) for x in (scheme_meta.get("eligibility_residency") or []) if str(x).strip()]
    user_res = _norm(profile.get("residency"))
    if res_tags:
        if not user_res:
            unknowns.append("residency missing for residency eligibility rule")
        elif user_res not in res_tags:
            hard_fail = True
            reasons.append(f"Residency '{user_res}' not in allowed {res_tags}")
        else:
            reasons.append("Residency matches eligibility rule")

    scheme_state = scheme_meta.get("state")
    user_state = _norm(profile.get("state"))
    if not _is_all_state(scheme_state):
        if not user_state:
            unknowns.append("state missing for state eligibility rule")
        elif user_state != _norm(scheme_state):
            hard_fail = True
            reasons.append(f"Scheme state '{scheme_state}' does not match user state '{profile.get('state')}'")
        else:
            reasons.append("State matches eligibility rule")

    if hard_fail:
        status = "ineligible"
    elif unknowns:
        status = "unknown"
    else:
        status = "eligible"

    # de-duplicate while preserving order
    seen = set()
    reasons = [r for r in reasons if not (r in seen or seen.add(r))]
    seen = set()
    unknowns = [u for u in unknowns if not (u in seen or seen.add(u))]

    return {"status": status, "reasons": reasons, "unknowns": unknowns}


def apply_rule_engine(profile: Dict[str, Any], schemes: List[Dict[str, Any]], scheme_meta_lookup: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    annotated: List[Dict[str, Any]] = []
    for s in schemes:
        sid = s.get("scheme_id")
        meta = (scheme_meta_lookup.get(sid) or {}).get("metadata", {}) if sid else {}
        if not meta:
            meta = {
                "state": s.get("state"),
                "eligibility_min_age": s.get("eligibility_min_age"),
                "eligibility_max_age": s.get("eligibility_max_age"),
                "eligibility_max_income": s.get("eligibility_max_income"),
                "eligibility_gender": s.get("eligibility_gender", "any"),
                "eligibility_caste_tags": s.get("eligibility_caste_tags", []),
                "eligibility_residency": s.get("eligibility_residency", []),
            }
        rule = evaluate_scheme_eligibility(profile or {}, meta)
        out = dict(s)
        out["eligibility_status"] = rule["status"]
        out["eligibility_reasons"] = rule["reasons"]
        out["eligibility_unknowns"] = rule["unknowns"]
        annotated.append(out)

    order = {"eligible": 0, "unknown": 1, "ineligible": 2}
    annotated.sort(key=lambda x: (order.get(x.get("eligibility_status"), 1), -float(x.get("score", 0) or 0)))
    return annotated
