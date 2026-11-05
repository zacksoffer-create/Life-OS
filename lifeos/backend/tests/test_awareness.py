"""Awareness: the game knows who everyone is (who's a guy or a girl, how old, who's family, what team, what's going on)
and so do you, as far as you know them."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import knowing, lines, messages, moments, social  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.story import begin, create_story  # noqa: E402
from tests.test_story import spec  # noqa: E402


def _world(per=10, days=12):
    w = create_story(spec(per=per))
    sim = Simulation(w)
    begin(sim)
    for m in moments.pending(w):
        moments.resolve(sim, m["id"], None)
    sim.advance_days(days)
    return w, sim, w.chars[w.meta["protagonist"]]


def _set(w, a, b, **kv):
    r = w.ensure_rel(a, b, w.day)
    for k, v in kv.items():
        setattr(r, k, float(v))
    return r


def test_you_know_more_about_people_the_better_you_know_them():
    w, sim, me = _world()
    sibs = set(sim.siblings(me.id))
    o = next(c for c in sorted(w.students(), key=lambda c: c.id) if c.id != me.id and c.id not in sibs and c.school == "hchs")
    _set(w, me.id, o.id, familiarity=5, affection=0)
    _set(w, o.id, me.id, trust=10)
    p = knowing.profile(sim, me.id, o.id)
    assert p["level"] == "everyone" and [s["level"] for s in p["sections"]] == ["everyone"]
    assert p["hidden"] > 0 and o.first in p["unlock"]
    keys = {f["k"] for f in p["sections"][0]["facts"]}
    assert {"Year", "Their group", "Dating"} <= keys and not keys & {"Into", "What drives them", "Has a thing for"}
    _set(w, me.id, o.id, familiarity=40, affection=20)
    p = knowing.profile(sim, me.id, o.id)
    assert p["level"] == "know" and "What they're like" in {f["k"] for s in p["sections"] for f in s["facts"]}
    _set(w, me.id, o.id, familiarity=60, affection=55)
    _set(w, o.id, me.id, trust=60)
    p = knowing.profile(sim, me.id, o.id)
    assert p["level"] == "close" and p["hidden"] == 0 and p["unlock"] is None
    assert "What drives them" in {f["k"] for s in p["sections"] for f in s["facts"]}
    sis = next(iter(sibs))
    assert knowing.level(sim, me.id, sis) == "close", "family knows family"


def test_profiles_say_what_people_actually_are():
    w, sim, me = _world()
    team = next(gid for gid in me.memberships if w.groups[gid]["kind"] == "team") if any(
        w.groups[g]["kind"] == "team" for g in me.memberships) else None
    p = knowing.profile(sim, me.id, me.id)
    facts = {f["k"]: f["v"] for s in p["sections"] for f in s["facts"]}
    assert facts["Year"].startswith("Freshman, ")
    if team:
        assert any(w.groups[team]["name"] in f["v"] for s in p["sections"] for f in s["facts"] if f["k"] == "Plays")
    # a couple shows up as dating, for everyone
    a, b = [c for c in w.students() if c.school == "hchs" and c.id != me.id and not c.flags.get("partner")][:2]
    a.flags["partner"], b.flags["partner"] = b.id, a.id
    pa = knowing.profile(sim, me.id, a.id)
    assert {"k": "Dating", "v": b.first} in pa["sections"][0]["facts"]
    assert f"dating {b.first}" in knowing.glance(sim, a.id)
    # your coach isn't a stranger
    coach = next((w.groups[g]["staff"] for g in me.memberships if w.groups[g].get("staff") in w.chars), None)
    if coach:
        assert knowing.level(sim, me.id, coach) in ("know", "close")
    # what's going on: an injury shows up for people who know them
    o = next(c for c in w.students() if c.school == "hchs" and c.id != me.id and c.id not in sim.siblings(me.id))
    o.flags["injured_until"], o.flags["injury"] = w.day + 14, "sprained ankle"
    _set(w, me.id, o.id, familiarity=50, affection=35)
    lately = [f["v"] for s in knowing.profile(sim, me.id, o.id)["sections"] for f in s["facts"] if f["k"] == "Lately"]
    assert any("sprained ankle" in x for x in lately)


def test_check_in_when_something_is_going_on_with_someone_you_know():
    w, sim, me = _world()
    o = next(c for c in w.students() if c.school == "hchs" and c.id != me.id and c.id not in sim.siblings(me.id))
    o.flags["injured_until"], o.flags["injury"] = w.day + 14, "sprained ankle"
    _set(w, me.id, o.id, familiarity=5, affection=0)
    assert not any(x["kind"] == "check_in" for x in messages.text_options(sim, o.id)), "you don't know them"
    _set(w, me.id, o.id, familiarity=50, affection=40)
    opt = next(x for x in messages.text_options(sim, o.id) if x["kind"] == "check_in")
    assert opt["label"] == "Ask how the sprained ankle is"
    messages.add_contact(sim, o.id)
    messages.text_first(sim, o.id, "check_in")
    t = messages.phone(w)["threads"][f"dm:{o.id}"]
    assert any("sprained ankle" in m["text"] for m in t["msgs"] if m["from"] == "me")
    assert t["msgs"][-1]["from"] == o.id and "i'm good" not in t["msgs"][-1]["text"].lower(), "they're hurt: they take it seriously"


def test_lines_know_whos_talking():
    w, sim, me = _world(days=2)
    guy = next(c for c in w.students() if c.gender == "m" and c.id != me.id)
    girl = next(c for c in w.students() if c.gender == "f")
    girl2 = next(c for c in w.students() if c.gender == "f" and c.id != girl.id)
    assert {"from_guy", "to_guy", "guys"} <= lines.identity_tags(w, guy, me)
    t = lines.identity_tags(w, girl, me)
    assert {"from_girl", "to_guy"} <= t and not t & {"guys", "girls"}
    assert "girls" in lines.identity_tags(w, girl, me, group=[girl.id, girl2.id])
    girls_team = [c.id for c in w.students() if c.gender == "f"][:8]
    boys_team = [c.id for c in w.students() if c.gender == "m"][:8]
    said_g = {lines.pick_text(sim, "team_pregame", f"g{i}", frm=girls_team[0], kw={"opp": "Hamden", "_group": girls_team}) for i in range(60)}
    said_b = {lines.pick_text(sim, "team_pregame", f"b{i}", frm=boys_team[0], kw={"opp": "Hamden", "_group": boys_team}) for i in range(60)}
    assert "lock in tomorrow boys" not in said_g and "lock in tomorrow ladies" not in said_b
    assert "lock in tomorrow ladies" in said_g and "lock in tomorrow boys" in said_b
    # "bro" only between guys (chat replies and openers)
    from lifeos import chat
    pool = chat._pool(sim, girl.id, "reply", "plans", "already")
    assert not any("bro" in x for x in pool)
    assert any("bro" in x for x in chat._pool(sim, guy.id, "reply", "plans", "already"))
    for i in range(40):
        assert lines._mod(sim, "open", {"close", "girls"}, f"s{i}") != "bro"


def test_romance_knows_age_family_and_who_youre_into():
    w, sim, me = _world(days=1)
    f9 = next(c for c in w.students() if c.gender == "f" and c.grade == 9 and "m" in c.attracted_to)
    m = {g: next((c for c in w.students() if c.gender == "m" and c.grade == g and "f" in c.attracted_to and c.id != me.id), None)
         for g in (9, 10, 11, 12)}
    assert social.romance_ok(w, f9.id, m[9].id) if m[9] else True
    if m[11]:
        assert social.romance_ok(w, f9.id, m[11].id), "two grades apart is fine"
    if m[12]:
        assert not social.romance_ok(w, f9.id, m[12].id), "a freshman and a senior: no"
        senior = m[12]
        senior.grade = 13  # a college freshman
        f12 = next((c for c in w.students() if c.gender == "f" and c.grade == 12 and "m" in c.attracted_to), None)
        if f12:
            assert social.romance_ok(w, f12.id, senior.id), "a senior and a college freshman"
        f11 = next((c for c in w.students() if c.gender == "f" and c.grade == 11 and "m" in c.attracted_to), None)
        if f11:
            assert not social.romance_ok(w, f11.id, senior.id), "a junior and a college student: no"
    sis = next(s for s in sim.siblings(me.id) if w.chars[s].gender == "f")
    assert not social.romance_ok(w, me.id, sis), "never family"
    coach = next(c for c in w.chars.values() if c.role == "staff")
    assert not social.romance_ok(w, me.id, coach.id)
    other = next(c for c in w.students() if c.gender == "m" and c.id != me.id and c.grade == me.grade)
    if "m" not in me.attracted_to:
        assert not social.romance_ok(w, me.id, other.id)


def test_clique_names_fit_whos_in_them():
    w, sim, me = _world(days=1)
    girls = [c.id for c in w.students() if c.gender == "f"][:4]
    mixed = girls[:2] + [c.id for c in w.students() if c.gender == "m"][:2]
    fr = [c.id for c in w.students() if c.grade == 9][:4]
    for cid in girls + mixed:
        w.chars[cid].interests = {"softball": 95}
    assert social.clique_name(w, girls, "qx") == "the Bat Girls"
    assert social.clique_name(w, mixed, "qy") != "the Bat Girls"
    for cid in fr:
        w.chars[cid].popularity = 95
    assert social.clique_name(w, fr, "qz") != "the Senior Lot Crowd"


def test_the_phone_contact_page_has_who_they_are():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    for m in moments.pending(api.lab.w):
        moments.resolve(api.lab.sim, m["id"], None)
    groups = c.get("/api/phone/contacts").json()["groups"]
    row = groups[0]["people"][0]
    assert row["glance"].startswith(row["year_label"])
    prof = c.get(f"/api/phone/contact/{row['id']}").json()
    assert prof["who"]["sections"] and prof["who"]["glance"] == row["glance"]
