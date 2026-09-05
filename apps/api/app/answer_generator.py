from app.llm import groq_generate_answer

from app.answer_templates import date_schedule
from app.answer_templates import payment_schedule
from app.answer_templates import procedure
from app.answer_templates import rule_policy
from app.answer_templates import form_requirement
from app.answer_templates import scholarship_info
from app.answer_templates import registration_info
from app.answer_templates import facility_info
from app.answer_templates import fee_info
from app.answer_templates import general_info


INTENT_TEMPLATE_MAP = {
    "date_schedule": date_schedule,
    "payment_schedule": payment_schedule,
    "procedure": procedure,
    "rule_policy": rule_policy,
    "form_requirement": form_requirement,
    "scholarship_info": scholarship_info,
    "registration_info": registration_info,
    "facility_info": facility_info,
    "fee_info": fee_info,
    "general_info": general_info,
    "profile_info": general_info,
    "location_info": general_info,
    "institution_fact": general_info,
}



def choose_top_k_for_answer(query_intent: str) -> int:
    if query_intent in {"date_schedule", "payment_schedule"}:
        return 2

    if query_intent == "procedure":
        return 5

    if query_intent == "rule_policy":
        return 3

    if query_intent == "form_requirement":
        return 2

    if query_intent in {
        "facility_info",
        "fee_info",
        "scholarship_info",
        "registration_info",
        "profile_info",
        "location_info",
        "institution_fact",
    }:
        return 3

    return 2


def build_context_from_reranked_results(
    reranked_results,
    top_k: int = 1,
    max_chars_per_doc: int = 2000
) -> str:
    context_blocks = []

    for idx, item in enumerate(reranked_results[:top_k], start=1):
        doc = item["doc"]
        metadata = doc.metadata

        file_name = metadata.get("file_name", "unknown_file")
        page = metadata.get("page", "unknown_page")
        chunk = metadata.get("chunk_index", "unknown_chunk")
        domain = metadata.get("domain", "unknown_domain")
        document_type = metadata.get("document_type", "unknown_document_type")
        academic_year = metadata.get("academic_year", "unknown_academic_year")
        document_year = metadata.get("document_year", "unknown_document_year")
        topic = metadata.get("topic", "unknown_topic")

        content = doc.page_content[:max_chars_per_doc]

        context_block = f"""
[SOURCE {idx}]
File: {file_name}
Page: {page}
Chunk: {chunk}
Domain: {domain}
Document Type: {document_type}
Academic Year: {academic_year}
Document Year: {document_year}
Topic: {topic}

Content:
{content}
"""

        context_blocks.append(context_block)

    institutional_context = """
[CORPUS CONTEXT]
The retrieved documents are part of the Universitas Negeri Malang (UM) document corpus.
When the user's question asks about Universitas Negeri Malang or UM, answer in that scope if the provided source content contains the relevant rule, procedure, date, facility, or requirement.
"""

    return f"{institutional_context}\n\n" + "\n\n".join(context_blocks)


def remove_source_lines(answer: str) -> str:
    lines = answer.strip().splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped.lower().startswith("sumber:"):
            continue

        if stripped.lower().startswith("source:"):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def is_unknown_answer(answer: str) -> bool:
    normalized_answer = " ".join(answer.lower().split())

    return any(
        message in normalized_answer
        for message in (
            "informasi tersebut tidak ditemukan secara jelas dalam dokumen yang tersedia",
            "informasi yang relevan tidak ditemukan dalam dokumen yang tersedia",
        )
    )


def build_extractive_fallback_answer(reranked_results, query_intent: str = "general_info") -> str:
    if not reranked_results:
        return "Informasi yang relevan tidak ditemukan dalam dokumen yang tersedia."

    top_k = min(choose_top_k_for_answer(query_intent), len(reranked_results), 3)
    bullets = []

    for item in reranked_results[:top_k]:
        content = " ".join(item["doc"].page_content.split())
        if len(content) > 700:
            content = content[:700].rsplit(" ", 1)[0].rstrip() + "..."
        if content:
            bullets.append(f"- {content}")

    if not bullets:
        return "Informasi yang relevan tidak ditemukan dalam dokumen yang tersedia."

    return (
        "Layanan model sedang terkena batas penggunaan, jadi jawaban ini disusun "
        "langsung dari konteks dokumen yang paling relevan:\n"
        + "\n".join(bullets)
    )


def generate_answer_from_context(
    user_query: str,
    reranked_results,
    query_intent: str = "general_info"
) -> str:
    if not reranked_results:
        return "Informasi yang relevan tidak ditemukan dalam dokumen yang tersedia."

    top_k = choose_top_k_for_answer(query_intent)

    context = build_context_from_reranked_results(
        reranked_results=reranked_results,
        top_k=top_k,
        max_chars_per_doc=2000
    )

    template_module = INTENT_TEMPLATE_MAP.get(query_intent, general_info)

    prompt = template_module.build_prompt(
        user_query=user_query,
        context=context
    )

    answer = groq_generate_answer(prompt)
    answer = remove_source_lines(answer)

    if not answer:
        answer = "Informasi tersebut tidak ditemukan secara jelas dalam dokumen yang tersedia."

    return answer
