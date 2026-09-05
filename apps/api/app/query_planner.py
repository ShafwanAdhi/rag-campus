import re
from typing import Any, Dict, List, Optional


FACULTY_ALIASES = {
    "fakultas teknik": "Fakultas Teknik",
    "ft": "Fakultas Teknik",
    "fakultas matematika dan ilmu pengetahuan alam": "Fakultas Matematika dan Ilmu Pengetahuan Alam",
    "fmipa": "Fakultas Matematika dan Ilmu Pengetahuan Alam",
    "fakultas ilmu pendidikan": "Fakultas Ilmu Pendidikan",
    "fip": "Fakultas Ilmu Pendidikan",
    "fakultas sastra": "Fakultas Sastra",
    "fs": "Fakultas Sastra",
    "fakultas ekonomi": "Fakultas Ekonomi",
    "fakultas ekonomi dan bisnis": "Fakultas Ekonomi dan Bisnis",
    "feb": "Fakultas Ekonomi dan Bisnis",
    "fakultas ilmu keolahragaan": "Fakultas Ilmu Keolahragaan",
    "fik": "Fakultas Ilmu Keolahragaan",
    "fakultas ilmu sosial": "Fakultas Ilmu Sosial",
    "fis": "Fakultas Ilmu Sosial",
    "fakultas psikologi": "Fakultas Psikologi",
    "fakultas pendidikan psikologi": "Fakultas Pendidikan Psikologi",
    "fppsi": "Fakultas Pendidikan Psikologi",
    "fakultas vokasi": "Fakultas Vokasi",
    "fakultas kedokteran": "Fakultas Kedokteran",
}

PROGRAM_STUDY_TERMS = {
    "prodi",
    "program studi",
    "jurusan",
}

PROGRAM_EXISTENCE_TERMS = {
    "apakah ada",
    "ada",
    "tersedia",
    "memiliki",
}

FACULTY_TERMS = {
    "fakultas",
}

RECTOR_TERMS = {
    "rektor",
    "pimpinan",
}

ACCREDITATION_TERMS = {
    "akreditasi",
}

LOCATION_TERMS = {
    "alamat",
    "lokasi",
    "dimana",
    "di mana",
    "berlokasi",
    "terletak",
}

FACILITY_LIST_TERMS = {
    "sarana umum",
    "fasilitas umum",
}

UNIVERSITY_TERMS = {
    "universitas negeri malang",
    "universitas malang",
    "um",
}

COUNT_TERMS = {
    "berapa",
    "jumlah",
    "ada berapa",
    "total",
}

LIST_TERMS = {
    "apa saja",
    "daftar",
    "sebutkan",
}


def normalize_query(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def tokenize_query(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def contains_phrase(text: str, phrases: set[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def contains_term(text: str, tokens: set[str], term: str) -> bool:
    normalized_term = normalize_query(term)
    if " " in normalized_term or "-" in normalized_term:
        return normalized_term in text
    return normalized_term in tokens


def contains_terms(text: str, terms: set[str]) -> bool:
    tokens = tokenize_query(text)
    return any(contains_term(text, tokens, term) for term in terms)


def detect_faculty(query: str) -> Optional[str]:
    padded_query = f" {query} "
    for alias, canonical in sorted(FACULTY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if " " in alias:
            if alias in query:
                return canonical
            continue

        if f" {alias} " in padded_query:
            return canonical

    return None


def detect_level(query: str) -> Optional[str]:
    normalized = query.upper()
    if re.search(r"\bS1\b|\bSARJANA\b", normalized):
        return "S1"
    if re.search(r"\bD3\b|\bDIII\b|\bDIPLOMA III\b", normalized):
        return "D3"
    if re.search(r"\bD4\b|\bDIV\b|\bSARJANA TERAPAN\b", normalized):
        return "D4"
    if re.search(r"\bS2\b|\bMAGISTER\b", normalized):
        return "S2"
    if re.search(r"\bS3\b|\bDOKTOR\b", normalized):
        return "S3"
    if re.search(r"\bPROFESI\b", normalized):
        return "Profesi"

    return None


def clean_program_candidate(value: str) -> str:
    cleaned = normalize_query(value)
    cleaned = re.sub(r"^(apakah|apa|ada|terdapat|tersedia|program studi|prodi|jurusan)\s+", "", cleaned)
    cleaned = re.sub(r"\s+(di|pada)$", "", cleaned)
    cleaned = re.sub(r"\b(universitas negeri malang|universitas malang|um)\b", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?.,")
    return cleaned.title() if cleaned else ""


def detect_requested_program(query: str, faculty: Optional[str]) -> Optional[str]:
    if not faculty:
        return None

    patterns = [
        r"(?:apakah\s+)?ada\s+(.+?)\s+di\s+fakultas",
        r"(?:apakah\s+)?ada\s+(.+?)\s+pada\s+fakultas",
        r"fakultas\s+.+?\s+memiliki\s+(.+?)(?:\?|$)",
        r"program\s+studi\s+(.+?)\s+di\s+fakultas",
        r"prodi\s+(.+?)\s+di\s+fakultas",
    ]

    for pattern in patterns:
        match = re.search(pattern, query)
        if not match:
            continue
        candidate = clean_program_candidate(match.group(1))
        if candidate:
            return candidate

    return None


def build_candidate_domains(plan: Dict[str, Any]) -> List[str]:
    if plan["intent"] in {"aggregate_count", "list_lookup", "existence_lookup"}:
        if plan.get("target") in {"institution_profile_fact", "campus_location"}:
            return ["general_profile"]
        if plan.get("target") == "general_facility":
            return ["facilities_and_campus_services", "general_profile"]
        if plan.get("target") == "faculty":
            return ["general_profile", "academic_administration"]
        if plan.get("target") == "program_study" and plan["intent"] == "existence_lookup":
            return ["academic_administration", "general_profile"]

        domains = ["academic_administration", "general_profile"]
        if plan.get("target") == "program_study":
            domains.append("finance_tuition_and_scholarship")
        return domains

    return []


def plan_query(user_query: str) -> Dict[str, Any]:
    query = normalize_query(user_query)
    asks_program_study = contains_terms(query, PROGRAM_STUDY_TERMS)
    asks_faculty = contains_terms(query, FACULTY_TERMS)
    asks_count = contains_terms(query, COUNT_TERMS)
    asks_list = contains_terms(query, LIST_TERMS)
    asks_university = contains_terms(query, UNIVERSITY_TERMS)
    asks_rector = contains_terms(query, RECTOR_TERMS)
    asks_accreditation = contains_terms(query, ACCREDITATION_TERMS)
    asks_location = contains_terms(query, LOCATION_TERMS)
    asks_general_facility = contains_terms(query, FACILITY_LIST_TERMS)
    asks_program_existence = contains_terms(query, PROGRAM_EXISTENCE_TERMS)
    faculty = detect_faculty(query)
    level = detect_level(query)
    requested_program = detect_requested_program(query, faculty)
    if asks_count or asks_list:
        requested_program = None

    intent = "rag"
    target = ""
    requires_structured_facts = False

    if faculty and requested_program and asks_program_existence and not asks_count and not asks_list:
        intent = "existence_lookup"
        target = "program_study"
        requires_structured_facts = True
    elif asks_program_study and asks_university and asks_count and not faculty:
        intent = "aggregate_count"
        target = "institution_profile_fact"
        requires_structured_facts = True
    elif asks_program_study and faculty and asks_count:
        intent = "aggregate_count"
        target = "program_study"
        requires_structured_facts = True
    elif asks_program_study and faculty and asks_list:
        intent = "list_lookup"
        target = "program_study"
        requires_structured_facts = True
    elif asks_program_study and asks_count:
        intent = "aggregate_count"
        target = "program_study"
        requires_structured_facts = True
    elif asks_faculty and asks_university and asks_count:
        intent = "aggregate_count"
        target = "faculty"
        requires_structured_facts = True
    elif asks_faculty and asks_university and asks_list:
        intent = "list_lookup"
        target = "faculty"
        requires_structured_facts = True
    elif asks_rector and asks_university:
        intent = "list_lookup"
        target = "institution_profile_fact"
        requires_structured_facts = True
    elif asks_accreditation and asks_university:
        intent = "list_lookup"
        target = "institution_profile_fact"
        requires_structured_facts = True
    elif asks_location and asks_university:
        intent = "list_lookup"
        target = "campus_location"
        requires_structured_facts = True
    elif asks_general_facility:
        intent = "list_lookup" if asks_list else "aggregate_count"
        target = "general_facility"
        requires_structured_facts = True

    plan = {
        "intent": intent,
        "target": target,
        "entities": {
            "faculty": faculty,
            "level": level,
            "program_name": requested_program,
            "university": "Universitas Negeri Malang" if asks_university else None,
            "fact_keys": [
                key
                for key, enabled in (
                    ("rector", asks_rector),
                    ("institution_accreditation", asks_accreditation),
                    ("total_program_studies", asks_program_study and asks_university and asks_count and not faculty),
                )
                if enabled
            ],
        },
        "requires_structured_facts": requires_structured_facts,
    }
    plan["candidate_domains"] = build_candidate_domains(plan)
    return plan
