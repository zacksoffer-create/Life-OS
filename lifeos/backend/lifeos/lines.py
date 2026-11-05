"""Lines: every line of dialogue can be texted or said, can fit its moment, and doesn't come back too soon.

A text-pool entry is a plain string (the text), or an object:
    {"text": "u free later?", "talk": "\\"You free later?\\" {them_first} asks.", "when": ["late_night", "close"]}
`text` is how it reads on the phone. `talk` is how they'd say it to your face; leave it out and the game makes one from
the text (capitalized, abbreviations spelled out, in quotes, with who said it and how: "Jake says at your locker").
`when` lists context tags (TAGS) that all have to be true for the line to be used. A line that fits the moment more
specifically gets picked over a generic one more often than not.

Mods dress a line for its context: an opener ("ok so", "u up?") or a closer ("lol") on a text, and on a spoken line how
it's said ("{them_first} {says}, grinning"). One base line times the openers, closers and ways of saying it is many lines.
Base mods are in data/mods.json; dialogue packs add more.

Nothing repeats too soon. Every pick is remembered in w.meta["lines"], and a line used recently sits out while anything
else fits; the bigger the pool, the longer it rests. Scene text and say/text lines can be lists of variants and get the
same treatment. All of this is presentation: it never touches the simulation's random numbers.
"""
from __future__ import annotations

import re
import zlib

TAGS = {
    "morning": "Early, before or during classes.",
    "afternoon": "Lunch, after school, or the middle of a free day.",
    "evening": "Evening.",
    "late_night": "Late at night.",
    "school_day": "A school day.",
    "weekend": "Saturday or Sunday.",
    "summer": "Summer break.",
    "high_school": "You're in high school.",
    "college": "You're in college.",
    "new": "They barely know you.",
    "friend": "They're your friend.",
    "close": "You're close (best-friend territory).",
    "crush": "They're into you (and you're not dating).",
    "partner": "You're dating.",
    "ex": "You used to date.",
    "rival": "There's a rivalry between you.",
    "family": "A parent or a brother or sister.",
    "parent": "Mom or Dad.",
    "sibling": "A brother or sister.",
    "coach": "A coach.",
    "teammate": "On a team with you.",
    "happy": "They're in a good mood.",
    "down": "They're in a bad mood.",
    "stressed": "They're stressed.",
    "tired": "They're running on empty.",
    "hurt": "They're injured right now.",
    "you_happy": "You're in a good mood.",
    "you_down": "You're in a bad mood.",
    "you_stressed": "You're stressed.",
    "from_guy": "A guy is saying it.",
    "from_girl": "A girl is saying it.",
    "to_guy": "You're a guy.",
    "to_girl": "You're a girl.",
    "guys": "Everyone in the conversation is a guy (you and them, or the whole group chat or team).",
    "girls": "Everyone in the conversation is a girl (you and them, or the whole group chat or team).",
    "same_year": "They're in your grade.",
    "older": "They're older than you (a higher grade).",
    "younger": "They're younger than you (a lower grade).",
}
PHASE_TAG = {"dawn": "morning", "classes": "morning", "lunch": "afternoon", "after_school": "afternoon", "day": "afternoon",
             "evening": "evening", "night": "late_night"}
# pools whose lines are casual enough to dress with an opener or a closer
DRESS = {"invite", "invite_date", "invite_later", "after_good", "after_good_date", "after_awkward", "u_ok", "they_apologize", "congrats_team",
         "consolation_cut", "congrats_award", "rumor", "chatter_partner", "flirt_in", "park_followup", "sibling_home", "sibling_chatter", "chatter_plans", "chatter_school", "chatter_vent", "chatter_funny",
         "chatter_game", "friend_first_day", "scene"}
SPOKEN = [(r"\bu\b", "you"), (r"\bur\b", "your"), (r"\br\b", "are"), (r"\btn\b", "tonight"), (r"\btmrw\b", "tomorrow"),
          (r"\bpls\b", "please"), (r"\bplz\b", "please"), (r"\bbc\b", "because"), (r"\brn\b", "right now"), (r"\bidk\b", "I don't know"),
          (r"\btho\b", "though"), (r"\bok\b", "okay"), (r"\bppl\b", "people"), (r"\bw\b", "with"), (r"\bfr\b", "for real"), (r"\bngl\b", "not gonna lie"),
          (r"\bi\b", "I"), (r"\bim\b", "I'm"), (r"\bi'm\b", "I'm"), (r"\bi'll\b", "I'll"), (r"\bi've\b", "I've"), (r"\bi'd\b", "I'd")]
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]+")
TRAILING = re.compile(r"(\s+(lol|lmao|haha|hahaha|lmfao))+[.!]*$", re.I)
OPEN_SKIP = {"hey", "yo", "ok", "okay", "so", "random", "u", "ugh", "morning", "hi", "hello", "wait", "omg", "bro", "dude"}


def _h(*parts) -> int:
    return zlib.crc32(":".join(str(p) for p in parts).encode())


def hid(s: str) -> str:
    return format(zlib.crc32(s.strip().lower().encode()), "08x")


def entry(x) -> dict:
    """A pool entry as {text, talk, when}, whichever way it was written."""
    if isinstance(x, dict):
        return {"text": x.get("text") or x.get("talk") or "", "talk": x.get("talk"), "when": list(x.get("when") or [])}
    return {"text": str(x), "talk": None, "when": []}


def text_of(x) -> str:
    return entry(x)["text"]


def fill(s, kw) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(kw.get(m.group(1), m.group(0))), s)


# ---------------------------------------------------------------------------------------- context

GENDER_TAG = {"m": "guy", "f": "girl"}
IDENTITY = {"from_guy", "from_girl", "to_guy", "to_girl", "guys", "girls", "same_year", "older", "younger"}


def identity_tags(w, speaker, me, group=None) -> set:
    """Who's talking to whom: a guy or a girl, to a guy or a girl, and whether the whole conversation (you two, or a group
    chat or team) is guys or girls. Lines that only fit one of those ("bro", "lock in boys") say so in `when`."""
    tags = set()
    if me is not None and me.gender in GENDER_TAG:
        tags.add("to_" + GENDER_TAG[me.gender])
    if speaker is not None and speaker.gender in GENDER_TAG:
        tags.add("from_" + GENDER_TAG[speaker.gender])
    people = [w.chars[x] for x in group if x in w.chars] if group else [c for c in (speaker, me) if c is not None]
    genders = {c.gender for c in people}
    if people and genders == {"m"}:
        tags.add("guys")
    elif people and genders == {"f"}:
        tags.add("girls")
    if speaker is not None and me is not None and speaker.role == me.role == "student" and speaker.grade and me.grade:
        tags.add("same_year" if speaker.grade == me.grade else "older" if speaker.grade > me.grade else "younger")
    return tags


def tags_for(sim, frm=None, phase=None, group=None) -> set:
    """What's true right now, for a line someone (frm) says or texts to you (or to a group: `group` is who's in it)."""
    from . import dialogue
    w = sim.w
    me = w.chars.get(w.meta.get("protagonist") or "")
    tags = {PHASE_TAG.get(phase or sim.current_phase(), "afternoon")}
    if not me:
        return tags
    if group:
        tags |= identity_tags(w, w.chars.get(frm) if frm else None, me, group)
    for r in ("school_day", "weekend", "summer"):
        try:
            if dialogue._requirement(sim, me, r):
                tags.add(r)
        except Exception:  # noqa: BLE001  a calendar edge case never blocks a line
            pass
    tags.add("college" if (me.grade or 0) >= 13 else "high_school")
    if me.mood >= 75:
        tags.add("you_happy")
    elif me.mood <= 25:
        tags.add("you_down")
    if (me.needs or {}).get("stress", 0) >= 65:
        tags.add("you_stressed")
    if not frm or frm == "me":
        return tags
    if str(frm).startswith("parent"):
        return tags | {"family", "parent"}
    c = w.chars.get(frm)
    if not c:
        return tags
    if not group:
        tags |= identity_tags(w, c, me)
    if c.role == "staff":
        tags.add("coach")
    if frm in sim.siblings(me.id):
        tags |= {"family", "sibling"}
    r = w.rels.get((frm, me.id))
    if r is not None:
        if r.familiarity < 25:
            tags.add("new")
        if r.affection >= 30:
            tags.add("friend")
        if r.affection >= 60:
            tags.add("close")
        if max(r.rivalry, getattr(w.rels.get((me.id, frm)), "rivalry", 0)) >= 40:
            tags.add("rival")
    if me.flags.get("partner") == frm:
        tags.add("partner")
    elif r is not None and r.attraction >= 50:
        tags.add("crush")
    if w.has_role(me.id, frm, "ex"):
        tags.add("ex")
    if any(frm in w.groups.get(g, {}).get("members", []) for g in me.memberships
           if w.groups.get(g, {}).get("skill") in sim.cat.sports["sports"]):
        tags.add("teammate")
    if c.mood >= 75:
        tags.add("happy")
    elif c.mood <= 25:
        tags.add("down")
    if (c.needs or {}).get("stress", 0) >= 65:
        tags.add("stressed")
    if (c.needs or {}).get("energy", 100) <= 25:
        tags.add("tired")
    if c.flags.get("injured_until", -1) >= w.day:
        tags.add("hurt")
    return tags


# ---------------------------------------------------------------------------------------- memory

def memory(sim) -> dict:
    return sim.w.meta.setdefault("lines", {})


def _remember(sim, key, h):
    m = memory(sim)
    used = m.setdefault(key, {})
    used[h] = sim.w.day
    if len(used) > 90:
        for k in sorted(used, key=used.get)[:len(used) - 90]:
            del used[k]


def choose(sim, key, items, salt, tags=frozenset(), avoid=None, text=lambda e: e["text"], when=lambda e: e["when"]):
    """The item to use: one that fits the moment, hasn't been used lately, and isn't what was just said."""
    if not items:
        return None
    fit = [e for e in items if set(when(e)) <= tags]
    if not fit:
        fit = [e for e in items if not when(e)] or list(items)
    used = memory(sim).get(key, {})
    day = sim.w.day
    rest = max(2, min(45, len(fit) * 2))   # days a line sits out after it's used

    def score(e):
        s = text(e)
        last = used.get(hid(s))
        ago = 10_000 if last is None else day - last
        fresh = ago >= rest
        said = bool(avoid) and s.lower().rstrip(".!") in avoid
        jitter = (_h(salt, hid(s)) % 1000) / 1000
        specific = any(t not in IDENTITY for t in when(e))  # who's talking only says whether a line fits, not that it's apt
        return (not said, fresh, jitter + (0.6 if specific else 0) if fresh else ago + jitter * 0.01)
    best = max(fit, key=score)
    _remember(sim, key, hid(text(best)))
    return best


def variant(sim, key, v, salt, tags=frozenset()):
    """A scene's text or a say line: one string, or a list of variants to rotate through."""
    if isinstance(v, list):
        return choose(sim, key, [{"text": s, "when": []} for s in v if isinstance(s, str)], salt, tags)["text"] if v else ""
    return v


# ---------------------------------------------------------------------------------------- texts and talk

def pick_text(sim, key, salt, frm=None, avoid=None, kw=None) -> str:
    """A text from a pool for someone to send you, fitted to the moment and not a repeat."""
    from . import dialogue
    kw = dict(kw or {})
    group = kw.pop("_group", None)  # who's in the group chat or on the team, when it isn't just you two
    pool = [entry(x) for x in dialogue.texts().get(key) or [key]]
    tags = tags_for(sim, frm, group=group)
    e = choose(sim, f"t:{key}", pool, salt, tags, avoid=avoid)
    out = fill(e["text"], kw)
    if key in DRESS and frm and frm != "me" and not str(frm).startswith("parent"):
        c = sim.w.chars.get(frm)
        if c and c.role != "staff":
            out = dress(sim, out, tags, salt)
    return out


def _mods(kind) -> dict:
    from . import dialogue
    return dialogue.mods().get(kind, {})


def _mod(sim, kind, tags, salt):
    bank = _mods(kind)
    # a key is one tag, several joined with + (all must hold: "close+guys"), or "any"
    opts = [(t, s) for t, lines in bank.items() if t == "any" or all(x in tags for x in t.split("+")) for s in lines]
    if not opts:
        return None
    pick = choose(sim, f"m:{kind}", [{"text": s, "when": [] if t == "any" else t.split("+")} for t, s in opts], salt, tags)
    return pick["text"]


def dress(sim, line, tags, salt) -> str:
    """Maybe an opener, maybe a closer: the same line, said the way this person would right now."""
    words = re.findall(r"[a-z']+", line.lower())
    r = _h(salt, "dress") % 100
    if r < 30 and words and words[0] not in OPEN_SKIP:
        o = _mod(sim, "open", tags, salt)
        if o and not any(wd in words[:3] for wd in re.findall(r"[a-z']+", o.lower())):
            line = f"{o} {line}"
    elif 30 <= r < 48 and not EMOJI.search(line[-3:]):
        cl = _mod(sim, "close", tags, salt)
        if cl and cl.lower() not in line.lower():
            line = f"{line.rstrip('.')} {cl}"
    return line


def speakable(line: str) -> str:
    """A text as you'd say it out loud: no emoji, no trailing lol, spelled out, capitalized."""
    s = EMOJI.sub("", line).strip()
    s = TRAILING.sub("", s).strip()
    for pat, rep in SPOKEN:
        s = re.sub(pat, rep, s, flags=re.I if pat in (r"\bi\b",) else 0)
    s = re.sub(r"\s+", " ", s).strip(" ,")
    return (s[:1].upper() + s[1:]) if s else s


def spoken(sim, e, speaker, salt, kw=None, tags=None) -> str:
    """The in-person version of a pool entry: their words in quotes, and who said it and how."""
    w = sim.w
    kw = dict(kw or {})
    c = w.chars.get(speaker)
    first = c.first if c else "They"
    tags = tags if tags is not None else tags_for(sim, speaker)
    if e.get("talk"):
        return fill(e["talk"], {**kw, "them_first": first, "says": "says"})
    s = speakable(fill(e["text"], kw))
    if not s:
        return ""
    q = s.endswith("?")
    attr = _mod(sim, "talk", tags, salt) or "{them_first} {says}"
    attr = attr.replace("{them_first}", first).replace("{says}", "asks" if q else "says")
    if s[-1] in ".,;:":
        s = s[:-1] + ","
    elif s[-1] not in "?!":
        s += ","
    return f"\"{s}\" {attr}."


def say_from_pool(sim, key, speaker, salt, kw=None) -> str:
    """Something someone says to your face, from a pool: its talk version if it has one, or the text said out loud."""
    from . import dialogue
    pool = [entry(x) for x in dialogue.texts().get(key) or []]
    if not pool:
        return ""
    tags = tags_for(sim, speaker)
    e = choose(sim, f"s:{key}", pool, salt, tags)
    return spoken(sim, e, speaker, salt, kw, tags)
