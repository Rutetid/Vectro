from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import os

from chatbot.retrieve import DEFAULT_MODEL_NAME, load_artifacts, retrieve_hybrid
from chatbot.generate import generate_schemes_response
from chatbot.profile_extract import extract_profile_from_message

# Load retrieval artifacts lazily to reduce startup memory
artifacts = None


def get_artifacts():
    global artifacts
    if artifacts is None:
        index_path = (
            "chatbot/chroma_index"
            if os.path.exists("chatbot/chroma_index")
            else "RAG/chatbot/chroma_index"
            if os.path.exists("RAG/chatbot/chroma_index")
            else "chatbot/hybrid_index"
            if os.path.exists("chatbot/hybrid_index")
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


class ChatRequest(BaseModel):
    message: str
    profile: Optional[UserProfile] = None
    profile_overrides: Optional[UserProfile] = None


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


def _run_rag(user: UserProfile, question: str):
    hybrid_artifacts = get_artifacts()
    profile_dict = user.model_dump()
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
        profile_for_rules=profile_dict,
    )
    if not search_output["results"]:
        return {
            "query": question,
            "total_schemes": 0,
            "meta": search_output["meta"],
            "context_chunks": search_output["context_chunks"],
            "answer": "I don't have enough information in my knowledge base to answer that. Please visit https://myscheme.gov.in for official details.",
            "schemes": [],
            "profile": profile_dict,
        }
    response = generate_schemes_response(retrieval_result=search_output, user_profile=profile_dict)
    response["profile"] = profile_dict
    return response


@app.post("/find-schemes")
def find_schemes(user: UserProfile):
    try:
        question = _build_query_from_profile(user)
        return _run_rag(user, question)
    except Exception as e:
        return {"error": "Internal processing error", "details": str(e)}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        message = (req.message or "").strip()
        if not message:
            return {"error": "Bad request", "details": "message is required"}

        extracted = extract_profile_from_message(message)
        merged = dict(extracted.get("profile") or {})

        override_profile = req.profile_overrides or req.profile
        if override_profile:
            for k, v in override_profile.model_dump().items():
                if v is not None and v != "" and v != []:
                    merged[k] = v

        user = UserProfile(**{k: merged.get(k) for k in UserProfile.model_fields.keys()})
        response = _run_rag(user, message)
        response["message"] = message
        response["extracted_profile"] = extracted.get("profile")
        response["missing_fields"] = extracted.get("missing_fields", [])
        response["extraction_source"] = extracted.get("source")
        return response
    except Exception as e:
        return {"error": "Internal processing error", "details": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
