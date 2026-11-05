"""Data catalogs: actions, world template, people, narrative templates, goals.

Catalogs are JSON files in backend/data. A world can carry action overrides (edits made in
the Engine Workshop) which are layered over the base catalog, so saves and experiments
keep the exact action numbers they ran with.
"""
from __future__ import annotations

import copy
import json
import os
from functools import lru_cache

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

TRAITS = ["sociability", "confidence", "discipline", "ambition", "impulsivity",
          "empathy", "competitiveness", "curiosity", "volatility", "loyalty"]
APTITUDES = ["athletic", "academic", "creativity", "technical", "charisma"]
MOTIVES = ["achievement", "approval", "belonging", "pleasure", "altruism", "mastery"]
NEEDS = ["energy", "social", "fun", "stress"]

ATTRIBUTE_DOCS = {
    "traits": {
        "layer": "Stable tendencies",
        "about": "Personality. Changes very slowly (confidence drifts with success and failure).",
        "items": {
            "sociability": "Seeks out company; drains faster when alone.",
            "confidence": "Willing to risk rejection; overestimates how things went.",
            "discipline": "Follows through on practice, study and commitments.",
            "ambition": "Wants to get somewhere; values long-term payoffs.",
            "impulsivity": "Acts on the moment; adds randomness and risk tolerance.",
            "empathy": "Reads others accurately; dislikes cruelty; helps.",
            "competitiveness": "Wants to win; forms rivalries with peers at a similar level.",
            "curiosity": "Open to new things; enjoys learning.",
            "volatility": "Emotional reactivity: bigger swings, quicker to confront.",
            "loyalty": "Sticks with people and commitments.",
        },
    },
    "aptitudes": {
        "layer": "Natural aptitude",
        "about": "Innate potential. Sets how fast a skill grows and how high it can go.",
        "items": {
            "athletic": "Sports.", "academic": "Schoolwork and writing.", "creativity": "Art and music.",
            "technical": "Robotics and code.", "charisma": "Acting and first impressions.",
        },
    },
    "skills": {"layer": "Learned capability", "about": "Grows with practice, fades without it.", "items": {}},
    "motives": {
        "layer": "Motivations",
        "about": "What this person wants. Multiplied by the global motive weights in the Workshop.",
        "items": {
            "achievement": "Grades, teams, winning.", "approval": "Status and being liked by the crowd.",
            "belonging": "Closeness and group membership.", "pleasure": "Fun now.",
            "altruism": "Helping others.", "mastery": "Getting good at a craft for its own sake.",
        },
    },
    "needs": {
        "layer": "Current condition",
        "about": "Temporary states that drain and recover daily. Energy/social/fun: high is good. Stress: high is bad.",
        "items": {"energy": "Physical energy.", "social": "Connection (low = lonely).", "fun": "Stimulation (low = bored).", "stress": "Pressure and worry."},
    },
}


def load_json(name: str) -> dict:
    with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def _base(name: str) -> dict:
    return load_json(name)


class CatalogError(ValueError):
    pass


ACTION_NUMERIC_FIELDS = ("base", "risk", "interest", "obligation", "importance")
ACTION_DICT_FIELDS = ("needs", "motives", "traits", "target_terms", "params")


class Catalogs:
    """Read-only view of the catalogs plus a world's action overrides."""

    def __init__(self, action_overrides: dict | None = None):
        self.world = _base("world.json")
        self.people = _base("people.json")
        from . import dialogue  # base content plus any dialogue packs
        self.templates = dialogue.templates()
        self.goals = _base("goals.json")["goals"]
        self.sports = _base("sports.json")
        self.colleges = _base("colleges.json")["colleges"]
        self.college_by_id = {c["id"]: c for c in self.colleges}
        self.moments = dialogue.moments()
        self.action_overrides = copy.deepcopy(action_overrides or {})
        self._build_actions()
        self.skills = {s["id"]: s for s in self.world["skills"]}
        self.hobbies = {h["id"]: h for h in self.world["hobbies"]}
        self.places = {p["id"]: p for p in self.world["places"]}
        self.group_defs = {g["id"]: g for g in self.world["groups"]}

    def _build_actions(self):
        base = _base("actions.json")["actions"]
        self.actions: dict[str, dict] = {}
        for a in base:
            a = copy.deepcopy(a)
            ov = self.action_overrides.get(a["id"])
            if ov:
                for k, v in ov.items():
                    if k in ACTION_DICT_FIELDS and isinstance(v, dict):
                        a.setdefault(k, {})
                        a[k].update(v)
                    else:
                        a[k] = v
            a.setdefault("needs", {})
            a.setdefault("motives", {})
            a.setdefault("traits", {})
            a.setdefault("target_terms", {})
            a.setdefault("requires", [])
            a.setdefault("params", {})
            a.setdefault("interest", 0.0)
            a.setdefault("obligation", 0.0)
            a.setdefault("risk", 0.0)
            a["enabled"] = a.get("enabled", True)
            self.actions[a["id"]] = a
        self.by_slot: dict[str, list[dict]] = {}
        for a in self.actions.values():
            if not a["enabled"]:
                continue
            for s in a["slots"]:
                self.by_slot.setdefault(s, []).append(a)

    def base_action(self, action_id: str) -> dict:
        for a in _base("actions.json")["actions"]:
            if a["id"] == action_id:
                return copy.deepcopy(a)
        raise CatalogError(f"unknown action {action_id}")

    def validate_action_override(self, action_id: str, changes: dict) -> dict:
        if action_id not in self.actions:
            raise CatalogError(f"unknown action {action_id}")
        base = self.base_action(action_id)
        out, errors = {}, []
        for k, v in changes.items():
            if k == "enabled":
                if not isinstance(v, bool):
                    errors.append("enabled must be true/false")
                else:
                    out[k] = v
            elif k in ACTION_NUMERIC_FIELDS:
                try:
                    num = float(v)
                except (TypeError, ValueError):
                    errors.append(f"{k} must be a number")
                    continue
                lim = 100 if k == "importance" else 50
                if not (-lim <= num <= lim):
                    errors.append(f"{k} must be between -{lim} and {lim}")
                    continue
                out[k] = num
            elif k in ("needs", "motives", "traits", "target_terms"):
                if not isinstance(v, dict):
                    errors.append(f"{k} must be an object")
                    continue
                allowed = {"needs": NEEDS, "motives": MOTIVES, "traits": TRAITS}.get(k)
                sub = {}
                for kk, vv in v.items():
                    if allowed is not None and kk not in allowed:
                        errors.append(f"{k}.{kk} is not a known {k[:-1]}")
                        continue
                    if k == "target_terms" and kk not in base.get("target_terms", {}):
                        errors.append(f"target_terms.{kk}: this action has no such term")
                        continue
                    try:
                        num = float(vv)
                    except (TypeError, ValueError):
                        errors.append(f"{k}.{kk} must be a number")
                        continue
                    if not (-10 <= num <= 10):
                        errors.append(f"{k}.{kk} must be between -10 and 10")
                        continue
                    sub[kk] = num
                out[k] = sub
            else:
                errors.append(f"{k} cannot be edited here")
        if errors:
            raise CatalogError("; ".join(errors))
        return out
