from typing import Any, Dict, Generator, List, Optional, Tuple
import hashlib
import json
import logging
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.fact_index import answer_from_facts
from app.llm import structured_cache_stats
from app.router import route_query_domain
from app.retrieval import (
    expand_with_neighbor_chunks,
    get_vectorstore,
    retrieve_with_fallback,
)
from app.reranking import formal_rerank
from app.answer_generator import (
    build_extractive_fallback_answer,
    choose_top_k_for_answer,
    generate_answer_from_context,
    is_unknown_answer,
)

from app.domains import academic_administration
from app.domains import thesis_final_project_and_graduation
from app.domains import finance_tuition_and_scholarship
from app.domains import facilities_and_campus_services
from app.domains import general_profile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="RAG Campus Assistant API",
    description="API RAG dengan response biasa dan response streaming status proses.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    if settings.app_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response

DOMAIN_MODULES = {
    "academic_administration": academic_administration,
    "finance_tuition_and_scholarship": finance_tuition_and_scholarship,
    "thesis_final_project_and_graduation": thesis_final_project_and_graduation,
    "facilities_and_campus_services": facilities_and_campus_services,
    "general_profile": general_profile,
}

COLLECTION_BY_DOMAIN = {
    "academic_administration": "academic_administration",
    "thesis_final_project_and_graduation": "thesis_final_project_and_graduation",
    "finance_tuition_and_scholarship": "finance_tuition_and_scholarship",
    "facilities_and_campus_services": "facilities_and_campus_services",
    "general_profile": "general_profile",
}

DOCUMENT_DIRECTORY_BY_DOMAIN = {
    "academic_administration": "domain1_academic_administration",
    "facilities_and_campus_services": "domain2_facilities_and_campus_services",
    "finance_tuition_and_scholarship": "domain3_finance_tuition_and_scholarship",
    "thesis_final_project_and_graduation": "domain4_thesis_final_project_and_graduation",
    "general_profile": ".",
}

DOCUMENTS_ROOT = settings.backend_dir.parent.parent / "data" / "documents"

ANSWER_STATUS_ANSWERED = "answered"
ANSWER_STATUS_NOT_FOUND = "not_found"
ANSWER_STATUS_DOMAIN_ERROR = "domain_error"
ANSWER_STATUS_NO_DOMAIN = "no_domain"

MIN_CONFIDENT_FINAL_SCORE = 1
MIN_CONFIDENT_KEYWORD_MATCHES = 1


class ChatRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Pertanyaan dari user",
    )


class ContextResponse(BaseModel):
    id: Optional[str] = None
    page_content: str
    metadata: Dict[str, Any]
    distance: Optional[float] = None
    keyword_bonus: Optional[float] = None
    penalty: Optional[float] = None
    final_score: Optional[float] = None
    heuristic_score: Optional[float] = None
    semantic_score: Optional[float] = None
    lexical_score: Optional[float] = None
    keyword_score: Optional[float] = None
    keyword_match_count: Optional[int] = None
    metadata_score: Optional[float] = None
    vector_rank: Optional[int] = None
    lexical_rank: Optional[int] = None
    retrieval_channels: List[str] = Field(default_factory=list)
    retrieval_rank: Optional[int] = None
    rerank_rank: Optional[int] = None
    rank_delta: Optional[int] = None
    matched_rerank_keywords: List[str] = Field(default_factory=list)
    contains_rerank_keyword: bool = False


class SourceResponse(BaseModel):
    file_name: str
    url: Optional[str] = None
    pages: List[Any] = Field(default_factory=list)
    chunks: List[Any] = Field(default_factory=list)
    domain: Optional[str] = None
    topic: Optional[str] = None


class ChatResponse(BaseModel):
    request_id: str = ""
    user_query: str
    answer: str
    answer_status: str = ANSWER_STATUS_ANSWERED
    route: Dict[str, Any]
    analyses: Dict[str, Any] = Field(default_factory=dict)
    domain_errors: Dict[str, str] = Field(default_factory=dict)
    sources: List[SourceResponse] = Field(default_factory=list)
    contexts: List[ContextResponse] = Field(default_factory=list)
    reranking_keyword: Dict[str, Any] = Field(default_factory=dict)
    query_intent_adaptive_top_k: Dict[str, Any] = Field(default_factory=dict)
    timings: Dict[str, Any] = Field(default_factory=dict)
    retrieval_confidence: Dict[str, Any] = Field(default_factory=dict)


def elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def make_request_id() -> str:
    return uuid.uuid4().hex[:12]


def hash_query(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        **fields,
    }
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


def compress_values(values: List[Any]) -> List[Any]:
    clean_values = []
    seen = set()

    for value in values:
        key = str(value)
        if key not in seen:
            seen.add(key)
            clean_values.append(value)

    return clean_values


def build_structured_sources(reranked_results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    sources: Dict[str, Dict[str, Any]] = {}

    for item in reranked_results[:top_k]:
        doc = item.get("doc")
        metadata = getattr(doc, "metadata", {}) or {}
        file_name = metadata.get("file_name") or metadata.get("source") or "unknown_file"

        if file_name not in sources:
            sources[file_name] = {
                "file_name": file_name,
                "url": build_document_url(metadata.get("domain"), file_name),
                "pages": [],
                "chunks": [],
                "domain": metadata.get("domain"),
                "topic": metadata.get("topic"),
            }

        sources[file_name]["pages"].append(metadata.get("page"))
        sources[file_name]["chunks"].append(metadata.get("chunk_index"))

    return [
        {
            **source,
            "pages": compress_values([
                value for value in source["pages"] if value is not None
            ]),
            "chunks": compress_values([
                value for value in source["chunks"] if value is not None
            ]),
        }
        for source in sources.values()
    ]


def build_fact_sources_with_urls(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            **source,
            "url": source.get("url") or build_document_url(
                source.get("domain"),
                source.get("file_name"),
            ),
        }
        for source in sources
    ]


def build_document_url(domain_key: Optional[str], file_name: Optional[str]) -> Optional[str]:
    if not domain_key or not file_name:
        return None

    if domain_key not in DOCUMENT_DIRECTORY_BY_DOMAIN:
        return None

    return f"/documents/{domain_key}/{quote(file_name, safe='')}"


def resolve_document_path(domain_key: str, file_name: str) -> Path:
    directory = DOCUMENT_DIRECTORY_BY_DOMAIN.get(domain_key)
    if not directory:
        raise HTTPException(status_code=404, detail="Domain dokumen tidak ditemukan")

    root = DOCUMENTS_ROOT.resolve()
    path = (root / directory / file_name).resolve()
    if root not in path.parents:
        raise HTTPException(status_code=400, detail="Nama dokumen tidak valid")

    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Dokumen PDF tidak ditemukan")

    return path


def serialize_context(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mengubah hasil retrieval/rerank yang berisi object Document
    menjadi dict biasa agar aman dikirim sebagai JSON.
    """
    doc = item.get("doc")
    metadata = {
        key: value
        for key, value in (getattr(doc, "metadata", {}) or {}).items()
        if not str(key).startswith("_")
    }

    return {
        "id": getattr(doc, "id", None),
        "page_content": getattr(doc, "page_content", ""),
        "metadata": metadata,
        "distance": item.get("distance"),
        "keyword_bonus": item.get("keyword_bonus"),
        "penalty": item.get("penalty"),
        "final_score": item.get("final_score"),
        "heuristic_score": item.get("heuristic_score"),
        "semantic_score": item.get("semantic_score"),
        "lexical_score": item.get("lexical_score"),
        "keyword_score": item.get("keyword_score"),
        "keyword_match_count": item.get("keyword_match_count"),
        "metadata_score": item.get("metadata_score"),
        "vector_rank": item.get("vector_rank"),
        "lexical_rank": item.get("lexical_rank"),
        "retrieval_channels": item.get("retrieval_channels", []),
        "retrieval_rank": item.get("retrieval_rank"),
        "rerank_rank": item.get("rerank_rank"),
        "rank_delta": item.get("rank_delta"),
        "matched_rerank_keywords": item.get("matched_rerank_keywords", []),
        "contains_rerank_keyword": item.get("contains_rerank_keyword", False),
    }


def make_sse_event(event: str, data: Dict[str, Any]) -> str:
    """
    Format event untuk Server-Sent Events.
    Frontend bisa membaca event: status, done, atau error.
    """
    json_data = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {json_data}\n\n"


def get_matched_keywords(text: str, rerank_keywords: List[str]) -> List[str]:
    """
    Menandai keyword hasil analyzer yang benar-benar muncul pada chunk.
    Ini dipakai untuk kebutuhan whitebox reranking keyword.
    """
    text_lower = text.lower()
    matched_keywords = []

    for keyword in rerank_keywords:
        keyword_text = str(keyword).strip()
        if keyword_text and keyword_text.lower() in text_lower:
            matched_keywords.append(keyword_text)

    return matched_keywords


def summarize_context_for_whitebox(item: Dict[str, Any]) -> Dict[str, Any]:
    doc = item.get("doc")
    metadata = getattr(doc, "metadata", {}) or {}

    return {
        "file_name": metadata.get("file_name"),
        "page": metadata.get("page"),
        "chunk_index": metadata.get("chunk_index"),
        "domain": metadata.get("domain"),
        "topic": metadata.get("topic"),
        "retrieval_rank": item.get("retrieval_rank"),
        "rerank_rank": item.get("rerank_rank"),
        "rank_delta": item.get("rank_delta"),
        "keyword_bonus": item.get("keyword_bonus"),
        "penalty": item.get("penalty"),
        "final_score": item.get("final_score"),
        "matched_rerank_keywords": item.get("matched_rerank_keywords", []),
    }


def annotate_rerank_results(
    *,
    retrieved_results: List[Any],
    reranked_results: List[Dict[str, Any]],
    rerank_keywords: List[str],
) -> List[Dict[str, Any]]:
    """
    Menambahkan rank sebelum dan sesudah reranking supaya frontend bisa
    mengecek apakah chunk yang memuat keyword penting naik peringkat.
    """
    retrieval_rank_by_doc = {
        id(doc): rank
        for rank, (doc, _distance) in enumerate(retrieved_results, start=1)
    }

    for rerank_rank, item in enumerate(reranked_results, start=1):
        doc = item.get("doc")
        retrieval_rank = retrieval_rank_by_doc.get(id(doc))
        matched_keywords = get_matched_keywords(
            getattr(doc, "page_content", ""),
            rerank_keywords,
        )

        item["retrieval_rank"] = retrieval_rank
        item["rerank_rank"] = rerank_rank
        item["rank_delta"] = (
            retrieval_rank - rerank_rank
            if retrieval_rank is not None
            else None
        )
        item["matched_rerank_keywords"] = matched_keywords
        item["contains_rerank_keyword"] = bool(matched_keywords)

    return reranked_results


def refresh_rerank_positions(reranked_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for rerank_rank, item in enumerate(reranked_results, start=1):
        retrieval_rank = item.get("retrieval_rank")
        item["rerank_rank"] = rerank_rank
        item["rank_delta"] = (
            retrieval_rank - rerank_rank
            if retrieval_rank is not None
            else None
        )

    return reranked_results


def build_keyword_reranking_report(
    *,
    domain: str,
    analysis: Dict[str, Any],
    retrieved_count: int,
    reranked_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    keyword_contexts = [
        item
        for item in reranked_results
        if item.get("contains_rerank_keyword")
    ]
    promoted_contexts = [
        item
        for item in keyword_contexts
        if (item.get("rank_delta") or 0) > 0
    ]

    return {
        "domain": domain,
        "rerank_keywords": analysis.get("rerank_keywords", []),
        "retrieved_count": retrieved_count,
        "reranked_count": len(reranked_results),
        "chunks_with_keyword_count": len(keyword_contexts),
        "promoted_keyword_chunk_count": len(promoted_contexts),
        "chunks_with_keyword_promoted": bool(promoted_contexts),
        "top_keyword_chunks": [
            summarize_context_for_whitebox(item)
            for item in keyword_contexts[:5]
        ],
    }


def build_query_intent_top_k_report(
    *,
    best_domain: Optional[str],
    analyses: Dict[str, Any],
    available_context_count: int,
) -> Dict[str, Any]:
    query_intent = analyses.get(best_domain or "", {}).get("analysis", {}).get(
        "query_intent",
        "general_info",
    )
    adaptive_top_k = choose_top_k_for_answer(query_intent)

    return {
        "best_domain": best_domain,
        "query_intent": query_intent,
        "adaptive_top_k": adaptive_top_k,
        "context_count_used": min(adaptive_top_k, available_context_count),
        "available_context_count": available_context_count,
        "selection_rule": "choose_top_k_for_answer(query_intent)",
    }


def calculate_domain_progress(
    *,
    index: int,
    total_domains: int,
    stage_fraction: float,
) -> int:
    """
    Membagi rentang 15-75 secara merata untuk seluruh domain.
    """
    safe_total = max(total_domains, 1)
    safe_fraction = max(0.0, min(1.0, stage_fraction))
    slot_start = 15 + ((index - 1) * 60 / safe_total)
    slot_size = 60 / safe_total
    return round(slot_start + (slot_size * safe_fraction))


def build_no_context_answer(
    *,
    domain_errors: Dict[str, str],
    domain_count: int,
) -> str:
    if domain_errors and len(domain_errors) >= domain_count:
        return "Seluruh domain yang dipilih gagal diproses. Silakan coba kembali."

    return "Informasi yang relevan tidak ditemukan dalam dokumen yang tersedia."


def build_no_context_status(
    *,
    domain_errors: Dict[str, str],
    domain_count: int,
) -> str:
    if domain_errors and len(domain_errors) >= domain_count:
        return ANSWER_STATUS_DOMAIN_ERROR

    return ANSWER_STATUS_NOT_FOUND


def build_retrieval_confidence(all_contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not all_contexts:
        return {
            "sufficient": False,
            "reason": "no_context",
            "thresholds": {
                "min_final_score": MIN_CONFIDENT_FINAL_SCORE,
                "min_keyword_matches": MIN_CONFIDENT_KEYWORD_MATCHES,
            },
        }

    top_context = all_contexts[0]
    matched_keywords = top_context.get("matched_rerank_keywords", []) or []
    top_final_score = top_context.get("final_score") or 0
    top_keyword_bonus = top_context.get("keyword_bonus") or 0
    top_distance = top_context.get("distance")

    sufficient = (
        top_final_score >= MIN_CONFIDENT_FINAL_SCORE
        or top_keyword_bonus >= MIN_CONFIDENT_KEYWORD_MATCHES
        or len(matched_keywords) >= MIN_CONFIDENT_KEYWORD_MATCHES
    )

    return {
        "sufficient": sufficient,
        "reason": "confident_context" if sufficient else "low_relevance_context",
        "top_final_score": top_final_score,
        "top_keyword_bonus": top_keyword_bonus,
        "top_keyword_match_count": len(matched_keywords),
        "top_distance": top_distance,
        "top_source": summarize_context_for_whitebox(top_context),
        "thresholds": {
            "min_final_score": MIN_CONFIDENT_FINAL_SCORE,
            "min_keyword_matches": MIN_CONFIDENT_KEYWORD_MATCHES,
        },
    }


def build_reranking_summary(reranking_keyword: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "chunks_with_keyword_promoted": any(
            report.get("chunks_with_keyword_promoted")
            for report in reranking_keyword.get("domains", {}).values()
        ),
        "promoted_keyword_chunk_count": sum(
            report.get("promoted_keyword_chunk_count", 0)
            for report in reranking_keyword.get("domains", {}).values()
        ),
        "chunks_with_keyword_count": sum(
            report.get("chunks_with_keyword_count", 0)
            for report in reranking_keyword.get("domains", {}).values()
        ),
    }


def get_retrieved_count(analysis_report: Dict[str, Any]) -> int:
    attempts = analysis_report.get("retrieval", {}).get("attempts") or []
    if not attempts:
        return 0

    return attempts[-1].get("result_count", 0)


def sort_contexts(all_contexts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        all_contexts,
        key=lambda item: (-(item.get("final_score", 0)), item.get("distance", 999)),
    )


def build_response_payload(
    *,
    request_id: str,
    user_query: str,
    answer: str,
    answer_status: str,
    route: Dict[str, Any],
    analyses: Dict[str, Any],
    domain_errors: Dict[str, str],
    sources: Optional[List[Dict[str, Any]]] = None,
    contexts: List[Dict[str, Any]],
    reranking_keyword: Dict[str, Any],
    query_intent_adaptive_top_k: Dict[str, Any],
    timings: Dict[str, Any],
    retrieval_confidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "request_id": request_id,
        "user_query": user_query,
        "answer": answer,
        "answer_status": answer_status,
        "route": route,
        "analyses": analyses,
        "domain_errors": domain_errors,
        "sources": sources if answer_status == ANSWER_STATUS_ANSWERED else [],
        "contexts": contexts if answer_status == ANSWER_STATUS_ANSWERED else [],
        "reranking_keyword": reranking_keyword,
        "query_intent_adaptive_top_k": query_intent_adaptive_top_k,
        "timings": timings,
        "retrieval_confidence": retrieval_confidence or {},
    }
    log_event(
        "rag_response_ready",
        request_id=request_id,
        query_hash=hash_query(user_query),
        answer_status=answer_status,
        domains=route.get("domains", []),
        source_count=len(payload["sources"]),
        context_count=len(payload["contexts"]),
        domain_error_count=len(domain_errors),
        total_ms=timings.get("total_ms"),
    )
    return payload


def run_domain_pipeline(
    *,
    user_query: str,
    domain: str,
    timings: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Optional[str], Dict[str, Any]]:
    domain_start = time.perf_counter()
    domain_timings: Dict[str, Any] = {}
    timings["domains"][domain] = domain_timings

    domain_module = DOMAIN_MODULES.get(domain)
    if domain_module is None:
        domain_timings["total_ms"] = elapsed_ms(domain_start)
        return [], {}, "Domain tidak dikenali.", {}

    try:
        analysis_start = time.perf_counter()
        analysis = domain_module.analyze_query(user_query)
        metadata_filter = domain_module.build_filter(analysis)
        domain_timings["analysis_ms"] = elapsed_ms(analysis_start)
        analysis_report = {
            "analysis": analysis,
            "metadata_filter": metadata_filter,
        }

        retrieval_start = time.perf_counter()
        collection_name = COLLECTION_BY_DOMAIN[domain]
        vectorstore = get_vectorstore(collection_name)
        results, retrieval_report = retrieve_with_fallback(
            vectorstore=vectorstore,
            query=user_query,
            metadata_filter=metadata_filter,
            k=10,
        )
        domain_timings["retrieval_ms"] = elapsed_ms(retrieval_start)
        analysis_report["retrieval"] = retrieval_report

        reranking_start = time.perf_counter()
        reranked = domain_module.rerank(
            results=results,
            rerank_keywords=analysis.get("rerank_keywords", []),
            query=user_query,
        )
        reranked = expand_with_neighbor_chunks(
            vectorstore,
            reranked,
            window=1,
            top_n=3,
        )
        reranked = annotate_rerank_results(
            retrieved_results=results,
            reranked_results=reranked,
            rerank_keywords=analysis.get("rerank_keywords", []),
        )
        reranked = formal_rerank(
            reranked_results=reranked,
            query=user_query,
            rerank_keywords=analysis.get("rerank_keywords", []),
            metadata_filter=metadata_filter,
        )
        reranked = refresh_rerank_positions(reranked)
        reranking_report = build_keyword_reranking_report(
            domain=domain,
            analysis=analysis,
            retrieved_count=len(results),
            reranked_results=reranked,
        )
        domain_timings["reranking_ms"] = elapsed_ms(reranking_start)

        return reranked[:5], analysis_report, None, reranking_report
    except Exception as exc:
        logger.exception("Failed to process domain %s", domain)
        return [], {"error": str(exc)}, str(exc), {}
    finally:
        domain_timings["total_ms"] = elapsed_ms(domain_start)


def rag_answer(user_query: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Versi response biasa: cocok untuk POST /chat.
    Tidak mengirim status bertahap ke frontend.
    """
    total_start = time.perf_counter()
    request_id = request_id or make_request_id()
    timings: Dict[str, Any] = {"domains": {}}

    log_event(
        "rag_request_started",
        request_id=request_id,
        query_hash=hash_query(user_query),
        mode="standard",
    )
    routing_start = time.perf_counter()
    route = route_query_domain(user_query)
    timings["routing_ms"] = elapsed_ms(routing_start)
    domains = route.get("domains", [])
    query_plan = route.get("query_plan", {})

    if not domains:
        timings["total_ms"] = elapsed_ms(total_start)
        return build_response_payload(
            request_id=request_id,
            user_query=user_query,
            answer="Domain pertanyaan tidak dapat ditentukan.",
            answer_status=ANSWER_STATUS_NO_DOMAIN,
            route=route,
            analyses={},
            domain_errors={},
            contexts=[],
            reranking_keyword={},
            query_intent_adaptive_top_k={},
            timings=timings,
        )

    fact_start = time.perf_counter()
    fact_answer = answer_from_facts(user_query, query_plan)
    timings["fact_search_ms"] = elapsed_ms(fact_start)
    if fact_answer:
        timings["total_ms"] = elapsed_ms(total_start)
        fact_contexts = fact_answer.get("contexts", [])
        return build_response_payload(
            request_id=request_id,
            user_query=user_query,
            answer=fact_answer["answer"],
            answer_status=ANSWER_STATUS_ANSWERED,
            route=route,
            analyses={
                "query_plan": query_plan,
                "structured_facts": {
                    "match_count": fact_answer.get("match_count", 0),
                    "summary": fact_answer.get("summary", {}),
                },
            },
            domain_errors={},
            sources=build_fact_sources_with_urls(fact_answer.get("sources", [])),
            contexts=[serialize_context(item) for item in fact_contexts[:3]],
            reranking_keyword={},
            query_intent_adaptive_top_k={
                "best_domain": "structured_facts",
                "query_intent": query_plan.get("intent"),
                "adaptive_top_k": len(fact_contexts),
                "context_count_used": len(fact_contexts),
                "available_context_count": len(fact_contexts),
                "selection_rule": "structured_fact_index_first",
            },
            timings=timings,
            retrieval_confidence={
                "sufficient": True,
                "reason": "structured_fact_match",
                "match_count": fact_answer.get("match_count", 0),
            },
        )

    all_contexts = []
    analyses = {}
    domain_errors = {}
    reranking_keyword = {"domains": {}}

    for domain in domains:
        contexts, analysis_report, error_message, reranking_report = run_domain_pipeline(
            user_query=user_query,
            domain=domain,
            timings=timings,
        )
        analyses[domain] = analysis_report

        if error_message:
            domain_errors[domain] = error_message
            continue

        if reranking_report:
            reranking_keyword["domains"][domain] = reranking_report
        all_contexts.extend(contexts)

    if not all_contexts:
        timings["total_ms"] = elapsed_ms(total_start)
        return build_response_payload(
            request_id=request_id,
            user_query=user_query,
            answer=build_no_context_answer(
                domain_errors=domain_errors,
                domain_count=len(domains),
            ),
            answer_status=build_no_context_status(
                domain_errors=domain_errors,
                domain_count=len(domains),
            ),
            route=route,
            analyses=analyses,
            domain_errors=domain_errors,
            contexts=[],
            reranking_keyword=reranking_keyword,
            query_intent_adaptive_top_k={},
            timings=timings,
        )

    global_reranking_start = time.perf_counter()
    all_contexts = sort_contexts(all_contexts)
    timings["global_reranking_ms"] = elapsed_ms(global_reranking_start)

    retrieval_confidence = build_retrieval_confidence(all_contexts)
    if not retrieval_confidence["sufficient"]:
        timings["total_ms"] = elapsed_ms(total_start)
        return build_response_payload(
            request_id=request_id,
            user_query=user_query,
            answer="Informasi yang relevan tidak ditemukan dalam dokumen yang tersedia.",
            answer_status=ANSWER_STATUS_NOT_FOUND,
            route=route,
            analyses=analyses,
            domain_errors=domain_errors,
            contexts=[],
            reranking_keyword=reranking_keyword,
            query_intent_adaptive_top_k={},
            timings=timings,
            retrieval_confidence=retrieval_confidence,
        )

    best_domain = all_contexts[0]["doc"].metadata.get("domain")
    query_intent = analyses.get(best_domain, {}).get("analysis", {}).get(
        "query_intent",
        "general_info",
    )
    query_intent_adaptive_top_k = build_query_intent_top_k_report(
        best_domain=best_domain,
        analyses=analyses,
        available_context_count=len(all_contexts),
    )
    reranking_keyword["summary"] = build_reranking_summary(reranking_keyword)

    answer_start = time.perf_counter()
    try:
        answer = generate_answer_from_context(
            user_query=user_query,
            reranked_results=all_contexts,
            query_intent=query_intent,
        )
    except Exception as exc:
        logger.exception("Failed to generate final answer")
        domain_errors["answer_generation"] = str(exc)
        answer = build_extractive_fallback_answer(
            reranked_results=all_contexts,
            query_intent=query_intent,
        )
        timings["answer_generation_ms"] = elapsed_ms(answer_start)
        timings["total_ms"] = elapsed_ms(total_start)
        top_k = query_intent_adaptive_top_k["adaptive_top_k"]
        return build_response_payload(
            request_id=request_id,
            user_query=user_query,
            answer=answer,
            answer_status=ANSWER_STATUS_ANSWERED,
            route=route,
            analyses=analyses,
            domain_errors=domain_errors,
            sources=build_structured_sources(all_contexts, top_k),
            contexts=[serialize_context(item) for item in all_contexts[:3]],
            reranking_keyword=reranking_keyword,
            query_intent_adaptive_top_k=query_intent_adaptive_top_k,
            timings=timings,
            retrieval_confidence=retrieval_confidence,
        )

    timings["answer_generation_ms"] = elapsed_ms(answer_start)
    timings["total_ms"] = elapsed_ms(total_start)
    answer_status = (
        ANSWER_STATUS_NOT_FOUND
        if is_unknown_answer(answer)
        else ANSWER_STATUS_ANSWERED
    )

    top_k = query_intent_adaptive_top_k["adaptive_top_k"]
    sources = build_structured_sources(all_contexts, top_k)
    payload = build_response_payload(
        request_id=request_id,
        user_query=user_query,
        answer=answer,
        answer_status=answer_status,
        route=route,
        analyses=analyses,
        domain_errors=domain_errors,
        sources=sources,
        contexts=[serialize_context(item) for item in all_contexts[:3]],
        reranking_keyword=reranking_keyword,
        query_intent_adaptive_top_k=query_intent_adaptive_top_k,
        timings=timings,
        retrieval_confidence=retrieval_confidence,
    )
    return payload


def rag_answer_stream(user_query: str) -> Generator[str, None, None]:
    """
    Versi streaming: cocok untuk GET /chat/stream.
    Fungsi ini mengirim status proses ke frontend secara bertahap.
    """
    total_start = time.perf_counter()
    request_id = make_request_id()
    timings: Dict[str, Any] = {"domains": {}}

    try:
        log_event(
            "rag_request_started",
            request_id=request_id,
            query_hash=hash_query(user_query),
            mode="stream",
        )
        yield make_sse_event(
            "status",
            {
                "request_id": request_id,
                "step": "routing",
                "message": "Menganalisis domain pertanyaan user...",
                "progress": 5,
            },
        )

        routing_start = time.perf_counter()
        route = route_query_domain(user_query)
        timings["routing_ms"] = elapsed_ms(routing_start)
        domains = route.get("domains", [])
        query_plan = route.get("query_plan", {})

        yield make_sse_event(
            "status",
            {
                "request_id": request_id,
                "step": "routing_done",
                "message": f"Query diarahkan ke domain: {', '.join(domains) if domains else 'tidak ditemukan'}",
                "progress": 15,
                "route": route,
                "domains": domains,
                "elapsed_ms": elapsed_ms(total_start),
            },
        )

        if not domains:
            timings["total_ms"] = elapsed_ms(total_start)
            yield make_sse_event(
                "done",
                build_response_payload(
                    request_id=request_id,
                    user_query=user_query,
                    answer="Domain pertanyaan tidak dapat ditentukan.",
                    answer_status=ANSWER_STATUS_NO_DOMAIN,
                    route=route,
                    analyses={},
                    domain_errors={},
                    contexts=[],
                    reranking_keyword={},
                    query_intent_adaptive_top_k={},
                    timings=timings,
                ),
            )
            return

        yield make_sse_event(
            "status",
            {
                "request_id": request_id,
                "step": "fact_search",
                "message": "Mencari jawaban di indeks fakta terstruktur...",
                "progress": 18,
                "query_plan": query_plan,
                "elapsed_ms": elapsed_ms(total_start),
            },
        )

        fact_start = time.perf_counter()
        fact_answer = answer_from_facts(user_query, query_plan)
        timings["fact_search_ms"] = elapsed_ms(fact_start)
        if fact_answer:
            timings["total_ms"] = elapsed_ms(total_start)
            fact_contexts = fact_answer.get("contexts", [])
            yield make_sse_event(
                "done",
                build_response_payload(
                    request_id=request_id,
                    user_query=user_query,
                    answer=fact_answer["answer"],
                    answer_status=ANSWER_STATUS_ANSWERED,
                    route=route,
                    analyses={
                        "query_plan": query_plan,
                        "structured_facts": {
                            "match_count": fact_answer.get("match_count", 0),
                            "summary": fact_answer.get("summary", {}),
                        },
                    },
                    domain_errors={},
                    sources=build_fact_sources_with_urls(fact_answer.get("sources", [])),
                    contexts=[serialize_context(item) for item in fact_contexts[:3]],
                    reranking_keyword={},
                    query_intent_adaptive_top_k={
                        "best_domain": "structured_facts",
                        "query_intent": query_plan.get("intent"),
                        "adaptive_top_k": len(fact_contexts),
                        "context_count_used": len(fact_contexts),
                        "available_context_count": len(fact_contexts),
                        "selection_rule": "structured_fact_index_first",
                    },
                    timings=timings,
                    retrieval_confidence={
                        "sufficient": True,
                        "reason": "structured_fact_match",
                        "match_count": fact_answer.get("match_count", 0),
                    },
                ),
            )
            return

        all_contexts = []
        analyses = {}
        domain_errors = {}
        reranking_keyword = {"domains": {}}
        total_domains = len(domains)

        for index, domain in enumerate(domains, start=1):
            domain_start = time.perf_counter()
            domain_timings: Dict[str, Any] = {}
            timings["domains"][domain] = domain_timings

            analyzing_progress = calculate_domain_progress(
                index=index,
                total_domains=total_domains,
                stage_fraction=0.15,
            )
            retrieving_progress = calculate_domain_progress(
                index=index,
                total_domains=total_domains,
                stage_fraction=0.50,
            )
            reranking_progress = calculate_domain_progress(
                index=index,
                total_domains=total_domains,
                stage_fraction=0.75,
            )
            domain_done_progress = calculate_domain_progress(
                index=index,
                total_domains=total_domains,
                stage_fraction=1.0,
            )

            domain_module = DOMAIN_MODULES.get(domain)
            if domain_module is None:
                error_message = "Domain tidak dikenali."
                domain_errors[domain] = error_message
                domain_timings["total_ms"] = elapsed_ms(domain_start)
                yield make_sse_event(
                    "status",
                    {
                        "step": "skip_domain",
                        "request_id": request_id,
                        "message": f"Domain {domain} tidak dikenali, dilewati.",
                        "progress": domain_done_progress,
                        "domain": domain,
                        "elapsed_ms": elapsed_ms(total_start),
                    },
                )
                continue

            yield make_sse_event(
                "status",
                {
                    "step": "analyzing_domain",
                    "request_id": request_id,
                    "message": f"Menganalisis query untuk domain {domain}...",
                    "progress": analyzing_progress,
                    "domain": domain,
                },
            )

            contexts, analysis_report, error_message, reranking_report = run_domain_pipeline(
                user_query=user_query,
                domain=domain,
                timings=timings,
            )
            analyses[domain] = analysis_report

            if not error_message:
                yield make_sse_event(
                    "status",
                    {
                        "step": "retrieving",
                        "request_id": request_id,
                        "message": f"Mengambil dokumen relevan dari ChromaDB untuk domain {domain}...",
                        "progress": retrieving_progress,
                        "domain": domain,
                        "metadata_filter": analysis_report.get("metadata_filter", {}),
                    },
                )

                yield make_sse_event(
                    "status",
                    {
                        "step": "reranking",
                        "request_id": request_id,
                        "message": f"Melakukan reranking dokumen untuk domain {domain}...",
                        "progress": reranking_progress,
                        "domain": domain,
                        "retrieved_count": get_retrieved_count(analysis_report),
                        "retrieval": analysis_report.get("retrieval", {}),
                        "elapsed_ms": elapsed_ms(total_start),
                    },
                )

                if reranking_report:
                    reranking_keyword["domains"][domain] = reranking_report
                all_contexts.extend(contexts)

                yield make_sse_event(
                    "status",
                    {
                        "step": "domain_done",
                        "request_id": request_id,
                        "message": f"Domain {domain} selesai diproses.",
                        "progress": domain_done_progress,
                        "domain": domain,
                        "selected_context_count": len(contexts),
                        "reranking_keyword": reranking_keyword["domains"].get(domain, {}),
                        "elapsed_ms": elapsed_ms(total_start),
                        "timings": timings["domains"].get(domain, {}),
                    },
                )
            else:
                domain_errors[domain] = error_message
                yield make_sse_event(
                    "status",
                    {
                        "step": "domain_error",
                        "request_id": request_id,
                        "message": f"Domain {domain} gagal diproses dan dilewati.",
                        "progress": domain_done_progress,
                        "domain": domain,
                        "error": error_message,
                        "elapsed_ms": elapsed_ms(total_start),
                        "timings": timings["domains"].get(domain, {}),
                    },
                )

        if not all_contexts:
            timings["total_ms"] = elapsed_ms(total_start)
            yield make_sse_event(
                "done",
                build_response_payload(
                    request_id=request_id,
                    user_query=user_query,
                    answer=build_no_context_answer(
                        domain_errors=domain_errors,
                        domain_count=len(domains),
                    ),
                    answer_status=build_no_context_status(
                        domain_errors=domain_errors,
                        domain_count=len(domains),
                    ),
                    route=route,
                    analyses=analyses,
                    domain_errors=domain_errors,
                    contexts=[],
                    reranking_keyword=reranking_keyword,
                    query_intent_adaptive_top_k={},
                    timings=timings,
                ),
            )
            return

        yield make_sse_event(
            "status",
            {
                "step": "global_reranking",
                "request_id": request_id,
                "message": "Mengurutkan ulang dokumen terbaik dari seluruh domain...",
                "progress": 80,
                "total_context_count": len(all_contexts),
                "elapsed_ms": elapsed_ms(total_start),
            },
        )

        global_reranking_start = time.perf_counter()
        all_contexts = sort_contexts(all_contexts)
        timings["global_reranking_ms"] = elapsed_ms(global_reranking_start)

        retrieval_confidence = build_retrieval_confidence(all_contexts)
        if not retrieval_confidence["sufficient"]:
            timings["total_ms"] = elapsed_ms(total_start)
            yield make_sse_event(
                "done",
                build_response_payload(
                    request_id=request_id,
                    user_query=user_query,
                    answer="Informasi yang relevan tidak ditemukan dalam dokumen yang tersedia.",
                    answer_status=ANSWER_STATUS_NOT_FOUND,
                    route=route,
                    analyses=analyses,
                    domain_errors=domain_errors,
                    contexts=[],
                    reranking_keyword=reranking_keyword,
                    query_intent_adaptive_top_k={},
                    timings=timings,
                    retrieval_confidence=retrieval_confidence,
                ),
            )
            return

        best_domain = all_contexts[0]["doc"].metadata.get("domain")
        query_intent = analyses.get(best_domain, {}).get("analysis", {}).get(
            "query_intent",
            "general_info",
        )
        query_intent_adaptive_top_k = build_query_intent_top_k_report(
            best_domain=best_domain,
            analyses=analyses,
            available_context_count=len(all_contexts),
        )
        reranking_keyword["summary"] = build_reranking_summary(reranking_keyword)

        yield make_sse_event(
            "status",
            {
                "step": "generating",
                "request_id": request_id,
                "message": "Menyusun jawaban akhir menggunakan konteks terbaik...",
                "progress": 90,
                "best_domain": best_domain,
                "query_intent": query_intent,
                "adaptive_top_k": query_intent_adaptive_top_k["adaptive_top_k"],
                "elapsed_ms": elapsed_ms(total_start),
            },
        )

        answer_start = time.perf_counter()
        try:
            answer = generate_answer_from_context(
                user_query=user_query,
                reranked_results=all_contexts,
                query_intent=query_intent,
            )
        except Exception as exc:
            logger.exception("Failed to generate final answer")
            domain_errors["answer_generation"] = str(exc)
            answer = build_extractive_fallback_answer(
                reranked_results=all_contexts,
                query_intent=query_intent,
            )
            timings["answer_generation_ms"] = elapsed_ms(answer_start)
            timings["total_ms"] = elapsed_ms(total_start)
            top_k = query_intent_adaptive_top_k["adaptive_top_k"]
            yield make_sse_event(
                "done",
                build_response_payload(
                    request_id=request_id,
                    user_query=user_query,
                    answer=answer,
                    answer_status=ANSWER_STATUS_ANSWERED,
                    route=route,
                    analyses=analyses,
                    domain_errors=domain_errors,
                    sources=build_structured_sources(all_contexts, top_k),
                    contexts=[serialize_context(item) for item in all_contexts[:3]],
                    reranking_keyword=reranking_keyword,
                    query_intent_adaptive_top_k=query_intent_adaptive_top_k,
                    timings=timings,
                    retrieval_confidence=retrieval_confidence,
                ),
            )
            return

        timings["answer_generation_ms"] = elapsed_ms(answer_start)
        timings["total_ms"] = elapsed_ms(total_start)
        answer_status = (
            ANSWER_STATUS_NOT_FOUND
            if is_unknown_answer(answer)
            else ANSWER_STATUS_ANSWERED
        )
        top_k = query_intent_adaptive_top_k["adaptive_top_k"]
        sources = build_structured_sources(all_contexts, top_k)
        payload = build_response_payload(
            request_id=request_id,
            user_query=user_query,
            answer=answer,
            answer_status=answer_status,
            route=route,
            analyses=analyses,
            domain_errors=domain_errors,
            sources=sources,
            contexts=[serialize_context(item) for item in all_contexts[:3]],
            reranking_keyword=reranking_keyword,
            query_intent_adaptive_top_k=query_intent_adaptive_top_k,
            timings=timings,
            retrieval_confidence=retrieval_confidence,
        )
        yield make_sse_event(
            "done",
            payload,
        )

    except Exception as exc:
        logger.exception("Failed to stream chat request")
        timings["total_ms"] = elapsed_ms(total_start)
        yield make_sse_event(
            "error",
            {
                "request_id": request_id,
                "step": "error",
                "message": str(exc),
                "timings": timings,
            },
        )


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "message": "RAG FastAPI server is running",
        "llm_provider": "groq",
        "app_env": settings.app_env,
        "frontend_origins": list(settings.frontend_origins),
        "cors_allow_origin_regex": settings.cors_allow_origin_regex,
        "docs": "/docs",
        "chat_endpoint": "POST /chat",
        "stream_endpoint": "GET /chat/stream?query=...",
    }


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/cache/stats")
def cache_stats() -> Dict[str, Any]:
    return {"structured_generation": structured_cache_stats()}


@app.get("/documents/{domain_key}/{file_name}")
def get_document_pdf(domain_key: str, file_name: str) -> FileResponse:
    path = resolve_document_path(domain_key, file_name)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> Dict[str, Any]:
    """
    Endpoint biasa:
    frontend menunggu sampai semua proses selesai, lalu menerima satu JSON final.
    """
    try:
        result = await run_in_threadpool(rag_answer, request.query)
        return {
            "request_id": result.get("request_id", ""),
            "user_query": request.query,
            "answer": result["answer"],
            "answer_status": result.get("answer_status", ANSWER_STATUS_ANSWERED),
            "route": result.get("route", {}),
            "analyses": result.get("analyses", {}),
            "domain_errors": result.get("domain_errors", {}),
            "sources": result.get("sources", []),
            "contexts": result.get("contexts", []),
            "reranking_keyword": result.get("reranking_keyword", {}),
            "query_intent_adaptive_top_k": result.get(
                "query_intent_adaptive_top_k",
                {},
            ),
            "timings": result.get("timings", {}),
            "retrieval_confidence": result.get("retrieval_confidence", {}),
        }
    except Exception as exc:
        logger.exception("Failed to process chat request")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/chat/stream")
def chat_stream(query: str = Query(..., min_length=1, max_length=1000)) -> StreamingResponse:
    """
    Endpoint streaming status:
    frontend akan menerima event bertahap lewat Server-Sent Events.
    """
    return StreamingResponse(
        rag_answer_stream(query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Jalankan dari root project:
# uvicorn main_streaming:app --reload
