import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

import main
from app import fact_index
from app.fact_extraction import extract_program_study_facts_from_pages
from app.query_planner import plan_query


class StructuredFactExtractionTests(unittest.TestCase):
    def test_extract_program_studies_across_continued_faculty_table(self):
        pages = [
            Document(
                page_content=(
                    "44|Pedoman Pendidikan Edisi 2020 "
                    "Tabel 6 Kode Matakuliah Keilmuan dan Keahlian Program Diploma III "
                    "III FAKULTAS TEKNIK 1 Teknik Mesin NTMEUM53xx"
                ),
                metadata={
                    "domain": "academic_administration",
                    "file_name": "pedoman.pdf",
                    "page": 68,
                    "document_year": "2020",
                    "topic": "pedoman_pendidikan",
                },
            ),
            Document(
                page_content=(
                    "Bab III Kurikulum | 45 "
                    "No Program Studi Kode Matakuliah "
                    "2 Teknik Sipil dan Bangunan NTSBUM53xx "
                    "3 Teknik Elektro NTROUM53xx "
                    "(3) Kode matakuliah yang berlaku di UM untuk program sarjana."
                ),
                metadata={
                    "domain": "academic_administration",
                    "file_name": "pedoman.pdf",
                    "page": 69,
                    "document_year": "2020",
                    "topic": "pedoman_pendidikan",
                },
            ),
        ]

        facts = extract_program_study_facts_from_pages(pages)
        names = [fact["program_name"] for fact in facts]

        self.assertEqual(
            names,
            ["Teknik Mesin", "Teknik Sipil dan Bangunan", "Teknik Elektro"],
        )
        self.assertTrue(all(fact["level"] == "D3" for fact in facts))

    def test_extract_faculty_units_prefers_official_list_section(self):
        from app.fact_extraction import extract_faculty_unit_facts_from_pages

        pages = [
            Document(
                page_content=(
                    "Pada 2023, UM membuka Fakultas Vokasi dan Fakultas Kedokteran. "
                    "Sepuluh fakultas tersebut adalah Fakultas Ilmu Pendidikan, "
                    "Fakultas Sastra, Fakultas Matematika dan Ilmu Pengetahuan Alam, "
                    "Fakultas Ekonomi dan Bisnis, Fakultas Teknik, Fakultas Ilmu "
                    "Keolahragaan, Fakultas Ilmu Sosial, Fakultas Psikologi, "
                    "Fakultas Vokasi, dan Fakultas Kedokteran. Selain fakultas "
                    "tersebut, UM memiliki Sekolah Pascasarjana."
                ),
                metadata={
                    "domain": "general_profile",
                    "file_name": "profil.pdf",
                    "page": 5,
                    "document_year": "general",
                    "topic": "institution_profile",
                },
            )
        ]

        facts = extract_faculty_unit_facts_from_pages(pages)
        names = [fact["faculty"] for fact in facts]

        self.assertEqual(
            names,
            [
                "Fakultas Ilmu Pendidikan",
                "Fakultas Sastra",
                "Fakultas Matematika dan Ilmu Pengetahuan Alam",
                "Fakultas Ekonomi dan Bisnis",
                "Fakultas Teknik",
                "Fakultas Ilmu Keolahragaan",
                "Fakultas Ilmu Sosial",
                "Fakultas Psikologi",
                "Fakultas Vokasi",
                "Fakultas Kedokteran",
            ],
        )


class StructuredFactAnswerTests(unittest.TestCase):
    def test_answer_from_facts_counts_latest_program_groups(self):
        facts = [
            {
                "fact_type": "program_study",
                "faculty": "Fakultas Teknik",
                "level": "S1",
                "program_name": "Teknik Mesin",
                "program_code": "NTMEUM6xxx",
                "file_name": "pedoman-2020.pdf",
                "page": 72,
                "domain": "academic_administration",
                "topic": "pedoman_pendidikan",
                "document_year": "2020",
            },
            {
                "fact_type": "program_study",
                "faculty": "Fakultas Teknik",
                "level": "S1",
                "program_name": "Teknik Sipil",
                "program_code": "NTSIUM6xxx",
                "file_name": "pedoman-2020.pdf",
                "page": 73,
                "domain": "academic_administration",
                "topic": "pedoman_pendidikan",
                "document_year": "2020",
            },
            {
                "fact_type": "program_study",
                "faculty": "Fakultas Teknik",
                "level": "D3",
                "program_name": "Tata Boga",
                "program_code": "NTBGUM53xx",
                "file_name": "pedoman-2020.pdf",
                "page": 69,
                "domain": "academic_administration",
                "topic": "pedoman_pendidikan",
                "document_year": "2020",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            fact_path = Path(tmpdir) / "facts.json"
            fact_path.write_text(json.dumps(facts), encoding="utf-8")
            with patch.object(
                fact_index,
                "settings",
                SimpleNamespace(structured_facts_path=fact_path),
            ):
                result = fact_index.answer_from_facts(
                    "ada berapa prodi di fakultas teknik?",
                    plan_query("ada berapa prodi di fakultas teknik?"),
                )

        self.assertIsNotNone(result)
        self.assertIn("2 program studi S1", result["answer"])
        self.assertIn("1 program studi D3", result["answer"])
        self.assertIn("totalnya 3 program studi", result["answer"])
        self.assertIn("Rinciannya:", result["answer"])
        self.assertIn("S1: Teknik Mesin, Teknik Sipil", result["answer"])
        self.assertIn("D3: Tata Boga", result["answer"])

    def test_answer_from_facts_answers_program_existence(self):
        facts = [
            {
                "fact_type": "program_study",
                "faculty": "Fakultas Teknik",
                "level": "S1",
                "program_name": "Teknik Informatika",
                "program_code": "NTIFUM6xxx",
                "file_name": "pedoman-2020.pdf",
                "page": 80,
                "domain": "academic_administration",
                "topic": "pedoman_pendidikan",
                "document_year": "2020",
            },
            {
                "fact_type": "program_study",
                "faculty": "Fakultas Teknik",
                "level": "S1",
                "program_name": "Teknik Mesin",
                "program_code": "NTMEUM6xxx",
                "file_name": "pedoman-2020.pdf",
                "page": 72,
                "domain": "academic_administration",
                "topic": "pedoman_pendidikan",
                "document_year": "2020",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            fact_path = Path(tmpdir) / "facts.json"
            fact_path.write_text(json.dumps(facts), encoding="utf-8")
            with patch.object(
                fact_index,
                "settings",
                SimpleNamespace(structured_facts_path=fact_path),
            ):
                result = fact_index.answer_from_facts(
                    "apakah ada teknik informatika di fakultas teknik um?",
                    plan_query("apakah ada teknik informatika di fakultas teknik um?"),
                )

        self.assertIsNotNone(result)
        self.assertEqual(
            result["answer"],
            "Ya, Fakultas Teknik memiliki program studi Teknik Informatika.",
        )
        self.assertEqual(result["match_count"], 1)
        self.assertEqual(result["sources"][0]["file_name"], "pedoman-2020.pdf")

    def test_answer_from_facts_counts_faculties_with_names(self):
        facts = [
            {
                "fact_type": "faculty_unit",
                "university": "Universitas Negeri Malang",
                "faculty": "Fakultas Ilmu Pendidikan",
                "additional_unit": "Sekolah Pascasarjana",
                "file_name": "profil.pdf",
                "page": 5,
                "domain": "general_profile",
                "topic": "institution_profile",
                "document_year": "general",
            },
            {
                "fact_type": "faculty_unit",
                "university": "Universitas Negeri Malang",
                "faculty": "Fakultas Teknik",
                "additional_unit": "Sekolah Pascasarjana",
                "file_name": "profil.pdf",
                "page": 5,
                "domain": "general_profile",
                "topic": "institution_profile",
                "document_year": "general",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            fact_path = Path(tmpdir) / "facts.json"
            fact_path.write_text(json.dumps(facts), encoding="utf-8")
            with patch.object(
                fact_index,
                "settings",
                SimpleNamespace(structured_facts_path=fact_path),
            ):
                result = fact_index.answer_from_facts(
                    "ada berapa fakultas di universitas negeri malang?",
                    plan_query("ada berapa fakultas di universitas negeri malang?"),
                )

        self.assertIsNotNone(result)
        self.assertIn("memiliki 2 fakultas", result["answer"])
        self.assertIn(
            "Fakultasnya adalah: Fakultas Ilmu Pendidikan, Fakultas Teknik",
            result["answer"],
        )
        self.assertIn("Sekolah Pascasarjana", result["answer"])

    def test_answer_from_facts_answers_institution_profile_fact(self):
        facts = [
            {
                "fact_type": "institution_fact",
                "fact_key": "rector",
                "value": "Prof. Dr. Hariyono, M.Pd.",
                "file_name": "profil-um.pdf",
                "page": 2,
                "domain": "general_profile",
                "topic": "institution_profile",
                "document_year": "general",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            fact_path = Path(tmpdir) / "facts.json"
            fact_path.write_text(json.dumps(facts), encoding="utf-8")
            with patch.object(
                fact_index,
                "settings",
                SimpleNamespace(structured_facts_path=fact_path),
            ):
                result = fact_index.answer_from_facts(
                    "siapa rektor universitas negeri malang?",
                    plan_query("siapa rektor universitas negeri malang?"),
                )

        self.assertIsNotNone(result)
        self.assertIn("Rektor Universitas Negeri Malang", result["answer"])
        self.assertIn("Prof. Dr. Hariyono, M.Pd.", result["answer"])
        self.assertEqual(result["sources"][0]["file_name"], "profil-um.pdf")

    def test_answer_from_facts_lists_general_facilities(self):
        facts = [
            {
                "fact_type": "general_facility",
                "facility_name": "Perpustakaan",
                "file_name": "profil-um.pdf",
                "page": 10,
                "domain": "general_profile",
                "topic": "general_facilities",
                "document_year": "general",
            },
            {
                "fact_type": "general_facility",
                "facility_name": "Asrama Mahasiswa",
                "file_name": "profil-um.pdf",
                "page": 10,
                "domain": "general_profile",
                "topic": "general_facilities",
                "document_year": "general",
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            fact_path = Path(tmpdir) / "facts.json"
            fact_path.write_text(json.dumps(facts), encoding="utf-8")
            with patch.object(
                fact_index,
                "settings",
                SimpleNamespace(structured_facts_path=fact_path),
            ):
                result = fact_index.answer_from_facts(
                    "apa saja sarana umum di UM?",
                    plan_query("apa saja sarana umum di UM?"),
                )

        self.assertIsNotNone(result)
        self.assertIn("2 sarana/fasilitas umum", result["answer"])
        self.assertIn("Perpustakaan", result["answer"])
        self.assertIn("Asrama Mahasiswa", result["answer"])
        self.assertEqual(result["contexts"][0]["doc"].metadata["chunk_index"], "structured_fact")

    def test_rag_answer_uses_structured_facts_before_retrieval(self):
        fact_context = {
            "doc": Document(
                page_content="Structured fact: Fakultas Teknik - S1",
                metadata={
                    "domain": "academic_administration",
                    "file_name": "pedoman.pdf",
                    "page": 72,
                    "chunk_index": "structured_fact",
                    "topic": "pedoman_pendidikan",
                },
            ),
            "distance": 0,
            "keyword_bonus": 1,
            "penalty": 0,
            "final_score": 99,
        }

        with (
            patch.object(
                main,
                "route_query_domain",
                return_value={
                    "domains": ["academic_administration", "general_profile"],
                    "reason": "test",
                    "query_plan": {
                        "intent": "aggregate_count",
                        "target": "program_study",
                        "entities": {"faculty": "Fakultas Teknik", "level": None},
                        "requires_structured_facts": True,
                    },
                },
            ),
            patch.object(
                main,
                "answer_from_facts",
                return_value={
                    "answer": "Fakultas Teknik memiliki 2 program studi S1.",
                    "sources": [
                        {
                            "file_name": "pedoman.pdf",
                            "domain": "academic_administration",
                            "pages": [72],
                            "chunks": [],
                            "topic": "pedoman_pendidikan",
                        }
                    ],
                    "contexts": [fact_context],
                    "match_count": 2,
                    "summary": {},
                },
            ),
            patch.object(main, "retrieve_with_fallback") as retrieve,
            patch.object(main, "generate_answer_from_context") as generate_answer,
        ):
            result = main.rag_answer("ada berapa prodi di fakultas teknik?")

        self.assertEqual(result["answer_status"], "answered")
        self.assertEqual(result["answer"], "Fakultas Teknik memiliki 2 program studi S1.")
        self.assertEqual(result["sources"][0]["url"], "/documents/academic_administration/pedoman.pdf")
        retrieve.assert_not_called()
        generate_answer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
