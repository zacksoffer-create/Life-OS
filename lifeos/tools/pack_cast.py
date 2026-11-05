"""Lock a dialogue pack's scenes onto one named person (a cast slot), right in the JSON file.

    python lifeos/tools/pack_cast.py "Friday Nights.json" "Brothers Same Team.json" \\
        --slot lead_brother --who older_brother --sport basketball --grade-offset 3 \\
        --bond familiarity=95,affection=75,trust=75 --floor affection=55,trust=55

Every scene whose "who" is in --replace (default: older_sibling) becomes "who": "cast:<slot>", the pack gets a "cast"
section describing that person, and nothing else changes (ids, text, choices, remembered facts). Packs that use the same
--slot name get the same person in your story. Writes <file>.cast.json next to each file (or use --in-place), and checks
each result with the game's own pack checker.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from lifeos import dialogue  # noqa: E402


def levels(s):
    if not s:
        return None
    out = {}
    for part in s.split(","):
        k, _, v = part.partition("=")
        out[k.strip()] = float(v)
    return out


def main():
    ap = argparse.ArgumentParser(description="Lock a pack's scenes onto one named person (a cast slot).")
    ap.add_argument("packs", nargs="+")
    ap.add_argument("--slot", required=True, help="the person's slot name, e.g. lead_brother (same name = same person across packs)")
    ap.add_argument("--who", required=True, help="the kind of person, e.g. older_brother")
    ap.add_argument("--sport", help="they play this sport (basketball, football, baseball, soccer)")
    ap.add_argument("--grade-offset", type=int, help="grades ahead of you (3 = a senior when you're a freshman)")
    ap.add_argument("--bond", help="start at least this close, e.g. familiarity=95,affection=75,trust=75")
    ap.add_argument("--floor", help="never drop below this in these storylines, e.g. affection=55,trust=55")
    ap.add_argument("--bind", choices=["start", "first_scene"], help="bind when the story starts (or at their first scene)")
    ap.add_argument("--replace", default="older_sibling", help="comma-separated kinds to replace (default older_sibling)")
    ap.add_argument("--in-place", action="store_true")
    a = ap.parse_args()
    spec = {"who": a.who, "sport": a.sport, "grade_offset": a.grade_offset, "bond": levels(a.bond), "floor": levels(a.floor), "bind": a.bind}
    bad = 0
    for path in a.packs:
        with open(path, encoding="utf-8") as f:
            pack = json.load(f)
        new = dialogue.lock_cast(pack, a.slot, spec, [k.strip() for k in a.replace.split(",")])
        n = new.pop("_locked", 0)
        rep = dialogue.check(new)
        out = path if a.in_place else os.path.splitext(path)[0] + ".cast.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(new, f, indent=1, ensure_ascii=False)
        print(f"{pack.get('name') or path}: {n} scene(s) now about cast:{a.slot} -> {out}")
        if not rep["ok"]:
            bad += 1
            for e in rep["errors"]:
                print("   problem:", e)
        for wn in rep["warnings"][:5]:
            print("   note:", wn)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
