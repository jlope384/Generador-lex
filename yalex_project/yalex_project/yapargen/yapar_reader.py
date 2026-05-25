from __future__ import annotations

import re
from pathlib import Path

from .token_contract import YAParSpec

# Matches:  %token  ID  NUMBER  PLUS  ...
_TOKEN_LINE = re.compile(r"^\s*%token\s+(.+)$")
# Matches:  %ignore  WS  COMMENT  ... (with percent sign)
_IGNORE_LINE = re.compile(r"^\s*%ignore\s+(.+)$")
# Matches:  IGNORE  WS  COMMENT  ... (bare keyword, no percent sign)
_BARE_IGNORE_LINE = re.compile(r"^\s*IGNORE\s+(.+)$")
# Section separator (YACC-style %%  or  //-style ---PRODUCTIONS---)
_SECTION_SEP = re.compile(r"^\s*%%\s*$")
# /* ... */ block comments (may span multiple lines)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


class YAParReadError(ValueError):
    """Raised when the .yapar source cannot be understood."""


def read_file(path: str | Path) -> YAParSpec:
    """Read a .yapar / .yalp file and return a :class:`YAParSpec`.

    Parses the header directives (``%token``, ``%ignore``) and captures
    everything after the ``%%`` separator as the raw productions string.

    Args:
        path: Path to the ``.yapar`` or ``.yalp`` file.

    Returns:
        A :class:`~yapargen.token_contract.YAParSpec` with the declared
        token names, ignore names, and the unparsed production text.

    Raises:
        FileNotFoundError: If *path* does not exist.
        YAParReadError:    If no ``%token`` directive is found or the source
                           is otherwise malformed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"YAPar file not found: {path}")

    return read_string(path.read_text(encoding="utf-8"), source=str(path))


def read_string(src: str, *, source: str = "<string>") -> YAParSpec:
    """Parse .yapar source from a string and return a :class:`YAParSpec`.

    Args:
        src:    Raw text of the .yapar specification.
        source: Optional label used in error messages (e.g. the file path).

    Returns:
        A populated :class:`~yapargen.token_contract.YAParSpec`.

    Raises:
        YAParReadError: If no ``%token`` directive is found.
    """
    src = _BLOCK_COMMENT.sub("", src)

    tokens: list[str] = []
    seen_tokens: set[str] = set()
    ignore: list[str] = []
    seen_ignore: set[str] = set()
    production_lines: list[str] = []
    in_productions = False

    for lineno, raw_line in enumerate(src.splitlines(), start=1):
        line = raw_line.rstrip()

        if _SECTION_SEP.match(line):
            in_productions = True
            continue

        if in_productions:
            production_lines.append(raw_line)
            continue

        # Strip inline comments ((*…*) style from YALex) and # comments.
        stripped = re.sub(r"\(\*.*?\*\)", "", line)
        stripped = stripped.split("#")[0].strip()
        if not stripped:
            continue

        m = _TOKEN_LINE.match(stripped)
        if m:
            for name in _split_token_names(m.group(1), lineno, source):
                _accumulate(name, tokens, seen_tokens, lineno, source, kind="token")
            continue

        m = _IGNORE_LINE.match(stripped) or _BARE_IGNORE_LINE.match(stripped)
        if m:
            for name in _split_token_names(m.group(1), lineno, source):
                _accumulate(name, ignore, seen_ignore, lineno, source, kind="ignore")
            continue

    if not tokens and not production_lines:
        raise YAParReadError(
            f"{source}: no %token directive found — is this a valid .yapar file?"
        )

    return YAParSpec(
        tokens=tokens,
        ignore=ignore,
        raw_productions="\n".join(production_lines),
    )


def _split_token_names(text: str, lineno: int, source: str) -> list[str]:
    """Split and validate a whitespace-separated list of token names.

    Tokens must be valid identifiers AND fully uppercase (e.g. ``ID``,
    ``NUMBER``, ``PLUS_OP``).  Mixed-case names raise :exc:`YAParReadError`.
    """
    names = text.split()
    bad_fmt = [n for n in names if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n)]
    if bad_fmt:
        raise YAParReadError(
            f"{source}:{lineno}: invalid token name(s): {', '.join(bad_fmt)}"
        )
    bad_case = [n for n in names if n != n.upper()]
    if bad_case:
        raise YAParReadError(
            f"{source}:{lineno}: token name(s) must be uppercase: {', '.join(bad_case)}"
        )
    return names


def _accumulate(
    name: str,
    lst: list[str],
    seen: set[str],
    lineno: int,
    source: str,
    kind: str,
) -> None:
    """Append *name* to *lst*, raising on duplicates."""
    if name in seen:
        raise YAParReadError(
            f"{source}:{lineno}: duplicate {kind} '{name}'"
        )
    seen.add(name)
    lst.append(name)
