"""Story moments: the points where the simulation stops and asks the protagonist's player.

Triggers are fired by the engine (injuries, offers, getting cut, siblings leaving, the college
decision...). A moment waits in w.meta["moments"] until the player picks a choice, or the
character decides for themselves. Choices run a small vocabulary of ops through the same Effects
recorder as everything else, and chance ops roll against the person's own traits, so the event
log shows exactly what was rolled and what changed.
"""
from __future__ import annotations

import string

from .history import Effects
from .rng import clamp, softmax_pick

DEDUPE = {"first_day", "college_decision", "summer", "graduation", "college_arrival", "year_review", "game_day", "benched",
          "mlb_draft", "draft_passed", "story_end", "class_quiz", "class_game"}


class _Safe(dict):
    def __missing__(self, key):
        return ""


def control(w) -> dict:
    c = w.meta.setdefault("control", {})
    c.setdefault("focus", "balanced")
    c.setdefault("ask_invites", False)
    c.setdefault("ask_romance", True)
    c.setdefault("stop_before_games", True)
    c.setdefault("stop_on_big", True)
    if not c.get("_free_time"):
        c["auto_lunch"] = False  # lunch is one of your free times now (practice takes after school): you pick it
        c["_free_time"] = 1
    c.setdefault("auto_lunch", False)
    c.setdefault("class_games", True)  # quick games in class most school days
    c.setdefault("editor", True)  # change anyone and anything (on to start; turn it off on the Me tab)
    return c


def light(kind: str) -> bool:
    """Moments a skip-ahead doesn't stop for: your character just plays them (class games, a night out)."""
    return kind == "class_game" or kind.startswith("night_")


def pending(w) -> list:
    return [m for m in w.meta.get("moments", []) if m["status"] == "pending"]


def _names(sim, ctx) -> dict:
    w = sim.w
    out = _Safe()
    out["school"] = sim.cat.world["school"]["name"]
    out["town"] = sim.cat.world["town"]["name"]
    for k, v in ctx.items():
        if isinstance(v, str) and v in w.chars:
            out[k] = w.chars[v].name
        elif isinstance(v, (str, int, float)):
            out[k] = v
    if "sport" in ctx and ctx["sport"] in sim.cat.sports["sports"]:
        out["sport"] = sim.cat.sports["sports"][ctx["sport"]]["label"].lower()
    return out


def _render(text, names) -> str:
    return string.Formatter().vformat(text, (), names)


def trigger(sim, kind: str, cid: str, ctx: dict):
    w = sim.w
    if not cid or cid != w.meta.get("protagonist"):
        return
    spec = sim.cat.moments.get(kind)
    if not spec:
        return
    ctl = control(w)
    if kind == "game_day" and not ctl.get("stop_before_games"):
        return
    if kind in DEDUPE and any(m["kind"] == kind and m["day"] == w.day for m in w.meta.get("moments", [])):
        return
    if kind == "college_decision" and any(m["kind"] == kind and m["status"] == "pending" for m in w.meta.get("moments", [])):
        return
    c = w.chars[cid]
    ctx = dict(ctx)
    _enrich(sim, c, kind, ctx)
    names = _names(sim, ctx)
    choices = []
    if spec.get("dynamic") == "paths":
        from .sports import path_options
        opts = path_options(sim, c)
        ctx["paths"] = opts
        for i, o in enumerate(opts):
            choices.append({"label": o["label"], "hint": "", "ops": [["path", i]], "fits": {}})
    elif spec.get("dynamic") == "night_people":  # tonight: the people here who matter to you, and someone new
        from . import nights
        choices = nights.people_choices(sim, c, ctx)
    else:
        for ch in spec["choices"]:
            req = ch.get("requires")
            if req and any(not ctx.get(r) for r in (req if isinstance(req, list) else [req])):
                continue
            from . import minigames
            if not minigames.choice_ok(ch.get("ops"), ctx):
                continue  # that mini game isn't ready yet
            choices.append({"label": _render(ch["label"], names), "hint": _render(ch.get("hint", ""), names), "ops": ch["ops"], "fits": ch.get("fits", {}),
                            "game": minigames.badge(ch.get("ops"), ctx)})
    from . import lines
    text = lines.variant(sim, f"scene:{kind}", spec["text"], f"{w.day}:{kind}")
    m = {"id": f"mo{w.next_id('moment')}", "kind": kind, "day": w.day, "status": "pending", "ctx": ctx,
         "title": _render(spec["title"], names), "text": _render(text, names),
         "choices": [{"label": ch["label"], "hint": ch["hint"], **({"game": ch["game"]} if ch.get("game") else {})} for ch in choices],
         "_choices": choices}
    # a scene written both ways can happen in person or by text: by text more on days off, rarely with family
    by = (spec.get("scene") or {}).get("by_text")
    them = ctx.get("them")
    if by and them in w.chars and "phone" in w.meta:
        fam = them in sim.siblings(c.id)
        p_text = 0.15 if fam else 0.6 if "school_day" not in lines.tags_for(sim, them) else 0.35
        if lines._h(w.seed, kind, w.day, "channel") % 100 < p_text * 100:
            line = _render(lines.variant(sim, f"bytext:{kind}", by, f"{w.day}:{kind}:text"), names)
            m["text"] = f"{w.chars[them].first} texted you: \"{line}\""
            m["by_text"] = line
    w.meta.setdefault("moments", []).append(m)
    from . import episodes
    episodes.on_trigger(sim, m)  # one big story: this is Season 2, Episode 6 (and what happened last time)
    if "phone" in w.meta:
        from . import messages
        messages.moment_text(sim, m)
    if len(w.meta["moments"]) > 300:
        w.meta["moments"] = [x for x in w.meta["moments"] if x["status"] == "pending"] + \
                            [x for x in w.meta["moments"] if x["status"] != "pending"][-200:]


def _enrich(sim, c, kind, ctx):
    w = sim.w
    R = w.rules
    if "group" in ctx and ctx["group"] in w.groups:
        g = w.groups[ctx["group"]]
        ctx.setdefault("coach", g.get("staff"))
        ctx.setdefault("sport", g.get("skill"))
        ctx["group"] = g["name"]
    if "days" in ctx:
        ctx["weeks"] = max(1, round(ctx["days"] / 7))
    if kind == "class_quiz":
        ctx["teacher_line"] = f" with {ctx['teacher']}" if ctx.get("teacher") else ""
    if ctx.get("sport"):
        ctx.setdefault("sport_id", ctx["sport"])
    best = sorted(((r.affection, o) for o, r in w.out.get(c.id, {}).items() if o in w.chars and w.chars[o].role != "staff"
                   and w.chars[o].status == "active"), reverse=True)
    if best:
        ctx.setdefault("best_friend", best[0][1])
    sibs = sim.siblings(c.id)
    if kind == "first_day":
        older = [w.chars[s] for s in sibs if (w.chars[s].grade or 0) > (c.grade or 9)]
        if older:
            parts = [f"{s.first} ({s.year_label.lower()})" for s in sorted(older, key=lambda s: -(s.grade or 0))]
            ctx["siblings_line"] = f"Your siblings {', '.join(parts[:-1]) + ' and ' + parts[-1] if len(parts) > 1 else parts[0]} are already here. "
        else:
            ctx["siblings_line"] = ""
    if kind in ("summer", "year_review"):
        f = sum(1 for o, r in w.out.get(c.id, {}).items() if r.affection >= R["rel.friend_threshold"])
        ctx["review"] = (f"You finished the year with {f} people you'd call friends, a {c.gpa:.2f} GPA"
                         + (f", and {len(c.awards)} award{'s' if len(c.awards) != 1 else ''} so far" if c.awards else "") + ".")
        ctx["summer_line"] = ""
        ctx["year_label"] = c.year_label + " year"


    if kind == "mlb_draft":
        ctx["return_line"] = ("As a senior you don't have much leverage. This is probably the offer." if ctx.get("senior")
                              else "You could also go back for your senior year and try to climb the board next July.")
    if kind == "draft_passed":
        ctx["udfa_line"] = ("A couple of teams called afterward about signing as an undrafted free agent." if ctx.get("udfa")
                            else "Nobody called afterward either.")
    if kind == "story_end":
        ctx["review"] = story_review(sim, c)
        st = w.meta.get("story")
        if st is not None:
            st["complete"] = True


def story_review(sim, c) -> str:
    """The closing summary: high school, college, the draft and the people."""
    w = sim.w
    school = sim.cat.world["school"]["name"]
    hs = [st for st in c.stats.values() if st.get("school") == "hchs"]
    col = [st for st in c.stats.values() if st.get("school") != "hchs"]
    hs_aw = [a for a in c.awards if any(a.get("season") == k and st.get("school") == "hchs" for k, st in c.stats.items())]
    parts = [f"Seven years ago you walked into {school} as a freshman."]
    if hs:
        sports_hs = sorted({st["sport"] for st in hs})
        parts.append(f"You played {sum(st['games'] for st in hs)} games of {', '.join(sports_hs)} there"
                     + (f" and won {len(hs_aw)} award{'s' if len(hs_aw) != 1 else ''}" if hs_aw else "") + ".")
    p = c.path or {}
    d = c.recruiting.get("draft") or {}
    colname = p.get("name") if p.get("kind") == "college" else (sim.cat.college_by_id.get(p.get("college") or "", {}).get("short"))
    if col and colname:
        parts.append(f"In college you played {sum(st['games'] for st in col)} games for {colname}.")
    if p.get("kind") == "pro":
        parts.append(f"Then the {p['team']} drafted you in round {p['round']} and you signed. Next stop: {p['level']}." if p.get("team")
                     else f"You went undrafted and signed anyway. Next stop: {p['level']}.")
    elif d.get("status") == "returned":
        parts.append(f"The {d.get('team')} drafted you in round {d.get('round')}, and you turned them down to go back for one more year.")
    elif d.get("status") == "returned_undrafted":
        parts.append("The draft passed you by, so you went back for one more year to change their minds.")
    elif d.get("status") == "undrafted":
        parts.append("The draft passed you by.")
    elif p.get("kind") == "work":
        parts.append(f"You stayed in {sim.cat.world['town']['name']} and went to work.")
    f = sum(1 for o, r in w.out.get(c.id, {}).items() if r.affection >= w.rules["rel.friend_threshold"])
    partner = c.flags.get("partner")
    parts.append(f"You've got {f} people you'd call friends" + (f", and you're with {w.chars[partner].short}" if partner in w.chars else "") + ".")
    parts.append("Those are the seven chapters. The world keeps going if you do.")
    return " ".join(parts)


def auto_choice(sim, c, m) -> int:
    rng = sim.streams.get("moment", m["id"])
    if m["kind"] in ("asked_out", "asked_to_dance"):
        from .worldgen import orientation_ok
        o = sim.w.chars.get(m["ctx"].get("other"))
        r = sim.w.rels.get((c.id, o.id)) if o else None
        if o is None or r is None:
            return 1
        keen = r.attraction + (r.affection * 0.4 if m["kind"] == "asked_to_dance" else 0)
        return 0 if (orientation_ok(c, o) and keen >= 45 and not (c.flags.get("partner") and m["kind"] == "asked_out")) else 1
    if m["kind"] == "college_decision":
        opts = m["ctx"]["paths"]
        idx, _ = softmax_pick([o["utility"] for o in opts], 6.0, rng.random())
        return idx
    us = []
    for ch in m["_choices"]:
        u = sum(coef * (c.traits.get(k, 50) - 50) / 50 for k, coef in ch.get("fits", {}).items()) * 4 + rng.gauss(0, 1)
        us.append(u)
    idx, _ = softmax_pick(us, 2.0, rng.random())
    return idx


def resolve(sim, mid: str, index: int | None, by: str = "player"):
    w = sim.w
    m = next((x for x in w.meta.get("moments", []) if x["id"] == mid), None)
    if m is None or m["status"] != "pending":
        raise ValueError("that moment is no longer waiting for a choice")
    c = w.chars[w.meta.get("protagonist")] if w.meta.get("protagonist") in w.chars else None
    if c is None:
        raise ValueError("there is no protagonist")
    if index is None:
        index = auto_choice(sim, c, m)
        by = "auto"
    if not 0 <= index < len(m["_choices"]):
        raise ValueError("no such choice")
    ch = m["_choices"][index]
    ctx = m["ctx"]
    targets = [v for k, v in ctx.items() if isinstance(v, str) and v in w.chars and v != c.id
               and k in ("them", "coach", "sibling", "roommate", "other", "origin", "partner")]
    ev = sim.new_event("moment", m["kind"], [c.id], targets[:3], 32, {"label": m["title"], "choice": ch["label"], "by": by})
    ev["text"] = f"{m['title']}: {c.short} {'chose' if by == 'player' else 'decided'} to {ch['label'][0].lower() + ch['label'][1:].rstrip('.')}."
    fx = Effects(w, ev)
    rng = sim.streams.get("moment-resolve", m["id"])
    run_ops(sim, c, ch["ops"], ctx, fx, ev, rng, m)
    if m["kind"] == "class_game":
        from . import classgames
        classgames.after(sim, m, ev, index)  # it counts a little toward that class
    if ctx.get("cast_slot"):
        from . import dialogue
        dialogue.keep_floor(sim, ctx)  # a storyline's bond (inseparable brothers) holds, whatever you chose
    from . import episodes
    episodes.on_resolve(sim, m, ch, ev)
    m["status"] = "resolved"
    m["choice"] = index
    m["by"] = by
    if "phone" in w.meta and m["kind"] in ("asked_out", "asked_to_dance"):
        from . import messages
        messages.answered_elsewhere(sim, "moment", m["id"], index)
    m["event"] = ev["id"]
    sim.finish(ev, fx)
    from . import scheduler
    scheduler.after_resolve(sim, m)  # a storyline scene that finished unlocks what waits on it; the next scene comes
    return ev


def _ref(ctx, key):
    return ctx.get(key, key)


def run_ops(sim, c, ops, ctx, fx, ev, rng, m):
    from . import sports
    w = sim.w
    names = _names(sim, ctx)
    for op in ops:
        kind = op[0]
        if kind == "focus":
            old = control(w)["focus"]
            control(w)["focus"] = op[1]
            if ev.get("changes") is not None:
                ev["changes"].append([c.id, "focus", old, op[1], "your choice"])
        elif kind == "sign_up":
            gid = op[1]
            it = next((i for i in sim.upcoming if i.get("group") == gid and i["kind"] == "tryout" and i["day"] >= w.day), None)
            if it and c.id not in w.registrations.get(it["key"], []):
                w.registrations.setdefault(it["key"], []).append(c.id)
                if ev.get("changes") is not None:
                    ev["changes"].append([c.id, "registered", None, it["name"], "your choice"])
        elif kind in ("rel", "rel_back"):
            other = _ref(ctx, op[1])
            if isinstance(other, str) and other in w.chars and other != c.id:
                a, b = (c.id, other) if kind == "rel" else (other, c.id)
                fx.rel(a, b, op[2], op[3], m["title"])
        elif kind == "mood":
            fx.mood(c.id, op[1], m["title"])
        elif kind == "need":
            fx.need(c.id, op[1], op[2], m["title"])
        elif kind == "trait":
            fx.trait(c.id, op[1], op[2], m["title"])
        elif kind == "skill":
            key = _ref(ctx, op[1])  # a skill id, or "sport": your main sport
            if key in sim.cat.skills:
                fx.skill(c.id, key, op[2], m["title"])
        elif kind == "interest":
            key = _ref(ctx, op[1])
            if isinstance(key, str) and (key in sim.cat.skills or key in sim.cat.hobbies):
                fx.interest(c.id, key, op[2], m["title"])
        elif kind == "rep":
            fx.rep(c.id, op[1], op[2], m["title"])
        elif kind == "goal":
            sport = _ref(ctx, op[2])
            if op[1] == "improve_skill" and sport in sim.cat.skills:
                sim.add_goal(c, "improve_skill", None, sim.cat.skills[sport]["label"].lower(), op[3], skill=sport, cause=ev)
        elif kind == "memory":
            withs = [_ref(ctx, r) for r in op[4]]
            withs = [x for x in withs if isinstance(x, str) and x in w.chars]
            fx.memory(c.id, m["kind"], withs, op[2], op[3], _render(op[1], names))
        elif kind == "family":
            for s in sim.siblings(c.id):
                fx.rel(c.id, s, op[1], op[2], m["title"])
                fx.rel(s, c.id, op[1], op[2], m["title"])
        elif kind == "flag":
            val = _render(op[2], names) if isinstance(op[2], str) else op[2]
            fx.flag(c.id, op[1], val, m["title"])
        elif kind == "approach":
            fx.flag(c.id, "game_approach", op[1], m["title"])
            fx.flag(c.id, "game_approach_day", w.day, m["title"])
        elif kind == "injury_shorten":
            until = c.flags.get("injured_until", w.day)
            fx.flag(c.id, "injured_until", w.day + int((until - w.day) * (1 - op[1])), m["title"])
        elif kind == "injury_extend":
            fx.flag(c.id, "injured_until", c.flags.get("injured_until", w.day) + op[1], m["title"])
        elif kind == "pro":
            sports.sign_pro(sim, c, fx=fx, udfa=(op[1] == "udfa"))
        elif kind == "draft_return":
            d = c.recruiting.get("draft")
            if d:
                d["status"] = "returned_undrafted" if d.get("status") == "undrafted" else "returned"
        elif kind == "retire_baseball":
            for gid in list(c.memberships):
                if w.groups[gid].get("skill") == "baseball":
                    fx.leave(c.id, gid, "stepped away from baseball")
            fx.interest(c.id, "baseball", -30, m["title"])
            if c.path:
                c.path["sport"] = None
        elif kind == "path":
            opt = ctx["paths"][op[1]]
            sports.choose_path(sim.institutions, c, rng, option=opt, how="player")
        elif kind == "answer_ask":
            from .actions import start_dating, _rejected
            other = ctx.get("other")
            if other in w.chars:
                if op[1] == "yes":
                    if ctx.get("dance_key"):
                        dd = w.dance_dates.setdefault(ctx["dance_key"], {})
                        dd[c.id] = other
                        dd[other] = c.id
                        fx.mood(c.id, 6, "dance date")
                        fx.mood(other, 8, "they said yes")
                    else:
                        start_dating(sim, other, c.id, ev, fx)
                else:
                    class _Ctx(dict):
                        pass
                    _rejected(sim, w.chars[other], c.id, ev, fx, rng, {"slot": "after_school"}, dance=bool(ctx.get("dance_key")))
        elif kind == "beat":
            sim.moment_trigger(op[1], c.id, {k: v for k, v in ctx.items() if not k.startswith("_")})  # the scene keeps going
        elif kind == "drama":
            from . import drama
            drama.op(sim, c, op, ctx, fx, ev, rng, m, lambda s: _render(s, names))
        elif kind == "night":
            from . import nights
            nights.op(sim, c, op, ctx, fx, ev, rng, m, lambda s: _render(s, names))
        elif kind == "vibe":
            from . import hangouts
            hangouts.vibe(sim, c, op, ctx, fx, ev, rng, m, lambda s: _render(s, names))
            extra = op[3] if len(op) > 3 and isinstance(op[3], dict) else {}
            if extra.get(ev["data"].get("vibe")):  # what else happens when it lands (or doesn't), written on the outcome
                run_ops(sim, c, extra[ev["data"]["vibe"]], ctx, fx, ev, rng, m)
        elif kind == "say":
            from . import lines
            ev["data"].setdefault("say", []).append(_render(lines.variant(sim, f"say:{m['kind']}", op[1], f"{m['id']}:{len(ev['data'].get('say', []))}"), names))
        elif kind == "text":
            who = _ref(ctx, op[1])
            if "phone" in w.meta and isinstance(who, str) and who in w.chars and who != c.id:
                from . import messages
                messages.add_contact(sim, who, "scene")
                from . import lines
                messages.later(sim, who, "scene", delay_phases=1, text=_render(lines.variant(sim, f"textop:{m['kind']}", op[2], f"{m['id']}:t"), names))
        elif kind == "hang_out":
            who = _ref(ctx, op[1])
            if isinstance(who, str) and who in w.chars and who != c.id:
                control(w)["queued"] = {"action": "hang_out", "target": who, "agreed": True, "day": w.day}
                if ev.get("changes") is not None:
                    ev["changes"].append([c.id, "plans", None, w.chars[who].first, "your choice"])
        elif kind == "remember":
            w.meta.setdefault("remembered", {})[op[1]] = {"day": w.day, "them": ctx.get("them")}
        elif kind == "forget":
            w.meta.setdefault("remembered", {}).pop(op[1], None)
        elif kind == "minigame":
            from . import minigames
            tiers = op[2] if len(op) > 2 and isinstance(op[2], dict) else {}
            spec = op[3] if len(op) > 3 and isinstance(op[3], dict) else {"base": 0.5}
            played = ctx.get("_mg")
            if played:
                tier = played["tier"]
                calc = {"step": "you played it", "terms": [["your score", f"{played['score']:g} of {played['max']:g}"]], "p": played["pct"],
                        "outcome": tier, "rule": "great at 80%+, good at 50%+"}
            else:
                tier, p, roll = minigames.fallback(c, spec, rng)
                calc = {"step": "how it went (not played)", "terms": [["odds", p]], "p": p, "roll": roll, "outcome": tier,
                        "rule": "nobody played it, so it rolls against your own stats"}
            if ev.get("calc") is not None:
                ev["calc"].append(calc)
            ev["data"]["minigame"] = {"game": minigames.resolve_game(op[1], ctx), "tier": tier, "played": bool(played),
                                      "score": played and played["score"], "max": played and played["max"]}
            ev["data"]["outcome"] = {"great": "success", "good": "success", "miss": "setback"}[tier]
            if c.id == w.meta.get("protagonist"):  # a sport's mini game on your game day: it's the game's big moment
                from . import gameplay
                gameplay.scene_play(sim, c, minigames.resolve_game(op[1], ctx), tier, played, m.get("title") or "a scene")
            run_ops(sim, c, tiers.get(tier) or [], ctx, fx, ev, rng, m)
        elif kind == "clutch":
            fx.flag(c.id, "game_clutch", op[1], m["title"])
            fx.flag(c.id, "game_clutch_day", w.day, m["title"])
            from . import gameplay
            mg = ctx.get("_mg")
            tier = "great" if op[1] >= 6 else "good" if op[1] > 0 else "miss"
            gameplay.note_play(sim, c, (mg or {}).get("tier") or tier, mg, ctx.get("sport_id") or ctx.get("sport"), "game day")
        elif kind == "chance":
            spec, ok_ops, bad_ops = op[1], op[2], op[3]
            terms = [["baseline", spec.get("base", 0.5)]]
            for k, coef in spec.items():
                if k == "base":
                    continue
                v = c.traits.get(k, c.aptitudes.get(k, c.skills.get(k, 50)))
                terms.append([f"{k} {v:.0f}", round(coef * (v - 50) / 100, 3)])
            p = clamp(sum(t[1] for t in terms), 0.05, 0.95)
            roll = rng.random()
            ok = roll < p
            if ev.get("calc") is not None:
                ev["calc"].append({"step": "how it goes", "terms": terms, "p": round(p, 3), "roll": round(roll, 4),
                                   "outcome": "it worked" if ok else "it didn't go your way",
                                   "rule": "chance = baseline + each trait's pull; a choice never guarantees the outcome"})
            ev["data"]["outcome"] = "success" if ok else "setback"
            run_ops(sim, c, ok_ops if ok else bad_ops, ctx, fx, ev, rng, m)
