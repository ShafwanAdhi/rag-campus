# SISDAS RAG Assistant

SISDAS RAG Assistant is a campus information chatbot built with a FastAPI RAG backend and a TanStack Start React frontend.

## Repository Layout

```text
ta-sisdas/
  apps/
    api/        FastAPI backend, RAG pipeline, Groq integration
    web/        TanStack Start React frontend
  data/
    chroma/     Active local Chroma vector database
    documents/  Source PDF documents grouped by SISDAS domain
  docs/         Architecture and project notes
  scripts/      Reusable indexing and metadata utilities
```

## Backend

```powershell
cd apps/api
pip install -r requirements.txt
uvicorn main:app --reload
```

Set `GROQ_API_KEY` in `apps/api/.env` before running live chat requests.

## Frontend

```powershell
cd apps/web
npm install
npm run dev
```

Set `VITE_API_BASE_URL` in `apps/web/.env` when the backend is not running at `http://127.0.0.1:8000`.

## Runtime Checks

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/cache/stats
```

## Indexing

Validate metadata:

```powershell
python scripts/validate_metadata.py
```

Inspect Chroma:

```powershell
python scripts/inspect_chroma.py --details
```

Re-index all domains:

```powershell
python scripts/index_documents.py --reset
```

## RAG Evaluation

Run the official evaluation set:

```powershell
python scripts/evaluate_rag.py
```

Run only the first few cases while iterating:

```powershell
python scripts/evaluate_rag.py --limit 3
```

## Production Notes

Do not commit local secrets, dependency folders, generated build output, or local cache artifacts. The repository ignores `.env`, `node_modules`, Python cache folders, frontend build output, and the local Chroma database.

For deployment, generate or mount `data/chroma` on the server after indexing. Keep `apps/api/.env.example` and `apps/web/.env.example` as templates, then create real `.env` files only on the deployment machine.

## Docker Deployment

Prepare the production environment file on the server:

```bash
cp .env.production.example .env.production
```

Fill `GROQ_API_KEY`, `VOYAGE_API_KEY`, and `FRONTEND_ORIGINS` in `.env.production`.
For the default deployment under `https://ragcampus.shafwan.digital/`, keep:

```env
FRONTEND_ORIGINS=https://ragcampus.shafwan.digital
VITE_BASE_PATH=/
VITE_API_BASE_URL=/api
PUBLIC_HTTP_PORT=8081
```

Start the stack:

```bash
docker compose up -d --build
```

The Docker stack listens on `127.0.0.1:8081` by default. Put the host Nginx in front of it and proxy `ragcampus.shafwan.digital/` to that local port.
