"""Every storyline scene asks you something: the prompt hands ChatGPT a template with the question and the choices built
in, a scene that comes back without them (no choices, or just one) is named with a fix-it message, template lines left
unfilled come out, and the storylines you're writing are listed with how far along each is."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_scene_import import own_packs, story  # noqa: E402,F401

FILLED = """```
--- 13. Front Row Seats
<a line or two of setup>
The gym is packed. Nicole spots you from the court.
nicole: You actually came.
nicole: So where are you sitting?
* "Front row." | nicole affection +
nicole: Front row, then. Come on.
* "Back row's fine."
nicole: Wow. Okay.
* "<choice 3>"
<what happens after it: their answer, 2 to 5 lines>

--- 14. The Banner
nicole: Please tell me that's not a banner.
nicole: It is. It has my face on it.
nicole: I'm going to die.

--- 15. Nicole Hears About It
nicole: People are talking about my brother.
* "Good talk?"
nicole: Annoyingly good.
```"""


def test_the_batch_prompt_is_a_template_with_the_question_and_choices_built_in(story):
    c, pid, _ = story
    b = c.get(f"/api/story/build/batch-prompt?pack={pid}&count=3").json()
    assert b["first"] == 13 and b["last"] == 15
    tpl = b["prompt"].split("## Fill in this template", 1)[1].split("Reply with ONE", 1)[0]
    for n, t in zip(range(13, 16), b["titles"]):
        assert f"--- {n}. {t}" in tpl
    assert tpl.count("<the question: someone asks me something, or it's my move>") == 3
    assert tpl.count('* "<choice 2>"') == 3
    assert "ENDS ON A QUESTION" in b["prompt"] and "doesn't count as written" in b["prompt"]


def force(pid, text):
    """Scenes that are already in, from before the rule (put straight into the file, the way old storylines have them)."""
    from lifeos import dialogue
    assert dialogue.add_script(dialogue.script_of(pid).rstrip("\n") + "\n\n" + text.strip("`\n") + "\n", into=pid)["ok"]


def test_a_scene_without_its_decision_cant_go_in_and_unfilled_template_lines_come_out(story):
    c, pid, _ = story
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": FILLED})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["got"] == [13, 15]  # 14 never asks you anything: it can't go in
    left = {s["n"]: " ".join(s["problems"]) for s in j["skipped"]}
    assert list(left) == [14] and "never asks you anything" in left[14]
    assert "only has one choice" in " ".join(g["problems"][0] for g in j["gaps"] if g["n"] == 15)  # in, but flagged
    assert j["written"] == 14
    assert "Every scene ends on a question" in j["fix_prompt"] and "Scene 14 (The Banner):" in j["fix_prompt"]
    from tests.test_scene_import import _scenes
    sc = _scenes(c, pid)[13]
    assert [ch["label"].strip('"') for ch in sc["choices"]] == ["Front row.", "Back row's fine."]  # the unfilled third came out
    assert "<" not in str(sc)
    assert any("template line left unfilled" in n for n in j["notes"])
    # the next prompt asks for them again
    b = c.get(f"/api/story/build/batch-prompt?pack={pid}&count=3").json()
    assert b["first"] == 14


def test_a_rewrite_without_its_decision_leaves_the_scene_as_it_was(story):
    c, pid, _ = story
    from tests.test_scene_import import _scenes
    before = _scenes(c, pid)[12]["choices"]
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": "--- 12. x\nnicole: hi\nnicole: bye\n"}).json()
    assert 12 in [s["n"] for s in r["skipped"]] and _scenes(c, pid)[12]["choices"] == before


def test_the_storylines_you_are_writing_and_a_checkup_of_one(story):
    c, pid, _ = story
    force(pid, FILLED)  # (from before the rule: they're in, broken)
    rows = c.get("/api/story/build/writing").json()["storylines"]
    me = next(x for x in rows if x["pack"] == pid)
    assert me["written"] == 15 and me["total"] >= 15 and me["needs_fixing"] >= 2 and "stuck" in me
    ck = c.get(f"/api/story/build/checkup?pack={pid}").json()
    assert {14, 15} <= {g["n"] for g in ck["gaps"]} and ck["fix_prompt"]
    fixed = """--- 14. The Banner
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
"""
    c.post("/api/story/build/scenes", json={"pack": pid, "text": fixed})
    ck = c.get(f"/api/story/build/checkup?pack={pid}").json()
    assert not {14, 15} & {g["n"] for g in ck["gaps"]}


def test_pasting_or_inserting_a_scene_without_its_decision_leaves_just_that_one_out(story):
    c, _, _ = story
    from lifeos import dialogue
    text = """=== Bus Rides Two
cast: sis = Nicole Soffer
years: freshman

--- Lunch
sis: You sitting with us?
* "Yeah."
sis: Okay.
* "No."
sis: Fine.

--- The Bus
sis: Move over.
sis: I said move.
"""
    ck = c.post("/api/dialogue/check", json={"text": text}).json()
    assert [x["title"] for x in ck["left_out"]] == ["The Bus"] and "never asks you anything" in ck["warnings"][0]
    r = c.post("/api/dialogue/packs", json={"text": text})
    assert r.status_code == 200, r.text
    pid = r.json()["added"]
    assert "The Bus" not in dialogue.script_of(pid) and "Lunch" in dialogue.script_of(pid)
    assert any("didn't go in" in n for n in r.json()["notes"])
    only_bad = text.replace("=== Bus Rides Two", "=== Bus Rides Three").split("--- Lunch")[0] + "--- The Bus\nsis: Move over.\n"
    assert c.post("/api/dialogue/packs", json={"text": only_bad}).status_code == 422
    # adding a scene right where it goes: same rule, and the scenes already there are left alone
    r = dialogue.insert_scenes(pid, None, "--- Parking Lot\nsis: Get in.\n")
    assert not r["ok"] and "didn't go in" in r["errors"][0]
    r = dialogue.insert_scenes(pid, None, "--- Parking Lot\nsis: Get in.\n* \"Shotgun.\"\nsis: Fine.\n* \"I'll walk.\"\nsis: Bye.\n")
    assert r["ok"] and "Parking Lot" in dialogue.script_of(pid)


def test_a_branch_finds_its_choice_when_the_scene_says_it_in_a_line(story):
    """The outline says "Ask her on a proper date"; the scene says "Nikki, I really like you. Will you go on a proper date
    with me?". That's the choice: no fix-it needed, and the next scene only comes after it."""
    c, _, _ = story
    outline = """=== Proper Date
cast: jen = Jennifer Soffer
years: freshman

outline:
1. The Talk | September | You and Jen on the beach.
2. The Date | October | Your first real date. | only if you picked "Ask her on a proper date" in 1
"""
    pid = c.post("/api/story/build/outline", json={"text": outline, "save": True}).json()["pack"]
    scenes = """--- 1. The Talk
jen: So where do we go from here?
* "Jen, I really like you. Will you go on a proper date with me?" | jen attraction ++
jen: Yes!
* "I want to see where this goes. We don't have to rush anything."
jen: I like that.
* "I need a little more time before we change anything."
jen: Okay.

--- 2. The Date
jen: You actually wore a collared shirt.
* "For you."
jen: Stop.
* "My mom made me."
jen: Of course she did.
"""
    r = c.post("/api/story/build/scenes", json={"pack": pid, "text": scenes}).json()
    assert r["got"] == [1, 2] and r["gaps"] == [], r["gaps"]
    assert c.get(f"/api/story/build/checkup?pack={pid}").json()["gaps"] == []
    p = dialogue_pack(pid)
    first, date = p["scenes"][0], p["scenes"][1]
    fact = (date.get("when") or {}).get("remembered")
    assert fact  # the date waits for the choice
    ops = [op for op in first["choices"][0].get("ops") or [] if op and op[0] == "remember"]
    assert any(fact[0] in op for op in ops) or any(fact in op for op in ops)
    others = [op for ch in first["choices"][1:] for op in ch.get("ops") or [] if op and op[0] == "remember"]
    assert not any(str(fact[0] if isinstance(fact, list) else fact) in map(str, op) for op in others)


def dialogue_pack(pid):
    from lifeos import dialogue
    return dialogue._script_pack(pid)["pack"]


def test_choice_words_match_only_when_its_clear():
    from lifeos import script as SC
    sc = {"choices": [{"label": '"Nikki, I really like you. Will you go on a proper date with me?"'},
                      {"label": '"I want to see where this goes with you. We don\'t have to rush anything."'},
                      {"label": '"I like you more than a friend, but I need a little more time before we change anything."'}]}
    assert SC.find_choice(sc, "Ask her on a proper date")[0] == 0
    assert SC.find_choice(sc, "Ask for more time")[0] == 2
    assert SC.find_choice(sc, "Tell her you like her") is None  # two of them say "like you": not clear, so no guess
    assert SC.find_choice({"choices": [{"label": '"Back row\'s fine."'}, {"label": '"I can\'t stay long."'}]}, "Front row") is None
