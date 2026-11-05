"""Pets: real animals with needs, a bond with each person, tricks, and chores somebody has to do.

The protagonist's household pets are full entities (w.meta["pets"]). Each pet has a set of duties
(breakfast, dinner, walks, litter...) and the family decides once who does what
(w.meta["responsibilities"]). Every night the duties resolve: whoever owns a duty does it or doesn't,
based on who they are and how their day went, and the pet, the family and the group chat react.
The protagonist can also do things with the pet from the phone: quick ones (a treat, a cuddle, feeding)
happen right away; longer ones (a walk, the park, fetch, training) use a free part of the day.
"""
from __future__ import annotations

import zlib

from . import calendar as calm
from .history import Effects
from .rng import clamp

SPECIES = {
    "dog": {"label": "Dog", "breeds": ["Golden Retriever", "Labrador", "Beagle", "Goldendoodle", "German Shepherd", "Border Collie",
                                        "Boxer", "Corgi", "Bernese Mountain Dog", "Rescue mix"],
            "coats": ["golden", "black", "chocolate", "cream", "tricolor", "brindle", "gray", "white"],
            "duties": ["feed_am", "feed_pm", "walk", "bath"]},
    "cat": {"label": "Cat", "breeds": ["Domestic shorthair", "Maine Coon", "Siamese", "Tabby", "Ragdoll", "Tuxedo"],
            "coats": ["orange", "gray", "black", "white", "calico", "tabby"],
            "duties": ["feed_am", "feed_pm", "litter", "brush"]},
    "rabbit": {"label": "Rabbit", "breeds": ["Holland Lop", "Mini Rex", "Lionhead", "Dutch"],
               "coats": ["white", "brown", "gray", "black", "spotted"],
               "duties": ["feed_am", "feed_pm", "cage", "brush"]},
}
DUTIES = {
    "feed_am": {"label": "Breakfast", "noun": "breakfast", "a": "breakfast", "when": "morning", "every": 1, "energy": 1, "hint": "Before school"},
    "feed_pm": {"label": "Dinner", "noun": "dinner", "a": "dinner", "when": "evening", "every": 1, "energy": 1, "hint": "Around six"},
    "walk": {"label": "Walks", "noun": "walk", "a": "a walk", "when": "evening", "every": 1, "energy": 4, "hint": "Every day, rain or shine"},
    "bath": {"label": "Bath", "noun": "bath", "a": "a bath", "when": "weekend", "every": 7, "energy": 4, "hint": "Once a week"},
    "litter": {"label": "Litter box", "noun": "litter box", "a": "a clean litter box", "when": "evening", "every": 1, "energy": 2, "hint": "Every day. Nobody likes this one."},
    "brush": {"label": "Brushing", "noun": "brushing", "a": "a brushing", "when": "weekend", "every": 7, "energy": 2, "hint": "Once a week"},
    "cage": {"label": "Clean the cage", "noun": "cage cleaning", "a": "a clean cage", "when": "weekend", "every": 7, "energy": 3, "hint": "Once a week"},
}
TRICKS = {"dog": ["sit", "shake", "lie down", "roll over", "high five", "play dead"],
          "cat": ["come when called", "high five", "sit"],
          "rabbit": ["come when called", "spin"]}
ACTIVITIES = {
    # everything with your pet is a quick tap: it happens right away, a few times a day, and never uses up your free time
    # ("action" is what everyone else in the house does with a free part of their day)
    "feed": {"label": "Feed", "quick": True, "per_day": 2},
    "walk": {"label": "Go for a walk", "quick": True, "per_day": 2, "action": "pet_walk", "species": ["dog"]},
    "play": {"label": "Play", "quick": True, "per_day": 2, "action": "pet_play"},
    "cuddle": {"label": "Cuddle", "quick": True, "per_day": 3},
    "treat": {"label": "Give a treat", "quick": True, "per_day": 3},
    "park": {"label": "Take to the park", "quick": True, "per_day": 1, "action": "pet_park", "species": ["dog"]},
    "train": {"label": "Teach a trick", "quick": True, "per_day": 1, "action": "pet_train"},
    "brush": {"label": "Brush", "quick": True, "per_day": 1},
    "clean": {"label": "Clean up", "quick": True, "per_day": 1},
}
CLEAN = {"dog": ("bath", "Give a bath"), "cat": ("litter", "Clean the litter box"), "rabbit": ("cage", "Clean the cage")}
OWNERS = ("me", "parents", "rotate")


def pets(w) -> dict:
    return w.meta.setdefault("pets", {})


def resp(w) -> dict:
    return w.meta.setdefault("responsibilities", {})


def household_pets(w, hid) -> list:
    return [p for p in pets(w).values() if p["household"] == hid and p.get("status", "home") != "gone"]


def _h(*parts) -> int:
    return zlib.crc32(":".join(str(p) for p in parts).encode())


def make_pet(sim, hid, species, name, breed=None, coat=None, age_years=None, day=None):
    w = sim.w
    sp = SPECIES.get(species) or SPECIES["dog"]
    n = len(pets(w)) + 1
    pid = f"pet{n}"
    while pid in pets(w):
        n += 1
        pid = f"pet{n}"
    seed = _h(hid, name, species)
    day = w.day if day is None else day
    age = age_years if age_years is not None else (1 + seed % 6)
    pet = {"id": pid, "name": name, "species": species if species in SPECIES else "dog",
           "breed": breed or sp["breeds"][seed % len(sp["breeds"])], "coat": coat or sp["coats"][(seed // 7) % len(sp["coats"])],
           "household": hid, "adopted": day, "born": day - int(age * 365), "status": "home",
           "personality": ["energetic", "cuddly", "goofy", "chill", "stubborn", "anxious"][(seed // 13) % 6],
           "happiness": 75.0, "fullness": 80.0, "energy": 70.0, "health": 92.0, "clean": 80.0,
           "bond": {}, "tricks": {}, "today": {}, "streaks": {}, "log": []}
    h = w.households.get(hid)
    if h:
        for m in h["members"]:
            pet["bond"][m] = 40.0 + (_h(pid, m) % 25)
    pets(w)[pid] = pet
    return pet


def ensure(sim):
    """Make the protagonist's household pet a full pet (once), from the household's pet line."""
    w = sim.w
    prot = w.meta.get("protagonist")
    c = w.chars.get(prot) if prot else None
    if not c or not c.household_id:
        return
    h = w.households.get(c.household_id)
    if h and h.get("pet") and not household_pets(w, c.household_id) and not w.meta.get("pets_seeded"):
        make_pet(sim, c.household_id, h["pet"]["species"], h["pet"]["name"], breed=h["pet"].get("breed"), coat=h["pet"].get("coat"), day=w.day)
    w.meta["pets_seeded"] = True


def pronoun(pet) -> tuple:
    return ("she", "her") if _h(pet["id"], "sex") % 2 else ("he", "his")


def age_years(w, pet) -> int:
    return max(0, (w.day - pet["born"]) // 365)


def setup_needed(w, pid) -> bool:
    return not resp(w).get(pid, {}).get("set_up")


def default_duties(sim, pet) -> dict:
    return {d: "parents" for d in SPECIES[pet["species"]]["duties"]}


def set_duties(sim, pid, duties: dict, by="you"):
    w = sim.w
    pet = pets(w)[pid]
    kids = _kids(sim, pet)
    clean = {}
    for d in SPECIES[pet["species"]]["duties"]:
        o = duties.get(d, "parents")
        if o not in OWNERS and o not in kids:
            raise ValueError(f"{DUTIES[d]['label']}: pick me, a sibling, parents or take turns")
        clean[d] = o
    first = setup_needed(w, pid)
    resp(w)[pid] = {"set_up": True, "duties": clean, "day": w.day}
    prot = w.meta.get("protagonist")
    mine = [DUTIES[d]["noun"] if DUTIES[d]["every"] == 1 and d != "walk" else ("walks" if d == "walk" else DUTIES[d]["noun"]) for d, o in clean.items() if o in ("me", prot)]
    turns = [DUTIES[d]["label"].lower() for d, o in clean.items() if o == "rotate"]
    ev = sim.new_event("pet", "chores_set", [prot], [], 18 if first else 8, {"label": pet["name"]})
    parts = []
    if mine:
        parts.append(f"you're on {', '.join(mine)}")
    if turns:
        parts.append(f"you take turns on {', '.join(turns)}")
    ev["text"] = f"The family split up {pet['name']}'s chores: " + ("; ".join(parts) if parts else "your parents have it covered") + "."
    sim.finish(ev, Effects(w, ev))
    from . import messages
    if first and mine:
        messages.family_text(sim, "pet_chores_set", pet=pet["name"], chores=", ".join(mine))
    return resp(w)[pid]


def _kids(sim, pet) -> list:
    w = sim.w
    h = w.households.get(pet["household"]) or {"members": []}
    return [m for m in h["members"] if m in w.chars and w.chars[m].role in ("student", "alumni") and w.chars[m].status == "active"]


def owner_today(sim, pet, duty) -> str | None:
    """Who is supposed to do this duty today: a character id, or 'parents'."""
    w = sim.w
    o = resp(w).get(pet["id"], {}).get("duties", {}).get(duty, "parents")
    prot = w.meta.get("protagonist")
    if o == "me":
        o = prot
    if o == "rotate":
        home = [k for k in _kids(sim, pet) if w.chars[k].location == "hollow_creek"]
        if not home:
            return "parents"
        o = sorted(home)[w.day % len(home)]
    if o != "parents" and (o not in w.chars or w.chars[o].location != "hollow_creek" or w.chars[o].status != "active"):
        return "parents"
    return o


def due_today(duty, day) -> bool:
    every = DUTIES[duty]["every"]
    return every == 1 or calm.weekday(day) == 6


# --- the day ---------------------------------------------------------------------------------

def dawn(sim):
    w = sim.w
    for pet in list(pets(w).values()):
        if pet.get("status", "home") == "gone":
            continue
        pet["today"] = {}
        pet["fullness"] = clamp(pet["fullness"] - 30, 0, 100)
        pet["energy"] = clamp(pet["energy"] + 30, 0, 100)
        pet["clean"] = clamp(pet["clean"] - 3, 0, 100)
        drift = -4 if pet["personality"] != "chill" else -2
        pet["happiness"] = clamp(pet["happiness"] + drift + (pet["fullness"] - 50) * 0.04, 0, 100)


def night(sim):
    """Chores resolve: done or not, and everyone notices."""
    w = sim.w
    prot = w.meta.get("protagonist")
    from . import messages
    for pet in list(pets(w).values()):
        if pet.get("status", "home") == "gone":
            continue
        rng = sim.streams.get("pet-night", w.day, pet["id"])
        missed_by_me = []
        done_by_me = []
        for duty in SPECIES[pet["species"]]["duties"]:
            if not due_today(duty, w.day) or pet["today"].get(duty):
                if pet["today"].get(duty) == prot:
                    done_by_me.append(duty)
                continue
            who = owner_today(sim, pet, duty)
            if who == "parents":
                ok = rng.random() < 0.97
            else:
                c = w.chars[who]
                busy = 0.12 if any(i["kind"] in ("game", "exam") and (i.get("group") in c.memberships or i["kind"] == "exam") for i in sim._today) else 0
                p = 0.78 + (c.traits["discipline"] - 50) / 220 + (c.traits.get("loyalty", 50) - 50) / 600 - busy - max(0, c.needs["stress"] - 65) / 200
                if who == prot:
                    p += 0.08  # it's on your list; you mostly remember
                ok = rng.random() < clamp(p, 0.15, 0.99)
            if ok:
                _do_duty(sim, pet, duty, who)
                if who == prot:
                    done_by_me.append(duty)
            else:
                _miss(pet, duty)
                if who == prot:
                    missed_by_me.append(duty)
                elif who != "parents" and who in w.chars and rng.random() < 0.3:
                    messages.family_text(sim, "pet_sibling_forgot", pet=pet["name"], who=w.chars[who].first, chore=DUTIES[duty]["noun"],
                                         chore_a=DUTIES[duty]["a"])
        st = pet["streaks"]
        if missed_by_me:
            st["me"] = 0
            labels = " and ".join(DUTIES[d]["noun"] for d in missed_by_me)
            labels_a = " or ".join(DUTIES[d]["a"] for d in missed_by_me)
            ev = sim.new_event("pet", "chore_missed", [prot], [], 22, {"label": pet["name"]})
            ev["text"] = f"You forgot {pet['name']}'s {labels} today."
            fx = Effects(w, ev)
            h = w.households.get(pet["household"]) or {}
            pet["bond"][prot] = clamp(pet["bond"].get(prot, 40) - 2, 0, 100)
            fx.mood(prot, -2, f"forgot {pet['name']}")
            sim.finish(ev, fx)
            messages.family_text(sim, "pet_you_forgot", pet=pet["name"], chore=labels, chore_a=labels_a, parent_style=h.get("style", "warm"))
        elif done_by_me:
            st["me"] = st.get("me", 0) + 1
            if st["me"] in (7, 30, 100):
                ev = sim.new_event("pet", "streak", [prot], [], 20, {"label": pet["name"]})
                ev["text"] = f"{st['me']} days straight of taking care of {pet['name']}."
                fx = Effects(w, ev)
                ph = messages.phone(w)
                ph["parent_trust"] = clamp(ph["parent_trust"] + 3, 0, 100)
                fx.mood(prot, 3, "a good streak")
                sim.finish(ev, fx)
                messages.family_text(sim, "pet_streak", pet=pet["name"], n=st["me"])
        if pet["happiness"] < 30 and _h(w.day, pet["id"]) % 4 == 0:
            messages.family_text(sim, "pet_sad", pet=pet["name"])
        pet["health"] = clamp(pet["health"] + (0.5 if pet["fullness"] > 40 else -2) - (0.8 if pet["clean"] < 25 else 0), 0, 100)


def bond_up(pet, cid, amount):
    b = pet["bond"].get(cid, 40.0)
    pet["bond"][cid] = clamp(b + amount * max(0.08, 1 - b / 105), 0, 100)


def _do_duty(sim, pet, duty, who):
    w = sim.w
    pet["today"][duty] = who
    if duty.startswith("feed"):
        pet["fullness"] = clamp(pet["fullness"] + 45, 0, 100)
        pet["happiness"] = clamp(pet["happiness"] + 3, 0, 100)
    elif duty == "walk":
        pet["energy"] = clamp(pet["energy"] - 25, 0, 100)
        pet["happiness"] = clamp(pet["happiness"] + 8, 0, 100)
    else:
        pet["clean"] = clamp(pet["clean"] + 40, 0, 100)
        pet["happiness"] = clamp(pet["happiness"] + 2, 0, 100)
    if who in w.chars:
        bond_up(pet, who, (1.5 if duty == "walk" else 0.5))
        c = w.chars[who]
        c.needs["energy"] = clamp(c.needs["energy"] - DUTIES[duty]["energy"], 0, 100)
        if duty == "walk":
            c.needs["stress"] = clamp(c.needs["stress"] - 2, 0, 100)


def _miss(pet, duty):
    if duty.startswith("feed"):
        pet["happiness"] = clamp(pet["happiness"] - 10, 0, 100)
    elif duty == "walk":
        pet["happiness"] = clamp(pet["happiness"] - 8, 0, 100)
        pet["energy"] = clamp(pet["energy"] + 10, 0, 100)
    else:
        pet["clean"] = clamp(pet["clean"] - 15, 0, 100)
        pet["happiness"] = clamp(pet["happiness"] - 3, 0, 100)


def weekly(sim):
    """Little pet life: a chewed shoe, a cat on the keyboard, a vet trip when health dips."""
    w = sim.w
    prot = w.meta.get("protagonist")
    for pet in list(pets(w).values()):
        if pet.get("status", "home") == "gone" or prot not in w.chars:
            continue
        rng = sim.streams.get("pet-week", w.day, pet["id"])
        if pet["health"] < 55 and rng.random() < 0.6:
            pet["health"] = clamp(pet["health"] + 30, 0, 100)
            ev = sim.new_event("pet", "vet", [prot], [], 24, {"label": pet["name"]})
            ev["text"] = f"{pet['name']} went to the vet and came home with medicine and a cone of shame."
            sim.finish(ev, Effects(w, ev))
            from . import messages
            messages.family_text(sim, "pet_vet", pet=pet["name"])
            continue
        if rng.random() < 0.35 and w.chars[prot].location == "hollow_creek":
            kind = rng.choice({"dog": ["chewed", "zoomies", "stole", "greeted"], "cat": ["keyboard", "knocked", "greeted"],
                               "rabbit": ["binky", "chewed"]}[pet["species"]])
            he, his = pronoun(pet)
            text = {"chewed": f"{pet['name']} chewed up one of your shoes. Just one. The left one.",
                    "zoomies": f"{pet['name']} got the zoomies in the living room and knocked over a lamp.",
                    "stole": f"{pet['name']} stole a slice of pizza off the counter and looked zero percent sorry.",
                    "greeted": f"{pet['name']} lost {his} mind with joy when you got home.",
                    "keyboard": f"{pet['name']} walked across your laptop mid-assignment and typed 'jjjjjjjjjj'.",
                    "knocked": f"{pet['name']} knocked a glass off the counter while making eye contact with you.",
                    "binky": f"{pet['name']} did a happy jump-twist across the living room."}[kind]
            ev = sim.new_event("pet", kind, [prot], [], 12, {"label": pet["name"]})
            ev["text"] = text
            fx = Effects(w, ev)
            fx.mood(prot, 2 if kind in ("greeted", "binky", "zoomies") else -1, pet["name"])
            sim.finish(ev, fx)


def greet_after(sim, cid, why):
    """A pet who loves you notices a bad day."""
    w = sim.w
    c = w.chars.get(cid)
    if not c or c.location != "hollow_creek":
        return
    for pet in household_pets(w, c.household_id):
        if pet["bond"].get(cid, 0) >= 60:
            ev = sim.new_event("pet", "comfort", [cid], [], 14, {"label": pet["name"]})
            ev["text"] = f"After {why}, {pet['name']} was waiting at the door like nothing else mattered."
            fx = Effects(w, ev)
            fx.mood(cid, 4, f"{pet['name']}")
            fx.need(cid, "stress", -4, f"{pet['name']}")
            sim.finish(ev, fx)
            return


# --- doing things together ---------------------------------------------------------------------

def quick(sim, pid, activity):
    """Treats, cuddles, feeding: immediate, a few times a day."""
    w = sim.w
    prot = w.meta.get("protagonist")
    pet = pets(w).get(pid)
    if not pet:
        raise ValueError("no such pet")
    c = w.chars[prot]
    if c.location != "hollow_creek" or c.household_id != pet["household"]:
        raise ValueError(f"{pet['name']} is at home and you're not")
    spec = ACTIVITIES.get(activity)
    if not spec or not spec.get("quick"):
        raise ValueError("that isn't a quick thing to do")
    used = pet["today"].get(f"q:{activity}", 0)
    if spec.get("species") and pet["species"] not in spec["species"]:
        raise ValueError(f"You can't really {spec['label'].lower()} with a {pet['species']}.")
    if used >= spec["per_day"]:
        raise ValueError({"treat": f"{pet['name']} has had enough treats today.", "cuddle": f"{pet['name']} has been cuddled plenty today.",
                          "feed": f"{pet['name']} has eaten.", "brush": "Already brushed today.", "walk": f"{pet['name']} is walked out for today.",
                          "park": "One park trip a day is plenty.", "play": f"{pet['name']} is tired out. Tomorrow.",
                          "train": f"{pet['name']} has learned enough for one day.", "clean": "Already done today."}[activity])
    pet["today"][f"q:{activity}"] = used + 1
    he, his = pronoun(pet)
    ev = sim.new_event("pet", activity, [prot], [], 6, {"label": pet["name"]})
    fx = Effects(w, ev)
    bond0 = pet["bond"].get(prot, 40)
    if activity == "cuddle":
        pet["happiness"] = clamp(pet["happiness"] + 4, 0, 100)
        bond_up(pet, prot, 1.2)
        fx.need(prot, "stress", -5, f"cuddling {pet['name']}")
        fx.mood(prot, 2, pet["name"])
        ev["text"] = {"dog": f"You sat on the floor with {pet['name']} and {he} rolled over for belly rubs.",
                      "cat": f"{pet['name']} decided, on {his} own terms, to curl up on your lap.",
                      "rabbit": f"{pet['name']} flopped next to you and let you pet {his} ears."}[pet["species"]]
    elif activity == "treat":
        pet["happiness"] = clamp(pet["happiness"] + 5, 0, 100)
        bond_up(pet, prot, 0.8)
        if used >= 2:
            pet["health"] = clamp(pet["health"] - 1, 0, 100)
        ev["text"] = f"You gave {pet['name']} a treat. Instant best friends." if used == 0 else f"Another treat for {pet['name']}. {he.capitalize()} is not complaining."
    elif activity == "feed":
        meal = "feed_am" if sim.current_phase() in ("dawn", "classes", "lunch", "day") else "feed_pm"
        if pet["today"].get(meal):
            pet["today"][f"q:{activity}"] = used
            raise ValueError(f"{pet['name']} already had {DUTIES[meal]['label'].lower()}.")
        _do_duty(sim, pet, meal, prot)
        bond_up(pet, prot, 0.5)
        ev["text"] = f"You fed {pet['name']} {DUTIES[meal]['label'].lower()}. {he.capitalize()} inhaled it."
    elif activity == "brush":
        pet["clean"] = clamp(pet["clean"] + 25, 0, 100)
        pet["happiness"] = clamp(pet["happiness"] + 2, 0, 100)
        if "brush" in SPECIES[pet["species"]]["duties"] and not pet["today"].get("brush"):
            pet["today"]["brush"] = prot
        ev["text"] = f"You brushed {pet['name']}. There is now enough fur on the floor to build a second {pet['species']}."
    elif activity == "clean":
        duty, label = CLEAN[pet["species"]]
        if duty in SPECIES[pet["species"]]["duties"] and pet["today"].get(duty):
            pet["today"][f"q:{activity}"] = used
            raise ValueError("Already done today.")
        _do_duty(sim, pet, duty, prot)
        ev["text"] = {"bath": f"You gave {pet['name']} a bath. You are now wetter than {he} is.",
                      "litter": "You cleaned the litter box. Nobody thanked you. Somebody should.",
                      "cage": f"You cleaned {pet['name']}'s cage. {he.capitalize()} immediately kicked hay everywhere."}[duty]
    else:  # walks, the park, playing, training: quick now, the same as when they took up your afternoon
        rng = sim.streams.get("pet-quick", w.day, pid, activity, used)
        ev["type"] = "pet_" + activity
        _timed(sim, c, pet, activity, ev, fx, rng)
    sim.finish(ev, fx)
    return {"text": ev["text"], "pet": view(sim, pet)}


def timed_resolve(sim, c, cand, ev, fx, rng, ctx):
    """Resolver for pet_walk / pet_park / pet_play / pet_train (used by everyone in the household)."""
    w = sim.w
    kind = cand.a["params"]["kind"]
    hp = household_pets(w, c.household_id)
    pet = next((p for p in hp if p["id"] == (cand.extra or {}).get("pet")), hp[0] if hp else None)
    if pet is None:
        ev["outcome"] = "no_pet"
        return
    _timed(sim, c, pet, kind, ev, fx, rng, (cand.extra or {}).get("trick"))


def _timed(sim, c, pet, kind, ev, fx, rng, trick=None):
    w = sim.w
    he, his = pronoun(pet)
    you = c.id == w.meta.get("protagonist")
    name = "You" if you else c.short
    ev["data"]["label"] = pet["name"]
    ev["outcome"] = kind
    q = 0.5 + (c.traits["empathy"] - 50) / 200 + rng.gauss(0, 0.15)
    bond0 = pet["bond"].get(c.id, 40)
    if kind in ("walk", "park"):
        pet["energy"] = clamp(pet["energy"] - (30 if kind == "park" else 22), 0, 100)
        pet["happiness"] = clamp(pet["happiness"] + (14 if kind == "park" else 9), 0, 100)
        pet["today"]["walk"] = pet["today"].get("walk") or c.id
        bond_up(pet, c.id, 2.5)
        fx.need(c.id, "stress", -8, f"walking {pet['name']}")
        fx.need(c.id, "fun", 6, pet["name"])
        fx.need(c.id, "energy", -5, "a long walk")
        fx.skill(c.id, "fitness", 0.15, f"walking {pet['name']}")
        summer = calm.date_of(w.day).month in (6, 7, 8)
        place = "Jacobs Beach" if (kind == "park" and summer) else "the Guilford Green" if kind == "park" else "the neighborhood"
        ev["data"]["place"] = place
        ev["text"] = (f"{name} took {pet['name']} to {place}. {he.capitalize()} sniffed every single tree."
                      if kind == "park" else f"{name} walked {pet['name']} around {place} as the streetlights came on.")
        if kind == "park":
            _park_meeting(sim, c, pet, place, ev, fx, rng)
    elif kind == "play":
        pet["energy"] = clamp(pet["energy"] - 15, 0, 100)
        pet["happiness"] = clamp(pet["happiness"] + 10, 0, 100)
        bond_up(pet, c.id, 2.0)
        fx.need(c.id, "fun", 10, f"playing with {pet['name']}")
        fx.need(c.id, "stress", -6, pet["name"])
        poss = "your" if you else "their"
        ev["text"] = {"dog": f"{name} played fetch with {pet['name']} in the backyard until {poss} arm gave out.",
                      "cat": f"{name} chased the laser pointer around with {pet['name']} until {pet['name']} pretended not to care.",
                      "rabbit": f"{name} built {pet['name']} an obstacle course out of shoe boxes."}[pet["species"]]
    elif kind == "train":
        tricks = TRICKS[pet["species"]]
        target = trick
        learning = [t for t in tricks if pet["tricks"].get(t, 0) < 100]
        if target not in learning:
            target = learning[0] if learning else tricks[-1]
        patience = (c.traits["discipline"] + c.traits["empathy"]) / 200
        mood_f = 0.6 + pet["happiness"] / 250 + (0.15 if pet["personality"] in ("goofy", "energetic") else -0.1 if pet["personality"] == "stubborn" else 0)
        gain = (12 + 22 * patience) * mood_f + rng.gauss(0, 5)
        before = pet["tricks"].get(target, 0)
        pet["tricks"][target] = clamp(before + max(3, gain), 0, 100)
        bond_up(pet, c.id, 1.5)
        pet["energy"] = clamp(pet["energy"] - 10, 0, 100)
        fx.need(c.id, "fun", 5, f"training {pet['name']}")
        ev["data"]["trick"] = target
        if before < 100 <= pet["tricks"][target]:
            ev["outcome"] = "learned"
            ev["importance"] = 22
            ev["text"] = f"{pet['name']} learned to {target}! {name} {'were' if you else 'was'} way too proud."
            fx.mood(c.id, 5, f"{pet['name']} learned a trick")
        else:
            ev["text"] = (f"{name} worked on '{target}' with {pet['name']}. "
                          + ("Real progress." if gain > 18 else "Some progress, mostly treats." if gain > 9 else f"{he.capitalize()} mostly wanted to chase {his} tail."))
        ev["data"]["progress"] = round(pet["tricks"][target])
    fx.mood(c.id, 2 * q, pet["name"])


def _park_meeting(sim, c, pet, place, ev, fx, rng):
    """At the park you run into people. Sometimes someone you know, sometimes someone new."""
    w = sim.w
    if rng.random() > 0.45:
        return
    busy = sim.slot.engaged if sim.slot is not None else {}
    pool = [o for o in w.chars.values() if o.id != c.id and o.status == "active" and o.role == "student" and o.location == c.location
            and o.id not in busy and o.id not in (w.households.get(c.household_id) or {}).get("members", [])]
    if not pool:
        return
    pool.sort(key=lambda o: o.id)
    o = pool[int(rng.random() * len(pool))]
    if sim.slot is not None:
        sim.engage(o.id, c.id)
    r = w.ensure_rel(c.id, o.id, w.day)
    met = r.familiarity > 5
    ev["targets"] = [o.id]
    ev["text"] += (f" {o.short} was there too and came over to say hi to {pet['name']}." if met
                   else f" A {o.year_label.lower()} named {o.short} stopped to pet {pet['name']}, and you two got talking.")
    for a, b in ((c.id, o.id), (o.id, c.id)):
        fx.rel(a, b, "familiarity", 6, f"ran into each other at {place}")
        fx.rel(a, b, "affection", 3, f"{pet['name']} broke the ice")
    if c.id == w.meta.get("protagonist"):
        from . import messages
        messages.later(sim, o.id, "park_followup", pet=pet["name"], place=place)


def queue(sim, pid, activity, trick=None):
    """Plan a longer activity for your next free part of the day."""
    w = sim.w
    spec = ACTIVITIES.get(activity)
    pet = pets(w).get(pid)
    if not spec or spec.get("quick") or not pet:
        raise ValueError("unknown activity")
    if spec.get("species") and pet["species"] not in spec["species"]:
        raise ValueError(f"You can't really {spec['label'].lower()} with a {pet['species']}.")
    q = {"action": spec["action"], "pet": pid, "day": w.day, "label": f"{spec['label']} with {pet['name']}"}
    if trick:
        q["trick"] = trick
    w.meta.setdefault("control", {})["queued"] = q
    return q


def view(sim, pet) -> dict:
    w = sim.w
    prot = w.meta.get("protagonist")
    he, his = pronoun(pet)
    duties = []
    r = resp(w).get(pet["id"], {})
    for d in SPECIES[pet["species"]]["duties"]:
        who = r.get("duties", {}).get(d, "parents")
        today = owner_today(sim, pet, d) if r.get("set_up") else "parents"
        duties.append({"id": d, "label": DUTIES[d]["label"], "hint": DUTIES[d]["hint"], "when": DUTIES[d]["when"], "owner": who,
                       "today": today, "due": due_today(d, w.day), "done": bool(pet["today"].get(d)), "done_by": pet["today"].get(d)})
    mood = ("thrilled" if pet["happiness"] >= 85 else "happy" if pet["happiness"] >= 65 else "okay" if pet["happiness"] >= 45
            else "mopey" if pet["happiness"] >= 25 else "miserable")
    return {"id": pet["id"], "name": pet["name"], "species": pet["species"], "species_label": SPECIES[pet["species"]]["label"],
            "breed": pet["breed"], "coat": pet["coat"], "personality": pet["personality"], "age": age_years(w, pet),
            "pronoun": he, "possessive": his, "mood": mood,
            "happiness": round(pet["happiness"]), "fullness": round(pet["fullness"]), "energy": round(pet["energy"]),
            "health": round(pet["health"]), "clean": round(pet["clean"]),
            "bond": {k: round(v) for k, v in pet["bond"].items()}, "my_bond": round(pet["bond"].get(prot, 0)),
            "tricks": [{"name": t, "progress": round(pet["tricks"].get(t, 0))} for t in TRICKS[pet["species"]]],
            "duties": duties, "setup_needed": setup_needed(w, pet["id"]), "streak": pet["streaks"].get("me", 0),
            "quick_left": {a: ACTIVITIES[a]["per_day"] - pet["today"].get(f"q:{a}", 0) for a, s in ACTIVITIES.items() if s.get("quick")},
            "activities": [{"id": a, "label": CLEAN[pet["species"]][1] if a == "clean" else s["label"], "quick": True}
                           for a, s in ACTIVITIES.items() if not s.get("species") or pet["species"] in s["species"]],
            "adopted": calm.label(pet["adopted"])}


# --- getting a pet ---------------------------------------------------------------------------

def ask_for_pet(sim, species):
    """Ask the parents. Their answer comes from who they are and how you've been doing."""
    w = sim.w
    prot = w.meta.get("protagonist")
    c = w.chars[prot]
    h = w.households.get(c.household_id)
    if not h:
        raise ValueError("you don't live at home right now")
    if species not in SPECIES:
        raise ValueError("pick a dog, cat or rabbit")
    last = w.meta.get("pet_asked", -999)
    if w.day - last < 21:
        raise ValueError(f"You just asked. Give it until {calm.label(last + 21)}.")
    w.meta["pet_asked"] = w.day
    from . import messages
    have = len(household_pets(w, c.household_id))
    terms = [["warmth", (h["warmth"] - 50) / 100], ["permissive", (h["permissive"] - 50) / 120],
             ["money at home", {"low": -0.25, "middle": 0.0, "high": 0.12}[h["income"]]],
             ["your grades", (c.gpa - 3.0) * 0.25], ["already have a pet", -0.25 * have],
             ["how much they trust you", (messages.phone(w)["parent_trust"] - 60) / 150]]
    p = clamp(0.35 + sum(t[1] for t in terms), 0.03, 0.92)
    rng = sim.streams.get("pet-ask", w.day)
    roll = rng.random()
    yes = roll < p
    ev = sim.new_event("pet", "asked", [prot], [], 20, {"label": species})
    ev["calc"] = [{"step": "your parents decide", "terms": [[k, round(v, 3)] for k, v in terms], "p": round(p, 3), "roll": round(roll, 4)}]
    reason = None
    if yes:
        ev["text"] = f"You asked for a {species}. After a long look between your parents: yes."
    else:
        reason = ("Not with money as tight as it is." if h["income"] == "low" else
                  "Maybe if your grades come up." if c.gpa < 3.0 else
                  "We already have our hands full." if have else
                  "Who's going to take care of it when you're busy? Ask again in a few weeks.")
        ev["text"] = f"You asked for a {species}. The answer: not right now. \"{reason}\""
    fx = Effects(w, ev)
    fx.mood(prot, 6 if yes else -3, "asked for a pet")
    sim.finish(ev, fx)
    if yes:
        w.meta["pet_approved"] = {"species": species, "day": w.day}
    return {"yes": yes, "p": round(p, 2), "reason": reason, "text": ev["text"]}


def adopt(sim, species, name, breed=None, coat=None):
    w = sim.w
    prot = w.meta.get("protagonist")
    c = w.chars[prot]
    ok = w.meta.get("pet_approved")
    if not ok or ok["species"] != species:
        raise ValueError("ask your parents first")
    name = (name or "").strip()[:20]
    if not name:
        raise ValueError("every pet needs a name")
    sp = SPECIES[species]
    if breed and breed not in sp["breeds"]:
        raise ValueError(f"pick one of: {', '.join(sp['breeds'])}")
    if coat and coat not in sp["coats"]:
        raise ValueError(f"pick a coat: {', '.join(sp['coats'])}")
    pet = make_pet(sim, c.household_id, species, name, breed=breed, coat=coat, age_years=0 if species != "rabbit" else 1)
    pet["bond"][prot] = 60.0
    h = w.households.get(c.household_id)
    if h and not h.get("pet"):
        h["pet"] = {"species": species, "name": name, "breed": pet["breed"]}
    w.meta.pop("pet_approved", None)
    ev = sim.new_event("pet", "adopted", [prot], [], 40, {"label": name})
    ev["text"] = f"You brought {name} home: a {pet['breed'].lower()} {'puppy' if species == 'dog' else 'kitten' if species == 'cat' else 'bunny'}."
    fx = Effects(w, ev)
    fx.mood(prot, 10, f"brought {name} home")
    fx.memory(prot, "pet_adopted", [], 0.9, 85, f"The day we brought {name} home")
    for s in sim.siblings(prot):
        fx.mood(s, 5, f"{name} came home")
    sim.finish(ev, fx)
    from . import messages
    messages.family_text(sim, "pet_adopted", pet=name)
    return view(sim, pet)
