"""Texting that goes back and forth: type anything, tap a suggestion, and flirting that says why."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import chat, messages  # noqa: E402
from tests.test_phone import story  # noqa: E402


def _setup(att, fam, aff):
    w, sim = story(pet=False)
    me = w.chars[w.meta["protagonist"]]
    sim.advance_days(2)
    g = next(c.id for c in w.students() if c.gender == "f" and "m" in c.attracted_to and not c.flags.get("partner") and not c.custom)
    messages.add_contact(sim, g)
    r = w.ensure_rel(g, me.id, w.day)
    r.familiarity, r.affection, r.attraction = fam, aff, att
    w.ensure_rel(me.id, g, w.day).familiarity = fam
    return w, sim, me, g


def test_reading_what_you_type():
    cases = {"hey!": "greet", "what are you up to?": "ask", "ok": "dry", "you're cute 😏": "flirt", "i miss you": "flirt",
             "wanna get food this weekend?": "plans", "sorry about earlier": "apology", "shut up loser": "rude", "gtg night!": "bye",
             "you killed it today": "compliment", "you ok? you seemed off": "support", "will you go out with me": "ask_out",
             "i just finished the math homework and it was brutal": "chat", "i'm convinced the cafeteria pizza is plastic lol": "joke"}
    for text, intent in cases.items():
        assert chat.classify(text)["intent"] == intent, (text, chat.classify(text))
    assert chat.classify("i miss you")["flirt"] == 2 and chat.classify("you're cute 😏")["flirt"] == 1
    assert not chat.classify("you're cute")["question"] and chat.classify("did you do the hw")["question"]


def test_a_conversation_goes_back_and_forth_until_they_wrap_it_up():
    w, sim, me, g = _setup(30, 50, 40)
    t = lambda: messages.phone(w)["threads"][f"dm:{g}"]  # noqa: E731
    sent = 0
    while chat.view(sim, g)["status"] != "done" and sent < 15:
        sug = chat.suggestions(sim, g)
        assert sug and all(s["text"] and s["tone"] for s in sug)
        pick = next((i for i, s in enumerate(sug) if s["intent"] in ("ask", "answer", "joke")), 0)
        chat.send(sim, g, None, pick)
        sent += 1
    assert 3 <= sent <= 12, sent
    theirs = [m for m in t()["msgs"] if m["from"] == g]
    assert len(theirs) >= sent and theirs[-1]["kind"] in ("chat_close", "chat_close_cold")
    # they're done for now: a text gets left on read, and a note says so
    chat.send(sim, g, "helloooo?")
    assert t()["msgs"][-2]["read"] and t()["msgs"][-1]["kind"] == "note"
    assert chat.suggestions(sim, g) == []
    # texting can't be farmed: a day's texting moves affection only so far
    assert messages.phone(w)["chat_gain"][g]["affection"] <= chat.CAP["affection"]


def test_flirting_lands_when_the_signs_are_there_and_says_why():
    w, sim, me, g = _setup(55, 55, 40)
    assert chat.read(sim, g)["label"] == "Seems into you"
    before = w.rels[(g, me.id)].attraction
    chat.send(sim, g, "hey")
    res = chat.send(sim, g, "ok you're kinda cute when you're annoyed 😏")
    assert res["result"] == "flirt_landed" and res["why"].startswith("Landed: ")
    assert w.rels[(g, me.id)].attraction > before
    assert any(m["kind"] == "note" and m["text"] == res["why"] for m in messages.phone(w)["threads"][f"dm:{g}"]["msgs"])
    assert any(s["text"].startswith("Flirted back") for s in chat.signals(sim, g))
    assert chat.stage(sim, g) == 3, "you flirted and they flirted back: flirty"


def test_flirting_with_someone_who_barely_knows_you_tells_you_to_talk_first():
    w, sim, me, g = _setup(10, 12, 2)
    assert chat.read(sim, g)["label"] == "Too early to tell" and chat.stage(sim, g) == 0
    res = chat.send(sim, g, "you're cute 😏")
    assert res["result"] in ("flirt_awkward", "flirt_shut")
    assert "barely know you" in res["why"] and "Talk and hang out first." in res["why"]
    assert "Get to know them first" in chat.tip(sim, g)


def test_typing_yes_to_an_invite_answers_it():
    w, sim, me, g = _setup(20, 50, 45)
    inv = {"id": "inv_t", "from": g, "to": me.id, "action": "hang_out", "status": "pending", "day": w.day, "event": None}
    w.meta.setdefault("inbox", []).append(inv)
    messages.post(sim, f"dm:{g}", g, "wanna hang after school?", replies=[{"label": "yes!", "fx": "invite:inv_t:yes"},
                                                                         {"label": "can't today", "fx": "invite:inv_t:no"}],
                  ctx={"invite": "inv_t"})
    chat.send(sim, g, "yeah i'm down")
    assert w.meta["control"]["queued"] == {"invite": "inv_t"}
    assert messages.phone(w)["threads"][f"dm:{g}"]["msgs"][-2]["text"] == "yeah i'm down"


def test_flirting_choices_say_how_risky_they_are():
    from lifeos import planner
    w, sim, me, g = _setup(55, 55, 40)
    opts = [{"index": 0, "action": "flirt", "target": g, "category": "romance"}, {"index": 1, "action": "ask_out", "target": g, "category": "romance"}]
    out = {o["action"]: o for o in planner.annotate(sim, me, opts)}
    assert out["flirt"]["group"] == "want" and out["flirt"]["reason"] == "Seems into you"
    assert out["ask_out"]["reason"].startswith("Risky"), "they haven't flirted back yet"
    r = w.rels[(g, me.id)]
    r.attraction = 5
    out = {o["action"]: o for o in planner.annotate(sim, me, opts)}
    assert out["flirt"]["reason"] == "Risky: just friends vibes"


def test_the_phone_routes():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    w, sim, me, g = _setup(40, 50, 35)
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    api.lab.replace_world(w)
    c = TestClient(api.app)
    th = c.get(f"/api/phone/thread/dm:{g}").json()
    assert th["chat"]["can_type"] and th["chat"]["suggestions"]
    r = c.post(f"/api/phone/thread/dm:{g}/say", json={"text": "heyyy what are you doing"})
    assert r.status_code == 200 and r.json()["thread"]["msgs"][-1]["from"] in (g, "note")
    r = c.post(f"/api/phone/thread/dm:{g}/say", json={"suggestion": 0})
    assert r.status_code == 200
    v = c.get(f"/api/phone/contact/{g}").json()["vibe"]
    assert v["stages"][0] == "Strangers" and v["read"] and v["tip"] and isinstance(v["signals"], list)
    assert len(c.get("/api/phone/flirting").json()["guide"]) >= 5
    assert c.post(f"/api/phone/thread/dm:{g}/say", json={"text": "   "}).status_code == 409


def test_teasing_vs_rude_and_flirt_styles():
    assert chat.classify("you're such a loser 😂")["intent"] == "joke" and chat.classify("you're such a loser 😂")["style"] == "tease"
    assert chat.classify("you're such a loser")["intent"] == "rude"
    assert chat.classify("ok i like you")["style"] == "bold"
    assert chat.classify("talking to you made my day")["style"] == "sweet"
    assert chat.classify("did it hurt when you fell from heaven 😏")["style"] == "cheesy"


def test_everyone_likes_different_things_and_you_learn_what():
    w, sim, me, g = _setup(45, 55, 40)
    t = chat.tastes(w.chars[g])
    assert set(t) == set(chat.STYLES) and 1 in t.values() and list(t.values()).count(-1) >= 2
    others = {tuple(sorted(chat.tastes(c).items())) for c in w.students()[:20]}
    assert len(others) >= 3, "different people, different tastes"
    loved = next(k for k, v in t.items() if v == 1)
    hated = next(k for k, v in t.items() if v == -1 and k != "cheesy") if any(v == -1 and k != "cheesy" for k, v in t.items()) else "cheesy"
    # a style they're not into costs you; one they love helps (same person, same moment)
    import random
    lo = chat.flirt_check(sim, g, 1, 0.5, 0.0, random.Random(1), style=hated)
    hi = chat.flirt_check(sim, g, 1, 0.5, 0.0, random.Random(1), style=loved)
    assert hi["score"] > lo["score"]
    assert "not into" in lo["why"] or lo["outcome"] in ("landed", "playful")
    # you only know once you've tried it
    assert not any(x["known"] for x in chat.tastes_view(sim, g))
    chat.send(sim, g, "hey")
    sug = chat.suggestions(sim, g)
    fl = next(i for i, s in enumerate(sug) if s["intent"] == "flirt")
    style = sug[fl]["style"]
    chat.send(sim, g, None, fl)
    known = {x["style"]: x for x in chat.tastes_view(sim, g)}
    assert known[style]["known"] and known[style]["taste"] == t[style]


def test_they_ask_you_things_and_your_answers_fit():
    w, sim, me, g = _setup(30, 50, 45)
    messages.post(sim, f"dm:{g}", g, "you going to the game friday?", kind="chat_ask", ctx={"a": "yesno"})
    sug = chat.suggestions(sim, g)
    assert [s.get("yn") for s in sug if s["intent"] == "answer"] == ["yes", "no"]
    chat.send(sim, g, "yeah obviously")
    th = messages.phone(w)["threads"][f"dm:{g}"]["msgs"]
    mine = max(i for i, m in enumerate(th) if m["from"] == "me")
    answer = th[mine + 1]["text"].lower()
    assert any(answer.startswith(x.lower().rstrip("!")[:6]) for x in chat.D()["reply"]["answered"]["yes"]), answer
    # bring up a test: they answer about it, and follow up after
    chat.send(sim, g, "ugh i have a chem test tomorrow")
    assert messages.phone(w)["threads"][f"dm:{g}"]["mentioned"]["topic"] == "school"
    sim.advance_days(2)
    msgs = messages.phone(w)["threads"][f"dm:{g}"]["msgs"]
    follow = [m for m in msgs if m["kind"] == "chat_follow"]
    assert follow and follow[-1]["text"] in chat.D()["follow"]["school"] and not follow[-1]["replies"]
    assert any(s["text"] == "Remembered what you told them" for s in chat.signals(sim, g))


def test_asking_out_by_text_plans_it_and_they_keep_their_word():
    from lifeos import planner
    w, sim, me, g = _setup(70, 70, 55)
    for _ in range(2):
        chat.send(sim, g, "you're kinda cute when you're annoyed 😏")
    assert chat.stage(sim, g) >= 3
    res = chat.send(sim, g, "ok real question. would you go out with me?")
    assert res["result"] == "flirt_landed" and "Plan made" in res["why"]
    q = w.meta["control"]["queued"]
    assert q["action"] == "ask_out" and q["target"] == g and q["expires"] == w.day + 4
    assert planner.plan_label(sim, q) == f"Asking {w.chars[g].first} out, next time you see them"
    assert w.rels[(me.id, g)].crush, "you asked them out: you're into them"
    assert w.chars[g].flags["told_to_ask"]["by"] == me.id


def test_a_partner_you_ignore_misses_you():
    from lifeos import planner
    w, sim, me, g = _setup(70, 70, 70)
    sim.advance_days(6)
    me.flags["partner"], w.chars[g].flags["partner"] = g, me.id
    r = w.rels[(me.id, g)]
    r.last_day = w.day - 5
    v = chat.vibe(sim, g)
    assert v["signals"][0]["text"].startswith("Feeling distant: 5 days") and "5 days" in v["tip"]
    plate = planner.today(sim)["plate"]
    assert any(p["title"] == f"{w.chars[g].first} misses you" for p in plate)


def test_packs_can_add_texting_lines():
    from lifeos import dialogue
    ok = dialogue.check({"name": "Chat test", "chat": {"topic": {"school": ["pop quiz again"]}, "ask": {"general": [{"q": "bonfire?", "a": "yesno"}]}}})
    assert ok["ok"] and ok["summary"]["chat"] == 2
    bad = dialogue.check({"name": "Chat test", "chat": {"topic": {"homework": ["x"]}, "ask": {"general": ["no kind"]}}})
    assert not bad["ok"] and len(bad["errors"]) == 2


def test_venting_good_news_gossip_and_thanks():
    assert chat.classify("my day honestly sucked")["intent"] == "vent"
    assert chat.classify("i'm so stressed about everything rn")["intent"] == "vent"
    assert chat.classify("guess what. i aced the test")["intent"] == "news"
    assert chat.classify("i made varsity!!")["intent"] == "news"
    assert chat.classify("did you hear about cole and paige")["intent"] == "gossip"
    assert chat.classify("thanks for today, seriously")["intent"] == "thanks"
    w, sim, me, g = _setup(20, 60, 60)
    me.needs["stress"] = 70
    chat.send(sim, g, "hey")
    res = chat.send(sim, g, "my day honestly sucked")
    assert me.needs["stress"] < 70 and "had your back" in (res["why"] or "")
    th = messages.phone(w)["threads"][f"dm:{g}"]["msgs"]
    assert any(m["kind"] == "chat_comfort" for m in th)
    sug = chat.suggestions(sim, g)
    assert any(s["intent"] == "thanks" for s in sug), "they had your back: you can say thanks"
    res = chat.send(sim, g, "i'm so stressed about everything rn")
    assert "wear on people" in (res["why"] or ""), "once a day is support"
    chat.send(sim, g, "guess what. i aced the test")
    assert any(m["kind"] == "chat_hype" for m in messages.phone(w)["threads"][f"dm:{g}"]["msgs"])


def test_they_bring_up_what_you_just_did_together_once():
    w, sim, me, g = _setup(20, 60, 60)
    ev = sim.new_event("interact.hang_out", "great", [me.id], [g], 10, {"place": "the diner"})
    ev["text"] = "You and them hung out."
    from lifeos.history import Effects
    sim.finish(ev, Effects(w, ev))
    chat.send(sim, g, "heyy")
    th = messages.phone(w)["threads"][f"dm:{g}"]["msgs"]
    rec = [m for m in th if m["kind"] == "chat_recent"]
    assert len(rec) == 1, [m["text"] for m in th]
    assert chat._recent(sim, g) is None, "it comes up once"


def test_storyline_people_text_like_themselves(tmp_path, monkeypatch):
    from lifeos import dialogue
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    pack = {"name": "Big brother texts", "chat": {"people": {"older_sibling": {
        "reply": {"greet": {"warm": ["what do you want, gremlin", "oh look who remembered i exist", "make it quick",
                                     "if this is about the car the answer is no", "speak", "yo what"],
                            "ok": ["what", "yeah?", "sup gremlin", "mhm", "what now", "talk"],
                            "cold": ["busy", "later", "not now", "what", "ok", "k"]}},
        "suggest": {"greet": ["can you drive me later", "is mom mad at me or", "what's for dinner", "you home?"]}}}}}
    r = dialogue.check(pack)
    assert r["ok"], r["errors"]
    dialogue.add_pack(pack)
    dialogue.reload()
    w, sim, me, g = _setup(20, 60, 60)
    sib = next(s for s in sim.siblings(me.id) if (w.chars[s].grade or 0) > (me.grade or 9))
    assert "older_sibling" in chat.kinds_of(sim, sib)
    own = set(x.lower() for x in pack["chat"]["people"]["older_sibling"]["reply"]["greet"]["warm"]
              + pack["chat"]["people"]["older_sibling"]["reply"]["greet"]["ok"] + pack["chat"]["people"]["older_sibling"]["reply"]["greet"]["cold"])
    hits = 0
    for i in range(6):
        t = messages.phone(w)["threads"].get(f"dm:{sib}")
        if t:
            t.pop("convo", None)  # a new conversation each time
        chat.send(sim, sib, "hey")
        last = next(m for m in reversed(messages.phone(w)["threads"][f"dm:{sib}"]["msgs"]) if m["from"] == sib and m["kind"] == "chat_react")
        hits += last["text"].lower().rstrip(".!") in {x.rstrip(".!") for x in own}
    assert hits >= 2, "your brother uses his own lines most of the time"
    bad = dialogue.check({"name": "x", "chat": {"people": {"big_bro": {"reply": {}}}}})
    assert not bad["ok"] and "isn't a kind of person" in bad["errors"][0]


def test_the_texting_prompt_is_complete_and_its_lines_load(tmp_path, monkeypatch):
    from lifeos import dialogue, script
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    try:
        assert dialogue.add_script("=== Brothers\ncast: bro = older brother\n\n--- Driveway  [freshman]\nbro: Shoot.\n* Okay\n")["ok"]
        p = dialogue.prompt_for_texting("yours:brothers")
        for must in ("=== Brothers texting", "chat people.older_brother.reply.greet.warm:", "reply.vent", "ask.general", "(yesno)",
                     "reply.flirt", "ONE code block", "chat <path>:"):
            assert must in p, must
        answer = ("=== Brothers texting\n\nchat people.older_brother.reply.greet.warm:\nyo\nwhat's good\n\n"
                  "chat people.older_brother.ask.general:\nu coming to the game (yesno)\nwhat are u doing (doing)\n")
        r = script.compile_script(answer)
        assert not r["errors"] and r["summary"]["lines"] == 4, r
        assert r["packs"][0]["chat"]["people"]["older_brother"]["reply"]["greet"]["warm"] == ["yo", "what's good"]
    finally:
        dialogue.reload()

