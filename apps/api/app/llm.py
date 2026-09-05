import random
import time
from typing import Any, Dict, Iterable, List, Optional

import requests

from app.config import settings
from app.structured_cache import LRUCache


RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
STRUCTURED_GENERATION_CACHE = LRUCache(settings.structured_cache_max_entries)


class GroqGenerationError(RuntimeError):
    pass


def _unique_models(models: Iterable[str]) -> List[str]:
    unique = []

    for model in models:
        clean_model = str(model).strip()
        if clean_model and clean_model not in unique:
            unique.append(clean_model)

    return unique


def get_model_chain(task: str, model: Optional[str] = None) -> List[str]:
    if model:
        return [model]

    chains = {
        "router": [
            settings.groq_router_model,
            settings.groq_router_fallback_model,
        ],
        "analyzer": [
            settings.groq_analyzer_model,
            settings.groq_analyzer_fallback_model,
        ],
        "answer": [
            settings.groq_answer_model,
            settings.groq_answer_fallback_model,
        ],
    }

    return _unique_models(chains.get(task, [settings.groq_answer_model]))


def is_retryable_error(error: Exception) -> bool:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)

    if status_code in RETRYABLE_STATUS_CODES:
        return True

    error_text = str(error).lower()
    retryable_keywords = [
        "timeout",
        "temporarily",
        "rate limit",
        "too many requests",
        "overloaded",
        "unavailable",
        "connection",
    ]

    return any(keyword in error_text for keyword in retryable_keywords)


def _extract_content(payload: Dict[str, Any], model: str) -> str:
    choices = payload.get("choices") or []

    if not choices:
        raise GroqGenerationError(f"Groq model {model} tidak mengembalikan choices.")

    message = choices[0].get("message") or {}
    content = message.get("content")

    if isinstance(content, str) and content.strip():
        return content

    raise GroqGenerationError(f"Groq model {model} tidak mengembalikan teks.")


def groq_generate_with_model(
    *,
    prompt: str,
    model: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    response_format: Optional[Dict[str, str]] = None,
) -> str:
    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY belum diset di file .env.")

    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})

    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    if response_format is not None:
        body["response_format"] = response_format

    response = requests.post(
        f"{settings.groq_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=settings.groq_timeout_seconds,
    )
    response.raise_for_status()

    return _extract_content(response.json(), model)


def groq_generate(
    prompt: str,
    *,
    task: str = "answer",
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    json_mode: bool = False,
) -> str:
    model_chain = get_model_chain(task, model)
    last_error: Optional[Exception] = None
    response_format = {"type": "json_object"} if json_mode else None

    for model_name in model_chain:
        for attempt in range(settings.groq_max_retries + 1):
            try:
                return groq_generate_with_model(
                    prompt=prompt,
                    model=model_name,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )
            except Exception as exc:
                last_error = exc

                if not is_retryable_error(exc):
                    break

                if attempt < settings.groq_max_retries:
                    wait_time = (2**attempt) + random.uniform(0, 0.5)
                    time.sleep(wait_time)

    raise GroqGenerationError(
        f"Seluruh model Groq gagal untuk task '{task}': {last_error}"
    )


def groq_generate_json(prompt: str, *, task: str = "analyzer") -> str:
    return groq_generate(
        prompt,
        task=task,
        json_mode=True,
        temperature=0.0,
    )


def groq_generate_json_cached(prompt: str, *, task: str = "analyzer") -> str:
    if not settings.structured_cache_enabled:
        return groq_generate_json(prompt, task=task)

    cache_key = (
        task,
        tuple(get_model_chain(task)),
        prompt,
    )
    cached = STRUCTURED_GENERATION_CACHE.get(cache_key)
    if cached is not None:
        return cached

    response = groq_generate_json(prompt, task=task)
    STRUCTURED_GENERATION_CACHE.set(cache_key, response)
    return response


def structured_cache_stats() -> Dict[str, Any]:
    return STRUCTURED_GENERATION_CACHE.stats()


def groq_generate_answer(prompt: str) -> str:
    return groq_generate(
        prompt,
        task="answer",
        temperature=0.0,
    )


def generate(prompt: str) -> str:
    return groq_generate_answer(prompt)
