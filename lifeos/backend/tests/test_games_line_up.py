"""Your games line up everywhere: the big moment you play (the mini game) is in your box score as the play itself and can
decide a close game; the game's write-up and the Sports tab say so; every game leaves a record storylines read
([if we won], {my_line}); and a storyline played in order waits for the game and plays the side of it that happened."""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lifeos import dialogue, gameplay, minigames, moments, scheduler, sportshub  # noqa: E402
from lifeos.engine import Simulation, SlotState  # noqa: E402
from lifeos.story import begin, create_story  # noqa: E402
from tests.test_story import spec  # noqa: E402


@pytest.fixture(autouse=True)
def own_packs(tmp_path, monkeypatch):
    monkeypatch.setattr(dialogue, "USER_DIR", str(tmp_path / "dialogue"))
    dialogue.reload()
    yield
    dialogue.reload()


def world():
    sim = Simulation(create_story(spec(per=6)))
    begin(sim)
    w = sim.w
    me = w.chars[w.meta["protagonist"]]
    gid = next(g for g in w.groups if w.groups[g].get("skill") == "football" and w.groups[g].get("school") != "college")
    g = w.groups[gid]
    if me.id not in g["members"]:
        g["members"].append(me.id)
        me.memberships.append(gid)
    g.setdefault("levels", {})[me.id] = "varsity"
    me.positions["football"] = "WR"
    return sim, me, gid


def game_today(sim, gid, n=1):
    w = sim.w
    it = {"day": w.day, "kind": "game", "group": gid, "key": f"game:{gid}:{w.day}:{n}", "slot": "evening"}
    w.calendar.append(it)
    return it


def play(sim, it, seed=1):
    g = sim.w.groups[it["group"]]
    sim.slot = SlotState("evening")
    sim.slot.attend[("event", it["key"])] = list(g["members"])
    sim.institutions.game(it, random.Random(seed))
    sim.slot = None


def big_moment(sim, me, gid, score, stats):
    moments.trigger(sim, "game_day", me.id, {"group": gid, "opponent": "Madison"})
    m = moments.pending(sim.w)[-1]
    i = next(k for k, ch in enumerate(m["choices"]) if "yourself" in ch["label"])
    cfg = minigames.start(sim, "sport", kind="moment", mid=m["id"], index=i, ctx=m["ctx"])
    minigames.finish(sim, cfg["session"], score, 10, stats)


def test_the_big_moment_is_in_the_box_score_the_write_up_and_the_sports_tab():
    sim, me, gid = world()
    it = game_today(sim, gid)
    big_moment(sim, me, gid, 10, {"mode": "goal", "result": "td", "yards": 12, "plays": 3})
    assert me.flags["game_play"]["tier"] == "great" and me.flags["game_play"]["stats"]["result"] == "td"
    play(sim, it, seed=3)
    ev = next(e for e in reversed(list(sim.w.history.events.values())) if e["type"] == "game" and e["outcome"] in ("win", "loss"))
    mine = ev["data"]["box"][me.id]
    assert mine.get("play") and "late" in mine["play"] and ev["data"]["play"] == mine["play"] and mine["play"] in ev["text"]
    if ev["outcome"] == "win" or "touchdown" in mine["play"]:
        assert mine["line"].get("rec_td", 0) >= 1 or "stopped" in mine["play"] or "picked up" in mine["play"]
    lg = me.flags["last_game"]
    assert lg["play"] == mine["play"] and lg["tier"] == "great" and lg["win"] == (ev["outcome"] == "win")
    log = sportshub._games(sim, me, sim.w.groups[gid])
    assert log[0]["play"] == mine["play"] and log[0]["play_tier"] == "great"


def test_a_great_big_moment_wins_close_games_a_miss_loses_them():
    wins = {"great": 0, "miss": 0}
    for tier, score in (("great", 10), ("miss", 1)):
        for seed in range(30):
            sim, me, gid = world()
            it = game_today(sim, gid, n=seed + 1)
            big_moment(sim, me, gid, score, {"mode": "goal", "result": "td" if tier == "great" else "downs", "yards": 3})
            play(sim, it, seed=seed)
            wins[tier] += me.flags["last_game"]["win"]
    assert wins["great"] > wins["miss"] + 3, wins


def test_a_scenes_mini_game_on_game_day_is_the_big_moment():
    sim, me, gid = world()
    game_today(sim, gid)
    r = dialogue.add_script("=== Game Night\nyears: freshman\n\n--- Last Drive\nCoach: Your ball. Win it.\n* \"Give it to me.\" | play football\n"
                            "    great: You walk it in. | mood +\n    good: Close. | mood +\n    miss: Stuffed. | mood -\n")
    assert r["ok"], r.get("errors")
    sim.cat = sim.cat.__class__(sim.w.action_overrides)
    sid = next(s for s, mm in sim.cat.moments.items() if (mm.get("scene") or {}).get("pack") == r["ids"][0])
    moments.trigger(sim, sid, me.id, {})
    m = moments.pending(sim.w)[-1]
    cfg = minigames.start(sim, "football", kind="moment", mid=m["id"], index=0, ctx=m["ctx"])
    minigames.finish(sim, cfg["session"], 9, 10, {"result": "td", "yards": 8})
    p = me.flags["game_play"]
    assert p["day"] == sim.w.day and p["tier"] == "great" and p["source"] == "Last Drive"


def test_storylines_follow_the_last_game():
    sim, me, gid = world()
    w = sim.w
    gameplay.record(me, w.day, "football", "Guilford Football", gid, "Branford", "24-21", True,
                    {"rec": 6, "rec_yds": 98, "rec_td": 1}, True, "great", "Zack scored the touchdown late to win it", False)
    for r, want in (("we_won", True), ("we_lost", False), ("i_played_great", True), ("i_won_it", True), ("i_started", True),
                    ("i_was_benched", False), ("rivalry_game", False)):
        assert dialogue._requirement(sim, me, r) is want, r
    n = gameplay.names(sim, me)
    assert n["last_game"] == "the 24-21 win over Branford" and n["my_line"] == "6 catches for 98 yards and a touchdown"
    assert n["big_play"] == "scored the touchdown late to win it"
    w.day += 4  # a few days on: the game isn't "just happened" any more
    assert dialogue._requirement(sim, me, "we_won") is False
    assert gameplay.names(sim, me)["last_opp"] == "Branford", "the words still say the last game"


def test_a_storyline_in_order_waits_for_the_game_and_plays_the_side_that_happened():
    sim, me, gid = world()
    w = sim.w
    r = dialogue.add_script("""=== Big Game Week
years: freshman

outline:
1. The Week Before | September | Practice is intense.
2. We Did It | September | The town goes nuts. | if we won
3. It Stings | September | Nobody talks on the bus. | if we lost
4. Moving On | September | The next week.

--- 1. The Week Before
Coach: Big one Friday.
* "Ready."
Coach: Good.

--- 2. We Did It
Coach: {last_game}. You had {my_line}.
* "Team win."
Coach: Enjoy it.

--- 3. It Stings
Coach: {last_game}. Head up.
* "Next time."
Coach: That's it.

--- 4. Moving On
Coach: New week.
* "Let's go."
Coach: Good.
""")
    assert r["ok"], r.get("errors")
    sim.cat = sim.cat.__class__(w.action_overrides)
    scheduler._cat_cache.clear()
    cat = scheduler.catalog(sim)
    pk = r["ids"][0]
    ch = cat["chapters"][pk]
    won, lost = ch[1], ch[2]
    assert cat["twins"][won] == [lost] and cat["twins"][lost] == [won]
    done = scheduler.done_map(w)
    done[ch[0]] = [w.day]  # the week before has happened
    w.calendar.append({"day": w.day + 3, "kind": "game", "group": gid, "key": f"game:{gid}:{w.day + 3}:9", "slot": "evening"})
    nxt = scheduler.next_chapter(sim, me, pk, cat)
    assert nxt[0] == won and nxt[1][0] == "waiting_for_game", nxt
    gameplay.record(me, w.day, "football", "Guilford Football", gid, "Branford", "14-21", False, {"rec": 2, "rec_yds": 20}, True,
                    "quiet", None, False)
    nxt = scheduler.next_chapter(sim, me, pk, cat)
    assert nxt == (lost, None), nxt
    done[lost] = [w.day]
    assert scheduler.gate(sim, me, won, cat)[0] == "exclusive_branch"
    assert scheduler.next_chapter(sim, me, pk, cat)[0] == ch[3]


def test_match_it_to_your_games_prompt():
    r = dialogue.add_script("=== Friday Nights\nyears: freshman\n\n--- The Big Game\nCoach: We win this, we're in.\n* \"Let's go.\"\nCoach: Go.\n")
    row = next(p for p in dialogue.packs() if p["id"] == r["ids"][0])
    assert dialogue.pack_summary(row)["games"]
    p = dialogue.prompt_for_games(r["ids"][0])
    for must in ("[if we won]", "The game will go that way", "{my_line}", "Keep everything else", "--- The Big Game", "## Your games"):
        assert must in p, must
    quiet = dialogue.add_script("=== Rainy Days\nyears: freshman\n\n--- Puzzle\nMom: Want to do a puzzle?\n* \"Sure.\"\nMom: Great.\n")
    assert not dialogue.pack_summary(next(p for p in dialogue.packs() if p["id"] == quiet["ids"][0]))["games"]


# --- the storyline decides: a chapter that says how the game went makes the game go that way -----------------------------

ORDERED = """=== Friday Lights
years: freshman

outline:
1. The Week Before | September | Practice is intense.
2. {title} | September | {summary}
3. Moving On | September | The next week.

--- 1. The Week Before
Coach: Big one Friday.
* "Ready."
Coach: Good.

--- 2. {title}
{line}
* "Yeah."
Coach: Okay.

--- 3. Moving On
Coach: New week.
* "Let's go."
Coach: Good.
"""


def _ordered(sim, me, text):
    from lifeos import scheduler as sch
    r = dialogue.add_script(text)
    assert r["ok"], r.get("errors")
    sim.cat = sim.cat.__class__(sim.w.action_overrides)
    sch._cat_cache.clear()
    cat = sch.catalog(sim)
    pk = r["ids"][0]
    ch = cat["chapters"][pk]
    sch.done_map(sim.w)[ch[0]] = [sim.w.day]
    return pk, ch, cat


def _results(text, seeds=12):
    out = []
    for seed in range(seeds):
        sim, me, gid = world()
        pk, ch, cat = _ordered(sim, me, text)
        it = game_today(sim, gid, n=seed + 1)
        play(sim, it, seed=seed)
        out.append((me.flags["last_game"]["win"], scheduler.next_chapter(sim, me, pk, scheduler.catalog(sim))[0] == ch[1]))
    return out


def test_a_storyline_that_says_we_won_makes_the_game_a_win():
    text = ORDERED.format(title="Victory Lap", summary="The town goes nuts.", line="Coach: What a win! The whole town is buzzing.")
    res = _results(text)
    assert all(win for win, _ in res), res
    assert all(nxt for _, nxt in res), "and the chapter is right there, ready to play"


def test_a_storyline_that_says_we_lost_makes_it_a_loss():
    text = ORDERED.format(title="The Bus Home", summary="Nobody talks.", line="Nobody talks on the bus. We lost 21-14.")
    assert not any(win for win, _ in _results(text))


def test_a_tag_or_an_outline_line_calls_it_too_and_both_ways_lets_the_game_decide():
    tagged = ORDERED.format(title="Celebration", summary="Pizza after. | if we won", line="Coach: Pizza's on me.")
    assert all(win for win, _ in _results(tagged))
    both = """=== Coin Flip
years: freshman

outline:
1. The Week Before | September | Practice.
2. We Did It | September | Party. | if we won
3. It Stings | September | Quiet bus. | if we lost

--- 1. The Week Before
Coach: Big one.
* "Ready."
Coach: Good.

--- 2. We Did It
Coach: Party.
* "Yes."
Coach: Go.

--- 3. It Stings
Coach: Head up.
* "Okay."
Coach: Good.
"""
    wins = [w for w, _ in _results(both, seeds=16)]
    assert any(wins) and not all(wins), "both ways written: the real game decides"


def test_reading_the_result_a_scene_takes_for_granted():
    a = gameplay.assumed_result
    assert a("Victory Lap", "Coach: Huge night.") == "we_won"
    assert a("The Bus Home", "Nobody talks. We lost 21-14.") == "we_lost"
    assert a("Film", "Coach: That loss is on all of us.", True) == "we_lost"
    assert a("The Next Morning", "Dad: We beat them!", True) == "we_won"
    for t, x in (("The Big Game", "Coach: We win this, we're in."), ("Rematch", "Last year we lost to them by 30."),
                 ("Hope", "We need a win so bad."), ("Dog", "We lost the dog at the park."), ("Debate", "We won the debate!"),
                 ("Mixed", "We won the opener but we lost the second game.")):
        assert a(t, x, t != "Dog" and t != "Debate") is None, (t, x)
