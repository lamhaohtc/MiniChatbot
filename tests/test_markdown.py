from optibot.markdown import content_hash, html_to_markdown, make_slug, render
from optibot.zendesk import RawArticle

BASE = "https://support.example.com"

HTML = """
<nav class="breadcrumbs"><a href="/hc">Home</a></nav>
<div class="promo-banner">Buy now!</div>
<h2>Step one</h2>
<p>Open the <a href="/hc/en-us/articles/123-Other">other article</a> and run:</p>
<pre><code class="language-bash">npm install\nnpm start</code></pre>
<ul><li>First</li><li>Second</li></ul>
<iframe src="https://www.youtube.com/embed/abc123"></iframe>
<img src="/hc/article_attachments/1/shot.png" alt="screenshot">
<script>track()</script>
"""


def test_strips_nav_and_ads_keeps_content():
    md = html_to_markdown(HTML, BASE)
    assert "Home" not in md
    assert "Buy now" not in md
    assert "track()" not in md
    assert "## Step one" in md
    assert "- First" in md and "- Second" in md


def test_relative_links_become_absolute():
    md = html_to_markdown(HTML, BASE)
    assert f"[other article]({BASE}/hc/en-us/articles/123-Other)" in md
    assert f"![screenshot]({BASE}/hc/article_attachments/1/shot.png)" in md


def test_code_block_fenced_with_language():
    md = html_to_markdown(HTML, BASE)
    assert "```bash\nnpm install\nnpm start\n```" in md


def test_embedded_video_becomes_link():
    md = html_to_markdown(HTML, BASE)
    assert "[Embedded video](https://www.youtube.com/embed/abc123)" in md


def test_inline_data_uri_images_are_dropped():
    blob = "data:image/png;base64," + "A" * 5000
    md = html_to_markdown(f'<p>Scan this:</p><img src="{blob}" alt="QR code"><img src="{blob}">', BASE)
    assert "base64" not in md
    assert "[image: QR code]" in md
    assert len(md) < 200


def test_crlf_and_nbsp_are_normalised():
    md = html_to_markdown("<p>line one\r\nstill one</p>\r\n<p>two&nbsp;words</p>", BASE)
    assert "\r" not in md
    assert "two words" in md
    assert html_to_markdown("<p>a</p>\r\n<p>b</p>", BASE) == html_to_markdown("<p>a</p>\n<p>b</p>", BASE)


def test_hash_ignores_metadata_but_not_content():
    assert content_hash("T", "body") == content_hash("T", "body")
    assert content_hash("T", "body") != content_hash("T", "body changed")


def test_render_front_matter_and_citation_line():
    art = RawArticle(
        id=42, title="How to add a YouTube video", body_html="<p>Hi</p>",
        html_url=f"{BASE}/hc/en-us/articles/42-How-to", section="Apps",
        updated_at="2026-01-01T00:00:00Z", edited_at="2026-01-01T00:00:00Z",
    )
    out = render(art, BASE)
    assert out.slug == "how-to-add-a-youtube-video-42"
    assert out.markdown.startswith("---\n")
    assert f"Article URL: {BASE}/hc/en-us/articles/42-How-to" in out.markdown
    assert "# How to add a YouTube video" in out.markdown
    assert out.content_hash in out.markdown


def test_slug_is_filesystem_safe():
    assert make_slug("Weird / Title: 100% ✓", 7) == "weird-title-100-7"
