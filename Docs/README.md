# Sensei

> An AI-powered Socratic learning assistant that guides students to understanding — not just answers.

## Overview

Sensei is a web-based educational chatbot that uses active learning mechanics to help students genuinely understand what they study. Unlike tools that simply answer questions, Sensei applies Socratic dialogue — asking guiding questions before giving direct answers — to build deeper retention and critical thinking.

Students can upload their own course materials (PDFs) and Sensei grounds its responses in those documents via a RAG pipeline. If no documents are uploaded, Sensei falls back to its general knowledge while staying scoped to the topic of the session. Every session has a defined scope, locked either by the first question or by the documents uploaded, keeping conversations focused.

Sensei also includes a Feynman evaluation mode: students explain a concept back in their own words and receive a structured score across the 7C's of communication, with detailed criticism and the option to retry.

## Features

- Socratic dialogue — guides students with questions before giving direct answers
- RAG pipeline — answers grounded in uploaded course materials when available
- Session scoping — topic locked at session start, off-topic questions redirected
- Feynman mode — student explains a concept, scored on the 7C's with detailed criticism
- BYOK (Bring Your Own Key) — sessions run on a shared Default Key with a daily allowance; a student can add their own Gemini key to lift the cap
- Session history — all sessions and Feynman scores saved and accessible
- Onboarding tour for first-time users

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js |
| Auth + Chat History + Metadata | Convex |
| AI Backend | FastAPI (Python) |
| Vector Database | Supabase (pgvector) |
| File Storage | Supabase Storage |
| LLM | Google Gemini (platform Default Key, or user's own via BYOK) |
| Embeddings | Google gemini-embedding-001 (1536-dim via MRL) |

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- A Convex account
- A Supabase account
- A Google Gemini API key for the platform Default Key (users may add their own via BYOK)

### Installation

```bash
git clone https://github.com/your-username/sensei.git
cd sensei

# Frontend
cd frontend
npm install
cp .env.example .env.local
npm run dev

# AI Backend
cd ../sensei-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

## Project Structure

```text
sensei/
├── frontend/               # Next.js app
│   ├── app/                # App router pages and layouts
│   ├── components/         # Reusable UI components
│   ├── convex/             # Convex schema, mutations, queries
│   └── lib/                # Utility functions, API client
│
├── sensei-api/             # FastAPI AI backend
│   ├── main.py             # App entry point, CORS, router registration
│   ├── routers/            # Route handlers (thin — delegate to services)
│   │   ├── ingest.py       # Document upload and processing routes
│   │   ├── chat.py         # Student Q&A routes
│   │   └── evaluate.py     # Feynman evaluation routes
│   ├── services/           # All business and AI logic
│   │   ├── embedder.py     # PDF extraction, chunking, embedding
│   │   ├── retriever.py    # Vector similarity search
│   │   ├── scorer.py       # Feynman 7C's scoring logic
│   │   └── gemini.py       # Single point of contact with Gemini API
│   ├── models/             # Pydantic request/response models
│   ├── config.py           # Environment variable loading
│   └── requirements.txt
│
└── docs/                   # Project documentation bundle
```

## Environment Variables

### Frontend (`frontend/.env.local`)

| Variable | Description | Required |
|---|---|---|
| `NEXT_PUBLIC_CONVEX_URL` | Convex deployment URL | Yes |
| `NEXT_PUBLIC_API_URL` | FastAPI base URL | Yes |

### AI Backend (`sensei-api/.env`)

| Variable | Description | Required |
|---|---|---|
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_KEY` | Supabase service role key | Yes |
| `GEMINI_API_KEY` | Platform Default Key, used for students without their own (ADR-0001) | Yes |
| `KEY_ENCRYPTION_SECRET` | Secret for encrypting/decrypting stored BYOK keys (ADR-0002) | Yes |
| `CONVEX_URL` | Convex deployment URL — server-to-server calls and JWKS fetch (ADR-0003) | Yes |
| `CONVEX_SERVICE_SECRET` | Shared secret for FastAPI → Convex purpose-built endpoints (ADR-0003) | Yes |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed frontend origins | Yes |

## License

MIT
