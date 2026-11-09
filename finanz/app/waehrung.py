"""Fremdwährungen: Konten und Renten in EUR, USD … in Franken umrechnen.

Kurse = Franken pro Einheit der Fremdwährung (EUR 0.92 heisst 1 EUR = 0.92 CHF).
Reihenfolge: automatisch geholter Tageskurs (wenn `waehrungen.automatisch`, Quelle: Referenzkurse der EZB über
frankfurter.dev, einmal pro Tag) → `waehrungen.kurse` aus der Konfiguration → Standard (EUR, Stand 09.11.2026).
Ohne Kurs wird 1:1 gerechnet und ein Hinweis angezeigt. Der Verlauf rechnet frühere Saldi mit dem heutigen Kurs.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from datetime import date

LOG = logging.getLogger("finanz")

STANDARD = {"CHF": 1.0, "EUR": 0.92}
STANDARD_STAND = "09.11.2026"
WAEHRUNGEN = ["CHF", "EUR", "USD", "GBP"]
_KONFIG: dict[str, float] = {}
_AUTOMATISCH = False


def uebernehmen(k: dict) -> None:
    """Beim Laden der Konfiguration aufgerufen."""
    global _AUTOMATISCH
    cfg = k.get("waehrungen") or {}
    _KONFIG.clear()
    for w, v in (cfg.get("kurse") or {}).items():
        try:
            if float(v) > 0:
                _KONFIG[str(w).upper()] = float(v)
        except (TypeError, ValueError):
            pass
    _AUTOMATISCH = bool(cfg.get("automatisch"))


def _tabelle(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS kurse (waehrung TEXT PRIMARY KEY, kurs REAL NOT NULL, datum TEXT NOT NULL)")


def kurse(db=None) -> dict[str, tuple[float, str]]:
    """Währung → (Kurs, Quelle)."""
    erg = {w: (v, f"Standard {STANDARD_STAND}") for w, v in STANDARD.items()}
    erg.update({w: (v, "Einstellungen") for w, v in _KONFIG.items()})
    if db is not None and _AUTOMATISCH:
        try:
            _tabelle(db)
            for r in db.execute("SELECT waehrung, kurs, datum FROM kurse"):
                erg[r[0]] = (float(r[1]), f"EZB {r[2]}")
        except Exception:  # noqa: BLE001
            pass
    erg["CHF"] = (1.0, "")
    return erg


def kurs(waehrung: str | None, db=None) -> float:
    w = (waehrung or "CHF").upper()
    return kurse(db).get(w, (1.0, ""))[0]


def bekannt(waehrung: str | None, db=None) -> bool:
    return (waehrung or "CHF").upper() in kurse(db)


def in_chf(betrag: float, waehrung: str | None, db=None) -> float:
    return float(betrag or 0) * kurs(waehrung, db)


def aktualisieren(db, waehrungen: list[str], heute: date | None = None) -> list[str]:
    """Tageskurse der EZB holen (nur wenn automatisch eingeschaltet). Gibt die aktualisierten Währungen zurück."""
    if not _AUTOMATISCH:
        return []
    heute = heute or date.today()
    _tabelle(db)
    offen = [w for w in {w.upper() for w in waehrungen} if w != "CHF"]
    stand = {r[0]: r[1] for r in db.execute("SELECT waehrung, datum FROM kurse")}
    offen = [w for w in offen if stand.get(w) != heute.isoformat()]
    erg = []
    for w in offen:
        try:
            url = f"https://api.frankfurter.dev/v1/latest?base={w}&symbols=CHF"
            with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310 – feste Adresse
                daten = json.loads(r.read().decode("utf-8"))
            k = float(daten["rates"]["CHF"])
            db.execute("INSERT OR REPLACE INTO kurse (waehrung, kurs, datum) VALUES (?, ?, ?)", (w, k, heute.isoformat()))
            erg.append(w)
        except Exception as e:  # noqa: BLE001
            LOG.warning("Kurs %s nicht geholt: %s", w, e)
    if erg:
        db.commit()
    return erg


def erkennen(text: str) -> str:
    """Währung aus einem Kontoauszug (Kopfzeilen) erkennen."""
    t = text[:3000].upper()
    zaehler = {w: t.count(w) for w in WAEHRUNGEN if w != "CHF"}
    w, n = max(zaehler.items(), key=lambda x: x[1])
    return w if n and n >= t.count("CHF") else "CHF"
