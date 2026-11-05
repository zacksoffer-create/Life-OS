"""Excel round-trip: the start of the master balancing workbook.

Export writes Rules, Actions, Characters and Groups sheets. Import reads Rules, Actions and
Characters back, validates every cell through the same checks the app uses, applies what is
valid, and reports every rejected cell. Columns marked (read only) are ignored on import.
"""
from __future__ import annotations

import io

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from .catalogs import APTITUDES, MOTIVES, NEEDS, TRAITS, CatalogError
from .engine import EditError
from .rules import RulesError, schema

HEAD = Font(bold=True, color="FFFFFF")
FILL = PatternFill("solid", fgColor="2B3A67")
RO = PatternFill("solid", fgColor="E8E8EE")


def _header(ws, cols, ro=()):
    ws.append(cols)
    for i, c in enumerate(cols, 1):
        cell = ws.cell(row=1, column=i)
        cell.font = HEAD
        cell.fill = FILL
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[cell.column_letter].width = max(10, min(40, len(str(c)) + 4))
    ws.freeze_panes = "B2"


def export_workbook(sim) -> bytes:
    w = sim.w
    wb = Workbook()
    ws = wb.active
    ws.title = "README"
    for line in [
        "LIFE OS balancing workbook",
        f"World: {w.name}   Day {w.day}   Seed {w.seed}",
        "",
        "Edit values in Rules, Actions and Characters, then import this file in the Engine Workshop.",
        "Grey columns are read only. Every value is validated; rejected cells are listed after import.",
        "Rules: change 'value'. Actions: change base, risk and the coefficient columns (need/motive/trait).",
        "Characters: change trait/aptitude/motive columns (0-100).",
    ]:
        ws.append([line])
    ws.column_dimensions["A"].width = 100
    sch = schema()
    rs = wb.create_sheet("Rules")
    _header(rs, ["key", "section", "label", "value", "default", "min", "max", "type", "description"])
    for k, p in sch.params.items():
        rs.append([k, p["section"], p["label"], w.rules[k], p["default"], p.get("min"), p.get("max"), p["type"], p["description"]])
    for row in rs.iter_rows(min_row=2):
        for cell in row:
            if cell.column != 4:
                cell.fill = RO
    acts = wb.create_sheet("Actions")
    cols = ["id", "label", "slots", "base", "risk"] + [f"need.{n}" for n in NEEDS] + [f"motive.{m}" for m in MOTIVES] + \
           [f"trait.{t}" for t in TRAITS] + ["resolver", "overridden"]
    _header(acts, cols)
    for a in sim.cat.actions.values():
        acts.append([a["id"], a["label"], ",".join(a["slots"]), a["base"], a["risk"]] +
                    [a["needs"].get(n, 0) for n in NEEDS] + [a["motives"].get(m, 0) for m in MOTIVES] +
                    [a["traits"].get(t, 0) for t in TRAITS] + [a["resolver"], "yes" if a["id"] in w.action_overrides else ""])
    ch = wb.create_sheet("Characters")
    cols = ["id", "name", "role", "grade", "archetype"] + [f"trait.{t}" for t in TRAITS] + [f"aptitude.{a}" for a in APTITUDES] + \
           [f"motive.{m}" for m in MOTIVES] + ["popularity (read only)", "gpa (read only)", "bio"]
    _header(ch, cols)
    for c in sorted(w.chars.values(), key=lambda c: (c.role, c.grade or 0, c.id)):
        ch.append([c.id, c.name, c.role, c.grade, c.archetype] + [round(c.traits[t], 1) for t in TRAITS] +
                  [round(c.aptitudes.get(a, 0), 1) for a in APTITUDES] + [round(c.motives.get(m, 0), 1) for m in MOTIVES] +
                  [round(c.popularity, 1), round(c.gpa, 2), c.bio])
    gs = wb.create_sheet("Groups")
    _header(gs, ["id", "name", "kind", "selection", "capacity", "skill", "members (read only)"])
    for g in w.groups.values():
        gs.append([g["id"], g["name"], g["kind"], g["selection"], g["capacity"], g.get("skill"), len(g["members"])])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def import_workbook(sim, data: bytes) -> dict:
    wb = load_workbook(io.BytesIO(data), data_only=True)
    report = {"rules": [], "actions": [], "characters": [], "errors": []}
    sch = schema()
    if "Rules" in wb.sheetnames:
        ws = wb["Rules"]
        rows = list(ws.iter_rows(min_row=1, values_only=True))
        hdr = [str(h) for h in rows[0]]
        ki, vi = hdr.index("key"), hdr.index("value")
        changes = {}
        for r in rows[1:]:
            if not r or r[ki] is None:
                continue
            key, val = str(r[ki]), r[vi]
            if key not in sch.params:
                report["errors"].append(f"Rules: unknown key {key}")
                continue
            if val != sim.w.rules.get(key):
                try:
                    changes[key] = sch.coerce(key, val)
                except ValueError as e:
                    report["errors"].append(f"Rules: {e}")
        if changes:
            try:
                diffs = sim.set_rules(changes, note="imported from workbook")
                report["rules"] = diffs
            except RulesError as e:
                report["errors"].extend(f"Rules: {x}" for x in e.errors)
    if "Actions" in wb.sheetnames:
        ws = wb["Actions"]
        rows = list(ws.iter_rows(min_row=1, values_only=True))
        hdr = [str(h) for h in rows[0]]
        for r in rows[1:]:
            if not r or r[0] is None:
                continue
            aid = str(r[0])
            if aid not in sim.cat.actions:
                report["errors"].append(f"Actions: unknown action {aid}")
                continue
            a = sim.cat.actions[aid]
            ch: dict = {}
            for i, col in enumerate(hdr):
                val = r[i] if i < len(r) else None
                if val is None or val == "":
                    continue
                try:
                    if col in ("base", "risk"):
                        if float(val) != float(a[col]):
                            ch[col] = float(val)
                    elif "." in col:
                        layer, key = col.split(".", 1)
                        field = {"need": "needs", "motive": "motives", "trait": "traits"}.get(layer)
                        if field and float(val) != float(a[field].get(key, 0)):
                            ch.setdefault(field, {})[key] = float(val)
                except (TypeError, ValueError):
                    report["errors"].append(f"Actions: {aid}.{col} is not a number ({val!r})")
            if ch:
                try:
                    sim.set_action_override(aid, ch)
                    report["actions"].append({"action": aid, "changes": ch})
                except CatalogError as e:
                    report["errors"].append(f"Actions: {aid}: {e}")
    if "Characters" in wb.sheetnames:
        ws = wb["Characters"]
        rows = list(ws.iter_rows(min_row=1, values_only=True))
        hdr = [str(h) for h in rows[0]]
        for r in rows[1:]:
            if not r or r[0] is None:
                continue
            cid = str(r[0])
            c = sim.w.chars.get(cid)
            if c is None:
                report["errors"].append(f"Characters: unknown id {cid}")
                continue
            ch = {}
            for i, col in enumerate(hdr):
                if "." not in col or "read only" in col:
                    continue
                layer, key = col.split(".", 1)
                field = {"trait": "traits", "aptitude": "aptitudes", "motive": "motives"}.get(layer)
                val = r[i] if i < len(r) else None
                if not field or val is None:
                    continue
                try:
                    if abs(float(val) - getattr(c, field).get(key, 0)) > 0.05:
                        ch.setdefault(field, {})[key] = val
                except (TypeError, ValueError):
                    report["errors"].append(f"Characters: {cid}.{col} is not a number ({val!r})")
            bi = hdr.index("bio") if "bio" in hdr else None
            if bi is not None and bi < len(r) and r[bi] and str(r[bi]) != c.bio:
                ch["bio"] = str(r[bi])
            if ch:
                try:
                    sim.edit_character(cid, ch)
                    report["characters"].append({"id": cid, "changes": ch})
                except EditError as e:
                    report["errors"].append(f"Characters: {cid}: {e}")
    return report
