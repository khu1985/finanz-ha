"""Gespeicherte Dokumente nach einem App-Update neu sichten.

Die Originale (Policen, Vorsorge- und Steuerdokumente) liegen im Datenordner. Nach einem Update – oder per Knopf –
liest die App sie mit der aktuellen Erkennung neu:
- Text neu auslesen (bessere PDF-Auswertung), dann Werte neu erkennen.
- Von Hand oder per KI bearbeitete Dokumente behalten ihre Werte (nur der Text wird erneuert), ausser «auch
  bearbeitete» ist gewählt. Bei Vorsorge- und Steuerdokumenten bleibt die gewählte Person erhalten.
- Ändern sich die Werte eines bereits übernommenen Vorsorge- oder Steuerdokuments, wird es wieder als «noch nicht
  übernommen» markiert, damit man die neuen Werte prüfen kann. Krankenkassen-Policen gehen bei geänderten Werten neu
  in den Krankenkassen-Rechner; eine neu erkannte Zusatzversicherung wird als eigener Vertrag angelegt.
- Buchungen im Budget werden mit den aktuellen Regeln neu kategorisiert.
Ergebnis und Version der letzten Sichtung stehen in der Tabelle `sichtung`.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

LOG = logging.getLogger("finanz")
GESCHUETZT = {"hand", "ki"}
_SPERRE = threading.Lock()


@dataclass
class Bericht:
    zeit: str
    version: str
    ausloeser: str
    geprueft: int = 0
    geaendert: list[str] = field(default_factory=list)       # «Bereich: Dokument (Felder)»
    neu: list[str] = field(default_factory=list)
    geschuetzt: int = 0
    fehlend: int = 0                                          # Originaldatei nicht mehr vorhanden
    buchungen: int = 0
    fehler: list[str] = field(default_factory=list)
    details: list[dict] = field(default_factory=list)        # {bereich, dokument, link, feld, alt, neu}


VERTRAG_FELDER = {
    "sparte": "Sparte", "versicherer": "Versicherer", "police": "Police / Versicherten-Nr.", "person": "Person",
    "praemie_jahr": "Prämie pro Jahr", "beginn": "Beginn", "ablauf": "Ablauf", "kuendigungsfrist_monate": "Kündigungsfrist (Monate)",
    "franchise": "Franchise", "selbstbehalt": "Selbstbehalt", "summe": "Versicherungssumme",
    "unfall_eingeschlossen": "Unfall eingeschlossen", "notiz": "Notiz", "modell": "Modell", "geburtsdatum": "Geburtsdatum",
    "unfall_praemie": "Unfallanteil pro Jahr", "produkte": "Produkte",
}


def _text(wert) -> str:
    if wert is None or wert == "":
        return "–"
    if isinstance(wert, float):
        return f"{wert:,.2f}".replace(",", "'").removesuffix(".00")
    if isinstance(wert, int) and not isinstance(wert, bool):
        return f"{wert:,}".replace(",", "'")
    return str(wert)


def _name(v: dict, werte: dict) -> str:
    """«Atupri · Krankenkasse Grundversicherung · Kai»"""
    import versicherungen as vi
    sparte = werte.get("sparte") or v.get("sparte")
    teile = [werte.get("versicherer") or v.get("versicherer") or v.get("dateiname"), vi.SPARTEN.get(sparte, sparte),
             werte.get("person") or v.get("person")]
    return " · ".join(str(t) for t in teile if t)


def _anzeige(feld: str, wert):
    import krankenkasse as kk
    import versicherungen as vi
    if feld == "sparte":
        return vi.SPARTEN.get(wert, wert)
    if feld == "modell":
        return kk.MODELLE.get(wert, wert) if wert else wert
    if feld == "unfall_eingeschlossen":
        return "ja" if wert else "nein"
    return wert


def _detail(b: Bericht, bereich: str, dokument: str, link: str, feld: str, alt, neu) -> None:
    b.details.append({"bereich": bereich, "dokument": dokument, "link": link, "feld": feld,
                      "alt": _text(alt), "neu": _text(neu)})


def _tabelle(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS sichtung (id INTEGER PRIMARY KEY AUTOINCREMENT, zeit TEXT NOT NULL, "
               "version TEXT NOT NULL, bericht TEXT NOT NULL)")


def letzte(db) -> Bericht | None:
    _tabelle(db)
    r = db.execute("SELECT bericht FROM sichtung ORDER BY id DESC LIMIT 1").fetchone()
    return Bericht(**json.loads(r[0])) if r else None


def _lesen(pfad: Path, dateiname: str) -> str | None:
    import versicherungen as vi
    if not pfad.exists():
        return None
    return vi.text_auslesen(dateiname, pfad.read_bytes())


def _versicherungen(k: dict, db, daten: Path, b: Bericht, alle: bool) -> bool:
    import krankenkasse as kk
    import versicherungen as vi
    vi.tabellen(db)
    config_geaendert = False
    gruppen: dict[str, list[dict]] = {}
    for v in vi.alle(db):
        if v["datei"]:
            gruppen.setdefault(v["datei"], []).append(v)
    for datei, vertraege in gruppen.items():
        vertraege.sort(key=lambda v: v["id"])
        haupt = vertraege[0]
        text = _lesen(vi.ordner(daten) / datei, haupt["dateiname"])
        if text is None:
            b.fehlend += 1
            continue
        b.geprueft += 1
        erkannt = vi.erkennen(text)
        zusatz = erkannt.pop("_zusatz", None)
        for v, werte in ((haupt, erkannt), *(((vertraege[1], zusatz),) if zusatz and len(vertraege) > 1 else ())):
            db.execute("UPDATE vertraege SET text = ? WHERE id = ?", (text, v["id"]))
            if v["quelle"] in GESCHUETZT and not alle:
                b.geschuetzt += 1
                continue
            neu = {f: w for f, w in werte.items() if f in vi.FELDER and w not in (None, "") and v.get(f) != w
                   and not (isinstance(w, (int, float)) and isinstance(v.get(f), (int, float)) and abs(v[f] - w) < 0.005)}
            if neu:
                for f_, w in sorted(neu.items()):
                    alt, w_ = _anzeige(f_, v.get(f_)), _anzeige(f_, w)
                    _detail(b, "Versicherungen", _name(v, werte), f"versicherungen/{v['id']}",
                            VERTRAG_FELDER.get(f_, f_), alt, w_)
                vi.aktualisieren(db, v["id"], neu, quelle="muster" if text.strip() else "ohne Text")
                b.geaendert.append(f"Versicherungen: {v['versicherer'] or v['dateiname']} "
                                   f"{vi.SPARTEN.get(werte.get('sparte', v['sparte']), '')} ({', '.join(sorted(neu))})".strip())
                if werte.get("sparte") == "kvg" and kk.police_uebernehmen(k, vi.einer(db, v["id"])):
                    config_geaendert = True
        db.commit()
        if zusatz and len(vertraege) == 1:
            cur = db.execute("INSERT INTO vertraege (dateiname, hochgeladen, text, datei) VALUES (?, ?, ?, ?)",
                             (haupt["dateiname"], datetime.now().isoformat(timespec="seconds"), text, datei))
            vi.aktualisieren(db, cur.lastrowid, zusatz, quelle="muster")
            b.neu.append(f"Versicherungen: Zusatzversicherung aus {haupt['dateiname']}")
            _detail(b, "Versicherungen", _name({**haupt, **zusatz}, zusatz),
                    f"versicherungen/{cur.lastrowid}", "neuer Vertrag",
                    None, f"{zusatz.get('produkte') or 'Zusatzversicherung'}, Prämie {_text(zusatz.get('praemie_jahr'))}/Jahr")
    db.commit()
    return config_geaendert


def _dokumente(db, daten: Path, b: Bericht, alle: bool, bereich: str, modul, tabelle: str, mit_jahr: bool) -> None:
    modul.tabellen(db)
    for d in modul.alle(db):
        if not d["datei"]:
            continue
        text = _lesen(modul.ordner(daten) / d["datei"], d["dateiname"])
        if text is None:
            b.fehlend += 1
            continue
        b.geprueft += 1
        db.execute(f"UPDATE {tabelle} SET text = ? WHERE id = ?", (text, d["id"]))   # noqa: S608 – feste Tabellennamen
        db.commit()
        if d["quelle"] in GESCHUETZT and not alle:
            b.geschuetzt += 1
            continue
        e = modul.erkennen(text)
        felder = []
        if e["typ"] != d["typ"]:
            felder.append("Art")
        if e["werte"] != d["werte"]:
            felder.append("Werte")
        if mit_jahr and e.get("jahr") and e["jahr"] != d["jahr"]:
            felder.append("Jahr")
        if not mit_jahr:
            for f in ("anbieter", "stichtag"):
                if e.get(f) and e[f] != d.get(f):
                    felder.append(f.capitalize())
        if not felder:
            continue
        link = f"{'steuern' if mit_jahr else 'vorsorge'}/dokument/{d['id']}"
        typen = modul.TYPEN
        if e["typ"] != d["typ"]:
            _detail(b, bereich, d["dateiname"], link, "Art", typen.get(d["typ"], d["typ"]), typen.get(e["typ"], e["typ"]))
        if mit_jahr and e.get("jahr") and e["jahr"] != d["jahr"]:
            _detail(b, bereich, d["dateiname"], link, "Jahr", str(d["jahr"] or ""), str(e["jahr"]))
        if not mit_jahr:
            for f_ in ("anbieter", "stichtag"):
                if e.get(f_) and e[f_] != d.get(f_):
                    _detail(b, bereich, d["dateiname"], link, f_.capitalize(), d.get(f_), e[f_])
        beschriftung = ({s_: t for s_, (t, _) in modul.FELDER.items()} if mit_jahr
                        else {s_: t for s_, (t, _) in modul.ZIELE.items()})
        for s_ in sorted(set(d["werte"]) | set(e["werte"])):
            if d["werte"].get(s_) != e["werte"].get(s_):
                _detail(b, bereich, d["dateiname"], link, beschriftung.get(s_, s_), d["werte"].get(s_), e["werte"].get(s_))
        person = d["person"] or e.get("person", "")
        if mit_jahr:
            modul.speichern(db, d["id"], e["typ"], e.get("jahr") or d["jahr"], person, e["werte"], quelle="muster")
        else:
            modul.speichern(db, d["id"], e["typ"], person, e["werte"], quelle="muster")
            db.execute("UPDATE vorsorge_dok SET anbieter = ?, stichtag = ? WHERE id = ?",
                       (e.get("anbieter") or d.get("anbieter", ""), e.get("stichtag") or d.get("stichtag", ""), d["id"]))
        if d.get("uebernommen") and "Werte" in felder:
            db.execute(f"UPDATE {tabelle} SET uebernommen = '' WHERE id = ?", (d["id"],))   # noqa: S608
            felder.append("bitte neu übernehmen")
        b.geaendert.append(f"{bereich}: {d['dateiname']} ({', '.join(felder)})")
        db.commit()
    db.commit()


def ausfuehren(k: dict, db, daten: Path, ausloeser: str = "Knopf", alle: bool = False) -> Bericht:
    import budget as bu
    import dokumente as dk
    import konfig
    import meta
    import steuerdokumente as sd
    with _SPERRE:
        b = Bericht(datetime.now().isoformat(timespec="seconds"), meta.version(), ausloeser)
        speichern = False
        for name, f in (("Versicherungen", lambda: _versicherungen(k, db, daten, b, alle)),
                        ("Vorsorgedokumente", lambda: _dokumente(db, daten, b, alle, "Vorsorge", dk, "vorsorge_dok", False)),
                        ("Steuerdokumente", lambda: _dokumente(db, daten, b, alle, "Steuern", sd, "steuer_dok", True)),
                        ("Budget", lambda: setattr(b, "buchungen", bu.neu_kategorisieren(db, k)))):
            try:
                if f():
                    speichern = True
            except Exception as e:  # noqa: BLE001
                LOG.warning("Neu sichten (%s): %s", name, e)
                b.fehler.append(f"{name}: {e}")
        if speichern:
            konfig.speichern(k)
        _tabelle(db)
        db.execute("INSERT INTO sichtung (zeit, version, bericht) VALUES (?, ?, ?)",
                   (b.zeit, b.version, json.dumps(asdict(b), ensure_ascii=False)))
        db.commit()
        LOG.info("Dokumente neu gesichtet (%s): %d geprüft, %d geändert, %d neu, %d von Hand bearbeitet belassen, "
                 "%d Buchungen neu kategorisiert", ausloeser, b.geprueft, len(b.geaendert), len(b.neu), b.geschuetzt,
                 b.buchungen)
        return b


def nach_update(laden, verbinden, daten: Path) -> threading.Thread | None:
    """Beim Start: einmal pro neuer Version im Hintergrund neu sichten."""
    import meta

    def lauf():
        try:
            with verbinden() as db:
                wenn_neue_version(laden, db, daten)
        except Exception as e:  # noqa: BLE001
            LOG.warning("Neu sichten nach dem Update: %s", e)
    t = threading.Thread(target=lauf, name="sichtung", daemon=True)
    t.start()
    return t


def wenn_neue_version(laden, db, daten: Path) -> Bericht | None:
    """Neu sichten, wenn die letzte Sichtung mit einer anderen Version lief; ohne Dokumente nur die Version merken."""
    import meta
    l_ = letzte(db)
    if l_ and l_.version == meta.version():
        return None
    if not _hat_dokumente(db):
        jetzt = datetime.now().isoformat(timespec="seconds")
        _tabelle(db)
        db.execute("INSERT INTO sichtung (zeit, version, bericht) VALUES (?, ?, ?)",
                   (jetzt, meta.version(), json.dumps(asdict(Bericht(jetzt, meta.version(), "Update")), ensure_ascii=False)))
        db.commit()
        return None
    return ausfuehren(laden(), db, daten, f"Update auf {meta.version()}")


def _hat_dokumente(db) -> bool:
    for t in ("vertraege", "vorsorge_dok", "steuer_dok"):
        try:
            if db.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone():  # noqa: S608
                return True
        except Exception:  # noqa: BLE001
            pass
    return False
