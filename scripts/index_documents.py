from __future__ import annotations

import argparse
import io
import os
import re
import sys
from pathlib import Path
from typing import Iterable, List

from domain_registry import DEFAULT_CHROMA_DIR, DEFAULT_DOCUMENTS_DIR, DOMAIN_CONFIGS
from build_fact_index import build_fact_index

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_DIR = PROJECT_ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def make_safe_id(text: str) -> str:
    text = text.replace(" ", "_")
    text = re.sub(r"[^a-zA-Z0-9_\-]", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def require_indexing_dependencies():
    try:
        import chromadb
        import fitz
        from PIL import Image
        import pytesseract
        from langchain_chroma import Chroma
        from langchain_community.document_loaders import PyPDFLoader
        from langchain_core.documents import Document
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from app.embeddings import build_embeddings
        from app.config import settings
    except ImportError as exc:
        raise SystemExit(
            "Missing indexing dependency. Install backend dependencies with "
            "`pip install -r apps/api/requirements.txt`."
        ) from exc

    return {
        "chromadb": chromadb,
        "fitz": fitz,
        "Image": Image,
        "pytesseract": pytesseract,
        "Chroma": Chroma,
        "PyPDFLoader": PyPDFLoader,
        "Document": Document,
        "RecursiveCharacterTextSplitter": RecursiveCharacterTextSplitter,
        "build_embeddings": build_embeddings,
        "settings": settings,
    }


def load_pdf_normal(pdf_path: Path, domain: str, metadata: dict, deps: dict):
    loader = deps["PyPDFLoader"](str(pdf_path))
    docs = loader.load()
    cleaned_docs = []

    for doc in docs:
        text = doc.page_content.strip()
        if not text:
            continue

        page = doc.metadata.get("page", 0)
        try:
            page = int(page) + 1
        except Exception:
            page = None

        doc.metadata = {
            "domain": domain,
            "source": str(pdf_path),
            "file_name": pdf_path.name,
            "page": page,
            "extraction_method": "pypdf",
            **metadata,
        }
        cleaned_docs.append(doc)

    return cleaned_docs


def load_pdf_ocr(
    pdf_path: Path,
    domain: str,
    metadata: dict,
    deps: dict,
):
    fitz = deps["fitz"]
    Image = deps["Image"]
    Document = deps["Document"]
    pytesseract = deps["pytesseract"]

    pdf = fitz.open(str(pdf_path))
    docs = []

    try:
        for page_number, page in enumerate(pdf, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
            image = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(image, lang="ind+eng").strip()

            print(f"  OCR page {page_number}: {len(text)} chars")

            if text:
                docs.append(
                    Document(
                        page_content=text,
                        metadata={
                            "domain": domain,
                            "source": str(pdf_path),
                            "file_name": pdf_path.name,
                            "page": page_number,
                            "extraction_method": "ocr_tesseract_ind_eng",
                            **metadata,
                        },
                    )
                )
    finally:
        pdf.close()

    return docs


def load_pdf_smart(
    pdf_path: Path,
    domain: str,
    metadata: dict,
    deps: dict,
    min_chars: int,
):
    print(f"\nLoading: {pdf_path.name}")
    normal_docs = load_pdf_normal(pdf_path, domain, metadata, deps)
    normal_chars = sum(len(doc.page_content) for doc in normal_docs)

    print(f"  Normal extraction chars: {normal_chars}")

    if normal_chars >= min_chars:
        print("  Using normal extraction")
        return normal_docs

    print("  Normal extraction too small. Using OCR")
    return load_pdf_ocr(pdf_path, domain, metadata, deps)


def index_domain(
    *,
    domain_key: str,
    documents_dir: Path,
    chroma_dir: Path,
    reset: bool,
    min_chars: int,
    chunk_size: int,
    chunk_overlap: int,
    deps: dict,
    embeddings,
    embedding_dimension: int,
) -> dict:
    domain_config = DOMAIN_CONFIGS[domain_key]
    domain_dir = documents_dir / domain_config.directory
    pdf_files = sorted(domain_dir.glob("*.pdf"))

    if not domain_dir.exists():
        raise FileNotFoundError(f"Domain document directory not found: {domain_dir}")

    print("=" * 100)
    print(f"DOMAIN: {domain_config.key}")
    print(f"Collection: {domain_config.collection}")
    print(f"Documents: {domain_dir}")
    print(f"PDF files found: {len(pdf_files)}")
    embedding_settings = deps["settings"]
    effective_embedding_model = (
        embedding_settings.ollama_embedding_model
        if embedding_settings.embedding_provider == "ollama"
        else embedding_settings.embedding_model
    )
    print(f"Embedding provider: {embedding_settings.embedding_provider}")
    print(f"Embedding model: {effective_embedding_model}")
    print("Embedding dimension:", embedding_dimension)

    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = deps["chromadb"].PersistentClient(path=str(chroma_dir))

    if reset:
        try:
            client.delete_collection(name=domain_config.collection)
            print(f"Old collection deleted: {domain_config.collection}")
        except Exception:
            print(f"No old collection found: {domain_config.collection}")

    vectorstore = deps["Chroma"](
        collection_name=domain_config.collection,
        embedding_function=embeddings,
        persist_directory=str(chroma_dir),
    )
    text_splitter = deps["RecursiveCharacterTextSplitter"].from_tiktoken_encoder(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    total_docs = 0
    total_chunks = 0
    failed_files = []

    for pdf_path in pdf_files:
        try:
            metadata = domain_config.metadata_by_file[pdf_path.name]
            docs = load_pdf_smart(
                pdf_path,
                domain_config.key,
                metadata,
                deps,
                min_chars,
            )
            print(f"  Total docs/pages loaded: {len(docs)}")

            if not docs:
                failed_files.append((pdf_path.name, "No text extracted"))
                print("  Skipped: no text extracted")
                continue

            splits = [
                split
                for split in text_splitter.split_documents(docs)
                if split.page_content and split.page_content.strip()
            ]

            file_key = make_safe_id(pdf_path.stem)
            for index, split in enumerate(splits):
                split.metadata["chunk_index"] = index
                split.metadata["file_key"] = file_key

            ids = [
                (
                    f"{domain_config.key}-{file_key}-page-"
                    f"{doc.metadata.get('page')}-chunk-{doc.metadata.get('chunk_index')}"
                )
                for doc in splits
            ]

            print(f"  Total chunks: {len(splits)}")

            if not splits:
                failed_files.append((pdf_path.name, "No chunks created"))
                print("  Skipped: no chunks created")
                continue

            vectorstore.add_documents(documents=splits, ids=ids)
            total_docs += len(docs)
            total_chunks += len(splits)
            print(f"  Indexed successfully: {pdf_path.name}")
        except Exception as exc:
            failed_files.append((pdf_path.name, str(exc)))
            print(f"  Failed: {pdf_path.name}")
            print(f"  Error: {exc}")

    collection_count = vectorstore._collection.count()
    print("SUMMARY")
    print("Total docs/pages:", total_docs)
    print("Total chunks indexed:", total_chunks)
    print("Total data in collection:", collection_count)

    return {
        "domain": domain_config.key,
        "collection": domain_config.collection,
        "total_pdfs": len(pdf_files),
        "total_docs": total_docs,
        "total_chunks": total_chunks,
        "collection_count": collection_count,
        "failed_files": failed_files,
    }


def parse_domains(values: Iterable[str] | None) -> List[str]:
    if not values:
        return list(DOMAIN_CONFIGS)

    selected = []
    for value in values:
        if value == "all":
            return list(DOMAIN_CONFIGS)
        selected.append(value)

    return selected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Index SISDAS PDF documents into Chroma.")
    parser.add_argument(
        "--domain",
        action="append",
        choices=[*DOMAIN_CONFIGS.keys(), "all"],
        help="Domain to index. Repeat for multiple domains. Defaults to all.",
    )
    parser.add_argument("--documents-dir", type=Path, default=DEFAULT_DOCUMENTS_DIR)
    parser.add_argument("--chroma-dir", type=Path, default=DEFAULT_CHROMA_DIR)
    parser.add_argument(
        "--embedding-provider",
        choices=["voyage", "ollama"],
        help="Override EMBEDDING_PROVIDER from apps/api/.env.",
    )
    parser.add_argument(
        "--embedding-model",
        help="Override EMBEDDING_MODEL from apps/api/.env.",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        help="Override EMBEDDING_BATCH_SIZE from apps/api/.env.",
    )
    parser.add_argument(
        "--embedding-min-request-interval",
        type=float,
        help="Override EMBEDDING_MIN_REQUEST_INTERVAL_SECONDS from apps/api/.env.",
    )
    parser.add_argument(
        "--embedding-max-retries",
        type=int,
        help="Override EMBEDDING_MAX_RETRIES from apps/api/.env.",
    )
    parser.add_argument("--min-chars", type=int, default=100)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--chunk-overlap", type=int, default=100)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete each target collection before indexing.",
    )
    parser.add_argument(
        "--tesseract-cmd",
        help="Optional full path to tesseract executable.",
    )
    parser.add_argument(
        "--skip-fact-index",
        action="store_true",
        help="Skip rebuilding structured fact index after document indexing.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.embedding_provider:
        os.environ["EMBEDDING_PROVIDER"] = args.embedding_provider
    if args.embedding_model:
        os.environ["EMBEDDING_MODEL"] = args.embedding_model
    if args.embedding_batch_size:
        os.environ["EMBEDDING_BATCH_SIZE"] = str(args.embedding_batch_size)
    if args.embedding_min_request_interval is not None:
        os.environ["EMBEDDING_MIN_REQUEST_INTERVAL_SECONDS"] = str(
            args.embedding_min_request_interval
        )
    if args.embedding_max_retries is not None:
        os.environ["EMBEDDING_MAX_RETRIES"] = str(args.embedding_max_retries)

    deps = require_indexing_dependencies()
    embeddings = deps["build_embeddings"]()
    test_vector = embeddings.embed_query("tes embedding")

    if len(test_vector) == 0:
        raise RuntimeError("Embedding failed. Check the selected embedding provider.")

    tesseract_cmd = args.tesseract_cmd or deps["settings"].tesseract_cmd
    if tesseract_cmd:
        deps["pytesseract"].pytesseract.tesseract_cmd = tesseract_cmd
        print(f"Tesseract command: {tesseract_cmd}")

    summaries = []
    for domain_key in parse_domains(args.domain):
        summaries.append(
            index_domain(
                domain_key=domain_key,
                documents_dir=args.documents_dir,
                chroma_dir=args.chroma_dir,
                reset=args.reset,
                min_chars=args.min_chars,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                deps=deps,
                embeddings=embeddings,
                embedding_dimension=len(test_vector),
            )
        )

    print("=" * 100)
    print("INDEXING COMPLETE")
    for summary in summaries:
        status = "OK" if not summary["failed_files"] else "WITH FAILURES"
        print(
            f"{summary['domain']}: {summary['total_chunks']} chunks, "
            f"collection count {summary['collection_count']} ({status})"
        )

    if not args.skip_fact_index:
        fact_output = deps["settings"].structured_facts_path
        facts = build_fact_index(
            domains=parse_domains(args.domain),
            documents_dir=args.documents_dir,
            output=fact_output,
        )
        print("=" * 100)
        print(f"STRUCTURED FACT INDEX COMPLETE: {len(facts)} facts")
        print(f"Output: {fact_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
