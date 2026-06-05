from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import faiss
import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi

from chatbot.ingest import tokenize_for_bm25


DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

ASSISTANT_INSTRUCTIONS = [
    "Grounding: Answer ONLY from provided context.",
    "Escape Hatch: If you don't know, say so.",
    "Citations: Cite your sources with metadata.",
    "Structure: Label each chunk clearly.",
]


@dataclass
class HybridArtifacts:
    chunks: List[Dict[str, Any]]
    vectors: np.ndarray
    faiss_index: faiss.Index
    bm25_tokens: List[List[str]]
    embeddings: HuggingFaceEmbeddings


def load_artifacts(
    index_dir: Path, model_name: str = DEFAULT_MODEL_NAME
) -> HybridArtifacts:
    index_dir = Path(index_dir)
    chunks: List[Dict[str, Any]] = []
    with (index_dir / "chunks.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    vectors = np.load(index_dir / "vectors.npy")
    faiss_index = faiss.read_index(str(index_dir / "faiss.index"))
    with (index_dir / "bm25_tokens.pkl").open("rb") as handle:
        bm25_tokens = pickle.load(handle)

    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
    )

    return HybridArtifacts(
        chunks=chunks,
        vectors=vectors,
        faiss_index=faiss_index,
        bm25_tokens=bm25_tokens,
        embeddings=embeddings,
    )


def _normalize_query_vector(
    embeddings: HuggingFaceEmbeddings, query: str
) -> np.ndarray:
    vec = np.array(embeddings.embed_query(query), dtype=np.float32)
    norm = np.linalg.norm(vec)
    if norm > 1e-12:
        vec = vec / norm
    return vec


def _is_all_or_empty(value: str) -> bool:
    return not value or value.lower() in {"all", "all states", "na", "n/a", "none"}


def _norm_gender(value: Optional[str]) -> str:
    text = (value or "").strip().lower()
    if text in {"male", "m"}:
        return "male"
    if text in {"female", "f"}:
        return "female"
    return ""


def _norm_residency(value: Optional[str]) -> str:
    text = (value or "").strip().lower()
    if "rural" in text:
        return "rural"
    if "urban" in text:
        return "urban"
    return ""


def _norm_caste(value: Optional[str]) -> str:
    text = (value or "").strip().lower()
    mapping = {
        "scheduled caste": "sc",
        "sc": "sc",
        "scheduled tribe": "st",
        "st": "st",
        "other backward class": "obc",
        "obc": "obc",
        "general": "general",
        "bpl": "bpl",
    }
    return mapping.get(text, text)


def _metadata_passes_profile(
    meta: Dict[str, Any],
    age: Optional[int],
    income: Optional[int],
    gender: Optional[str],
    caste: Optional[str],
    residency: Optional[str],
) -> bool:
    min_age = meta.get("eligibility_min_age")
    max_age = meta.get("eligibility_max_age")
    max_income = meta.get("eligibility_max_income")
    required_gender = str(meta.get("eligibility_gender") or "any").lower()
    required_caste_tags = [
        str(item).lower() for item in (meta.get("eligibility_caste_tags") or [])
    ]
    required_residency = [
        str(item).lower() for item in (meta.get("eligibility_residency") or [])
    ]

    if age is not None:
        if min_age is not None and age < int(min_age):
            return False
        if max_age is not None and age > int(max_age):
            return False

    if income is not None and max_income is not None and income > int(max_income):
        return False

    user_gender = _norm_gender(gender)
    if (
        user_gender
        and required_gender in {"male", "female"}
        and user_gender != required_gender
    ):
        return False

    user_caste = _norm_caste(caste)
    if user_caste and required_caste_tags and user_caste not in required_caste_tags:
        return False

    user_residency = _norm_residency(residency)
    if (
        user_residency
        and required_residency
        and user_residency not in required_residency
    ):
        return False

    return True


def filter_candidate_indices(
    chunks: Sequence[Dict[str, Any]],
    state: Optional[str] = None,
    categories: Optional[List[str]] = None,
    level: Optional[str] = None,
    age: Optional[int] = None,
    income: Optional[int] = None,
    gender: Optional[str] = None,
    caste: Optional[str] = None,
    residency: Optional[str] = None,
) -> List[int]:
    state_norm = (state or "").strip().lower()
    categories_norm = [c.strip().lower() for c in (categories or []) if c.strip()]
    level_norm = (level or "").strip().lower()

    candidate_indices: List[int] = []
    for i, chunk in enumerate(chunks):
        meta = chunk.get("metadata", {})

        meta_state = str(meta.get("state", "")).strip()
        if state_norm:
            if _is_all_or_empty(meta_state):
                pass
            elif meta_state.lower() != state_norm:
                continue

        if level_norm:
            meta_level = str(meta.get("level", "")).strip().lower()
            if level_norm not in meta_level:
                continue

        if categories_norm:
            meta_categories = [
                str(item).strip().lower() for item in meta.get("categories", [])
            ]
            if not any(cat in meta_categories for cat in categories_norm):
                continue

        if not _metadata_passes_profile(meta, age, income, gender, caste, residency):
            continue

        candidate_indices.append(i)

    return candidate_indices


def faiss_rank(
    artifacts: HybridArtifacts,
    query: str,
    candidate_indices: List[int],
    top_k: int,
) -> List[int]:
    if not candidate_indices:
        return []

    candidate_vectors = artifacts.vectors[candidate_indices]
    local_index = faiss.IndexFlatIP(candidate_vectors.shape[1])
    local_index.add(candidate_vectors)

    query_vec = _normalize_query_vector(artifacts.embeddings, query).reshape(1, -1)
    _, local_ids = local_index.search(query_vec, min(top_k, len(candidate_indices)))
    ranked: List[int] = []
    for local_id in local_ids[0]:
        if local_id < 0:
            continue
        ranked.append(candidate_indices[int(local_id)])
    return ranked


def bm25_rank(
    artifacts: HybridArtifacts,
    query: str,
    candidate_indices: List[int],
    top_k: int,
) -> List[int]:
    if not candidate_indices:
        return []

    corpus = [artifacts.bm25_tokens[idx] for idx in candidate_indices]
    bm25 = BM25Okapi(corpus)
    query_tokens = tokenize_for_bm25(query)
    scores = bm25.get_scores(query_tokens)

    sorted_local = np.argsort(scores)[::-1][: min(top_k, len(candidate_indices))]
    return [candidate_indices[int(i)] for i in sorted_local]


def reciprocal_rank_fusion(
    rank_lists: List[List[int]], k: int = 60
) -> Dict[int, float]:
    fused: Dict[int, float] = {}
    for ranked in rank_lists:
        for position, doc_idx in enumerate(ranked, start=1):
            fused[doc_idx] = fused.get(doc_idx, 0.0) + 1.0 / (k + position)
    return fused


def _citation_for_chunk(
    chunk: Dict[str, Any], score: float, label: str
) -> Dict[str, Any]:
    meta = chunk.get("metadata", {})
    return {
        "label": label,
        "chunk_id": chunk.get("chunk_id", ""),
        "section": chunk.get("section", ""),
        "score": round(float(score), 6),
        "scheme_id": chunk.get("scheme_id", ""),
        "scheme_name": meta.get("scheme_name", ""),
        "state": meta.get("state", ""),
        "level": meta.get("level", ""),
        "source_url": meta.get("source_url", ""),
    }


def _truncate_text(text: str, max_chars: int = 600) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def aggregate_by_scheme(
    chunks: Sequence[Dict[str, Any]],
    fused_scores: Dict[int, float],
    max_schemes: int = 5,
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    ranked_chunk_indices = sorted(
        fused_scores.keys(), key=lambda idx: fused_scores[idx], reverse=True
    )

    for idx in ranked_chunk_indices:
        score = fused_scores[idx]
        chunk = chunks[idx]
        scheme_id = chunk["scheme_id"]
        meta = chunk.get("metadata", {})
        entry = grouped.setdefault(
            scheme_id,
            {
                "scheme_id": scheme_id,
                "scheme_name": meta.get("scheme_name", scheme_id),
                "score": 0.0,
                "state": meta.get("state", ""),
                "level": meta.get("level", ""),
                "categories": meta.get("categories", []),
                "matched_sections": set(),
                "evidence": "",
                "citations": [],
            },
        )

        entry["score"] = max(entry["score"], float(score))
        entry["matched_sections"].add(chunk.get("section", "unknown"))
        if not entry["evidence"]:
            entry["evidence"] = chunk.get("text", "")

        if len(entry["citations"]) < 3:
            label = f"CHUNK-{len(entry['citations']) + 1}"
            entry["citations"].append(_citation_for_chunk(chunk, score, label))

    results: List[Dict[str, Any]] = []
    for value in grouped.values():
        section_bonus = 0.01 * len(value["matched_sections"])
        value["score"] = round(value["score"] + section_bonus, 6)
        value["matched_sections"] = sorted(value["matched_sections"])
        value["evidence"] = _truncate_text(value["evidence"], max_chars=800)
        results.append(value)

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:max_schemes]


def _build_context_chunks(
    chunks: Sequence[Dict[str, Any]],
    fused_scores: Dict[int, float],
    max_chunks: int = 8,
) -> List[Dict[str, Any]]:
    ranked = sorted(
        fused_scores.keys(), key=lambda idx: fused_scores[idx], reverse=True
    )[:max_chunks]
    context: List[Dict[str, Any]] = []
    for i, idx in enumerate(ranked, start=1):
        chunk = chunks[idx]
        label = f"CHUNK-{i}"
        context.append(
            {
                "label": label,
                "text": _truncate_text(chunk.get("text", ""), max_chars=700),
                "citation": _citation_for_chunk(chunk, fused_scores[idx], label),
            }
        )
    return context


def retrieve_hybrid(
    artifacts: HybridArtifacts,
    query: str,
    state: Optional[str] = None,
    categories: Optional[List[str]] = None,
    level: Optional[str] = None,
    age: Optional[int] = None,
    income: Optional[int] = None,
    gender: Optional[str] = None,
    caste: Optional[str] = None,
    residency: Optional[str] = None,
    faiss_top_k: int = 50,
    bm25_top_k: int = 50,
    max_schemes: int = 5,
) -> Dict[str, Any]:
    candidate_indices = filter_candidate_indices(
        chunks=artifacts.chunks,
        state=state,
        categories=categories,
        level=level,
        age=age,
        income=income,
        gender=gender,
        caste=caste,
        residency=residency,
    )

    meta = {
        "total_chunks": len(artifacts.chunks),
        "candidate_chunks": len(candidate_indices),
        "faiss_hits": 0,
        "bm25_hits": 0,
        "filters_applied": {
            "state": state,
            "categories": categories or [],
            "level": level,
            "age": age,
            "income": income,
            "gender": gender,
            "caste": caste,
            "residency": residency,
        },
    }

    if not candidate_indices:
        return {
            "query": query,
            "total_schemes": 0,
            "results": [],
            "context_chunks": [],
            "assistant_instructions": ASSISTANT_INSTRUCTIONS,
            "grounded_answer": "I don't know based on the provided context.",
            "meta": meta,
        }

    faiss_hits = faiss_rank(artifacts, query, candidate_indices, top_k=faiss_top_k)
    bm25_hits = bm25_rank(artifacts, query, candidate_indices, top_k=bm25_top_k)
    fused_scores = reciprocal_rank_fusion([faiss_hits, bm25_hits], k=60)
    ranked_schemes = aggregate_by_scheme(
        artifacts.chunks, fused_scores, max_schemes=max_schemes
    )
    context_chunks = _build_context_chunks(artifacts.chunks, fused_scores, max_chunks=8)

    meta["faiss_hits"] = len(faiss_hits)
    meta["bm25_hits"] = len(bm25_hits)

    grounded_answer = "I don't know based on the provided context."
    if ranked_schemes:
        grounded_answer = "Top schemes returned from filtered context."

    return {
        "query": query,
        "total_schemes": len(ranked_schemes),
        "results": ranked_schemes,
        "context_chunks": context_chunks,
        "assistant_instructions": ASSISTANT_INSTRUCTIONS,
        "grounded_answer": grounded_answer,
        "meta": meta,
    }
