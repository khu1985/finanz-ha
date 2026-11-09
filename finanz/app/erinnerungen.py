"""Erinnerungen: wiederkehrende Aufgaben aus der Planung plus eigene, mit «erledigt» und HA-Benachrichtigung."""
from __future__ import annotations

from tausender import TS  # noqa: E402

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
    return f"{v:,.0f}" >> TS


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
        import krankenkasse as kk
        spar = sum(e.ersparnis for e in kk.haushalt(k, vi.alle(db)))
        zusatz = (f" Franchise-Optimierung spart rund CHF {_chf(spar)} pro Jahr." if spar >= 50 else
                  " Prämien und Gesundheitskosten unter «Versicherungen» eintragen, um die beste Franchise zu berechnen.")
        erg.append(Erinnerung(f"kvg-{j}", "Krankenkasse vergleichen", date(j, 11, 30),
                              "Neue Prämien sind bekannt; Grundversicherung bis 30. November eingeschrieben kündigen, Franchise "
                              "oder Modell wechseln." + zusatz, "versicherungen"))

    # Kündigungsfristen der Verträge
    for t in vi.kuendigungstermine(vi.alle(db), heute):
        if t.vertrag["sparte"] == "kvg":
            continue
        if (t.kuendigen_bis - heute).days <= 60:
            name = t.vertrag["versicherer"] or vi.SPARTEN.get(t.vertrag["sparte"], "Vertrag")
            erg.append(Erinnerung(f"kuendigung-{t.vertrag['id']}-{t.kuendigen_bis}", f"Kündigungsfrist {name}", t.kuendigen_bis,
                                  f"Kündigen bis {t.kuendigen_bis:%d.%m.%Y}, wirksam auf {t.wirksam_auf:%d.%m.%Y}. Offerten vergleichen.",
                                  "versicherungen"))

    # Steuererklärung: Frist aus dem Wohnkanton (oder eigene Frist bzw. Erstreckung)
    import kantone
    f = kantone.steuererklaerung(k)
    monat, tag = (int(x) for x in f.gewaehlt.split("-"))
    frist = _datum(j, monat, tag)
    ordentlich = _datum(j, *(int(x) for x in f.frist.split("-")))
    sichtbar_ab = _monate_zurueck(ordentlich, 2)
    if sichtbar_ab <= heute <= frist + timedelta(days=7):
        tipps = ["Belege: Lohnausweise, 3a-Bescheinigungen, PK-Einkauf, Schuldzinsen, Unterhalt, Kinderbetreuung."]
        if (k.get("wohnen") or {}).get("aktiv") and float(k["wohnen"].get("eigenmietwert", 0) or 0):
            tipps.append("Liegenschaftsunterhalt effektiv abziehen, wenn höher als die Pauschale.")
        if k["haushalt"].get("zivilstand") != "verheiratet" and k["haushalt"].get("kinder"):
            tipps.append("Kinderabzug und Elterntarif zwischen beiden Erklärungen abstimmen.")
        quelle = {"kanton": f"Frist {f.name}", "eigen": "eigene Frist", "erstreckt": "erstreckte Frist",
                  "standard": "angenommene Frist"}[f.quelle]
        if f.quelle != "erstreckt" and f.erstreckung:
            tipps.append(f"Erstreckung bis spätestens {f.erstreckung[3:]}.{f.erstreckung[:2]}. möglich – nach Gesuch das Datum "
                         "unter Einstellungen → Erinnerungen eintragen.")
        if f.pruefen:
            tipps.append("Datum auf der zugestellten Steuererklärung prüfen.")
        erg.append(Erinnerung(f"steuererklaerung-{j}", f"Steuererklärung {j - 1} einreichen ({quelle})", frist,
                              " ".join(tipps) + " Danach die Erklärung unter «Steuern» hochladen.", "steuern"))

    # Steueroptimierung
    erg.extend(_steueroptimierung(k, db, heute))
    erg.extend(_zuzug(k, heute))
    import kinder as ki
    erg.extend(ki.erinnerungen(k, heute))

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


def _zuzug(k: dict, heute: date) -> list[Erinnerung]:
    import zuzug as zz
    return zz.erinnerungen(k, heute)


def _steueroptimierung(k: dict, db, heute: date) -> list[Erinnerung]:
    """Erinnerungen aus PK-Einkauf-Optimierung, 3a-Lücken, Liegenschaftsunterhalt und 3a-Staffelung."""
    import steuerdokumente as sd
    import steuern as st
    import szenarien as sz
    import vorsorge as vs

    j = heute.year
    kz = k["kennzahlen"]
    erg: list[Erinnerung] = []

    # PK-Einkauf: optimaler Betrag für dieses Jahr, wenn noch nichts geplant ist
    if heute >= date(j, 9, 1):
        for p in k["personen"]:
            if any(int(e["jahr"]) == j for e in p["pk"].get("einkauf_geplant") or []):
                continue                                   # eigene Erinnerung «PK-Einkauf überweisen»
            if float(p["pk"].get("einkauf_potenzial", 0) or 0) < 5000 or float(p.get("lohn_brutto", 0)) <= 0:
                continue
            try:
                bis = min(vs.pensionsjahr(p) - 1, j + 9)
                plan = sz.einkauf_optimieren(k, p["name"], 0, j, bis, schwelle=20, schritt=5000, heute=heute)
            except (StopIteration, ValueError):
                continue
            betrag = plan.plan.get(j, 0)
            if betrag <= 0:
                continue
            ersparnis = plan.ersparnis.get(j, 0)
            erg.append(Erinnerung(
                f"pk-optimal-{p['name']}-{j}", f"PK-Einkauf {j} prüfen – {p['name']}", date(j, 12, 10),
                f"Optimal wären rund CHF {_chf(betrag)} (Ersparnis rund CHF {_chf(ersparnis)}, "
                f"{ersparnis / betrag * 100:.0f} %). Plan unter «Szenarien» übernehmen und bei der Kasse die Zahlungsfrist erfragen.",
                "szenarien"))

    # 3a-Lücke des Vorjahres nachzahlen (seit 2026 möglich für Lücken ab 2025), aus den Steuerdokumenten
    if j >= 2026 and heute >= date(j, 9, 1):
        doks = sd.alle(db)
        for p in k["personen"]:
            if float(p.get("lohn_brutto", 0)) <= 0:
                continue
            import zuzug as zz
            z = zz.datum(p)
            for jahr in range(max(2025, j - 10, z.year if z else 0), j):   # nur Jahre mit Erwerb in der Schweiz
                eigene = [x for x in doks if vi_gleich(x["person"], p["name"]) and x["jahr"] == jahr
                          and "abzug_3a" in x["werte"]]
                d = next(iter(sd.massgebend(eigene).values()), None)
                if not d or "abzug_3a" not in d["werte"]:
                    continue
                luecke = kz["saeule3a_max"] - float(d["werte"]["abzug_3a"])
                if luecke < 100:
                    continue
                e = st.ersparnis_abzug(k, luecke, p["name"])
                erg.append(Erinnerung(
                    f"3a-nachzahlen-{p['name']}-{jahr}-{j}", f"3a-Lücke {jahr} nachzahlen – {p['name']}", date(j, 12, 20),
                    f"{jahr} fehlen CHF {_chf(luecke)} bis zum Maximum. Nachzahlung möglich, wenn der Beitrag {j} voll einbezahlt "
                    f"ist; Ersparnis rund CHF {_chf(e['total'])}.", "steuern"))

    # Liegenschaftsunterhalt vor dem Wegfall des Eigenmietwerts
    w = k.get("wohnen") or {}
    letztes = int(kz.get("eigenmietwert_abschaffung", 2029)) - 1
    if w.get("aktiv") and float(w.get("eigenmietwert", 0) or 0) and j <= letztes and heute >= date(j, 10, 1):
        rest = letztes - j + 1
        erg.append(Erinnerung(
            f"unterhalt-{j}", "Liegenschaftsunterhalt planen", date(j, 12, 31),
            f"Unterhalt ist nur noch bis {letztes} abzugsfähig ({rest} Steuerjahr{'e' if rest > 1 else ''}). Grössere Arbeiten "
            f"bis Ende {letztes} abschliessen und auf Jahre mit hohem Grenzsteuersatz verteilen; Unterhalt der vermieteten "
            "Wohnung bleibt abzugsfähig.", "steuern"))

    # 3a auf mehrere Konten verteilen (gestaffelter Bezug)
    if heute >= date(j, 10, 15):
        for p in k["personen"]:
            konten = int(p["saeule3a"].get("konten", 1) or 1)
            if konten < 3 and float(p["saeule3a"].get("beitrag_jahr", 0) or 0) > 0 and vs.pensionsjahr(p) - j > 3:
                erg.append(Erinnerung(
                    f"3a-konto-{p['name']}-{j}", f"Weiteres 3a-Konto eröffnen – {p['name']}", date(j, 12, 20),
                    f"Heute {konten} Konto/Konten. Mit 3–5 Konten lässt sich der Bezug auf mehrere Jahre staffeln "
                    "(tiefere Kapitalbezugssteuer, siehe «Steuern» → Kapitalbezug). Die nächste Einzahlung aufs neue Konto.",
                    "steuern"))
    return erg


def vi_gleich(a: str, b: str) -> bool:
    import versicherungen as vi
    return vi.gleiche_person(a or "", b or "")


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
