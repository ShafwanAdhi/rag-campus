import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from langchain_core.documents import Document

from app.config import settings

DETAIL_LIST_THRESHOLD = 20


def load_facts(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    facts_path = path or settings.structured_facts_path
    if not facts_path.exists():
        return []

    try:
        payload = json.loads(facts_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, list):
        return []

    return [fact for fact in payload if isinstance(fact, dict)]


def normalize_text(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def numeric_year(value: Any) -> int:
    match = re.search(r"(20\d{2}|19\d{2})", str(value or ""))
    return int(match.group(1)) if match else 0


def program_identity(fact: Dict[str, Any]) -> tuple:
    return (
        normalize_text(fact.get("level")),
        normalize_text(fact.get("program_name")),
        normalize_text(fact.get("program_code")),
    )


def faculty_identity(fact: Dict[str, Any]) -> tuple:
    return (
        normalize_text(fact.get("university")),
        normalize_text(fact.get("faculty")),
    )


def source_group_key(fact: Dict[str, Any]) -> tuple:
    return (
        fact.get("file_name"),
        fact.get("document_year"),
        fact.get("academic_year"),
        fact.get("level"),
    )


def faculty_source_group_key(fact: Dict[str, Any]) -> tuple:
    return (
        fact.get("file_name"),
        fact.get("document_year"),
        fact.get("academic_year"),
        fact.get("page"),
    )


def filter_program_study_facts(
    facts: Iterable[Dict[str, Any]],
    *,
    faculty: Optional[str],
    level: Optional[str],
) -> List[Dict[str, Any]]:
    matched = []
    faculty_key = normalize_text(faculty)
    level_key = normalize_text(level)

    for fact in facts:
        if fact.get("fact_type") != "program_study":
            continue
        if faculty_key and normalize_text(fact.get("faculty")) != faculty_key:
            continue
        if level_key and normalize_text(fact.get("level")) != level_key:
            continue
        matched.append(fact)

    return matched


def filter_program_existence_facts(
    facts: Iterable[Dict[str, Any]],
    *,
    faculty: Optional[str],
    requested_program: Optional[str],
    level: Optional[str],
) -> List[Dict[str, Any]]:
    faculty_matches = filter_program_study_facts(
        facts,
        faculty=faculty,
        level=level,
    )
    program_key = normalize_text(requested_program)
    if not program_key:
        return []

    exact_matches = [
        fact for fact in faculty_matches
        if normalize_text(fact.get("program_name")) == program_key
    ]
    if exact_matches:
        return exact_matches

    return [
        fact for fact in faculty_matches
        if program_key in normalize_text(fact.get("program_name"))
        or normalize_text(fact.get("program_name")) in program_key
    ]


def group_programs_by_source(facts: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple, Dict[str, Any]] = {}
    seen_programs: Dict[tuple, set] = defaultdict(set)

    for fact in facts:
        key = source_group_key(fact)
        if key not in grouped:
            grouped[key] = {
                "file_name": fact.get("file_name"),
                "source": fact.get("source"),
                "domain": fact.get("domain"),
                "topic": fact.get("topic"),
                "document_type": fact.get("document_type"),
                "document_year": fact.get("document_year"),
                "academic_year": fact.get("academic_year"),
                "faculty": fact.get("faculty"),
                "level": fact.get("level"),
                "pages": [],
                "programs": [],
            }

        identity = program_identity(fact)
        if identity in seen_programs[key]:
            continue
        seen_programs[key].add(identity)

        grouped[key]["programs"].append(
            {
                "name": fact.get("program_name"),
                "code": fact.get("program_code"),
                "page": fact.get("page"),
            }
        )
        if fact.get("page") not in grouped[key]["pages"]:
            grouped[key]["pages"].append(fact.get("page"))

    result = list(grouped.values())
    result.sort(
        key=lambda group: (
            numeric_year(group.get("document_year")),
            len(group.get("programs", [])),
        ),
        reverse=True,
    )
    return result


def filter_faculty_unit_facts(
    facts: Iterable[Dict[str, Any]],
    *,
    university: Optional[str],
) -> List[Dict[str, Any]]:
    matched = []
    university_key = normalize_text(university or "Universitas Negeri Malang")

    for fact in facts:
        if fact.get("fact_type") != "faculty_unit":
            continue
        if university_key and normalize_text(fact.get("university")) != university_key:
            continue
        matched.append(fact)

    return matched


def filter_institution_facts(
    facts: Iterable[Dict[str, Any]],
    *,
    fact_keys: Iterable[str],
) -> List[Dict[str, Any]]:
    keys = set(fact_keys)
    matched = []
    for fact in facts:
        if fact.get("fact_type") != "institution_fact":
            continue
        if keys and fact.get("fact_key") not in keys:
            continue
        matched.append(fact)

    matched.sort(
        key=lambda fact: (
            numeric_year(fact.get("document_year")),
            fact.get("page") or 0,
        ),
        reverse=True,
    )
    return matched


def filter_general_facility_facts(facts: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    matched = [
        fact for fact in facts
        if fact.get("fact_type") == "general_facility"
    ]
    matched.sort(key=lambda fact: fact.get("page") or 0)
    return matched


def group_faculties_by_source(facts: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple, Dict[str, Any]] = {}
    seen_faculties: Dict[tuple, set] = defaultdict(set)

    for fact in facts:
        key = faculty_source_group_key(fact)
        if key not in grouped:
            grouped[key] = {
                "file_name": fact.get("file_name"),
                "source": fact.get("source"),
                "domain": fact.get("domain"),
                "topic": fact.get("topic"),
                "document_type": fact.get("document_type"),
                "document_year": fact.get("document_year"),
                "academic_year": fact.get("academic_year"),
                "university": fact.get("university"),
                "pages": [],
                "faculties": [],
                "additional_units": [],
            }

        identity = faculty_identity(fact)
        if identity in seen_faculties[key]:
            continue
        seen_faculties[key].add(identity)

        grouped[key]["faculties"].append(fact.get("faculty"))
        if fact.get("page") not in grouped[key]["pages"]:
            grouped[key]["pages"].append(fact.get("page"))
        additional_unit = fact.get("additional_unit")
        if additional_unit and additional_unit not in grouped[key]["additional_units"]:
            grouped[key]["additional_units"].append(additional_unit)

    result = list(grouped.values())
    result.sort(
        key=lambda group: (
            len(group.get("faculties", [])),
            numeric_year(group.get("document_year")),
        ),
        reverse=True,
    )
    return result


def build_faculty_summary(groups: List[Dict[str, Any]], query_plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not groups:
        return None

    selected = groups[0]
    total = len(selected.get("faculties", []))
    if total <= 0:
        return None

    return {
        "university": query_plan.get("entities", {}).get("university")
        or selected.get("university")
        or "Universitas Negeri Malang",
        "intent": query_plan.get("intent"),
        "total": total,
        "groups": [selected],
        "faculty_names": selected.get("faculties", []),
        "additional_units": selected.get("additional_units", []),
    }


def build_program_summary(groups: List[Dict[str, Any]], query_plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not groups:
        return None

    faculty = query_plan.get("entities", {}).get("faculty") or groups[0].get("faculty")
    requested_level = query_plan.get("entities", {}).get("level")
    latest_year = numeric_year(groups[0].get("document_year"))
    latest_groups = [
        group
        for group in groups
        if numeric_year(group.get("document_year")) == latest_year
        and group.get("file_name") == groups[0].get("file_name")
    ]

    if requested_level:
        selected_groups = [
            group for group in latest_groups
            if normalize_text(group.get("level")) == normalize_text(requested_level)
        ] or latest_groups[:1]
    else:
        selected_groups = latest_groups

    total = sum(len(group.get("programs", [])) for group in selected_groups)
    if total <= 0:
        return None

    program_names = [
        program["name"]
        for group in selected_groups
        for program in group.get("programs", [])
    ]

    return {
        "faculty": faculty,
        "requested_level": requested_level,
        "intent": query_plan.get("intent"),
        "total": total,
        "groups": selected_groups,
        "program_names": program_names,
    }


def build_program_answer(summary: Dict[str, Any]) -> str:
    faculty = summary["faculty"]
    groups = summary["groups"]
    should_list_programs = (
        summary.get("intent") == "list_lookup"
        or summary.get("total", 0) <= DETAIL_LIST_THRESHOLD
    )

    if len(groups) == 1:
        group = groups[0]
        level = group.get("level") or "program"
        answer = (
            f"{faculty} memiliki {summary['total']} program studi {level}."
        )
        if should_list_programs:
            answer += f" Program studinya adalah: {format_program_groups(groups)}."
        return answer

    parts = [
        f"{len(group.get('programs', []))} program studi {group.get('level')}"
        for group in groups
    ]
    answer = (
        f"{faculty} memiliki {', dan '.join(parts)}. Jika semua jenjang tersebut "
        f"dihitung bersama, totalnya {summary['total']} program studi."
    )
    if should_list_programs:
        answer += f" Rinciannya: {format_program_groups(groups)}."
    return answer


def build_program_existence_answer(summary: Dict[str, Any]) -> str:
    faculty = summary["faculty"]
    program_names = summary.get("program_names", [])
    requested_program = summary.get("requested_program")

    if not program_names:
        return f"Informasi tentang {requested_program} di {faculty} tidak ditemukan secara jelas dalam data program studi yang tersedia."

    if len(program_names) == 1:
        return f"Ya, {faculty} memiliki program studi {program_names[0]}."

    return (
        f"Ya, {faculty} memiliki program studi yang sesuai dengan pertanyaan tersebut: "
        f"{', '.join(program_names)}."
    )


def format_program_groups(groups: List[Dict[str, Any]]) -> str:
    sections = []
    for group in groups:
        names = [
            program["name"]
            for program in group.get("programs", [])
            if program.get("name")
        ]
        if not names:
            continue
        level = group.get("level")
        if level:
            sections.append(f"{level}: {', '.join(names)}")
        else:
            sections.append(", ".join(names))

    return "; ".join(sections)


def build_faculty_answer(summary: Dict[str, Any]) -> str:
    university = summary["university"]
    faculty_names = summary["faculty_names"]
    answer = (
        f"{university} memiliki {summary['total']} fakultas."
    )

    if summary["total"] <= DETAIL_LIST_THRESHOLD:
        answer += f" Fakultasnya adalah: {', '.join(faculty_names)}."
    if summary.get("additional_units"):
        answer += f" Selain itu, UM juga memiliki {', '.join(summary['additional_units'])}."

    return answer


def build_institution_fact_answer(facts: List[Dict[str, Any]], query_plan: Dict[str, Any]) -> str:
    fact = facts[0]
    key = fact.get("fact_key")
    value = fact.get("value")

    if key == "rector":
        return f"Rektor Universitas Negeri Malang adalah {value}."
    if key == "institution_accreditation":
        return f"Akreditasi institusi Universitas Negeri Malang adalah {value}."
    if key == "campus_locations":
        return f"Lokasi Universitas Negeri Malang: {value}"
    if key == "total_program_studies":
        return f"Universitas Negeri Malang memiliki total {value}."

    return f"{value}."


def build_general_facility_summary(facts: List[Dict[str, Any]], query_plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not facts:
        return None

    source_file = facts[0].get("file_name")
    selected = [fact for fact in facts if fact.get("file_name") == source_file]
    facility_names = []
    seen = set()
    for fact in selected:
        facility_name = fact.get("facility_name")
        normalized = normalize_text(facility_name)
        if facility_name and normalized not in seen:
            seen.add(normalized)
            facility_names.append(facility_name)

    if not facility_names:
        return None

    return {
        "university": "Universitas Negeri Malang",
        "intent": query_plan.get("intent"),
        "total": len(facility_names),
        "groups": [
            {
                "file_name": source_file,
                "domain": selected[0].get("domain"),
                "topic": selected[0].get("topic"),
                "document_type": selected[0].get("document_type"),
                "document_year": selected[0].get("document_year"),
                "academic_year": selected[0].get("academic_year"),
                "pages": sorted({
                    fact.get("page") for fact in selected
                    if fact.get("page") is not None
                }),
                "facilities": facility_names,
            }
        ],
        "facility_names": facility_names,
    }


def build_general_facility_answer(summary: Dict[str, Any]) -> str:
    answer = (
        f"Universitas Negeri Malang memiliki {summary['total']} sarana/fasilitas umum."
    )
    if summary["total"] <= DETAIL_LIST_THRESHOLD:
        answer += f" Fasilitasnya adalah: {', '.join(summary['facility_names'])}."

    return answer


def build_fact_sources(groups: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources: Dict[str, Dict[str, Any]] = {}

    for group in groups:
        file_name = group.get("file_name") or "unknown_file"
        if file_name not in sources:
            sources[file_name] = {
                "file_name": file_name,
                "url": None,
                "pages": [],
                "chunks": [],
                "domain": group.get("domain"),
                "topic": group.get("topic"),
            }

        for page in group.get("pages", []):
            if page is not None and page not in sources[file_name]["pages"]:
                sources[file_name]["pages"].append(page)

    return [
        {
            **source,
            "pages": sorted(source["pages"]),
        }
        for source in sources.values()
    ]


def build_fact_contexts(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    contexts = []
    for rank, group in enumerate(summary["groups"], start=1):
        if "programs" in group:
            item_lines = [
                f"{index}. {program['name']} ({program['code']})"
                for index, program in enumerate(group.get("programs", []), start=1)
            ]
            header = f"Structured fact: {group.get('faculty')} - {group.get('level')}"
            count_label = "Program count"
            keyword_label = "program studi"
            item_count = len(group.get("programs", []))
        else:
            items = group.get("faculties", group.get("facilities", []))
            label = "faculties" if "faculties" in group else "facilities"
            item_lines = [
                f"{index}. {item}"
                for index, item in enumerate(items, start=1)
            ]
            header = f"Structured fact: {group.get('university', 'Universitas Negeri Malang')} - {label}"
            count_label = "Faculty count" if label == "faculties" else "Facility count"
            keyword_label = "fakultas" if label == "faculties" else "fasilitas"
            item_count = len(items)

        content = "\n".join(
            [
                header,
                f"{count_label}: {item_count}",
                *item_lines,
            ]
        )
        metadata = {
            "domain": group.get("domain"),
            "file_name": group.get("file_name"),
            "page": group.get("pages", [None])[0],
            "chunk_index": "structured_fact",
            "document_type": group.get("document_type"),
            "academic_year": group.get("academic_year"),
            "document_year": group.get("document_year"),
            "topic": group.get("topic"),
        }
        contexts.append(
            {
                "doc": Document(page_content=content, metadata=metadata),
                "distance": 0,
                "keyword_bonus": len(group.get("programs", [])),
                "penalty": 0,
                "final_score": 100 - rank,
                "retrieval_rank": rank,
                "rerank_rank": rank,
                "matched_rerank_keywords": [
                    group.get("faculty") or group.get("university"),
                    keyword_label,
                    group.get("level"),
                ],
                "contains_rerank_keyword": True,
            }
        )

    return contexts


def answer_from_facts(user_query: str, query_plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not query_plan.get("requires_structured_facts"):
        return None

    facts = load_facts()

    if query_plan.get("target") == "institution_profile_fact":
        matched = filter_institution_facts(
            facts,
            fact_keys=query_plan.get("entities", {}).get("fact_keys", []),
        )
        if not matched:
            return None
        group = {
            "file_name": matched[0].get("file_name"),
            "domain": matched[0].get("domain"),
            "topic": matched[0].get("topic"),
            "document_type": matched[0].get("document_type"),
            "document_year": matched[0].get("document_year"),
            "academic_year": matched[0].get("academic_year"),
            "pages": [matched[0].get("page")],
        }
        context = {
            "doc": Document(
                page_content=f"Structured fact: {matched[0].get('fact_key')}: {matched[0].get('value')}",
                metadata={
                    "domain": matched[0].get("domain"),
                    "file_name": matched[0].get("file_name"),
                    "page": matched[0].get("page"),
                    "chunk_index": "structured_fact",
                    "document_type": matched[0].get("document_type"),
                    "academic_year": matched[0].get("academic_year"),
                    "document_year": matched[0].get("document_year"),
                    "topic": matched[0].get("topic"),
                },
            ),
            "distance": 0,
            "keyword_bonus": 1,
            "penalty": 0,
            "final_score": 100,
            "retrieval_rank": 1,
            "rerank_rank": 1,
            "matched_rerank_keywords": [matched[0].get("fact_key")],
            "contains_rerank_keyword": True,
        }
        return {
            "answer": build_institution_fact_answer(matched, query_plan),
            "summary": {"fact": matched[0], "groups": [group]},
            "sources": build_fact_sources([group]),
            "contexts": [context],
            "match_count": len(matched),
            "query": user_query,
        }

    if query_plan.get("target") == "campus_location":
        matched = filter_institution_facts(facts, fact_keys=["campus_locations"])
        if not matched:
            return None
        location_plan = {
            **query_plan,
            "entities": {
                **query_plan.get("entities", {}),
                "fact_keys": ["campus_locations"],
            },
        }
        return answer_from_facts(user_query, {**location_plan, "target": "institution_profile_fact"})

    if query_plan.get("target") == "general_facility":
        matched = filter_general_facility_facts(facts)
        summary = build_general_facility_summary(matched, query_plan)
        if summary is None:
            return None
        return {
            "answer": build_general_facility_answer(summary),
            "summary": summary,
            "sources": build_fact_sources(summary["groups"]),
            "contexts": build_fact_contexts(summary),
            "match_count": len(matched),
            "query": user_query,
        }

    if query_plan.get("target") == "faculty":
        matched = filter_faculty_unit_facts(
            facts,
            university=query_plan.get("entities", {}).get("university"),
        )
        groups = group_faculties_by_source(matched)
        summary = build_faculty_summary(groups, query_plan)
        if summary is None:
            return None

        return {
            "answer": build_faculty_answer(summary),
            "summary": summary,
            "sources": build_fact_sources(summary["groups"]),
            "contexts": build_fact_contexts(summary),
            "match_count": len(matched),
            "query": user_query,
        }

    if query_plan.get("target") != "program_study":
        return None

    if query_plan.get("intent") == "existence_lookup":
        matched = filter_program_existence_facts(
            facts,
            faculty=query_plan.get("entities", {}).get("faculty"),
            requested_program=query_plan.get("entities", {}).get("program_name"),
            level=query_plan.get("entities", {}).get("level"),
        )
        groups = group_programs_by_source(matched)
        summary = build_program_summary(groups, query_plan)
        if summary is None:
            return None
        summary["requested_program"] = query_plan.get("entities", {}).get("program_name")
        return {
            "answer": build_program_existence_answer(summary),
            "summary": summary,
            "sources": build_fact_sources(summary["groups"]),
            "contexts": build_fact_contexts(summary),
            "match_count": len(matched),
            "query": user_query,
        }

    matched = filter_program_study_facts(
        facts,
        faculty=query_plan.get("entities", {}).get("faculty"),
        level=query_plan.get("entities", {}).get("level"),
    )
    groups = group_programs_by_source(matched)
    summary = build_program_summary(groups, query_plan)
    if summary is None:
        return None

    return {
        "answer": build_program_answer(summary),
        "summary": summary,
        "sources": build_fact_sources(summary["groups"]),
        "contexts": build_fact_contexts(summary),
        "match_count": len(matched),
        "query": user_query,
    }
