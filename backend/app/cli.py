import argparse

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.graph import build_graph
from app.agents.personas import load_personas


def format_citations(citations: list[dict]) -> str:
    lines = []
    for c in citations:
        lines.append(f"    [{c['title']} — {c['author']}, chunk {c['chunk_index']}]")
    return "\n".join(lines)


async def chat_loop(mode: str, persona_ids: list[str], language: str = "en") -> None:
    graph = build_graph()
    personas = load_personas()
    history: list = []

    print("Aloof from the World — REPL (type 'exit' to quit, 'mode study|discuss' to switch)")
    if mode == "discuss":
        names = ", ".join(personas[pid].name for pid in persona_ids)
        print(f"Discuss mode with {names} (language: {language}).")
    else:
        print(f"Study mode with the Tutor (language: {language}).")

    while True:
        try:
            user_input = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break
        if user_input.lower().startswith("mode "):
            mode = "study" if "study" in user_input.lower() else "discuss"
            print(f"(mode switched to {mode})")
            continue

        history.append(HumanMessage(content=user_input))
        state = await graph.ainvoke(
            {
                "messages": history,
                "mode": mode,
                "language": language,
                "persona_ids": persona_ids,
            }
        )
        for resp in state.get("responses", []):
            print(f"\n{resp['responder_name']}> {resp['content']}")
            if resp.get("citations"):
                print(format_citations(resp["citations"]))
            if resp.get("critic_note"):
                print(f"    (moderator's note: {resp['critic_note']})")
            history.append(
                AIMessage(content=resp["content"], name=resp["responder"])
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat with the agents in your terminal")
    parser.add_argument("--mode", choices=["discuss", "study"], default="discuss")
    parser.add_argument("--personas", default="socrates",
                        help="Comma-separated persona ids (several = roundtable)")
    parser.add_argument("--language", choices=["en", "zh"], default="en")
    args = parser.parse_args()

    import asyncio

    asyncio.run(chat_loop(args.mode, args.personas.split(","), args.language))


if __name__ == "__main__":
    main()
