"""Zwischenspeicher für teure Berechnungen, die auf jeder Seite und im Hintergrund mehrfach laufen
(Ampeln, Erinnerungen, Finanzplan, Steuererklärung, Verträge …).

Ein Ergebnis gilt, solange sich nichts geändert hat: gleiche Argumente (die Konfiguration als Inhalt), gleiche
Datenbank (Änderungszeit der Datei samt Journal) und gleiche Konfigurationsdatei. Jede gespeicherte Änderung macht
damit alle Ergebnisse ungültig – auch aus dem Hintergrund. In einer offenen Schreib-Transaktion, bei Datenbanken im
Arbeitsspeicher (Tests) oder unbekannten Argumenten wird immer neu gerechnet.
"""
from __future__ import annotations

import copy
import functools
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from datetime import date

LOG = logging.getLogger("finanz")
_SPEICHER: dict[tuple, tuple[float, object]] = {}
_SPERRE = threading.Lock()
MAX_EINTRAEGE = 200
MAX_ALTER = 600            # Sekunden; Sicherheitsnetz, falls eine Änderung die Datei nicht berührt
TREFFER = {"ja": 0, "nein": 0}

FUNKTIONEN = [
    ("versicherungen", "alle"), ("ampel", "bewerten"), ("erinnerungen", "alle"), ("steuererklaerung", "erstellen"),
    ("finanzplan", "rechnen"), ("szenarien", "einkauf_optimieren"), ("vorsorge", "pensionsluecke"),
    ("anlage", "pruefen"), ("krankenkasse", "haushalt"), ("steuern", "kapitalbezug_varianten"),
]


def _db_stand(db) -> tuple | None:
    try:
        if db.in_transaction:
            return None
        pfad = db.execute("PRAGMA database_list").fetchone()[2]
    except (sqlite3.Error, AttributeError, TypeError, IndexError):
        return None
    if not pfad:
        return None                                # Datenbank im Arbeitsspeicher
    stand = [pfad]
    for p in (pfad, pfad + "-wal", pfad + "-journal"):
        try:
            stand.append(os.stat(p).st_mtime_ns)
        except OSError:
            stand.append(0)
    return tuple(stand)


def _konfig_stand() -> int:
    try:
        import konfig
        return os.stat(konfig.konfig_pfad()).st_mtime_ns
    except Exception:  # noqa: BLE001
        return 0


def _wert(x):
    if isinstance(x, sqlite3.Connection):
        return "db"
    if isinstance(x, (str, int, float, bool, type(None), date)):
        return repr(x)
    if isinstance(x, (dict, list, tuple)):
        return hashlib.sha1(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()
    raise TypeError                                  # unbekannt → nicht zwischenspeichern


def speichernd(name: str):
    def deko(f):
        @functools.wraps(f)
        def innen(*a, **kw):
            db = next((x for x in list(a) + list(kw.values()) if isinstance(x, sqlite3.Connection)), None)
            stand = _db_stand(db) if db is not None else ("ohne-db",)
            if stand is None:
                return f(*a, **kw)
            try:
                schluessel = (name, stand, _konfig_stand(), tuple(_wert(x) for x in a),
                              tuple(sorted((k_, _wert(v)) for k_, v in kw.items())))
            except TypeError:
                return f(*a, **kw)
            jetzt = time.time()
            with _SPERRE:
                treffer = _SPEICHER.get(schluessel)
            if treffer and jetzt - treffer[0] < MAX_ALTER:
                TREFFER["ja"] += 1
                return copy.deepcopy(treffer[1])
            TREFFER["nein"] += 1
            erg = f(*a, **kw)
            with _SPERRE:
                if len(_SPEICHER) >= MAX_EINTRAEGE:
                    for s in sorted(_SPEICHER, key=lambda s_: _SPEICHER[s_][0])[: MAX_EINTRAEGE // 4]:
                        _SPEICHER.pop(s, None)
                _SPEICHER[schluessel] = (jetzt, copy.deepcopy(erg))
            return erg
        innen.__zwischengespeichert__ = True
        return innen
    return deko


def einschalten() -> int:
    """Die Funktionen aus FUNKTIONEN in ihren Modulen durch zwischengespeicherte Fassungen ersetzen."""
    import importlib
    n = 0
    for modul, funktion in FUNKTIONEN:
        try:
            m = importlib.import_module(modul)
            f = getattr(m, funktion, None)
            if f and not getattr(f, "__zwischengespeichert__", False):
                setattr(m, funktion, speichernd(f"{modul}.{funktion}")(f))
                n += 1
        except Exception as e:  # noqa: BLE001
            LOG.debug("Zwischenspeicher %s.%s: %s", modul, funktion, e)
    return n


def leeren() -> None:
    with _SPERRE:
        _SPEICHER.clear()
