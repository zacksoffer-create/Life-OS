"""Adding your own texting: flirt lines and group chats in plain blocks, written by ChatGPT (or you), pasted in, fixed
rather than refused, and live right away."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import chat, dialogue, groupchat, messages, script, scriptfix  # noqa: E402
from tests.test_chat import _setup  # noqa: E402
from tests.test_story import spec  # noqa: E402

SAMPLE = """Here you go!
```
flirt tease:
  you're lucky you're funny bc that hat was a choice
  ok who gave you permission to be this {cute|annoying}
flirt bold later:
  i'm taking you to the diner friday. that's the plan
flirt answers tease, lands:
  oh you think you're so smooth
flirt follow-ups sweet after a laugh:
  ok fine. for real tho i like this
flirt first:
  you were the best part of chem today
flirt back letdown:
  haha you're the best but i think we're better as friends
flirt payoff plans:
  ok diner friday. you're buying fries

group chat crew, weekend:
  A: fantasy draft is tonight. who's in
  B: i'm taking the jets defense first
  C: why would you do that
  B: because i believe
  * {B} you're gonna finish last | A +, B -, fun +
      A: LMAO
      B: watch me
      dm B: ok be honest is the jets thing bad
  * i'm in. i'm winning the whole thing | A +, crew +
      C: we'll see about that
```"""


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


def test_flirt_blocks_go_where_flirting_looks_for_them():
    assert script.flirt_path("tease") == ["banter", "open", "early", "tease"]
    assert script.flirt_path("bold later") == ["banter", "open", "close", "bold"]
    assert script.flirt_path("answers bold, laughs") == ["banter", "them", "bold", "playful"]
    assert script.flirt_path("follow-ups cool") == ["banter", "back", "landed", "cool"]
    assert script.flirt_path("follow-ups sweet after a laugh") == ["banter", "back", "playful", "sweet"]
    assert script.flirt_path("first later") == ["banter", "in", "close"]
    assert script.flirt_path("back let them down easy") == ["banter", "in_back", "letdown"]
    assert script.flirt_path("payoff good night") == ["banter", "payoff", "goodnight"]
    with pytest.raises(script.Fail):
        script.flirt_path("answers tease, maybe")
    r = script.compile_script(script.extract(SAMPLE))
    assert not r["errors"], r["errors"]
    ch = r["packs"][0]["chat"]["banter"]
    assert ch["open"]["early"]["tease"][1:] == ["ok who gave you permission to be this cute", "ok who gave you permission to be this annoying"]
    assert ch["payoff"]["plans"] == ["ok diner friday. you're buying fries"]


def test_a_group_chat_block_is_a_conversation_with_replies_effects_and_a_dm():
    r = script.compile_script(script.extract(SAMPLE))
    b = r["packs"][0]["groupchat"][0]
    assert b["chat"] == "crew" and b["when"] == ["weekend"] and len(b["lines"]) == 4 and b["lines"][0] == ["A", "fantasy draft is tonight. who's in"]
    first = b["you"][0]
    assert first["say"] == "{B} you're gonna finish last" and first["then"] == [["A", "LMAO"], ["B", "watch me"]]
    assert first["fx"] == {"A": {"affection": 1.5}, "B": {"affection": -1.0}, "me": {"fun": 1.5}}
    assert first["dm"] == {"from": "B", "text": "ok be honest is the jets thing bad"}
    assert b["you"][1]["fx"] == {"A": {"affection": 1.5}, "crew": {"cohesion": 1.5}}
    fam = script.compile_script("group chat family, pet:\n  mom: who fed {pet}\n  sibling: not me\n  * i did | trust +\n      mom: thank you\n")
    assert not fam["errors"] and fam["packs"][0]["groupchat"][0]["lines"][0][0] == "P"


def test_what_chatgpt_gets_wrong_in_texting_is_fixed_not_refused():
    bad = """flirt teese:
  you wish
flirt answers bold, maybe:
  hm
group chat crew, weekend, full moon:
  A: yo
  D: who's D
  B: sup
  * hey | A +, vibes +
      A: hey
"""
    fx = scriptfix.repair(bad, library={})
    assert fx["ok"], fx["result"]["errors"]
    notes = " | ".join(n["text"] for n in fx["notes"])
    assert "flirt tease:" in fx["text"], fx["text"]
    pk = fx["result"]["packs"][0]
    assert pk["chat"]["banter"]["open"]["early"]["tease"] == ["you wish"]
    assert pk.get("groupchat") and pk["groupchat"][0]["lines"] == [["A", "yo"], ["B", "sup"]], notes


def test_add_texting_through_the_phone_and_it_plays():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    p = c.get("/api/texting/prompt", params={"what": "both", "ask": "sarcastic flirting, the boys roasting each other", "size": "few"}).json()
    for must in ("sarcastic flirting", "Zack", "flirt answers tease, lands:", "group chat <crew|team|family>", "{A}", "write 2"):
        assert must in p["prompt"], must
    assert c.get("/api/texting/prompt", params={"what": "flirt"}).json()["prompt"].count("group chat") == 0
    ck = c.post("/api/texting/check", json={"text": SAMPLE}).json()
    assert ck["breakdown"]["flirt_total"] == 9 and len(ck["breakdown"]["group_chats"]) == 1, ck  # ({cute|annoying} is two)
    assert {f["label"] for f in ck["breakdown"]["flirt"]} >= {"flirt openers", "payoffs", "them flirting first"}
    assert not dialogue.packs(), "checking doesn't add anything"
    assert c.post("/api/texting/check", json={"text": "just words"}).status_code == 422
    r = c.post("/api/texting/add", json={"text": SAMPLE}).json()
    assert r["ok"] and r["pack"]
    row = next(x for x in r["packs"] if x["id"] == r["pack"])
    assert row["texting"] == {"flirt": 9, "group_chats": 1, "lines": 0}
    assert "you were the best part of chem today" in chat.D()["banter"]["in"]["early"]
    assert any(b["id"].startswith("pk_") for b in groupchat.D()["bursts"])
    # it plays: the pasted group chat starts up and your answer lands, with the DM after
    sim = api.lab.sim
    w = sim.w
    me = w.chars[w.meta["protagonist"]]
    friends = [x.id for x in w.students() if x.id != me.id and x.household_id != me.household_id][:3]
    w.meta["squad"] = {"ids": friends, "cohesion": 50.0, "formed": w.day, "updated": w.day + 400, "last_you": None, "jokes": [], "name": "the boys"}
    mine = [b for b in groupchat.D()["bursts"] if b["id"].startswith("pk_")]
    groupchat._DATA, saved = {"bursts": []}, groupchat._DATA
    try:
        assert groupchat.start(sim, "crew", {"weekend"})
    finally:
        groupchat._DATA = saved
    t = messages.phone(w)["threads"]["squad"]
    last = t["msgs"][-1]
    assert last["text"] == "because i believe" and len(last["replies"]) == 2 and mine
    cast = list(t["bursts"].values())[-1]["cast"]
    assert last["replies"][0]["label"] == f"{w.chars[cast['B']].first} you're gonna finish last"
    messages.reply(sim, "squad", last["id"], 0)
    assert any(x["key"] == "chat_side" and x["from"] == cast["B"] for x in messages.phone(w)["pending"])


CHATGPT_STYLE = """Here's your texting pack! 😄

```
**flirt sarcastic:**
  wow you're so funny (not)
  ok that was actually kind of good
### Flirt (cute)
  you were the best part of my day ngl
flirt answers sarcastic, into it:
  oh so we're doing this
**group chat crew, weekend:**
  Jake: draft tonight. Tyler you're picking last
  Tyler: jets defense first
  Marcus: why would you do that
  * Tyler you're finishing last | Jake +, Tyler -
      Jake: LMAO
      dm Tyler: be honest is the jets thing bad
  * i'm in | crew +
      Marcus: we'll see
```
Let me know if you want more!"""


def test_what_chatgpt_actually_sends_goes_in():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    ck = c.post("/api/texting/check", json={"text": CHATGPT_STYLE})
    assert ck.status_code == 200, ck.json()
    b = ck.json()["breakdown"]
    assert b["flirt_total"] == 4 and len(b["group_chats"]) == 1, b
    assert any("Jake is A" in n for n in ck.json()["notes"])
    r = c.post("/api/texting/add", json={"text": CHATGPT_STYLE}).json()
    assert r["ok"]
    ban = chat.D()["banter"]
    assert "wow you're so funny (not)" in ban["open"]["early"]["tease"], "sarcastic is teasing"
    assert "you were the best part of my day ngl" in ban["open"]["early"]["sweet"], "cute is sweet"
    assert "oh so we're doing this" in ban["them"]["tease"]["landed"]
    b0 = next(x for x in groupchat.D()["bursts"] if x["id"].startswith("pk_"))
    assert [r_ for r_, _ in b0["lines"]] == ["A", "B", "C"] and b0["lines"][0][1] == "draft tonight. {B} you're picking last"
    assert b0["you"][0]["fx"] == {"A": {"affection": 1.5}, "B": {"affection": -1.0}} and b0["you"][0]["dm"]["from"] == "B"


def test_when_nothing_goes_in_it_says_why_and_how_to_ask_again():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    prose = c.post("/api/texting/check", json={"text": "Sure! Here are some ideas for flirty texts in your game."}).json()
    assert "none of the template's sections" in prose["errors"][0] and "flirt tease:" in prose["fix_prompt"]
    bad = c.post("/api/texting/check", json={"text": "```\nflirt mysterious:\n  hmm\n```"}).json()
    assert any("mysterious" in e for e in bad["errors"]) and "group chat <crew|team|family>" in bad["fix_prompt"]
    p = c.get("/api/texting/prompt", params={"what": "both"}).json()["prompt"]
    assert "never a name" in p and "Keep every header line exactly" in p


def test_every_flirt_header_the_prompt_allows_has_a_place_in_the_game():
    """A header that compiles but has no slot in the game's texting lines fails the whole paste ("isn't a place for
    lines"): flirt back cheesy did. Every combination the prompt offers has to land somewhere real."""
    base = dialogue._base("chat.json")["banter"]
    styles = script.FLIRT_STYLES + ("cool",) + tuple(script.STYLE_WORDS)
    keys = ["first", "first later", "back letdown", "back cool"] + [f"payoff {x}" for x in script.FLIRT_PAYOFF]
    for st in styles:
        keys += [st, f"{st} later", f"follow-ups {st}", f"follow-ups {st} after a laugh", f"back {st}"]
        keys += [f"answers {st}, {how}" for how in script.FLIRT_OUT]
    missing = []
    for k in keys:
        try:
            path = script.flirt_path(k)
        except script.Fail:
            continue
        d = {"banter": base}
        for x in path:
            if not isinstance(d, dict) or x not in d:
                missing.append((k, path))
                break
            d = d[x]
    assert not missing, missing[:10]
    fx = scriptfix.repair("flirt back cheesy:\n  is this a pickup line or are you just happy to see me\n", library={})
    assert fx["ok"] and fx["result"]["packs"][0]["chat"]["banter"]["in_back"]["funny"]



def _client():
    from fastapi.testclient import TestClient
    from lifeos import api
    from lifeos.storage import Store
    api.lab = api.Lab(Store(":memory:"), fresh=True)
    c = TestClient(api.app)
    assert c.post("/api/story/new", json={"spec": spec(per=6)}).status_code == 200
    return c


def test_the_prompt_is_a_template_of_the_games_own_slots_for_what_you_pick():
    from lifeos import texting
    c = _client()
    r = c.get("/api/texting/prompt", params={"what": "flirt", "size": "few", "parts": "start,end", "style": "tease"}).json()
    blk = r["prompt"].split("## The template")[1].split("```")[1]
    heads = [ln for ln in blk.strip().split("\n") if not ln.startswith(" ")]
    assert heads == ["flirt tease:", "flirt tease later:", "flirt payoff blush:", "flirt payoff plans:", "flirt payoff goodnight:",
                     "flirt payoff ask:"], heads
    assert r["sections"] == 6 and r["lines"] == 12 and "replace the ... with 2 lines" in r["prompt"]
    everything = c.get("/api/texting/prompt", params={"what": "both"}).json()
    assert everything["sections"] == len(texting.sections()) and everything["group_chats"] == 4
    # every header the template can ever show has a real place in the game
    base = dialogue._base("chat.json")["banter"]
    for h, _ in texting.sections():
        d = {"banter": base}
        for x in script.flirt_path(h[len("flirt "):-1]):
            assert isinstance(d, dict) and x in d, h
            d = d[x]


def test_a_filled_in_template_goes_in_and_a_bad_section_doesnt_stop_the_rest():
    c = _client()
    filled = """Here you go!
```
flirt tease:
  ok who said you could be this funny
  bold of you to text first
flirt tease later:
  ...
flirt mysterious:
  hmm
flirt answers tease, perhaps:
  ok
flirt payoff plans:
  diner friday. you're buying fries
```"""
    ck = c.post("/api/texting/check", json={"text": filled}).json()
    assert ck["breakdown"]["flirt_total"] == 3, ck
    assert [s["header"] for s in ck["skipped"]] == ["flirt mysterious:", "flirt answers tease, perhaps:"], ck["skipped"]
    assert "Send just those sections again" in ck["fix_prompt"] and "flirt mysterious:" in ck["fix_prompt"]
    r = c.post("/api/texting/add", json={"text": filled}).json()
    assert r["ok"] and r["breakdown"]["flirt_total"] == 3 and len(r["skipped"]) == 2 and r["fix_prompt"]
    ban = chat.D()["banter"]
    assert "bold of you to text first" in ban["open"]["early"]["tease"] and "diner friday. you're buying fries" in ban["payoff"]["plans"]
    assert "..." not in ban["open"]["close"]["tease"], "a section nobody filled in isn't added"
