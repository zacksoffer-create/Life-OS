"""Your games, lined up: the mini game you play, the box score, the Sports tab and your storylines all tell the same game.

- The big moment: on game day, "Take over late" launches your sport's mini game, and so does a storyline scene's
  `play football` on a day you have a football game. Either way, how it went is the game's big moment: it's in your stat
  line as the play itself (the touchdown run, the homer, the late three), it swings a close game (a great play can win
  it, a miss can lose it), and the game's write-up says so.
- The record: every game you play leaves `last_game` on you: the score, win or loss, your line, how you played (great,
  good, quiet, rough, off the bench) and your big moment. Storylines read it: `[if we won]`, `[if I played great]`,
  `{last_game}`, `{my_line}` (dialogue.py), and the Sports tab shows the same game with the same play.
"""
from __future__ import annotations

import functools
import re

# which sport a mini game is the big moment for
GAME_SPORTS = {"football": ("football",), "basketball": ("basketball",), "playmaker": ("basketball",),
               "baseball": ("baseball", "softball"), "swing_lab": ("baseball", "softball"), "soccer_11": ("soccer",),
               "soccer_pk": ("soccer",)}
CLUTCH = {"great": 7, "good": 3, "miss": -2}       # how much better you played (the game-day choice's own numbers)
SWING = {"great": 6.0, "good": 2.0, "miss": -5.0}  # how much the big moment moves the game itself
RECENT_DAYS = 3                                    # a storyline's "after the game" is the few days after it


def todays_game(sim, c, sports) -> str | None:
    """The team of yours with a game in one of these sports today that hasn't been played yet (group id), or None."""
    w = sim.w
    for it in w.calendar:
        if it.get("kind") != "game" or it.get("day") != w.day:
            continue
        g = w.groups.get(it.get("group"))
        if not g or it["group"] not in c.memberships or g.get("skill") not in sports:
            continue
        if it.get("key") in (g.get("played") or []):
            continue
        return it["group"]
    return None


def note_play(sim, c, tier: str, mg: dict | None, sport: str | None = None, source: str = "game day"):
    """How the big moment went (great/good/miss, and what the mini game says happened): it goes into today's game."""
    w = sim.w
    c.flags["game_clutch"] = CLUTCH.get(tier, 0)
    c.flags["game_clutch_day"] = w.day
    c.flags["game_play"] = {"day": w.day, "tier": tier, "game": (mg or {}).get("game"), "stats": dict((mg or {}).get("stats") or {}),
                            "played": bool(mg), "sport": sport, "source": source}


def scene_play(sim, c, game_id: str | None, tier: str, mg: dict | None, source: str):
    """A scene's mini game on a day you have a game in that sport: it's the game's big moment."""
    sports = GAME_SPORTS.get(game_id or "")
    if not sports or (c.flags.get("game_play") or {}).get("day") == sim.w.day:
        return  # not a sport, or today's big moment already happened
    gid = todays_game(sim, c, sports)
    if gid:
        note_play(sim, c, tier, mg, sim.w.groups[gid]["skill"], source)


def todays_play(c, day, sport):
    p = c.flags.get("game_play")
    if not p or p.get("day") != day or (p.get("sport") and p["sport"] != sport):
        return None
    return p


def apply_play(sport: str, pos: str, line: dict, play: dict, first: str, team_tds: int | None) -> str:
    """Put the big moment in the stat line (as the play itself) and say what it was."""
    tier, st = play.get("tier"), play.get("stats") or {}
    yds = int(st.get("yards") or 0)
    if sport == "football":
        how = st.get("result")
        td = (how == "td") if how else tier == "great"
        td = td and (team_tds is None or team_tds > 0)
        if pos == "QB":
            if td:
                line["pass_td"] = line.get("pass_td", 0) + 1
                line["pass_yds"] = line.get("pass_yds", 0) + max(yds, 12)
                return f"{first} threw the touchdown late"
            if how == "turnover" or tier == "miss":
                line["int_thrown"] = line.get("int_thrown", 0) + 1
                return f"{first} threw a pick in the big moment"
            line["pass_yds"] = line.get("pass_yds", 0) + max(yds, 8)
            return f"{first} moved the ball late ({max(yds, 8)} yards)"
        if pos in ("RB", "WR", "TE", "QB") or pos not in ("DL", "LB", "DB", "K", "OL"):
            key = "rush" if pos == "RB" else "rec"
            if key == "rec":
                line["rec"] = line.get("rec", 0) + 1
            if td:
                line[f"{key}_td"] = line.get(f"{key}_td", 0) + 1
                line[f"{key}_yds"] = line.get(f"{key}_yds", 0) + max(yds, 6)
                return f"{first} scored the touchdown late ({max(yds, 6)} yards on the drive)"
            if how in ("turnover", "safety") or tier == "miss":
                return f"{first} was stopped in the big moment"
            line[f"{key}_yds"] = line.get(f"{key}_yds", 0) + max(yds, 5)
            return f"{first} picked up {max(yds, 5)} yards late"
        if pos == "K":
            if tier != "miss":
                line["fg"] = line.get("fg", 0) + 1
                return f"{first} hit the kick late"
            return f"{first} missed the kick late"
        if tier == "great":
            k = "sacks" if pos == "DL" else "ints"
            line[k] = line.get(k, 0) + 1
            return f"{first} made the stop of the game ({'a sack' if k == 'sacks' else 'an interception'})"
        if tier == "good":
            line["tackles"] = line.get("tackles", 0) + 2
            return f"{first} made the stops late"
        return f"{first} got beat on the big play"
    if sport == "basketball":
        if tier == "great":
            line["pts"] = line.get("pts", 0) + 3
            return f"{first} hit the big three late"
        if tier == "good":
            line["pts"] = line.get("pts", 0) + 2
            return f"{first} scored the big bucket late"
        return f"{first} missed the big shot late"
    if sport in ("baseball", "softball"):
        line["ab"] = line.get("ab", 0) + 1
        if tier == "great":
            line["h"] = line.get("h", 0) + 1
            line["hr"] = line.get("hr", 0) + 1
            line["rbi"] = line.get("rbi", 0) + 2
            return f"{first} homered in the big at-bat"
        if tier == "good":
            line["h"] = line.get("h", 0) + 1
            line["rbi"] = line.get("rbi", 0) + 1
            return f"{first} came through with a run-scoring hit late"
        line["k"] = line.get("k", 0) + 1
        return f"{first} struck out in the big at-bat"
    if sport == "soccer":
        goals = int(st.get("goals") or 0)
        if pos == "GK":
            if tier != "miss":
                line["saves"] = line.get("saves", 0) + 1
                return f"{first} made the big save late"
            return f"{first} was beaten late"
        if tier == "great" or goals:
            line["goals"] = line.get("goals", 0) + max(1, min(goals, 2))
            line["shots"] = line.get("shots", 0) + max(1, min(goals, 2))
            return f"{first} scored the big goal late"
        line["shots"] = line.get("shots", 0) + 1
        if tier == "good":
            line["assists"] = line.get("assists", 0) + 1
            return f"{first} set up the big goal late"
        return f"{first} missed the big chance late"
    return f"{first} had the big moment"


def perf_tier(pre: float, perf: float, starter: bool, play: dict | None) -> str:
    """How you played, in a word: great, good, quiet, rough, or bench."""
    if play and play.get("tier") == "great":
        return "great"
    if play and play.get("tier") == "miss":
        return "rough"
    d = perf - pre
    if not starter:
        return "bench" if d < 6 else "good"
    return "great" if d >= 6 else "good" if d >= -2 else "quiet" if d >= -8 else "rough"


def record(c, day, sport, team_name, gid, opp, score, win, line, starter, tier, play_text, rivalry):
    c.flags["last_game"] = {"day": day, "sport": sport, "team": team_name, "group": gid, "opp": opp, "score": score, "win": win,
                            "line": dict(line), "starter": starter, "tier": tier, "play": play_text, "rivalry": rivalry}


# --- what storylines can say ---------------------------------------------------------------------

def last(w, me, recent=True):
    g = (me.flags or {}).get("last_game")
    if not g:
        return None
    if recent and w.day - g["day"] > RECENT_DAYS:
        return None
    return g


def requirement(sim, me, r) -> bool | None:
    """A storyline condition about your games (None: not one of these)."""
    if r not in REQS:
        return None
    g = last(sim.w, me)
    if not g:
        return False
    return {"we_won": g["win"], "we_lost": not g["win"], "i_played_great": g["tier"] == "great",
            "i_played_badly": g["tier"] == "rough", "i_won_it": g["win"] and bool(g.get("play")) and g["tier"] == "great",
            "i_started": g["starter"], "i_was_benched": not g["starter"], "rivalry_game": bool(g.get("rivalry"))}[r]


OTHER_WAY = {"we_won": "we_lost", "we_lost": "we_won", "i_played_great": "i_played_badly", "i_played_badly": "i_played_great",
             "i_started": "i_was_benched", "i_was_benched": "i_started", "i_won_it": "we_lost"}
REQS = {"we_won": "Your team won its last game (in the last few days).", "we_lost": "Your team lost its last game.",
        "i_played_great": "You played great in your last game.", "i_played_badly": "You had a rough last game.",
        "i_won_it": "You won your last game yourself, in the big moment.", "i_started": "You started your last game.",
        "i_was_benched": "You came off the bench (or sat) in your last game.",
        "rivalry_game": "Your last game was against your rival."}


def line_words(sport, line) -> str:
    """"6 catches for 98 yards and a touchdown" (or the box score's own words)."""
    from .sports import line_text
    if sport == "football":
        bits = []
        if line.get("pass_yds"):
            bits.append(f"{line['pass_yds']} passing yards")
        if line.get("rec"):
            bits.append(f"{line['rec']} catch{'es' if line['rec'] != 1 else ''} for {line.get('rec_yds', 0)} yards")
        if line.get("rush_yds"):
            bits.append(f"{line['rush_yds']} yards rushing")
        tds = line.get("pass_td", 0) + line.get("rush_td", 0) + line.get("rec_td", 0)
        if tds:
            bits.append("a touchdown" if tds == 1 else f"{tds} touchdowns")
        if line.get("tackles"):
            bits.append(f"{line['tackles']} tackle{'s' if line['tackles'] != 1 else ''}")
        for k, w1 in (("sacks", "sack"), ("ints", "interception"), ("fg", "field goal")):
            if line.get(k):
                bits.append(f"{line[k]} {w1}{'s' if line[k] != 1 else ''}")
        if not bits:
            return "a quiet night"
        return ", ".join(bits[:-1]) + (" and " if len(bits) > 1 else "") + bits[-1]
    if sport == "basketball":
        bits = [f"{line.get('pts', 0)} points"] + [f"{line[k]} {w1}" for k, w1 in (("reb", "rebounds"), ("ast", "assists")) if line.get(k)]
        return ", ".join(bits)
    return line_text(sport, line)


def names(sim, me) -> dict:
    """The words a storyline's lines can use about your games."""
    w = sim.w
    g = last(w, me, recent=False)
    out = {"last_game": "the last game", "last_opp": "them", "last_score": "", "my_line": "a quiet night", "big_play": "the big play",
           "team_record": "", "my_season": ""}
    if g:
        res = "win over" if g["win"] else "loss to"
        out.update({"last_game": f"the {g['score']} {res} {g['opp']}", "last_opp": g["opp"], "last_score": g["score"],
                    "my_line": line_words(g["sport"], g["line"]), "big_play": (g.get("play") or "the big play").split(" ", 1)[-1]})
        grp = w.groups.get(g["group"]) or {}
        rec = grp.get("record") or {}
        if rec:
            out["team_record"] = f"{rec.get('w', 0)}-{rec.get('l', 0)}"
        from .sports import season_key
        st = me.stats.get(season_key(g["sport"], g["day"], "varsity")) or me.stats.get(season_key(g["sport"], g["day"], "jv"))
        if st and st.get("games"):
            out["my_season"] = f"{line_words(g['sport'], st['line'])} in {st['games']} game{'s' if st['games'] != 1 else ''}"
    return out


NAMES = {"last_game": "your last game, like \"the 24-21 win over Branford\"", "last_opp": "who you played (Branford)",
         "last_score": "the score (24-21)", "my_line": "how you did (6 catches for 98 yards and a touchdown)",
         "big_play": "your big moment (scored the touchdown late)", "team_record": "your team's record (6-2)",
         "my_season": "your season so far (41 catches for 612 yards and 7 touchdowns in 8 games)"}


# --- the storyline decides: a scene that says how the game went makes the game go that way ------------------------------

PAST_SEASON = re.compile(r"\b(last (year|season|time|week|game)|years? ago|ever since|never|haven't|hasn't|didn't|if we|when we|"
                         r"we could|we can|we'll|we will|gonna|going to|need (a|to)|want (a|to))\b", re.I)
WON = re.compile(r"\b(we|you guys|you all|y'all|the team|our team|the boys|the girls)\s+(just\s+|actually\s+|really\s+)?"
                 r"(won|beat|crushed|destroyed|pulled it off)\b|\b(that|what a|big|huge|after the)\s+win\b|\bvictory\b|"
                 r"\bwinning (touchdown|td|shot|goal|run|hit|basket|kick)\b|\bwon the (game|big game|championship|title|rivalry|opener)\b", re.I)
LOST = re.compile(r"\b(we|you guys|you all|y'all|the team|our team|the boys|the girls)\s+(just\s+|actually\s+|really\s+)?"
                  r"(lost|got (crushed|blown out|beat|smoked|destroyed))\b|\b(that|tough|brutal|bad|ugly|after the)\s+loss\b|"
                  r"\blost the (game|big game|championship|title|rivalry|opener)\b|\bdefeat\b", re.I)
GAME_WORDS = re.compile(r"\b(game|games|match|playoffs?|season|scrimmage|homecoming|rivalry|touchdown|scored|coach|score|"
                        r"football|basketball|baseball|soccer|softball)\b", re.I)


STRONG = re.compile(r"\b(what a|that|huge|big|after the|tough|brutal|ugly)\s+(win|loss)\b|\bvictory\b|\bdefeat\b|"
                    r"\b(won|lost) the (game|big game|championship|title|rivalry|opener)\b", re.I)
SCORE = re.compile(r"\b\d{1,3}\s?(-|to)\s?\d{1,3}\b")


@functools.lru_cache(maxsize=16384)
def assumed_result(title: str, text: str, sporty: bool = False) -> str | None:
    """The result a scene takes for granted, from its words ("we won", "that loss"): we_won, we_lost, or None. A scene
    counts as about a game if it says so, has a score, or is in a storyline about a sport (sporty); anything about another
    season, the future or a maybe doesn't count, and both ways is neither."""
    words = f"{title}. {text}"
    about = sporty or bool(GAME_WORDS.search(words) or SCORE.search(words))
    w = l = 0
    for sent in re.split(r"(?<=[.!?])\s+|\n", words):
        if PAST_SEASON.search(sent):
            continue
        strong = STRONG.search(sent)
        if not (about or strong):
            continue
        w += bool(WON.search(sent))
        l += bool(LOST.search(sent))
    return "we_won" if w and not l else "we_lost" if l and not w else None


DECIDES = {"we_won": "win", "i_won_it": "win", "we_lost": "loss"}


def storyline_calls(sim, me, sport) -> dict | None:
    """Does a storyline need your next game to go a certain way? The next chapter of a storyline played in order that's
    waiting only on a game, says (or takes for granted) how it went, and has no other-way twin: {"result": win|loss,
    "great": you played great, "storyline": its name}. None if nothing calls it, or two storylines disagree."""
    from . import dialogue, scheduler
    cat = scheduler.catalog(sim)
    calls = []
    for pk in sorted(cat["ordered"]):
        sid, why = scheduler.next_chapter(sim, me, pk, cat)
        if not sid or not why or why[0] != "waiting_for_game" or (cat.get("twins") or {}).get(sid):
            continue
        info = cat["info"].get(sid) or {}
        if info.get("sport") and info["sport"] != sport:
            continue
        reqs = set((cat["scenes"][sid].get("when") or {}).get("requires") or []) | ({info["assumes"]} if info.get("assumes") else set())
        res = {DECIDES[r] for r in reqs if r in DECIDES}
        if len(res) == 1:
            p = next((x for x in dialogue.packs() if x["id"] == pk), None)
            calls.append({"result": res.pop(), "great": bool(reqs & {"i_played_great", "i_won_it"}), "won_it": "i_won_it" in reqs,
                          "storyline": (p or {}).get("pack", {}).get("name") or pk, "scene": sid})
    if not calls or len({c["result"] for c in calls}) > 1:
        return None
    return calls[0]
