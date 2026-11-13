"""Hypothekarzinsen am Markt: SARON und publizierte Richtzinsen der Banken (SNB-Datenportal) sowie eigene Offerten.

Quellen (offen, ohne Schlüssel; es gehen keine eigenen Daten hinaus):
- SARON täglich: SNB-Cube `zirepo` (Reihe H0, Schlusskurs Overnight)
- Publizierte Zinssätze für neue Hypotheken, Monatsmittel der Banken: SNB-Cube `zikrepro` (Festhypotheken nach
  Laufzeit 1–15 Jahre, variable Hypothek, SARON-Hypothek mit 3 bzw. 5 Jahren Rahmenlaufzeit)

Rangfolge für die Hypothekar-Strategie: Festsatz aus den Einstellungen (`wohnen.strategie.fest`) > beste eigene
Offerte der letzten 90 Tage > Monatsmittel der SNB > Standardwerte.
"""
from __future__ import annotations

import csv
import io
import logging
import urllib.request
from datetime import date, datetime, timedelta

LOG = logging.getLogger("finanz")
BASIS = "https://data.snb.ch/api/cube/{cube}/data/csv/en"
QUELLE = "https://data.snb.ch/de/topics/ziredev/cube/zikrepro"
# Produktcodes im Cube zikrepro → Laufzeit in Jahren (Festhypotheken)
FEST = {"11": 1, "20": 2, "30": 3, "40": 4, "50": 5, "60": 6, "70": 7, "80": 8, "9": 9, "10": 10,
        "HYP_11": 11, "HYP_12": 12, "HYP_13": 13, "HYP_14": 14, "HYP_15": 15}
ANDERE = {"MV": "variabel", "SARJ03": "saron3", "SARJ05": "saron5"}
VERGLEICH = [("Comparis", "https://www.comparis.ch/hypotheken/zinssatz"),
             ("MoneyPark", "https://www.moneypark.ch/hypotheken/aktuelle-hypothekarzinsen.html"),
             ("Hypotheke.ch", "https://www.hypotheke.ch/zinsen")]


def tabellen(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS marktzinsen (datum TEXT NOT NULL, produkt TEXT NOT NULL, zins REAL NOT NULL, "
               "quelle TEXT NOT NULL, geholt TEXT NOT NULL, PRIMARY KEY (datum, produkt, quelle))")


def _csv(text: str, cube: str) -> list[dict]:
    """SNB-CSV: «CubeId»-Zeile, «PublishingDate», Leerzeile, dann Date;D0;…;Value."""
    zeilen = text.lstrip("﻿").splitlines()
    if not zeilen or cube not in zeilen[0]:
        raise ValueError(f"SNB {cube}: unerwartete Antwort")
    start = next((i for i, z in enumerate(zeilen) if z.startswith('"Date"') or z.startswith("Date")), None)
    if start is None:
        raise ValueError(f"SNB {cube}: keine Daten")
    return [r for r in csv.DictReader(io.StringIO("\n".join(zeilen[start:])), delimiter=";") if (r.get("Value") or "").strip()]


def einlesen(db, zikrepro: str | None = None, zirepo: str | None = None) -> int:
    """CSV-Texte der beiden Cubes übernehmen (für Tests und manuelles Einlesen)."""
    tabellen(db)
    jetzt = datetime.now().isoformat(timespec="seconds")
    n = 0
    for r in _csv(zikrepro, "zikrepro") if zikrepro else []:
        if r.get("D0") not in ("M", None):
            continue
        code = r.get("D1") or ""
        produkt = f"fest{FEST[code]}" if code in FEST else ANDERE.get(code)
        if produkt:
            db.execute("INSERT OR REPLACE INTO marktzinsen VALUES (?, ?, ?, 'snb', ?)",
                       (r["Date"][:7], produkt, float(r["Value"]), jetzt))
            n += 1
    for r in _csv(zirepo, "zirepo") if zirepo else []:
        if r.get("D0") == "H0":
            db.execute("INSERT OR REPLACE INTO marktzinsen VALUES (?, 'saron', ?, 'snb', ?)",
                       (r["Date"][:10], float(r["Value"]), jetzt))
            n += 1
    db.commit()
    return n


def _holen(cube: str, abfrage: str, zeit: int) -> str:
    url = BASIS.format(cube=cube) + "?" + abfrage
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "finanz-ha"}), timeout=zeit) as r:  # noqa: S310
        return r.read().decode("utf-8-sig")


def holen(db, heute: date | None = None, zeit: int = 30) -> int:
    heute = heute or date.today()
    von_monat = f"{heute.year - 2}-{heute.month:02d}"
    von_tag = (heute - timedelta(days=45)).isoformat()
    return einlesen(db, _holen("zikrepro", f"dimSel=D0(M)&fromDate={von_monat}", zeit),
                    _holen("zirepo", f"dimSel=D0(H0)&fromDate={von_tag}", zeit))


def aktualisieren(k: dict, db, heute: date | None = None) -> bool:
    """Einmal am Tag holen, wenn Wohneigentum aktiv ist (`wohnen.strategie.marktzinsen: false` schaltet aus)."""
    w = k.get("wohnen") or {}
    if not w.get("aktiv") or (w.get("strategie") or {}).get("marktzinsen") is False:
        return False
    global _VERSUCH
    heute = heute or date.today()
    tabellen(db)
    zuletzt = db.execute("SELECT MAX(geholt) FROM marktzinsen WHERE quelle = 'snb'").fetchone()[0]
    if zuletzt and zuletzt[:10] == heute.isoformat():
        return False
    if _VERSUCH and datetime.now() - _VERSUCH < timedelta(hours=6):
        return False                                 # ohne Internet nicht alle 15 Minuten neu versuchen
    _VERSUCH = datetime.now()
    holen(db, heute)
    return True


_VERSUCH: datetime | None = None


def aktuell(db) -> dict:
    """Neueste Werte: {produkt: (zins, datum)} – saron täglich, übrige als Monatsmittel."""
    tabellen(db)
    erg = {}
    for produkt, datum, zins in db.execute(
            "SELECT produkt, datum, zins FROM marktzinsen m WHERE quelle = 'snb' AND datum = "
            "(SELECT MAX(datum) FROM marktzinsen WHERE produkt = m.produkt AND quelle = 'snb')"):
        erg[produkt] = (zins, datum)
    return erg


def verlauf(db, produkt: str, monate: int = 24) -> list[tuple[str, float]]:
    tabellen(db)
    zeilen = db.execute("SELECT datum, zins FROM marktzinsen WHERE produkt = ? AND quelle = 'snb' ORDER BY datum",
                        (produkt,)).fetchall()
    if produkt == "saron":                         # Monatsende-Werte, damit die Achse zu den Monatsmitteln passt
        monat = {}
        for d, z in zeilen:
            monat[d[:7]] = z
        zeilen = sorted(monat.items())
    return [(d, z) for d, z in zeilen][-monate:]


def trend(db, produkt: str, monate: int = 3) -> float | None:
    """Veränderung in Prozentpunkten gegenüber vor `monate` Monaten."""
    v = verlauf(db, produkt, monate + 1)
    return round(v[-1][1] - v[0][1], 2) if len(v) > monate else None


def offerten(k: dict, heute: date | None = None, tage: int = 90) -> list[dict]:
    heute = heute or date.today()
    erg = []
    for o in ((k.get("wohnen") or {}).get("strategie") or {}).get("offerten") or []:
        try:
            d = date.fromisoformat(str(o.get("datum")))
        except ValueError:
            continue
        if (heute - d).days <= tage:
            erg.append({**o, "zins": float(o.get("zins") or 0), "alt": (heute - d).days})
    return sorted(erg, key=lambda o: (o.get("produkt", ""), o["zins"]))


def saetze(k: dict, db, heute: date | None = None) -> dict:
    """Festsätze {Laufzeit: (Zins, Herkunft)}, SARON (Zins, Herkunft) und geschätzte SARON-Marge für die Strategie."""
    eigen = (k.get("wohnen") or {}).get("strategie") or {}
    markt = aktuell(db) if db is not None else {}
    fest = {}
    for produkt, (z, d) in markt.items():
        if produkt.startswith("fest"):
            fest[int(produkt[4:])] = (z, f"SNB-Mittel {d[5:7]}.{d[:4]}")
    for o in offerten(k, heute):
        p = str(o.get("produkt") or "")
        if p.startswith("fest") and p[4:].isdigit():
            lz = int(p[4:])
            if lz not in fest or fest[lz][1].startswith("SNB") or o["zins"] < fest[lz][0]:
                fest[lz] = (o["zins"], f"Offerte {o.get('bank') or ''}".strip())
    for lz, z in (eigen.get("fest") or {}).items():
        fest[int(lz)] = (float(z), "Einstellungen")
    saron = None
    if "saron" in markt:
        z, d = markt["saron"]
        saron = (z, f"SNB {d[8:10]}.{d[5:7]}.{d[:4]}")
    if str(eigen.get("saron", "")).strip() not in ("", "None"):
        saron = (float(eigen["saron"]), "Einstellungen")
    marge = None
    if "saron5" in markt and saron:
        marge = (round(markt["saron5"][0] - max(saron[0], 0.0), 2), "SNB-Mittel SARON-Hypothek − SARON")
    for o in offerten(k, heute):
        if o.get("produkt") == "saron" and saron:
            m = round(o["zins"] - max(saron[0], 0.0), 2)
            if marge is None or marge[1].startswith("SNB") or m < marge[0]:
                marge = (m, f"Offerte {o.get('bank') or ''}".strip())
    if str(eigen.get("marge_saron", "")).strip() not in ("", "None"):
        marge = (float(eigen["marge_saron"]), "Einstellungen")
    return {"fest": dict(sorted(fest.items())), "saron": saron, "marge": marge}
