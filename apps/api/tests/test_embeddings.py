import unittest
from unittest.mock import patch

from app.embeddings import VoyageEmbeddings


class FakeVoyageResponse:
    status_code = 200
    text = ""

    def __init__(self, data=None):
        self.data = data or [
            {"index": 1, "embedding": [0.3, 0.4]},
            {"index": 0, "embedding": [0.1, 0.2]},
        ]

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": self.data}


class VoyageEmbeddingsTests(unittest.TestCase):
    def make_embeddings(self) -> VoyageEmbeddings:
        return VoyageEmbeddings(
            api_key="test-voyage-key",
            model="voyage-multilingual-2",
            base_url="https://api.voyageai.com/v1",
            timeout_seconds=60,
            batch_size=64,
            min_request_interval_seconds=0,
            max_retries=0,
        )

    def test_embed_documents_uses_voyage_document_input_type(self):
        embeddings = self.make_embeddings()

        with patch.object(
            embeddings.session,
            "post",
            return_value=FakeVoyageResponse(),
        ) as post:
            result = embeddings.embed_documents(["dokumen satu", "dokumen dua"])

        self.assertEqual(result, [[0.1, 0.2], [0.3, 0.4]])
        post.assert_called_once()
        kwargs = post.call_args.kwargs
        self.assertEqual(
            post.call_args.args[0],
            "https://api.voyageai.com/v1/embeddings",
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-voyage-key")
        self.assertEqual(kwargs["json"]["model"], "voyage-multilingual-2")
        self.assertEqual(kwargs["json"]["input_type"], "document")
        self.assertEqual(kwargs["json"]["input"], ["dokumen satu", "dokumen dua"])

    def test_embed_query_uses_voyage_query_input_type(self):
        embeddings = self.make_embeddings()

        with patch.object(
            embeddings.session,
            "post",
            return_value=FakeVoyageResponse(
                [{"index": 0, "embedding": [0.1, 0.2]}]
            ),
        ) as post:
            result = embeddings.embed_query("cara cuti kuliah")

        self.assertEqual(result, [0.1, 0.2])
        self.assertEqual(post.call_args.kwargs["json"]["input_type"], "query")
        self.assertEqual(post.call_args.kwargs["json"]["input"], ["cara cuti kuliah"])

    def test_embed_query_reuses_cached_embedding_for_same_text(self):
        embeddings = self.make_embeddings()

        with patch.object(
            embeddings.session,
            "post",
            return_value=FakeVoyageResponse(
                [{"index": 0, "embedding": [0.1, 0.2]}]
            ),
        ) as post:
            first = embeddings.embed_query("apa itu universitas negeri malang?")
            second = embeddings.embed_query("apa itu universitas negeri malang?")

        self.assertEqual(first, second)
        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
