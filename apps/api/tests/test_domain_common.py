import unittest
from unittest.mock import patch

from app.domains.common import (
    DomainAnalyzerConfig,
    analyze_query_with_config,
    build_filter_from_config,
    clean_keywords,
)
from app.domains import academic_administration
from app.domains import facilities_and_campus_services
from app.domains import general_profile
from app.domains import thesis_final_project_and_graduation
from app.router import route_query_domain


class DomainCommonTests(unittest.TestCase):
    def test_clean_keywords_removes_campus_boilerplate(self):
        self.assertEqual(
            clean_keywords([
                "Universitas Negeri Malang",
                "cuti kuliah",
                "UM",
                "mengajukan",
                "SKCK",
            ]),
            ["cuti kuliah", "SKCK"],
        )

    def test_analyze_query_with_config_cleans_invalid_values(self):
        config = DomainAnalyzerConfig(
            domain="test_domain",
            valid_query_intents={"general_info", "procedure"},
            valid_metadata_values={
                "document_type": {"guide"},
                "topic": {"valid_topic"},
            },
            metadata_filter_fields=("document_type", "topic"),
        )

        with patch(
            "app.domains.common.groq_generate_json_cached",
            return_value=(
                '{"query_intent":"made_up","metadata_filters":'
                '{"document_type":"guide","topic":"invalid_topic"},'
                '"rerank_keywords":[" alpha ","alpha","beta"],"reason":"test"}'
            ),
        ):
            result = analyze_query_with_config(
                user_query="test",
                prompt="prompt",
                config=config,
            )

        self.assertEqual(result["query_intent"], "general_info")
        self.assertEqual(result["metadata_filters"], {"document_type": "guide"})
        self.assertEqual(result["rerank_keywords"], ["alpha", "beta"])

    def test_academic_leave_query_uses_domain_only_filter_and_specific_keywords(self):
        with patch(
            "app.domains.common.groq_generate_json_cached",
            return_value=(
                '{"query_intent":"rule_policy","metadata_filters":'
                '{"document_type":"academic_guide","academic_year":"general",'
                '"topic":"administrasi_akademik"},'
                '"rerank_keywords":["Universitas Negeri Malang","mengajukan"],'
                '"reason":"test"}'
            ),
        ):
            result = academic_administration.analyze_query(
                "Bagaimana cara mengajukan cuti kuliah di Universitas Negeri Malang?"
            )

        self.assertEqual(result["query_intent"], "procedure")
        self.assertEqual(result["metadata_filters"], {})
        self.assertEqual(
            academic_administration.build_filter(result),
            {"domain": "academic_administration"},
        )
        self.assertIn("tata cara permohonan cuti kuliah", result["rerank_keywords"])
        self.assertIn("Subbag Registrasi dan Statistik", result["rerank_keywords"])
        self.assertNotIn("Universitas Negeri Malang", result["rerank_keywords"])
        self.assertNotIn("mengajukan", result["rerank_keywords"])

    def test_build_filter_uses_default_light_fields(self):
        config = DomainAnalyzerConfig(
            domain="test_domain",
            valid_query_intents={"general_info"},
            valid_metadata_values={
                "document_type": {"guide"},
                "topic": {"valid_topic"},
            },
            metadata_filter_fields=("document_type", "topic"),
            default_metadata_filter_fields=("topic",),
        )
        analysis = {
            "metadata_filters": {
                "document_type": "guide",
                "topic": "valid_topic",
            }
        }

        self.assertEqual(
            build_filter_from_config(analysis=analysis, config=config),
            {"$and": [{"domain": "test_domain"}, {"topic": "valid_topic"}]},
        )
        self.assertEqual(
            build_filter_from_config(analysis=analysis, config=config, strict=True),
            {
                "$and": [
                    {"domain": "test_domain"},
                    {"document_type": "guide"},
                    {"topic": "valid_topic"},
                ]
            },
        )

    def test_general_institution_query_routes_to_single_general_profile_domain(self):
        with patch("app.router.groq_generate_json_cached") as generate_json:
            result = route_query_domain("Apa itu Universitas Negeri Malang?")

        self.assertEqual(result["domains"], ["general_profile"])
        generate_json.assert_not_called()

    def test_institution_faculty_count_query_routes_to_general_profile_domain(self):
        with patch("app.router.groq_generate_json_cached") as generate_json:
            result = route_query_domain("Berapa jumlah fakultas di Universitas Negeri Malang?")

        self.assertEqual(result["domains"], ["general_profile", "academic_administration"])
        self.assertEqual(result["query_plan"]["intent"], "aggregate_count")
        self.assertEqual(result["query_plan"]["target"], "faculty")
        generate_json.assert_not_called()

    def test_program_study_count_query_routes_to_structured_fact_domains(self):
        with patch("app.router.groq_generate_json_cached") as generate_json:
            result = route_query_domain("Ada berapa prodi di Fakultas Teknik?")

        self.assertEqual(
            result["domains"],
            [
                "academic_administration",
                "general_profile",
                "finance_tuition_and_scholarship",
            ],
        )
        self.assertEqual(result["query_plan"]["intent"], "aggregate_count")
        self.assertIsNone(result["query_plan"]["entities"]["program_name"])
        self.assertEqual(
            result["query_plan"]["entities"]["faculty"],
            "Fakultas Teknik",
        )
        generate_json.assert_not_called()

    def test_program_existence_query_with_um_routes_to_structured_fact_domains(self):
        with patch("app.router.groq_generate_json_cached") as generate_json:
            result = route_query_domain("Apakah ada teknik informatika di fakultas teknik UM?")

        self.assertEqual(
            result["domains"],
            ["academic_administration", "general_profile"],
        )
        self.assertEqual(result["query_plan"]["intent"], "existence_lookup")
        self.assertEqual(result["query_plan"]["target"], "program_study")
        self.assertEqual(result["query_plan"]["entities"]["program_name"], "Teknik Informatika")
        self.assertEqual(result["query_plan"]["entities"]["faculty"], "Fakultas Teknik")
        generate_json.assert_not_called()

    def test_institution_location_query_routes_to_single_general_profile_domain(self):
        with patch("app.router.groq_generate_json_cached") as generate_json:
            result = route_query_domain("Di kota apa Universitas Malang berlokasi?")

        self.assertEqual(result["domains"], ["general_profile"])
        generate_json.assert_not_called()

    def test_developer_profile_query_routes_to_single_general_profile_domain(self):
        with patch("app.router.groq_generate_json_cached") as generate_json:
            result = route_query_domain("Siapa pengembang sistem ini?")

        self.assertEqual(result["domains"], ["general_profile"])
        generate_json.assert_not_called()

    def test_thesis_guidance_query_does_not_route_to_finance_from_bi_substring(self):
        with patch("app.router.groq_generate_json_cached") as generate_json:
            result = route_query_domain("Bagaimana prosedur pembimbingan skripsi?")

        self.assertEqual(result["domains"], ["thesis_final_project_and_graduation"])
        generate_json.assert_not_called()

    def test_thesis_guidance_card_query_routes_only_to_thesis_domain(self):
        with patch("app.router.groq_generate_json_cached") as generate_json:
            result = route_query_domain("Apa fungsi kartu bimbingan skripsi?")

        self.assertEqual(result["domains"], ["thesis_final_project_and_graduation"])
        generate_json.assert_not_called()

    def test_registration_query_routes_to_finance_domain(self):
        with patch("app.router.groq_generate_json_cached") as generate_json:
            result = route_query_domain("Apa informasi registrasi mahasiswa baru jalur UTBK SNBT 2024?")

        self.assertEqual(result["domains"], ["finance_tuition_and_scholarship"])
        generate_json.assert_not_called()

    def test_general_facility_query_routes_to_facilities_and_general_profile(self):
        with patch("app.router.groq_generate_json_cached") as generate_json:
            result = route_query_domain("Apa saja sarana umum di UM?")

        self.assertEqual(result["domains"], ["facilities_and_campus_services", "general_profile"])
        self.assertEqual(result["query_plan"]["target"], "general_facility")
        generate_json.assert_not_called()

    def test_facilities_analyzer_falls_back_when_groq_fails(self):
        with patch(
            "app.domains.common.groq_generate_json_cached",
            side_effect=RuntimeError("429 rate limit"),
        ):
            result = facilities_and_campus_services.analyze_query(
                "Bagaimana prosedur penggunaan studio musik?"
            )

        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["metadata_filters"]["topic"], "music_studio")
        self.assertIn("studio musik", result["rerank_keywords"])

    def test_thesis_analyzer_falls_back_when_groq_fails(self):
        with patch(
            "app.domains.common.groq_generate_json_cached",
            side_effect=RuntimeError("429 rate limit"),
        ):
            result = thesis_final_project_and_graduation.analyze_query(
                "Apa fungsi kartu bimbingan skripsi?"
            )

        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["metadata_filters"]["topic"], "thesis_guidance_card")
        self.assertIn("kartu bimbingan skripsi", result["rerank_keywords"])

    def test_general_profile_enriches_faculty_count_keywords(self):
        keywords = general_profile.enrich_rerank_keywords(
            "Berapa jumlah fakultas di Universitas Negeri Malang?",
            [],
        )

        self.assertIn("jumlah fakultas", keywords)
        self.assertIn("sepuluh fakultas", keywords)
        self.assertIn("satu Sekolah Pascasarjana", keywords)


if __name__ == "__main__":
    unittest.main()
