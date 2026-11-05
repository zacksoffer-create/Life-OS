"""Next episode never lives a year forward looking for a scene that isn't coming: it stops at once when no storyline
scene can come (and says why), and otherwise looks about two months ahead at most."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _story():
    from fastapi.testclient import TestClient
    from lifeos import api, moments
    from lifeos.storage import Store
    from tests.test_story import spec
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    for m in moments.pending(api.lab.w):
        moments.resolve(api.lab.sim, m["id"], None)
    return c, api


def _wait(api):
    for _ in range(3000):
        if api.lab.job.get("status") != "running":
            return api.lab.job
        time.sleep(0.01)
    raise AssertionError("still running")


def test_nothing_can_come_so_it_stops_right_away_and_says_why(monkeypatch):
    c, api = _story()
    from lifeos import scheduler
    monkeypatch.setattr(scheduler, "ahead", lambda sim: {"open": 0, "ready": 0, "why": "12 scenes: nobody in your story fits"})
    monkeypatch.setattr(scheduler, "deliver", lambda sim: None)
    d0 = api.lab.w.day
    c.post("/api/story/advance", json={"until": "episode"})
    j = _wait(api)
    assert j["stop"] == "nothing_left" and j["why"] == "12 scenes: nobody in your story fits"
    assert api.lab.w.day == d0  # not a single day lived looking


def test_it_looks_about_two_months_ahead_at_most(monkeypatch):
    c, api = _story()
    from lifeos import moments, scheduler
    monkeypatch.setattr(scheduler, "deliver", lambda sim: None)
    monkeypatch.setattr(scheduler, "is_episode", lambda sim, kind: False)
    monkeypatch.setattr(moments, "pending", lambda w: [])
    monkeypatch.setattr(scheduler, "ahead", lambda sim: {"open": 3, "ready": 0, "why": "3 scenes: not yet"})
    d0 = api.lab.w.day
    c.post("/api/story/advance", json={"until": "episode"})
    j = _wait(api)
    assert j["stop"] == "time" and 55 <= api.lab.w.day - d0 <= 62


def test_ahead_counts_what_can_still_come():
    c, api = _story()
    from lifeos import scheduler
    a = scheduler.ahead(api.lab.sim)
    assert set(a) == {"open", "ready", "why"} and a["open"] >= a["ready"] >= 0
