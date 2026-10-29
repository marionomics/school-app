"""@mentions: parsing, and deciding who a submission's team is.

Spec: docs/superpowers/specs/2026-10-28-menciones-equipos-design.md
"""
import re
from typing import List

# The UserUpdate username pattern. Not preceded by a word character, so an
# email address is not a mention; not followed by one, so @ + 21 letters is
# not a truncated username.
MENTION_RE = re.compile(r"(?<![A-Za-z0-9_@])@([A-Za-z0-9_]{3,20})(?![A-Za-z0-9_])")


def parse_usernames(content: str) -> List[str]:
    out: List[str] = []
    for m in MENTION_RE.finditer(content or ""):
        name = m.group(1).lower()
        if name not in out:
            out.append(name)
    return out
