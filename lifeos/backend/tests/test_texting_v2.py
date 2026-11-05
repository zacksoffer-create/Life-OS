"""Texting that's fun: flirting that goes back and forth and somewhere, people who flirt first (and a kind way to say
no), and group chats where people talk to each other and you can jump in."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import chat, groupchat, messages  # noqa: E402
from tests.test_chat import _setup  # noqa: E402


def _flirt(sim, g):
    sug = chat.suggestions(sim, g)
    i = next(k for k, s in enumerate(sug) if s["intent"] == "flirt")
    return sug, chat.send(sim, g, suggestion=i)


def test_a_flirt_that_lands_gets_follow_ups_that_build_on_it_and_goes_somewhere():
    w, sim, me, g = _setup(70, 70, 60)
    w.chars[g].mood = 85.0
    _, r = _flirt(sim, g)
    assert r["result"] == "flirt_landed", r
    sug = chat.suggestions(sim, g)
    moves = [s.get("banter") for s in sug]
    assert "cool" in moves and len([m for m in moves if m in chat.STYLES]) == 2, sug
    assert all(s["text"] for s in sug)
    before = w.rels[(g, me.id)].attraction
    went = None
    for _ in range(3):
        sug, r = _flirt(sim, g)
        if r["why"] and r["why"].startswith("That went somewhere"):
            went = r["why"]
            break
    assert went, "a few good beats in a row go somewhere"
    assert w.rels[(g, me.id)].attraction > before
    assert chat.suggestions(sim, g) and not any(s.get("banter") for s in chat.suggestions(sim, g)), "once it paid off, it's a normal chat again"


def test_they_can_flirt_first_and_you_can_let_them_down_easy():
    w, sim, me, g = _setup(60, 55, 40)
    messages.later(sim, g, "chat_flirt_in", delay_phases=0, text=chat.flirt_in_line(sim, g), ctx={"fast": True})
    messages.tick(sim)
    t = messages.phone(w)["threads"][f"dm:{g}"]
    assert t["msgs"][-1]["kind"] == "chat_flirt_in" and t["msgs"][-1]["text"]
    sug = chat.suggestions(sim, g)
    moves = [s.get("banter") for s in sug]
    assert "letdown" in moves and "cool" in moves, sug
    before = w.rels[(g, me.id)].attraction
    r = chat.send(sim, g, suggestion=moves.index("letdown"))
    assert r["result"] == "letdown" and "down easy" in r["why"]
    assert w.rels[(g, me.id)].attraction < before


def test_no_flirting_with_family():
    w, sim, me, g = _setup(60, 55, 40)
    sib = sim.siblings(me.id)[0]
    messages.add_contact(sim, sib)
    messages.later(sim, sib, "chat_flirt_in", delay_phases=0, text="hey", ctx={})
    messages.tick(sim)
    assert not any(s.get("banter") for s in chat.suggestions(sim, sib))


def _crew(sim, w, me, n=3):
    friends = [c.id for c in w.students() if c.id != me.id and c.household_id != me.household_id][:n]
    w.meta["squad"] = {"ids": friends, "cohesion": 50.0, "formed": w.day, "updated": w.day, "last_you": None, "jokes": [], "name": "the crew"}
    return friends


def test_a_group_chat_talks_and_you_can_jump_in(monkeypatch):
    w, sim, me, g = _setup(10, 40, 20)
    friends = _crew(sim, w, me)
    data = groupchat.D()
    monkeypatch.setattr(groupchat, "_DATA", {"bursts": [b for b in data["bursts"] if b["id"] == "haircut"]})
    assert groupchat.start(sim, "crew")
    t = messages.phone(w)["threads"]["squad"]
    burst = [m for m in t["msgs"] if m["kind"] == "burst"]
    assert len(burst) == 5 and len({m["from"] for m in burst}) == 3 and set(m["from"] for m in burst) <= set(friends)
    assert burst[-1]["replies"] and len(burst[-1]["replies"]) == 3 and all(m["replies"] is None for m in burst[:-1])
    def mins(at):
        hm, ampm = at.split(" ")
        hh, mm = (int(x) for x in hm.split(":"))
        return (hh % 12 + (12 if ampm == "PM" else 0)) * 60 + mm
    assert [mins(m["at"]) for m in burst] == sorted(mins(m["at"]) for m in burst), "they land in order"
    v = messages.thread_view(sim, "squad", mark_read=True)
    assert v["fresh"] == 5 and messages.thread_view(sim, "squad", mark_read=True)["fresh"] == 0
    inst = burst[-1]["replies"][1]["fx"].split(":")[1]
    cast = t["bursts"][inst]["cast"]
    b_before = w.rels[(cast["B"], me.id)].affection
    a_before = w.rels[(cast["A"], me.id)].affection
    r = messages.reply(sim, "squad", burst[-1]["id"], 1)  # "it looks like someone did it in the dark"
    said = [m["text"] for m in r["thread"]["msgs"][-4:]]
    assert said[0] == "it looks like someone did it in the dark" and "LMAOOO" in said[1]
    assert w.rels[(cast["B"], me.id)].affection < b_before and w.rels[(cast["A"], me.id)].affection > a_before
    side = [x for x in messages.phone(w)["pending"] if x["key"] == "chat_side"]
    assert side and side[0]["from"] == cast["B"], "the one you roasted DMs you after"


def test_the_team_chat_talks_about_the_game_and_the_family_chat_has_parents():
    w, sim, me, g = _setup(10, 40, 20)
    team = next((w.groups[x] for x in me.memberships if x in w.groups and w.groups[x]["kind"] == "team"), None)
    if team is not None and len([m for m in team["members"] if m != me.id]) >= 3:
        assert groupchat.start(sim, "team", {"pregame"}, group=team, opp="Hamden")
        t = messages.phone(w)["threads"][f"team:{team['id']}"]
        last = next(b for b in reversed(groupchat.D()["bursts"]) if b["id"] == list(t["bursts"].values())[-1]["id"])
        assert "pregame" in last.get("when", [])
    assert groupchat.start(sim, "family")
    fam = [m for m in messages.phone(w)["threads"]["family"]["msgs"] if m["kind"] == "burst"]
    assert fam and any(m["from"].startswith("parent") for m in fam)


def test_group_chats_happen_on_their_own():
    w, sim, me, g = _setup(10, 40, 20)
    _crew(sim, w, me)
    for _ in range(12):
        sim.advance_days(1)
        w.meta["squad"]["updated"] = w.day  # keep the test crew
    kinds = [m["kind"] for t in messages.phone(w)["threads"].values() for m in t["msgs"]]
    assert kinds.count("burst") >= 4
