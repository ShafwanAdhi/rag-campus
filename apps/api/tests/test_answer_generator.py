import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from app.answer_generator import generate_answer_from_context


def make_reranked_result():
    return [
        {
            "doc": Document(
                page_content="Konten dokumen contoh.",
                metadata={
                    "file_name": "dokumen.pdf",
                    "page": 1,
                    "chunk_index": 0,
                    "domain": "academic_administration",
                    "document_type": "guide",
                    "academic_year": "general",
                    "document_year": "2026",
                    "topic": "general",
                },
            ),
            "distance": 0.1,
            "final_score": 0.9,
        }
    ]


class AnswerGeneratorTests(unittest.TestCase):
    def test_unknown_answer_does_not_append_source_line(self):
        with patch(
            "app.answer_generator.groq_generate_answer",
            return_value="Informasi tersebut tidak ditemukan secara jelas dalam dokumen yang tersedia.",
        ):
            answer = generate_answer_from_context(
                user_query="pertanyaan tidak ada di dokumen",
                reranked_results=make_reranked_result(),
                query_intent="general_info",
            )

        self.assertEqual(
            answer,
            "Informasi tersebut tidak ditemukan secara jelas dalam dokumen yang tersedia.",
        )
        self.assertNotIn("Sumber:", answer)

    def test_known_answer_does_not_append_source_line(self):
        with patch(
            "app.answer_generator.groq_generate_answer",
            return_value="Jawaban berdasarkan dokumen.",
        ):
            answer = generate_answer_from_context(
                user_query="pertanyaan ada di dokumen",
                reranked_results=make_reranked_result(),
                query_intent="general_info",
            )

        self.assertIn("Jawaban berdasarkan dokumen.", answer)
        self.assertNotIn("Sumber:", answer)


if __name__ == "__main__":
    unittest.main()
