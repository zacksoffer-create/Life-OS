"""Bigger schools, and the people you make who start high school later: younger siblings and future freshmen."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402

from lifeos import calendar as calm  # noqa: E402
from lifeos.engine import Simulation  # noqa: E402
from lifeos.story import StoryError, arrive, begin, create_story, incoming_view  # noqa: E402
from tests.test_story import spec  # noqa: E402


def future_spec(**kw):
    s = spec(per=6, **kw)
    s["siblings"].append({"key": "lil", "first": "Sam", "gender": "m", "grade": 8, "strength": 20})
    s["cast"] += [{"key": "kid", "first": "Nora", "last": "Vale", "gender": "f", "grade": 7,
                   "relationships": [{"to": "me", "type": "neighbor"}]},
                  {"key": "pal", "first": "Theo", "last": "Marsh", "gender": "m", "grade": 9,
                   "relationships": [{"to": "kid", "type": "best_friend"}]}]
    return s


def test_younger_kids_wait_in_middle_school_until_their_freshman_year():
    w = create_story(future_spec())
    keys = w.meta["story"]["keys"]
    assert "lil" not in keys and "kid" not in keys and "pal" in keys
    assert not any(c.first in ("Sam", "Nora") and c.custom for c in w.chars.values())
    view = {x["key"]: x for x in incoming_view(w)}
    assert view["lil"]["year_label"] == "8th grade" and view["lil"]["starts"] == "Starts high school next fall"
    assert view["kid"]["year_label"] == "7th grade" and view["kid"]["starts"] == "Starts high school in 2 years"
    # they don't count against this year's classes
    assert sum(1 for c in w.students() if c.grade == 9) >= 6
    sim = Simulation(w)
    begin(sim)
    me = w.chars[w.meta["protagonist"]]
    assert not arrive(sim, 0), "nobody's due the first fall"
    # next fall: your little brother starts high school, in your house, as your brother
    (sam,) = arrive(sim, 1)
    assert sam.first == "Sam" and sam.grade == 9 and sam.custom and sam.household_id == me.household_id
    assert sam.id in sim.siblings(me.id) and w.rels[(me.id, sam.id)].familiarity >= 90
    assert calm.date_of(sam.birth_day).year == calm.START.year - 13, "a year younger than you"
    assert keys["lil"] == sam.id and [x["key"] for x in incoming_view(w)] == ["kid"]
    assert not arrive(sim, 1), "a person arrives once"
    # the fall after: the neighbor kid, and the friendship you described for her comes with her
    (nora,) = arrive(sim, 2)
    assert nora.last == "Vale" and nora.grade == 9 and nora.household_id != me.household_id
    assert w.rels[(keys["pal"], nora.id)].affection >= 80, "Theo's best friend arrives as his best friend"
    assert (me.id, nora.id) in w.rels and not incoming_view(w)


def test_your_little_brother_shows_up_with_the_freshman_class_on_sept_1():
    w = create_story(future_spec())
    sim = Simulation(w)
    begin(sim)
    me = w.chars[w.meta["protagonist"]]
    y1 = calm.md_to_day(1, sim.cat.world["calendar"]["school_year_start"])
    sim.advance_days(y1 - w.day + 1)
    sam = w.chars[w.meta["story"]["keys"]["lil"]]
    assert sam.grade == 9 and sam.status == "active" and me.grade == 10
    feed = [w.history.events[e] for e in w.history.by_char[me.id] if e in w.history.events]
    hello = [e for e in feed if e["type"] == "new_year" and e["outcome"] == "arrived" and sam.id in e["actors"]]
    assert hello and "little brother Sam" in hello[0]["text"]
    from lifeos import pov
    assert pov.event_line(w, hello[0], me.id).startswith("Your little brother Sam starts at")
    # the freshman class is still about the size of the class that graduated: Sam took one of the spots
    started = next(e for e in w.history.events.values() if e["type"] == "new_year" and e["outcome"] == "started")
    assert sam.id in started["data"]["freshmen"] and len(started["data"]["freshmen"]) == max(1, w.meta["graduated_last"])
    from lifeos import phone_api
    assert phone_api.incoming_view(w) and all(x["key"] != "lil" for x in phone_api.incoming_view(w))


def test_bigger_schools_and_their_rosters():
    w = create_story(spec(per=24))
    assert len([c for c in w.students() if c.grade == 9]) >= 24
    assert w.groups["football"]["capacity"] == 32 and w.groups["football"]["jv_capacity"] == 24
    assert create_story(spec(per=40))
    with pytest.raises(StoryError):
        create_story(spec(per=41))
    with pytest.raises(StoryError, match="6, 7 or 8"):
        s = spec(per=6)
        s["cast"].append({"first": "Tiny", "gender": "m", "grade": 5})
        create_story(s)
    with pytest.raises(StoryError):
        create_story(spec(per=6, grade=8))  # you start in high school
