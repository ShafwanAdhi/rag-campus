import json
import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional

from app.llm import groq_generate_json_cached


KeywordEnricher = Callable[[str, list], list]

BOILERPLATE_KEYWORDS = {
    "bagaimana",
    "cara",
    "kampus",
    "kuliah",
    "mahasiswa",
    "mengajukan",
    "um",
    "universitas negeri malang",
}


@dataclass(frozen=True)
class DomainAnalyzerConfig:
    domain: str
    valid_query_intents: set
    valid_metadata_values: Dict[str, set]
    metadata_filter_fields: tuple
    default_query_intent: str = "general_info"
    default_metadata_filter_fields: Optional[tuple] = None
    fallback_analyzer: Optional[Callable[[str], dict]] = None


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


def clean_keywords(keywords: Iterable) -> list:
    if not isinstance(keywords, list):
        return []

    cleaned = []
    seen = set()
    for keyword in keywords:
        keyword_text = str(keyword).strip()
        normalized_keyword = " ".join(keyword_text.lower().split())
        if not keyword_text or normalized_keyword in BOILERPLATE_KEYWORDS:
            continue
        if normalized_keyword not in seen:
            seen.add(normalized_keyword)
            cleaned.append(keyword_text)

    return cleaned


def clean_metadata_filters(metadata_filters: dict, config: DomainAnalyzerConfig) -> dict:
    if not isinstance(metadata_filters, dict):
        metadata_filters = {}

    clean_filters = {}
    for field, allowed_values in config.valid_metadata_values.items():
        value = metadata_filters.get(field, "")
        if value in allowed_values:
            clean_filters[field] = value

    return clean_filters


def analyze_query_with_config(
    *,
    user_query: str,
    prompt: str,
    config: DomainAnalyzerConfig,
    enrich_keywords: Optional[KeywordEnricher] = None,
) -> dict:
    try:
        response = groq_generate_json_cached(prompt, task="analyzer")
    except Exception as exc:
        if config.fallback_analyzer is not None:
            result = config.fallback_analyzer(user_query)
            query_intent = result.get(
                "query_intent",
                config.default_query_intent,
            )
            if query_intent not in config.valid_query_intents:
                query_intent = config.default_query_intent
            rerank_keywords = clean_keywords(result.get("rerank_keywords", []))
            if enrich_keywords is not None:
                rerank_keywords = enrich_keywords(user_query, rerank_keywords)

            return {
                "domain": config.domain,
                "query_intent": query_intent,
                "metadata_filters": clean_metadata_filters(
                    result.get("metadata_filters", {}),
                    config,
                ),
                "rerank_keywords": rerank_keywords,
                "reason": result.get("reason", f"Fallback analyzer used: {exc}"),
                "fallback_used": True,
                "fallback_error": str(exc),
            }

        raise

    try:
        result = extract_json(response)
    except json.JSONDecodeError:
        return {
            "domain": config.domain,
            "query_intent": config.default_query_intent,
            "metadata_filters": {},
            "rerank_keywords": [],
            "reason": "Failed to parse analyzer output.",
            "raw_response": response,
        }

    query_intent = result.get("query_intent", config.default_query_intent)
    if query_intent not in config.valid_query_intents:
        query_intent = config.default_query_intent

    rerank_keywords = clean_keywords(result.get("rerank_keywords", []))
    if enrich_keywords is not None:
        rerank_keywords = enrich_keywords(user_query, rerank_keywords)

    return {
        "domain": config.domain,
        "query_intent": query_intent,
        "metadata_filters": clean_metadata_filters(
            result.get("metadata_filters", {}),
            config,
        ),
        "rerank_keywords": rerank_keywords,
        "reason": result.get("reason", ""),
    }


def build_filter_from_config(
    *,
    analysis: dict,
    config: DomainAnalyzerConfig,
    strict: bool = False,
) -> dict:
    filters = [{"domain": config.domain}]
    metadata_filters = analysis.get("metadata_filters", {})
    filter_fields = (
        config.metadata_filter_fields
        if strict or config.default_metadata_filter_fields is None
        else config.default_metadata_filter_fields
    )

    for key in filter_fields:
        value = metadata_filters.get(key)
        if value:
            filters.append({key: value})

    if len(filters) == 1:
        return filters[0]

    return {"$and": filters}
