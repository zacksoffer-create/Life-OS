"""Every choice ChatGPT writes stays a choice, with what happens after it, and the scene that follows a choice stays tied
to it: outcomes written flush left under each choice, "Choice 1:" / "Outcome:" labels, `**` second rounds and
`either way:` are read as meant; a reply that got cut off doesn't save a half scene; and anything missing (a choice with
nothing after it, the choice a later scene follows) is named, with a message for ChatGPT to fill it in."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue  # noqa: E402
from tests.test_scene_import import _paths, _scenes, own_packs, story  # noqa: E402,F401

FLUSH = """Here are scenes 13 to 15!

```
--- 13. Front Row Seats
The gym is packed. Nicole spots you from the court.
nicole: You actually came.
* "Front row." | nicole affection +
nicole: Front row, then. Come on.
remember front_row_season
* "Back row's fine."
nicole: Wow. Okay.
* "I can't stay long."
nicole: Seriously? It's the opener.

--- 14. The Banner
nicole: Please tell me that's not a banner.
Choice 1: "It's a banner." (+Nicole affection)
Outcome: She hides her face, but she's smiling.
Choice 2: "It's a tablecloth."
Outcome: Nicole: Nobody believes that.

--- 15. Nicole Hears About It
nicole: People are talking about my brother.
* "Good talk?"
nicole: Annoyingly good.
** "Told you." | nicole affection +
nicole: Don't push it.
** "I'll tone it down."
nicole: Don't you dare.
* "I can take it down." | nicole affection -
nicole: Leave it.
either way:
nicole: Anyway. Practice.
```"""


def _top(sc):
    return [ch["label"] for ch in sc["choices"]]


def _after(ch):
    """What plays after a choice: its lines (said right after it) and the next beat's."""
    t = ch.get("then") or {}
    return " ".join([str(o[1]) for o in ch.get("ops") or [] if o and o[0] == "say"] + [str(t.get("text") or "")])


def test_outcomes_under_each_choice_keep_every_choice_side_by_side(story):
    c, pid, _ = story
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": FLUSH}).json()
    assert r["got"] == [13, 14, 15] and not r["skipped"] and not r["gaps"], (r["skipped"], r["gaps"])
    sc = _scenes(c, pid)
    s13 = sc[13]
    assert _top(s13) == ['"Front row."', '"Back row\'s fine."', '"I can\'t stay long."'], "three choices, none buried under another"
    assert [("Front row, then" in _after(ch), "Wow" in _after(ch), "Seriously" in _after(ch)) for ch in s13["choices"]] == \
        [(True, False, False), (False, True, False), (False, False, True)], "each choice keeps its own answer"
    assert ["remember", "front_row_season"] in s13["choices"][0]["ops"]
    s14 = sc[14]
    assert _top(s14) == ['"It\'s a banner."', '"It\'s a tablecloth."'], "Choice 1: / Choice 2: are choices"
    assert "smiling" in _after(s14["choices"][0]) and "Nobody believes" in _after(s14["choices"][1])
    assert any(o[0].startswith("rel") for o in s14["choices"][0]["ops"]), "(+Nicole affection) is an effect"
    s15 = sc[15]
    assert _top(s15) == ['"Good talk?"', '"I can take it down."']
    paths = _paths(s15["choices"])
    assert [lab for lab, _ in paths] == [['"Good talk?"', '"Told you."'], ['"Good talk?"', '"I\'ll tone it down."'], ['"I can take it down."']]


def test_the_scene_after_a_choice_stays_tied_to_it(story):
    c, pid, api = story
    c.post("/api/story/build/scenes", json={"pack": pid, "text": FLUSH})
    sc = _scenes(c, pid)
    first = sc[13]["choices"][0]
    facts = [o[1] for o in first["ops"] if o[0] == "remember" and o[1] != "front_row_season"]
    assert facts, "scene 15 (only if you picked Front row in 13) is wired to the top-level Front row choice"
    assert facts[0] in (sc[15].get("when") or {}).get("remembered", [])
    assert not any(o[0] == "remember" and o[1] == facts[0] for ch in sc[13]["choices"][1:] for o in ch["ops"])


def test_a_reply_that_got_cut_off_doesnt_save_half_a_scene(story):
    c, pid, _ = story
    cut = FLUSH.rsplit("either way:", 1)[0].rsplit("** \"I'll tone it down.\"", 1)[0].rstrip("`\n")  # ...and no closing ```
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": cut}).json()
    assert r["got"] == [13, 14] and [s["n"] for s in r["skipped"]] == [15]
    assert dialogue.CUT in r["skipped"][0]["problems"][0]
    assert "Scene 15 (Nicole Hears About It)" in r["fix_prompt"] and "never cut one short" in r["fix_prompt"]
    assert 15 not in _scenes(c, pid), "it isn't in as half a scene"
    nxt = c.get("/api/story/build/batch-prompt", params={"pack": pid}).json()
    assert nxt["first"] == 15, "the next prompt asks for it again"
    # copied without the ``` (ChatGPT's copy button): the last scene stopping right after a choice gives it away
    bare = "--- 15. Nicole Hears About It\nnicole: People are talking.\n* \"Good talk?\"\nnicole: Annoyingly good.\n* \"I can take it down.\""
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": FLUSH.split("--- 15.")[0].split("```\n", 1)[1] + bare}).json()
    assert [s["n"] for s in r["skipped"]] == [15] and "stops right after the choice" in r["skipped"][0]["problems"][0]


def test_whats_missing_is_named_and_goes_to_chatgpt(story):
    c, pid, _ = story
    lazy = """--- 13. Front Row Seats
nicole: You came.
* "Back row's fine."
nicole: Wow. Okay.
* "I can't stay long."
nicole: Seriously?

--- 14. The Banner
nicole: Is that a banner?
* "It is."
nicole: Oh no.
* "No."
* "Maybe."
nicole: Maybe?
"""
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": lazy}).json()
    assert r["got"] == [13, 14] and not r["skipped"]
    gaps = {g["n"]: g["problems"] for g in r["gaps"]}
    assert any("needs a choice like “Front row”" in p and "scene 15" in p for p in gaps[13]), gaps
    assert gaps[14] == ['nothing happens after the choice "No." (the others have lines after them)']
    assert "These went in, but with pieces missing" in r["fix_prompt"] and "Scene 14 (The Banner)" in r["fix_prompt"]


def test_the_prompt_asks_for_three_and_says_which_choice_a_scene_follows(story):
    c, pid, _ = story
    c.post("/api/story/build/scenes", json={"pack": pid, "text": FLUSH.split("--- 14.")[0] + "```"})
    p = c.get("/api/story/build/batch-prompt", params={"pack": pid}).json()
    assert (p["first"], p["last"]) == (14, 16)
    assert 'Scene 15 only happens if I picked "Front row." in scene 13' in p["prompt"], "in the words scene 13 actually has"
    for must in ("down to the next `* `", "`** `", "either way:", "never cut one short"):
        assert must in p["prompt"], must
    one = c.get("/api/story/build/batch-prompt", params={"pack": pid, "count": 1}).json()
    assert "Scene 14: 14. The Banner." in one["prompt"]
