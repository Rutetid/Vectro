# Vectro RAG API

Government scheme discovery using semantic search with FAISS and sentence-transformers.

## Features

- 🔍 Semantic search through government schemes
- 🚀 Fast FAISS vector database
- 🎯 Personalized recommendations based on user profile
- 📊 Relevance scoring

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
- FAISS (vector database)
- sentence-transformers
- LangChain
