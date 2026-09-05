import json
import re
from app.llm import groq_generate_json_cached
from app.query_planner import plan_query


VALID_DOMAINS = {
    "academic_administration",
    "thesis_final_project_and_graduation",
    "finance_tuition_and_scholarship",
    "facilities_and_campus_services",
    "general_profile",
}

INSTITUTION_TERMS = {
    "universitas negeri malang",
    "universitas malang",
    "um",
}

INSTITUTION_PROFILE_HINTS = {
    "apa",
    "itu",
    "tentang",
    "profil",
    "sejarah",
    "identitas",
    "status",
    "akreditasi",
    "rektor",
    "berapa",
    "jumlah",
    "fakultas",
    "prodi",
    "jurusan",
    "departemen",
    "unit",
    "lokasi",
    "alamat",
    "dimana",
    "mana",
    "kota",
    "berlokasi",
    "terletak",
    "berada",
}

DEVELOPER_PROFILE_HINTS = {
    "pengembang",
    "developer",
    "pembuat",
    "author",
    "peneliti",
    "dibuat",
    "membuat",
    "kamu",
    "anda",
    "profilmu",
}

FINANCE_TERMS = {
    "ukt",
    "ipi",
    "beasiswa",
    "kip",
    "kip-k",
    "bi",
    "bank indonesia",
    "pembayaran",
    "bayar",
    "registrasi mahasiswa baru",
    "maba",
    "snbt",
    "snbp",
    "mandiri",
    "semester genap",
    "semester gasal",
}

THESIS_GRADUATION_TERMS = {
    "skripsi",
    "tugas akhir",
    "pembimbingan",
    "bimbingan",
    "kartu bimbingan",
    "persetujuan tema",
    "wisuda",
    "yudisium",
    "ijazah",
    "wisudawan",
}

FACILITY_TERMS = {
    "perpustakaan",
    "sarana",
    "fasilitas",
    "laboratorium",
    "lab",
    "studio",
    "tarif penggunaan alat",
    "media rekam",
    "studio musik",
    "studio tari",
    "studio lukis",
}


def tokenize_query(user_query: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", user_query.lower()))


def matches_term(normalized_query: str, tokens: set[str], term: str) -> bool:
    normalized_term = " ".join(term.lower().split())
    if " " in normalized_term or "-" in normalized_term:
        return normalized_term in normalized_query
    return normalized_term in tokens


def should_route_to_general_profile(user_query: str) -> bool:
    normalized_query = " ".join(user_query.lower().split())
    tokens = tokenize_query(normalized_query)

    has_institution = (
        "universitas negeri malang" in normalized_query
        or "universitas malang" in normalized_query
        or "um" in tokens
    )
    has_institution_hint = bool(tokens & INSTITUTION_PROFILE_HINTS)
    has_developer_hint = bool(tokens & DEVELOPER_PROFILE_HINTS)

    return (has_institution and has_institution_hint) or has_developer_hint


def route_by_deterministic_terms(user_query: str) -> dict | None:
    normalized_query = " ".join(user_query.lower().split())
    tokens = tokenize_query(normalized_query)
    domains = []

    if any(matches_term(normalized_query, tokens, term) for term in FINANCE_TERMS):
        domains.append("finance_tuition_and_scholarship")

    if any(matches_term(normalized_query, tokens, term) for term in THESIS_GRADUATION_TERMS):
        domains.append("thesis_final_project_and_graduation")

    if any(matches_term(normalized_query, tokens, term) for term in FACILITY_TERMS):
        domains.append("facilities_and_campus_services")

    if not domains:
        return None

    return {
        "domains": domains,
        "reason": "Deterministic router memilih domain dari istilah domain-spesifik.",
    }


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```json", "", text)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    text = text.strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise json.JSONDecodeError("No JSON object found", text, 0)

    return json.loads(match.group(0))


def route_query_domain(user_query: str) -> dict:
    query_plan = plan_query(user_query)
    if query_plan.get("candidate_domains"):
        return {
            "domains": query_plan["candidate_domains"],
            "reason": "Query planner memilih multi-domain untuk pertanyaan fakta terstruktur.",
            "query_plan": query_plan,
        }

    deterministic_route = route_by_deterministic_terms(user_query)
    if deterministic_route:
        return {
            **deterministic_route,
            "query_plan": query_plan,
        }

    if should_route_to_general_profile(user_query):
        return {
            "domains": ["general_profile"],
            "reason": "Pertanyaan profil umum diarahkan ke domain general_profile.",
            "query_plan": query_plan,
        }

    prompt = f"""
You are a domain router for a university campus RAG system.

Classify the user's question into one or more relevant domains.

Available domains:
1. academic_administration
   Questions about KRS, academic calendar, class schedule, grades, transcript,
   attendance, academic rules, study plan, academic status, and academic administration.

2. thesis_final_project_and_graduation
   Questions about thesis, final project, proposal seminar, thesis defense,
   supervisors, graduation requirements, graduation registration, and graduation ceremony.

3. finance_tuition_and_scholarship
   Questions about UKT, tuition fees, payment, invoices, scholarships,
   financial aid, installments, and student financial obligations.

4. facilities_and_campus_services
   Questions about library, laboratories, classrooms, Wi-Fi, parking,
   dormitory, health services, student ID card, and campus services.

5. general_profile
   Questions about the general profile, identity, location, address, city,
   status, faculty count, academic units, accreditation, leadership, or basic
   description of Universitas Negeri Malang, and questions about the
   developer/creator/profile of this system.

Rules:
- The question may belong to more than one domain.
- Use general_profile for institution profile, university location/address,
  faculty count, academic units, accreditation, leadership, and developer
  profile questions.
- Return only valid domain names.
- Do not explain outside JSON.
- Output must be valid JSON only.

Output schema:
{{
  "domains": ["domain_name"],
  "reason": "short reason"
}}

User question:
{user_query}

Output:
"""

    response = groq_generate_json_cached(prompt, task="router")

    try:
        result = extract_json(response)
    except json.JSONDecodeError:
        return {
            "domains": [],
            "reason": "Failed to parse router output.",
            "raw_response": response,
            "query_plan": query_plan,
        }

    domains = [
        domain for domain in result.get("domains", [])
        if domain in VALID_DOMAINS
    ]

    return {
        "domains": domains,
        "reason": result.get("reason", ""),
        "query_plan": query_plan,
    }
