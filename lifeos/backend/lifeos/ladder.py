"""The ladder: who's popular at school, who's moving, and why.

Popularity in the game is real, recomputed every week from how everyone sees everyone: how many people know you, how
much they like and respect you (and how popular *they* are), the prestige of your teams and groups, and your reputation
(social.recompute_popularity). This turns it into the Scene tab's ladder:

- snapshot(): once a week, everyone's rank at school, so the ladder can show who went up and who went down (and your own
  rank over the whole story)
- view(): the full rankings (the whole school or one grade) with movement, what each person is known for, and how they
  connect to you (friend, family, crush, your storylines); the biggest movers this week and the thing that moved them;
  what your standing is made of, in its real ingredients, with what changed this week; and who's next up the ladder
- superlatives(): the yearbook, live: Most Popular, Best Athlete, Biggest Brain, Life of the Party...
"""
from __future__ import annotations

from . import calendar as calm
from .scene import _friend, _me, _mini, reputation, students, tier

KEEP = 16          # weekly snapshots kept for everyone (movement, sparklines for others)
SPORTS = ("football", "basketball", "baseball", "soccer", "softball")
GRADE_LABEL = {9: "Freshmen", 10: "Sophomores", 11: "Juniors", 12: "Seniors", 13: "College freshmen", 14: "College sophomores",
               15: "College juniors", 16: "College seniors"}


def _ranked(sim, me) -> list:
    return sorted(students(sim, me), key=lambda c: (-c.popularity, c.id))


def hist(w) -> dict:
    return w.meta.setdefault("scene_hist", {"snaps": [], "me": []})


def snapshot(sim):
    """Once a week, after popularity is recomputed: everyone's rank at your school."""
    w = sim.w
    me = _me(sim)
    if me is None:
        return
    ranked = _ranked(sim, me)
    h = hist(w)
    if h["snaps"] and h["snaps"][-1]["day"] == w.day:
        return
    ranks = {c.id: i + 1 for i, c in enumerate(ranked)}
    h["snaps"].append({"day": w.day, "rank": ranks, "of": len(ranked)})
    del h["snaps"][:-KEEP]
    h["me"].append([w.day, ranks.get(me.id, len(ranked)), len(ranked), round(me.popularity, 1)])


def _week_ago(w) -> dict | None:
    snaps = hist(w)["snaps"]
    if not snaps:
        return None
    older = [s for s in snaps if s["day"] <= w.day - 6]
    return older[-1] if older else snaps[0]


def _known_for(sim, c) -> str:
    w = sim.w
    rep = reputation(c)
    if rep:
        return rep[0]
    teams = [w.groups[g] for g in c.memberships if g in w.groups and w.groups[g].get("kind") == "team"]
    if teams:
        return teams[0].get("name", "a team")
    cl = w.cliques.get(c.flags.get("clique") or "")
    if cl and cl.get("active"):
        return cl["name"]
    return ""


def _cast_people(sim) -> dict:
    """Who your storylines are about: person id -> the storylines' names."""
    from . import dialogue
    w = sim.w
    out: dict = {}
    names = {p["id"]: p["pack"].get("name") for p in dialogue.packs()}
    cast = dialogue.merged().get("cast") or {}
    for slot, rec in (w.meta.get("cast_slots") or {}).items():
        cid = rec.get("id")
        if cid in w.chars:
            for pk in (cast.get(slot) or {}).get("packs") or []:
                if names.get(pk) and names[pk] not in out.setdefault(cid, []):
                    out[cid].append(names[pk])
    return out


def _tags(sim, me, cid, fam, cast) -> list:
    w = sim.w
    t = []
    if cid == me.id:
        return ["you"]
    if cid in fam:
        t.append("family")
    if me.flags.get("partner") == cid:
        t.append("dating")
    r = w.rels.get((me.id, cid))
    if r:
        if r.crush:
            t.append("crush")
        if r.label in ("best friend", "close friend", "friend") or _friend(w, me.id, cid):
            t.append("friend")
        if r.rivalry >= 50:
            t.append("rival")
    if cid in cast:
        t.append("storyline")
    return t


SOCIAL = ("milestone", "exclusion", "game", "tryout", "audition", "party", "prank", "spread_rumor", "rumor", "clique", "confront",
          "fight", "award", "election", "sign_up", "tease", "injury", "quit_group", "night", "dance", "ask", "date", "romance",
          "breakup", "partner", "introduce", "drama", "makeup", "cut")


def social(e) -> bool:
    """Something people at school would see or hear about (not your quiz, your pet or your job)."""
    from . import scheduler
    t = e["type"]
    if t == "moment":
        return scheduler._is_story(e.get("outcome"))  # a storyline scene: something you did
    return t.split(".")[0].split("_")[0] in SOCIAL or t in SOCIAL


GOOD = {"made", "walk_on", "captain", "lead", "legend", "formed", "friends", "close_friends", "best_friends", "landed", "star",
        "first_start", "won", "hit", "great", "good", "hosted", "elected", "win"}
BAD = {"flop", "caught", "cut", "dissolved", "drifted", "argument", "hurt", "quit", "lost", "dumped", "rejected", "loss", "benched"}


def tone(e, cid) -> int:
    """Good news (+1) or bad news (-1) for this person, or neither."""
    t, o = e["type"], e.get("outcome") or ""
    if t == "exclusion":  # the one frozen out is the actor; the table they tried to join didn't win anything
        return -1 if cid in (e.get("actors") or []) else 0
    if cid in (e.get("targets") or []) and cid not in (e.get("actors") or []):
        return -1 if t in ("spread_rumor", "rumor", "confront", "tease", "prank") else 0
    if t in ("injury", "confront", "quit_group", "breakup"):
        return -1
    return 1 if o in GOOD or t in ("award", "party") and o not in BAD else -1 if o in BAD else 0


def _why(sim, me, cid, since, want: int = 0) -> str | None:
    """The biggest thing that happened to them lately that you'd know about."""
    from .phone_api import private
    from . import pov
    w = sim.w
    best = None
    for eid in reversed(w.history.by_char.get(cid, [])[-60:]):
        e = w.history.events.get(eid)
        if not e or e["day"] < since or private(e, me.id) or e["importance"] < 18 or not social(e) or e["type"] == "moment":
            continue
        if cid not in e.get("actors", []) and e["type"] not in ("rumor", "spread_rumor", "confront"):
            continue  # it happened to them, not just near them
        if want and tone(e, cid) != want:
            continue  # risers get the good news, fallers the bad
        if best is None or e["importance"] > best["importance"]:
            best = e
    return pov.event_line(w, best, me.id) if best else None


def _parts(sim, me, studs) -> dict:
    """What your standing is made of, in the same ingredients the game counts, next to the best at your school."""
    w = sim.w
    thr = w.rules["rel.friend_threshold"]
    ids = [c.id for c in studs]

    def counts(cid):
        known = liked = disliked = 0
        fans = []
        for t in ids:
            if t == cid:
                continue
            r = w.rels.get((t, cid))
            if not r:
                continue
            if r.familiarity >= 30:
                known += 1
            if r.affection >= thr:
                liked += 1
                fans.append(t)
            elif r.affection <= -10:
                disliked += 1
        return known, liked, disliked, fans
    best = {"known": 1, "liked": 1, "fans": 1, "groups": 1}
    mine = None
    for c in studs:
        k, l, d, fans = counts(c.id)
        pull = sum(w.chars[f].popularity for f in sorted(fans, key=lambda f: -w.chars[f].popularity)[:10]) / 10
        g = sum(w.groups[x].get("prestige", 0) for x in c.memberships if x in w.groups)
        best = {"known": max(best["known"], k), "liked": max(best["liked"], l), "fans": max(best["fans"], pull), "groups": max(best["groups"], g)}
        if c.id == me.id:
            mine = (k, l, d, fans, pull, g)
    k, l, d, fans, pull, g = mine or (0, 0, 0, [], 0, 0)
    n = max(1, len(ids) - 1)
    fam = set(sim.siblings(me.id))
    top_fans = sorted((f for f in fans if f not in fam), key=lambda f: (-w.chars[f].popularity, f))[:3]
    groups = sorted((w.groups[x] for x in me.memberships if x in w.groups and w.groups[x].get("prestige", 0) > 0),
                    key=lambda x: -x.get("prestige", 0))
    rep = reputation(me)
    parts = [
        {"key": "reach", "label": "People who know you", "value": k, "of": n, "score": round(100 * k / best["known"]),
         "line": f"{k} of {n} people at school know who you are."},
        {"key": "liked", "label": "People who like you", "value": l, "score": round(100 * l / best["liked"]),
         "line": f"{l} like you" + (f", {d} don't" if d else "") + "."},
        {"key": "fans", "label": "Who likes you", "score": round(100 * pull / best["fans"]),
         "line": ("Popular people like you: " + ", ".join(w.chars[f].first for f in top_fans) + ".") if top_fans and w.chars[top_fans[0]].popularity >= 60
         else ("Your friends: " + ", ".join(w.chars[f].first for f in top_fans) + ". Getting in with more popular people moves you faster.") if top_fans
         else "Your family's in your corner. Nobody else yet." if any(f in fam for f in fans) else "Nobody's really in your corner yet."},
        {"key": "groups", "label": "Teams and groups", "score": round(100 * g / best["groups"]),
         "line": ("On " + ", ".join(x.get("name", "a team") for x in groups[:3]) + ".") if groups else "No team or club yet. Varsity and the big clubs count for a lot."},
        {"key": "rep", "label": "Reputation", "score": min(100, round(10 * sum(v for v in (me.reputation or {}).values() if v > 0))),
         "line": ("People say you're " + ", ".join(rep) + ".") if rep else "No reputation yet: nothing people talk about."},
    ]
    weakest = min(parts[:4], key=lambda x: x["score"])
    tip = {"reach": "More people need to know you: games, parties, getting introduced.",
           "liked": "People know you, but not enough of them like you. Hang out, make up with the ones you're fighting with.",
           "fans": "Get in with people who are already popular: their friends follow.",
           "groups": ("Your teams count. Varsity and the big clubs count most: make varsity, or add a club people know." if groups
                      else "Make a team or join a big club. Tryouts and sign-ups are on your calendar.")}[weakest["key"]]
    return {"parts": parts, "tip": tip}


def view(sim, scope: str = "school") -> dict:
    """The ladder for the Scene tab: you, the movers, what moves you, your storylines' people, and the full rankings
    (scope: school, grade (yours), or 9-12)."""
    w = sim.w
    me = _me(sim)
    ranked = _ranked(sim, me)
    if not hist(w)["snaps"]:
        snapshot(sim)  # the first time: a starting point, movement shows from next week
    then = _week_ago(w)
    fam = set(sim.siblings(me.id))
    cast = _cast_people(sim)
    rank_of = {c.id: i + 1 for i, c in enumerate(ranked)}

    def move(cid):
        if not then or then["day"] == w.day or cid not in then["rank"]:
            return None
        return then["rank"][cid] - rank_of[cid]

    thr = w.rules["rel.friend_threshold"]
    friends = [f for f in w.out.get(me.id, {}) if f in w.chars and _friend(w, me.id, f) and w.chars[f].status == "active"]

    def via(cid):
        """You barely know them: the friend of yours who could introduce you."""
        r = w.rels.get((me.id, cid))
        if cid == me.id or (r and r.familiarity >= 15):
            return None
        best = max((f for f in friends if f != cid and (w.rels.get((f, cid)) and w.rels[(f, cid)].affection >= thr)),
                   key=lambda f: (w.rels[(f, cid)].affection, f), default=None)
        return _mini(w, best) if best else None

    def row(c, r=None):
        mine = w.rels.get((me.id, c.id))
        return {**_mini(w, c.id), "rank": r or rank_of[c.id], "move": move(c.id), "pop": round(c.popularity), "grade": c.grade,
                "known_for": _known_for(sim, c), "tags": _tags(sim, me, c.id, fam, cast), "storylines": cast.get(c.id, []),
                "label": (mine.label if mine and mine.familiarity >= 15 else None) if c.id != me.id else None, "via": via(c.id)}
    if scope == "grade":
        pool = [c for c in ranked if c.grade == me.grade]
    elif scope.isdigit():
        pool = [c for c in ranked if c.grade == int(scope)]
    else:
        pool = ranked
    rows = [{**row(c), "scope_rank": i + 1} for i, c in enumerate(pool)]
    # the movers: up and down the most this week, and what moved them
    since = then["day"] if then else w.day - 7
    moves = [(move(c.id), c) for c in ranked if move(c.id)]
    up = sorted((m for m in moves if m[0] > 0), key=lambda m: (-m[0], m[1].id))[:5]
    down = sorted((m for m in moves if m[0] < 0), key=lambda m: (m[0], m[1].id))[:5]
    movers = {"up": [{**row(c), "why": _why(sim, me, c.id, since, +1)} for _, c in up],
              "down": [{**row(c), "why": _why(sim, me, c.id, since, -1)} for _, c in down]}
    # you
    my = rank_of.get(me.id, len(ranked))
    above = ranked[my - 2] if my >= 2 else None
    grade = [c for c in ranked if c.grade == me.grade]
    myhist = hist(w)["me"][-60:]
    events = []
    for eid in reversed(w.history.by_char.get(me.id, [])[-80:]):
        e = w.history.events.get(eid)
        if e and e["day"] >= since and e["importance"] >= 18 and social(e):
            from . import pov
            events.append({"text": pov.event_line(w, e, me.id), "date": calm.label(e["day"]), "imp": e["importance"]})
    events = sorted(events, key=lambda x: -x["imp"])[:4]
    you = {**row(me), "of": len(ranked), "tier": tier(my, len(ranked)), "grade_rank": next((i + 1 for i, c in enumerate(grade) if c.id == me.id), 0),
           "grade_of": len(grade), "grade_label": GRADE_LABEL.get(me.grade, "Your grade"),
           "history": [{"day": d, "date": calm.label(d), "rank": r, "of": n} for d, r, n, _ in myhist],
           "next_up": {**row(above), "gap": round(above.popularity - me.popularity, 1)} if above else None,
           "this_week": events, **_parts(sim, me, ranked)}
    people = []
    for cid, lines in cast.items():
        if cid in rank_of and cid != me.id:
            people.append({**row(w.chars[cid]), "storylines": lines})
        elif cid in w.chars and cid != me.id:  # graduated, away at college: still yours
            c = w.chars[cid]
            people.append({**_mini(w, cid), "rank": None, "move": None, "known_for": c.year_label, "tags": ["storyline"], "storylines": lines})
    return {"you": you, "movers": movers, "rows": rows, "scope": scope, "of": len(pool), "storyline_people": people,
            "week_of": calm.label(then["day"]) if then else None, "superlatives": superlatives(sim, me, ranked)}


def superlatives(sim, me, ranked) -> list:
    """The yearbook, live. Each one: who has it, and where you'd place."""
    w = sim.w

    def sport(c):
        best = max((c.skills.get(s, 0) for s in SPORTS), default=0)
        varsity = any(w.groups[g].get("kind") == "team" and w.groups[g].get("level", "varsity") == "varsity" for g in c.memberships if g in w.groups)
        return best + (12 if varsity else 0)
    rep = lambda c, *ks: sum((c.reputation or {}).get(k, 0) for k in ks)
    cats = [
        ("popular", "Most Popular", lambda c: c.popularity),
        ("athlete", "Best Athlete", sport),
        ("brain", "Biggest Brain", lambda c: c.gpa * 25 + c.skills.get("academics", 0) * 0.3),
        ("party", "Life of the Party", lambda c: rep(c, "host", "legend") * 3 + c.traits.get("sociability", 50) * 0.2),
        ("nice", "Nicest Person", lambda c: rep(c, "kind") * 3 + c.traits.get("empathy", 50) * 0.5),
        ("drama", "Drama Magnet", lambda c: rep(c, "gossip", "troublemaker", "mean") * 3 + c.traits.get("volatility", 50) * 0.2),
        ("success", "Most Likely to Succeed", lambda c: c.traits.get("ambition", 50) * 0.5 + c.gpa * 12 + c.traits.get("discipline", 50) * 0.3),
    ]
    out = []
    for key, label, f in cats:
        order = sorted(ranked, key=lambda c: (-f(c), c.id))
        if not order:
            continue
        pos = next((i + 1 for i, c in enumerate(order) if c.id == me.id), None)
        out.append({"key": key, "label": label, "winner": {**_mini(w, order[0].id), "you": order[0].id == me.id},
                    "runners": [_mini(w, c.id) for c in order[1:3]], "you": pos})
    # the couple: two people together, both liked, into each other
    best, score = None, -1
    seen = set()
    for c in ranked:
        p = c.flags.get("partner")
        if not p or p not in w.chars or frozenset((c.id, p)) in seen:
            continue
        seen.add(frozenset((c.id, p)))
        r1, r2 = w.rels.get((c.id, p)), w.rels.get((p, c.id))
        s = (c.popularity + w.chars[p].popularity) / 2 + ((r1.affection if r1 else 0) + (r2.affection if r2 else 0)) / 4
        if s > score:
            best, score = (c.id, p), s
    if best:
        out.append({"key": "couple", "label": "Cutest Couple", "winner": {**_mini(w, best[0]), "you": me.id in best},
                    "partner": _mini(w, best[1]), "runners": [], "you": 1 if me.id in best else None})
    return out
