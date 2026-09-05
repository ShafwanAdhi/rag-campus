from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_chroma import Chroma

from app.config import settings
from app.embeddings import get_embeddings
from app.reranking import bm25_scores, normalize_scores


CHROMA_DIR = settings.chroma_dir


def get_vectorstore(collection_name: str):
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def normalize_filter(metadata_filter: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not metadata_filter:
        return None

    if not isinstance(metadata_filter, dict):
        return metadata_filter

    if len(metadata_filter) == 1:
        operator = next(iter(metadata_filter))
        if operator in {"$and", "$or"} and isinstance(metadata_filter[operator], list):
            conditions = [
                normalized
                for condition in metadata_filter[operator]
                if isinstance(condition, dict)
                for normalized in [normalize_filter(condition)]
                if normalized
            ]

            if not conditions:
                return None
            if len(conditions) == 1:
                return conditions[0]

            return {operator: conditions}

    return metadata_filter


def document_key(doc: Document) -> Tuple[Any, Any, Any, Any]:
    metadata = doc.metadata or {}
    return (
        metadata.get("source") or metadata.get("file_name"),
        metadata.get("page"),
        metadata.get("chunk_index"),
        getattr(doc, "id", None),
    )


def with_retrieval_signal(
    doc: Document,
    *,
    channel: str,
    rank: int,
    score: Optional[float] = None,
    distance: Optional[float] = None,
) -> Document:
    metadata = dict(doc.metadata or {})
    signal = dict(metadata.get("_retrieval", {}) or {})
    channels = list(signal.get("channels", []))
    if channel not in channels:
        channels.append(channel)

    signal["channels"] = channels
    signal[f"{channel}_rank"] = rank

    if score is not None:
        signal[f"{channel}_score_normalized"] = score

    if distance is not None:
        signal["vector_distance"] = distance

    metadata["_retrieval"] = signal
    return Document(
        page_content=doc.page_content,
        metadata=metadata,
        id=getattr(doc, "id", None),
    )


def get_collection_documents(
    vectorstore,
    metadata_filter: Optional[Dict[str, Any]],
) -> List[Document]:
    collection = getattr(vectorstore, "_collection", None)
    if collection is None:
        return []

    applied_filter = normalize_filter(metadata_filter)
    kwargs: Dict[str, Any] = {"include": ["documents", "metadatas"]}
    if applied_filter:
        kwargs["where"] = applied_filter

    payload = collection.get(**kwargs)
    ids = payload.get("ids") or []
    documents = payload.get("documents") or []
    metadatas = payload.get("metadatas") or []

    return [
        Document(
            page_content=document or "",
            metadata=metadata or {},
            id=ids[index] if index < len(ids) else None,
        )
        for index, (document, metadata) in enumerate(zip(documents, metadatas))
    ]


def get_neighbor_documents(
    vectorstore,
    *,
    file_name: str,
    chunk_index: int,
    window: int = 1,
) -> List[Document]:
    collection = getattr(vectorstore, "_collection", None)
    if collection is None or not file_name:
        return []

    neighbors = []
    for offset in range(-window, window + 1):
        if offset == 0:
            continue

        neighbor_index = chunk_index + offset
        if neighbor_index < 0:
            continue

        payload = collection.get(
            where={
                "$and": [
                    {"file_name": file_name},
                    {"chunk_index": neighbor_index},
                ]
            },
            include=["documents", "metadatas"],
        )
        ids = payload.get("ids") or []
        documents = payload.get("documents") or []
        metadatas = payload.get("metadatas") or []

        for index, (document, metadata) in enumerate(zip(documents, metadatas)):
            neighbors.append(
                Document(
                    page_content=document or "",
                    metadata=metadata or {},
                    id=ids[index] if index < len(ids) else None,
                )
            )

    return neighbors


def expand_with_neighbor_chunks(
    vectorstore,
    reranked_results: List[Dict[str, Any]],
    *,
    window: int = 1,
    top_n: int = 3,
) -> List[Dict[str, Any]]:
    expanded: Dict[Tuple[Any, Any, Any, Any], Dict[str, Any]] = {
        document_key(item["doc"]): item
        for item in reranked_results
        if item.get("doc") is not None
    }

    for seed in reranked_results[:top_n]:
        doc = seed.get("doc")
        metadata = getattr(doc, "metadata", {}) or {}
        file_name = metadata.get("file_name")
        chunk_index = metadata.get("chunk_index")

        if not isinstance(chunk_index, int):
            continue

        for neighbor in get_neighbor_documents(
            vectorstore,
            file_name=file_name,
            chunk_index=chunk_index,
            window=window,
        ):
            key = document_key(neighbor)
            if key in expanded:
                continue

            neighbor_metadata = dict(neighbor.metadata or {})
            signal = dict(neighbor_metadata.get("_retrieval", {}) or {})
            signal["channels"] = list(dict.fromkeys([
                *signal.get("channels", []),
                "neighbor",
            ]))
            signal["neighbor_of_chunk_index"] = chunk_index
            signal["neighbor_window"] = window
            neighbor_metadata["_retrieval"] = signal

            expanded[key] = {
                "doc": Document(
                    page_content=neighbor.page_content,
                    metadata=neighbor_metadata,
                    id=getattr(neighbor, "id", None),
                ),
                "distance": seed.get("distance", 999),
                "keyword_bonus": 0,
                "penalty": 0,
                "final_score": max((seed.get("final_score") or 0) - 0.25, 0),
                "sort_key": (
                    -(max((seed.get("final_score") or 0) - 0.25, 0)),
                    seed.get("distance", 999),
                ),
            }

    return list(expanded.values())


def lexical_search(
    vectorstore,
    query: str,
    metadata_filter: Optional[Dict[str, Any]],
    k: int,
) -> List[Tuple[Document, float]]:
    documents = get_collection_documents(vectorstore, metadata_filter)
    if not documents:
        return []

    raw_scores = bm25_scores(query, [doc.page_content for doc in documents])
    normalized_scores = normalize_scores(raw_scores)
    scored_docs = [
        (doc, raw_score, normalized_score)
        for doc, raw_score, normalized_score in zip(
            documents,
            raw_scores,
            normalized_scores,
        )
        if raw_score > 0
    ]
    scored_docs.sort(key=lambda item: item[1], reverse=True)

    return [
        (
            with_retrieval_signal(
                doc,
                channel="lexical",
                rank=rank,
                score=normalized_score,
            ),
            _raw_score,
        )
        for rank, (doc, _raw_score, normalized_score) in enumerate(
            scored_docs[:k],
            start=1,
        )
    ]


def merge_hybrid_results(
    vector_results: List[Tuple[Document, float]],
    lexical_results: List[Tuple[Document, float]],
    k: int,
) -> List[Tuple[Document, float]]:
    merged: Dict[Tuple[Any, Any, Any, Any], Tuple[Document, float]] = {}

    for rank, (doc, distance) in enumerate(vector_results, start=1):
        signaled_doc = with_retrieval_signal(
            doc,
            channel="vector",
            rank=rank,
            distance=distance,
        )
        merged[document_key(signaled_doc)] = (signaled_doc, distance)

    for rank, (doc, _score) in enumerate(lexical_results, start=1):
        key = document_key(doc)
        if key in merged:
            existing_doc, existing_distance = merged[key]
            existing_signal = dict((existing_doc.metadata or {}).get("_retrieval", {}) or {})
            lexical_signal = dict((doc.metadata or {}).get("_retrieval", {}) or {})
            channels = list(dict.fromkeys(
                existing_signal.get("channels", []) + lexical_signal.get("channels", [])
            ))
            existing_signal.update(lexical_signal)
            existing_signal["channels"] = channels
            metadata = dict(existing_doc.metadata or {})
            metadata["_retrieval"] = existing_signal
            merged[key] = (
                Document(
                    page_content=existing_doc.page_content,
                    metadata=metadata,
                    id=getattr(existing_doc, "id", None),
                ),
                existing_distance,
            )
        else:
            merged[key] = (doc, 1.0 + (rank / 1000))

    return sorted(
        merged.values(),
        key=lambda item: (
            0 if "vector" in ((item[0].metadata or {}).get("_retrieval", {}).get("channels", [])) else 1,
            item[1],
        ),
    )[:k]


def retrieve(vectorstore, query: str, metadata_filter: dict, k: int = 10):
    normalized_filter = normalize_filter(metadata_filter)
    if normalized_filter:
        return vectorstore.similarity_search_with_score(
            query,
            k=k,
            filter=normalized_filter,
        )

    return vectorstore.similarity_search_with_score(
        query,
        k=k
    )


def _flatten_filter(metadata_filter: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not metadata_filter:
        return []

    if (
        set(metadata_filter) == {"$and"}
        and isinstance(metadata_filter["$and"], list)
    ):
        return [
            condition
            for condition in metadata_filter["$and"]
            if isinstance(condition, dict) and condition
        ]

    return [metadata_filter]


def _combine_filter_conditions(
    conditions: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def build_filter_candidates(
    metadata_filter: Optional[Dict[str, Any]],
) -> List[Optional[Dict[str, Any]]]:
    """
    Membuat urutan filter dari paling ketat ke paling longgar.

    Nilai metadata "general" dilepas lebih dulu karena sering dipakai analyzer
    saat user tidak menyebut tahun, sementara dokumen aktual memiliki tahun
    spesifik. Filter domain dipertahankan selama tersedia.
    """
    conditions = _flatten_filter(metadata_filter)
    candidates: List[Optional[Dict[str, Any]]] = []

    def add_candidate(candidate_conditions: List[Dict[str, Any]]) -> None:
        candidate = normalize_filter(_combine_filter_conditions(candidate_conditions))
        if candidate not in candidates:
            candidates.append(candidate)

    add_candidate(conditions)

    without_general = [
        condition
        for condition in conditions
        if not any(value == "general" for value in condition.values())
    ]
    add_candidate(without_general)

    working_conditions = list(without_general)
    while any("domain" not in condition for condition in working_conditions):
        for index in range(len(working_conditions) - 1, -1, -1):
            if "domain" not in working_conditions[index]:
                del working_conditions[index]
                add_candidate(working_conditions)
                break

    if not candidates:
        candidates.append(None)

    return candidates


def retrieve_with_fallback(
    vectorstore,
    query: str,
    metadata_filter: Optional[Dict[str, Any]],
    k: int = 10,
) -> Tuple[List[Any], Dict[str, Any]]:
    """
    Menjalankan retrieval dengan satu query embedding dan filter adaptif.

    Filter berikutnya hanya dicoba saat filter sebelumnya tidak menghasilkan
    dokumen. Laporan dikembalikan agar fallback dapat terlihat di whitebox API.
    """
    embedding_function = getattr(vectorstore, "_embedding_function", None)
    if embedding_function is None:
        applied_filter = normalize_filter(metadata_filter)
        results = retrieve(vectorstore, query, applied_filter or {}, k)
        return results, {
            "requested_filter": metadata_filter,
            "applied_filter": applied_filter,
            "fallback_used": applied_filter != metadata_filter,
            "attempts": [
                {
                    "filter": applied_filter,
                    "result_count": len(results),
                }
            ],
        }

    query_embedding = embedding_function.embed_query(query)
    attempts = []
    candidates = build_filter_candidates(metadata_filter)

    for candidate_filter in candidates:
        vector_results = vectorstore.similarity_search_by_vector_with_relevance_scores(
            embedding=query_embedding,
            k=max(k * 2, 20),
            filter=candidate_filter,
        )
        lexical_results = lexical_search(
            vectorstore=vectorstore,
            query=query,
            metadata_filter=candidate_filter,
            k=max(k * 2, 20),
        )
        results = merge_hybrid_results(
            vector_results=vector_results,
            lexical_results=lexical_results,
            k=k,
        )
        attempts.append(
            {
                "filter": candidate_filter,
                "mode": "hybrid_vector_bm25",
                "vector_count": len(vector_results),
                "lexical_count": len(lexical_results),
                "result_count": len(results),
            }
        )

        if results:
            return results, {
                "requested_filter": metadata_filter,
                "applied_filter": candidate_filter,
                "fallback_used": candidate_filter != metadata_filter,
                "mode": "hybrid_vector_bm25",
                "attempts": attempts,
            }

    return [], {
        "requested_filter": metadata_filter,
        "applied_filter": candidates[-1],
        "fallback_used": len(candidates) > 1,
        "mode": "hybrid_vector_bm25",
        "attempts": attempts,
    }
