"""Configurable rules: schema, defaults, validation and versioning.

The schema (data/rules_schema.json) lists every tunable parameter with type, range and
description. Values are plain dicts keyed by dotted names ("motive.approval"); the
engine reads them directly. Changes go through validate() so out-of-range or unknown
values are rejected before they can reach a simulation.
"""
from __future__ import annotations

import hashlib
import json

from .catalogs import load_json


class RulesError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class RuleSchema:
    def __init__(self, doc: dict | None = None):
        doc = doc or load_json("rules_schema.json")
        self.version = doc["version"]
        self.sections = doc["sections"]
        self.params: dict[str, dict] = {}
        for sec in self.sections:
            for p in sec["params"]:
                p = dict(p)
                p["section"] = sec["id"]
                self.params[p["key"]] = p

    def defaults(self) -> dict:
        return {k: p["default"] for k, p in self.params.items()}

    def coerce(self, key: str, value):
        p = self.params[key]
        t = p["type"]
        if t == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str) and value.lower() in ("true", "false", "1", "0", "yes", "no"):
                return value.lower() in ("true", "1", "yes")
            if isinstance(value, (int, float)) and value in (0, 1):
                return bool(value)
            raise ValueError(f"{key}: expected true/false, got {value!r}")
        if isinstance(value, bool):
            raise ValueError(f"{key}: expected a number, got {value!r}")
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{key}: expected a number, got {value!r}")
        if num != num or num in (float("inf"), float("-inf")):
            raise ValueError(f"{key}: not a finite number")
        if t == "int":
            if abs(num - round(num)) > 1e-9:
                raise ValueError(f"{key}: expected a whole number, got {value!r}")
            num = int(round(num))
        lo, hi = p.get("min"), p.get("max")
        if lo is not None and num < lo:
            raise ValueError(f"{key}: {num} is below the minimum {lo}")
        if hi is not None and num > hi:
            raise ValueError(f"{key}: {num} is above the maximum {hi}")
        return num

    def validate(self, changes: dict) -> dict:
        """Return coerced changes or raise RulesError listing every problem."""
        out, errors = {}, []
        for key, value in changes.items():
            if key not in self.params:
                errors.append(f"{key}: unknown parameter")
                continue
            try:
                out[key] = self.coerce(key, value)
            except ValueError as e:
                errors.append(str(e))
        if errors:
            raise RulesError(errors)
        return out

    def validate_full(self, values: dict) -> dict:
        merged = self.defaults()
        merged.update(self.validate({k: v for k, v in values.items()}))
        cross = []
        if merged["rel.friend_threshold"] >= merged["rel.close_threshold"]:
            cross.append("rel.friend_threshold must be below rel.close_threshold")
        if merged["rel.close_threshold"] >= merged["rel.best_threshold"]:
            cross.append("rel.close_threshold must be below rel.best_threshold")
        if cross:
            raise RulesError(cross)
        return merged


def rules_hash(values: dict) -> str:
    return hashlib.sha1(json.dumps(values, sort_keys=True).encode()).hexdigest()[:10]


_SCHEMA: RuleSchema | None = None


def schema() -> RuleSchema:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = RuleSchema()
    return _SCHEMA
