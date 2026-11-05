"""How people look: skin, hair, eyes, glasses. Used by the phone's portraits.

Generated looks come from a hash of the character id (no simulation randomness is used, so adding
looks never changes what happens). Families resemble each other: skin tone comes from the household,
and hair and eye color usually do. Anything set in the character builder overrides the generated value.
"""
from __future__ import annotations

import zlib

SKIN = ["porcelain", "fair", "light", "medium", "tan", "olive", "brown", "deep"]
HAIR_STYLES = ["buzz", "short", "crew", "side_part", "messy", "curly_short", "fade", "afro",
               "bob", "long_straight", "long_wavy", "ponytail", "bun", "curly_long", "braids", "locs", "bald"]
HAIR_COLORS = ["black", "dark_brown", "brown", "light_brown", "auburn", "red", "strawberry", "blonde", "platinum", "gray"]
EYES = ["dark_brown", "brown", "hazel", "green", "blue", "gray"]
FACIAL_HAIR = ["none", "stubble", "mustache", "goatee", "beard"]
FIELDS = {"skin": SKIN, "hair": HAIR_STYLES, "hair_color": HAIR_COLORS, "eyes": EYES, "facial_hair": FACIAL_HAIR}

_MASC = ["short", "crew", "side_part", "messy", "curly_short", "fade", "buzz", "afro", "locs"]
_FEM = ["long_straight", "long_wavy", "ponytail", "bun", "bob", "curly_long", "braids", "long_straight", "long_wavy"]


def _h(cid: str, key: str) -> int:
    return zlib.crc32(f"{cid}:{key}".encode())


def _pick(cid, key, options, weights=None):
    x = _h(cid, key) % 10000 / 10000
    if not weights:
        return options[int(x * len(options))]
    tot = sum(weights)
    acc = 0.0
    for o, wt in zip(options, weights):
        acc += wt / tot
        if x < acc:
            return o
    return options[-1]


def generated(c) -> dict:
    cid = c.id
    fam = getattr(c, "household_id", None)
    skin = _pick(fam or cid, "skin", SKIN, [6, 14, 16, 16, 12, 10, 14, 12])
    if fam and _h(cid, "skin-shift") % 6 == 0:  # siblings are close, not identical
        skin = SKIN[max(0, min(len(SKIN) - 1, SKIN.index(skin) + (1 if _h(cid, "dir") % 2 else -1)))]
    dark = SKIN.index(skin) >= 5
    if c.gender == "m":
        styles = _MASC
    elif c.gender == "f":
        styles = _FEM
    else:
        styles = ["short", "messy", "bob", "curly_short", "long_wavy", "side_part", "curly_long"]
    if not dark and SKIN.index(skin) <= 3:
        styles = [x for x in styles if x not in ("afro", "locs", "braids")]
    hair = _pick(cid, "hair", styles)
    if dark and hair in ("long_straight", "messy", "side_part") and _h(cid, "texture") % 3 == 0:
        hair = {"long_straight": "braids", "messy": "curly_short", "side_part": "fade"}[hair]
    color_w = [40, 30, 14, 6, 3, 1, 1, 4, 1, 0] if dark else [10, 22, 22, 14, 6, 4, 3, 15, 3, 1]
    age = c.age(0) if hasattr(c, "age") else 16
    hair_color = _pick(fam if fam and _h(cid, "fam-hair") % 10 < 7 else cid, "hair_color", HAIR_COLORS, color_w)
    if c.role == "staff" and _h(cid, "gray") % 3 == 0:
        hair_color = "gray"
    if c.role == "staff" and c.gender == "m" and _h(cid, "bald") % 5 == 0:
        hair = "bald"
    eyes = _pick(fam if fam and _h(cid, "fam-eyes") % 10 < 6 else cid, "eyes", EYES, [34, 22, 14, 8, 16, 6] if not dark else [60, 30, 8, 1, 1, 0])
    facial = "none"
    if c.gender == "m":
        if c.role == "staff":
            facial = _pick(cid, "facial", FACIAL_HAIR, [40, 15, 10, 15, 20])
        elif (c.grade or 0) >= 12 or c.role == "alumni":
            facial = _pick(cid, "facial", FACIAL_HAIR, [80, 15, 0, 3, 2])
    return {"skin": skin, "hair": hair, "hair_color": hair_color, "eyes": eyes, "facial_hair": facial,
            "glasses": _h(cid, "glasses") % 100 < (22 if c.role == "staff" else 14),
            "freckles": (not dark) and _h(cid, "freckles") % 100 < 12}


def resemble(c, anchor: dict) -> dict:
    """Family features for someone whose look is on auto, taken from a relative's chosen look (the protagonist's, in a story).
    Same odds as generated(): skin is shared (now and then a shade off), hair color usually, eye color often.
    Returns only the fields to set; anything the person already has chosen is left alone."""
    cid = c.id
    mine = {k: v for k, v in (getattr(c, "look", None) or {}).items() if v not in (None, "")}
    gen = generated(c)
    out = {}
    if anchor.get("skin") in SKIN and "skin" not in mine:
        skin = anchor["skin"]
        if _h(cid, "skin-shift") % 6 == 0:
            skin = SKIN[max(0, min(len(SKIN) - 1, SKIN.index(skin) + (1 if _h(cid, "dir") % 2 else -1)))]
        out["skin"] = skin
        if SKIN.index(skin) <= 3 and "hair" not in mine and gen["hair"] in ("afro", "locs", "braids"):
            pool = [x for x in (_MASC if c.gender == "m" else _FEM if c.gender == "f" else ["short", "messy", "bob", "long_wavy"]) if x not in ("afro", "locs", "braids")]
            out["hair"] = _pick(cid, "hair-light", pool)
    if anchor.get("hair_color") in HAIR_COLORS and "hair_color" not in mine and _h(cid, "fam-hair") % 10 < 7:
        out["hair_color"] = anchor["hair_color"]
    if anchor.get("eyes") in EYES and "eyes" not in mine and _h(cid, "fam-eyes") % 10 < 6:
        out["eyes"] = anchor["eyes"]
    return out


def look_of(c) -> dict:
    out = generated(c)
    out.update({k: v for k, v in (getattr(c, "look", None) or {}).items() if v not in (None, "")})
    return out


def validate(look, path, errors):
    if not look:
        return
    if not isinstance(look, dict):
        errors.append(f"{path}.look must be an object")
        return
    for k, v in look.items():
        if k in FIELDS:
            if v not in FIELDS[k]:
                errors.append(f"{path}.look.{k}: {v} isn't one of {', '.join(FIELDS[k])}")
        elif k in ("glasses", "freckles"):
            if not isinstance(v, bool):
                errors.append(f"{path}.look.{k} must be true or false")
        else:
            errors.append(f"{path}.look: unknown field {k}")
