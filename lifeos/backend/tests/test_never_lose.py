"""Nothing you add can wipe out what you have: an expansion is always its own piece (even when ChatGPT reuses the
storyline's name or forgets `expands:`), a paste replaces a storyline only when it's a newer version of it, and every
replaced, edited or removed storyline can be brought back."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue  # noqa: E402
from tests.test_builder import OUTLINE, SCENES_1  # noqa: E402
from tests.test_scheduler import BROTHER, TWINS  # noqa: E402
from tests.test_story import spec  # noqa: E402

EXP = """=== {title}
{exp}years: freshman

outline:
1. Christmas Eve | Christmas Eve | Mike comes home late.
2. New Year's | New Year's Eve | You both stay up.
"""


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


@pytest.fixture
def c():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    client = TestClient(api.app)
    assert client.post("/api/story/new", json={"spec": spec(per=6, siblings=[BROTHER] + TWINS)}).status_code == 200
    return client


def _brothers(c):
    pid = c.post("/api/story/build/outline", json={"text": OUTLINE, "save": True}).json()["pack"]
    c.post("/api/story/build/scenes", json={"pack": pid, "text": SCENES_1})
    return pid


def _rows(c):
    return {r["name"]: r for r in c.get("/api/dialogue/packs").json()["packs"]}


@pytest.mark.parametrize("title,exp", [("Brothers: Same Team", "expands: Brothers: Same Team\n"), ("Brothers: Same Team", ""),
                                       ("Holidays with Mike", ""), ("Brothers: Same Team: Holidays", "expands: Brothers: Same Team\n")])
def test_an_expansion_never_takes_its_storylines_place(c, title, exp):
    pid = _brothers(c)
    r = c.post("/api/story/build/outline", json={"text": EXP.format(title=title, exp=exp), "save": True, "expand": pid}).json()
    rows = _rows(c)
    assert len(rows["Brothers: Same Team"]["scenes"]) == 5, "the storyline keeps every scene"
    new = next(x for x in rows.values() if x["id"] == r["pack"])
    assert new["expands"] == "Brothers: Same Team" and new["name"] != "Brothers: Same Team", new
    assert r["title"] == new["name"]
    c.post("/api/story/build/scenes", json={"pack": r["pack"], "text": "--- 1. Christmas Eve\nmike: You up?\n* Yeah\n"})
    rows = _rows(c)
    assert len(rows["Brothers: Same Team"]["scenes"]) == 5 and len(rows[new["name"]]["scenes"]) == 1


def test_a_paste_with_the_same_name_replaces_only_a_newer_version(c):
    _brothers(c)
    full = dialogue.script_of(next(r["id"] for r in _rows(c).values()))
    # the same storyline, one scene more: an update
    r = dialogue.add_script(full + "\n--- 6. Making Up\nmike: We're good.\n* ok\n")
    assert r["ok"] and len(_rows(c)) == 1 and len(_rows(c)["Brothers: Same Team"]["scenes"]) == 6
    # a different storyline with the same name: kept alongside, nothing replaced
    r = dialogue.add_script("=== Brothers: Same Team\n\n--- Something else\nmike: hm\n* ok\n")
    assert r["ok"] and any("nothing of yours was replaced" in n for n in r["notes"])
    rows = _rows(c)
    assert len(rows["Brothers: Same Team"]["scenes"]) == 6 and "Brothers: Same Team (2)" in rows
    # texting added twice is two packs; a new season plan replaces the old one
    assert dialogue.add_script("=== Texting\nflirt tease:\n  you wish\n")["ok"]
    assert dialogue.add_script("=== Texting\nflirt sweet:\n  same honestly\n")["ok"]
    assert {"Texting", "Texting (2)"} <= set(_rows(c))
    plan = "=== Season plan\nschedule:\n  Brothers: Same Team: Tryouts [freshman · {m}]\n"
    assert dialogue.add_script(plan.format(m="October"))["ok"] and dialogue.add_script(plan.format(m="November"))["ok"]
    assert [n for n in _rows(c) if n.startswith("Season plan")] == ["Season plan"]


def test_replaced_edited_and_removed_storylines_can_come_back(c):
    pid = _brothers(c)
    vs = c.get("/api/dialogue/history").json()["versions"]
    assert vs and vs[0]["why"] == "edited" and vs[0]["title"] == "Brothers: Same Team", "adding scenes keeps the version before"
    assert c.post(f"/api/dialogue/packs/{pid.replace(':', '%3A')}/remove").status_code == 200
    assert "Brothers: Same Team" not in _rows(c)
    gone = c.get("/api/dialogue/history").json()["versions"][0]
    assert gone["why"] == "removed" and gone["scenes"] == 5
    r = c.post("/api/dialogue/history/restore", json={"file": gone["file"]}).json()
    assert r["restored"] == pid and len(_rows(c)["Brothers: Same Team"]["scenes"]) == 5
    assert c.post("/api/dialogue/history/restore", json={"file": "nope.story"}).status_code == 404
    for _ in range(12):  # only the last few are kept
        dialogue.add_script(dialogue.script_of(pid), into=pid)
    assert sum(1 for v in dialogue.history() if v["stem"] == "brothers_same_team") == dialogue.HISTORY_KEEP


def test_many_expansions_on_one_storyline_all_attach_and_all_play(c):
    from lifeos import scheduler
    from lifeos import api
    base = _brothers(c)

    def add(expand, title, exp, second):
        text = (f"=== {title}\n{exp}years: freshman\n\noutline:\n1. Christmas Eve | Christmas Eve | Mike comes home late.\n"
                f"2. {second} | | stuff\n")
        r = c.post("/api/story/build/outline", json={"text": text, "save": True, "expand": expand}).json()
        c.post("/api/story/build/scenes", json={"pack": r["pack"], "text": f"--- 1. Christmas Eve\nmike: hi\n* ok\n\n--- 2. {second}\nmike: yo\n* ok\n"})
        return r["pack"]
    a = add(base, "Brothers: Same Team: Holidays", "expands: Brothers: Same Team\n", "New Year's")
    add(base, "Brothers: Same Team", "", "Snow Day")  # ChatGPT reused the storyline's name and forgot expands:
    add(base, "Brothers: Same Team", "", "Spring Break")  # ...twice
    add(a, "Brothers: Same Team: Holidays", "expands: Brothers: Same Team: Holidays\n", "Easter")  # more, from an expansion
    rows = _rows(c)
    assert len(rows["Brothers: Same Team"]["scenes"]) == 5
    more = [r for r in rows.values() if r.get("expands")]
    assert len(more) == 4 and all(r["expands"] == "Brothers: Same Team" for r in more), [(r["name"], r["expands"]) for r in more]
    ids = [s["id"] for r in rows.values() for s in r["scenes"]]
    assert len(ids) == 13 and len(set(ids)) == 13, "every scene has its own id, even four Christmas Eves"
    rd = c.get("/api/story/storyline/read", params={"pack": base}).json()
    assert rd["total"] == 13 and len(rd["parts"]) == 5
    sim = api.lab.sim
    scheduler.dry_run(sim, 365, None, full=False)
    played = {r["sid"] for r in scheduler.rows(sim) if r.get("day") is not None}
    assert set(ids) <= played, set(ids) - played
    p = c.get("/api/story/build/outline-prompt", params={"ask": "more", "expand": base}).json()["prompt"]
    assert "Expansions it already has" in p and "Brothers: Same Team: Holidays: Christmas Eve, New Year's" in p


def test_a_storyline_with_only_its_outline_so_far_can_be_expanded(c):
    base = c.post("/api/story/build/outline", json={"text": OUTLINE.replace("=== Brothers: Same Team", "=== Brothers base"),
                                                     "save": True}).json()["pack"]
    ck = c.post("/api/story/build/outline", json={"text": OUTLINE, "expand": base}).json()
    assert ck["expands"] == "Brothers base" and not any("came off" in n for n in ck["notes"]), ck["notes"]
    sv = c.post("/api/story/build/outline", json={"text": OUTLINE, "expand": base, "save": True}).json()
    assert sv["expands"] == "Brothers base"
    assert _rows(c)[sv["title"]]["expands"] == "Brothers base"


TWINS_BASE = "The Twin Sisters: Popularity, Friends, and Family Reputation"  # 60 characters, file names are cut at 40


def test_expansions_of_a_storyline_with_a_long_name_save_right_away(c):
    import time
    base = dialogue.add_script(f"=== {TWINS_BASE}\ncast: jen = Jen Soffer\nyears: freshman-junior\n\n"
                               + "".join(f"--- Twins {i}\njen: line {i}\n* ok\n\n" for i in range(6)))["ids"][0]
    heist = (f"=== {TWINS_BASE}: The Great Hoodie Heist\nexpands: {TWINS_BASE}\nyears: freshman-junior\nabout: Jen keeps stealing hoodies.\n\n"
             "outline:\n1. That's Literally My Hoodie | freshman · September · school day | Jen wears your Yankees hoodie.\n"
             "9. The Unofficial Closet Agreement | freshman · June · weekend · big | You set rules.\n"
             "10. The Borrowing System Lasts One Day | sophomore · September · first day of school | She finds a loophole. "
             "| only if you picked \"Make her ask before borrowing\" in 9\n")
    names = []
    for _ in range(3):  # the same expansion three times: each its own, none in place of another, none hanging
        t0 = time.time()
        r = c.post("/api/story/build/outline", json={"text": heist, "save": True, "expand": base}).json()
        assert time.time() - t0 < 5, "saving never hangs on a long name"
        names.append(r["title"])
        assert r["expands"] == TWINS_BASE
    assert names == [f"{TWINS_BASE}: The Great Hoodie Heist", f"{TWINS_BASE}: The Great Hoodie Heist (2)",
                     f"{TWINS_BASE}: The Great Hoodie Heist (3)"], names
    rows = _rows(c)
    assert len(rows[TWINS_BASE]["scenes"]) == 6 and all(rows[n]["expands"] == TWINS_BASE for n in names)
    assert len({rows[n]["file"] for n in names} | {rows[TWINS_BASE]["file"]}) == 4, "each in its own file"
    pid = next(rows[n]["id"] for n in names[:1])
    got = c.post("/api/story/build/scenes", json={"pack": pid, "text": "--- 1. That's Literally My Hoodie\njen: Nice hoodie, right?\n* \"That's mine.\"\n"}).json()
    assert got["got"] == [1] and len(_rows(c)[TWINS_BASE]["scenes"]) == 6
