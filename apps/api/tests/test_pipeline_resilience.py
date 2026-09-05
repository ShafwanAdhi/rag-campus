import json
import unittest
from unittest.mock import patch

from langchain_core.documents import Document

import main
from app.retrieval import (
    build_filter_candidates,
    expand_with_neighbor_chunks,
    normalize_filter,
    retrieve_with_fallback,
)


class FakeEmbedding:
    def __init__(self):
        self.call_count = 0

    def embed_query(self, query):
        self.call_count += 1
        return [0.1, 0.2]


class FakeVectorstore:
    def __init__(self):
        self._embedding_function = FakeEmbedding()
        self.filters = []

    def similarity_search_by_vector_with_relevance_scores(
        self,
        embedding,
        k,
        filter,
    ):
        self.filters.append(filter)
        if len(self.filters) == 1:
            return []
        return [
            (
                Document(
                    page_content="jadwal krs",
                    metadata={
                        "file_name": "kalender.pdf",
                        "page": 1,
                        "chunk_index": 0,
                    },
                ),
                0.1,
            )
        ]


class FakeCollection:
    def get(self, **kwargs):
        return {
            "ids": ["lexical-1"],
            "documents": [
                "Registrasi akademik KRS Online semester gasal 2026/2027."
            ],
            "metadatas": [
                {
                    "file_name": "kalender.pdf",
                    "page": 1,
                    "chunk_index": 1,
                    "domain": "academic_administration",
                }
            ],
        }


class LexicalOnlyVectorstore:
    def __init__(self):
        self._embedding_function = FakeEmbedding()
        self._collection = FakeCollection()

    def similarity_search_by_vector_with_relevance_scores(
        self,
        embedding,
        k,
        filter,
    ):
        return []


class NeighborCollection:
    def __init__(self):
        self.rows = {
            4: "Sebelum prosedur cuti.",
            5: "Tata cara permohonan cuti kuliah dimulai di sini.",
            6: "Mahasiswa menyerahkan permohonan kepada Subbag Registrasi.",
        }

    def get(self, **kwargs):
        where = kwargs.get("where", {})
        conditions = where.get("$and", [])
        chunk_index = None
        for condition in conditions:
            if "chunk_index" in condition:
                chunk_index = condition["chunk_index"]

        if chunk_index not in self.rows:
            return {"ids": [], "documents": [], "metadatas": []}

        return {
            "ids": [f"doc-page-1-chunk-{chunk_index}"],
            "documents": [self.rows[chunk_index]],
            "metadatas": [
                {
                    "file_name": "pedoman.pdf",
                    "page": 1,
                    "chunk_index": chunk_index,
                    "domain": "academic_administration",
                }
            ],
        }


class NeighborVectorstore:
    def __init__(self):
        self._collection = NeighborCollection()


class FailingDomain:
    @staticmethod
    def analyze_query(user_query):
        raise RuntimeError("analyzer unavailable")


class WorkingDomain:
    @staticmethod
    def analyze_query(user_query):
        return {
            "query_intent": "general_info",
            "metadata_filters": {},
            "rerank_keywords": [],
        }

    @staticmethod
    def build_filter(analysis):
        return {"domain": "facilities_and_campus_services"}

    @staticmethod
    def rerank(results, rerank_keywords, query):
        return [
            {
                "doc": doc,
                "distance": distance,
                "keyword_bonus": 0,
                "penalty": 0,
                "final_score": 1,
            }
            for doc, distance in results
        ]


class LowConfidenceDomain(WorkingDomain):
    @staticmethod
    def rerank(results, rerank_keywords, query):
        return [
            {
                "doc": doc,
                "distance": distance,
                "keyword_bonus": 0,
                "penalty": 0,
                "final_score": 0,
            }
            for doc, distance in results
        ]


def parse_sse_events(raw_events):
    parsed = []
    for raw_event in raw_events:
        event_name = None
        data = None
        for line in raw_event.strip().splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            if line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        parsed.append((event_name, data))
    return parsed


class RetrievalFallbackTests(unittest.TestCase):
    def test_single_condition_and_filter_is_normalized_for_chroma(self):
        requested_filter = {"$and": [{"domain": "academic_administration"}]}

        self.assertEqual(
            normalize_filter(requested_filter),
            {"domain": "academic_administration"},
        )
        self.assertEqual(
            build_filter_candidates(requested_filter),
            [{"domain": "academic_administration"}],
        )

    def test_general_filter_is_relaxed_before_other_metadata(self):
        requested_filter = {
            "$and": [
                {"domain": "academic_administration"},
                {"document_type": "academic_calendar"},
                {"academic_year": "general"},
                {"topic": "academic_calendar"},
            ]
        }

        candidates = build_filter_candidates(requested_filter)

        self.assertEqual(candidates[0], requested_filter)
        self.assertEqual(
            candidates[1],
            {
                "$and": [
                    {"domain": "academic_administration"},
                    {"document_type": "academic_calendar"},
                    {"topic": "academic_calendar"},
                ]
            },
        )

    def test_fallback_reuses_one_query_embedding(self):
        vectorstore = FakeVectorstore()
        requested_filter = {
            "$and": [
                {"domain": "academic_administration"},
                {"academic_year": "general"},
            ]
        }

        results, report = retrieve_with_fallback(
            vectorstore=vectorstore,
            query="jadwal krs",
            metadata_filter=requested_filter,
            k=10,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].page_content, "jadwal krs")
        self.assertEqual(vectorstore._embedding_function.call_count, 1)
        self.assertTrue(report["fallback_used"])
        self.assertEqual(len(report["attempts"]), 2)

    def test_hybrid_retrieval_uses_lexical_results_when_vector_is_empty(self):
        vectorstore = LexicalOnlyVectorstore()

        results, report = retrieve_with_fallback(
            vectorstore=vectorstore,
            query="KRS Online semester gasal 2026/2027",
            metadata_filter={"domain": "academic_administration"},
            k=10,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(report["mode"], "hybrid_vector_bm25")
        self.assertEqual(report["attempts"][0]["vector_count"], 0)
        self.assertEqual(report["attempts"][0]["lexical_count"], 1)
        self.assertEqual(
            results[0][0].metadata["_retrieval"]["channels"],
            ["lexical"],
        )

    def test_neighbor_expansion_adds_adjacent_chunks(self):
        seed_doc = Document(
            page_content="Tata cara permohonan cuti kuliah dimulai di sini.",
            metadata={
                "file_name": "pedoman.pdf",
                "page": 1,
                "chunk_index": 5,
                "domain": "academic_administration",
            },
        )
        seed_results = [
            {
                "doc": seed_doc,
                "distance": 0.1,
                "keyword_bonus": 3,
                "penalty": 0,
                "final_score": 3,
            }
        ]

        expanded = expand_with_neighbor_chunks(
            NeighborVectorstore(),
            seed_results,
            window=1,
            top_n=1,
        )
        chunk_indexes = sorted(
            item["doc"].metadata["chunk_index"]
            for item in expanded
        )

        self.assertEqual(chunk_indexes, [4, 5, 6])
        neighbor_channels = [
            item["doc"].metadata.get("_retrieval", {}).get("channels", [])
            for item in expanded
            if item["doc"].metadata["chunk_index"] != 5
        ]
        self.assertTrue(all("neighbor" in channels for channels in neighbor_channels))


class PipelineResilienceTests(unittest.TestCase):
    def test_progress_is_monotonic_for_multiple_domains(self):
        progress_values = [5, 15]
        for index in range(1, 5):
            for stage_fraction in (0.15, 0.50, 0.75, 1.0):
                progress_values.append(
                    main.calculate_domain_progress(
                        index=index,
                        total_domains=4,
                        stage_fraction=stage_fraction,
                    )
                )
        progress_values.extend([80, 90, 100])

        self.assertEqual(progress_values, sorted(progress_values))

    def test_stream_continues_when_one_domain_fails(self):
        document = Document(
            page_content="Informasi fasilitas kampus.",
            metadata={
                "domain": "facilities_and_campus_services",
                "file_name": "fasilitas.pdf",
                "page": 1,
                "chunk_index": 0,
            },
        )
        retrieval_report = {
            "requested_filter": {"domain": "facilities_and_campus_services"},
            "applied_filter": {"domain": "facilities_and_campus_services"},
            "fallback_used": False,
            "attempts": [],
        }

        with (
            patch.object(
                main,
                "route_query_domain",
                return_value={
                    "domains": [
                        "academic_administration",
                        "facilities_and_campus_services",
                    ],
                    "reason": "test",
                },
            ),
            patch.dict(
                main.DOMAIN_MODULES,
                {
                    "academic_administration": FailingDomain,
                    "facilities_and_campus_services": WorkingDomain,
                },
            ),
            patch.object(main, "get_vectorstore", return_value=object()),
            patch.object(
                main,
                "retrieve_with_fallback",
                return_value=([(document, 0.1)], retrieval_report),
            ),
            patch.object(
                main,
                "generate_answer_from_context",
                return_value="Jawaban tetap tersedia.",
            ),
        ):
            events = parse_sse_events(
                list(main.rag_answer_stream("pertanyaan multi-domain"))
            )

        status_payloads = [
            data for event_name, data in events if event_name == "status"
        ]
        done_payload = next(
            data for event_name, data in events if event_name == "done"
        )

        self.assertTrue(
            any(payload["step"] == "domain_error" for payload in status_payloads)
        )
        self.assertEqual(done_payload["answer"], "Jawaban tetap tersedia.")
        self.assertEqual(done_payload["answer_status"], "answered")
        self.assertEqual(done_payload["sources"][0]["file_name"], "fasilitas.pdf")
        self.assertEqual(done_payload["sources"][0]["pages"], [1])
        self.assertIn(
            "academic_administration",
            done_payload["domain_errors"],
        )
        self.assertEqual(len(done_payload["contexts"]), 1)
        self.assertIn("timings", done_payload)
        self.assertIn("domains", done_payload["timings"])
        self.assertIn(
            "facilities_and_campus_services",
            done_payload["timings"]["domains"],
        )

    def test_low_confidence_context_returns_not_found_without_generation(self):
        document = Document(
            page_content="Konten umum yang tidak cukup cocok.",
            metadata={
                "domain": "facilities_and_campus_services",
                "file_name": "fasilitas.pdf",
                "page": 1,
                "chunk_index": 0,
            },
        )
        retrieval_report = {
            "requested_filter": {"domain": "facilities_and_campus_services"},
            "applied_filter": {"domain": "facilities_and_campus_services"},
            "fallback_used": False,
            "attempts": [{"result_count": 1}],
        }

        with (
            patch.object(
                main,
                "route_query_domain",
                return_value={
                    "domains": ["facilities_and_campus_services"],
                    "reason": "test",
                },
            ),
            patch.dict(
                main.DOMAIN_MODULES,
                {"facilities_and_campus_services": LowConfidenceDomain},
            ),
            patch.object(main, "get_vectorstore", return_value=object()),
            patch.object(
                main,
                "retrieve_with_fallback",
                return_value=([(document, 0.9)], retrieval_report),
            ),
            patch.object(main, "generate_answer_from_context") as generate_answer,
        ):
            result = main.rag_answer("pertanyaan tidak tersedia")

        self.assertEqual(result["answer_status"], "not_found")
        self.assertFalse(result["retrieval_confidence"]["sufficient"])
        self.assertEqual(result["contexts"], [])
        generate_answer.assert_not_called()

    def test_answer_generation_error_returns_extractive_fallback(self):
        document = Document(
            page_content="Konten valid.",
            metadata={
                "domain": "facilities_and_campus_services",
                "file_name": "fasilitas.pdf",
                "page": 1,
                "chunk_index": 0,
            },
        )
        retrieval_report = {
            "requested_filter": {"domain": "facilities_and_campus_services"},
            "applied_filter": {"domain": "facilities_and_campus_services"},
            "fallback_used": False,
            "attempts": [{"result_count": 1}],
        }

        with (
            patch.object(
                main,
                "route_query_domain",
                return_value={
                    "domains": ["facilities_and_campus_services"],
                    "reason": "test",
                },
            ),
            patch.dict(
                main.DOMAIN_MODULES,
                {"facilities_and_campus_services": WorkingDomain},
            ),
            patch.object(main, "get_vectorstore", return_value=object()),
            patch.object(
                main,
                "retrieve_with_fallback",
                return_value=([(document, 0.1)], retrieval_report),
            ),
            patch.object(
                main,
                "generate_answer_from_context",
                side_effect=RuntimeError("rate limited"),
            ),
        ):
            result = main.rag_answer("pertanyaan valid")

        self.assertEqual(result["answer_status"], "answered")
        self.assertIn("answer_generation", result["domain_errors"])
        self.assertIn("Konten valid.", result["answer"])
        self.assertEqual(len(result["contexts"]), 1)
        self.assertEqual(result["sources"][0]["file_name"], "fasilitas.pdf")


if __name__ == "__main__":
    unittest.main()
