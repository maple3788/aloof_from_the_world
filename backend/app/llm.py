from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from app.config import EmbeddingProvider, LLMProvider, Settings, get_settings


class ChromaDefaultEmbeddings(Embeddings):
    """LangChain adapter over Chroma's bundled ONNX MiniLM embedding function.

    Zero-config local embeddings: no API key, no torch, no Ollama required.
    """

    def __init__(self) -> None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        self._fn = DefaultEmbeddingFunction()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, vec)) for vec in self._fn(texts)]

    def embed_query(self, text: str) -> list[float]:
        return list(map(float, self._fn([text])[0]))


def get_chat_model(settings: Settings | None = None, **overrides) -> BaseChatModel:
    settings = settings or get_settings()
    if settings.llm_provider == LLMProvider.OPENAI:
        from langchain_openai import ChatOpenAI

        extra = {"base_url": settings.openai_base_url} if settings.openai_base_url else {}
        return ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            **extra,
            **overrides,
        )
    if settings.llm_provider == LLMProvider.ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.anthropic_model, api_key=settings.anthropic_api_key, **overrides
        )
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.ollama_model, base_url=settings.ollama_base_url, **overrides
    )


def get_embeddings(settings: Settings | None = None) -> Embeddings:
    settings = settings or get_settings()
    if settings.embedding_provider == EmbeddingProvider.OPENAI:
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.openai_embedding_model, api_key=settings.openai_api_key
        )
    if settings.embedding_provider == EmbeddingProvider.OLLAMA:
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=settings.ollama_embedding_model, base_url=settings.ollama_base_url
        )
    return ChromaDefaultEmbeddings()
