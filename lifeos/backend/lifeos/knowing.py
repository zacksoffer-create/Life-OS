"""Who everyone is, and how much of it you know.

Everybody has a profile built from the simulation as it stands right now: their year, the teams they play on and where,
clubs and job, their group, who they're dating, their family at school, what people say about them, what they're into,
what they're like, who they're closest to, what's going on with them lately, what's next for them, what drives them,
what they're working toward and who they like.

How much of it you know depends on how well you know them (`level`):
  - everyone: what the whole school knows (year, teams, clubs, job, group, who they're dating, family, reputation);
  - know: you actually know them (familiarity 30+, or family): what they're into, what they're like, who they're
    closest to, what's going on lately, grades, what's next;
  - close: friends who trust each other, family you get along with, or the person you're dating: what drives them, what
    they're working toward, who they like, what home is like.
The rest shows as "you'd know more if you were closer", with what it takes.
"""
from __future__ import annotations

from . import calendar as calm

LEVELS = ("everyone", "know", "close")
LEVEL_LABEL = {"everyone": "Everyone knows", "know": "You know", "close": "Only people close to them know"}
UNLOCK = {"know": "Spend more time with {first} and you'll learn what they're into, what they're like and what's going on with them.",
          "close": "Get close to {first} (friends who trust each other) and you'll learn what drives them, what they want and who they like."}
TRAIT_WORDS = {"sociability": ("outgoing", "quiet"), "confidence": ("confident", "unsure of themselves"),
               "discipline": ("disciplined", "easily distracted"), "ambition": ("ambitious", "laid-back about the future"),
               "impulsivity": ("impulsive", "careful"), "empathy": ("caring", "blunt"), "competitiveness": ("competitive", "easygoing"),
               "curiosity": ("curious", "set in their ways"), "volatility": ("hot-headed", "even-keeled"), "loyalty": ("loyal", "independent")}
MOTIVE_WORDS = {"achievement": "winning and getting somewhere", "approval": "being liked and noticed", "belonging": "their people",
                "pleasure": "having a good time", "altruism": "helping people", "mastery": "getting really good at things"}
HOME = {"warm": "Warm, supportive parents", "strict": "Strict parents with high expectations", "permissive": "Laid-back parents",
        "distant": "Busy, distant parents", "overbearing": "Loving but overbearing parents"}
KNOWN_AS = {"embarrassed": "the one with the embarrassing story", "troublemaker": "trouble", "flaky": "flaky"}
INTEREST_WORDS = {"pickup_games": "pickup ball", "batting_cage": "the batting cages", "academics": "school", "fitness": "working out",
                  "tech": "robotics and code", "drama": "acting", "art": "art", "music": "music", "writing": "writing"}


def level(sim, viewer: str, cid: str) -> str:
    """How well viewer knows cid: 'everyone' (only what the school knows), 'know' or 'close'."""
    w = sim.w
    if viewer == cid:
        return "close"
    r = w.rels.get((viewer, cid))
    back = w.rels.get((cid, viewer))
    V, C = w.chars.get(viewer), w.chars.get(cid)
    family = cid in sim.siblings(viewer) or bool(V and C and V.household_id and V.household_id == C.household_id)
    if family:
        return "close" if (r is None or r.affection >= 15) else "know"
    if V is not None and V.flags.get("partner") == cid:
        return "close"
    if C is not None and C.role == "staff" and any(w.groups.get(g, {}).get("staff") == cid for g in (V.memberships if V else [])):
        return "know"  # your coach or club advisor
    if r and back and r.familiarity >= 45 and r.affection >= 40 and back.trust >= 45:
        return "close"
    if r and r.familiarity >= 30:
        return "know"
    return "everyone"


def _first(w, cid) -> str:
    c = w.chars.get(cid)
    return c.first if c else cid


def _interest_label(sim, k) -> str:
    if k in INTEREST_WORDS:
        return INTEREST_WORDS[k]
    lab = (sim.cat.skills.get(k) or sim.cat.hobbies.get(k) or {}).get("label") or k.replace("_", " ")
    return lab.lower()


def teams(sim, c) -> list:
    """'Starting striker, Guilford Girls Soccer' for each team they're on (or coach)."""
    w = sim.w
    out = []
    sp = sim.cat.sports["sports"]
    for gid in c.memberships:
        g = w.groups.get(gid)
        if not g or g["kind"] != "team":
            continue
        sport = g.get("skill")
        lvl = (g.get("levels") or {}).get(c.id, "varsity")
        pos = c.positions.get(sport)
        role = (sp.get(sport, {}).get("positions", {}).get(pos) or "").lower()
        starter = bool(c.flags.get(f"started:{gid}:{lvl}"))
        bits = [("starting " if starter else "") + (role or "player")]
        if lvl == "jv":
            bits.append("JV")
        out.append({"id": gid, "text": f"{bits[0].capitalize()}{', JV' if lvl == 'jv' else ''} · {g['name']}", "team": g["name"],
                    "sport": sport})
    if c.role == "staff":
        for g in w.groups.values():
            if g.get("staff") == c.id and g["kind"] in ("team", "production", "club"):
                out.append({"id": g["id"], "text": g["name"], "team": g["name"], "sport": g.get("skill"), "coach": g["kind"] == "team"})
    return out


def best_friend(sim, cid, exclude=()) -> str | None:
    w = sim.w
    fam = set(sim.siblings(cid))
    rows = [(r.affection, o) for o, r in w.out.get(cid, {}).items() if o in w.chars and o not in fam and o not in exclude
            and w.chars[o].role != "staff" and w.chars[o].status == "active" and r.affection >= w.rules["rel.friend_threshold"]]
    return max(rows)[1] if rows else None


def crush_of(sim, cid) -> str | None:
    """Who they're into right now (not the person they're dating)."""
    from .social import romance_ok
    w = sim.w
    c = w.chars[cid]
    rows = [(r.attraction, o) for o, r in w.out.get(cid, {}).items() if o in w.chars and o != c.flags.get("partner")
            and w.chars[o].status == "active" and r.attraction >= w.rules["rel.crush_threshold"] and romance_ok(w, cid, o)]
    return max(rows)[1] if rows else None


def lately(sim, c, viewer=None) -> list:
    """What's going on with them right now, as you'd hear it."""
    w = sim.w
    out = []
    hurt = c.flags.get("injured_until", -1)
    if hurt >= w.day:
        wk = max(1, round((hurt - w.day) / 7))
        out.append(f"Out with a {c.flags.get('injury') or 'injury'}, about {wk} more week{'s' if wk != 1 else ''}")
    if c.flags.get("grounded_until", -1) >= w.day:
        out.append("Grounded")
    for m in sorted(c.memories, key=lambda m: -m["day"]):
        if w.day - m["day"] > 14:
            break
        if m["kind"] == "cut_from_team":
            out.append("Just got cut from a team")
        elif m["kind"] == "made_team":
            team = next((w.groups[t]["name"] for t in m.get("tags") or [] if t in w.groups), None)
            out.append(f"Just made {team}" if team else "Just made a team")
        elif m["kind"] == "broke_up":
            out.append("Just went through a breakup")
        elif m["kind"] == "award":
            out.append(m["text"])
        elif m["kind"] == "star_game":
            out.append(f"Big game: {m['text']}")
        if len(out) >= 3:
            break
    try:
        from . import drama
        for f in drama.state(w)["fallouts"][::-1]:
            if not f["fixed"] and c.id in (f["a"], f["b"]) and w.day - f["day"] <= 30:
                other = f["b"] if f["a"] == c.id else f["a"]
                out.append(f"Not speaking to {_first(w, other)}")
                break
    except Exception:  # noqa: BLE001  drama state is optional in older saves
        pass
    game = next((i for i in w.calendar if i["kind"] == "game" and i.get("group") in c.memberships and 0 <= i["day"] - w.day <= 3), None)
    if game:
        from .sports import opponent_name
        g = w.groups[game["group"]]
        last = str(game.get("key", "")).split(":")[-1]
        when = "today" if game["day"] == w.day else "tomorrow" if game["day"] == w.day + 1 else calm.label(game["day"]).split(",")[0]
        out.append(f"{g['name']} plays {opponent_name(sim, g, int(last) if last.isdigit() else 1)} {when}")
    stress = (c.needs or {}).get("stress", 40)
    if stress >= 70:
        out.append("Really stressed lately")
    elif c.mood <= 30:
        out.append("Seems down lately")
    elif c.mood >= 80:
        out.append("In a great mood lately")
    return out[:4]


def next_for(sim, c) -> str | None:
    """College, work, offers: what's next for them."""
    w = sim.w
    p = c.path or {}
    if p.get("kind") == "college" and p.get("name"):
        return (f"Plays {p['sport']} at {p['name']}" if p.get("sport") and p.get("started") else
                f"Committed to play {p['sport']} at {p['name']}" if p.get("sport") else
                f"At {p['name']}" if p.get("started") else f"Going to {p['name']}")
    if p.get("kind") == "work":
        return "Staying in town to work"
    if p.get("kind") == "pro":
        return f"Playing pro ball{(' for the ' + p['team']) if p.get('team') else ''}"
    offers = (c.recruiting or {}).get("offers") or []
    if offers:
        o = offers[-1]
        return f"{len(offers)} college offer{'s' if len(offers) != 1 else ''} (latest: {o.get('short') or o['name']}, {o['sport']})"
    interest = (c.recruiting or {}).get("interest") or {}
    if interest:
        key = max(interest, key=lambda k: interest[k])
        col = sim.cat.college_by_id.get(key.split(":")[0])
        if col:
            return f"{col['short']} coaches are keeping an eye on them ({key.split(':')[1]})"
    return None


def _year(sim, c) -> str:
    w = sim.w
    if c.role == "staff":
        return c.role_label or "Staff"
    age = c.age(w.day)
    if c.role == "student" and c.school == "hchs":
        return f"{c.year_label}, {age}"
    if c.role == "student":
        where = (w.meta.get("college") or {}).get("short") if c.school == "college" else (c.path or {}).get("name")
        return f"{c.year_label}{(' at ' + where) if where else ''}, {age}"
    return f"Graduated, {age}"


def glance(sim, cid) -> str:
    """One line: 'Sophomore · Girls Soccer · dating Theo'."""
    w = sim.w
    c = w.chars[cid]
    bits = [c.year_label]
    t = teams(sim, c)
    if t and c.role != "staff":
        bits.append(t[0]["team"].replace(sim.cat.world["school"]["name"].split()[0] + " ", "", 1))
    if c.flags.get("partner") in w.chars:
        bits.append(f"dating {_first(w, c.flags['partner'])}")
    return " · ".join(bits)


def profile(sim, viewer: str, cid: str) -> dict:
    """Everything about cid, split by who'd know it, with what viewer knows unlocked."""
    from . import scene
    w = sim.w
    c = w.chars[cid]
    lv = level(sim, viewer, cid)
    facts = {k: [] for k in LEVELS}

    def add(k, v, at="everyone", tone=None):
        if v:
            facts[at].append({"k": k, "v": v, **({"tone": tone} if tone else {})})

    # everyone knows
    add("Year", _year(sim, c))
    for t in teams(sim, c):
        add("Plays" if c.role != "staff" else "Coaches" if t.get("coach") else "Runs", t["text"])
    clubs = [w.groups[g]["name"] for g in c.memberships if w.groups[g]["kind"] in ("club", "production", "council")]
    add("Clubs", ", ".join(clubs))
    job = next((w.groups[g]["name"] for g in c.memberships if w.groups[g]["kind"] == "job"), None)
    add("Works at", job)
    if c.role == "student":
        cl = w.cliques.get(c.flags.get("clique") or "")
        add("Their group", cl["name"] if cl and cl.get("active") else "Floats between groups")
        p = c.flags.get("partner")
        add("Dating", "you" if p == viewer else _first(w, p) if p in w.chars else "Nobody right now")
    sibs = [s for s in sim.siblings(cid) if w.chars[s].role in ("student", "alumni")]
    if sibs:
        add("Family", ", ".join(f"{_first(w, s)} ({'you' if s == viewer else w.chars[s].year_label.lower()})" for s in sibs))
    tags = sorted(((k, v) for k, v in (c.reputation or {}).items() if v >= 4), key=lambda x: -x[1])[:3]
    add("Known as", ", ".join(KNOWN_AS.get(k) or scene.REP_WORDS.get(k, k.replace("_", " ")) for k, _ in tags))
    # you know them
    if c.role != "staff":
        top = [k for k, v in sorted(c.interests.items(), key=lambda x: -x[1]) if v >= 50][:3]
        add("Into", ", ".join(_interest_label(sim, k) for k in top), "know")
    hi = sorted(((v, k) for k, v in c.traits.items() if k in TRAIT_WORDS and v >= 65), reverse=True)[:2]
    lo = sorted((v, k) for k, v in c.traits.items() if k in TRAIT_WORDS and v <= 32)[:1]
    words = [TRAIT_WORDS[k][0] for _, k in hi] + [TRAIT_WORDS[k][1] for _, k in lo]
    add("What they're like", ", ".join(words) or "pretty even, no sharp edges", "know")
    if c.role != "staff":
        bf = best_friend(sim, cid)
        add("Closest to", "you" if bf == viewer else _first(w, bf) if bf else None, "know")
        foe = [(max(r.rivalry, -r.affection), o) for o, r in w.out.get(cid, {}).items() if o in w.chars
               and (r.rivalry >= 45 or r.affection <= -30) and w.chars[o].status == "active"]
        if foe:
            o = max(foe)[1]
            add("Doesn't get along with", "you" if o == viewer else _first(w, o), "know")
    for line in lately(sim, c, viewer):
        add("Lately", line, "know")
    if c.role == "student" and c.gpa:
        add("Grades", "honor roll" if c.gpa >= 3.6 else "solid" if c.gpa >= 3.0 else "getting by" if c.gpa >= 2.4 else "struggling", "know")
    add("What's next", next_for(sim, c), "know")
    # close
    mot = sorted(((v, k) for k, v in (c.motives or {}).items() if k in MOTIVE_WORDS), reverse=True)
    if mot:
        add("What drives them", MOTIVE_WORDS[mot[0][1]], "close")
    goals = [g["label"] for g in sorted(c.goals, key=lambda g: -g.get("priority", 0)) if g["status"] == "active"][:2]
    add("Working toward", ", ".join(goals), "close")
    if c.role == "student":
        cr = crush_of(sim, cid)
        add("Has a thing for", "someone they won't name around you 👀" if cr == viewer else _first(w, cr) if cr else None, "close", "love")
    h = w.households.get(c.household_id or "")
    if h and c.role != "staff":
        add("At home", HOME.get(h.get("style")) or (h.get("style_label") or "").capitalize(), "close")
    open_ = LEVELS[: LEVELS.index(lv) + 1]
    sections = [{"level": k, "label": LEVEL_LABEL[k], "facts": facts[k]} for k in open_ if facts[k]]
    hidden = sum(len(facts[k]) for k in LEVELS if k not in open_)
    nxt = LEVELS[LEVELS.index(lv) + 1] if lv != "close" else None
    return {"level": lv, "glance": glance(sim, cid), "sections": sections, "hidden": hidden,
            "unlock": UNLOCK[nxt].format(first=c.first) if nxt and hidden else None}
