"""Ask OptiBot a question from the terminal, grounded only in the uploaded docs.

Gemini: generate_content with the file_search tool over the File Search store.
OpenAI: Responses API with file_search over the vector store (the Assistants API
was sunset on 2026-08-26; this is its replacement).
    python ask.py "How do I add a YouTube video?"
"""
from __future__ import annotations

import re
import sys

from optibot.config import Settings

SYSTEM_PROMPT = """You are OptiBot, the customer-support bot for OptiSigns.com.
• Tone: helpful, factual, concise.
• Only answer using the uploaded docs.
• Max 5 bullet points; else link to the doc.
• Cite up to 3 "Article URL:" lines per reply."""

_URL_RE = re.compile(r"Article URL:\s*(\S+)")


def ask_gemini(cfg: Settings, question: str) -> tuple[str, list[str]]:
    from google.genai import Client, types

    from google.genai.errors import APIError

    client = Client(api_key=cfg.gemini_api_key)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(file_search=types.FileSearch(file_search_store_names=[cfg.vector_store_id]))],
    )
    models = [m.strip() for m in cfg.gemini_model.split(",") if m.strip()]
    resp = None
    for i, model in enumerate(models):
        try:
            resp = client.models.generate_content(model=model, contents=question, config=config)
            break
        except APIError as exc:  # 503 = high demand, 404 = model retired for this account
            if exc.code not in (503, 404) or i == len(models) - 1:
                raise
            print(f"[{model} unavailable ({exc.code}), trying {models[i + 1]}]", file=sys.stderr)
    cited: list[str] = []
    gm = resp.candidates[0].grounding_metadata if resp.candidates else None
    for ch in (gm.grounding_chunks if gm and gm.grounding_chunks else []):
        rc = ch.retrieved_context
        if not rc:
            continue
        url = next((m.string_value for m in (rc.custom_metadata or []) if m.key == "source_url"), None)
        if not url and rc.text:
            m = _URL_RE.search(rc.text)
            url = m.group(1) if m else None
        if url and url not in cited:
            cited.append(url)
    return resp.text or "", cited


def ask_openai(cfg: Settings, question: str) -> tuple[str, list[str]]:
    from openai import OpenAI

    client = OpenAI(api_key=cfg.openai_api_key)
    resp = client.responses.create(
        model=cfg.openai_model,
        instructions=SYSTEM_PROMPT,
        input=question,
        tools=[{"type": "file_search", "vector_store_ids": [cfg.vector_store_id], "max_num_results": 6}],
        include=["file_search_call.results"],
    )
    cited: list[str] = []
    for item in resp.output:
        if item.type == "file_search_call" and item.results:
            for r in item.results:
                url = (r.attributes or {}).get("source_url")
                if url and url not in cited:
                    cited.append(url)
    return resp.output_text, cited


def main() -> int:
    question = " ".join(sys.argv[1:]) or "How do I add a YouTube video?"
    cfg = Settings.from_env()
    if not cfg.api_key or not cfg.vector_store_id:
        print(f"set {cfg.api_key_var} and VECTOR_STORE_ID first", file=sys.stderr)
        return 2
    answer, cited = (ask_gemini if cfg.provider == "gemini" else ask_openai)(cfg, question)
    print(answer.strip())
    if cited:
        print("\nSources retrieved:")
        for u in cited[:3]:
            print(" -", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
