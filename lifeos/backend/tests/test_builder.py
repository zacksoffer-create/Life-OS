"""Building a storyline the way that holds up: ChatGPT plans an outline (one line per scene), then writes the scenes a few
at a time. The game owns the order, the timing and the branches, and fixes what's fixable in what ChatGPT wrote instead of
refusing it."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, moments, scheduler, script, scriptfix  # noqa: E402
from lifeos.catalogs import Catalogs  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.story import begin, create_story  # noqa: E402
from tests.test_scheduler import BROTHER, TWINS  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


OUTLINE = """=== Brothers: Same Team
cast: mike = Mike Soffer
years: freshman
about: You and Mike on the same team for one season.

outline:
1. Saved You a Seat | September | Mike saves you a seat on the bus.
2. The Passenger Seat | | Mike drives you to school for the first time.
3. Tryouts | November · big | You both try out.
4. Turkey Day | Thanksgiving | Mike is weird at dinner.
5. The Fight | December | You fight about playing time.
6. Making Up | | Mike apologizes. | only if you picked "Say sorry" in 5
7. Senior Night | February · big · Feb 30th maybe | Mike's last home game.
8. Last Bus Ride | June | The season's over.
"""

SCENES_1 = """Here are scenes 1 to 5!
```
--- 1. Saved You a Seat
mike: Sit. Don't make it weird.
* "Thanks." | mike affection +
* Sit in the back

--- 2. Passenger Seat  [after Saved You a Seat · if nope]
mike: Seatbelt. Rule one.
* Buckle up
* "Yes, Dad."

--- Tryouts
mike: Don't embarrass me.
* Go hard | mike respect +
* Coast

--- 4) Turkey Day
Mom: Somebody set the table.
mike: Not it.
* Set it | family afection +

--- 5. The Fight
mike: You took my minutes.
* "Sorry." | mike affection +
* "Earn them back."
```"""


def _story():
    sim = Simulation(create_story(spec(per=6, siblings=[BROTHER] + TWINS)))
    begin(sim)
    for m in moments.pending(sim.w):
        moments.resolve(sim, m["id"], 0)
    return sim


def test_an_outline_is_read_leniently():
    r = script.compile_script(OUTLINE)
    assert not r["errors"], r["errors"]
    pk = r["packs"][0]
    assert [e["n"] for e in pk["outline"]] == list(range(1, 9)) and not pk.get("scenes")
    e = {x["n"]: x for x in pk["outline"]}
    assert e[3]["when"] == "November · big" and e[2]["when"] == "" and e[4]["when"] == "Thanksgiving"
    assert e[7]["when"] == "February · big", "a time the game doesn't know is left out, with a note"
    assert any("Feb 30th maybe" in w["text"] for w in r["warnings"])
    assert e[6]["if"] == "only if you picked “Say sorry” in 5"
    alt = script.compile_script(OUTLINE.replace('| only if you picked "Say sorry" in 5', "| only if 5: Say sorry"))
    assert alt["packs"][0]["outline"][5]["if"] == "only if you picked “Say sorry” in 5"


def test_scenes_take_their_place_time_and_branches_from_the_outline():
    r = script.compile_script(OUTLINE + "\n" + SCENES_1.split("```")[1].split("\n", 1)[1].replace("afection", "affection")
                              + "\n--- 6. Making Up\nmike: We're good.\n* Hug it out\n")
    assert not r["errors"], r["errors"]
    pk = r["packs"][0]
    sc = {s["title"]: s for s in pk["scenes"]}
    assert [s["title"] for s in pk["scenes"]] == ["Saved You a Seat", "The Passenger Seat", "Tryouts", "Turkey Day", "The Fight", "Making Up"]
    assert sc["The Passenger Seat"]["when"] .get("after") is None and "remembered" not in sc["The Passenger Seat"]["when"], \
        "the scene's own after / if are the outline's job"
    assert sc["Saved You a Seat"]["when"]["months"] == [9] and sc["Turkey Day"]["when"]["dates"] == ["thanksgiving"]
    assert sc["The Passenger Seat"]["when"]["not_before"].startswith(("09", "10")), "between September and November"
    assert sc["Tryouts"]["when"]["importance"] == "major"
    fact = sc["Making Up"]["when"]["remembered"][0]
    assert ["remember", fact] in sc["The Fight"]["choices"][0]["ops"], "“Sorry.” is the choice like “Say sorry”"
    assert {e["n"]: e["written"] for e in pk["outline"]} == {1: True, 2: True, 3: True, 4: True, 5: True, 6: True, 7: False, 8: False}
    # a branch pointing at a choice that isn't there: the scene plays either way
    r = script.compile_script(OUTLINE.replace('"Say sorry"', '"Run away to Ohio"') + "\n--- 5. The Fight\nmike: x\n* Sorry\n\n--- 6. Making Up\nmike: y\n* ok\n")
    six = next(s for s in r["packs"][0]["scenes"] if s["title"] == "Making Up")
    assert "remembered" not in six["when"] and any("plays either way" in w["text"] for w in r["warnings"])


def test_an_outlined_storyline_plays_in_order_spaced_through_the_year():
    titles = [f"Week {i}" for i in range(1, 11)]
    src = "=== Spaced\ncast: mike = Mike Soffer\nyears: freshman\n\noutline:\n" + "".join(f"{i}. {t} | | stuff\n" for i, t in enumerate(titles, 1))
    src += "".join(f"\n--- {i}. {t}\nmike: {t}.\n* ok\n" for i, t in enumerate(titles, 1))
    assert dialogue.add_script(src)["ok"]
    sim = _story()
    scheduler.dry_run(sim, 365, None, full=False)
    rows = {r["title"]: r for r in scheduler.rows(sim)}
    days = [rows[t]["day"] for t in titles]
    assert all(d is not None for d in days) and days == sorted(days)
    assert len(set(days)) == 10 and min(b - a for a, b in zip(days, days[1:])) >= 14, "spaced out, not bunched up"


def test_build_a_storyline_through_the_api():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6, siblings=[BROTHER] + TWINS)}).status_code == 200
    op = c.get("/api/story/build/outline-prompt", params={"ask": "Mike and me on the same team", "size": "bunch"}).json()
    p = op["prompt"]
    for must in ("Mike and me on the same team", "Mike Soffer", "outline:", "only if you picked", "12 to 18 scenes", "Thanksgiving"):
        assert must in p, must
    assert op["chars"] < 5000, "short: the outline is the first step"
    pv = c.post("/api/story/build/outline", json={"text": "Sure!\n```\n" + OUTLINE + "```"}).json()
    assert pv["title"] == "Brothers: Same Team" and len(pv["outline"]) == 8 and pv["cast"][0]["label"] == "Mike Soffer"
    assert not dialogue.packs(), "checking doesn't save"
    sv = c.post("/api/story/build/outline", json={"text": OUTLINE, "save": True}).json()
    pid = sv["pack"]
    row = next(x for x in sv["packs"] if x["id"] == pid)
    assert row["outline"] == {"total": 8, "written": 0} and row["ok"]
    bp = c.get("/api/story/build/batch-prompt", params={"pack": pid, "count": 5}).json()
    assert (bp["first"], bp["last"], bp["written"], bp["total"]) == (1, 5, 0, 8)
    assert "Scene 5 must have a choice like “Say sorry”" in bp["prompt"] and "--- 1. Saved You a Seat" in bp["prompt"]
    assert "No tags in [ ]" in bp["prompt"] and "## Choices" in bp["prompt"] and "## Retiming" not in bp["prompt"]
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": SCENES_1}).json()
    assert r["got"] == [1, 2, 3, 4, 5] and (r["written"], r["total"]) == (5, 8)
    assert any(n.startswith("scene 4 (Turkey Day), line 4: ") and "'afection' read as 'affection'" in n for n in r["notes"]), r["notes"]
    src = dialogue.script_of(pid)
    assert "--- 2. The Passenger Seat\n" in src and "if nope" not in src, "its line as the outline has it (the outline says when)"
    bp = c.get("/api/story/build/batch-prompt", params={"pack": pid, "count": 5}).json()
    assert (bp["first"], bp["last"]) == (6, 8) and "## The scene right before these" in bp["prompt"] and "You took my minutes" in bp["prompt"]
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": "--- 6. Making Up\nmike: Good?\n* Good\n\n--- 7. Senior Night\nmike: Last one.\n* Cheer\n\n"
                                                                     "--- 8. Last Bus Ride\nmike: That's it.\n* ok\n"}).json()
    assert (r["written"], r["total"]) == (8, 8)
    assert c.get("/api/story/build/batch-prompt", params={"pack": pid}).json()["done"]
    # a scene written again replaces the old one
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": "--- 2. The Passenger Seat\nmike: New rules.\n* ok\n"}).json()
    assert r["got"] == [2] and dialogue.script_of(pid).count("--- 2.") == 1 and "New rules." in dialogue.script_of(pid)
    rd = c.get("/api/story/storyline/read", params={"pack": pid}).json()
    assert rd["total"] == 8 and not rd.get("unwritten")
    # timing by hand edits the outline itself
    tm = c.post(f"/api/dialogue/packs/{pid.replace(':', '%3A')}/timing", json={"years": ["sophomore"], "seasons": [], "spread": True}).json()
    assert tm["timing"]["years"] == ["sophomore"] and "years: sophomore" in dialogue.script_of(pid)


def test_read_it_shows_what_isnt_written_yet():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6, siblings=[BROTHER] + TWINS)}).status_code == 200
    pid = dialogue.add_script(OUTLINE)["ids"][0]
    dialogue.merge_scenes(pid, SCENES_1)
    rd = c.get("/api/story/storyline/read", params={"pack": pid}).json()
    assert rd["total"] == 5 and rd["unwritten"] == 3
    un = [x for x in rd["scenes"] if x.get("unwritten")]
    assert [x["outline_n"] for x in un] == [6, 7, 8] and un[0]["if"] == "only if you picked “Say sorry” in 5"


def test_what_chatgpt_gets_wrong_is_fixed_not_refused():
    bad = """=== X
cast: danny = Danny Kim
cast: lunchy = the lunch lady

--- A  [Thanksgivng · if never_set]
dany: hi {danny_frist}
lunchy: Trays.
* ok | fnu +, zzqx +, danny affection +
* two
* three
* four
* five
"""
    r = scriptfix.repair(bad, library={})
    assert r["ok"], r["result"]["errors"]
    t = r["text"]
    assert "[thanksgiving]" in t and "danny: hi {danny}" in t and "Lunchy: Trays." in t
    assert "* ok | fun +, danny affection +" in t and "* five" not in t
    notes = " | ".join(n["text"] for n in r["notes"])
    for must in ("'fnu' read as 'fun'", "'zzqx +' came off", "'dany' read as 'danny'", "came off", "past the fourth"):
        assert must in notes, must
    assert not scriptfix.repair("just some words, no scenes at all", library={})["ok"]


def test_the_engine_says_which_build_it_is():
    from fastapi.testclient import TestClient
    from lifeos import api
    assert TestClient(api.app).get("/api/version").json() == {"engine": "lab"}


def test_an_outline_written_a_little_differently_still_reads():
    from lifeos import script
    for text in ("1. Opening - September - Mike drives you\n2. Close - June - done",
                 "=== Holidays\n| # | Title | When | What |\n|---|---|---|---|\n| 1 | Opening | September | Mike drives you |\n| 2 | Close | June | done |",
                 "=== X\noutline:\n1. **Opening** | September | Mike drives you\n2. Close | June | done",
                 "```\n=== X\n- 1) Opening — September — Mike drives you\n- 2) Close — June — done\n```"):
        r = script.compile_script(script.normalize_outline(text))
        assert not r["errors"], (text, r["errors"])
        assert [(e["n"], e["title"], e["when"]) for e in r["packs"][0]["outline"]] == [(1, "Opening", "September"), (2, "Close", "June")], text


def test_a_paste_that_isnt_an_outline_says_what_one_looks_like_in_words():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6, siblings=[BROTHER] + TWINS)}).status_code == 200
    r = c.post("/api/story/build/outline", json={"text": "here's a story about my brother, hope you like it"})
    assert r.status_code == 422
    errs = r.json()["errors"]
    assert all(isinstance(e, str) for e in errs) and errs[0].startswith("There's no outline in that"), errs
    r = c.post("/api/texting/check", json={"text": "just words"})
    assert r.status_code == 422 and all(isinstance(e, str) for e in r.json()["errors"])
