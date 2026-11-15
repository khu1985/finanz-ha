"""Simulationen: benannte Varianten des Plans, die nur ausgewählte Annahmen ändern – nebeneinander verglichen.

Eine Simulation speichert nur ihre Änderungen (z. B. «Person 1: Pension mit 62», «Pensum 80 % ab heute»,
«PK-Einkäufe 2027–2030»). Gerechnet wird immer auf den aktuellen Einstellungen; ändern sich Lohn oder Vermögen,
rechnen alle Simulationen automatisch mit. «Übernehmen» schreibt die Änderungen in die Einstellungen.

Kennzahlen pro Variante: Pensionierung, Pensionslücke pro Jahr (heutige Franken), freies Vermögen bei der
Pensionierung (mittlerer Verlauf), Erfolgsquote bis zum Endalter, Jahr, in dem das Geld ausgeht, Steuern heute,
PK-Einkäufe total.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import datetime

# (Schlüssel, Bezeichnung, Typ, Grenzen bzw. Auswahl) – pro Person
PERSON = [
    ("pensionierung_alter", "Pensionierung mit (Alter)", "zahl", (55, 70)),
    ("pensum", "Pensum % (Lohn, PK und Sparen passen sich an)", "zahl", (10, 100)),
    ("lohn_brutto", "Bruttolohn (CHF/Jahr)", "zahl", (0, 5_000_000)),
    ("sparen_monat", "Sparen pro Monat (CHF)", "zahl", (-50_000, 50_000)),
    ("pk.kapitalbezug_anteil", "PK als Kapital %", "zahl", (0, 100)),
    ("pk.einkauf_geplant", "PK-Einkäufe (Jahr: Betrag, …; leer lassen = unverändert, «keine» = ohne)", "einkauf", None),
    ("saeule3a.beitrag_jahr", "3a-Einzahlung pro Jahr", "zahl", (0, 40_000)),
]
HAUSHALT = [
    ("haushalt.bedarf_ruhestand", "Bedarf im Ruhestand (CHF/Jahr)", "zahl", (0, 1_000_000)),
    ("anlage.risiko", "Anlagerisiko", "wahl", ("tief", "mittel", "hoch")),
    ("annahmen.teuerung", "Teuerung % pro Jahr", "zahl", (-2, 10)),
    ("ziele", "Zusätzliches Lebensziel (Name; Jahr; Betrag)", "ziel", None),
]


def _chf(v: float) -> str:
    return f"{v:,.0f}" >> TS


def tabellen(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS simulationen (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                  notiz TEXT NOT NULL DEFAULT '', aenderungen TEXT NOT NULL DEFAULT '[]', erstellt TEXT NOT NULL,
                  geaendert TEXT NOT NULL)""")


def alle(db) -> list[dict]:
    tabellen(db)
    return [{**dict(r), "aenderungen": json.loads(r["aenderungen"])}
            for r in db.execute("SELECT * FROM simulationen ORDER BY id")]


def holen(db, sid: int) -> dict | None:
    return next((s for s in alle(db) if s["id"] == sid), None)


def speichern(db, name: str, aenderungen: list[dict], notiz: str = "", sid: int | None = None) -> int:
    tabellen(db)
    name = (name or "").strip()[:60]
    if not name:
        raise ValueError("Namen für die Simulation angeben.")
    jetzt = datetime.now().isoformat(timespec="seconds")
    andere = db.execute("SELECT id FROM simulationen WHERE name = ? AND id != ?", (name, sid or -1)).fetchone()
    if andere:
        raise ValueError(f"Eine Simulation «{name}» gibt es schon.")
    daten = json.dumps(aenderungen, ensure_ascii=False)
    if sid:
        db.execute("UPDATE simulationen SET name = ?, notiz = ?, aenderungen = ?, geaendert = ? WHERE id = ?",
                   (name, notiz.strip()[:300], daten, jetzt, sid))
        return sid
    return db.execute("INSERT INTO simulationen (name, notiz, aenderungen, erstellt, geaendert) VALUES (?, ?, ?, ?, ?)",
                      (name, notiz.strip()[:300], daten, jetzt, jetzt)).lastrowid


def loeschen(db, sid: int) -> None:
    tabellen(db)
    db.execute("DELETE FROM simulationen WHERE id = ?", (sid,))


def kopieren(db, sid: int) -> int:
    s = holen(db, sid)
    if not s:
        raise ValueError("Simulation nicht gefunden.")
    namen = {x["name"] for x in alle(db)}
    n, i = f"{s['name']} (Kopie)", 2
    while n in namen:
        n, i = f"{s['name']} (Kopie {i})", i + 1
    return speichern(db, n, s["aenderungen"], s["notiz"])


# ---------------------------------------------------------------- Werte lesen, prüfen, anwenden

def _hole(d: dict, pfad: str):
    for teil in pfad.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(teil)
    return d


def _setze(d: dict, pfad: str, wert) -> None:
    teile = pfad.split(".")
    for teil in teile[:-1]:
        d = d.setdefault(teil, {})
    d[teile[-1]] = wert


def einkauf_lesen(text: str) -> list[dict]:
    t = (text or "").strip()
    if t.lower() in ("keine", "kein", "0", "-", "–"):
        return []
    erg = []
    for jahr, betrag in re.findall(r"(20\d\d)\s*[:=]\s*(\d[\d'’]*(?:\.\d+)?)", t):
        b = float(re.sub(r"[’']", "", betrag))
        if b > 0:
            erg.append({"jahr": int(jahr), "betrag": int(round(b))})
    if not erg:
        raise ValueError("PK-Einkäufe als «2027: 20000, 2028: 15000» angeben oder «keine».")
    return sorted(erg, key=lambda e: e["jahr"])


def einkauf_text(liste) -> str:
    return ", ".join(f"{e['jahr']}: {int(e['betrag'])}" for e in liste or []) or "keine"


def ziel_lesen(text: str) -> dict:
    teile = [x.strip() for x in re.split(r"[;|]", text or "")]
    if len(teile) != 3 or not teile[1].isdigit():
        raise ValueError("Lebensziel als «Name; Jahr; Betrag» angeben, z. B. «Weltreise; 2032; 40000».")
    return {"name": teile[0][:60] or "Ziel", "jahr": int(teile[1]),
            "betrag": float(re.sub(r"[’' ]", "", teile[2]).replace(",", ".") or 0)}


def pruefen(k: dict, schluessel: str, person: str | None, roh: str):
    """Text aus dem Formular → gespeicherter Wert (ValueError bei Unsinn)."""
    defs = {s: (n, t, g) for s, n, t, g in PERSON + HAUSHALT}
    if schluessel not in defs:
        raise ValueError("Unbekannte Annahme.")
    name, typ, grenzen = defs[schluessel]
    if person is not None and person not in [p["name"] for p in k["personen"]]:
        raise ValueError(f"Person «{person}» gibt es nicht.")
    if typ == "einkauf":
        return einkauf_lesen(roh)
    if typ == "ziel":
        return ziel_lesen(roh)
    if typ == "wahl":
        if roh not in grenzen:
            raise ValueError(f"{name}: {', '.join(grenzen)}.")
        return roh
    try:
        x = float(str(roh).replace("'", "").replace("’", "").replace(",", ".").strip())
    except ValueError:
        raise ValueError(f"{name}: Zahl angeben.") from None
    lo, hi = grenzen
    if not lo <= x <= hi:
        raise ValueError(f"{name}: zwischen {lo:g} und {hi:g}.")
    return int(x) if x == int(x) else x


def _pensum(k: dict, k2: dict, person: str, neu: float, sparen_fix: bool) -> None:
    """Pensum ändern: Lohn und PK-Sparbeitrag im Verhältnis, Sparen um das wegfallende bzw. zusätzliche Netto
    (nach Steuern; weniger Pensum spart Betreuungskosten wie im Teilzeit-Rechner)."""
    from datetime import date
    import steuern as st
    import teilzeit as tz
    import vorsorge as vs
    p = next(x for x in k["personen"] if x["name"] == person)
    p2 = next(x for x in k2["personen"] if x["name"] == person)
    alt = float(p.get("pensum") or 100) or 100
    f = neu / alt
    p2["pensum"] = neu
    p2["lohn_brutto"] = round(float(p2.get("lohn_brutto") or 0) * f)
    for feld in ("sparbeitrag_jahr", "versicherter_lohn"):
        if float(p2["pk"].get(feld) or 0):
            p2["pk"][feld] = round(float(p2["pk"][feld]) * f)
    if sparen_fix or neu == alt:
        return
    heute = date.today()
    if neu < alt:
        jahre = tz.rechnen(k, person, neu, heute.year, vs.pensionsjahr(p) - 1).jahre
        delta = jahre[0].saldo if jahre else 0.0                       # negativ: weniger zum Sparen
    else:
        sozial = float(k["kennzahlen"].get("sozialabzug", 6.4) or 6.4) / 100
        netto = float(p.get("lohn_brutto") or 0) * (f - 1) * (1 - sozial)
        delta = netto - st.ersparnis_abzug(k, netto, person)["total"]
    p2["sparen_monat"] = round(float(p2.get("sparen_monat") or 0) + delta / 12)


def anwenden(k: dict, aenderungen: list[dict]) -> dict:
    k2 = copy.deepcopy(k)
    sparen_fix = {a.get("person") for a in aenderungen if a["schluessel"] == "sparen_monat"}
    for a in aenderungen:                                   # Lohn zuerst, damit das Pensum auf dem neuen Lohn rechnet
        if a["schluessel"] == "lohn_brutto" and a.get("person"):
            p = next((x for x in k2["personen"] if x["name"] == a["person"]), None)
            if p is not None:
                p["lohn_brutto"] = a["wert"]
    for a in aenderungen:
        if a["schluessel"] == "lohn_brutto":
            continue
        if a["schluessel"] == "pensum" and a.get("person"):
            if any(x["name"] == a["person"] for x in k2["personen"]):
                _pensum(k, k2, a["person"], float(a["wert"]), a["person"] in sparen_fix)
            continue
        if a.get("person"):
            p = next((x for x in k2["personen"] if x["name"] == a["person"]), None)
            if p is None:
                continue
            _setze(p, a["schluessel"], copy.deepcopy(a["wert"]))
        elif a["schluessel"] == "ziele":
            k2.setdefault("ziele", []).append(copy.deepcopy(a["wert"]))
        else:
            _setze(k2, a["schluessel"], a["wert"])
    return k2


def beschreiben(a: dict) -> str:
    defs = {s: n for s, n, _, _ in PERSON + HAUSHALT}
    name = defs.get(a["schluessel"], a["schluessel"]).split(" (")[0]
    w = a["wert"]
    if a["schluessel"] == "pk.einkauf_geplant":
        wert = einkauf_text(w)
    elif a["schluessel"] == "ziele":
        wert = f"{w['name']} {w['jahr']}, CHF {_chf(w['betrag'])}"
    elif isinstance(w, (int, float)):
        wert = f"{w:,.0f}".replace(",", "’") if abs(w) >= 1000 else f"{w:g}"
    else:
        wert = str(w)
    return (f"{a['person']}: " if a.get("person") else "") + f"{name} {wert}"


def heute_wert(k: dict, schluessel: str, person: str | None):
    if person:
        p = next((x for x in k["personen"] if x["name"] == person), {})
        return _hole(p, schluessel)
    if schluessel == "anlage.risiko":
        return (k.get("anlage") or {}).get("risiko", "mittel")
    return _hole(k, schluessel)


# ---------------------------------------------------------------- Auswerten

@dataclass
class Ergebnis:
    name: str
    pension: str
    luecke: float
    vermoegen_pension: float
    erfolg: float
    reicht_bis: int | None
    steuern: float
    einkauf: float
    fehler: str = ""
    verlauf: list[tuple[int, float]] = field(default_factory=list)   # freies Vermögen, mittlerer Verlauf
    hinweise: list[str] = field(default_factory=list)


def auswerten(k: dict, frei: float, name: str = "Heute", pfade: int = 400) -> Ergebnis:
    import finanzplan as fp
    import steuern as st
    import vorsorge as vs
    try:
        plan = fp.rechnen(k, frei, pfade=pfade)
        lu = vs.pensionsluecke(k, frei)
        pj = {j.jahr: j for j in plan.jahre}
        med = dict(plan.perzentile.get(50) or [])
        vp = med.get(plan.pension_jahr, pj[plan.pension_jahr].vermoegen if plan.pension_jahr in pj else 0)
        pension = ", ".join(f"{p['name']} {vs.pensionsjahr(p)}" for p in k["personen"])
        einkauf = sum(float(e.get("betrag") or 0) for p in k["personen"]
                      for e in (p.get("pk") or {}).get("einkauf_geplant") or [])
        return Ergebnis(name, pension, round(lu.luecke), round(vp), round(plan.erfolg), plan.reicht_bis,
                        round(float(st.steuern_heute(k)["total"])), round(einkauf),
                        verlauf=list(plan.perzentile.get(50) or [(j.jahr, j.vermoegen) for j in plan.jahre]),
                        hinweise=plan.hinweise[:2])
    except Exception as e:  # noqa: BLE001 – eine kaputte Annahme soll den Vergleich nicht verhindern
        return Ergebnis(name, "", 0, 0, 0, None, 0, 0, fehler=str(e))


def vergleich(k: dict, db, ids: list[int] | None = None) -> list[tuple[dict | None, Ergebnis]]:
    import vermoegen as vm
    frei = vm.nettovermoegen(db)["frei"]
    erg: list[tuple[dict | None, Ergebnis]] = [(None, auswerten(k, frei))]
    for s in alle(db):
        if ids and s["id"] not in ids:
            continue
        erg.append((s, auswerten(anwenden(k, s["aenderungen"]), frei, s["name"])))
    return erg


def uebernehmen(k: dict, s: dict) -> dict:
    """Änderungen der Simulation in die Einstellungen schreiben (gibt die neue Konfiguration zurück)."""
    return anwenden(k, s["aenderungen"])
