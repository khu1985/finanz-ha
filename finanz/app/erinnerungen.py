"""Erinnerungen: wiederkehrende Aufgaben aus der Planung plus eigene, mit «erledigt» und HA-Benachrichtigung."""
from __future__ import annotations

import json
import logging
import os
import threading
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta

LOG = logging.getLogger("finanz")


@dataclass
class Erinnerung:
    schluessel: str      # eindeutig pro Aufgabe und Periode
    titel: str
    faellig: date
    text: str
    seite: str
    eigen: bool = False

    def tage(self, heute: date) -> int:
        return (self.faellig - heute).days


def _datum(jahr: int, monat: int, tag: int) -> date:
    import calendar
    return date(jahr, monat, min(tag, calendar.monthrange(jahr, monat)[1]))


def _monate_zurueck(d: date, n: int) -> date:
    m = d.month - 1 - n
    return _datum(d.year + m // 12, m % 12 + 1, d.day)


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")


def tabellen(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS erinnerungen_erledigt (schluessel TEXT PRIMARY KEY, datum TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS erinnerungen_gesendet (schluessel TEXT NOT NULL, stufe TEXT NOT NULL, datum TEXT NOT NULL,
                                                          PRIMARY KEY (schluessel, stufe));
        """
    )


def alle(k: dict, db, heute: date | None = None, mit_erledigten: bool = False) -> list[Erinnerung]:
    import vermoegen as vm
    import versicherungen as vi

    heute = heute or date.today()
    cfg = k.get("erinnerungen") or {}
    j = heute.year
    erg: list[Erinnerung] = []

    # Saldi nachführen (monatlich)
    letzter = db.execute("SELECT MAX(datum) FROM saldi").fetchone()[0]
    if letzter:
        faellig = date.fromisoformat(letzter) + timedelta(days=31)
        if (faellig - heute).days <= 7:
            erg.append(Erinnerung(f"saldi-{heute:%Y-%m}", "Saldi nachführen", faellig,
                                  f"Letzte Saldi vom {date.fromisoformat(letzter):%d.%m.%Y} – Kontoauszüge importieren.", "vermoegen"))
    elif vm.konten(db) == []:
        erg.append(Erinnerung(f"saldi-{heute:%Y-%m}", "Vermögen erfassen", heute, "Noch keine Saldi – Kontoauszüge importieren.",
                              "vermoegen"))

    # 3a-Einzahlung bis Bankschluss im Dezember
    if heute >= date(j, 10, 15):
        for p in k["personen"]:
            if float(p.get("lohn_brutto", 0)) > 0:
                betrag = min(float(p["saeule3a"].get("beitrag_jahr", 0)) or k["kennzahlen"]["saeule3a_max"],
                             k["kennzahlen"]["saeule3a_max"])
                erg.append(Erinnerung(f"3a-{p['name']}-{j}", f"3a einzahlen – {p['name']}", date(j, 12, 20),
                                      f"Bis CHF {_chf(betrag)} (Maximum {_chf(k['kennzahlen']['saeule3a_max'])}); Gutschrift muss vor "
                                      "Jahresende bei der Stiftung sein.", "vorsorge"))

    # Geplante PK-Einkäufe dieses Jahres
    if heute >= date(j, 9, 1):
        for p in k["personen"]:
            for e in p["pk"].get("einkauf_geplant") or []:
                if int(e["jahr"]) == j:
                    erg.append(Erinnerung(f"pk-{p['name']}-{j}", f"PK-Einkauf überweisen – {p['name']}", date(j, 12, 10),
                                          f"CHF {_chf(float(e['betrag']))} – vorher bei der Kasse Einkaufsbestätigung und "
                                          "Zahlungsfrist erfragen (meist Mitte Dezember).", "szenarien"))

    # Krankenkasse
    if date(j, 9, 20) <= heute <= date(j, 11, 30):
        erg.append(Erinnerung(f"kvg-{j}", "Krankenkasse vergleichen", date(j, 11, 30),
                              "Neue Prämien sind bekannt; Grundversicherung bis 30. November eingeschrieben kündigen.", "versicherungen"))

    # Kündigungsfristen der Verträge
    for t in vi.kuendigungstermine(vi.alle(db), heute):
        if t.vertrag["sparte"] == "kvg":
            continue
        if (t.kuendigen_bis - heute).days <= 60:
            name = t.vertrag["versicherer"] or vi.SPARTEN.get(t.vertrag["sparte"], "Vertrag")
            erg.append(Erinnerung(f"kuendigung-{t.vertrag['id']}-{t.kuendigen_bis}", f"Kündigungsfrist {name}", t.kuendigen_bis,
                                  f"Kündigen bis {t.kuendigen_bis:%d.%m.%Y}, wirksam auf {t.wirksam_auf:%d.%m.%Y}. Offerten vergleichen.",
                                  "versicherungen"))

    # Steuererklärung
    frist_txt = str(cfg.get("steuererklaerung_frist") or "03-31")
    monat, tag = (int(x) for x in frist_txt.split("-")[-2:])
    frist = _datum(j, monat, tag)
    if _monate_zurueck(frist, 2) <= heute <= frist + timedelta(days=7):
        erg.append(Erinnerung(f"steuererklaerung-{j}", f"Steuererklärung {j - 1} einreichen", frist,
                              "Belege sammeln (Lohnausweis, 3a, PK-Einkauf, Schuldzinsen, Unterhalt); bei Bedarf Fristerstreckung "
                              "beantragen. Danach die Erklärung unter «Steuern» hochladen.", "steuern"))

    # Vorsorgeausweise
    if date(j, 2, 1) <= heute <= date(j, 4, 30):
        erg.append(Erinnerung(f"ausweis-{j}", "Neue Vorsorgeausweise hochladen", date(j, 3, 31),
                              "Die Pensionskassen versenden den Ausweis mit Stand 1. Januar – unter «Vorsorge» hochladen.", "vorsorge"))

    # Kennzahlen
    if heute.month == 1:
        erg.append(Erinnerung(f"kennzahlen-{j}", "Kennzahlen prüfen", date(j, 1, 31),
                              "AHV, BVG, 3a-Maximum und Steuertarif für das neue Jahr in den Einstellungen nachführen.", "einstellungen"))

    # Hypothek
    w = k.get("wohnen") or {}
    if w.get("aktiv") and w.get("hypothek_faellig"):
        f = date.fromisoformat(str(w["hypothek_faellig"]))
        start = _monate_zurueck(f, 36)
        if start <= heute <= f:
            erg.append(Erinnerung(f"hypothek-{f}", f"Hypothek per {f:%d.%m.%Y} vorbereiten", _monate_zurueck(f, 12),
                                  "Offerten einholen, Forward-Festhypothek prüfen, Amortisation und Strategie unter «Szenarien» festlegen.",
                                  "szenarien"))

    # Eigene Erinnerungen
    for i, e in enumerate(cfg.get("eigene") or []):
        try:
            erg.extend(_eigene(e, i, heute))
        except (ValueError, KeyError, TypeError) as fehler:
            LOG.warning("Erinnerung %s ungültig: %s", e, fehler)

    if not mit_erledigten:
        tabellen(db)
        erledigt = {r[0] for r in db.execute("SELECT schluessel FROM erinnerungen_erledigt")}
        erg = [e for e in erg if e.schluessel not in erledigt]
    return sorted(erg, key=lambda e: e.faellig)


def _eigene(e: dict, i: int, heute: date) -> list[Erinnerung]:
    teile = str(e["datum"]).split("-")
    wdh = str(e.get("wiederholung") or ("jaehrlich" if len(teile) == 2 else "einmalig"))
    vorlauf = int(e.get("vorlauf", 30))
    titel = str(e["titel"])
    if wdh == "monatlich":
        tag = int(teile[-1])
        f = _datum(heute.year, heute.month, tag)
        if f < heute - timedelta(days=7):
            f = _datum(heute.year + (heute.month == 12), heute.month % 12 + 1, tag)
    elif wdh == "jaehrlich":
        f = _datum(heute.year, int(teile[-2]), int(teile[-1]))
        if f < heute - timedelta(days=7):
            f = _datum(heute.year + 1, int(teile[-2]), int(teile[-1]))
    else:
        f = date.fromisoformat(str(e["datum"]))
    if (f - heute).days > vorlauf:
        return []
    return [Erinnerung(f"eigen-{i}-{f}", titel, f, str(e.get("text", "")), str(e.get("seite", "")), True)]


def erledigen(db, schluessel: str) -> None:
    tabellen(db)
    db.execute("INSERT OR REPLACE INTO erinnerungen_erledigt (schluessel, datum) VALUES (?, ?)",
               (schluessel, datetime.now().isoformat(timespec="seconds")))
    db.commit()


def status(e: Erinnerung, heute: date) -> str:
    import ampel as am
    t = e.tage(heute)
    return am.ROT if t <= 7 else am.GELB if t <= 30 else am.GRUEN


# ---------------------------------------------------------------- Benachrichtigung über Home Assistant

def _ha_dienst(dienst: str, daten: dict) -> None:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("Kein Zugriff auf Home Assistant (SUPERVISOR_TOKEN fehlt).")
    domain, name = dienst.split(".", 1)
    req = urllib.request.Request(f"http://supervisor/core/api/services/{domain}/{name}", data=json.dumps(daten).encode(),
                                 method="POST", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20):
        pass


def benachrichtigen(k: dict, db, heute: date | None = None, senden=_ha_dienst) -> list[str]:
    """Sendet je Erinnerung höchstens zwei Meldungen: beim Erscheinen und wenn sie fällig ist (≤ 1 Tag)."""
    cfg = k.get("erinnerungen") or {}
    ziel = str(cfg.get("benachrichtigung") or "").strip()
    if not ziel:
        return []
    heute = heute or date.today()
    tabellen(db)
    gesendet = {(r[0], r[1]) for r in db.execute("SELECT schluessel, stufe FROM erinnerungen_gesendet")}
    erg = []
    for e in alle(k, db, heute):
        stufe = "faellig" if e.tage(heute) <= 1 else "neu"
        if (e.schluessel, stufe) in gesendet or (stufe == "neu" and (e.schluessel, "faellig") in gesendet):
            continue
        titel = ("Fällig: " if stufe == "faellig" else "Finanzen: ") + e.titel
        text = f"{e.text} (bis {e.faellig:%d.%m.%Y})"
        if ziel == "persistent":
            senden("persistent_notification.create", {"title": titel, "message": text, "notification_id": f"finanz_{e.schluessel}"})
        else:
            dienst = ziel if "." in ziel else f"notify.{ziel}"
            senden(dienst, {"title": titel, "message": text})
        db.execute("INSERT OR REPLACE INTO erinnerungen_gesendet (schluessel, stufe, datum) VALUES (?, ?, ?)",
                   (e.schluessel, stufe, datetime.now().isoformat(timespec="seconds")))
        db.commit()
        erg.append(titel)
    for t in erg:
        LOG.info("Benachrichtigung gesendet: %s", t)
    return erg


def hintergrund(laden, verbinden, intervall: int = 3600) -> threading.Thread:
    """Prüft stündlich die Erinnerungen und sendet fällige Benachrichtigungen."""
    def schleife():
        import time
        time.sleep(15)
        while True:
            try:
                with verbinden() as db:
                    benachrichtigen(laden(), db)
            except Exception as e:  # noqa: BLE001
                LOG.warning("Erinnerungen: %s", e)
            time.sleep(intervall)

    t = threading.Thread(target=schleife, name="erinnerungen", daemon=True)
    t.start()
    return t
