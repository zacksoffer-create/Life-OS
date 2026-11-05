"""Fix or change a storyline you already have: what's broken (scene by scene) in one ChatGPT prompt, a change in your own
words, the reply pasted back replacing just those scenes (and cast lines) in place, undo, and a cast line switched
between one set person and a role."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue  # noqa: E402
from tests.test_scene_import import own_packs, story  # noqa: E402,F401
from tests.test_storyline_checkup import FILLED, force  # noqa: E402

LOOSE = """=== Bus Rides
cast: sis = Nicole Soffer
years: freshman

--- Lunch
sis: You're sitting with us?
* "Yeah."
sis: Okay. Don't be weird.
* "No."
sis: Fine by me.

--- The Bus
sis: Move over.
sis: I said move.
"""


def test_an_outlined_storyline_fixed_from_one_prompt_and_undone(story):
    c, pid, _ = story
    force(pid, FILLED)  # (old scenes, from before a scene without its decision was refused)
    pr = c.get(f"/api/story/revise?pack={pid}").json()
    broken = {s["n"]: s for s in pr["scenes"]}
    assert {14, 15} <= set(broken) and "never asks you anything" in broken[14]["problems"][0]
    assert broken[14]["src"].startswith("--- 14. The Banner")
    fp = c.get(f"/api/story/revise/fix-prompt?pack={pid}").json()["prompt"]
    assert "## What's broken" in fp and "Scene 14 (The Banner):" in fp and "--- 14. The Banner" in fp
    assert "every scene ends on a question" in fp.lower()
    reply = """Here you go:
```
--- 14. The Banner
nicole: Please tell me that's not a banner.
* "It's a banner." | nicole affection +
nicole: I'm going to die. Thank you.
* "It's a tablecloth."
nicole: Nobody believes that.

--- 15. Nicole Hears About It
nicole: People are talking about my brother.
* "Good talk?"
nicole: Annoyingly good.
* "I'll keep it down."
nicole: Don't you dare.
```"""
    r = c.post("/api/story/revise/apply", json={"pack": pid, "text": reply}).json()
    assert r["ok"] and r["replaced"] == ["Scene 14 (The Banner)", "Scene 15 (Nicole Hears About It)"], r
    assert not {14, 15} & {s["n"] for s in r["still"]}
    assert c.get(f"/api/story/revise?pack={pid}").json()["can_undo"]
    after = c.post("/api/story/revise/undo", json={"pack": pid}).json()
    assert {14, 15} <= {s["n"] for s in after["scenes"]} and not after["can_undo"]


def test_a_plain_storyline_changed_scenes_by_title_and_a_person_becomes_a_role(story):
    c, _, _ = story
    pid = dialogue.add_script(LOOSE)["ids"][0]
    pr = c.get(f"/api/story/revise?pack={pid}").json()
    assert [s["title"] for s in pr["scenes"]] == ["The Bus"]
    assert pr["cast"] == [{"name": "sis", "value": "Nicole Soffer", "named": True}]
    cp = c.post("/api/story/revise/change-prompt", json={"pack": pid, "ask": "make sis any friend instead of Nicole"}).json()["prompt"]
    assert "make sis any friend" in cp and "--- The Bus" in cp and "these scenes are broken" in cp and "Roles: friend" in cp
    reply = """```
cast: sis = friend, girl

--- The Bus
sis: Move over.
* "Make me." | sis affection -
sis: Gladly.
* "Fine." | sis affection +
sis: Thank you.

--- The Cafeteria Fight
sis: whatever
```"""
    r = c.post("/api/story/revise/apply", json={"pack": pid, "text": reply}).json()
    assert r["ok"] and r["head"] == ["cast: sis = friend, girl"] and r["replaced"] == ["The Bus"]
    assert [s["title"] for s in r["skipped"]] == ["The Cafeteria Fight"]  # not one of its scenes: nothing added
    assert r["still"] == []
    view = c.get(f"/api/story/revise?pack={pid}").json()
    assert view["cast"][0]["named"] is False and view["scene_count"] == 2
    src = dialogue.script_of(pid)
    assert "Lunch" in src and "Okay. Don't be weird." in src  # the scene nobody touched is as it was


def test_who_is_in_it_switches_between_a_person_and_a_role_without_chatgpt(story):
    c, _, _ = story
    pid = dialogue.add_script(LOOSE)["ids"][0]
    r = c.post("/api/story/revise/cast", json={"pack": pid, "name": "sis", "value": "teammate, girl"})
    assert r.status_code == 200, r.text
    assert r.json()["cast"] == [{"name": "sis", "value": "teammate, girl", "named": False}]
    assert "cast: sis = teammate, girl" in dialogue.script_of(pid)
    r = c.post("/api/story/revise/cast", json={"pack": pid, "name": "sis", "value": "Nicole Soffer"})
    assert r.json()["cast"][0]["named"] is True
    assert c.post("/api/story/revise/cast", json={"pack": pid, "name": "nobody", "value": "friend"}).status_code == 404
    assert c.post("/api/story/revise/apply", json={"pack": pid, "text": "just some words"}).json()["ok"] is False


def test_a_fix_that_still_has_no_decision_doesnt_go_in(story):
    c, _, _ = story
    pid = dialogue.add_script(LOOSE)["ids"][0]
    r = c.post("/api/story/revise/apply", json={"pack": pid, "text": "--- The Bus\nsis: Move over.\nsis: Now.\n"}).json()
    assert not r["ok"] and r["skipped"][0]["title"] == "The Bus" and "never asks you anything" in r["skipped"][0]["problems"][0]
    assert "sis: I said move." in dialogue.script_of(pid)  # as it was
