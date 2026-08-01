from app.agents.personas import get_persona, load_personas


def test_starter_personas_load():
    personas = load_personas()
    assert {"socrates", "nietzsche", "freud", "confucius"} <= set(personas)


def test_persona_cards_have_voice_and_corpus_scope():
    for card in load_personas().values():
        assert card.voice and card.worldview
        assert card.style_rules
        assert card.authors or card.traditions


def test_system_prompt_includes_context_and_rules():
    socrates = get_persona("socrates")
    prompt = socrates.system_prompt("[1] The Republic — Plato:\nVirtue is knowledge.")
    assert "You are Socrates" in prompt
    assert "The Republic" in prompt
    assert "elenchus" in prompt


def test_roundtable_prompt_names_other_speakers():
    freud = get_persona("freud")
    prompt = freud.system_prompt("(none)", other_speakers=["Socrates"])
    assert "Socrates" in prompt


def test_system_prompt_appends_language_directive():
    socrates = get_persona("socrates")
    assert "简体中文" in socrates.system_prompt("(none)", language="zh")
    assert "Reply in English." in socrates.system_prompt("(none)", language="en")


def test_persona_cards_have_bilingual_greetings():
    for card in load_personas().values():
        assert card.greeting_zh, f"{card.id} is missing greeting_zh"
