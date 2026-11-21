"""Geführte Checklisten: Monats-Check (jeden Monat) und Jahresabschluss (Januar bis März).

Jeder Punkt hat – wo die App es weiss – einen automatischen Status (erledigt, wenn die Daten es zeigen) und lässt
sich von Hand abhaken (Tabelle checkliste). Offene Checklisten erscheinen als Erinnerung.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import date, timedelta

LOG = logging.getLogger("finanz")
_LOKAL = threading.local()            # verhindert Rekursion: Erinnerungen → Checkliste → Erinnerungen


@dataclass
class Punkt:
    schluessel: str
    titel: str
    text: str
    seite: str
    auto: bool | None = None          # True = laut Daten erledigt, False = laut Daten offen, None = unbekannt
    grund: str = ""                   # warum offen bzw. erledigt (aus den Daten)
    erledigt: str = ""                # von Hand abgehakt am (ISO)

    @property
    def fertig(self) -> bool:
        return bool(self.erledigt) or self.auto is True


@dataclass
class Liste:
    schluessel: str                   # monat-2026-11, jahr-2026
    titel: str
    faellig: date
    punkte: list[Punkt]

    @property
    def offen(self) -> list[Punkt]:
        return [p for p in self.punkte if not p.fertig]


def tabellen(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS checkliste (liste TEXT NOT NULL, punkt TEXT NOT NULL, erledigt TEXT NOT NULL, "
               "PRIMARY KEY (liste, punkt))")


def abhaken(db, liste: str, punkt: str, an: bool = True) -> None:
    tabellen(db)
    if an:
        db.execute("INSERT OR REPLACE INTO checkliste VALUES (?, ?, ?)", (liste, punkt, date.today().isoformat()))
    else:
        db.execute("DELETE FROM checkliste WHERE liste = ? AND punkt = ?", (liste, punkt))
    db.commit()


def _erledigt(db, liste: str) -> dict[str, str]:
    tabellen(db)
    return {p: d for p, d in db.execute("SELECT punkt, erledigt FROM checkliste WHERE liste = ?", (liste,))}


def _versuch(f, standard=(None, "")):
    try:
        return f()
    except Exception as e:  # noqa: BLE001 – ein fehlender Teil soll die Checkliste nicht verhindern
        LOG.debug("Checkliste: %s", e)
        return standard


# ---------------------------------------------------------------- Monats-Check

def _buchungen(db, bis: date):
    import budget as bu
    daten = [b["datum"] for b in bu.alle(db)]
    if not daten:
        return False, "noch keine Buchungen importiert"
    letzte = max(daten)
    return letzte >= bis.isoformat(), f"Buchungen bis {date.fromisoformat(letzte[:10]):%d.%m.%Y}"


def _saldi(db, heute: date, tage: int = 40):
    import vermoegen as vm
    alt = [x["name"] for x in vm.konten(db) if not x.get("aufgeloest") and x["art"] in ("bank", "depot", "krypto",
                                                                                         "kindersparen")
           and (not x.get("datum") or x["datum"] < (heute - timedelta(days=tage)).isoformat())]
    if alt:
        return False, f"älter als {tage} Tage: {', '.join(alt[:5])}{' …' if len(alt) > 5 else ''}"
    return True, "alle Saldi aktuell"


def _aufgaben(k, db, heute: date):
    if getattr(_LOKAL, "in_erinnerungen", False):
        return None, ""
    import erinnerungen as er
    faellig = [e for e in er.alle(k, db, heute) if e.tage(heute) <= 7 and not e.schluessel.startswith("checkliste-")]
    if faellig:
        return False, f"{len(faellig)} fällig: {', '.join(e.titel for e in faellig[:3])}{' …' if len(faellig) > 3 else ''}"
    return True, "nichts fällig"


def _pruefen(k, db):
    import herkunft
    zu = [i for i in herkunft.alle(db, k).values() if i.status in ("pruefen", "beispiel")]
    if zu:
        return False, f"{len(zu)} Wert(e) zu prüfen bzw. Beispielwerte"
    return True, "alle Werte geprüft"


def _steuern(k, db, heute: date):
    import steuerzahlung as sz
    ueber = [p for p in sz.auswerten(k, db, heute) if p.offen > 0.5 and p.faellig < heute]
    if ueber:
        return False, f"überfällig: {', '.join(f'{p.name} {p.jahr}' for p in ueber[:3])}"
    return True, "keine überfälligen Steuern"


def monat(k: dict, db, heute: date | None = None) -> Liste:
    heute = heute or date.today()
    schl = f"monat-{heute:%Y-%m}"
    ende_vormonat = heute.replace(day=1) - timedelta(days=1)
    punkte = [
        Punkt("buchungen", "Kontoauszüge importieren",
              f"Bankauszüge bis Ende {ende_vormonat:%m.%Y} hochladen – sie füllen Budget und Liquidität.", "vermoegen",
              *_versuch(lambda: _buchungen(db, ende_vormonat - timedelta(days=3)))),
        Punkt("saldi", "Saldi aktualisieren", "Kontostände von Bankkonten, Depot und Krypto eintragen bzw. importieren "
              "(3a, Policen und Hypothek genügen einmal im Jahr).",
              "vermoegen", *_versuch(lambda: _saldi(db, heute))),
        Punkt("aufgaben", "Fällige Aufgaben erledigen", "Was in den nächsten 7 Tagen fällig ist.", "uebersicht",
              *_versuch(lambda: _aufgaben(k, db, heute))),
        Punkt("steuern", "Steuerzahlungen erfassen", "Bezahlte Steuerrechnungen im Steuerkonto eintragen.",
              "steuerzahlung", *_versuch(lambda: _steuern(k, db, heute))),
        Punkt("pruefen", "Erkannte Werte bestätigen",
              "Werte aus hochgeladenen Dokumenten und automatischen Abgleichen prüfen und bestätigen.",
              "datenqualitaet", *_versuch(lambda: _pruefen(k, db))),
        Punkt("dokumente", "Neue Dokumente hochladen",
              "Neue Policen, Ausweise, Steuerrechnungen und Verträge des Monats – die App erkennt die Werte.",
              "dokumente"),
    ]
    erl = _erledigt(db, schl)
    for p in punkte:
        p.erledigt = erl.get(p.schluessel, "")
    return Liste(schl, f"Monats-Check {heute:%m.%Y}", date(heute.year, heute.month, min(10, 28)), punkte)


# ---------------------------------------------------------------- Jahresabschluss

def _saldi_jahresende(db, jahr: int):
    import vermoegen as vm
    ohne = []
    for x in vm.konten(db):
        if x.get("aufgeloest") or x["art"] in ("immobilie", "fahrzeug"):
            continue
        n = db.execute("SELECT COUNT(*) FROM saldi WHERE konto_id = ? AND datum BETWEEN ? AND ?",
                       (x["id"], f"{jahr}-12-24", f"{jahr + 1}-01-07")).fetchone()[0]
        if not n:
            ohne.append(x["name"])
    if ohne:
        return False, f"ohne Saldo per 31.12.: {', '.join(ohne[:5])}{' …' if len(ohne) > 5 else ''}"
    return True, "alle Konten per 31.12."


def _dokument(db, typen: tuple[str, ...], ab: str):
    import dokumente as dk
    gef = [d for d in dk.alle(db) if d["typ"] in typen and (d.get("stichtag") or d["hochgeladen"][:10]) >= ab]
    return (True, f"{len(gef)} hochgeladen") if gef else (None, "")


def jahr(k: dict, db, heute: date | None = None) -> Liste:
    heute = heute or date.today()
    j = heute.year - 1 if heute.month <= 6 else heute.year
    schl = f"jahr-{j}"
    wohnen = bool((k.get("wohnen") or {}).get("aktiv"))
    punkte = [
        Punkt("saldi", f"Saldi per 31.12.{j} erfassen", "Alle Konten mit dem Stand per Jahresende – für Steuern und "
              "Vermögensverlauf.", "vermoegen", *_versuch(lambda: _saldi_jahresende(db, j))),
        Punkt("lohn", "Lohnausweise ablegen", "Lohnausweis jeder Person (Steuererklärung, Lohn prüfen).", "dokumente"),
        Punkt("dreia", "3a-Bescheinigungen", "Bescheinigungen der Einzahlungen in die Säule 3a.", "vorsorge",
              *_versuch(lambda: _dokument(db, ("saeule3a",), f"{j}-12-01"))),
        Punkt("pk", "Neuer Vorsorgeausweis", "PK-Ausweis per 1.1. hochladen – Altersguthaben, Einkaufspotenzial, Risiko.",
              "vorsorge", *_versuch(lambda: _dokument(db, ("pk_ausweis",), f"{j + 1}-01-01"))),
        Punkt("wertschriften", "Zins- und Wertschriftenausweise", "Steuerauszug bzw. Zinsausweise der Banken.", "dokumente"),
        *([Punkt("hypothek", "Hypothekarzins und Unterhalt", "Zinsbestätigung der Bank und Belege für den "
                 "Liegenschaftsunterhalt.", "wohnen")] if wohnen else []),
        Punkt("abzuege", "Belege für Abzüge", "Krankheitskosten, Spenden, Kinderbetreuung, Weiterbildung.", "steuererklaerung"),
        Punkt("praemien", "Neue Prämien eintragen", "Krankenkasse und andere Versicherungen mit den Prämien des neuen "
              "Jahres.", "versicherungen"),
        Punkt("erklaerung", f"Steuererklärung {j} einreichen", "Im Kanton Basel-Landschaft bis 31. März (Frist "
              "verlängerbar).", "steuererklaerung"),
    ]
    erl = _erledigt(db, schl)
    for p in punkte:
        p.erledigt = erl.get(p.schluessel, "")
    return Liste(schl, f"Jahresabschluss {j}", date(j + 1, 3, 31), punkte)


def erinnerungen(k: dict, db, heute: date | None = None) -> list:
    from erinnerungen import Erinnerung
    heute = heute or date.today()
    erg = []
    _LOKAL.in_erinnerungen = True
    try:
        m = monat(k, db, heute)
    finally:
        _LOKAL.in_erinnerungen = False
    if m.offen and heute.day >= 1:
        erg.append(Erinnerung(f"checkliste-{m.schluessel}", m.titel, m.faellig,
                              f"Noch offen: {', '.join(p.titel for p in m.offen[:3])}"
                              + (" …" if len(m.offen) > 3 else "") + ".", "checklisten"))
    if 1 <= heute.month <= 4:
        j = jahr(k, db, heute)
        if j.offen:
            erg.append(Erinnerung(f"checkliste-{j.schluessel}", j.titel, j.faellig,
                                  f"{len(j.offen)} von {len(j.punkte)} Punkten offen.", "checklisten#jahr"))
    return erg
