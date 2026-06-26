"""Tiny .env loader (no dependency) so API keys 'just work' without exporting them.

Call load_env() at the start of any entrypoint. Existing environment variables win,
so you can still override on the command line.
"""
from __future__ import annotations

import os
import pathlib
import re

_loaded = False


def load_env(path: str = ".env") -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    p = pathlib.Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        # Quoted value: keep verbatim (a '#' inside quotes is part of the value).
        if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
            val = val[1:-1]
        else:
            # Unquoted: strip an inline comment ('#' at start or after whitespace),
            # e.g. `GROQ_API_KEY=gsk_…   # endpoint note` -> just the key.
            val = re.split(r"(?:^|\s)#", val, 1)[0].strip()
        if key and key not in os.environ:
            os.environ[key] = val
