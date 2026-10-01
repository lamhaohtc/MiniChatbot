"""Local replica of OpenAI's `static` chunking strategy, used only to count chunks.

The vector-store API exposes a file's parsed text but not its chunk boundaries,
so the number of chunks embedded is computed here with the same sliding window:
windows of `max_tokens` advancing by `max_tokens - overlap_tokens`.
Token counts use cl100k_base, the tokenizer of the text-embedding-3 models.
"""
from __future__ import annotations

import math
from functools import lru_cache


@lru_cache(maxsize=1)
def _encoder():
    import tiktoken  # imported lazily: downloads its BPE table on first use

    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text, disallowed_special=()))


def count_chunks(text: str, max_tokens: int = 800, overlap_tokens: int = 400) -> int:
    """Number of sliding-window chunks for `text`."""
    return chunks_for_tokens(count_tokens(text), max_tokens, overlap_tokens)


def chunks_for_tokens(n_tokens: int, max_tokens: int, overlap_tokens: int) -> int:
    if overlap_tokens >= max_tokens:
        raise ValueError("overlap must be smaller than the chunk size")
    if n_tokens <= max_tokens:
        return 1
    step = max_tokens - overlap_tokens
    return math.ceil((n_tokens - max_tokens) / step) + 1
