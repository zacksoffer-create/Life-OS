"""Second person for the phone: "Zack sat with Danny at lunch" becomes "You sat with Danny at lunch".

Event text is written in the third person so the lab can read it about anyone. On the phone, the
story is yours, so lines about the protagonist are rewritten. This is presentation only.
"""
from __future__ import annotations

import re

VERB_FIX = {"was": "were", "is": "are", "has": "have", "does": "do", "wasn't": "weren't", "isn't": "aren't",
            "hasn't": "haven't", "doesn't": "don't", "plans": "plan", "wants": "want", "gets": "get", "makes": "make",
            "takes": "take", "feels": "feel", "needs": "need", "says": "say", "thinks": "think", "goes": "go", "knows": "know",
            "likes": "like", "loves": "love", "starts": "start", "keeps": "keep", "considers": "consider", "reports": "report",
            "finished": "finished", "seems": "seem", "looks": "look", "gives": "give", "tries": "try", "hopes": "hope"}


NOT_VERBS = {"is", "was", "has", "does", "us", "as", "his", "this", "plus", "always", "perhaps", "towards", "across", "less", "unless",
             "yes", "thus", "its", "guys", "s", "yourself", "yours", "afterwards", "besides"}


def _agree(word: str) -> str:
    """Third-person singular verb -> second person ('thinks' -> 'think', 'tries' -> 'try', "wasn't" -> "weren't")."""
    if word in VERB_FIX:
        return VERB_FIX[word]
    if word in NOT_VERBS or len(word) < 4 or not word.endswith("s") or word.endswith("ss") or word.endswith("us") or word.endswith("'s"):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "sses", "xes", "zes", "oes")):
        return word[:-2]
    return word[:-1]


def second_person(text: str, c, solo: bool = False) -> str:
    """Rewrite references to character c as 'you'. solo=True also rewrites they/their (no one else in the line)."""
    if not text or c is None:
        return text
    names = sorted({c.name, c.first, getattr(c, "short", c.first)}, key=len, reverse=True)
    pat = "|".join(re.escape(n) for n in names if n)
    if not pat:
        return text
    out = re.sub(rf"\b(?:{pat})'s\b", "your", text)
    out = re.sub(rf"\b(?:{pat})\b", "you", out)
    if solo:
        out = re.sub(r"\bthemselves\b", "yourself", out)
        out = re.sub(r"\btheir\b", "your", out)
        out = re.sub(r"\bthey\b", "you", out)
        out = re.sub(r"\bthem\b", "you", out)
    # verb agreement right after "you" (allowing one adverb in between: "you now thinks" -> "you now think")
    out = re.sub(r"\byou ((?:now|only|also|still|finally|really|never|always|just|quietly|actually|officially|even|already) )?([a-z]+n't|[a-z]+)\b",
                 lambda m: "you " + (m.group(1) or "") + _agree(m.group(2)), out)
    out = re.sub(r"^([Yy]ou\b.*?\bone of) their\b", r"\1 your", out)
    out = re.sub(r"\byou and (\w+) (was|is|has)\b", lambda m: f"you and {m.group(1)} " + {"was": "were", "is": "are", "has": "have"}[m.group(2)], out)
    # sentence starts
    out = re.sub(r"(^|[.!?]\s+|\"\s*)you\b", lambda m: m.group(1) + "You", out)
    out = re.sub(r"(^|[.!?]\s+)your\b", lambda m: m.group(1) + "Your", out)
    out = out.replace("you yourself", "you")
    return out


def event_line(w, ev, pid) -> str:
    c = w.chars.get(pid)
    text = ev.get("text") or ""
    others = [x for x in (ev.get("actors") or []) + (ev.get("targets") or []) if x != pid]
    return second_person(text, c, solo=not others)
