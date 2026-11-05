"""Add to your story: the prompt knows the story, a pasted pack is previewed on a copy before anything is saved, and
schedules can replace an after-link or retire a scene."""
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, moments, scheduler, storybuilder  # noqa: E402
from tests.test_scheduler import BROTHER, S, TWINS, season_plan  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


def _client():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    for p in season_plan():
        dialogue.add_pack(copy.deepcopy(p))
    dialogue.reload()
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6, siblings=[BROTHER] + TWINS)}).status_code == 200
    for m in moments.pending(api.lab.w):
        moments.resolve(api.lab.sim, m["id"], 0)
    api.lab.sim.advance_days(1)
    return c, api


ADDITIONS = {"dialogue_pack": 1, "name": "Additions: sophomore fall", "in_order": False,
             "cast": {"lead_brother": {"who": "older_brother", "sport": "basketball", "grade_offset": 3, "bind": "start"}},
             "scenes": [S("add_soph1_bro_calls", "cast:lead_brother", years=["sophomore"], months=[10], importance="regular"),
                        S("add_soph1_hallway", years=["sophomore"], not_before="09-10", not_after="09-30", importance="ambient")],
             "schedule": {"bro_college_call": {"years": ["sophomore"], "after": ["add_soph1_bro_calls"], "replace_after": True},
                          "twins_graduation": {"skip": True}}}


def test_the_prompt_knows_the_story_and_how_it_plays():
    c, api = _client()
    r = c.get("/api/story/add/prompt?ask=more%20sophomore%20year").json()
    p = r["prompt"]
    assert not r["checked"] and r["suggestions"]
    for must in ("more sophomore year", "cast: lead_brother = older brother", "Mike", "=== Brothers: Same Team", "--- bro team 05 tryouts",
                 "schedule:", "[skip]", "# LIFE OS story scripts", "ONE code block"):
        assert must in p, must
    assert "texts <pool>" not in p, "the storyline part of the guide only"
    rep = c.get("/api/story/schedule/report?days=400").json()
    assert rep["coverage"]["years"][0]["total"] > 0
    r = c.get("/api/story/add/prompt").json()
    assert r["checked"] and "Scenes that played per month" in r["prompt"]


SOPH = """Here you go!
```
=== Sophomore fall
cast: lead_brother = older brother, plays basketball, 3 years older, from the start
order: any

--- Bro calls  [sophomore · October]
lead_brother: You still alive over there?
* "Barely."      | lead_brother affection +
* Let it ring

--- The hallway  [sophomore · after Sep 10 · before Sep 30 · small]
Lockers slam. Everybody's somebody new this year.
* Keep your head down
* Say hi to everyone   | mood +

schedule:
bro college call [sophomore · after Sophomore fall: Bro calls · replace]
twins graduation [skip]
```
"""


def test_a_pasted_script_is_previewed_on_a_copy_and_nothing_is_saved():
    c, api = _client()
    before = [p["id"] for p in dialogue.packs()]
    r = c.post("/api/story/add/preview", json={"text": SOPH}).json()
    assert r["ok"] and r["script"], r["errors"]
    new = {x["title"]: x for x in r["new"]}
    assert new["Bro calls"]["state"] == "played" and "Oct" in new["Bro calls"]["date"]
    assert new["The hallway"]["state"] == "played" and "Sep" in new["The hallway"]["date"]
    changed = {x["sid"]: x for x in r["changed"]}
    assert changed["twins_graduation"]["reason"] == "skipped_by_plan", changed
    assert [p["id"] for p in dialogue.packs()] == before, "nothing saved"
    assert c.post("/api/dialogue/packs", json={"text": SOPH}).status_code == 200
    m = dialogue.merged()["moments"]
    calls = next(k for k, v in m.items() if v.get("title") == "Bro calls")
    assert m["bro_college_call"]["scene"]["when"]["after"] == [calls], "replace swapped the after-link"
    # sent back with the same title, it's an update: nothing in it is new
    r = c.post("/api/story/add/preview", json={"text": SOPH}).json()
    assert r["ok"] and r["new"] == [] and r["replaces"], r


def test_a_pasted_pack_is_previewed_on_a_copy_and_nothing_is_saved():
    c, api = _client()
    before = [p["id"] for p in dialogue.packs()]
    text = "Here you go!\n```json\n" + __import__("json").dumps(ADDITIONS) + "\n```"
    r = c.post("/api/story/add/preview", json={"text": text}).json()
    assert r["ok"], r["errors"]
    new = {x["sid"]: x for x in r["new"]}
    assert new["add_soph1_bro_calls"]["state"] == "played" and "Oct" in new["add_soph1_bro_calls"]["date"]
    assert new["add_soph1_hallway"]["state"] == "played" and "Sep" in new["add_soph1_hallway"]["date"]
    changed = {x["sid"]: x for x in r["changed"]}
    assert changed["twins_graduation"]["reason"] == "skipped_by_plan"
    assert [p["id"] for p in dialogue.packs()] == before and "add_soph1_bro_calls" not in dialogue.merged()["moments"], "nothing saved"
    assert c.post("/api/dialogue/packs", json={"pack": ADDITIONS}).status_code == 200
    assert "add_soph1_bro_calls" in dialogue.merged()["moments"]
    when = dialogue.merged()["moments"]["bro_college_call"]["scene"]["when"]
    assert when["after"] == ["add_soph1_bro_calls"], "replace_after replaced the after-link"


def test_a_broken_pack_comes_back_with_a_fix_prompt():
    c, api = _client()
    bad = copy.deepcopy(ADDITIONS)
    bad["scenes"][0]["when"]["years"] = ["fifth_year"]
    bad["schedule"]["twins_graduation"]["skip"] = "yes"
    r = c.post("/api/story/add/preview", json={"pack": bad}).json()
    assert not r["ok"] and r["errors"] and "fix exactly these problems" in r["fix_prompt"].lower()
    r = c.post("/api/story/add/preview", json={"text": "no json here"}).json()
    assert not r["ok"] and r["errors"]
    r = c.post("/api/story/add/preview", json={"text": SOPH.replace("| mood +", "| zzqx +")}).json()
    assert r["ok"] and r["notes"] == ["line 13: the effect 'zzqx +' came off ('zzqx +' isn't an effect I know)"], r["notes"]


def test_coverage_finds_the_quiet_stretches():
    c, api = _client()
    sim = api.lab.sim
    run = {"start": sim.w.day, "end": sim.w.day + 120, "per_day": {sim.w.day + 2: ["a"], sim.w.day + 70: ["b", "c"]}}
    cov = storybuilder.coverage(sim, run)
    assert cov["years"][0]["total"] == 3 and cov["quiet"] and cov["quiet"][0]["days"] >= 50
