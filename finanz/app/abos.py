"""Wiederkehrende Zahlungen und Abos aus den importierten Buchungen erkennen.

Gleiche Gegenpartei (Buchungstext ohne Datum, Referenz- und Kartennummern), ähnlicher Betrag (±15 %) und
regelmässiger Abstand: wöchentlich, monatlich, alle zwei Monate, vierteljährlich, halbjährlich oder jährlich.
Ergebnis: Rhythmus, letzter Betrag, Betrag pro Jahr, nächste erwartete Belastung, Preisänderung und – wenn der
Name passt – der zugehörige Vertrag unter Versicherungen.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from datetime import date, timedelta

RHYTHMEN = [  # (Name, Tage, Toleranz in Tagen, pro Jahr, Mindestanzahl)
    ("wöchentlich", 7, 2, 52, 4),
    ("monatlich", 30.4, 5, 12, 3),
    ("alle 2 Monate", 61, 7, 6, 3),
    ("vierteljährlich", 91, 10, 4, 3),
    ("halbjährlich", 182, 15, 2, 2),
    ("jährlich", 365, 20, 1, 2),
]
NICHT = ("umbuchung", "übertrag", "uebertrag", "bargeld", "bancomat", "geldautomat", "atm ", "twint an ", "twint von ")


def gegenpartei(text: str) -> str:
    """Buchungstext ohne Zahlen, Datum, Referenzen – als Schlüssel für die gleiche Gegenpartei."""
    t = (text or "").lower()
    t = re.sub(r"\b(?:ref|referenz|kartennr|karte|card|mitteilung|zahlung|belastung|lastschrift|dauerauftrag|"
               r"ebill|e-bill|lsv\+?|debit direct|einkauf|kauf|gutschrift|überweisung|ueberweisung|"
               r"qr-?rechnung|zahlungsauftrag)\b", " ", t)
    t = re.sub(r"[\d.,:/'’*#+-]+", " ", t)
    t = re.sub(r"\b(ch|chf|eur|usd|ag|sa|gmbh|ltd|inc)\b", " ", t)
    woerter = [w for w in t.split() if len(w) > 2][:4]
    return " ".join(woerter)


@dataclass
class Abo:
    name: str               # lesbarer Name (häufigster Originaltext, gekürzt)
    schluessel: str
    kategorie: str
    rhythmus: str
    betrag: float           # letzter Betrag (positiv)
    pro_jahr: float
    anzahl: int
    letzte: str
    naechste: str
    vorher: float | None    # früherer Betrag, falls geändert
    aenderung: float | None  # in %
    vertrag: str = ""       # passender Vertrag unter Versicherungen
    eingang: bool = False   # wiederkehrende Gutschrift (Lohn, Rente)


def _rhythmus(abstaende: list[float]):
    med = statistics.median(abstaende)
    for name, tage, tol, pro_jahr, mind in RHYTHMEN:
        if abs(med - tage) <= tol:
            passend = sum(1 for a in abstaende if abs(a - tage) <= tol * 1.5)
            if passend >= max(1, len(abstaende) * 0.7):
                return name, tage, pro_jahr, mind
    return None


def erkennen(buchungen: list[dict], vertraege: list[dict] | None = None, heute: date | None = None,
             mit_eingaengen: bool = False) -> list[Abo]:
    import budget as bu
    heute = heute or date.today()
    gruppen: dict[tuple[str, bool], list[dict]] = {}
    for b in buchungen:
        if b.get("kategorie") in (bu.UMBUCHUNG,) or any(n in (b.get("text") or "").lower() for n in NICHT):
            continue
        if b["betrag"] > 0 and not mit_eingaengen:
            continue
        s = gegenpartei(b.get("text") or "")
        if s:
            gruppen.setdefault((s, b["betrag"] > 0), []).append(b)
    erg = []
    for (s, eingang), liste in gruppen.items():
        liste.sort(key=lambda b: b["datum"])
        # pro Tag nur eine Buchung (Sammelbuchungen, Doppelimporte)
        tage = {}
        for b in liste:
            tage.setdefault(b["datum"], b)
        liste = list(tage.values())
        if len(liste) < 2:
            continue
        betraege = [abs(b["betrag"]) for b in liste]
        # Abos haben feste Beträge mit gelegentlicher Preisänderung; Einkäufe schwanken jedes Mal
        if min(betraege) < 1:
            continue
        paare = list(zip(betraege, betraege[1:]))
        gleich = sum(1 for x, y in paare if abs(y - x) <= 0.02 * x)
        if len(betraege) == 2:
            if abs(paare[0][1] - paare[0][0]) > 0.15 * paare[0][0]:
                continue
        elif gleich < 0.6 * len(paare) or any(abs(y - x) > 0.5 * x for x, y in paare):
            continue
        daten = [date.fromisoformat(b["datum"]) for b in liste]
        abstaende = [(b - a).days for a, b in zip(daten, daten[1:])]
        r = _rhythmus(abstaende)
        if not r:
            continue
        name, tage_r, pro_jahr, mind = r
        if len(liste) < mind:
            continue
        letzte = daten[-1]
        if (heute - letzte).days > tage_r * 2 + 20:
            continue                                    # vermutlich beendet
        naechste = letzte + timedelta(days=round(tage_r))
        betrag = betraege[-1]
        vorher = next((x for x in reversed(betraege[:-1]) if abs(x - betrag) > 0.005), None)
        aenderung = round((betrag - vorher) / vorher * 100, 1) if vorher else None
        texte = [b.get("text") or "" for b in liste]
        lesbar = max(set(texte), key=texte.count)
        lesbar = re.sub(r"\s+", " ", re.sub(r"\b\d[\d.,:/'’ -]{5,}\b", "", lesbar)).strip()[:60] or s
        vertrag = ""
        for v in vertraege or []:
            vers = (v.get("versicherer") or "").lower()
            if vers and len(vers) > 2 and vers.split()[0] in s:
                vertrag = f"{v.get('versicherer')} ({v.get('sparte')})"
                break
        erg.append(Abo(lesbar, s, liste[-1].get("kategorie") or "", name, round(betrag, 2), round(betrag * pro_jahr, 2),
                       len(liste), letzte.isoformat(), naechste.isoformat(), vorher, aenderung, vertrag, eingang))
    erg.sort(key=lambda a: -a.pro_jahr)
    return erg


def summe(abos: list[Abo]) -> float:
    return round(sum(a.pro_jahr for a in abos if not a.eingang), 2)
