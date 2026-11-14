"""Sensoren für Home Assistant: Kennzahlen der Finanzplanung als `sensor.finanz_*` bereitstellen.

Die App schreibt die Zustände über die REST-API von Home Assistant (über den Supervisor, `homeassistant_api`).
Solche Zustände überstehen keinen Neustart von Home Assistant; die App schreibt sie deshalb beim Start, alle
15 Minuten und nach jeder Änderung neu. Für Verlauf und Statistik genügt das (state_class gesetzt).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime

LOG = logging.getLogger("finanz")
_letzter: dict = {"zeit": None, "anzahl": 0, "fehler": "", "werte": []}
_ausloeser = threading.Event()


@dataclass
class Sensor:
    schluessel: str
    name: str
    zustand: object
    einheit: str = ""
    geraeteklasse: str = ""
    zustandsklasse: str = ""
    symbol: str = "mdi:finance"
    attribute: dict = field(default_factory=dict)

    def entity_id(self, praefix: str) -> str:
        return f"sensor.{praefix}_{self.schluessel}"

    def nutzlast(self) -> dict:
        attr = {"friendly_name": f"Finanzen {self.name}", "icon": self.symbol, **self.attribute}
        if self.einheit:
            attr["unit_of_measurement"] = self.einheit
        if self.geraeteklasse:
            attr["device_class"] = self.geraeteklasse
        if self.zustandsklasse:
            attr["state_class"] = self.zustandsklasse
        return {"state": "unknown" if self.zustand is None else str(self.zustand), "attributes": attr}


def _chf(name: str, schluessel: str, wert, symbol: str = "mdi:cash", **attr) -> Sensor:
    return Sensor(schluessel, name, None if wert is None else round(float(wert)), "CHF", "monetary", "total", symbol, attr)


def berechnen(k: dict, db, heute: date | None = None) -> list[Sensor]:
    import ampel as am
    import anlage as an
    import berater as br
    import erinnerungen as er
    import fruehpension as fp
    import kantone
    import krankenkasse as kk
    import steuern as st
    import vermoegen as vm
    import versicherungen as vi
    import vorsorge as vs

    heute = heute or date.today()
    s: list[Sensor] = []

    _letzter["bereich_fehler"] = {}

    def sicher(fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 – ein fehlerhafter Bereich darf die übrigen Sensoren nicht verhindern
            import traceback
            _letzter["bereich_fehler"][fn.__name__] = f"{type(e).__name__}: {e} | {traceback.format_exc(limit=-3)}"
            LOG.warning("Sensoren «%s» übersprungen: %s", fn.__name__, e)

    nv = vm.nettovermoegen(db)
    konten = vm.konten(db)
    letzter = db.execute("SELECT MAX(datum) FROM saldi").fetchone()[0]
    s.append(_chf("Nettovermögen", "nettovermoegen", nv["total"], "mdi:scale-balance",
                  nach_art={vm.ARTEN.get(a, a): round(v) for a, v in nv["nach_art"].items()}, stand=letzter))
    s.append(_chf("Freies Vermögen", "freies_vermoegen", nv["verfuegbar"], "mdi:wallet"))
    s.append(_chf("Gebundene Vorsorge", "gebundene_vorsorge", nv["gebunden"], "mdi:piggy-bank"))
    s.append(_chf("Liquidität", "liquiditaet", sum(x["wert"] for x in konten if x["art"] == "bank"), "mdi:bank"))
    s.append(Sensor("saldi_alter", "Alter der Saldi", (heute - date.fromisoformat(letzter)).days if letzter else None,
                    "d", "duration", "measurement", "mdi:calendar-clock", {"stand": letzter}))

    def ruhestand():
        l = vs.pensionsluecke(k, nv["frei"], heute.year)
        s.append(_chf("Einkommen im Ruhestand", "einkommen_ruhestand", l.einkommen, "mdi:beach",
                      ab_jahr=l.jahr, ahv=l.ahv, pk_rente=l.pk_rente, kapitalverzehr=l.kapitalverzehr, rente_ausland=l.ausland, bedarf=l.bedarf))
        s.append(_chf("Pensionslücke", "pensionsluecke", l.luecke, "mdi:chart-bell-curve", ab_jahr=l.jahr,
                      mittel=l.luecke_mittel, nach_20_jahren=l.luecke_spaeter, teuerung=l.teuerung))
        s.append(Sensor("ersatzquote", "Ersatzquote", l.ersatzquote, "%", "", "measurement", "mdi:percent"))
    sicher(ruhestand)

    def frueh():
        varianten = fp.vergleich(k, nv["frei"], heute=heute)
        s.append(Sensor("fruehestes_pensionsalter", "Frühestes Pensionsalter ohne Lücke",
                        fp.fruehestes_ohne_luecke(varianten), "Jahre", "", "measurement", "mdi:account-clock",
                        {"einkommen": {v.alter: v.einkommen for v in varianten}}))
    sicher(frueh)

    def steuern():
        t = st.steuern_heute(k)
        s.append(_chf("Steuern pro Jahr", "steuern_jahr", t["total_inkl"], "mdi:bank-transfer-out", bund=t["bund"],
                      kanton=t["kanton"], vermoegen=t["vermoegen"], effektiv=t["effektiv"],
                      pro_person={e["name"]: e["total"] for e in t["einheiten"]}))
        s.append(Sensor("grenzsteuersatz", "Grenzsteuersatz", t["grenz_total"], "%", "", "measurement", "mdi:percent-outline"))
        f = kantone.steuererklaerung(k)
        j = heute.year
        frist = er._datum(j, *(int(x) for x in f.gewaehlt.split("-")))
        if (frist - heute).days < -7:
            frist = er._datum(j + 1, *(int(x) for x in f.gewaehlt.split("-")))
        s.append(Sensor("steuererklaerung_frist", "Frist Steuererklärung", frist.isoformat(), "", "date", "",
                        "mdi:file-document-clock", {"kanton": f.kanton, "erstreckt": f.quelle == "erstreckt",
                                                     "tage": (frist - heute).days}))
    sicher(steuern)

    def wohnen():
        a = br.amortisation(k, db, heute)
        if a:
            s.append(_chf("Amortisation verfügbar", "amortisation_verfuegbar", a.verfuegbar, "mdi:home-percent",
                          faellig=a.faellig.isoformat(), ziel=a.ziel, maximal=a.maximal, hypothek_danach=a.hypothek_danach))
    sicher(wohnen)

    def versicherung():
        vertraege = vi.alle(db)
        s.append(_chf("Versicherungsprämien", "versicherungspraemien", vi.praemien(vertraege)["total"], "mdi:shield-account",
                      vertraege=len(vertraege)))
        kv = kk.haushalt(k, vertraege)
        if kv:
            s.append(_chf("Krankenkasse Ersparnis", "krankenkasse_ersparnis", sum(e.ersparnis for e in kv), "mdi:medical-bag",
                          optimale_franchise={e.person.name: e.beste for e in kv}))
    sicher(versicherung)

    def anlage():
        c = an.pruefen(k, db, heute)
        if c.finanz_total:
            s.append(_chf("Ohne Zweck auf Konten", "ungenutzt", max(0, c.anlegbar - c.depot), "mdi:piggy-bank-outline",
                          mehrertrag_jahr=c.opportunitaet, krypto_anteil=c.krypto_anteil))
    sicher(anlage)

    def budget():
        import budget as bu
        b = bu.auswerten(k, db, heute=heute)
        if b is None:
            return
        gespart = (b.ueberschuss + b.sparen_konto) / 12
        s.append(_chf("Ausgaben pro Monat", "ausgaben_monat", b.ausgaben / 12, "mdi:cart-outline",
                      einnahmen=round(b.einnahmen / 12), monate=b.monate, bis=b.bis,
                      kategorien={n: round(j / 12) for n, j, _ in b.kategorien[:8]}))
        s.append(_chf("Gespart pro Monat", "gespart_monat", gespart, "mdi:piggy-bank", plan=round(b.sparen_plan / 12)))
        s.append(Sensor("sparquote", "Sparquote", round(gespart * 12 / b.einnahmen * 100, 1) if b.einnahmen else 0, "%", "",
                        "measurement", "mdi:percent-outline"))
    sicher(budget)

    def ampeln():
        liste = am.bewerten(k, db, heute)
        gesamt = am.schlechteste(a.status for a in liste)
        zaehler = {x: sum(1 for a in liste if a.status == x) for x in (am.ROT, am.GELB, am.GRUEN)}
        s.append(Sensor("ampel", "Ampel", gesamt, "", "enum", "", {am.ROT: "mdi:alert-circle", am.GELB: "mdi:alert",
                                                                       am.GRUEN: "mdi:check-circle"}.get(gesamt, "mdi:help-circle"),
                        {"options": [am.GRUEN, am.GELB, am.ROT, am.GRAU], "handeln": zaehler[am.ROT],
                         "pruefen": zaehler[am.GELB], "in_ordnung": zaehler[am.GRUEN],
                         "bereiche": {a.bereich: a.status for a in liste},
                         "texte": {a.bereich: a.text for a in liste if a.status in (am.ROT, am.GELB)}}))
        s.append(Sensor("handeln", "Zu handeln", zaehler[am.ROT], "", "", "measurement", "mdi:alert-circle",
                        {"bereiche": [a.bereich for a in liste if a.status == am.ROT]}))
    sicher(ampeln)

    def erinnerungen():
        offen = er.alle(k, db, heute)
        n = offen[0] if offen else None
        s.append(Sensor("erinnerungen", "Anstehende Erinnerungen", len(offen), "", "", "measurement", "mdi:bell-ring",
                        {"dringend": sum(1 for e in offen if e.tage(heute) <= 7),
                         "liste": [{"titel": e.titel, "faellig": e.faellig.isoformat()} for e in offen[:10]]}))
        s.append(Sensor("naechste_frist", "Nächste Frist", n.faellig.isoformat() if n else None, "", "date", "",
                        "mdi:calendar-alert", {"titel": n.titel if n else "", "text": n.text if n else "",
                                               "tage": n.tage(heute) if n else None}))
    sicher(erinnerungen)
    return s


# ---------------------------------------------------------------- Schreiben

def _senden_ha(entity_id: str, nutzlast: dict) -> None:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("Kein Zugriff auf Home Assistant (SUPERVISOR_TOKEN fehlt).")
    req = urllib.request.Request(f"http://supervisor/core/api/states/{entity_id}", data=json.dumps(nutzlast).encode(),
                                 method="POST", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15):
        pass


def schreiben(k: dict, db, senden=_senden_ha, heute: date | None = None) -> list[Sensor]:
    cfg = k.get("sensoren") or {}
    if not cfg.get("aktiv", True):
        return []
    praefix = str(cfg.get("praefix") or "finanz").strip().lower().replace(" ", "_")
    werte = berechnen(k, db, heute)
    fehler = ""
    for x in werte:
        try:
            senden(x.entity_id(praefix), x.nutzlast())
        except Exception as e:  # noqa: BLE001
            fehler = str(e)
            break
    _letzter.update(zeit=datetime.now().isoformat(timespec="seconds"), anzahl=0 if fehler else len(werte), fehler=fehler,
                    werte=[(x.entity_id(praefix), x.nutzlast()["state"], x.einheit) for x in werte])
    if fehler:
        LOG.warning("Sensoren nicht geschrieben: %s", fehler)
    else:
        LOG.debug("%d Sensoren geschrieben", len(werte))
    return werte


def status() -> dict:
    return dict(_letzter)


def aktualisieren() -> None:
    """Nach einer Änderung: Sensoren im Hintergrund neu schreiben."""
    _ausloeser.set()


def nebenaufgaben(k: dict, db) -> None:
    """Wechselkurse (falls eingeschaltet) holen und den monatlichen Stand für den Jahresbericht speichern."""
    try:
        import vermoegen as vm
        import waehrung as wg
        import zuzug as zz
        offen = {x["waehrung"] for x in vm.konten(db)} | {str(zz.cfg(p).get("rente_ausland_waehrung") or "CHF")
                                                         for p in k["personen"]}
        neu = wg.aktualisieren(db, sorted(offen))
        if neu:
            LOG.info("Wechselkurse aktualisiert: %s", ", ".join(neu))
    except Exception as e:  # noqa: BLE001
        LOG.warning("Wechselkurse: %s", e)
    try:
        import marktzinsen as mz
        if mz.aktualisieren(k, db):
            LOG.info("Marktzinsen (SARON, Hypotheken) der SNB aktualisiert")
    except Exception as e:  # noqa: BLE001
        LOG.warning("Marktzinsen: %s", e)
    try:
        import bericht
        if bericht.automatisch(k, db):
            LOG.info("Monatsstand für den Jahresbericht gespeichert")
    except Exception as e:  # noqa: BLE001
        LOG.warning("Monatsstand: %s", e)


def _3a_abgleichen(k: dict, db) -> None:
    import dreia
    import konfig
    if dreia.abgleichen(k, db):
        konfig.speichern(k)


def _usability(k: dict, db) -> None:
    """Einmal am Tag alle Seiten auf Usability prüfen (Ergebnis unter Vorschläge)."""
    import meta
    import usability as us
    from datetime import date
    if us.faellig(db, meta.version(), date.today().isoformat()):
        us.sichern(db, us.pruefen(k, db))


def hintergrund(laden, verbinden, intervall: int = 900) -> threading.Thread:
    def schleife():
        time.sleep(10)
        while True:
            try:
                import leistung as le
                with verbinden() as db:
                    k = laden()
                    _3a_abgleichen(k, db)
                    with le.Stoppuhr("hintergrund", "Kurse, Zinsen, Monatsstand"):
                        nebenaufgaben(k, db)
                    with le.Stoppuhr("hintergrund", "Sensoren schreiben"):
                        schreiben(k, db)
                    le.sichern(db)
                    _usability(k, db)
            except Exception as e:  # noqa: BLE001
                LOG.warning("Sensoren: %s", e)
            _ausloeser.wait(intervall)
            _ausloeser.clear()
            time.sleep(2)  # mehrere Änderungen kurz hintereinander zusammenfassen

    t = threading.Thread(target=schleife, name="sensoren", daemon=True)
    t.start()
    return t
