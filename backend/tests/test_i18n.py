from types import SimpleNamespace

from app.agents.i18n import language_directive, normalize_language, retrieval_query


class RecordingLLM:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[str] = []

    async def ainvoke(self, prompt, config=None):
        self.calls.append(str(prompt))
        return SimpleNamespace(content=self.responses[len(self.calls) - 1])


class FailingLLM:
    async def ainvoke(self, prompt, config=None):
        raise RuntimeError("llm unavailable")


def test_normalize_language_defaults_and_passes_through():
    assert normalize_language(None) == "en"
    assert normalize_language("fr") == "en"
    assert normalize_language("zh") == "zh"
    assert normalize_language("en") == "en"


def test_language_directive_pins_chinese():
    assert "简体中文" in language_directive("zh")
    assert language_directive("en") == "Reply in English."


async def test_retrieval_query_english_short_circuits():
    llm = RecordingLLM(["unused"])
    assert await retrieval_query(llm, "What is virtue?", "en") == "What is virtue?"
    assert llm.calls == []  # no LLM call wasted for English


async def test_retrieval_query_chinese_is_translated():
    llm = RecordingLLM(["What is virtue?"])
    assert await retrieval_query(llm, "什么是美德？", "zh") == "What is virtue?"
    assert "什么是美德？" in llm.calls[0]


async def test_retrieval_query_falls_back_on_failure():
    assert await retrieval_query(FailingLLM(), "什么是美德？", "zh") == "什么是美德？"
