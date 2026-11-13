"""Vorschläge für die Weiterentwicklung – aus den eigenen Daten abgeleitet und anonymisiert zum Weitergeben.

Quellen:
- Dokumente: von Hand korrigierte Werte (Erkennung lag falsch), nicht erkannte Felder, Arten und Sparten, PDFs ohne Text
- Protokoll: Warnungen und Fehler der letzten 30 Tage, gruppiert
- Kanton: fehlende kantonale Werte (Unterhaltspauschale, Eigenmietwert Bund, Fristen)
- Einstellungen: Felder mit roter Ampel
- eigene Ideen

Weitergegeben wird nur, was die Person selbst kopiert, herunterlädt oder als GitHub-Issue öffnet. Namen, Orte,
Policen- und Kontonummern, Dateinamen, E-Mail, IBAN, AHV-Nummer, Datumsangaben und Beträge werden ersetzt.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

LOG = logging.getLogger("finanz")

HOCH, MITTEL, TIEF = 3, 2, 1
PRIO_TEXT = {HOCH: "hoch", MITTEL: "mittel", TIEF: "tief"}
ISSUE_MAX = 6000            # Zeichen im Issue-Text (die URL darf nicht zu lang werden)

# Erwartete Werte je Steuerdokument-Art; Tupel = eines davon genügt
STEUER_ERWARTET = {
    "veranlagung": [("steuerbar_kanton",), ("steuerbar_bund",), ("steuerbares_vermoegen",),
                    ("steuer_kanton_gemeinde", "staatssteuer"), ("bundessteuer",)],
    "erklaerung": [("steuerbar_kanton",), ("steuerbar_bund",), ("einkuenfte_total",)],
    "rechnung": [("steuer_kanton_gemeinde", "staatssteuer", "bundessteuer")],
}
# Erwartete Felder je Versicherungssparte (alle Sparten: Prämie, Versicherer)
VERSICHERUNG_ERWARTET = {"kvg": ["franchise", "modell"], "vvg": ["produkte"],
                         "erwerbsunfaehigkeit": ["iv_rente_jahr", "iv_wartefrist_monate"]}
# Persönliche Felder werden nie verglichen oder genannt
VERSICHERUNG_PRIVAT = {"police", "person", "geburtsdatum", "notiz"}
# Schlüssel in finanz.yaml, deren Werte persönlich sind
PRIVATE_SCHLUESSEL = re.compile(r"name|vorname|ort|gemeinde|strasse|adresse|plz|email|mail|telefon|natel|arzt|kontakt|"
                                r"police|iban|nummer|ahv|arbeitgeber|partner|bank|konto|person|anlaufstelle|notiz|"
                                r"beguenstigt|erbe|vormund|beistand|schule|kita|hinweis|bemerkung", re.I)


# Schlüssel, deren Werte Namen sind – nur hier werden auch einzelne Wörter (Vor-/Nachname) ersetzt
NAMEN_SCHLUESSEL = re.compile(r"name|vorname|person|partner|arbeitgeber|kontakt|arzt|beguenstigt|erbe|vormund|beistand",
                              re.I)


@dataclass
class Vorschlag:
    bereich: str
    titel: str
    detail: str = ""
    anzahl: int = 1
    gewicht: int = MITTEL
    schluessel: str = field(default="", init=False)

    def __post_init__(self):
        self.schluessel = hashlib.sha1(f"{self.bereich}|{self.titel}".encode()).hexdigest()[:12]


# ---------------------------------------------------------------- Anonymisieren

def _vokabular(db) -> set[str]:
    """Wörter, die die App selbst verwendet (Beschriftungen, Arten, Anbieter) – werden nie ersetzt."""
    import dokumente as dk
    import kantone
    import sichtung
    import steuerdokumente as sd
    import versicherungen as vi
    texte = [*vi.SPARTEN.values(), *dk.TYPEN.values(), *sd.TYPEN.values(), *sichtung.VERTRAG_FELDER.values(),
             *(b for b, _ in sd.FELDER.values()), *(b for b, _ in dk.ZIELE.values()), *dk.ANBIETER_3A,
             *kantone.NAMEN.values(), "Feld fehlt nach dem Einlesen", "Wert wurde von Hand korrigiert"]
    for tabelle, spalte in (("vertraege", "versicherer"), ("vorsorge_dok", "anbieter")):
        try:
            texte += [w for (w,) in db.execute(f"SELECT DISTINCT {spalte} FROM {tabelle}") if w]   # noqa: S608
        except Exception:  # noqa: BLE001
            pass
    return {w.lower() for t in texte for w in [t, *re.split(r"[\s,;/()+–-]+", str(t))] if w}


def _private_texte(k: dict, db) -> list[str]:
    """Alle persönlichen Zeichenketten aus Konfiguration und Datenbank (Namen, Orte, Nummern, Dateinamen)."""
    gefunden: set[str] = set()
    namen: set[str] = set()

    def lauf(x, schluessel=""):
        if isinstance(x, dict):
            for kk, v in x.items():
                # Schlüssel von Wörterbüchern können selbst Namen sein (z. B. anteil_immobilie: {Name: 50})
                if isinstance(v, (int, float)) and isinstance(kk, str) and PRIVATE_SCHLUESSEL.search(schluessel):
                    gefunden.add(kk)
                    namen.add(kk)
                lauf(v, str(kk))
        elif isinstance(x, list):
            for v in x:
                lauf(v, schluessel)
        elif isinstance(x, str) and PRIVATE_SCHLUESSEL.search(schluessel):
            gefunden.add(x)
            if NAMEN_SCHLUESSEL.search(schluessel):
                namen.add(x)

    lauf(k)
    abfragen = [("vertraege", ["police", "person", "dateiname", "geburtsdatum", "notiz"]),
                ("vorsorge_dok", ["person", "dateiname"]), ("steuer_dok", ["person", "dateiname"]),
                ("konten", ["name", "person"])]
    for tabelle, spalten in abfragen:
        try:
            vorhanden = {r[1] for r in db.execute(f"PRAGMA table_info({tabelle})")}   # noqa: S608 – feste Namen
            for sp in (s for s in spalten if s in vorhanden):
                for (w,) in db.execute(f"SELECT DISTINCT {sp} FROM {tabelle}"):   # noqa: S608
                    if isinstance(w, str):
                        gefunden.add(w)
                        if sp == "dateiname":
                            gefunden.add(Path(w).stem)
                        if sp in ("person", "name"):
                            namen.add(w)
        except Exception:  # noqa: BLE001 – Tabelle fehlt
            continue
    vokabular = _vokabular(db)
    teile: set[str] = set()
    for t in gefunden:
        t = t.strip()
        if len(t) >= 3 and t.lower() not in vokabular:
            teile.add(t)
    for t in namen:
        # einzelne Wörter von Namen («Vorname Nachname-Doppelname»), aber keine kurzen Wörter wie «von»
        teile.update(w for w in re.split(r"[\s,;/-]+", t.strip())
                     if len(w) >= 3 and not w.isdigit() and w.lower() not in vokabular)
    return sorted(teile, key=len, reverse=True)


MUSTER = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "‹E-Mail›"),
    (re.compile(r"\bCH\d{2}(?:\s?[0-9A-Z]{4}){4}\s?[0-9A-Z]\b", re.I), "‹IBAN›"),
    (re.compile(r"\b756[.\s]?\d{4}[.\s]?\d{4}[.\s]?\d{2}\b"), "‹AHV-Nr›"),
    (re.compile(r"(?:\+41|\b0)\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}\b"), "‹Telefon›"),
    (re.compile(r"\b\d{1,2}\.\d{1,2}\.(?:19|20)\d{2}\b|\b(?:19|20)\d{2}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b"),
     "‹Datum›"),
    (re.compile(r"(?:/[\w.\-]+){2,}"), "‹Pfad›"),
    (re.compile(r"(?:CHF|EUR|Fr\.)\s?-?\d[\d'’ .,]*"), "‹Betrag›"),
    (re.compile(r"\b\d{1,3}(?:['’]\d{3})+(?:[.,]\d+)?\b|\b\d{4,}(?:[.,]\d+)?\b"), "‹Zahl›"),
]


def _muster(text: str) -> str:
    for muster, ersatz in MUSTER:
        text = muster.sub(ersatz, text)
    return text


def anonymisieren(text: str, private: list[str]) -> str:
    text = _muster(text)
    for t in private:
        text = re.sub(r"(?<!\w)" + re.escape(t) + r"(?!\w)", "‹…›", text, flags=re.I)
    return text


# ---------------------------------------------------------------- Quellen

def _problem(probleme: dict | None, schluessel: str, titel: str, text: str, feld: str) -> None:
    """Dokument mit Erkennungsproblem merken – für anonymisierte Textauszüge."""
    if probleme is None:
        return
    p = probleme.setdefault(schluessel, {"titel": titel, "text": text, "felder": set()})
    p["felder"].add(feld)


def _zaehlen(ziel: dict, schluessel: tuple, gewicht: int = MITTEL) -> None:
    a, g = ziel.get(schluessel, (0, gewicht))
    ziel[schluessel] = (a + 1, max(g, gewicht))


def _vorsorge(db, erg: dict, probleme: dict | None = None) -> None:
    import dokumente as dk
    try:
        dk.tabellen(db)
        alle = dk.alle(db)
    except Exception:  # noqa: BLE001
        return
    beschriftung = {s: t for s, (t, _) in dk.ZIELE.items()}
    for d in alle:
        text = d.get("text") or ""
        if d.get("datei") and not text.strip():
            _zaehlen(erg, ("Dokumente erkennen", "Vorsorgedokumente ohne Text – auch die Texterkennung (OCR) fand nichts",
                           ""), HOCH)
            continue
        if not text.strip():
            continue
        anbieter = d.get("anbieter") or "unbekannter Anbieter"
        e = dk.erkennen(text)
        if d["typ"] == "sonstiges":
            _zaehlen(erg, ("Dokumente erkennen", f"Vorsorgedokument nicht erkannt ({anbieter})",
                           "Art «Sonstiges» – Stichworte für diese Dokumentart fehlen"), MITTEL)
            _problem(probleme, f"d:{d['id']}", f"Vorsorgedokument ({anbieter})", text, "typ")
            continue
        art = dk.TYPEN.get(d["typ"], d["typ"])
        dok = (f"d:{d['id']}", f"{art} ({anbieter})", text)
        if d.get("quelle") == "hand":
            if e["typ"] != d["typ"]:
                _zaehlen(erg, ("Dokumente erkennen", f"{art} ({anbieter}): als «{dk.TYPEN.get(e['typ'], e['typ'])}» erkannt",
                               "von Hand auf die richtige Art korrigiert"), HOCH)
            for f in sorted(set(d["werte"]) | set(e["werte"])):
                if d["werte"].get(f) not in (None, "") and d["werte"].get(f) != e["werte"].get(f):
                    wie = "nicht erkannt" if e["werte"].get(f) in (None, "") else "falsch erkannt"
                    _zaehlen(erg, ("Dokumente erkennen", f"{art} ({anbieter}): «{beschriftung.get(f, f)}» {wie}",
                                   "Wert wurde von Hand korrigiert"), HOCH)
                    _problem(probleme, *dok, f)
        else:
            for f in dk.WERTE_JE_TYP.get(d["typ"], []):
                if d["werte"].get(f) in (None, ""):
                    _zaehlen(erg, ("Dokumente erkennen", f"{art} ({anbieter}): «{beschriftung.get(f, f)}» nicht erkannt",
                                   "Feld fehlt nach dem Einlesen"), MITTEL)
                    _problem(probleme, *dok, f)


def _steuern(k: dict, db, erg: dict, probleme: dict | None = None) -> None:
    import steuerdokumente as sd
    try:
        sd.tabellen(db)
        alle = sd.alle(db)
    except Exception:  # noqa: BLE001
        return
    kanton = str(k["haushalt"].get("kanton") or "").upper() or "?"
    beschriftung = {s: t for s, (t, _) in sd.FELDER.items()}
    for d in alle:
        text = d.get("text") or ""
        if d.get("datei") and not text.strip():
            _zaehlen(erg, ("Dokumente erkennen", "Steuerdokumente ohne Text – auch die Texterkennung (OCR) fand nichts", ""),
                     HOCH)
            continue
        if not text.strip():
            continue
        art = f"{sd.TYPEN.get(d['typ'], d['typ'])} Kanton {kanton}"
        if d["typ"] == "sonstiges":
            _zaehlen(erg, ("Dokumente erkennen", f"Steuerdokument nicht erkannt (Kanton {kanton})",
                           "Art «Sonstiges» – Stichworte für diese Dokumentart fehlen"), MITTEL)
            _problem(probleme, f"s:{d['id']}", f"Steuerdokument (Kanton {kanton})", text, "typ")
            continue
        e = sd.erkennen(text)
        dok = (f"s:{d['id']}", art, text)
        if d.get("quelle") == "hand":
            if e["typ"] != d["typ"]:
                _zaehlen(erg, ("Dokumente erkennen", f"{art}: als «{sd.TYPEN.get(e['typ'], e['typ'])}» erkannt",
                               "von Hand auf die richtige Art korrigiert"), HOCH)
            for f in sorted(set(d["werte"]) | set(e["werte"])):
                if d["werte"].get(f) not in (None, "") and d["werte"].get(f) != e["werte"].get(f):
                    wie = "nicht erkannt" if e["werte"].get(f) in (None, "") else "falsch erkannt"
                    _zaehlen(erg, ("Dokumente erkennen", f"{art}: «{beschriftung.get(f, f)}» {wie}",
                                   "Wert wurde von Hand korrigiert"), HOCH)
                    _problem(probleme, *dok, f)
        else:
            for gruppe in STEUER_ERWARTET.get(d["typ"], []):
                if all(d["werte"].get(f) in (None, "") for f in gruppe):
                    namen = " / ".join(beschriftung.get(f, f) for f in gruppe)
                    _zaehlen(erg, ("Dokumente erkennen", f"{art}: «{namen}» nicht erkannt", "Feld fehlt nach dem Einlesen"),
                             MITTEL)
                    _problem(probleme, *dok, gruppe[0])


def _versicherungen(db, erg: dict, probleme: dict | None = None) -> None:
    import sichtung
    import versicherungen as vi
    try:
        vi.tabellen(db)
        alle = vi.alle(db)
    except Exception:  # noqa: BLE001
        return
    erkannt_je_datei: dict[str, dict] = {}
    for v in alle:
        if v.get("quelle") == "liste" or not v.get("datei"):
            continue
        text = v.get("text") or ""
        if not text.strip():
            _zaehlen(erg, ("Dokumente erkennen", "Policen ohne Text – auch die Texterkennung (OCR) fand nichts", ""), HOCH)
            continue
        versicherer = v.get("versicherer") or "unbekannter Versicherer"
        sparte = vi.SPARTEN.get(v["sparte"], v["sparte"])
        if v["datei"] not in erkannt_je_datei:
            erkannt_je_datei[v["datei"]] = vi.erkennen(text)
        e = erkannt_je_datei[v["datei"]]
        if v["sparte"] == "vvg" and e.get("_zusatz"):
            e = e["_zusatz"]
        dok = (f"v:{v['datei']}", f"{sparte} ({versicherer})", text)
        if v["sparte"] == "sonstiges":
            _zaehlen(erg, ("Dokumente erkennen", f"Versicherungssparte nicht erkannt ({versicherer})",
                           "Sparte «Sonstiges» – Stichworte fehlen"), MITTEL)
            _problem(probleme, *dok, "sparte")
        if v.get("quelle") == "hand":
            for f in vi.FELDER:
                if f in VERSICHERUNG_PRIVAT or v.get(f) in (None, "", 0):
                    continue
                w = e.get(f)
                gleich = (w == v.get(f) or (isinstance(w, (int, float)) and isinstance(v.get(f), (int, float))
                                            and abs(w - v[f]) < 0.005))
                if not gleich:
                    wie = "nicht erkannt" if w in (None, "", 0) else "falsch erkannt"
                    _zaehlen(erg, ("Dokumente erkennen",
                                   f"{sparte} ({versicherer}): «{sichtung.VERTRAG_FELDER.get(f, f)}» {wie}",
                                   "Wert wurde von Hand korrigiert"), HOCH)
                    _problem(probleme, *dok, f)
        else:
            for f in ["praemie_jahr", "versicherer"] + VERSICHERUNG_ERWARTET.get(v["sparte"], []):
                if v.get(f) in (None, "", 0):
                    _zaehlen(erg, ("Dokumente erkennen",
                                   f"{sparte} ({versicherer}): «{sichtung.VERTRAG_FELDER.get(f, f)}» nicht erkannt",
                                   "Feld fehlt nach dem Einlesen"), MITTEL)
                    _problem(probleme, *dok, f)


def _normalisieren(meldung: str) -> str:
    erste = meldung.splitlines()[0]
    ausnahme = ""
    if "Traceback" in meldung:
        zeilen = [z.strip() for z in meldung.splitlines() if z.strip()]
        stelle = next((re.sub(r'.*[/\\](\w+\.py)", line \d+, in (\w+).*', r"\1:\2", z)
                       for z in reversed(zeilen) if z.startswith("File ") and "/app/" in z.replace("\\", "/")), "")
        ausnahme = (zeilen[-1].split(":")[0] if zeilen else "") + (f" in {stelle}" if stelle else "")
    erste = re.sub(r"Command '?\[[^\]]*\]'?", "Befehl", erste)          # Programmaufrufe mit Pfaden kürzen
    erste = re.sub(r"'[^']*'|\"[^\"]*\"|«[^»]*»", "‹…›", _muster(erste))
    erste = re.sub(r"\b\d+\b", "#", erste)
    return (erste[:160] + (f" – {ausnahme}" if ausnahme else "")).strip()


def seit_version(eintraege: list[tuple[str, str, str]], version: str, muster: str) -> str | None:
    """Zeit des ersten Starts der aktuellen Version (nach dem letzten Start einer anderen Version), sonst None.

    `eintraege`: (Zeit, Stufe, Text) neueste zuerst; `muster`: Regex mit einer Gruppe für die Version."""
    seit, vorher = None, None
    for zeit, _stufe, text in reversed(eintraege):
        m = re.search(muster, text)
        if not m:
            continue
        if m.group(1) == version and vorher != version:
            seit = zeit
        vorher = m.group(1)
    return seit if vorher == version else None


def _protokoll(daten: Path, erg: dict, tage: int = 30) -> None:
    """Warnungen und Fehler seit dem Start der installierten Version – Behobenes aus älteren Versionen zählt nicht."""
    import meta
    alle = meta.protokoll(daten / "finanz.log", "INFO", 20000)
    seit = seit_version(alle, meta.version(), r"Finanzplanung (\S+) startet")
    grenze = seit or (datetime.now() - timedelta(days=tage)).strftime("%Y-%m-%d")
    hinweis = f"seit Version {meta.version()}" if seit else f"im Protokoll der letzten {tage} Tage"
    for zeit, stufe, text in alle:
        if stufe not in ("WARNING", "ERROR", "CRITICAL") or zeit < grenze:
            continue
        gewicht = HOCH if stufe in ("ERROR", "CRITICAL") or "Traceback" in text else MITTEL
        _zaehlen(erg, ("Fehler und Warnungen", f"{stufe}: {_normalisieren(text)}", hinweis), gewicht)


def _kanton(k: dict, erg: dict) -> None:
    import kantone
    kanton = str(k["haushalt"].get("kanton") or "").upper()
    if not kanton:
        return
    if kanton not in kantone.FRISTEN:
        _zaehlen(erg, ("Kantonale Werte", f"Kanton {kanton}: Fristen der Steuererklärung nicht hinterlegt",
                       "Erinnerungen nutzen Standardfristen"), MITTEL)
    if (k.get("wohnen") or {}).get("aktiv"):
        if kanton not in kantone.PAUSCHAL_STAAT:
            _zaehlen(erg, ("Kantonale Werte", f"Kanton {kanton}: Unterhaltspauschale Staatssteuer nicht hinterlegt",
                           "es gelten die Sätze des Bundes (10 % / 20 %)"), MITTEL)
        if kanton not in kantone.EMW_BUND_FAKTOR and not (k["wohnen"].get("eigenmietwert_bund")):
            _zaehlen(erg, ("Kantonale Werte", f"Kanton {kanton}: Faktor Eigenmietwert Bund prüfen",
                           "heute Bund = Staat (Faktor 1)"), TIEF)


def _einstellungen(k: dict, erg: dict) -> None:
    import ampel as am
    import pruefung
    import seiten
    try:
        zf = pruefung.zusammenfassung(k, seiten.alle_felder(k))
    except Exception:  # noqa: BLE001
        return
    for pfad, text, _grund in zf.get(am.ROT, []):
        feld = re.sub(r"^personen\.\d+\.", "Person · ", pfad)
        _zaehlen(erg, ("Einstellungen", f"Rote Ampel bei «{text}» ({feld})",
                       "Prüfregel zu streng, Feld unklar oder Wert fehlt"), TIEF)


# ---------------------------------------------------------------- Status und eigene Ideen

def tabellen(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS vorschlag_status (schluessel TEXT PRIMARY KEY, status TEXT NOT NULL, "
               "datum TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS vorschlag_idee (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, "
               "datum TEXT NOT NULL)")


# Bereiche, deren Vorschläge dauerhaft aus den Daten folgen (Protokollmeldungen beginnen mit jeder Version neu)
VERLAUF_BEREICHE = ("Dokumente erkennen", "Kantonale Werte", "Einstellungen", "Leistung")


def _verlauf_tabelle(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS vorschlag_verlauf (schluessel TEXT PRIMARY KEY, bereich TEXT NOT NULL, "
               "titel TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', version_zuerst TEXT NOT NULL, "
               "version_zuletzt TEXT NOT NULL, erledigt_version TEXT, erledigt_datum TEXT, durch TEXT)")


def verlauf_nachfuehren(db, liste: list[Vorschlag], version: str | None = None) -> None:
    """Offene Vorschläge merken; was nicht mehr vorkommt, gilt als erledigt – durch ein Update, wenn die Version
    seit dem letzten Auftreten gewechselt hat, sonst durch eine Änderung an den Daten."""
    if version is None:
        import meta
        version = meta.version()
    _verlauf_tabelle(db)
    jetzt = datetime.now().isoformat(timespec="seconds")
    offen = {v.schluessel: v for v in liste if v.bereich in VERLAUF_BEREICHE}
    for s, v in offen.items():
        db.execute("INSERT INTO vorschlag_verlauf (schluessel, bereich, titel, detail, version_zuerst, version_zuletzt) "
                   "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(schluessel) DO UPDATE SET version_zuletzt = excluded.version_zuletzt, "
                   "erledigt_version = NULL, erledigt_datum = NULL, durch = NULL",
                   (s, v.bereich, v.titel, v.detail, version, version))
    for s, zuletzt in db.execute("SELECT schluessel, version_zuletzt FROM vorschlag_verlauf "
                                 "WHERE erledigt_version IS NULL").fetchall():
        if s not in offen:
            db.execute("UPDATE vorschlag_verlauf SET erledigt_version = ?, erledigt_datum = ?, durch = ? "
                       "WHERE schluessel = ?", (version, jetzt, "update" if zuletzt != version else "aenderung", s))
    db.commit()


def erledigt(db, nur_version: str | None = None, anzahl: int = 60) -> list[tuple[Vorschlag, str, str, str]]:
    """Erledigte Vorschläge (neueste zuerst), pro Dokument gruppiert: (Vorschlag, Version, Datum, «update»/«aenderung»)."""
    _verlauf_tabelle(db)
    sql = ("SELECT bereich, titel, detail, erledigt_version, erledigt_datum, durch FROM vorschlag_verlauf "
           "WHERE erledigt_version IS NOT NULL" + (" AND erledigt_version = ? AND durch = 'update'" if nur_version else "")
           + " ORDER BY erledigt_datum DESC, titel LIMIT ?")
    zeilen = db.execute(sql, (nur_version, anzahl) if nur_version else (anzahl,)).fetchall()
    info = {}
    roh = []
    for bereich, titel, detail, version, datum, durch in zeilen:
        marke = f"{durch}|{version}"
        info[marke] = (version, (datum or "")[:10], durch or "")
        roh.append(Vorschlag(bereich, titel.replace("falsch erkannt", "nicht erkannt"), marke))
    erg = []
    for v in _gruppieren(roh):
        v.titel = re.sub(r" nicht erkannt$", "", v.titel)
        erg.append((v, *info[v.detail]))
    return erg


def ausblenden(db, schluessel: list[str], status: str = "ausgeblendet") -> None:
    tabellen(db)
    jetzt = datetime.now().isoformat(timespec="seconds")
    for s in schluessel:
        if status:
            db.execute("INSERT OR REPLACE INTO vorschlag_status VALUES (?, ?, ?)", (s, status, jetzt))
        else:
            db.execute("DELETE FROM vorschlag_status WHERE schluessel = ?", (s,))
    db.commit()


def status(db) -> dict[str, str]:
    tabellen(db)
    return {s: st for s, st in db.execute("SELECT schluessel, status FROM vorschlag_status")}


def idee_speichern(db, text: str) -> None:
    tabellen(db)
    text = text.strip()
    if not text:
        raise ValueError("Bitte eine Idee eingeben.")
    db.execute("INSERT INTO vorschlag_idee (text, datum) VALUES (?, ?)", (text[:2000], datetime.now().isoformat(timespec="seconds")))
    db.commit()


def idee_loeschen(db, iid: int) -> None:
    tabellen(db)
    db.execute("DELETE FROM vorschlag_idee WHERE id = ?", (iid,))
    db.commit()


def ideen(db) -> list[dict]:
    tabellen(db)
    return [{"id": i, "text": t, "datum": d} for i, t, d in
            db.execute("SELECT id, text, datum FROM vorschlag_idee ORDER BY id")]


# ---------------------------------------------------------------- Sammeln und Bericht

GRUPPE = re.compile(r"^(?P<dok>.+?): «(?P<feld>.+)» (?P<wie>nicht erkannt|falsch erkannt)$")


def _gruppieren(liste: list[Vorschlag]) -> list[Vorschlag]:
    """Pro Dokument und Art des Problems eine Zeile mit allen betroffenen Feldern."""
    gruppen: dict[tuple, list[Vorschlag]] = {}
    rest = []
    for v in liste:
        m = GRUPPE.match(v.titel) if v.bereich == "Dokumente erkennen" else None
        if m:
            gruppen.setdefault((m["dok"], m["wie"], v.detail), []).append(v)
        else:
            rest.append(v)
    for (dok, wie, detail), vs_ in gruppen.items():
        if len(vs_) == 1:
            rest.append(vs_[0])
            continue
        felder = ", ".join(f"«{GRUPPE.match(v.titel)['feld']}»" for v in sorted(vs_, key=lambda x: (-x.anzahl, x.titel)))
        rest.append(Vorschlag("Dokumente erkennen", f"{dok}: {felder} {wie}", detail,
                              max(v.anzahl for v in vs_), max(v.gewicht for v in vs_)))
    return rest


def sammeln(k: dict, db, daten: Path) -> list[Vorschlag]:
    """Alle Vorschläge, bereits anonymisiert und pro Dokument gruppiert, wichtigste zuerst."""
    erg: dict[tuple, tuple[int, int]] = {}
    _vorsorge(db, erg)
    _steuern(k, db, erg)
    _versicherungen(db, erg)
    _protokoll(daten, erg)
    _kanton(k, erg)
    _einstellungen(k, erg)
    try:
        import leistung as le
        for titel, detail, gewicht in le.vorschlaege(db, daten):
            _zaehlen(erg, ("Leistung", titel, detail), gewicht)
    except Exception:  # noqa: BLE001
        LOG.exception("Vorschläge: Leistung nicht ausgewertet")
    private = _private_texte(k, db)
    liste = [Vorschlag(bereich, titel, detail, anzahl, gewicht) if bereich == "Leistung"      # nur Zeiten und Mengen
             else Vorschlag(bereich, anonymisieren(titel, private), anonymisieren(detail, private), anzahl, gewicht)
             for (bereich, titel, detail), (anzahl, gewicht) in erg.items()]
    try:
        verlauf_nachfuehren(db, liste)
    except Exception:  # noqa: BLE001 – der Verlauf ist eine Zugabe, die Vorschläge gehen vor
        LOG.exception("Vorschläge: Verlauf nicht nachgeführt")
    liste = _gruppieren(liste)
    eigene: dict[str, int] = {}
    for i in ideen(db):
        t = anonymisieren(i["text"].strip(), private)
        eigene[t] = eigene.get(t, 0) + 1
    liste += [Vorschlag("Eigene Ideen", t, "", n, MITTEL) for t, n in eigene.items()]
    reihenfolge = ["Dokumente erkennen", "Fehler und Warnungen", "Leistung", "Kantonale Werte", "Einstellungen",
                   "Eigene Ideen"]
    liste.sort(key=lambda v: (-v.gewicht, reihenfolge.index(v.bereich) if v.bereich in reihenfolge else 9, -v.anzahl,
                              v.titel))
    return liste


# ---------------------------------------------------------------- Anonymisierte Textauszüge

# Stichwörter je Feld, um die passenden Zeilen im Dokument zu finden (sonst die Wörter der Beschriftung)
STICHWORTE = {
    "kuendigungsfrist_monate": r"k[üu]ndig|frist|vertragsdauer|verl[äa]nger",
    "praemie_jahr": r"pr[äa]mie|beitrag|zahlbar|total|j[äa]hrlich|betrag",
    "beginn": r"beginn|g[üu]ltig|ab\b|vom\b|laufzeit|dauer",
    "ablauf": r"ablauf|ende\b|bis\b|laufzeit|dauer|verfall|f[äa]llig",
    "summe": r"summe|versichert|leistung|kapital|deckung",
    "franchise": r"franchise", "modell": r"modell|hausarzt|telmed|hmo",
    "typ": r"", "sparte": r"", "versicherer": r"",
}
KOPF_FELDER = {"typ", "sparte", "versicherer"}   # dafür zählen die ersten Zeilen (Briefkopf, Titel)
# Zeilen, die nie in einen Auszug kommen: Anrede, Adresse, Personalien und Gesundheitsangaben (Vorbehalte)
PERSOENLICH = re.compile(r"geburtsdatum|\bgeb\.|nationalit|zivilstand|heimatort|versicherte\s+person|"
                         r"versicherungsnehmer|zahlbar\s+durch|anschrift|eigentümerschaft|e-?mail|@|"
                         r"erkrank|verletzung|diagnose|vorbehalt|gelenk|befund|operation|raucher|leiden\b", re.I)
ADRESSE = re.compile(r"\b(?:herrn?|frau|familie|eheleute)\b|\b\d{4}\s+[A-ZÄÖÜ][a-zäöüé]+|"
                     r"\b[A-ZÄÖÜ][a-zäöüé]+(?:strasse|weg|gasse|platz|allee|rain|ring)\s+\d", re.I)
MAX_ZEILEN = 40
MAX_DOKUMENTE = 12


def _stichworte(feld: str) -> str:
    if feld in STICHWORTE:
        return STICHWORTE[feld]
    if feld.startswith("iv_"):
        return r"invalid|erwerbsunf|\biv\b|rente|wartefrist|pr[äa]mienbefreiung"
    import dokumente as dk
    import sichtung
    import steuerdokumente as sd
    beschriftung = {**sichtung.VERTRAG_FELDER, **{s: t for s, (t, _) in dk.ZIELE.items()},
                    **{s: b for s, (b, _) in sd.FELDER.items()}}.get(feld, feld)
    woerter = [w.lower() for w in re.findall(r"[A-Za-zÄÖÜäöüé]{5,}", beschriftung)
               if w.lower() not in {"prognose", "info", "saldo", "unter", "vermögen", "ersetzt", "policen", "heute",
                                    "einkommen", "steuerbares", "monate"}]
    return "|".join(re.escape(w[:8]) for w in woerter) or re.escape(feld)


def _auszug_anonym(zeile: str, private: list[str]) -> str:
    for t in private:
        zeile = re.sub(r"(?<!\w)" + re.escape(t) + r"(?!\w)", "‹…›", zeile, flags=re.I)
    zeile = MUSTER[0][0].sub("‹E-Mail›", zeile)
    return re.sub(r"\d", "9", zeile)


def auszug(text: str, felder: set[str], private: list[str]) -> list[str]:
    """Relevante Zeilen eines Dokuments, anonymisiert: Ziffern → 9, Namen ersetzt, Adress- und Anredezeilen weg."""
    zeilen = [" ".join(z.split()) for z in (text or "").replace("\f", "\n").splitlines()]
    zeilen = [z for z in zeilen if z]
    nehmen: set[int] = set()
    if felder & KOPF_FELDER:
        nehmen.update(range(min(10, len(zeilen))))
    muster = "|".join(f"(?:{s})" for s in (_stichworte(f) for f in felder - KOPF_FELDER) if s)
    if muster:
        rx = re.compile(muster, re.I)
        for i, z in enumerate(zeilen):
            if rx.search(z):
                nehmen.update(j for j in (i - 1, i, i + 1) if 0 <= j < len(zeilen))
    aus = []
    for i in sorted(nehmen):
        z = zeilen[i]
        if ADRESSE.search(z) or PERSOENLICH.search(z) or MUSTER[1][0].search(z) or MUSTER[2][0].search(z):
            continue
        z = _auszug_anonym(z, private)[:160]
        if z.strip("‹…› ") and (not aus or aus[-1] != z):
            aus.append(z)
        if len(aus) >= MAX_ZEILEN:
            break
    return aus


def textauszuege(k: dict, db) -> list[tuple[str, list[str]]]:
    """(Dokument-Titel, anonymisierte Zeilen) für Dokumente mit Erkennungsproblemen – nur wenn gewünscht."""
    probleme: dict = {}
    egal: dict = {}
    _vorsorge(db, egal, probleme)
    _steuern(k, db, egal, probleme)
    _versicherungen(db, egal, probleme)
    private = _private_texte(k, db)
    aus = []
    for p in sorted(probleme.values(), key=lambda p: (-len(p["felder"]), p["titel"])):
        titel = anonymisieren(p["titel"], private)
        zeilen = auszug(p["text"], p["felder"], private)
        if zeilen:
            aus.append((titel, zeilen))
        if len(aus) >= MAX_DOKUMENTE:
            break
    return aus


def bericht(vorschlaege: list[Vorschlag], version: str, kanton: str = "",
            auszuege: list[tuple[str, list[str]]] | None = None, erledigt_: list[Vorschlag] | None = None,
            leistung: list[str] | None = None) -> str:
    """Markdown-Text zum Weitergeben (nur die übergebenen, bereits anonymisierten Vorschläge und Auszüge)."""
    kopf = [f"Vorschläge aus der Finanzplanung {version}" + (f" · Kanton {kanton}" if kanton else ""),
            "", "_Automatisch abgeleitet und anonymisiert (keine Namen, Beträge, Daten oder Dateinamen)._", ""]
    teile = []
    for bereich in dict.fromkeys(v.bereich for v in vorschlaege):
        teile.append(f"### {bereich}")
        for v in (x for x in vorschlaege if x.bereich == bereich):
            n = f" ({v.anzahl}×)" if v.anzahl > 1 else ""
            d = f" – {v.detail}" if v.detail else ""
            teile.append(f"- [{PRIO_TEXT[v.gewicht]}] {v.titel}{n}{d}")
        teile.append("")
    if leistung:
        teile += ["### Leistung (Messwerte dieser Version)", "", "```", *leistung, "```", ""]
    if erledigt_:
        teile += [f"### Mit {version} erledigt", ""] + [f"- {v.titel}" for v in erledigt_] + [""]
    if auszuege:
        teile += ["### Textauszüge (anonymisiert: Ziffern → 9, Namen und Adressen entfernt)", ""]
        for titel, zeilen in auszuege:
            teile += [f"**{titel}**", "", "```", *zeilen, "```", ""]
    return "\n".join(kopf + (teile or ["Keine Vorschläge."])).strip() + "\n"


def issue_link(repo_url: str, text: str, version: str) -> str:
    body = text if len(text) <= ISSUE_MAX else text[:ISSUE_MAX] + "\n\n… (gekürzt – vollständig als Datei angehängt)"
    return (repo_url.rstrip("/") + "/issues/new?title=" + quote(f"Vorschläge aus der App ({version})")
            + "&body=" + quote(body))
