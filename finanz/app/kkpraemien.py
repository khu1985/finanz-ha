"""Prämien der Grundversicherung aller Krankenkassen (offene Daten des BAG, priminfo) – Vergleich pro Person.

Quelle: BAG, «Krankenversicherungsprämien» auf opendata.swiss (Datei Prämien_CH.csv, rund 25 MB, jährlich im
Herbst für das Folgejahr). Die App lädt die Datei auf Knopfdruck (oder nimmt sie als Upload bzw. aus dem
Import-Ordner) und behält nur die Zeilen des Wohnkantons. Beide Formate werden gelesen: bis Prämienjahr 2026
(«FRA-300», «AKL-ERW», «PR-REG CH1», «TAR-HAM») und ab 2027 («FRA_01_E_0300», «AKA_03_ERW», «PR_REG_1», «PRAXIS»).
"""
from __future__ import annotations

import base64
import csv
import io
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date

LOG = logging.getLogger("finanz")
URL = "https://opendata.bagnet.ch/?r=/download&path=" + urllib.parse.quote(
    base64.b64encode("/Praemien/Prämien_CH.csv".encode()).decode(), safe="")
QUELLE = "https://opendata.swiss/de/dataset/health-insurance-premiums"

# BAG-Nummer → gebräuchlicher Name (Stand Prämien 2027); unbekannte Nummern erscheinen als «Kasse Nr. …»
NAMEN = {
    8: "CSS", 32: "Aquilana", 134: "Einsiedler", 194: "Sumiswalder", 246: "KK Steffisburg", 290: "Concordia",
    312: "Atupri", 343: "Avenir (Groupe Mutuel)", 360: "Luzerner Hinterland", 376: "KPT", 455: "ÖKK", 509: "Sympany",
    780: "Glarner", 820: "curaulta", 881: "EGK", 923: "SLKK", 941: "sodalis", 966: "vita surselva",
    1040: "Visperterminen", 1113: "Vallée d'Entremont", 1318: "Wädenswil", 1322: "Birchmeier", 1384: "SWICA",
    1386: "Galenos", 1401: "rhenusana", 1479: "Mutuel (Groupe Mutuel)", 1507: "AMB", 1509: "Sanitas",
    1535: "Philos (Groupe Mutuel)", 1542: "Assura", 1555: "Visana", 1560: "Agrisano", 1562: "Helsana", 1568: "sana24",
}
TYPEN = {"BASE": "Standard", "PRAXIS": "Hausarzt/HMO", "TEL_DIG": "Telmed/digital", "FLEX": "Flexibel"}
# App-Modelle (krankenkasse.MODELLE) → Tariftyp
MODELL_TYP = {"standard": "BASE", "hausarzt": "PRAXIS", "hmo": "PRAXIS", "telmed": "TEL_DIG"}


def name(nr: int) -> str:
    return NAMEN.get(int(nr), f"Kasse Nr. {nr}")


def _typ(t: str) -> str:
    t = t.upper().replace("TAR-", "")
    return {"HAM": "PRAXIS", "HMO": "PRAXIS", "DIV": "FLEX", "TEL": "TEL_DIG"}.get(t, t)


def _alter(a: str) -> str:
    return "KIN" if "KIN" in a else "JUG" if "JUG" in a else "ERW"


def _franchise(f: str) -> int | None:
    m = re.search(r"(\d+)$", f or "")
    return int(m.group(1)) if m else None


def _region(r: str) -> int:
    m = re.search(r"(\d+)$", r or "")
    return int(m.group(1)) if m else 0


def _zeilen(datei, kanton: str):
    for r in csv.DictReader(datei):
        if (r.get("Kanton") or "").upper() != kanton:
            continue
        f = _franchise(r.get("Franchise") or "")
        try:
            praemie = float((r.get("Prämie") or "").replace(",", "."))
        except ValueError:
            continue
        if f is None:
            continue
        yield (int(r.get("Geschäftsjahr") or 0), int(r["Versicherer"]), _region(r.get("Region") or ""),
               _alter(r.get("Altersklasse") or ""), 1 if "MIT" in (r.get("Unfalleinschluss") or "").upper() else 0,
               r.get("Tarif") or "", _typ(r.get("Tariftyp") or ""), f, round(praemie, 2),
               (r.get("Tarifbezeichnung") or "").strip()[:80])


def tabellen(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS kk_praemien (jahr INTEGER, kanton TEXT, versicherer INTEGER, region INTEGER, "
               "alter_ TEXT, unfall INTEGER, tarif TEXT, typ TEXT, franchise INTEGER, praemie REAL, bezeichnung TEXT)")
    db.execute("CREATE INDEX IF NOT EXISTS kk_praemien_suche ON kk_praemien (kanton, region, alter_, unfall, jahr)")


def einlesen(db, quelle, kanton: str) -> tuple[int, int]:
    """Prämien_CH.csv (Bytes oder offene Binärdatei) für einen Kanton übernehmen. Ergibt (Jahr, Anzahl Zeilen)."""
    kanton = kanton.upper()
    roh = io.BytesIO(quelle) if isinstance(quelle, (bytes, bytearray)) else quelle
    text = io.TextIOWrapper(roh, encoding="utf-8-sig", newline="")
    zeilen = list(_zeilen(text, kanton))
    if not zeilen:
        raise ValueError(f"Keine Prämien für Kanton {kanton} in der Datei (erwartet: Prämien_CH.csv des BAG).")
    tabellen(db)
    jahre = {z[0] for z in zeilen}
    for j in jahre:
        db.execute("DELETE FROM kk_praemien WHERE jahr = ? AND kanton = ?", (j, kanton))
    db.executemany("INSERT INTO kk_praemien VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   [(z[0], kanton, *z[1:]) for z in zeilen])
    db.commit()
    return max(jahre), len(zeilen)


def herunterladen(db, kanton: str, zeit: int = 120) -> tuple[int, int]:
    """Aktuelle Datei beim BAG holen (rund 25 MB, gestreamt; behalten wird nur der Kanton)."""
    anfrage = urllib.request.Request(URL, headers={"User-Agent": "finanz-ha"})
    with urllib.request.urlopen(anfrage, timeout=zeit) as antwort:  # noqa: S310 – feste Adresse des BAG
        return einlesen(db, antwort, kanton)


def jahre(db, kanton: str) -> list[int]:
    tabellen(db)
    return [r[0] for r in db.execute("SELECT DISTINCT jahr FROM kk_praemien WHERE kanton = ? ORDER BY jahr DESC",
                                      (kanton.upper(),))]


def altersklasse(geburtsjahr: int | None, jahr: int, kind: bool = False) -> str:
    if geburtsjahr:
        a = jahr - geburtsjahr
        return "KIN" if a <= 18 else "JUG" if a <= 25 else "ERW"
    return "KIN" if kind else "ERW"


@dataclass
class Angebot:
    versicherer: int
    kasse: str
    tarif: str
    modell: str
    bezeichnung: str
    franchise: int
    praemie_monat: float
    kosten_jahr: float          # Prämie + Kostenbeteiligung bei den erwarteten Gesundheitskosten


def angebote(db, kanton: str, region: int, alter: str, unfall: bool, gesundheitskosten: float,
             jahr: int | None = None, nur_typen: set[str] | None = None) -> list[Angebot]:
    """Alle Kassen, Modelle und Franchisen – sortiert nach Gesamtkosten pro Jahr."""
    import krankenkasse as kk
    tabellen(db)
    jahr = jahr or (jahre(db, kanton) or [0])[0]
    zeilen = db.execute("SELECT versicherer, tarif, typ, bezeichnung, franchise, praemie FROM kk_praemien WHERE "
                        "jahr = ? AND kanton = ? AND region = ? AND alter_ = ? AND unfall = ?",
                        (jahr, kanton.upper(), region, alter, 1 if unfall else 0)).fetchall()
    erg = []
    for vers, tarif, typ, bez, f, p in zeilen:
        if nur_typen and typ not in nur_typen:
            continue
        kosten = p * 12 + kk.kostenbeteiligung(gesundheitskosten, f, alter == "KIN")
        erg.append(Angebot(vers, name(vers), tarif, TYPEN.get(typ, typ), bez, f, p, round(kosten, 2)))
    erg.sort(key=lambda a: (a.kosten_jahr, a.praemie_monat))
    return erg


def region_aus_policen(vertraege: list[dict], kanton: str) -> int | None:
    """Prämienregion aus der Notiz einer KVG-Police («Prämienregion BL 1»)."""
    for v in vertraege:
        m = re.search(r"Prämienregion\s+([A-Z]{2})?\s*(\d)", v.get("notiz") or "")
        if v.get("sparte") == "kvg" and m and (not m.group(1) or m.group(1) == kanton.upper()):
            return int(m.group(2))
    return None


def vergleich(k: dict, db, vertraege: list[dict]) -> dict:
    """Pro Person: günstigste Angebote, günstigstes bei gleichem Modell und Franchise, Ersparnis gegenüber heute."""
    import kinder as ki
    import krankenkasse as kk
    kanton = str(k["haushalt"].get("kanton") or "").upper()
    js = jahre(db, kanton) if kanton else []
    if not js:
        return {"jahr": None, "kanton": kanton, "personen": []}
    jahr = js[0]
    cfg = k.get("krankenkasse") or {}
    region = cfg.get("region")
    region = int(region) if str(region or "").strip().isdigit() else region_aus_policen(vertraege, kanton)
    regionen = [r[0] for r in db.execute("SELECT DISTINCT region FROM kk_praemien WHERE jahr = ? AND kanton = ?",
                                         (jahr, kanton))]
    if region is None:
        region = regionen[0] if len(regionen) == 1 else None
    geburt = {p["name"]: str(p.get("geburtsdatum") or "")[:4] for p in k["personen"]}
    geburt.update({c["name"]: str(ki.geburt(c) or "")[:4] for c in ki.liste(k)})
    personen = []
    for p in kk.personen(k, vertraege):
        gj = geburt.get(p.name, "")
        alter = altersklasse(int(gj) if gj.isdigit() else None, jahr, p.kind)
        if region is None:
            personen.append({"person": p, "alter": alter, "angebote": [], "heute": None, "gleich": None, "eigene": None})
            continue
        alle = angebote(db, kanton, region, alter, p.unfall, p.kosten_jahr, jahr)
        heute = round(p.praemie_monat * 12 + kk.kostenbeteiligung(p.kosten_jahr, p.franchise, p.kind), 2) \
            if p.praemie_monat else None
        typ = MODELL_TYP.get(p.modell, "BASE")
        gleich = next((a for a in alle if a.franchise == p.franchise and _typ_von(a) == typ), None)
        eigene_kasse = _kasse_nr(p.versicherer)
        eigene = next((a for a in alle if a.versicherer == eigene_kasse), None) if eigene_kasse else None
        personen.append({"person": p, "alter": alter, "angebote": alle, "heute": heute, "gleich": gleich,
                         "eigene": eigene})
    return {"jahr": jahr, "kanton": kanton, "region": region, "regionen": sorted(regionen), "personen": personen}


def _kasse_nr(versicherer: str) -> int | None:
    """BAG-Nummer zum Versicherernamen einer Police («Atupri Gesundheitsversicherung» → 312)."""
    v = (versicherer or "").lower()
    for nr, n in NAMEN.items():
        kurz = n.split(" (")[0].lower()
        if kurz and kurz in v:
            return nr
    return None


def _typ_von(a: Angebot) -> str:
    return next((t for t, n in TYPEN.items() if n == a.modell), a.modell)


def stand(db, kanton: str) -> str:
    js = jahre(db, kanton) if kanton else []
    return f"Prämien {js[0]} für {kanton.upper()}" if js else ""


def heute_jahr() -> int:
    return date.today().year
