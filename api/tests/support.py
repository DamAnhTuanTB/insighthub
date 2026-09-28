"""Test configuration never uses developer credentials or sends paid requests."""

import os
from contextlib import contextmanager
from unittest.mock import patch

os.environ.update(
    RAG_MODE="fixture",
    LLM_PROVIDER="fixture",
    EMBEDDING_PROVIDER="fixture",
    LLM_MODEL="",
    EMBEDDING_MODEL="",
    EMBEDDING_DIM="1024",
)
from app.core.config import get_settings

get_settings.cache_clear()


@contextmanager
def configured(**values):
    defaults = {
        "RAG_MODE": "fixture",
        "LLM_PROVIDER": "fixture",
        "EMBEDDING_PROVIDER": "fixture",
        "LLM_MODEL": "",
        "EMBEDDING_MODEL": "",
        "EMBEDDING_DIM": "1024",
        "GEMINI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "VOYAGE_API_KEY": "",
        "OPENAI_API_KEY": "",
        "LITELLM_API_KEY": "",
        "GEMINI_CHAT_MODEL": "",
        "ANTHROPIC_CHAT_MODEL": "",
        "OLLAMA_CHAT_MODEL": "",
        "OPENAI_CHAT_MODEL": "",
        "OPENAI_BASE_URL": "",
        "EMBEDDING_REVISION": "1",
        "CHUNK_SIZE": "800",
        "CHUNK_OVERLAP": "100",
    }
    defaults.update({key.upper(): str(value) for key, value in values.items()})
    with patch.dict(os.environ, defaults):
        get_settings.cache_clear()
        try:
            yield get_settings()
        finally:
            get_settings.cache_clear()


def real_config(provider="openai", **extra):
    values = {
        "rag_mode": "real",
        "llm_provider": provider,
        "embedding_provider": "openai",
        "openai_base_url": "https://gateway.example/v1",
        "openai_api_key": "test-secret",
        "llm_model": "test-chat-model",
    }
    values.update(extra)
    return configured(**values)
