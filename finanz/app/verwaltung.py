"""Übersicht und Verwaltung aller gespeicherten Dokumente und Einträge.

Bereiche: Versicherungen (Verträge, auch aus Listen), Vorsorge- und Steuerdokumente, Buchungen pro Konto.
Schlüssel: «v:ID» Vertrag, «d:ID» Vorsorgedokument, «s:ID» Steuerdokument, «b:Konto» Buchungen eines Kontos.
Duplikate = gleicher Dateiinhalt (Prüfsumme) im gleichen Bereich; beim Bereinigen bleibt das älteste.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

BEREICHE = {"v": "Versicherungen", "d": "Vorsorge", "s": "Steuern", "b": "Buchungen"}


@dataclass
class Eintrag:
    schluessel: str
    bereich: str
    titel: str
    art: str
    person: str
    datum: str
    groesse: int
    text: str | None
    link: str
    original: str
    pruefsumme: str = ""
    duplikat_von: str = ""          # Schlüssel des älteren Eintrags mit gleichem Inhalt


def _datei(pfad: Path) -> tuple[int, str]:
    try:
        inhalt = pfad.read_bytes()
    except OSError:
        return 0, ""
    return len(inhalt), hashlib.sha1(inhalt).hexdigest()


def eintraege(db, daten: Path) -> list[Eintrag]:
    import budget as bu
    import dokumente as dk
    import steuerdokumente as sd
    import versicherungen as vi
    erg: list[Eintrag] = []
    vi.tabellen(db)
    for v in vi.alle(db):
        g, h = _datei(vi.ordner(daten) / v["datei"]) if v["datei"] else (0, "")
        titel = " · ".join(x for x in (v["versicherer"], vi.SPARTEN.get(v["sparte"], v["sparte"])) if x) or v["dateiname"]
        erg.append(Eintrag(f"v:{v['id']}", "Versicherungen", titel, v["dateiname"] if v["datei"] else "aus Liste",
                           v["person"], v["hochgeladen"][:10], g, v["text"] if v["datei"] else None,
                           f"versicherungen/{v['id']}", f"versicherungen/{v['id']}/datei" if v["datei"] else "", h))
    for modul, kurz, bereich, link in ((dk, "d", "Vorsorge", "vorsorge/dokument"), (sd, "s", "Steuern", "steuern/dokument")):
        modul.tabellen(db)
        for d in modul.alle(db):
            g, h = _datei(modul.ordner(daten) / d["datei"]) if d["datei"] else (0, "")
            art = modul.TYPEN.get(d["typ"], d["typ"]) + (f" {d['jahr']}" if kurz == "s" and d.get("jahr") else "")
            erg.append(Eintrag(f"{kurz}:{d['id']}", bereich, d["dateiname"], art, d["person"], d["hochgeladen"][:10], g,
                               d["text"], f"{link}/{d['id']}", f"{link}/{d['id']}/datei" if d["datei"] else "", h))
    bu._tabelle(db)
    for r in db.execute("SELECT konto, COUNT(*), MIN(datum), MAX(datum) FROM buchungen GROUP BY konto ORDER BY konto"):
        erg.append(Eintrag(f"b:{r[0]}", "Buchungen", r[0], f"{r[1]} Buchungen {r[2][:7]} bis {r[3][:7]}", "", r[3], 0,
                           None, "budget", ""))
    # Duplikate: gleicher Inhalt im gleichen Bereich, verschiedene Einträge (KVG und VVG aus einem PDF zählen nicht)
    erste: dict[tuple[str, str], Eintrag] = {}
    for e in sorted(erg, key=lambda e: (e.datum, e.schluessel)):
        if not e.pruefsumme:
            continue
        schl = (e.bereich, e.pruefsumme)
        if schl in erste and not (e.bereich == "Versicherungen" and _gleiche_datei(db, erste[schl], e)):
            e.duplikat_von = erste[schl].schluessel
        else:
            erste.setdefault(schl, e)
    return erg


def _gleiche_datei(db, a: Eintrag, b: Eintrag) -> bool:
    ra = db.execute("SELECT datei FROM vertraege WHERE id = ?", (int(a.schluessel[2:]),)).fetchone()
    rb = db.execute("SELECT datei FROM vertraege WHERE id = ?", (int(b.schluessel[2:]),)).fetchone()
    return bool(ra and rb and ra[0] == rb[0])


def loeschen(db, daten: Path, schluessel: list[str]) -> int:
    import budget as bu
    import dokumente as dk
    import steuerdokumente as sd
    import versicherungen as vi
    n = 0
    for s in dict.fromkeys(schluessel):
        art, _, wert = s.partition(":")
        if not wert:
            continue
        if art == "v" and wert.isdigit():
            vi.loeschen(db, daten, int(wert))
        elif art == "d" and wert.isdigit():
            dk.loeschen(db, daten, int(wert))
        elif art == "s" and wert.isdigit():
            sd.loeschen(db, daten, int(wert))
        elif art == "b":
            bu.loeschen(db, wert)
            db.commit()
        else:
            continue
        n += 1
    return n


def groesse_text(b: int) -> str:
    if b >= 1_048_576:
        return f"{b / 1_048_576:.1f} MB"
    if b >= 1024:
        return f"{b / 1024:.0f} kB"
    return f"{b} B" if b else "–"


def neue_dateien(db, daten: Path, kurz: str, dateien: list[tuple[str, bytes]]) -> tuple[list[tuple[str, bytes]], list[str]]:
    """Dateien mit gleichem Inhalt wie ein vorhandenes Dokument im gleichen Bereich überspringen."""
    bereich = BEREICHE[kurz]
    vorhanden = {e.pruefsumme: e.titel for e in eintraege(db, daten) if e.bereich == bereich and e.pruefsumme}
    neu, doppelt = [], []
    for name, inhalt in dateien:
        if not inhalt:
            continue
        h = hashlib.sha1(inhalt).hexdigest()
        if h in vorhanden:
            doppelt.append(f"{name} (schon vorhanden: {vorhanden[h]})")
        else:
            vorhanden[h] = name
            neu.append((name, inhalt))
    return neu, doppelt


PERSONEN_TABELLEN = ("konten", "vertraege", "vorsorge_dok", "steuer_dok")


def person_umbenennen_db(db, alt: str, neu: str) -> int:
    """Zuordnung von Konten, Verträgen und Dokumenten auf den neuen Namen umschreiben."""
    n = 0
    for tabelle in PERSONEN_TABELLEN:
        try:
            n += db.execute(f"UPDATE {tabelle} SET person = ? WHERE person = ?", (neu, alt)).rowcount
        except Exception:  # noqa: BLE001 – Tabelle (noch) nicht vorhanden
            pass
    db.commit()
    return n
