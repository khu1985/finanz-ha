"""Version, Änderungen und Protokoll der App."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
# Im Container liegen config.yaml und CHANGELOG.md unter /app/meta, im Repository eine Ebene höher.
KANDIDATEN = [APP_DIR / "meta", APP_DIR.parent]


def _datei(name: str) -> Path | None:
    for ordner in KANDIDATEN:
        if (ordner / name).exists():
            return ordner / name
    return None


@lru_cache(maxsize=1)
def version() -> str:
    pfad = _datei("config.yaml")
    if pfad:
        m = re.search(r'^version:\s*"?([^"\n]+)"?', pfad.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip()
    return "unbekannt"


@lru_cache(maxsize=1)
def repository() -> str:
    pfad = _datei("config.yaml")
    if pfad:
        m = re.search(r'^url:\s*"?([^"\n]+)"?', pfad.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip()
    return "https://github.com/khu1985/finanz-ha"


@lru_cache(maxsize=1)
def changelog() -> str:
    pfad = _datei("CHANGELOG.md")
    return pfad.read_text(encoding="utf-8") if pfad else "Keine Änderungen gefunden."


STUFEN = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def protokoll(log_datei: Path, stufe: str = "INFO", zeilen: int = 400) -> list[tuple[str, str, str]]:
    """Letzte Einträge (Zeit, Stufe, Text), neueste zuerst; mehrzeilige Einträge (Tracebacks) zusammengefasst."""
    dateien = [log_datei.with_name(log_datei.name + ".1"), log_datei]
    roh = []
    for d in dateien:
        if d.exists():
            roh += d.read_text(encoding="utf-8", errors="replace").splitlines()
    eintraege: list[list[str]] = []
    muster = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ (\w+) (.*)$")
    for zeile in roh:
        m = muster.match(zeile)
        if m:
            eintraege.append([m.group(1), m.group(2), m.group(3)])
        elif eintraege:
            eintraege[-1][2] += "\n" + zeile
    minimum = STUFEN.index(stufe) if stufe in STUFEN else 1
    gefiltert = [tuple(e) for e in eintraege if e[1] in STUFEN and STUFEN.index(e[1]) >= minimum]
    return list(reversed(gefiltert[-zeilen:]))
