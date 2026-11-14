"""Solaranlage und vZEV: Werte aus der vZEV-App (Sensoren in Home Assistant), Rendite, Steuern, Komponenten.

Quelle der laufenden Werte: die vZEV-App schreibt `sensor.<präfix>_wertschoepfung_jahr` (Attribute mieter_chf,
eigen_chf, export_chf), `_produktion_jahr` (kWh), `_offene_rechnungen` (CHF) und `_ueberfaellig` (Anzahl). Die
Finanz-App liest sie einmal am Tag über die Home-Assistant-API und speichert sie (Tabelle `solar_werte`); vom letzten
vollen Jahr gilt der Stand am Jahresende, sonst wird das laufende Jahr mit der typischen Monatsverteilung der
Produktion hochgerechnet. Ohne vZEV-App lassen sich die Jahreswerte von Hand eintragen.

Konfiguration unter `solar` (alles freiwillig):
- aktiv, sensor_praefix (Standard vzev), leistung_kwp
- investition, investition_jahr, foerderung (Einmalvergütung), gebaeude_bestehend (Gebäude stand bei Auftrag schon
  mindestens zwei volle Jahre), unterhalt_jahr (Standard 1 % der Investition), lebensdauer (25), degradation (0.5 %/J.)
- strombezug_jahr: eigene Stromkosten (BL: Einspeisung wird netto besteuert, Vergütung minus privater Bezug)
- wechselrichter_jahr/_kosten, batterie_jahr/_kosten (Lebensdauer 12 Jahre); Module mit der Lebensdauer der Anlage
- von Hand statt Sensor: mieter_jahr, eigen_jahr, export_jahr, produktion_jahr

Steuern (Kanton BL, Steuerbuch 29-08): Energiesparmassnahmen an bestehenden Gebäuden sind zu 100 % abziehbar (wie
Unterhalt, nicht neben der Pauschale; nicht bei Bau zeitnah zum Neubau); nicht verrechenbare Kosten in die nächste
oder übernächste Steuerperiode übertragbar; Subventionen mindern den Abzug bzw. sind Einkommen. Einspeisung: Nettoertrag
(Vergütung minus privater Strombezug) unter «Übrige Einkünfte», negativ nicht abziehbar. Den Stromverkauf an Mieter
rechnet die App als steuerbares Einkommen (Einordnung mit der Steuerverwaltung klären).
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

LOG = logging.getLogger("finanz")
# typische Verteilung der PV-Produktion über das Jahr (Mittelland, % pro Monat)
MONATE = [2.5, 4.5, 8.0, 11.0, 12.5, 13.0, 13.5, 12.0, 9.0, 6.0, 3.0, 2.0]
SENSOREN = ("wertschoepfung_jahr", "produktion_jahr", "offene_rechnungen", "ueberfaellig")
_VERSUCH: datetime | None = None
QUELLEN = [
    ("Steuerbuch BL 29-08: Energiesparmassnahmen und Photovoltaik",
     "https://kanton.baselland.ch/finanz-und-kirchendirektion/steuerverwaltung-steuerbuch/band-1/einkommen/downloads-1/"
     "band1_029_08.pdf"),
    ("Swissolar: Merkblatt Steuerpraxis Photovoltaik",
     "https://www.swissolar.ch/01_wissen/fachwissen/photovoltaik/merkblaetter/21009d_merkblatt_steuerpraxis.pdf"),
]


def _zahl(v, std: float = 0.0) -> float:
    try:
        t = str(v).replace("'", "").replace(",", ".").strip()
        return float(t) if t not in ("", "None") else std
    except ValueError:
        return std


def cfg(k: dict) -> dict:
    return k.get("solar") or {}


def aktiv(k: dict) -> bool:
    c = cfg(k)
    return bool(c.get("aktiv") or c.get("investition") or c.get("mieter_jahr") or c.get("export_jahr"))


# ---------------------------------------------------------------- Werte aus Home Assistant

def tabellen(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS solar_werte (datum TEXT NOT NULL, name TEXT NOT NULL, wert REAL, "
               "attribute TEXT NOT NULL DEFAULT '{}', PRIMARY KEY (datum, name))")


def _lesen(entity_id: str) -> dict | None:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    req = urllib.request.Request(f"http://supervisor/core/api/states/{entity_id}",
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 – feste Adresse im Supervisor
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def einlesen(db, zustaende: dict[str, dict], heute: date | None = None) -> int:
    """Zustände {name: {"state": …, "attributes": {…}}} speichern (für Tests und den Abruf)."""
    heute = heute or date.today()
    tabellen(db)
    n = 0
    for name, z in zustaende.items():
        try:
            wert = float(z.get("state"))
        except (TypeError, ValueError):
            continue
        db.execute("INSERT OR REPLACE INTO solar_werte VALUES (?, ?, ?, ?)",
                   (heute.isoformat(), name, wert, json.dumps(z.get("attributes") or {})))
        n += 1
    db.commit()
    return n


def holen(k: dict, db, heute: date | None = None) -> int:
    praefix = str(cfg(k).get("sensor_praefix") or "vzev")
    zustaende = {}
    for s in SENSOREN:
        z = _lesen(f"sensor.{praefix}_{s}")
        if z:
            zustaende[s] = z
    return einlesen(db, zustaende, heute)


def aktualisieren(k: dict, db, heute: date | None = None) -> bool:
    """Einmal am Tag holen (nur mit Home Assistant und aktiver Solaranlage)."""
    global _VERSUCH
    if not aktiv(k) or not os.environ.get("SUPERVISOR_TOKEN"):
        return False
    heute = heute or date.today()
    tabellen(db)
    if db.execute("SELECT 1 FROM solar_werte WHERE datum = ?", (heute.isoformat(),)).fetchone():
        return False
    if _VERSUCH and datetime.now() - _VERSUCH < timedelta(hours=6):
        return False
    _VERSUCH = datetime.now()
    return holen(k, db, heute) > 0


def _neueste(db, name: str, bis: date | None = None) -> tuple[str, float, dict] | None:
    tabellen(db)
    sql = "SELECT datum, wert, attribute FROM solar_werte WHERE name = ?" + (" AND datum <= ?" if bis else "")
    r = db.execute(sql + " ORDER BY datum DESC LIMIT 1", (name, bis.isoformat()) if bis else (name,)).fetchone()
    return (r[0], float(r[1]), json.loads(r[2] or "{}")) if r else None


def _anteil_bis(d: date) -> float:
    """Anteil der Jahresproduktion bis zum Datum (typische Verteilung)."""
    voll = sum(MONATE[:d.month - 1])
    tage = (date(d.year + (d.month == 12), d.month % 12 + 1, 1) - date(d.year, d.month, 1)).days
    return (voll + MONATE[d.month - 1] * d.day / tage) / sum(MONATE)


# ---------------------------------------------------------------- Jahreswerte, Rendite, Steuern

@dataclass
class Jahr:
    mieter: float
    eigen: float
    export: float
    produktion: float
    quelle: str

    @property
    def total(self) -> float:
        return self.mieter + self.eigen + self.export


def jahreswerte(k: dict, db, heute: date | None = None) -> Jahr | None:
    heute = heute or date.today()
    c = cfg(k)
    if any(c.get(s) not in (None, "") for s in ("mieter_jahr", "eigen_jahr", "export_jahr")):
        return Jahr(_zahl(c.get("mieter_jahr")), _zahl(c.get("eigen_jahr")), _zahl(c.get("export_jahr")),
                    _zahl(c.get("produktion_jahr")), "Einstellungen")
    if db is None:
        v = c.get("werte_vzev") or {}            # zuletzt aus der vZEV-App übernommen (siehe abgleichen)
        if not v:
            return None
        return Jahr(_zahl(v.get("mieter")), _zahl(v.get("eigen")), _zahl(v.get("export")), _zahl(v.get("produktion")),
                    str(v.get("quelle") or "vZEV-App"))
    # letztes volles Jahr: Stand am Jahresende (letzter Wert des Vorjahres im Dezember)
    vor = _neueste(db, "wertschoepfung_jahr", date(heute.year - 1, 12, 31))
    if vor and vor[0][:7] == f"{heute.year - 1}-12":
        attr = vor[2]
        prod = _neueste(db, "produktion_jahr", date(heute.year - 1, 12, 31))
        return Jahr(_zahl(attr.get("mieter_chf")), _zahl(attr.get("eigen_chf")), _zahl(attr.get("export_chf")),
                    prod[1] if prod and prod[0][:4] == str(heute.year - 1) else 0.0, f"vZEV-App, Jahr {heute.year - 1}")
    jetzt = _neueste(db, "wertschoepfung_jahr")
    if not jetzt or jetzt[0][:4] != str(heute.year):
        return None
    d = date.fromisoformat(jetzt[0])
    f = 1 / max(0.05, _anteil_bis(d))
    attr = jetzt[2]
    prod = _neueste(db, "produktion_jahr")
    return Jahr(_zahl(attr.get("mieter_chf")) * f, _zahl(attr.get("eigen_chf")) * f, _zahl(attr.get("export_chf")) * f,
                (prod[1] * f) if prod and prod[0][:4] == str(heute.year) else 0.0,
                f"vZEV-App, {heute.year} bis {d:%d.%m.} hochgerechnet ({_anteil_bis(d) * 100:.0f} % der Jahresproduktion)")


@dataclass
class Auswertung:
    jahr: Jahr | None
    investition: float
    foerderung: float
    abzug: float                       # Investitionsabzug (bestehendes Gebäude)
    steuer_ersparnis: float            # durch den Abzug
    unterhalt: float
    einkommen_steuerbar: float         # Mieter + Einspeisung netto
    steuer_ertrag: float               # Steuern auf das Einkommen (Grenzsteuersatz)
    nutzen_jahr: float                 # Wertschöpfung − Unterhalt − Steuern
    netto_investition: float
    amortisation_jahre: float | None
    rendite: float | None              # % pro Jahr über die Lebensdauer (interner Zinsfuss)
    lebensdauer: int
    ende_jahr: int | None
    komponenten: list[dict]
    offene: float
    ueberfaellig: int
    hinweise: list[str] = field(default_factory=list)


def komponenten(k: dict) -> list[dict]:
    """Bauteile der Anlage für die Erneuerungsplanung: Module, Wechselrichter, Batterie."""
    c = cfg(k)
    inv = _zahl(c.get("investition"))
    jahr = int(_zahl(c.get("investition_jahr"))) or None
    if not inv or not jahr:
        return []
    erg = [{"name": "PV: Module", "letzte": jahr, "lebensdauer": int(_zahl(c.get("lebensdauer"), 25)) or 25,
            "kosten": round(inv * 0.55, -2)},
           {"name": "PV: Wechselrichter", "letzte": int(_zahl(c.get("wechselrichter_jahr"))) or jahr, "lebensdauer": 12,
            "kosten": round(_zahl(c.get("wechselrichter_kosten")) or inv * 0.12, -2)}]
    if _zahl(c.get("batterie_kosten")):
        erg.append({"name": "PV: Batterie", "letzte": int(_zahl(c.get("batterie_jahr"))) or jahr, "lebensdauer": 12,
                    "kosten": round(_zahl(c.get("batterie_kosten")), -2)})
    return erg


def _irr(zahlungen: list[float]) -> float | None:
    def npv(r):
        return sum(z / (1 + r) ** i for i, z in enumerate(zahlungen))
    lo, hi = -0.5, 1.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(80):
        m = (lo + hi) / 2
        if npv(lo) * npv(m) <= 0:
            hi = m
        else:
            lo = m
    return (lo + hi) / 2


def auswerten(k: dict, db, heute: date | None = None) -> Auswertung | None:
    import steuern as st
    heute = heute or date.today()
    if not aktiv(k):
        return None
    c = cfg(k)
    j = jahreswerte(k, db, heute)
    inv = _zahl(c.get("investition"))
    foe = _zahl(c.get("foerderung"))
    bestehend = c.get("gebaeude_bestehend", True) is not False
    abzug = max(0.0, inv - foe) if bestehend else 0.0
    try:
        ersparnis = st.ersparnis_abzug(k, abzug)["total"] if abzug else 0
    except Exception:  # noqa: BLE001
        ersparnis = 0
    unterhalt = _zahl(c.get("unterhalt_jahr")) or inv * 0.01
    lebensdauer = int(_zahl(c.get("lebensdauer"), 25)) or 25
    inv_jahr = int(_zahl(c.get("investition_jahr"))) or None
    ende = inv_jahr + lebensdauer if inv_jahr else None
    hinw = []
    steuerbar = steuer = nutzen = 0.0
    if j:
        export_netto = max(0.0, j.export - _zahl(c.get("strombezug_jahr")))
        steuerbar = j.mieter + export_netto
        try:
            steuer = -st.ersparnis_abzug(k, -steuerbar)["total"] if steuerbar else 0.0
        except Exception:  # noqa: BLE001
            steuer = 0.0
        nutzen = j.total - unterhalt - steuer
    netto = max(0.0, inv - foe - ersparnis)
    amort = round(netto / nutzen, 1) if nutzen > 0 and netto else None
    rendite = None
    if netto and nutzen > 0 and inv_jahr:
        deg = _zahl(c.get("degradation"), 0.5) / 100
        rest = max(1, (ende or inv_jahr + 25) - inv_jahr)
        rendite = _irr([-netto] + [nutzen * (1 - deg) ** i for i in range(rest)])
    # Hinweise
    if not inv:
        hinw.append("Investition und Jahr der Anlage fehlen – sonst lassen sich Rendite, Abzug und Erneuerung nicht rechnen.")
    if j is None:
        hinw.append("Noch keine Werte aus der vZEV-App – «Werte holen» oder die Jahreswerte von Hand eintragen.")
    if inv and inv_jahr and inv_jahr >= heute.year - 2 and bestehend:
        hinw.append(f"Investitionsabzug: CHF {_chf(abzug)} als Liegenschaftsunterhalt im Jahr {inv_jahr} (nur mit "
                    "effektiven Kosten statt Pauschale); was das Einkommen übersteigt, in die nächste oder übernächste "
                    f"Steuerperiode übertragen – Steuerersparnis rund CHF {_chf(ersparnis)}.")
    if inv and not bestehend:
        hinw.append("Anlage zeitnah zum Neubau: In BL ist der Abzug als Energiesparmassnahme dann in der Regel "
                    "nicht möglich.")
    if j and j.export and not _zahl(c.get("strombezug_jahr")):
        hinw.append("BL besteuert die Einspeisung netto (Vergütung minus privater Strombezug): eigene Stromkosten "
                    "eintragen, sonst rechnet die App mit der ganzen Vergütung.")
    offen = _neueste(db, "offene_rechnungen") if db is not None else None
    ueber = _neueste(db, "ueberfaellig") if db is not None else None
    n_ueber = int(ueber[1]) if ueber and ueber[0] >= (heute - timedelta(days=7)).isoformat() else 0
    if n_ueber:
        hinw.append(f"{n_ueber} überfällige vZEV-Rechnung(en) – Zahlungseingang in der vZEV-App prüfen und mahnen.")
    for b in komponenten(k):
        faellig = b["letzte"] + b["lebensdauer"]
        if faellig <= heute.year + 3:
            hinw.append(f"{b['name']}: Ersatz um {faellig} (rund CHF {_chf(b['kosten'])}) – in der Erneuerungsplanung "
                        "unter Wohnen eingeplant.")
    return Auswertung(j, inv, foe, abzug, ersparnis, round(unterhalt), round(steuerbar), round(steuer), round(nutzen),
                      round(netto), amort, None if rendite is None else round(rendite * 100, 1), lebensdauer, ende,
                      komponenten(k), offen[1] if offen else 0.0, n_ueber, hinw)


def abgleichen(k: dict, db, heute: date | None = None) -> bool:
    """Jahreswerte aus der vZEV-App als `solar.werte_vzev` in die Konfiguration (für Rechnungen ohne Datenbank)."""
    if not aktiv(k):
        return False
    try:
        j = jahreswerte({"solar": {s: v for s, v in cfg(k).items() if s not in ("mieter_jahr", "eigen_jahr",
                                                                              "export_jahr")}}, db, heute)
    except Exception:  # noqa: BLE001
        return False
    if not j or j.quelle == "Einstellungen":
        return False
    neu = {"mieter": round(j.mieter), "eigen": round(j.eigen), "export": round(j.export),
           "produktion": round(j.produktion), "quelle": j.quelle}
    if (k.get("solar") or {}).get("werte_vzev") == neu:
        return False
    k.setdefault("solar", {})["werte_vzev"] = neu
    return True


def finanzplan(k: dict, db, jahre_: list[int], pension: int) -> tuple[dict[int, float], dict[int, float]]:
    """(Mehrkosten vor der Pensionierung, Einnahmen ab der Pensionierung) pro Jahr.

    Vor der Pensionierung stecken Ertrag und tiefere Stromkosten schon im Sparpotenzial; es zählt nur der Wegfall nach
    dem Ende der Lebensdauer. Ab der Pensionierung zählen Verkauf an Mieter und Einspeisung (abzüglich Unterhalt und
    Steuern) als Einnahme, solange die Anlage läuft; danach fehlen auch die tieferen Stromkosten."""
    a = auswerten(k, db)
    if not a or not a.jahr:
        return {}, {}
    c = cfg(k)
    deg = _zahl(c.get("degradation"), 0.5) / 100
    start = int(_zahl(c.get("investition_jahr"))) or jahre_[0]
    bar = a.jahr.mieter + a.jahr.export - a.unterhalt - a.steuer_ertrag
    vorher, einnahmen = {}, {}
    for jj in jahre_:
        laeuft = not a.ende_jahr or jj <= a.ende_jahr
        faktor = (1 - deg) ** max(0, jj - max(start, jahre_[0]))
        if jj < pension:
            if not laeuft:
                vorher[jj] = (bar + a.jahr.eigen) * faktor
        elif laeuft:
            einnahmen[jj] = bar * faktor
        else:
            vorher[jj] = a.jahr.eigen * faktor
    return vorher, einnahmen


def erinnerungen(k: dict, db=None, heute: date | None = None) -> list:
    from erinnerungen import Erinnerung
    heute = heute or date.today()
    erg = []
    if not aktiv(k):
        return erg
    if heute.month <= 3:
        erg.append(Erinnerung(f"solar-steuer-{heute.year - 1}", "vZEV-Jahresabrechnung für die Steuererklärung",
                              date(heute.year, 3, 31), "Stromverkauf an Mieter und Einspeisevergütung "
                              f"{heute.year - 1} aus der vZEV-App als Beleg; Einspeisung in BL netto unter «Übrige "
                              "Einkünfte».", "solar"))
    if db is not None:
        try:
            ueber = _neueste(db, "ueberfaellig")
            if ueber and ueber[1] and ueber[0] >= (heute - timedelta(days=7)).isoformat():
                erg.append(Erinnerung(f"solar-ueberfaellig-{heute:%Y-%m}", "Überfällige vZEV-Rechnungen", heute,
                                      f"{int(ueber[1])} Rechnung(en) überfällig – in der vZEV-App mahnen.", "solar"))
        except Exception:  # noqa: BLE001
            pass
    return erg


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")
