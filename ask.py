"""Ask OptiBot a question from the terminal (Responses API + file_search).

The Assistants API was sunset on 2026-08-26, so the assistant is defined as a
system prompt + file_search over the vector store, exactly as the Playground does.
    python ask.py "How do I add a YouTube video?"
"""
from __future__ import annotations

import sys

from openai import OpenAI

from optibot.config import Settings

SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""


def main() -> int:
    question = " ".join(sys.argv[1:]) or "How do I add a YouTube video?"
    cfg = Settings.from_env()
    if not cfg.openai_api_key or not cfg.vector_store_id:
        print("set OPENAI_API_KEY and VECTOR_STORE_ID first", file=sys.stderr)
        return 2
    client = OpenAI(api_key=cfg.openai_api_key)
    resp = client.responses.create(
        model="gpt-4.1-mini",
        instructions=SYSTEM_PROMPT,
        input=question,
        tools=[{"type": "file_search", "vector_store_ids": [cfg.vector_store_id], "max_num_results": 6}],
        include=["file_search_call.results"],
    )
    print(resp.output_text)
    cited: list[str] = []
    for item in resp.output:
        if item.type == "file_search_call" and item.results:
            for r in item.results:
                url = (r.attributes or {}).get("source_url")
                if url and url not in cited:
                    cited.append(url)
    if cited:
        print("\nSources retrieved:")
        for u in cited[:3]:
            print(" -", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
