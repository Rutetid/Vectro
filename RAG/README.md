# Vectro RAG API

Government scheme discovery using hybrid retrieval (ChromaDB vector search + BM25) with grounded LLM answers.

## Features

- 🔍 Hybrid search: ChromaDB semantic vectors + BM25 lexical ranking (RRF fusion)
- 🗂️ Persistent ChromaDB index (`chatbot/chroma_index/chroma_db`)
- 🎯 Metadata-aware filtering (state/category/age/income/gender/caste/residency)
- 🧾 Grounded answer generation with source citations

## API Endpoints

### `POST /find-schemes`

Find relevant government schemes based on user profile.

**Request Body:**

```json
{
  "age": 25,
  "gender": "male",
  "income": 500000,
  "state": "Maharashtra",
  "occupation": "private",
  "caste": "general",
  "residency": "urban"
}
```

**Response:**

```json
{
  "query": "Find government schemes for 25 year old private general male in Maharashtra with income under 500000",
  "total_schemes": 5,
  "results": [
    {
      "index": 1,
      "scheme_text": "Scheme details...",
      "relevance_score": 0.85
    }
  ]
}
```

## Local Development

```bash
pip install -r requirements.txt

# Build index (small smoke test)
python -m chatbot.index_build --data chatbot/rag_data_100.jsonl --output chatbot/chroma_index --limit 100

# Full index
# python -m chatbot.index_build --data chatbot/rag_data.jsonl --output chatbot/chroma_index

uvicorn main:app --reload --port 7860
```

## Deployment

### Option 1: Hugging Face Spaces (Recommended)

1. Create new Space at https://huggingface.co/spaces
2. Select Docker SDK
3. Push this repository

### Option 2: Railway

```bash
railway login
railway up
```

### Option 3: Render

- Use optimized `Procfile` with single worker
- Requires at least 1GB RAM (paid plan)

## Tech Stack

- FastAPI
- ChromaDB (persistent vector database)
- BM25 (`rank-bm25`) + Reciprocal Rank Fusion
- sentence-transformers
- OpenRouter/OpenAI SDK for generation
