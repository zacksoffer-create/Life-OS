"""A backup: your whole story in one .lifeos file, to move between the phone and the desktop (the lab), either way.

It's the world (everyone, everything that's happened) plus everything you wrote for it: your storylines, expansions and
texting (the script files), and which of them are switched off. Opening one anywhere puts those in that copy's library
too, so the story plays there the way it did where you made the backup.

The format: zlib-compressed JSON of the world, with the rest under "bundle". Copies of LIFE OS from before the bundle
existed still open these (they read the world and skip the rest), and a backup without a bundle opens here.
"""
from __future__ import annotations

import json
import os
import re
import zlib

from .release import RELEASE

MAX_FILE = 2_000_000  # (characters in one storyline file)
PACK_EXT = (".story", ".json")


def _pack_files() -> list:
    from . import dialogue
    d = dialogue.USER_DIR
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.startswith(".") or fn == "state.json" or not fn.endswith(PACK_EXT):
            continue
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                out.append({"file": fn, "text": f.read()})
        except (OSError, UnicodeDecodeError):
            continue
    return out


def bundle() -> dict:
    """Everything you wrote, and which version of LIFE OS made the backup."""
    from . import dialogue
    from .local_api import engine_build
    files = _pack_files()
    ids = {f"yours:{f['file'].rsplit('.', 1)[0]}" for f in files}
    off = [x for x in dialogue._state().get("disabled", []) if x in ids]
    return {"v": 1, "release": RELEASE, "engine": engine_build(), "packs": files, "disabled": off}


def make(w) -> bytes:
    """The backup file for this world."""
    d = w.to_dict()
    d["bundle"] = bundle()
    return zlib.compress(json.dumps(d, separators=(",", ":")).encode("utf-8"), 6)


def wrap(world_bytes: bytes) -> bytes:
    """A saved world (as the lab keeps it) as a backup file: with everything you wrote."""
    d = json.loads(zlib.decompress(world_bytes).decode("utf-8"))
    d["bundle"] = bundle()
    return zlib.compress(json.dumps(d, separators=(",", ":")).encode("utf-8"), 6)


def read(data: bytes):
    """A backup (or a plain saved world, compressed or as JSON) -> (world, bundle or None). ValueError if it isn't one."""
    from .model import World
    try:
        d = json.loads(zlib.decompress(data).decode("utf-8"))
    except Exception:  # noqa: BLE001
        try:
            d = json.loads(data.decode("utf-8-sig"))
        except Exception:  # noqa: BLE001
            raise ValueError("That file isn't a LIFE OS backup.")
    if not isinstance(d, dict) or not isinstance(d.get("chars"), list):
        raise ValueError("That file isn't a LIFE OS backup.")
    b = d.pop("bundle", None)
    try:
        w = World.from_dict(d)
    except Exception:  # noqa: BLE001
        raise ValueError("That backup is damaged: the story in it can't be read.")
    if w.history is None:
        from .history import History
        w.history = History()
    return w, (b if isinstance(b, dict) else None)


def newer_note(b: dict | None) -> str | None:
    """If the backup came from a newer LIFE OS than this one: say so, and what to do."""
    rel = str((b or {}).get("release") or "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", rel) and rel > RELEASE:
        return (f"This backup is from a newer LIFE OS ({rel}) than this copy ({RELEASE}). It's loaded, but anything newer "
                "than this copy won't show here: get the latest desktop version (the link is on your phone: Me tab, under "
                "\"See it on a computer\") and load it again there.")
    return None


def install(b: dict | None) -> dict:
    """Put what a backup carries into this copy's library: a storyline it doesn't have is added; one it has in another
    version becomes the backup's (the one it replaces is kept under older versions); the same file is left alone. Which ones
    are switched off follows the backup. {"added", "updated", "same"}"""
    from . import dialogue
    out = {"added": 0, "updated": 0, "same": 0}
    if not b:
        return out
    os.makedirs(dialogue.USER_DIR, exist_ok=True)
    ids = set()
    for p in b.get("packs") or []:
        if not isinstance(p, dict):
            continue
        fn = os.path.basename(str(p.get("file") or ""))
        text = p.get("text")
        if not fn or fn.startswith(".") or fn == "state.json" or not fn.endswith(PACK_EXT) or not isinstance(text, str) \
                or len(text) > MAX_FILE:
            continue
        ids.add(f"yours:{fn.rsplit('.', 1)[0]}")
        path = os.path.join(dialogue.USER_DIR, fn)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    if f.read() == text:
                        out["same"] += 1
                        continue
            except (OSError, UnicodeDecodeError):
                pass
            dialogue._backup(path, "replaced by a backup")
            out["updated"] += 1
        else:
            out["added"] += 1
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    st = dialogue._state()
    off = {x for x in b.get("disabled") or [] if x in ids}
    st["disabled"] = sorted((set(st.get("disabled", [])) - ids) | off)
    dialogue._save_state(st)
    dialogue.reload()
    return out


def summary(got: dict) -> str:
    """"2 storylines added, 1 updated" (or "")."""
    bits = [f"{got[k]} {w}" for k, w in (("added", "added"), ("updated", "updated")) if got.get(k)]
    return ("Storylines and texting: " + ", ".join(bits) + ".") if bits else ""
