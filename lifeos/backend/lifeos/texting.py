"""Adding texting (flirt lines and group chats), the reliable way.

ChatGPT doesn't compose block headers any more: the prompt is a template the game builds from its own texting slots (the
places flirt lines can actually go, from data/chat.json), and ChatGPT fills it in under headers it copies. You pick what
to fill: which parts of flirting (starting it, how they react, keeping it going, when they flirt first, how it ends), which
style, and how many lines each. A paste is taken section by section: every section that works goes in, and each one that
doesn't is listed with why, with a message for ChatGPT that asks for just those again. One bad section never stops the rest.
"""
from __future__ import annotations

import re

STYLES = ("tease", "sweet", "bold", "funny", "cheesy")
STYLE_SAY = {"tease": "teasing / sarcastic", "sweet": "sweet", "bold": "bold", "funny": "funny", "cheesy": "cheesy", "cool": "playing it cool",
             "letdown": "letting them down easy, kindly"}
PARTS = (("start", "Starting it", "your first flirty texts"), ("react", "How they react", "their answer: into it, laughing it off, "
         "awkward, or a no"), ("keep", "Keeping it going", "what you send next"), ("first", "When they flirt first",
         "them making the first move, and how you answer"), ("end", "How it ends", "when it really goes somewhere"))
OUT = (("landed", "lands", "they're into it"), ("playful", "laughs", "they laugh it off"), ("awkward", "awkward", "it's awkward"),
       ("shut", "no", "they shut it down, kindly"))
PAYOFF = {"blush": "they're blushing", "plans": "making real plans", "goodnight": "going to bed smiling",
          "ask": "telling me to ask them out in person"}
PER = {"few": 2, "bunch": 3, "lot": 5}
GROUP_N = {"few": 2, "bunch": 4, "lot": 8}


def _base():
    from . import dialogue
    return dialogue._base("chat.json")["banter"]


def sections(parts=None, style: str = "all") -> list:
    """The template's sections for these parts and style: [(header, what it is)]. Built from the game's own slots, so
    every header has somewhere to go."""
    from . import script
    b = _base()
    parts = [p for p in (parts or [k for k, _, _ in PARTS]) if p in {k for k, _, _ in PARTS}]
    styles = list(STYLES) if style in (None, "", "all") else [style] if style in STYLES else list(STYLES)
    out = []
    if "start" in parts:
        for st in styles:
            if st in b["open"]["early"]:
                out.append((f"flirt {st}:", f"me starting a {STYLE_SAY[st]} flirt"))
            if st in b["open"]["close"]:
                out.append((f"flirt {st} later:", f"me starting a {STYLE_SAY[st]} flirt, once we're already flirty"))
    if "react" in parts:
        for st in styles:
            for key, word, say in OUT:
                if key in b["them"].get(st, {}):
                    out.append((f"flirt answers {st}, {word}:", f"them answering my {STYLE_SAY[st]} flirt: {say}"))
    if "keep" in parts:
        for st in styles + (["cool"] if style in (None, "", "all") else []):
            if st in b["back"]["landed"]:
                out.append((f"flirt follow-ups {st}:", f"what I send next after it landed ({STYLE_SAY[st]})"))
            if st in b["back"]["playful"]:
                out.append((f"flirt follow-ups {st} after a laugh:", f"what I send next after they laughed it off ({STYLE_SAY[st]})"))
    if "first" in parts:
        out += [("flirt first:", "them flirting with me first"), ("flirt first later:", "them flirting first, once we're flirty")]
        for st in styles + ["cool", "letdown"]:
            if st in b["in_back"]:
                out.append((f"flirt back {st}:", f"me answering when they flirt first ({STYLE_SAY[st]})"))
    if "end" in parts:
        for k, say in PAYOFF.items():
            if k in b["payoff"]:
                out.append((f"flirt payoff {k}:", f"them ending it when it went somewhere: {say}"))
    for h, _ in out:  # (a header that doesn't compile to a real slot is a bug here, not ChatGPT's)
        script.flirt_path(h[len("flirt "):-1])
    return out


def prompt(name: str, what: str = "flirt", ask: str = "", size: str = "bunch", parts=None, style: str = "all") -> dict:
    """The ChatGPT prompt: a template to fill in. {"prompt", "sections", "lines"}"""
    from .storybuilder import TEXTING_GROUP
    what = what if what in ("flirt", "group", "both") else "flirt"
    per = PER.get(size, 3)
    secs = sections(parts, style) if what in ("flirt", "both") else []
    groups = GROUP_N.get(size, 4) if what in ("group", "both") else 0
    L = [f"I'm adding texting to LIFE OS, a life-simulation game: I play {name}, starting high school in Guilford, Connecticut "
         "in fall 2010, through college. The game decides who sends these and when; you write how people text.", "",
         "## What I want", "", (ask.strip() or "[describe it here: the vibe, who it's for, what you want more of]"), "",
         "## How to answer", "",
         "Reply with ONE code block (```): the template below, filled in, and nothing after it."]
    if secs:
        L += [f"- Keep every header line exactly as it is: copy it, don't change, bold or add a word. Under each one, replace "
              f"the ... with {per} lines, each on its own line, indented two spaces. Nothing for a section? Delete it.",
              "- How teenagers actually text: lowercase, short (under 120 characters), specific, funny when it fits. PG-13. "
              "Most lines without emoji; a few with one. {me} is me; no names of real people.", "",
              "## The template", "", "```"]
        for h, _ in secs:
            L += [h, "  ..."]
        if groups:
            L += ["", f"(then the {groups} group chats, below)"]
        L += ["```", "", "## What each section is", ""]
        L += [f"- `{h}` {say}" for h, say in secs]
        L.append("")
    if groups:
        L += [f"## Group chats: write {groups}" + (", after the flirt sections, in the same code block" if secs else ""), "",
              "Each one in exactly this shape. Whoever's talking is A, B or C (family: mom, dad, sibling), never a name.", ""]
        L.append(TEXTING_GROUP.split("\n", 2)[2].strip())
    text = "\n".join(L).rstrip() + "\n"
    return {"prompt": text, "sections": len(secs), "lines": len(secs) * per, "group_chats": groups}


# --- taking a paste ------------------------------------------------------------------------------------------------

HEAD = re.compile(r"(?i)^(flirt\b|group\s+chat\b|texts?\s|chat\s)")
FILLER = re.compile(r"^\s*(\.\.\.|…|\(.*\)|\[.*\]|-+)\s*$")


def take(text: str) -> dict:
    """A paste, section by section: {"text": the sections that work (a script), "skipped": [{"header", "why"}],
    "notes": what got fixed}. Template lines nobody filled in (...) and sections left empty are dropped quietly."""
    from . import dialogue, script, scriptfix
    src = script.extract(text).replace("\r\n", "\n")
    lines, origin, notes = scriptfix.habits(src)
    blocks, cur = [], None
    for ln in lines:
        if ln.strip().startswith(("===", "```")):
            continue
        if ln[:1] not in (" ", "\t") and HEAD.match(ln.strip()):
            cur = [ln.rstrip()]
            blocks.append(cur)
        elif cur is not None:
            cur.append(ln.rstrip())
    good, skipped, fixed = [], [], [n["text"] for n in notes if not n["text"].startswith("read '")]
    lib = dialogue.library()
    for blk in blocks:
        body = [ln for ln in blk[1:] if ln.strip() and not FILLER.match(ln)]
        if not body:
            continue
        fx = scriptfix.repair("=== Texting\n" + "\n".join([blk[0]] + body) + "\n", library=lib)
        packs = fx["result"]["packs"] if fx["ok"] else []
        n = sum(_count(pk) for pk in packs)
        if fx["ok"] and n:
            good.append(fx["text"].split("\n", 1)[1].strip("\n"))
            fixed += [f"{blk[0].strip()} {x['text']}" for x in fx["notes"]]
        else:
            why = [x["text"] for x in fx["notes"] if "came off" in x["text"]] + \
                [e["text"] for e in fx["result"]["errors"] if "nothing in this pack" not in e["text"]]
            skipped.append({"header": blk[0].strip(), "why": (_why(why[0]) if why else "nothing in it the game could use")})
    return {"text": ("=== Texting\n" + "\n\n".join(good) + "\n") if good else "", "skipped": skipped, "notes": fixed,
            "blocks": len(blocks)}


def _why(note: str) -> str:
    """A repair note as the reason itself: "the line came off ('x' isn't a kind of flirt line)" -> "'x' isn't a kind..."."""
    m = re.search(r"came off \((.+)\)$", note)
    return m.group(1) if m else note


def _count(pk) -> int:
    from . import dialogue
    b = dialogue.texting_breakdown(pk)
    return b["flirt_total"] + b["texting"] + len(b["group_chats"])


def valid_headers() -> str:
    """Every flirt header the game has, and the group chat one (for a fix-it message)."""
    hs = [h for h, _ in sections()]
    return "\n".join(hs) + "\ngroup chat <crew|team|family>, <when>:  (who's talking: A, B, C; family: mom, dad, sibling; never names)"


def fix_prompt(skipped: list, none_at_all: bool = False) -> str:
    if none_at_all:
        head = "The LIFE OS game couldn't use your texting reply: it didn't have any of the template's sections in it."
    else:
        head = "Some sections of your LIFE OS texting reply couldn't go in:\n" + "\n".join(f"- {s['header']} {s['why']}" for s in skipped)
    return (head + "\n\nSend just " + ("it" if none_at_all else "those sections") + " again in ONE code block, nothing after it. "
            "Copy each header exactly from this list (plain text, no bold, no #), with its lines under it indented two spaces:\n\n"
            + valid_headers() + "\n")
