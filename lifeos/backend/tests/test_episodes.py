"""Episodes back to back: Next episode lives your life up to the next storyline scene and stops there, every time."""
import copy
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, moments, scheduler  # noqa: E402
from tests.test_scheduler import BROTHER, TWINS, season_plan  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


AROUND = "=== Around school\norder: any\n\n" + "\n".join(
    f"--- {t}  [freshman · always]\nbest friend: {{Huh.|Okay.}} {t}.\n* Sure | mood +\n* Nah\n"
    for t in ("Locker jam", "Lunch line", "Fire drill", "Pop quiz rumor", "Bus stop"))


def _client():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    for p in season_plan():
        dialogue.add_pack(copy.deepcopy(p))
    assert dialogue.add_script(AROUND)["ok"]  # one-offs that can come any time (so there's always something ready)
    dialogue.reload()
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6, siblings=[BROTHER] + TWINS)}).status_code == 200
    return c, api


def _next_episode(c):
    j = c.post("/api/story/advance", json={"until": "episode"}).json()
    while j.get("status") == "running":
        time.sleep(0.05)
        j = c.get("/api/sim/job").json()
    return j


def _play_through(c, w, sim, root):
    """Answer every beat of the scene, the way the phone does."""
    for _ in range(20):
        pend = [m for m in moments.pending(w) if scheduler._root(sim, m["kind"]) == root]
        if not pend:
            return
        r = c.post(f"/api/phone/moment/{pend[0]['id']}", json={"index": 0}).json()
        if r.get("minigame"):
            c.post(f"/api/phone/moment/{pend[0]['id']}", json={"index": 0, "auto": True})
    raise AssertionError("the scene never finished")


def test_next_episode_goes_straight_to_the_next_scene_every_time():
    c, api = _client()
    w, sim = api.lab.w, api.lab.sim
    assert c.post("/api/story/control", json={"binge": True}).json()["binge"] is True
    assert c.get("/api/phone/state").json()["stories"]["binge"] is True
    played, days = [], []
    for _ in range(8):
        start = w.day
        j = _next_episode(c)
        assert j["status"] == "done" and j["stop"] == "episode", j
        pend = moments.pending(w)
        # only the scene is waiting: tryouts, invites, class games and the rest, your character already handled
        assert pend and all(scheduler.is_episode(sim, m["kind"]) for m in pend), [m["kind"] for m in pend]
        root = scheduler._root(sim, pend[0]["kind"])
        _play_through(c, w, sim, root)
        played.append(root)
        days.append(w.day - start)
        assert root in scheduler.done_map(w)
    assert len(set(played)) == 8, played
    assert c.get("/api/phone/state").json()["stories"]["played"] >= 8


def test_next_episode_stops_right_away_when_a_scene_is_already_waiting():
    c, api = _client()
    w, sim = api.lab.w, api.lab.sim
    _next_episode(c)
    day, waiting = w.day, [m["id"] for m in moments.pending(w)]
    j = _next_episode(c)  # didn't answer it: the same scene is still there, no time passed
    assert j["stop"] == "episode" and w.day == day and [m["id"] for m in moments.pending(w)] == waiting


def _played_order(c, w, sim, wanted, limit=40):
    """Next episode until every scene in wanted has played; the order they played in."""
    order = []
    for _ in range(limit):
        if set(wanted) <= set(order):
            break
        j = _next_episode(c)
        assert j["stop"] == "episode", j
        root = scheduler._root(sim, moments.pending(w)[0]["kind"])
        _play_through(c, w, sim, root)
        if root in wanted:
            order.append(root)
    return order


def test_move_an_episode_ahead_of_another_and_back():
    c, api = _client()
    w, sim = api.lab.w, api.lab.sim
    _next_episode(c)
    rows = c.get("/api/story/order").json()["list"]
    assert len(rows) >= 4 and all(r["date"] and r["storyline"] is not None for r in rows)
    # two episodes from different storylines, the later one moved ahead of the earlier
    i = next(i for i in range(len(rows) - 1) if rows[i]["pack"] != rows[i + 1]["pack"] and rows[i + 1]["in_days"] > rows[i]["in_days"])
    a, b = rows[i]["sid"], rows[i + 1]["sid"]
    r = c.post("/api/story/order/move", json={"sid": b, "before": a})
    assert r.status_code == 200, r.text
    v = r.json()
    ids = [x["sid"] for x in v["list"]]
    assert b in ids and (a not in ids or ids.index(b) < ids.index(a)), ids
    assert v["note"] and v["changes"] == [{"sid": a, "title": rows[i]["title"], "waits_for": [{"sid": b, "title": rows[i + 1]["title"]}]}]
    assert next(x for x in v["list"] if x["sid"] == a)["waits_for"] == [rows[i + 1]["title"]] if a in ids else True
    # moving it back undoes the move instead of stacking a second one
    r = c.post("/api/story/order/move", json={"sid": a, "before": b}).json()
    assert r["undid"] and r["changes"] == [] and not scheduler.holds(w)
    # and for real: with the move in, b plays first
    c.post("/api/story/order/move", json={"sid": b, "before": a})
    order = _played_order(c, w, sim, [a, b])
    assert order == [b, a], order


def test_chapters_of_one_storyline_stay_in_order():
    c, api = _client()
    w, sim = api.lab.w, api.lab.sim
    cat = scheduler.catalog(sim)
    pk = next(p for p in cat["ordered"] if len(cat["chapters"][p]) >= 3)
    ch = cat["chapters"][pk]
    r = c.post("/api/story/order/move", json={"sid": ch[2], "before": ch[1]})
    assert r.status_code == 422 and "in order" in r.json()["detail"]
    # and no loops: once b is ahead of a, a can't also be put ahead of b by some other route
    rows = c.get("/api/story/order").json()["list"]
    i = next(i for i in range(len(rows) - 1) if rows[i]["pack"] != rows[i + 1]["pack"])
    a, b = rows[i]["sid"], rows[i + 1]["sid"]
    assert c.post("/api/story/order/move", json={"sid": b, "before": a}).status_code == 200
    assert scheduler._waits_on(sim, cat, a, b) and not scheduler._waits_on(sim, cat, b, a)
    c.post("/api/story/order/clear", json={})
    assert not scheduler.holds(w)


def test_play_next_pulls_a_ready_episode_to_the_front():
    c, api = _client()
    w, sim = api.lab.w, api.lab.sim
    j = _next_episode(c)
    _play_through(c, w, sim, scheduler._root(sim, moments.pending(w)[0]["kind"]))
    rows = c.get("/api/story/order").json()["list"]
    later = [r for r in rows[1:] if r["ready"]]
    assert later, rows
    pick = later[-1]["sid"]
    assert c.post("/api/story/order/next", json={"sid": pick}).status_code == 200
    day = w.day
    _next_episode(c)
    assert scheduler._root(sim, moments.pending(w)[0]["kind"]) == pick and w.day == day
    # one that can't happen yet says why
    blocked = next((r for r in rows if not r["ready"]), None)
    if blocked:
        r = c.post("/api/story/order/next", json={"sid": blocked["sid"]})
        assert r.status_code == 422 and "can't come yet" in r.json()["detail"]


def test_play_next_picked_during_a_scene_comes_right_after_it():
    c, api = _client()
    w, sim = api.lab.w, api.lab.sim
    _next_episode(c)
    cur = scheduler._root(sim, moments.pending(w)[0]["kind"])
    rows = c.get("/api/story/order").json()["list"]
    assert not any("{" in r["title"] for r in rows), [r["title"] for r in rows]  # names filled in, or who in words
    pick = [r for r in rows[1:] if r["ready"]][-1]["sid"]
    assert c.post("/api/story/order/next", json={"sid": pick}).status_code == 200
    _play_through(c, w, sim, cur)  # its follow-ups don't cut in front of your pick
    _next_episode(c)
    assert scheduler._root(sim, moments.pending(w)[0]["kind"]) == pick
