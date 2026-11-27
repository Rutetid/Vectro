from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from sentence_transformers import CrossEncoder

from chatbot.retrieve import (
    DEFAULT_MODEL_NAME,
    aggregate_by_scheme,
    bm25_rank,
    chroma_vector_rank,
    filter_candidate_indices,
    load_artifacts,
    reciprocal_rank_fusion,
)


DEFAULT_EVAL_PATH = Path(__file__).resolve().parent / "eval_queries.jsonl"
DEFAULT_INDEX_DIR = Path(__file__).resolve().parent / "chroma_index"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def load_eval_queries(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_profile_query(q: Dict[str, Any]) -> str:
    if q.get("query"):
        return str(q["query"])
    parts = ["Find relevant government schemes"]
    for k, label in [("age", "for {} year old"), ("occupation", "{}"), ("caste", "{}"), ("gender", "{}"), ("state", "in {}")]:
        v = q.get(k)
        if v is not None and str(v).strip():
            parts.append(label.format(v))
    if q.get("income") is not None:
        parts.append(f"with income under {q['income']}")
    return " ".join(parts)


def scheme_ids_from_ranked(chunks, fused_scores, max_schemes=5) -> List[str]:
    ranked = aggregate_by_scheme(chunks, fused_scores, max_schemes=max_schemes)
    return [r.get("scheme_id", "") for r in ranked]


def rerank_schemes(artifacts, query: str, fused_scores: Dict[int, float], reranker: CrossEncoder, max_schemes: int = 5) -> List[str]:
    # Take top candidates by RRF, rerank by cross-encoder using best evidence chunk per scheme
    prelim = aggregate_by_scheme(artifacts.chunks, fused_scores, max_schemes=20)
    if not prelim:
        return []
    pairs = [(query, p.get("evidence", "")) for p in prelim]
    scores = reranker.predict(pairs)
    for p, s in zip(prelim, scores):
        p["_rerank"] = float(s)
    prelim.sort(key=lambda x: x["_rerank"], reverse=True)
    return [p.get("scheme_id", "") for p in prelim[:max_schemes]]


def eval_method(name: str, run_fn, queries: List[Dict[str, Any]], k: int = 5) -> Dict[str, Any]:
    recall_hits = 0
    rr_total = 0.0
    latencies = []
    per_query = []
    for q in queries:
        gold = set(q.get("relevant_scheme_ids", []))
        t0 = time.perf_counter()
        predicted = run_fn(q)
        latencies.append((time.perf_counter() - t0) * 1000)
        hit_rank = None
        for i, sid in enumerate(predicted[:k], start=1):
            if sid in gold:
                hit_rank = i
                break
        hit = hit_rank is not None
        recall_hits += 1 if hit else 0
        rr_total += (1.0 / hit_rank) if hit_rank else 0.0
        per_query.append({"query": q.get("query") or build_profile_query(q), "gold": list(gold), "predicted": predicted[:k], "hit_rank": hit_rank})
    n = max(len(queries), 1)
    return {
        "method": name,
        "n": len(queries),
        f"Recall@{k}": round(recall_hits / n, 4),
        "MRR": round(rr_total / n, 4),
        "Avg latency (ms)": round(sum(latencies) / n, 2),
        "per_query": per_query,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate retrieval methods")
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL_NAME)
    parser.add_argument("--no-reranker", action="store_true")
    args = parser.parse_args()

    artifacts = load_artifacts(args.index_dir, model_name=args.model)
    queries = load_eval_queries(args.eval_file)
    if not queries:
        raise SystemExit(f"No eval queries found in {args.eval_file}")

    reranker = None
    if not args.no_reranker:
        reranker = CrossEncoder(RERANK_MODEL)

    def make_run(mode: str):
        def run(q):
            query = build_profile_query(q)
            candidates = filter_candidate_indices(
                artifacts.chunks,
                state=q.get("state"), categories=q.get("categories"), level=q.get("level"),
                age=q.get("age"), income=q.get("income"), gender=q.get("gender"),
                caste=q.get("caste"), residency=q.get("residency"),
            )
            if not candidates:
                return []
            vec = chroma_vector_rank(artifacts, query, candidates, top_k=50)
            bm = bm25_rank(artifacts, query, candidates, top_k=50)
            if mode == "bm25":
                fused = reciprocal_rank_fusion([bm], k=60)
                return scheme_ids_from_ranked(artifacts.chunks, fused, args.k)
            if mode == "vector":
                fused = reciprocal_rank_fusion([vec], k=60)
                return scheme_ids_from_ranked(artifacts.chunks, fused, args.k)
            fused = reciprocal_rank_fusion([vec, bm], k=60)
            if mode == "hybrid":
                return scheme_ids_from_ranked(artifacts.chunks, fused, args.k)
            if mode == "hybrid_rerank":
                return rerank_schemes(artifacts, query, fused, reranker, args.k)
            raise ValueError(mode)
        return run

    methods = ["bm25", "vector", "hybrid"] + ([] if args.no_reranker else ["hybrid_rerank"])
    results = [eval_method(m, make_run(m), queries, k=args.k) for m in methods]

    print("\n| Method | Recall@{} | MRR | Avg latency (ms) |".format(args.k))
    print("|---|---:|---:|---:|")
    label = {"bm25": "BM25 only", "vector": "Vector only", "hybrid": "Hybrid (RRF)", "hybrid_rerank": "Hybrid + reranker"}
    for r in results:
        print(f"| {label.get(r['method'], r['method'])} | {r[f'Recall@{args.k}']:.4f} | {r['MRR']:.4f} | {r['Avg latency (ms)']:.2f} |")

    out = {"k": args.k, "eval_file": str(args.eval_file), "index_dir": str(args.index_dir), "results": results}
    out_path = args.eval_file.with_suffix(".results.json")
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved detailed results to {out_path}")


if __name__ == "__main__":
    main()
