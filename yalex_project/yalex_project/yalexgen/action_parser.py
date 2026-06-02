from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ActionInfo:
    kind: str
    token_name: Optional[str] = None
    raw: str = ''
    argument: Optional[str] = None


RETURN_LEXBUF = re.compile(r'^return\s+lexbuf\s*;?\s*$')
RETURN_NAME = re.compile(r'^return\s+([A-Za-z_][A-Za-z0-9_]*)\s*;?\s*$')
RETURN_CALL = re.compile(r'^return\s+([A-Za-z_][A-Za-z0-9_]*)\((.*)\)\s*;?\s*$')
RAISE_CALL = re.compile(r'^raise\s*\((.*)\)\s*;?\s*$')


def parse_action(action_text: str) -> ActionInfo:
    action = ' '.join(action_text.strip().split())
    if not action:
        return ActionInfo(kind='raw', raw='')
    if RETURN_LEXBUF.match(action):
        return ActionInfo(kind='skip', raw=action_text)
    m = RETURN_CALL.match(action)
    if m:
        return ActionInfo(kind='return_call', token_name=m.group(1), argument=m.group(2).strip(), raw=action_text)
    m = RETURN_NAME.match(action)
    if m:
        return ActionInfo(kind='return_name', token_name=m.group(1), raw=action_text)
    m = RAISE_CALL.match(action)
    if m:
        return ActionInfo(kind='raise', raw=action_text, argument=m.group(1).strip())
    return ActionInfo(kind='raw', raw=action_text)
