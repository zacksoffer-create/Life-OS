"""Texting that goes back and forth: type anything, or tap a suggestion, and they answer like themselves.

What you type is read for what you're doing (saying hi, asking something, joking, complimenting, flirting, making
plans, checking on them, apologizing, being dry or rude, saying bye) and how much effort it shows. It doesn't
understand every word the way a person would.

A conversation has energy. How much depends on how much they like you, how social they are, whether they're into
you, and how stressed they are. Every message uses a little; good ones give some back; dry or rude ones drain it.
When it runs out they wrap it up ("gtg, ttyl"), and texting again right away doesn't help.

Flirting runs on five things, and every flirt tells you which ones decided it:
  closeness  how well they know you and like you as a person
  interest   whether they're into you (the signals on their contact page tell you)
  moment     their mood, their stress, how the conversation's been going
  pace       one step at a time: talking, joking around, flirting, then asking out
  you        your confidence and charm, and putting a little effort in
"""
from __future__ import annotations

import re

from .history import Effects
from .rng import clamp

PEOPLE_ORDER = ("twin", "older_brother", "older_sister", "younger_brother", "younger_sister", "older_sibling", "younger_sibling",
                "brother", "sister", "sibling", "partner", "crush", "ex", "rival", "coach", "best_friend", "teammate", "friend",
                "classmate")  # most specific first: whose own lines get used
STAGES = ["Strangers", "Know each other", "Friendly", "Flirty", "Talking stage", "Dating"]
GUIDE = [
    {"t": "They have to know you a little", "d": "Flirting with someone who barely knows you is a gamble. Say hi, talk, hang out first."},
    {"t": "Watch the signals", "d": "Do they text you first, ask about you, laugh at your jokes, flirt back? Their contact page keeps track."},
    {"t": "One step at a time", "d": "Talking, then joking around, then a light flirt, then asking out. Skipping steps is where it gets awkward."},
    {"t": "Read the room", "d": "Stressed, in a bad mood, or the conversation's gone dry? Not now."},
    {"t": "If they go cold, back off", "d": "Short answers, laughing it off, leaving you on read: pushing harder makes it worse."},
    {"t": "Confidence helps, effort counts", "d": "Charm and a real message go a long way. They can't make someone into you who isn't."},
    {"t": "Ask out in person", "d": "Once they're flirting back, ask them out when you see them. Over text they'll tell you to say it to their face."},
]
TONE = {"vent": "😮‍💨", "news": "🎉", "thanks": "🙏", "gossip": "👀", "greet": "👋", "ask": "💬", "answer": "↩", "joke": "😂", "compliment": "✨", "flirt": "😏", "flirt_strong": "😏",
        "plans": "📅", "support": "🤝", "good_luck": "💪", "congrats": "🎉", "apology": "🙏", "love": "❤️", "bye": "👋"}
CAP = {"affection": 6.0, "familiarity": 5.0, "attraction": 8.0}  # most a day of texting one person can move things
_DATA = None


def D() -> dict:
    """The texting lines: the built-in ones plus any from dialogue packs."""
    from . import dialogue
    return dialogue.chat_lines()


# --- reading what you typed --------------------------------------------------------------------

FLIRT_EMOJI = ("😏", "😉", "😘", "🥰", "😍", "😳", "💕", "❤️", "♥", "💘", "😚", "🫣", "👀")
RX = [
    ("rude", r"\b(stfu|shut up|loser|idiot|stupid|ugly|hate you|annoying|f+u+c*k+ (off|you)|dumb(ass)?|weirdo|creep|nobody likes you)\b"),
    ("apology", r"\b(sorry|my bad|apologi[sz]e|i was wrong|forgive me|i messed up)\b"),
    ("ask_out", r"(go out with me|be my (gf|bf|girlfriend|boyfriend)|wanna go out|want to go out|go on a date|like a date|ask(ing)? you out)"),
    ("love", r"\b(love you|love u|ily|ilysm)\b"),
    ("bye", r"^(ok+ |okay |alright |anyway |well )?(gtg|g2g|gotta go|got to go|good ?night|gn|nighty?|bye+|ttyl|talk (to you )?(later|tomorrow|tmrw)|cya|see ya|later)\b"),
    ("vent", r"(\b(day|today|week|school|life|everything|practice)\b.{0,20}\b(sucked|sucks|was (so )?(awful|terrible|bad|rough|the worst)|is (so )?(awful|terrible|the worst))|i'?m (so |really |kinda |lowkey |honestly )?(stressed|sad|upset|exhausted|overwhelmed|done with|over it)|worst day|i hate (school|my life|this|everything)|can'?t do this anymore|feel(ing)? (so )?(bad|down|awful|terrible)|having a (bad|rough) (day|week))"),
    ("news", r"(\bi made (the|varsity|jv)|\bi got (in|into|an a|accepted|the part|my license|a job|asked)|guess what|\bwe won\b|\bi won\b|\bi passed\b|\bi aced\b|i'?m starting|i'?m (going|in) to|big news)"),
    ("plans", r"\b(wanna|want to|down to|u down|you down|hang ?out|hang|come over|get food|grab food|get pizza|movie|tonight\?|this weekend|after school|let'?s go|let'?s|chill (later|tomorrow|this))\b"),
    ("flirt", r"\b(cute|pretty|hot|handsome|beautiful|gorgeous|miss (you|u)|thinking (about|of) (you|u)|crush|kiss|babe|flirt|you look good|u look good|your smile|ur smile|your eyes|ur eyes|like you|like u|into you|into u)\b"),
    ("support", r"\b(you ok|u ok|you good\?|u good\?|are you okay|here for you|here if you|that sucks|feel better|hope you'?re ok|how are you holding up|wanna talk)\b"),
    ("gossip", r"(did you hear|guess who|apparently|i heard (that|about)|there'?s a rumor|everyone'?s saying|you won'?t believe what)"),
    ("thanks", r"\b(thanks|thank you|thx|ty|appreciate (it|you))\b"),
    ("compliment", r"\b(nice|great job|good job|congrats|congratulations|you killed it|killed it|amazing|awesome|so good|proud of you|smart|funny|talented|clutch|you'?re the best|ur the best)\b"),
    ("greet", r"^(hey+|hi+|hello|yo+|sup|wassup|what'?s up|whats good|heyo|howdy)\b"),
]
STRONG = r"\b(miss (you|u)|thinking (about|of) (you|u)|kiss|i like you|i like u|into you|into u|babe|love)\b"
DRY = r"^(k|kk|ok|okay|cool|sure|whatever|idk|fine|lol|ya|yeah|ye|yep|mhm|nm|nothing|ok lol|lol ok|same)[.!]*$"
JOKE = r"(\blol\b|\blmao\b|\bhaha+|\bhehe|😂|🤣|\bjk\b|💀|\blmfao\b)"
QUESTION = r"^((what|how|why|when|where|who|wyd|hbu|wbu)\b|(did|do|are|r|is|can|could|would|will|have|were|was) (you|u|we|i|they|he|she|it)\b)"
TOPICS = {"game": r"\b(game|practice|coach|team|match|season|play(ed|ing)?)\b", "school": r"\b(test|quiz|homework|hw|class|teacher|exam|grade|essay)\b",
          "music": r"\b(song|music|album|concert|playlist|listen)\b", "weekend": r"\b(weekend|saturday|sunday|friday|party|dance)\b",
          "food": r"\b(food|pizza|hungry|eat|dinner|lunch)\b"}
STYLE_RX = [
    ("cheesy", r"(are you a |did it hurt|you must be tired|fell from heaven|\bangel\b|parking ticket|got a map|lost in your eyes|stole my heart|cute-?cumber|is your name)"),
    ("bold", r"\b(i like you|i like u|go out with me|be my|just us|take you out|kiss|date)\b"),
    ("sweet", r"\b(made my day|like talking to you|easy to talk to|glad (i met|we|you)|means a lot|thinking (about|of) (you|u)|miss (you|u)|you'?re (so )?(sweet|kind|amazing|beautiful|pretty))\b"),
    ("tease", r"\b(annoying|nerd|loser|dork|weirdo|you wish|bet you can'?t|whatever you say|so dramatic|try me|admit it|you'?re lucky)\b"),
]
PLAYFUL = r"(😏|😂|🤣|😜|😝|\blol\b|\blmao\b|\bhaha|\bjk\b|💀)"
MEAN = r"\b(hate you|f+u+c*k|nobody likes you|ugly|kill yourself|kys)\b"
STYLES = ("tease", "sweet", "bold", "funny", "cheesy")
STYLE_WORD = {"tease": ("Teasing", "the teasing"), "sweet": ("Sweet stuff", "sweet stuff"), "bold": ("Being direct", "you being direct"),
              "funny": ("Making them laugh", "the jokes"), "cheesy": ("Cheesy lines", "cheesy lines")}
STYLE_TONE = {"tease": "😏", "sweet": "🥰", "bold": "🔥", "funny": "😂", "cheesy": "🧀", "playful": "😏"}
BANTER_TONE = {"cool": "😌", "letdown": "🙂"}
SPARK = {"landed": 1.0, "playful": 0.5, "awkward": -1.0, "shut": -2.0}  # how a flirt beat moves things along
YES = r"^(yes+|yeah+|yea|yep|sure|ok(ay)?|down|i'?m down|bet|of course|definitely|deal|sounds good|let'?s do it)\b"
NO = r"^(no+|nah|nope|can'?t|i can'?t|busy|not today|maybe another|sorry,? (i )?can'?t)\b"


def classify(text: str) -> dict:
    """What a message you typed is doing, how flirty it is, and how much effort it shows."""
    s = (text or "").strip()
    low = s.lower()
    words = re.findall(r"[a-z0-9']+", low)
    f = {"text": s, "words": len(words), "question": "?" in s or bool(re.match(QUESTION, low)),
         "effort": round(clamp(len(words) / 12, 0, 1), 2), "topic": next((k for k, rx in TOPICS.items() if re.search(rx, low)), None),
         "flirt": 0, "joke": bool(re.search(JOKE, low))}
    emoji = any(e in s for e in FLIRT_EMOJI)
    intent = None
    for name, rx in RX:
        if re.search(rx, low):
            if name == "bye" and len(words) > 7:
                continue  # "ok gtg" closes; a long message that happens to say "later" doesn't
            intent = name
            break
    if intent in ("flirt", "ask_out", "love") or emoji:
        f["flirt"] = 2 if (intent in ("ask_out", "love") or re.search(STRONG, low)) else 1
        if intent is None or intent in ("greet", "compliment", "chat"):
            intent = "flirt"
    if intent is None:
        if re.match(DRY, low) or not words:
            intent = "dry"
        elif f["question"]:
            intent = "ask"
        elif f["joke"]:
            intent = "joke"
        else:
            intent = "chat"
    if intent == "rude" and re.search(PLAYFUL, s) and not re.search(MEAN, low):
        intent = "flirt" if emoji else "joke"  # "you're such a loser 😂" is teasing, not rude
        f["flirt"] = 1 if emoji else 0
    style = next((name for name, rx in STYLE_RX if re.search(rx, low)), None)
    if intent in ("chat", "greet") and style == "sweet":
        intent = "compliment"  # "talking to you made my day" is a sweet thing to say
    if intent == "flirt":
        style = style or ("funny" if f["joke"] else "playful")
    elif intent == "joke":
        style = "tease" if style == "tease" else "funny"
    elif intent == "compliment":
        style = "sweet"
    elif intent not in ("ask_out", "love"):
        style = None
    f["intent"], f["style"] = intent, style
    return f


def tastes(o) -> dict:
    """What works on this person: what you set in the editor, else their personality decides it. +1 they love it,
    -1 they're not into it."""
    base = personality_tastes(o)
    mine = (o.flags or {}).get("tastes") or {}
    return {k: int(mine[k]) if mine.get(k) in (-1, 0, 1) else v for k, v in base.items()}


def personality_tastes(o) -> dict:
    t = o.traits
    raw = {"tease": (t["competitiveness"] + t["impulsivity"]) / 2 - t["volatility"] * 0.3 + 15,
           "sweet": (t["empathy"] + t["loyalty"]) / 2,
           "bold": (t["confidence"] + t["impulsivity"]) / 2,
           "funny": (t["sociability"] + t["curiosity"]) / 2,
           "cheesy": (t["sociability"] + t["impulsivity"]) / 2 - 18}
    order = sorted(raw, key=lambda k: (-raw[k], k))
    out = {k: 0 for k in raw}
    out[order[0]] = 1
    if raw[order[1]] >= raw[order[0]] - 6:
        out[order[1]] = 1
    out[order[-1]] = -1
    out[order[-2]] = -1 if out[order[-2]] == 0 else out[order[-2]]
    return out


def _learn(sim, cid, style):
    """You tried a style on them: now you know how it goes over."""
    from .messages import phone
    if style in STYLES:
        phone(sim.w).setdefault("tastes", {}).setdefault(cid, {})[style] = tastes(sim.w.chars[cid])[style]


def tastes_view(sim, cid) -> list:
    from .messages import phone
    known = phone(sim.w).get("tastes", {}).get(cid, {})
    return [{"style": k, "label": STYLE_WORD[k][0], "known": k in known, "taste": known.get(k)} for k in STYLES]


# --- how things stand between you ---------------------------------------------------------------

def _me(sim):
    from .messages import prot
    return prot(sim.w)


def _thread(sim, cid):
    from .messages import dm
    return dm(sim, cid)


def _landed_flirts(sim, cid, days=30) -> int:
    w = sim.w
    me = _me(sim)
    n = sum(1 for m in _thread(sim, cid)["msgs"] if m["from"] == cid and m.get("kind") == "chat_flirt_landed" and w.day - m["day"] <= days)
    for eid in w.history.by_char.get(me.id, [])[-400:]:
        e = w.history.events.get(eid)
        if e and e["type"] == "interact.flirt" and cid in e["actors"] + e["targets"] and e.get("outcome") in ("good", "great") \
                and w.day - e["day"] <= days:
            n += 1
    return n


def stage(sim, cid) -> int:
    """Where you two are: strangers, know each other, friendly, flirty, talking stage, dating."""
    w = sim.w
    me = _me(sim)
    if me.flags.get("partner") == cid:
        return 5
    r = w.rels.get((cid, me.id))
    if not r or r.familiarity < 15:
        return 0
    if cid in sim.siblings(me.id) or w.chars[cid].role == "staff":
        return 2 if r.affection >= 15 else 1
    flirts = _landed_flirts(sim, cid)
    if flirts >= 2 and r.attraction >= 50:
        return 4
    if flirts >= 1 and r.attraction >= 30:
        return 3
    if r.affection >= 15 and r.familiarity >= 30:
        return 2
    return 1


def _open_to_you(sim, cid):
    """None if they could be into you; otherwise the reason they can't."""
    from .social import orientation_ok
    w = sim.w
    me = _me(sim)
    o = w.chars[cid]
    if cid in sim.siblings(me.id):
        return "family"
    if o.role == "staff":
        return "staff"
    if o.flags.get("partner") and o.flags["partner"] != me.id:
        return "taken"
    if not orientation_ok(o, me):
        return "not_into"
    return None


def read(sim, cid) -> dict:
    """Your read on whether they're into you. Once you know someone a little, you can tell."""
    w = sim.w
    me = _me(sim)
    r = w.rels.get((cid, me.id))
    why = _open_to_you(sim, cid)
    if why == "family":
        return {"label": "Family", "tone": "none", "level": -1}
    if why == "staff":
        return {"label": "A teacher or coach", "tone": "none", "level": -1}
    if me.flags.get("partner") == cid:
        return {"label": "You're together", "tone": "good", "level": 4}
    if why == "taken":
        return {"label": f"They're dating {w.chars[w.chars[cid].flags['partner']].first}", "tone": "bad", "level": 0}
    if not r or r.familiarity < 20:
        return {"label": "Too early to tell", "tone": "unknown", "level": -1}
    if why == "not_into":
        return {"label": "Just friends vibes", "tone": "bad", "level": 0}
    a = r.attraction
    if a >= 60:
        return {"label": "Definitely into you", "tone": "good", "level": 4}
    if a >= 40:
        return {"label": "Seems into you", "tone": "good", "level": 3}
    if a >= 22:
        return {"label": "Maybe. Some signs", "tone": "neutral", "level": 2}
    return {"label": "Just friends vibes", "tone": "bad", "level": 0 if a < 10 else 1}


def signals(sim, cid, days=21) -> list:
    """What you've noticed lately: the things that tell you how they feel."""
    w = sim.w
    me = _me(sim)
    t = _thread(sim, cid)
    recent = [m for m in t["msgs"] if w.day - m["day"] <= days]
    out = []
    starts = 0
    seen_days = set()
    for m in recent:
        if m["day"] in seen_days or m.get("kind") == "note":
            continue
        seen_days.add(m["day"])
        if m["from"] == cid:
            starts += 1
    count = lambda k: sum(1 for m in recent if m["from"] == cid and m.get("kind") == k)  # noqa: E731
    if starts:
        out.append({"text": f"Texted you first{f' ({starts}×)' if starts > 1 else ''}", "good": True})
    if count("chat_double"):
        out.append({"text": "Double-texted you", "good": True})
    if count("chat_follow"):
        out.append({"text": "Remembered what you told them", "good": True})
    back = count("chat_flirt_landed")
    if back:
        out.append({"text": "Flirted back" + (f" ({back}×)" if back > 1 else ""), "good": True})
    if count("chat_ask"):
        out.append({"text": "Asked about you", "good": True})
    if count("chat_laugh"):
        out.append({"text": "Laughed at your jokes", "good": True})
    if any(w.day - d <= days for d in t.get("long_days", [])):
        out.append({"text": "Kept the conversation going", "good": True})
    if count("chat_flirt_playful"):
        out.append({"text": "Laughed off a flirt (but didn't mind)", "good": None})
    if count("chat_dry") + count("chat_close_cold"):
        out.append({"text": "Short, dry answers", "good": False})
    if count("chat_flirt_awkward"):
        out.append({"text": "A flirt got awkward", "good": False})
    if count("chat_flirt_shut"):
        out.append({"text": "Shut a flirt down", "good": False})
    unread = sum(1 for m in recent if m["from"] == "me" and m.get("read") and m.get("kind") in ("chat", "first"))
    if unread:
        out.append({"text": "Left you on read", "good": False})
    for eid in w.history.by_char.get(me.id, [])[-300:]:
        e = w.history.events.get(eid)
        if not e or w.day - e["day"] > days or cid not in e["actors"] + e["targets"]:
            continue
        k, o = e["type"], e.get("outcome")
        if k == "interact.flirt" and o in ("good", "great"):
            out.append({"text": "Flirting went well in person", "good": True})
        elif k == "interact.flirt" and o in ("awkward", "bad"):
            out.append({"text": "Flirting got awkward in person", "good": False})
        elif k in ("interact.hang_out", "interact.date") and o == "great":
            out.append({"text": "Had a great time with you", "good": True})
        elif k in ("interact.hang_out", "interact.date") and o in ("declined", "busy"):
            out.append({"text": "Turned down plans", "good": False})
    if me.flags.get("partner") == cid:
        mine = w.rels.get((me.id, cid))
        gap = w.day - mine.last_day if mine and mine.last_day >= 0 else 0
        if gap >= 4:
            out.insert(0, {"text": f"Feeling distant: {gap} days since you talked", "good": False})
    seen, uniq = set(), []
    for s in out:
        if s["text"] not in seen:
            seen.add(s["text"])
            uniq.append(s)
    return uniq[:8]


def tip(sim, cid, st=None, rd=None) -> str:
    st = stage(sim, cid) if st is None else st
    rd = read(sim, cid) if rd is None else rd
    why = _open_to_you(sim, cid)
    if why in ("family", "staff"):
        return ""
    if why == "taken":
        return "They're with someone. Flirting now mostly makes things weird."
    if st == 5:
        mine = sim.w.rels.get((_me(sim).id, cid))
        gap = sim.w.day - mine.last_day if mine and mine.last_day >= 0 else 0
        if gap >= 4:
            return f"It's been {gap} days. Text them or make plans before they start to wonder."
        return "You're together. Text, hang out, show up for them."
    if rd["level"] == -1 or st == 0:
        return "Get to know them first: say hi, ask about their day, hang out. Flirting with someone who barely knows you is a gamble."
    if rd["level"] <= 1:
        return "They see you as a friend right now. Hang out and make them laugh; flirting now will probably be awkward."
    if st <= 2:
        return "There are signs. Try a light flirt and see if they flirt back. Everyone's different: see what style works on them."
    if st == 3:
        return "They flirt back. Keep it going, then ask them to hang out, just you two."
    return "This is going somewhere. Ask them out in person."


def vibe(sim, cid) -> dict:
    st = stage(sim, cid)
    rd = read(sim, cid)
    return {"stage": st, "stages": STAGES, "read": rd["label"], "tone": rd["tone"], "level": rd["level"],
            "signals": signals(sim, cid), "tip": tip(sim, cid, st, rd), "tastes": tastes_view(sim, cid),
            "romance": vibe_relevant(sim, cid)}


# --- flirting, and why it worked -----------------------------------------------------------------

WHY = {
    "closeness": ("you two are close", "you barely know each other yet", "Talk more first."),
    "interest": ("they were already into you", "they don't seem into you like that (yet)", "Watch for signals before you flirt."),
    "moment": ("they were in a good mood", "bad timing", "Try another time."),
    "pace": ("you'd built up to it", "too much, too fast", "Joke around first, then flirt."),
    "you": ("you were smooth about it", "it came off a little forced", "Put a little more into it."),
}


def _band(sim, cid) -> str:
    """Early (still getting to know each other) or close (flirty already): which lines fit."""
    return "close" if stage(sim, cid) >= 3 else "early"


def _banter_mode(sim, cid, c, last):
    """Mid-flirt, what's next: {"mode": "back", "after": "landed"|"playful"} once they answered a flirt of yours,
    {"mode": "in"} when they started it. None otherwise."""
    if last is None or last["from"] != cid:
        return None
    if last.get("kind") == "chat_flirt_in":
        return {"mode": "in"}
    bt = (c or {}).get("banter") or {}
    if bt.get("open") and bt.get("after") in ("landed", "playful"):
        return {"mode": "back", "after": bt["after"]}
    return None


def _banter_suggestions(sim, cid, bm, salt, avoid) -> list:
    """Two styles (one you know they love, or one you haven't tried on them) and playing it cool; when they started it,
    letting them down easy too."""
    from .messages import _fill, _h, phone
    w = sim.w
    me = _me(sim)
    o = w.chars[cid]
    known = phone(w).get("tastes", {}).get(cid, {})
    loved = [k for k in STYLES if known.get(k) == 1]
    rest = [k for k in ("tease", "sweet", "bold", "funny", "cheesy") if k not in loved and known.get(k) != -1]
    rot = _h(salt, "bt") % max(1, len(rest))
    order = loved + rest[rot:] + rest[:rot]
    picks = order[:2] if len(order) >= 2 else (order + ["sweet", "tease"])[:2]
    if bm["mode"] == "back" and bm["after"] == "landed" and stage(sim, cid) >= 3 and "bold" not in picks and known.get("bold") != -1:
        picks[1] = "bold"  # it's going well: the direct option's there
    moves = picks + ["cool"] + (["letdown"] if bm["mode"] == "in" and me.flags.get("partner") != cid else [])
    out = []
    for mv in moves:
        path = ("banter", "in_back", mv) if bm["mode"] == "in" else ("banter", "back", bm["after"], mv)
        pool = _pool(sim, cid, *path)
        if not pool:
            continue
        out.append({"text": _fill(_pick(sim, pool, f"{salt}:{mv}", avoid), {"them": o.first, "me": me.first}),
                    "intent": "letdown" if mv == "letdown" else "flirt", "tone": STYLE_TONE.get(mv) or BANTER_TONE.get(mv, "😏"),
                    "style": mv, "banter": mv})
    return out


def _banter_step(sim, cid, c, out, cool, them_first, prev, fx, salt, avoid) -> str | None:
    """One beat of a flirt. A few good ones in a row and it goes somewhere; an awkward one and it can fizzle. Returns
    what to tell you when it went somewhere (or fizzled)."""
    from .messages import _h
    o = sim.w.chars[cid]
    bt = dict(prev) if prev else {"beat": 0, "spark": 0.5 if them_first else 0.0}
    bt["beat"] += 1
    bt["spark"] += SPARK[out] * (0.5 if cool else 1.0)
    bt["open"] = False
    note = None
    if out in ("awkward", "shut"):
        if prev and out == "awkward" and _h(salt, "fz") % 2 == 0:
            _say(sim, cid, None, None, salt + ":fz", "chat_flirt_awkward", avoid, pool=_pool(sim, cid, "banter", "fizzle"))
            c["closed"] = True
            note = f"It fizzled. {o.first} needed a breather; one step at a time."
    elif (bt["beat"] >= 2 and bt["spark"] >= 2.0) or (bt["beat"] >= 3 and bt["spark"] >= 1.5):
        note = _payoff(sim, cid, c, fx, salt, avoid)
    elif bt["beat"] < 3:
        bt["open"] = True
        bt["after"] = "landed" if out == "landed" else "playful"
    c["banter"] = bt
    return note


def _payoff(sim, cid, c, fx, salt, avoid) -> str:
    """A flirt that went somewhere: they say so, and it leads somewhere (bed, plans, or ask me out in person)."""
    w = sim.w
    me = _me(sim)
    o = w.chars[cid]
    rt = w.rels.get((cid, me.id))
    partner = me.flags.get("partner") == cid
    ctl = w.meta.setdefault("control", {})
    q = ctl.get("queued")
    if sim.current_phase() == "night":
        kind = "goodnight"
    elif not partner and stage(sim, cid) >= 3 and rt and rt.attraction >= 50 and not o.flags.get("partner") \
            and (not q or q.get("action") == "ask_out"):
        kind = "ask"
    elif not q and o.status == "active" and o.location == me.location:
        kind = "plans"
    else:
        kind = "blush"
    _say(sim, cid, None, None, salt + ":po", "chat_flirt_landed", avoid, pool=_pool(sim, cid, "banter", "payoff", kind))
    _gain(sim, cid, fx, cid, "attraction", 3.0, "a flirt that went somewhere")
    _gain(sim, cid, fx, cid, "affection", 1.0, "a flirt that went somewhere")
    fx.mood(me.id, 3, f"texting {o.first}")
    fx.need(me.id, "fun", 3, "texting")
    if kind == "goodnight":
        c["closed"] = True
        return f"That went somewhere. {o.first} went to bed smiling."
    if kind == "ask":
        o.flags["told_to_ask"] = {"by": me.id, "day": w.day}
        r_me = w.ensure_rel(me.id, cid, w.day)
        need = w.rules["rel.crush_threshold"] + 2 - r_me.attraction
        if need > 0:
            fx.rel(me.id, cid, "attraction", need, "you're into them")
        ctl["queued"] = {"action": "ask_out", "target": cid, "day": w.day, "expires": w.day + 4}
        return f"That went somewhere: {o.first} wants you to ask them out in person. Plan made: you'll ask the next time you see them."
    if kind == "plans":
        ctl["queued"] = {"action": "hang_out", "target": cid, "agreed": True, "day": w.day}
        return f"That went somewhere: plans made. You'll hang out with {o.first} at your next free time."
    return f"That went somewhere: {o.first} is into this."


def flirt_in_line(sim, cid) -> str:
    """Them flirting first: a line that fits where you two are."""
    from .messages import _fill, _h
    w = sim.w
    pool = _pool(sim, cid, "banter", "in", _band(sim, cid))
    return _fill(pool[_h(w.day, cid, "in") % len(pool)], {"me": _me(sim).first}) if pool else "hey 😏"


def flirt_check(sim, cid, strength: int, effort: float, momentum: float, rng, style: str | None = None) -> dict:
    """Did the flirt land? Five readable parts, the two that mattered most become the reason."""
    w = sim.w
    me = _me(sim)
    o = w.chars[cid]
    rt = w.ensure_rel(cid, me.id, w.day)
    block = _open_to_you(sim, cid)
    if block in ("taken", "not_into", "staff"):
        why = {"taken": "they're dating someone", "not_into": "they're not into you that way", "staff": "that's a teacher or coach. Hard no"}[block]
        return {"outcome": "shut", "why": f"Shut down: {why}.", "terms": []}
    closeness = 0.6 * ((rt.familiarity - 35) / 65 * 0.5 + rt.affection / 100 * 0.6)
    interest = 0.9 * (rt.attraction - 30) / 40
    stress = max(0.0, o.needs.get("stress", 40) - 60) / 40
    moment = 0.4 * (o.mood - 55) / 45 - 0.4 * stress + momentum + (0.1 if sim.current_phase() in ("evening", "night") else 0.0)
    need = 2 if strength <= 1 else 3
    st = stage(sim, cid)
    pace = 0.25 if st >= need else -0.35 * (need - st)
    you = 0.4 * (me.aptitudes["charisma"] + me.traits["confidence"] - 100) / 100 + 0.15 * effort
    terms = [("closeness", closeness), ("interest", interest), ("moment", moment), ("pace", pace), ("you", you)]
    if style in STYLES:
        terms.append(("style", 0.32 * tastes(o)[style]))  # everyone's different
    score = sum(v for _, v in terms) + rng.gauss(0, 0.15)
    if score >= 0.9:
        out = "landed"
    elif score >= 0.35:
        out = "playful"
    elif score >= -0.6 or rt.attraction >= 15:
        out = "awkward"
    else:
        out = "shut"
    pos = sorted([t for t in terms if t[1] > 0.12], key=lambda t: -t[1])
    neg = sorted([t for t in terms if t[1] < -0.05], key=lambda t: t[1])

    def word(k, good):
        if k == "style":
            return f"they love {STYLE_WORD[style][1]}" if good else f"they're not into {STYLE_WORD[style][1]}"
        if k == "pace" and not good and st <= 1:
            return "they barely know you yet"
        if k == "moment" and not good:
            return "they're stressed out" if stress > 0.3 else "they're in a bad mood" if o.mood < 40 else "the conversation had gone dry" if momentum < 0 else "bad timing"
        return WHY[k][0 if good else 1]
    sv = dict(terms).get("style", 0)
    if out == "landed":
        why = "Landed: " + " and ".join(word(k, True) for k, _ in pos[:2]) + "." if pos else "Landed."
        if sv < 0:
            why += f" (They're not big on {STYLE_WORD[style][1]}, though.)"
    elif out == "playful":
        why = "They liked it" + (f" ({word(pos[0][0], True)})" if pos else "") + (f", but {word(neg[0][0], False)}." if neg else ".")
    else:
        lead = "Awkward" if out == "awkward" else "Shut down"
        why = f"{lead}: " + " and ".join(word(k, False) for k, _ in neg[:2]) + "." if neg else f"{lead}."
        if sv > 0 and not any(k == "style" for k, _ in neg):
            why += f" They do love {STYLE_WORD[style][1]}, so it's not the style."
        if neg:
            k0 = neg[0][0]
            why += " " + ("Talk and hang out first." if k0 in ("pace", "closeness") and st <= 1 else "Try a different style with them." if k0 == "style"
                          else WHY[k0][2])
    return {"outcome": out, "why": why[0].upper() + why[1:], "terms": [[k, round(v, 2)] for k, v in terms], "score": round(score, 2)}


def why_interact(terms, me_first: bool) -> str | None:
    """In person: the parts of how an interaction went, in words (from social.interact's terms)."""
    names = [("compatibility", "you two click", "you don't have much in common"), ("charm", "you were charming", "you weren't at your smoothest"),
             ("their mood", "they were in a good mood", "they were in a bad mood"), ("feelings", "they already like you", "they don't really like you"),
             ("their stress", None, "they were stressed"), ("your mood", "you were in a good mood", "you were in a bad mood"),
             ("luck", "a little luck", "bad luck"), ("chemistry", "there's chemistry", "no real chemistry")]
    vals = [t[1] for t in terms[1:]]
    if not me_first:
        return None
    parts = [(names[i], v) for i, v in enumerate(vals) if i < len(names)]
    pos = sorted([(n, v) for n, v in parts if v > 0.04 and n[1]], key=lambda x: -x[1])
    neg = sorted([(n, v) for n, v in parts if v < -0.04 and n[2]], key=lambda x: x[1])
    good = sum(vals) >= 0.15
    lead = [n[1] for n, _ in pos[:2]] if good else [n[2] for n, _ in neg[:2]]
    other = [n[2] for n, _ in neg[:1]] if good else [n[1] for n, _ in pos[:1]]
    if not lead and not other:
        return None
    if not lead:
        lead, other = other, []
    s = " and ".join(lead)
    if other:
        s += (", despite " if good else ", even though ") + ("some " + other[0] if other[0] == "bad luck" and good else other[0])
    return "Why: " + s + "."


def why_ask_out(terms, yes: bool) -> str:
    """In person: why they said yes or no to going out."""
    d = {t[0]: t[1] for t in terms}
    att = next((v for k, v in d.items() if "attraction" in k), 0)
    aff = next((v for k, v in d.items() if "affection" in k), 0)
    taken = next((v for k, v in d.items() if k == "already taken"), 0)
    other = next((v for k, v in d.items() if k == "likes someone else"), 0)
    if yes and d.get("they told you to ask them in person"):
        return "Why: they told you to ask them in person, and they meant it."
    if yes:
        bits = ["they were into you"] if att > -1 else []
        if aff > 0.3:
            bits.append("they really like you")
        return "Why: " + (" and ".join(bits) if bits else "you took the shot at the right time") + "."
    if taken < 0:
        return "Why: they're with someone."
    if att <= -7:
        return "Why: they're not into you that way."
    bits = []
    if att < -1:
        bits.append("they're not into you like that yet")
    if other < 0:
        bits.append("they like someone else")
    if aff < 0:
        bits.append("they don't know you that well")
    return "Why: " + (" and ".join(bits[:2]) if bits else "just not the right time") + ". Flirt first, and wait for them to flirt back."


# --- the conversation -----------------------------------------------------------------------------

def _convo(sim, cid) -> dict:
    """Today's conversation with them (one per part of the day)."""
    w = sim.w
    t = _thread(sim, cid)
    c = t.get("convo")
    ph = sim.current_phase()
    if not c or c.get("day") != w.day or c.get("phase") != ph:
        earlier = c.get("today", 0) + 1 if c and c.get("day") == w.day else 0
        c = {"day": w.day, "phase": ph, "energy": None, "turns": 0, "momentum": 0.0, "closed": False, "double": 0, "today": earlier}
        t["convo"] = c
    return c


def _energy(sim, cid, c) -> float:
    w = sim.w
    me = _me(sim)
    o = w.chars[cid]
    r = w.ensure_rel(cid, me.id, w.day)
    e = 2 + r.affection / 25 + o.traits["sociability"] / 50 + max(0.0, r.attraction - 30) / 20 - max(0.0, o.needs.get("stress", 40) - 65) / 15
    if me.flags.get("partner") == cid:
        e += 2
    return clamp(e - c.get("today", 0) * 1.2, 1, 9)


def _gain(sim, cid, fx, who, what, amount, why):
    """Relationship change from texting, capped per person per day (spamming doesn't farm it)."""
    w = sim.w
    from .messages import phone
    me = _me(sim)
    day = phone(w).setdefault("chat_gain", {}).setdefault(cid, {"day": w.day})
    if day.get("day") != w.day:
        day.clear()
        day["day"] = w.day
    if amount > 0 and what in CAP:
        room = CAP[what] - day.get(what, 0)
        amount = max(0.0, min(amount, room))
        day[what] = day.get(what, 0) + amount
    if amount:
        fx.rel(who, me.id if who == cid else cid, what, amount, why)


def _pick(sim, pool: list, salt: str, avoid: set) -> str:
    from .messages import _h
    if not pool:
        return ""
    i0 = _h(salt) % len(pool)
    for k in range(len(pool)):
        s = pool[(i0 + k) % len(pool)]
        if s.lower().rstrip(".!") not in avoid:
            return s
    return pool[i0]


def kinds_of(sim, cid) -> list:
    """What kinds of person they are to you (older sibling, crush, coach...), most specific first."""
    from . import dialogue
    me = _me(sim)
    if not me:
        return []
    cache = sim.__dict__.setdefault("_kinds_cache", {})
    key = (sim.w.day, sim.w.phase, cid)
    if key not in cache:
        cache.clear()
        cache[key] = [k for k in PEOPLE_ORDER if cid in dialogue.candidates(sim, me, k)]
    return cache[key]


def _get(d, path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _pool(sim, cid, *path) -> list:
    """Lines for this spot: theirs (from what kind of person they are to you) most of the time, everyone's otherwise."""
    from .messages import _h
    from . import dialogue
    base = _get(D(), path) or []
    own = []
    kinds = None
    for pack, people in dialogue.chat_people():
        kinds = kinds if kinds is not None else kinds_of(sim, cid)
        for k in kinds:
            if k not in people:
                continue
            if k in dialogue.CASTABLE:  # that storyline is about one person: theirs only
                me = _me(sim)
                if dialogue.pick_cast(sim, me, pack, k, dialogue.candidates(sim, me, k)) != cid:
                    continue
            own += _get(people[k], path) or []
    if own and (not base or _h(sim.w.day, cid, *path, len(_thread(sim, cid)["msgs"])) % 10 < 7):
        return _fit(sim, cid, own)
    return _fit(sim, cid, base or own)


def _fit(sim, cid, pool) -> list:
    """The lines that fit who's talking and the moment (a line's `when`), as text. "bro we're already hanging" is
    between guys; a line without `when` fits anyone."""
    from . import lines
    if not any(isinstance(x, dict) and "q" not in x for x in pool):
        return list(pool)  # plain lines, or questions ({"q": ..., "a": ...}) that their caller reads as they are
    from .messages import _h
    tags = lines.tags_for(sim, cid)
    pairs = [(x, x if isinstance(x, dict) and "q" in x else lines.entry(x)["text"], list((x.get("when") or []) if isinstance(x, dict) else []))
             for x in pool]
    fit = [(out, wh) for _, out, wh in pairs if set(wh) <= tags]
    apt = [out for out, wh in fit if any(t not in lines.IDENTITY for t in wh)]  # about this moment ("hurt")
    if apt and _h(sim.w.day, cid, len(pool)) % 4:
        return apt
    return [out for out, _ in fit] or [out for _, out, wh in pairs if not wh] or [out for _, out, _ in pairs]


def _keen(sim, cid) -> bool:
    """Someone into you (or very close to you) answers fast."""
    w = sim.w
    me = _me(sim)
    r = w.rels.get((cid, me.id))
    return bool(r and (r.attraction >= 45 or r.affection >= 70 or me.flags.get("partner") == cid))


def _say(sim, cid, key, outcome, salt, kind, avoid, pool=None):
    from .messages import post, _fill
    pool = pool if pool is not None else _pool(sim, cid, "reply", key, outcome)
    me = _me(sim)
    return post(sim, f"dm:{cid}", cid, _fill(_pick(sim, pool, salt, avoid), {"me": me.first}), kind=kind, unread=False,
                ctx={"fast": True} if _keen(sim, cid) else None)


def _note(sim, cid, text):
    from .messages import post
    return post(sim, f"dm:{cid}", "note", text, kind="note", unread=False)


def _pending(sim, cid):
    """Their last message, if it's still waiting on an answer from you."""
    from .messages import _reply_open
    t = _thread(sim, cid)
    for m in reversed(t["msgs"]):
        if m["from"] == "me":
            return None
        if m.get("kind") == "note":
            continue
        return m if _reply_open(sim, m) else None
    return None


def send(sim, cid, text: str | None = None, suggestion: int | None = None) -> dict:
    """You send a text: typed, or one of the suggestions. They answer (or don't), and things move a little."""
    from .messages import _avoid, _h, phone, post, reply, sender_name
    w = sim.w
    me = _me(sim)
    o = w.chars.get(cid)
    if not me or not o:
        raise ValueError("unknown person")
    if cid not in phone(w)["contacts"] and cid not in sim.siblings(me.id):
        raise ValueError(f"You don't have {o.first}'s number yet.")
    if suggestion is not None:
        sug = suggestions(sim, cid)
        if not 0 <= suggestion < len(sug):
            raise ValueError("no such suggestion")
        text, forced = sug[suggestion]["text"], sug[suggestion]["intent"]
        sug_style, sug_yn = sug[suggestion].get("style"), sug[suggestion].get("yn")
    else:
        forced = sug_style = sug_yn = None
    cool = sug_style == "cool"  # playing it cool: a flirt that doesn't push
    text = (text or "").strip()[:240]
    if not text:
        raise ValueError("say something")
    f = classify(text)
    intent = forced or f["intent"]
    if forced in ("flirt", "flirt_strong"):
        f["flirt"] = 2 if forced == "flirt_strong" else max(1, f["flirt"])
        intent = "flirt"
    if forced in ("good_luck", "congrats"):
        intent = "compliment"
    if forced == "answer":
        intent = "chat"
    if forced == "ask_out":
        intent = "ask_out"
    if forced == "letdown":
        intent = "letdown"
    style = sug_style or f.get("style")
    tid = f"dm:{cid}"
    # they asked you a yes-or-no question: a yes or a no is an answer to it
    last_q = next((m for m in reversed(_thread(sim, cid)["msgs"]) if m.get("kind") != "note"), None)
    yn = sug_yn
    if yn is None and last_q is not None and last_q["from"] == cid and (last_q.get("ctx") or {}).get("a") == "yesno":
        yn = "yes" if re.match(YES, text.lower()) else "no" if re.match(NO, text.lower()) else None
    if yn and intent in ("chat", "dry", "ask", "greet"):
        intent = "answered"
    # their last text was asking you something with set answers (an invite, a moment): a typed yes or no counts
    pend = _pending(sim, cid)
    if pend is not None:
        low = text.lower()
        linked = [i for i, r in enumerate(pend["replies"]) if r["fx"].startswith(("invite:", "moment:"))]
        if linked:
            yes_i = next((i for i in linked if pend["replies"][i]["fx"].endswith(":yes") or pend["replies"][i]["fx"].endswith(":0")), None)
            no_i = next((i for i in linked if i != yes_i), None)
            pick_i = yes_i if re.match(YES, low) else no_i if re.match(NO, low) else None
            if pick_i is not None:
                pend["replies"][pick_i] = dict(pend["replies"][pick_i], label=text)
                return reply(sim, tid, pend["id"], pick_i)
        else:
            pend["chosen"] = -2  # you answered in your own words
    c = _convo(sim, cid)
    if c["energy"] is None:
        c["energy"] = _energy(sim, cid, c)
    avoid = _avoid(sim, tid)
    salt = f"{w.day}:{cid}:{phone(w)['next']}"
    mine = post(sim, tid, "me", text, kind="chat", unread=False)
    rng = sim.streams.get("chat", w.day, cid, phone(w)["next"])
    ev = sim.new_event("text", intent, [me.id], [cid], 2, {"label": text, "thread": tid})
    ev["text"] = f"{me.short} texted {o.first}: \"{text}\""
    fx = Effects(w, ev)
    rt = w.ensure_rel(cid, me.id, w.day)
    if c["closed"]:
        # they already wrapped it up: texting again doesn't get an answer, and doing it twice is a lot
        c["double"] += 1
        mine["read"] = True
        if c["double"] >= 2:
            _gain(sim, cid, fx, cid, "perceived", -1.5, "double texting")
        sim.finish(ev, fx)
        if c["double"] == 1:
            _note(sim, cid, f"{o.first} is done talking for now. Texting again won't help; try later.")
        return {"thread": None, "result": "read"}
    sib = cid in sim.siblings(me.id)
    warmth = rt.affection / 100 + (o.traits["sociability"] - 50) / 100 + rng.gauss(0, 0.12)
    ok = "warm" if warmth > 0.25 else "ok" if warmth > -0.15 else "cold"
    cost, result, why, ask = 1.0, "replied", None, False
    plans = False
    if sib and intent in ("flirt", "ask_out"):
        _say(sim, cid, "family", "sib_flirt", salt, "chat_react", avoid)
    elif intent in ("greet", "chat", "ask") and c["turns"] == 0 and ok != "cold" and _recent(sim, cid):
        rk = _recent(sim, cid)
        _say(sim, cid, None, None, salt, "chat_recent", avoid, pool=_pool(sim, cid, "recent", rk.split(":")[0]))  # "today was so fun"
        _thread(sim, cid)["recent_said"] = rk
        _gain(sim, cid, fx, cid, "affection", 1.0, "remembering a good time")
        ask = _h(salt, "rq") % 2 == 0
    elif intent == "greet":
        _say(sim, cid, "greet", ok, salt, "chat_react", avoid)
        ask = ok != "cold"
        _gain(sim, cid, fx, cid, "familiarity", 0.6, "texting")
    elif intent == "answered":
        _say(sim, cid, "answered", yn, salt, "chat_react", avoid)
        _gain(sim, cid, fx, cid, "familiarity", 0.8, "texting")
        _gain(sim, cid, fx, cid, "affection", 0.5, "texting")
        ask = ok == "warm" and _h(salt, "ask") % 2 == 0
        cost = 0.7
    elif intent in ("chat", "ask"):
        topic = f["topic"]
        if topic and ok != "cold" and topic in D().get("topic", {}) and _h(salt, "tp") % 5 < 3:
            _say(sim, cid, None, None, salt, "chat_react", avoid, pool=_pool(sim, cid, "topic", topic))  # they answer what you brought up
        else:
            _say(sim, cid, "ask" if f["question"] else "chat", ok, salt, "chat_react", avoid)
        if topic in ("school", "game", "weekend"):
            _thread(sim, cid)["mentioned"] = {"topic": topic, "day": w.day}
        _gain(sim, cid, fx, cid, "familiarity", 1.0, "texting")
        _gain(sim, cid, fx, cid, "affection", 0.6 + 0.6 * f["effort"] if ok != "cold" else 0.0, "a good conversation")
        ask = ok == "warm" and _h(salt, "ask") % 3 != 0
        cost = 0.8
    elif intent == "joke":
        from .social import compatibility
        taste = tastes(o)[style] if style in STYLES else 0
        q = 0.4 * compatibility(w, me, o) + (me.aptitudes["charisma"] - 50) / 100 + (o.mood - 50) / 100 + 0.3 * taste + rng.gauss(0, 0.2)
        _learn(sim, cid, style)
        if taste < 0 and style == "tease" and q <= 0.15:
            _say(sim, cid, "style", "hates", salt, "chat_react", avoid)
            _gain(sim, cid, fx, cid, "perceived", -1.5, "teasing they didn't like")
            c["momentum"] -= 0.15
            why = f"{o.first} isn't into teasing. Try a different style with them."
        elif q > 0:
            _say(sim, cid, "style" if taste > 0 and _h(salt, "lv") % 2 else "joke", "loves" if taste > 0 and _h(salt, "lv") % 2 else "laugh",
                 salt, "chat_laugh", avoid)
            _gain(sim, cid, fx, cid, "affection", 1.2, "made them laugh")
            fx.need(me.id, "fun", 2, "texting")
            c["momentum"] = min(0.3, c["momentum"] + 0.1)
            cost = 0.6
        else:
            _say(sim, cid, "joke", "meh", salt, "chat_react", avoid)
            c["momentum"] -= 0.1
    elif intent == "vent":
        today = sum(1 for m in _thread(sim, cid)["msgs"] if m["from"] == "me" and m["day"] == w.day and m.get("kind") == "vent")
        mine["kind"] = "vent"
        close = rt.affection >= 30 or o.traits["empathy"] >= 65
        if close and today == 0:
            _say(sim, cid, "vent", "comfort", salt, "chat_comfort", avoid)
            fx.need(me.id, "stress", -7, f"venting to {o.first}")
            fx.mood(me.id, 2, f"{o.first} had your back")
            _gain(sim, cid, fx, cid, "affection", 1.5, "you trusted them with it")
            fx.rel(cid, me.id, "trust", 2, "you opened up")
            fx.rel(me.id, cid, "trust", 2, "they had your back")
            why = f"{o.first} had your back. Venting to someone close takes the edge off." if today == 0 else None
        else:
            _say(sim, cid, "vent", "meh", salt, "chat_react", avoid)
            fx.need(me.id, "stress", -2, "venting")
            why = (f"You two aren't that close yet. Venting lands better with a close friend." if not close
                   else "Once a day is support. More than that and it starts to wear on people.")
        if f["topic"] in ("school", "game", "weekend"):
            _thread(sim, cid)["mentioned"] = {"topic": f["topic"], "day": w.day}
        cost = 0.7
    elif intent == "news":
        if rt.affection >= 20:
            _say(sim, cid, "news", "hype", salt, "chat_hype", avoid)
            fx.mood(me.id, 3, f"{o.first} hyped you up")
            _gain(sim, cid, fx, cid, "affection", 1.0, "you shared good news")
            c["momentum"] = min(0.3, c["momentum"] + 0.1)
        else:
            _say(sim, cid, "news", "meh", salt, "chat_react", avoid)
        cost = 0.7
    elif intent == "gossip":
        if o.traits["sociability"] + o.traits["impulsivity"] >= 105 or rt.affection >= 55:
            _say(sim, cid, "gossip", "spill", salt, "chat_gossip", avoid)
            fx.need(me.id, "fun", 3, "gossip")
            _gain(sim, cid, fx, cid, "familiarity", 1.5, "gossiping")
            _gain(sim, cid, fx, cid, "affection", 0.8, "gossiping")
        else:
            _say(sim, cid, "gossip", "shut", salt, "chat_react", avoid)
            _gain(sim, cid, fx, cid, "perceived", -1.0, "not into gossip")
            why = f"{o.first} isn't into gossip."
    elif intent == "thanks":
        _say(sim, cid, "thanks", "warm" if ok == "warm" else "ok", salt, "chat_react", avoid)
        _gain(sim, cid, fx, cid, "affection", 1.0, "you said thanks")
        cost = 0.6
    elif intent == "compliment":
        _learn(sim, cid, "sweet")
        if tastes(o)["sweet"] < 0 and rt.affection < 50:
            _say(sim, cid, "compliment", "weird", salt, "chat_react", avoid)
            why = f"{o.first} gets weird about sweet stuff. Make them laugh instead."
        elif rt.affection >= 10 or rt.familiarity >= 40:
            _say(sim, cid, "compliment", "warm", salt, "chat_react", avoid)
            _gain(sim, cid, fx, cid, "affection", 2.0, "a nice text")
            _gain(sim, cid, fx, cid, "perceived", 1.5, "a nice text")
        else:
            _say(sim, cid, "compliment", "weird", salt, "chat_react", avoid)
    elif intent == "support":
        # they're going through something you'd know about: hurt, cut, a breakup, a bad stretch
        down = (o.needs.get("stress", 40) > 55 or o.mood < 45 or o.flags.get("injured_until", -1) >= w.day
                or any(m["valence"] <= -0.3 and w.day - m["day"] <= (10 if m["kind"] in ("cut_from_team", "broke_up") else 4)
                       for m in o.memories))
        if down:
            _say(sim, cid, "support", "thanks", salt, "chat_react", avoid)
            _gain(sim, cid, fx, cid, "affection", 3.0, "you checked on them")
            fx.rel(cid, me.id, "trust", 3, "you checked on them")
            fx.need(cid, "stress", -5, "someone checked on them")
            c["momentum"] = min(0.3, c["momentum"] + 0.15)
        else:
            _say(sim, cid, "support", "fine", salt, "chat_react", avoid)
            _gain(sim, cid, fx, cid, "affection", 0.5, "you checked on them")
    elif intent == "apology":
        if rt.affection > -30:
            _say(sim, cid, "apology", "accept", salt, "chat_react", avoid)
            fx.rel(cid, me.id, "rivalry", -6, "you apologized")
            fx.rel(cid, me.id, "trust", 3, "you apologized")
            _gain(sim, cid, fx, cid, "affection", 2.0, "you apologized")
        else:
            _say(sim, cid, "apology", "cold", salt, "chat_react", avoid)
    elif intent == "dry":
        c["momentum"] -= 0.2
        _gain(sim, cid, fx, cid, "perceived", -1.0, "a dry text")
        cost = 1.5
        if rt.affection >= 35 and _h(salt, "chk") % 2 == 0:
            _say(sim, cid, "dry", "check", salt, "chat_react", avoid)
        else:
            _say(sim, cid, "dry", "dry", salt, "chat_dry", avoid)
    elif intent == "rude":
        _say(sim, cid, "rude", "hurt", salt, "chat_react", avoid)
        fx.rel(cid, me.id, "affection", -4, "you were rude")
        fx.rel(cid, me.id, "rivalry", 5, "you were rude")
        fx.rel(cid, me.id, "perceived", -6, "you were rude")
        c["energy"] = 0
        result = "rude"
    elif intent == "bye":
        post(sim, tid, cid, _pick(sim, _pool(sim, cid, "close", "nice" if ok != "cold" else "tired"), salt, avoid), kind="chat_close", unread=False)
        _gain(sim, cid, fx, cid, "perceived", 0.5, "ended on a good note")
        if c["turns"] >= 4:
            post(sim, tid, "note", "Nice. Ending on a good note leaves them wanting more.", kind="note", unread=False)
        c["closed"] = True
        result = "bye"
    elif intent == "love" and (me.flags.get("partner") == cid or sib):
        _say(sim, cid, "love", "back" if not sib else "fam", salt, "chat_react", avoid)
        _gain(sim, cid, fx, cid, "affection", 2.0, "love you")
    elif intent == "plans" and (w.meta.get("control", {}).get("queued") or {}).get("target") == cid:
        _say(sim, cid, "plans", "already", salt, "chat_react", avoid)
    elif intent == "plans" and (w.meta.get("control", {}).get("queued") or {}).get("agreed"):
        q = w.meta["control"]["queued"]
        _say(sim, cid, "plans", "no" if ok != "cold" else "cold", salt, "chat_react", avoid)
        other = w.chars[q["target"]].first if q.get("target") in w.chars else "someone"
        _note(sim, cid, f"You already have plans with {other} at your next free time. Ask {o.first} after that.")
    elif intent == "plans":
        free = o.location == me.location and o.status == "active"
        p = clamp((rt.affection + o.traits["sociability"] * 0.3 - 10) / 70, 0.02, 0.92) * (1 if free else 0.1)
        if me.flags.get("partner") == cid:
            p = max(p, 0.8)
        if rng.random() < p:
            _say(sim, cid, "plans", "yes", salt, "chat_plans_yes", avoid)
            w.meta.setdefault("control", {})["queued"] = {"action": "hang_out", "target": cid, "agreed": True, "day": w.day}
            _gain(sim, cid, fx, cid, "affection", 1.0, "making plans")
            _note(sim, cid, "Plans made. You'll hang out at your next free time.")
            plans, result = True, "plans"
        else:
            _say(sim, cid, "plans", "no" if ok != "cold" else "cold", salt, "chat_react", avoid)
    elif intent == "letdown":
        # they flirted, you're not into it: kind beats cold
        _say(sim, cid, None, None, salt, "chat_react", avoid, pool=_pool(sim, cid, "banter", "letdown"))
        fx.rel(cid, me.id, "attraction", -12, "you let them down easy")
        _gain(sim, cid, fx, cid, "affection", 0.5, "you were nice about it")
        c["banter"] = None
        why = f"You let {o.first} down easy. No hard feelings."
        result = "letdown"
    elif intent in ("flirt", "ask_out", "love"):
        prev = c.get("banter") if (c.get("banter") or {}).get("open") else None
        them_first = last_q is not None and last_q["from"] == cid and last_q.get("kind") == "chat_flirt_in"
        lift = (0.2 if them_first else 0.0) + (0.1 * prev["beat"] if prev and prev.get("after") == "landed" else 0.0)
        res = flirt_check(sim, cid, 1 if cool else 2 if intent in ("ask_out", "love") else max(1, f["flirt"]), 0.0 if cool else f["effort"],
                          c["momentum"] + lift, rng, style=style if intent == "flirt" else None)
        out = res["outcome"]
        if cool and out == "shut" and _open_to_you(sim, cid) is None:
            out = "awkward"  # playing it cool never gets you shut down
        why = res["why"]
        if intent == "flirt":
            _learn(sim, cid, style)
        if intent == "ask_out" and out == "landed":
            _say(sim, cid, "ask_out", "yes", salt, "chat_flirt_landed", avoid)
            # they said to ask in person: they meant it, and the game plans it for the next time you see them
            o.flags["told_to_ask"] = {"by": me.id, "day": w.day}
            r_me = w.ensure_rel(me.id, cid, w.day)
            need = w.rules["rel.crush_threshold"] + 2 - r_me.attraction
            if need > 0:
                fx.rel(me.id, cid, "attraction", need, "you asked them out")
            q = w.meta.setdefault("control", {}).get("queued")
            if not q or q.get("action") == "ask_out":
                w.meta["control"]["queued"] = {"action": "ask_out", "target": cid, "day": w.day, "expires": w.day + 4}
                why += f" Plan made: you'll ask {o.first} out the next time you see them."
            else:
                why += f" Ask {o.first} out when you see them: it's in your choices."
        elif intent == "ask_out" and out == "shut":
            _say(sim, cid, "ask_out", "no", salt, "chat_flirt_shut", avoid)
        elif intent == "flirt" and style in STYLES and _h(salt, "st") % 2 and (
                (tastes(o)[style] > 0 and out == "landed") or (tastes(o)[style] < 0 and out in ("awkward", "shut"))):
            _say(sim, cid, "style", "loves" if out == "landed" else "hates", salt, f"chat_flirt_{out}", avoid)
        else:
            key = "cool" if cool else style if style in STYLES else None
            pool = _pool(sim, cid, "banter", "them", key, out) if key and intent == "flirt" else None
            if pool and _h(salt, "bp") % 10 < 8:
                _say(sim, cid, None, None, salt, f"chat_flirt_{out}", avoid, pool=pool)  # answered in the flavor of what you sent
            else:
                _say(sim, cid, "flirt", out, salt, f"chat_flirt_{out}", avoid)
        if out == "landed":
            _gain(sim, cid, fx, cid, "attraction", 4.0, "flirting")
            _gain(sim, cid, fx, me.id, "attraction", 3.0, "flirting")
            _gain(sim, cid, fx, cid, "affection", 1.0, "flirting")
            c["momentum"] = min(0.3, c["momentum"] + 0.15)
            cost = 0.5
            ask = _h(salt, "fa") % 2 == 0
        elif out == "playful":
            _gain(sim, cid, fx, cid, "attraction", 1.5, "flirting")
            cost = 0.8
        elif out == "awkward":
            _gain(sim, cid, fx, cid, "perceived", -1.0, "an awkward flirt")
            c["momentum"] -= 0.15
            cost = 1.4
        else:
            _gain(sim, cid, fx, cid, "perceived", -3.0, "a flirt that didn't land")
            fx.rel(cid, me.id, "attraction", -1.5, "a flirt that didn't land")
            c["momentum"] -= 0.3
            cost = 2.0
        if intent == "flirt":
            went = _banter_step(sim, cid, c, out, cool, them_first, prev, fx, salt, avoid)
            if went:
                why, ask = went, False  # the payoff is the last word
            if (c.get("banter") or {}).get("open"):
                ask = False  # they don't change the subject mid-flirt
        ev["importance"] = 8
        ev["outcome"] = out
        ev["data"]["why"] = why
        result = f"flirt_{out}"
    else:
        _say(sim, cid, "chat", ok, salt, "chat_react", avoid)
    if intent not in ("flirt", "letdown") and (c.get("banter") or {}).get("open"):
        c["banter"]["open"] = False  # you changed the subject
    c["turns"] += 1
    c["energy"] -= cost
    good = result not in ("rude", "flirt_awkward", "flirt_shut") and intent not in ("dry", "bye")
    if good and not c["closed"] and _keen(sim, cid) and not sib and rng.random() < 0.35:
        post(sim, tid, cid, _pick(sim, _pool(sim, cid, "double"), salt + ":dbl", avoid), kind="chat_double", unread=False, ctx={"fast": True})
    if c["energy"] <= 0 and not c["closed"]:
        tone = "cold" if result == "rude" or c["momentum"] < -0.3 else "nice" if ok == "warm" else "tired"
        post(sim, tid, cid, _pick(sim, _pool(sim, cid, "close", tone), salt + ":close", avoid), kind="chat_close" if tone != "cold" else "chat_close_cold", unread=False)
        c["closed"] = True
    elif ask and not c["closed"]:
        pool = _pool(sim, cid, "ask", "flirty" if result == "flirt_landed" else "general")
        qs = [x if isinstance(x, dict) else {"q": x, "a": "open"} for x in pool]
        text_q = _pick(sim, [x["q"] for x in qs], salt + ":ask", avoid)
        kind_a = next((x["a"] for x in qs if x["q"] == text_q), "open")
        post(sim, tid, cid, text_q, kind="chat_ask", unread=False, ctx={"a": kind_a, **({"fast": True} if _keen(sim, cid) else {})})
    if c["turns"] == 5:
        t = _thread(sim, cid)
        t["long_days"] = (t.get("long_days", []) + [w.day])[-10:]  # a real back-and-forth
    if why:
        notes = [m for m in _thread(sim, cid)["msgs"][-8:] if m.get("kind") == "note"]
        if not notes or notes[-1]["text"] != why:  # same reason as last time: the reply says it
            _note(sim, cid, why)
    sim.finish(ev, fx)
    phone(w)["texted"][cid] = w.day
    return {"thread": None, "result": result, "plans": plans, "why": why, "who": sender_name(sim, cid)}


def suggestions(sim, cid) -> list:
    """A few things you could send next, fitted to where the conversation and the two of you are."""
    from .messages import _avoid, _h, phone
    w = sim.w
    me = _me(sim)
    o = w.chars.get(cid)
    if not me or not o:
        return []
    t = _thread(sim, cid)
    c = t.get("convo") if t.get("convo", {}).get("day") == w.day and t["convo"].get("phase") == sim.current_phase() else None
    if c and c.get("closed"):
        return []
    last = next((m for m in reversed(t["msgs"]) if m.get("kind") != "note"), None)
    talking = bool(c and c["turns"])
    asked = last is not None and last["from"] == cid and (last.get("kind") == "chat_ask" or last["text"].rstrip().endswith("?"))
    a_kind = (last.get("ctx") or {}).get("a", "doing") if asked else None
    rd = read(sim, cid)
    st = stage(sim, cid)
    sib = cid in sim.siblings(me.id)
    partner = me.flags.get("partner") == cid
    bm = None if (sib or o.role == "staff") else _banter_mode(sim, cid, c, last)
    if bm:
        # mid-flirt: what you say next builds on what they just said
        out = _banter_suggestions(sim, cid, bm, f"{w.day}:{cid}:{len(t['msgs'])}", _avoid(sim, f"dm:{cid}"))
        if talking and c["turns"] >= 2:
            out.append({"text": _pick(sim, _pool(sim, cid, "suggest", "bye"), f"{w.day}:{cid}:bye", _avoid(sim, f"dm:{cid}")),
                        "intent": "bye", "tone": TONE["bye"]})
        return out
    cands = []  # (rank to pick, rank to show, suggestion)

    def add(pick, show, intent, pool, tone=None, **extra):
        cands.append((pick, show, dict(intent=intent, pool=pool, tone=tone or TONE.get(intent, "💬"), **extra)))
    if asked and a_kind == "yesno":
        add(0, 0, "answer", "yes", "↩", yn="yes")
        add(0, 0, "answer", "no", "↩", yn="no")
    elif asked:
        add(0, 0, "answer", a_kind if a_kind in D()["answer"] else "doing", "↩")
    elif not talking:
        add(0, 0, "greet", "greet")
    soon = {i["group"] for i in w.calendar if i["kind"] == "game" and i["day"] in (w.day, w.day + 1)}
    if any(g in soon for g in o.memberships):
        add(3, 1, "good_luck", "good_luck")
    if any(w.day - x["day"] <= 7 for x in o.achievements):
        add(3, 1, "congrats", "congrats")
    hurt = any(m["valence"] <= -0.3 and cid in m.get("with", []) and w.day - m["day"] <= 21 for m in me.memories)
    r_me = w.rels.get((me.id, cid))
    if hurt or (r_me and (r_me.affection < 0 or r_me.rivalry >= 45)):
        add(3, 1, "apology", "apology")
    if o.needs.get("stress", 40) > 60:
        add(3, 1, "support", "support")
    add(5, 2, "ask", "ask")
    add(5, 2, "joke", "joke")
    if me.needs.get("stress", 40) >= 60 and (r_me := w.rels.get((me.id, cid))) and r_me.affection >= 30:
        add(3, 1, "vent", "vent", "😮‍💨")
    recent_win = any(x["day"] >= w.day - 1 for x in me.achievements)
    if recent_win:
        add(3, 1, "news", "news", "🎉")
    if last is not None and last["from"] == cid and last.get("kind") == "chat_comfort":
        add(2, 1, "thanks", "thanks", "🙏")
    if partner:
        add(2, 3, "love", "love")
        add(4, 4, "plans", "plans")
    if not sib and o.role != "staff" and (partner or rd["level"] >= 2):
        # a flirt in a style: one you know they love, or one you haven't tried on them yet
        known = phone(w).get("tastes", {}).get(cid, {})
        loved = [k for k in STYLES if known.get(k) == 1]
        fresh = [k for k in ("tease", "sweet", "bold", "funny") if k not in known]
        style = loved[_h(w.day, cid) % len(loved)] if loved else fresh[_h(w.day, cid, len(t["msgs"])) % len(fresh)] if fresh else None
        if style and f"flirt_{style}" in D()["suggest"]:
            add(2, 3, "flirt", f"flirt_{style}", STYLE_TONE[style], style=style)
        else:
            add(2, 3, "flirt_strong" if st >= 3 else "flirt", "flirt_strong" if st >= 3 else "flirt")
        if st >= 3 and not partner:
            add(2, 3, "ask_out", "ask_out", "💘")
    if not partner and ((r_me and r_me.affection >= 20) or st >= 2):
        add(4, 4, "plans", "plans")
    if talking and c["turns"] >= 2:
        add(1, 9, "bye", "bye")
    salt = f"{w.day}:{cid}:{len(t['msgs'])}"
    seen, picked = set(), []
    # answers to their question come first and keep their order (yes before no); the rest shuffle by the day
    for pick, show, sug in sorted(cands, key=lambda x: (x[0], 0 if x[0] == 0 else _h(salt, x[2]["pool"]) % 7)):
        key = sug["pool"] + str(sug.get("yn"))
        if key in seen:
            continue
        seen.add(key)
        picked.append((show, sug))
        if len(picked) >= 4:
            break
    avoid = _avoid(sim, f"dm:{cid}")
    out = []
    for show, sug in sorted(picked, key=lambda x: x[0]):
        pool = _pool(sim, cid, "answer", sug["pool"]) if sug["intent"] == "answer" else _pool(sim, cid, "suggest", sug["pool"])
        if sug["intent"] == "flirt" and sug.get("style") in STYLES:  # openers that fit where you two are
            pool = (_pool(sim, cid, "banter", "open", _band(sim, cid), sug["style"]) or []) + pool
        if not pool:
            continue
        item = {"text": _pick(sim, pool, f"{salt}:{sug['pool']}", avoid), "intent": sug["intent"], "tone": sug["tone"]}
        for k in ("style", "yn"):
            if sug.get(k):
                item[k] = sug[k]
        out.append(item)
    return out


def view(sim, cid) -> dict:
    """The compose bar for a conversation: what you can send, and where things stand."""
    from .messages import phone
    w = sim.w
    me = _me(sim)
    o = w.chars.get(cid)
    if not o or not me:
        return {"can_type": False, "suggestions": [], "status": "none"}
    if cid not in phone(w)["contacts"] and cid not in sim.siblings(me.id):
        return {"can_type": False, "suggestions": [], "status": "no_number"}
    t = _thread(sim, cid)
    c = t.get("convo")
    live = c and c.get("day") == w.day and c.get("phase") == sim.current_phase()
    status = "done" if live and c.get("closed") else "open" if live and c.get("turns") else "new"
    rd = read(sim, cid)
    return {"can_type": True, "suggestions": suggestions(sim, cid), "status": status,
            "stage": STAGES[stage(sim, cid)], "read": rd["label"], "tone": rd["tone"], "romance": vibe_relevant(sim, cid)}


def vibe_relevant(sim, cid) -> bool:
    from .social import orientation_ok
    w = sim.w
    me = _me(sim)
    r = w.rels.get((cid, me.id))
    maybe = orientation_ok(me, w.chars[cid]) or (r is not None and r.attraction >= 30) or me.flags.get("partner") == cid
    return bool(maybe) and _open_to_you(sim, cid) not in ("family", "staff")


def _recent(sim, cid) -> str | None:
    """Something you two just did together (today or yesterday) that they'd bring up, if they haven't already."""
    w = sim.w
    me = _me(sim)
    said = _thread(sim, cid).get("recent_said", "")
    for eid in reversed(w.history.by_char.get(me.id, [])[-80:]):
        e = w.history.events.get(eid)
        if not e or w.day - e["day"] > 1:
            continue
        both = me.id in e["actors"] + e["targets"] + e.get("involved", []) and cid in e["actors"] + e["targets"] + e.get("involved", [])
        if not both:
            continue
        k = None
        if e["type"] == "interact.hang_out" and e.get("outcome") in ("good", "great", "accepted", "ok"):
            k = "group" if (e.get("data") or {}).get("act") or (e.get("data") or {}).get("crew") else "hangout"
        elif e["type"] == "interact.date" and e.get("outcome") in ("good", "great"):
            k = "date"
        elif e["type"] == "game" and e.get("outcome") in ("win", "loss"):
            k = "game_" + e["outcome"]
        if k:
            return None if said == f"{k}:{eid}" else f"{k}:{eid}"  # each shared moment comes up once
    return None


def follow_ups(sim):
    """Mornings: friends follow up on what you told them ("how'd the test go??")."""
    from .messages import _h, later, phone
    w = sim.w
    me = _me(sim)
    if not me:
        return
    for tid, t in phone(w)["threads"].items():
        m = t.get("mentioned")
        if not m or not tid.startswith("dm:"):
            continue
        cid = tid[3:]
        r = w.rels.get((cid, me.id))
        if 1 <= w.day - m["day"] <= 2 and cid in w.chars and r and r.affection >= 25:
            pool = _pool(sim, cid, "follow", m["topic"])
            if pool:
                later(sim, cid, "chat_follow", delay_phases=2 + _h(w.day, cid) % 3, text=pool[_h(w.day, cid, "f") % len(pool)],
                      ctx={"a": "day"})
            t.pop("mentioned", None)
        elif w.day - m["day"] > 2:
            t.pop("mentioned", None)
