import math
import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional


STOPWORDS = {
    "apa",
    "agar",
    "atau",
    "bagaimana",
    "cara",
    "dan",
    "dengan",
    "di",
    "dalam",
    "dari",
    "ini",
    "itu",
    "ke",
    "kuliah",
    "mahasiswa",
    "mengajukan",
    "pada",
    "tidak",
    "untuk",
    "yang",
}


def tokenize(text: Any) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+(?:/[0-9]+)?", str(text or "").lower())
        if len(token) > 1 and token not in STOPWORDS
    ]


def term_frequency(tokens: Iterable[str]) -> Counter:
    return Counter(tokens)


def bm25_scores(query: str, documents: List[str]) -> List[float]:
    query_terms = tokenize(query)
    if not query_terms or not documents:
        return [0.0 for _document in documents]

    tokenized_docs = [tokenize(document) for document in documents]
    doc_count = len(tokenized_docs)
    avgdl = sum(len(tokens) for tokens in tokenized_docs) / max(doc_count, 1)
    doc_freq = Counter()

    for tokens in tokenized_docs:
        for token in set(tokens):
            doc_freq[token] += 1

    k1 = 1.5
    b = 0.75
    scores = []

    for tokens in tokenized_docs:
        frequencies = term_frequency(tokens)
        doc_len = len(tokens) or 1
        score = 0.0

        for term in query_terms:
            tf = frequencies.get(term, 0)
            if not tf:
                continue

            idf = math.log(1 + ((doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5)))
            denominator = tf + k1 * (1 - b + b * doc_len / max(avgdl, 1))
            score += idf * ((tf * (k1 + 1)) / denominator)

        scores.append(score)

    return scores


def normalize_scores(scores: List[float]) -> List[float]:
    if not scores:
        return []

    max_score = max(scores)
    if max_score <= 0:
        return [0.0 for _score in scores]

    return [score / max_score for score in scores]


def normalize_keyword(keyword: str) -> str:
    return " ".join(str(keyword or "").lower().split())


def count_keyword_matches(text: str, keywords: Iterable[str]) -> int:
    text_lower = text.lower()
    matches = 0

    for keyword in keywords:
        keyword_text = normalize_keyword(keyword)
        if keyword_text and keyword_text in text_lower:
            matches += 1

    return matches


def metadata_match_score(metadata: Dict[str, Any], metadata_filter: Optional[Dict[str, Any]]) -> float:
    if not metadata_filter:
        return 0.0

    conditions = flatten_metadata_filter(metadata_filter)
    scored_conditions = [
        condition
        for condition in conditions
        if "domain" not in condition and condition
    ]

    if not scored_conditions:
        return 0.0

    matches = 0
    for condition in scored_conditions:
        for key, value in condition.items():
            if value and metadata.get(key) == value:
                matches += 1

    return matches / len(scored_conditions)


def flatten_metadata_filter(metadata_filter: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not metadata_filter:
        return []

    if set(metadata_filter) == {"$and"} and isinstance(metadata_filter["$and"], list):
        return [
            condition
            for condition in metadata_filter["$and"]
            if isinstance(condition, dict) and condition
        ]

    return [metadata_filter]


def semantic_score_from_distance(distance: Optional[float]) -> float:
    try:
        value = float(distance)
    except (TypeError, ValueError):
        return 0.0

    if value < 0:
        return 0.0

    return max(0.0, min(1.0, 1.0 - value))


def get_retrieval_signal(item: Dict[str, Any]) -> Dict[str, Any]:
    doc = item.get("doc")
    metadata = getattr(doc, "metadata", {}) or {}
    signal = metadata.get("_retrieval", {})
    return signal if isinstance(signal, dict) else {}


def formal_rerank(
    *,
    reranked_results: List[Dict[str, Any]],
    query: str,
    rerank_keywords: Iterable[str],
    metadata_filter: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    keywords = list(rerank_keywords)
    documents = [
        getattr(item.get("doc"), "page_content", "")
        for item in reranked_results
    ]
    lexical_scores = normalize_scores(bm25_scores(query, documents))

    formal_results = []
    for index, item in enumerate(reranked_results):
        doc = item.get("doc")
        text = getattr(doc, "page_content", "")
        metadata = getattr(doc, "metadata", {}) or {}
        retrieval_signal = get_retrieval_signal(item)

        heuristic_score = item.get("final_score", 0) or 0
        keyword_match_count = count_keyword_matches(text, keywords)
        keyword_score = min(keyword_match_count / max(len(keywords), 1), 1.0)
        lexical_score = max(
            lexical_scores[index] if index < len(lexical_scores) else 0.0,
            float(retrieval_signal.get("bm25_score_normalized", 0.0) or 0.0),
        )
        semantic_score = semantic_score_from_distance(item.get("distance"))
        metadata_score = metadata_match_score(metadata, metadata_filter)
        penalty = item.get("penalty", 0) or 0

        final_score = (
            heuristic_score
            + (1.5 * semantic_score)
            + (1.2 * lexical_score)
            + (2.0 * keyword_score)
            + (0.8 * metadata_score)
            - (0.2 * penalty)
        )

        formal_item = {
            **item,
            "heuristic_score": heuristic_score,
            "semantic_score": round(semantic_score, 4),
            "lexical_score": round(lexical_score, 4),
            "keyword_score": round(keyword_score, 4),
            "keyword_match_count": keyword_match_count,
            "metadata_score": round(metadata_score, 4),
            "vector_rank": retrieval_signal.get("vector_rank"),
            "lexical_rank": retrieval_signal.get("lexical_rank"),
            "retrieval_channels": retrieval_signal.get("channels", []),
            "final_score": round(final_score, 4),
        }
        formal_item["sort_key"] = (
            -formal_item["final_score"],
            item.get("distance", 999),
        )
        formal_results.append(formal_item)

    return sorted(formal_results, key=lambda result: result["sort_key"])
