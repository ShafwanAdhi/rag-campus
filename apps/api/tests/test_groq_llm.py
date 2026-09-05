import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app.llm as llm
from app.structured_cache import LRUCache


class FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"domains":["academic_administration"]}',
                    },
                },
            ],
        }


class GroqLlmTests(unittest.TestCase):
    def fake_settings(self, *, cache_enabled=True):
        return SimpleNamespace(
            groq_api_key="test-key",
            groq_base_url="https://api.groq.com/openai/v1",
            groq_router_model="groq/compound-mini",
            groq_router_fallback_model="openai/gpt-oss-20b",
            groq_analyzer_model="groq/compound-mini",
            groq_analyzer_fallback_model="qwen/qwen3.8-27b",
            groq_answer_model="groq/compound",
            groq_answer_fallback_model="groq/compound-mini",
            groq_timeout_seconds=60,
            groq_max_retries=0,
            structured_cache_enabled=cache_enabled,
            structured_cache_max_entries=4,
        )

    def test_json_generation_uses_groq_chat_completions(self):
        with (
            patch.object(llm, "settings", self.fake_settings()),
            patch.object(llm.requests, "post", return_value=FakeResponse()) as post,
        ):
            result = llm.groq_generate_json("Return JSON.", task="router")

        self.assertEqual(result, '{"domains":["academic_administration"]}')
        post.assert_called_once()

        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs

        self.assertEqual(
            url,
            "https://api.groq.com/openai/v1/chat/completions",
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["json"]["model"], "groq/compound-mini")
        self.assertEqual(kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertEqual(kwargs["timeout"], 60)

    def test_cached_json_generation_reuses_router_result(self):
        with (
            patch.object(llm, "settings", self.fake_settings(cache_enabled=True)),
            patch.object(llm, "STRUCTURED_GENERATION_CACHE", LRUCache(4)),
            patch.object(
                llm,
                "groq_generate_json",
                return_value='{"domains":["academic_administration"]}',
            ) as generate_json,
        ):
            first = llm.groq_generate_json_cached("Return JSON.", task="router")
            second = llm.groq_generate_json_cached("Return JSON.", task="router")

        self.assertEqual(first, second)
        generate_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
