from __future__ import annotations

import argparse
from pathlib import Path

from domain_registry import DEFAULT_DOCUMENTS_DIR, DOMAIN_CONFIGS


def validate_domain(domain_key: str, documents_dir: Path) -> list[str]:
    errors = []
    domain_config = DOMAIN_CONFIGS[domain_key]
    domain_dir = documents_dir / domain_config.directory

    if not domain_dir.exists():
        return [f"{domain_key}: missing directory {domain_dir}"]

    pdf_names = {path.name for path in domain_dir.glob("*.pdf")}
    metadata_names = set(domain_config.metadata_by_file)

    for file_name in sorted(pdf_names - metadata_names):
        errors.append(f"{domain_key}: missing metadata for {file_name}")

    for file_name in sorted(metadata_names - pdf_names):
        errors.append(f"{domain_key}: metadata exists but PDF is missing: {file_name}")

    for file_name, metadata in sorted(domain_config.metadata_by_file.items()):
        for key in domain_config.required_metadata_keys:
            if not metadata.get(key):
                errors.append(f"{domain_key}: {file_name} missing `{key}`")

    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate SISDAS document metadata maps.")
    parser.add_argument("--documents-dir", type=Path, default=DEFAULT_DOCUMENTS_DIR)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    all_errors = []

    for domain_key in DOMAIN_CONFIGS:
        all_errors.extend(validate_domain(domain_key, args.documents_dir))

    if all_errors:
        print("Metadata validation failed:")
        for error in all_errors:
            print(f"- {error}")
        return 1

    total_files = sum(len(config.metadata_by_file) for config in DOMAIN_CONFIGS.values())
    print(f"Metadata validation OK: {total_files} PDF metadata entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
