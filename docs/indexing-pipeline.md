# Indexing Pipeline

The indexing pipeline is now script-based. The original notebooks remain in `notebooks/indexing`, but repeatable indexing should use `scripts/index_documents.py`.

## Inputs

PDF documents live in:

```text
data/documents/
```

Metadata is centralized in:

```text
scripts/domain_registry.py
```

Each PDF must have metadata values for its domain. The metadata is attached to every page/chunk before insertion into Chroma.

## Output

The active Chroma database lives in:

```text
data/chroma/
```

The backend reads this path through:

```text
apps/api/.env
```

with:

```text
CHROMA_DIR=../../data/chroma
```

Structured facts extracted from tables/lists live in:

```text
data/structured_facts.json
```

The backend reads this path through:

```text
STRUCTURED_FACTS_PATH=../../data/structured_facts.json
```

## Validate Metadata

Run this before indexing:

```powershell
python scripts/validate_metadata.py
```

It checks:

- every PDF has a metadata entry
- every metadata entry points to an existing PDF
- required metadata keys are present

## Inspect Existing Chroma

```powershell
python scripts/inspect_chroma.py
python scripts/inspect_chroma.py --details
```

This prints collections, chunk counts, metadata keys, and optional detailed metadata values.

## Re-index

Set the embedding API key in:

```text
apps/api/.env
```

with:

```text
EMBEDDING_PROVIDER=voyage
EMBEDDING_MODEL=voyage-multilingual-2
VOYAGE_API_KEY=your_voyage_api_key_here
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Index all domains:

```powershell
python scripts/index_documents.py --reset
```

Index one domain:

```powershell
python scripts/index_documents.py --domain academic_administration --reset
```

Rebuild only the structured fact index without embedding calls:

```powershell
python scripts/build_fact_index.py
```

Use a custom Tesseract path when OCR is needed:

```powershell
python scripts/index_documents.py --reset --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

If `TESSERACT_CMD` is set in `apps/api/.env`, the `--tesseract-cmd` argument is
not required.

## Notes

The script keeps the existing extraction strategy:

- try normal PDF text extraction first
- use OCR only when normal extraction is too small
- split text into 500-token chunks with 100-token overlap
- embed chunks with Voyage AI `voyage-multilingual-2` by default
- write each domain to its matching Chroma collection
- rebuild a structured fact index for table/list questions such as program
  study counts per faculty

The backend must use the same embedding provider and model at runtime, because
query vectors and indexed document vectors must be in the same embedding space.
