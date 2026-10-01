import pytest

from optibot.chunking import chunks_for_tokens, count_chunks


@pytest.mark.parametrize(
    "tokens, expected",
    [(0, 1), (1, 1), (800, 1), (801, 2), (1200, 2), (1201, 3), (2000, 4), (4000, 9)],
)
def test_sliding_window_count(tokens, expected):
    assert chunks_for_tokens(tokens, 800, 400) == expected


def test_no_overlap_is_plain_division():
    assert chunks_for_tokens(1600, 800, 0) == 2
    assert chunks_for_tokens(1601, 800, 0) == 3


def test_overlap_must_be_smaller_than_window():
    with pytest.raises(ValueError):
        chunks_for_tokens(10, 100, 100)


def test_count_chunks_on_real_text():
    short = "How to add a YouTube video. " * 10
    long = "How to add a YouTube video. " * 1000
    assert count_chunks(short) == 1
    assert count_chunks(long) > 10


def test_gemini_adapter_counts_whitespace_tokens():
    from optibot.store_gemini import GeminiStoreClient

    store = GeminiStoreClient("test-key", 400, 80)
    assert store.count_chunks("word " * 1000) == chunks_for_tokens(1000, 400, 80)
    assert store.count_chunks("short text") == 1
