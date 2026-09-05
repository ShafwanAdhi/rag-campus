from __future__ import annotations

import time
from collections import OrderedDict
from typing import List, Optional

import requests
from langchain_core.embeddings import Embeddings

from app.config import settings


class VoyageEmbeddings(Embeddings):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int,
        batch_size: int,
        min_request_interval_seconds: float,
        max_retries: int,
        query_cache_max_entries: int = 256,
    ) -> None:
        if not api_key:
            raise RuntimeError(
                "VOYAGE_API_KEY is required when EMBEDDING_PROVIDER=voyage."
            )

        self.api_key = api_key
        self.model = model
        self.endpoint = f"{base_url.rstrip('/')}/embeddings"
        self.timeout_seconds = timeout_seconds
        self.batch_size = max(batch_size, 1)
        self.min_request_interval_seconds = max(min_request_interval_seconds, 0)
        self.max_retries = max(max_retries, 0)
        self.query_cache_max_entries = max(query_cache_max_entries, 0)
        self._query_cache: OrderedDict[str, List[float]] = OrderedDict()
        self._last_request_at = 0.0
        self.session = requests.Session()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        clean_texts = [text or "" for text in texts]
        embeddings: List[List[float]] = []

        for start in range(0, len(clean_texts), self.batch_size):
            batch = clean_texts[start : start + self.batch_size]
            embeddings.extend(self._embed(batch, input_type="document"))

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        clean_text = text or ""
        cached = self._query_cache.get(clean_text)
        if cached is not None:
            self._query_cache.move_to_end(clean_text)
            return list(cached)

        embedding = self._embed([clean_text], input_type="query")[0]
        if self.query_cache_max_entries > 0:
            self._query_cache[clean_text] = list(embedding)
            self._query_cache.move_to_end(clean_text)
            while len(self._query_cache) > self.query_cache_max_entries:
                self._query_cache.popitem(last=False)

        return embedding

    def _embed(self, texts: List[str], *, input_type: str) -> List[List[float]]:
        response = None
        for attempt in range(self.max_retries + 1):
            self._wait_for_rate_limit()
            response = self.session.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": texts,
                    "model": self.model,
                    "input_type": input_type,
                },
                timeout=self.timeout_seconds,
            )
            self._last_request_at = time.monotonic()

            if response.status_code != 429:
                break

            if attempt >= self.max_retries:
                break

            time.sleep(self._retry_delay(response, attempt))

        if response is None:
            raise RuntimeError("Voyage embedding request was not sent.")

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(
                f"Voyage embedding request failed with HTTP {response.status_code}: "
                f"{response.text[:500]}"
            ) from exc

        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, list):
            raise RuntimeError("Voyage embedding response did not contain a data list.")

        ordered_data = sorted(
            data,
            key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0,
        )
        embeddings = [
            item.get("embedding")
            for item in ordered_data
            if isinstance(item, dict) and isinstance(item.get("embedding"), list)
        ]

        if len(embeddings) != len(texts):
            raise RuntimeError(
                "Voyage embedding response count did not match requested input count."
            )

        return embeddings

    def _wait_for_rate_limit(self) -> None:
        if self.min_request_interval_seconds <= 0:
            return

        elapsed = time.monotonic() - self._last_request_at
        remaining = self.min_request_interval_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _retry_delay(self, response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(float(retry_after), self.min_request_interval_seconds)
            except ValueError:
                pass

        return max(self.min_request_interval_seconds, min(60.0, 2.0**attempt))


_embeddings: Optional[Embeddings] = None


def build_embeddings() -> Embeddings:
    provider = settings.embedding_provider.lower()

    if provider == "voyage":
        return VoyageEmbeddings(
            api_key=settings.voyage_api_key,
            model=settings.embedding_model,
            base_url=settings.voyage_base_url,
            timeout_seconds=settings.embedding_timeout_seconds,
            batch_size=settings.embedding_batch_size,
            min_request_interval_seconds=settings.embedding_min_request_interval_seconds,
            max_retries=settings.embedding_max_retries,
        )

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=settings.ollama_embedding_model,
            client_kwargs={"timeout": settings.ollama_embedding_timeout_seconds},
        )

    raise RuntimeError(
        f"Unsupported EMBEDDING_PROVIDER={settings.embedding_provider!r}. "
        "Use 'voyage' or 'ollama'."
    )


def get_embeddings() -> Embeddings:
    global _embeddings

    if _embeddings is None:
        _embeddings = build_embeddings()

    return _embeddings
