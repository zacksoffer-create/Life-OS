"""Repair a story script instead of refusing it.

ChatGPT gets most of a script right and a few words wrong: an effect the game doesn't know, a typo'd name, a tag that
isn't one, a line too long. Refusing the whole paste for that made adding a storyline a back-and-forth. Here the
compiler stays strict, and this module reads its errors line by line and fixes or drops exactly the broken piece:

- an unknown effect, trait, game or style on a choice: that one effect comes off (the rest stay)
- an unknown tag on a scene (or a fact nothing remembers, or an `after` to a scene that isn't there): that tag comes off
- someone talking who isn't in the cast: they become a walk-on (`dany:` -> `Dany:`)
- a {placeholder} the game can't fill: its words stay, as plain text
- outcomes without a roll or game: they become plain lines; a roll or vibe without outcomes: it comes off
- a fifth choice, a sixth beat, a stray line: it comes off (or is tucked under the choice before it)
- a line too long: it's split at a sentence

If a line still has a problem after its fix, its effects or tags come off; after that, the line (with what's under it).
Only a paste with no scenes or lines in it at all fails. Every fix comes back as a note with its line number, and the
fixed script is what gets saved, so what you read is what plays.
"""
from __future__ import annotations

import re

from . import script as SC

EFFECT_WORDS = ("isn't an effect", "isn't a trait", "isn't a reputation", "isn't part of a relationship",
                "isn't something people get into", "isn't a mini game", "isn't a style", "isn't an amount",
                "should be a short lowercase fact name", "can talk in a scene, but", "isn't who this scene is about",
                "isn't someone this scene knows", "focus is one of", "talent or skill to roll against")
TAG_WORDS = ("isn't a tag I know", "needs a date", "'with' goes on a scene", "isn't a kind of person.", "use the opposite",
             "a feeling goes on a scene", "a feeling can only be checked", "if takes a fact", "spread goes on the storyline",
             "no choice in this script or your storylines remembers", "has no scene called", "there's no scene called that here",
             "spread needs the school years")


def _indent(s: str) -> int:
    return len(s) - len(s.lstrip(" "))


def _quoted(msg: str) -> str | None:
    m = re.search(r"'([^']+)'", msg)
    return m.group(1) if m else None


def _split_bar(line: str) -> tuple:
    """'* label | a, b' -> ('* label', ['a', 'b']) (a bar inside {a|b} versions doesn't count)."""
    parts = SC._split(line, "|")
    if len(parts) < 2:
        return line, []
    return parts[0].rstrip(), [x.strip() for x in ", ".join(parts[1:]).split(",") if x.strip()]


def _join_bar(head: str, items: list) -> str:
    return f"{head} | {', '.join(items)}" if items else head


def _block_end(lines: list, i: int) -> int:
    """The line after everything indented under line i."""
    base = _indent(lines[i] or "")
    j = i + 1
    while j < len(lines) and (lines[j] is None or not lines[j].strip() or _indent(lines[j]) > base):
        if lines[j] is not None and lines[j].strip() and _indent(lines[j]) <= base:
            break
        j += 1
    # (trailing blank lines stay)
    while j > i + 1 and lines[j - 1] is not None and not lines[j - 1].strip():
        j -= 1
    return j


def _scene_end(lines: list, i: int) -> int:
    j = i + 1
    while j < len(lines):
        t = (lines[j] or "").strip()
        if SC.SCENE_RE.match(t) or SC.SECTION_RE.match(t):
            break
        j += 1
    return j


def _drop_tag(line: str, q: str) -> str | None:
    """A scene line (or when:) without the tag that has q in it."""
    m = re.fullmatch(r"(\s*---\s*)(.+?)((?:\s*\[[^\]]*\])*)\s*(#[a-z][a-z0-9_]{2,79})?\s*", line)
    if m:
        toks = [t.strip() for t in re.split(r"\s*[·;,]\s*", " · ".join(re.findall(r"\[([^\]]*)\]", m.group(3) or ""))) if t.strip()]
        keep = [t for t in toks if q.lower() not in t.lower()]
        if len(keep) == len(toks):
            return None
        return f"{m.group(1)}{m.group(2).rstrip()}" + (f"  [{' · '.join(keep)}]" if keep else "") + (f" {m.group(4)}" if m.group(4) else "")
    a = SC.ATTR_RE.match(line.strip())
    if a and a.group(1).lower() == "when":
        toks = [t for t in re.split(r"\s*[·;,]\s*", a.group(2)) if t.strip()]
        keep = [t for t in toks if q.lower() not in t.lower()]
        if len(keep) == len(toks):
            return None
        return ("when: " + " · ".join(keep)) if keep else ""
    return None


def _strip_tags(line: str) -> str | None:
    m = re.fullmatch(r"(\s*---\s*)(.+?)((?:\s*\[[^\]]*\])+)\s*(#[a-z][a-z0-9_]{2,79})?\s*", line)
    if not m:
        return None
    return f"{m.group(1)}{m.group(2).rstrip()}" + (f" {m.group(4)}" if m.group(4) else "")


def _split_long(line: str, limit: int) -> list | None:
    """A line too long: two (or more) lines at sentence breaks, the speaker kept on each."""
    ind = " " * _indent(line)
    body = line.strip()
    head, items = _split_bar(body)
    sp = SC.SPEAKER_RE.match(head)
    who, text = (sp.group(1) + ": ", sp.group(2)) if sp else ("", head)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) < 2:
        return None
    out, cur = [], ""
    for s in sentences:
        if cur and len(who) + len(cur) + len(s) + 1 > limit * 0.9:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    out.append(cur)
    if len(out) < 2:
        mid = len(sentences) // 2
        out = [" ".join(sentences[:mid]), " ".join(sentences[mid:])]
    lines = [ind + who + x for x in out]
    if items:
        lines[-1] = _join_bar(lines[-1], items)
    return lines


def _typo(line: str, msg: str, q: str | None):
    """The checker saw a likely typo ("Did you mean fun?"): read it as that. (line, note) or None."""
    import difflib
    m = re.search(r"Did you mean ([^?,]+)", msg)
    if not m:
        return None
    sugg = m.group(1).strip()
    target = q or (re.search(r"\{([^{}]+)\}", msg).group(1) if re.search(r"\{([^{}]+)\}", msg) else None)
    if not target or target.lower() not in line.lower():
        return None
    words = re.findall(r"[A-Za-z][A-Za-z_']*", target)
    best = max(words, key=lambda w: difflib.SequenceMatcher(None, w.lower(), sugg.lower()).ratio(), default=None)
    if not best or difflib.SequenceMatcher(None, best.lower(), sugg.lower()).ratio() < 0.6 or best.lower() == sugg.lower():
        return None
    new = re.sub(r"(?<![A-Za-z_])" + re.escape(best) + r"(?![A-Za-z_])", sugg, line, count=1, flags=re.I)
    if new == line:
        return None
    return new, f"'{best}' read as '{sugg}' (looked like a typo)"


def _fix(lines: list, i: int, msg: str, level: int) -> str | None:
    """Fix line i for this problem. Returns what was done (a note), or None if nothing could be done at this level."""
    line = lines[i]
    if line is None:
        return None
    t = line.strip()
    q = _quoted(msg)
    is_choice = t.startswith("*")
    is_scene = bool(SC.SCENE_RE.match(t))
    if level == 0:
        typo = _typo(line, msg, q)
        if typo:
            lines[i], note = typo
            return note
        ph = re.search(r"\{([^{}]+)\} isn't a name the game can fill", msg)
        if ph:
            lines[i] = line.replace("{" + ph.group(1) + "}", ph.group(1).replace("_", " "))
            return f"{{{ph.group(1)}}} isn't something the game fills in: kept as words"
        if "talks, but" in msg and q:
            sp = SC.SPEAKER_RE.match(t)
            if sp:
                lab = sp.group(1).strip()
                lines[i] = line.replace(lab + ":", lab[:1].upper() + lab[1:] + ":", 1)
                return f"'{lab}' isn't in the cast: they talk as a walk-on"
        if "isn't in a scene or a block" in msg:
            lines[i] = None
            return "a stray line outside any scene came off"
        if "comes after the choices" in msg:
            lines[i] = "    " + line.lstrip()
            return "a line after the choices was tucked under the choice before it"
        if "not on the scene's opening lines" in msg:
            head, _ = _split_bar(t)
            lines[i] = " " * _indent(line) + head
            return "effects on an opening line came off (effects only happen when you choose)"
        if "at most 4 choices" in msg or "five beats deep" in msg:
            j = _block_end(lines, i)
            for k in range(i, j):
                lines[k] = None
            return "a choice past the fourth (or a beat past the fifth) came off" if "4 choices" in msg else "a beat past the fifth came off"
        if "outcomes need" in msg:
            base = _indent(line)
            changed = False
            for k in range(i + 1, _block_end(lines, i)):
                if lines[k] is not None and _indent(lines[k]) > base:
                    m = SC.OUTCOME_RE.match(lines[k].strip())
                    if m:
                        lines[k] = " " * _indent(lines[k]) + (m.group(2).strip() or "...")
                        changed = True
            return "outcomes without a roll or game under them became plain lines" if changed else None
        if "a chance needs what happens" in msg or "a vibe needs what happens" in msg:
            head, items = _split_bar(t)
            keep = [x for x in items if not (re.match(r"(chance\s+)?\d{1,3}\s*%", x.lower()) or x.lower().startswith("vibe"))]
            lines[i] = " " * _indent(line) + _join_bar(head, keep)
            return "a roll (or vibe) without outcomes under it came off"
        if any(w in msg for w in TAG_WORDS) and q:
            tq = q
            m = re.match(r"(after|if)\s+(.+)", q)
            if "has no scene called" in msg or "there's no scene called that here" in msg:
                tq = "after " + (re.match(r"after (.+)", q).group(1) if q.startswith("after ") else q)
            new = _drop_tag(line, tq) if not m or "has no scene called" in msg else _drop_tag(line, q)
            if new is not None:
                if new == "":
                    lines[i] = None
                else:
                    lines[i] = new
                return f"the tag '{tq}' came off ({msg.split('.')[0]})"
        if "spread goes on the storyline" in msg:
            new = _drop_tag(line, "spread")
            if new is not None:
                lines[i] = new
                return "spread came off a scene (it goes on the storyline)"
        if any(w in msg for w in EFFECT_WORDS) and q:
            head, items = _split_bar(t)
            keep = [x for x in items if q.lower() not in x.lower()]
            if items and len(keep) < len(items):
                lines[i] = " " * _indent(line) + _join_bar(head, keep)
                return f"the effect '{', '.join(x for x in items if x not in keep)}' came off ({msg.split('.')[0]})"
            if re.match(r"(remember|forget)\s", t) or SC.TEXTS_RE.match(t):
                lines[i] = None
                return f"'{t}' came off ({msg.split('.')[0]})"
        if "keep it under" in msg:
            lim = int(re.search(r"under (\d+)", msg).group(1))
            # the long line is this one or one under it (the checker names the choice or scene it belongs to)
            span = range(i, _scene_end(lines, i) if is_scene else _block_end(lines, i))
            longest = max((k for k in span if lines[k] is not None), key=lambda k: len(lines[k].strip()), default=i)
            if len(lines[longest].strip()) > lim * 0.8:
                parts = _split_long(lines[longest], lim)
                if parts:
                    lines[longest] = "\n".join(parts)  # (split into lines when the script is put back together)
                    return "a long line was split in two"
            if is_scene:  # the scene's opening lines are too long all together: the last of them come off
                body = [k for k in span if k > i and lines[k] is not None and lines[k].strip() and _indent(lines[k]) == 0
                        and not lines[k].strip().startswith("*")]
                total = sum(len(lines[k]) for k in body)
                dropped = 0
                while body and total > lim * 0.95:
                    k = body.pop()
                    total -= len(lines[k])
                    lines[k] = None
                    dropped += 1
                if dropped:
                    return f"the scene's opening was too long: its last {dropped} line{'s' if dropped > 1 else ''} came off"
        if "isn't a kind of person a storyline can keep" in msg or "cast looks like" in msg or "already in the cast" in msg:
            lines[i] = None
            return f"a cast line came off ({msg.split('.')[0]}): its lines talk as a walk-on"
        if "there's no storyline called" in msg or "is itself an expansion" in msg:
            lines[i] = None
            return "expands: came off (that storyline isn't there): it's a storyline of its own"
        if "isn't a time a group chat can wait for" in msg and q:  # group chat crew, weekend, full moon: -> without it
            new = re.sub(r"\s*,\s*" + re.escape(q) + r"(?=\s*[,:])", "", line, count=1, flags=re.I)
            if new != line:
                lines[i] = new
                return f"'{q}' came off the group chat (it isn't a time the game knows)"
        if "isn't someone in this chat or something an effect changes" in msg and q:
            head, items = _split_bar(t)
            keep = [x for x in items if not re.match(re.escape(q) + r"\b", x.strip(), re.I)]
            if items and len(keep) < len(items):
                lines[i] = " " * _indent(line) + _join_bar(head, keep)
                return f"the effect '{', '.join(x for x in items if x not in keep)}' came off (it isn't something a group chat changes)"
        if "a reply ends with its tone" in msg:
            lines[i] = line.rstrip() + " (ok)"
            return "a reply without a tone got (ok)"
        if "a question ends with" in msg:
            lines[i] = line.rstrip() + " (open)"
            return "a question without its kind got (open)"
        return None
    if level == 1:
        if is_choice or "|" in t:
            head, items = _split_bar(t)
            if items:
                lines[i] = " " * _indent(line) + head
                return f"its effects came off ({msg.split('.')[0]})"
        if is_scene:
            new = _strip_tags(line)
            if new is not None:
                lines[i] = new
                return f"its tags came off ({msg.split('.')[0]})"
        return None
    # level 2: the line goes (with what's under it); a scene line takes its scene with it
    if SC.SECTION_RE.match(t):
        return None
    end = _scene_end(lines, i) if is_scene else _block_end(lines, i)
    for k in range(i, max(end, i + 1)):
        lines[k] = None
    return ("the scene came off" if is_scene else "the line came off") + f" ({msg.split('.')[0]})"


# ---------------------------------------------------------------------------------------- ChatGPT's habits, read as meant
ITALIC_RE = re.compile(r"^(\s*)(?:\*(?![\s*])(.+?)(?<![\s*])\*|_(?![\s_])(.+?)(?<![\s_])_)\s*$")  # *She smiles.*
BOLD_SPEAKER_RE = re.compile(r"^(\s*)\*\*([A-Za-z][\w .'-]{0,24}?)\s*:?\s*\*\*\s*:?\s*(.+)$")  # **Nicole:** hi
ARROW_FX_RE = re.compile(r"^(\s*\*{1,2}\s+.+?)\s+(?:->|→|=>)\s+(.+)$")  # * "Sure." -> nicole affection +
PAREN_FX_RE = re.compile(r"^(\s*\*{1,2}\s+.+?)\s*\(([^()]+)\)\s*$")  # * "Sure." (nicole affection +), if it reads as effects
LOOKS_FX_RE = re.compile(r"(^|\s)[+-]{1,3}(\s|$|,)|[+-]\d|(^|[\s,])[+-]{1,3}\s?[A-Za-z]|\bremember\b", re.I)
# inside a scene: choices and outcomes the way ChatGPT labels them
CHOICE_LABEL_RE = re.compile(r"^(\s*)(?:[-•]\s*)?(?:(?:choice|option)\s*#?\s*[0-9A-Da-d]{0,2}\s*[:.)\-–]|\(?[A-Da-d1-4]\))\s*(.+)$", re.I)
OUTCOME_RE = re.compile(r"^(\s*)(?:[-•]\s*)?(?:outcome|result|response|reaction|what happens)\s*[0-9A-Da-d]{0,2}\s*(?:\([^)]*\))?\s*:\s*(.+)$", re.I)
EITHER_RE = re.compile(r"^\s*(?:either way|whichever you pick(?:ed)?|no matter (?:what|which)(?: you pick(?:ed)?)?|afterwards?|"
                       r"after (?:either|any|all the|the) choices?)\s*[:.]?\s*$", re.I)


def _level(t: str) -> int:
    """1 for a choice (`* `), 2 for a choice inside a choice (`** `), 0 for anything else."""
    if t.startswith("** ") or t == "**":
        return 2
    return 1 if t.startswith("* ") or t == "*" else 0


def _is_choice(t: str) -> bool:
    return _level(t) > 0


def _fx_terms(s: str) -> str:
    """Effects the way ChatGPT writes them, the game's way: "+Nicole affection, -stress" -> "nicole affection +, stress -"."""
    out = []
    for term in re.split(r"\s*[,;]\s*|\s+and\s+", s.strip()):
        m = re.match(r"^([+-]{1,3}|[+-]\d+)\s*([A-Za-z][\w']*?)(?:'s)?(?:\s+([A-Za-z]+))?$", term)
        if m:
            term = " ".join(x.lower() for x in (m.group(2), m.group(3)) if x) + " " + m.group(1)
        out.append(term)
    return ", ".join(t for t in out if t)


def _fx_fix(ln: str):
    """A choice with its effects after an arrow or in parentheses -> effects after |. (None if there's nothing to fix.)"""
    t = ln.strip()
    if not _is_choice(t) or " | " in t:
        return None
    m = ARROW_FX_RE.match(ln)
    if not m:
        m = PAREN_FX_RE.match(ln)
        m = m if m and LOOKS_FX_RE.search(m.group(2)) else None  # ("(sarcastically)" stays part of what you say)
    return f"{m.group(1).rstrip()} | {_fx_terms(m.group(2))}" if m else None


def _scene_line(ln: str):
    """One line of a scene as ChatGPT labels it -> the game's way, and what was done (or None)."""
    m = CHOICE_LABEL_RE.match(ln)
    if m and m.group(2).strip():
        ln = f"{m.group(1)}* {m.group(2).strip()}"
        return (_fx_fix(ln) or ln), "a numbered or lettered choice (Choice 1:, Option A:, A)) became a choice (* )"
    m = OUTCOME_RE.match(ln)
    if m and m.group(2).strip():
        return f"{m.group(1)}{m.group(2).strip()}", "an Outcome: label came off (the line plays after its choice)"
    return ln, None


def _restage(body: list) -> tuple:
    """A scene's lines (each (text, origin)), with everything after a choice put where it plays:
    - the lines written right under a choice (flush left, down to the next choice) are that choice's;
    - `** ` choices come right after the choice above them;
    - talk after choices whose own lines are indented (or after an `either way:` line) follows whichever you pick,
      and a round of choices after that talk comes after each of the first ones.
    Returns (lines, what happened or None)."""
    lead = 0
    while lead < len(body) and not body[lead][0].strip():
        lead += 1
    real = [x for x in body if x[0].strip()]
    if not real:
        return body, None
    base = min(_indent(x[0]) for x in real)
    rel = [((x[0][base:] if x[0].strip() else ""), x[1]) for x in body[lead:]]  # (base indent off)
    items = []  # top-level lines with what's under them
    for x in rel:
        if x[0].strip() and _indent(x[0]) == 0:
            items.append([x])
        elif items:
            items[-1].append(x)
    kinds = ["e" if EITHER_RE.match(it[0][0]) else ("l", "c1", "c2")[_level(it[0][0].strip())] for it in items]
    if not any(k in ("c1", "c2") for k in kinds):
        return body, None
    first = next(i for i, k in enumerate(kinds) if k in ("c1", "c2"))
    rounds, shared = [[]], [[]]
    mode, marker, cur, sub = None, False, None, None
    used = set()
    for it, k in zip(items[first:], kinds[first:]):
        if k == "e":
            mode, marker, sub = "shared", True, None
            used.add("either")
            continue
        if k == "c1" or (k == "c2" and cur is None):
            if mode == "shared" and (shared[-1] or marker):
                rounds.append([])
                shared.append([])
                used.add("rounds")
            mode, marker, sub = None, False, None
            cur = {"head": it, "own": [], "subs": []}
            rounds[-1].append(cur)
        elif k == "c2":
            sub = {"head": it, "own": [], "subs": []}
            cur["subs"].append(sub)
            used.add("subs")
        elif mode == "shared":
            shared[-1].append(it)
        elif sub is not None:
            sub["own"].append(it)
            used.add("own")
        elif not any(x[0].strip() for ch in rounds[-1] for x in ch["head"][1:]):
            cur["own"].append(it)  # nothing indented under any choice here: the lines right under a choice are its own
            used.add("own")
        else:  # the choices have their lines indented under them: talk after them is for whichever you pick
            mode = "shared"
            shared[-1].append(it)
            used.add("shared")
    if not used:
        return body, None  # the usual: talk, then choices with what follows each indented under it

    def push(lines, by):
        return [((" " * by + x[0]) if x[0].strip() else x[0], x[1]) for x in lines]

    def emit(ch, cont):
        h = ch["head"]
        t = h[0][0].strip()
        out = [("* " + t[2:].lstrip() if _level(t) == 2 else h[0][0], h[0][1])] + h[1:]
        kids = [x for x in h[1:] if x[0].strip()]
        under = _indent(kids[0][0]) if kids else 4
        for it in ch["own"]:
            out += push(it, under)
        if ch["subs"]:
            for s_ in ch["subs"]:
                out += push(emit(s_, cont), under)
        elif cont:
            out += push(cont, under)
        return out

    def round_lines(r):
        cont = [x for it in shared[r] for x in it] + (round_lines(r + 1) if r + 1 < len(rounds) else [])
        out = []
        for ch in rounds[r]:
            out += emit(ch, cont)
        return out
    what = []
    if "own" in used:
        what.append("the lines written right under each choice now play after that choice")
    if "subs" in used:
        what.append("the ** choices now come right after the choice above them")
    if "shared" in used or "either" in used:
        what.append("the lines after the choices now follow whichever choice you pick")
    if "rounds" in used:
        what.append("a second round of choices now comes after each first choice")
    opening = body[:lead] + push([x for it in items[:first] for x in it], base)
    return opening + push(round_lines(0), base), "; ".join(what)


HEADER_RE = re.compile(r"^\s*(?:[#>\-•]+\s*)?\**_*\s*((?:flirt|group\s+chat)\b[^\n]*?)\s*_*\**\s*(:)?\s*_*\**\s*$", re.I)
SPEAKER_RE = re.compile(r"^(\s*)(dm\s+)?([A-Za-z][\w'.]*(?:\s[A-Za-z][\w'.]*)?)\s*:\s*(.*)$")


def _texting_header(ln: str):
    """`**flirt tease:**`, `### Flirt (tease)`, `- group chat crew, weekend:` -> the block header the game reads (or None)."""
    raw = ln.rstrip()
    if not raw.strip() or raw[:1] in (" ", "\t"):
        return None
    m = HEADER_RE.match(raw)
    if not m:
        return None
    decorated = raw.strip()[:1] in "#*>-•_" or raw.strip()[:2] == "**"
    if not (m.group(2) or decorated):
        return None  # a plain line that just starts with "flirt": not a header
    inner = re.sub(r"[()*_]", " ", m.group(1))
    inner = re.sub(r"\s+", " ", inner).strip().rstrip(":").strip()
    inner = re.sub(r"(?i)^flirt\s*[-–—:]\s*", "flirt ", inner)
    out = inner[0].lower() + inner[1:] + ":"
    return out if out != raw.strip() else None


def _group_names(block: list) -> tuple:
    """A group chat with people's names in it (Jake:, Tyler:) -> the roles the game casts (A:, B:, C:), everywhere in the
    block: who's talking, dm Jake:, effects (Jake +) and the names in what they say. (lines, what it did or None)"""
    from . import script as SC
    head = block[0][0].strip().lower()
    m = re.match(r"group\s+chat\s+([^,:]+)", head)
    chat = SC.GROUP_CHATS.get((m.group(1).strip() if m else ""), None)
    if chat not in ("crew", "team"):
        return block, None
    roles = SC.GROUP_ROLES[chat]
    names: dict = {}
    taken = set()  # the roles already speaking as themselves (A:, B:)
    for ln, _ in block[1:]:
        sm = SPEAKER_RE.match(ln) if not ln.strip().startswith("*") else None
        if sm and sm.group(3).strip().lower() in roles:
            taken.add(roles[sm.group(3).strip().lower()])
    for ln, _ in block[1:]:
        t = ln.strip()
        if t.startswith("*"):
            continue
        sm = SPEAKER_RE.match(ln)
        if not sm:
            continue
        who = sm.group(3).strip()
        if who.lower() in roles or who.lower() in ("me", "you", "i", "{me}") or len(who) == 1:
            continue  # (a role, me, or a letter the game doesn't have: that's left to the fixer)
        free = [r for r in ("A", "B", "C") if r not in taken and r not in names.values()]
        if who not in names and free:
            names[who] = free[0]
    if not names:
        return block, None
    out = []
    for ln, o in block:
        new = ln
        sm = SPEAKER_RE.match(ln) if not ln.strip().startswith("*") else None
        if sm and sm.group(3).strip() in names:
            new = f"{sm.group(1)}{sm.group(2) or ''}{names[sm.group(3).strip()]}: {sm.group(4)}"
        for nm, r in names.items():
            if " | " in new:  # effects: Jake + -> A +
                a, b = new.split(" | ", 1)
                b = re.sub(rf"\b{re.escape(nm)}\b", r, b)
                new = f"{a} | {b}"
            head_, sep, rest = new.partition(": ") if re.match(r"^\s*(dm\s+)?[A-Z]:\s", new) else ("", "", new)
            rest = re.sub(rf"\b{re.escape(nm)}\b", "{" + r + "}", rest)
            new = head_ + sep + rest
        out.append((new, o))
    return out, "the names in the group chat became A, B and C (the game picks who): " + ", ".join(f"{k} is {v}" for k, v in names.items())


# a template line left as it was: "<what happens after it>", "* \"<choice 3>\"", "* <choice 3> | ..."
PLACEHOLDER_RE = re.compile(r'^\s*(\*{1,2}\s*)?["“]?<[^<>]{1,80}>["”]?\s*(\|.*)?$')


def habits(src: str) -> tuple:
    """What ChatGPT often writes, the way it meant it: *narration in italics* and **Name:** in bold are plain lines, effects
    after an arrow or in parentheses go after |, and a scene's talk or choices after its choices go where they play.
    Returns (lines, origin: each line's number in what was pasted, notes)."""
    out, notes = [], []
    for n, ln in enumerate(src.split("\n"), start=1):
        if PLACEHOLDER_RE.match(ln):  # a line of the template ChatGPT left as it was ("<what happens after it>")
            notes.append({"line": n, "text": f"a template line left unfilled came out ({ln.strip()[:40]})"})
            continue
        h = _texting_header(ln)
        if h:
            notes.append({"line": n, "text": f"read '{ln.strip()}' as {h}"})
            ln = h
        t = ln.strip()
        m = BOLD_SPEAKER_RE.match(ln)
        if m:
            ln = f"{m.group(1)}{m.group(2).strip()}: {m.group(3).strip()}"
            notes.append({"line": n, "text": "a **bold** name became a plain speaker"})
        elif ITALIC_RE.match(ln) and " | " not in t and not _is_choice(t):
            m = ITALIC_RE.match(ln)
            ln = f"{m.group(1)}{(m.group(2) or m.group(3)).strip()}"
            notes.append({"line": n, "text": "*narration in italics* became a plain line (a * at the start is a choice)"})
        elif _fx_fix(ln):
            ln = _fx_fix(ln)
            notes.append({"line": n, "text": "the effects after an arrow (or in parentheses) went after |"})
        out.append((ln, n))
    # group chats with people's names: the roles the game casts
    i = 0
    while i < len(out):
        if re.match(r"(?i)^group\s+chat\b", out[i][0]):
            j = i + 1
            while j < len(out) and not (out[j][0][:1] not in (" ", "\t", "") and re.match(r"(?i)^(flirt|group\s+chat|texts?|chat|===|---)\b", out[j][0])):
                j += 1
            blk, what = _group_names(out[i:j])
            if what:
                out[i:j] = blk
                notes.append({"line": out[i][1], "text": what})
            i = j
        else:
            i += 1
    # scenes: what comes after the choices
    res, i = [], 0
    while i < len(out):
        t = out[i][0].strip()
        if SC.SCENE_RE.match(t):
            j = i + 1
            while j < len(out) and not (SC.SCENE_RE.match(out[j][0].strip()) or SC.SECTION_RE.match(out[j][0].strip())
                                        or (SC.BLOCK_RE.match(out[j][0].strip()) and _indent(out[j][0]) == 0)):
                j += 1
            body = []
            for ln, o in out[i + 1:j]:
                ln2, did = _scene_line(ln)
                if did:
                    notes.append({"line": o, "text": did})
                body.append((ln2, o))
            body, what = _restage(body)
            if what:
                notes.append({"line": out[i][1], "text": f"in this scene, {what}"})
            res.append(out[i])
            res += body
            i = j
        else:
            res.append(out[i])
            i += 1
    return [x[0] for x in res], [x[1] for x in res], notes


def repair(text: str, library=None, default_title: str = "Untitled", passes: int = 14) -> dict:
    """Compile the script, fixing what's broken until it compiles. {"text": the fixed script, "notes": [{"line", "text"}],
    "result": the compile, "ok": it compiled}. Notes use the line numbers of the script as pasted."""
    src0 = SC.extract(text).replace("\r\n", "\n")
    lines0, origin, notes = habits(src0)
    src = "\n".join(lines0)
    level: dict = {}  # (line text, problem) -> how far we've gone with it
    # (origin: each current line's number in the script as pasted)
    r = None
    for _ in range(passes):
        r = SC.compile_script(src, default_title=default_title, library=library)
        if not r["errors"]:
            if not r["packs"]:  # nothing left to add: say so instead of adding nothing
                r = {**r, "errors": [{"line": 1, "text": "there's nothing in that: no storyline, scene or lines the game can use"}]}
                return {"ok": False, "text": src, "notes": notes, "result": r, "origin": origin}
            return {"ok": True, "text": src, "notes": notes, "result": r, "origin": origin}
        lines = src.split("\n")
        by_line: dict = {}
        errors = r["errors"]
        if len(errors) > 1:  # "nothing in this pack" is because of the others: fix those first
            errors = [e for e in errors if "there's nothing in this pack" not in e["text"]] or errors
        for e in errors:
            by_line.setdefault(e["line"], []).append(e["text"])
        done_any = False
        for n in sorted(by_line, reverse=True):  # bottom up: a fix never moves the lines above it
            i = n - 1
            if not 0 <= i < len(lines) or lines[i] is None:
                continue
            for msg in by_line[n]:
                if lines[i] is None:
                    break
                key = (lines[i].strip(), msg)
                lv = level.get(key, 0)
                did = None
                while lv <= 2 and did is None:
                    did = _fix(lines, i, msg, lv)
                    if did is None:
                        lv += 1
                level[key] = lv + 1
                if did:
                    notes.append({"line": origin[i] if i < len(origin) else n, "text": did})
                    done_any = True
        if not done_any:
            break
        new_origin, out = [], []
        for k, ln in enumerate(lines):
            if ln is None:
                continue
            for piece in ln.split("\n"):
                out.append(piece)
                new_origin.append(origin[k] if k < len(origin) else k + 1)
        src, origin = "\n".join(out), new_origin
        r = None
    if r is None:  # (the last pass changed the script: its problems are the ones left in it now)
        r = SC.compile_script(src, default_title=default_title, library=library)
    return {"ok": not r["errors"] and bool(r["packs"]), "text": src, "notes": notes, "result": r, "origin": origin}
