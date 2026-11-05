"""World state: characters, directed relationships, bonds, households, groups, rumors.

Layers on a character are kept apart on purpose:
  traits      stable tendencies (personality)
  aptitudes   innate potential (sets skill growth rate and ceiling)
  skills      learned capabilities (grow with practice, fade without)
  motives     what the person wants (weights on kinds of payoff)
  needs/mood  temporary condition (drain and recover daily)
  household, money, memberships, flags  external circumstances
  memories, expectations, habits        experience

Relationships are directed: rels[(a, b)] is how a sees b. b's view of a is a separate
record. Formal roles (sibling, partner, ex) live in bonds, keyed by the unordered pair.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields


@dataclass
class Character:
    id: str
    first: str
    last: str
    gender: str
    pronouns: str
    role: str
    grade: int | None
    birth_day: int
    household_id: str | None
    archetype: str
    attracted_to: list = field(default_factory=list)
    bio: str = ""
    color: str = "#7c8cff"
    title: str = ""
    role_label: str = ""
    featured: bool = False
    status: str = "active"
    traits: dict = field(default_factory=dict)
    aptitudes: dict = field(default_factory=dict)
    skills: dict = field(default_factory=dict)
    motives: dict = field(default_factory=dict)
    needs: dict = field(default_factory=dict)
    mood: float = 60.0
    interests: dict = field(default_factory=dict)
    goals: list = field(default_factory=list)
    memories: list = field(default_factory=list)
    expectations: dict = field(default_factory=dict)
    habits: dict = field(default_factory=dict)
    reputation: dict = field(default_factory=dict)
    popularity: float = 30.0
    money: float = 20.0
    gpa: float = 3.0
    study_ema: float = 0.0
    flags: dict = field(default_factory=dict)
    memberships: list = field(default_factory=list)
    past_memberships: list = field(default_factory=list)
    achievements: list = field(default_factory=list)
    counters: dict = field(default_factory=dict)
    recent_actions: list = field(default_factory=list)
    # where they are and where they go to school ("hchs", "college", "away:<college id>", None)
    school: str | None = "hchs"
    location: str = "hollow_creek"
    # athlete details
    body: dict = field(default_factory=dict)        # {"height_in": 70, "build": "athletic"}
    positions: dict = field(default_factory=dict)   # {"football": "RB", ...}
    jersey: int = 0
    stats: dict = field(default_factory=dict)       # "football:2025:varsity" -> {games, line, team, level}
    awards: list = field(default_factory=list)
    recruiting: dict = field(default_factory=dict)  # {"interest": {...}, "offers": [...], "admits": [...]}
    path: dict = field(default_factory=dict)        # after high school: {"kind": "college"|"work", ...}
    gpa_history: list = field(default_factory=list)
    custom: bool = False                            # created by the user
    look: dict = field(default_factory=dict)        # appearance set in the builder (generated values fill the rest)

    @property
    def year_label(self) -> str:
        if self.role == "staff":
            return self.role_label or "Staff"
        if self.grade and self.grade <= 12:
            return {9: "Freshman", 10: "Sophomore", 11: "Junior", 12: "Senior"}[self.grade]
        if self.grade and self.grade > 12:
            return ["College freshman", "College sophomore", "College junior", "College senior"][min(3, self.grade - 13)]
        return "Graduate"

    @property
    def name(self) -> str:
        if self.role == "staff" and self.title:
            return f"{self.title} {self.last}"
        return f"{self.first} {self.last}"

    @property
    def short(self) -> str:
        if self.role == "staff" and self.title:
            return f"{self.title} {self.last}"
        return self.first

    def age(self, day: int) -> int:
        return int((day - self.birth_day) // 365.25)

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, d: dict) -> "Character":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})


@dataclass(slots=True)
class Rel:
    src: str
    dst: str
    familiarity: float = 0.0
    affection: float = 0.0
    respect: float = 0.0
    attraction: float = 0.0
    trust: float = 30.0
    rivalry: float = 0.0
    perceived: float = 0.0
    met_day: int = -1
    last_day: int = -1
    pos: int = 0
    neg: int = 0
    label: str = "stranger"
    crush: bool = False
    peak_affection: float = 0.0
    milestones: list = field(default_factory=list)
    recent: list = field(default_factory=list)

    def to_list(self) -> list:
        return [self.src, self.dst, self.familiarity, self.affection, self.respect, self.attraction, self.trust,
                self.rivalry, self.perceived, self.met_day, self.last_day, self.pos, self.neg, self.label, self.crush,
                self.peak_affection, self.milestones, self.recent]

    @classmethod
    def from_list(cls, x: list) -> "Rel":
        return cls(*x)

    def to_dict(self) -> dict:
        return {"src": self.src, "dst": self.dst, "familiarity": self.familiarity, "affection": self.affection,
                "respect": self.respect, "attraction": self.attraction, "trust": self.trust, "rivalry": self.rivalry,
                "perceived": self.perceived, "met_day": self.met_day, "last_day": self.last_day, "pos": self.pos,
                "neg": self.neg, "label": self.label, "crush": self.crush, "peak_affection": self.peak_affection,
                "milestones": self.milestones, "recent": self.recent}


REL_FIELDS = {"familiarity": (0, 100), "affection": (-100, 100), "respect": (-100, 100), "attraction": (0, 100),
              "trust": (0, 100), "rivalry": (0, 100), "perceived": (-100, 100)}


def pair_key(a: str, b: str) -> str:
    return f"{a}|{b}" if a < b else f"{b}|{a}"


class World:
    """The single authoritative simulation state. Everything that matters is in here."""

    def __init__(self):
        self.name = "Guilford"
        self.gen_seed = 0
        self.seed = 0
        self.day = 0
        self.phase = 0
        self.year = 0
        self.chars: dict[str, Character] = {}
        self.rels: dict[tuple, Rel] = {}
        self.out: dict[str, dict[str, Rel]] = {}
        self.bonds: dict[str, dict] = {}
        self.households: dict[str, dict] = {}
        self.groups: dict[str, dict] = {}
        self.cliques: dict[str, dict] = {}
        self.rumors: dict[str, dict] = {}
        self.calendar: list[dict] = []
        self.registrations: dict[str, list] = {}
        self.parties: dict[str, dict] = {}
        self.dance_dates: dict[str, dict] = {}
        self.schedule: list[dict] = []
        self.rules: dict = {}
        self.rule_changes: list[dict] = []
        self.action_overrides: dict = {}
        self.stats_series: list[dict] = []
        self.counters: dict = {"char": 0, "goal": 0, "mem": 0, "rumor": 0, "clique": 0, "household": 0}
        self.history = None  # History, attached by the engine
        self.tracing = True
        self.meta: dict = {}

    # relationships -------------------------------------------------------
    def rel(self, a: str, b: str) -> Rel | None:
        return self.rels.get((a, b))

    def ensure_rel(self, a: str, b: str, day: int) -> Rel:
        r = self.rels.get((a, b))
        if r is None:
            r = Rel(a, b, met_day=day, last_day=day)
            self.rels[(a, b)] = r
            self.out.setdefault(a, {})[b] = r
        return r

    def bond(self, a: str, b: str) -> dict | None:
        return self.bonds.get(pair_key(a, b))

    def has_role(self, a: str, b: str, role: str) -> bool:
        bd = self.bonds.get(pair_key(a, b))
        return bool(bd and role in bd["roles"])

    def partner_of(self, cid: str) -> str | None:
        return self.chars[cid].flags.get("partner")

    def students(self) -> list[Character]:
        return [c for c in self.chars.values() if c.role == "student" and c.status == "active"]

    def active(self) -> list[Character]:
        return [c for c in self.chars.values() if c.status == "active"]

    def next_id(self, kind: str) -> int:
        self.counters[kind] = self.counters.get(kind, 0) + 1
        return self.counters[kind]

    # serialization -------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "format": "lifeos-world/1",
            "name": self.name, "gen_seed": self.gen_seed, "seed": self.seed, "day": self.day, "phase": self.phase,
            "year": self.year,
            "chars": [c.to_dict() for c in self.chars.values()],
            "rels": [r.to_list() for r in self.rels.values()],
            "bonds": self.bonds, "households": self.households, "groups": self.groups, "cliques": self.cliques,
            "rumors": self.rumors, "calendar": self.calendar, "registrations": self.registrations,
            "parties": self.parties, "dance_dates": self.dance_dates, "schedule": self.schedule,
            "rules": self.rules, "rule_changes": self.rule_changes, "action_overrides": self.action_overrides,
            "stats_series": self.stats_series, "counters": self.counters, "meta": self.meta,
            "history": self.history.to_dict() if self.history is not None else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "World":
        from .history import History
        w = cls()
        for k in ("name", "gen_seed", "seed", "day", "phase", "year", "bonds", "households", "groups", "cliques",
                  "rumors", "calendar", "registrations", "parties", "dance_dates", "schedule", "rules",
                  "rule_changes", "action_overrides", "stats_series", "counters", "meta"):
            if k in d:
                setattr(w, k, d[k])
        for cd in d["chars"]:
            c = Character.from_dict(cd)
            w.chars[c.id] = c
        for x in d["rels"]:
            r = Rel.from_list(x)
            w.rels[(r.src, r.dst)] = r
            w.out.setdefault(r.src, {})[r.dst] = r
        w.history = History.from_dict(d.get("history") or {})
        return w
