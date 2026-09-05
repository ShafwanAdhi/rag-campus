# Groq Model Strategy for SISDAS RAG

This document describes the proposed model architecture for moving SISDAS RAG
to Groq API based generation while using a separate embedding provider for
retrieval.

The recommendation is based on the model list provided in the screenshot:

- `groq/compound`
- `groq/compound-mini`
- `openai/gpt-oss-120b`
- `openai/gpt-oss-20b`
- `openai/gpt-oss-safeguard-20b`
- `qwen/qwen3.6-27b`
- `qwen/qwen3.8-27b`
- `meta-llama/llama-prompt-guard-2-22m`
- `meta-llama/llama-prompt-guard-2-86m`
- `whisper-large-v3`
- `whisper-large-v3-turbo`

## Current Pipeline

Current backend flow:

1. User query arrives through `/chat` or `/chat/stream`.
2. Query planner detects structured fact intents such as aggregate counts and
   entity lookups.
3. Domain router classifies the query into one or more SISDAS domains.
4. Structured fact index is checked first for table/list questions.
5. A domain analyzer detects query intent, metadata filters, and rerank keywords.
6. Chroma retrieves candidate chunks using Voyage AI `voyage-multilingual-2`
   embeddings.
7. Domain reranker promotes relevant chunks with keyword and metadata heuristics.
8. Answer generator builds a context prompt and produces the final answer.
9. Backend adds source metadata and returns whitebox process details.

## Recommended Default Model Assignment

### Prompt Guard

Default model: `meta-llama/llama-prompt-guard-2-22m`

Use this before routing to detect prompt injection or malicious instructions inside the user query. It is small and suitable for a cheap first pass.

Escalation model: `meta-llama/llama-prompt-guard-2-86m`

Use this only when the 22m model returns an uncertain or borderline result.

### Domain Router

Default model: `groq/compound-mini`

The router only needs compact JSON classification. It should be fast, low cost, and consistent. The prompt should force strict JSON output.

Fallback model: `openai/gpt-oss-20b`

Use this when `compound-mini` fails to produce valid JSON after repair/parsing attempts.

### Domain Query Analyzer

Default model: `groq/compound-mini`

Analyzer output is structured JSON: query intent, metadata filters, rerank keywords, and reason. This is a good fit for the mini model because the prompt contains explicit allowed values and the Python code already validates all outputs.

Fallback model: `qwen/qwen3.8-27b`

Use Qwen when Indonesian phrasing is complex or when `compound-mini` repeatedly returns invalid JSON. It is a good candidate for multilingual classification and extraction.

### Retrieval Embeddings

Default model: Voyage AI `voyage-multilingual-2`.

The provided Groq model list does not include an embedding model. Retrieval
therefore uses Voyage AI as a separate embedding API. Ollama `bge-m3` remains an
optional local fallback, but it should not be mixed with a Voyage-built Chroma
index.

### Reranking

Default strategy: keep deterministic heuristic reranking in Python.

Do not call an LLM for every retrieved chunk by default. Reranking can multiply API calls and hit RPM/TPM limits quickly. The current domain-specific keyword and metadata scoring is transparent and easier to defend in a thesis.

Optional LLM rerank mode: `groq/compound-mini`

Use only for offline evaluation or a small top-N candidate pass, not as the production default.

### Final Answer Generation

Default model: `groq/compound`

The final answer step needs the best balance of answer quality and available token budget. The screenshot shows `compound` and `compound-mini` with much larger TPM than the other text models, so they are safer for RAG prompts that include several context chunks.

Fallback model: `groq/compound-mini`

Use when `compound` fails, times out, or reaches a rate limit.

Quality mode: `openai/gpt-oss-120b`

Use only as an optional setting for low-volume, quality-focused evaluation. It has a smaller TPM limit in the screenshot, so it should not be the default for context-heavy RAG answers.

### Answer Safety Check

Default model: none for normal campus QA.

Most SISDAS answers are administrative, academic, finance, facility, or graduation information. A mandatory second LLM safety pass may add latency without much benefit.

Optional model: `openai/gpt-oss-safeguard-20b`

Use for future high-risk categories or public deployment moderation.

### Audio Input

Default model: `whisper-large-v3-turbo`

Use if SISDAS adds voice questions. It is the better default for latency.

Accuracy mode: `whisper-large-v3`

Use when transcription accuracy matters more than speed.

## Model Matrix

| Pipeline Step | Default | Fallback | Reason |
| --- | --- | --- | --- |
| Prompt guard | `meta-llama/llama-prompt-guard-2-22m` | `meta-llama/llama-prompt-guard-2-86m` | Fast first-pass injection detection |
| Domain router | `groq/compound-mini` | `openai/gpt-oss-20b` | Small JSON classification task |
| Domain analyzer | `groq/compound-mini` | `qwen/qwen3.8-27b` | Structured extraction with Indonesian support |
| Embedding retrieval | `voyage-multilingual-2` | local `bge-m3` optional | Groq list does not include embeddings |
| Reranking | Python heuristics | `groq/compound-mini` optional | Transparent and API-efficient |
| Final answer | `groq/compound` | `groq/compound-mini` | Best token budget fit for RAG context |
| Quality evaluation | `openai/gpt-oss-120b` | `groq/compound` | Optional, not production default |
| Audio transcription | `whisper-large-v3-turbo` | `whisper-large-v3` | Future voice input |

## Rate Limit Strategy

Use the fewest LLM calls possible per request:

1. Prompt guard: 1 small call.
2. Router: 1 call.
3. Analyzer: 1 call per selected domain.
4. Retrieval: Voyage embedding call, no Groq.
5. Reranking: local heuristic, no Groq.
6. Final answer: 1 call.

For a single-domain query, the expected Groq calls are 3 to 4. For a multi-domain query, analyzer calls increase linearly. This is why reranking should remain local.

## Recommended Implementation Direction

1. Add a Groq client wrapper in backend config/LLM layer.
2. Load secrets and model IDs from `.env`.
3. Replace hardcoded Gemini key with `GROQ_API_KEY`.
4. Use Voyage AI `voyage-multilingual-2` for document indexing and runtime query
   embeddings.
5. Make router and analyzers return strict JSON and add repair/retry logic.
6. Keep current source attribution and whitebox reports.
7. Add tests that mock the Groq client instead of calling the real API.

## Repo Cleanup Direction

Target structure:

```text
ta-sisdas/
  apps/
    api/
    web/
  data/
    chroma/
    chroma_legacy_empty/
    documents/
  docs/
  notebooks/
    indexing/
  scripts/
```

Suggested migration:

1. `sisdas-campus-guide` is moved to `apps/web`.
2. `sisdas-rag-inference-api` is moved to `apps/api`.
3. `document` is moved to `data/documents`.
4. Active Chroma data is moved to `data/chroma`.
5. Old indexing notebooks are moved to `notebooks/indexing` as experiment records.
6. Reusable indexing utilities live in `scripts`.

The root-level `data/chroma_legacy_empty` directory is retained only as a migration artifact from the previous empty root Chroma database.
