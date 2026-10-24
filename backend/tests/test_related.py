"""对照's recommendations: the platform's related videos, closest in title first, this one left out."""
from fastapi.testclient import TestClient

from modules.video_source.base import Resolver
from tests.test_replay import job_for


def test_related_are_ranked_by_shared_words_and_say_which_are_imported(tmp_path, monkeypatch):
    import app

    job = job_for(tmp_path)
    job.video.title = "VLOOKUP函数使用方法详解"

    class Bili(Resolver):
        async def related(self, video):
            item = lambda bv, title, views: {"url": f"https://www.bilibili.com/video/{bv}/", "title": title, "author": "u",  # noqa: E731
                                             "duration": 60, "views": views, "cover": ""}
            return [item("BVa", "数据透视表入门", 9_000_000), item("BVb", "VLOOKUP函数的三种用法", 10),
                    item(video.video_id, "VLOOKUP函数使用方法详解", 1)]

    job.resolver = Bili()
    monkeypatch.setitem(app.jobs, "job1", job)
    monkeypatch.setattr(app.store, "list", lambda limit, owner=None: [{"video_id": "BVa"}])
    got = TestClient(app.app).get("/api/link-jobs/job1/related").json()
    assert [(i["title"], i["imported"]) for i in got["items"]] == [("VLOOKUP函数的三种用法", False), ("数据透视表入门", True)]


def test_a_platform_without_recommendations_says_so(tmp_path, monkeypatch):
    import app

    job = job_for(tmp_path)
    job.resolver = Resolver()
    monkeypatch.setitem(app.jobs, "job1", job)
    assert TestClient(app.app).get("/api/link-jobs/job1/related").json()["status"] == "unavailable"
