"""Wertschriften pro Position: Titel, Stückzahl, Kurs, Wert; Aufteilung nach Anlageklasse, Region und Währung,
Rendite gegenüber dem Vorjahr und laufende Kosten (TER).

Quellen: E-Steuerauszug (XML nach eCH-0196, Positionen per 31.12.) oder eine eigene Liste als CSV
(`Datum;Depot;ISIN;Name;Kategorie;Währung;Menge;Kurs;Wert CHF`). Eine Position ist eine Zeile pro Depot, Stichtag
und Titel; ein neuer Import desselben Depots und Stichtags ersetzt den früheren.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field

KLASSEN = ["Aktien", "Obligationen", "Immobilien", "Rohstoffe", "Geldmarkt", "Derivate", "Übrige"]
AKTIENARTIG = {"Aktien"}
LAENDER = {"CH": "Schweiz", "LI": "Schweiz", "US": "USA", "CA": "Nordamerika", "JP": "Japan", "GB": "Europa",
           "DE": "Europa", "FR": "Europa", "NL": "Europa", "AT": "Europa", "IT": "Europa", "ES": "Europa",
           "SE": "Europa", "DK": "Europa", "NO": "Europa", "FI": "Europa", "BE": "Europa", "CN": "Schwellenländer",
           "IN": "Schwellenländer", "BR": "Schwellenländer", "KR": "Schwellenländer", "TW": "Schwellenländer"}
# Typische Kosten (TER in %), solange keine eigene Angabe erfasst ist
TER_RICHTWERT = {"Aktien": 0.0, "Obligationen": 0.0}


@dataclass
class Position:
    stichtag: str
    depot: str
    isin: str
    name: str
    kategorie: str = ""
    waehrung: str = "CHF"
    land: str = ""
    menge: float = 0.0
    kurs: float = 0.0
    wert: float = 0.0           # CHF per Stichtag
    ertrag: float = 0.0         # Erträge im Jahr (CHF)
    klasse: str = ""
    region: str = ""
    fonds: bool = False
    ter: float | None = None
    rendite: float | None = None   # % gegenüber dem Vorjahr (nur bei unveränderter Stückzahl)
    anteil: float = 0.0


def tabellen(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS wertschriften (stichtag TEXT NOT NULL, depot TEXT NOT NULL, isin TEXT, "
               "name TEXT, kategorie TEXT, waehrung TEXT, land TEXT, menge REAL, kurs REAL, wert REAL, ertrag REAL, "
               "quelle TEXT)")


def klasse(kategorie: str, name: str) -> tuple[str, bool]:
    """Anlageklasse aus der Kategorie des Steuerauszugs (SHARE, FUND, BOND …) bzw. dem Namen. (Klasse, ist_fonds)"""
    k = (kategorie or "").upper()
    n = (name or "").lower()
    fonds = k in ("FUND", "ETF") or bool(re.search(r"\b(etf|fonds?|fund|ucits|index|sicav|tracker)\b", n))
    if k in ("OPTION", "DEVT", "FUTURE"):
        return "Derivate", False
    if k == "BOND" or re.search(r"\b(bond|oblig\w*|anleihe|fixed income|treasury|aggregate|rent\w*fonds)\b", n):
        return "Obligationen", fonds
    if re.search(r"immo|real estate|reit|property|immobilien", n):
        return "Immobilien", fonds
    if re.search(r"\b(gold|silber|silver|commodit\w*|rohstoff\w*|platin)\b", n):
        return "Rohstoffe", fonds
    if re.search(r"geldmarkt|money market|liquidity|cash", n):
        return "Geldmarkt", fonds
    if k in ("SHARE", "FUND", "ETF", "PARTICIPATION") or fonds or not k:
        return "Aktien", fonds
    return "Übrige", fonds


def region(land: str, isin: str, name: str, fonds: bool) -> str:
    n = (name or "").lower()
    if fonds or (isin or "")[:2] in ("IE", "LU"):
        for muster, r in ((r"world|global|welt|acwi|all.country", "Welt"), (r"emerging|schwellen", "Schwellenländer"),
                          (r"europe|europa|euro stoxx|stoxx 600", "Europa"), (r"\busa?\b|s&p|nasdaq|amerika|america", "USA"),
                          (r"swiss|schweiz|\bsmi\b|\bspi\b|\bch\b", "Schweiz"), (r"japan", "Japan"), (r"pacific|asia", "Asien/Pazifik")):
            if re.search(muster, n):
                return r
        if fonds:
            return "Welt/gemischt"
    land = (land or isin[:2] if isin else land or "").upper()[:2]
    return LAENDER.get(land, "Übrige Länder" if land else "unbekannt")


def speichern(db, positionen: list[Position], quelle: str) -> int:
    tabellen(db)
    for depot, stichtag in {(p.depot, p.stichtag) for p in positionen}:
        db.execute("DELETE FROM wertschriften WHERE depot = ? AND stichtag = ?", (depot, stichtag))
    db.executemany("INSERT INTO wertschriften VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   [(p.stichtag, p.depot, p.isin, p.name, p.kategorie, p.waehrung, p.land, p.menge, p.kurs, p.wert,
                     p.ertrag, quelle) for p in positionen])
    db.commit()
    return len(positionen)


def _datum(text: str) -> str:
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    raise ValueError(f"Datum «{text}» nicht lesbar (TT.MM.JJJJ oder JJJJ-MM-TT).")


def csv_lesen(inhalt: bytes) -> list[Position]:
    """Eigene Liste: Datum;Depot;ISIN;Name;Kategorie;Währung;Menge;Kurs;Wert CHF (Kopfzeile, ; oder ,)."""
    import vermoegen as vm
    text = inhalt.decode("utf-8-sig", errors="replace")
    trenner = ";" if text.split("\n", 1)[0].count(";") >= text.split("\n", 1)[0].count(",") else ","
    zeilen = list(csv.reader(io.StringIO(text), delimiter=trenner))
    kopf = [z.strip().lower() for z in zeilen[0]] if zeilen else []

    def spalte(*namen):
        return next((i for i, h in enumerate(kopf) if any(n in h for n in namen)), None)
    i_d, i_dep, i_isin, i_name = spalte("datum", "stichtag"), spalte("depot"), spalte("isin"), spalte("name", "titel")
    i_kat, i_wg, i_m, i_k, i_w = spalte("kategorie", "art"), spalte("währung", "waehrung"), spalte("menge", "anzahl", "stück"), \
        spalte("kurs"), spalte("wert")
    if None in (i_d, i_name, i_w):
        raise ValueError("Kopfzeile mit Datum, Name und Wert erwartet (Datum;Depot;ISIN;Name;Kategorie;Währung;Menge;Kurs;Wert CHF).")
    erg = []
    for z in zeilen[1:]:
        if not z or not any(x.strip() for x in z):
            continue
        g = lambda i: (z[i].strip() if i is not None and i < len(z) else "")  # noqa: E731
        erg.append(Position(_datum(g(i_d)), g(i_dep) or "Depot",
                            g(i_isin).upper(), g(i_name), g(i_kat).upper(), (g(i_wg) or "CHF").upper(), "",
                            vm.zahl(g(i_m) or "0"), vm.zahl(g(i_k) or "0"), vm.zahl(g(i_w) or "0")))
    if not erg:
        raise ValueError("Keine Positionen in der Datei.")
    return erg


def stichtage(db) -> list[str]:
    tabellen(db)
    return [r[0] for r in db.execute("SELECT DISTINCT stichtag FROM wertschriften ORDER BY stichtag DESC")]


def _laden(db, stichtag: str) -> list[Position]:
    return [Position(*r[:11]) for r in db.execute(
        "SELECT stichtag, depot, isin, name, kategorie, waehrung, land, menge, kurs, wert, ertrag FROM wertschriften "
        "WHERE stichtag = ? ORDER BY wert DESC", (stichtag,))]


@dataclass
class Uebersicht:
    stichtag: str
    positionen: list[Position]
    wert: float
    klassen: dict[str, float] = field(default_factory=dict)
    regionen: dict[str, float] = field(default_factory=dict)
    waehrungen: dict[str, float] = field(default_factory=dict)
    kosten: float = 0.0            # laufende Kosten pro Jahr (TER × Wert), soweit bekannt
    ohne_ter: int = 0              # Fonds ohne TER-Angabe
    rendite: float | None = None   # gewichtete Rendite der unveränderten Positionen
    vorjahr: str = ""


def uebersicht(k: dict, db, stichtag: str | None = None) -> Uebersicht | None:
    tage = stichtage(db)
    if not tage:
        return None
    stichtag = stichtag or tage[0]
    pos = _laden(db, stichtag)
    vorher = next((t for t in tage if t < stichtag), "")
    alt = {(p.depot, p.isin or p.name): p for p in _laden(db, vorher)} if vorher else {}
    ter = {str(i).upper(): float(v) for i, v in ((k.get("wertschriften") or {}).get("ter") or {}).items()}
    u = Uebersicht(stichtag, pos, round(sum(p.wert for p in pos), 2), vorjahr=vorher)
    gew, summe_r = 0.0, 0.0
    for p in pos:
        p.klasse, p.fonds = klasse(p.kategorie, p.name)
        p.region = region(p.land, p.isin, p.name, p.fonds)
        p.anteil = round(p.wert / u.wert * 100, 1) if u.wert else 0.0
        p.ter = ter.get(p.isin.upper()) if p.isin else None
        if p.ter is None and not p.fonds:
            p.ter = 0.0                      # Einzeltitel: keine laufenden Fondskosten
        if p.ter is not None:
            u.kosten += p.wert * p.ter / 100
        elif p.fonds:
            u.ohne_ter += 1
        a = alt.get((p.depot, p.isin or p.name))
        if a and a.wert > 0 and abs(a.menge - p.menge) < 1e-6:
            p.rendite = round((p.wert + p.ertrag - a.wert) / a.wert * 100, 1)
            gew += a.wert
            summe_r += p.rendite * a.wert
        for ziel, schl in ((u.klassen, p.klasse), (u.regionen, p.region), (u.waehrungen, p.waehrung or "CHF")):
            ziel[schl] = round(ziel.get(schl, 0) + p.wert, 2)
    u.rendite = round(summe_r / gew, 1) if gew else None
    u.kosten = round(u.kosten, 2)
    for d in (u.klassen, u.regionen, u.waehrungen):
        geordnet = dict(sorted(d.items(), key=lambda x: -x[1]))
        d.clear()
        d.update(geordnet)
    return u


def aktienwert(k: dict, db) -> float | None:
    """Wert der aktienartigen Positionen am letzten Stichtag (für den Anlage-Check), None ohne Positionen."""
    u = uebersicht(k, db)
    return sum(v for kl, v in u.klassen.items() if kl in AKTIENARTIG) if u else None


def hinweise(u: Uebersicht) -> list[str]:
    h = []
    if not u.wert:
        return h
    gross = [p for p in u.positionen if not p.fonds and p.anteil >= 10]
    for p in gross:
        h.append(f"Klumpenrisiko: {p.name} macht {p.anteil:.0f} % der Wertschriften aus (Einzeltitel über 10 %).")
    fremd = sum(v for w, v in u.waehrungen.items() if w != "CHF") / u.wert * 100
    if fremd > 60:
        h.append(f"{fremd:.0f} % in Fremdwährungen – Ausgaben fallen in Franken an; für den sicheren Teil eher CHF.")
    ch = u.regionen.get("Schweiz", 0) / u.wert * 100
    if ch > 60:
        h.append(f"{ch:.0f} % Schweiz – der Heimmarkt ist klein und von wenigen Firmen geprägt (Nestlé, Novartis, Roche).")
    if u.ohne_ter:
        h.append(f"{u.ohne_ter} Fonds ohne Kostenangabe (TER) – im Factsheet nachsehen und unten eintragen.")
    if u.kosten and u.kosten / u.wert * 100 > 0.6:
        h.append(f"Laufende Fondskosten {u.kosten / u.wert * 100:.2f} % pro Jahr – breite Indexfonds kosten oft unter 0,2 %.")
    return h
