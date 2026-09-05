# RAG Evaluation

The official SISDAS RAG evaluation set lives at:

```text
data/evaluation/rag_eval_set.json
```

Each case defines:

- `question`
- `expected_domains`
- `expected_intent`
- `expected_sources`
- `expected_topics`
- `key_facts`

Run the evaluator from the repository root:

```powershell
python scripts/evaluate_rag.py
```

Use a smaller sample during iteration:

```powershell
python scripts/evaluate_rag.py --limit 3
```

The evaluator reports:

- domain accuracy
- intent accuracy
- source hit@1
- source hit@3
- topic hit@3
- key fact coverage
- domain error rate
- average latency

Use `--json` to print the full machine-readable result:

```powershell
python scripts/evaluate_rag.py --json
```
