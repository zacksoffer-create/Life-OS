"""Story scripts: how LIFE OS content is written. Plain text, like a screenplay, that the game compiles.

    === Same Team
    cast: bro = older brother, plays basketball, 3 years older
    about: You and your brother on the same team for one season.

    --- The tryout list  [freshman · November · weekday]
    bro: You're actually trying out? Coach'll eat you alive.
    * "Watch me."              | confidence +, bro respect +
        bro: ...Alright. Don't embarrass me.
    * "Help me get ready?"     | bro affection ++, basketball +
        bro: Driveway. Six a.m. Don't be late.
        remember bro_trains_you
    * Shrug.                   | bro affection -

    --- Six a.m.  [next day · if bro_trains_you]
    bro: You're late. {Again.|Shocker.}
    * Run the drill            | play basketball
        great: You hit nine straight. | bro respect ++
        good: Not bad.               | bro respect +
        miss: You airball the last one.
    * "Five more minutes..."   | bro respect -

The pieces:
- === starts a storyline (its scenes play in order, each waiting for the one before; "order: any" lets them come in any
  order). Under it: cast (the people it's about, kept for the whole story), when (tags every scene gets), about (notes).
- --- starts a scene: a title, then [tags] for when it can happen (school year, month, weekday, a date, how likely,
  after another scene, a gap, if / unless a remembered fact, feelings, your stats, who it's with, how big it is).
- In a scene: plain lines are narration; "name: line" is someone talking (a cast name, you, best friend, sibling,
  partner, or a kind of person like friend or coach, who then is who the scene is about; a capitalized name like Mom or
  Coach Reyes is just a label). {a|b|c} is a line with versions. {bro} says someone's name.
- * starts a choice: what you say or do, then | and its effects. Lines under it play after you pick it. Choices under a
  choice keep the scene going (a beat, up to five deep). great/good/miss after "play <game>", yes/no after "50%", and
  good/meh/bad after "vibe tease" are the outcomes.
- Effects: "bro affection +" (how they feel about you; ++ and +++ are bigger, - goes down; "both" for both ways, "my bro
  affection +" for yours), "stress -", "mood +", "confidence +", "basketball +", "into guitar +", "rep tough +",
  "family affection +", "remember fact", "forget fact", "play game", "50% +charisma", "vibe tease", "focus social",
  "hang out with bro", 'text bro "line"', "fits loyalty" (who'd pick it when the game picks for you).
- Line blocks add to the game's pools: texts <pool>:, replies <set>: (each "line (tone)"), narration <key>:,
  mods <open|close|talk> <tag>:, chat <path>:, trivia <subject>: ("Question? = right | wrong | wrong | wrong (grade 10)"),
  choices <moment>: (more choices on one of the game's own moments).
- // starts a comment.

compile_script(text) -> {"packs": [pack dicts in the game's internal format], "errors": [{"line", "text"}], "warnings"}.
Errors say what's wrong in words, with the line number. The game's own checker (dialogue.check) runs on what comes out,
and anything it finds is mapped back to its line too.
"""
from __future__ import annotations

import difflib
import itertools
import re

MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                          "september", "october", "november", "december"])}
MON3 = {k[:3]: v for k, v in MONTHS.items()}
SEASONS = {"fall": [9, 10, 11], "autumn": [9, 10, 11], "winter": [12, 1, 2], "spring": [3, 4, 5], "summer": [6, 7, 8]}
WEEKDAY = {"monday": "mon", "tuesday": "tue", "wednesday": "wed", "thursday": "thu", "friday": "fri", "saturday": "sat",
           "sunday": "sun"}
HOLIDAYS = {"halloween": "10-31", "christmas": "12-25", "christmas eve": "12-24", "new year's eve": "12-31",
            "new years eve": "12-31", "new year's day": "01-01", "valentine's day": "02-14", "valentines day": "02-14",
            "st. patrick's day": "03-17", "st patrick's day": "03-17", "july 4th": "07-04", "fourth of july": "07-04",
            "groundhog day": "02-02", "april fools": "04-01", "april fools' day": "04-01", "april fool's day": "04-01",
            "veterans day": "11-11", "cinco de mayo": "05-05", "christmas day": "12-25", "new years day": "01-01",
            "new year's": "01-01", "new years": "01-01"}
# days that move from year to year, and the school calendar's own days (worked out by the game: calendar.named_days)
NAMED = {"thanksgiving": "thanksgiving", "thanksgiving day": "thanksgiving", "black friday": "black_friday",
         "easter": "easter", "easter sunday": "easter", "mother's day": "mothers_day", "mothers day": "mothers_day",
         "father's day": "fathers_day", "fathers day": "fathers_day", "memorial day": "memorial_day", "labor day": "labor_day",
         "mlk day": "mlk_day", "martin luther king day": "mlk_day", "martin luther king jr. day": "mlk_day",
         "presidents day": "presidents_day", "presidents' day": "presidents_day", "president's day": "presidents_day",
         "columbus day": "columbus_day", "super bowl": "super_bowl", "super bowl sunday": "super_bowl",
         "first day of school": "first_day_of_school", "the first day of school": "first_day_of_school",
         "last day of school": "last_day_of_school", "the last day of school": "last_day_of_school",
         "homecoming": "homecoming", "homecoming dance": "homecoming", "homecoming night": "homecoming", "homecoming week": "homecoming_week",
         "snow ball": "snow_ball", "winter formal": "snow_ball", "prom": "prom", "prom night": "prom", "prom week": "prom_week",
         "graduation": "graduation", "graduation day": "graduation", "midterms": "midterms", "midterm": "midterms",
         "midterms week": "midterms_week", "midterm week": "midterms_week", "finals": "finals", "final exams": "finals",
         "finals week": "finals_week", "report cards": "report_cards", "report card day": "report_cards",
         "thanksgiving break": "thanksgiving_break", "winter break": "winter_break", "christmas break": "winter_break",
         "holiday break": "winter_break", "spring break": "spring_break"}
# people who can talk in a scene without being someone the game keeps track of (they're just a label)
WALKONS = {"mom", "dad", "grandma", "grandpa", "aunt", "uncle", "teacher", "the teacher", "principal", "the principal", "nurse",
           "the nurse", "doctor", "the doctor", "waiter", "waitress", "the waiter", "cashier", "the cashier", "officer",
           "the officer", "cop", "a cop", "neighbor", "the neighbor", "bus driver", "the bus driver", "announcer", "the announcer",
           "ref", "the ref", "umpire", "the ump", "librarian", "guidance counselor", "counselor", "everyone", "the crowd",
           "the team", "someone", "a voice", "stranger", "a stranger", "the dj", "dj", "barista", "the barista", "boss",
           "the boss", "manager", "the manager", "mr. and mrs.", "mom and dad", "your mom", "your dad", "the class"}
CHANCES = {"rare": 0.02, "uncommon": 0.04, "sometimes": 0.08, "often": 0.15, "likely": 0.3, "always": 1.0}
YEAR_WORDS = ("freshman", "sophomore", "junior", "senior")
IMPORTANCE = {"big": "major", "major": "major", "finale": "finale", "small": "ambient", "minor": "ambient", "ambient": "ambient",
              "regular": "regular"}
CLASS_ALIASES = {"bio": "biology", "chem": "chemistry", "history": "world_history", "us history": "us_history",
                 "gym": "health", "pe": "health", "p.e.": "health", "health": "health", "spanish": "spanish", "english": "english",
                 "math": "math", "physics": "physics", "chemistry": "chemistry", "biology": "biology"}
NUMWORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "ten": 10}
REL_ALIASES = {"affection": "affection", "likes": "affection", "like": "affection", "trust": "trust", "respect": "respect",
               "attraction": "attraction", "into": "attraction", "rivalry": "rivalry", "familiarity": "familiarity",
               "knows": "familiarity", "perceived": "perceived"}
TRAIT_ALIASES = {"confident": "confidence", "disciplined": "discipline", "loyal": "loyalty", "ambitious": "ambition",
                 "impulsive": "impulsivity", "empathetic": "empathy", "competitive": "competitiveness", "curious": "curiosity",
                 "volatile": "volatility", "outgoing": "sociability"}
PEOPLE = {"best friend": "best_friend", "best_friend": "best_friend", "bff": "best_friend", "sibling": "sibling",
          "partner": "partner", "boyfriend": "partner", "girlfriend": "partner", "them": "them", "they": "them"}
KIND_ALIASES = {"big brother": "older_brother", "big sister": "older_sister", "little brother": "younger_brother",
                "little sister": "younger_sister", "older brother": "older_brother", "older sister": "older_sister",
                "younger brother": "younger_brother", "younger sister": "younger_sister", "older sibling": "older_sibling",
                "younger sibling": "younger_sibling", "best friend": "best_friend"}
OUTCOMES = {"great": "game", "good": "game", "miss": "game", "yes": "chance", "no": "chance", "meh": "vibe", "bad": "vibe"}
STEP = {"rel": (3, 6, 10), "need": (5, 10, 18), "mood": (3, 6, 10), "trait": (1, 2, 4), "skill": (1, 2, 3), "interest": (3, 6, 12),
        "rep": (2, 4, 8), "family": (3, 6, 10)}
GAME_STAT = {"trivia": "academic", "mathdash": "academic", "flash": "academic", "oddone": "academic", "lineup": "academic",
             "hold": "athletic", "sweep": "athletic", "reflex": "athletic"}
BLOCKS = ("texts", "replies", "narration", "mods", "chat", "trivia", "choices", "flirt", "group chat")

SECTION_RE = re.compile(r"^===\s*(.+?)\s*$")
SCENE_RE = re.compile(r"^---\s*(.+?)\s*$")
BLOCK_RE = re.compile(r"^(texts|replies|narration|mods|chat|trivia|choices|flirt|group\s+chat)\s+(.+?)\s*:\s*$|^(schedule|outline)\s*:\s*$", re.I)
ATTR_RE = re.compile(r"^(cast|when|years|order|about|notes?|expands)\s*:\s*(.*)$", re.I)
SPEAKER_RE = re.compile(r"^([A-Za-z][\w .'-]{0,24}?):\s+(.+)$")
OUTCOME_RE = re.compile(r"^(great|good|miss|yes|no|meh|bad)\s*:\s*(.*)$", re.I)
TEXTS_RE = re.compile(r"^(.+?)\s+texts(?: you)?\s*:\s*(.+)$", re.I)
MEMORY_RE = re.compile(r"^memory\s*:\s*(.+?)(?:\s*\((good|great|bad|awful|happy|sad)\))?\s*$", re.I)
CMD_RE = re.compile(r"^(remember|forget)\s+([a-z][a-z0-9_]{2,79})\s*$")
VARIANT_RE = re.compile(r"\{([^{}]*\|[^{}]*)\}")
NAME_RE = re.compile(r"\{([^{}|]+)\}")


def slug(s: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")
    if s and not s[0].isalpha():
        s = "s_" + s
    return (s or "x")[:n].strip("_")


class Fail(Exception):
    pass


def _suggest(word, options) -> str:
    near = difflib.get_close_matches(str(word).lower(), [str(o) for o in options], n=3, cutoff=0.6)
    return f" Did you mean {', '.join(near)}?" if near else ""


def _split(s: str, sep: str) -> list:
    """Split on sep outside {braces} and "quotes"."""
    out, cur, depth, q = [], "", 0, False
    for ch in s:
        if ch == '"':
            q = not q
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0 and not q:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [x.strip() for x in out]


def _vocab():
    """The game's own words (skills, traits, games...), read once."""
    if not hasattr(_vocab, "v"):
        from . import dialogue as D
        from .catalogs import APTITUDES, TRAITS
        from .minigames import reg
        _vocab.v = {"traits": set(TRAITS), "apt": set(APTITUDES), "skills": D._skill_ids() | {"sport"},
                    "interests": D._interest_ids() | {"sport"}, "needs": set(D.NEEDS), "focus": set(D.FOCUS_MODES),
                    "rep": set(D.REP_TAGS), "games": set(reg()["games"]) | {"sport"}, "vibes": set(D.VIBE_STYLES),
                    "who": set(D.WHO), "castable": set(D.CASTABLE), "requires": dict(D.REQUIRES), "years": set(D.YEARS),
                    "names": set(D.SCENE_NAMES), "tones": set(D.REPLY_TONES), "sports": set(D._base("sports.json")["sports"])}
    return _vocab.v


# ---------------------------------------------------------------------------------------------------- lines
class Line:
    __slots__ = ("n", "indent", "text")

    def __init__(self, n, indent, text):
        self.n, self.indent, self.text = n, indent, text


class Node:
    def __init__(self, line: Line):
        self.line, self.children = line, []

    @property
    def text(self):
        return self.line.text


def _lines(text: str) -> list:
    out = []
    for i, raw in enumerate(text.replace("\r\n", "\n").replace("\t", "    ").split("\n"), start=1):
        s = raw.rstrip()
        stripped = s.lstrip()
        if not stripped or stripped.startswith("//"):
            continue
        out.append(Line(i, len(s) - len(stripped), stripped))
    return out


def _tree(lines: list) -> list:
    """Indentation into a tree: a line's children are the lines under it, indented further."""
    roots, stack = [], []
    for ln in lines:
        node = Node(ln)
        while stack and stack[-1].line.indent >= ln.indent:
            stack.pop()
        (stack[-1].children if stack else roots).append(node)
        stack.append(node)
    return roots


# ---------------------------------------------------------------------------------------------------- text
def variants(s: str, cap: int = 6) -> list:
    """'Hey {there|you}.' -> ['Hey there.', 'Hey you.']"""
    parts = VARIANT_RE.split(s)
    if len(parts) == 1:
        return [s]
    pools = [[p] if i % 2 == 0 else [x.strip() for x in p.split("|")] for i, p in enumerate(parts)]
    n = max(len(p) for p in pools)
    return list(dict.fromkeys("".join(p[k % len(p)] for p in pools).replace("  ", " ").strip() for k in range(min(n, cap))))


class Scene:
    """What a scene knows while it compiles: who it's about and who it can name."""

    def __init__(self, sec, who_slot=None, who_kind=None):
        self.sec = sec
        self.who_slot = who_slot  # a cast name
        self.who_kind = who_kind  # a kind of person (friend, coach...)
        self.cast_refs = set()

    @property
    def who(self):
        return f"cast:{self.who_slot}" if self.who_slot else self.who_kind

    def person(self, name: str, n: int) -> str:
        """A person as effects name them -> the game's reference."""
        k = name.strip().lower()
        k = re.sub(r"^the\s+", "", k)
        if self.who_kind and KIND_ALIASES.get(k, k.replace(" ", "_")) == self.who_kind:
            return "them"  # (the scene's person, even when it's your best friend or sibling)
        if k in self.sec.cast:
            if k == self.who_slot:
                return "them"
            self.cast_refs.add(k)
            return f"cast_{k}"
        if k in PEOPLE:
            return PEOPLE[k]
        if k in WALKONS or name.strip()[:1].isupper() and " " not in k and k not in _vocab()["who"] and k not in KIND_ALIASES:
            raise Fail(f"'{name}' can talk in a scene, but the game doesn't keep track of how they feel about you. Use your own "
                       "feelings instead (mood +, stress -), family affection + (you and your siblings), or someone the scene "
                       "is about")
        kind = KIND_ALIASES.get(k, k.replace(" ", "_"))
        if kind in _vocab()["who"]:
            if kind == self.who_kind:
                return "them"
            raise Fail(f"'{name}' isn't who this scene is about ({self.who_kind or 'nobody yet'}); a scene can affect its "
                       f"person, your best friend, sibling, partner and this storyline's cast")
        opts = list(self.sec.cast) + list(PEOPLE) + ([self.who_kind] if self.who_kind else [])
        raise Fail(f"'{name}' isn't someone this scene knows.{_suggest(k, opts)} Use: {', '.join(sorted(set(opts)))}")

    def names(self, s: str, n: int) -> str:
        """{bro} -> the right placeholder for the game; {school}, {sport}... pass through."""
        V = _vocab()

        def one(m):
            k = m.group(1).strip()
            low = k.lower()
            if low in ("me", "you", "me_first"):
                return "{me_first}"
            if low in self.sec.cast:
                if low == self.who_slot:
                    return "{them_first}"
                self.cast_refs.add(low)
                return "{cast_" + low + "_first}"
            if low in ("them", "them_first") or (self.who_kind and KIND_ALIASES.get(low, low.replace(" ", "_")) == self.who_kind):
                return "{them_first}"
            p = PEOPLE.get(low)
            if p in ("best_friend", "sibling", "partner"):
                return "{" + p + "_first}"
            kind = KIND_ALIASES.get(low, low.replace(" ", "_"))
            if kind == self.who_kind:
                return "{them_first}"
            if k in V["names"] or k.startswith("cast_"):
                return "{" + k + "}"
            raise Fail(f"{{{k}}} isn't a name the game can fill in here.{_suggest(low, list(self.sec.cast) + sorted(V['names']))}")
        return NAME_RE.sub(one, s)

    def speaker(self, who: str) -> str | None:
        """A speaker's label: {them_first}, You, Mom... None if it isn't a speaker at all."""
        low = who.strip().lower()
        if low in ("you", "me"):
            return "You"
        if low in self.sec.cast:
            if self.who_slot is None and self.who_kind is None:
                self.who_slot = low
            if low == self.who_slot:
                return "{them_first}"
            self.cast_refs.add(low)
            return "{cast_" + low + "_first}"
        kind = KIND_ALIASES.get(low, low.replace(" ", "_"))
        if self.who_kind and kind == self.who_kind:
            return "{them_first}"
        p = PEOPLE.get(low)
        if p in ("best_friend", "sibling", "partner"):
            return "{" + p + "_first}"
        if p == "them":
            return "{them_first}"
        if kind in _vocab()["who"]:
            if self.who_slot is None and self.who_kind is None:
                self.who_kind = kind
            if kind == self.who_kind:
                return "{them_first}"
            raise Fail(f"'{who}' talks, but this scene is about {self.who_kind or self.who_slot}: a scene is about one person "
                       "(plus your best friend, sibling, partner and the storyline's cast)")
        if who[:1].isupper():
            return who.strip()  # Mom, Coach Reyes: just a label
        if low in WALKONS:
            return who.strip()[:1].upper() + who.strip()[1:]  # mom: -> Mom:
        if re.fullmatch(r"[a-z][a-z0-9_]{1,30}", low):
            raise Fail(f"'{who.strip()}' talks, but nobody here is called that.{_suggest(low, list(self.sec.cast) + list(PEOPLE))} "
                       f"Add them to the cast (cast: {low} = <who they are, or their name>), or write a walk-on with a capital "
                       f"({who.strip().title()}:)")
        return None

    def line(self, s: str, n: int) -> list:
        """A line of narration or dialogue -> its versions, ready for the game."""
        m = SPEAKER_RE.match(s)
        if m:
            lab = self.speaker(m.group(1))
            if lab is not None:
                body = m.group(2).strip()
                return [self.names(f"{lab}: {v}", n) for v in variants(body)]
        return [self.names(v, n) for v in variants(s)]


# ---------------------------------------------------------------------------------------------------- effects
def _amount(tok: str, kind: str) -> int:
    if re.fullmatch(r"[+-]{1,3}", tok):
        step = STEP[kind][len(tok) - 1]
        return step if tok[0] == "+" else -step
    if re.fullmatch(r"[+-]\d+", tok):
        return int(tok)
    raise Fail(f"'{tok}' isn't an amount: use +, ++, +++, -, --, --- or a number like +5")


def effects(text: str, sc: Scene, n: int, out: dict) -> list:
    """'bro affection ++, stress -, remember x' -> the game's ops. Branching effects (play, %, vibe) and fits go in out."""
    V = _vocab()
    ops = []
    for item in _split(text, ","):
        if not item:
            continue
        low = item.lower().strip()
        m = re.fullmatch(r"(remember|forget)\s+(\S+)", low)
        if m:
            if not re.fullmatch(r"[a-z][a-z0-9_]{2,79}", m.group(2)):
                raise Fail(f"'{m.group(2)}' should be a short lowercase fact name with underscores, like bro_trains_you")
            ops.append([m.group(1), m.group(2)])
            continue
        m = re.fullmatch(r"play\s+(\S+)", low)
        if m:
            g = m.group(1)
            if g not in V["games"]:
                raise Fail(f"'{g}' isn't a mini game.{_suggest(g, V['games'])} Games: {', '.join(sorted(V['games']))}")
            out["branch"] = ("game", g)
            continue
        m = re.fullmatch(r"vibe\s+(\w+)", low)
        if m:
            if m.group(1) not in V["vibes"]:
                raise Fail(f"'{m.group(1)}' isn't a style. Use: {', '.join(V['vibes'])}")
            out["branch"] = ("vibe", m.group(1))
            continue
        m = re.fullmatch(r"(?:chance\s+)?(\d{1,3})\s*%\s*(.*)", low)
        if m:
            spec = {"base": max(0.01, min(1.0, int(m.group(1)) / 100))}
            for tok in re.findall(r"([+-])\s*([a-z_]+)", m.group(2)):
                stat = TRAIT_ALIASES.get(tok[1], tok[1])
                if stat not in V["traits"] | V["apt"] | V["skills"]:
                    raise Fail(f"'{tok[1]}' isn't a trait, talent or skill to roll against.{_suggest(stat, V['traits'] | V['apt'])} "
                               f"Traits: {', '.join(sorted(V['traits']))}. Talents: {', '.join(sorted(V['apt']))}. Or a skill "
                               f"(like {', '.join(sorted(V['skills'])[:6])}).")
                spec[stat] = 0.3 if tok[0] == "+" else -0.3
            out["branch"] = ("chance", spec)
            continue
        m = re.fullmatch(r"fits\s+(.+)", low)
        if m:
            for tok in _split(m.group(1), " "):
                neg = tok.startswith("-")
                t = TRAIT_ALIASES.get(tok.lstrip("+-"), tok.lstrip("+-"))
                if t not in V["traits"]:
                    raise Fail(f"'{tok}' isn't a trait.{_suggest(t, V['traits'])} Traits: {', '.join(sorted(V['traits']))}")
                out.setdefault("fits", {})[t] = -1 if neg else 1
            continue
        m = re.fullmatch(r"focus\s+(\w+)", low)
        if m:
            if m.group(1) not in V["focus"]:
                raise Fail(f"focus is one of {', '.join(V['focus'])}")
            ops.append(["focus", m.group(1)])
            continue
        m = re.fullmatch(r"(?:hang out|plans)\s+with\s+(.+)", low)
        if m:
            ops.append(["hang_out", sc.person(m.group(1), n)])
            continue
        m = re.fullmatch(r'text\s+(.+?)\s+"(.+)"', item.strip(), re.I)
        if m:
            ops.append(["text", sc.person(m.group(1), n), [sc.names(v, n) for v in variants(m.group(2))]])
            continue
        m = re.fullmatch(r"(.+?)\s+([+-]{1,3}|[+-]\d+)(\s+both)?", low)
        if not m:
            raise Fail(f"'{item.strip()}' isn't an effect I know. Effects look like: bro affection +, stress -, confidence +, "
                       "remember a_fact, play basketball, 50% +charisma")
        head, tok, both = m.group(1).strip(), m.group(2), bool(m.group(3))
        if head == "mood":
            ops.append(["mood", _amount(tok, "mood")])
        elif head in V["needs"]:
            ops.append(["need", head, _amount(tok, "need")])
        elif head.startswith("rep ") or head.endswith(" rep"):
            tag = head.replace("rep", "").strip()
            if tag not in V["rep"]:
                raise Fail(f"'{tag}' isn't a reputation.{_suggest(tag, V['rep'])} Reputations: {', '.join(V['rep'])}")
            ops.append(["rep", tag, _amount(tok, "rep")])
        elif head.startswith("family "):
            f = REL_ALIASES.get(head[7:].strip())
            if not f:
                raise Fail(f"'{head[7:]}' isn't part of a relationship.{_suggest(head[7:], ['affection', 'trust', 'respect', 'rivalry'])} Use: affection, trust, respect, rivalry")
            ops.append(["family", f, _amount(tok, "family")])
        elif head.startswith("into "):
            k = head[5:].strip().replace(" ", "_")
            if k not in V["interests"]:
                raise Fail(f"'{k}' isn't something people get into here.{_suggest(k, V['interests'])}")
            ops.append(["interest", k, _amount(tok, "interest")])
        elif TRAIT_ALIASES.get(head, head) in V["traits"]:
            t = TRAIT_ALIASES.get(head, head)
            amt = _amount(tok, "trait")
            ops.append(["trait", t, amt])
            out.setdefault("fits", {}).setdefault(t, 1 if amt > 0 else -1)
        elif head.replace(" ", "_") in V["skills"]:
            ops.append(["skill", head.replace(" ", "_"), _amount(tok, "skill")])
        elif head.replace(" ", "_") in V["interests"]:
            ops.append(["interest", head.replace(" ", "_"), _amount(tok, "interest")])
        else:
            words = head.split()
            mine = words[0] == "my"
            if mine:
                words = words[1:]
            if len(words) < 2 or words[-1] not in REL_ALIASES:
                opts = sorted(V["needs"] | V["traits"] | V["skills"] | {"mood"})
                raise Fail(f"'{item.strip()}' isn't an effect I know.{_suggest(head, opts)} For a person it's "
                           "'<person> affection +' (or trust, respect, attraction, rivalry)")
            ref = sc.person(" ".join(words[:-1]), n)
            f = REL_ALIASES[words[-1]]
            amt = _amount(tok, "rel")
            if both:
                ops += [["rel_back", ref, f, amt], ["rel", ref, f, amt]]
            else:
                ops.append(["rel" if mine else "rel_back", ref, f, amt])
    return ops


# ---------------------------------------------------------------------------------------------------- tags (when)
def _subjects() -> dict:
    from . import dialogue as D
    return D.class_subjects()


def _date(s: str, approx: bool = False):
    """A day: "Oct 31", a holiday, or a named day that moves (thanksgiving, prom...). approx=True gives a named day's usual
    month-day instead (for windows: after Thanksgiving)."""
    from . import calendar as calm
    low = s.lower().strip().rstrip(".")
    if low in HOLIDAYS:
        return HOLIDAYS[low]
    if low in NAMED:
        return calm.APPROX_MD[NAMED[low]] if approx else NAMED[low]
    m = re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?", low)
    if m:
        mo = MONTHS.get(m.group(1)) or MON3.get(m.group(1)[:3])
        if mo and 1 <= int(m.group(2)) <= 31:
            return f"{mo:02d}-{int(m.group(2)):02d}"
    return None


def _years(tok: str):
    low = tok.lower().replace("–", "-").replace("—", "-")
    low = re.sub(r"\s+year$", "", low)
    pre = ""
    if low.startswith("college "):
        pre, low = "college_", low[8:]
    m = re.fullmatch(r"(freshman|sophomore|junior|senior)(?:\s*(?:-|to)\s*(?:college\s+)?(freshman|sophomore|junior|senior))?", low)
    if not m:
        return None
    a = YEAR_WORDS.index(m.group(1))
    b = YEAR_WORDS.index(m.group(2)) if m.group(2) else a
    return [pre + YEAR_WORDS[i] for i in range(a, b + 1)]


def tags(text: str, sc: Scene | None, n: int, when: dict, sec) -> dict:
    """'freshman · November · weekday · after The tryout list' -> the game's conditions (into when)."""
    V = _vocab()
    for tok in [t for t in re.split(r"\s*[·;,]\s*", text) if t.strip()]:
        low = tok.lower().strip()
        ys = _years(low)
        if ys:
            when["years"] = list(dict.fromkeys(when.get("years", []) + ys))
            continue
        if low in ("high school", "college"):
            when.setdefault("years", []).append(low.replace(" ", "_"))
            continue
        if low in MONTHS or low in MON3:
            when.setdefault("months", []).append(MONTHS.get(low) or MON3[low])
            continue
        if low in SEASONS:
            when["months"] = sorted(set(when.get("months", [])) | set(SEASONS[low]))
            continue
        if low in WEEKDAY or low in WEEKDAY.values():
            when.setdefault("weekdays", []).append(WEEKDAY.get(low, low))
            continue
        if low in ("weekday", "weekdays"):
            when["weekdays"] = ["mon", "tue", "wed", "thu", "fri"]
            continue
        if low in ("weekend", "school day", "summer break"):
            when.setdefault("requires", []).append({"weekend": "weekend", "school day": "school_day", "summer break": "summer"}[low])
            continue
        m = re.fullmatch(r"(?:in|during)\s+(.+?)(?:\s+class)?", low)
        if m and (m.group(1) in CLASS_ALIASES or m.group(1).replace(" ", "_") in _subjects()):
            subj = CLASS_ALIASES.get(m.group(1), m.group(1).replace(" ", "_"))
            when.setdefault("requires", []).append(f"class:{subj}")  # a school day you have that class; {teacher} and {class}
            continue
        if low in ("in class", "during class"):
            when.setdefault("requires", []).append("school_day")
            continue
        if low in ("spread", "spread out", "spread it out", "spread over the year", "spread across the year"):
            when["spread"] = True  # (the storyline's scenes, in order, across its school years)
            continue
        if low in CHANCES:
            when["chance"] = CHANCES[low]
            continue
        m = re.fullmatch(r"(\d{1,3})\s*%", low)
        if m:
            when["chance"] = max(0.001, min(1.0, int(m.group(1)) / 100))
            continue
        if low == "once":
            when["once"] = True
            continue
        m = re.fullmatch(r"(?:repeats\s*)?(?:every\s+(\d+)\s+days?)?", low)
        if low.startswith(("repeats", "every ")) and m:
            when["once"] = False
            when["cooldown_days"] = int(m.group(1) or 30)
            continue
        if low in IMPORTANCE:
            when["importance"] = IMPORTANCE[low]
            continue
        if low in ("same day", "next day"):
            when["gap_days"] = 0 if low == "same day" else 1
            continue
        m = re.fullmatch(r"(\d+|a|an|one|two|three|four|five|six|ten)\s+(day|week|month)s?\s+later", low)
        if m:
            k = NUMWORDS.get(m.group(1)) or int(m.group(1))
            when["gap_days"] = k * {"day": 1, "week": 7, "month": 30}[m.group(2)]
            continue
        d = _date(low)
        if d:
            when.setdefault("dates", []).append(d)
            continue
        m = re.fullmatch(r"(after|before)\s+(.+)", tok.strip(), re.I)
        if m:
            d = _date(m.group(2), approx=True)
            if d:
                when["not_before" if m.group(1).lower() == "after" else "not_after"] = d
            elif m.group(1).lower() == "after":
                sec.pending_after.append((when, m.group(2).strip(), n))
            else:
                raise Fail(f"'before {m.group(2)}' needs a date, like before Nov 15")
            continue
        m = re.fullmatch(r"with\s+(.+)", low)
        if m:
            k = m.group(1).strip()
            if sc is None:
                raise Fail("'with' goes on a scene, not the whole storyline")
            if k in sec.cast:
                sc.who_slot = k
            else:
                kind = KIND_ALIASES.get(k, k.replace(" ", "_"))
                if kind not in V["who"]:
                    raise Fail(f"'{k}' isn't a kind of person.{_suggest(kind, V['who'])} Use: {', '.join(sorted(V['who']))}, or a cast name")
                sc.who_kind = kind
            continue
        m = re.fullmatch(r"(if|unless)\s+(not\s+)?(.+)", low)
        if m:
            neg = m.group(1) == "unless" or bool(m.group(2))
            cond = m.group(3).strip()
            req = cond.replace(" ", "_")
            if req in V["requires"] or cond.startswith("pro:"):
                if neg:
                    raise Fail(f"'{tok}': use the opposite instead (like single for not dating)")
                when.setdefault("requires", []).append(cond if cond.startswith("pro:") else req)
                continue
            mm = re.fullmatch(r"(stress|energy|social|fun|mood|gpa)\s+(-?\d+(?:\.\d+)?)\s*([+-])", cond)
            if mm:
                v = float(mm.group(2))
                lo, hi = (-100 if mm.group(1) == "mood" else 0), (4 if mm.group(1) == "gpa" else 100)
                when.setdefault("me", {})[mm.group(1)] = [v, hi] if mm.group(3) == "+" else [lo, v]
                continue
            mm = re.fullmatch(r"(my\s+)?(.+?)\s+(affection|trust|respect|attraction|rivalry|familiarity|likes)\s+(-?\d+)\s*([+-])", cond)
            if mm:
                if sc is None:
                    raise Fail("a feeling goes on a scene, not the whole storyline")
                ref = sc.person(mm.group(2), n) if mm.group(2) not in ("you", "they", "them") else "them"
                if ref != "them":
                    raise Fail(f"'{tok}': a feeling can only be checked for the person the scene is about")
                v = int(mm.group(4))
                key = "you_feel" if mm.group(1) or mm.group(2) == "you" else "they_feel"
                when.setdefault(key, {})[REL_ALIASES[mm.group(3)]] = [v, 100] if mm.group(5) == "+" else [-100, v]
                continue
            if not re.fullmatch(r"[a-z][a-z0-9_]{2,79}", cond):
                opts = list(V["requires"]) + ["a_fact_you_remembered"]
                raise Fail(f"'{tok}': if takes a fact you remembered (like if bro_trains_you), or one of: "
                           f"{', '.join(r.replace('_', ' ') for r in V['requires'])}.{_suggest(req, opts)}")
            when.setdefault("not_remembered" if neg else "remembered", []).append(cond)
            continue
        everything = (list(MONTHS) + list(SEASONS) + list(WEEKDAY) + list(CHANCES) + list(IMPORTANCE) + list(NAMED) + list(HOLIDAYS) +
                      ["weekend", "weekday", "school day", "once", "repeats", "same day", "next day"] + list(YEAR_WORDS))
        raise Fail(f"'{tok.strip()}' isn't a tag I know.{_suggest(low, everything)} Tags are things like freshman, November, "
                   "weekend, Oct 31, 10%, after <scene>, next day, if <fact>, with <person>, big")
    return when


# ---------------------------------------------------------------------------------------------------- cast
def cast_spec(desc: str) -> dict:
    """'older brother, plays basketball, 3 years older, close' -> a cast slot."""
    V = _vocab()
    parts = _split(desc, ",")
    head = parts[0].lower().strip()
    head = re.sub(r"^(an?|the|your)\s+", "", head)
    orig = parts[0].strip()
    if (re.fullmatch(r"[A-Z][A-Za-z'.\-]*(?:\s+[A-Z][A-Za-z'.\-]*){0,3}", orig) and head not in KIND_ALIASES
            and head.replace(" ", "_") not in V["castable"] and head not in ("best friend", "friend")):
        spec = {"who": "named", "name": orig}  # someone in your world, by name: "Ally Soffer" (or "Ally")
        label = []
        for p in parts[1:]:
            low = p.lower().strip()
            if low in ("from the start", "from day one"):
                spec["bind"] = "start"
            elif low in ("close", "tight"):
                spec["bond"] = {"affection": 65, "trust": 60}
            else:
                label.append(p.strip())
        if label:
            spec["label"] = ", ".join(label)
        return spec
    of = re.fullmatch(r"(best friend|friend|teammate|boyfriend|girlfriend|partner)\s+of\s+([a-z][a-z0-9_]*)", head)
    if of:  # someone in another cast member's life: "friend of sis"
        k2 = {"best friend": "best_friend", "boyfriend": "partner", "girlfriend": "partner"}.get(of.group(1), of.group(1))
        spec = {"who": k2, "of": of.group(2)}
        if of.group(1) == "boyfriend":
            spec["gender"] = "m"
        elif of.group(1) == "girlfriend":
            spec["gender"] = "f"
        parts = parts[1:]
        label = []
        for p in parts:
            low = p.lower().strip()
            if low in ("girl", "female", "a girl"):
                spec["gender"] = "f"
            elif low in ("guy", "boy", "male", "a guy"):
                spec["gender"] = "m"
            elif low in ("from the start", "from day one"):
                spec["bind"] = "start"
            elif re.fullmatch(r"(?:plays\s+)?(\w+)(?:\s+player)?", low) and re.fullmatch(r"(?:plays\s+)?(\w+)(?:\s+player)?", low).group(1) in V["sports"]:
                spec["sport"] = re.fullmatch(r"(?:plays\s+)?(\w+)(?:\s+player)?", low).group(1)
            else:
                label.append(p.strip())
        if label:
            spec["label"] = ", ".join(label)
        return spec
    kind = KIND_ALIASES.get(head, head.replace(" ", "_"))
    if kind not in V["castable"]:
        raise Fail(f"'{parts[0]}' isn't a kind of person a storyline can keep.{_suggest(kind, V['castable'])} "
                   f"Use: {', '.join(k.replace('_', ' ') for k in sorted(V['castable']))}, or someone in your story by name "
                   "(cast: ally = Ally Soffer)")
    spec = {"who": kind}
    label = []
    for p in parts[1:]:
        low = p.lower().strip()
        m = re.fullmatch(r"(?:plays\s+)?(\w+)(?:\s+player)?", low)
        if m and m.group(1) in V["sports"]:
            spec["sport"] = m.group(1)
            continue
        m = re.fullmatch(r"(\d+|a|an|one|two|three|four)\s+(?:years?|grades?)\s+(older|younger|ahead|behind)", low)
        if m:
            k = NUMWORDS.get(m.group(1)) or int(m.group(1))
            spec["grade_offset"] = k if m.group(2) in ("older", "ahead") else -k
            continue
        if low in ("a senior", "a junior", "a sophomore"):
            spec["grade_offset"] = {"a senior": 3, "a junior": 2, "a sophomore": 1}[low]
            continue
        if low in ("girl", "female", "a girl"):
            spec["gender"] = "f"
            continue
        if low in ("guy", "boy", "male", "a guy"):
            spec["gender"] = "m"
            continue
        if low in ("close", "tight"):
            spec["bond"] = {"affection": 65, "trust": 60}
            continue
        if low in ("from the start", "from day one"):
            spec["bind"] = "start"
            continue
        label.append(p.strip())
    if label:
        spec["label"] = ", ".join(label)
    return spec


def cast_line(name: str, spec: dict) -> str:
    """A cast slot back as a script line: cast: bro = older brother, plays basketball, 3 years older"""
    if spec.get("who") == "named":
        bits = [str(spec.get("name"))]
    elif spec.get("of"):
        bits = [{"best_friend": "best friend", "partner": "boyfriend" if spec.get("gender") == "m" else "girlfriend" if spec.get("gender") == "f"
                 else "partner"}.get(spec["who"], str(spec["who"]).replace("_", " ")) + f" of {spec['of']}"]
    else:
        bits = [str(spec.get("who", "friend")).replace("_", " ")]
    if spec.get("sport"):
        bits.append(f"plays {spec['sport']}")
    off = spec.get("grade_offset")
    if off:
        bits.append(f"{abs(off)} years {'older' if off > 0 else 'younger'}")
    if spec.get("gender") and not str(spec.get("who", "")).endswith(("brother", "sister")) and spec.get("who") != "named" \
            and not (spec.get("of") and spec.get("who") == "partner"):
        bits.append("girl" if spec["gender"] == "f" else "guy")
    if spec.get("bond"):
        bits.append("close")
    if spec.get("bind") == "start":
        bits.append("from the start")
    if spec.get("label"):
        bits.append(spec["label"])
    return f"cast: {name} = " + ", ".join(bits)


# ---------------------------------------------------------------------------------------------------- the compiler
class Section:
    def __init__(self, title, n):
        self.title, self.n = title, n
        self.cast, self.defaults, self.about, self.order_any = {}, {}, None, False
        self.scenes, self.blocks = [], []
        self.pending_after = []
        self.lines_map = {}
        self.src_lines = []
        self.local = {}  # scene titles in this script -> ids (filled as scenes compile)
        self.expands = None  # the storyline this one adds to (an expansion): its title
        self.expands_line = n
        self.inherited = set()  # cast names that came from it
        self.parent_titles = {}  # its scene titles -> ids, for "after <scene>"

    def schedule_key(self, ref: str) -> str:
        return self.local.get(ref.lower()) or (ref if re.fullmatch(r"[a-z][a-z0-9_]{2,79}", ref) else "@" + ref)


def _children_text(node) -> list:
    return [c for c in node.children]


def _choice(node: Node, sc: Scene, depth: int, errs, path, sec) -> dict:
    """One '* choice | effects' with what's under it."""
    body = node.text[1:].strip()
    parts = _split(body, "|")
    label = parts[0].strip()
    extra = {}
    sec.lines_map[path] = node.line.n
    if not label.strip('"\' '):
        errs.append((node.line.n, "a choice needs words (what you say or do), like: * Front row | nicole affection +"))
    try:
        ops = effects(", ".join(parts[1:]), sc, node.line.n, extra) if len(parts) > 1 else []
    except Fail as e:
        errs.append((node.line.n, str(e)))
        ops = []
    lines, nested, outs = [], [], {}
    for ch in node.children:
        t = ch.text
        try:
            if t.startswith("*"):
                nested.append(ch)
            elif OUTCOME_RE.match(t):
                outs[OUTCOME_RE.match(t).group(1).lower()] = ch
            elif t.startswith("|"):
                ops += effects(t[1:], sc, ch.line.n, extra)
            elif CMD_RE.match(t):
                m = CMD_RE.match(t)
                ops.append([m.group(1), m.group(2)])
            elif MEMORY_RE.match(t):
                m = MEMORY_RE.match(t)
                val = {"good": 0.4, "great": 0.7, "happy": 0.4, "bad": -0.4, "awful": -0.7, "sad": -0.4}.get((m.group(2) or "").lower(), 0.2)
                who = ["them"] if sc.who else []
                ops.append(["memory", sc.names(m.group(1).strip(), ch.line.n), val, 45, who])
            elif TEXTS_RE.match(t) and ":" not in TEXTS_RE.match(t).group(1):
                m = TEXTS_RE.match(t)  # "bro texts: u up" -> they text you later today
                ops.append(["text", sc.person(m.group(1), ch.line.n), [sc.names(v, ch.line.n) for v in variants(m.group(2))]])
            else:
                bar = _split(t, "|")
                if len(bar) > 1:  # "bro: Fine. | bro respect +": they say it, and the effects happen
                    t = bar[0].strip()
                    ops += effects(", ".join(bar[1:]), sc, ch.line.n, extra)
                lines.append((ch.line.n, sc.line(t, ch.line.n)))
                for gc in ch.children:  # a line continued, indented under it
                    if gc.text.startswith("*"):
                        nested.append(gc)
                    else:
                        lines.append((gc.line.n, sc.line(gc.text, gc.line.n)))
        except Fail as e:
            errs.append((ch.line.n, str(e)))
    branch = extra.get("branch")
    if outs:
        fits = {"game": {"great", "good", "miss"}, "chance": {"yes", "no"}, "vibe": {"good", "meh", "bad"}}
        kind = branch[0] if branch and set(outs) <= fits.get(branch[0], set()) else OUTCOMES[next(iter(outs))]
        if not branch or branch[0] != kind:  # ("good:" works for a mini game and for a vibe)
            need = {"game": "play <game>", "chance": "a chance like 50%", "vibe": "vibe <style>"}[kind]
            errs.append((node.line.n, f"{'/'.join(k for k in outs)}: outcomes need {need} on the choice"))
        else:
            tiers = {}
            for k, onode in outs.items():
                o_extra = {}
                o_ops = []
                m = OUTCOME_RE.match(onode.text)
                rest = m.group(2).strip()
                try:
                    if rest:
                        p2 = _split(rest, "|")
                        if p2[0]:
                            o_ops.append(["say", sc.line(p2[0], onode.line.n)])
                        if len(p2) > 1:
                            o_ops += effects(", ".join(p2[1:]), sc, onode.line.n, o_extra)
                    for c2 in onode.children:
                        if c2.text.startswith("|"):
                            o_ops += effects(c2.text[1:], sc, c2.line.n, o_extra)
                        elif CMD_RE.match(c2.text):
                            mm = CMD_RE.match(c2.text)
                            o_ops.append([mm.group(1), mm.group(2)])
                        else:
                            o_ops.append(["say", sc.line(c2.text, c2.line.n)])
                except Fail as e:
                    errs.append((onode.line.n, str(e)))
                tiers[k] = o_ops
            if kind == "game":
                stat = GAME_STAT.get(branch[1], "athletic")
                ops.append(["minigame", branch[1], {k: tiers.get(k, []) for k in ("great", "good", "miss")}, {"base": 0.5, stat: 0.3}])
            elif kind == "chance":
                ops.append(["chance", branch[1], tiers.get("yes", []), tiers.get("no", [])])
            else:
                lines_only = {k: [o[1] for o in v if o[0] == "say"] for k, v in tiers.items()}
                more = {k: [o for o in v if o[0] != "say"] for k, v in tiers.items()}
                op = ["vibe", branch[1], {k: (v[0] if len(v) == 1 else [x for vs in v for x in vs]) or ["..."]
                                          for k, v in lines_only.items()}]
                if any(more.values()):
                    op.append({k: v for k, v in more.items() if v})  # effects on an outcome happen too
                ops.append(op)
    elif branch:
        if branch[0] == "game":
            stat = GAME_STAT.get(branch[1], "athletic")
            ops.append(["minigame", branch[1], {"great": [["mood", 4]], "good": [["mood", 2]], "miss": []}, {"base": 0.5, stat: 0.3}])
        elif branch[0] == "chance":
            errs.append((node.line.n, "a chance needs what happens: yes: ... and no: ... under the choice"))
        else:
            errs.append((node.line.n, "a vibe needs what happens: good: ..., meh: ..., bad: ... under the choice"))
    out = {"label": sc.names(variants(label)[0], node.line.n) if label else "..."}
    if extra.get("fits"):
        out["fits"] = extra["fits"]
    if nested:
        if depth >= 4:
            errs.append((nested[0].line.n, "a scene can keep going five beats deep at most; end it here"))
            nested = []
        else:
            text = _join([v for _, v in lines]) or ["..."]
            out["then"] = {"text": text, "choices": [_choice(c, sc, depth + 1, errs, f"{path}.then.choices[{i}]", sec)
                                                     for i, c in enumerate(nested)]}
            lines = []
    for _, vs in lines:
        ops.append(["say", vs if len(vs) > 1 else vs[0]])
    out["ops"] = ops
    return out


def _join(line_versions: list) -> list | str:
    """Several lines, each with versions -> versions of the whole passage (newline between lines)."""
    if not line_versions:
        return []
    n = max(len(v) for v in line_versions)
    out = list(dict.fromkeys("\n".join(v[k % len(v)] for v in line_versions) for k in range(min(n, 6))))
    return out[0] if len(out) == 1 else out


def _scene(sec: Section, head: Line, body: list, errs: list, idx: int, ids: set) -> dict | None:
    m = re.fullmatch(r"(.+?)(?:\s+#([a-z][a-z0-9_]{2,79}))?((?:\s*\[[^\]]*\])*)\s*(?:#([a-z][a-z0-9_]{2,79}))?", SCENE_RE.match(head.text).group(1))
    title = (m.group(1) if m else SCENE_RE.match(head.text).group(1)).strip()
    tag_text = " · ".join(re.findall(r"\[([^\]]*)\]", m.group(3) if m else ""))
    sid = (m.group(2) or m.group(4)) if m else None
    entry = None
    if getattr(sec, "outline", None) is not None:
        num = re.match(r"(?:scene\s*|chapter\s*|#)?(\d+)\s*[.):\-]\s*(.+)$", title, re.I)
        entry = _entry(sec, int(num.group(1)) if num else None, num.group(2) if num else title)
        if num:
            title = num.group(2).strip()
        kept = [t for t in re.split(r"\s*[·;,]\s*", tag_text) if t.strip().lower() in IMPORTANCE or t.strip().lower().startswith("with ")]
        if entry is not None:
            title = entry["title"]
            tag_text = " · ".join([x for x in [entry["when"]] + kept if x])
        else:
            tag_text = " · ".join(kept)  # (a scene the outline doesn't have: it comes after the outlined ones)
    sc = Scene(sec)
    when = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in sec.defaults.items()
            if k != "spread"}
    own: dict = {}
    try:
        tags(tag_text, sc, head.n, own, sec)
    except Fail as e:
        errs.append((head.n, str(e)))
    if own.pop("spread", None):
        errs.append((head.n, "spread goes on the storyline (when: freshman · spread), not on one scene"))
    timed = {"years", "months", "dates", "not_before", "not_after"}
    if own.keys() & {"months", "dates", "not_before", "not_after"}:  # its own season replaces the storyline's
        for k in ("months", "dates", "not_before", "not_after"):
            when.pop(k, None)
    for k, v in own.items():  # the scene's own tags win; conditions add up
        if k in ("requires", "remembered", "not_remembered", "after") and isinstance(v, list):
            when[k] = list(dict.fromkeys((when.get(k) or []) + v))
        else:
            when[k] = v
    for i, (wd, ref, n) in enumerate(sec.pending_after):
        if wd is own:
            sec.pending_after[i] = (when, ref, n)  # (an `after` it names links up into the merged tags)
    sec.own_time = getattr(sec, "own_time", set())
    if own.keys() & timed:
        sec.own_time.add(head.n)
    sid = sid or f"{slug(sec.title, 28)}_{slug(title, 40)}"
    base, k = sid, 2
    while sid in ids:
        sid, k = f"{base}_{k}", k + 1
    ids.add(sid)
    if entry is not None:
        sec.entry_of[sid] = entry["n"]
    path = f"scenes[{idx}]"
    sec.lines_map[path] = head.n
    roots = _tree(body)
    # who the scene is about: an explicit "with", else the first person who talks
    for r in roots:
        sm = SPEAKER_RE.match(r.text)
        if sm and not r.text.startswith("*"):
            try:
                sc.speaker(sm.group(1))
            except Fail:
                pass
            if sc.who:
                break
    text_lines, choices = [], []
    for r in roots:
        t = r.text
        try:
            if t.startswith("*"):
                choices.append(r)
            elif t.startswith("|") or CMD_RE.match(t) or len(_split(t, "|")) > 1:
                errs.append((r.line.n, "effects go on a choice (* label | effects) or a line under one, not on the scene's "
                                       "opening lines"))
            elif choices:
                errs.append((r.line.n, "this line comes after the choices: put it under one (indented) or before them"))
            else:
                text_lines.append(sc.line(t, r.line.n))
                for c in r.children:
                    text_lines.append(sc.line(c.text, c.line.n))
        except Fail as e:
            errs.append((r.line.n, str(e)))
    if len(choices) > 4:
        errs.append((choices[4].line.n, "a scene has at most 4 choices"))
        choices = choices[:4]
    compiled = [_choice(c, sc, 1, errs, f"{path}.choices[{i}]", sec) for i, c in enumerate(choices)]
    if not compiled:
        compiled = [{"label": "Continue", "ops": []}]
    out = {"id": sid, "title": sc.names(title, head.n) if "{" in title else title, "text": _join(text_lines) or "...",
           "choices": compiled, "line": head.n,
           "src": "\n".join([head.text] + [(" " * ln.indent) + ln.text for ln in body])}
    if sc.who:
        out["who"] = sc.who
    if sc.cast_refs - ({sc.who_slot} if sc.who_slot else set()):
        out["cast_refs"] = sorted(sc.cast_refs - ({sc.who_slot} if sc.who_slot else set()))
    if when:
        out["when"] = when
    return out


# ---------------------------------------------------------------------------------------------------- texting blocks
FLIRT_STYLES = ("tease", "sweet", "bold", "funny", "cheesy")
# the styles ChatGPT tends to invent, as the game's: "flirt sarcastic:" is teasing
STYLE_WORDS = {"sarcastic": "tease", "teasing": "tease", "teasy": "tease", "playful": "tease", "flirty": "tease", "snarky": "tease",
               "banter": "tease", "roast": "tease", "roasting": "tease", "witty": "funny", "silly": "funny", "goofy": "funny",
               "joking": "funny", "jokey": "funny", "dry": "funny", "humor": "funny", "humorous": "funny", "cute": "sweet",
               "soft": "sweet", "wholesome": "sweet", "romantic": "sweet", "shy": "sweet", "genuine": "sweet", "nice": "sweet",
               "confident": "bold", "direct": "bold", "forward": "bold", "smooth": "bold", "spicy": "bold", "daring": "bold",
               "corny": "cheesy", "pickup": "cheesy", "pick-up": "cheesy", "cringe": "cheesy", "cringey": "cheesy",
               "chill": "cool", "casual": "cool", "nonchalant": "cool"}
FLIRT_OUT = {"lands": "landed", "land": "landed", "landed": "landed", "laughs": "playful", "laugh": "playful", "laughs it off": "playful",
             "playful": "playful", "awkward": "awkward", "no": "shut", "shut down": "shut", "shut": "shut", "nope": "shut",
             "works": "landed", "worked": "landed", "goes well": "landed", "went well": "landed", "good": "landed", "yes": "landed",
             "into it": "landed", "success": "landed", "positive": "landed", "laughed": "playful", "laughed it off": "playful",
             "lol": "playful", "deflects": "playful", "weird": "awkward", "cringe": "awkward", "fail": "awkward", "flops": "awkward",
             "rejected": "shut", "rejection": "shut", "not into it": "shut", "not interested": "shut", "shuts it down": "shut",
             "turned down": "shut", "negative": "shut"}
FLIRT_PAYOFF = {"blush": "blush", "blushing": "blush", "plans": "plans", "goodnight": "goodnight", "good night": "goodnight",
                "night": "goodnight", "ask": "ask", "ask me out": "ask", "ask out": "ask"}
FLIRT_BACK = {**{x: x for x in FLIRT_STYLES}, "cool": "cool", "play it cool": "cool", "letdown": "letdown", "let down": "letdown",
              "let them down": "letdown", "let them down easy": "letdown",
              "cheesy": "funny"}  # (answering a first flirt has no cheesy option: those lines go with the funny ones)
FLIRT_HELP = ("flirt blocks: flirt tease: (openers; styles tease, sweet, bold, funny, cheesy; add later for once you're flirty), "
              "flirt answers bold, lands: (lands, laughs, awkward, no), flirt follow-ups tease: (add after a laugh), flirt first:, "
              "flirt back sweet: (or cool, letdown), flirt payoff blush: (blush, plans, goodnight, ask)")


FLIRT_SAY = {"way a flirt goes": "lands, laughs, awkward or no", "way a flirt can end": "blush, plans, goodnight or ask",
             "way to answer a flirt": "tease, sweet, bold, funny, cheesy, cool or letdown", "flirt style": "tease, sweet, bold, funny, cheesy or cool"}


def _flirt_word(word, table, what):
    w = word.strip()
    if w in table:
        return table[w]
    raise Fail(f"'{w}' isn't a {what}.{_suggest(w, list(table))} Use: {FLIRT_SAY.get(what, ', '.join(dict.fromkeys(table.values())))}")


def flirt_path(key: str) -> list:
    """`flirt answers bold, lands` -> where those lines go in the texting lines (chat.json "banter")."""
    k = re.sub(r"\s+", " ", key.lower().replace(",", " ").replace("(", " ").replace(")", " ")).strip()
    k = " ".join(STYLE_WORDS.get(x, x) for x in k.split(" "))  # (sarcastic -> tease...)
    later = k.endswith(" later")
    if later:
        k = k[:-6].strip()
    band = "close" if later else "early"
    if k in ("first", "them first", "they flirt first"):
        return ["banter", "in", band]
    m = re.fullmatch(r"(?:answers?|they answer|replies) (\w+) (.+)", k)
    if m:
        return ["banter", "them", _flirt_word(m.group(1), {**{x: x for x in FLIRT_STYLES}, "cool": "cool"}, "flirt style"),
                _flirt_word(m.group(2), FLIRT_OUT, "way a flirt goes")]
    m = re.fullmatch(r"(?:follow-?ups?|follow ups?|next) (\w+)( after a laugh| after they laugh)?", k)
    if m:
        return ["banter", "back", "playful" if m.group(2) else "landed",
                _flirt_word(m.group(1), {**{x: x for x in FLIRT_STYLES}, "cool": "cool"}, "flirt style")]
    m = re.fullmatch(r"back (.+)", k)
    if m:
        return ["banter", "in_back", _flirt_word(m.group(1), FLIRT_BACK, "way to answer a flirt")]
    m = re.fullmatch(r"(?:payoff|it goes somewhere|ending) (.+)", k)
    if m:
        return ["banter", "payoff", _flirt_word(m.group(1), FLIRT_PAYOFF, "way a flirt can end")]
    if k in FLIRT_STYLES:
        return ["banter", "open", band, k]
    near = _suggest(k.split(" ")[0], list(FLIRT_STYLES) + ["answers", "follow-ups", "first", "back", "payoff"])
    raise Fail(f"'flirt {key}' isn't a kind of flirt line.{near} {FLIRT_HELP}")


GROUP_CHATS = {"crew": "crew", "friends": "crew", "squad": "crew", "the boys": "crew", "the girls": "crew", "the crew": "crew",
               "team": "team", "teammates": "team", "the team": "team", "family": "family", "the family": "family", "parents": "family"}
GROUP_WHEN = {"weekend": "weekend", "school day": "school_day", "school_day": "school_day", "school night": "school_night",
              "school_night": "school_night", "winter": "winter", "pet": "has_pet", "has pet": "has_pet", "has_pet": "has_pet",
              "pregame": "pregame", "game tomorrow": "pregame", "before a game": "pregame", "win": "win", "after a win": "win",
              "loss": "loss", "after a loss": "loss"}
GROUP_ROLES = {"crew": {"a": "A", "b": "B", "c": "C"}, "team": {"a": "A", "b": "B", "c": "C"},
               "family": {"p": "P", "q": "Q", "s": "S", "t": "T", "parent": "P", "mom": "P", "other parent": "Q", "dad": "Q",
                          "sibling": "S", "brother": "S", "sister": "S", "other sibling": "T"}}
GROUP_FX_ME = ("fun", "stress", "mood")
AMOUNT = {"+": 1.5, "++": 3.0, "+++": 4.5, "-": -1.0, "--": -2.0, "---": -3.0}


def _group_fx(text: str, roles: dict, n: int) -> dict:
    """`A +, B -, fun ++, crew +` -> {"A": {"affection": 1.5}, "B": {...}, "me": {"fun": 3}, "crew": {"cohesion": 1.5}}"""
    out: dict = {}
    for tok in _split(text, ","):
        tok = tok.strip()
        if not tok:
            continue
        m = re.fullmatch(r"(.+?)\s*(?:affection|likes you|happy)?\s*([+-]{1,3}|[+-]\d+(?:\.\d+)?)", tok, re.I)
        if not m:
            raise Fail(f"'{tok}' isn't an effect. Effects look like: A +, B -, fun ++, stress -, crew +, trust +")
        who, amt = m.group(1).strip().lower(), m.group(2)
        v = AMOUNT.get(amt) if amt in AMOUNT else float(amt)
        if who in roles:
            out.setdefault(roles[who], {})["affection"] = v
        elif who in GROUP_FX_ME:
            out.setdefault("me", {})[who] = v
        elif who in ("crew", "cohesion", "group", "the group"):
            out.setdefault("crew", {})["cohesion"] = v
        elif who in ("trust", "parents", "parent trust"):
            out.setdefault("parents", {})["trust"] = v
        else:
            raise Fail(f"'{who}' isn't someone in this chat or something an effect changes.{_suggest(who, list(roles) + list(GROUP_FX_ME) + ['crew', 'trust'])} "
                       f"Use the people ({', '.join(sorted({r for r in roles.values()}))}), fun, stress, mood, crew or trust")
    return out


def _group_chat(key: str, nodes: list, pack: dict, errs: list, head_n: int):
    """`group chat crew, weekend:` and a little conversation: who says what (A:, B:...), then what you can jump in with
    (`* what you say | effects`, with their answers indented under it, and `dm B: ...` for someone DMing you after)."""
    bits = [b.strip().lower() for b in _split(key, ",") if b.strip()]
    if not bits or bits[0] not in GROUP_CHATS:
        errs.append((head_n, f"'group chat {key}' needs which chat first: crew, team or family.{_suggest(bits[0] if bits else '', GROUP_CHATS)}"))
        return
    chat = GROUP_CHATS[bits[0]]
    when = []
    for b in bits[1:]:
        if b in GROUP_WHEN:
            when.append(GROUP_WHEN[b])
        else:
            errs.append((head_n, f"'{b}' isn't a time a group chat can wait for.{_suggest(b, GROUP_WHEN)} "
                                 f"Use: weekend, school day, school night, winter, pet, game tomorrow, after a win, after a loss"))
            return
    roles = GROUP_ROLES[chat]
    speak = re.compile(r"^(dm\s+)?([A-Za-z][A-Za-z ]{0,13}?)\s*:\s*(.+)$")

    def said(nd):
        m = speak.match(nd.text)
        if not m:
            raise Fail(f"in a group chat, a line is who's talking and what they say, like A: yo what's the move")
        who = m.group(2).strip().lower()
        if who not in roles:
            raise Fail(f"'{m.group(2)}' isn't someone in the {chat} chat.{_suggest(who, roles)} Use "
                       + (", ".join(sorted(set(roles.values()))) if chat != "family" else "parent, other parent, sibling, other sibling"))
        t = m.group(3).strip().strip('"')
        if len(t) > 200:
            raise Fail(f"a text is short: keep it under 200 characters (this one is {len(t)})")
        return bool(m.group(1)), roles[who], t
    lines, you = [], []
    before = len(errs)
    for nd in nodes:
        try:
            if nd.text.startswith("*"):
                label, _, fx = nd.text[1:].partition("|")
                label = label.strip().strip('"')
                if not label:
                    raise Fail("a reply needs what you say: * honestly it's not that bad | B +")
                opt = {"say": label, "then": [], "fx": _group_fx(fx, roles, nd.line.n) if fx.strip() else {}}
                for ch in _flatten(nd.children):
                    try:
                        dm, role, t = said(ch)
                    except Fail as e:
                        errs.append((ch.line.n, str(e)))
                        continue
                    if dm:
                        opt["dm"] = {"from": role, "text": t}
                    else:
                        opt["then"].append([role, t])
                if len(you) >= 4:
                    raise Fail("that's past the fourth reply: three is plenty, four at most")
                you.append(opt)
            else:
                if you:
                    raise Fail("the conversation comes first, then your replies (* ...): this line is after them")
                dm, role, t = said(nd)
                lines.append([role, t])
        except Fail as e:
            errs.append((nd.line.n, str(e)))
    if len(errs) > before:
        return  # fix those first: then see whether there's enough left
    if len(lines) < 2 or not you:
        errs.append((head_n, "a group chat needs at least two lines of them talking and at least one thing you can say (* ...)"))
        return
    import hashlib
    bid = "pk_" + hashlib.sha1(("|".join(t for _, t in lines)).encode()).hexdigest()[:10]
    pack.setdefault("groupchat", []).append({"id": bid, "chat": chat, "when": when, "lines": lines, "you": you, "line": head_n})


def _block(kind: str, key: str, nodes: list, pack: dict, errs: list, sec: Section, head_n: int = 0):
    V = _vocab()
    kind = re.sub(r"\s+", " ", kind.lower())
    key = key.strip()
    if kind == "flirt":
        try:
            path = flirt_path(key)
        except Fail as e:
            errs.append((head_n, str(e)))
            return
        cur = pack.setdefault("chat", {})
        for k in path[:-1]:
            cur = cur.setdefault(k, {})
        lst = cur.setdefault(path[-1], [])
        for nd in _flatten(nodes):
            t = nd.text.strip().strip('"')
            if len(t) > 200:
                errs.append((nd.line.n, f"a text is short: keep it under 200 characters (this one is {len(t)})"))
            elif t:
                lst.extend(variants(t))
        return
    if kind == "group chat":
        _group_chat(key, nodes, pack, errs, head_n)
        return
    flat = []
    for nd in nodes:
        flat.append(nd)
        flat.extend(_flatten(nd.children))
    try:
        if kind == "texts":
            pool = pack.setdefault("texts", {}).setdefault(key, [])
            for nd in flat:
                pool.extend(variants(nd.text))
        elif kind == "replies":
            rs = pack.setdefault("replies", {}).setdefault(key, [])
            for nd in flat:
                m = re.fullmatch(r"(.+?)\s*\((\w+)\)", nd.text)
                if not m or m.group(2).lower() not in V["tones"]:
                    errs.append((nd.line.n, f"a reply ends with its tone in parentheses, like: on it (warm). Tones: {', '.join(sorted(V['tones']))}"))
                    continue
                rs.append([m.group(1).strip(), m.group(2).lower()])
        elif kind == "narration":
            pack.setdefault("narration", {}).setdefault(key, []).extend(nd.text for nd in flat)
        elif kind == "mods":
            bits = key.split()
            if len(bits) != 2:
                raise Fail("mods take a kind and a tag, like: mods open late_night:")
            pack.setdefault("mods", {}).setdefault(bits[0], {}).setdefault(bits[1], []).extend(nd.text for nd in flat)
        elif kind == "chat":
            cur = pack.setdefault("chat", {})
            ks = key.split(".")
            for k in ks[:-1]:
                cur = cur.setdefault(k, {})
            lst = cur.setdefault(ks[-1], [])
            for nd in flat:
                if ks[-2:-1] == ["ask"] or (len(ks) >= 2 and ks[-2] == "ask"):
                    m = re.fullmatch(r"(.+?)\s*\((yesno|doing|day|weekend|open|flirty)\)", nd.text)
                    if not m:
                        errs.append((nd.line.n, "a question ends with what kind of answer it wants: (yesno), (doing), (day), (weekend), (open) or (flirty)"))
                        continue
                    lst.append({"q": m.group(1).strip(), "a": m.group(2)})
                else:
                    lst.append(nd.text)
        elif kind == "trivia":
            qs = pack.setdefault("trivia", {}).setdefault(key.lower(), [])
            for nd in flat:
                m = re.fullmatch(r"(.+?)\s*=\s*(.+?)(?:\s*\((?:grade\s*)?(\d{1,2})\))?", nd.text)
                ans = _split(m.group(2), "|") if m else []
                if not m or len(ans) != 4:
                    errs.append((nd.line.n, "a question looks like: What's the powerhouse of the cell? = the mitochondria | the nucleus | the ribosome | the membrane (grade 9)"))
                    continue
                q = {"q": m.group(1).strip(), "a": ans[0], "w": ans[1:]}
                if m.group(3):
                    q["g"] = int(m.group(3))
                qs.append(q)
        elif kind == "schedule":
            # retime any scene, in any storyline: "Same Team: Cut day [college junior · March · after Prom night]"
            for nd in flat:
                m = re.fullmatch(r"(.+?)\s*((?:\[[^\]]*\]\s*)+)", nd.text)
                if not m:
                    errs.append((nd.line.n, "a schedule line is a scene and its new tags, like: Same Team: Cut day [sophomore · March]"))
                    continue
                ref = m.group(1).strip()
                raw = " · ".join(re.findall(r"\[([^\]]*)\]", m.group(2)))
                flags = {}
                keep = []
                for tok in re.split(r"\s*[·;,]\s*", raw):
                    low = tok.strip().lower()
                    if low in ("replace", "replace after"):
                        flags["replace_after"] = True
                    elif low in ("skip", "retire", "drop"):
                        flags["skip"] = True
                    elif low:
                        keep.append(tok)
                w2: dict = {}
                try:
                    tags(" · ".join(keep), None, nd.line.n, w2, sec)
                    _check_ref(ref, sec, nd.line.n)
                except Fail as e:
                    errs.append((nd.line.n, str(e)))
                    continue
                bad = [k for k in w2 if k not in ("years", "after", "gap_days", "months", "not_before", "not_after", "importance", "spread")]
                if bad:
                    errs.append((nd.line.n, f"a schedule can set the school year, months, after, a gap, before/after a date and how big; not {', '.join(bad)}"))
                    continue
                key = sec.schedule_key(ref)
                w2.update(flags)  # (the same dict: an `after` that links up later lands in it)
                pack.setdefault("schedule", {})[key] = w2
                sec.lines_map[f"schedule.{key}"] = nd.line.n
        elif kind == "choices":
            sc = Scene(sec)
            chs = pack.setdefault("moment_choices", {}).setdefault(key, [])
            for i, nd in enumerate(nodes):
                if nd.text.startswith("*"):
                    chs.append(_choice(nd, sc, 1, errs, f"moment_choices.{key}[{i}]", sec))
                else:
                    errs.append((nd.line.n, "under choices <moment>: each choice starts with *"))
    except Fail as e:
        errs.append((nodes[0].line.n if nodes else 0, str(e)))


def _flatten(nodes):
    out = []
    for n in nodes:
        out.append(n)
        out.extend(_flatten(n.children))
    return out


SCHOOL_MONTHS = [9, 10, 11, 12, 1, 2, 3, 4, 5, 6]
YEAR_ORDER = ["freshman", "sophomore", "junior", "senior", "college_freshman", "college_sophomore", "college_junior", "college_senior"]


def _head_title(h) -> str:
    """A scene line's title, in lowercase (without its [tags] and #id)."""
    return re.sub(r"\s*(\[.*|#.*)$", "", SCENE_RE.match(h.text).group(1)).strip().lower()


def _check_ref(ref: str, sec, n):
    """A schedule line's scene (or whole storyline) has to be one you have, or one in this script."""
    names = getattr(sec, "lib_names", None)
    if names is None:
        return  # (no storylines at hand to check against: checked again when it's added)
    low = ref.strip().lower()
    if (low in sec.lib_titles or low in getattr(sec, "here_scene_titles", set()) or low in getattr(sec, "here_full", set())
            or low in names or re.fullmatch(r"[a-z][a-z0-9_]{2,79}", ref.strip())):
        return
    if ":" in low:
        st, _, ti = low.rpartition(":")
        if st.strip() in names:
            opts = [t.split(": ", 1)[1] for t in list(sec.lib_titles) + list(getattr(sec, "here_full", ())) if t.startswith(st.strip() + ": ")]
            raise Fail(f"{ref.rpartition(':')[0].strip()} has no scene called '{ti.strip()}'.{_suggest(ti.strip(), opts)}")
    opts = [t for t in sec.lib_titles if ": " in t] + sorted(names)
    raise Fail(f"there's no scene or storyline called '{ref.strip()}'.{_suggest(low, opts)} Write it as <Storyline>: <scene title>, "
               "or a storyline's title to retime all of it")


def concrete_years(years) -> list:
    """freshman, high_school, college... -> the school years themselves, in order."""
    from . import dialogue as D
    grades = sorted({g for y in (years or []) for g in D.YEARS.get(y, ())})
    return [y for y in YEAR_ORDER if D.YEARS[y][0] in grades]


def spread_slots(years, months, n: int) -> list:
    """n scenes in order across these school years (and months: the school year, Sept to June, if none): (year, month) each."""
    ys = concrete_years(years)
    if not ys:
        raise Fail("spread needs the school years to spread across, like when: freshman · spread (or freshman-junior · spread)")
    ms = [m for m in SCHOOL_MONTHS + [7, 8] if m in (months or SCHOOL_MONTHS)]
    slots = [(y, m) for y in ys for m in ms]
    return [slots[min(len(slots) - 1, (k * len(slots)) // max(1, n))] for k in range(n)]


def spread(scenes: list, years, months, keep=()):
    """Give each scene that doesn't have its own timing a school year and month, in order, evenly across the years. Scenes
    that keep their own month (or day: Thanksgiving, prom) stay put, and the ones between them are spaced out between them,
    so the order holds."""
    from . import calendar as calm
    ys = concrete_years(years)
    if not ys:
        raise Fail("spread needs the school years to spread across, like when: freshman · spread (or freshman-junior · spread)")
    ms = [m for m in SCHOOL_MONTHS + [7, 8] if m in (months or SCHOOL_MONTHS)]
    slots = [(y, m) for y in ys for m in ms]
    order = [m for m in SCHOOL_MONTHS + [7, 8]]

    def place(y, mo):
        exact = [i for i, (sy, sm) in enumerate(slots) if sy == y and sm == mo]
        if exact:
            return exact[0]
        later = [i for i, (sy, sm) in enumerate(slots) if sy == y and order.index(sm) >= order.index(mo)]
        return later[0] if later else max(i for i, (sy, _) in enumerate(slots) if sy == y)

    def where(i, sc):  # a kept scene's place among the slots
        w = sc.get("when") or {}
        mo = (w.get("months") or [None])[0]
        if mo is None and w.get("dates"):
            d = w["dates"][0]
            mo = int((calm.APPROX_MD.get(d) or d)[:2])
        if mo is None:
            return None
        mine = [x for x in (w.get("years") or []) if x in ys] or ys
        if len(mine) > 1:  # no year of its own: the year where it falls in the run of scenes
            ideal = i * len(slots) / max(1, len(scenes))
            y = min(mine, key=lambda x: abs(place(x, mo) - ideal))
            w["years"] = [y]
        else:
            y = mine[0]
        return place(y, mo)
    marks = [(i, where(i, sc)) for i, sc in enumerate(scenes) if sc["id"] in keep]
    marks = [(i, p) for i, p in marks if p is not None]
    bounds = [(-1, -1)] + marks + [(len(scenes), len(slots))]
    for (i0, p0), (i1, p1) in zip(bounds, bounds[1:]):
        free = [sc for sc in scenes[i0 + 1:i1] if sc["id"] not in keep]
        lo, hi = p0, max(p1, p0 + 1)
        for j, sc in enumerate(free):
            k = int(round(lo + (hi - lo) * (j + 1) / (len(free) + 1)))
            y, m = slots[min(len(slots) - 1, max(0, k))]
            w = sc.setdefault("when", {})
            w["years"], w["months"] = [y], [m]


# ---------------------------------------------------------------------------------------------------- outlined storylines
OUTLINE_RE = re.compile(r"^(?:[-*]\s*)?(?:scene\s*|chapter\s*|#)?(\d+)\s*[.):\-]\s*(.+)$", re.I)
COND_RE = re.compile(r"^(only if|if|unless)\s+(?:you\s+(?:picked|chose|choose|pick)\s+)?(?:scene\s*|#)?(\d+)\s*[:,\-]?\s*(.+)$", re.I)
COND_RE2 = re.compile(r"^(only if|if|unless)\s+you\s+(?:picked|chose|choose|pick)\s+[\"“']?(.+?)[\"”']?\s+in\s+(?:scene\s*|#)?(\d+)\s*$", re.I)


def _parse_outline(body: list, sec, warns) -> list:
    """`7. The Apology | March | Mike won't talk to you | only if you picked "Apologize" in 5` -> outline entries. Anything
    it can't read is left out with a note; the when part keeps the words the game knows and drops the rest."""
    out = []
    for ln in body:
        t = ln.text.strip()
        m = OUTLINE_RE.match(t)
        if not m:
            warns.append((ln.n, "an outline line looks like: 7. The Apology | March | what happens (this one was left out)"))
            continue
        parts = [x.strip() for x in _split(m.group(2), "|")]
        title = parts[0].strip(" \"'“”") or f"Scene {m.group(1)}"
        cond, rest, game = None, [], None
        for x in parts[1:]:
            gm = GAME_COND_RE.match(x)
            if gm:  # how your real game went: `| if we won`
                game = gm.group(2).lower().replace(" ", "_")
                continue
            c = COND_RE2.match(x)
            if c:
                cond = {"neg": c.group(1).lower() == "unless", "n": int(c.group(3)), "label": c.group(2).strip(" \"'“”")}
                continue
            c = COND_RE.match(x)
            if c and x.lower().startswith(("only if", "unless")):
                cond = {"neg": c.group(1).lower() == "unless", "n": int(c.group(2)), "label": c.group(3).strip(" \"'“”")}
                continue
            rest.append(x)
        when_raw = rest[0] if rest else ""
        summary = " | ".join(rest[1:]) if len(rest) > 1 else ""
        good = []
        for tok in [x for x in re.split(r"\s*[·;,]\s*", when_raw) if x.strip()]:
            if tok.strip().lower() in ("any", "anytime", "-", "—", "whenever"):
                continue
            gm = GAME_COND_RE.match(tok.strip())
            if gm:
                game = gm.group(2).lower().replace(" ", "_")
                continue
            try:
                tags(tok, None, ln.n, {}, sec)
                if re.match(r"(after|if|unless)\s", tok.strip().lower()):
                    raise Fail("order and conditions come from the outline")
                good.append(tok.strip())
            except Fail:
                warns.append((ln.n, f"'{tok.strip()}' isn't a time the game knows: scene {m.group(1)} gets its time from the outline"))
        out.append({"n": int(m.group(1)), "title": title[:90], "when": " · ".join(good), "summary": summary, "if": cond, "line": ln.n,
                    "game": game})
    out.sort(key=lambda e: e["n"])
    return out


GAME_COND_RE = re.compile(r"^(only\s+)?if\s+(we won|we lost|i played great|i played badly|i won it|i started|i was benched|rivalry game)\s*$", re.I)


def _entry(sec, n, title):
    """The outline entry a written scene belongs to: by its number, else by its title (close enough)."""
    import difflib
    if n is not None:
        hit = next((e for e in sec.outline if e["n"] == n), None)
        if hit:
            return hit
    low = (title or "").strip().lower()
    for e in sec.outline:
        if e["title"].lower() == low:
            return e
    near = difflib.get_close_matches(low, [e["title"].lower() for e in sec.outline], n=1, cutoff=0.75)
    return next((e for e in sec.outline if e["title"].lower() == near[0]), None) if near else None


def _choices_in(sc) -> list:
    out = []

    def walk(chs):
        for ch in chs or []:
            if isinstance(ch, dict):
                out.append(ch)
                if isinstance(ch.get("then"), dict):
                    walk(ch["then"].get("choices"))
    walk(sc.get("choices"))
    return out


def find_choice(sc, label: str):
    """The choice in a scene (any depth) most like these words: (index in _choices_in, the choice) or None."""
    import difflib
    chs = _choices_in(sc)
    want = re.sub(r"[^a-z0-9 ]", "", str(label).lower()).strip()
    labels = [re.sub(r"[^a-z0-9 ]", "", str(ch.get("label", "")).lower()).strip() for ch in chs]
    k = next((i for i, lb in enumerate(labels) if lb == want or (want and lb and (want in lb or lb in want))), None)
    if k is None:
        near = difflib.get_close_matches(want, labels, n=1, cutoff=0.55)
        k = labels.index(near[0]) if near else None
    if k is None:
        k = _by_words(want, labels)
    return None if k is None else (k, chs[k])


_PLAIN = set("a an the to on in at of for with and or but so if it its is be am are was do did not no yes i me my you your "
             "we us our he him his she her they them their this that these those just really very go going get got will would "
             "can could should want let lets ask tell say said".split())


def _stem(w: str) -> str:
    for suf in ("ing", "ly", "ed", "es", "s", "e"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def _by_words(want: str, labels: list):
    """The outline names a choice in its own words ("Ask her on a proper date") and the scene says it in a line ("Nikki,
    will you go on a proper date with me?"): the choice that shares the most of its meaningful words, if it clearly
    does (most of them, and more than any other choice)."""
    key = {_stem(w) for w in want.split() if w not in _PLAIN and len(w) > 1}
    if not key:
        return None
    scores = [len(key & {_stem(w) for w in lb.split() if w not in _PLAIN}) for lb in labels]
    if not scores:
        return None
    best = max(scores)
    if best == 0 or best * 2 <= len(key) or scores.count(best) > 1:  # (most of them: "Back row's fine" isn't "Front row")
        return None
    return scores.index(best)


AFTER_OPS = ("say", "remember", "forget", "memory", "text", "minigame", "chance", "hang_out", "play", "vibe")


def _has_after(ch: dict) -> bool:
    """Something happens after you pick it: lines, more choices, or something it sets up."""
    t = ch.get("then")
    if isinstance(t, dict) and (str(t.get("text") or "").strip() not in ("", "...") or t.get("choices")):
        return True
    return any(isinstance(op, list) and op and str(op[0]) in AFTER_OPS for op in ch.get("ops") or [])


def real_choices(sc) -> list:
    """A scene's own choices (not the "Continue" a scene with none gets)."""
    chs = [c for c in sc.get("choices") or [] if isinstance(c, dict)]
    return [] if [c.get("label") for c in chs] == ["Continue"] else chs


def choice_gaps(sc) -> list:
    """Choices with nothing after them while the ones beside them have something: what ChatGPT left out."""
    out = []

    def walk(chs):
        chs = [c for c in chs or [] if isinstance(c, dict)]
        if any(_has_after(c) for c in chs):
            out.extend(f"nothing happens after the choice {c.get('label')} (the others have lines after them)"
                       for c in chs if not _has_after(c) and c.get("label") != "Continue")
        for c in chs:
            if isinstance(c.get("then"), dict):
                walk(c["then"].get("choices"))
    walk(real_choices(sc))
    return out


def no_question(sc) -> str | None:
    """A scene that never asks you anything (no choices: it just ends), or asks with only one answer: why, or None. Every
    storyline scene should end on a question with 2 to 4 choices, so you get to decide how it goes."""
    chs = real_choices(sc)
    if not chs:
        return "it never asks you anything: it needs to end on a question with 2 to 4 choices (and what happens after each)"
    if len(chs) == 1:
        return f"it only has one choice ({chs[0].get('label')}): give it 2 to 4, so you actually get to pick"
    return None


def no_choices(sc) -> str | None:
    """A scene with no decision at all (it just ends): it can't go in. (One choice goes in, flagged by no_question.)"""
    if real_choices(sc):
        return None
    return "it never asks you anything: it needs to end on a question with 2 to 4 choices (and what happens after each)"


def stops_short(sc, others_have_choices: bool):
    """The last scene of a reply that stops partway (ChatGPT ran out of room): why, or None."""
    chs = real_choices(sc)
    if not chs and others_have_choices:
        return "it stops before its choices"
    if len(chs) > 1 and not _has_after(chs[-1]) and any(_has_after(c) for c in chs[:-1]):
        return f"it stops right after the choice {chs[-1].get('label')}, with nothing after it"
    return None


def _built(sec, scenes: list, pack: dict, warns) -> list:
    """An outlined storyline: its scenes in outline order (unwritten ones simply aren't there yet), each placed in the
    school year: holidays and named months keep their day, the rest are spaced evenly by date; "only if you picked X in 5"
    wired both ends. Nothing here can stop the storyline: a branch that can't be found plays either way."""
    order = {e["n"]: i for i, e in enumerate(sec.outline)}
    scenes.sort(key=lambda sc: order.get(sec.entry_of.get(sc["id"]), 10**6))
    by_n = {sec.entry_of[sc["id"]]: sc for sc in scenes if sc["id"] in sec.entry_of}
    for sc in scenes:  # the outline decides order and branches: no after / if of the scene's own
        w = sc.get("when") or {}
        for k in ("after", "remembered", "not_remembered"):
            w.pop(k, None)
    years = sec.defaults.get("years") or ["freshman"]
    if not sec.defaults.get("years"):
        warns.append((sec.n, "no years: line, so it's freshman year (add years: sophomore, or freshman-junior)"))
    keep = {sc["id"] for sc in scenes if (sc.get("when") or {}).keys() & {"months", "dates", "not_before", "not_after"}
            and not _same_months(sc, sec)}
    try:
        place(scenes, years, sec.defaults.get("months"), keep, total=len(sec.outline), slot_of=lambda sc: order.get(sec.entry_of.get(sc["id"])))
    except Fail as e:
        warns.append((sec.n, str(e)))
    for e in sec.outline:  # how your real game went (`| if we won`): the scene waits for a game that went that way
        sc = by_n.get(e["n"])
        if e.get("game") and sc is not None:
            req = sc.setdefault("when", {}).setdefault("requires", [])
            if e["game"] not in req:
                req.append(e["game"])
    for e in sec.outline:
        c = e.get("if")
        sc = by_n.get(e["n"])
        if not c or sc is None:
            continue
        src = by_n.get(c["n"])
        if src is None:
            warns.append((e["line"], f"scene {e['n']}: only if a choice in scene {c['n']}, which isn't written yet: it plays either way for now"))
            continue
        hit = find_choice(src, c["label"])
        if hit is None:
            warns.append((e["line"], f"scene {e['n']}: scene {c['n']} has no choice like \"{c['label']}\": it plays either way"))
            continue
        fact = f"{slug(sec.title, 20)}_{c['n']}_{slug(c['label'], 24)}"
        ops = hit[1].setdefault("ops", [])
        if ["remember", fact] not in ops:
            ops.append(["remember", fact])
        sc.setdefault("when", {}).setdefault("not_remembered" if c["neg"] else "remembered", []).append(fact)
    pack["outline"] = [{"n": e["n"], "title": e["title"], "when": e["when"], "summary": e["summary"],
                        "if": " · ".join(x for x in ((f"{'unless' if e['if']['neg'] else 'only if'} you picked “{e['if']['label']}” in {e['if']['n']}" if e.get("if") else None),
                                                     ("if " + e["game"].replace("_", " ").replace("i ", "I ", 1) if e.get("game") else None)) if x) or None,
                        "written": e["n"] in by_n, "sid": by_n[e["n"]]["id"] if e["n"] in by_n else None} for e in sec.outline]
    return scenes


def _same_months(sc, sec) -> bool:
    """True if the scene's months are just the storyline's own (from years:), not one of its own."""
    w = sc.get("when") or {}
    return bool(w.get("months")) and w.get("months") == sec.defaults.get("months") and not w.get("dates")


def place(scenes: list, years, months, keep=(), total=None, slot_of=None):
    """Space scenes out by date across their school years, in order: each gets its year and a day it can come from
    (not before), evenly. Scenes in keep stay on their own month or day, and the ones between them are spaced between them.
    total/slot_of: an outlined storyline spaces by its outline (unwritten scenes keep their place)."""
    from . import calendar as calm
    ys = concrete_years(years) or ["freshman"]
    ms = [m for m in SCHOOL_MONTHS + [7, 8] if m in (months or SCHOOL_MONTHS)]
    days = []  # every day it could be, in order: (year, month, day)
    for y in ys:
        for mo in ms:
            for d in range(1, (30 if mo in (4, 6, 9, 11) else 28 if mo == 2 else 31) + 1):
                days.append((y, mo, d))
    n_total = total or len(scenes)
    pos = (lambda sc, i: slot_of(sc)) if slot_of else (lambda sc, i: i)

    def anchor(sc, i):
        w = sc.get("when") or {}
        mo = (w.get("months") or [None])[0]
        if mo is None and w.get("dates"):
            d = w["dates"][0]
            mo = int((calm.APPROX_MD.get(d) or d)[:2])
        if mo is None and w.get("not_before"):
            mo = int(w["not_before"][:2])
        if mo is None:
            return None
        mine = [x for x in (w.get("years") or []) if x in ys] or ys
        ideal = (pos(sc, i) or 0) * len(days) / max(1, n_total)
        cands = [k for k, (y, m, d) in enumerate(days) if y in mine and m == mo]
        if not cands:
            cands = [k for k, (y, m, d) in enumerate(days) if y in mine] or [0]
        k = min(cands, key=lambda c: abs(c - ideal))
        y = days[k][0]
        if len(mine) > 1 or not w.get("years"):
            w["years"] = [y]
        return min(c for c in cands if days[c][0] == y)
    marks = [(i, anchor(sc, i)) for i, sc in enumerate(scenes) if sc["id"] in keep]
    marks = [(i, k) for i, k in marks if k is not None]
    bounds = [(-1, -1)] + marks + [(len(scenes), len(days))]
    for (i0, k0), (i1, k1) in zip(bounds, bounds[1:]):
        free = [(i, sc) for i, sc in enumerate(scenes[i0 + 1:i1], start=i0 + 1) if sc["id"] not in keep]
        lo, hi = k0, max(k1, k0 + 1)
        for j, (i, sc) in enumerate(free):
            if slot_of and i0 < 0 and i1 >= len(scenes):  # no anchors: space by the outline itself
                k = int((pos(sc, i) or 0) * len(days) / max(1, n_total))
            else:
                k = int(round(lo + (hi - lo) * (j + 1) / (len(free) + 1)))
            y, mo, d = days[min(len(days) - 1, max(0, k))]
            w = sc.setdefault("when", {})
            w["years"] = [y]
            for key in ("months", "not_after"):
                w.pop(key, None)
            w["not_before"] = f"{mo:02d}-{d:02d}"


def _expands(sec, title: str, library, here=None):
    """`expands: Sisters`: this storyline adds to that one. It gets its cast (the same people) and can name its scenes."""
    title = title.strip()
    same = (here or {}).get(title.lower())
    if same is not None:  # its storyline is in this same script
        sec.expands = same.title
        for name, spec in same.cast.items():
            if name not in sec.cast:
                sec.cast[name] = dict(spec)
                sec.inherited.add(name)
        return
    if library is None:
        return  # (checked again when it's added to your game, with your storylines at hand)
    parent = library.get(title.lower())
    if parent is None:
        raise Fail(f"there's no storyline called '{title}' to add to.{_suggest(title.lower(), list(library))}")
    if parent.get("expands"):
        raise Fail(f"'{title}' is itself an expansion of {parent['expands']}: expand {parent['expands']} instead")
    sec.expands = parent.get("name") or title
    for name, spec in (parent.get("cast") or {}).items():
        if name not in sec.cast:
            sec.cast[name] = dict(spec)
            sec.inherited.add(name)
    for sc in parent.get("scenes") or []:
        if isinstance(sc, dict) and sc.get("title"):
            sec.parent_titles[str(sc["title"]).lower()] = sc["id"]


def split_sections(text: str) -> list:
    """The script's === sections as (title, source text) — for saving each storyline to its own file."""
    out, cur, title = [], [], None
    for raw in text.replace("\r\n", "\n").split("\n"):
        m = SECTION_RE.match(raw.strip())
        if m:
            if cur and (title or any(x.strip() for x in cur)):
                out.append((title, "\n".join(cur).strip() + "\n"))
            cur, title = [raw], m.group(1).strip()
        else:
            cur.append(raw)
    if cur and any(x.strip() for x in cur):
        out.append((title, "\n".join(cur).strip() + "\n"))
    return out


def normalize_outline(text: str) -> str:
    """An outline the way ChatGPT sometimes writes it, the way the game reads it: the numbered lines without `outline:`
    above them, dashes instead of | between the parts, **bold** titles, or a table."""
    src = extract(text)
    out, saw_numbered, has_header = [], False, bool(re.search(r"^\s*outline\s*:\s*$", src, re.M | re.I))
    num = re.compile(r"^\s*(?:[-*]\s*)?(?:scene\s*)?(\d{1,3})\s*[.):]\s+(.+)$", re.I)
    for raw in src.split("\n"):
        ln = raw.rstrip()
        cells = [c.strip() for c in ln.strip().strip("|").split("|")] if ln.strip().startswith("|") else None
        if cells is not None:  # a table: | 1 | Title | When | What happens |
            if all(re.fullmatch(r":?-{2,}:?", c) or not c for c in cells) or not (cells and cells[0].rstrip(".").isdigit()):
                continue  # its header and the --- line under it
            ln = f"{cells[0].rstrip('.')}. " + " | ".join(cells[1:])
        m = num.match(ln)
        if m:
            body = m.group(2).replace("**", "").replace("__", "")
            if "|" not in body:
                body = re.sub(r"\s+[—–-]\s+", " | ", body, count=3)  # Title — September — what happens
            if not saw_numbered and not has_header:
                out.append("outline:")
            saw_numbered = True
            ln = f"{m.group(1)}. {body.strip()}"
        out.append(ln)
    return "\n".join(out) + ("\n" if src.endswith("\n") else "")


def looks_like_script(text: str) -> bool:
    return bool(re.search(r"^\s*(===|---)\s*\S", text, re.M)) or bool(
        re.search(r"^\s*(texts|replies|chat|trivia|flirt|group\s+chat)\s+\S.*:\s*$", text, re.M))


def extract(text: str) -> str:
    """A script from a paste: ChatGPT's answer with the script in a ``` block, or the script itself."""
    fences = re.findall(r"```[a-zA-Z]*\n([\s\S]*?)```", text)
    if fences:
        return "\n\n".join(f for f in fences if looks_like_script(f)) or fences[0]
    return text.strip().lstrip("﻿")


def compile_script(text: str, default_title: str = "Untitled", library: dict | None = None) -> dict:
    """A script -> the game's packs, one per === section, with errors by line number. library: the storylines you have
    ({title in lowercase: pack}), for expansions (`expands: <Storyline>` takes its cast and can name its scenes)."""
    from . import dialogue as D
    lines = _lines(text)
    errs: list = []
    warns: list = []
    sections: list = []
    sec = None
    i = 0
    ids: set = set()
    while i < len(lines):
        ln = lines[i]
        t = ln.text
        m = SECTION_RE.match(t)
        if m:
            sec = Section(m.group(1).strip(), ln.n)
            sections.append(sec)
            i += 1
            continue
        if sec is None:
            sec = Section(default_title, ln.n)
            sections.append(sec)
        m = ATTR_RE.match(t)
        if m and not sec.scenes and not sec.blocks and ln.indent == 0:
            k, v = m.group(1).lower(), m.group(2).strip()
            try:
                if k == "cast":
                    mm = re.fullmatch(r"([a-z][a-z0-9_]{2,30})\s*=\s*(.+)", v)
                    if not mm:
                        raise Fail("cast looks like: cast: bro = older brother, plays basketball, 3 years older "
                                   "(a short lowercase name, at least 3 letters, then who they are)")
                    if mm.group(1) in sec.cast and mm.group(1) not in sec.inherited:
                        raise Fail(f"'{mm.group(1)}' is already in the cast")
                    sec.inherited.discard(mm.group(1))
                    sec.cast[mm.group(1)] = cast_spec(mm.group(2))
                    sec.lines_map[f"cast.{mm.group(1)}"] = ln.n
                elif k in ("when", "years"):  # (years: is how an outlined storyline says when it happens)
                    tags(v, None, ln.n, sec.defaults, sec)
                elif k == "order":
                    sec.order_any = v.lower() in ("any", "any order", "loose", "free")
                elif k == "expands":
                    if not v.strip():
                        raise Fail("expands: names the storyline this adds to, like expands: Sisters")
                    sec.expands, sec.expands_line = v.strip(), ln.n  # (worked out once every section is read)
                else:
                    sec.about = v
            except Fail as e:
                errs.append((ln.n, str(e)))
            i += 1
            continue
        m = SCENE_RE.match(t)
        if m:
            j = i + 1
            while j < len(lines) and not (SECTION_RE.match(lines[j].text) or SCENE_RE.match(lines[j].text)
                                          or (BLOCK_RE.match(lines[j].text) and lines[j].indent == 0)):
                j += 1
            sec.scenes.append((ln, lines[i + 1:j]))
            i = j
            continue
        m = BLOCK_RE.match(t)
        if m and ln.indent == 0:
            j = i + 1
            while j < len(lines) and not (SECTION_RE.match(lines[j].text) or SCENE_RE.match(lines[j].text)
                                          or (BLOCK_RE.match(lines[j].text) and lines[j].indent == 0)):
                j += 1
            sec.blocks.append((ln, m.group(1) or m.group(3), m.group(2) or "", lines[i + 1:j]))
            i = j
            continue
        errs.append((ln.n, "this line isn't in a scene or a block. Start a scene with --- Title, or a block like texts chatter_school:"))
        i += 1
    # expansions: each takes its storyline's cast (from this script, or the ones you have)
    here = {x.title.lower(): x for x in sections if not x.expands}
    for x in sections:
        if x.expands:
            try:
                _expands(x, x.expands, library, here)
            except Fail as e:
                errs.append((x.expands_line, str(e)))
    if library is not None:  # your storylines' scene titles, for "after <Storyline>: <scene>" and schedule lines
        lib_titles, lib_names = {}, set()
        for pk in library.values():
            nm = str(pk.get("name") or "").lower()
            lib_names.add(nm)
            for sc in pk.get("scenes") or []:
                if isinstance(sc, dict) and sc.get("title"):
                    lib_titles[f"{nm}: {str(sc['title']).lower()}"] = sc["id"]
                    lib_titles.setdefault(str(sc["title"]).lower(), sc["id"])
        here_titles = {x.title.lower() for x in sections}
        for x in sections:
            x.lib_titles, x.lib_names = lib_titles, lib_names | here_titles
            x.here_scene_titles = {_head_title(h) for y in sections for h, _ in y.scenes}
            x.here_full = {y.title.lower() + ": " + _head_title(h) for y in sections for h, _ in y.scenes}
    # titles across the whole script, for "after <scene>"
    summaries: list = []
    packs = []
    by_title = {}
    compiled = []
    for sec in sections:
        pack = {"dialogue_pack": 1, "name": sec.title[:D.MAX_NAME], "script": {"title": sec.title, "line": sec.n}}
        if sec.expands:
            pack["expands"] = sec.expands
        if sec.about:
            pack["notes"] = sec.about
        if sec.cast:
            pack["cast"] = sec.cast
        ob = [b for b in sec.blocks if str(b[1]).lower() == "outline"]
        if ob:  # an outlined storyline: the game owns its order, timing and branches
            sec.blocks = [b for b in sec.blocks if str(b[1]).lower() != "outline"]
            sec.outline = _parse_outline(ob[0][3], sec, warns)
            sec.entry_of = {}
        scenes = []
        for idx, (head, body) in enumerate(sec.scenes):
            sc = _scene(sec, head, body, errs, idx, ids)
            if sc:
                scenes.append(sc)
                by_title[sc["title"].lower()] = sc["id"]
                by_title[f"{sec.title.lower()}: {sc['title'].lower()}"] = sc["id"]
                sec.local[sc["title"].lower()] = sc["id"]
                sec.local[f"{sec.title.lower()}: {sc['title'].lower()}"] = sc["id"]
        if getattr(sec, "outline", None) is not None:
            scenes = _built(sec, scenes, pack, warns)
        elif scenes and sec.defaults.get("spread"):
            try:
                spread(scenes, sec.defaults.get("years"), sec.defaults.get("months"),
                       keep={sc["id"] for sc in scenes if sc.get("line") in getattr(sec, "own_time", set())})
            except Fail as e:
                errs.append((sec.n, str(e)))
        if scenes:
            pack["scenes"] = scenes
            pack["in_order"] = not sec.order_any
        for head, kind, key, body in sec.blocks:
            _block(kind, key, _tree(body), pack, errs, sec, head.n)
        compiled.append((sec, pack))
    for sec, pack in compiled:
        for when, ref, n in sec.pending_after:
            sid = by_title.get(ref.lower()) or sec.parent_titles.get(ref.lower())
            if sid is None and getattr(sec, "lib_titles", None) is not None:
                hit = sec.lib_titles.get(ref.lower())
                if hit:
                    sid = hit  # a scene in a storyline you have
                elif ":" in ref and ref.split(":")[0].strip().lower() in sec.lib_names:
                    st, _, ti = ref.rpartition(":")
                    near = _suggest(ti.strip().lower(), [t.split(": ", 1)[1] for t in sec.lib_titles if t.startswith(st.strip().lower() + ": ")])
                    errs.append((n, f"'after {ref}': {st.strip()} has no scene called '{ti.strip()}'.{near}"))
                    continue
            if sid is None and re.fullmatch(r"[a-z][a-z0-9_]{2,79}", ref):
                sid = ref  # a scene id from another storyline
            if sid is None:
                if ":" not in ref:
                    near = _suggest(ref.lower(), list(by_title))
                    if near:
                        errs.append((n, f"'after {ref}': there's no scene called that here.{near} (For a scene in another "
                                        "storyline, write its storyline too: after Same Team: Cut day)"))
                        continue
                sid = "@" + ref  # another storyline's scene: it links up when that storyline is loaded
                warns.append((n, f"'after {ref}' isn't in this script; it links up with a loaded storyline that has it"))
            when.setdefault("after", []).append(sid)
        if not sec.order_any and pack.get("scenes"):
            # a storyline plays in order already: `after <an earlier scene of it>` is just the order, not "only if that
            # one happened" (so one scene that can't happen doesn't take every scene after it down with it)
            before: set = set()
            for sc in pack["scenes"]:
                w = sc.get("when") or {}
                if w.get("after"):
                    w["after"] = [a for a in w["after"] if a not in before]
                    if not w["after"]:
                        del w["after"]
                before.add(sc["id"])
        rep = D.check(pack)
        for e in rep["errors"]:
            errs.append((_line_of(e, sec), _plain(e)))
        for wmsg in rep["warnings"]:
            if "is ignored" not in wmsg:
                warns.append((_line_of(wmsg, sec), _plain(wmsg)))
        packs.append(pack)
        summaries.append(rep.get("summary") or {})
    if library is not None:  # an `if <fact>` that nothing remembers would wait forever: say so now
        known = set()
        for pk in list(library.values()) + packs:
            for sc in (pk.get("scenes") or []) + [{"choices": v} for v in (pk.get("moment_choices") or {}).values()]:
                if isinstance(sc, dict):
                    known |= {op[1] for op in D._all_ops(sc) if isinstance(op, list) and len(op) > 1 and op[0] == "remember"}
        for pk in packs:
            for sc in pk.get("scenes") or []:
                for f in (sc.get("when") or {}).get("remembered") or []:
                    if f not in known:
                        errs.append((sc.get("line") or 1, f"'if {f}': no choice in this script or your storylines remembers {f}, so "
                                     f"this scene would never happen.{_suggest(f, sorted(known))} Take the if off, or have a choice "
                                     f"remember {f} (a line `remember {f}` under it)"))
    errs = sorted(set(errs), key=lambda e: e[0])
    return {"packs": packs, "pack_summaries": summaries, "errors": [{"line": n, "text": t} for n, t in errs],
            "warnings": [{"line": n, "text": t} for n, t in sorted(set(warns), key=lambda e: e[0])],
            "summary": {"storylines": sum(1 for p in packs if p.get("scenes")),
                        "scenes": sum(len(p.get("scenes", [])) for p in packs),
                        "lines": sum(_leaves(p.get(k)) for p in packs for k in ("texts", "replies", "narration", "mods", "chat",
                                                                                     "trivia", "moment_choices"))}}


def _leaves(x) -> int:
    """How many lines a pool holds (texts, chat paths, mods: lists inside dicts, any depth)."""
    if isinstance(x, dict):
        return sum(_leaves(v) for v in x.values())
    if isinstance(x, list):
        return len(x)
    return 0


def _line_of(msg: str, sec: Section) -> int:
    """The script line a checker message is about (the deepest place it names)."""
    where = msg.split(":")[0]
    where = re.sub(r" \([a-z0-9_]+\)", "", where)
    best = sec.n
    best_len = -1
    for path, n in sec.lines_map.items():
        if where.startswith(path) and len(path) > best_len:
            best, best_len = n, len(path)
    return best


def _plain(msg: str) -> str:
    """A checker message without its JSON path."""
    parts = msg.split(": ", 1)
    return parts[1] if len(parts) == 2 and re.match(r"^[\w\[\]\.() -]+$", parts[0]) else msg


def scene_source(pack: dict, sid: str) -> str | None:
    for sc in pack.get("scenes", []):
        if sc.get("id") == sid:
            return sc.get("src")
    return None


# ---------------------------------------------------------------------------------------------------- the guide
EXAMPLE = '''=== Same Team
cast: bro = older brother, plays basketball, 3 years older, close
about: You and your brother on the same team for one season.
when: freshman-junior

--- The tryout list  [freshman · November · weekday]
The list goes up outside the gym. {bro} is already there.
bro: You're actually trying out? Coach'll eat you alive.
* "Watch me."               | confidence +, bro respect +
    bro: ...Alright. Don't embarrass me.
* "Help me get ready?"      | bro affection ++, basketball +
    bro: Driveway. Six a.m. Don't be late.
    remember bro_trains_you
* Shrug.                    | bro affection -

--- Six a.m.  [next day · if bro_trains_you]
bro: You're late. {Again.|Shocker.|Unbelievable.}
* Run the drill             | play basketball
    great: You hit nine straight. | bro respect ++
    good: Not bad.               | bro respect +
    miss: You airball the last one.
* "Five more minutes..."    | bro respect -
    bro: I'm telling Coach.

--- Cut day  [a week later · big]
The roster's on the gym door.
* Look for your name        | 60% +athletic
    yes: It's there. Second line from the bottom. | mood ++, remember made_jv
    no: It isn't.                                 | mood --, stress +
* Wait for {bro}
    bro: Come on. We'll look together.
    * "I can't."            | bro affection +, fits -confidence
        bro: Then I will.
    * "Okay."
        bro texts: proud of u either way'''


def guide(story_only: bool = False) -> str:
    """How to write a story script, generated from the game's own lists (so it's never out of date)."""
    from . import dialogue as D
    from . import lines as LN
    from . import pro
    V = _vocab()
    a = []
    A = a.append
    A("# LIFE OS story scripts")
    A("")
    A("Everything you add to LIFE OS (storylines, one-off scenes, texting lines) is a story script: plain text, like a "
      "screenplay. The game reads it and checks every line. What it can fix (a typo, a tag it doesn't know, a line that's "
      "too long, a fact nothing sets) it fixes, and tells you what it changed by line number; it only refuses a paste with "
      "nothing usable left in it.")
    A("")
    A("## The shape")
    A("")
    A("```")
    A(EXAMPLE)
    A("```")
    A("")
    A("## Storylines")
    A("")
    A("- `=== Title` starts a storyline. Its scenes play in the order they're written, each one waiting for the one before "
      "(as soon as it's ready: tags hold it to its season), so don't tag a scene `after` the scene before it. If one can't "
      "happen, the storyline moves on to the next. `order: any` under the title lets them come in any order (good for a bag "
      "of one-off moments).")
    A("- `cast: <name> = <who they are>`: a specific person the storyline is about, the same person for the whole story "
      "(across storylines too: the same cast name means the same person). Who: "
      + ", ".join(k.replace("_", " ") for k in sorted(V["castable"])) + ". Then any of: `plays <sport>` ("
      + ", ".join(sorted(V["sports"])) + "), `3 years older` / `2 years younger`, `girl` / `guy`, `close` (you start close), "
      "`from the start` (picked on day one, not at their first scene), and any words that describe them (\"the one who got away\").")
    A("- Someone in your story, by name: `cast: ally = Ally Soffer` (or just the first name if it's unique). The storyline is "
      "about exactly that person, and the same name in another storyline means the same person.")
    A("- Someone in another cast member's life: `cast: kayla = friend of sis, girl` (also `best friend of`, `teammate of`, "
      "`boyfriend of`, `girlfriend of`). The game picks them from that person's own friends (or team), and they stay the "
      "same person.")
    A("- `expands: <Storyline>` (under the title, like `=== Sisters: Holidays` then `expands: Sisters`): an expansion, more "
      "scenes for a storyline you have, in its own piece. It already has that storyline's cast (don't copy the cast: lines) "
      "and can say `after <one of its scenes>`.")
    A("- `when: <tags>`: tags every scene in the storyline gets (like `freshman-junior`). A scene's own year, month or day "
      "wins over these.")
    A("- `when: freshman · spread` spreads the storyline's scenes across that school year, in order, about evenly from "
      "September to June (or across several years: `freshman-sophomore · spread`; or a season: `junior · spring · spread`). "
      "Scenes with their own timing keep it.")
    A("- `about: <notes>`: what the storyline is about, for you and for ChatGPT.")
    A("- A scene in another storyline: `after Same Team: Cut day`.")
    A("")
    A("## Outlines (big storylines)")
    A("")
    A("For a storyline with more than a handful of scenes, plan it first: an `outline:` block under the title, one line per "
      "scene, then write the scenes a few at a time. The outline owns the order, the timing and the branches, so the scenes "
      "themselves are just people and choices.")
    A("")
    A("```")
    A("=== Brothers: Same Team")
    A("cast: mike = Mike Soffer")
    A("years: freshman")
    A("")
    A("outline:")
    A("1. Saved You a Seat | September | Mike saves you a seat on the bus.")
    A("2. The Passenger Seat | | Mike drives you to school for the first time.")
    A("3. Tryouts | November · big | You both try out.")
    A("4. Turkey Day | Thanksgiving | Mike is weird at dinner.")
    A("5. The Fight | December | You fight about playing time.")
    A("6. Making Up | | Mike apologizes. | only if you picked \"Say sorry\" in 5")
    A("")
    A("--- 1. Saved You a Seat")
    A("mike: Sit. Don't make it weird.")
    A("* \"Thanks.\" | mike affection +")
    A("* Sit in the back")
    A("```")
    A("")
    A("- Each line: `number. Title | when | what happens`, and optionally `| only if you picked \"<choice>\" in <number>`.")
    A("- `when` is a month, a holiday (Halloween, Thanksgiving, Christmas), a school day (homecoming, prom, winter break, "
      "the first or last day of school), `big` for a major scene, or blank: blank scenes are spaced out between the ones "
      "around them. `years:` under the title says which school year(s). A time the game doesn't know is left out, with a note.")
    A("- A scene is `--- <number>. <Title>` and matches its outline line by number (or title). Tags on it are ignored, "
      "except `big` and `with`: its time and place come from the outline. Scenes not written yet just don't play.")
    A("- `only if you picked \"Say sorry\" in 5`: the game finds the choice in scene 5 most like \"Say sorry\", has it "
      "remember that, and plays the scene only if you picked it. If scene 5 has nothing like it, the scene plays either way.")
    A("- On the phone: Me > Storylines > Write more makes the outline prompt, then a prompt for the next few scenes at a "
      "time, and shows how many are written.")
    A("")
    A("## Scenes")
    A("")
    A("`--- Title  [tags]` starts a scene. Tags (separate with · or commas):")
    A("")
    A("- School year: freshman, sophomore, junior, senior, college freshman ... college senior, ranges like `freshman-junior`, "
      "or `high school` / `college`.")
    A("- Month or season: `November`, `Nov`, `fall`, `winter`, `spring`, `summer`. A day: `Oct 31`, or a holiday: `Halloween`, "
      "`Christmas Eve`, `Christmas`, `New Year's Eve`, `New Year's Day`, `Valentine's Day`, `St. Patrick's Day`, "
      "`April Fools`, `July 4th`, `Veterans Day`.")
    A("- Days that move, worked out for every year: `Thanksgiving`, `Black Friday`, `Easter`, `Mother's Day`, `Father's Day`, "
      "`Memorial Day`, `Labor Day`, `MLK Day`, `Presidents' Day`, `Columbus Day`, `Super Bowl` (the real Sunday each year)."
      + " The school calendar's own days: " + ", ".join(
        f"`{k.replace('_', ' ')}`" for k in ("first_day_of_school", "last_day_of_school", "homecoming", "homecoming_week",
                                              "snow_ball", "prom", "prom_week", "midterms", "midterms_week", "finals",
                                              "finals_week", "report_cards", "graduation", "thanksgiving_break", "winter_break",
                                              "spring_break")) + ". A scene tagged with one of these always gets its day "
      "(you don't need a chance). `after Nov 15` / `before Thanksgiving` for a window.")
    A("- In class: `in biology` (or " + ", ".join(f"`in {k.replace('_', ' ')}`" for k in sorted(_subjects()) if k != "biology")
      + ", `in gym`) puts it on a school day in that class, if you're taking it that year; `{teacher}` and `{class}` say "
      "your teacher's name and the class. `in class` is any class.")
    A("- Day: `weekday`, `weekend`, `school day`, `summer break`, or a weekday (`friday`).")
    A("- How likely on a day it can happen (one-off scenes): `rare`, `uncommon`, `sometimes`, `often`, `likely`, `always`, "
      "or `10%`. Storyline scenes don't need one.")
    A("- Repeats: scenes happen once; `repeats every 30 days` lets one come back.")
    A("- Order and gaps: `after <scene title>` (or `after <Storyline>: <title>`), `same day`, `next day`, `a week later`, "
      "`3 days later`, `a month later`.")
    A("- Facts: `if <fact>` / `unless <fact>` (a fact a choice remembered). A fact has to be remembered by a choice "
      "somewhere (`remember <fact>` under it): never wait on a fact nothing sets, or the scene never comes. Situations: `if " + "`, `if ".join(
        k.replace("_", " ") for k in D.REQUIRES) + "`.")
    A("- Feelings and stats: `if bro trust 40+` (how the scene's person feels about you), `if my affection 60+` (how you "
      "feel about them), `if stress 60+`, `if mood 20-`, `if gpa 3.5+`.")
    A("- The sports world: `if pro:<condition>`, like `if pro:my_team_in_playoffs` (your MLB team: "
      + ", ".join(k[4:] for k in pro.REQUIRES if k.count(":") == 1) + "), `if pro:<league>:<condition>` with league nfl, nba, "
      "cfb, mbb, wbb, epl, laliga, seriea, bund, ligue1, ucl, cbase, msoc, wsoc and condition in_season, my_team_winning, "
      "my_team_losing, my_team_in_postseason, my_team_alive, my_team_champs, my_team_ranked (college). A what-if world: "
      "`if pro:whatif:harper_2019`.")
    A("- Who it's with: `with best friend`, `with crush`, `with older sister`, `with coach`, or a cast name. Without it, "
      "the first person who talks is who the scene is about. Kinds of people: " + ", ".join(k.replace("_", " ") for k in sorted(V["who"])) + ".")
    A("- How big: `small`, `regular`, `big` (a turning point), `finale`.")
    A("")
    A("## People and lines")
    A("")
    A("- A plain line is narration, in second person (\"You...\").")
    A("- `name: line` is someone talking: a cast name, `you`, `best friend`, `sibling`, `partner`, or the kind of person the "
      "scene is with (`friend:`, `coach:`).")
    A("- Anyone else can talk too, as a walk-on: `Mom:`, `Dad:`, `Grandma:`, `{teacher}:`, `Coach Reyes:`, `The waiter:`. "
      "They're just a name on the line: the game doesn't track how they feel, so effects go on you (`mood +`), your family "
      "(`family affection +`) or the scene's person.")
    A("- `{bro}` says a cast member's name; `{best friend}`, `{sibling}`, `{partner}`, `{me}` too. The game also fills in "
      + ", ".join("{" + n + "}" for n in sorted(V["names"]) if not n.endswith("_first") and n not in ("them", "best_friend", "sibling", "partner")) + ".")
    A("- `{a|b|c}` gives a line versions; the game rotates them so nothing repeats.")
    A(f"- Room: a scene's opening lines can run about {D.MAX_SCENE_TEXT:,} characters together (15 to 25 lines of back and "
      f"forth); one line up to {D.MAX_LINE}; a choice up to {D.MAX_LABEL}; a title up to {D.MAX_TITLE}. Longer than that, split "
      "it: more lines, or a beat (choices under a choice).")
    A("- A scene can involve your best friend, sibling, partner and anyone in the storyline's cast, plus the one person it's with.")
    A("")
    A("## Choices")
    A("")
    A("- `* <what you say or do>  | <effects>`. 1 to 4 per scene (none at all makes a \"Continue\"). Quotes for things you say.")
    A("- The lines after a choice, down to the next `* `, play after you pick it (indenting them under it works too). Give every "
      "choice at least one line. `remember <fact>` / `forget <fact>` on their own line work too, "
      "and `bro texts: <line>` sends you a text later that day. A line can end in effects too: `bro: Fine. | bro respect +`. "
      "(The scene's opening lines can't: effects only happen when you choose.)")
    A("- `** <choice>` is a choice inside the choice above it: a second round right after it, its lines following it the same "
      "way. (Or indent choices under a choice, up to five deep.)")
    A("- `either way:` on its own line, after the choices: what comes after it plays whichever choice you picked.")
    A("- Outcomes, indented under the choice: after `play <game>` write `great:`, `good:`, `miss:`; after a chance like "
      "`60% +athletic` write `yes:` and `no:`; after `vibe <style>` write `good:`, `meh:`, `bad:`. Each is a line, then | effects.")
    A("- `memory: <text> (good)` gives you a memory (good, great, bad, awful).")
    A("")
    A("## Your games")
    A("")
    A("A storyline decides its games: the scores, your stats and the team's record follow what its scenes say happened.")
    A("")
    A("- A scene after a game says how it went: `[if we won]`, `[if we lost]`, `[if I played great]`, `[if I won it]` (you won "
      "it in the big moment), or just its words (\"we won\", \"that loss\"). In a storyline played in order, your next game "
      "goes that way and the scene comes right after it. (In an outline: end the line with `| if we won`.)")
    A("- Or let the real game decide: two scenes side by side, one `[if we won]` and the next `[if we lost]` (or `[if I played "
      "great]` / `[if I played badly]`, `[if I started]` / `[if I was benched]`). Whichever matches the game plays; the other "
      "never does. `[if rivalry game]` waits for the rival game.")
    A("- Words: `{last_game}` (the 24-21 win over Branford), `{last_opp}`, `{last_score}`, `{my_line}` (6 catches for 98 "
      "yards and a touchdown), `{big_play}` (scored the touchdown late), `{team_record}` (6-2), `{my_season}`.")
    A("- A choice with `| play football` (or basketball, baseball, soccer_11) on your game day is that game's big moment: how "
      "you play it goes in your stat line and can decide a close game.")
    A("")
    A("## Effects")
    A("")
    A("Separate with commas. `+` small, `++` medium, `+++` big, `-` `--` `---` down, or a number like `+5`.")
    A("")
    A("- How someone feels about you: `<person> affection +` (or trust, respect, attraction, rivalry, familiarity). "
      "`both` at the end for both ways; `my <person> affection +` for how you feel about them.")
    A("- You: `mood +`, " + ", ".join(f"`{n} -`" for n in sorted(V["needs"])) + " (energy, social = not lonely, fun, stress).")
    A("- Traits: " + ", ".join(sorted(V["traits"])) + " (also confident, loyal, disciplined...).")
    A("- Skills: " + ", ".join(sorted(V["skills"])) + " (`sport` = your main sport). Interests: `into <x> +` with " +
      ", ".join(sorted(V["interests"])) + ".")
    A("- Reputation: `rep <tag> +` with " + ", ".join(sorted(V["rep"])) + ". Family: `family affection +` (you and every sibling).")
    A("- `play <game>`: " + "; ".join(f"`{g}` ({D.MG_FITS.get(g, '')})" for g in sorted(V["games"] - {"sport"})) +
      "; `sport` = your sport's game.")
    A("- `60% +charisma -impulsivity`: a roll on your talents (" + ", ".join(sorted(V["apt"])) + ") and traits.")
    A("- `vibe <style>`: " + ", ".join(V["vibes"]) + " (lands or misses by what they like).")
    A("- `focus <mode>` (" + ", ".join(sorted(V["focus"])) + "), `hang out with <person>`, `text <person> \"<line>\"`, "
      "`fits loyalty` / `fits -discipline` (who'd pick this when the game picks for you; trait effects count too).")
    if not story_only:
        A("")
        from .storybuilder import TEXTING_FLIRT, TEXTING_GROUP
        A("## Texting: flirting and group chats")
        A("")
        A("Flirt lines and group chat conversations go in their own blocks, in any script (on the phone: Phone > Add texting "
          "writes the ChatGPT prompt for you). They go live as soon as they're added, alongside the game's own.")
        A("")
        A(TEXTING_FLIRT.replace("## Flirting", "### Flirting").rstrip())
        A("")
        A(TEXTING_GROUP.replace("## Group chats", "### Group chats").rstrip())
        A("")
        A("## Lines for the game's pools")
        A("")
        A("A block is a header line and then one entry per line under it (until a blank line or the next header).")
        A("")
        A("- `texts <pool>:` text messages. Pools: " + "; ".join(f"`{k}` ({v[:-1] if v.endswith('.') else v})" for k, v in D.POOL_DOCS.items()) + ".")
        A("- `replies <set>:` buttons you can answer with, each ending in its tone: `on it (warm)`. Sets: "
          + ", ".join(f"`{k}`" for k in D._base_reply_sets()) + ". Tones: " + "; ".join(f"`{k}` ({v.split('.')[0].lower()})" for k, v in D.REPLY_TONES.items()) + ".")
        A("- `narration <key>:` story-feed lines, like `narration study.focused:` (keys: study, practice_skill, hobby, rest, "
          "hang_out and more, each `.focused` / `.distracted`).")
        A("- `mods <open|close|talk> <tag>:` openers (\"ok so\"), closers (\"lol\") and ways of saying things "
          "(\"{them_first} {says}, grinning\"), for a context: " + ", ".join(LN.TAGS) + " (join with +: close+guys).")
        A("- `chat <path>:` texting conversation lines, like `chat reply.greet.warm:`, `chat topic.school:`, "
          "`chat people.older_brother.reply.greet.warm:` (lines for one kind of person), `chat ask.general:` (each ends with "
          "what it asks: (yesno), (doing), (day), (weekend), (open) or (flirty)).")
        A("- `trivia <subject>:` `Question? = right answer | wrong | wrong | wrong (grade 10)`. Subjects: "
          + ", ".join(s for s in __import__("lifeos.trivia", fromlist=["bank"]).bank()["subjects"] if s != "math") + ".")
        A("- `choices <moment>:` more `*` choices on one of the game's own moments (like `choices rumor:`).")
    A("")
    A("## Retiming scenes")
    A("")
    A("`schedule:` (a line on its own inside a storyline) and then one line per scene to retime, from any storyline: "
      "`Same Team: Cut day [sophomore · March · after Prom night]`; `[replace]` replaces its after-links, `[skip]` retires it.")
    A("")
    A("A line can retime a whole storyline: `Same Team [freshman · spread]` puts all of it in freshman year, spread out in "
      "order (holidays and school days keep their day). Names have to match: a scene or storyline that isn't there is an "
      "error, with what it might have meant.")
    A("")
    A("## Writing well")
    A("")
    A("- Real people, real voices: short lines, specific details, how teenagers actually talk. PG-13.")
    A("- Every choice should feel different and matter a little. Use `remember` and `if` so later scenes answer earlier choices.")
    A("- Let scenes breathe: a couple of lines of setup, talk that goes back and forth, a beat or two deep where it matters.")
    A("- Use versions `{a|b}` on lines that come back, and the mini games where they fit.")
    A("- `//` starts a comment the game ignores.")
    return "\n".join(a)


LONG_RULE = """- If it won't all fit in one reply, stop after a whole scene (never in the middle of one) and say "say continue for \
part 2". When I say continue, send the rest as a new code block that starts with `=== <the same title> (part 2)` and \
`expands: <the storyline's title>`, its first scene tagged `after <the last scene you sent>` (and part 3 the same way). \
I add each part as it comes.
"""

PROMPT_NEW = """You're writing for LIFE OS, a life-simulation game: I play one person from the first day of high school \
(Guilford High School in Guilford, Connecticut, fall 2010) through college. The game's stories are written as story \
scripts (the format is below).

## What I want

{ask}

## How to answer

- Reply with ONE code block (```) holding the whole script, and nothing after it.
{long}
- Write a lot, and make it a story: storylines with scenes in order, talk that goes back and forth, choices that matter \
later (remember / if), beats where a scene keeps going, the mini games where they fit, versions {{a|b}} on lines that repeat.
- Follow the format and the lists exactly. The game checks every line and tells me what to fix by line number.

"""

PROMPT_CONTINUE = """You're building out one of my storylines for LIFE OS, a life-simulation game: I play one person from \
the first day of high school (Guilford High School in Guilford, Connecticut, fall 2010) through college. Here's the \
storyline as it is now, in the game's story script format (described below).

## What I want

{ask}

## The storyline

```
{script}
```

## How to answer

- Send back the COMPLETE storyline as ONE code block (```), starting with the same `=== {title}` line (it replaces the \
old one), and nothing after it.
- Keep what's there unless I asked to change it; keep scene titles the same so my progress stays.
- Follow the format and the lists exactly. The game checks every line and tells me what to fix by line number.

"""

PROMPT_TEXTING = """I want the people in one of my LIFE OS storylines to text like themselves. LIFE OS is a life-simulation \
game (high school in Guilford, Connecticut, fall 2010, through college). Here's the storyline:

```
{script}
```

Write texting lines for its people as `chat` blocks (format below), using the most specific kind of person for each \
(`chat people.older_brother.reply.greet.warm:`): for each person at least reply.greet (warm, ok, cold), reply.chat (warm, \
ok, cold), reply.ask (warm, ok, cold), reply.joke (laugh, meh), reply.plans (yes, no, already), reply.vent (comfort, meh), \
ask.general (questions they'd text back, each ending in what it asks: (yesno), (doing), (day), (weekend), (open) or \
(flirty)), topic (game, school, music, weekend, food), close (nice, tired, cold), and suggest (greet, ask, joke, plans: \
things I'd text them). For a crush, partner or ex also reply.flirt (landed, playful, awkward, shut) and ask.flirty. At \
least 6 lines in every list, short like real texts.

Reply with ONE code block (```) that starts with `=== {title} texting` and holds only the chat blocks, nothing after it.

"""

PROMPT_PLAN = """Here are all my LIFE OS storylines (a life sim: high school in Guilford, Connecticut, fall 2010, through \
college junior year), as the scene lines with their tags:

{headers}
{current}
## What I want

{ask}

## How to answer

Reply with ONE code block (```) that starts with `=== Season plan`, and nothing after it. In it:

- a `schedule:` block: a line per scene you want to move or link, `<Storyline>: <Scene title> [new tags]` (school year, \
months, after <Storyline>: <Scene>, a gap, before/after a date, how big; [replace] replaces its after-links, [skip] \
retires it). Only the scenes that change. To move a whole storyline into one year, one line does it: \
`<Storyline> [freshman · spread]` (all of it in that year, spread out in order). Use the titles exactly as listed.
- crossover scenes where storylines meet, if they'd help: `--- Title [tags · after <Storyline>: <Scene>]`, written like \
any scene (with `order: any` under the title if they don't go in a row). Copy the cast: lines of anyone who talks in \
them from the storylines above.
{keep}
"""


def prompt_new(ask: str = "") -> str:
    return PROMPT_NEW.format(ask=(ask or "").strip() or "[describe it here: who it's about, what happens, which years]",
                             long=LONG_RULE.rstrip("\n")) + guide()


def prompt_continue(text: str, title: str, ask: str = "") -> str:
    return PROMPT_CONTINUE.format(ask=(ask or "").strip() or "Make it bigger and better: more scenes, more back and forth, "
                                  "choices that come back later.", script=text.strip(), title=title) + guide(story_only=True)


def prompt_texting(text: str, title: str) -> str:
    return PROMPT_TEXTING.format(script=text.strip(), title=title) + guide()


def prompt_plan(headers: str, ask: str = "", current: str | None = None) -> str:
    cur = (f"\n## My season plan now\n\n```\n{current.strip()}\n```\n") if current else ""
    keep = ("\nYour answer replaces my season plan: send it back whole, with what's in it now kept unless I asked to change "
            "it.\n") if current else ""
    return PROMPT_PLAN.format(headers=headers, current=cur, keep=keep, ask=(ask or "").strip() or "Make all of it one story "
                              "across the years: spread the scenes over the seasons and link storylines where they'd cross.") \
        + guide(story_only=True)


# ---------------------------------------------------------------------------------------------------- outline, then batches
WHEN_WORDS = ("a month (September ... August), a season (fall, winter, spring, summer), a holiday (Halloween, Thanksgiving, "
              "Christmas Eve, New Year's Eve, Valentine's Day, Easter, Mother's Day, July 4th...), a school day (first day of "
              "school, homecoming, homecoming week, prom, finals week, spring break, winter break, last day of school, "
              "graduation), weekend, a school year (sophomore) if it's not the storyline's, and big for a turning point. Or "
              "leave it empty and the game spaces it out.")

OUTLINE_PROMPT = """You're planning a storyline for LIFE OS, a life-simulation game: I play one person from the first day of \
high school (Guilford High School in Guilford, Connecticut, fall 2010) through college. First we make an OUTLINE: one line \
per scene. Then I'll ask you to write the scenes a few at a time.

## What I want

{ask}

## The people around me (cast them by name)

{people}
{existing}
## How to answer

Reply with ONE code block (```) and nothing after it, exactly in this shape:

```
=== {title_hint}
{expands_line}cast: mike = Mike Soffer
years: freshman
about: one or two sentences: what this storyline is about.

outline:
1. Saved You a Seat | September | Mike saves you a seat on the bus on the first day.
2. The Passenger Seat | | Mike drives you to school for the first time and lays down the rules.
3. Tryouts | November · big | You both try out; only one of you is sure to make it.
4. Turkey Day | Thanksgiving | Mike is off at dinner and won't say why.
5. The Fight | December | You fight about playing time.
6. Making Up | | Mike comes around. | only if you picked "Say sorry" in 5
```

- {size}. Number them in the order they happen.
- `cast:` lines for the people in it: a short lowercase name, then their full name from the list above (`cast: mike = Mike \
Soffer`), or who they are if they aren't on it (`cast: kayla = friend of ally, girl`; `cast: coach = coach`). Mom, Dad, \
teachers and other walk-ons don't need a cast line.
- `years:` the school years it covers: {years_words} (or a range: freshman-sophomore).
- Each line: number, title, when, what happens. When is {when_words}
- A branch: add `| only if you picked "<a choice>" in <number>` (or `unless you picked ...`) to a scene that only happens \
after a certain choice in an earlier scene. Use them for the moments that matter, not everywhere.
- Make it a story: a beginning, turns, a payoff. Spread it through the year; put holiday and school-day moments on them.
- A scene after one of my games: say how it went by ending the line with `| if we won` or `| if we lost` (or `| if I \
played great`): the game goes that way, and the score, my stats and the record match. (Want the real game to decide \
instead? Write both ways side by side, `| if we won` then `| if we lost`, and whichever happens plays.)
"""

BATCH_PROMPT = """You're writing scenes for a LIFE OS storyline (a life-simulation game: I play one person from high school \
in Guilford, Connecticut, fall 2010, through college). Here's its outline; write the scenes I ask for, in the game's \
story script format (below).

## The storyline

```
{header}
```

## The outline

{outline}
{previous}
## Write now

{scenes}: {which}.{needs}

## Fill in this template

Keep every `---` line exactly as it is. Replace each <...> with the real thing (no brackets left), add as many lines as \
the scene needs, and keep the shape: setup, the back-and-forth, then the question, then the choices with what happens \
after each.

```
{template}
```

Reply with ONE code block (```) holding just those scenes, each starting with `--- <number>. <title>` (like \
`--- {first}. {first_title}`), nothing after the block. No tags in [ ] and no `after` or `if`: the game times them and \
plays them in order from the outline (and a line ending `| if we won` makes the game go that way: write it as if it did). Each scene: a couple of lines of setup, real back-and-forth (15 to 25 lines is \
plenty), then it ENDS ON A QUESTION (someone asks me something, or it's my move) with 2 to 4 choices that matter, and \
what happens after EVERY choice. A scene with no choices, or only one, doesn't count as written. Write every scene all the way to its end: if \
you're running out of room, write fewer scenes, never cut one short.

How choices work (no indenting needed):
- `* ` starts a choice. The lines after it, down to the next `* `, are what happens after you pick it: their answer, \
`remember` lines. Every choice gets at least one line.
- `** ` is a choice inside the choice above it (a second round right after it); its lines follow it the same way.
- `either way:` on its own line: what comes after it plays whichever choice you picked.
- Effects go after `|` on the choice (`* "Front row." | nicole affection +`), never in parentheses or after an arrow.
- Narration is a plain line: no *italics*, no **bold** names, no "Choice 1:" or "Outcome:" labels.

```
--- 1. Example
nicole: You actually came.
nicole: Where are we sitting?
* "Front row." | nicole affection +
nicole: Front row, then. Come on.
** "Lead the way." | nicole affection +
remember sat_front_row
** "Actually, the back's fine."
nicole: You're impossible.
* "My mom made me."
nicole: Wow. Thanks.
either way:
nicole: Anyway. The game's starting.
```

---

"""


def scene_template(n: int, title: str, choices: int = 3, must: str | None = None) -> str:
    """One scene to fill in: its exact header, then the shape every scene has (setup, talk, the question, the choices)."""
    L = [f"--- {n}. {title}", "<a line or two of setup>", "<the back-and-forth: who says what, 10 to 20 lines>",
         "<the question: someone asks me something, or it's my move>"]
    for i in range(1, choices + 1):
        lab = f"<a choice like “{must}”>" if must and i == 1 else f"<choice {i}>"
        L += [f'* "{lab}"', "<what happens after it: their answer, 2 to 5 lines>"]
    return "\n".join(L)


def guide_scenes() -> str:
    """The parts of the guide a batch of scenes needs: people and lines, choices, effects, writing well (no tags, timing
    or storyline wiring: an outlined storyline gets those from its outline)."""
    g = guide(story_only=True)
    keep = []
    for part in re.split(r"(?m)^(?=## )", g):
        head = part.split("\n", 1)[0].strip()
        if head in ("## People and lines", "## Choices", "## Your games", "## Effects", "## Writing well"):
            keep.append(part.rstrip())
    return "# LIFE OS story scripts: writing scenes\n\n" + "\n\n".join(keep) + "\n"


def outline_entries(pack: dict) -> list:
    return pack.get("outline") or []


def batch_plan(pack: dict, count: int = 6) -> tuple:
    """The next scenes to write: the first unwritten ones in the outline, up to count. (first, last, [entries])"""
    todo = [e for e in outline_entries(pack) if not e.get("written")]
    take = todo[:count]
    return (take[0]["n"], take[-1]["n"], take) if take else (None, None, [])

