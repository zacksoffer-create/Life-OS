"""Fix or change a storyline you already have, without writing it again.

- What's broken: every scene that never asks you anything (no choices, or one), a choice with nothing after it, a choice
  a later scene needs that isn't there. One ChatGPT prompt holds just those scenes, as they are now, with what's wrong.
- Change something: say what ("make Danny a role", "move it to junior year"); the prompt has the storyline as it is and
  asks for only the cast lines and scenes that change (so a long storyline never gets cut off).
- Paste the reply back: each scene replaces the one with its number (or title) in place, cast and years lines replace
  theirs, and a scene that still can't go in stays as it was. The version before is kept: undo puts it back.
- Who's in it: a cast line switched between one set person and a role, by the game, no ChatGPT needed.
"""
from __future__ import annotations

import difflib
import re

from . import dialogue as D
from . import script as SC

HEAD_KEYS = ("cast", "years", "when", "order")
ROLES = ("friend", "teammate", "classmate", "ex", "coach", "older brother", "older sister", "younger brother", "younger sister",
         "older sibling", "younger sibling", "brother", "sister", "sibling", "twin")
CAST_RE = re.compile(r"^\s*cast:\s*([\w-]+)\s*=\s*(.+?)\s*$", re.I)


def _blocks(lines: list) -> tuple:
    """(the lines before the first scene, [each scene's lines, its --- line first])"""
    head, out, cur = [], [], None
    for ln in lines:
        if SC.SCENE_RE.match(ln.strip()):
            cur = [ln]
            out.append(cur)
        elif cur is None:
            head.append(ln)
        else:
            cur.append(ln)
    for b in out:
        while len(b) > 1 and not b[-1].strip():
            b.pop()
    return head, out


def _key(header: str) -> tuple:
    """A --- line -> (its outline number or None, its title)"""
    t = SC.SCENE_RE.match(header.strip()).group(1)
    t = re.sub(r"\s*(\[.*|#[a-z].*)$", "", t).strip()
    m = re.match(r"(?:scene\s*|chapter\s*|#)?(\d+)\s*[.):\-]\s*(.+)$", t, re.I)
    return (int(m.group(1)), m.group(2).strip()) if m else (None, t)


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _warn(w) -> str:
    return f"line {w['line']}: {w['text']}" if isinstance(w, dict) else str(w)


def cast_view(p: dict) -> list:
    out = []
    for ln in p["script"].split("\n"):
        if SC.SCENE_RE.match(ln.strip()):
            break
        m = CAST_RE.match(ln)
        if m:
            try:
                spec = SC.cast_spec(m.group(2))
            except Exception:  # noqa: BLE001
                spec = {}
            out.append({"name": m.group(1).lower(), "value": m.group(2), "named": spec.get("who") == "named"})
    return out


def problems(pid: str) -> dict:
    """{pack, name, outlined, scenes: [{key, n, title, problems, src}], warnings, cast}"""
    p = D._script_pack(pid)
    pack = p["pack"]
    ents = SC.outline_entries(pack)
    by_sid = {e.get("sid"): e for e in ents if e.get("written")}
    gaps = {g["n"]: g["problems"] for g in D._gaps_of(p, [e["n"] for e in ents if e.get("written")])} if ents else {}
    _, blocks = _blocks(p["script"].rstrip("\n").split("\n"))
    src_by = {}
    for b in blocks:
        n, t = _key(b[0])
        src_by[n if ents and n is not None else _norm(t)] = "\n".join(b)
    out = []
    for sc in pack.get("scenes") or []:
        if not isinstance(sc, dict):
            continue
        e = by_sid.get(sc.get("id"))
        if e:
            probs = gaps.get(e["n"], [])
        else:
            q = SC.no_question(sc)
            probs = ([q] if q else []) + SC.choice_gaps(sc)
        if probs:
            title = e["title"] if e else sc.get("title") or ""
            src = src_by.get(e["n"] if e else _norm(title)) or (sc.get("src") or "").strip()
            out.append({"key": str(e["n"]) if e else title, "n": e["n"] if e else None, "title": title, "problems": probs, "src": src})
    return {"pack": pid, "name": pack.get("name") or pid, "outlined": bool(ents), "scenes": out,
            "scene_count": sum(1 for sc in pack.get("scenes") or [] if isinstance(sc, dict)),
            "warnings": [_warn(w) for w in (p["check"].get("warnings") or [])][:12], "cast": cast_view(p),
            "can_undo": can_undo(pid), "roles": list(ROLES)}


def _head_text(p: dict) -> str:
    head, _ = _blocks(p["script"].rstrip("\n").split("\n"))
    keep = [ln for ln in head if not re.match(r"^\s*(outline:|\d+\.\s)", ln, re.I)]
    return "\n".join(keep).strip()


RULES = """- ONE code block (```) holding just those scenes, nothing after the block. Each starts with its `---` line exactly as it \
is now (same number, same title).
- Keep what works: the same people, the same story, the lines that are fine. Fix what's listed.
- Every scene ends on a question (someone asks me something, or it's my move), then 2 to 4 choices, with what happens after \
EVERY choice. A scene with no choices, or only one, isn't fixed.
- `* ` starts a choice; the lines after it, down to the next `* `, are what happens after it. `** ` is a choice inside the \
choice above it. `either way:` on its own line: what follows plays whichever I picked.
- Effects go after `|` on a choice (`* "Front row." | nicole affection +`). Narration is a plain line: no *italics*, no \
**bold** names, no "Choice 1:" or "Outcome:" labels.
- If they don't all fit in one reply, send fewer: never cut a scene short. I'll ask for the rest."""

INTRO = ("LIFE OS is a life-simulation game: I play one person from high school in Guilford, Connecticut, fall 2010, "
         "through college. Storylines are written in its story script format (the guide is at the end).")


def fix_prompt(pid: str, only: list | None = None) -> str:
    """Just the broken scenes, as they are now, with what's wrong with each, and how to send them back."""
    pr = problems(pid)
    scenes = [s for s in pr["scenes"] if not only or s["key"] in only]
    if not scenes:
        return ""
    p = D._script_pack(pid)
    L = [f"Some scenes in one of my LIFE OS storylines are broken. Fix just these {len(scenes)} and send them back. {INTRO}", "",
         "## The storyline", "", "```", _head_text(p), "```", "", "## What's broken", ""]
    for s in scenes:
        L.append(f"{'Scene ' + str(s['n']) + ' (' + s['title'] + ')' if s['n'] else s['title']}:")
        L += [f"- {x}" for x in s["problems"]]
        L.append("")
    L += ["## The scenes as they are now", "", "```", "\n\n".join(s["src"] for s in scenes), "```", "",
          "## How to send them back", "", RULES, "", SC.guide_scenes()]
    return "\n".join(L)


def change_prompt(pid: str, ask: str) -> str:
    """The storyline as it is, what you want changed, and: send back only the lines and scenes that change."""
    ask = (ask or "").strip()
    if not ask:
        raise ValueError("say what you want changed")
    pr = problems(pid)
    p = D._script_pack(pid)
    body = re.sub(r"(?ms)^\s*outline:.*?(?=^---)", "", p["script"]).strip()
    L = [f"I want to change one of my LIFE OS storylines. {INTRO}", "", "## What I want changed", "", ask, "",
         "## The storyline as it is now", "", "```", body, "```", ""]
    if pr["scenes"]:
        L += ["## While you're at it, these scenes are broken (fix them too)", ""]
        for s in pr["scenes"]:
            L.append(f"- {'Scene ' + str(s['n']) + ' (' + s['title'] + ')' if s['n'] else s['title']}: " + "; ".join(s["problems"]))
        L.append("")
    L += ["## How to send it back", "",
          "- ONE code block. First, only the top lines that change (a `cast:` line, `years:`, `when:`), each written out "
          "whole. Then only the scenes that change, each starting with its `---` line exactly as it is now and written "
          "complete, first line to last. Leave out everything that stays the same.",
          "- Don't add or remove scenes, and don't change any `---` line: numbers and titles stay as they are.",
          "- To make someone a role instead of one set person, change their cast line, not their lines: `cast: danny = "
          "friend, guy` instead of `cast: danny = Danny Russo` (they still talk as `danny:`). Roles: " + ", ".join(ROLES)
          + "; or someone in another person's life: `friend of sis`, `best friend of mike`, `teammate of mike`, "
          "`girlfriend of mike`. Add `girl` / `guy`, `plays <sport>`, `close`, `2 years older` if it matters.",
          "- To make a role one set person, put their full name: `cast: danny = Danny Russo`.",
          RULES.split("\n", 1)[1], "", SC.guide_scenes()]
    return "\n".join(L)


def _apply_head(head: list, rhead: list) -> tuple:
    """The storyline's top lines with the reply's cast / years / when lines put in. (new head, [changed lines])"""
    new, changed = list(head), []
    for ln in rhead:
        t = ln.strip()
        m = re.match(r"^(%s)\s*:\s*(.+)$" % "|".join(HEAD_KEYS), t, re.I)
        if not m:
            continue
        key = m.group(1).lower()
        t = f"{key}: {m.group(2).strip()}"
        if key == "cast":
            cm = CAST_RE.match(t)
            if not cm:
                continue
            t = f"cast: {cm.group(1).lower()} = {cm.group(2)}"
            i = next((k for k, x in enumerate(new) if (c2 := CAST_RE.match(x)) and c2.group(1).lower() == cm.group(1).lower()), None)
        else:
            i = next((k for k, x in enumerate(new) if re.match(rf"^\s*{key}\s*:", x, re.I)), None)
        if i is None:
            at = [k for k, x in enumerate(new) if re.match(r"^\s*(===|cast|years|when|expands)\b", x, re.I)]
            new.insert((at[-1] + 1) if at else len(new), t)
        elif new[i].strip() == t:
            continue
        else:
            new[i] = t
        changed.append(t)
    return new, changed


def _ok(text: str) -> tuple:
    from . import scriptfix
    fx = scriptfix.repair(text, library=D.library())
    return fx["ok"], [_warn(e) for e in fx["result"]["errors"]]


def apply(pid: str, text: str) -> dict:
    """Put a reply in: cast / years lines and scenes replace theirs, in place. A scene that still can't go in stays as it
    was (and says why). {ok, replaced, skipped, head, notes, still, fix_prompt, undo}"""
    p = D._script_pack(pid)
    ents = SC.outline_entries(p["pack"])
    rhead, rblocks = _blocks(SC.extract(text or "").replace("\r\n", "\n").split("\n"))
    head, blocks = _blocks(p["script"].rstrip("\n").split("\n"))
    new_head, changed = _apply_head(head, rhead)
    if not rblocks and not changed:
        return {"ok": False, "errors": ["there are no scenes or cast lines in that: scenes start with their --- line, "
                                        "exactly as it is in the storyline"]}
    undo = _keep_for_undo(pid, p["script"])
    notes, skipped, replaced = [], [], []
    if changed:
        trial = "\n".join(new_head + [ln for b in blocks for ln in [""] + b]) + "\n"
        ok, errs = _ok(trial)
        if ok:
            r = D.add_script(trial, into=pid)
            if not r["ok"]:
                ok, errs = False, r["errors"]
        if not ok:
            skipped.append({"title": "The top lines (" + ", ".join(changed) + ")", "problems": errs[:4]})
            changed = []
    if rblocks and ents:
        r = D.merge_scenes(pid, "\n\n".join("\n".join(b) for b in rblocks))
        if not r.get("ok"):
            skipped += [{"title": f"Scene {s['n']} ({s['title']})", "problems": s["problems"]} for s in r.get("skipped") or []]
            if not r.get("skipped"):
                skipped.append({"title": "Those scenes", "problems": r.get("errors", [])[:4]})
        else:
            titles = {e["n"]: e["title"] for e in ents}
            replaced += [f"Scene {n} ({titles.get(n, '')})" for n in r.get("got", [])]
            skipped += [{"title": f"Scene {s['n']} ({s['title']})", "problems": s["problems"]} for s in r.get("skipped") or []]
            notes += r.get("notes", [])
    elif rblocks:
        p = D._script_pack(pid)
        head, blocks = _blocks(p["script"].rstrip("\n").split("\n"))
        names = [_norm(_key(b[0])[1]) for b in blocks]
        cur = [list(b) for b in blocks]
        for nb in rblocks:
            t = _key(nb[0])[1]
            k = _norm(t)
            i = names.index(k) if k in names else None
            if i is None:
                near = difflib.get_close_matches(k, names, n=1, cutoff=0.8)
                i = names.index(near[0]) if near else None
            if i is None:
                skipped.append({"title": t, "problems": ["there's no scene called that in this storyline (here, scenes keep "
                                                         "their titles: copy the --- line exactly)"]})
                continue
            nb = [blocks[i][0]] + nb[1:]  # (its --- line as it is: the scene keeps its title and tags)
            trial = cur[:i] + [nb] + cur[i + 1:]
            ok, errs = _ok("\n".join(head + [ln for b in trial for ln in [""] + b]) + "\n")
            if ok:  # a scene that still never asks you anything can't go in: it stays as it was
                _, left = D.drop_unasked("\n".join(head + [""] + nb) + "\n", only={D._title_key(_key(nb[0])[1])})
                if left:
                    ok, errs = False, left[0]["problems"]
            if ok:
                cur = trial
                replaced.append(_key(blocks[i][0])[1])
            else:
                skipped.append({"title": t, "problems": errs[:4] or ["it couldn't go in"]})
        if replaced:
            r = D.add_script("\n".join(head + [ln for b in cur for ln in [""] + b]) + "\n", into=pid)
            if not r["ok"]:
                return {"ok": False, "errors": r["errors"][:6], "undo": undo}
            notes += [D._note_text(n) for n in r.get("notes", [])]
    after = problems(pid)
    return {"ok": bool(replaced or changed), "replaced": replaced, "head": changed, "skipped": skipped, "notes": notes[:20],
            "still": [{"key": s["key"], "n": s["n"], "title": s["title"], "problems": s["problems"]} for s in after["scenes"]],
            "fix_prompt": fix_prompt(pid) if after["scenes"] else "", "undo": undo,
            "errors": [] if (replaced or changed) else [x for s in skipped for x in s["problems"]][:6]}


def _undo_path(pid: str) -> str:
    import os
    return os.path.join(D._history_dir(), os.path.basename(D._script_path(pid))[:-6] + "~undo.story")


def _keep_for_undo(pid: str, text: str) -> bool:
    """The storyline as it was before this paste, kept on its own (not one of the older versions, which a long merge can
    push out)."""
    import os
    path = _undo_path(pid)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def can_undo(pid: str) -> bool:
    import os
    return os.path.exists(_undo_path(pid))


def undo(pid: str) -> dict:
    """Put back the version from before the last Fix or change it (what's there now becomes an older version)."""
    import os
    path = _undo_path(pid)
    if not os.path.exists(path):
        raise KeyError(pid)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    r = D.add_script(text, into=pid)
    if not r["ok"]:
        raise ValueError(r["errors"][0])
    os.remove(path)
    return problems(pid)


def set_cast(pid: str, name: str, value: str) -> list:
    """One cast line, switched (a set person <-> a role, or anything about them), saved if the storyline still checks."""
    value = (value or "").strip()
    if not value:
        raise ValueError("say who they are: a name, or a role like friend, guy")
    p = D._script_pack(pid)
    head, blocks = _blocks(p["script"].rstrip("\n").split("\n"))
    i = next((k for k, x in enumerate(head) if (m := CAST_RE.match(x)) and m.group(1).lower() == name.lower()), None)
    if i is None:
        raise KeyError(name)
    head[i] = f"cast: {name.lower()} = {value}"
    text = "\n".join(head + [ln for b in blocks for ln in [""] + b]) + "\n"
    from . import scriptfix
    fx = scriptfix.repair(text, library=D.library())
    bad = [e for e in fx["result"]["errors"]]
    line_of = i + 1
    if bad or not fx["ok"]:
        raise ValueError(next((e["text"] for e in bad if e.get("line") == line_of), _warn(bad[0]) if bad else "that doesn't work"))
    D._backup(D._script_path(pid), "before a cast change")
    r = D.add_script(text, into=pid)
    if not r["ok"]:
        raise ValueError(r["errors"][0])
    return cast_view(D._script_pack(pid))
