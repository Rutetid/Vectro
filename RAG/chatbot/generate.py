from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

SYSTEM_PROMPT = """\
You are a government scheme recommendation assistant for Indian citizens. \
You help users discover welfare schemes they may be eligible for based on their profile.

## STRICT GROUNDING RULES

1. Answer ONLY using information explicitly stated in the RETRIEVED CONTEXT below. \
Do NOT use your general training knowledge to supplement or fill gaps.

2. Every factual claim MUST cite its source using [Source N] where N matches the \
chunk number. Example: "PM-KISAN provides ₹6,000 per year [Source 1]."

3. If the RETRIEVED CONTEXT does not contain enough information to answer the \
question, say exactly:
"I don't have enough information in my knowledge base to answer that. \
Please visit https://myscheme.gov.in for official details."
Do NOT guess or use outside knowledge.

4. If the context PARTIALLY answers the question, state what you can confirm \
and explicitly flag what remains unanswered.

5. Never fabricate scheme names, eligibility criteria, deadlines, or financial \
figures. Only state what appears in the source documents.

## ELIGIBILITY ASSESSMENT

When a user provides their profile, compare their attributes against the \
eligibility criteria in the retrieved context:
- If RULE ENGINE STATUS is provided for a scheme, treat it as authoritative. Do NOT override it.
- For `eligible`, explain which criteria are satisfied. For `ineligible`, explain the rule-engine reason. For `unknown`, clearly state missing user/scheme information.
- If the context does not contain eligibility criteria and no rule-engine status is available, say so rather than guessing.

## OUTPUT FORMAT

Structure your response as:

**Schemes You May Be Eligible For**
1. **[Scheme Name]** — [Source N]
   - Benefit: [what they receive]
   - Eligibility: [which criteria they meet]
   - How to Apply: [application process if available]

**Schemes You Are Not Eligible For** (if applicable)
1. **[Scheme Name]** — [Source N]
   - Reason: [specific criterion not met]

**Additional Information**
[Any relevant notes, deadlines, or links]

If no relevant schemes are found, say:
"I couldn't find specific schemes matching your profile. I recommend visiting \
https://myscheme.gov.in or contacting your local welfare office for guidance."
"""


def _build_user_prompt(
    retrieval_result: Dict[str, Any],
    user_profile: Dict[str, Any],
) -> str:
    parts: List[str] = []

    profile_str = json.dumps(
        {k: v for k, v in user_profile.items() if v is not None},
        indent=2,
        ensure_ascii=False,
    )
    parts.append(f"## USER PROFILE\n{profile_str}")

    schemes = retrieval_result.get("results", []) or retrieval_result.get("schemes", [])
    rule_lines = []
    for s in schemes:
        status = s.get("eligibility_status")
        if not status:
            continue
        reasons = "; ".join(s.get("eligibility_reasons", [])[:4])
        unknowns = "; ".join(s.get("eligibility_unknowns", [])[:3])
        rule_lines.append(
            f"- {s.get('scheme_name','Unknown')} [{s.get('scheme_id','')}]: status={status}"
            + (f"; reasons={reasons}" if reasons else "")
            + (f"; unknowns={unknowns}" if unknowns else "")
        )
    if rule_lines:
        parts.append("## RULE ENGINE ELIGIBILITY\n" + "\n".join(rule_lines))

    context_chunks = retrieval_result.get("context_chunks", [])
    if context_chunks:
        chunk_texts = []
        for i, chunk in enumerate(context_chunks, start=1):
            citation = chunk.get("citation", {})
            scheme = citation.get("scheme_name", "Unknown")
            section = citation.get("section", "general")
            source_url = citation.get("source_url", "")
            header = f"[Source {i}] {scheme} | {section}"
            if source_url:
                header += f" | {source_url}"
            chunk_texts.append(f"{header}\n{chunk.get('text', '')}")
        parts.append("## RETRIEVED CONTEXT\n" + "\n---\n".join(chunk_texts))

    query = retrieval_result.get("query", "")
    parts.append(f"## USER QUESTION\n{query}")

    return "\n\n".join(parts)


def generate_schemes_response(
    retrieval_result: Dict[str, Any],
    user_profile: Dict[str, Any],
    model: str = "google/gemini-2.5-flash",
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> Dict[str, Any]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {
            "answer": "Generation service is not configured. Set OPENROUTER_API_KEY.",
            "schemes": retrieval_result.get("results", []),
            "context_chunks": retrieval_result.get("context_chunks", []),
            "meta": retrieval_result.get("meta", {}),
        }

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    user_prompt = _build_user_prompt(retrieval_result, user_profile)

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        answer = response.choices[0].message.content or ""
    except Exception as e:
        answer = (
            f"Error generating response: {e}. "
            "Here are the raw retrieved results instead."
        )

    return {
        "query": retrieval_result.get("query", ""),
        "answer": answer,
        "schemes": retrieval_result.get("results", []),
        "context_chunks": retrieval_result.get("context_chunks", []),
        "meta": retrieval_result.get("meta", {}),
    }
