"""The character worksheet: an Excel file (and a guide for talking it through with an AI) that becomes a story.

Fill in as much or as little as you like. Blank cells are generated from the person's type, exactly
like leaving a slider on auto in the builder. Import the file in the story setup (Load a cast file)
or turn the guide's JSON output into a cast file.

Layout: every person is a column, every field is a row. Column A holds the field code the importer
reads (don't change it), column B the field name, column C what it means and what's allowed.
"""
from __future__ import annotations

import io
import json
import re

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from . import appearance
from .story import COACHABLE
from .catalogs import APTITUDES, ATTRIBUTE_DOCS, MOTIVES, TRAITS, Catalogs

GREEN = "1F6B3A"
HEAD = PatternFill("solid", fgColor=GREEN)
SECTION = PatternFill("solid", fgColor="DDEFE3")
INPUT = PatternFill("solid", fgColor="FFFDF4")
THIN = Side(style="thin", color="C9D6CC")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
N_SIBS, N_PEOPLE = 4, 30



PROGRAM_COLS = [("football", "football"), ("basketball", "men's basketball"), ("basketball_w", "women's basketball"),
                ("baseball", "baseball"), ("softball", "softball"), ("soccer", "men's soccer"), ("soccer_w", "women's soccer")]


def side_strengths(c, sport) -> str:
    """'men's 70, women's 62' or 'program strength 90'."""
    keys = [k for k in c["programs"] if (k[:-2] if k.endswith("_w") else k) == sport]
    if len(keys) == 1:
        return f"program strength {c['programs'][keys[0]]}"
    return ", ".join(f"{'women' if k.endswith('_w') else 'men'}'s {c['programs'][k]}" for k in sorted(keys))

def _people_fields(cat: Catalogs, kind: str) -> list:
    """(code, label, help, validation) rows. validation: ('list', [...]) | ('ref', name) | ('num', lo, hi) | None."""
    sp = cat.sports["sports"]
    arch = [a["id"] for a in cat.people["archetypes"]]
    rows = [("#", "WHO THEY ARE", "", None),
            ("first", "First name", "Required. Leave the whole column blank to skip this person.", None),
            ("last", "Last name", "Blank: the family name (siblings) or a generated one.", None),
            ("gender", "Gender", "m, f or nb", ("list", ["m", "f", "nb"])),
            ("pronouns", "Pronouns", "Optional, e.g. she/her", None),
            ("attracted_to", "Attracted to", "Any of m, f, nb, comma separated (e.g. f or m,f). Blank = generated.", None)]
    if kind != "staff":
        if kind == "you":
            rows.append(("grade", "Grade on day one", "9, 10, 11 or 12 (you usually start as a freshman)", ("list", ["9", "10", "11", "12"])))
        else:
            rows.append(("grade", "Grade on day one", "9, 10, 11 or 12. Younger? 8, 7 or 6: still in middle school, they start high school "
                         "as a freshman 1, 2 or 3 years in, with that year's class.", ("list", ["9", "10", "11", "12", "8", "7", "6"])))
    rows += [("birthday", "Birthday", "Month/day, e.g. 4/12", None),
             ("archetype", "Starting type", "Fills every blank number with that type's typical values. See Reference.", ("ref", "archetypes")),
             ("bio", "A line about them", "Optional. Up to 500 characters.", None)]
    if kind == "people":
        rows += [("role", "Role", "student (default) or staff (a coach or teacher)", ("list", ["student", "staff"])),
                 ("title", "Staff title", "Staff only: Coach, Mr., Ms., Dr.", None),
                 ("role_label", "Staff job", "Staff only, e.g. Varsity baseball coach", None),
                 ("coach_of", "Coaches", "Staff only, a team: football, basketball (boys), basketball_girls, baseball, softball, "
                  "soccer (boys) or soccer_girls", ("list", list(COACHABLE)))]
    if kind in ("sibling", "people"):
        rows += [("#", "YOU TWO", "", None),
                 ("rel_type", "How they relate to you", "From their side. See Reference: relationship types." + (" Siblings default to sibling." if kind == "sibling" else ""), ("ref", "relationships")),
                 ("rel_strength", "How strong", "-40 (much weaker) to 40 (much stronger). 0 = typical.", ("num", -40, 40))]
        if kind == "sibling":
            rows.append(("twin_of", "Twin of", "me, or another sibling's column code (S1-S4). Twins share a birthday and grade.", None))
        else:
            rows.append(("household", "Lives with", "Blank = their own family. 'family' = they live with you (like a sibling).", ("list", ["family"])))
    rows += [("#", "LOOK", "Blank = generated. Pick from the lists.", None)]
    for k, opts in appearance.FIELDS.items():
        rows.append((f"look:{k}", k.replace("_", " ").capitalize(), ", ".join(opts), ("ref", f"look_{k}")))
    rows += [("look:glasses", "Glasses", "yes or no", ("list", ["yes", "no"])), ("look:freckles", "Freckles", "yes or no", ("list", ["yes", "no"]))]
    if kind != "staff":
        rows += [("#", "ATHLETE", "", None),
                 ("height_ft", "Height (feet)", "e.g. 5", ("num", 4, 7)), ("height_in", "Height (inches)", "e.g. 10  (so 5 and 10 = 5'10\")", ("num", 0, 11)),
                 ("build", "Build", "slight, average, athletic or strong", ("list", ["slight", "average", "athletic", "strong"])),
                 ("jersey", "Jersey number", "0-99", ("num", 0, 99))]
        for s, v in sp.items():
            rows.append((f"pos:{s}", f"{v['label']} position", ", ".join(f"{k} ({lab})" for k, lab in v["positions"].items()), ("ref", f"pos_{s}")))
    for layer, keys, title in (("traits", TRAITS, "PERSONALITY (0-100)"), ("aptitudes", APTITUDES, "NATURAL TALENT (0-100)"), ("motives", MOTIVES, "WHAT DRIVES THEM (0-100)")):
        if kind == "staff" and layer != "traits":
            continue
        rows.append(("#", title, ATTRIBUTE_DOCS[layer]["about"], None))
        for k in keys:
            rows.append((f"{layer}:{k}", k.capitalize(), ATTRIBUTE_DOCS[layer]["items"].get(k, ""), ("num", 0, 100)))
    if kind != "staff":
        rows.append(("#", "INTERESTS (0-100)", "How much they're into each thing. 80+ = a big part of who they are. Blank = from their type.", None))
        for s in cat.world["skills"]:
            rows.append((f"interest:{s['id']}", s["label"], "", ("num", 0, 100)))
        for hb in cat.world["hobbies"]:
            rows.append((f"interest:{hb['id']}", hb["label"].capitalize(), "hobby", ("num", 0, 100)))
        rows.append(("#", "STARTING SKILLS (0-100)", "How good they are on day one. A typical freshman is 25-50 in a sport; varsity seniors 55-75.", None))
        for s in cat.world["skills"]:
            rows.append((f"skill:{s['id']}", s["label"], "", ("num", 0, 100)))
    if kind in ("sibling", "people"):
        rows += [("#", "AFTER HIGH SCHOOL", "", None),
                 ("path", "Their path", "Blank = let it play out. 'work' = stay in town. Or a college (uconn) or college:sport (uconn:basketball). See Reference.", ("ref", "paths"))]
    return rows


def build_workbook(cat: Catalogs | None = None) -> bytes:
    cat = cat or Catalogs()
    wb = Workbook()
    _start_sheet(wb.active, cat)
    ref = wb.create_sheet("Reference")
    ranges = _reference_sheet(ref, cat)
    _story_sheet(wb.create_sheet("Story & Family", 1), cat)
    _people_sheet(wb.create_sheet("You", 2), cat, "you", ["me"], ranges)
    _people_sheet(wb.create_sheet("Siblings", 3), cat, "sibling", [f"S{i + 1}" for i in range(N_SIBS)], ranges)
    _people_sheet(wb.create_sheet("Your People", 4), cat, "people", [f"P{i + 1}" for i in range(N_PEOPLE)], ranges)
    _extra_sheet(wb.create_sheet("Extra Relationships", 5), cat, ranges)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _start_sheet(ws, cat):
    ws.title = "Start Here"
    town = cat.world["town"]["name"]
    lines = [
        ("LIFE OS character worksheet", True),
        ("", False),
        (f"Plan your story before you build it: you, your family and the people you want in your life in {town}.", False),
        ("", False),
        ("How to use it", True),
        ("1. Fill in what you know. Every blank is generated from the person's type, so a first name and a type is enough.", False),
        ("2. 'You' is your character. 'Siblings' has a column per brother or sister (S1-S4). 'Your People' has 30 columns (P1-P30).", False),
        ("3. Dropdowns and number limits show what's allowed. The Reference tab explains every type, trait, position and college.", False),
        ("4. In the app: My Story, then Start your story, then 'Load a cast file', and pick this .xlsx. Everything lands in the builder,", False),
        ("   where you can still change anything before you start.", False),
        ("", False),
        ("Talking it through first", True),
        ("Not sure about the numbers? Open the worksheet guide (character-worksheet-guide.md, also in the app's story setup).", False),
        ("It has a prompt you can paste into ChatGPT or Claude: it interviews you about each person, explains the trade-offs,", False),
        ("and gives you back a cast file the app loads directly. You can also just describe people here and fill numbers in later.", False),
        ("", False),
        ("Rules of thumb", True),
        ("- 50 is average for every 0-100 number. 70+ stands out, 85+ is rare. Nobody should be 90+ at everything.", False),
        ("- Talent (aptitude) is the ceiling. Skills are where they start. Discipline decides how fast they climb.", False),
        ("- Interests decide what they choose to do with their time. A 3-sport athlete wants 75+ in all three sports.", False),
        ("- Relationships are written from the other person's side: 'crush' on Sophie's column means Sophie has a crush on you.", False),
        ("- Don't edit column A (the field codes). The importer reads them.", False),
    ]
    for i, (t, bold) in enumerate(lines, 1):
        c = ws.cell(row=i, column=1, value=t)
        c.font = Font(bold=bold, size=16 if i == 1 else 12 if bold else 11, color=GREEN if bold else "222222")
    ws.column_dimensions["A"].width = 130


def _story_sheet(ws, cat):
    ws.title = "Story & Family"
    styles = cat.people["guardian_styles"]
    rows = [("#", "STORY", "", None),
            ("title", "Story title", "e.g. The Soffer Years", None),
            ("students_per_grade", "Students per grade", "6-40. Generated classmates fill each grade around your people. 12-20 plays smoothly on a phone.", ("num", 6, 40)),
            ("gen_seed", "World seed", "Optional number. Same setup + same seed = the same town.", None),
            ("#", "YOUR FAMILY", "", None),
            ("family_last", "Family last name", "Blank = your last name", None),
            ("guardian1", "Parent / guardian 1", "First name is fine (e.g. Linda)", None),
            ("guardian2", "Parent / guardian 2", "Optional", None),
            ("style", "How they parent", ", ".join(f"{s['id']} ({s['label']})" for s in styles), ("list", [s["id"] for s in styles])),
            ("income", "Money at home", "low, middle or high", ("list", ["low", "middle", "high"])),
            ("pet", "Family pet", "none, chance, dog, cat or rabbit", ("list", ["none", "chance", "dog", "cat", "rabbit"])),
            ("pet_name", "Pet's name", "If you picked a species", None)]
    _form(ws, rows, ["Value"], {})


def _form(ws, rows, cols, ranges):
    widths = {"A": 18, "B": 26, "C": 70}
    ws.cell(row=1, column=1, value="code").font = Font(bold=True, color="FFFFFF")
    ws.cell(row=1, column=2, value="Field").font = Font(bold=True, color="FFFFFF")
    ws.cell(row=1, column=3, value="What it means / allowed").font = Font(bold=True, color="FFFFFF")
    for j, name in enumerate(cols):
        c = ws.cell(row=1, column=4 + j, value=name)
        c.font = Font(bold=True, color="FFFFFF")
        c.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(4 + j)].width = 16
    for col in range(1, 4 + len(cols)):
        ws.cell(row=1, column=col).fill = HEAD
    for k, v in widths.items():
        ws.column_dimensions[k].width = v
    ws.freeze_panes = "D2"
    last_col = get_column_letter(3 + len(cols))
    for i, (code, label, hlp, val) in enumerate(rows, 2):
        ws.cell(row=i, column=1, value=code).font = Font(color="8A9A8E", size=9)
        lc = ws.cell(row=i, column=2, value=label)
        hc = ws.cell(row=i, column=3, value=hlp)
        hc.alignment = Alignment(wrap_text=False)
        hc.font = Font(color="56655A", size=10)
        if code == "#":
            for col in range(1, 4 + len(cols)):
                ws.cell(row=i, column=col).fill = SECTION
            lc.font = Font(bold=True, color=GREEN)
            continue
        lc.font = Font(bold=code in ("first",))
        for j in range(len(cols)):
            c = ws.cell(row=i, column=4 + j)
            c.fill = INPUT
            c.border = BOX
            c.alignment = Alignment(horizontal="center")
        if val:
            rng = f"D{i}:{last_col}{i}"
            if val[0] == "list":
                dv = DataValidation(type="list", formula1='"' + ",".join(val[1]) + '"', allow_blank=True)
            elif val[0] == "ref":
                dv = DataValidation(type="list", formula1=ranges[val[1]], allow_blank=True)
            else:
                dv = DataValidation(type="whole", operator="between", formula1=str(val[1]), formula2=str(val[2]), allow_blank=True)
                dv.error = f"Use a whole number from {val[1]} to {val[2]}."
                dv.errorTitle = "Out of range"
            dv.showErrorMessage = True
            ws.add_data_validation(dv)
            dv.add(rng)


def _people_sheet(ws, cat, kind, cols, ranges):
    _form(ws, _people_fields(cat, kind), cols, ranges)


def _extra_sheet(ws, cat, ranges):
    ws.cell(row=1, column=1, value="Extra relationships between people in your story (not you). Use column codes: S1-S4, P1-P30.").font = Font(bold=True, color=GREEN)
    heads = ["From (code)", "To (code)", "Type (from 'From's side)", "Strength -40..40"]
    for j, h in enumerate(heads, 1):
        c = ws.cell(row=2, column=j, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = HEAD
        ws.column_dimensions[get_column_letter(j)].width = 26
    dv = DataValidation(type="list", formula1=ranges["relationships"], allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("C3:C40")
    for r in range(3, 41):
        for j in range(1, 5):
            ws.cell(row=r, column=j).fill = INPUT
            ws.cell(row=r, column=j).border = BOX
    ws.cell(row=3, column=1, value="")


def _reference_sheet(ws, cat):
    from .story import REL_PRESETS
    ranges = {}
    col = 1

    def table(name, title, header, rows, key_col=0):
        nonlocal col
        ws.cell(row=1, column=col, value=title).font = Font(bold=True, color=GREEN, size=12)
        for j, h in enumerate(header):
            c = ws.cell(row=2, column=col + j, value=h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = HEAD
            ws.column_dimensions[get_column_letter(col + j)].width = max(12, min(48, len(h) + 4))
        for i, r in enumerate(rows, 3):
            for j, v in enumerate(r):
                ws.cell(row=i, column=col + j, value=v)
        letter = get_column_letter(col + key_col)
        ranges[name] = f"=Reference!${letter}$3:${letter}${2 + len(rows)}"
        col += len(header) + 1

    arch = cat.people["archetypes"]
    table("archetypes", "Starting types (typical values)", ["type", "name"] + [t for t in TRAITS] + list(APTITUDES),
          [[a["id"], a["label"]] + [round(a["traits"].get(t, 50)) for t in TRAITS] + [round(a["aptitudes"].get(x, 50)) for x in APTITUDES] for a in arch])
    table("relationships", "Relationship types (from the other person's side)", ["type", "meaning"],
          [[k, v["label"]] for k, v in REL_PRESETS.items()])
    for s, v in cat.sports["sports"].items():
        table(f"pos_{s}", f"{v['label']} positions", ["position", "name"], [[k, lab] for k, lab in v["positions"].items()])
    paths = [["work", "Stay in town and work"]]
    for c in cat.colleges:
        paths.append([c["id"], f"{c['name']} as a student"])
        for s in c["sports"]:
            paths.append([f"{c['id']}:{s}", f"Play {s} at {c['short']} ({side_strengths(c, s)})"])
    table("paths", "After high school", ["path", "meaning"], paths)
    for k, opts in appearance.FIELDS.items():
        table(f"look_{k}", f"Look: {k.replace('_', ' ')}", [k], [[o] for o in opts])
    table("colleges", "Colleges (program strength; blank = no team)", ["id", "name", "conference", "GPA to get in", "GPA recruits need"]
          + [h for _, h in PROGRAM_COLS],
          [[c["id"], c["name"], c.get("conference", ""), c["min_gpa"], c.get("athlete_min_gpa", "")]
           + [c["programs"].get(k, "") for k, _ in PROGRAM_COLS] for c in cat.colleges])
    return ranges


# --- reading it back ---------------------------------------------------------------------------

def _val(v):
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _read_form(ws):
    """{column header: {code: value}} for a person-per-column sheet."""
    heads = {}
    for j in range(4, ws.max_column + 1):
        h = ws.cell(row=1, column=j).value
        if h:
            heads[j] = str(h).strip()
    out = {h: {} for h in heads.values()}
    for i in range(2, ws.max_row + 1):
        code = ws.cell(row=i, column=1).value
        if not code or code == "#":
            continue
        for j, h in heads.items():
            v = _val(ws.cell(row=i, column=j).value)
            if v is not None:
                out[h][str(code).strip()] = v
    return out


def _person(d: dict, errors: list, where: str) -> dict | None:
    if not d.get("first"):
        return None
    p = {}
    for k in ("first", "last", "gender", "pronouns", "archetype", "bio", "role", "title", "role_label", "coach_of", "household", "twin_of"):
        if d.get(k) is not None:
            p[k] = str(d[k]).strip()
    if "gender" in p:
        p["gender"] = p["gender"].lower()[:2].replace("fe", "f").replace("ma", "m").replace("no", "nb")
    if d.get("attracted_to"):
        p["attracted_to"] = [x.strip().lower() for x in str(d["attracted_to"]).split(",") if x.strip()]
    if d.get("grade") is not None:
        try:
            p["grade"] = int(d["grade"])
        except ValueError:
            errors.append(f"{where}: grade should be 9-12 (or 6-8 for someone who starts high school later)")
    if d.get("birthday"):
        m = re.match(r"^\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})", str(d["birthday"]))
        if hasattr(d["birthday"], "month"):
            p["birthday"] = [d["birthday"].month, d["birthday"].day]
        elif m:
            p["birthday"] = [int(m.group(1)), int(m.group(2))]
        else:
            errors.append(f"{where}: birthday should look like 4/12")
    look = {}
    for k, v in d.items():
        if k.startswith("look:"):
            f = k.split(":", 1)[1]
            look[f] = str(v).lower() in ("yes", "y", "true", "1") if f in ("glasses", "freckles") else str(v)
    if look:
        p["look"] = look
    if d.get("height_ft") is not None or d.get("height_in") is not None:
        try:
            p.setdefault("body", {})["height_in"] = int(d.get("height_ft") or 0) * 12 + int(d.get("height_in") or 0)
        except ValueError:
            errors.append(f"{where}: height should be numbers")
    if d.get("build"):
        p.setdefault("body", {})["build"] = str(d["build"]).lower()
    if d.get("jersey") is not None:
        p["jersey"] = d["jersey"]
    for prefix, layer in (("traits:", "traits"), ("aptitudes:", "aptitudes"), ("motives:", "motives"), ("interest:", "interests"),
                          ("skill:", "skills"), ("pos:", "positions")):
        vals = {k.split(":", 1)[1]: v for k, v in d.items() if k.startswith(prefix)}
        if vals:
            p[layer] = vals
    if d.get("path"):
        s = str(d["path"]).strip().lower()
        p["path"] = {"kind": "work"} if s == "work" else ({"college": s.split(":")[0], "sport": s.split(":")[1]} if ":" in s else {"college": s})
    return p


def parse_workbook(data: bytes) -> dict:
    """Turn a filled worksheet into a story spec (the same format the setup wizard saves)."""
    wb = load_workbook(io.BytesIO(data), data_only=True)
    errors = []
    spec = {"siblings": [], "cast": []}
    if "Story & Family" in wb.sheetnames:
        sf = _read_form(wb["Story & Family"]).get("Value", {})
        if sf.get("title"):
            spec["title"] = str(sf["title"])
        if sf.get("students_per_grade"):
            spec["students_per_grade"] = int(sf["students_per_grade"])
        if sf.get("gen_seed"):
            spec["gen_seed"] = int(sf["gen_seed"])
        fam = {}
        if sf.get("family_last"):
            fam["last"] = str(sf["family_last"])
        gs = [str(sf[k]) for k in ("guardian1", "guardian2") if sf.get(k)]
        if gs:
            fam["guardians"] = gs
        for k in ("style", "income"):
            if sf.get(k):
                fam[k] = str(sf[k]).lower()
        pet = str(sf.get("pet") or "").lower()
        if pet == "none":
            fam["pet"] = None
        elif pet in ("dog", "cat", "rabbit"):
            fam["pet"] = {"species": pet, "name": str(sf.get("pet_name") or pet.capitalize())}
        spec["family"] = fam
    if "You" in wb.sheetnames:
        me = _person(_read_form(wb["You"]).get("me", {}), errors, "You")
        if me:
            spec["protagonist"] = me
    rels_to_me = {}
    if "Siblings" in wb.sheetnames:
        for key, d in _read_form(wb["Siblings"]).items():
            p = _person(d, errors, f"Siblings {key}")
            if not p:
                continue
            p["key"] = key
            if d.get("rel_strength") is not None:
                p["strength"] = d["rel_strength"]
            if d.get("rel_type") and d["rel_type"] != "sibling":
                p["relationship"] = str(d["rel_type"])
            spec["siblings"].append(p)
    if "Your People" in wb.sheetnames:
        for key, d in _read_form(wb["Your People"]).items():
            p = _person(d, errors, f"Your People {key}")
            if not p:
                continue
            p["key"] = key
            if d.get("rel_type"):
                r = {"to": "me", "type": str(d["rel_type"])}
                if d.get("rel_strength") is not None:
                    r["strength"] = d["rel_strength"]
                p.setdefault("relationships", []).append(r)
            spec["cast"].append(p)
    if "Extra Relationships" in wb.sheetnames:
        ws = wb["Extra Relationships"]
        people = {p["key"]: p for p in spec["siblings"] + spec["cast"]}
        for i in range(3, ws.max_row + 1):
            a, b, t, s = (_val(ws.cell(row=i, column=j).value) for j in range(1, 5))
            if not (a and b and t):
                continue
            if str(a) not in people:
                errors.append(f"Extra Relationships row {i}: no person with code {a}")
                continue
            r = {"to": "me" if str(b).lower() == "me" else str(b), "type": str(t)}
            if s is not None:
                r["strength"] = s
            people[str(a)].setdefault("relationships", []).append(r)
    if not spec.get("protagonist"):
        errors.append("The 'You' sheet needs at least a first name.")
    if errors:
        from .story import StoryError
        raise StoryError(errors)
    return spec


# --- the guide ---------------------------------------------------------------------------------

def guide_markdown(cat: Catalogs | None = None) -> str:
    from .story import REL_PRESETS
    cat = cat or Catalogs()
    town = cat.world["town"]["name"]
    school = cat.world["school"]["name"]
    sp = cat.sports["sports"]
    arch = cat.people["archetypes"]
    L = []
    L.append("# LIFE OS character worksheet guide\n")
    L.append(f"Use this to plan the people in your story (you, your family, your friends, your crush, your rivals, your coaches) "
             f"before you build them in the app. The story starts on the first day of school at {school} in {town}, and runs seven years.\n")
    L.append("You have three ways to do it:\n")
    L.append("1. **Fill in the Excel worksheet** (`character-worksheet.xlsx`) and load it in the app: My Story, Start your story, Load a cast file.")
    L.append("2. **Talk it through with ChatGPT or Claude.** Paste the prompt below, answer its questions, and save the JSON it gives you "
             "as a `.json` file. Load that file the same way.")
    L.append("3. **Mix them.** Talk it through first, then type the numbers into the worksheet.\n")
    L.append("Anything you leave blank is generated from the person's type, so you only need to decide what matters to you.\n")
    L.append("## The prompt to paste\n")
    L.append("````text")
    L.append(PROMPT.replace("{school}", school).replace("{town}", town).strip())
    L.append("````\n")
    L.append("## Numbers: what they mean\n")
    L.append("Every 0-100 number: 50 is average, 70+ stands out, 85+ is rare. Nobody should be high at everything; the interesting "
             "people have a few clear strengths and a weakness or two.\n")
    for layer in ("traits", "aptitudes", "motives"):
        doc = ATTRIBUTE_DOCS[layer]
        L.append(f"### {doc['layer']} ({layer})\n\n{doc['about']}\n")
        for k, v in doc["items"].items():
            L.append(f"- **{k}**: {v}")
        L.append("")
    L.append("### Interests and starting skills\n")
    L.append("Interests (0-100) decide what they choose to do with their time. Skills (0-100) are how good they are on day one; "
             "a typical freshman is 25-50 in a sport, varsity seniors are 55-75, and college recruits are higher. Talent "
             "(aptitude) sets how fast skills grow and how high they can go.\n")
    L.append("Skills: " + ", ".join(f"`{s['id']}`" for s in cat.world["skills"]))
    L.append("\nHobbies (interests only): " + ", ".join(f"`{h['id']}`" for h in cat.world["hobbies"]) + "\n")
    L.append("## Starting types\n")
    L.append("| type | name | typical personality |\n|---|---|---|")
    for a in arch:
        top = sorted(a["traits"].items(), key=lambda x: -x[1])[:3]
        L.append(f"| `{a['id']}` | {a['label']} | " + ", ".join(f"{k} {round(v)}" for k, v in top) + " |")
    L.append("\n## Sports and positions\n")
    for s, v in sp.items():
        L.append(f"- **{v['label']}**: " + ", ".join(f"`{k}` {lab}" for k, lab in v["positions"].items()))
    L.append("\nBody matters: height helps in basketball (and for pitchers), build matters in football "
             "(`strong` for linemen, `athletic` or `slight` for skill positions). Builds: `slight`, `average`, `athletic`, `strong`.\n")
    L.append("## Relationship types\n")
    L.append("Always written from the other person's side, toward the one they point at (`me` = you).\n")
    for k, v in REL_PRESETS.items():
        L.append(f"- `{k}`: {v['label']}")
    L.append("\n## After high school (for anyone but you)\n")
    L.append("Leave it out to let it play out. `{\"kind\": \"work\"}` stays in town. `{\"college\": \"uconn\", \"sport\": \"basketball\"}` "
             "plays a sport there; `{\"college\": \"uconn\"}` goes as a student.\n")
    L.append("Program strength 0-100 by team (blank: no team on that side). A girl's `sport` is her side's team: "
             "`basketball` at UConn means women's basketball, and `baseball` for a girl means softball.\n")
    L.append("| id | college | conference | " + " | ".join(h for _, h in PROGRAM_COLS) + " |\n|" + "---|" * (3 + len(PROGRAM_COLS)))
    for c in cat.colleges:
        L.append(f"| `{c['id']}` | {c['name']} | {c.get('conference', '')} | "
                 + " | ".join(str(c['programs'].get(k, '')) for k, _ in PROGRAM_COLS) + " |")
    L.append("\n## Looks\n")
    for k, opts in appearance.FIELDS.items():
        L.append(f"- **{k}**: " + ", ".join(f"`{o}`" for o in opts))
    L.append("- **glasses**, **freckles**: true or false\n")
    L.append("## The cast file format\n")
    L.append("This is what the AI should give you back (and what the app saves when you download a cast). "
             "Everything except first names is optional.\n")
    L.append("```json")
    L.append(json.dumps(EXAMPLE, indent=2))
    L.append("```")
    return "\n".join(L) + "\n"


PROMPT = """
You're helping me plan the characters for my LIFE OS story, a life simulation that starts on my first day at {school} in {town} and runs seven years (high school, then college or work).

Interview me one person at a time: me first, then my family (parents, siblings, a pet if we have one), then the people I want in my story (friends, a crush, rivals, coaches, and younger kids who'll start high school later, like a little brother or the neighbor kid). I can add as many people as I want. For each person, ask a few natural questions about who they are, what they're into and how we know each other, then propose numbers and explain them in one line each. Push back if I make someone great at everything; real people have a couple of clear strengths and a weakness or two. Keep it conversational, not a form.

The fields (all optional except first names; blanks get generated):
- first, last, gender (m/f/nb), pronouns, attracted_to (list of m/f/nb), grade (9-12 on day one; for a younger sibling or anyone still in middle school, 8, 7 or 6: they start high school as a freshman 1, 2 or 3 years in), birthday [month, day], archetype (athlete, artist, scholar, socialite, loner, rebel, leader, techie, performer, caretaker, drifter), bio
- traits 0-100: sociability, confidence, discipline, ambition, impulsivity, empathy, competitiveness, curiosity, volatility, loyalty
- aptitudes 0-100 (natural talent): athletic, academic, creativity, technical, charisma
- motives 0-100: achievement, approval, belonging, pleasure, altruism, mastery
- interests 0-100 and skills 0-100 by id: academics, football, basketball, baseball, soccer, softball, fitness, art, music, robotics, writing, acting (plus hobbies as interests). A typical freshman is 25-50 in a sport. Teams are split: boys play football, basketball, soccer and baseball; girls play basketball, soccer and softball (a girl's baseball turns into softball).
- body: height_in (inches), build (slight/average/athletic/strong); positions per sport (football QB/RB/WR/TE/OL/DL/LB/DB/K, basketball PG/SG/SF/PF/C, baseball and softball P/C/1B/2B/3B/SS/OF, soccer GK/CB/FB/CM/WM/ST); jersey
- look: skin, hair, hair_color, eyes, facial_hair, glasses, freckles (options are in the guide)
- relationships: [{"to": "me" or another person's key, "type": best_friend|close_friend|friend|acquaintance|crush|admirer|mutual_crush|dating|ex|rival|enemy|teammate|neighbor|mentor, "strength": -40..40}], written from that person's side
- siblings: key, twin_of ("me" or another sibling's key), strength (how well we get along, -40..40)
- anyone but me can have a path after high school: {"kind": "work"} or {"college": "uconn", "sport": "basketball"} (colleges: uconn, stanford, ucla, lsu, unc, texas, oklahoma, fsu, miami, michigan, scsu, gateway)
- family: last, guardians (names), style (warm/strict/permissive/distant/overbearing), income (low/middle/high), pet ({"species": "dog", "name": "Buster"}, or null for none)

When we're done, give me the whole thing as one JSON object in exactly this shape, in a single code block, with nothing I'd need to fix by hand:
{"title": "...", "students_per_grade": 12, "protagonist": {...}, "family": {...}, "siblings": [{"key": "S1", ...}], "cast": [{"key": "P1", ...}]}
students_per_grade is how many classmates each grade starts with (6-40, around my people); 12-20 plays smoothly on a phone.
"""

EXAMPLE = {
    "title": "The Soffer Years", "students_per_grade": 12,
    "protagonist": {"first": "Zack", "last": "Soffer", "gender": "m", "grade": 9, "archetype": "athlete", "attracted_to": ["f"],
                    "traits": {"discipline": 70, "competitiveness": 85, "sociability": 68},
                    "aptitudes": {"athletic": 82, "academic": 55},
                    "interests": {"football": 80, "basketball": 78, "baseball": 92},
                    "skills": {"football": 42, "basketball": 45, "baseball": 52},
                    "body": {"height_in": 71, "build": "athletic"}, "positions": {"football": "WR", "basketball": "SG", "baseball": "SS"},
                    "jersey": 2, "birthday": [4, 12], "look": {"hair": "short", "hair_color": "brown"}},
    "family": {"last": "Soffer", "guardians": ["Linda", "Rob"], "style": "warm", "income": "middle", "pet": {"species": "dog", "name": "Buster"}},
    "siblings": [{"key": "S1", "first": "Mike", "gender": "m", "grade": 12, "archetype": "athlete", "interests": {"basketball": 88},
                  "path": {"college": "uconn", "sport": "basketball"}, "strength": 10},
                 {"key": "S2", "first": "Ally", "gender": "f", "grade": 10},
                 {"key": "S3", "first": "Jen", "gender": "f", "grade": 10, "twin_of": "S2"}],
    "cast": [{"key": "P1", "first": "Danny", "last": "Kim", "gender": "m", "grade": 9, "archetype": "athlete",
              "relationships": [{"to": "me", "type": "best_friend"}]},
             {"key": "P2", "first": "Sophie", "last": "Lane", "gender": "f", "grade": 9, "relationships": [{"to": "me", "type": "mutual_crush"}]}],
}
