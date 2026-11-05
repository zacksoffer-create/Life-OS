"""Packs always load: texting lines merge with the built-in ones however they're written, and one pack that can't load
never keeps the game from opening."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import chat, dialogue, messages, moments  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.story import begin, create_story  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


TEXTING = {"dialogue_pack": 1, "name": "Texting lines", "chat": {
    # the places where the built-in lists hold lines with a context ({"text": ..., "when": [...]})
    "reply": {"plans": {"already": ["we literally already have plans lol"]}, "support": {"thanks": ["ok that actually helped"]}},
    "recent": {"group": ["still thinking about last night"]},
    "ask": {"general": [{"q": "you going to the bonfire friday?", "a": "yesno"}]},
    "people": {"older_sibling": {"recent": {"group": ["mom asked where we were. i covered"]}}}}}


def test_a_texting_pack_loads_next_to_lines_with_a_context():
    assert dialogue.check(TEXTING)["ok"]
    dialogue.add_pack(TEXTING)
    dialogue.reload()
    m = dialogue.merged()  # this crashed opening the game ("KeyError: 'q'")
    assert not m["load_errors"]
    already = m["chat"]["reply"]["plans"]["already"]
    assert "we literally already have plans lol" in already and any(isinstance(x, dict) and "bro" in x["text"] for x in already)
    assert "still thinking about last night" in m["chat"]["recent"]["group"]
    assert any(isinstance(x, dict) and x.get("q") == "you going to the bonfire friday?" for x in m["chat"]["ask"]["general"])
    dialogue.add_pack(TEXTING)  # the same lines again don't double up
    dialogue.reload()
    assert dialogue.merged()["chat"]["recent"]["group"].count("still thinking about last night") == 1


def test_questions_people_text_you_are_real_questions():
    dialogue.add_pack(TEXTING)
    dialogue.reload()
    sim = Simulation(create_story(spec(per=6)))
    begin(sim)
    for m in moments.pending(sim.w):
        moments.resolve(sim, m["id"], 0)
    w = sim.w
    me = w.chars[w.meta["protagonist"]]
    o = next(c for c in w.students() if c.id != me.id and c.id not in sim.siblings(me.id))
    pool = chat._pool(sim, o.id, "ask", "general")
    assert pool and all(isinstance(x, dict) and x.get("q") for x in pool), "questions keep their text and their kind of answer"
    messages.add_contact(sim, o.id)
    for k in ("familiarity", "affection"):
        setattr(w.ensure_rel(o.id, me.id, w.day), k, 70.0)
        setattr(w.ensure_rel(me.id, o.id, w.day), k, 70.0)
    for _ in range(6):
        chat.send(sim, o.id, "what are you up to tonight?")
    asks = [m for m in messages.phone(w)["threads"][f"dm:{o.id}"]["msgs"] if m.get("kind") == "chat_ask"]
    assert all(m["text"].strip() for m in asks), "no empty texts"


def test_one_broken_pack_never_keeps_the_game_from_opening(monkeypatch):
    dialogue.add_pack(TEXTING)
    dialogue.add_pack({"dialogue_pack": 1, "name": "Fine pack", "texts": {"chatter_school": ["did anyone do the reading"]}})
    dialogue.reload()
    real = dialogue._merge_chat

    def broken(into, add):
        if "we literally already have plans lol" in str(add):
            raise KeyError("q")
        return real(into, add)
    monkeypatch.setattr(dialogue, "_merge_chat", broken)
    dialogue.reload()
    m = dialogue.merged()
    bad = [pid for pid in m["load_errors"]]
    assert len(bad) == 1 and "texting" in bad[0]
    assert any("chatter_school" in k for k in m["texts"]) and "did anyone do the reading" in [str(x) for x in m["texts"]["chatter_school"]]
    card = next(dialogue.pack_summary(p) for p in dialogue.packs() if p["id"] == bad[0])
    assert not card["ok"] and "couldn't load it" in card["errors"][0]


def test_a_season_plan_with_a_long_authored_gap_loads():
    plan = {"dialogue_pack": 1, "name": "Season plan",
            "schedule": {"bro_team_37_same_team": {"years": ["college_senior"], "after": ["bro_team_36_two_adults"], "gap_days": 550}}}
    r = dialogue.check(plan)
    assert r["ok"], r["errors"]
    plan["schedule"]["bro_team_37_same_team"]["gap_days"] = 4000
    assert not dialogue.check(plan)["ok"]
