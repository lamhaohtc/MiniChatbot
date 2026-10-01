"""Orchestration test with a fake store: verifies delete-before-upload, counts, and failure handling."""
from optibot.markdown import MarkdownArticle
from optibot.store import RemoteFile
from optibot.sync import apply_plan, plan_sync


class FakeStore:
    def __init__(self, fail_slugs=()):
        self.calls: list[tuple[str, str]] = []
        self.fail_slugs = set(fail_slugs)

    def delete(self, store_id, file_id):
        self.calls.append(("delete", file_id))

    def upload(self, store_id, art):
        if art.slug in self.fail_slugs:
            raise RuntimeError("boom")
        self.calls.append(("upload", art.slug))
        return f"file_{art.id}", 3  # 3 chunks each


def art(i, h):
    return MarkdownArticle(id=i, slug=f"a-{i}", title=f"A{i}", html_url=f"u{i}", content_hash=h, markdown="x")


def test_apply_plan_counts_and_ordering():
    local = [art(1, "same"), art(2, "changed"), art(3, "new")]
    remote = {1: RemoteFile("f1", 1, "same", "a-1"), 2: RemoteFile("f2", 2, "old", "a-2"), 4: RemoteFile("f4", 4, "x", "a-4")}
    store = FakeStore()
    res = apply_plan(store, "vs", plan_sync(local, remote), concurrency=1)

    assert (res.added, res.updated, res.skipped, res.removed) == (1, 1, 1, 1)
    assert res.files_embedded == 2 and res.chunks_embedded == 6 and res.failed == 0
    # Removed article and stale copy of the updated one are deleted before any upload.
    deletes = [c for c in store.calls if c[0] == "delete"]
    first_upload = next(i for i, c in enumerate(store.calls) if c[0] == "upload")
    assert {c[1] for c in deletes} == {"f4", "f2"}
    assert all(store.calls.index(d) < first_upload for d in deletes)


def test_apply_plan_reports_failures_without_aborting():
    local = [art(1, "h"), art(2, "h")]
    store = FakeStore(fail_slugs={"a-1"})
    res = apply_plan(store, "vs", plan_sync(local, {}), concurrency=2)
    assert res.added == 2 and res.files_embedded == 1 and res.failed == 1
