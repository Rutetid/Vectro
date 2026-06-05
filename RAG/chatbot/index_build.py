from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings

from chatbot.ingest import (
    build_chunk_corpus,
    load_jsonl,
    tokenize_for_bm25,
    write_jsonl,
)


DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def create_sample_dataset(
    source_path: Path, target_path: Path, limit: int = 100
) -> int:
    rows = load_jsonl(source_path, limit=limit)
    write_jsonl(target_path, rows)
    return len(rows)


def build_indexes(
    data_path: Path,
    output_dir: Path,
    limit: Optional[int] = None,
    model_name: str = DEFAULT_MODEL_NAME,
    max_words: int = 380,
    overlap_words: int = 70,
    batch_size: int = 32,
) -> Dict[str, Any]:
    chunks = build_chunk_corpus(
        data_path=data_path,
        limit=limit,
        max_words=max_words,
        overlap_words=overlap_words,
    )
    if not chunks:
        raise ValueError("No chunks were generated from the provided dataset")

    texts = [chunk["text"] for chunk in chunks]
    tokenized_corpus = [tokenize_for_bm25(text) for text in texts]

    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True, "batch_size": batch_size},
    )

    vectors = np.array(embeddings.embed_documents(texts), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.clip(norms, 1e-12, None)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    output_dir.mkdir(parents=True, exist_ok=True)

    sidecar_path = output_dir / "chunks.jsonl"
    with sidecar_path.open("w", encoding="utf-8") as handle:
        for row in chunks:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    faiss.write_index(index, str(output_dir / "faiss.index"))
    np.save(output_dir / "vectors.npy", vectors)

    with (output_dir / "bm25_tokens.pkl").open("wb") as handle:
        pickle.dump(tokenized_corpus, handle)

    manifest = {
        "data_path": str(data_path),
        "index_type": "IndexFlatIP",
        "embedding_model": model_name,
        "total_chunks": len(chunks),
        "max_words": max_words,
        "overlap_words": overlap_words,
        "batch_size": batch_size,
        "files": {
            "faiss": "faiss.index",
            "vectors": "vectors.npy",
            "chunks": "chunks.jsonl",
            "bm25_tokens": "bm25_tokens.pkl",
        },
    }
    with (output_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    return manifest


def _default_dataset_path() -> Path:
    return Path(__file__).resolve().parent / "rag_data.jsonl"


def _default_sample_path() -> Path:
    return Path(__file__).resolve().parent / "rag_data_100.jsonl"


def _default_index_path() -> Path:
    return Path(__file__).resolve().parent / "hybrid_index"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build FAISS + BM25 hybrid index")
    parser.add_argument("--data", type=Path, default=_default_dataset_path())
    parser.add_argument("--output", type=Path, default=_default_index_path())
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--build-sample", action="store_true")
    parser.add_argument("--sample-output", type=Path, default=_default_sample_path())
    parser.add_argument("--max-words", type=int, default=380)
    parser.add_argument("--overlap-words", type=int, default=70)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL_NAME)
    args = parser.parse_args()

    data_path = args.data
    if args.build_sample:
        total = create_sample_dataset(
            args.data, args.sample_output, limit=args.sample_size
        )
        data_path = args.sample_output
        print(f"Created sample dataset with {total} rows at {data_path}")

    manifest = build_indexes(
        data_path=data_path,
        output_dir=args.output,
        limit=args.limit,
        model_name=args.model,
        max_words=args.max_words,
        overlap_words=args.overlap_words,
        batch_size=args.batch_size,
    )
    print(f"Built index with {manifest['total_chunks']} chunks at {args.output}")


if __name__ == "__main__":
    main()
