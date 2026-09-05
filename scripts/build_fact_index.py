from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, List

from domain_registry import DEFAULT_DOCUMENTS_DIR, DOMAIN_CONFIGS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_DIR = PROJECT_ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.config import settings
from app.fact_extraction import (
    extract_faculty_unit_facts_from_pages,
    extract_general_facility_facts_from_pages,
    extract_institution_profile_facts_from_pages,
    extract_program_study_facts_from_pages,
    write_facts,
)


def require_dependencies():
    try:
        from langchain_community.document_loaders import PyPDFLoader
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency. Install backend dependencies with "
            "`pip install -r apps/api/requirements.txt`."
        ) from exc

    return {"PyPDFLoader": PyPDFLoader}


def parse_domains(values: Iterable[str] | None) -> List[str]:
    if not values:
        return list(DOMAIN_CONFIGS)

    selected = []
    for value in values:
        if value == "all":
            return list(DOMAIN_CONFIGS)
        selected.append(value)

    return selected


def infer_document_year(file_name: str, metadata: dict) -> str:
    existing = metadata.get("document_year")
    if existing:
        return existing

    years = re.findall(r"(20\d{2}|19\d{2})", file_name)
    if years:
        return max(years)

    academic_year = metadata.get("academic_year", "")
    years = re.findall(r"(20\d{2}|19\d{2})", academic_year)
    return max(years) if years else "general"


def load_pages(pdf_path: Path, domain_key: str, metadata: dict, loader_cls):
    loader = loader_cls(str(pdf_path))
    docs = loader.load()
    pages = []
    enriched_metadata = {
        **metadata,
        "document_year": infer_document_year(pdf_path.name, metadata),
    }

    for doc in docs:
        page = doc.metadata.get("page", 0)
        try:
            page = int(page) + 1
        except Exception:
            page = None

        doc.metadata = {
            "domain": domain_key,
            "source": str(pdf_path),
            "file_name": pdf_path.name,
            "page": page,
            **enriched_metadata,
        }
        pages.append(doc)

    return pages


def build_fact_index(*, domains: Iterable[str], documents_dir: Path, output: Path) -> List[dict]:
    deps = require_dependencies()
    facts = []

    for domain_key in domains:
        domain_config = DOMAIN_CONFIGS[domain_key]
        domain_dir = documents_dir / domain_config.directory
        if not domain_dir.exists():
            continue

        for pdf_path in sorted(domain_dir.glob("*.pdf")):
            metadata = domain_config.metadata_by_file.get(pdf_path.name)
            if metadata is None:
                continue

            pages = load_pages(
                pdf_path=pdf_path,
                domain_key=domain_key,
                metadata=metadata,
                loader_cls=deps["PyPDFLoader"],
            )
            facts.extend(extract_program_study_facts_from_pages(pages))
            facts.extend(extract_faculty_unit_facts_from_pages(pages))
            facts.extend(extract_institution_profile_facts_from_pages(pages))
            facts.extend(extract_general_facility_facts_from_pages(pages))

    write_facts(output, facts)
    return facts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build structured fact index from SISDAS documents.",
    )
    parser.add_argument(
        "--domain",
        action="append",
        choices=[*DOMAIN_CONFIGS.keys(), "all"],
        help="Domain to scan. Repeat for multiple domains. Defaults to all.",
    )
    parser.add_argument("--documents-dir", type=Path, default=DEFAULT_DOCUMENTS_DIR)
    parser.add_argument("--output", type=Path, default=settings.structured_facts_path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    facts = build_fact_index(
        domains=parse_domains(args.domain),
        documents_dir=args.documents_dir,
        output=args.output,
    )
    print(f"Structured facts written: {args.output}")
    print(f"Structured facts: {len(facts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
