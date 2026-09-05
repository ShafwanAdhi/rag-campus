from app.domains.common import (
    DomainAnalyzerConfig,
    analyze_query_with_config,
    build_filter_from_config,
)
from app.query_planner import plan_query


DOMAIN = "general_profile"

VALID_DOCUMENT_TYPES = {
    "institution_profile",
    "developer_profile",
}

VALID_ACADEMIC_YEARS = {
    "general",
}

VALID_DOCUMENT_YEARS = {
    "general",
}

VALID_TOPICS = {
    "institution_profile",
    "developer_profile",
}

VALID_QUERY_INTENTS = {
    "general_info",
    "profile_info",
    "location_info",
    "institution_fact",
}

ANALYZER_CONFIG = DomainAnalyzerConfig(
    domain=DOMAIN,
    valid_query_intents=VALID_QUERY_INTENTS,
    valid_metadata_values={
        "document_type": VALID_DOCUMENT_TYPES,
        "academic_year": VALID_ACADEMIC_YEARS,
        "document_year": VALID_DOCUMENT_YEARS,
        "topic": VALID_TOPICS,
    },
    metadata_filter_fields=(
        "document_type",
        "academic_year",
        "document_year",
        "topic",
    ),
    default_metadata_filter_fields=("topic",),
)


QUERY_FACETS = {
    "institution": {
        "triggers": (
            "universitas negeri malang",
            "universitas malang",
            " um ",
        ),
        "keywords": (
            "Universitas Negeri Malang",
            "UM",
            "profil universitas",
            "alamat",
            "lokasi",
            "Kota Malang",
        ),
    },
    "faculty": {
        "triggers": (
            "fakultas",
            "jumlah fakultas",
            "daftar fakultas",
            "unit akademik",
            "sekolah pascasarjana",
        ),
        "keywords": (
            "jumlah fakultas",
            "sepuluh fakultas",
            "satu Sekolah Pascasarjana",
            "sebelas unit akademik utama",
            "daftar unit",
            "Fakultas Ilmu Pendidikan",
            "Fakultas Kedokteran",
        ),
    },
    "academic_structure": {
        "triggers": (
            "program studi",
            "prodi",
            "jurusan",
            "departemen",
            "pendidikan vokasi",
            "sarjana",
            "magister",
            "doktor",
        ),
        "keywords": (
            "program studi",
            "departemen",
            "pendidikan vokasi",
            "sarjana",
            "magister",
            "doktor",
            "struktur akademik",
        ),
    },
    "leadership_status": {
        "triggers": (
            "rektor",
            "akreditasi",
            "status",
            "ptn",
            "ptn bh",
            "badan hukum",
        ),
        "keywords": (
            "rektor",
            "akreditasi",
            "Unggul",
            "Perguruan Tinggi Negeri Badan Hukum",
            "PTN Badan Hukum",
        ),
    },
    "location": {
        "triggers": (
            "dimana",
            "di mana",
            "lokasi",
            "alamat",
            "kota",
            "berlokasi",
            "terletak",
            "berada",
        ),
        "keywords": (
            "lokasi",
            "alamat",
            "kota",
            "Kota Malang",
            "Jalan Semarang",
        ),
    },
    "developer": {
        "triggers": (
            "pengembang",
            "developer",
            "pembuat",
            "author",
            "peneliti",
            "profilmu",
            "tentang kamu",
        ),
        "keywords": (
            "pengembang",
            "developer",
            "profil pengembang",
            "pembuat sistem",
            "peneliti",
        ),
    },
}


def query_has_trigger(query_lower: str, triggers: tuple) -> bool:
    padded_query = f" {query_lower} "
    return any(trigger in padded_query for trigger in triggers)


def enrich_rerank_keywords(user_query: str, keywords: list) -> list:
    query_lower = user_query.lower()
    query_plan = plan_query(user_query)
    entities = query_plan.get("entities", {})
    requested_program = entities.get("program_name")
    faculty = entities.get("faculty")
    seed_keywords = []

    if query_plan.get("intent") == "existence_lookup" and requested_program:
        seed_keywords.extend([
            requested_program,
            faculty,
            "program studi",
        ])
        if requested_program.lower() == "teknik informatika":
            seed_keywords.extend(["Teknik Informatika", "informatika", "komputasi"])
    else:
        for facet in QUERY_FACETS.values():
            if query_has_trigger(query_lower, facet["triggers"]):
                seed_keywords.extend(facet["keywords"])

    if requested_program:
        seed_keywords.append(requested_program)
    if faculty:
        seed_keywords.append(faculty)

    enriched = []
    seen = set()
    for keyword in [*seed_keywords, *keywords]:
        normalized = " ".join(str(keyword).lower().split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            enriched.append(keyword)

    return enriched


def analyze_query(user_query: str) -> dict:
    prompt = f"""
You are a query analyzer for the general_profile domain in a university RAG system.

This domain contains:
- general profile of Universitas Negeri Malang
- identity, status, location, address, and general information about UM
- factual institution information such as faculty count, academic units,
  study programs, accreditation, leadership, and history
- general profile of the system developer

Available metadata fields:
- document_type
- academic_year
- document_year
- topic

Allowed document_type values:
- institution_profile
- developer_profile

Allowed academic_year values:
- general

Allowed document_year values:
- general

Allowed topic values:
- institution_profile
- developer_profile

Query intent values:
- general_info
- profile_info
- location_info
- institution_fact

Rules:
- Use topic "institution_profile" for questions about Universitas Negeri Malang, UM, location, address, campus identity, institutional profile, or general information about the university.
- Use topic "institution_profile" for questions about faculty count, faculty list, academic units, study programs, rector, accreditation, institutional status, or university history.
- Use topic "developer_profile" for questions about the developer, creator, author, researcher, student, or person who built the system.
- Use query_intent "location_info" for location/address/city questions.
- Use query_intent "profile_info" for identity/profile questions.
- Use query_intent "institution_fact" for concrete factual questions about UM, including counts, lists, rector, accreditation, academic structure, or institutional status.
- Use metadata filters only when clearly implied by the question.
- If unsure, leave metadata value as an empty string.
- Specific entity words must go into rerank_keywords.
- Do not invent new metadata values.
- Output must be valid JSON only.
- Do not include markdown.

Output schema:
{{
  "domain": "general_profile",
  "query_intent": "general_info | profile_info | location_info | institution_fact",
  "metadata_filters": {{
    "document_type": "value_or_empty_string",
    "academic_year": "value_or_empty_string",
    "document_year": "value_or_empty_string",
    "topic": "value_or_empty_string"
  }},
  "rerank_keywords": ["keyword_1", "keyword_2"],
  "reason": "short reason"
}}

Examples:

User question:
"Apa itu Universitas Negeri Malang?"

Output:
{{
  "domain": "general_profile",
  "query_intent": "profile_info",
  "metadata_filters": {{
    "document_type": "institution_profile",
    "academic_year": "general",
    "document_year": "general",
    "topic": "institution_profile"
  }},
  "rerank_keywords": ["Universitas Negeri Malang", "profil universitas", "UM"],
  "reason": "The question asks for the university profile."
}}

User question:
"Di kota apa Universitas Malang berlokasi?"

Output:
{{
  "domain": "general_profile",
  "query_intent": "location_info",
  "metadata_filters": {{
    "document_type": "institution_profile",
    "academic_year": "general",
    "document_year": "general",
    "topic": "institution_profile"
  }},
  "rerank_keywords": ["Universitas Negeri Malang", "lokasi", "alamat", "kota"],
  "reason": "The question asks for the university location."
}}

User question:
"Berapa jumlah fakultas di Universitas Negeri Malang?"

Output:
{{
  "domain": "general_profile",
  "query_intent": "institution_fact",
  "metadata_filters": {{
    "document_type": "institution_profile",
    "academic_year": "general",
    "document_year": "general",
    "topic": "institution_profile"
  }},
  "rerank_keywords": ["jumlah fakultas", "sepuluh fakultas", "Sekolah Pascasarjana", "struktur akademik UM"],
  "reason": "The question asks for a concrete institutional fact about UM."
}}

User question:
"Siapa pengembang sistem ini?"

Output:
{{
  "domain": "general_profile",
  "query_intent": "profile_info",
  "metadata_filters": {{
    "document_type": "developer_profile",
    "academic_year": "general",
    "document_year": "general",
    "topic": "developer_profile"
  }},
  "rerank_keywords": ["pengembang", "pembuat sistem", "profil pengembang"],
  "reason": "The question asks about the developer profile."
}}

Now analyze the question.

User question:
{user_query}

Output:
"""

    return analyze_query_with_config(
        user_query=user_query,
        prompt=prompt,
        config=ANALYZER_CONFIG,
        enrich_keywords=enrich_rerank_keywords,
    )


def build_filter(analysis: dict, strict: bool = False) -> dict:
    return build_filter_from_config(
        analysis=analysis,
        config=ANALYZER_CONFIG,
        strict=strict,
    )


def rerank(results, rerank_keywords: list, query: str = ""):
    query_lower = query.lower()
    query_plan = plan_query(query)
    requested_program = query_plan.get("entities", {}).get("program_name")
    requested_faculty = query_plan.get("entities", {}).get("faculty")
    is_developer_query = any(
        term in query_lower
        for term in QUERY_FACETS["developer"]["triggers"]
    )
    is_institution_query = query_has_trigger(query_lower, QUERY_FACETS["institution"]["triggers"])
    is_location_query = query_has_trigger(query_lower, QUERY_FACETS["location"]["triggers"])
    is_faculty_query = query_has_trigger(query_lower, QUERY_FACETS["faculty"]["triggers"])
    is_academic_structure_query = query_has_trigger(
        query_lower,
        QUERY_FACETS["academic_structure"]["triggers"],
    )
    is_leadership_status_query = query_has_trigger(
        query_lower,
        QUERY_FACETS["leadership_status"]["triggers"],
    )

    reranked = []
    for doc, distance in results:
        text = doc.page_content.lower()
        metadata = doc.metadata or {}
        topic = metadata.get("topic", "")

        bonus = 0
        penalty = 0

        for keyword in rerank_keywords:
            keyword_lower = keyword.lower().strip()
            if keyword_lower and keyword_lower in text:
                bonus += 2

        if is_developer_query:
            if topic == "developer_profile":
                bonus += 10
            if "pengembang" in text or "developer" in text or "pembuat" in text:
                bonus += 5

        if is_institution_query:
            if topic == "institution_profile":
                bonus += 10
            if "universitas negeri malang" in text or " um " in f" {text} ":
                bonus += 5

        if is_location_query:
            if topic == "institution_profile":
                bonus += 8
            if "malang" in text or "alamat" in text or "lokasi" in text:
                bonus += 5

        if is_faculty_query:
            if topic == "institution_profile":
                bonus += 10
            if "jumlah fakultas" in text:
                bonus += 8
            if "sepuluh fakultas" in text:
                bonus += 8
            if "sekolah pascasarjana" in text:
                bonus += 4
            if "fakultas" in text:
                bonus += 4

        if is_academic_structure_query:
            if topic == "institution_profile":
                bonus += 8
            if any(term in text for term in ("program studi", "departemen", "struktur akademik")):
                bonus += 5

        if requested_program:
            program_key = requested_program.lower()
            if program_key in text:
                bonus += 18
            if "teknik informatika" in program_key and any(
                term in text for term in ("teknik informatika", "informatika", "komputasi")
            ):
                bonus += 12
            if requested_faculty and requested_faculty.lower() in text:
                bonus += 8

        if is_leadership_status_query:
            if topic == "institution_profile":
                bonus += 8
            if any(term in text for term in ("rektor", "akreditasi", "badan hukum", "unggul")):
                bonus += 5

        if topic == "developer_profile" and not is_developer_query:
            penalty += 4
        if topic == "institution_profile" and is_developer_query:
            penalty += 4

        final_score = bonus - penalty
        reranked.append(
            {
                "doc": doc,
                "distance": distance,
                "keyword_bonus": bonus,
                "penalty": penalty,
                "final_score": final_score,
                "sort_key": (-final_score, distance),
            }
        )

    return sorted(reranked, key=lambda item: item["sort_key"])
