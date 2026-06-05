from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import os

from chatbot.retrieve import DEFAULT_MODEL_NAME, load_artifacts, retrieve_hybrid

# Load retrieval artifacts lazily to reduce startup memory
artifacts = None


def get_artifacts():
    global artifacts
    if artifacts is None:
        index_path = (
            "chatbot/hybrid_index"
            if os.path.exists("chatbot")
            else "RAG/chatbot/hybrid_index"
        )
        artifacts = load_artifacts(index_path, model_name=DEFAULT_MODEL_NAME)
    return artifacts


app = FastAPI(title="Vectro RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserProfile(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    income: Optional[int] = None
    state: Optional[str] = None
    occupation: Optional[str] = None
    caste: Optional[str] = None
    residency: Optional[str] = None
    level: Optional[str] = None
    categories: Optional[List[str]] = None
    query: Optional[str] = None


def _build_query_from_profile(user: UserProfile) -> str:
    if user.query and user.query.strip():
        return user.query.strip()

    query_parts = ["Find relevant government schemes"]

    if user.age is not None:
        query_parts.append(f"for {user.age} year old")
    if user.occupation:
        query_parts.append(user.occupation)
    if user.caste:
        query_parts.append(user.caste)
    if user.gender:
        query_parts.append(user.gender)
    if user.state:
        query_parts.append(f"in {user.state}")
    if user.income is not None:
        query_parts.append(f"with income under {user.income}")
    if user.residency:
        query_parts.append(f"from {user.residency} area")
    if user.categories:
        query_parts.append(f"focused on {' and '.join(user.categories)}")

    return " ".join(query_parts)


@app.get("/")
def root():
    return {"status": "ok", "message": "Vectro RAG API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/find-schemes")
def find_schemes(user: UserProfile):
    try:
        hybrid_artifacts = get_artifacts()  # Lazy load
        question = _build_query_from_profile(user)
        search_output = retrieve_hybrid(
            artifacts=hybrid_artifacts,
            query=question,
            state=user.state,
            categories=user.categories,
            level=user.level,
            age=user.age,
            income=user.income,
            gender=user.gender,
            caste=user.caste,
            residency=user.residency,
            faiss_top_k=50,
            bm25_top_k=50,
            max_schemes=5,
        )

        if not search_output["results"]:
            return {
                "query": question,
                "total_schemes": 0,
                "meta": search_output["meta"],
                "assistant_instructions": search_output["assistant_instructions"],
                "context_chunks": search_output["context_chunks"],
                "grounded_answer": search_output["grounded_answer"],
                "message": "No government schemes found matching the user profile.",
            }

        return {
            "query": question,
            "total_schemes": search_output["total_schemes"],
            "meta": search_output["meta"],
            "assistant_instructions": search_output["assistant_instructions"],
            "grounded_answer": search_output["grounded_answer"],
            "context_chunks": search_output["context_chunks"],
            "results": search_output["results"],
        }

    except Exception as e:
        return {"error": "Internal processing error", "details": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
