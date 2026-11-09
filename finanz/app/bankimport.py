"""Bank-Import: Kontoauszüge als CSV aus dem E-Banking einlesen und Monatssaldi übernehmen.

Erkennt Trennzeichen, Kodierung, Vorspann-Zeilen (Kontonummer, IBAN, Zeitraum) und die Spalten über
typische Bezeichnungen der Schweizer Banken (Raiffeisen, UBS, ZKB, PostFinance, Kantonalbanken, Migros Bank,
neon, Yuh, VIAC, frankly, finpension …). Ohne Saldo-Spalte wird der Verlauf aus den Beträgen und einem
bekannten Endsaldo zurückgerechnet.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

import vermoegen as vm

SPALTEN = {
    "datum": ["buchungsdatum", "datum", "booking date", "booked at", "abschlussdatum", "transaktionsdatum", "date",
              "valuta", "valutadatum", "value date", "trade date", "buchungstag", "bewertungsdatum"],
    "saldo": ["saldo", "saldo chf", "kontostand", "balance", "saldo in chf", "neuer saldo", "endsaldo",
              "vermögen", "portfoliowert", "gesamtwert", "depotwert", "total value"],
    "betrag": ["betrag", "amount", "betrag chf", "betrag in chf", "umsatz", "transaction amount", "credit/debit amount",
               "einzelbetrag"],
    "gutschrift": ["gutschrift", "gutschrift in chf", "credit", "eingang", "haben"],
    "belastung": ["belastung", "lastschrift", "belastung in chf", "debit", "ausgang", "soll"],
    "text": ["buchungstext", "text", "beschreibung", "description", "mitteilung", "details", "avisierungstext"],
}

BANKEN = [("raiffeisen", "Raiffeisen"), ("ubs", "UBS"), ("zkb", "ZKB"), ("zürcher kantonalbank", "ZKB"),
          ("postfinance", "PostFinance"), ("blkb", "BLKB"), ("basellandschaftliche", "BLKB"), ("bkb", "BKB"),
          ("migros bank", "Migros Bank"), ("neon", "neon"), ("yuh", "Yuh"), ("viac", "VIAC"), ("frankly", "frankly"),
          ("finpension", "finpension"), ("valiant", "Valiant"), ("cler", "Bank Cler"), ("swissquote", "Swissquote"),
          ("revolut", "Revolut"), ("credit suisse", "UBS")]

VORSORGE = {"viac", "frankly", "finpension"}


@dataclass
class Auszug:
    bank: str
    iban: str
    konto_vorschlag: str
    art_vorschlag: str
    spalten: dict[str, str]
    buchungen: int
    monatssaldi: dict[str, tuple[str, float]]   # "JJJJ-MM" → (Datum, Saldo) letzter Saldo im Monat
    letzter: tuple[str, float] | None
    zeitraum: tuple[str, str] | None
    einnahmen: float = 0.0
    ausgaben: float = 0.0
    hinweise: list[str] = field(default_factory=list)
    waehrung: str = "CHF"


def _dekodieren(inhalt: bytes) -> str:
    if inhalt[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return inhalt.decode("utf-16")
    for kod in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return inhalt.decode(kod)
        except UnicodeDecodeError:
            continue
    return inhalt.decode("utf-8", errors="replace")


def _trennzeichen(zeilen: list[str]) -> str:
    probe = [z for z in zeilen[:40] if z.strip()]
    return max((";", ",", "\t"), key=lambda t: sum(min(z.count(t), 12) for z in probe))


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip().strip('"').lower())


def _kopfzeile(zeilen: list[list[str]]) -> int:
    """Index der Kopfzeile: die erste Zeile mit einer Datums- und einer Betrags- oder Saldo-Spalte."""
    for i, z in enumerate(zeilen[:60]):
        namen = {_norm(x) for x in z}
        hat_datum = any(n in namen for n in SPALTEN["datum"])
        hat_wert = any(n in namen for s in ("saldo", "betrag", "gutschrift", "belastung") for n in SPALTEN[s])
        if hat_datum and hat_wert:
            return i
    raise ValueError("Keine Kopfzeile mit Datum und Betrag/Saldo gefunden – ist das ein Kontoauszug als CSV?")


def _spalte(kopf: list[str], art: str) -> int | None:
    namen = [_norm(x) for x in kopf]
    for kandidat in SPALTEN[art]:
        if kandidat in namen:
            return namen.index(kandidat)
    for i, n in enumerate(namen):  # Teiltreffer, z. B. «Saldo (CHF)»
        if any(n.startswith(k) for k in SPALTEN[art]):
            return i
    return None


def _datum(t: str) -> str | None:
    t = (t or "").strip().strip('"')
    t = t.split(" ")[0].split("T")[0]
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _zahl(t: str) -> float | None:
    t = (t or "").strip().strip('"')
    if not t or t in ("-", "–"):
        return None
    try:
        return vm.zahl(t.replace("−", "-"))
    except ValueError:
        return None


def analysieren(inhalt: bytes, dateiname: str = "") -> Auszug:
    text = _dekodieren(inhalt)
    roh = text.splitlines()
    trenn = _trennzeichen(roh)
    zeilen = list(csv.reader(io.StringIO(text), delimiter=trenn))
    i_kopf = _kopfzeile(zeilen)
    kopf, daten = zeilen[i_kopf], zeilen[i_kopf + 1:]
    vorspann = " ".join(" ".join(z) for z in zeilen[:i_kopf]) + " " + dateiname
    iban_m = re.search(r"\bCH\d{2}(?:\s?[0-9A-Z]{4}){4}\s?[0-9A-Z]\b", text.replace(" ", " "))
    iban = re.sub(r"\s", "", iban_m.group(0)) if iban_m else ""
    tl = (vorspann + " " + text[:3000]).lower()
    bank = next((n for s, n in BANKEN if s in tl), "")
    sp = {art: _spalte(kopf, art) for art in SPALTEN}
    if sp["datum"] is None:
        raise ValueError("Keine Datumsspalte erkannt.")
    eintraege = []
    for z in daten:
        if len(z) <= sp["datum"]:
            continue
        tag = _datum(z[sp["datum"]])
        if not tag:
            continue
        saldo = _zahl(z[sp["saldo"]]) if sp["saldo"] is not None and len(z) > sp["saldo"] else None
        betrag = None
        if sp["betrag"] is not None and len(z) > sp["betrag"]:
            betrag = _zahl(z[sp["betrag"]])
        elif sp["gutschrift"] is not None or sp["belastung"] is not None:
            gut = _zahl(z[sp["gutschrift"]]) if sp["gutschrift"] is not None and len(z) > sp["gutschrift"] else None
            bel = _zahl(z[sp["belastung"]]) if sp["belastung"] is not None and len(z) > sp["belastung"] else None
            if gut is not None or bel is not None:
                betrag = (gut or 0) - abs(bel or 0)
        eintraege.append((tag, saldo, betrag))
    if not eintraege:
        raise ValueError("Keine Buchungen mit gültigem Datum gefunden.")
    hinweise = []
    if eintraege[0][0] > eintraege[-1][0]:
        eintraege.reverse()  # neueste zuerst → chronologisch, damit der letzte Saldo eines Tages zählt
    eintraege.sort(key=lambda e: e[0])
    if not any(e[1] is not None for e in eintraege):
        hinweise.append("Kein Saldo im Auszug – Verlauf wird aus den Beträgen zurückgerechnet, sobald ein Endsaldo bekannt ist.")
    monats: dict[str, tuple[str, float]] = {}
    for tag, saldo, _ in eintraege:
        if saldo is not None:
            monats[tag[:7]] = (tag, saldo)
    betraege = [b for _, _, b in eintraege if b is not None]
    letzter = max(monats.values()) if monats else None
    name = " ".join(x for x in (bank, ("…" + iban[-4:]) if iban else "") if x) or (dateiname.rsplit(".", 1)[0] or "Bankkonto")
    art = "vorsorge" if bank.lower() in VORSORGE else "bank"
    if bank.lower() in VORSORGE:
        hinweise.append("Vorsorgeanbieter erkannt – 3a-Guthaben gehört eigentlich in die Vorsorge (Einstellungen → 3a); "
                        "als Vermögen nur importieren, wenn es frei verfügbar ist.")
    return Auszug(bank, iban, name, art, {a: kopf[i] for a, i in sp.items() if i is not None}, len(eintraege), monats,
                  letzter, (eintraege[0][0], eintraege[-1][0]),
                  round(sum(b for b in betraege if b > 0), 2), round(-sum(b for b in betraege if b < 0), 2), hinweise)


def rueckrechnen(inhalt: bytes, endsaldo: float, stichtag: str | None = None) -> dict[str, tuple[str, float]]:
    """Ohne Saldo-Spalte: Monatssaldi aus Beträgen und einem bekannten Endsaldo (am letzten Buchungstag)."""
    text = _dekodieren(inhalt)
    zeilen = list(csv.reader(io.StringIO(text), delimiter=_trennzeichen(text.splitlines())))
    i = _kopfzeile(zeilen)
    kopf = zeilen[i]
    sp = {art: _spalte(kopf, art) for art in SPALTEN}
    buchungen = []
    for z in zeilen[i + 1:]:
        tag = _datum(z[sp["datum"]]) if sp["datum"] is not None and len(z) > sp["datum"] else None
        if not tag:
            continue
        if sp["betrag"] is not None and len(z) > sp["betrag"]:
            b = _zahl(z[sp["betrag"]]) or 0
        else:
            gut = _zahl(z[sp["gutschrift"]]) if sp["gutschrift"] is not None and len(z) > sp["gutschrift"] else 0
            bel = _zahl(z[sp["belastung"]]) if sp["belastung"] is not None and len(z) > sp["belastung"] else 0
            b = (gut or 0) - abs(bel or 0)
        buchungen.append((tag, b))
    if buchungen and buchungen[0][0] > buchungen[-1][0]:
        buchungen.reverse()
    buchungen.sort(key=lambda b: b[0])
    saldo, monats = endsaldo, {}
    for tag, b in reversed(buchungen):
        monats.setdefault(tag[:7], (tag, round(saldo, 2)))
        saldo -= b
    return dict(sorted(monats.items()))


def importieren(db, auszug: Auszug, konto: str, art: str, person: str,
                monatssaldi: dict[str, tuple[str, float]] | None = None) -> int:
    werte = monatssaldi if monatssaldi is not None else auszug.monatssaldi
    kid = vm.konto_anlegen(db, konto.strip() or auszug.konto_vorschlag, art or auszug.art_vorschlag, person,
                           auszug.waehrung)
    for tag, saldo in werte.values():
        vm.saldo_setzen(db, kid, tag, saldo)
    return len(werte)


def aus_datei(db, inhalt: bytes, dateiname: str, konto: str = "", art: str = "", person: str = "",
              endsaldo: float | None = None) -> tuple[Auszug, int]:
    import waehrung as wg
    a = analysieren(inhalt, dateiname)
    a.waehrung = wg.erkennen(_dekodieren(inhalt))
    monats = None
    if not a.monatssaldi:
        if endsaldo is None:
            raise ValueError("Der Auszug enthält keinen Saldo. Bitte den aktuellen Kontostand als Endsaldo angeben.")
        monats = rueckrechnen(inhalt, endsaldo)
    return a, importieren(db, a, konto, art, person, monats)


def buchungen_lesen(inhalt: bytes) -> list[tuple[str, float, str]]:
    """Einzelbuchungen (Datum, Betrag, Text) für die Budget-Auswertung; leer, wenn der Auszug keine Beträge hat."""
    text = _dekodieren(inhalt)
    zeilen = list(csv.reader(io.StringIO(text), delimiter=_trennzeichen(text.splitlines())))
    i = _kopfzeile(zeilen)
    kopf = zeilen[i]
    sp = {art: _spalte(kopf, art) for art in SPALTEN}
    if sp["datum"] is None or (sp["betrag"] is None and sp["gutschrift"] is None and sp["belastung"] is None):
        return []
    # weitere Textspalten (z. B. Zahlungsempfänger, Mitteilung) anhängen
    textspalten = [j for j, n in enumerate(kopf) if any(w in _norm(n) for w in
                   ("text", "beschreibung", "mitteilung", "empfänger", "auftraggeber", "zahlungs", "details",
                    "description", "händler", "merchant", "verwendungszweck"))]
    erg = []
    for z in zeilen[i + 1:]:
        if len(z) <= sp["datum"]:
            continue
        tag = _datum(z[sp["datum"]])
        if not tag:
            continue
        if sp["betrag"] is not None and len(z) > sp["betrag"]:
            b = _zahl(z[sp["betrag"]])
        else:
            gut = _zahl(z[sp["gutschrift"]]) if sp["gutschrift"] is not None and len(z) > sp["gutschrift"] else None
            bel = _zahl(z[sp["belastung"]]) if sp["belastung"] is not None and len(z) > sp["belastung"] else None
            b = None if gut is None and bel is None else (gut or 0) - abs(bel or 0)
        if b is None or b == 0:
            continue
        t = " ".join(dict.fromkeys(z[j].strip() for j in textspalten if j < len(z) and z[j].strip()))
        erg.append((tag, round(b, 2), re.sub(r"\s+", " ", t)[:200]))
    return erg
