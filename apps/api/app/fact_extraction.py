import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


FACULTY_NAMES = [
    "Fakultas Ilmu Pendidikan",
    "Fakultas Sastra",
    "Fakultas Matematika dan Ilmu Pengetahuan Alam",
    "Fakultas Ekonomi dan Bisnis",
    "Fakultas Ekonomi",
    "Fakultas Teknik",
    "Fakultas Ilmu Keolahragaan",
    "Fakultas Ilmu Sosial",
    "Fakultas Psikologi",
    "Fakultas Pendidikan Psikologi",
    "Fakultas Vokasi",
    "Fakultas Kedokteran",
]

PROGRAM_CODE_PATTERN = r"[A-Z$][A-Z0-9]{2,}[A-Za-z0-9]*x{2,}|[Xx]{4}[0-9]{4}|[A-Z]{4,}[0-9][0-9A-Za-zxO]+"
PROGRAM_ROW_PATTERN = re.compile(
    rf"(?:^|\s)(?P<number>\d{{1,2}})\.?\s+"
    rf"(?P<level>S1|S2|S3|D3|D4|DIV|DIII|Profesi|SI1|Sl)?\s*"
    rf"(?P<name>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 /\-&.,()]+?)\s+"
    rf"(?P<code>{PROGRAM_CODE_PATTERN})(?=\s+\d{{1,2}}\.?\s+|\s+[IVX]+\s+FAKULTAS|\s+FAKULTAS|\s+Pasal|\s*$)",
    re.IGNORECASE,
)

CONTINUATION_STOP_PATTERNS = (
    r"\(\d+\)\s+Kode",
    r"Tabel\s+\d+\s+Kode Matakuliah Universiter",
    r"Tabel\s+\d+\s+Kode Matakuliah Dasar",
    r"Tabel\s+\d+\s+Kode Matakuliah yang Diseragamkan",
    r"Tabel\s+\d+\s+Kode Matakuliah Fakultas",
    r"Pasal\s+\d+",
)

FACULTY_LIST_MARKERS = (
    "sepuluh fakultas tersebut adalah",
    "daftar unit tersebut adalah",
    "sepuluh fakultas um adalah",
)

GENERAL_FACILITY_MARKER = "antara lain"


def normalize_space(text: str) -> str:
    text = str(text or "").replace("\xa0", " ")
    text = re.sub(r"\bBab\s+[IVXLC]+\s+[^|\n]{1,80}\|\s*\d+\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+\|Pedoman Pendidikan [^\n]{0,80}", " ", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def normalize_level(level: Optional[str], code: str, default_level: Optional[str]) -> str:
    clean_level = normalize_space(level or "").upper()
    code_upper = (code or "").upper()

    if clean_level in {"SI1", "SL"}:
        return "S1"
    if clean_level == "DIII":
        return "D3"
    if clean_level == "DIV":
        return "D4"
    if clean_level in {"S1", "S2", "S3", "D3", "D4"}:
        return clean_level
    if clean_level == "PROFESI":
        return "Profesi"
    if default_level:
        return default_level
    if "53" in code_upper:
        return "D3"

    return "S1"


def clean_program_name(name: str) -> str:
    name = normalize_space(name)
    name = re.sub(r"^(S1|S2|S3|D3|D4|DIV|DIII|SI1|Sl)\s+", "", name, flags=re.IGNORECASE)
    return name.strip(" .;:")


def detect_default_level(text: str) -> Optional[str]:
    text_lower = text.lower()
    if "program diploma iii" in text_lower or "diploma iii" in text_lower:
        return "D3"
    if "program sarjana" in text_lower:
        return "S1"
    if "program vokasi" in text_lower or "sarjana terapan" in text_lower:
        return "D4"

    return None


def split_continuation_program_section(text: str) -> tuple[str, bool]:
    earliest_stop = None
    for pattern in CONTINUATION_STOP_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match and (earliest_stop is None or match.start() < earliest_stop):
            earliest_stop = match.start()

    if earliest_stop is None:
        return text, False

    return text[:earliest_stop], True


def find_faculty_positions(text: str) -> List[tuple[int, str]]:
    positions = []
    text_lower = text.lower()

    for faculty in FACULTY_NAMES:
        start = 0
        faculty_lower = faculty.lower()
        while True:
            index = text_lower.find(faculty_lower, start)
            if index == -1:
                break
            positions.append((index, faculty))
            start = index + len(faculty_lower)

    return sorted(positions, key=lambda item: item[0])


def find_non_overlapping_faculties(text: str) -> List[str]:
    matches = []
    text_lower = text.lower()
    occupied_spans: List[tuple[int, int]] = []

    for faculty in sorted(FACULTY_NAMES, key=len, reverse=True):
        faculty_lower = faculty.lower()
        start = 0
        while True:
            index = text_lower.find(faculty_lower, start)
            if index == -1:
                break

            end = index + len(faculty_lower)
            overlaps = any(index < used_end and end > used_start for used_start, used_end in occupied_spans)
            if not overlaps:
                occupied_spans.append((index, end))
                matches.append((index, faculty))

            start = end

    return [
        faculty
        for _index, faculty in sorted(matches, key=lambda item: item[0])
    ]


def select_faculty_listing_text(text: str) -> str:
    text_lower = text.lower()
    marker_positions = [
        text_lower.find(marker)
        for marker in FACULTY_LIST_MARKERS
        if text_lower.find(marker) != -1
    ]
    if not marker_positions:
        return text

    start = min(marker_positions)
    section = text[start:]
    stop_match = re.search(
        r"\b(Selain fakultas|UM memiliki Sekolah|JUMLAH PROGRAM STUDI|UM menyelenggarakan)\b",
        section,
        flags=re.IGNORECASE,
    )
    if stop_match:
        return section[:stop_match.start()]

    return section


def is_program_record(name: str, code: str) -> bool:
    name_lower = name.lower()
    code_upper = code.upper()
    if not name or len(name) < 3:
        return False
    if "skripsi" in name_lower:
        return False
    if "kode matakuliah" in name_lower or "nama matakuliah" in name_lower:
        return False
    if not code:
        return False
    if code_upper.startswith(("UNIV", "UPLP", "UPKL", "UKKN", "UKPL")):
        return False

    return True


def extract_program_rows(
    *,
    text: str,
    faculty: str,
    page: int,
    default_level: Optional[str],
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    facts = []

    for match in PROGRAM_ROW_PATTERN.finditer(text):
        program_name = clean_program_name(match.group("name"))
        code = normalize_space(match.group("code"))
        if not is_program_record(program_name, code):
            continue

        facts.append(
            {
                "fact_type": "program_study",
                "university": "Universitas Negeri Malang",
                "faculty": faculty,
                "level": normalize_level(match.group("level"), code, default_level),
                "program_name": program_name,
                "program_code": code,
                "row_number": int(match.group("number")),
                "domain": metadata.get("domain"),
                "file_name": metadata.get("file_name"),
                "source": metadata.get("source"),
                "page": page,
                "document_type": metadata.get("document_type"),
                "academic_year": metadata.get("academic_year"),
                "document_year": metadata.get("document_year") or metadata.get("academic_year"),
                "topic": metadata.get("topic"),
            }
        )

    return facts


def extract_program_study_facts_from_pages(pages: Iterable[Any]) -> List[Dict[str, Any]]:
    facts = []
    current_faculty: Optional[str] = None
    current_level: Optional[str] = None

    for page_doc in pages:
        text = normalize_space(getattr(page_doc, "page_content", ""))
        metadata = getattr(page_doc, "metadata", {}) or {}
        page_number = metadata.get("page")

        if not text:
            continue

        page_level = detect_default_level(text)
        positions = find_faculty_positions(text)
        if not positions:
            if current_faculty:
                continuation_text, should_stop = split_continuation_program_section(text)
                facts.extend(
                    extract_program_rows(
                        text=continuation_text,
                        faculty=current_faculty,
                        page=page_number,
                        default_level=current_level,
                        metadata=metadata,
                    )
                )
                if should_stop:
                    current_faculty = None
                    current_level = page_level or current_level
            elif page_level:
                current_level = page_level
            continue

        if page_level:
            current_level = page_level

        if positions[0][0] > 0 and current_faculty:
            continuation_text, should_stop = split_continuation_program_section(
                text[:positions[0][0]]
            )
            facts.extend(
                extract_program_rows(
                    text=continuation_text,
                    faculty=current_faculty,
                    page=page_number,
                    default_level=current_level,
                    metadata=metadata,
                )
            )
            if should_stop:
                current_faculty = None

        for index, (start, faculty) in enumerate(positions):
            end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
            section = text[start:end]
            current_faculty = faculty
            facts.extend(
                extract_program_rows(
                    text=section,
                    faculty=faculty,
                    page=page_number,
                    default_level=current_level,
                    metadata=metadata,
                )
            )

    return dedupe_facts(facts)


def extract_faculty_unit_facts_from_pages(pages: Iterable[Any]) -> List[Dict[str, Any]]:
    facts = []

    for page_doc in pages:
        text = normalize_space(getattr(page_doc, "page_content", ""))
        text_lower = text.lower()
        metadata = getattr(page_doc, "metadata", {}) or {}
        page_number = metadata.get("page")

        if "universitas negeri malang" not in text_lower and " um " not in f" {text_lower} ":
            continue
        if "fakultas" not in text_lower:
            continue

        listing_text = select_faculty_listing_text(text)
        found_faculties = find_non_overlapping_faculties(listing_text)
        if len(found_faculties) < 5:
            continue

        for faculty in found_faculties:
            facts.append(
                {
                    "fact_type": "faculty_unit",
                    "university": "Universitas Negeri Malang",
                    "faculty": faculty,
                    "additional_unit": (
                        "Sekolah Pascasarjana"
                        if "sekolah pascasarjana" in text_lower
                        else ""
                    ),
                    "domain": metadata.get("domain"),
                    "file_name": metadata.get("file_name"),
                    "source": metadata.get("source"),
                    "page": page_number,
                    "document_type": metadata.get("document_type"),
                    "academic_year": metadata.get("academic_year"),
                    "document_year": metadata.get("document_year") or metadata.get("academic_year"),
                    "topic": metadata.get("topic"),
                }
            )

    return dedupe_facts(facts)


def extract_institution_profile_facts_from_pages(pages: Iterable[Any]) -> List[Dict[str, Any]]:
    facts = []

    for page_doc in pages:
        text = normalize_space(getattr(page_doc, "page_content", ""))
        metadata = getattr(page_doc, "metadata", {}) or {}
        page_number = metadata.get("page")
        text_lower = text.lower()

        if metadata.get("topic") != "institution_profile":
            continue

        rektor_match = re.search(
            r"Rektor(?: Universitas Negeri Malang| UM)? per [^.:\n]+(?:adalah|:)\s*([^.\n]+)",
            text,
            flags=re.IGNORECASE,
        )
        if rektor_match:
            facts.append(
                build_simple_fact(
                    fact_key="rector",
                    value=rektor_match.group(1).strip(),
                    page=page_number,
                    metadata=metadata,
                )
            )

        accreditation_match = re.search(
            r"Akreditasi institusi UM adalah\s+([^.\n]+)",
            text,
            flags=re.IGNORECASE,
        )
        if not accreditation_match:
            accreditation_match = re.search(
                r"peringkat Akreditasi\s+([^.\n]+?)\s+sebagai institusi",
                text,
                flags=re.IGNORECASE,
            )
        if accreditation_match:
            facts.append(
                build_simple_fact(
                    fact_key="institution_accreditation",
                    value=accreditation_match.group(1).strip(),
                    page=page_number,
                    metadata=metadata,
                )
            )

        total_program_match = re.search(
            r"menampilkan total\s+(\d+)\s+program studi",
            text,
            flags=re.IGNORECASE,
        )
        if total_program_match:
            facts.append(
                build_simple_fact(
                    fact_key="total_program_studies",
                    value=f"{total_program_match.group(1)} program studi",
                    page=page_number,
                    metadata=metadata,
                )
            )

        if "kampus utama" in text_lower and "jalan semarang" in text_lower:
            location_sentences = [
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", text)
                if "kampus" in sentence.lower()
                and any(term in sentence.lower() for term in ("jalan", "kota malang", "kota blitar"))
            ]
            if location_sentences:
                facts.append(
                    build_simple_fact(
                        fact_key="campus_locations",
                        value=" ".join(location_sentences[:4]),
                        page=page_number,
                        metadata=metadata,
                    )
                )

    return dedupe_facts(facts)


def split_facility_items(text: str) -> List[str]:
    text = re.sub(r"\s+dan\s+", ", ", text)
    raw_items = [item.strip(" .;:") for item in text.split(",")]
    items = []

    for item in raw_items:
        if not item:
            continue
        if len(item) > 90:
            continue
        items.append(item)

    return items


def extract_general_facility_facts_from_pages(pages: Iterable[Any]) -> List[Dict[str, Any]]:
    facts = []

    for page_doc in pages:
        text = normalize_space(getattr(page_doc, "page_content", ""))
        metadata = getattr(page_doc, "metadata", {}) or {}
        page_number = metadata.get("page")
        text_lower = text.lower()

        if metadata.get("topic") != "general_facilities":
            continue
        if "beberapa sarana" not in text_lower and "fasilitas umum" not in text_lower:
            continue

        marker_index = text_lower.find(GENERAL_FACILITY_MARKER)
        if marker_index == -1:
            continue

        section = text[marker_index + len(GENERAL_FACILITY_MARKER):]
        stop_match = re.search(r"\bAsrama Mahasiswa\b", section)
        if stop_match:
            section = section[:stop_match.start()]

        for facility in split_facility_items(section):
            facts.append(
                {
                    "fact_type": "general_facility",
                    "university": "Universitas Negeri Malang",
                    "facility_name": facility,
                    "domain": metadata.get("domain"),
                    "file_name": metadata.get("file_name"),
                    "source": metadata.get("source"),
                    "page": page_number,
                    "document_type": metadata.get("document_type"),
                    "academic_year": metadata.get("academic_year"),
                    "document_year": metadata.get("document_year") or metadata.get("academic_year"),
                    "topic": metadata.get("topic"),
                }
            )

    return dedupe_facts(facts)


def build_simple_fact(
    *,
    fact_key: str,
    value: str,
    page: int,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "fact_type": "institution_fact",
        "fact_key": fact_key,
        "university": "Universitas Negeri Malang",
        "value": value,
        "domain": metadata.get("domain"),
        "file_name": metadata.get("file_name"),
        "source": metadata.get("source"),
        "page": page,
        "document_type": metadata.get("document_type"),
        "academic_year": metadata.get("academic_year"),
        "document_year": metadata.get("document_year") or metadata.get("academic_year"),
        "topic": metadata.get("topic"),
    }


def fact_key(fact: Dict[str, Any]) -> tuple:
    if fact.get("fact_type") == "faculty_unit":
        return (
            fact.get("fact_type"),
            fact.get("university"),
            fact.get("faculty"),
            fact.get("file_name"),
            fact.get("page"),
        )
    if fact.get("fact_type") == "institution_fact":
        return (
            fact.get("fact_type"),
            fact.get("fact_key"),
            fact.get("value"),
            fact.get("file_name"),
            fact.get("page"),
        )
    if fact.get("fact_type") == "general_facility":
        return (
            fact.get("fact_type"),
            fact.get("facility_name"),
            fact.get("file_name"),
            fact.get("page"),
        )

    return (
        fact.get("fact_type"),
        fact.get("faculty"),
        fact.get("level"),
        fact.get("program_name"),
        fact.get("program_code"),
        fact.get("file_name"),
        fact.get("page"),
    )


def dedupe_facts(facts: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped = []
    seen = set()
    for fact in facts:
        key = fact_key(fact)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(fact)

    return deduped


def write_facts(path: Path, facts: Iterable[Dict[str, Any]]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(list(facts), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
