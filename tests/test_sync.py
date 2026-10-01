from optibot.markdown import MarkdownArticle
from optibot.store import RemoteFile
from optibot.sync import plan_sync


def art(i: int, h: str) -> MarkdownArticle:
    return MarkdownArticle(id=i, slug=f"a-{i}", title=f"A{i}", html_url=f"u{i}", content_hash=h, markdown="x")


def remote(i: int, h: str) -> RemoteFile:
    return RemoteFile(file_id=f"file_{i}", article_id=i, content_hash=h, slug=f"a-{i}")


def test_first_run_everything_is_added():
    plan = plan_sync([art(1, "h1"), art(2, "h2")], {})
    assert [a.id for a in plan.added] == [1, 2]
    assert plan.updated == plan.skipped == plan.removed == []


def test_second_run_unchanged_is_skipped():
    local = [art(1, "h1"), art(2, "h2")]
    plan = plan_sync(local, {1: remote(1, "h1"), 2: remote(2, "h2")})
    assert plan.added == plan.updated == plan.removed == []
    assert [a.id for a in plan.skipped] == [1, 2]


def test_changed_hash_is_updated_and_old_file_is_known():
    plan = plan_sync([art(1, "new")], {1: remote(1, "old")})
    assert len(plan.updated) == 1
    new, old = plan.updated[0]
    assert new.content_hash == "new" and old.file_id == "file_1"


def test_unpublished_article_is_removed():
    plan = plan_sync([art(1, "h1")], {1: remote(1, "h1"), 9: remote(9, "h9")})
    assert [r.article_id for r in plan.removed] == [9]
    assert len(plan.skipped) == 1


def test_mixed_delta_counts():
    local = [art(1, "same"), art(2, "changed"), art(3, "brand-new")]
    rem = {1: remote(1, "same"), 2: remote(2, "old"), 4: remote(4, "gone")}
    plan = plan_sync(local, rem)
    assert (len(plan.added), len(plan.updated), len(plan.skipped), len(plan.removed)) == (1, 1, 1, 1)
