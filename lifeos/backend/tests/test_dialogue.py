"""Dialogue packs: checking, loading, merging, and scenes that happen in the story."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, messages, moments  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.story import begin, create_story  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    """Every test gets an empty folder for 'your' packs (the built-in starter pack still loads)."""
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


EVERYDAY = """
=== Everyday life
order: any
about: Small moments at home and school.

--- {older sibling} needs a favor #cover_for_me  [freshman-junior · school day · 5% · with older sibling]
{older sibling} leans into your doorway, already whispering.
older sibling: If anyone asks, I was at the library till eleven. Deal?
* Deal. You owe me.                          | older sibling affection ++, remember covered_for_sibling, fits loyalty
    older sibling: Legend.
* No way. I'm not lying for you.             | older sibling affection -, fits discipline
    older sibling: Wow. Okay. Remember this.
* Only if you drive me to practice all week. | 50% +charisma
    yes: older sibling: ...Fine. Seven sharp. | older sibling respect +
    no: older sibling: Forget it.            | older sibling affection -

--- The library story #cover_story_falls_apart  [if covered_for_sibling · school day · 6% · with older sibling]
Your parents are at the kitchen table with a phone face up between them.
Mom: Funny thing. The library closes at eight.
* Stick to the story.                        | 40% +charisma, fits loyalty
    yes: They don't buy it, but they let it go. | older sibling trust ++, forget covered_for_sibling
    no: "Nice try. You're both on dishes for a week." | stress +, forget covered_for_sibling
* Come clean.                                | older sibling affection --, forget covered_for_sibling, text older sibling "seriously??"
    {older sibling} gets the lecture.

--- {pet} got out #pet_got_out  [if has pet · 3%]
Someone left the side gate open. {pet} is three yards away and very proud of it.
* Sprint after them.                         | 45% +athletic
    yes: You catch {pet} two streets over.    | energy -, mood +
    no: {pet} thinks this is the best game ever invented. | energy --, stress +
* Grab the treat bag and shake it.           | 70%
    yes: {pet} trots right back.              | mood +
    no: Apparently the neighbor's yard is better than treats. | stress +
* Get {sibling} to help corner them.         | family affection +
    {sibling} cuts across the lawn. Teamwork.

--- Your hoodie is missing #hoodie_thief  [4% · with sibling]
Your favorite hoodie isn't in your drawer. Then {sibling} walks past your door wearing it.
* Let it go.                                 | sibling affection +
    sibling: Thank you for your donation.
* Steal their charger back.                  | fun +

--- Halloween #halloween_plans  [Oct 31 · high school · repeats every 300 days · with best friend]
best friend: {Okay. What are we doing tonight?|It's Halloween. We're doing something. What?}
* Party at a senior's house.                 | 55% +sociability
    yes: Half the school is there.            | fun ++, social +, best friend affection +
    no: The cops show up at 10:30.            | fun +, stress +
* Scary movies at your place.                | best friend affection ++, fun +
* Hand out candy and eat most of it.         | fun +

--- Test tomorrow #test_tomorrow  [school day · often · repeats every 20 days · with friend]
friend: did u study for tomorrow
* "Obviously."                               | academics +
* "...there's a test?"                       | stress +

--- Lunch line #lunch_line  [school day · often · repeats every 20 days · with best friend]
best friend: They ran out of fries. This is the worst day of my life.
* Split yours.                               | best friend affection +
* "Character building."                      | fun +
"""


def install():
    r = dialogue.add_script(EVERYDAY)
    assert r["ok"], r["errors"]
    return r


def story(**kw):
    s = spec(per=6, **kw)
    sim = Simulation(create_story(s))
    begin(sim)
    for m in moments.pending(sim.w):
        moments.resolve(sim, m["id"], 0)
    return sim


def test_built_in_packs_are_clean_and_the_guide_lists_everything():
    for p in dialogue.packs():
        assert p["check"]["ok"], (p["id"], p["check"]["errors"])
    from lifeos import script
    g = dialogue.guide_markdown()
    for must in ("chatter_school", "sibling_tease", "older sibling", "if <fact>", "remember", "hang_out", "choices <moment>:",
                 "texts <pool>:", "chat <path>:", "schedule:", "{a|b}"):
        assert must in g, must
    assert dialogue.prompt_for_ai().startswith("You're writing for LIFE OS")
    shape = g.split("## The shape")[1].split("```")[1]
    assert not script.compile_script(shape)["errors"], "the guide's own example loads"


def test_check_explains_mistakes_in_plain_words():
    bad = {"name": "oops", "texts": {"chater_school": ["x"], "invite": ["come to {placee}"]},
           "replies": {"chatter_plans": [["ok", "happy"]]},
           "scenes": [{"id": "x1x", "who": "bff", "title": "t", "text": "t", "when": {"chanse": 0.1},
                       "choices": [{"label": "a", "ops": [["moood", 2]]}]}]}
    r = dialogue.check(bad)
    msg = " | ".join(r["errors"])
    assert not r["ok"]
    for frag in ("Did you mean chatter_school", "{placee}", "'happy' isn't a tone", "'bff' isn't a kind of person",
                 "Did you mean chance", "Did you mean mood"):
        assert frag in msg, frag


def test_a_pack_pasted_from_chatgpt_loads_and_adds_lines():
    answer = "Here you go!\n```json\n" + json.dumps({
        "dialogue_pack": 1, "name": "More school texts",
        "texts": {"chatter_school": ["did u start the lab report", "is the quiz today or tmrw"]},
        "replies": {"chatter_school": [["on it", "warm"], ["what lab report 💀", "funny"]]},
    }) + "\n```\nLet me know if you want more."
    pack = dialogue.parse_text(answer)
    r = dialogue.add_pack(pack)
    assert r["ok"] and r["id"] == "yours:more_school_texts"
    assert "did u start the lab report" in messages.T()["chatter_school"]
    labels = [l for l, _ in dialogue.reply_sets()["chatter_school"]]
    assert "what lab report 💀" in labels
    for salt in ("a", "b", "c", "d"):
        opts = messages._replies("chatter_school", salt)
        assert len(opts) == 3 and len({o["fx"] for o in opts}) >= 2
    dialogue.set_enabled("yours:more_school_texts", False)
    assert "did u start the lab report" not in messages.T()["chatter_school"]
    dialogue.set_enabled("yours:more_school_texts", True)
    dialogue.remove_pack("yours:more_school_texts")
    assert not any(p["id"] == "yours:more_school_texts" for p in dialogue.packs())
    with pytest.raises(ValueError):
        dialogue.remove_pack("builtin:anything")
    with pytest.raises(ValueError):
        dialogue.parse_text("sorry, I can't help with that")


def test_scenes_play_with_dialogue_texts_and_follow_ups():
    install()
    sim = story()
    m = dialogue.try_scene(sim, "cover_for_me")
    them = m["ctx"]["them"]
    assert sim.w.chars[them].first in m["title"] and "{" not in m["text"]
    ev = moments.resolve(sim, m["id"], 0)
    assert ev["data"]["say"] and "Legend" in ev["data"]["say"][0]
    assert sim.w.meta["remembered"]["covered_for_sibling"]["them"] == them
    m2 = dialogue.try_scene(sim, "cover_story_falls_apart")
    assert m2["ctx"]["them"] == them, "the follow-up is about the same sibling"
    moments.resolve(sim, m2["id"], 1)
    assert "covered_for_sibling" not in sim.w.meta["remembered"]
    for _ in range(4):
        sim.step()
    t = messages.phone(sim.w)["threads"].get(f"dm:{them}")
    assert t and any(x["text"] == "seriously??" or "seriously" in x["text"] for x in t["msgs"])


def test_a_choice_that_needs_someone_only_shows_when_they_exist():
    install()
    s = spec(per=6)
    s["siblings"] = []
    s["family"]["pet"] = {"species": "dog", "name": "Scout"}
    sim = Simulation(create_story(s))
    begin(sim)
    for m in moments.pending(sim.w):
        moments.resolve(sim, m["id"], 0)
    m = dialogue.try_scene(sim, "pet_got_out")
    labels = [c["label"] for c in m["choices"]]
    assert len(labels) == 2 and not any("corner" in x for x in labels)
    with pytest.raises(ValueError):
        dialogue.try_scene(sim, "hoodie_thief")  # needs a sibling


def test_scenes_happen_on_their_own_and_dated_ones_get_their_day():
    from lifeos import calendar as calm
    install()
    sim = story()
    w = sim.w
    while calm.date_of(w.day) <= calm.date_of(0).replace(month=11, day=1):
        for m in moments.pending(w):
            if m["kind"] != "halloween_plans":
                moments.resolve(sim, m["id"], None)
        sim.step()
    seen = w.meta.get("scenes_seen", {})
    assert seen.get("halloween_plans") and str(calm.date_of(seen["halloween_plans"][0])).endswith("10-31")
    assert len(seen) >= 3


def test_dialogue_api_and_the_phone_engine_layer(tmp_path):
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    assert not c.get("/api/dialogue/packs").json()["packs"], "the game ships no packs: you write them"
    r = c.post("/api/dialogue/packs", json={"text": "Sure! Here it is:\n```\n" + EVERYDAY + "```"})
    assert r.status_code == 200 and r.json()["ids"] == ["yours:everyday_life"]
    j = c.get("/api/dialogue/packs").json()
    assert any(p["id"] == "yours:everyday_life" and p["enabled"] and p["kind"] == "script" for p in j["packs"]) and "test_tomorrow" in j["scenes"]
    src = c.get("/api/dialogue/packs/yours%3Aeveryday_life/script").json()["text"]
    assert src.startswith("=== Everyday life")
    typo = c.post("/api/dialogue/packs/yours%3Aeveryday_life/script", json={"text": src.replace("| fun +", "| fnu +", 1)})
    assert typo.status_code == 200 and "'fnu' read as 'fun'" in " ".join(typo.json()["notes"]) and "fnu" not in typo.json()["text"]
    bad = c.post("/api/dialogue/packs/yours%3Aeveryday_life/script", json={"text": src.replace("| fun +", "| zzqx +", 1)})
    assert bad.status_code == 200 and "the effect 'zzqx +' came off" in " ".join(bad.json()["notes"])
    ok = c.post("/api/dialogue/packs/yours%3Aeveryday_life/script", json={"text": src.replace("Lunch line", "The lunch line")})
    assert ok.status_code == 200 and ok.json()["ids"] == ["yours:everyday_life"]
    chk = c.post("/api/dialogue/check", json={"text": EVERYDAY.replace("with best friend]", "with besty]")}).json()
    assert chk["ok"] and chk["notes"] and "with besty" not in chk["fixed"], chk["notes"]  # what adding it would fix
    bad = c.post("/api/dialogue/packs", json={"text": '{"name": "x", "texts": {"nope": ["hi"]}}'})
    assert bad.status_code == 422 and bad.json()["errors"]
    good = {"name": "Snow day", "scenes": [{
        "id": "snow_day", "who": "best_friend", "when": {"months": [1, 2]}, "title": "Snow day",
        "text": "{them_first}: \"SCHOOL'S CANCELLED\"",
        "choices": [{"label": "Sledding.", "ops": [["need", "fun", 8], ["say", "Best day of the year."]]},
                    {"label": "Sleep till noon.", "ops": [["need", "energy", 10]]}]}]}
    assert c.post("/api/dialogue/check", json={"pack": good}).json()["ok"]
    r = c.post("/api/dialogue/packs", json={"pack": good})
    assert r.status_code == 200 and "snow_day" in r.json()["scenes"]
    t = c.post("/api/dialogue/try/snow_day")
    assert t.status_code == 200 and t.json()["moment"]["title"] == "Snow day"
    assert c.post("/api/dialogue/packs/yours%3Asnow_day/enabled", json={"enabled": False}).status_code == 200
    assert "snow_day" not in c.get("/api/dialogue/packs").json()["scenes"]
    assert c.post("/api/dialogue/packs/builtin%3Anothing/remove").status_code == 409
    assert c.post("/api/dialogue/packs/yours%3Asnow_day/remove").status_code == 200
    assert c.post("/api/dialogue/packs/yours%3Aeveryday_life/remove").status_code == 200
    assert "texts <pool>:" in c.get("/api/dialogue/guide.md").text and "# LIFE OS story scripts" in c.get("/api/dialogue/guide").json()["text"]
    assert "texts" in c.get("/api/dialogue/current").json()
    assert len(c.get("/api/dialogue/prompt").json()["prompt"]) > 5000


def test_every_line_two_ways_with_context_mods_and_no_repeats():
    pack = {
        "dialogue_pack": 1, "name": "Two ways",
        "texts": {
            "chatter_school": [
                "did u do the reading",
                {"text": "u up? i can't do this essay", "when": ["late_night"]},
                {"text": "notes pls", "talk": "\"Can I see your notes?\" {them_first} asks, already reaching for them."},
            ],
            "hang_talk": [{"text": "this is the best idea you've had all year", "when": ["close"]}],
        },
        "mods": {"open": {"close": ["okay real question"]}, "close": {"any": ["fr fr"]}, "talk": {"happy": ["{them_first} {says}, practically bouncing"]}},
        "scenes": [{
            "id": "two_way_scene", "who": "friend", "when": {"chance": 0.01},
            "title": "{them_first} has a plan",
            "text": ["{them_first} slides into the seat next to you. \"I have a plan.\"", "{them_first} catches you after class. \"Okay. I have a plan.\"",
                     "\"Don't say no yet,\" {them_first} says, falling into step with you."],
            "by_text": ["ok i have a plan. don't say no yet", "hear me out. i have a plan"],
            "choices": [{"label": "I'm in.", "ops": [["say", ["\"Knew it,\" {them_first} says.", "{them_first} fist-bumps you."]]]},
                        {"label": "Absolutely not.", "ops": [["mood", -1]]}],
        }],
    }
    r = dialogue.check(pack)
    assert r["ok"], r["errors"]
    assert r["summary"]["mods"] == 3 and r["summary"]["texts"] == 4
    bad = dialogue.check({"name": "x", "texts": {"chatter_school": [{"text": "hi", "when": ["midnight"]}]},
                          "mods": {"talk": {"any": ["says it slowly"]}, "open": {"sometimes": ["yo"]}}})
    msgs = " ".join(bad["errors"])
    assert "midnight" in msgs and "them_first" in msgs and "sometimes" in msgs
    assert dialogue.add_pack(pack)["ok"]
    sim = story()
    w = sim.w
    me = w.chars[w.meta["protagonist"]]
    friend = next(o for o in w.out[me.id] if w.chars[o].role != "staff" and o not in sim.siblings(me.id))
    from lifeos import lines, narrative
    # texts from one friend on one day: never the same line twice while there's anything else
    n = min(8, len(dialogue.texts()["chatter_school"]))
    got = [lines.pick_text(sim, "chatter_school", f"s{i}", frm=friend) for i in range(n)]
    base = [lines.speakable(x).lower() for x in got]
    assert len(set(got)) == len(got), got
    assert len({lines.hid(x) for x in got}) == n and len(base) == n
    # context: a parent is family, late at night is late_night
    assert {"family", "parent"} <= lines.tags_for(sim, "parent1")
    assert "late_night" in lines.tags_for(sim, friend, phase="night")
    # the spoken version of a text: spelled out, in quotes, with who said it
    sp = lines.spoken(sim, lines.entry("u coming tmrw?"), friend, "x")
    assert sp.startswith("\"You coming tomorrow?\"") and w.chars[friend].first in sp and " asks" in sp
    assert lines.spoken(sim, lines.entry({"text": "notes pls", "talk": "\"Notes?\" {them_first} asks."}), friend, "y") == f"\"Notes?\" {w.chars[friend].first} asks."
    # versions rotate before they repeat
    vs = [lines.variant(sim, "test:v", ["a", "b", "c"], f"v{i}") for i in range(3)]
    assert sorted(vs) == ["a", "b", "c"]
    # a scene written both ways, happening by text: their message lands in your phone and the choices are your replies
    m = dialogue.try_scene(sim, "two_way_scene")
    them = m["ctx"]["them"]
    assert "{" not in m["text"]
    m["by_text"] = "ok i have a plan. don't say no yet"
    messages.moment_text(sim, m)
    t = messages.phone(w)["threads"][f"dm:{them}"]
    msg = t["msgs"][-1]
    assert msg["text"].lower().startswith("ok i have a plan") and [r["label"] for r in msg["replies"]] == ["I'm in.", "Absolutely not."]
    messages.reply(sim, t["id"], msg["id"], 1)
    assert next(x for x in w.meta["moments"] if x["id"] == m["id"])["status"] != "pending"
    # in person: hanging out with you, they say something in the story feed
    said = None
    for eid in range(1, 40):
        ev = {"id": 90_000 + eid, "type": "interact.hang_out", "outcome": "great", "actors": [me.id], "targets": [friend], "data": {"place": "the beach"}}
        txt = narrative.render(sim, ev)
        if "\"" in txt:
            said = txt
            break
    assert said and w.chars[friend].first in said.split("\"")[-1]


def test_the_build_out_prompt_carries_your_script():
    install()
    p = dialogue.prompt_for_update("yours:everyday_life", "more about the bus")
    assert p.startswith("You're building out one of my storylines") and "=== Everyday life" in p and "more about the bus" in p
    assert "# LIFE OS story scripts" in p and "texts <pool>:" not in p, "the storyline part of the guide"
    assert dialogue.prompt_for_update().startswith("You're writing for LIFE OS")
    with pytest.raises(KeyError):
        dialogue.prompt_for_update("yours:nope")
    assert dialogue.add_pack({"dialogue_pack": 1, "name": "Old pack", "texts": {"chatter_vent": ["so tired"]}})["ok"]
    with pytest.raises(ValueError):
        dialogue.prompt_for_update("yours:old_pack")  # the old JSON format: paste it again as a script
    g = dialogue.guide_markdown()
    for must in ("mods <open|close|talk> <tag>:", "late_night", "soccer_11", "{a|b}", "60% +charisma"):
        assert must in g, must
    assert "Write a lot" in dialogue.prompt_for_ai()


def test_long_descriptive_ids_and_texted_versions_from_a_coach_load():
    sc = lambda sid, who, **kw: {"id": sid, **({"who": who} if who else {}), "title": "A thing", "text": "Something happens.",
                                 "choices": [{"label": "Okay.", "ops": [["mood", 1]]}, {"label": "No.", "ops": [["mood", -1]]}], **kw}
    pack = {"name": "Baseball extras", "scenes": [
        sc("baseball_extra_07_first_varsity_hit_aftermath", "teammate"),
        sc("baseball_extra_02_first_varsity_atbat", "coach", by_text="you're leading off tomorrow. be ready"),
        sc("baseball_extra_03_offseason_home_run_derby", None, by_text="derby saturday?"),
    ]}
    r = dialogue.check(pack)
    assert r["ok"], r["errors"]
    assert any("skipped" in wn and "who" in wn for wn in r["warnings"]), r["warnings"]
    bad = dialogue.check({"name": "x", "scenes": [sc("big game", None), sc("x" * 90, None)]})
    msg = " ".join(bad["errors"])
    assert "lowercase letters, digits and underscores" in msg and "keep it under 80" in msg


def _hoops_pack():
    return {"name": "Hoops with my brother", "scenes": [
        {"id": "driveway_one_on_one", "title": "One on one in the driveway", "who": "older_sibling",
         "text": "{them_first} tosses you the basketball. \"First to eleven. He who loses does the dishes,\" he says, already backing you down.",
         "choices": [{"label": "Take him to the hoop", "ops": [["say", "\"Not bad,\" {them_first} says. His jumper is still better."]]},
                     {"label": "Tell him you're tired", "ops": [["mood", -1]]}]}],
        "chat": {"people": {"older_sibling": {"reply": {"greet": {"warm": ["what do you want, rook", "you shooting later or what", "driveway, 5 min",
                                                                           "if you're asking for a ride, no", "speak", "yo"]}}}}}}


def test_a_storyline_picks_the_person_it_is_about_and_keeps_them():
    from lifeos import chat, messages
    sim = story()
    w = sim.w
    me = w.chars[w.meta["protagonist"]]
    olds = dialogue.candidates(sim, me, "older_sibling")
    bros = dialogue.candidates(sim, me, "older_brother")
    sis = dialogue.candidates(sim, me, "older_sister")
    assert set(olds) == set(bros) | set(sis) and bros and sis
    assert all(w.chars[b].gender == "m" for b in bros) and all(w.chars[x].gender == "f" for x in sis)
    r = dialogue.add_pack(_hoops_pack())
    dialogue.reload()
    sim = Simulation(w)
    pid = next(p["id"] for p in dialogue.packs() if p["pack"]["name"] == "Hoops with my brother")
    assert dialogue.pack_kinds(pid) == ["older_sibling"]
    picks = {dialogue._context(sim, me, "older_sibling", {}, sim.streams.get("t", i), pack=pid)["them"] for i in range(6)}
    assert len(picks) == 1, "the same person every time"
    them = picks.pop()
    assert w.chars[them].gender == "m", "a basketball story that says 'he' and 'his' is about your brother"
    assert dialogue.cast_of(w, pid, "older_sibling") == them
    # texting lines from that storyline: only the person it's about uses them
    other = next(x for x in sis if x != them)
    for cid in (them, other):
        messages.add_contact(sim, cid)
    own = set(_hoops_pack()["chat"]["people"]["older_sibling"]["reply"]["greet"]["warm"])
    assert own & set(chat._pool(sim, them, "reply", "greet", "warm"))
    assert not own & set(chat._pool(sim, other, "reply", "greet", "warm")), "your sister doesn't text with your brother's lines"
    # you can change who it's about
    dialogue.set_cast(w, pid, "older_sibling", other)
    assert dialogue._context(sim, me, "older_sibling", {}, sim.streams.get("t", 9), pack=pid)["them"] == other


def test_the_cast_routes():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    from tests.test_story import spec
    dialogue.add_pack(_hoops_pack())
    dialogue.reload()
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    pid = next(p["id"] for p in dialogue.packs() if p["pack"]["name"] == "Hoops with my brother")
    k = c.get(f"/api/dialogue/cast?pack={pid}").json()["kinds"]
    assert k and k[0]["who"] == "older_sibling" and len(k[0]["options"]) >= 2
    pick = k[0]["options"][-1]["id"]
    r = c.post("/api/dialogue/cast", json={"pack": pid, "who": "older_sibling", "char": pick}).json()
    assert r["kinds"][0]["current"]["id"] == pick
    assert c.post("/api/dialogue/cast", json={"pack": pid, "who": "older_sibling", "char": "nobody"}).status_code == 409
    r = c.post("/api/dialogue/cast", json={"pack": pid, "who": "older_sibling", "char": None}).json()
    assert r["kinds"][0]["current"] is None


def _arc():
    return {"name": "Big brother season", "scenes": [
        {"id": "bro_driveway", "title": "The driveway", "who": "older_brother",
         "text": "{them_first} is shooting in the driveway when you get home. He bounces you the ball. \"First to eleven.\"",
         "choices": [
             {"label": "You're on", "ops": [["remember", "played_bro"]],
              "then": {"text": "It's 10-10. {them_first} is talking trash about your left hand. Next bucket wins.",
                       "choices": [{"label": "Drive left. Prove him wrong.", "ops": [["vibe", "bold", {"good": ["You score. He can't believe it."],
                                                                                                    "meh": ["He blocks it, barely."],
                                                                                                    "bad": ["He swats it into the neighbor's yard."]}]]},
                                   {"label": "Pull up from deep", "ops": [["mood", 2]]}]}},
             {"label": "Homework first", "ops": [["mood", -1]]}]},
        {"id": "bro_tryouts", "title": "Tryout nerves", "who": "older_brother",
         "text": "{them_first} knocks on your door the night before tryouts. He doesn't say much. He sits on the end of your bed.",
         "choices": [{"label": "Ask how he's feeling", "ops": [["vibe", "sweet", {"good": "He actually tells you.", "meh": "He shrugs.", "bad": "\"I'm fine.\" He leaves."}]]},
                     {"label": "Crack a joke", "ops": [["vibe", "funny", {"good": "He laughs.", "meh": "A smirk.", "bad": "Not now."}]]}]},
        {"id": "bro_rematch", "title": "The rematch", "who": "older_brother", "when": {"remembered": ["played_bro"]},
         "text": "\"Rematch,\" {them_first} says, tossing you the ball. He's been thinking about the last one.",
         "choices": [{"label": "Bring it", "ops": [["mood", 3]]}, {"label": "Not today", "ops": [["mood", -1]]}]},
        {"id": "bro_senior_night", "title": "Senior night", "who": "older_brother",
         "text": "It's {them_first}'s senior night. He looks up at you in the stands before the anthem.",
         "choices": [{"label": "Hold up the sign you made", "ops": [["rel_back", "them", "affection", 6]]},
                     {"label": "Yell his name", "ops": [["mood", 2]]}]}]}


def _brother_story():
    sim = story()
    w = sim.w
    me = w.chars[w.meta["protagonist"]]
    assert dialogue.candidates(sim, me, "older_brother"), "the test story has an older brother"
    return sim, w, me


def test_storylines_check_beats_styles_and_chapters():
    r = dialogue.check(_arc())
    assert r["ok"], r["errors"]
    bad = _arc()
    bad["scenes"][1]["who"] = None
    deep = {"label": "z"}
    for k in range(5):  # five more beats under the two the arc has: past the limit
        deep = {"label": f"a{k}", "then": {"text": f"beat {k}", "choices": [deep, {"label": f"d{k}"}]}}
    bad["scenes"][0]["choices"][0]["then"]["choices"][0]["then"] = {"text": "x", "choices": [deep, {"label": "d"}]}
    bad["scenes"][2]["when"]["after"] = ["Not An Id"]
    errs = " | ".join(dialogue.check(bad)["errors"])
    assert "needs the scene to be about someone" in errs and "keep going" in errs and "scene ids" in errs


def test_a_storyline_plays_in_order_and_scenes_keep_going():
    dialogue.add_pack(_arc())
    dialogue.reload()
    sim, w, me = _brother_story()
    sim = Simulation(w)
    pid = next(p["id"] for p in dialogue.packs() if p["pack"]["name"] == "Big brother season")
    assert dialogue.in_order(pid), "your storylines play in order by default"
    order, fired = [], []
    for _ in range(80):
        for m in moments.pending(w):
            if m["kind"] == "bro_driveway":
                moments.resolve(sim, m["id"], 0)  # you're on: and it keeps going
                beat = next((x for x in moments.pending(w) if x["kind"].startswith("bro_driveway__")), None)
                assert beat and beat["title"] == "The driveway" and "10-10" in beat["text"]
                moments.resolve(sim, beat["id"], 0)
            else:
                moments.resolve(sim, m["id"], 0)
        seen = w.meta.get("scenes_seen", {})
        for sid in ("bro_driveway", "bro_tryouts", "bro_rematch", "bro_senior_night"):
            if sid in seen and sid not in order:
                order.append(sid)
                fired.append(seen[sid][0])
        if len(order) == 4:
            break
        sim.advance_days(1)
    assert order == ["bro_driveway", "bro_tryouts", "bro_rematch", "bro_senior_night"], order
    assert fired == sorted(fired), "chapters in order (dense pacing: as soon as each is ready, no five-day floor)"
    assert dialogue.progress(sim, pid) == {"done": 4, "of": 4, "next": None, "in_order": True}
    from lifeos import chat
    bro = dialogue.candidates(sim, me, "older_brother")[0]
    assert any(x["known"] for x in chat.tastes_view(sim, bro)), "the style choices in his story taught you what he likes"


def test_a_branch_waits_for_what_you_chose_and_the_label_says_where_you_are():
    dialogue.add_pack(_arc())
    dialogue.reload()
    sim, w, me = _brother_story()
    sim = Simulation(w)
    pid = next(p["id"] for p in dialogue.packs() if p["pack"]["name"] == "Big brother season")
    first = dialogue.fire(sim, "bro_driveway", dialogue._context(sim, me, "older_brother", {}, sim.streams.get("x", 1), pack=pid))
    assert dialogue.chapter_label(sim, "bro_driveway") == "Big brother season · Chapter 1 of 4"
    moments.resolve(sim, first["id"], 1)  # homework first: no game with your brother, so no rematch later
    assert not dialogue._when_ok(sim, me, "bro_rematch", sim.cat.moments["bro_rematch"]["scene"]["when"])
    dialogue.set_in_order(pid, False)
    assert not dialogue.in_order(pid) and dialogue.chapter_label(sim, "bro_driveway") == "Big brother season"


def test_every_prompt_asks_for_one_script_block():
    install()
    for p in (dialogue.prompt_for_ai(), dialogue.prompt_for_update("yours:everyday_life"), dialogue.prompt_for_texting("yours:everyday_life"),
              dialogue.prompt_for_show()):
        assert "ONE code block" in p and "=== " in p and "# LIFE OS story scripts" in p


def test_one_big_story_seasons_episodes_and_previously():
    from lifeos import episodes
    dialogue.add_pack(_arc())
    dialogue.reload()
    sim, w, me = _brother_story()
    sim = Simulation(w)
    pid = next(p["id"] for p in dialogue.packs() if p["pack"]["name"] == "Big brother season")
    before = len(episodes.log(w))
    first = dialogue.fire(sim, "bro_driveway", dialogue._context(sim, me, "older_brother", {}, sim.streams.get("x", 1), pack=pid))
    n, label = episodes.season(sim)
    assert n == 1 and label == "Freshman year"
    assert first["episode"]["number"] == before + 1 and episodes.label(first).startswith(f"Season 1 · Episode {before + 1}")
    moments.resolve(sim, first["id"], 0)
    beat = next(x for x in moments.pending(w) if x["kind"].startswith("bro_driveway__"))
    assert beat["episode"]["number"] == first["episode"]["number"], "the next beat is the same episode"
    moments.resolve(sim, beat["id"], 0)
    e = episodes.log(w)[-1]
    assert e["kind"] == "bro_driveway" and e["choices"] == ["You're on", "Drive left. Prove him wrong."] and e["storyline"] == "Big brother season"
    second = dialogue.fire(sim, "bro_tryouts", dialogue._context(sim, me, "older_brother", {}, sim.streams.get("x", 2), pack=pid))
    assert second["previously"].startswith("Previously, in \u201cThe driveway\u201d: you went with \u201cYou're on\u201d then \u201cDrive left. Prove him wrong\u201d.")
    assert second["episode"]["number"] == first["episode"]["number"] + 1
    g = episodes.guide(sim)
    assert g["now"]["label"] == "Freshman year" and g["seasons"][0]["episodes"][-1]["title"] == "Tryout nerves"
    assert any(c["storyline"] == "Big brother season" and c["chapter"] == 3 for c in g["coming_up"])
    # hangouts and quizzes aren't episodes
    assert not episodes.counts("hang_dock_dare") and not episodes.counts("class_quiz") and episodes.counts("asked_out")


def test_a_season_plan_schedules_episodes_across_storylines():
    dialogue.add_pack(_arc())
    other = {"name": "Crush arc", "scenes": [
        {"id": "crush_first_text", "title": "The first text", "who": "crush", "text": "{them_first} texts you first. Huh.",
         "choices": [{"label": "Text back fast", "ops": [["mood", 2]]}, {"label": "Wait an hour", "ops": [["mood", 1]]}]}]}
    dialogue.add_pack(other)
    plan = {"name": "Season plan", "schedule": {"bro_tryouts": {"after": ["crush_first_text"], "gap_days": 2},
                                                "bro_senior_night": {"years": ["senior"]}},
            "scenes": [{"id": "crossover_bleachers", "title": "The bleachers", "who": "older_brother",
                        "when": {"after": ["bro_tryouts"]},
                        "text": "Your brother catches you looking at someone in the bleachers.",
                        "choices": [{"label": "Deny everything", "ops": [["vibe", "tease", {"good": "He laughs.", "meh": "He shrugs.", "bad": "He tells mom."}]]},
                                    {"label": "Ask for advice", "ops": [["remember", "asked_bro_advice"]]}]}]}
    r = dialogue.check(plan)
    assert r["ok"] and r["summary"]["schedule"] == 2, r["errors"]
    assert not dialogue.check({"name": "x", "schedule": {"bro_tryouts": {"year": ["senior"]}}})["ok"]
    dialogue.add_pack(plan)
    dialogue.reload()
    sim, w, me = _brother_story()
    sim = Simulation(w)
    when = sim.cat.moments["bro_tryouts"]["scene"]["when"]
    assert when["after"] == ["crush_first_text"] and when["gap_days"] == 2
    assert sim.cat.moments["bro_senior_night"]["scene"]["when"]["years"] == ["senior"]
    w.meta.setdefault("scenes_seen", {})["bro_driveway"] = [w.day]
    assert not dialogue._when_ok(sim, me, "bro_tryouts", when), "it waits for the crush storyline's first episode"
    p = dialogue.prompt_for_show("tie the crush in")
    assert "=== Big brother season" in p and "=== Crush arc" in p and "--- The first text" in p and "tie the crush in" in p
    assert "starts with `=== Season plan`" in p and "## My season plan now" not in p
    # a season plan in script form comes back whole: the next plan prompt carries it, and it isn't listed as a storyline
    plan_script = "=== Season plan\n\n--- On the bleachers  [freshman · after Big brother season: Tryout nerves]\nIt's loud.\n* Wave\n\nschedule:\nBig brother season: Senior night [senior]\n"
    r = dialogue.add_script(plan_script)
    assert r["ok"], r["errors"]
    p = dialogue.prompt_for_show()
    assert "## My season plan now" in p and "--- On the bleachers" in p.split("## My season plan now")[1]
    assert "--- On the bleachers" not in p.split("## My season plan now")[0], "the plan itself isn't listed as a storyline"
