"""The Sports tab: your season, your playing time, the league, the awards race and recruiting, for each team you're on.

- Season: the record and where it puts you in the conference, the streak, the last game and the next one (the rival game
  flagged), your role, your stat line and game log, the team's leaders
- Playing time: the coach starts the best players by sport rating (sports.rating: skill counts most, then athleticism,
  fitness, size and build, confidence), so this shows your rating in those same parts next to the last starter's (or the
  player chasing your spot), the whole depth chart with the starting line, and what to do about it; plus the coach's trust
  and your attendance (missing too much gets you dropped)
- League: the standings (league.py) with this week's power-ranking moves, and the league leaders
- Awards: Player of the Week, the All-Conference race (everyone in the league by impact per game), the team MVP race
- Recruiting: who's interested, the offers, and what coaches look at
"""
from __future__ import annotations

from . import calendar as calm
from . import league as lg
from .sports import BUILD_BONUS, body_bonus, line_text, rating, season_key  # noqa: F401


def _me(sim):
    p = sim.w.meta.get("protagonist")
    return sim.w.chars.get(p) if p else None


def _teams(sim, me) -> list:
    w = sim.w
    return [w.groups[g] for g in me.memberships if g in w.groups and w.groups[g].get("kind") == "team"]


def _in_season(w, g) -> bool:
    return any(i["kind"] == "game" and i.get("group") == g["id"] and 0 <= i["day"] - w.day <= 10 for i in w.calendar) or \
        any(i["kind"] == "game" and i.get("group") == g["id"] and 0 <= w.day - i["day"] <= 10 for i in w.calendar)


def _parts(c, sport) -> dict:
    sk = c.skills.get(sport, 0)
    return {"skill": round(0.6 * sk, 1), "athletic": round(0.15 * c.aptitudes.get("athletic", 50), 1),
            "fitness": round(0.12 * c.skills.get("fitness", 30), 1), "body": round(body_bonus(c, sport), 1),
            "confidence": round(0.06 * (c.traits.get("confidence", 50) - 50), 1)}


PART_LABEL = {"skill": "Skill", "athletic": "Athleticism", "fitness": "Fitness", "body": "Size and build", "confidence": "Confidence"}
PART_HOW = {"skill": "practice and train (skill counts most: 60%)", "athletic": "it's mostly what you were born with",
            "fitness": "work out", "body": "your size and build (it is what it is)", "confidence": "play well and it comes"}


def _playing_time(sim, me, g) -> dict:
    from .institutions import misses
    w = sim.w
    sport = g["skill"]
    lv = g.get("levels", {})
    level = lv.get(me.id, "varsity")
    squad = [m for m in g["members"] if lv.get(m, "varsity") == level and m in w.chars]
    n = g.get("starters", 5)
    ranked = sorted(squad, key=lambda m: (-rating(w.chars[m], sport), m))
    pos = next((i for i, m in enumerate(ranked) if m == me.id), len(ranked))
    starter = pos < n
    rival_id = (ranked[n] if len(ranked) > n else None) if starter else (ranked[n - 1] if len(ranked) >= n else None)
    mine = _parts(me, sport)
    mr = round(rating(me, sport), 1)
    cmp = None
    if rival_id:
        o = w.chars[rival_id]
        theirs = _parts(o, sport)
        orr = round(rating(o, sport), 1)
        diff = {k: round(mine[k] - theirs[k], 1) for k in mine}
        worst = min(diff, key=lambda k: diff[k] if k in ("skill", "fitness", "confidence") else 99)
        cmp = {"id": o.id, "name": o.name, "first": o.first, "rating": orr, "gap": round(mr - orr, 1), "diff": diff,
               "line": (f"You're starting. {o.first} is {abs(round(mr - orr, 1))} behind you for your spot." if starter
                        else f"{o.first} has the last starting spot by {abs(round(mr - orr, 1))}."),
               "how": PART_HOW[worst]}
    injured = me.flags.get("injured_until", -1) >= w.day
    coach = g.get("staff")
    trust = None
    if coach and coach in w.chars:
        r = w.rels.get((coach, me.id))
        trust = {"name": w.chars[coach].name, "respect": round(r.respect) if r else 0, "label": "trusts you" if r and r.respect >= 40
                 else "is still deciding about you" if not r or r.respect >= 10 else "doesn't trust you yet"}
    tip = (f"You're hurt ({me.flags.get('injury')}): back {calm.label(me.flags['injured_until'])}." if injured
           else f"Keep it: {cmp['how']}." if starter and cmp else
           f"To start: {cmp['how']}." if cmp else "Show up and play: the rest follows.")
    depth = [{"id": m, "name": w.chars[m].name, "first": w.chars[m].first, "rating": round(rating(w.chars[m], sport), 1),
              "pos": w.chars[m].positions.get(sport), "grade": w.chars[m].grade, "you": m == me.id, "starter": i < n}
             for i, m in enumerate(ranked)]
    return {"level": level, "position": me.positions.get(sport), "starter": starter, "spot": pos + 1, "starters": n, "of": len(ranked),
            "rating": mr, "parts": [{"key": k, "label": PART_LABEL[k], "value": v} for k, v in mine.items()], "vs": cmp,
            "depth": depth, "tip": tip, "coach": trust, "missed": misses(g, me.id), "injured": injured}


def _games(sim, me, g, n=8) -> list:
    w = sim.w
    out = []
    for eid in reversed(w.history.by_char.get(me.id, [])[-400:]):
        e = w.history.events.get(eid)
        if not e or e["type"] != "game" or e.get("group") != g["id"] or e["outcome"] not in ("win", "loss"):
            continue
        b = (e["data"].get("box") or {}).get(me.id) or {}
        out.append({"date": calm.label(e["day"]), "opponent": e["data"].get("opponent"), "win": e["outcome"] == "win",
                    "score": e["data"].get("score"), "line": line_text(g["skill"], b.get("line") or {}) if b else "didn't play",
                    "started": bool(b.get("starter")), "rivalry": bool(e["data"].get("rivalry")), "level": e["data"].get("level"),
                    "play": b.get("play"), "play_tier": e["data"].get("play_tier") if b.get("play") else None})
        if len(out) >= n:
            break
    return out


def _next(sim, g) -> dict | None:
    w = sim.w
    nxt = min((i for i in w.calendar if i["kind"] == "game" and i.get("group") == g["id"] and i["day"] >= w.day),
              key=lambda i: i["day"], default=None)
    if not nxt:
        return None
    num = int(str(nxt["key"]).split(":")[-1]) if str(nxt["key"]).split(":")[-1].isdigit() else 1
    opp = lg.opponent(sim, g, num)
    lea = lg.league(sim, g)
    row = next((r for r in lg.table(lea) if r["name"] == opp["name"]), None)
    return {"date": calm.label(nxt["day"]), "in_days": nxt["day"] - w.day, "opponent": opp["name"], "rival": opp["name"] == lea.get("rival"),
            "their_record": f"{row['w']}-{row['l']}" if row else None, "their_rank": row["rank"] if row else None,
            "stars": [{"name": s["name"], "pos": s["pos"]} for s in opp["stars"][:2]]}


def view(sim, gid: str | None = None) -> dict:
    w = sim.w
    me = _me(sim)
    teams = _teams(sim, me)
    if not teams:
        tries = sorted((i for i in w.calendar if i["kind"] == "tryout" and 0 <= i["day"] - w.day <= 120), key=lambda i: i["day"])
        return {"teams": [], "tryouts": [{"name": i["name"], "date": calm.label(i["day"])} for i in tries[:4]]}
    g = next((t for t in teams if t["id"] == gid), None) or next((t for t in teams if _in_season(w, t)), None) or teams[0]
    sport = g["skill"]
    lea = lg.league(sim, g)
    rows = lg.table(lea)
    us = next(r for r in rows if r["ours"])
    pw = lea.get("power") or []
    now = pw[-1]["ranks"] if pw else {}
    prev = pw[-2]["ranks"] if len(pw) > 1 else {}
    for r in rows:
        r["power"] = now.get(r["name"])
        r["power_move"] = (prev[r["name"]] - now[r["name"]]) if r["name"] in prev and r["name"] in now else None
    st = me.stats.get(season_key(sport, w.day, g.get("levels", {}).get(me.id, "varsity"))) or {}
    # the races: everyone in the league by impact per game (yours and the other schools' stars), and your team's MVP
    race = []
    skey = season_key(sport, w.day, "varsity")
    for m in g["members"]:
        s = (w.chars[m].stats.get(skey) or {}) if m in w.chars else {}
        if s.get("games"):
            race.append({"id": m, "name": w.chars[m].name, "team": lea["ours"], "ours": True, "you": m == me.id,
                         "per": round(s["impact"] / s["games"], 1), "games": s["games"], "line": line_text(sport, s["line"])})
    for t in lea["teams"].values():
        for s in t["stars"]:
            if s["games"]:
                race.append({"id": s["id"], "name": s["name"], "team": t["name"], "ours": False, "you": False,
                             "per": round(s["impact"] / s["games"], 1), "games": s["games"], "line": line_text(sport, s["line"])})
    race.sort(key=lambda r: (-r["per"], r["name"]))
    cut = 60 if g.get("school") != "college" else 66
    mvp = sorted((r for r in race if r["ours"]), key=lambda r: (-r["per"] * r["games"], r["name"]))
    rec = me.recruiting or {}
    interest = sorted(((k, v) for k, v in (rec.get("interest") or {}).items() if k.endswith(":" + sport)), key=lambda kv: -kv[1])[:8]
    cols = {c["id"]: c for c in sim.cat.colleges}
    return {
        "teams": [{"id": t["id"], "name": t["name"], "sport": t["skill"], "in_season": _in_season(w, t)} for t in teams],
        "team": {"id": g["id"], "name": g["name"], "sport": sport, "label": sim.cat.sports["sports"][sport]["label"],
                 "record": f"{us['w']}-{us['l']}", "rank": us["rank"], "of": len(rows), "streak": us["streak"], "last": us["last"],
                 "next": _next(sim, g), "conference": "SCC" if g.get("school") != "college" else "Conference",
                 "title": lea.get("title"), "prestige": g.get("prestige"), "rival": lea.get("rival"), "ours": lea["ours"]},
        "you": {**_playing_time(sim, me, g), "season": line_text(sport, st.get("line") or {}) if st.get("games") else None,
                "games": st.get("games", 0), "starts": st.get("starts", 0), "log": _games(sim, me, g),
                "awards": [a["label"] for a in me.awards if a.get("sport") == sport][-6:]},
        "standings": rows,
        "leaders": lg.leaders(sim, lea, g),
        "potw": list(reversed(lea.get("potw") or []))[:6],
        "race": {"all_conf": race[:12], "you": next((i + 1 for i, r in enumerate(race) if r["you"]), None), "cut": cut,
                 "mvp": mvp[:6]},
        "recruiting": {"grade": me.grade, "score": (rec.get("score") or {}).get(sport),
                       "interest": [{"name": cols[k.split(":")[0]]["name"] if k.split(":")[0] in cols else k, "level": v,
                                     "tier": (cols.get(k.split(":")[0]) or {}).get("tier")} for k, v in interest],
                       "offers": [o for o in (rec.get("offers") or []) if o.get("sport") == sport]},
    }
