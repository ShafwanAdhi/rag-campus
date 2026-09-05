from app.domains.common import (
    DomainAnalyzerConfig,
    analyze_query_with_config,
    build_filter_from_config,
)


VALID_DOCUMENT_TYPES = {
    "academic_calendar",
    "academic_regulation",
    "academic_guide",
    "general_document"
}

VALID_ACADEMIC_YEARS = {
    "2026/2027",
    "2024/2025",
    "general"
}

VALID_TOPICS = {
    "academic_calendar",
    "administrasi_akademik",
    "kurikulum",
    "pedoman_pendidikan",
    "penilaian_hasil_belajar",
    "general"
}

VALID_QUERY_INTENTS = {
    "date_schedule",
    "rule_policy",
    "procedure",
    "general_info"
}

ANALYZER_CONFIG = DomainAnalyzerConfig(
    domain="academic_administration",
    valid_query_intents=VALID_QUERY_INTENTS,
    valid_metadata_values={
        "document_type": VALID_DOCUMENT_TYPES,
        "academic_year": VALID_ACADEMIC_YEARS,
        "topic": VALID_TOPICS,
    },
    metadata_filter_fields=("document_type", "academic_year", "topic"),
)


LEAVE_QUERY_TERMS = {
    "cuti",
    "cuti kuliah",
    "permohonan cuti",
    "pengajuan cuti",
    "surat keterangan cuti kuliah",
    "skck",
}

LEAVE_PROCEDURE_TERMS = {
    "bagaimana",
    "cara",
    "mengajukan",
    "pengajuan",
    "permohonan",
    "prosedur",
    "tata cara",
}

LEAVE_RERANK_KEYWORDS = [
    "cuti kuliah",
    "permohonan cuti kuliah",
    "pengajuan cuti kuliah",
    "tata cara permohonan cuti kuliah",
    "format permohonan cuti kuliah",
    "Surat Keterangan Cuti Kuliah",
    "SKCK",
    "Subbag Registrasi dan Statistik",
    "BAKPIK",
]

PROGRAM_STUDY_TERMS = {
    "prodi",
    "program studi",
    "jurusan",
    "fakultas",
}

PROGRAM_STUDY_RERANK_KEYWORDS = [
    "program studi",
    "prodi",
    "fakultas",
    "kode matakuliah",
    "kurikulum",
]


def is_leave_query(user_query: str) -> bool:
    query = user_query.lower()
    return any(term in query for term in LEAVE_QUERY_TERMS)


def is_program_study_query(user_query: str) -> bool:
    query = user_query.lower()
    return any(term in query for term in PROGRAM_STUDY_TERMS)


def enrich_program_study_keywords(user_query: str, keywords: list) -> list:
    if not is_program_study_query(user_query):
        return keywords

    query = user_query.lower()
    seed_keywords = list(PROGRAM_STUDY_RERANK_KEYWORDS)

    if "fakultas teknik" in query or " ft " in f" {query} ":
        seed_keywords.extend(["Fakultas Teknik", "FT"])

    enriched = []
    seen = set()
    for keyword in [*seed_keywords, *keywords]:
        normalized = " ".join(str(keyword).lower().split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            enriched.append(keyword)

    return enriched


def enrich_academic_keywords(user_query: str, keywords: list) -> list:
    if not is_leave_query(user_query):
        return enrich_program_study_keywords(user_query, keywords)

    enriched = []
    seen = set()
    for keyword in [*LEAVE_RERANK_KEYWORDS, *keywords]:
        normalized = " ".join(str(keyword).lower().split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            enriched.append(keyword)

    return enriched


def apply_program_study_query_overrides(user_query: str, analysis: dict) -> dict:
    if not is_program_study_query(user_query):
        return analysis

    analysis = dict(analysis)
    analysis["metadata_filters"] = {}
    analysis["rerank_keywords"] = enrich_program_study_keywords(
        user_query,
        analysis.get("rerank_keywords", []),
    )
    analysis["program_study_query"] = True
    analysis["query_intent"] = "general_info"
    return analysis


def apply_leave_query_overrides(user_query: str, analysis: dict) -> dict:
    if not is_leave_query(user_query):
        return analysis

    query = user_query.lower()
    analysis = dict(analysis)
    analysis["metadata_filters"] = {}
    analysis["rerank_keywords"] = enrich_academic_keywords(
        user_query,
        analysis.get("rerank_keywords", []),
    )
    analysis["leave_query"] = True

    if any(term in query for term in LEAVE_PROCEDURE_TERMS):
        analysis["query_intent"] = "procedure"
    else:
        analysis["query_intent"] = "rule_policy"

    return analysis



def analyze_query(user_query: str) -> dict:
    prompt = f"""
You are a query analyzer for the academic_administration domain in a university RAG system.

Your task:
1. Detect safe metadata filters.
2. Detect rerank keywords.
3. Detect query intent.

Available metadata fields:
- document_type
- academic_year
- topic

Allowed document_type values:
- academic_calendar
- academic_regulation
- academic_guide
- general_document

Allowed academic_year values:
- 2026/2027
- 2024/2025
- general

Allowed topic values:
- academic_calendar
- administrasi_akademik
- kurikulum
- pedoman_pendidikan
- penilaian_hasil_belajar
- general

Rules:
- For schedule/date questions, use document_type "academic_calendar".
- For rules/policy questions, use document_type "academic_regulation" or "academic_guide".
- If the query mentions 2026/2027 or 2026-2027, use academic_year "2026/2027".
- If the query mentions 2024/2025 or 2024-2025, use academic_year "2024/2025".
- If the query is about general rules, use academic_year "general".
- For specific schedule activities such as KRS, UKT, KHS, yudisium, masa perkuliahan, or ujian, use topic "academic_calendar".
- Specific activity words must go into rerank_keywords, not topic.
- Do not invent new metadata values.
- Output must be valid JSON only.

Output schema:
{{
  "domain": "academic_administration",
  "query_intent": "date_schedule | rule_policy | procedure | general_info",
  "metadata_filters": {{
    "document_type": "value_or_empty_string",
    "academic_year": "value_or_empty_string",
    "topic": "value_or_empty_string"
  }},
  "rerank_keywords": ["keyword_1", "keyword_2"],
  "reason": "short reason"
}}

Examples:

User question:
"Kapan registrasi akademik KRS Online semester gasal 2026/2027?"

Output:
{{
  "domain": "academic_administration",
  "query_intent": "date_schedule",
  "metadata_filters": {{
    "document_type": "academic_calendar",
    "academic_year": "2026/2027",
    "topic": "academic_calendar"
  }},
  "rerank_keywords": ["registrasi akademik", "KRS Online", "semester gasal", "2026/2027"],
  "reason": "The question asks for an academic calendar schedule."
}}

User question:
"Apa aturan penilaian hasil belajar mahasiswa?"

Output:
{{
  "domain": "academic_administration",
  "query_intent": "rule_policy",
  "metadata_filters": {{
    "document_type": "academic_regulation",
    "academic_year": "general",
    "topic": "penilaian_hasil_belajar"
  }},
  "rerank_keywords": ["penilaian", "hasil belajar", "nilai mahasiswa"],
  "reason": "The question asks about assessment rules."
}}

User question:
"Bagaimana aturan cuti kuliah mahasiswa?"

Output:
{{
  "domain": "academic_administration",
  "query_intent": "rule_policy",
  "metadata_filters": {{
    "document_type": "academic_regulation",
    "academic_year": "general",
    "topic": "administrasi_akademik"
  }},
  "rerank_keywords": ["cuti kuliah", "permohonan cuti", "SKCK"],
  "reason": "The question asks about academic leave rules."
}}

Now analyze the question.

User question:
{user_query}

Output:
"""

    analysis = analyze_query_with_config(
        user_query=user_query,
        prompt=prompt,
        config=ANALYZER_CONFIG,
        enrich_keywords=enrich_academic_keywords,
    )
    analysis = apply_leave_query_overrides(user_query, analysis)
    return apply_program_study_query_overrides(user_query, analysis)


def build_filter(analysis: dict) -> dict:
    if analysis.get("leave_query") or analysis.get("program_study_query"):
        return {"domain": ANALYZER_CONFIG.domain}

    return build_filter_from_config(
        analysis=analysis,
        config=ANALYZER_CONFIG,
    )


def rerank(results, rerank_keywords: list, query: str = ""):
    query_lower = query.lower()

    strong_phrases = [
        "registrasi akademik (krs online)",
        "registrasi akademik krs online",
        "krs online",
        "pembayaran ukt",
        "registrasi administrasi/pembayaran ukt",
        "masa perkuliahan",
        "kartu hasil studi",
        "khs online",
        "batas akhir yudisium",
        "yudisium di fakultas",
    ]

    negative_phrases = [
        "krs oleh operator fakultas",
        "cakra widya",
        "semester antara",
        "kartu rencana ekstrakurikuler",
        "kre online",
    ]

    reranked = []

    for doc, distance in results:
        text = doc.page_content.lower()
        bonus = 0
        penalty = 0

        for keyword in rerank_keywords:
            keyword_lower = keyword.lower().strip()
            if keyword_lower and keyword_lower in text:
                bonus += 1

        for phrase in strong_phrases:
            if phrase in query_lower and phrase in text:
                bonus += 5

        if "krs online" in query_lower:
            if "registrasi akademik (krs online)" in text:
                bonus += 10
            if "registrasi akademik" in text and "krs online" in text:
                bonus += 5

        if is_leave_query(query):
            if "tata cara permohonan cuti kuliah" in text:
                bonus += 12
            if "format permohonan cuti kuliah" in text:
                bonus += 8
            if "subbag registrasi dan statistik" in text:
                bonus += 6
            if "surat keterangan cuti kuliah" in text or "skck" in text:
                bonus += 5
            if "permohonan cuti kuliah" in text:
                bonus += 4
            if "wisuda" in text and "cuti kuliah" not in text:
                penalty += 4

        if is_program_study_query(query):
            if "program studi" in text or "prodi" in text:
                bonus += 4
            if "fakultas" in text:
                bonus += 2
            if "kode matakuliah" in text or "kurikulum" in text:
                bonus += 2
            if "fakultas teknik" in query_lower:
                if "fakultas teknik" in text:
                    bonus += 10
                if "teknik mesin" in text or "teknik sipil" in text or "teknik informatika" in text:
                    bonus += 4

        for phrase in negative_phrases:
            if phrase in text:
                penalty += 2

        reranked.append({
            "doc": doc,
            "distance": distance,
            "keyword_bonus": bonus,
            "penalty": penalty,
            "final_score": bonus - penalty,
            "sort_key": (-(bonus - penalty), distance)
        })

    return sorted(reranked, key=lambda item: item["sort_key"])
