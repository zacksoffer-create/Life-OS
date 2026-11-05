"""The league: your conference as real teams.

Before this, an opponent was a name and a random strength. Now every school your team plays is a team that lasts the
season: its own strength (some programs are better than others, and it changes year to year), its record, the points
it scores and gives up, its streak, and its stars (named players with season stat lines). Every week your team plays,
the rest of the conference plays too, so the standings are real. On top of that:

- the schedule rotates through the conference, and one school is your rival (Hand, for Guilford): that game matters more
- power rankings every week (who's moving), league leaders (your teammates next to the other schools' stars), Player of
  the Week (yours to win), and the regular-season title
- how your team does is how it's seen: a winning team's prestige goes up, and prestige is one of the things your
  popularity is made of; big games, Player of the Week and awards travel around school (people who'd never met you
  know your name), which is how the sports side feeds the Scene's ladder
"""
from __future__ import annotations

import random
import zlib

from . import calendar as calm
from .history import Effects
from .rng import clamp

LEADERS = {
    "football": [("pass_yds", "Passing yards"), ("rush_yds", "Rushing yards"), ("rec_yds", "Receiving yards"), ("tackles", "Tackles"),
                 ("sacks", "Sacks")],
    "basketball": [("pts", "Points"), ("reb", "Rebounds"), ("ast", "Assists"), ("stl", "Steals")],
    "baseball": [("h", "Hits"), ("hr", "Home runs"), ("rbi", "RBI"), ("k", "Strikeouts")],
    "softball": [("h", "Hits"), ("hr", "Home runs"), ("rbi", "RBI"), ("k", "Strikeouts")],
    "soccer": [("goals", "Goals"), ("assists", "Assists"), ("saves", "Saves")],
}
PER_GAME = {"basketball"}  # leaders by average, the way the sport counts it
STAR_POS = {"football": ["QB", "RB", "WR", "LB"], "basketball": ["PG", "SF", "C"], "baseball": ["P", "SS", "CF"],
            "softball": ["P", "SS", "CF"], "soccer": ["ST", "CM", "GK"]}
RIVALS = {"hchs": "Hand"}  # Guilford's rival: the shoreline game


def _h(*p) -> int:
    return zlib.crc32(":".join(str(x) for x in p).encode())


def _year(day) -> int:
    return calm.START.year + calm.school_year_of(day)


def _names(sim, g) -> list:
    school = "college" if g.get("school") == "college" else "hchs"
    names = sim.cat.world.get("opponents", {}).get(school) or ["Rival"]
    meta = sim.w.meta.get("college")
    if school == "college" and meta and meta["id"] in sim.cat.college_by_id:
        opp = sim.cat.college_by_id[meta["id"]].get("opponents", {})
        names = opp.get(g.get("skill")) or opp.get("default") or names
    return list(names)


def ours(sim, g) -> str:
    if g.get("school") == "college" and sim.w.meta.get("college"):
        col = sim.cat.college_by_id.get(sim.w.meta["college"]["id"]) or {}
        return col.get("short") or "Your team"
    import re
    sch = sim.cat.world["school"]
    return re.sub(r"\s+High( School)?$", "", sch.get("short") or sch.get("name", "Your team")) or "Your team"


def rival(sim, g) -> str | None:
    return None if g.get("school") == "college" else RIVALS.get("hchs")


def _base(sim, g) -> float:
    if g.get("school") == "college" and sim.w.meta.get("college"):
        from .sports import college_level
        return college_level(sim.w.meta["college"], g.get("side") or g.get("skill"))
    return 48.0


def _star_names(sim, rng, gender, n) -> list:
    from .catalogs import _base as data
    pool = data("people.json")["names"]
    firsts = pool["male"] if gender == "m" else pool["female"]
    lasts = pool["last"] + pool["last_more"]
    out = set()
    while len(out) < n:
        out.add(f"{rng.choice(firsts)} {rng.choice(lasts)}")
    return sorted(out)


def league(sim, g, day=None) -> dict:
    """This season's league for a team (made the first time it's needed, the same way every time)."""
    w = sim.w
    day = w.day if day is None else day
    y = _year(day)
    key = f"{g['id']}:{y}"
    L = w.meta.setdefault("league", {})
    if key in L:
        return L[key]
    rng = random.Random(_h(w.seed, key))
    sport = g["skill"]
    gender = "f" if g.get("side", "").endswith("_w") or g["id"].endswith("_girls") or sport == "softball" else "m"
    # the conference is pitched at your team's level (half how good your roster is, half a typical team), so most
    # seasons are a fight, and a team that's really weak or really loaded still feels it
    base = 0.6 * our_strength(sim, g) + 0.4 * (_base(sim, g) - 2)
    teams = {}
    for n in _names(sim, g):
        # some programs are just better at a sport (partly every story, partly this world's), and it shifts year to year
        prog = ((_h(n, sport) % 11) - 5) * 0.5 + ((_h(w.seed, n, sport) % 9) - 4) * 0.6
        s = round(base + prog + rng.gauss(0, 3.5), 1)
        stars = []
        for pos, name in zip(STAR_POS.get(sport, ["?"]), _star_names(sim, rng, gender, len(STAR_POS.get(sport, ["?"])))):
            stars.append({"id": f"opp:{_h(key, n, name) % 10**8}", "name": name, "pos": pos, "grade": rng.choice([10, 11, 11, 12, 12]),
                          "rating": round(s + rng.gauss(7, 4), 1), "games": 0, "line": {}, "impact": 0.0})
        teams[n] = {"name": n, "strength": s, "w": 0, "l": 0, "pf": 0, "pa": 0, "results": [], "stars": stars}
    us = ours(sim, g)
    teams[us] = {"name": us, "strength": None, "w": 0, "l": 0, "pf": 0, "pa": 0, "results": [], "stars": [], "ours": True}
    order = sorted(_names(sim, g), key=lambda n: _h(key, "order", n))
    riv = rival(sim, g)
    if riv in order:  # the rival game comes late, when it matters most
        order.remove(riv)
        order.insert(max(0, min(len(order), 7)), riv)
    L[key] = {"key": key, "group": g["id"], "sport": sport, "year": y, "ours": us, "rival": riv, "teams": teams, "schedule": order,
              "rounds": [], "potw": [], "power": [], "title": None, "gender": gender}
    for k in sorted(L, key=lambda k: L[k].get("year", 0))[:-12]:  # keep a couple of seasons per team
        del L[k]
    return L[key]


def opponent(sim, g, num: int) -> dict:
    lea = league(sim, g)
    name = lea["schedule"][(num - 1) % len(lea["schedule"])]
    return lea["teams"][name]


def our_strength(sim, g) -> float:
    """How good your team is on paper: its best players' ratings (power rankings use it; the games use real performances)."""
    from .sports import rating
    w = sim.w
    lv = g.get("levels", {})
    rs = sorted((rating(w.chars[m], g["skill"]) for m in g["members"] if lv.get(m, "varsity") == "varsity" and m in w.chars), reverse=True)
    top = rs[: g.get("starters", 5)]
    return round(sum(top) / len(top), 1) if top else 40.0


def _scores(score: str) -> tuple:
    try:
        a, b = score.split("-")
        return int(a), int(b)
    except Exception:  # noqa: BLE001
        return 1, 0


def _star_game(sim, lea, team, f_team, rng, day, perfs):
    from .sports import stat_line
    for s in team["stars"]:
        perf = s["rating"] + rng.gauss(0, 7) + f_team
        line = stat_line(lea["sport"], s["pos"], clamp(perf / 62, 0.25, 1.8), True, rng)
        s["games"] += 1
        s["impact"] = round(s["impact"] + perf, 1)
        for k, v in line.items():
            s["line"][k] = s["line"].get(k, 0) + v
        perfs.append({"perf": round(perf, 1), "id": s["id"], "name": s["name"], "team": team["name"], "line": line, "day": day})


def _result(lea, a, b, sa, sb, day, rivalry=False):
    for t, us_, them, pf, pa in ((a, a, b, sa, sb), (b, b, a, sb, sa)):
        win = pf > pa
        t["w" if win else "l"] += 1
        t["pf"] += pf
        t["pa"] += pa
        t["results"].append({"day": day, "vs": them["name"], "win": win, "score": f"{max(pf, pa)}-{min(pf, pa)}"})


def record(sim, inst, g, num: int, win: bool, score: str, box: dict, rng) -> dict:
    """After your team's game: the result in the table, the other school's stars' lines, and the rest of the conference's
    games that week."""
    w = sim.w
    lea = league(sim, g)
    us = lea["teams"][lea["ours"]]
    opp = opponent(sim, g, num)
    pf, pa = _scores(score)  # the score reads from your side: yours first
    perfs = [{"perf": v["perf"], "id": cid, "name": w.chars[cid].name, "team": lea["ours"], "line": v["line"], "day": w.day, "ours": True}
             for cid, v in box.items() if v.get("perf") is not None]
    _result(lea, us, opp, pf, pa, w.day)
    _star_game(sim, lea, opp, -3 if win else 3, rng, w.day, perfs)
    rest = [n for n in lea["teams"] if n not in (lea["ours"], opp["name"])]
    rest.sort(key=lambda n: _h(lea["key"], num, n))
    games = [{"a": lea["ours"], "b": opp["name"], "score": f"{max(pf, pa)}-{min(pf, pa)}", "winner": lea["ours"] if win else opp["name"]}]
    for i in range(0, len(rest) - 1, 2):
        t1, t2 = lea["teams"][rest[i]], lea["teams"][rest[i + 1]]
        margin = t1["strength"] - t2["strength"] + rng.gauss(0, 7) + 1.5
        s = inst.score_line(lea["sport"], margin, rng)
        x, y = _scores(s)  # from the first team's side
        if margin > 0:
            _result(lea, t1, t2, x, y, w.day)
        else:
            _result(lea, t2, t1, y, x, w.day)
        _star_game(sim, lea, t1, 0, rng, w.day, perfs)
        _star_game(sim, lea, t2, 0, rng, w.day, perfs)
        games.append({"a": t1["name"], "b": t2["name"], "score": f"{max(x, y)}-{min(x, y)}", "winner": t1["name"] if margin > 0 else t2["name"]})
    perfs.sort(key=lambda p: -p["perf"])
    lea["rounds"].append({"n": num, "day": w.day, "games": games, "top": perfs[:6]})
    _prestige(sim, g, lea)
    return {"opponent": opp["name"], "rivalry": opp["name"] == lea["rival"]}


def _prestige(sim, g, lea):
    """A team's standing at school follows its record (prestige counts toward popularity)."""
    us = lea["teams"][lea["ours"]]
    gp = us["w"] + us["l"]
    base = g.setdefault("prestige_base", g.get("prestige", 50))
    if gp >= 3:
        title = 8 if any(x.get("title") == lea["ours"] for x in sim.w.meta.get("league", {}).values() if x.get("group") == g["id"] and x is not lea) else 0
        g["prestige"] = round(clamp(base + 24 * (us["w"] / gp - 0.5) + title, 15, 98), 1)


def table(lea) -> list:
    rows = []
    for t in lea["teams"].values():
        gp = t["w"] + t["l"]
        last = t["results"][-1] if t["results"] else None
        streak, n = "", 0
        for r in reversed(t["results"]):
            if streak and (r["win"] != (streak == "W")):
                break
            streak = "W" if r["win"] else "L"
            n += 1
        rows.append({"name": t["name"], "w": t["w"], "l": t["l"], "pct": round(t["w"] / gp, 3) if gp else 0.0, "pf": t["pf"], "pa": t["pa"],
                     "diff": t["pf"] - t["pa"], "streak": f"{streak}{n}" if streak else "", "ours": bool(t.get("ours")),
                     "rival": t["name"] == lea.get("rival"), "last": last})
    rows.sort(key=lambda r: (-r["pct"], -(r["w"]), -r["diff"], r["name"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def weekly(sim):
    """Once a week: power rankings, and Player of the Week in every league that played."""
    w = sim.w
    for lea in list(w.meta.get("league", {}).values()):
        if lea.get("year") != _year(w.day):
            continue
        week = [r for r in lea["rounds"] if w.day - 7 < r["day"] <= w.day]
        if not week:
            continue
        g = w.groups.get(lea["group"])
        ours_s = our_strength(sim, g) if g else 45
        power = sorted(lea["teams"].values(), key=lambda t: (-(t["w"] - t["l"]) * 3 - (t["strength"] if t["strength"] is not None else ours_s), t["name"]))
        lea["power"].append({"day": w.day, "ranks": {t["name"]: i + 1 for i, t in enumerate(power)}})
        del lea["power"][:-12]
        best = max((p for r in week for p in r["top"]), key=lambda p: p["perf"], default=None)
        if best:
            from .sports import line_text
            pick = {**best, "text": line_text(lea["sport"], best["line"]), "week_of": calm.label(w.day)}
            lea["potw"].append(pick)
            if best.get("ours") and best["id"] in w.chars and g:
                c = w.chars[best["id"]]
                conf = "SCC" if g.get("school") != "college" else "Conference"
                ev = sim.new_event("award", "potw", [c.id], [], 30, {"label": f"{conf} Player of the Week", "group": g["id"]})
                ev["text"] = f"{c.short} was named {conf} Player of the Week: {pick['text']}."
                fx = Effects(w, ev)
                fx.rep(c.id, "star", 4, "Player of the Week")
                c.awards.append({"day": w.day, "label": f"{conf} Player of the Week", "sport": lea["sport"], "potw": True})
                buzz(sim, fx, c.id, 18, "Player of the Week", lea["sport"])
                sim.finish(ev, fx)


def season_end(sim, g):
    """The regular season's over: the title, and what it means for the team."""
    w = sim.w
    key = f"{g['id']}:{_year(w.day)}"
    lea = w.meta.get("league", {}).get(key)
    if not lea or lea.get("title"):
        return
    rows = table(lea)
    if not rows or not (rows[0]["w"] + rows[0]["l"]):
        return
    lea["title"] = rows[0]["name"]
    if rows[0]["ours"]:
        members = [m for m in g["members"] if g.get("levels", {}).get(m, "varsity") == "varsity" and m in w.chars]
        ev = sim.new_event("award", "title", members, [], 44, {"label": f"{g['name']}: regular-season champions", "group": g["id"]})
        ev["text"] = f"{g['name']} won the regular-season title, {rows[0]['w']}-{rows[0]['l']}."
        fx = Effects(w, ev)
        for m in members:
            fx.mood(m, 8, "won the title")
            buzz(sim, fx, m, 8, "won the title", lea["sport"])
        sim.finish(ev, fx)
    _prestige(sim, g, lea)


def buzz(sim, fx, cid, size: float, why: str, sport: str | None = None):
    """Word gets around school: people who barely knew them know them now, and respect them a little more. This is how
    a big game reaches the Scene's ladder (familiarity and respect are what popularity is made of)."""
    w = sim.w
    c = w.chars.get(cid)
    if not c or c.role != "student":
        return
    rng = random.Random(_h(w.seed, w.day, cid, why))
    pool = [o for o in w.chars.values() if o.role == "student" and o.status == "active" and o.school == c.school
            and o.location == c.location and o.id != cid]
    share = clamp(size / 50, 0.1, 0.7)
    for o in pool:
        if rng.random() > share:
            continue
        fan = bool(sport) and o.interests.get(sport, 0) >= 50  # the ones who follow the sport hear more, and care more
        fx.rel(o.id, cid, "familiarity", size * (0.35 if fan else 0.22), why)
        fx.rel(o.id, cid, "respect", size * (0.2 if fan else 0.12), why)


def leaders(sim, lea, g) -> dict:
    """Your teammates next to the other schools' stars, in the stats the sport counts."""
    from .sports import season_key
    w = sim.w
    sport = lea["sport"]
    rows = []
    skey = season_key(sport, w.day, "varsity")
    for cid in (g["members"] if g else []):
        st = (w.chars[cid].stats.get(skey) or {}) if cid in w.chars else {}
        if st.get("games"):
            rows.append({"id": cid, "name": w.chars[cid].name, "team": lea["ours"], "ours": True, "games": st["games"], "line": st["line"]})
    for t in lea["teams"].values():
        for s in t["stars"]:
            if s["games"]:
                rows.append({"id": s["id"], "name": s["name"], "team": t["name"], "ours": False, "games": s["games"], "line": s["line"],
                             "pos": s["pos"], "grade": s["grade"]})
    out = {}
    for k, label in LEADERS.get(sport, []):
        val = (lambda r: r["line"].get(k, 0) / max(1, r["games"])) if sport in PER_GAME else (lambda r: r["line"].get(k, 0))
        top = sorted((r for r in rows if r["line"].get(k)), key=lambda r: (-val(r), r["name"]))[:6]
        if top:
            out[k] = {"label": label + (" per game" if sport in PER_GAME else ""),
                      "rows": [{"id": r["id"], "name": r["name"], "team": r["team"], "ours": r["ours"],
                                "value": round(val(r), 1) if sport in PER_GAME else int(val(r))} for r in top]}
    return out
