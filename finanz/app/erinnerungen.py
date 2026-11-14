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
        try:
            import kkpraemien as kp
            kanton = str(k["haushalt"].get("kanton") or "").upper()
            if kanton and (j + 1) not in kp.jahre(db, kanton):
                zusatz += f" Unter «Versicherungen» die Prämien {j + 1} aller Kassen vom BAG laden und vergleichen."
            elif kanton:
                v = kp.vergleich(k, db, vi.alle(db))
                gewinn = sum(max(0.0, (e["heute"] or 0) - e["angebote"][0].kosten_jahr)
                             for e in v["personen"] if e["heute"] and e["angebote"])
                if gewinn >= 100:
                    zusatz += f" Laut Kassenvergleich {v['jahr']} sind bis CHF {_chf(gewinn)} pro Jahr günstiger möglich."
        except Exception as e_:  # noqa: BLE001
            LOG.debug("Kassenvergleich für Erinnerung: %s", e_)
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
        tipps = ["Checkliste mit Belegen und Werten aus der App unter «Steuererklärung»."]
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
                              " ".join(tipps) + " Danach die Erklärung unter «Steuern» hochladen.", "steuererklaerung"))

    # Steueroptimierung
    erg.extend(_steueroptimierung(k, db, heute))
    erg.extend(_zuzug(k, heute))
    import kinder as ki
    erg.extend(ki.erinnerungen(k, heute))
    import kinderphasen as kp
    erg.extend(kp.erinnerungen(k, heute))
    import immobilie as im
    erg.extend(im.erinnerungen(k, heute))

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
            markt = ""
            try:
                import marktzinsen as mz
                akt = mz.aktuell(db)
                if "fest10" in akt:
                    t10 = mz.trend(db, "fest10")
                    markt = (f" Richtzinsen heute: 5 J. {akt['fest5'][0]:.2f} %, 10 J. {akt['fest10'][0]:.2f} %"
                             if "fest5" in akt else f" Richtzins 10 J. heute {akt['fest10'][0]:.2f} %")
                    markt += (f" ({t10:+.2f} in 3 Monaten)." if t10 else ".")
                if not mz.offerten(k, heute):
                    markt += " Offerten unter «Szenarien» erfassen."
            except Exception:  # noqa: BLE001
                pass
            erg.append(Erinnerung(f"hypothek-{f}", f"Hypothek per {f:%d.%m.%Y} vorbereiten", _monate_zurueck(f, 12),
                                  "Offerten einholen, Forward-Festhypothek prüfen, Amortisation und Strategie unter «Szenarien» "
                                  "festlegen." + markt, "szenarien"))

    erg.extend(_neuere(k, db, heute))

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


def _neuere(k: dict, db, heute: date) -> list[Erinnerung]:
    """E-Steuerauszug, Abos, Finanzplan, Notfallordner und Namen – jede Quelle für sich abgesichert."""
    j = heute.year
    erg: list[Erinnerung] = []

    def sicher(f):
        try:
            erg.extend(f())
        except Exception as e:  # noqa: BLE001
            LOG.debug("Erinnerung %s: %s", f.__name__, e)

    def steuerauszug():
        import esteuerauszug as es
        if not (date(j, 1, 15) <= heute <= date(j, 3, 31)):
            return []
        vorjahr = [a for a in es.alle(db) if a["jahr"] == j - 1]
        if vorjahr:
            return []
        return [Erinnerung(f"steuerauszug-{j}", f"E-Steuerauszüge {j - 1} einlesen", date(j, 2, 28),
                           "Die Banken stellen den Steuerauszug im Januar bzw. Februar im E-Banking bereit. Unter «Steuern» "
                           "einlesen (am besten die XML-Datei): Saldi per 31.12., Wertschriften, Erträge und "
                           "Verrechnungssteuer für die Steuererklärung.", "steuern")]

    def abos():
        import abos as ab
        import budget as bu
        import versicherungen as vi
        liste = ab.erkennen(bu.alle(db), vi.alle(db), heute)
        r = []
        for a in liste:
            letzte = date.fromisoformat(a.letzte)
            if a.aenderung and a.aenderung >= 5 and (heute - letzte).days <= 45:
                r.append(Erinnerung(f"abo-teurer-{a.schluessel}-{a.letzte}", f"Teurer geworden: {a.name[:40]}", letzte + timedelta(days=30),
                                    f"{a.aenderung:+.0f} % seit der letzten Zahlung ({a.vorher:.2f} → {a.betrag:.2f}, "
                                    f"CHF {_chf(a.pro_jahr)} pro Jahr). Noch nötig – oder kündigen bzw. Angebot vergleichen?",
                                    "budget"))
            naechste = date.fromisoformat(a.naechste)
            if a.rhythmus in ("jährlich", "halbjährlich") and a.betrag >= 500 and 0 <= (naechste - heute).days <= 30:
                r.append(Erinnerung(f"abo-faellig-{a.schluessel}-{a.naechste}", f"Grössere Zahlung: {a.name[:40]}", naechste,
                                    f"Erwartet rund CHF {_chf(a.betrag)} ({a.rhythmus}) – Liquidität auf dem Konto sicherstellen.",
                                    "budget"))
        return r

    def finanzplan():
        import finanzplan as fp
        import vermoegen as vm
        if not float(k["haushalt"].get("bedarf_ruhestand") or 0):
            return []
        p = fp.rechnen(k, vm.nettovermoegen(db)["frei"], j, pfade=300)
        if p.erfolg >= 70:
            return []
        return [Erinnerung(f"finanzplan-{j}", "Finanzplan ist knapp", date(j, 12, 31),
                           f"Nur in {p.erfolg:.0f} % der simulierten Verläufe reicht das Geld bis {p.end_alter}"
                           + (f"; mit 90 % Sicherheit tragbar wären rund CHF {_chf(p.bedarf_sicher)} pro Jahr"
                              if p.bedarf_sicher else "")
                           + ". Hebel: mehr sparen, PK-Einkauf, später pensionieren oder Bedarf senken.", "finanzplan")]

    def notfall():
        if not (date(j, 11, 1) <= heute <= date(j, 12, 31)):
            return []
        return [Erinnerung(f"notfall-{j}", "Notfallordner und Verfügungen prüfen", date(j, 12, 31),
                           "Einmal im Jahr: Kontakte, Konten und Policen im Notfallordner, Begünstigungen (PK, 3a, Policen), "
                           "Testament und Vorsorgeauftrag noch aktuell? Nach Heirat, Geburt, Trennung, Haus- oder Stellenwechsel "
                           "sofort.", "notfall")]

    def namen():
        offen = [p["name"] for p in k["personen"] if not p.get("nachname") and len(str(p.get("name") or "").split()) > 1
                 and not str(p.get("name")).split()[-1].isdigit()]
        if not offen:
            return []
        return [Erinnerung(f"namen-{'-'.join(offen)}", "Vor- und Nachname trennen", heute,
                           "In der App reicht der Vorname; Verfügungen und Schreiben brauchen den vollen Namen. Unter "
                           "Einstellungen «Namen aufteilen».", "einstellungen")]

    for f in (steuerauszug, abos, finanzplan, notfall, namen):
        sicher(f)
    return erg


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
