"""Sports: ratings, varsity/JV rosters, starters, box scores, season stats, awards, injuries, recruiting.

A player's sport rating combines learned skill, athletic aptitude, fitness, body (height for
basketball, build for football lines) and confidence. Coaches pick and start players from it;
game stat lines are drawn from position templates scaled by how well the player performed and
how much they played. Season totals feed awards, and awards plus production feed recruiting.
"""
from __future__ import annotations

import math

from . import calendar as calm
from .history import Effects
from .rng import clamp, sigmoid

SPORTS = ("football", "basketball", "baseball", "soccer", "softball")
# Sports only one side plays here (football and baseball are the boys' teams, softball the girls'). Basketball and soccer
# have a boys' team and a girls' team, in high school and in college (the women's college side is keyed "<sport>_w").
ONLY = {"football": "m", "baseball": "m", "softball": "f"}
INJURY_RATE = {"football": 0.010, "basketball": 0.005, "baseball": 0.0035, "soccer": 0.006, "softball": 0.0035}
INJURIES = {
    "football": [("sprained ankle", 10, 21), ("shoulder strain", 10, 28), ("concussion", 7, 18), ("torn hamstring", 21, 42), ("broken wrist", 28, 49)],
    "basketball": [("sprained ankle", 7, 21), ("jammed finger", 4, 10), ("knee strain", 10, 28), ("back spasms", 5, 14)],
    "baseball": [("pulled hamstring", 7, 21), ("sore elbow", 7, 24), ("sprained wrist", 7, 18)],
    "soccer": [("sprained ankle", 7, 21), ("pulled groin", 7, 21), ("knee sprain", 14, 35), ("concussion", 7, 18), ("bruised shin", 4, 10)],
    "softball": [("pulled hamstring", 7, 21), ("sore shoulder", 7, 21), ("sprained wrist", 7, 18), ("jammed finger", 4, 10)],
}
BAT_SPORTS = ("baseball", "softball")
BUILD_BONUS = {"slight": -5, "average": 0, "athletic": 4, "strong": 5}
CONF_SHORT = {"Southern Connecticut Conference": "SCC", "Big Ten": "Big Ten", "Big East": "Big East", "SEC": "SEC", "ACC": "ACC", "NE10": "NE10"}


# --- who plays where: boys' and girls' teams ---------------------------------------------

def sports_for(gender) -> list:
    """The sports someone can play on a school team. Nonbinary students can try out for either side."""
    return [s for s in SPORTS if ONLY.get(s) in (None, gender) or gender not in ("m", "f")]


def side(sport, gender) -> str:
    """The program key for a sport and a player's gender: 'soccer_w' is women's soccer; softball is already women's."""
    return f"{sport}_w" if gender == "f" and sport not in ONLY else sport


def side_label(sport, gender, labels) -> str:
    """'Women's Soccer', 'Men's Basketball', 'Football'."""
    base = labels.get(sport, {}).get("label", sport.title())
    if sport in ONLY:
        return base
    return ("Women's " if side(sport, gender).endswith("_w") else "Men's ") + base


def can_play(c, g) -> bool:
    """Whether this person can be on this team: boys' teams are for boys, girls' teams for girls (nonbinary: either)."""
    want = g.get("gender")
    return not want or c.gender not in ("m", "f") or c.gender == want


def team_for(w, c, sport, school="hchs"):
    """The team id for this person in this sport at a school ('hchs' or 'college'), or None when there isn't one."""
    if school == "college":
        gid = f"col_{side(sport, c.gender)}"
        return gid if gid in w.groups else None
    for g in sorted(w.groups.values(), key=lambda g: g["id"]):
        if g["kind"] == "team" and g.get("skill") == sport and g.get("school") == school and can_play(c, g):
            return g["id"]
    return None


SWAP = {"f": {"baseball": "softball"}, "m": {"softball": "baseball"}}  # the same swing, the other side's team


def fit_sport(sport, gender):
    """The sport someone of this gender would actually play for this one ('baseball' for a girl is softball)."""
    return SWAP.get(gender, {}).get(sport, sport)


def fit_to_side(c) -> list:
    """Point someone's sports at teams they can be on: a girl who plays baseball plays softball, a boy who plays softball
    plays baseball. Interest, skill and position carry over. Returns the (from, to) pairs that moved."""
    moved = []
    for a, b in SWAP.get(c.gender, {}).items():
        if c.interests.get(a, 0) <= c.interests.get(b, 0):
            continue
        c.interests[b] = c.interests.pop(a)
        if c.skills.get(a, 0) > c.skills.get(b, 0):
            c.skills[b] = c.skills[a]
        if a in c.positions and b not in c.positions:
            c.positions[b] = c.positions[a]
        moved.append((a, b))
    return moved


def offers_side(col, sport, gender) -> bool:
    return side(sport, gender) in col.get("programs", {})


def _season_days(g):
    a = calm.md_to_day(0, tuple(g["season"]["start"]))
    b = calm.md_to_day(0, tuple(g["season"]["end"]))
    if b < a:
        b = calm.md_to_day(1, tuple(g["season"]["end"]))
    return a, b


def seasons_overlap(g1, g2) -> bool:
    a1, b1 = _season_days(g1)
    a2, b2 = _season_days(g2)
    return a1 <= b2 and a2 <= b1


def clash(w, c, g):
    """Another team this person is on (or trying out for) whose season overlaps this one: one sport a season."""
    year = calm.school_year_of(w.day)
    for o in sorted(w.groups.values(), key=lambda o: o["id"]):
        if o["id"] == g["id"] or o["kind"] != "team" or o.get("school") != g.get("school") or not seasons_overlap(o, g):
            continue
        if o["id"] in c.memberships or c.id in w.registrations.get(f"tryout:{o['id']}:{year}", []):
            return o
    return None


def program(col, sport) -> float:
    """A program's strength, 0-100. `sport` can be a side key ('soccer_w')."""
    return float(col.get("programs", {}).get(sport, 0))


def recruit_bar(col, sport) -> float:
    """The recruiting score a player needs before this program offers."""
    return 52 + 0.36 * program(col, sport)


def team_level(col, sport) -> float:
    """How well this program's team plays (the bar for starting, and the opponents' strength)."""
    return 58 + 0.2 * program(col, sport)


def college_level(meta, sport) -> float:
    return (meta.get("levels") or {}).get(sport, meta.get("level", 70))


def aid_label(col, sport) -> str:
    # football and basketball scholarships are full rides at D1; soccer, baseball and softball split theirs
    return "full scholarship" if sport in ("football", "basketball") and col.get("tier") == "D1" else "partial scholarship"


def poisson(rng, lam: float) -> int:
    lam = max(0.0, lam)
    if lam > 30:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1


def binom(rng, n: int, p: float) -> int:
    return sum(1 for _ in range(n) if rng.random() < p)


# --- bodies and positions ------------------------------------------------------------

def default_body(c, rng) -> dict:
    mean = {"m": 69.5, "f": 64.5}.get(c.gender, 67.0)
    sd = 3.0 if c.gender != "f" else 2.6
    h = mean + rng.gauss(0, sd) + (c.aptitudes.get("athletic", 50) - 50) / 25
    if c.grade and c.grade <= 10:
        h -= (11 - c.grade) * 0.8  # still growing
    h = clamp(h, mean - 6.5, mean + 9)
    a = c.aptitudes.get("athletic", 50)
    r = rng.random()
    if a >= 65:
        build = "athletic" if r < 0.6 else "strong"
    elif a <= 40:
        build = "slight" if r < 0.55 else "average"
    else:
        build = "average" if r < 0.5 else ("athletic" if r < 0.75 else ("strong" if r < 0.88 else "slight"))
    return {"height_in": int(round(h)), "build": build}


def default_position(c, sport: str, rng) -> str:
    b = c.body or {}
    h = b.get("height_in", 68)
    build = b.get("build", "average")
    t = c.traits
    if sport == "basketball":
        return "C" if h >= 77 else "PF" if h >= 74 else "SF" if h >= 72 else "SG" if h >= 69 else "PG"
    if sport == "football":
        if build == "strong":
            return "OL" if rng.random() < 0.5 else "DL"
        if build == "slight":
            return ["WR", "DB", "K"][int(rng.random() * 3)]
        if t["confidence"] > 65 and c.aptitudes.get("academic", 50) > 55 and rng.random() < 0.35:
            return "QB"
        return ["RB", "WR", "LB", "DB", "TE", "LB"][int(rng.random() * 6)]
    if sport in BAT_SPORTS:
        if t["competitiveness"] > 65 and rng.random() < 0.4:
            return "P"
        if build == "strong" and t["discipline"] > 55 and rng.random() < 0.4:
            return "C"
        return ["1B", "2B", "SS", "3B", "OF", "OF"][int(rng.random() * 6)]
    if sport == "soccer":
        if h >= ({"f": 67}.get(c.gender, 72)) and t["confidence"] > 55 and rng.random() < 0.3:
            return "GK"
        if build == "strong":
            return "CB"
        if build == "slight":
            return ["WM", "CM", "FB"][int(rng.random() * 3)]
        if t["competitiveness"] > 65 and t["confidence"] > 60 and rng.random() < 0.45:
            return "ST"
        return ["CM", "FB", "WM", "CB", "ST", "CM"][int(rng.random() * 6)]
    return ""


def ensure_athlete(c, sport, rng):
    if not c.body:
        c.body = default_body(c, rng)
    if sport and sport not in c.positions:
        c.positions[sport] = default_position(c, sport, rng)
    if not c.jersey:
        c.jersey = 1 + int(rng.random() * 98)


def body_bonus(c, sport, pos=None) -> float:
    b = c.body or {}
    h = b.get("height_in", 68)
    build = b.get("build", "average")
    pos = pos or c.positions.get(sport)
    if sport == "basketball":
        v = (h - 70) * 1.1
        if pos in ("C", "PF"):
            v += (h - 74) * 0.5
        return clamp(v, -12, 14)
    if sport == "football":
        v = BUILD_BONUS.get(build, 0)
        if pos in ("OL", "DL"):
            v += {"strong": 7, "athletic": 2, "average": -2, "slight": -10}.get(build, 0)
        if pos in ("WR", "DB", "RB"):
            v += {"slight": 3, "athletic": 3, "strong": -2}.get(build, 0)
        return v
    if sport in BAT_SPORTS and pos == "P":
        return (h - (65 if sport == "softball" else 70)) * 0.4
    if sport == "soccer":
        v = {"slight": 1, "average": 0, "athletic": 4, "strong": 2}.get(build, 0)
        if pos == "GK":
            v += clamp((h - (66 if c.gender == "f" else 71)) * 0.6, -4, 5)
        if pos == "CB":
            v += {"strong": 3, "slight": -4}.get(build, 0)
        return v
    return 0.0


def rating(c, sport: str, pos=None) -> float:
    """How good someone is at a sport right now (0-100ish, no randomness)."""
    sk = c.skills.get(sport, 0)
    fit = c.skills.get("fitness", 30)
    return (0.6 * sk + 0.15 * c.aptitudes.get("athletic", 50) + 0.12 * fit + body_bonus(c, sport, pos)
            + 0.06 * (c.traits.get("confidence", 50) - 50) + 6)


def healthy(w, cid) -> bool:
    return w.chars[cid].flags.get("injured_until", -1) < w.day


def season_key(sport, day, level):
    y = calm.START.year + calm.school_year_of(day)
    return f"{sport}:{y}-{str(y + 1)[2:]}:{level}"


# --- box scores ------------------------------------------------------------------------

def stat_line(sport, pos, f, starter, rng) -> dict:
    if sport == "football":
        if pos == "QB":
            return {"pass_yds": max(0, int(rng.gauss(170 * f, 45))), "pass_td": poisson(rng, 1.4 * f),
                    "int_thrown": poisson(rng, 0.9 * max(0.3, 1.6 - f)), "rush_yds": int(rng.gauss(15 * f, 12))}
        if pos == "RB":
            rec = poisson(rng, 1.5 * f)
            return {"rush_yds": max(-5, int(rng.gauss(75 * f, 25))), "rush_td": poisson(rng, 0.7 * f), "rec": rec,
                    "rec_yds": max(0, int(rec * rng.gauss(8, 3)))}
        if pos in ("WR", "TE"):
            k = 3.5 if pos == "WR" else 2.0
            rec = poisson(rng, k * f)
            return {"rec": rec, "rec_yds": max(0, int(rec * rng.gauss(13 if pos == "WR" else 10, 4))),
                    "rec_td": poisson(rng, (0.45 if pos == "WR" else 0.25) * f)}
        if pos == "DL":
            return {"tackles": poisson(rng, 2.5 * f), "sacks": poisson(rng, 0.5 * f)}
        if pos == "LB":
            return {"tackles": poisson(rng, 5.5 * f), "sacks": poisson(rng, 0.3 * f), "ints": poisson(rng, 0.1 * f)}
        if pos == "DB":
            return {"tackles": poisson(rng, 3.5 * f), "ints": poisson(rng, 0.25 * f)}
        if pos == "K":
            return {"fg": poisson(rng, 1.0 * f)}
        return {"tackles": poisson(rng, 0.4 * f)}  # OL: rarely in the box score
    if sport == "basketball":
        base = {"PG": (10, 3, 5), "SG": (13, 3, 2.5), "SF": (11, 5, 2), "PF": (9, 7, 1.5), "C": (8, 8, 1)}.get(pos, (9, 4, 2))
        return {"pts": max(0, int(rng.gauss(base[0] * f, 3))), "reb": poisson(rng, base[1] * f), "ast": poisson(rng, base[2] * f),
                "stl": poisson(rng, 0.9 * f), "blk": poisson(rng, (1.5 if pos == "C" else 0.8 if pos == "PF" else 0.3) * f)}
    if sport == "soccer":
        # goals, assists and shots by where you play; keepers make saves and keep clean sheets (set by the game)
        g, a, sh = {"ST": (0.55, 0.2, 3.2), "WM": (0.3, 0.3, 2.0), "CM": (0.18, 0.32, 1.4), "FB": (0.05, 0.15, 0.4),
                    "CB": (0.06, 0.04, 0.4), "GK": (0.0, 0.0, 0.0)}.get(pos, (0.15, 0.15, 1.0))
        if pos == "GK":
            return {"saves": poisson(rng, 4.0 * clamp(f, 0.4, 1.6))} if starter else {}
        shots = poisson(rng, sh * f)
        return {"goals": min(shots, poisson(rng, g * f)), "assists": poisson(rng, a * f), "shots": shots}
    if sport in BAT_SPORTS:
        ab = 4 if starter else 1
        avg = clamp(0.12 + 0.22 * f, 0.05, 0.5)
        h = binom(rng, ab, avg)
        hr = binom(rng, h, clamp(0.1 * f, 0, 0.4))
        line = {"ab": ab, "h": h, "hr": hr, "rbi": poisson(rng, 0.5 * h + hr), "sb": poisson(rng, 0.2 * f)}
        if pos == "P" and starter:
            ip = round(clamp(rng.gauss(5 * f, 1), 1, 7))
            line.update({"ip": ip, "k": poisson(rng, ip * 1.1 * f), "er": poisson(rng, ip * 0.45 * max(0.3, 1.5 - f))})
        return line
    return {}


def line_text(sport, line) -> str:
    order = {"football": [("pass_yds", "pass yds"), ("pass_td", "TD"), ("rush_yds", "rush yds"), ("rush_td", "TD"), ("rec", "rec"),
                          ("rec_yds", "yds"), ("rec_td", "TD"), ("tackles", "tackles"), ("sacks", "sacks"), ("ints", "INT"), ("fg", "FG")],
             "basketball": [("pts", "PTS"), ("reb", "REB"), ("ast", "AST"), ("stl", "STL"), ("blk", "BLK")],
             "baseball": [("h", "H"), ("ab", "AB"), ("hr", "HR"), ("rbi", "RBI"), ("k", "K"), ("ip", "IP")],
             "soccer": [("goals", "G"), ("assists", "A"), ("saves", "saves"), ("clean_sheets", "clean sheets"), ("shots", "shots")]}
    order["softball"] = order["baseball"]
    order = order[sport]
    parts = []
    for k, label in order:
        v = line.get(k)
        if not v:
            continue
        if sport in BAT_SPORTS and k == "h":
            parts.append(f"{v}-for-{line.get('ab', 0)}")
            continue
        if sport in BAT_SPORTS and k == "ab":
            continue
        if sport == "soccer" and k in ("goals", "assists", "shots", "saves"):
            word = {"goals": "goal", "assists": "assist", "shots": "shot", "saves": "save"}[k]
            parts.append(f"{v} {word}{'s' if v != 1 else ''}")
            continue
        if sport == "soccer" and k == "clean_sheets" and v == 1:
            parts.append("a clean sheet")
            continue
        if v == 1 and label in ("tackles", "sacks"):
            label = label[:-1]
        parts.append(f"{v} {label}")
    return ", ".join(parts[:4]) if parts else "limited minutes"


def add_line(dst: dict, line: dict):
    for k, v in line.items():
        dst[k] = dst.get(k, 0) + v


# --- games -----------------------------------------------------------------------------

def opponent_name(sim, g, n: int) -> str:
    school = "college" if g.get("school") == "college" else "hchs"
    names = sim.cat.world.get("opponents", {}).get(school) or ["Rival"]
    meta = sim.w.meta.get("college")
    if school == "college" and meta and meta["id"] in sim.cat.college_by_id:
        opp = sim.cat.college_by_id[meta["id"]].get("opponents", {})
        names = opp.get(g.get("skill")) or opp.get("default") or names
    return names[(n * 7 + len(g["id"])) % len(names)]


def soccer_box(box, score, win, rng):
    """Make the box score add up to the scoreline: each of our goals goes to one player (strikers most often), most
    have an assist, and a starting keeper who conceded nothing keeps a clean sheet."""
    a, b = (int(x) for x in score.split("-"))
    ours, theirs = (max(a, b), min(a, b)) if win else (min(a, b), max(a, b))
    field = sorted(k for k, v in box.items() if v["pos"] != "GK")
    weight = {k: max(0.05, box[k]["line"].get("shots", 0) + {"ST": 1.2, "WM": 0.7, "CM": 0.45}.get(box[k]["pos"], 0.12)) for k in field}
    for k in field:
        box[k]["line"]["goals"] = 0
        box[k]["line"]["assists"] = 0
    def pick(pool):
        tot = sum(weight[k] for k in pool)
        x = rng.random() * tot
        for k in pool:
            x -= weight[k]
            if x <= 0:
                return k
        return pool[-1]
    for _ in range(ours if field else 0):
        k = pick(field)
        box[k]["line"]["goals"] += 1
        box[k]["line"]["shots"] = max(box[k]["line"].get("shots", 0), box[k]["line"]["goals"])
        others = [o for o in field if o != k]
        if others and rng.random() < 0.72:
            box[pick(others)]["line"]["assists"] += 1
    for k, v in box.items():
        if v["pos"] == "GK" and v["starter"]:
            v["line"]["saves"] = v["line"].get("saves", 0)
            if theirs == 0:
                v["line"]["clean_sheets"] = 1
        for key in ("goals", "assists"):
            if not v["line"].get(key):
                v["line"].pop(key, None)


def football_score(margin, rng):
    """A football score that adds up: touchdowns (7) and field goals (3) for each side, the winner by about the margin.
    Returns (winner's points, loser's points, the winner-or-loser's touchdown budget for your box score)."""
    gap = max(1, int(abs(margin) / 1.6))
    lose_td, lose_fg = int(rng.random() * 3), int(rng.random() * 2)
    lose = 7 * lose_td + 3 * lose_fg
    win_td, win_fg = lose_td, lose_fg
    while 7 * win_td + 3 * win_fg - lose < gap or 7 * win_td + 3 * win_fg <= lose:
        if rng.random() < 0.6:
            win_td += 1
        else:
            win_fg += 1
    return 7 * win_td + 3 * win_fg, lose, (win_td, lose_td)


def play_game(inst, it, rng):
    sim = inst.sim
    w = sim.w
    g = w.groups[it["group"]]
    levels = g.setdefault("levels", {})
    came = set(sim.slot.attend.get(("event", it["key"]), []))
    fans = sorted(set(sim.slot.attend.get(("spectate", it["key"]), [])))
    num = int(it["key"].split(":")[-1]) if it["key"].split(":")[-1].isdigit() else 1
    done = g.setdefault("played", [])
    if it["key"] in done:
        return  # a game is played once, whatever happens to the save or the slot
    done.append(it["key"])
    del done[:-60]
    for level in ("varsity", "jv"):
        squad = [m for m in g["members"] if levels.get(m, "varsity") == level]
        if not squad:
            continue
        players = sorted(c for c in squad if c in came and healthy(w, c))
        missing = sorted(c for c in squad if c not in came and healthy(w, c))
        _game(inst, g, it, level, players, missing, fans if level == "varsity" else [], num, rng)


def _game(inst, g, it, level, players, missing, fans, num, rng):
    from .institutions import ambient, mark
    sim = inst.sim
    w = sim.w
    sport = g["skill"]
    n_start = g.get("starters", 5)
    pre = {cid: rating(w.chars[cid], sport) for cid in players}
    starters = sorted(players, key=lambda x: (-pre[x], x))[:n_start]
    perf, share, appr = {}, {}, {}
    for cid in players:
        c = w.chars[cid]
        approach = c.flags.get("game_approach") if c.flags.get("game_approach_day") == w.day else None
        appr[cid] = approach
        bonus = {"all_out": 4.0, "smart": 0.0, "team": -1.0}.get(approach, 0.0)
        if c.flags.get("game_clutch_day") == w.day:  # you played the big moment yourself
            bonus += float(c.flags.get("game_clutch", 0))
        perf[cid] = pre[cid] + rng.gauss(0, 7) + bonus + (c.mood - 55) * 0.05
    college = w.meta.get("college") if g.get("school") == "college" else None
    clevel = college_level(college, g.get("side") or sport) if college else None
    filler = (clevel - 8) if college else 38.0
    if college:
        bar = clevel + 2
        starters = [s for s in starters if pre[s] + (w.chars[s].grade - 13) * 2 >= bar or len(players) <= n_start // 2]
        share = {}
    filled = [perf[s] for s in starters] + [filler] * max(0, n_start - len(starters))
    share = {cid: 1.0 if cid in starters else 0.3 for cid in players}
    strength = sum(filled) / max(1, len(filled))
    base = clevel if college else (48 if level == "varsity" else 41)
    rivalry = False
    if level == "varsity":  # a real team in the league: its own strength, record and stars (league.py)
        from . import league as lg
        ot = lg.opponent(sim, g, num)
        opp = ot["strength"] + rng.gauss(0, 5)
        oname = ot["name"]
        rivalry = oname == lg.league(sim, g).get("rival")
    else:
        opp = base + rng.gauss(0, 8)
        oname = opponent_name(sim, g, num)
    home = 2 if fans else 0
    margin = strength - opp + rng.gauss(0, 6) + home
    from . import gameplay
    you_ = w.meta.get("protagonist")
    play = gameplay.todays_play(w.chars[you_], w.day, sport) if you_ in players else None
    before = margin
    if play:  # your big moment (the mini game) can win a close game, or lose one
        margin += gameplay.SWING.get(play["tier"], 0) * (1.0 if you_ in starters else 0.6)
    call = gameplay.storyline_calls(sim, w.chars[you_], sport) if you_ in players else None
    if call:  # a storyline says how this game goes: it goes that way (by about as much as it would have)
        if call["result"] == "win" and margin <= 0:
            margin = abs(margin) * 0.6 + 1 + rng.random() * 4
        elif call["result"] == "loss" and margin > 0:
            margin = -(abs(margin) * 0.6 + 1 + rng.random() * 4)
        if call["great"]:
            perf[you_] = max(perf[you_], pre[you_] + 7)
    win = margin > 0
    score = inst.score_line(sport, margin, rng)
    tds = None
    if sport == "football":
        a, b, (wtd, ltd) = football_score(margin, rng)
        score = f"{a}-{b}" if win else f"{b}-{a}"
        tds = {"team": wtd if win else ltd, "left": wtd if win else ltd}
    box = {}
    skey = season_key(sport, w.day, level)
    for cid in players:
        c = w.chars[cid]
        pos = c.positions.get(sport) or default_position(c, sport, rng)
        f = clamp(perf[cid] / 62, 0.25, 1.8) * (1.0 if cid in starters else 0.35)
        line = stat_line(sport, pos, f, cid in starters, rng)
        if tds is not None:
            # touchdowns come out of the team's: a rusher or receiver can't score more than the team did
            for k in ("rush_td", "rec_td"):
                if k in line:
                    line[k] = min(line[k], tds["left"])
                    tds["left"] -= line[k]
            if "pass_td" in line:
                line["pass_td"] = min(line["pass_td"], tds["team"])
        box[cid] = {"pos": pos, "starter": cid in starters, "line": line, "perf": round(perf[cid], 1), "approach": appr[cid]}
    if sport == "soccer":
        soccer_box(box, score, win, rng)
    if not play and call and call.get("won_it") and win:  # "I won it": the storyline's big moment, in the box score
        play = {"tier": "great", "stats": {}}
    play_text = None
    if play:
        me_ = w.chars[you_]
        play_text = gameplay.apply_play(sport, box[you_]["pos"], box[you_]["line"], play, me_.first,
                                        (tds or {}).get("team") if tds is not None else None)
        if win and play["tier"] == "miss":
            play_text += ", but they held on"
        elif not win and play["tier"] == "great":
            play_text += ", but it wasn't enough"
        elif win and before <= 0:
            play_text += " to win it"
        elif not win and before > 0:
            play_text += ", and they lost it late"
        box[you_]["play"] = play_text
    for cid in players:
        c = w.chars[cid]
        line = box[cid]["line"]
        st = c.stats.setdefault(skey, {"sport": sport, "level": level, "team": g["id"], "team_name": g["name"],
                                       "school": g.get("school"), "games": 0, "starts": 0, "wins": 0, "losses": 0,
                                       "line": {}, "impact": 0.0})
        st["games"] += 1
        st["starts"] += 1 if cid in starters else 0
        st["wins" if win else "losses"] += 1
        st["impact"] = round(st["impact"] + perf[cid] * share[cid], 2)
        add_line(st["line"], line)
    label = f"{g['name']}{' JV' if level == 'jv' else ''}"
    ev = inst.event("game", "win" if win else "loss", players, importance=14 if level == "varsity" else 7, group=g["id"],
                    involved=fans, data={"group": label, "score": score, "opponent": oname, "level": level, "sport": sport,
                                          "box": box, "starters": starters, "fans": len(fans)})
    ev["text"] = f"{label} {'beat' if win else 'lost to'} {'rival ' if rivalry else ''}{oname}, {score}." + (f" {play_text}." if play_text else "")
    ev["data"]["rivalry"] = rivalry
    if play_text:
        ev["data"]["play"] = play_text
        ev["data"]["play_tier"] = play["tier"]
    if call:
        ev["data"]["storyline"] = call["storyline"]  # (the lab can see the storyline called this one)
    if you_ in players:  # what storylines (and the Sports tab) know about your last game
        tier_ = gameplay.perf_tier(pre[you_], perf[you_], you_ in starters, play)
        if call and call["great"]:
            tier_ = "great"
        gameplay.record(w.chars[you_], w.day, sport, label, g["id"], oname, score, win, box[you_]["line"], you_ in starters,
                        tier_, play_text, rivalry)

    if w.tracing:
        ev["calc"] = [{"step": "game result", "terms": [["team strength (avg of starters' performances)", round(strength, 2)],
                                                         ["opponent strength", round(opp, 2)], ["home crowd", home]],
                       "total": round(margin, 2), "outcome": "win" if win else "loss",
                       "rule": f"{n_start} starters picked by sport rating (skill, aptitude, fitness, body, confidence); performance = rating + luck",
                       "performances": {k: round(v, 1) for k, v in perf.items()}}]
    fx = Effects(w, ev)
    if level == "varsity":
        g["record"]["w" if win else "l"] += 1
        from . import league as lg
        lg.record(sim, inst, g, num, win, score, box, rng)
    else:
        g.setdefault("record_jv", {"w": 0, "l": 0})["w" if win else "l"] += 1
    for cid in players:
        fx.mood(cid, 6 if win else -4, "game")
        fx.need(cid, "energy", -14 if cid in starters else -6, "game")
        fx.need(cid, "fun", 10 if win else 3, "game")
        fx.rep(cid, "athlete", 1.0 if cid in starters else 0.3, "played")
        mark(g, cid, True)
        if appr[cid] == "team":
            for o in players[:6]:
                if o != cid:
                    fx.rel(o, cid, "affection", 1.5, "played for the team")
    for i in range(len(players)):
        for j in range(i + 1, min(len(players), i + 4)):
            ambient(sim, fx, players[i], players[j], 0.3 if win else 0.05, f"{label} game")
    for cid in fans:
        fx.need(cid, "social", 10, "watched the game")
        fx.need(cid, "fun", 9 if win else 5, "watched the game")
    coach = g.get("staff")
    for cid in missing:
        mark(g, cid, False)
        if coach:
            fx.rel(coach, cid, "respect", -8, "missed a game")
    sim.attach_traces(ev, players + fans)
    sim.finish(ev, fx)
    you = w.meta.get("protagonist")
    if you in missing:  # the team played without you: say so, or the record looks like it jumped
        e0 = inst.event("game", "missed", [you], importance=24 if level == "varsity" else 14, group=g["id"],
                        data={"group": label, "score": score, "opponent": oname, "level": level, "sport": sport})
        e0["text"] = f"{w.chars[you].short} missed the game. {label} {'beat' if win else 'lost to'} {oname}, {score}."
        e0["causes"] = [ev["id"]]
        sim.finish(e0, Effects(w, e0))
    # first starts and standouts
    for cid in starters:
        c = w.chars[cid]
        k = f"started:{g['id']}:{level}"
        if not c.flags.get(k):
            c.flags[k] = w.day
            e2 = inst.event("game", "first_start", [cid], importance=30, group=g["id"], data={"group": label})
            e2["text"] = f"{c.short} made their first start for {label}."
            e2["causes"] = [ev["id"]]
            f2 = Effects(w, e2)
            f2.memory(cid, "first_start", [coach] if coach else [], 0.7, 60, f"First start for {label}")
            sim.confidence(cid, 1.5, f2, "first start")
            sim.finish(e2, f2)
    prot = w.meta.get("protagonist")
    if prot in players and level == "varsity":
        pc = w.chars[prot]
        streak = 0 if prot in starters else pc.flags.get("bench_streak", 0) + 1
        pc.flags["bench_streak"] = streak
        if streak == 3:
            sim.moment_trigger("benched", prot, {"group": g["id"], "games": streak})
    notable = [k for k in players if any(v for v in box[k]["line"].values())]
    if notable:
        star = max(notable, key=lambda k: (perf[k] * share[k], k))
        if level == "varsity" or w.meta.get("protagonist") == star:
            line = box[star]["line"]
            e3 = inst.event("game", "star", [star], importance=26 if level == "varsity" else 14, group=g["id"],
                            data={"group": label, "score": score, "line": line})
            e3["text"] = f"{w.chars[star].short} led {label}: {line_text(sport, line)}."
            e3["causes"] = [ev["id"]]
            f3 = Effects(w, e3)
            f3.rep(star, "star", 3, "standout game")
            f3.mood(star, 5, "standout game")
            if level == "varsity":  # word gets around school (more if it was the rival game)
                from . import league as lg
                lg.buzz(sim, f3, star, 16 if rivalry else 10, f"a big game against {oname}", sport)
            if win:
                f3.memory(star, "star_game", [], 0.55, 45, f"{line_text(sport, line)} in a {score} win over {oname}")
            sim.finish(e3, f3)
    # injuries
    for cid in players:
        c = w.chars[cid]
        mult = {"all_out": 1.8, "smart": 0.6}.get(box[cid].get("approach"), 1.0)
        p = INJURY_RATE[sport] * (1.35 - c.skills.get("fitness", 30) / 100) * share[cid] * mult * (1.4 if g.get("school") == "college" else 1)
        if rng.random() < p:
            injure(inst, cid, sport, rng, ev)
    for cid in missing:
        from .institutions import misses
        if misses(g, cid) > w.rules["inst.absence_tolerance"] and cid in g["members"]:
            inst.drop(g["id"], cid, "dropped", ev, rng)


def injure(inst, cid, sport, rng, cause=None, during="game"):
    sim = inst.sim
    w = sim.w
    c = w.chars[cid]
    name, lo, hi = INJURIES[sport][int(rng.random() * len(INJURIES[sport]))]
    days = int(lo + rng.random() * (hi - lo))
    ev = inst.event("injury", "hurt", [cid], importance=34, data={"label": name, "n": days, "sport": sport})
    ev["text"] = f"{c.short} suffered a {name} {'in a game' if during == 'game' else 'at practice'} and will be out about {max(1, days // 7)} week{'s' if days >= 14 else ''}."
    if cause and cause.get("id"):
        ev["causes"] = [cause["id"]]
    fx = Effects(w, ev)
    fx.flag(cid, "injured_until", w.day + days, name)
    fx.flag(cid, "injury", name, name)
    fx.mood(cid, -10, name)
    fx.need(cid, "stress", 9, name)
    fx.memory(cid, "injured", [], -0.6, 60, f"Got hurt: {name}")
    sim.finish(ev, fx)
    sim.moment_trigger("injury", cid, {"injury": name, "days": days, "sport": sport, "event": ev.get("id")})


# --- seasons, awards, recruiting -----------------------------------------------------------

def season_awards(inst, g):
    """Team MVP and all-conference honors from the season's recorded games."""
    sim = inst.sim
    w = sim.w
    sport = g["skill"]
    skey = season_key(sport, w.day, "varsity")
    rows = []
    for cid in g["members"]:
        st = w.chars[cid].stats.get(skey)
        if st and st["games"]:
            rows.append((st["impact"], cid, st))
    rows.sort(key=lambda r: (-r[0], r[1]))
    awards = []
    if rows:
        awards.append((rows[0][1], f"{g['name']} MVP"))
        for imp, cid, st in rows:
            if st["starts"] >= max(2, st["games"] // 2) and imp / st["games"] >= (66 if g.get("school") == "college" else 60):
                if g.get("school") == "college" and w.meta.get("college"):
                    conf = sim.cat.college_by_id[w.meta["college"]["id"]].get("conference") or "Conference"
                else:
                    conf = sim.cat.world["school"].get("conference", "Conference")
                awards.append((cid, f"All-{CONF_SHORT.get(conf, conf)} {sim.cat.sports['sports'][sport]['label']}"))
    for cid, label in awards:
        c = w.chars[cid]
        ev = inst.event("award", "won", [cid], importance=36, group=g["id"], data={"label": label})
        ev["text"] = f"{c.short} was named {label}."
        fx = Effects(w, ev)
        c.awards.append({"day": w.day, "label": label, "sport": sport, "season": skey})
        c.achievements.append({"day": w.day, "label": label, "event": ev.get("id")})
        fx.rep(cid, "star", 6, label)
        from . import league as lg
        lg.buzz(sim, fx, cid, 22 if label.startswith("All-") else 14, label, sport)
        fx.memory(cid, "award", [], 0.8, 70, f"Named {label}")
        sim.confidence(cid, 2.0, fx, label)
        sim.finish(ev, fx)
    return awards


def recruit_score(c, sport) -> float:
    entries = [st for k, st in c.stats.items() if k.startswith(sport + ":") and st["level"] == "varsity" and st["games"]]
    prod = 0.0
    if entries:
        last = entries[-1]
        prod = (last["impact"] / last["games"] - 60) * 0.25
    aw = min(6, 2 * sum(1 for a in c.awards if a.get("sport") == sport))
    return rating(c, sport) + prod + aw + ((c.grade or 12) - 10) * 1.0


def recruiting_update(inst, c, sport, rng):
    sim = inst.sim
    w = sim.w
    if c.role != "student" or c.school != "hchs" or (c.grade or 0) < 10:
        return
    rec = c.recruiting
    rec.setdefault("interest", {})
    rec.setdefault("offers", [])
    rec.setdefault("score", {})
    score = recruit_score(c, sport)
    rec["score"][sport] = round(score, 1)
    sd = side(sport, c.gender)
    for col in sim.cat.colleges:
        if not offers_side(col, sport, c.gender):
            continue  # no team on their side (no men's soccer at Texas, no softball at Miami)
        key = f"{col['id']}:{sport}"
        gap = score - recruit_bar(col, sd)
        if gap < -6:
            continue
        first = key not in rec["interest"]
        rec["interest"][key] = max(rec["interest"].get(key, 0), int(clamp(50 + gap * 5, 5, 99)))
        already = any(o["college"] == col["id"] and o["sport"] == sport for o in rec["offers"])
        eligible = c.gpa >= col.get("athlete_min_gpa", 2.3) - 0.25
        p = sigmoid(gap / 3) * (0.9 if c.grade >= 12 else 0.5 if c.grade == 11 else 0.0)
        if not already and c.grade >= 11 and gap >= 0 and eligible and rng.random() < p:
            make_offer(inst, c, col, sport)
        elif first:
            ev = inst.event("recruiting", "interest", [c.id], importance=22, data={"label": col["name"], "sport": sport})
            ev["text"] = f"{col['short']} coaches are keeping an eye on {c.short} ({sport})."
            sim.finish(ev, Effects(w, ev))


def make_offer(inst, c, col, sport, committed=False):
    sim = inst.sim
    w = sim.w
    aid = aid_label(col, sport)
    offer = {"college": col["id"], "name": col["name"], "short": col["short"], "tier": col["tier"], "conference": col.get("conference"),
             "sport": sport, "side": side(sport, c.gender), "scholarship": True, "aid": aid, "min_gpa": col.get("athlete_min_gpa", 2.3),
             "day": w.day}
    c.recruiting.setdefault("offers", []).append(offer)
    ev = inst.event("recruiting", "offer", [c.id], importance=42, data={"label": col["name"], "sport": sport})
    ev["text"] = f"{col['name']} offered {c.short} a {aid} to play {sport}."
    fx = Effects(w, ev)
    fx.mood(c.id, 10, "college offer")
    fx.memory(c.id, "offer", [], 0.8, 70, f"Offer from {col['short']} for {sport}")
    sim.confidence(c.id, 1.5, fx, "college offer")
    sim.finish(ev, fx)
    if not committed:
        sim.moment_trigger("offer", c.id, {"college": col["id"], "college_name": col["name"], "sport": sport, "tier": col.get("conference") or col["tier"]})
    return offer


def admissions(inst, rng):
    """Senior spring: acceptance letters, and offers that don't survive the GPA check."""
    sim = inst.sim
    w = sim.w
    for c in sorted(w.students(), key=lambda c: c.id):
        if c.school != "hchs" or c.grade != 12:
            continue
        prot = w.meta.get("protagonist") == c.id
        preset = c.flags.get("preset_path") or {}
        if preset.get("college") and preset.get("sport") and not any(o["college"] == preset["college"] and o["sport"] == preset["sport"]
                                                                     for o in c.recruiting.get("offers", [])):
            make_offer(inst, c, sim.cat.college_by_id[preset["college"]], preset["sport"], committed=True)
        admits = []
        for col in sim.cat.colleges:
            gpa = c.gpa + rng.gauss(0, 0.1)
            p = col.get("admit_cap", 1.0) * sigmoid((gpa - col["min_gpa"]) / 0.12)
            if (preset.get("college") == col["id"] and not preset.get("sport")) or rng.random() < p:
                admits.append({"college": col["id"], "name": col["name"], "short": col["short"], "tier": col["tier"],
                               "conference": col.get("conference")})
        c.recruiting["admits"] = admits
        ev = inst.event("admissions", "letters", [c.id], importance=30 if prot else 12,
                        data={"label": ", ".join(a["short"] for a in admits[:4])})
        big = [a["short"] for a in admits if not sim.cat.college_by_id[a["college"]].get("local")]
        ev["text"] = (f"{c.short} got into {len(admits)} school{'s' if len(admits) != 1 else ''}"
                      + (f", including {', '.join(big[:3])}" if big else "") + ".")
        sim.finish(ev, Effects(w, ev))
        kept, lost = [], []
        for o in c.recruiting.get("offers", []):
            (kept if c.gpa >= o.get("min_gpa", 0) or (preset.get("college") == o["college"] and preset.get("sport") == o["sport"]) else lost).append(o)
        for o in lost:
            ev = inst.event("recruiting", "pulled", [c.id], importance=40 if prot else 14, data={"label": o["name"], "sport": o["sport"]})
            ev["text"] = (f"{o.get('short', o['name'])} pulled its {o['sport']} offer: {c.short}'s {c.gpa:.2f} GPA is under "
                          f"the {o['min_gpa']:.1f} it needs from recruits.")
            fx = Effects(w, ev)
            fx.mood(c.id, -8, "offer pulled over grades")
            fx.memory(c.id, "offer_pulled", [], -0.6, 60, f"Lost the {o.get('short', o['name'])} offer over my GPA")
            sim.finish(ev, fx)
        c.recruiting["offers"] = kept
        if lost:
            c.recruiting.setdefault("lost_offers", []).extend(lost)


def path_options(sim, c) -> list:
    """Every realistic thing a senior could do next, with a utility for autonomous choosing."""
    w = sim.w
    t, m = c.traits, c.motives
    h = w.households.get(c.household_id) or {}
    poor = h.get("income") == "low"
    opts = []
    for o in c.recruiting.get("offers", []):
        col = sim.cat.college_by_id[o["college"]]
        iv = c.interests.get(o["sport"], 50)
        full = o.get("aid", "full scholarship").startswith("full")
        v = (10 + program(col, o.get("side") or o["sport"]) * 0.22 + iv * 0.2 + (8 if full else 4) + m["achievement"] * 0.1
             + (6 if poor else 0) + (4 if col.get("home_state") and m["belonging"] > 60 else 0))
        opts.append({"kind": "college", "college": o["college"], "name": o["name"], "tier": o["tier"], "conference": col.get("conference"),
                     "sport": o["sport"], "scholarship": True, "aid": o.get("aid"), "program": program(col, o.get("side") or o["sport"]),
                     "utility": round(v, 1), "label": f"Play {o['sport']} at {col['short']} ({o.get('aid', 'scholarship')})"})
    for a in c.recruiting.get("admits", []):
        col = sim.cat.college_by_id[a["college"]]
        v = (6 + col.get("academic_rank", 50) * 0.18 + t["ambition"] * 0.15 + c.aptitudes["academic"] * 0.05
             - (5 if poor and not col.get("home_state") else 0))
        opts.append({"kind": "college", "college": a["college"], "name": a["name"], "tier": a["tier"], "conference": col.get("conference"),
                     "sport": None, "scholarship": False, "aid": None, "program": None, "utility": round(v, 1),
                     "label": f"Go to {col['short']} as a regular student"})
    v = 12 + m["pleasure"] * 0.08 + (50 - t["ambition"]) * 0.2 + (6 if poor else 0)
    town = sim.cat.world["town"]["name"]
    opts.append({"kind": "work", "college": None, "name": town, "tier": None, "conference": None, "sport": None, "scholarship": False,
                 "aid": None, "program": None, "utility": round(v, 1), "label": f"Stay in {town} and work"})
    return opts


def choose_path(inst, c, rng, option=None, how="decided"):
    sim = inst.sim
    w = sim.w
    opts = path_options(sim, c)
    preset = c.flags.get("preset_path")
    if option is None and preset:
        option = next((o for o in opts if (preset.get("kind") == "work" and o["kind"] == "work")
                       or (o["college"] == preset.get("college") and o["sport"] == preset.get("sport"))), None)
    if option is None:
        from .rng import softmax_pick
        idx, _ = softmax_pick([o["utility"] for o in opts], 6.0, rng.random())
        option = opts[idx]
    c.path = {k: option.get(k) for k in ("kind", "college", "name", "tier", "conference", "sport", "scholarship", "aid")}
    c.path["decided"] = w.day
    if option["kind"] == "college":
        txt = (f"{c.short} committed to play {option['sport']} at {option['name']} ({option.get('aid') or 'scholarship'})." if option["sport"]
               else f"{c.short} will attend {option['name']} in the fall.")
    else:
        txt = f"{c.short} plans to stay in {sim.cat.world['town']['name']} and work after graduation."
    ev = inst.event("path", "chosen", [c.id], importance=40, data={"label": option["label"]})
    ev["text"] = txt
    fx = Effects(w, ev)
    fx.memory(c.id, "decision", [], 0.6, 70, txt.replace(c.short, "I", 1))
    fx.mood(c.id, 5, "made the big decision")
    sim.finish(ev, fx)
    return c.path


# --- the MLB draft --------------------------------------------------------------------------

def college_baseball(c) -> list:
    """College baseball seasons, oldest first (on campus or offscreen)."""
    return [st for k, st in sorted(c.stats.items()) if st["sport"] == "baseball" and st["games"]
            and (st.get("school") == "college" or str(st.get("school") or "").startswith("away:"))]


def plays_college_baseball(w, c) -> bool:
    p = c.path or {}
    if p.get("kind") != "college" or c.role != "student" or not c.grade or c.grade < 13:
        return False
    return "col_baseball" in c.memberships or (p.get("sport") == "baseball" and str(c.school or "").startswith("away:")) \
        or bool(college_baseball(c))


def draft_score(sim, c) -> dict:
    """How MLB scouts see a college player: tools, production against their level, honors and exposure."""
    w = sim.w
    p = c.path or {}
    col = sim.cat.college_by_id.get(p.get("college")) or {}
    lvl = team_level(col, "baseball") if col else 70.0
    seasons = college_baseball(c)[-2:]
    r = rating(c, "baseball")
    prod = 0.0
    if seasons:
        ipg = sum(st["impact"] for st in seasons) / max(1, sum(st["games"] for st in seasons))
        starts = sum(st["starts"] for st in seasons) / max(1, sum(st["games"] for st in seasons))
        prod = 0.3 * (ipg - lvl) * (0.5 + 0.5 * starts)
    honors = [a for a in c.awards if a.get("sport") == "baseball" and a.get("season") and any(
        a["season"] == k for k, st in c.stats.items() if st in seasons or st.get("school") == "college")]
    aw = min(8.0, 2.5 * len(honors))
    exposure = (program(col, "baseball") - 80) / 10 if col else -2.0
    total = r + prod + aw + exposure
    terms = [["baseball rating", round(r, 1)], ["production vs. level", round(prod, 1)], ["honors", aw], ["program exposure", round(exposure, 1)]]
    return {"score": round(total, 1), "terms": terms, "pick": pick_from_score(total), "round": round_of(pick_from_score(total))}


def pick_from_score(x: float) -> int:
    import math
    return max(1, int(round(10 * math.exp((97 - x) * 0.2))))


def round_of(pick: int, rounds: int = 20) -> int | None:
    """About 31 picks a round; past the last round you go undrafted (20 rounds now, 40 in the 2010s, 50 before)."""
    if pick > rounds * 31 - 5:
        return None
    return min(rounds, (pick - 1) // 31 + 1)


def slot_value(sim, pick: int) -> int:
    pts = sim.cat.sports["mlb"]["slots"]
    for (p0, v0), (p1, v1) in zip(pts, pts[1:]):
        if p0 <= pick <= p1:
            import math
            t = (math.log(pick) - math.log(p0)) / max(1e-9, math.log(p1) - math.log(p0))
            return int(round(math.exp(math.log(v0) + t * (math.log(v1) - math.log(v0))) / 5000) * 5000)
    return pts[-1][1]


def money(n: int) -> str:
    return f"${n / 1_000_000:.1f} million" if n >= 1_000_000 else f"${n // 1000:,}K"


def first_level(rnd: int | None) -> str:
    if not rnd:
        return "a rookie-ball complex team"
    return "High-A" if rnd <= 2 else "Low-A" if rnd <= 10 else "a rookie-ball complex team"


def mlb_draft(sim):
    """Draft day. Eligible: college juniors and seniors who play baseball."""
    w = sim.w
    mlb = sim.cat.sports["mlb"]
    year = calm.date_of(w.day).year
    rng = sim.streams.get("mlb-draft", year)
    from . import mlb as mlb_world
    order = mlb_world.draft_order(sim, year)  # worst record last season picks first (each team by its name that year)
    rounds = mlb_world.draft_info(year)[1]
    if len(order) != len(mlb["teams"]):
        order = list(mlb["teams"])
        rng.shuffle(order)
    prot = w.meta.get("protagonist")
    pool = []
    for c in sorted(w.chars.values(), key=lambda c: c.id):
        if c.status != "active" or c.grade not in (15, 16) or not plays_college_baseball(w, c):
            continue
        d = draft_score(sim, c)
        noisy = d["score"] + rng.gauss(0, 2.5)
        pool.append((pick_from_score(noisy), c, d, noisy))
    taken = set()
    for pick, c, d, noisy in sorted(pool, key=lambda x: (x[0], x[1].id)):
        while pick in taken:
            pick += 1
        rnd = round_of(pick, rounds)
        senior = c.grade == 16
        if rnd is None:
            c.recruiting["draft"] = {"year": year, "status": "undrafted", "score": d["score"], "terms": d["terms"], "senior": senior}
            ev = sim.new_event("draft", "passed", [c.id], [], 40 if c.id == prot else 8, {"label": "MLB Draft"})
            ev["text"] = f"All {rounds} rounds of the MLB Draft went by without {c.short}'s name."
            sim.finish(ev, Effects(w, ev))
            if c.id == prot:
                sim.moment_trigger("draft_passed", c.id, {"college_name": (c.path or {}).get("name", "school"), "udfa": d["score"] >= 72,
                                                          "senior": senior})
            continue
        taken.add(pick)
        team = order[(pick - 1) % len(order)]
        bonus = slot_value(sim, pick)
        if senior and pick > 100:
            bonus = max(10000, int(bonus * 0.4 / 5000) * 5000)
        c.recruiting["draft"] = {"year": year, "status": "drafted", "pick": pick, "round": rnd, "team": team, "bonus": bonus,
                                 "level": first_level(rnd), "score": d["score"], "terms": d["terms"], "senior": senior}
        ev = sim.new_event("draft", "drafted", [c.id], [], 60 if c.id == prot else 20, {"label": team})
        ev["text"] = f"The {team} drafted {c.short} in round {rnd}, pick {pick} overall. Slot value: about {money(bonus)}."
        rule = f"pick = 10 x e^(0.2 x (97 - score)); past pick {rounds * 31 - 5} is undrafted ({rounds} rounds in {year})"
        ev["calc"] = ([{"step": "MLB draft", "terms": d["terms"], "total": d["score"], "with_luck": round(noisy, 1), "pick": pick,
                        "rule": rule}] if w.tracing or c.id == prot else None)
        fx = Effects(w, ev)
        fx.mood(c.id, 15, "drafted")
        fx.memory(c.id, "drafted", [], 0.9, 90, f"Drafted by the {team}, round {rnd}")
        for s in sim.siblings(c.id):
            fx.mood(s, 6, f"{c.short} got drafted")
        sim.finish(ev, fx)
        if c.id == prot:
            sim.moment_trigger("mlb_draft", c.id, {"team": team, "round": rnd, "pick": pick, "bonus": money(bonus),
                                                   "level": first_level(rnd), "college_name": (c.path or {}).get("name", "school"),
                                                   "senior": senior})
        elif rnd <= 10 or senior:
            sign_pro(sim, c, fx=None)


def sign_pro(sim, c, fx=None, udfa=False):
    """Sign a pro contract: leave college for the minor leagues (offscreen from here)."""
    w = sim.w
    d = c.recruiting.get("draft") or {}
    own = fx is None
    if own:
        ev = sim.new_event("draft", "signed", [c.id], [], 50 if c.id == w.meta.get("protagonist") else 14, {"label": d.get("team", "")})
        fx = Effects(w, ev)
    team = d.get("team") if not udfa else None
    level = d.get("level") if not udfa else "a rookie-ball complex team"
    for gid in list(c.memberships):
        if w.groups[gid].get("school") == "college" or w.groups[gid]["kind"] == "job":
            fx.leave(c.id, gid, "signed a pro contract")
    c.path = {"kind": "pro", "team": team, "round": d.get("round"), "pick": d.get("pick"), "bonus": 0 if udfa else d.get("bonus"),
              "level": level, "college": (c.path or {}).get("college"), "name": team or "pro ball", "udfa": udfa, "started": w.day}
    c.role = "alumni"
    c.grade = None
    c.school = None
    c.location = "away"
    c.flags.pop("term_location", None)
    d["status"] = "signed"
    if own:
        ev["text"] = (f"{c.short} signed with the {team} and reports to their {level} club." if team
                      else f"{c.short} signed as an undrafted free agent and reports to {level}.")
        sim.finish(ev, fx)
