# Repository Structure

The project is organized as a small monorepo:

```text
ta-sisdas/
  apps/
    api/
    web/
  data/
    chroma/
    documents/
  docs/
  scripts/
```

## apps/api

FastAPI backend for the RAG pipeline. It contains:

- domain routing
- domain query analysis
- Chroma retrieval
- heuristic reranking
- answer generation through Groq
- streaming and non-streaming chat endpoints

The backend reads local secrets and runtime configuration from `apps/api/.env`.

## apps/web

TanStack Start React frontend. It contains the SISDAS chat UI, process summary UI, source cards, and document listing page.

## data/documents

Source PDFs grouped by SISDAS domain:

- `domain1_academic_administration`
- `domain2_facilities_and_campus_services`
- `domain3_finance_tuition_and_scholarship`
- `domain4_thesis_final_project_and_graduation`

## data/chroma

Active local Chroma vector database used by the backend. The backend default `CHROMA_DIR` points here through `apps/api/.env`.

## scripts

Reusable operational utilities:

- `domain_registry.py`: domain directory and metadata registry
- `validate_metadata.py`: validates PDF files against metadata registry
- `inspect_chroma.py`: inspects Chroma collections and metadata
- `index_documents.py`: indexes source PDFs into Chroma
