"""Dialogue packs: more lines, more reply options, more narration, more choices, and whole new scenes, from one JSON file.

Anyone can write a pack: you, ChatGPT, Claude. A pack only ever adds. The base content stays in data/*.json and the code;
packs layer on top in load order:
  1. built-in packs shipped with the game:   backend/data/dialogue/*.json
  2. your packs, loaded in the app:          USER_DIR (the lab: lifeos/var/dialogue; the phone: its own storage)

A pack has up to five sections:
  texts           more lines for a text-message pool        {"chatter_school": ["did u finish the lab"]}
  replies         more reply buttons for a reply set        {"chatter_school": [["send it to me pls", "warm"]]}
  narration       more lines for the story feed             {"study.focused": ["{a} finally got the chem stuff to click."]}
  moment_choices  extra choices on an existing moment       {"rumor": [{"label": ..., "ops": [...]}]}
  scenes          brand-new moments, with rules for when they can happen and who they're about

check(pack) explains every problem in plain words, so a writer (or an AI) can fix it. guide_markdown() and PROMPT are
generated from the real game data, so they're never out of date.
"""
from __future__ import annotations

import copy
import difflib
import json
import os
import re

from . import lines as _lines
from .catalogs import APTITUDES, TRAITS, _base, DATA_DIR

BUILTIN_DIR = os.path.join(DATA_DIR, "dialogue")
USER_DIR = os.environ.get("LIFEOS_DIALOGUE") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "var", "dialogue")

SECTIONS = ("texts", "replies", "narration", "moment_choices", "scenes", "trivia", "mods", "chat", "schedule", "groupchat")
MOD_KINDS = {"open": "said before a text (\"ok so\", \"u up?\")", "close": "tacked on after a text (\"lol\")",
             "talk": "how a line is said in person: \"{them_first} {says}, grinning\" ({says} becomes says or asks)"}
PH = re.compile(r"\{(\w+)\}")
SLUG = re.compile(r"^[a-z][a-z0-9_]{2,79}$")   # ids and remembered facts: lowercase, digits, underscores, up to 80 long


def _slug_problem(v) -> str:
    """Why a name isn't a good id, in words."""
    if not isinstance(v, str) or not v:
        return "needs a short lowercase id with underscores, like cover_for_me"
    if len(v) > 80:
        return f"is {len(v)} characters; keep it under 80"
    if not re.match(r"^[a-z]", v):
        return f"'{v}' has to start with a lowercase letter"
    bad = sorted(set(re.sub(r"[a-z0-9_]", "", v)))
    if bad:
        return f"'{v}' can only have lowercase letters, digits and underscores (it has {' '.join(repr(c) for c in bad)})"
    return f"'{v}' is too short; use at least 3 characters"

# ---------------------------------------------------------------------------------------- vocabulary

REPLY_TONES = {
    "warm": "Friendly. They like you a little more and feel you care.",
    "funny": "Makes them laugh. They like you more and you have a bit more fun.",
    "vent": "Honest about how you feel. Your stress drops and they feel closer.",
    "thanks": "Grateful. Same effect as warm.",
    "forgive": "You let something go. Less rivalry, more trust.",
    "flirt": "Flirty. If they're into you, attraction goes up both ways. If not, it's a little awkward.",
    "dry": "Short and flat. They feel a bit less liked.",
    "cold": "Shuts them down. They feel a lot less liked.",
    "sibling_warm": "Brother or sister only: affectionate.",
    "sibling_tease": "Brother or sister only: teasing. Barely moves anything, it's just how siblings talk.",
}

REPLY_SET_DOCS = {
    "warm": "After a good hangout ('that was fun today').",
    "awkward": "After a hangout that went badly.",
    "support": "When a friend checks on you after something bad (got cut, a fight).",
    "apology": "When someone apologizes to you.",
    "thanks": "When someone congratulates you.",
    "rumor": "When a friend says people are talking about you.",
    "chatter_plans": "A friend's random text about plans.",
    "chatter_school": "A friend's random text about school or homework.",
    "chatter_vent": "A friend venting (tired, stressed).",
    "chatter_funny": "A friend texting something funny.",
    "chatter_game": "A friend texting about a game.",
    "partner": "Your boyfriend or girlfriend texting something sweet.",
    "flirt": "Someone flirting with you.",
    "sibling": "A brother or sister texting.",
    "generic": "Anything else.",
}

POOL_DOCS = {
    "invite": "A friend asks you to hang out.",
    "invite_later": "A friend who asked while you were busy, texting to try again later.",
    "invite_date": "Someone you're dating or into asks you somewhere, just the two of you.",
    "after_good": "A friend, after a good hangout.",
    "after_good_date": "After a good date.",
    "after_awkward": "After a hangout that went badly.",
    "u_ok": "A friend checks on you after something bad happened with {other}.",
    "they_apologize": "Someone apologizes after a fight.",
    "congrats_team": "A friend congratulates you on making {team}.",
    "consolation_cut": "A friend, after you got cut.",
    "congrats_award": "A friend, after you won {event}.",
    "rumor": "A friend tells you people are talking about you.",
    "chatter_partner": "Your boyfriend or girlfriend, a random sweet text.",
    "flirt_in": "Someone with a crush on you flirts.",
    "asked_out": "Someone asks you out (you answer yes or no).",
    "asked_to_dance": "Someone asks you to {event} (a dance).",
    "park_followup": "Someone you met at the dog park, about your dog {pet}.",
    "team_pregame": "Team group chat the night before a game.",
    "team_win": "Team group chat after a win.",
    "team_loss": "Team group chat after a loss.",
    "parent_pregame": "Mom or Dad in the family chat before your game.",
    "parent_win": "Mom or Dad after your team won.",
    "parent_loss": "Mom or Dad after a loss.",
    "parent_made_team": "Mom or Dad after you made {team}.",
    "parent_cut": "Mom or Dad after you got cut.",
    "parent_award": "Mom or Dad after you won {event}.",
    "parent_offer": "Mom or Dad after a scholarship offer from {college}.",
    "parent_report_proud": "Mom or Dad after a good report card.",
    "parent_report_worried": "Mom or Dad after a bad report card.",
    "parent_grounded": "Mom or Dad grounding you.",
    "parent_drafted": "Mom or Dad after you got drafted by {team}.",
    "pet_adopted": "Family chat the day a new pet comes home.",
    "pet_chores_set": "A parent confirming your pet chores ({chores}).",
    "pet_you_forgot": "A parent: you forgot a pet chore ({chore_a}).",
    "pet_you_forgot_strict": "A strict parent: you forgot a pet chore.",
    "pet_sibling_forgot": "A parent: a sibling ({who}) forgot a pet chore.",
    "pet_streak": "A parent: the pet's been happy because you've been on it.",
    "pet_sad": "A parent: the pet's been moping.",
    "pet_vet": "A parent: the pet went to the vet.",
    "pet_reminder": "A parent reminding you about a pet chore.",
    "sibling_home": "A brother or sister away at college, coming home.",
    "sibling_leaving": "A brother or sister leaving for college.",
    "sibling_chatter": "A brother or sister, random texts.",
    "coach_starting": "Your coach: you're starting.",
    "coach_bench": "Your coach: you're coming off the bench.",
    "react_warm": "How someone answers your warm reply.",
    "react_funny": "How someone answers your funny reply.",
    "react_dry": "How someone answers your dry reply.",
    "react_flirt_yes": "Someone who's into you, answering your flirt.",
    "react_flirt_no": "Someone who isn't into you, answering your flirt.",
    "react_plans_yes": "Someone saying yes to plans.",
    "react_plans_no": "Someone saying no to plans.",
    "react_parent": "Mom or Dad answering your nice reply.",
    "react_parent_annoyed": "Mom or Dad answering an attitude reply.",
    "reply_hey": "Someone answering your 'hey' (they're glad you texted).",
    "reply_hey_dry": "Someone answering your 'hey' (meh).",
    "first_hey": "YOU, texting someone first: just saying hey.",
    "first_hang": "YOU, asking someone to hang out ({place} available).",
    "first_flirt": "YOU, flirting first.",
    "first_good_luck": "YOU, wishing someone luck before their game.",
    "first_congrats": "YOU, congratulating someone.",
    "first_sorry": "YOU, apologizing.",
    "chatter_plans": "A friend, random text about plans (reply set: chatter_plans).",
    "chatter_school": "A friend, random text about school (reply set: chatter_school).",
    "chatter_vent": "A friend venting (reply set: chatter_vent).",
    "chatter_funny": "A friend texting something funny (reply set: chatter_funny).",
    "chatter_game": "A friend texting about a game (reply set: chatter_game).",
    "parent_first_day": "Mom or Dad, the first morning of high school.",
    "friend_first_day": "A friend, the first morning of high school.",
    "hang_talk": "IN PERSON: something they say while you're hanging out at {place} (shows in the story feed).",
    "date_talk": "IN PERSON: something they say on a date at {place}.",
    "chat_talk": "IN PERSON: something they say when you stop and talk (hallway, lunch, practice).",
    "awkward_talk": "IN PERSON: something they say when a hangout or date is going badly.",
}

WHO = {
    "best_friend": "The person you like most (not family, not a coach).",
    "friend": "A random friend.",
    "crush": "The person you're most attracted to who isn't your partner.",
    "partner": "Your boyfriend or girlfriend.",
    "ex": "An ex.",
    "rival": "Your biggest rival.",
    "teammate": "A random teammate on one of your teams.",
    "classmate": "Someone in your grade you barely know.",
    "sibling": "A random brother or sister.",
    "older_sibling": "An older brother or sister.",
    "younger_sibling": "A younger brother or sister.",
    "brother": "A brother.",
    "sister": "A sister.",
    "older_brother": "An older brother.",
    "older_sister": "An older sister.",
    "younger_brother": "A younger brother.",
    "younger_sister": "A younger sister.",
    "twin": "Your twin.",
    "coach": "A coach of one of your teams.",
}

VIBE_STYLES = ("tease", "sweet", "bold", "funny", "cheesy", "chill")
SIBLING_KINDS = ("sibling", "older_sibling", "younger_sibling", "twin", "brother", "sister", "older_brother", "older_sister",
                 "younger_brother", "younger_sister")
CASTABLE = SIBLING_KINDS + ("friend", "teammate", "classmate", "ex", "coach")  # kinds with more than one person who fits: a storyline keeps its pick
YEARS = {"freshman": (9,), "sophomore": (10,), "junior": (11,), "senior": (12,), "high_school": (9, 10, 11, 12),
         "college_freshman": (13,), "college_sophomore": (14,), "college_junior": (15,), "college_senior": (16,),
         "college": (13, 14, 15, 16)}
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
REQUIRES = {
    "dating": "You're dating someone.", "single": "You're not dating anyone.", "has_pet": "Your family has a pet.",
    "has_sibling": "You have a brother or sister.", "plays_sport": "You're on a team.",
    "in_season": "One of your teams has a game within a week.", "injured": "You're hurt.", "grounded": "You're grounded.",
    "school_day": "It's a school day.", "weekend": "It's Saturday or Sunday.", "summer": "It's summer break.",
    "in_high_school": "You're in high school.", "in_college": "You're in college.",
    # your last game (a few days after it): gameplay.py
    "we_won": "Your team won its last game (in the last few days).", "we_lost": "Your team lost its last game.",
    "i_played_great": "You played great in your last game.", "i_played_badly": "You had a rough last game.",
    "i_won_it": "You won your last game yourself, in the big moment.", "i_started": "You started your last game.",
    "i_was_benched": "You came off the bench (or sat) in your last game.", "rivalry_game": "Your last game was against your rival.",
}
ME_STATS = {"stress": "0-100", "energy": "0-100", "social": "0-100 (low = lonely)", "fun": "0-100 (low = bored)",
            "mood": "-100 to 100", "gpa": "0.0-4.0"}
REL_FIELDS = {"familiarity": "how well you know each other", "affection": "how much you like them (-100 to 100)",
              "attraction": "romantic interest", "trust": "trust", "respect": "respect", "rivalry": "rivalry",
              "perceived": "how much you think they like you"}
NEEDS = ("energy", "social", "fun", "stress")
FOCUS_MODES = ("balanced", "athletics", "academics", "social", "romance", "family", "rest")
REP_TAGS = ("athlete", "star", "legend", "tough", "host", "performer", "gossip", "flaky", "troublemaker", "mean", "embarrassed")
SCENE_REFS = ("them", "best_friend", "sibling", "partner")
SCENE_NAMES = {"them", "them_first", "best_friend", "best_friend_first", "sibling", "sibling_first", "partner", "partner_first",
               "me_first", "school", "town", "sport", "pet", "my_team", "my_team_record", "my_team_star", "mlb_champ",
               "my_nfl_team", "my_nba_team", "my_college", "my_nfl_record", "my_nba_record", "my_cfb_record", "my_mbb_record",
               "my_wbb_record", "nfl_champ", "nba_champ", "cfb_champ", "mbb_champ", "wbb_champ", "my_club", "epl_champ",
               "ucl_champ", "ballon_dor",  # (the last three rows: pro.py)
               "teacher", "class",  # (a scene set in one of your classes: `in biology`)
               "last_game", "last_opp", "last_score", "my_line", "big_play", "team_record", "my_season"}  # (your games: gameplay.py)
DEFAULT_CHANCE = 0.04
CHAPTER_CHANCE = 0.5    # the relaxed profile's odds a due chapter comes today (pacing lives in scheduler.py now)
MAX_BEATS = 5           # how deep a scene can keep going with "then" (a script's choices under choices)
# how long things can be (a scene's lines are joined into its text: room for a real back-and-forth)
MAX_SCENE_TEXT = 4000   # a scene's opening lines together (or a beat's)
MAX_LINE = 800          # one line said after a choice, or an outcome
MAX_LABEL = 140         # a choice
MAX_TITLE = 100         # a scene's title
MAX_NAME = 160          # a storyline's name (an expansion's is its storyline's plus its own: "<Storyline>: <part>")
NO_ADD = {"college_decision"}  # choices are built from your real options

# where each mini game fits in a story, for the guide
MG_FITS = {
    "trivia": "a pop quiz, a study session, trivia night at a restaurant, a bet over who knows more",
    "soccer_pk": "penalties at the park, settling an argument, a gym-class shootout",
    "soccer_11": "a pickup match, gym class, a game where your team needs a goal",
    "basketball": "shooting around in the driveway, HORSE with a sibling, open gym, a dare from half court",
    "playmaker": "running the offense at the park, a pickup run where you have to find the open man",
    "football": "a goal-line stand at practice, a backyard game, a bet on one play",
    "baseball": "a big at-bat, batting practice, a home run derby with friends",
    "swing_lab": "the batting cages, a hitting lesson",
    "golf": "a round with a parent, a golf outing, a bet on one hole",
    "cup_pong": "a friend's basement, a party (beer pong in college)",
    "paper_toss": "bored in class, the trash can across the room",
    "hold": "a steady pour in chem lab, one brushstroke, a power throw in gym, holding a note (press, hold, let go on the line)",
    "sweep": "stopping a pendulum, hitting the beat, timing a jump rope, any \"tap at the right moment\"",
    "mathdash": "mental math with a friend, splitting a check, making change at a register job, counting atoms",
    "flash": "remembering a pattern, ear training in band, a memory bet",
    "oddone": "proofreading a friend's essay, spot the difference, a typo on a sign",
    "lineup": "a timeline review, ranking things with friends, putting cards in order",
    "reflex": "catching something falling, a reaction test, first hand up, a quick-draw bet",
}

# ops a pack can use: name -> (arg count, how to write it, what it does)
OPS = {
    "say": (1, '["say", ["{them_first} grins. \\"owe you one.\\"", "\\"Legend,\\" {them_first} says."]]', "A line of dialogue or narration shown right after the choice. One line, or a list of versions the game rotates through."),
    "text": (2, '["text", "them", ["thanks for today fr", "ok that was fun"]]', "Someone (them, best_friend, sibling, partner) texts you this later today. One line or a list of versions."),
    "rel": (3, '["rel", "them", "affection", 6]', "Change how YOU feel about someone (field, amount -30..30)."),
    "rel_back": (3, '["rel_back", "them", "trust", 5]', "Change how THEY feel about you."),
    "mood": (1, '["mood", 4]', "Your mood, -20..20."),
    "need": (2, '["need", "stress", -6]', "energy, social, fun or stress, -30..30."),
    "trait": (2, '["trait", "confidence", 2]', "A personality trait, -10..10 (use sparingly)."),
    "skill": (2, '["skill", "sport", 1]', "A skill, -10..10. \"sport\" means your main sport."),
    "interest": (2, '["interest", "guitar", 5]', "How into something you are, -30..30. \"sport\" works here too."),
    "rep": (2, '["rep", "tough", 3]', "Your reputation for something, -20..20."),
    "memory": (4, '["memory", "Covered for {them_first}", 0.4, 40, ["them"]]', "A memory: text, feeling (-1..1), how big (0..100), who was there."),
    "family": (2, '["family", "affection", 3]', "You and every sibling, both directions."),
    "focus": (1, '["focus", "social"]', "What you focus on next: balanced, athletics, academics, social, romance, family, rest."),
    "hang_out": (1, '["hang_out", "them"]', "Makes plans: you'll hang out with them at your next free time."),
    "remember": (1, '["remember", "covered_for_sibling"]', "Remember a fact so a later scene can depend on it."),
    "forget": (1, '["forget", "covered_for_sibling"]', "Forget a remembered fact."),
    "minigame": (3, '["minigame", "soccer_pk", {"great": [ops], "good": [ops], "miss": [ops]}, {"base": 0.5, "athletic": 0.3}]',
                 "You play a mini game; how you do (great 80%+, good 50%+, else miss) picks the ops. If nobody plays it, the odds roll instead. The choice only shows when the game is ready."),
    "vibe": (2, '["vibe", "tease", {"good": ["{them_first} cracks up."], "meh": ["A small laugh."], "bad": ["{them_first} goes quiet."]}]',
             "A choice in a style (tease, sweet, bold, funny, cheesy, or chill for the safe pick) that lands or misses by what they like. "
             "good / meh / bad are what happens, a line or a list of versions. Only in scenes about someone (who)."),
    "chance": (3, '["chance", {"base": 0.5, "charisma": 0.3}, [ops if it works], [ops if it doesn\'t]]',
               "Roll against your own traits and talents. base 0..1, then +coef x (stat - 50)/100 for each stat."),
}


# ---------------------------------------------------------------------------------------- base data

def _texts_base() -> dict:
    return {k: v for k, v in _base("texts.json").items() if isinstance(v, list)}


def _skill_ids() -> set:
    return {s["id"] for s in _base("world.json")["skills"]}


def _interest_ids() -> set:
    w = _base("world.json")
    return {s["id"] for s in w["skills"]} | {h["id"] for h in w["hobbies"]}


def _base_reply_sets() -> dict:
    from .messages import REPLY_SETS
    return REPLY_SETS


def _names_in(*texts) -> set:
    out = set()
    for t in texts:
        if isinstance(t, str):
            out |= set(PH.findall(t))
    return out


def pool_names(pool: str) -> set:
    return _names_in(*_texts_base().get(pool, []))


def narration_names(key: str) -> set:
    return _names_in(*_base("templates.json")["templates"].get(key, [])) | {"a"}


def _moment_texts(spec) -> list:
    out = [spec.get("title", ""), spec.get("text", "")]
    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, list):
            for y in x:
                walk(y)
        elif isinstance(x, dict):
            for y in x.values():
                walk(y)
    walk(spec.get("choices", []))
    return out


def moment_names(mid: str) -> set:
    spec = _base("moments.json")["moments"].get(mid, {})
    return _names_in(*_moment_texts(spec)) | {"school", "town", "best_friend"}


def moment_refs(mid: str) -> set:
    spec = _base("moments.json")["moments"].get(mid, {})
    refs = {"best_friend"}
    def walk(ops):
        for op in ops or []:
            if not isinstance(op, list) or not op:
                continue
            if op[0] in ("rel", "rel_back") and len(op) > 1:
                refs.add(op[1])
            if op[0] == "memory" and len(op) > 4 and isinstance(op[4], list):
                refs.update(op[4])
            if op[0] == "chance" and len(op) > 3:
                walk(op[2])
                walk(op[3])
    for ch in spec.get("choices", []):
        walk(ch.get("ops"))
    people = {"other", "sibling", "coach", "origin", "roommate", "best_friend"}
    return (refs | (moment_names(mid) & people)) - {"school", "town"}


# ---------------------------------------------------------------------------------------- checking

class _Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append(f"{where}: {msg}" if where else msg)

    def warn(self, where, msg):
        self.warnings.append(f"{where}: {msg}" if where else msg)


def _suggest(word, options) -> str:
    near = difflib.get_close_matches(str(word), list(options), n=3, cutoff=0.5)
    return f" Did you mean {', '.join(near)}?" if near else ""


def _check_line(R, where, s, allowed, max_len=240):
    if not isinstance(s, str) or not s.strip():
        R.err(where, "needs to be a non-empty piece of text")
        return False
    if len(s) > max_len:
        R.err(where, f"is {len(s)} characters; keep it under {max_len}")
        return False
    bad = set(PH.findall(s)) - set(allowed)
    if bad:
        ok = ", ".join("{" + a + "}" for a in sorted(allowed)) or "none"
        R.err(where, f"uses {', '.join('{' + b + '}' for b in sorted(bad))}, which isn't filled in here. Allowed: {ok}")
        return False
    if s.count("{") != s.count("}"):
        R.err(where, "has an unmatched { or }")
        return False
    return True


def _check_variants(R, where, v, allowed, max_len=240):
    """One line, or a list of versions of it (the game rotates through them and doesn't repeat one too soon)."""
    if isinstance(v, list):
        if not 1 <= len(v) <= 20:
            R.err(where, "a list of versions has 1 to 20 lines")
            return False
        return all([_check_line(R, f"{where}[{i}]", x, allowed, max_len) for i, x in enumerate(v)])
    return _check_line(R, where, v, allowed, max_len)


def _num(R, where, v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        R.err(where, f"needs a number ({lo} to {hi})")
        return False
    if not lo <= v <= hi:
        R.err(where, f"is {v}; keep it between {lo} and {hi}")
        return False
    return True


def _check_ops(R, where, ops, refs, names, depth=0):
    if not isinstance(ops, list):
        R.err(where, "ops must be a list like [[\"mood\", 3], [\"say\", \"...\"]]")
        return
    for i, op in enumerate(ops):
        w = f"{where}[{i}]"
        if not isinstance(op, list) or not op or not isinstance(op[0], str):
            R.err(w, 'each op is a list that starts with its name, like ["mood", 3]')
            continue
        name, args = op[0], op[1:]
        if name not in OPS:
            R.err(w, f"'{name}' isn't an op.{_suggest(name, OPS)} Ops: {', '.join(OPS)}")
            continue
        n = OPS[name][0]
        if len(args) != n and not (name == "vibe" and len(args) == 3):  # (a vibe can carry more effects per outcome)
            R.err(w, f"{name} takes {n} value{'s' if n != 1 else ''}, like {OPS[name][1]}")
            continue
        ref_ok = lambda r: r in refs or R.err(w, f"'{r}' isn't someone this can refer to here. Use one of: {', '.join(sorted(refs)) or 'nobody'}")  # noqa: E731
        if name == "say":
            _check_variants(R, w, args[0], names, MAX_LINE)
        elif name == "text":
            if args[0] in refs:
                _check_variants(R, w, args[1], names, 200)
            else:
                ref_ok(args[0])
        elif name in ("rel", "rel_back"):
            if args[0] in refs:
                if args[1] not in REL_FIELDS:
                    R.err(w, f"'{args[1]}' isn't a relationship field. Use: {', '.join(REL_FIELDS)}")
                _num(R, w, args[2], -30, 30)
            else:
                ref_ok(args[0])
        elif name == "mood":
            _num(R, w, args[0], -20, 20)
        elif name == "need":
            if args[0] not in NEEDS:
                R.err(w, f"'{args[0]}' isn't a need. Use: {', '.join(NEEDS)}")
            _num(R, w, args[1], -30, 30)
        elif name == "trait":
            if args[0] not in TRAITS:
                R.err(w, f"'{args[0]}' isn't a trait.{_suggest(args[0], TRAITS)} Traits: {', '.join(TRAITS)}")
            _num(R, w, args[1], -10, 10)
        elif name == "skill":
            if args[0] != "sport" and args[0] not in _skill_ids():
                R.err(w, f"'{args[0]}' isn't a skill.{_suggest(args[0], _skill_ids())}")
            _num(R, w, args[1], -10, 10)
        elif name == "interest":
            if args[0] != "sport" and args[0] not in _interest_ids():
                R.err(w, f"'{args[0]}' isn't something people get into here.{_suggest(args[0], _interest_ids())}")
            _num(R, w, args[1], -30, 30)
        elif name == "rep":
            if not isinstance(args[0], str) or not SLUG.match(args[0]):
                R.err(w, "a reputation tag is one lowercase word, like tough or flaky")
            elif args[0] not in REP_TAGS:
                R.warn(w, f"'{args[0]}' is a new reputation tag (known: {', '.join(REP_TAGS)})")
            _num(R, w, args[1], -20, 20)
        elif name == "memory":
            _check_line(R, w, args[0], names, 120)
            _num(R, w, args[1], -1, 1)
            _num(R, w, args[2], 0, 100)
            if not isinstance(args[3], list):
                R.err(w, 'the last value is a list of who was there, like ["them"] (or [] for nobody)')
            else:
                for r in args[3]:
                    ref_ok(r)
        elif name == "family":
            if args[0] not in REL_FIELDS:
                R.err(w, f"'{args[0]}' isn't a relationship field. Use: {', '.join(REL_FIELDS)}")
            _num(R, w, args[1], -20, 20)
        elif name == "focus":
            if args[0] not in FOCUS_MODES:
                R.err(w, f"focus is one of {', '.join(FOCUS_MODES)}")
        elif name == "hang_out":
            ref_ok(args[0])
        elif name in ("remember", "forget"):
            if not isinstance(args[0], str) or not SLUG.match(args[0]):
                R.err(w, "a remembered fact " + _slug_problem(args[0]).replace("needs a short lowercase id", "needs a short lowercase name").removeprefix("is "))
        elif name == "vibe":
            style, outs = args[0], args[1]
            if len(args) > 2:  # what else happens on each outcome: {"good": [ops], ...}
                if not isinstance(args[2], dict) or any(k not in ("good", "meh", "bad") or not isinstance(v, list) for k, v in args[2].items()):
                    R.err(w, 'the third value maps good / meh / bad to more effects, like {"good": [["mood", 2]]}')
                else:
                    for k, v in args[2].items():
                        _check_ops(R, f"{w} ({k})", v, refs, names, depth + 1)
            if style not in VIBE_STYLES:
                R.err(w, f"'{style}' isn't a style. Use: {', '.join(VIBE_STYLES)}")
            if "them" not in refs:
                R.err(w, "a style choice needs the scene to be about someone (set who)")
            if not isinstance(outs, dict) or not outs or any(k not in ("good", "meh", "bad") for k in outs):
                R.err(w, 'the second value maps good / meh / bad to what happens, like {"good": ["..."], "meh": ["..."], "bad": ["..."]}')
            else:
                for ok_, lines in outs.items():
                    _check_variants(R, f"{w} ({ok_})", lines, names, MAX_LINE)
        elif name == "minigame":
            from .minigames import reg
            game, tiers, spec = args
            games = reg()["games"]
            if game != "sport" and game not in games:
                R.err(w, f"'{game}' isn't a mini game.{_suggest(game, games)} Games: {', '.join(games)}")
            if not isinstance(tiers, dict) or not tiers or any(k not in ("great", "good", "miss") for k in tiers):
                R.err(w, 'the second value maps great / good / miss to ops, like {"great": [["mood", 4]], "miss": [["need", "stress", 3]]}')
            else:
                for tk, tops in tiers.items():
                    _check_ops(R, f"{w} ({tk})", tops, refs, names, depth + 1)
            if not isinstance(spec, dict) or "base" not in spec:
                R.err(w, 'the last value is the odds if nobody plays, like {"base": 0.5, "athletic": 0.3}')
        elif name == "chance":
            spec, ok_ops, bad_ops = args
            if not isinstance(spec, dict) or "base" not in spec:
                R.err(w, 'chance starts with odds like {"base": 0.5, "charisma": 0.3}')
            else:
                stats = set(TRAITS) | set(APTITUDES) | _skill_ids()
                for k, v in spec.items():
                    if k == "base":
                        _num(R, w + ".base", v, 0, 1)
                    elif k not in stats:
                        R.err(w, f"'{k}' isn't a trait, talent or skill to roll against.{_suggest(k, stats)}")
                    else:
                        _num(R, f"{w}.{k}", v, -1, 1)
            if depth > 2:
                R.err(w, "chance inside chance inside chance is too deep")
            else:
                _check_ops(R, w + " (if it works)", ok_ops, refs, names, depth + 1)
                _check_ops(R, w + " (if it doesn't)", bad_ops, refs, names, depth + 1)


def _check_choice(R, where, ch, refs, names, depth=0):
    if not isinstance(ch, dict):
        R.err(where, 'a choice looks like {"label": "...", "ops": [...]}')
        return
    for k in ch:
        if k not in ("label", "hint", "fits", "ops", "then"):
            R.warn(where, f"'{k}' is ignored (a choice has label, hint, fits, ops, then)")
    then = ch.get("then")
    if then is not None:
        if depth + 1 >= MAX_BEATS:
            R.err(where + ".then", f"a scene can keep going {MAX_BEATS - 1} times at most; end it here")
        elif not isinstance(then, dict) or "text" not in then or "choices" not in then:
            R.err(where + ".then", 'keeps the scene going: {"text": "what happens next", "choices": [2 to 4 choices]}')
        else:
            _check_variants(R, where + ".then.text", then["text"], names, MAX_SCENE_TEXT)
            tch = then["choices"]
            if not isinstance(tch, list) or not 1 <= len(tch) <= 4:
                R.err(where + ".then.choices", "needs 1 to 4 choices")
            else:
                for i, c2 in enumerate(tch):
                    _check_choice(R, f"{where}.then.choices[{i}]", c2, refs, names, depth + 1)
    _check_line(R, where + ".label", ch.get("label"), names, MAX_LABEL)
    if ch.get("hint") is not None:
        _check_line(R, where + ".hint", ch["hint"], names, 140)
    fits = ch.get("fits", {})
    if not isinstance(fits, dict):
        R.err(where + ".fits", 'fits looks like {"empathy": 1, "impulsivity": -0.5}')
    else:
        for k, v in fits.items():
            if k not in TRAITS:
                R.err(where + ".fits", f"'{k}' isn't a trait.{_suggest(k, TRAITS)}")
            else:
                _num(R, f"{where}.fits.{k}", v, -2, 2)
    _check_ops(R, where + ".ops", ch.get("ops", []), refs, names)


def _check_range(R, where, rng, lo, hi):
    if not (isinstance(rng, list) and len(rng) == 2):
        R.err(where, f"is a range like [{lo}, {hi}]")
        return
    _num(R, where, rng[0], lo, hi)
    _num(R, where, rng[1], lo, hi)


WHEN_KEYS = {"chance", "years", "months", "dates", "weekdays", "requires", "you_feel", "they_feel", "me",
             "remembered", "not_remembered", "once", "cooldown_days", "after", "gap_days", "not_before", "not_after", "importance"}


def _check_scene(R, where, sc, seen_ids):
    base_moments = _base("moments.json")["moments"]
    if not isinstance(sc, dict):
        R.err(where, "a scene is an object with id, title, text, choices")
        return
    sid = sc.get("id")
    if not isinstance(sid, str) or not SLUG.match(sid):
        R.err(where + ".id", _slug_problem(sid))
    elif sid in base_moments:
        R.err(where + ".id", f"'{sid}' is already a moment in the game; pick another id")
    elif sid in seen_ids:
        R.err(where + ".id", f"'{sid}' is used twice")
    else:
        seen_ids.add(sid)
    for k in sc:
        if k in WHEN_KEYS:
            R.warn(where, f"'{k}' is ignored here: it goes inside \"when\", like \"when\": {{\"{k}\": ...}}")
        elif k not in ("id", "title", "text", "by_text", "who", "when", "choices", "notes", "src", "line", "cast_refs"):
            R.warn(where, f"'{k}' is ignored (a scene has id, title, text, by_text, who, when, choices)")
    who = sc.get("who")
    if isinstance(who, str) and who.startswith("cast:"):
        if who[5:] not in getattr(R, "slots", set()):
            R.err(where + ".who", f"'{who}' needs a cast slot named '{who[5:]}' in this pack's \"cast\" section"
                  + (f" (this pack has: {', '.join(sorted(R.slots))})" if getattr(R, "slots", None) else ""))
    elif who is not None and who not in WHO:
        R.err(where + ".who", f"'{who}' isn't a kind of person.{_suggest(who, WHO)} Use: {', '.join(WHO)}, or cast:<slot> for a named person")
    names = set(SCENE_NAMES)
    refs = set(SCENE_REFS)
    for s in getattr(R, "slots", set()):  # the storyline's other people, by name: {cast_coach_first}, effects on cast_coach
        names |= {f"cast_{s}", f"cast_{s}_first"}
        refs.add(f"cast_{s}")
    for s in sc.get("cast_refs") or []:
        if s not in getattr(R, "slots", set()):
            R.err(where, f"names '{s}', who isn't in this storyline's cast")
    if not who:
        names -= {"them", "them_first"}
        refs -= {"them"}
    _check_line(R, where + ".title", sc.get("title"), names, MAX_TITLE)
    _check_variants(R, where + ".text", sc.get("text"), names, MAX_SCENE_TEXT)
    if sc.get("by_text") is not None:
        if not who:
            R.warn(where + ".by_text", "is skipped: a texted version needs the scene to be about someone (set who), so the game knows who it's from")
        else:
            _check_variants(R, where + ".by_text", sc["by_text"], names, 220)
    when = sc.get("when", {})
    if not isinstance(when, dict):
        R.err(where + ".when", "when is an object, like {\"chance\": 0.05, \"years\": [\"freshman\"]}")
        when = {}
    allowed_when = WHEN_KEYS
    for k, v in when.items():
        w = f"{where}.when.{k}"
        if k not in allowed_when:
            R.err(w, f"isn't a condition.{_suggest(k, allowed_when)} Conditions: {', '.join(sorted(allowed_when))}")
        elif k == "chance":
            _num(R, w, v, 0.001, 1)
        elif k == "years":
            for y in v if isinstance(v, list) else [v]:
                if y not in YEARS:
                    R.err(w, f"'{y}' isn't a school year. Use: {', '.join(YEARS)}")
        elif k == "months":
            for m in v if isinstance(v, list) else [v]:
                _num(R, w, m, 1, 12)
        elif k == "dates":
            from . import calendar as _calm
            for d in v if isinstance(v, list) else [v]:
                if not (isinstance(d, str) and (re.match(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$", d) or d in _calm.NAMED_DAYS)):
                    R.err(w, f"'{d}' should look like \"10-31\" (month-day) or be a named day: {', '.join(_calm.NAMED_DAYS)}")
        elif k == "weekdays":
            for d in v if isinstance(v, list) else [v]:
                if d not in WEEKDAYS:
                    R.err(w, f"'{d}' isn't a weekday. Use: {', '.join(WEEKDAYS)}")
        elif k == "requires":
            for r in v if isinstance(v, list) else [v]:
                if isinstance(r, str) and r.startswith("class:"):
                    if r[6:] not in class_subjects():
                        R.err(w, f"'{r[6:]}' isn't a class. Classes: {', '.join(sorted(class_subjects()))}")
                    continue
                if r not in REQUIRES and not (isinstance(r, str) and r.startswith("pro:") and _pro().known(r)):
                    every = {**REQUIRES, **_pro().REQUIRES}
                    R.err(w, f"'{r}' isn't something a scene can require.{_suggest(r, every)} Use: {', '.join(every)}, "
                             f"or pro:whatif:<id> ({', '.join(_pro().mlb.WHATIF)})")
        elif k in ("you_feel", "they_feel"):
            if not who:
                R.err(w, "only works when the scene is about someone (set who)")
            elif not isinstance(v, dict):
                R.err(w, 'looks like {"affection": [40, 100]}')
            else:
                for f, rng in v.items():
                    if f not in REL_FIELDS:
                        R.err(w, f"'{f}' isn't a relationship field. Use: {', '.join(REL_FIELDS)}")
                    else:
                        _check_range(R, f"{w}.{f}", rng, -100, 100)
        elif k == "me":
            if not isinstance(v, dict):
                R.err(w, 'looks like {"stress": [60, 100]}')
            else:
                for f, rng in v.items():
                    if f not in ME_STATS:
                        R.err(w, f"'{f}' isn't one of your stats. Use: {', '.join(ME_STATS)}")
                    else:
                        _check_range(R, f"{w}.{f}", rng, -100 if f == "mood" else 0, 4 if f == "gpa" else 100)
        elif k in ("remembered", "not_remembered"):
            for r in v if isinstance(v, list) else [v]:
                if not isinstance(r, str) or not SLUG.match(r):
                    R.err(w, _slug_problem(r))
        elif k == "once":
            if not isinstance(v, bool):
                R.err(w, "is true or false")
        elif k == "cooldown_days":
            _num(R, w, v, 1, 2000)
        elif k == "after":
            for a in v if isinstance(v, list) else [v]:
                if not isinstance(a, str) or not (SLUG.match(a) or a.startswith("@")):
                    R.err(w, "is a list of scene ids that have to happen first")
        elif k == "gap_days":
            _num(R, w, v, 0, 2600)  # up to the whole seven years: a long authored gap is the author's call
        elif k in ("not_before", "not_after"):
            if not isinstance(v, str) or not re.match(r"^(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])$", v):
                R.err(w, 'is a month-day inside the school year, like "11-15"')
        elif k == "importance":
            if v not in ("ambient", "regular", "major", "finale"):
                R.err(w, "is ambient, regular, major or finale")
    chs = sc.get("choices")
    if not isinstance(chs, list) or not 1 <= len(chs) <= 4:
        R.err(where + ".choices", "a scene needs 1 to 4 choices")
        chs = chs if isinstance(chs, list) else []
    for i, ch in enumerate(chs):
        _check_choice(R, f"{where}.choices[{i}]", ch, refs, names)


def parse_text(text: str) -> dict:
    """A pack from a file or a paste: plain JSON, or ChatGPT's answer with the JSON somewhere inside it."""
    t = text.strip().lstrip("﻿")
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", t)
    if fence:
        t = fence.group(1)
    else:
        a, b = t.find("{"), t.rfind("}")
        if a < 0 or b < a:
            raise ValueError("There's no dialogue pack in that text (it should be a JSON block that starts with { and ends with }).")
        t = t[a:b + 1]
    try:
        data = json.loads(t)
    except json.JSONDecodeError as e:
        raise ValueError(f"That JSON has a mistake near line {e.lineno}, column {e.colno}: {e.msg}. "
                         "Ask ChatGPT to send the pack again as valid JSON.") from None
    if not isinstance(data, dict):
        raise ValueError("A dialogue pack is a JSON object (it starts with {).")
    return data


def check(pack: dict) -> dict:
    """Every problem with a pack, in plain words. errors stop it from loading; warnings don't."""
    R = _Report()
    if not isinstance(pack, dict):
        R.err("", "a dialogue pack is a JSON object")
        return {"ok": False, "errors": R.errors, "warnings": R.warnings, "summary": {}}
    if not any(k in pack for k in SECTIONS) and not pack.get("outline"):  # (an outline with no scenes written yet is fine)
        R.err("", f"there's nothing in this pack. Add at least one of: {', '.join(SECTIONS)}")
    if pack.get("dialogue_pack") not in (1, None):
        R.warn("dialogue_pack", "should be 1")
    name = pack.get("name")
    if not isinstance(name, str) or not name.strip():
        R.err("name", "give the pack a short name, like \"Freshman fall\"")
    elif len(name) > MAX_NAME:
        R.err("name", f"keep the name under {MAX_NAME} characters")
    for k in pack:
        if k not in SECTIONS + ("dialogue_pack", "name", "author", "notes", "version", "in_order", "cast", "script", "expands", "outline"):
            R.warn(k, f"isn't part of a pack and is ignored.{_suggest(k, SECTIONS)}")
    base_texts = _texts_base()
    added = {"texts": 0, "replies": 0, "narration": 0, "moment_choices": 0, "scenes": 0, "duplicates": 0}

    texts = pack.get("texts", {})
    if not isinstance(texts, dict):
        R.err("texts", 'is an object of pool names to lists of lines, like {"chatter_school": ["..."]}')
        texts = {}
    for pool, lines in texts.items():
        w = f"texts.{pool}"
        if pool not in base_texts:
            R.err(w, f"there's no '{pool}' pool.{_suggest(pool, base_texts)}")
            continue
        if not isinstance(lines, list):
            R.err(w, "is a list of lines")
            continue
        have = {_lines.text_of(x).lower().strip() for x in base_texts[pool]}
        allowed = pool_names(pool)
        for i, s in enumerate(lines):
            wi = f"{w}[{i}]"
            if isinstance(s, dict):
                for k in s:
                    if k not in ("text", "talk", "when"):
                        R.warn(wi, f"'{k}' is ignored (a line has text, talk and when)")
                if not _check_line(R, wi + ".text", s.get("text"), allowed, 200):
                    continue
                if s.get("talk") is not None and not _check_line(R, wi + ".talk", s["talk"], allowed | {"them_first", "says"}, 300):
                    continue
                wh = s.get("when", [])
                if not isinstance(wh, list) or any(t not in _lines.TAGS for t in wh):
                    bad = [t for t in (wh if isinstance(wh, list) else [wh]) if t not in _lines.TAGS]
                    R.err(wi + ".when", f"is a list of context tags; {', '.join(map(str, bad))} isn't one.{_suggest(str(bad[0]) if bad else '', _lines.TAGS)} Tags: {', '.join(_lines.TAGS)}")
                    continue
                key = s["text"].lower().strip()
            elif _check_line(R, wi, s, allowed, 200):
                key = s.lower().strip()
            else:
                continue
            if key in have:
                added["duplicates"] += 1
            else:
                have.add(key)
                added["texts"] += 1

    replies = pack.get("replies", {})
    if not isinstance(replies, dict):
        R.err("replies", 'is an object of reply sets to options, like {"chatter_school": [["on it", "warm"]]}')
        replies = {}
    sets = _base_reply_sets()
    for rs, opts in replies.items():
        w = f"replies.{rs}"
        if rs not in sets:
            R.err(w, f"there's no '{rs}' reply set.{_suggest(rs, sets)} Sets: {', '.join(sets)}")
            continue
        if not isinstance(opts, list):
            R.err(w, 'is a list of [label, tone] pairs, like [["lmao same", "funny"]]')
            continue
        for i, o in enumerate(opts):
            label, tone = (o.get("label"), o.get("tone")) if isinstance(o, dict) else (o if isinstance(o, list) and len(o) == 2 else (None, None))
            if label is None:
                R.err(f"{w}[{i}]", 'each option is ["what you say", "tone"]')
                continue
            if _check_line(R, f"{w}[{i}]", label, set(), 80):
                if tone not in REPLY_TONES:
                    R.err(f"{w}[{i}]", f"'{tone}' isn't a tone.{_suggest(tone, REPLY_TONES)} Tones: {', '.join(REPLY_TONES)}")
                elif tone.startswith("sibling") and rs != "sibling":
                    R.err(f"{w}[{i}]", "sibling tones only work in the sibling reply set")
                else:
                    added["replies"] += 1

    narration = pack.get("narration", {})
    if not isinstance(narration, dict):
        R.err("narration", 'is an object like {"study.focused": ["{a} ..."]}')
        narration = {}
    templates = _base("templates.json")["templates"]
    for key, lines in narration.items():
        w = f"narration.{key}"
        if key not in templates:
            R.err(w, f"there's no '{key}' narration.{_suggest(key, templates)}")
            continue
        if not isinstance(lines, list):
            R.err(w, "is a list of lines")
            continue
        for i, s in enumerate(lines):
            if _check_line(R, f"{w}[{i}]", s, narration_names(key), 240):
                added["narration"] += 1

    mc = pack.get("moment_choices", {})
    if not isinstance(mc, dict):
        R.err("moment_choices", 'is an object like {"rumor": [{"label": "...", "ops": [...]}]}')
        mc = {}
    base_moments = _base("moments.json")["moments"]
    for mid, chs in mc.items():
        w = f"moment_choices.{mid}"
        if mid not in base_moments:
            R.err(w, f"there's no '{mid}' moment.{_suggest(mid, base_moments)}")
            continue
        if mid in NO_ADD or base_moments[mid].get("dynamic"):
            R.err(w, f"{mid}'s choices come from the game itself, so they can't be added to")
            continue
        if not isinstance(chs, list):
            R.err(w, "is a list of choices")
            continue
        if len(base_moments[mid].get("choices", [])) + len(chs) > 5:
            R.err(w, "a moment can have at most 5 choices in all")
        for i, ch in enumerate(chs):
            _check_choice(R, f"{w}[{i}]", ch, moment_refs(mid), moment_names(mid))
            added["moment_choices"] += 1

    tv = pack.get("trivia", {})
    added["trivia"] = 0
    if not isinstance(tv, dict):
        R.err("trivia", 'is an object of subjects to questions, like {"biology": [{"q": "...", "a": "...", "w": ["...", "...", "..."], "g": 9}]}')
        tv = {}
    from .trivia import bank as _tbank
    tsubs = _tbank()["subjects"]
    have_q = {q["q"].lower() for qs in _tbank()["questions"].values() for q in qs}
    for sub, qs in tv.items():
        w = f"trivia.{sub}"
        if sub not in tsubs or sub == "math":
            R.err(w, f"'{sub}' isn't a trivia subject (math is generated).{_suggest(sub, [k for k in tsubs if k != 'math'])} Subjects: {', '.join(k for k in tsubs if k != 'math')}")
            continue
        if not isinstance(qs, list):
            R.err(w, "is a list of questions")
            continue
        for i, q in enumerate(qs):
            wq = f"{w}[{i}]"
            if not isinstance(q, dict):
                R.err(wq, 'a question looks like {"q": "...", "a": "right answer", "w": ["wrong", "wrong", "wrong"], "g": 9}')
                continue
            ok = _check_line(R, wq + ".q", q.get("q"), set(), 200) and _check_line(R, wq + ".a", q.get("a"), set(), 80)
            wr = q.get("w")
            if not isinstance(wr, list) or len(wr) != 3 or not all(isinstance(x, str) and x.strip() for x in wr):
                R.err(wq + ".w", "needs exactly three wrong answers")
                ok = False
            elif ok and (len({x.strip().lower() for x in wr} | {q["a"].strip().lower()}) != 4):
                R.err(wq + ".w", "the four answers have to be different from each other")
                ok = False
            if q.get("g") is not None and (isinstance(q["g"], bool) or not isinstance(q["g"], int) or not 9 <= q["g"] <= 13):
                R.err(wq + ".g", "g is the lowest grade it fits: 9, 10, 11, 12, or 13 for college")
                ok = False
            if ok:
                if q["q"].lower() in have_q:
                    added["duplicates"] += 1
                else:
                    added["trivia"] += 1
    mods = pack.get("mods", {})
    added["mods"] = 0
    if not isinstance(mods, dict):
        R.err("mods", 'is an object like {"open": {"late_night": ["u up?"]}, "close": {"close": ["fr"]}, "talk": {"happy": ["{them_first} {says}, grinning"]}}')
        mods = {}
    for kind, bank in mods.items():
        w = f"mods.{kind}"
        if kind not in MOD_KINDS:
            R.err(w, f"'{kind}' isn't a kind of mod. Use: {', '.join(MOD_KINDS)}")
            continue
        if not isinstance(bank, dict):
            R.err(w, 'is an object of context tags to lines, like {"late_night": ["u up?"]}')
            continue
        for tag, ls in bank.items():
            wt = f"{w}.{tag}"
            bad = [t for t in tag.split("+") if t not in _lines.TAGS] if tag != "any" else []
            if bad:
                R.err(wt, f"'{bad[0]}' isn't a context tag.{_suggest(bad[0], _lines.TAGS)} Tags: any, {', '.join(_lines.TAGS)} "
                          "(join several with +, like close+guys)")
                continue
            if not isinstance(ls, list):
                R.err(wt, "is a list of lines")
                continue
            for i, x in enumerate(ls):
                if kind == "talk":
                    if _check_line(R, f"{wt}[{i}]", x, {"them_first", "says"}, 90):
                        if "{them_first}" not in x:
                            R.err(f"{wt}[{i}]", "a way of saying something needs {them_first} (who's talking), like \"{them_first} {says}, grinning\"")
                        else:
                            added["mods"] += 1
                elif _check_line(R, f"{wt}[{i}]", x, set(), 40):
                    added["mods"] += 1

    added["chat"] = _check_chat(R, pack.get("chat", {}))
    added["schedule"] = _check_schedule(R, pack.get("schedule", {}))

    R.slots = _check_cast(R, pack["cast"]) if "cast" in pack else set()  # named people this storyline is about
    scenes = pack.get("scenes", [])
    if not isinstance(scenes, list):
        R.err("scenes", "is a list of scenes")
        scenes = []
    seen = set()
    for i, sc in enumerate(scenes):
        _check_scene(R, f"scenes[{i}]" + (f" ({sc.get('id')})" if isinstance(sc, dict) and sc.get("id") else ""), sc, seen)
        added["scenes"] += 1
    if added["duplicates"]:
        R.warn("texts", f"{added['duplicates']} line{'s are' if added['duplicates'] != 1 else ' is'} already in the game and will be skipped")
    return {"ok": not R.errors, "errors": R.errors, "warnings": R.warnings, "summary": added}


SCHEDULE_KEYS = ("years", "after", "gap_days", "months", "not_before", "not_after", "importance", "replace_after", "skip", "spread")


def _check_schedule(R, sch) -> int:
    """When episodes of any storyline air: {"scene_id": {"years": [...], "after": [...], "gap_days": n, "months": [...]}}."""
    if not sch:
        return 0
    if not isinstance(sch, dict):
        R.err("schedule", 'is an object of scene ids to when they air, like {"bro_driveway": {"years": ["freshman"], "after": ["crush_first_text"]}}')
        return 0
    n = 0
    for sid, v in sch.items():
        w = f"schedule.{sid}"
        if not isinstance(sid, str) or not (SLUG.match(sid) or sid.startswith("@")):
            R.err(w, "needs to be a scene id")
            continue
        if not isinstance(v, dict) or not v:
            R.err(w, 'is an object like {"years": ["sophomore"], "after": ["other_scene_id"]}')
            continue
        for k, x in v.items():
            if k not in SCHEDULE_KEYS:
                R.err(f"{w}.{k}", f"isn't part of a schedule. Use: {', '.join(SCHEDULE_KEYS)}")
            elif k == "years":
                for y in x if isinstance(x, list) else [x]:
                    if y not in YEARS:
                        R.err(f"{w}.years", f"'{y}' isn't a school year. Use: {', '.join(YEARS)}")
            elif k == "after":
                for a in x if isinstance(x, list) else [x]:
                    if not isinstance(a, str) or not (SLUG.match(a) or a.startswith("@")):
                        R.err(f"{w}.after", "is a list of scene ids")
            elif k == "spread":
                if not isinstance(x, bool):
                    R.err(f"{w}.spread", "is true or false")
            elif k == "gap_days":
                _num(R, f"{w}.gap_days", x, 0, 2600)
            elif k == "months":
                for mo in x if isinstance(x, list) else [x]:
                    _num(R, f"{w}.months", mo, 1, 12)
            elif k in ("not_before", "not_after"):
                if not isinstance(x, str) or not re.match(r"^(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])$", x):
                    R.err(f"{w}.{k}", 'is a month-day inside the school year, like "11-15"')
            elif k == "importance" and x not in ("ambient", "regular", "major", "finale"):
                R.err(f"{w}.importance", "is ambient, regular, major or finale")
            elif k in ("replace_after", "skip") and not isinstance(x, bool):
                R.err(f"{w}.{k}", "is true or false")
        n += 1
    return n


def _check_chat(R, chat) -> int:
    """Texting lines (chat.py): same shape as the built-in ones, lists of short lines in places that exist."""
    if not chat:
        return 0
    base = _base("chat.json")
    if not isinstance(chat, dict):
        R.err("chat", 'is an object like {"topic": {"school": ["pop quiz again"]}, "suggest": {"flirt_tease": ["you wish"]}}')
        return 0
    n = 0

    def walk(v, b, where):
        nonlocal n
        if isinstance(b, dict):
            if not isinstance(v, dict):
                R.err(where, "should be an object here")
                return
            for k, sub in v.items():
                if k not in b:
                    R.err(f"{where}.{k}", f"isn't a place for lines.{_suggest(k, list(b))} Use: {', '.join(x for x in b if not x.startswith('_'))}")
                    continue
                walk(sub, b[k], f"{where}.{k}")
            return
        if not isinstance(v, list):
            R.err(where, "is a list of lines")
            return
        for i, x in enumerate(v):
            if re.search(r"\.ask\.(general|flirty)$", where):
                kinds = ("yesno", "doing", "day", "weekend", "open", "flirty")
                if not isinstance(x, dict) or "q" not in x or x.get("a") not in kinds:
                    R.err(f"{where}[{i}]", f'is a question like {{"q": "you going friday?", "a": "yesno"}}; "a" is one of {", ".join(kinds)}')
                    continue
                if _check_line(R, f"{where}[{i}].q", x["q"], {"me"}, 160):
                    n += 1
            elif _check_line(R, f"{where}[{i}]", x, {"me"}, 200):
                n += 1
    shape = {k: v for k, v in base.items() if not k.startswith("_")}
    for k, v in chat.items():
        if k == "people":  # lines for one kind of person: the same shape, used first for them
            if not isinstance(v, dict):
                R.err("chat.people", 'is an object of kinds of people to lines, like {"older_sibling": {"reply": {"greet": {"warm": ["what do you want"]}}}}')
                continue
            for kind, sub in v.items():
                if kind not in WHO:
                    R.err(f"chat.people.{kind}", f"isn't a kind of person.{_suggest(kind, WHO)} Use: {', '.join(WHO)}")
                    continue
                walk(sub, shape, f"chat.people.{kind}")
            continue
        if k not in base or k.startswith("_"):
            R.err(f"chat.{k}", f"isn't part of chat lines.{_suggest(k, list(shape) + ['people'])}")
            continue
        walk(v, base[k], f"chat.{k}")
    return n


# ---------------------------------------------------------------------------------------- packs on disk

def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (s or "pack").lower()).strip("_")
    return (s or "pack")[:40]


def _state_path():
    return os.path.join(USER_DIR, "state.json")


def _state() -> dict:
    try:
        with open(_state_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"disabled": []}


def _save_state(st):
    os.makedirs(USER_DIR, exist_ok=True)
    tmp = _state_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(tmp, _state_path())


_dir_cache: dict = {}   # (folder, source) -> (when it was last looked at, the packs)
_file_cache: dict = {}  # (folder, file) -> (mtime, size, its packs): a file is compiled once until it changes
DIR_RECHECK = 2.0       # seconds: packs() is called constantly; the folder is looked at again at most this often


_EXP_RE = re.compile(r"^\s*expands\s*:\s*(.+?)\s*$", re.I | re.M)
_exp_cache: dict = {}  # (folder, file) -> (stamp, the storyline it expands or None)


def _expands_of(folder, fn, stamp):
    hit = _exp_cache.get((folder, fn))
    if hit and hit[0] == stamp:
        return hit[1]
    par = None
    if fn.endswith(".story"):
        try:
            with open(os.path.join(folder, fn), encoding="utf-8") as f:
                m = _EXP_RE.search(f.read())
            par = m.group(1) if m else None
        except OSError:
            par = None
    _exp_cache[(folder, fn)] = (stamp, par)
    return par


def _parent_sig(lib, title) -> str:
    """What an expansion takes from its storyline (cast and scene titles): if that changes, it's compiled again."""
    p = lib.get((title or "").lower())
    if not p:
        return "none"
    return json.dumps([p.get("name"), p.get("cast") or {}, [(sc.get("title"), sc.get("id")) for sc in p.get("scenes") or [] if isinstance(sc, dict)]],
                      sort_keys=True, default=str)


def _read_dir(folder, source):
    """The packs in a folder. Each file is read and compiled once until it changes (and a compiled script is kept on disk,
    so the phone doesn't compile your whole library every time it opens); the folder itself is looked at again only
    every couple of seconds, or right after reload(). Expansions load after the storylines they add to."""
    import time
    if not os.path.isdir(folder):
        return []
    now = time.monotonic()
    hit = _dir_cache.get((folder, source))
    if hit and now - hit[0] < DIR_RECHECK:
        return [dict(p) for p in hit[1]]
    first, later = [], []
    for fn in sorted(os.listdir(folder)):
        if not (fn.endswith(".json") or fn.endswith(".story")) or fn == "state.json":
            continue
        try:
            st = os.stat(os.path.join(folder, fn))
            stamp = (st.st_mtime_ns, st.st_size)
        except OSError:
            continue
        par = _expands_of(folder, fn, stamp)
        (later if par else first).append((fn, stamp, par))
    out = []
    for fn, stamp, _ in first:
        fc = _file_cache.get((folder, fn))
        if not fc or fc[0] != stamp:
            fc = _file_cache[(folder, fn)] = (stamp, _read_file(folder, fn, source))
        out.extend(fc[1])
    lib = library(out)
    for fn, stamp, par in later:
        sig = _parent_sig(lib, par)
        fc = _file_cache.get((folder, fn))
        if not fc or fc[0] != (stamp, sig):
            fc = _file_cache[(folder, fn)] = ((stamp, sig), _read_file(folder, fn, source, lib, sig))
        out.extend(fc[1])
    _dir_cache[(folder, source)] = (now, out)
    return [dict(p) for p in out]


def library(recs=None) -> dict:
    """Your storylines by title (lowercase) -> pack: what expansions add to."""
    recs = packs() if recs is None else recs
    return {str(p["pack"].get("name")).lower(): p["pack"] for p in recs  # (an outline with nothing written yet counts)
            if p["pack"].get("name") and (p["pack"].get("scenes") is not None or p["pack"].get("outline"))}


def _touched(path):
    """The game just wrote or removed this file: forget its compile (a timestamp alone can miss a quick same-size edit)."""
    _file_cache.pop((os.path.dirname(path), os.path.basename(path)), None)


_COMPILER_KEY = None


def _compiler_key() -> str:
    """Changes whenever the script compiler or the checker changes (so a kept compile is never stale)."""
    global _COMPILER_KEY
    if _COMPILER_KEY is None:
        import hashlib
        from . import script as SC
        h = hashlib.sha1()
        for f in (SC.__file__, __file__):
            try:
                with open(f, "rb") as fh:
                    h.update(fh.read())
            except OSError:
                h.update(f.encode())
        _COMPILER_KEY = h.hexdigest()[:16]
    return _COMPILER_KEY


def _read_file(folder, fn, source, lib=None, sig="") -> list:
    """One file's packs: a story script (compiled, or its kept compile) or an old JSON pack. lib: the storylines an
    expansion can add to (sig: what it takes from them, part of the kept compile's key)."""
    from . import script as SC
    path = os.path.join(folder, fn)
    if fn.endswith(".story"):  # a story script: one or more storylines (=== sections)
        stem = fn[:-6]
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except (OSError, ValueError) as e:
            return [{"id": f"{source}:{stem}", "file": fn, "source": source, "pack": {"name": stem}, "kind": "script",
                     "script": "", "check": {"ok": False, "errors": [f"couldn't read it: {e}"], "warnings": [], "summary": {}}}]
        import hashlib
        key = hashlib.sha1((_compiler_key() + "\0" + sig + "\0" + text).encode("utf-8")).hexdigest()
        kept = os.path.join(folder, ".compiled", stem + ".json")
        recs = None
        try:
            with open(kept, encoding="utf-8") as f:
                k = json.load(f)
            if k.get("key") == key:
                recs = k["recs"]
        except (OSError, ValueError, KeyError):
            recs = None
        if recs is None:
            # (references to other storylines were checked when it was added; loading just links them up. An expansion
            # gets the storylines it can add to.)
            r = SC.compile_script(text, default_title=stem.replace("_", " ").title(), library=lib)
            errs = [f"line {e['line']}: {e['text']}" for e in r["errors"]]
            warns = [f"line {e['line']}: {e['text']}" for e in r["warnings"]]
            sums = r.get("pack_summaries") or []
            recs = [{"id": f"{source}:{stem}" + (f"~{i + 1}" if i else ""), "file": fn, "source": source, "pack": pk, "kind": "script",
                     "check": {"ok": not errs, "errors": errs, "warnings": warns, "summary": (sums[i] if i < len(sums) and not errs else {})}}
                    for i, pk in enumerate(r["packs"] or [{"name": stem}])]
            try:
                os.makedirs(os.path.dirname(kept), exist_ok=True)
                with open(kept + ".tmp", "w", encoding="utf-8") as f:
                    json.dump({"key": key, "recs": recs}, f, separators=(",", ":"))
                os.replace(kept + ".tmp", kept)
            except OSError:
                pass  # (keeping the compile is only a speed-up)
        return [{**rec, "script": text} for rec in recs]
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        rep = check(data)
    except (OSError, ValueError) as e:
        data, rep = {}, {"ok": False, "errors": [f"couldn't read it: {e}"], "warnings": [], "summary": {}}
    return [{"id": f"{source}:{fn[:-5]}", "file": fn, "source": source, "pack": data, "check": rep}]


_trial: list = []
_hidden: set = set()


def packs() -> list:
    """Every pack the game knows about, in load order, with whether it's on and what it adds."""
    disabled = set(_state().get("disabled", []))
    out = []
    mine = [p for p in _read_dir(USER_DIR, "yours") if p["id"] not in _hidden]
    for p in _read_dir(BUILTIN_DIR, "builtin") + mine + [dict(t) for t in _trial]:
        p["enabled"] = p["id"] not in disabled and p["check"]["ok"]
        out.append(p)
    _unique_scene_ids(out)
    return out


def _unique_scene_ids(entries: list):
    """Every scene has its own id. Ids come from the storyline's name (cut short) and the scene's title, so two expansions
    of one storyline can land on the same one ("Brothers: Same Team: Holidays" and "...Holidays (2)", each with a
    Christmas Eve): the later one's scene gets the file's name on the end, everywhere that storyline is read. Ids that are
    already unique never change (what you've played stays played)."""
    seen: set = set()
    for k, p in enumerate(entries):
        pk = p["pack"]
        scs = [sc for sc in pk.get("scenes") or [] if isinstance(sc, dict)]
        clash = {sc.get("id") for sc in scs if sc.get("id") in seen}
        if clash:
            stem = re.sub(r"[^a-z0-9]+", "_", p["id"].split(":", 1)[-1].lower()).strip("_")[:24] or "pack"
            mine = {sc.get("id") for sc in scs}
            ren = {}
            for old in sorted(clash):
                new, n = f"{old}__{stem}", 2
                while new in seen or new in mine:
                    new, n = f"{old}__{stem}{n}", n + 1
                ren[old] = new

            def moved(sc):
                when = sc.get("when") or {}
                after = when.get("after")
                if sc.get("id") not in ren and not (isinstance(after, list) and any(a in ren for a in after)) and after not in ren:
                    return sc
                sc = dict(sc, id=ren.get(sc.get("id"), sc.get("id")))
                if after:
                    sc["when"] = dict(when, after=[ren.get(a, a) for a in after] if isinstance(after, list) else ren.get(after, after))
                return sc
            pk = dict(pk, scenes=[moved(sc) if isinstance(sc, dict) else sc for sc in pk.get("scenes") or []])
            if pk.get("outline"):
                pk["outline"] = [dict(e, sid=ren.get(e.get("sid"), e.get("sid"))) if isinstance(e, dict) else e for e in pk["outline"]]
            entries[k] = dict(p, pack=pk)
        seen.update(sc.get("id") for sc in entries[k]["pack"].get("scenes") or [] if isinstance(sc, dict))


class trial_pack:
    """with trial_pack(pack or [packs], hide=[pack ids]): the game sees these packs as if they were added (and the hidden
    ones as if they were gone: a storyline being replaced by a new version of itself), for a preview; it forgets it after."""
    def __init__(self, pack, hide=()):
        ps = pack if isinstance(pack, list) else [pack]
        self.ps = [{"id": f"yours:__trial__{i}" if i else "yours:__trial__", "file": "__trial__.json", "source": "yours", "pack": pk,
                    "kind": "script" if pk.get("script") else "json", "check": check(pk)} for i, pk in enumerate(ps)]
        self.hide = set(hide)

    def __enter__(self):
        _trial[:] = self.ps
        _hidden.clear()
        _hidden.update(self.hide)
        reload()
        return self

    def __exit__(self, *exc):
        _trial.clear()
        _hidden.clear()
        reload()
        return False


FLIRT_AREAS = (("open", "flirt openers"), ("them", "how they answer"), ("back", "follow-ups"), ("in", "them flirting first"),
               ("in_back", "ways to answer them"), ("payoff", "payoffs"))


def _leaf_count(v) -> int:
    return len(v) if isinstance(v, list) else sum(_leaf_count(x) for x in v.values()) if isinstance(v, dict) else 0


def texting_breakdown(pk: dict) -> dict:
    """What a pack adds to texting: flirt lines by kind, other texting lines, and its group chats (by how they start)."""
    ch = pk.get("chat") or {}
    banter = ch.get("banter") or {}
    flirt = [{"label": label, "n": _leaf_count(banter.get(k))} for k, label in FLIRT_AREAS if _leaf_count(banter.get(k))]
    other = _leaf_count({k: v for k, v in ch.items() if k != "banter"})
    chats = [{"chat": b.get("chat"), "when": b.get("when") or [], "first": (b.get("lines") or [["", ""]])[0][1],
              "lines": len(b.get("lines") or []), "replies": len(b.get("you") or [])} for b in pk.get("groupchat") or []]
    return {"flirt": flirt, "flirt_total": sum(x["n"] for x in flirt), "texting": other, "group_chats": chats}


def pack_summary(p) -> dict:
    pk = p["pack"]
    kind = p.get("kind", "json")
    load = (merged().get("load_errors") or {}).get(p["id"]) if p["enabled"] else None
    return {"id": p["id"], "name": pk.get("name") or p["file"], "author": pk.get("author"), "notes": pk.get("notes"),
            "source": p["source"], "enabled": p["enabled"], "ok": p["check"]["ok"] and not load,
            "errors": ([load] if load else []) + p["check"]["errors"][:20],
            "warnings": p["check"]["warnings"][:20], "summary": p["check"]["summary"],
            "scenes": [{"id": s.get("id"), "title": s.get("title"), "who": s.get("who")} for s in pk.get("scenes", []) if isinstance(s, dict)],
            "kind": kind, "file": p.get("file"), "lines": sum(len(v) for v in (pk.get("texts") or {}).values()),
            "texting": {"flirt": _leaf_count((pk.get("chat") or {}).get("banter")), "group_chats": len(pk.get("groupchat") or []),
                        "lines": _leaf_count({k: v for k, v in (pk.get("chat") or {}).items() if k != "banter"})},
            "expands": pk.get("expands"),
            "outline": ({"total": len(pk["outline"]), "written": sum(1 for e in pk["outline"] if e.get("written"))}
                        if pk.get("outline") else None),
            "cast": [{"name": k, "who": v.get("who"), "label": slot_label(normalize_slot(v))} for k, v in (pk.get("cast") or {}).items()],
            "games": _about_games(pk)}


GAME_WORDS = re.compile(r"\b(game|games|match|tryouts?|playoffs?|season|scrimmage|homecoming|rivalry|touchdown|scored|coach)\b", re.I)


_games_memo: dict = {}  # id(compiled pack) -> (that pack, the answer): a storyline is read for games once until it changes


def _about_games(pk) -> bool:
    """Does this storyline have scenes about your games (so it can follow how they really go)?"""
    hit = _games_memo.get(id(pk))
    if hit is not None and hit[0] is pk:
        return hit[1]
    if len(_games_memo) > 2000:
        _games_memo.clear()
    v = _about_games_now(pk)
    _games_memo[id(pk)] = (pk, v)
    return v


def _about_games_now(pk) -> bool:
    for s_ in pk.get("scenes") or []:
        if not isinstance(s_, dict):
            continue
        words = f"{s_.get('title', '')} {s_.get('text', '') if isinstance(s_.get('text'), str) else ''}"
        if GAME_WORDS.search(words) or any(re.search(rx, words.lower()) for rx in SPORT_WORDS.values()):
            return True
    return False


def prompt_for_games(pid: str) -> str:
    """For ChatGPT: make this storyline's game scenes follow the real games. Keeps every scene; adds the other way."""
    from . import script as SC
    p = next((x for x in packs() if x["id"] == pid), None)
    if p is None:
        raise KeyError(pid)
    if p.get("kind") != "script":
        raise ValueError("that one isn't a story script")
    g = SC.guide(story_only=True)
    i = g.find("## Your games")
    games = g[i:g.find("\n## ", i + 5)].strip() if i >= 0 else ""
    outlined = bool(p["pack"].get("outline"))
    return "\n".join([
        "This is a storyline from LIFE OS, a life-simulation game where I play one person from high school through college. "
        "Its scenes decide how my games go: the score, my stats and my team's record follow what a scene says happened. "
        "Make that clear and exact.",
        "",
        "Rewrite it so that:",
        "- Every scene that comes after one of my games and takes a result for granted is tagged with it: [if we won], "
        "[if we lost], [if I played great], [if I won it] (I won it in the big moment). The game will go that way.",
        ("- It has an outline: put the tag at the end of that scene's outline line instead (`| if we won`), not on the scene."
         if outlined else "- Scenes before a game (getting ready, nerves) don't need a tag."),
        "- Where a line mentions the game, the score or how I did, use the real words so they match the box score: {last_game} "
        "(the 24-21 win over Branford), {last_score}, {last_opp}, {my_line} (6 catches for 98 yards and a touchdown), "
        "{big_play}, {team_record}, {my_season}. Don't make up a different score or stats.",
        "- Keep everything else exactly as it is: every scene and its title, every choice, effect and remember line.",
        "",
        "Reply with the whole storyline in ONE code block (```), nothing after it.",
        "",
        games,
        "",
        "The storyline:",
        "",
        "```",
        p["script"].strip(),
        "```",
        "",
    ])


def add_pack(data: dict) -> dict:
    rep = check(data)
    if not rep["ok"]:
        return {"ok": False, **rep}
    os.makedirs(USER_DIR, exist_ok=True)
    base = _slug(data.get("name"))
    fn = f"{base}.json"
    path = os.path.join(USER_DIR, fn)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(path + ".tmp", path)
    _touched(path)
    st = _state()
    st["disabled"] = [d for d in st.get("disabled", []) if d != f"yours:{base}"]
    _save_state(st)
    reload()
    return {"ok": True, "id": f"yours:{base}", **rep}


def set_enabled(pid: str, on: bool):
    if not any(p["id"] == pid for p in packs()):
        raise KeyError(pid)
    st = _state()
    dis = set(st.get("disabled", []))
    (dis.discard if on else dis.add)(pid)
    st["disabled"] = sorted(dis)
    _save_state(st)
    reload()


def remove_pack(pid: str):
    src, _, name = pid.partition(":")
    if src != "yours":
        raise ValueError("built-in packs can be turned off, not removed")
    name = name.split("~")[0]
    for ext in (".story", ".json"):
        path = os.path.join(USER_DIR, f"{name}{ext}")
        if os.path.exists(path):
            _backup(path, "removed")
            os.remove(path)
            _touched(path)
            try:
                os.remove(os.path.join(USER_DIR, ".compiled", f"{name}.json"))  # (its kept compile)
            except OSError:
                pass
            reload()
            return
    raise KeyError(pid)


# ---------------------------------------------------------------------------------------- story scripts on disk
def with_inserted(pid: str, after: str | None, text: str) -> tuple:
    """A storyline's script with new scenes put right after one of its scenes (or before the first): (new source, the line
    the new text starts on, how many lines it is)."""
    from . import script as SC
    p = _script_pack(pid)
    src = p["script"].rstrip("\n").split("\n")
    snippet = [ln for ln in SC.extract(text).strip("\n").split("\n") if not SC.SECTION_RE.match(ln.strip())]
    if not any(SC.SCENE_RE.match(ln.strip()) for ln in snippet):
        raise ValueError("there's no scene in that: a scene starts with --- and its title")
    scenes = p["pack"].get("scenes") or []
    heads = sorted(sc["line"] for sc in scenes if isinstance(sc, dict) and sc.get("line"))
    if after:
        sc = next((x for x in scenes if x.get("id") == after), None)
        if sc is None:
            raise KeyError(after)
        nxt = [h for h in heads if h > sc["line"]]
        k = (nxt[0] - 1) if nxt else len(src)  # (0-based index of the next scene's header, or the end)
        while k > 0 and not src[k - 1].strip():
            k -= 1
    else:
        k = (heads[0] - 1) if heads else len(src)
    new = src[:k] + [""] + snippet + [""] + src[k:]
    return "\n".join(new).rstrip("\n") + "\n", k + 2, len(snippet)


def merge_scenes(pid: str, text: str) -> dict:
    """A batch of scenes for an outlined storyline: each goes in its place by its outline number (or title), replacing
    that scene if it was written before; anything else in the paste (a === line, the outline again) is left out."""
    import difflib
    from . import script as SC
    p = _script_pack(pid)
    entries = SC.outline_entries(p["pack"])
    if not entries:
        raise ValueError("this storyline doesn't have an outline")
    src = p["script"].rstrip("\n").split("\n")
    k0 = next((i for i, ln in enumerate(src) if SC.SCENE_RE.match(ln.strip())), len(src))
    head, body = src[:k0], src[k0:]

    def blocks(lines):
        out, cur = [], None
        for ln in lines:
            t = ln.strip()
            if SC.SECTION_RE.match(t) or (t.lower().startswith("outline:") and cur is None):
                cur = None
                continue
            if SC.SCENE_RE.match(t):
                cur = [ln]
                out.append(cur)
            elif cur is not None:
                cur.append(ln)
        return out

    def number(block):
        t = SC.SCENE_RE.match(block[0].strip()).group(1)
        t = re.sub(r"\s*(\[.*|#[a-z].*)$", "", t).strip()
        m = re.match(r"(?:scene\s*|chapter\s*|#)?(\d+)\s*[.):\-]\s*(.+)$", t, re.I)
        if m and any(e["n"] == int(m.group(1)) for e in entries):
            return int(m.group(1))
        title = (m.group(2) if m else t).strip().lower()
        hit = next((e["n"] for e in entries if e["title"].lower() == title), None)
        if hit is None:
            near = difflib.get_close_matches(title, [e["title"].lower() for e in entries], n=1, cutoff=0.75)
            hit = next((e["n"] for e in entries if near and e["title"].lower() == near[0]), None)
        return hit
    have = {}
    extra = []
    for b in blocks(body):
        n = number(b)
        (have.__setitem__(n, b) if n is not None else extra.append(b))
    before = dict(have)  # (what each scene was: a new version that can't go in leaves this one)
    new = blocks(SC.extract(text).replace("\r\n", "\n").split("\n"))
    if not new:
        return {"ok": False, "errors": ["there are no scenes in that: each starts with --- and its number and title"], "notes": []}
    got = []
    for b in new:
        n = number(b)
        if n is None:
            extra.append(b)
            continue
        e = next(x for x in entries if x["n"] == n)
        b[0] = f"--- {n}. {e['title']}"  # (its title as the outline has it: the scene keeps its place)
        while len(b) > 1 and not b[-1].strip():
            b.pop()
        have[n] = b
        got.append(n)
    titles = {e["n"]: e["title"] for e in entries}
    skipped: dict = {}  # scene number -> what's wrong with it (it stays as it was)
    for n in got:  # nothing under its title: a scene that never got written, not one to add
        if not any(ln.strip() for ln in have[n][1:]):
            skipped[n] = ["it's empty: there are no lines or choices under its title"]
    last = got[-1] if got else None  # (the scene a reply that ran out of room stops in)
    if last is not None and last not in skipped and cut_off(text):
        skipped[last] = [CUT + " (its code block never closed)"]

    def build():
        out = list(head)
        while out and not out[-1].strip():
            out.pop()
        starts = []  # (the line a scene starts on, its number): so notes and problems can say which scene, which line
        for n in sorted(set(have) | set(before)):
            blk = before.get(n) if n in skipped else have.get(n)
            if not blk:
                continue
            out += [""]
            starts.append((len(out) + 1, n))
            out += blk
        for b in extra:
            out += [""]
            starts.append((len(out) + 1, None))
            out += b
        return out, starts

    def scene_at(ln, starts):
        hit = next(((st, n) for st, n in reversed(starts) if st <= ln), None)
        return (hit[1], ln - hit[0] + 1) if hit else ("head", ln)

    def where(note, starts):
        note = _note_text(note)
        m = re.match(r"line (\d+): (.*)$", note)
        if not m:
            return note
        n, k = scene_at(int(m.group(1)), starts)
        return (f"scene {n} ({titles.get(n, '')}), line {k}: " if isinstance(n, int) else "the storyline's top: " if n == "head" else "") + m.group(2)
    r: dict = {}
    for _ in range(2 * len(got) + 2):  # (each pass leaves at least one more scene out, or stops)
        out, starts = build()
        r = add_script("\n".join(out) + "\n", into=pid)
        if r["ok"]:
            # a scene the fixer had to take out entirely isn't in: it stays as it was, and you hear why
            p2 = _script_pack(pid)
            ents = SC.outline_entries(p2["pack"])
            by_id = {sc.get("id"): sc for sc in p2["pack"].get("scenes") or [] if isinstance(sc, dict)}
            # (a scene left with nothing after its fixes, just "..." and Continue, isn't in either)
            blank = {e["n"] for e in ents if (sc := by_id.get(e.get("sid"))) is not None and str(sc.get("text", "")).strip() in ("", "...")
                     and [c.get("label") for c in sc.get("choices") or []] in ([], ["Continue"])}
            done = {e["n"] for e in ents if e.get("written")} - blank
            gone = [n for n in got if n not in skipped and n not in done]
            if not gone and last is not None and last not in skipped:
                # the last scene of the reply stops partway: ChatGPT ran out of room
                sc_of = {e["n"]: by_id.get(e.get("sid")) for e in ents}
                others = any(SC.real_choices(sc_of[n] or {}) for n in got if n != last and n not in skipped)
                why = SC.stops_short(sc_of.get(last) or {}, others) if sc_of.get(last) else None
                if why:
                    skipped[last] = [f"{CUT}: {why}"]
                    continue
            if not gone:
                # a scene that never asks you anything (no choices) can't go in: it stays as it was
                sc_of = {e["n"]: by_id.get(e.get("sid")) for e in ents}
                unasked = {n: SC.no_choices(sc_of[n]) for n in got if n not in skipped and sc_of.get(n)}
                unasked = {n: w for n, w in unasked.items() if w}
                if unasked:
                    for n, w in unasked.items():
                        skipped[n] = [w]
                    continue
                break
            for n in gone:
                said = [w for w in (where(x, starts) for x in r.get("notes", [])) if w.startswith(f"scene {n} (")]
                skipped[n] = [re.sub(r"^scene \d+ \([^)]*\), ", "", w) for w in said] or ["nothing in it was something the game could use"]
            continue
        # a scene you just pasted that still has a problem stays out (as it was); a problem anywhere else stops it all
        bad, other = {}, []
        for msg, at, quote in zip(r["errors"], r.get("error_at") or [], r.get("error_quote") or []):
            n, k = scene_at(at, starts)
            text_ = re.sub(r"^line \d+: ", "", msg)
            said = f' "{quote[:90]}"' if quote else ""
            if n in got and n not in skipped:
                bad.setdefault(n, []).append(f"line {k}{said}: {text_}")
            else:
                other.append((n, k, said, text_))
        if other and not bad:
            # a problem with the storyline as a whole: find which new scene brings it (leave each out in turn)
            from . import scriptfix
            for n in [x for x in got if x not in skipped]:
                skipped[n] = []
                trial, _ = build()
                ok = scriptfix.repair("\n".join(trial) + "\n", library=library())["ok"]
                del skipped[n]
                if ok:
                    bad[n] = [f"with this scene the storyline has a problem: {t}" for _, _, _, t in other]
                    break
        if not bad:
            msgs = [f"{'the storyline' if n == 'head' else f'scene {n}'}, line {k}{said}: {t}" for n, k, said, t in other] or \
                [where(x, starts) for x in r["errors"]]
            return {"ok": False, "errors": msgs, "notes": [where(x, starts) for x in r.get("notes", [])], "got": [],
                    "skipped": [{"n": n, "title": titles.get(n, ""), "problems": ps} for n, ps in sorted(skipped.items())]}
        skipped.update(bad)
    r["got"] = [n for n in got if n not in skipped]
    r["skipped"] = [{"n": n, "title": titles.get(n, ""), "problems": ps} for n, ps in sorted(skipped.items())]
    r["notes"] = [where(x, starts) for x in r.get("notes", [])]
    r["gaps"] = scene_gaps(pid, r["got"]) if r.get("ok") else []
    return r


CUT = "ChatGPT's reply got cut off in this scene"


def cut_off(text: str) -> bool:
    """A reply that ran out of room: its code block was opened and never closed."""
    return sum(1 for ln in text.split("\n") if ln.strip().startswith("```")) % 2 == 1


def scene_gaps(pid: str, ns: list) -> list:
    """Scenes that went in with pieces missing: a choice with nothing after it, or no choice like the one a later scene
    follows. [{n, title, problems}]"""
    return _gaps_of(_script_pack(pid), ns)


def _gaps_of(p: dict, ns: list) -> list:
    from . import script as SC
    ents = SC.outline_entries(p["pack"])
    by_id = {sc.get("id"): sc for sc in p["pack"].get("scenes") or [] if isinstance(sc, dict)}
    sc_of = {e["n"]: by_id.get(e.get("sid")) for e in ents if e.get("written")}
    out: dict = {}
    for n in ns:
        if sc_of.get(n):
            q = SC.no_question(sc_of[n])
            if q:
                out.setdefault(n, []).append(q)
            out.setdefault(n, []).extend(SC.choice_gaps(sc_of[n]))
    for e in ents:
        m = re.search(r"you picked “(.+?)” in (\d+)", e.get("if") or "")
        if m and int(m.group(2)) in ns and sc_of.get(int(m.group(2))) and SC.find_choice(sc_of[int(m.group(2))], m.group(1)) is None:
            out.setdefault(int(m.group(2)), []).append(
                f"it needs a choice like “{m.group(1)}” (use those words in the choice, so the game can find it): scene {e['n']} "
                f"only happens after it (until then scene {e['n']} plays either way)")
    titles = {e["n"]: e["title"] for e in ents}
    return [{"n": n, "title": titles.get(n, ""), "problems": ps} for n, ps in sorted(out.items()) if ps]


def checkup(pid: str) -> dict:
    """An outlined storyline's written scenes, checked: any that never ask you anything (or give only one choice), a
    choice with nothing after it, a choice a later scene needs that isn't there. With a fix-it message that asks ChatGPT
    for just those, whole. {pack, name, written, total, gaps, fix_prompt}"""
    from . import script as SC
    p = _script_pack(pid)
    ents = SC.outline_entries(p["pack"])
    ns = [e["n"] for e in ents if e.get("written")]
    gaps = scene_gaps(pid, ns) if ents else []
    return {"pack": pid, "name": p["pack"].get("name") or pid, "written": len(ns), "total": len(ents), "gaps": gaps,
            "fix_prompt": fix_prompt([], gaps)}


def writing(sim) -> list:
    """Your outlined storylines, for switching between them while you write: how far along each is, how many written
    scenes need fixing, and how many can't come in your story as it stands (with the usual why)."""
    from collections import Counter
    from . import scheduler, script as SC
    by: dict = {}
    try:
        for r in scheduler.rows(sim):
            by.setdefault(r.get("pack"), []).append(r)
    except Exception:  # noqa: BLE001  (no story yet: progress only)
        by = {}
    out = []
    for p in packs():
        if p.get("kind") != "script" or not str(p["id"]).startswith("yours:"):
            continue
        ents = SC.outline_entries(p["pack"])
        if not ents:
            continue
        ns = [e["n"] for e in ents if e.get("written")]
        gaps = _gaps_of(p, ns)
        mine = by.get(p["id"], [])
        stuck = [r for r in mine if r.get("state") in ("unreachable", "expired")]
        top = Counter(r.get("why") or (r.get("reason") or "").replace("_", " ") for r in stuck).most_common(1)
        out.append({"pack": p["id"], "name": p["pack"].get("name") or p["id"], "written": len(ns), "total": len(ents),
                    "played": sum(1 for r in mine if r.get("state") == "played"), "needs_fixing": len(gaps),
                    "stuck": len(stuck), "stuck_why": top[0][0] if top else None, "on": bool(p.get("enabled", True))})
    return sorted(out, key=lambda x: (x["written"] >= x["total"] and not x["needs_fixing"], x["name"].lower()))


def _title_key(t: str) -> str:
    t = re.sub(r"#\S+\s*$", "", t or "")
    t = re.sub(r"\[[^\]]*\]", "", t)
    return re.sub(r"^\d+\s*[.):\-]\s*", "", t).strip().lower()


def drop_unasked(text: str, only: set | None = None) -> tuple:
    """A scene that never asks you anything (no choices) can't go in: take those out of a script (only the
    ones titled in `only`, when given: the scenes being added, never ones already there). -> (script, [{title, problems}])"""
    from . import script as SC
    from . import scriptfix
    fx = scriptfix.repair(text, library=library())
    if fx["result"]["errors"]:
        return text, []
    out = []
    for pk in fx["result"]["packs"]:
        for sc in pk.get("scenes") or []:
            if not isinstance(sc, dict):
                continue
            k = _title_key(sc.get("title") or "")
            if only is not None and k not in only:
                continue
            why = SC.no_choices(sc)
            if why:
                out.append({"title": sc.get("title") or "", "key": k, "problems": [why]})
    if not out:
        return text, []
    gone = {x["key"] for x in out}
    keep, skip = [], False
    for ln in fx["text"].split("\n"):
        m = SC.SCENE_RE.match(ln.strip())
        if m:
            skip = _title_key(m.group(1)) in gone
        elif ln.strip().startswith("==="):
            skip = False
        if not skip:
            keep.append(ln)
    return "\n".join(keep), [{"title": x["title"], "problems": x["problems"]} for x in out]


def unasked_note(left: list) -> list:
    return [f"“{x['title']}” didn't go in: {x['problems'][0]}" for x in left]


def insert_scenes(pid: str, after: str | None, text: str) -> dict:
    """Put new scenes into a storyline right where they go: its file gets them, in order, and they play there. A new
    scene that never asks you anything doesn't go in (and says why)."""
    new, first, n = with_inserted(pid, after, text)
    mine = set(_scene_titles(text))
    new2, left = drop_unasked(new, only=mine)
    if left and len(left) >= len(mine):
        return {"ok": False, "errors": unasked_note(left), "error_lines": [], "left_out": left}
    if left:
        new = new2
    r = add_script(new, into=pid)
    r["left_out"] = left
    if left:
        r["notes"] = unasked_note(left) + list(r.get("notes") or [])
    if not r["ok"]:
        # errors in what was pasted get its own line numbers; anything else is the storyline's
        lines = []
        for e in r["error_lines"]:
            if first <= e["line"] < first + n:
                lines.append({"line": e["line"] - first + 1, "text": e["text"], "yours": True})
            else:
                lines.append({"line": e["line"], "text": e["text"], "yours": False})
        r["error_lines"] = lines
        r["errors"] = [f"{'line' if x['yours'] else 'storyline line'} {x['line']}: {x['text']}" for x in lines]
    return r
def _script_path(pid: str) -> str:
    src, _, name = pid.partition(":")
    if src != "yours":
        raise ValueError("built-in storylines can't be edited here")
    return os.path.join(USER_DIR, f"{name.split('~')[0]}.story")


def script_of(pid: str) -> str:
    """A storyline's script, as written."""
    p = next((p for p in packs() if p["id"] == pid), None)
    if p is None:
        raise KeyError(pid)
    if p.get("kind") != "script":
        raise ValueError("that pack isn't a story script")
    return p["script"]


# ---------------------------------------------------------------------------------------------------- timing, by hand

def _year_word(y: str) -> str:
    return y.replace("_", " ")


def _timing_token(tok: str) -> str | None:
    """What a tag is about: "year", "season" (months or a season), "spread", or None (anything else: keep it)."""
    from . import script as SC
    low = tok.strip().lower()
    if not low:
        return None
    if SC._years(low) or low in ("high school", "college"):
        return "year"
    if low in SC.MONTHS or low in SC.MON3 or low in SC.SEASONS:
        return "season"
    if low.startswith("spread"):
        return "spread"
    return None


def _header_end(lines: list) -> int:
    """Where a storyline's header (=== title, cast:, when:...) ends: its first scene or block."""
    from . import script as SC
    for i, ln in enumerate(lines):
        t = ln.strip()
        if i and (SC.SCENE_RE.match(t) or SC.SECTION_RE.match(t) or (SC.BLOCK_RE.match(t) and not ln.startswith(" "))):
            return i
    return len(lines)


def timing_of(pid: str) -> dict:
    """A storyline's own timing (its when: line): its school years, months, and whether it's spread out."""
    from . import script as SC
    lines = _script_pack(pid)["script"].split("\n")
    for ln in lines[:_header_end(lines)]:
        m = SC.ATTR_RE.match(ln.strip())
        if m and m.group(1).lower() in ("when", "years"):
            d: dict = {}
            try:
                SC.tags(m.group(2), None, 0, d, SC.Section("x", 0))
            except SC.Fail:
                pass
            return {"years": SC.concrete_years(d.get("years")), "months": d.get("months") or [], "spread": bool(d.get("spread")),
                    "line": m.group(2).strip()}
    return {"years": [], "months": [], "spread": False, "line": ""}


def _retag(header: str, drop_months: bool) -> str:
    """A scene line without its own school year (and month, if asked): the storyline's timing decides those."""
    m = re.fullmatch(r"(\s*---\s*)(.+?)((?:\s*\[[^\]]*\])*)\s*(#[a-z][a-z0-9_]{2,79})?\s*", header)
    if not m:
        return header
    toks = [t.strip() for t in re.split(r"\s*[·;,]\s*", " · ".join(re.findall(r"\[([^\]]*)\]", m.group(3) or ""))) if t.strip()]
    keep = [t for t in toks if not (_timing_token(t) == "year" or (drop_months and (_timing_token(t) == "season" or
                                    re.fullmatch(r"(after|before)\s+\w+\.?\s+\d{1,2}(st|nd|rd|th)?", t.lower()))))]
    return f"{m.group(1)}{m.group(2).rstrip()}" + (f"  [{' · '.join(keep)}]" if keep else "") + (f" {m.group(4)}" if m.group(4) else "")


def set_timing(pid: str, years: list, seasons: list, spread: bool, every_scene: bool = True, keep_months: bool = True) -> dict:
    """Set a storyline's timing by hand: its when: line gets these school years and seasons (and spread), keeping its
    other tags. every_scene: its scenes' own school years go (they all follow this), and their months too unless
    keep_months (holidays and school days always keep their day). Saved like any edit (checked first)."""
    from . import script as SC
    p = _script_pack(pid)
    if p["pack"].get("outline"):
        return _set_outlined_timing(p, pid, years, seasons, every_scene, keep_months)
    src = p["script"].rstrip("\n").split("\n")
    end = _header_end(src)
    if every_scene and years:
        stop = next((i for i in range(end, len(src)) if SC.SECTION_RE.match(src[i].strip())), len(src))
        for i in range(end, stop):
            if SC.SCENE_RE.match(src[i].strip()):
                src[i] = _retag(src[i], drop_months=not keep_months)
    at, keep = None, []
    for i in range(end):
        m = SC.ATTR_RE.match(src[i].strip())
        if m and m.group(1).lower() == "when":
            at = i
            keep = [t for t in re.split(r"\s*[·;,]\s*", m.group(2)) if t.strip() and _timing_token(t) is None]
    toks = [_year_word(y) for y in years if y in YEARS] + [x for x in seasons if x in SC.SEASONS] + keep
    if spread and years:
        toks.append("spread")
    line = ("when: " + " · ".join(toks)) if toks else None
    if at is not None:
        if line:
            src[at] = line
        else:
            del src[at]
    elif line:
        src.insert(1, line)
    return add_script("\n".join(src) + "\n", into=pid)


def _outline_lines(src: list) -> tuple:
    """Where an outlined storyline's outline block is: (its first line, the line after it)."""
    from . import script as SC
    a = next((i for i, ln in enumerate(src) if ln.strip().lower() == "outline:"), None)
    if a is None:
        return None, None
    b = a + 1
    while b < len(src) and not (SC.SCENE_RE.match(src[b].strip()) or SC.SECTION_RE.match(src[b].strip())):
        b += 1
    return a, b


def _retime_outline_line(line: str, year: str | None, month: int | None, drop_years: bool, drop_months: bool) -> str:
    """An outline line with its when part changed: `7. Title | <when> | what happens | only if ...`."""
    from . import script as SC
    m = SC.OUTLINE_RE.match(line.strip())
    if not m:
        return line
    parts = [x.strip() for x in SC._split(m.group(2), "|")]
    while len(parts) < 2:
        parts.append("")
    toks = [t for t in re.split(r"\s*[·;,]\s*", parts[1]) if t.strip()]
    toks = [t for t in toks if not ((drop_years and _timing_token(t) == "year") or (drop_months and _timing_token(t) == "season"))]
    names = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    new = ([_year_word(year)] if year in YEARS else []) + ([names[int(month)]] if month and 1 <= int(month) <= 12 else []) + toks
    parts[1] = " · ".join(new)
    return f"{m.group(1)}. " + " | ".join(parts).rstrip(" |")


def _set_outlined_timing(p, pid, years, seasons, every_scene, keep_months) -> dict:
    """An outlined storyline's timing: its years: line (school years and seasons; it's always spaced out), and its outline's
    own years (and months, unless keep_months) come off so everything follows it."""
    from . import script as SC
    src = p["script"].rstrip("\n").split("\n")
    end = _header_end(src)
    toks = [_year_word(y) for y in years if y in YEARS] + [x for x in seasons if x in SC.SEASONS]
    at = next((i for i in range(end) if (SC.ATTR_RE.match(src[i].strip()) or [None, ""])[0] and
               SC.ATTR_RE.match(src[i].strip()).group(1).lower() in ("years", "when")), None)
    line = ("years: " + " · ".join(toks)) if toks else None
    if at is not None:
        if line:
            src[at] = line
        else:
            del src[at]
    elif line:
        src.insert(1, line)
    if every_scene and years:
        a, b = _outline_lines(src)
        if a is not None:
            for i in range(a + 1, b):
                src[i] = _retime_outline_line(src[i], None, None, True, not keep_months)
    return add_script("\n".join(src) + "\n", into=pid)


def set_scene_timing(pid: str, sid: str, year: str | None, month: int | None) -> dict:
    """Move one scene: its school year and month (None leaves that part to the storyline). Its other tags stay."""
    from . import script as SC
    p = _script_pack(pid)
    entry = next((e for e in p["pack"].get("outline") or [] if e.get("sid") == sid or f"{pid}#{e['n']}" == sid), None)
    if entry is not None:  # an outlined storyline: its outline line says when
        src = p["script"].rstrip("\n").split("\n")
        a, b = _outline_lines(src)
        for i in range(a + 1, b):
            m = SC.OUTLINE_RE.match(src[i].strip())
            if m and int(m.group(1)) == entry["n"]:
                src[i] = _retime_outline_line(src[i], year, month, True, bool(month))
                return add_script("\n".join(src) + "\n", into=pid)
        raise KeyError(sid)
    sc = next((x for x in p["pack"].get("scenes") or [] if isinstance(x, dict) and x.get("id") == sid), None)
    if sc is None or not sc.get("line"):
        raise KeyError(sid)
    src = p["script"].rstrip("\n").split("\n")
    i = sc["line"] - 1
    m = re.fullmatch(r"(\s*---\s*)(.+?)((?:\s*\[[^\]]*\])*)\s*(#[a-z][a-z0-9_]{2,79})?\s*", src[i])
    if not m:
        raise KeyError(sid)
    toks = [t.strip() for t in re.split(r"\s*[·;,]\s*", " · ".join(re.findall(r"\[([^\]]*)\]", m.group(3) or ""))) if t.strip()]
    keep = [t for t in toks if not (_timing_token(t) in ("year", "season") or
                                    (month and re.fullmatch(r"(after|before)\s+\w+\.?\s+\d{1,2}(st|nd|rd|th)?", t.lower())))]
    names = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    new = ([_year_word(year)] if year in YEARS else []) + ([names[int(month)]] if month and 1 <= int(month) <= 12 else []) + keep
    src[i] = f"{m.group(1)}{m.group(2).rstrip()}" + (f"  [{' · '.join(new)}]" if new else "") + (f" {m.group(4)}" if m.group(4) else "")
    return add_script("\n".join(src) + "\n", into=pid)


def add_script(text: str, into: str | None = None, strict: bool = False) -> dict:
    """Add scripts: each === storyline goes to its own file (a storyline with the same title is replaced: that's how
    you update one). into=<pack id> saves the text as that storyline's file instead (editing it in place).
    Anything fixable is fixed (scriptfix: an unknown effect or tag comes off, an unknown speaker talks as a walk-on...)
    and each fix comes back as a note; the fixed script is what's saved. strict=True refuses instead."""
    from . import script as SC
    from . import scriptfix
    if strict:
        src = SC.extract(text)
        r = SC.compile_script(src, library=library())
        notes = []
    else:
        fx = scriptfix.repair(text, library=library())
        src, r, notes = fx["text"], fx["result"], fx["notes"]
    if r["errors"]:
        org, now = (fx.get("origin") or []) if not strict else [], src.split("\n")
        return {"ok": False, "errors": [f"line {e['line']}: {e['text']}" for e in r["errors"]], "warnings": r["warnings"],
                "error_lines": r["errors"], "notes": [_note_text(n) for n in notes],
                # each problem's line in the script as it came in, and that line as it reads
                "error_at": [org[e["line"] - 1] if 0 < e["line"] <= len(org) else e["line"] for e in r["errors"]],
                "error_quote": [now[e["line"] - 1].strip() if 0 < e["line"] <= len(now) else "" for e in r["errors"]]}
    os.makedirs(USER_DIR, exist_ok=True)
    secs = SC.split_sections(src)
    ids = []
    kept_notes = []
    for i, (title, body) in enumerate(secs):
        if into and i == 0:
            path = _script_path(into)
            _backup(path, "edited")
        else:
            path = os.path.join(USER_DIR, f"{_slug(title or 'untitled')}.story")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    old = f.read()
                if _is_update(old, body):
                    _backup(path, "replaced by a newer version")
                else:
                    # a different storyline (or an expansion) with the same name: never write over what you have
                    title2 = _free_title(title or "Untitled", body)
                    if title2 != title:
                        body = _retitle(body, title2)
                        kept_notes.append(f"You already have \"{title}\": this was added as \"{title2}\" (nothing of yours was replaced)")
                    path = os.path.join(USER_DIR, f"{_free_stem(_slug(title2))}.story")  # its own file, whatever the name
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(path + ".tmp", path)
        _touched(path)
        ids.append("yours:" + os.path.basename(path)[:-6])
    st = _state()
    st["disabled"] = [d for d in st.get("disabled", []) if d not in ids]
    _save_state(st)
    reload()
    return {"ok": True, "ids": ids, "warnings": [f"line {e['line']}: {e['text']}" for e in r["warnings"]], "summary": r["summary"],
            "notes": kept_notes + [f"line {n['line']}: {n['text']}" for n in notes], "text": src}


def fix_prompt(skipped: list, gaps: list | None = None) -> str:
    """What to tell ChatGPT when scenes couldn't go in or went in with pieces missing: which, the exact lines and what's
    wrong, and the rules that cover nearly every mistake. Empty when everything went in whole."""
    gaps = gaps or []
    if not skipped and not gaps:
        return ""
    L = []
    if skipped:
        L += ["Some of the LIFE OS scenes you wrote couldn't go into the game:", ""]
        for sk in skipped:
            L.append(f"Scene {sk['n']} ({sk.get('title') or ''}):")
            L += [f"- {p}" for p in sk.get("problems") or []]
            L.append("")
    if gaps:
        L += ["These went in, but with pieces missing:", ""]
        for g in gaps:
            L.append(f"Scene {g['n']} ({g.get('title') or ''}):")
            L += [f"- {p}" for p in g.get("problems") or []]
            L.append("")
    L += ["Send just these scenes again, each one complete from its first line to its last, in ONE code block, same format "
          "(each starts with --- <number>. <title>), nothing after it. If they don't all fit, send fewer: never cut one short.", "",
          "Rules that fix most of these:",
          "- Every scene ends on a question (someone asks me something, or it's my move), then 2 to 4 choices.",
          "- `* ` starts a choice; the lines after it, down to the next `* `, are what happens after it. Every choice gets at "
          "least one line.",
          "- `** ` is a choice inside the choice above it. `either way:` on its own line: what follows plays whichever you picked.",
          "- Effects go after | on a choice: * \"Front row.\" | nicole affection +",
          "- Narration is a plain line: no *italics*, no **bold** names, no Choice 1: or Outcome: labels.",
          "- Only the people in the storyline's cast talk by their cast name; anyone else talks by name (Mom:, Coach Reyes:)."]
    return "\n".join(L) + "\n"


def _note_text(n) -> str:
    """A fix or a problem, as words: "line 4: ..." (they come as {line, text} from the fixer)."""
    if isinstance(n, dict):
        return f"line {n.get('line')}: {n.get('text')}" if n.get("line") else str(n.get("text", ""))
    return str(n)


# ---------------------------------------------------------------------------------------- never lose a storyline
HISTORY_KEEP = 8  # older versions kept per storyline


def _scene_titles(body: str) -> list:
    out = []
    for ln in body.split("\n"):
        m = re.match(r"^\s*---\s*(.+?)\s*$", ln)
        if m:
            t = re.sub(r"#\S+\s*$", "", m.group(1))
            t = re.sub(r"\[[^\]]*\]", "", t)
            t = re.sub(r"^\d+\s*[.):\-]\s*", "", t).strip().lower()
            if t:
                out.append(t)
    return out


def _schedule_only(body: str) -> bool:
    return bool(re.search(r"^\s*schedule\s*:", body, re.M | re.I)) and not re.search(
        r"^\s*(---|outline\s*:|(texts|replies|chat|flirt|group\s+chat|trivia|narration|mods|choices)\s+\S)", body, re.M | re.I)


def _is_update(old: str, new: str) -> bool:
    """A paste with the same name as one you have replaces it only when it's that storyline again, newer: a season plan, or a
    version that still has every scene the old one had. Anything else is kept alongside it."""
    if _schedule_only(old) and _schedule_only(new):
        return True
    plan = lambda b: bool(re.search(r"^\s*===\s*season plan\s*$", b, re.M | re.I))  # noqa: E731  (Make it one story: the newest plan)
    if plan(old) and plan(new):
        return True
    was, now = _scene_titles(old), set(_scene_titles(new))
    if re.search(r"^\s*expands\s*:", new, re.M | re.I) and not re.search(r"^\s*expands\s*:", old, re.M | re.I):
        return False  # an expansion never takes its storyline's place
    return bool(was) and set(was) <= now


def _names_in_use() -> set:
    return {str(p["pack"].get("name") or "").strip().lower() for p in packs()}


def _free_title(title: str, body: str) -> str:
    """A name nobody's using: an expansion named after its storyline becomes "<Storyline>: more"; anything else gets (2), (3)..."""
    # (names only: two long names can share a file name, since file names are cut short; _free_stem picks the file)
    used = _names_in_use()
    m = re.search(r"^\s*expands\s*:\s*(.+?)\s*$", body, re.M | re.I)
    base = f"{m.group(1)}: more" if m and m.group(1).strip().lower() == title.strip().lower() else title
    if base.strip().lower() not in used:
        return base
    n = 2
    while f"{base} ({n})".lower() in used:
        n += 1
    return f"{base} ({n})"


def _free_stem(stem: str) -> str:
    n, out = 2, stem
    while os.path.exists(os.path.join(USER_DIR, f"{out}.story")) or os.path.exists(os.path.join(USER_DIR, f"{out}.json")):
        out = f"{stem[:34]}_{n}"
        n += 1
    return out


def _retitle(body: str, title: str) -> str:
    return re.sub(r"^(\s*===\s*).+$", lambda m: m.group(1) + title, body, count=1, flags=re.M) if re.search(r"^\s*===", body, re.M) \
        else f"=== {title}\n{body}"


def _history_dir() -> str:
    return os.path.join(USER_DIR, ".history")


def _history_index() -> dict:
    try:
        with open(os.path.join(_history_dir(), "index.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _backup(path: str, why: str):
    """Keep the version that's about to be replaced or removed (the last few per storyline), so it can come back."""
    import shutil
    import time
    if not os.path.exists(path) or not path.endswith(".story"):
        return
    d = _history_dir()
    os.makedirs(d, exist_ok=True)
    stem = os.path.basename(path)[:-6]
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^\s*===\s*(.+?)\s*$", text, re.M)
    now = time.time()
    fn = f"{stem}~{int(now * 1000)}.story"
    shutil.copyfile(path, os.path.join(d, fn))
    idx = _history_index()
    idx[fn] = {"stem": stem, "title": m.group(1) if m else stem, "why": why, "at": now, "scenes": len(_scene_titles(text))}
    mine = sorted((k for k, v in idx.items() if v.get("stem") == stem), key=lambda k: idx[k]["at"])
    for k in mine[:-HISTORY_KEEP]:
        idx.pop(k, None)
        try:
            os.remove(os.path.join(d, k))
        except OSError:
            pass
    with open(os.path.join(d, "index.json.tmp"), "w", encoding="utf-8") as f:
        json.dump(idx, f)
    os.replace(os.path.join(d, "index.json.tmp"), os.path.join(d, "index.json"))
    return fn


def history() -> list:
    """Older versions of your storylines (replaced, edited or removed), newest first."""
    idx = _history_index()
    out = [{"file": k, **v} for k, v in idx.items() if os.path.exists(os.path.join(_history_dir(), k))]
    return sorted(out, key=lambda x: -x["at"])


def restore(fn: str) -> str:
    """Bring an older version back. If that storyline is still there it's kept as an older version itself. Its pack id."""
    idx = _history_index()
    meta = idx.get(fn)
    src = os.path.join(_history_dir(), os.path.basename(fn))
    if not meta or not os.path.exists(src):
        raise KeyError(fn)
    with open(src, encoding="utf-8") as f:
        text = f.read()
    path = os.path.join(USER_DIR, f"{meta['stem']}.story")
    _backup(path, "replaced by an older version")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)
    _touched(path)
    st = _state()
    st["disabled"] = [d for d in st.get("disabled", []) if d != f"yours:{meta['stem']}"]
    _save_state(st)
    reload()
    return f"yours:{meta['stem']}"


def as_expansion(text: str, pid: str) -> str:
    """What ChatGPT wrote as more of a storyline, made sure to be an expansion of it: `expands:` added if it's missing, and
    a name of its own if it reused the storyline's (so it can never take the storyline's place)."""
    from . import script as SC
    p = _script_pack(pid)
    if p["pack"].get("expands"):  # more of an expansion is more of its storyline
        p = _script_pack(next(x["id"] for x in packs() if x["pack"].get("name") == p["pack"]["expands"]))
    parent = p["pack"].get("name") or ""
    src = SC.extract(text)
    m = re.search(r"^(\s*===\s*)(.+?)\s*$", src, re.M)
    if not m:
        return f"=== {parent}: more\nexpands: {parent}\n" + src
    title = m.group(2)
    if title.strip().lower() == parent.strip().lower():
        title = _free_title(f"{parent}: more", "")
    head = f"{m.group(1)}{title}"
    rest = src[m.end():]
    if re.search(r"^\s*expands\s*:", rest, re.M | re.I):  # whatever it said (an expansion's name, a typo): the storyline itself
        rest = re.sub(r"^(\s*expands\s*:\s*).*$", lambda mm: mm.group(1) + parent, rest, count=1, flags=re.M | re.I)
    else:
        head += f"\nexpands: {parent}"
    return src[:m.start()] + head + rest


# ---------------------------------------------------------------------------------------- merged content

_cache: dict = {}


def reload():
    _cache.clear()
    _dir_cache.clear()


NEEDABLE = {"them": "them", "them_first": "them", "best_friend": "best_friend", "best_friend_first": "best_friend",
            "sibling": "sibling", "sibling_first": "sibling", "partner": "partner", "partner_first": "partner", "pet": "pet"}


def needs(obj) -> list:
    """Who has to exist for this text or choice to make sense ({sibling_first}, ["rel", "partner", ...], ...)."""
    out = set()
    def walk(x, in_ops=False):
        if isinstance(x, str):
            out.update(NEEDABLE[n] for n in PH.findall(x) if n in NEEDABLE)
        elif isinstance(x, dict):
            for k, v in x.items():
                if k not in ("fits", "requires"):
                    walk(v, in_ops or k == "ops")
        elif isinstance(x, list):
            if in_ops and x and isinstance(x[0], str) and x[0] in ("rel", "rel_back", "text", "hang_out") and len(x) > 1 and x[1] in NEEDABLE:
                out.add(NEEDABLE[x[1]])
            if in_ops and x and x[0] == "memory" and len(x) > 4 and isinstance(x[4], list):
                out.update(NEEDABLE[r] for r in x[4] if r in NEEDABLE)
            for y in x:
                walk(y, in_ops)
    walk(obj)
    return sorted(out)


_needs_memo: dict = {}  # (id of a choice's ops, label, hint) -> (those ops, who it needs): a scene's choices are walked once


def _with_needs(ch) -> dict:
    ops = ch.get("ops", [])
    k = (id(ops), ch.get("label"), ch.get("hint"))
    hit = _needs_memo.get(k)
    if hit is not None and hit[0] is ops:
        n = hit[1]
    else:
        n = needs({"label": ch.get("label"), "hint": ch.get("hint"), "ops": ops})
        if len(_needs_memo) > 60000:
            _needs_memo.clear()
        _needs_memo[k] = (ops, n)
    ch = dict(ch, fits=ch.get("fits", {}), ops=ops)
    if n:
        ch["requires"] = n
    return ch


def _build(only: set | None = None) -> dict:
    texts = copy.deepcopy(_texts_base())
    templates = copy.deepcopy(_base("templates.json")["templates"])
    moments = copy.deepcopy(_base("moments.json")["moments"])
    from . import drama, hangouts, nights
    hangouts.register(moments)
    nights.register(moments)  # parties and dances, scene by scene
    drama.register(moments)  # friends fighting, triangles, falling out and making up
    replies = {k: list(v) for k, v in _base_reply_sets().items()}
    mods = {k: copy.deepcopy(v) for k, v in _base("mods.json").items() if k in MOD_KINDS}
    loaded = []
    trivia_extra: dict = {}
    chat_lines = copy.deepcopy(_base("chat.json"))
    chat_people = []  # (pack, {kind: lines}): a storyline's own people text with these
    group_chats, gc_seen = [], set()  # group chat conversations from your packs (groupchat.py)
    in_order = {}  # pack -> its scenes happen as chapters, in the order they're written
    for p in packs():
        if not p["enabled"] or (only is not None and p["id"] not in only):
            continue
        pk = p["pack"]
        loaded.append(p["id"])
        for pool, lines in (pk.get("texts") or {}).items():
            have = {_lines.text_of(x).lower().strip() for x in texts[pool]}
            for s in lines:
                k = _lines.text_of(s).lower().strip()
                if k not in have:
                    texts[pool].append(s)
                    have.add(k)
        for kind, bank in (pk.get("mods") or {}).items():
            for tag, ls in bank.items():
                cur = mods.setdefault(kind, {}).setdefault(tag, [])
                cur.extend(x for x in ls if x not in cur)
        for rs, opts in (pk.get("replies") or {}).items():
            have = {l.lower() for l, _ in replies[rs]}
            for o in opts:
                label, tone = (o["label"], o["tone"]) if isinstance(o, dict) else (o[0], o[1])
                if label.lower() not in have:
                    replies[rs].append((label, tone))
                    have.add(label.lower())
        for key, lines in (pk.get("narration") or {}).items():
            templates[key] = templates[key] + [s for s in lines if s not in templates[key]]
        for mid, chs in (pk.get("moment_choices") or {}).items():
            moments[mid]["choices"] = moments[mid]["choices"] + [_with_needs(ch) for ch in chs]
        _merge_chat(chat_lines, {k: v for k, v in (pk.get("chat") or {}).items() if k != "people"})
        if (pk.get("chat") or {}).get("people"):
            chat_people.append((p["id"], pk["chat"]["people"]))
        for b in pk.get("groupchat") or []:
            if isinstance(b, dict) and b.get("id") not in gc_seen:
                gc_seen.add(b["id"])
                group_chats.append(b)
        for sub, qs in (pk.get("trivia") or {}).items():
            trivia_extra.setdefault(sub, []).extend({"q": q["q"], "a": q["a"], "w": list(q["w"]), "g": q.get("g", 9)} for q in qs)
        st_order = _state().get("order", {})
        in_order[p["id"]] = st_order.get(p["id"], pk.get("in_order", p["source"] == "yours"))
        for n, sc in enumerate(pk.get("scenes") or []):
            if sc["id"] in moments:
                continue  # an earlier pack already has a scene with this id
            moments[sc["id"]] = {"title": sc["title"], "text": sc["text"],
                                 "choices": _with_beats(moments, sc["id"], sc["title"], p["id"], sc["choices"], ""),
                                 "scene": {"who": sc.get("who"), "when": sc.get("when", {}), "pack": p["id"], "by_text": sc.get("by_text"), "order": n,
                                           "cast_refs": sc.get("cast_refs") or [],
                                           "needs": needs({"title": sc["title"], "text": sc["text"]})}}
    cast = {}  # named people storylines are about: a slot name means the same person in every pack that uses it
    for p in packs():
        if p["enabled"] and p["id"] in loaded:
            for name, spec in (p["pack"].get("cast") or {}).items():
                if isinstance(spec, dict):
                    d = cast.setdefault(name, {"spec": normalize_slot(spec), "packs": []})
                    d["packs"].append(p["id"])
    # scripts can name another storyline's scene ("after Same Team: Cut day"): resolve those by title now that all are in
    titles = {}
    pack_names = {x["id"]: x["pack"].get("name") or "" for x in packs()}
    for mid, mm in moments.items():
        scn = mm.get("scene")
        if scn:
            nm = pack_names.get(scn.get("pack"), "")
            titles.setdefault(str(mm.get("title", "")).lower(), mid)
            titles[f"{str(nm).lower()}: {str(mm.get('title', '')).lower()}"] = mid
    resolve = lambda r: titles.get(r[1:].strip().lower()) if isinstance(r, str) and r.startswith("@") else r  # noqa: E731
    for mm in moments.values():
        scn = mm.get("scene")
        if scn and (scn.get("when") or {}).get("after"):
            a = scn["when"]["after"]
            scn["when"] = {**scn["when"], "after": [x for x in (resolve(y) for y in (a if isinstance(a, list) else [a])) if x]}
    by_name = {}  # a storyline's title -> its scenes, in order (a season plan can retime all of one)
    for p in packs():
        if p["enabled"] and p["id"] in loaded and p["pack"].get("name"):
            by_name[str(p["pack"]["name"]).lower()] = [sc["id"] for sc in p["pack"].get("scenes") or [] if isinstance(sc, dict) and sc.get("id") in moments]
    for p in packs():  # a season plan places any storyline's episodes across the seasons
        if p["enabled"] and p["id"] in loaded:
            for sid0, sch in (p["pack"].get("schedule") or {}).items():
                whole = by_name.get(sid0[1:].strip().lower()) if isinstance(sid0, str) and sid0.startswith("@") and not resolve(sid0) else None
                if whole and isinstance(sch, dict):  # "Danny [freshman · spread]": the whole storyline
                    _retime_all(moments, whole, sch, resolve)
                    continue
                sid = resolve(sid0)
                if isinstance(sch, dict) and sch.get("after"):
                    sch = {**sch, "after": [x for x in (resolve(y) for y in (sch["after"] if isinstance(sch["after"], list) else [sch["after"]])) if x]}
                sc = (moments.get(sid) or {}).get("scene")
                if sc is not None and isinstance(sch, dict):
                    when = dict(sc.get("when") or {})
                    for k, v in sch.items():
                        if k == "after":
                            add = v if isinstance(v, list) else [v]
                            when["after"] = sorted(set(add if sch.get("replace_after") else (when.get("after") or []) + add))
                        elif k in SCHEDULE_KEYS and k != "replace_after":
                            when[k] = v
                    sc["when"] = when
    return {"texts": texts, "templates": templates, "moments": moments, "replies": replies, "trivia": trivia_extra, "mods": mods,
            "chat": chat_lines, "chat_people": chat_people, "in_order": in_order, "loaded": loaded, "cast": cast,
            "groupchat": group_chats, "load_errors": {}}


def _retime_all(moments, sids, sch, resolve):
    """A season plan line for a whole storyline: its years (and months) for every scene; spread puts them in order across
    those years. Dated scenes (holidays, school days) keep their day."""
    from . import script as SC
    sch = dict(sch)
    spread = sch.pop("spread", False)
    if sch.get("after"):
        sch["after"] = [x for x in (resolve(y) for y in (sch["after"] if isinstance(sch["after"], list) else [sch["after"]])) if x]
    free = [s_ for s_ in sids if not (moments[s_]["scene"].get("when") or {}).get("dates")]
    slots = dict(zip(free, SC.spread_slots(sch.get("years"), sch.get("months"), len(free)))) if spread and sch.get("years") else {}
    for i, s_ in enumerate(sids):
        sc = moments[s_]["scene"]
        when = dict(sc.get("when") or {})
        for k, v in sch.items():
            if k == "after":
                if i == 0:  # the storyline starts after it
                    when["after"] = sorted(set(v if sch.get("replace_after") else (when.get("after") or []) + v))
            elif k in SCHEDULE_KEYS and k != "replace_after":
                when[k] = v
        if s_ in slots:
            when["years"], when["months"] = [slots[s_][0]], [slots[s_][1]]
            for k in ("not_before", "not_after"):
                when.pop(k, None)
        sc["when"] = when


def _build_safely() -> dict:
    """A pack broke loading: find which (adding them one at a time) and leave just those out, with why. The game always
    opens; the pack's card says what went wrong."""
    bad, ok = {}, []
    for p in packs():
        if not p["enabled"]:
            continue
        try:
            _build(only=set(ok + [p["id"]]))
            ok.append(p["id"])
        except Exception as e:  # noqa: BLE001
            bad[p["id"]] = f"couldn't load it ({type(e).__name__}: {e}). The rest of your packs are on; this one is skipped."
    m = _build(only=set(ok))
    m["load_errors"] = bad
    return m


def _with_beats(moments, sid, title, pack, choices, path) -> list:
    """Choices, where one with "then" keeps the scene going: the next beat is its own moment, right after."""
    out = []
    for i, ch in enumerate(choices):
        c2 = _with_needs({k: v for k, v in ch.items() if k != "then"})
        then = ch.get("then")
        if isinstance(then, dict):
            bid = f"{sid}__{path}{i}"
            moments[bid] = {"title": title, "text": then["text"], "beat_of": sid, "scene_pack": pack,
                            "choices": _with_beats(moments, sid, title, pack, then.get("choices") or [], f"{path}{i}_")}
            c2["ops"] = list(c2["ops"]) + [["beat", bid]]
        out.append(c2)
    return out


def in_order(pid) -> bool:
    return bool(merged()["in_order"].get(pid))


def set_in_order(pid: str, on: bool):
    if not any(p["id"] == pid for p in packs()):
        raise KeyError(pid)
    st = _state()
    st.setdefault("order", {})[pid] = bool(on)
    _save_state(st)
    reload()


def chapters(sim, pid) -> list:
    """A storyline's scenes in order (not the beats inside them)."""
    return sorted(((m["scene"].get("order", 0), sid, m) for sid, m in sim.cat.moments.items()
                   if (m.get("scene") or {}).get("pack") == pid), key=lambda x: x[0])


def progress(sim, pid) -> dict:
    """How far along a storyline you are: chapters done, out of how many, and what's next."""
    seen = sim.w.meta.get("scenes_seen", {})
    ch = chapters(sim, pid)
    done = sum(1 for _, sid, _ in ch if sid in seen)
    nxt = next((m["title"] for _, sid, m in ch if sid not in seen), None)
    return {"done": done, "of": len(ch), "next": nxt, "in_order": in_order(pid)}


def chapter_label(sim, kind) -> str | None:
    """'Hoops with my brother · Chapter 2 of 5' for a scene (or a beat inside one)."""
    m = sim.cat.moments.get(kind) or {}
    sid = m.get("beat_of") or kind
    sc = (sim.cat.moments.get(sid) or {}).get("scene")
    if not sc:
        return None
    pid = sc.get("pack")
    p = next((x for x in packs() if x["id"] == pid), None)
    name = (p["pack"].get("name") if p else None) or "A storyline"
    if not in_order(pid):
        return name
    ch = chapters(sim, pid)
    n = next((i for i, (_, s, _) in enumerate(ch) if s == sid), 0) + 1
    return f"{name} · Chapter {n} of {len(ch)}"


def _merge_chat(into: dict, add: dict):
    """A pack's texting lines go into the same places as the built-in ones (no duplicates)."""
    for k, v in add.items():
        if k.startswith("_"):
            continue
        if k == "people" and isinstance(v, dict):
            into.setdefault("people", {})
            for kind, sub in v.items():
                into["people"].setdefault(kind, {})
                _merge_people(into["people"][kind], sub)
        elif isinstance(v, dict) and isinstance(into.get(k), dict):
            _merge_chat(into[k], v)
        elif isinstance(v, list) and isinstance(into.get(k), list):
            have = {_line_key(x) for x in into[k]}
            for x in v:
                key = _line_key(x)
                if key not in have:
                    into[k].append(x)
                    have.add(key)


def _line_key(x) -> str:
    """What makes a texting line the same line, whichever way it's written: a plain line, a question {"q": ...}, or a
    line with a context {"text": ..., "when": [...]}."""
    if isinstance(x, dict):
        return str(x.get("q") or x.get("text") or x.get("talk") or "").lower()
    return str(x).lower()


def _merge_people(into: dict, add: dict):
    for k, v in add.items():
        if isinstance(v, dict):
            _merge_people(into.setdefault(k, {}), v)
        elif isinstance(v, list):
            cur = into.setdefault(k, [])
            have = {_line_key(x) for x in cur}
            cur.extend(x for x in v if _line_key(x) not in have)


def chat_people() -> list:
    return merged()["chat_people"]


def pack_kinds(pack: str) -> list:
    """The kinds of people a storyline is about (from its scenes and its texting lines)."""
    m = merged()
    kinds = {(v.get("scene") or {}).get("who") for v in m["moments"].values() if (v.get("scene") or {}).get("pack") == pack}
    for pid, people in m["chat_people"]:
        if pid == pack:
            kinds |= set(people)
    return [k for k in WHO if k in kinds and k in CASTABLE]


def chat_lines() -> dict:
    return merged()["chat"]


def merged() -> dict:
    if "m" not in _cache:
        try:
            _cache["m"] = _build()
        except Exception:  # noqa: BLE001  never let one pack keep the game from opening
            _cache["m"] = _build_safely()
    return _cache["m"]


def texts() -> dict:
    return merged()["texts"]


def templates() -> dict:
    return merged()["templates"]


def moments() -> dict:
    return merged()["moments"]


def reply_sets() -> dict:
    return merged()["replies"]


def mods() -> dict:
    return merged()["mods"]


# ---------------------------------------------------------------------------------------- scenes in play

def _rel(w, a, b, f):
    r = w.rels.get((a, b))
    return getattr(r, f, 0.0) if r else 0.0


def _family(sim, me):
    return set(sim.siblings(me.id))


def candidates(sim, me, who) -> list:
    """People who fit 'who', best fit first (for the 'best' kinds) or in a fixed order (for the random kinds)."""
    w = sim.w
    fam = _family(sim, me)
    ok = lambda o: o in w.chars and w.chars[o].status == "active" and o != me.id  # noqa: E731
    known = [o for o in w.out.get(me.id, {}) if ok(o)]
    people = [o for o in known if w.chars[o].role != "staff" and o not in fam]
    thr = w.rules.get("rel.friend_threshold", 35)
    if who == "best_friend":
        return sorted([o for o in people if _rel(w, me.id, o, "affection") >= thr * 0.8], key=lambda o: -_rel(w, me.id, o, "affection"))[:1]
    if who == "friend":
        return sorted(o for o in people if _rel(w, me.id, o, "affection") >= thr)
    if who == "crush":
        partner = me.flags.get("partner")
        return sorted([o for o in people if o != partner and _rel(w, me.id, o, "attraction") >= 30],
                      key=lambda o: -_rel(w, me.id, o, "attraction"))[:1]
    if who == "partner":
        p = me.flags.get("partner")
        return [p] if p and ok(p) else []
    if who == "ex":
        return sorted(o for o in people if w.has_role(me.id, o, "ex"))
    if who == "rival":
        riv = lambda o: max(_rel(w, me.id, o, "rivalry"), _rel(w, o, me.id, "rivalry"))  # noqa: E731
        return sorted([o for o in people if riv(o) >= 30], key=lambda o: -riv(o))[:1]
    if who == "teammate":
        mates = set()
        for gid in me.memberships:
            g = w.groups.get(gid)
            if g and g.get("skill") in sim.cat.sports["sports"]:
                mates |= {m for m in g["members"] if ok(m) and m not in fam}
        return sorted(mates)
    if who == "classmate":
        return sorted(c.id for c in w.students() if ok(c.id) and c.grade == me.grade and c.school == me.school
                      and c.id not in fam and _rel(w, me.id, c.id, "familiarity") < 30)
    if who in SIBLING_KINDS:
        sibs = [s for s in sim.siblings(me.id) if ok(s)]
        g = me.grade or 9
        if who.startswith("older_"):
            sibs = [s for s in sibs if (w.chars[s].grade or 99) > g]
        elif who.startswith("younger_"):
            sibs = [s for s in sibs if (w.chars[s].grade or 0) < g]
        if who.endswith("brother"):
            sibs = [s for s in sibs if w.chars[s].gender == "m"]
        elif who.endswith("sister"):
            sibs = [s for s in sibs if w.chars[s].gender == "f"]
        elif who == "twin":
            sibs = [s for s in sibs if w.has_role(me.id, s, "twin")]
        return sibs
    if who == "coach":
        return sorted({w.groups[g].get("staff") for g in me.memberships if w.groups.get(g, {}).get("staff") and ok(w.groups[g]["staff"])})
    return []


def _pro():
    from . import pro
    return pro


def _requirement(sim, me, r) -> bool:
    from . import calendar as calm
    w = sim.w
    if isinstance(r, str) and r.startswith("pro:"):
        return _pro().requirement(sim, me, r)  # the pro leagues running in the background (pro.py)
    from . import gameplay
    g = gameplay.requirement(sim, me, r)  # your last game: we won, I played great, I won it...
    if g is not None:
        return g
    cal = sim.cat.world["calendar"]
    if r == "dating":
        return bool(me.flags.get("partner"))
    if r == "single":
        return not me.flags.get("partner")
    if r == "has_pet":
        h = w.households.get(me.household_id) or {}
        return bool(h.get("pet")) or any(p.get("household") == me.household_id and p.get("status") == "home" for p in w.meta.get("pets", {}).values())
    if r == "has_sibling":
        return bool(sim.siblings(me.id))
    if r == "plays_sport":
        return any(w.groups.get(g, {}).get("skill") in sim.cat.sports["sports"] for g in me.memberships)
    if r == "in_season":
        return any(i["kind"] == "game" and i.get("group") in me.memberships and abs(i["day"] - w.day) <= 7 for i in w.calendar)
    if r == "injured":
        return me.flags.get("injured_until", -1) >= w.day
    if r == "grounded":
        return me.flags.get("grounded_until", -1) >= w.day
    if r == "school_day":
        return calm.is_school_day(w.day, cal)
    if r == "weekend":
        return calm.date_of(w.day).weekday() >= 5
    if r == "summer":
        return calm.break_name(w.day, cal) == "Summer"
    if r == "in_high_school":
        return (me.grade or 0) <= 12
    if r == "in_college":
        return (me.grade or 0) >= 13
    if isinstance(r, str) and r.startswith("class:"):
        return my_class(sim, me, r[6:]) is not None and calm.is_school_day(w.day, cal)
    return False


_SUBJECTS = None


def class_subjects() -> dict:
    """Every class subject a scene can be set in (biology, chemistry, spanish...) -> a class name for it."""
    global _SUBJECTS
    if _SUBJECTS is None:
        d = _base("classes.json")
        out = {}
        for rows in d["grades"].values():
            for r in rows:
                for spec in (r["std"], r["hon"]):
                    out.setdefault(spec[1], spec[0])
        for e in d.get("electives") or []:
            out.setdefault(e["class"][1], e["class"][0])
        _SUBJECTS = out
    return _SUBJECTS


def my_class(sim, me, subject):
    """Your class in that subject this school year (its name and teacher), or None."""
    from . import classes
    if (me.grade or 0) > 12:
        return None
    try:
        sched = classes.schedule(sim, me)
    except Exception:  # noqa: BLE001  (no schedule for this person)
        return None
    return next((c for c in sched if c.get("subject") == subject), None)


def _remembered_who(w, key):
    v = w.meta.get("remembered", {}).get(key)
    return v.get("them") if isinstance(v, dict) else None


def _in(v, rng):
    return rng[0] <= v <= rng[1]


def _when_ok(sim, me, sid, when, ignore_time=False) -> bool:
    from . import calendar as calm
    w = sim.w
    seen = w.meta.get("scenes_seen", {}).get(sid, [])
    if not ignore_time:
        if seen and when.get("once", True):
            return False
        if seen and when.get("cooldown_days") and w.day - seen[-1] < when["cooldown_days"]:
            return False
        d = calm.date_of(w.day)
        if when.get("dates") and not calm.date_matches(w.day, when["dates"], sim.cat.world["calendar"]):
            return False
        if when.get("months") and d.month not in when["months"]:
            return False
        if when.get("weekdays") and WEEKDAYS[d.weekday()] not in when["weekdays"]:
            return False
    if when.get("years") and not any((me.grade or 0) in YEARS[y] for y in when["years"]):
        return False
    for r in when.get("requires", []):
        if not _requirement(sim, me, r):
            return False
    mem = w.meta.get("remembered", {})
    if any(k not in mem for k in when.get("remembered", [])) or any(k in mem for k in when.get("not_remembered", [])):
        return False
    alldone = w.meta.get("scenes_done", {})  # after = those scenes have resolved, not just started
    after = when.get("after") or []
    after = after if isinstance(after, list) else [after]
    if any(a not in alldone and not _expired(sim, me, a) for a in after):
        return False  # (a chapter whose school years are over counts as skipped, so the story doesn't get stuck)
    done_after = [alldone[a][-1] for a in after if a in alldone]
    if done_after and when.get("gap_days") and not ignore_time and w.day - max(done_after) < when["gap_days"]:
        return False
    for f, rng in (when.get("me") or {}).items():
        v = me.mood if f == "mood" else me.gpa if f == "gpa" else me.needs.get(f, 50)
        if not _in(v, rng):
            return False
    return True


def cast_of(w, pack, who):
    return (w.meta.get("pack_cast", {}).get(pack) or {}).get(who)


def set_cast(w, pack, who, cid):
    w.meta.setdefault("pack_cast", {}).setdefault(pack, {})[who] = cid


# ---------------------------------------------------------------------------------------- cast slots
# A pack can name the people it's about: "cast": {"lead_brother": {"who": "older_brother", "sport": "basketball",
# "grade_offset": 3}}, and its scenes say "who": "cast:lead_brother". A slot is bound once, to one real person in your story
# (never a new or changed one), and stays bound for the whole run: through graduation, college, everything. Every pack that
# uses the same slot name gets the same person. If nobody fits, those scenes just don't happen.

CAST_FIELDS = ("who", "gender", "sport", "grade_offset", "bind", "bond", "floor", "label", "of", "name")
OF_KINDS = ("friend", "best_friend", "teammate", "partner")  # "friend of sis": someone in another cast member's life
CAST_ALIASES = {"relationship_to_player": "who", "grade_offset_at_player_freshman": "grade_offset", "grade_offset_at_start": "grade_offset"}
CAST_SPORT_FLAGS = {"basketball_player": "basketball", "football_player": "football", "baseball_player": "baseball", "soccer_player": "soccer",
                    "softball_player": "softball"}
CAST_ACCEPTED = ("same_high_school_at_start", "bind_once", "notes")  # fine to include: always true / informational
GENDERS = {"m": "m", "male": "m", "boy": "m", "f": "f", "female": "f", "girl": "f"}


def normalize_slot(spec: dict) -> dict:
    out = {}
    for k, v in spec.items():
        if k in CAST_SPORT_FLAGS:
            if v:
                out["sport"] = CAST_SPORT_FLAGS[k]
            continue
        k2 = CAST_ALIASES.get(k, k)
        if k2 == "gender":
            v = GENDERS.get(str(v).lower(), v)
        if k2 in CAST_FIELDS:
            out[k2] = v
    who = out.get("who")
    if isinstance(who, str) and who.endswith("brother"):
        out.setdefault("gender", "m")
    elif isinstance(who, str) and who.endswith("sister"):
        out.setdefault("gender", "f")
    out.setdefault("bind", "first_scene")
    return out


def _check_cast(R, cast) -> set:
    if not isinstance(cast, dict):
        R.err("cast", 'is an object of named people, like {"lead_brother": {"who": "older_brother", "sport": "basketball"}}')
        return set()
    sports = set(_base("sports.json")["sports"])
    out = set()
    for name, spec in cast.items():
        w = f"cast.{name}"
        if not isinstance(name, str) or not SLUG.match(name):
            R.err(w, _slug_problem(name))
            continue
        if not isinstance(spec, dict):
            R.err(w, 'is an object like {"who": "older_brother"}')
            continue
        for k in spec:
            if k not in CAST_FIELDS + tuple(CAST_ALIASES) + tuple(CAST_SPORT_FLAGS) + CAST_ACCEPTED:
                R.warn(w, f"'{k}' is ignored. A cast slot has: {', '.join(CAST_FIELDS)}")
        n = normalize_slot(spec)
        who = n.get("who")
        if who == "named":  # someone in your story, by name
            if not isinstance(n.get("name"), str) or not n["name"].strip():
                R.err(w + ".name", "is the person's name, like \"Ally Soffer\"")
                continue
        elif n.get("of") is not None:
            if who not in OF_KINDS:
                R.err(w + ".who", f"someone in another person's life is their {', '.join(OF_KINDS)}; not '{who}'")
                continue
            if not isinstance(n["of"], str) or n["of"] not in cast or n["of"] == name:
                R.err(w + ".of", f"'{n['of']}' has to be another person in this storyline's cast ({', '.join(k for k in cast if k != name) or 'none yet'})")
                continue
        elif who not in CASTABLE:
            R.err(w + ".who", f"'{who}' isn't a kind of person a slot can be. Use one of: {', '.join(CASTABLE)}")
            continue
        g = n.get("gender")
        if g is not None and g not in ("m", "f"):
            R.err(w + ".gender", 'is "male" or "female"')
        elif (g == "f" and who.endswith("brother")) or (g == "m" and who.endswith("sister")):
            R.err(w + ".gender", f"doesn't match '{who}'")
        if n.get("sport") is not None and n["sport"] not in sports:
            R.err(w + ".sport", f"'{n['sport']}' isn't a sport. Sports: {', '.join(sorted(sports))}")
        off = n.get("grade_offset")
        if off is not None and (not isinstance(off, int) or isinstance(off, bool) or not -8 <= off <= 8):
            R.err(w + ".grade_offset", "is how many grades ahead of you they are (3 = a senior when you're a freshman; -2 = two behind)")
        if n.get("bind") not in ("start", "first_scene"):
            R.err(w + ".bind", '"start" (bind when the story starts) or "first_scene" (when their first scene comes up)')
        for key in ("bond", "floor"):
            v = n.get(key)
            if v is None:
                continue
            if not isinstance(v, dict):
                R.err(f"{w}.{key}", 'is an object like {"affection": 70, "trust": 70}')
                continue
            for f, x in v.items():
                if f not in REL_FIELDS:
                    R.err(f"{w}.{key}.{f}", f"isn't part of a relationship. Use: {', '.join(REL_FIELDS)}")
                elif not isinstance(x, (int, float)) or isinstance(x, bool) or not -100 <= x <= 100:
                    R.err(f"{w}.{key}.{f}", "is a number from -100 to 100")
        out.add(name)
    return out


def slot_spec(name):
    return (merged()["cast"].get(name) or {}).get("spec")


def slot_label(spec) -> str:
    if spec.get("label"):
        return spec["label"]
    if spec.get("who") == "named":
        return str(spec.get("name"))
    if spec.get("of"):
        kind = {"friend": "a friend", "best_friend": "the best friend", "teammate": "a teammate", "partner": "the boyfriend or girlfriend"}
        return f"{kind.get(spec.get('who'), 'someone')} of {spec['of']}" + (f", who plays {spec['sport']}" if spec.get("sport") else "")
    bits = [WHO.get(spec.get("who"), "someone")[:-1].lower()]
    if spec.get("sport"):
        bits.append(f"who plays {spec['sport']}")
    off = spec.get("grade_offset")
    if off:
        bits.append(f"{abs(off)} grade{'s' if abs(off) != 1 else ''} {'ahead of' if off > 0 else 'behind'} you")
    return ", ".join(bits)


def plays(sim, c, sport) -> bool:
    """On (or was on) that sport's team, or clearly into it."""
    w = sim.w
    if any(w.groups.get(g, {}).get("skill") == sport for g in c.memberships):
        return True
    if any(isinstance(pm, dict) and w.groups.get(pm.get("group"), {}).get("skill") == sport for pm in c.past_memberships):
        return True
    if (c.path or {}).get("sport") == sport:
        return True
    return c.skills.get(sport, 0) >= 55 or c.interests.get(sport, 0) >= 70


def _people_of(sim, me, who, base) -> list:
    """Someone in another person's life (their friends, best friend, teammates, partner), best fit first: never you or your
    family, and never someone another slot already means."""
    w = sim.w
    taken = {r.get("id") for r in (w.meta.get("cast_slots") or {}).values()}
    fam = _family(sim, me) | {me.id, base}
    ok = lambda o: o in w.chars and w.chars[o].status == "active" and o not in fam and o not in taken  # noqa: E731
    b = w.chars[base]
    if who == "partner":
        p = b.flags.get("partner")
        return [p] if p and ok(p) else []
    if who == "teammate":
        mates = set()
        for gid in b.memberships:
            g = w.groups.get(gid)
            if g and g.get("skill") in sim.cat.sports["sports"]:
                mates |= {m for m in g["members"] if ok(m)}
        return sorted(mates, key=lambda o: (-_rel(w, base, o, "affection"), o))
    thr = w.rules.get("rel.friend_threshold", 35)
    fr = sorted((o for o in w.out.get(base, {}) if ok(o) and w.chars[o].role != "staff" and _rel(w, base, o, "affection") >= thr),
                key=lambda o: (-_rel(w, base, o, "affection"), o))
    if not fr:  # nobody that close yet: the storyline makes it so with the best fit around them (same school, same year)
        pool = [c.id for c in w.students() if ok(c.id) and c.school == b.school and c.role != "staff"]
        fr = sorted(pool, key=lambda o: (-_rel(w, base, o, "affection"), abs((w.chars[o].grade or 0) - (b.grade or 0)),
                                         -_rel(w, base, o, "familiarity"), o))[:12]
    return fr[:1] if who == "best_friend" else fr


def named(sim, me, name: str) -> list:
    """Someone in your story by name: their full name, or a first name (the one you know best if there are several)."""
    w = sim.w
    want = " ".join(name.lower().split())
    if not want:
        return []
    act = [c for c in w.chars.values() if c.status == "active" and c.id != me.id]
    full = [c.id for c in act if c.name.lower() == want]
    if full:
        return full[:1]
    first = [c.id for c in act if c.first.lower() == want]
    return sorted(first, key=lambda o: (-_rel(w, me.id, o, "familiarity"), o))[:1]


def slot_candidates(sim, me, spec) -> list:
    """Everyone in your story who fits a slot right now."""
    w = sim.w
    if spec.get("who") == "named":
        return named(sim, me, spec.get("name") or "")
    if spec.get("of"):
        base = bound(sim, spec["of"]) or (bind(sim, me, spec["of"]) if spec["of"] in merged()["cast"] else None)
        out = _people_of(sim, me, spec["who"], base) if base else []
    else:
        out = candidates(sim, me, spec["who"])
    if spec.get("gender"):
        out = [o for o in out if w.chars[o].gender == spec["gender"]]
    if spec.get("sport"):
        out = [o for o in out if plays(sim, w.chars[o], spec["sport"])]
    off = spec.get("grade_offset")
    if off is not None and me.grade:
        out = [o for o in out if w.chars[o].grade is None or w.chars[o].grade - me.grade == off]
    return out


def bound(sim, name):
    """Who a slot is bound to (None if it isn't, or if they're gone from your story)."""
    rec = sim.w.meta.get("cast_slots", {}).get(name)
    cid = rec and rec.get("id")
    c = sim.w.chars.get(cid) if cid else None
    return cid if c and c.status == "active" else None


def bind(sim, me, name, cid=None, by="auto"):
    """The person a slot means in this story: bound once, then the same person every time (even after they graduate).
    The best fit is the one whose life matches what the storylines say (the brother who plays basketball); ties go the
    same way every time. Pass cid to pick them yourself."""
    w = sim.w
    d = merged()["cast"].get(name)
    if not d:
        return None
    spec = d["spec"]
    if cid is None:
        cur = bound(sim, name)
        if cur or name in w.meta.get("cast_slots", {}):
            return cur  # bound already (if they've left your story, so does this storyline: nobody gets swapped in)
        cands = slot_candidates(sim, me, spec)
        if not cands:
            return None
        words = " ".join(_story_words(sim, p) for p in d["packs"])
        cid = sorted(cands, key=lambda o: (-_fit(sim, o, words), o))[0]
    w.meta.setdefault("cast_slots", {})[name] = {"id": cid, "day": w.day, "by": by, "who": spec["who"]}
    w.meta.setdefault("cast_log", []).append([w.day, name, cid, by])
    _raise_to(sim, me.id, cid, spec.get("bond"))
    if spec.get("of") and spec.get("who") in ("friend", "best_friend"):  # the storyline says they're friends: now they are
        base = bound(sim, spec["of"])
        if base:
            close = spec["who"] == "best_friend"
            _raise_to(sim, base, cid, {"familiarity": 80 if close else 65, "affection": 70 if close else 50, "trust": 60 if close else 40})
    return cid


def _raise_to(sim, a, b, levels):
    """Make sure two people are at least this close (both ways). Never lowers anything."""
    from .social import label_for
    w = sim.w
    if not levels:
        return
    for x, y in ((a, b), (b, a)):
        r = w.ensure_rel(x, y, w.day)
        for f, v in levels.items():
            if getattr(r, f, None) is not None and getattr(r, f) < v:
                setattr(r, f, float(v))
        r.peak_affection = max(r.peak_affection, r.affection)
        r.label = label_for(r, w.rules)


def keep_floor(sim, ctx):
    """After a scene with a slot that has a floor: whatever you chose, the bond stays at least that strong."""
    name = (ctx or {}).get("cast_slot")
    spec = slot_spec(name) if name else None
    me = sim.w.meta.get("protagonist")
    if spec and spec.get("floor") and me and ctx.get("them") in sim.w.chars:
        _raise_to(sim, me, ctx["them"], spec["floor"])


def _expired(sim, me, sid) -> bool:
    """A scene whose school years are all behind you (it can't happen anymore)."""
    spec = sim.cat.moments.get(sid) or {}
    years = ((spec.get("scene") or {}).get("when") or {}).get("years") or []
    grades = [g for y in years for g in YEARS.get(y, ())]
    return bool(grades) and max(grades) < (me.grade or 0)


def suggest_lock(sim, pack_id, kind) -> dict:
    """What a general kind most likely means in this storyline, from what it says: older_sibling + "he/his/brother" and
    "hoops/court" -> your older brother who plays basketball."""
    words = _story_words(sim, pack_id)
    he, she = len(re.findall(MALE, words)), len(re.findall(FEMALE, words))
    base = kind.replace("_sibling", "") if kind != "sibling" else ""
    pre = f"{base}_" if base else ""
    who = kind if kind == "twin" else f"{pre}brother" if he > she * 1.5 else f"{pre}sister" if she > he * 1.5 else kind
    counts = {s: len(re.findall(rx, words)) for s, rx in SPORT_WORDS.items()}
    sport = max(counts, key=lambda s: counts[s]) if max(counts.values(), default=0) >= 3 else None
    return {"who": who, "sport": sport, "slot": who}


def lock_cast(pack: dict, slot: str, spec: dict, replace: list) -> dict:
    """Rewrite a pack so its scenes (and texting lines) about a general kind of person are about one named person:
    adds the cast slot and points those scenes at it. Everything else in the pack stays exactly as it was."""
    import copy
    out = copy.deepcopy(pack)
    cast = out.setdefault("cast", {})
    cast[slot] = dict(cast.get(slot) or {}, **{k: v for k, v in spec.items() if v is not None})
    n = 0
    for sc in out.get("scenes") or []:
        if isinstance(sc, dict) and sc.get("who") in replace:
            sc["who"] = f"cast:{slot}"
            n += 1
    people = (out.get("chat") or {}).get("people")
    target = normalize_slot(cast[slot]).get("who")
    if isinstance(people, dict) and target in WHO:
        for k in list(people):
            if k in replace and k != target:
                lines = people.pop(k)
                if isinstance(lines, dict) and isinstance(people.get(target), dict):
                    for sec, v in lines.items():
                        people[target][sec] = (people[target].get(sec) or []) + (v if isinstance(v, list) else [v])
                else:
                    people[target] = lines
    out["_locked"] = n
    return out


MALE = r"\b(he|him|his|himself|brother|bro|son|guy)\b"
FEMALE = r"\b(she|her|hers|herself|sister|sis|daughter|girl)\b"
SPORT_WORDS = {"basketball": r"\b(basketball|hoops?|court|dunk|layup|jumper|three[- ]pointer|free throws?|point guard)\b",
               "football": r"\b(football|touchdown|quarterback|qb|end zone|gridiron|huddle)\b",
               "baseball": r"\b(baseball|batting|pitcher|inning|home run|dugout|shortstop|bullpen)\b",
               "soccer": r"\b(soccer|striker|goalie|keeper|penalty kick|free kick|corner kick|hat trick|the pitch)\b",
               "softball": r"\b(softball|windmill|fastpitch)\b"}


def _story_words(sim, pack) -> str:
    """Everything a storyline says (its scenes' titles, text and lines), to tell who it's about."""
    out = []
    for sid, m in sim.cat.moments.items():
        if (m.get("scene") or {}).get("pack") == pack or m.get("scene_pack") == pack:
            out.append(json.dumps([m.get("title"), m.get("text"), (m.get("scene") or {}).get("by_text"),
                                   [(c.get("label"), c.get("ops")) for c in m.get("choices", [])]], ensure_ascii=False))
    return " ".join(out).lower()


def _fit(sim, cid, words) -> float:
    """How well someone fits what a storyline says: the right brother or sister, the one who plays the sport it's about."""
    w = sim.w
    c = w.chars[cid]
    he, she = len(re.findall(MALE, words)), len(re.findall(FEMALE, words))
    score = 0.0
    if he + she:
        score += 2.0 * (he - she) / (he + she) * (1 if c.gender == "m" else -1 if c.gender == "f" else 0)
    for sport, rx in SPORT_WORDS.items():
        n = len(re.findall(rx, words))
        if n:
            plays = any(w.groups.get(g, {}).get("skill") == sport for g in c.memberships) or (c.path or {}).get("sport") == sport
            score += min(3.0, n * 0.5) * ((1.0 if plays else 0.0) + c.interests.get(sport, 0) / 100)
    return score


def pick_cast(sim, me, pack, who, cands):
    """The person a storyline is about: the one you picked, else the one it keeps using, else the best fit (and keep them)."""
    from . import groundwork
    w = sim.w
    if not cands:
        return None
    mine = groundwork.my_pick(w, pack, who) if pack else None
    if mine in cands:
        return mine
    kept = cast_of(w, pack, who) if pack else None
    if kept in cands:
        return kept
    if len(cands) == 1 or not pack:
        return cands[0]
    words = _story_words(sim, pack)
    best = sorted(cands, key=lambda o: (-_fit(sim, o, words), o))[0]
    if not mine:  # (your pick stays your pick: someone else only for today)
        set_cast(w, pack, who, best)
    return best


def _context(sim, me, who, when, rng, pack=None, cast_refs=None) -> dict | None:
    """Who the scene is about and everything its text can say. None if nobody fits (or a cast member it needs isn't in
    your story)."""
    w = sim.w
    ctx = {"me_first": me.first}
    if who and who.startswith("cast:"):
        name = who[5:]
        them = bind(sim, me, name)
        if not them:
            return None  # nobody fits that slot in your story: these scenes don't happen
        if not (all(_in(_rel(w, me.id, them, f), r) for f, r in (when.get("you_feel") or {}).items())
                and all(_in(_rel(w, them, me.id, f), r) for f, r in (when.get("they_feel") or {}).items())):
            return None
        ctx["them"] = them
        ctx["them_first"] = w.chars[them].first
        ctx["cast_slot"] = name
        who = None
    if who:
        cands = candidates(sim, me, who)
        about = [_remembered_who(w, k) for k in when.get("remembered", [])]
        about = [a for a in about if a in cands]
        if about:  # a follow-up scene stays with the person the fact was about
            cands = about[:1]
        cands = [o for o in cands
                 if all(_in(_rel(w, me.id, o, f), r) for f, r in (when.get("you_feel") or {}).items())
                 and all(_in(_rel(w, o, me.id, f), r) for f, r in (when.get("they_feel") or {}).items())]
        if not cands:
            return None
        if who in ("best_friend", "crush", "rival", "partner"):
            them = cands[0]
        elif pack and who in CASTABLE:
            them = pick_cast(sim, me, pack, who, cands)  # the storyline's person: the same one every time
        else:
            them = cands[int(rng.random() * len(cands))]
        ctx["them"] = them
        ctx["them_first"] = w.chars[them].first
    best = candidates(sim, me, "best_friend")
    if best:
        ctx["best_friend"] = best[0]
        ctx["best_friend_first"] = w.chars[best[0]].first
    sibs = [s for s in sim.siblings(me.id) if s != ctx.get("them") and w.chars[s].status == "active"]
    if sibs:
        s = sibs[int(rng.random() * len(sibs))]
        ctx["sibling"] = s
        ctx["sibling_first"] = w.chars[s].first
    p = me.flags.get("partner")
    if p in w.chars:
        ctx["partner"] = p
        ctx["partner_first"] = w.chars[p].first
    sports = [g.get("skill") for g in (w.groups.get(x, {}) for x in me.memberships) if g.get("skill") in sim.cat.sports["sports"]]
    if not sports:
        sports = sorted((s for s in sim.cat.sports["sports"]), key=lambda s: -me.interests.get(s, 0))[:1]
    if sports:
        ctx["sport"] = sports[0]
    h = w.households.get(me.household_id) or {}
    pets = [p for p in w.meta.get("pets", {}).values() if p.get("household") == me.household_id and p.get("status") == "home"]
    if pets or h.get("pet"):
        ctx["pet"] = pets[0]["name"] if pets else h["pet"]["name"]
    for name in cast_refs or []:  # the storyline's other people in this scene: the same person every time
        cid = bind(sim, me, name)
        if not cid or cid == ctx.get("them") or cid == me.id:
            return None
        ctx[f"cast_{name}"] = cid
        ctx[f"cast_{name}_first"] = w.chars[cid].first
    ctx.update(_pro_names(sim, me))
    from . import gameplay
    ctx.update(gameplay.names(sim, me))  # your games: {last_game}, {my_line}, {team_record}...
    subj = next((r[6:] for r in (when or {}).get("requires") or [] if isinstance(r, str) and r.startswith("class:")), None)
    cls = my_class(sim, me, subj) if subj else None
    ctx["teacher"] = cls["teacher"] if cls else "your teacher"  # a scene set in one of your classes: its teacher and name
    ctx["class"] = cls["name"] if cls else "class"
    return ctx


_PRO_CACHE: dict = {}


def _pro_names(sim, me) -> dict:
    key = (id(sim.w), sim.w.day, me.id)
    if _PRO_CACHE.get("key") != key:
        _PRO_CACHE.update(key=key, val=_pro().names(sim, me))
    return _PRO_CACHE["val"]


def _playable(spec, ctx) -> bool:
    """Everyone the scene mentions exists, and its choices still make sense (at least two, or its only one)."""
    if any(not ctx.get(n) for n in spec["scene"].get("needs", [])):
        return False
    usable = [ch for ch in spec["choices"] if not any(not ctx.get(r) for r in ch.get("requires", []))]
    return len(usable) >= min(2, max(1, len(spec["choices"])))


def maybe_scene(sim):
    """Each morning in story mode: plan today's storyline scenes and present the first (scheduler.py decides what's ready
    and how many; the old one-scene-every-couple-of-days and five-days-between-chapters rules are the relaxed profile)."""
    from . import scheduler
    scheduler.plan_day(sim)
    return None


def fire(sim, sid, ctx):
    from . import moments as mo
    w = sim.w
    before = len(w.meta.get("moments", []))
    mo.trigger(sim, sid, w.meta["protagonist"], ctx)
    if len(w.meta.get("moments", [])) == before:
        return None
    w.meta.setdefault("scenes_seen", {}).setdefault(sid, []).append(w.day)
    return w.meta["moments"][-1]


def try_scene(sim, sid):
    """Play a scene right now, to see how it reads (ignores the date and chance, still needs someone who fits)."""
    w = sim.w
    spec = sim.cat.moments.get(sid)
    if not spec or not spec.get("scene"):
        raise KeyError(sid)
    me = w.chars.get(w.meta.get("protagonist") or "")
    if not me:
        raise ValueError("start a story first")
    when = spec["scene"].get("when") or {}
    who = spec["scene"].get("who")
    ctx = _context(sim, me, who, when, sim.streams.get("scene-try", w.day, sid), pack=spec["scene"].get("pack"),
                   cast_refs=spec["scene"].get("cast_refs"))
    if ctx is None:
        if isinstance(who, str) and who.startswith("cast:"):
            raise ValueError(f"nobody in your story fits '{who[5:]}' ({slot_label(slot_spec(who[5:]) or {})})")
        raise ValueError(f"nobody fits '{who}' in your story right now ({WHO.get(who, '')[:-1].lower()})")
    if not _playable(spec, ctx):
        words = {"them": "someone who fits", "best_friend": "a best friend", "partner": "a boyfriend or girlfriend", "pet": "a pet",
                 "sibling": "another brother or sister" if who in ("sibling", "older_sibling", "younger_sibling", "twin") else "a brother or sister"}
        missing = [words.get(n, n) for n in spec["scene"].get("needs", []) if not ctx.get(n)]
        raise ValueError(f"This scene needs {' and '.join(missing) or 'more people'} in your story.")
    m = fire(sim, sid, ctx)
    if m is None:
        raise ValueError("that scene couldn't start")
    return m


# ---------------------------------------------------------------------------------------- the guide and the prompt

EXAMPLE = {
    "dialogue_pack": 1,
    "name": "Cover for me",
    "author": "ChatGPT",
    "texts": {
        "sibling_chatter": [
            "did you take my charger again",
            {"text": "mom's asking where you are. i said practice", "talk": "\"Mom's asking where you are. I said practice,\" {them_first} whispers from the doorway."},
            {"text": "u up? i need a favor", "when": ["late_night"]},
        ],
        "hang_talk": ["ok but this is the best fries in town", {"text": "i'm so glad we did this", "when": ["close"]}],
    },
    "mods": {"open": {"sibling": ["ok don't be mad but"]}, "talk": {"sibling": ["{them_first} {says}, already halfway out the door"]}},
    "replies": {"sibling": [["absolutely not", "sibling_tease"]]},
    "scenes": [{
        "id": "cover_for_me",
        "who": "older_sibling",
        "when": {"years": ["freshman", "sophomore"], "requires": ["school_day"], "chance": 0.05},
        "title": "{them_first} needs a favor",
        "text": [
            "{them_first} leans into your doorway, already whispering. \"If anyone asks, I was at the library till eleven. Deal?\"",
            "{them_first} corners you in the kitchen. \"Library. Till eleven. You saw me there. Okay?\"",
            "{them_first} drops onto the end of your bed. \"I need an alibi and you're it. Library, eleven. Please.\"",
        ],
        "by_text": ["if mom asks i was at the library till 11. deal??", "ok i need you to cover for me tonight. library. 11. pls"],
        "choices": [
            {"label": "Deal. You owe me.", "fits": {"loyalty": 1},
             "ops": [["rel_back", "them", "affection", 6], ["remember", "covered_for_sibling"],
                     ["say", ["{them_first} points at you on the way out. \"Legend.\"", "\"You're the best. Seriously,\" {them_first} says."]]]},
            {"label": "No way. I'm not lying for you.", "fits": {"discipline": 1, "loyalty": -0.5},
             "ops": [["rel_back", "them", "affection", -4], ["say", ["\"Wow. Okay. Remember this.\"", "{them_first} just stares at you. \"Unbelievable.\""]]]},
            {"label": "Beat me in HORSE and I'll do it.", "fits": {"competitiveness": 1},
             "ops": [["minigame", "basketball",
                      {"great": [["rel_back", "them", "respect", 5], ["say", "You drain the last shot. {them_first} groans. \"Fine. I'll cover for myself.\""]],
                       "good": [["say", "It comes down to the last shot. You call it a tie and cover anyway."], ["rel_back", "them", "affection", 3]],
                       "miss": [["rel_back", "them", "affection", 4], ["say", "{them_first} wins easy. \"Library. Eleven. Thanks.\""]]},
                      {"base": 0.5, "athletic": 0.3}]]},
        ],
    }],
}

# ---------------------------------------------------------------------------------------- the guide and the prompts
# Everything is written as story scripts now (script.py): the guide and every ChatGPT prompt come from there.

def guide_markdown() -> str:
    from . import script
    return script.guide()


def prompt_for_ai(ask: str = "") -> str:
    from . import script
    return script.prompt_new(ask)


def _script_pack(pid: str):
    p = next((p for p in packs() if p["id"] == pid), None)
    if p is None:
        raise KeyError(pid)
    if p.get("kind") != "script":
        raise ValueError("that storyline is in the old JSON format: paste it again as a script")
    return p


def prompt_for_update(pid: str | None = None, ask: str = "") -> str:
    """Build out a storyline: the prompt with its whole script in it (or, with no storyline, the one for a new one)."""
    from . import script
    if not pid:
        return script.prompt_new(ask)
    p = _script_pack(pid)
    return script.prompt_continue(p["script"], p["pack"].get("name") or "Storyline", ask)


def prompt_for_texting(pid: str | None = None) -> str:
    """Texting lines for a storyline's people, as chat blocks."""
    from . import script
    if not pid:
        return script.prompt_new("Texting lines (chat blocks) for the people in my story.")
    p = _script_pack(pid)
    return script.prompt_texting(p["script"], p["pack"].get("name") or "Storyline")


def storyline_headers(skip=()) -> str:
    """Every storyline as its scene lines with their tags (what a season plan works from)."""
    out = []
    for p in packs():
        if not p["enabled"] or not p["pack"].get("scenes") or (p["pack"].get("name") or "").lower() in skip:
            continue
        out.append(f"=== {p['pack'].get('name')}" + ("" if in_order(p["id"]) else "  (any order)"))
        if p["pack"].get("expands"):
            out.append(f"expands: {p['pack']['expands']}")
        else:
            from . import script as SC
            out += [SC.cast_line(n, spec) for n, spec in (p["pack"].get("cast") or {}).items()]
        for sc in p["pack"]["scenes"]:
            src = (sc.get("src") or "").split("\n")[0] if isinstance(sc, dict) else ""
            out.append(src or f"--- {sc.get('title')}")
        out.append("")
    return "\n".join(out) or "(no storylines yet)"


def prompt_for_show(ask: str = "") -> str:
    """Make it one story: every storyline's scene lines, and the season plan you have now (sent back whole)."""
    from . import script
    plan = next((p for p in packs() if p.get("kind") == "script" and (p["pack"].get("name") or "").lower() == "season plan"), None)
    return script.prompt_plan(storyline_headers(skip=("season plan",)), ask, plan["script"] if plan else None)


def _all_ops(sc):
    out = []

    def walk(chs):
        for ch in chs or []:
            if isinstance(ch, dict):
                out.extend(ch.get("ops") or [])
                if isinstance(ch.get("then"), dict):
                    walk(ch["then"].get("choices"))
    walk(sc.get("choices"))
    return out


def current_dialogue() -> dict:
    """Everything in the game right now (base plus packs), for an AI to read before writing more."""
    m = merged()
    return {"texts": m["texts"], "replies": {k: [list(o) for o in v] for k, v in m["replies"].items()},
            "moments": {k: {"title": v["title"], "text": v["text"], "choices": [c.get("label") for c in v.get("choices", [])]}
                        for k, v in m["moments"].items()},
            "packs": m["loaded"]}


if __name__ == "__main__":  # python -m lifeos.dialogue check story.story   |   python -m lifeos.dialogue guide > guide.md
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "check":
        from . import script as _sc
        with open(sys.argv[2], encoding="utf-8") as f:
            txt = f.read()
        if _sc.looks_like_script(txt):
            r = _sc.compile_script(txt)
            for e in r["errors"]:
                print(f"ERROR   line {e['line']}: {e['text']}")
            print("OK" if not r["errors"] else "NOT OK", r["summary"])
            sys.exit(1 if r["errors"] else 0)
        r = check(parse_text(txt))
        for e in r["errors"]:
            print("ERROR  ", e)
        for wn in r["warnings"]:
            print("warning", wn)
        print("OK" if r["ok"] else "NOT OK", r["summary"])
        sys.exit(0 if r["ok"] else 1)
    elif len(sys.argv) >= 2 and sys.argv[1] == "guide":
        print(guide_markdown())
    else:
        print("usage: python -m lifeos.dialogue check <story.story> | guide")
