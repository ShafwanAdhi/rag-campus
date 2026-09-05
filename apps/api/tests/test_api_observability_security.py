import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

import main
from app import config


class ApiObservabilitySecurityTests(unittest.TestCase):
    def test_security_headers_are_present(self):
        response = TestClient(main.app).get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(
            response.headers["Referrer-Policy"],
            "strict-origin-when-cross-origin",
        )

    def test_hsts_is_enabled_in_production_mode(self):
        with patch.object(main, "settings", SimpleNamespace(app_env="production")):
            response = TestClient(main.app).get("/health")

        self.assertEqual(
            response.headers["Strict-Transport-Security"],
            "max-age=31536000; includeSubDomains",
        )

    def test_structured_sources_are_grouped_outside_answer_text(self):
        reranked_results = [
            {
                "doc": Document(
                    page_content="Konten fasilitas.",
                    metadata={
                        "file_name": "fasilitas.pdf",
                        "page": 1,
                        "chunk_index": 0,
                        "domain": "facilities_and_campus_services",
                        "topic": "library",
                    },
                ),
            },
            {
                "doc": Document(
                    page_content="Konten fasilitas lanjutan.",
                    metadata={
                        "file_name": "fasilitas.pdf",
                        "page": 1,
                        "chunk_index": 1,
                        "domain": "facilities_and_campus_services",
                        "topic": "library",
                    },
                ),
            },
        ]

        sources = main.build_structured_sources(reranked_results, top_k=2)

        self.assertEqual(
            sources,
            [
                {
                    "file_name": "fasilitas.pdf",
                    "url": "/documents/facilities_and_campus_services/fasilitas.pdf",
                    "pages": [1],
                    "chunks": [0, 1],
                    "domain": "facilities_and_campus_services",
                    "topic": "library",
                }
            ],
        )

    def test_document_pdf_endpoint_serves_local_pdf(self):
        response = TestClient(main.app).get(
            "/documents/academic_administration/Kalender-Akademik-2026-2027.pdf"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")

    def test_document_pdf_endpoint_blocks_path_traversal(self):
        response = TestClient(main.app).get(
            "/documents/academic_administration/..%2F..%2F.env"
        )

        self.assertIn(response.status_code, {400, 404})


class ConfigCorsTests(unittest.TestCase):
    def test_production_cors_is_explicit_and_does_not_use_dev_regex(self):
        env = {
            "APP_ENV": "production",
            "FRONTEND_ORIGINS": "*,https://sisdas.example.edu,http://localhost:3000",
        }

        with patch.object(config, "load_dotenv"), patch.dict(os.environ, env, clear=True):
            settings = config.build_settings()

        self.assertEqual(settings.app_env, "production")
        self.assertEqual(settings.frontend_origins, ("https://sisdas.example.edu",))
        self.assertIsNone(settings.cors_allow_origin_regex)

    def test_development_cors_keeps_localhost_defaults(self):
        with (
            patch.object(config, "load_dotenv"),
            patch.dict(os.environ, {"APP_ENV": "development"}, clear=True),
        ):
            settings = config.build_settings()

        self.assertIn("http://localhost:5173", settings.frontend_origins)
        self.assertIsNotNone(settings.cors_allow_origin_regex)


if __name__ == "__main__":
    unittest.main()
