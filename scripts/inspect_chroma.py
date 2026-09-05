from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from domain_registry import DEFAULT_CHROMA_DIR


def scalar_expression(alias: str = "m") -> str:
    return (
        f"coalesce({alias}.string_value, {alias}.int_value, "
        f"{alias}.float_value, {alias}.bool_value)"
    )


def print_rows(title: str, rows: list[tuple]) -> None:
    print(title)
    if not rows:
        print("-")
        return

    for row in rows:
        print(" | ".join(str(value) for value in row))


def inspect_chroma(chroma_dir: Path, details: bool) -> int:
    db_path = chroma_dir / "chroma.sqlite3"

    if not db_path.exists():
        print(f"Chroma sqlite database not found: {db_path}")
        return 1

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    collections = list(cur.execute("select id, name from collections order by name"))
    print_rows("Collections", [(name, collection_id) for collection_id, name in collections])

    count_query = """
        select c.name, count(e.id)
        from collections c
        left join segments s on s.collection = c.id
        left join embeddings e on e.segment_id = s.id
        group by c.name
        order by c.name
    """
    print_rows("Chunk Count by Collection", list(cur.execute(count_query)))

    key_query = """
        select m.key, count(*)
        from embedding_metadata m
        group by m.key
        order by m.key
    """
    print_rows("Metadata Keys", list(cur.execute(key_query)))

    if details:
        value_query = f"""
            select c.name, m.key, {scalar_expression()} as value, count(*)
            from embedding_metadata m
            join embeddings e on m.id = e.id
            join segments s on e.segment_id = s.id
            join collections c on s.collection = c.id
            where m.key in ('file_name', 'document_type', 'academic_year', 'document_year', 'topic')
            group by c.name, m.key, value
            order by c.name, m.key, value
        """
        print_rows("Metadata Values", list(cur.execute(value_query)))

    con.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect SISDAS Chroma metadata.")
    parser.add_argument("--chroma-dir", type=Path, default=DEFAULT_CHROMA_DIR)
    parser.add_argument("--details", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return inspect_chroma(args.chroma_dir, args.details)


if __name__ == "__main__":
    raise SystemExit(main())
