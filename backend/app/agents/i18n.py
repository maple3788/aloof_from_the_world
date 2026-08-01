"""Per-session conversation language: English (default) or Simplified Chinese."""

from langchain_core.language_models import BaseChatModel

SUPPORTED_LANGUAGES = {"en", "zh"}
DEFAULT_LANGUAGE = "en"

TRANSLATE_PROMPT = (
    "Translate the following text into English for semantic search over English "
    "philosophy, psychology, and history books. Reply with ONLY the translation, "
    "no explanations.\n\n{text}"
)


def normalize_language(language: str | None) -> str:
    return language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def language_directive(language: str) -> str:
    """Prompt snippet pinning the reply language; appended last for emphasis."""
    if language == "zh":
        return (
            "IMPORTANT — reply language: write your ENTIRE reply in Simplified Chinese "
            "(简体中文). When quoting the source passages, keep the quotation in the "
            "original English, then continue in Chinese. Never switch your reply to English."
        )
    return "Reply in English."


async def retrieval_query(llm: BaseChatModel, query: str, language: str) -> str:
    """The embedding model is English-centric, so Chinese queries are translated
    for retrieval only; the user's original message is used everywhere else."""
    if language != "zh":
        return query
    try:
        result = await llm.ainvoke(
            TRANSLATE_PROMPT.format(text=query), config={"tags": ["translate"]}
        )
        translated = str(result.content).strip()
    except Exception:
        return query
    return translated or query
