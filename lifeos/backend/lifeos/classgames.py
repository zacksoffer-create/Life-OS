"""Class games: quick challenges that keep class fun, a few seconds each.

Most school days one of your teachers throws something quick at the class: fill the beaker to the line, stop the pendulum
at the bottom, find the typo, put the cards in order, catch the ruler, a three-question lightning round. It's a moment
before class ("Second period, Chemistry...") that you can play yourself, hand to the classmate next to you, or sit out.
How you do is a small bump to your mood and your academics, it counts a little toward that class's grade, and the
classmate watching notices. Quiz and test days stay quizzes. When you skip ahead, your character decides for you.

The games (data/minigames.json, "class": true) are built into the phone. This module picks today's class and setup
(data/class_games.json) and makes each round: where the line is, how fast the needle swings, which cards get dealt.
Difficulty rises with your grade; your academics (and talent) widen the window a little.
"""
from __future__ import annotations

import random
import re
import zlib

from . import calendar as calm
from .catalogs import _base
from .rng import clamp

GAMES = ("hold", "sweep", "mathdash", "flash", "oddone", "lineup", "reflex")
LIGHT = {"class_game"}  # moments a skip-ahead doesn't stop for (your character just plays it)
TIER_PCT = {"great": 0.9, "good": 0.65, "miss": 0.3}
DEFAULT_SKIN = {"hold": "pour", "sweep": "generic", "mathdash": "math", "flash": "generic", "oddone": "general",
                "lineup": "general", "reflex": "test", "trivia": "quiz"}
HOW = {"hold": "Press and hold. Let go on the line.", "sweep": "Tap to stop it in the zone.",
       "mathdash": "Tap the right answer. Fast.", "flash": "Watch the pattern, then tap it back.",
       "oddone": "Tap the one that's different.", "lineup": "Tap them in order.", "reflex": "Wait for it. Tap the instant it goes."}

_DATA = None


def D() -> dict:
    global _DATA
    if _DATA is None:
        _DATA = _base("class_games.json")
    return _DATA


def _h(*p) -> int:
    return zlib.crc32(":".join(str(x) for x in p).encode())


class _Safe(dict):
    def __missing__(self, key):
        return ""


def _fmt(s: str, fill: dict) -> str:
    return s.format_map(_Safe(fill))


def state(w) -> dict:
    s = w.meta.setdefault("class_games", {})
    s.setdefault("recent", [])   # setup ids, newest last (so the same thing doesn't come up twice in a row)
    s.setdefault("played", 0)
    s.setdefault("won", 0)
    return s


def setups_for(subject: str) -> list:
    return [s for s in D()["setups"] if subject in s["subjects"]]


def _classmate(sim, c, salt):
    """Someone in the class with you: a classmate you know most of the time, anyone in your grade otherwise."""
    w = sim.w
    college = (c.grade or 0) >= 13
    pool = sorted((x for x in w.chars.values() if x.id != c.id and x.status == "active" and x.role == "student"
                   and x.school == c.school and x.location == c.location and (college or x.grade == c.grade)), key=lambda x: x.id)
    if not pool:
        return None
    known = [x for x in pool if (c.id, x.id) in w.rels and (x.id, c.id) in w.rels]
    use = known if known and _h(salt, "known") % 100 < 70 else pool
    return use[_h(salt, "who") % len(use)]


def maybe(sim, c):
    """Dawn on a school day: maybe one of your teachers has something quick planned (most days, never on quiz days)."""
    from . import classes, moments
    w = sim.w
    if not moments.control(w).get("class_games", True):
        return
    cal = sim.cat.world["calendar"]
    if c.role != "student" or c.location == "away" or c.status != "active" or not calm.is_school_day(w.day, cal):
        return
    if any(m["kind"] in ("class_quiz", "class_game") and m["day"] == w.day for m in w.meta.get("moments", [])):
        return  # a quiz today is today's class game
    rate = D()["rate"]["college" if (c.grade or 0) >= 13 else "high_school"]
    if _h(w.gen_seed, w.day, "class-game") % 1000 >= rate * 1000:
        return
    ctx = context(sim, c)
    if ctx:
        sim.moment_trigger("class_game", c.id, ctx)


def context(sim, c, setup_id: str | None = None) -> dict | None:
    """Today's class challenge: which class (and period), which setup, who's next to you, and every line already filled in."""
    from . import classes
    from .minigames import ready, reg
    w = sim.w
    sched = classes.schedule(sim, c)
    if not sched:
        return None
    st = state(w)
    salt = f"{w.gen_seed}:{w.day}"
    order = sorted(range(len(sched)), key=lambda i: _h(salt, "class", i))
    pick = None
    for i in order:
        cls = sched[i]
        opts = [s for s in setups_for(cls["subject"]) if ready(s["game"]) and (setup_id is None or s["id"] == setup_id)]
        fresh = [s for s in opts if s["id"] not in st["recent"][-4:]] or opts
        if fresh:
            pick = (i, cls, fresh[_h(salt, "setup") % len(fresh)])
            break
    if not pick and setup_id:  # asked for a specific one (tests, the lab): put it in the closest class you have
        s = next((x for x in D()["setups"] if x["id"] == setup_id), None)
        if s:
            i = next((k for k, x in enumerate(sched) if x["subject"] in s["subjects"]), 0)
            pick = (i, sched[i], s)
    if not pick:
        return None
    i, cls, s = pick
    them = _classmate(sim, c, salt)
    first = them.first if them else "the kid next to you"
    periods = D()["periods"]
    fill = {"period": periods[min(i, len(periods) - 1)], "class_name": cls["name"], "teacher": cls["teacher"] or "Your teacher",
            "them_first": first}

    def one(key, pool):
        return _fmt(pool[_h(salt, s["id"], key) % len(pool)], fill)

    g = reg()["games"][s["game"]]
    ctx = {"cg": s["id"], "cg_game": s["game"], "cg_skin": s.get("skin") or DEFAULT_SKIN.get(s["game"], "generic"), "cg_set": s.get("set"),
           "cg_how": s.get("how") or HOW.get(s["game"], ""), "class_id": cls["id"], "class_name": cls["name"], "teacher": cls["teacher"],
           "subject": cls["subject"], "period": fill["period"], "them_first": first,
           "cg_title": s["title"], "cg_text": one("text", s["text"]), "cg_go": s["go"],
           "cg_hint": s.get("hint") or f"you play it · about {g.get('secs', 8)} seconds",
           "cg_great": one("great", s["great"]), "cg_good": one("good", s["good"]), "cg_miss": one("miss", s["miss"]),
           "cg_pass_label": one("pass_label", D()["pass_label"]), "cg_pass": one("pass", D()["pass"]),
           "cg_sit_label": one("sit_label", D()["sit_label"]), "cg_sit": one("sit", D()["sit"])}
    if them:
        ctx["them"] = them.id
    if s["game"] == "trivia":  # a lightning round: three quick questions in this class's subject
        ctx.update({"subjects": [cls["subject"]], "math_courses": [cls.get("math") or "algebra1"], "n": 3, "seconds": 10,
                    "mg_label": cls["name"]})
    st["recent"] = (st["recent"] + [s["id"]])[-8:]
    return ctx


def after(sim, m, ev, index=None):
    """The class game is decided: if you went for it (played, or your character did), it counts toward that class."""
    from . import classes
    w = sim.w
    ctx = m["ctx"]
    c = w.chars[w.meta["protagonist"]]
    mg = (ev.get("data") or {}).get("minigame")
    where = f"{m['title']} in {ctx.get('class_name')}" if ctx.get("class_name") and ctx.get("class_name") not in m["title"] else m["title"]
    ev["text"] = (f"{where}: {c.short} went for it." if mg else
                  f"{where}: {c.short} let {ctx.get('them_first') or 'someone else'} take it." if index == 1 else
                  f"{where}: {c.short} sat it out.")
    if not mg:
        return  # handed it off or sat it out
    played = ctx.get("_mg")
    pct = played["pct"] if played else TIER_PCT[mg["tier"]]
    key = f"{classes._year_key(sim, c)}|{m['ctx'].get('class_id')}"
    g = classes.store(w).setdefault("games", {})
    g[key] = (g.get(key, []) + [round(pct, 3)])[-20:]
    st = state(w)
    st["played"] += 1
    st["won"] += 1 if mg["tier"] == "great" else 0


# ------------------------------------------------------------------------------------------- rounds

def skin_for(game: str, ctx: dict, title: str) -> dict:
    return {"id": ctx.get("cg_skin") or DEFAULT_SKIN.get(game, "generic"), "title": ctx.get("cg_title") or title,
            "how": ctx.get("cg_how") or HOW.get(game, ""), "badge": ctx.get("class_name") or ctx.get("mg_label") or "Just for fun"}


def round_for(sim, c, game: str, ctx: dict, seed: int, difficulty: float, skill: float) -> dict:
    """Everything the phone needs to play one round, tuned to your grade (difficulty) and how good you are (skill)."""
    rng = random.Random(seed)
    ease = clamp((skill - difficulty) / 100, -0.25, 0.3)  # better than the room: the window is a little wider
    hard = clamp((difficulty - 45) / 30, 0, 1)            # freshman 0 -> college senior about 0.8
    grade = c.grade or 9
    skin = ctx.get("cg_skin") or DEFAULT_SKIN.get(game, "generic")
    return {"hold": _hold, "sweep": _sweep, "mathdash": _mathdash, "flash": _flash, "oddone": _oddone, "lineup": _lineup,
            "reflex": _reflex}[game](rng, ease, hard, grade, skin, ctx)


def _hold(rng, ease, hard, grade, skin, ctx):
    tries = []
    for i in range(3):
        center = round(rng.uniform(0.45, 0.85), 3)
        tries.append({"center": center, "hw": round(0.065 * (1 + ease) * (1 - 0.15 * hard), 3),
                      "T": round(max(1.2, (1.9 - 0.45 * hard) * rng.uniform(0.9, 1.1)), 2)})
    return {"tries": tries, "near": 0.05, "curve": 1.35}


def _sweep(rng, ease, hard, grade, skin, ctx):
    tries = []
    for i, base in enumerate((0.55, 0.7, 0.85)):
        center = 0.5 if skin == "pendulum" else round(rng.uniform(0.2, 0.8), 3)  # a pendulum stops at the bottom (where it's fastest)
        tries.append({"center": center, "hw": round(0.075 * (1 + ease), 3),
                      "speed": round(base * (1 + 0.35 * hard), 3), "phase": round(rng.random(), 3)})
    return {"tries": tries, "near": 0.05, "timeout": 4.5}


SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
FORMULAS = ["H2O", "CO2", "CH4", "NaCl", "NH3", "O3", "C2H6", "H2SO4", "CaCO3", "C6H12O6", "NaHCO3", "H2O2", "Fe2O3", "C3H8",
            "KNO3", "C2H5OH", "HCl", "N2O"]


def atoms_in(formula: str) -> int:
    return sum(int(n or 1) for _, n in re.findall(r"([A-Z][a-z]?)(\d*)", formula))


def _options(rng, right, near) -> tuple[list, int]:
    """The right answer and two close wrong ones, shuffled."""
    wrong = []
    for x in near:
        if x != right and x not in wrong:
            wrong.append(x)
        if len(wrong) == 2:
            break
    opts = [right] + wrong
    rng.shuffle(opts)
    return opts, opts.index(right)


def _math_problem(rng, grade):
    kinds = ["add", "sub", "mul", "div"] + (["sq", "pct", "neg"] if grade >= 10 else ["mul"])
    k = rng.choice(kinds)
    if k == "add":
        a, b = rng.randint(12, 89), rng.randint(12, 89)
        q, ans = f"{a} + {b}", a + b
    elif k == "sub":
        a = rng.randint(40, 99)
        b = rng.randint(11, a - 5)
        q, ans = f"{a} − {b}", a - b
    elif k == "mul":
        top = 15 if grade >= 11 else 12
        a, b = rng.randint(3, top), rng.randint(3, 12)
        q, ans = f"{a} × {b}", a * b
    elif k == "div":
        b, ans = rng.randint(3, 12), rng.randint(3, 12)
        q = f"{b * ans} ÷ {b}"
    elif k == "sq":
        n = rng.randint(11, 20)
        q, ans = f"{n}²", n * n
    elif k == "pct":
        p = rng.choice([10, 20, 25, 50, 75])
        base = rng.choice([40, 60, 80, 120, 200, 240]) if p in (25, 75) else rng.randint(2, 20) * 10
        q, ans = f"{p}% of {base}", p * base // 100
    else:
        a, b = rng.randint(-15, -2), rng.randint(3, 15)
        if rng.random() < 0.5:
            q, ans = f"{a} + {b}", a + b
        else:
            q, ans = f"{a} − {b}", a - b
    sw = int(str(abs(ans))[::-1]) * (1 if ans >= 0 else -1) if abs(ans) >= 10 else ans + 3
    near = [ans + d for d in rng.sample([1, -1, 2, -2, 10, -10], 4)] + [sw, ans + 3, ans + 4]
    opts, idx = _options(rng, str(ans), [str(x) for x in near if ans < 0 or x >= 0])
    return {"q": q, "choices": opts, "answer": idx}


def _money_problem(rng):
    k = rng.choice(["change", "change", "tip", "off"])
    if k == "change":
        pay = rng.choice([10, 20, 20, 50])
        cents = rng.randint(150, pay * 100 - 25)
        q, ans = f"${cents / 100:.2f} paid with ${pay}. Change?", pay * 100 - cents
    elif k == "tip":
        bill, p = rng.choice([20, 30, 40, 60, 80, 50]), rng.choice([15, 20])
        q, ans = f"{p}% tip on ${bill}", bill * p
    else:
        price, p = rng.choice([20, 40, 60, 80, 120]), rng.choice([10, 25, 50])
        q, ans = f"{p}% off ${price}", price * (100 - p)
    fmt = lambda x: f"${x / 100:.2f}"
    opts, idx = _options(rng, fmt(ans), [fmt(ans + d) for d in rng.sample([100, -100, 10, -10, 5, -5, 50], 4) if ans + d > 0])
    return {"q": q, "choices": opts, "answer": idx}


def _atoms_problem(rng, used):
    pool = [f for f in FORMULAS if f not in used] or FORMULAS
    f = rng.choice(pool)
    used.add(f)
    n = atoms_in(f)
    opts, idx = _options(rng, str(n), [str(n + d) for d in rng.sample([1, -1, 2, -2, 3], 3) if n + d > 0])
    return {"q": f.translate(SUB), "choices": opts, "answer": idx}


def _mathdash(rng, ease, hard, grade, skin, ctx):
    used: set = set()
    probs = []
    for _ in range(5):
        if skin == "money":
            probs.append(_money_problem(rng))
        elif skin == "atoms":
            probs.append(_atoms_problem(rng, used))
        else:
            probs.append(_math_problem(rng, grade))
    base = {"money": 5.5, "atoms": 4.0}.get(skin, 3.6)
    return {"problems": probs, "seconds": round(clamp(base * (1 + ease) * (1 - 0.12 * hard), 2.6, 6.5), 2),
            "prompt": {"money": "Money math", "atoms": "How many atoms?"}.get(skin, "Quick math")}


def _flash(rng, ease, hard, grade, skin, ctx):
    n1 = 3 + (1 if hard >= 0.35 else 0)
    rounds = []
    for n in (n1, n1 + 1):
        seq = []
        while len(seq) < n:
            t = rng.randrange(9)
            if not seq or seq[-1] != t:
                seq.append(t)
        rounds.append(seq)
    return {"rounds": rounds, "grid": 3, "on": int(clamp(440 - 110 * hard - 60 * ease, 280, 480)), "gap": 170}


def _dna(rng, n):
    s = "".join(rng.choice("ACGT") for _ in range(n))
    i = rng.randrange(n)
    t = s[:i] + rng.choice([b for b in "ACGT" if b != s[i]]) + s[i + 1:]
    return s, t


def _oddone(rng, ease, hard, grade, skin, ctx):
    words = skin in ("english", "spanish")
    sizes, cols = ((9, 12, 15), (3, 3, 3)) if words else ((9, 16, 20), (3, 4, 4))
    bank = D()["banks"]["oddone"]
    pairs = list(bank.get(skin, bank["general"])["pairs"]) if skin not in ("dna", "color") else []
    rng.shuffle(pairs)
    rounds = []
    hue = rng.randrange(360)
    for r, (n, k) in enumerate(zip(sizes, cols)):
        odd = rng.randrange(n)
        if skin == "color":
            hue = (hue + rng.randint(70, 160)) % 360
            sat, lit = rng.randint(55, 75), rng.randint(45, 60)
            delta = round((16, 11, 8)[r] * (1 + 0.6 * ease) * (1 - 0.25 * hard), 1)
            base, other = f"hsl({hue} {sat}% {lit}%)", f"hsl({hue} {sat}% {round(lit + delta, 1)}%)"
            rounds.append({"tiles": [other if i == odd else base for i in range(n)], "odd": odd, "cols": k, "color": True})
            continue
        if skin == "dna":
            a, b = _dna(rng, 4 if r == 0 else 5)
        else:
            a, b = pairs[r % len(pairs)]
        rounds.append({"tiles": [b if i == odd else a for i in range(n)], "odd": odd, "cols": k})
    return {"rounds": rounds, "seconds": round(clamp(5.0 * (1 + ease) * (1 - 0.1 * hard), 3.5, 6.5), 2),
            "fast": round(clamp(2.4 * (1 + ease), 1.8, 3.2), 2), "mono": skin == "dna"}


def _year(v: int) -> str:
    return f"{-v} BC" if v < 0 else str(v)


def _lineup_items(rng, skin, ctx, k, used):
    """k cards with different values from this subject's bank (or made up on the spot for math and binary)."""
    banks = D()["banks"]["lineup"]
    subject = ctx.get("subject") or ""
    if skin == "general":
        skin = rng.choice(["us_history", "chemistry", "spanish", "art", "math"])
    if skin == "math":
        pool = [["−2", -2.0], ["−½", -0.5], ["0", 0.0], ["⅓", 1 / 3], ["0.4", 0.4], ["½", 0.5], ["⅔", 2 / 3], ["0.7", 0.7], ["¾", 0.75],
                ["0.8", 0.8], ["1", 1.0], ["√2", 2 ** 0.5], ["1.5", 1.5], ["π", 3.14159], ["√10", 10 ** 0.5], ["4", 4.0], ["2³", 8.0]]
        picks = []
        for item in rng.sample(pool, len(pool)):
            if all(abs(item[1] - p[1]) >= 0.05 for p in picks) and item[0] not in used:
                picks.append(item)
            if len(picks) == k:
                break
        return [{"label": a, "value": v} for a, v in picks], "Smallest first.", "none"
    if skin == "tech":
        nums = rng.sample(range(2, 16), k)
        return [{"label": format(n, "b"), "value": n, "reveal": str(n)} for n in nums], "Smallest first.", "reveal"
    if skin == "english":
        words = rng.choice(banks["english"]["words"])
        return [{"label": x, "value": x} for x in rng.sample(words, k)], "ABC order.", "none"
    key = {"history": subject if subject in banks else "us_history", "chemistry": "chemistry", "biology": "biology", "physics": "physics",
           "spanish": "spanish", "art": "art", "music": "music"}.get(skin, skin)
    b = banks.get(key) or banks["us_history"]
    how = b.get("how", "In order.")
    if "sets" in b:
        si = ctx.get("cg_set")
        si = si if isinstance(si, int) and 0 <= si < len(b["sets"]) else rng.randrange(len(b["sets"]))
        items = b["sets"][si]
        how = (b.get("set_how") or [how] * len(b["sets"]))[si]
    else:
        items = b["items"]
    fresh = [x for x in items if x[0] not in used]
    pool = fresh if len(fresh) >= k else items
    seen_v, picks = set(), []
    for x in rng.sample(pool, len(pool)):
        if x[1] not in seen_v:
            seen_v.add(x[1])
            picks.append(x)
        if len(picks) == k:
            break
    out = []
    for x in picks:
        it = {"label": x[0], "value": x[1]}
        if len(x) > 2:
            it["color"] = x[2]
        if b.get("show") == "year":
            it["reveal"] = _year(x[1])
        elif b.get("show") == "value":
            it["reveal"] = str(x[1])
        out.append(it)
    return out, how, "reveal" if b.get("show") in ("year", "value") else "none"


def _lineup(rng, ease, hard, grade, skin, ctx):
    k = 5 if hard >= 0.6 else 4
    rounds, used = [], set()
    for _ in range(2):
        items, how, show = _lineup_items(rng, skin, ctx, k, used)
        used |= {i["label"] for i in items}
        order = sorted(range(len(items)), key=lambda i: items[i]["value"])
        shown = list(range(len(items)))
        for _ in range(5):
            rng.shuffle(shown)
            if shown != order:
                break
        rounds.append({"items": [items[i] for i in shown], "order": [shown.index(i) for i in order], "how": how, "show": show})
    return {"rounds": rounds, "seconds": round(clamp(8.0 * (1 + ease) * (1 - 0.12 * hard) + (1.5 if k == 5 else 0), 5.5, 11), 2)}


def _reflex(rng, ease, hard, grade, skin, ctx):
    return {"tries": [{"wait": round(rng.uniform(0.9, 2.6), 2)} for _ in range(3)],
            "great_ms": int(clamp(360 + 150 * ease, 300, 430)), "ok_ms": int(clamp(560 + 150 * ease, 480, 660))}
