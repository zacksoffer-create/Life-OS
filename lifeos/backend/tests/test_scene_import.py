"""Importing scenes for a storyline that's being written a few at a time (Write more > Write the scenes): what ChatGPT
sends is read the way it meant it, a scene that still can't go in stays out (as it was) with exactly what to fix, and
nothing anyone pastes crashes the importer or touches the scenes already in."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, scheduler  # noqa: E402
from tests.data.nicoles_biggest_fan import BASE, BROKEN_16, OUTLINE, SCENES_1_12, SCENES_13_18, TITLE  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


@pytest.fixture
def story():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    s = spec(per=6)
    s["siblings"] = [{"key": "nicole", "first": "Nicole", "gender": "f", "grade": 11},
                     {"key": "jen", "first": "Jennifer", "gender": "f", "grade": 11, "twin_of": "nicole"}]
    assert c.post("/api/story/new", json={"spec": s}).status_code == 200
    base = dialogue.add_script(f"=== {BASE}\ncast: jen = Jennifer Soffer\nyears: freshman-junior\n\n--- Twins 1\njen: hi\n* ok\n")["ids"][0]
    pid = c.post("/api/story/build/outline", json={"text": OUTLINE, "save": True, "expand": base}).json()["pack"]
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": SCENES_1_12}).json()
    assert r["written"] == 12
    return c, pid, api


def _scenes(c, pid):
    p = dialogue._script_pack(pid)
    from lifeos import script
    by_id = {sc["id"]: sc for sc in p["pack"]["scenes"]}
    return {e["n"]: by_id[e["sid"]] for e in script.outline_entries(p["pack"]) if e.get("written")}


def _paths(chs, ops=()):
    """Every way through a scene's choices: [(labels, ops on the way)]."""
    out = []
    for ch in chs:
        here = list(ops) + [o[0] + ":" + str(o[1]) if len(o) > 1 else o[0] for o in ch.get("ops", [])]
        sub = (ch.get("then") or {}).get("choices") or []
        out += [([ch["label"]] + lab, o) for lab, o in _paths(sub, here)] if sub else [([ch["label"]], here)]
    return out


def test_the_crash_a_scene_the_fixer_cant_fix_is_reported_not_a_type_error(story):
    c, pid, _ = story
    text = SCENES_13_18.replace("--- 15. Nicole Hears About It", "texts nicole_hype:\n  go nicole\n\n--- 15. Nicole Hears About It")
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": text})
    assert r.status_code == 200, r.text  # (it used to be a 500: TypeError: expected string or bytes-like object, got 'dict')
    j = r.json()
    assert j["got"] == [13, 15, 16, 17, 18] and j["written"] == 17
    assert [(s["n"], s["title"]) for s in j["skipped"]] == [(14, "The Banner")]
    assert "nicole_hype" in j["skipped"][0]["problems"][0]
    assert "Scene 14 (The Banner):" in j["fix_prompt"] and "`* ` starts a choice" in j["fix_prompt"]
    assert all(isinstance(n, str) for n in j["notes"])


def test_scenes_13_to_18_as_chatgpt_wrote_them_all_go_in_as_meant(story):
    c, pid, _ = story
    before = {n: (sc["text"], [ch["label"] for ch in sc["choices"]]) for n, sc in _scenes(c, pid).items()}
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": SCENES_13_18}).json()
    assert r["got"] == [13, 14, 15, 16, 17, 18] and not r["skipped"] and r["written"] == 18
    sc = _scenes(c, pid)
    assert {n: (sc[n]["text"], [ch["label"] for ch in sc[n]["choices"]]) for n in range(1, 13)} == before, "the first twelve are untouched"
    s13 = sc[13]
    assert "The gym is packed" in s13["text"] and "You got here early." in s13["text"], "italics are narration, **Nicole:** talks"
    assert [ch["label"] for ch in s13["choices"]] == ['"Front row"', '"Traffic was light."'], "two choices, then a second round under each"
    paths = _paths(s13["choices"])
    assert len(paths) == 4 and all(len(lab) == 2 for lab, _ in paths)
    assert all("remember:front_row_season" in ops for _, ops in paths), "the line after everything plays whichever way you went"
    assert any(o.startswith("rel") for o in _paths(s13["choices"][:1])[0][1]), "-> nicole affection + is an effect"
    assert any(o.startswith("rel") for o in _paths(s13["choices"][1:])[0][1]), "(nicole affection -) is an effect"
    assert all("remember:wore_the_shirt" in ops for lab, ops in paths if lab[1] == '"Obviously."')
    s14 = sc[14]
    assert "unrolls a bedsheet" in s14["text"] and len(s14["choices"]) == 2
    assert all(any("Hang it where I can't see it" in str(o) for o in ops) for _, ops in _paths(s14["choices"]))
    assert all("remember:banquet_speech" in ops for _, ops in _paths(sc[18]["choices"]))
    s17 = _paths(sc[17]["choices"])
    assert len(s17) == 4 and any("remember:sat_after_the_loss" in ops for _, ops in s17)


def test_properly_nested_choices_go_in_unchanged(story):
    c, pid, _ = story
    nested = """--- 13. Front Row Seats
nicole: You actually came.
* "Wouldn't miss it." | nicole affection +
    nicole: Front row, then.
    * "Lead the way." | nicole affection +
        remember sat_front_row
    * "I'm good in the back."
* "My mom made me."
    nicole: Wow. Thanks.
"""
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": nested}).json()
    assert r["got"] == [13] and not any("now comes after" in n or "now follow" in n for n in r["notes"])
    paths = _paths(_scenes(c, pid)[13]["choices"])
    assert [lab for lab, _ in paths] == [['"Wouldn\'t miss it."', '"Lead the way."'], ['"Wouldn\'t miss it."', '"I\'m good in the back."'],
                                         ['"My mom made me."']]
    assert "remember:sat_front_row" in paths[0][1]


@pytest.mark.parametrize("text,status", [
    ("lol here you go, hope you like them", 422),
    ("--- 13. Front Row Seats\n\n--- 14. The Banner\n* | nicole affection +\n", 200),
    (BROKEN_16, 200),
    ("--- 13. Front Row Seats\n" + "nicole: " + "really " * 400 + "long\n* ok\n", 200),
    ("```\n--- 13. Front Row Seats\nnicole: hi\n* \"ok\" | nicole vibes +++, remember\n```", 200),
    ({"not": "text"}, 200),
])
def test_malformed_input_never_crashes_and_never_touches_what_is_there(story, text, status):
    c, pid, _ = story
    before = _scenes(c, pid)
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": text})
    assert r.status_code in (status, 422), r.text
    j = r.json()
    after = _scenes(c, pid)
    assert {n: after[n]["text"] for n in before} == {n: before[n]["text"] for n in before}
    for sk in j.get("skipped") or []:
        assert sk["problems"] and all(isinstance(p, str) and p for p in sk["problems"])
    if r.status_code == 422:
        assert j["errors"] and all(isinstance(e, str) for e in j["errors"])


def test_an_empty_or_wordless_scene_is_reported_and_left_out(story):
    c, pid, _ = story
    j = c.post("/api/story/build/scenes", json={"pack": pid, "text": "--- 13. Front Row Seats\n\n--- 14. The Banner\n* | nicole affection +\n"}).json()
    assert j["got"] == [] and [s["n"] for s in j["skipped"]] == [13, 14] and j["written"] == 12
    assert "empty" in j["skipped"][0]["problems"][0] and "line 2" in j["skipped"][1]["problems"][0] and "needs words" in j["skipped"][1]["problems"][0]


def test_a_new_version_that_cant_go_in_leaves_the_old_one(story):
    c, pid, _ = story
    c.post("/api/story/build/scenes", json={"pack": pid, "text": SCENES_13_18})
    old = _scenes(c, pid)[14]["text"]
    j = c.post("/api/story/build/scenes", json={"pack": pid, "text": "--- 14. The Banner\n\n"}).json()
    assert [s["n"] for s in j["skipped"]] == [14] and _scenes(c, pid)[14]["text"] == old and j["written"] == 18


def test_all_six_play_in_the_outlines_order(story):
    c, pid, api = story
    c.post("/api/story/build/scenes", json={"pack": pid, "text": SCENES_13_18})
    sc = _scenes(c, pid)
    # scene 15 is only if you picked "Front row" in 13: that choice remembers what 15 waits for
    fact = sc[15]["when"]["remembered"][0]
    assert any(o == ["remember", fact] for o in sc[13]["choices"][0]["ops"])
    sim = api.lab.sim
    scheduler.dry_run(sim, 365 * 3, None, full=False)
    day = {r["sid"]: r.get("day") for r in scheduler.rows(sim)}
    played = [(n, day.get(sc[n]["id"])) for n in range(13, 19) if day.get(sc[n]["id"]) is not None]
    assert [n for n, _ in played] == sorted(n for n, _ in played) and [d for _, d in played] == sorted(d for _, d in played)
    assert {13, 14, 16, 17, 18} <= {n for n, _ in played}, played
    assert all(day.get(sc[n]["id"]) is not None for n in range(1, 13)), "the first twelve still play"
