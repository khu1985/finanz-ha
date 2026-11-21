"""Fahrzeuge: Wert, Kosten pro Jahr und Kilometer, Leasing, Ersatz und Termine (MFK, Leasingende).

Pro Fahrzeug unter `fahrzeuge[]` (alles ausser dem Namen freiwillig):
- name, person, antrieb (benzin | diesel | hybrid | elektro), erstzulassung (JJJJ-MM), kaufdatum, kaufpreis,
  wert (eigener Verkehrswert, z. B. aus Eurotax) mit wert_datum
- km_jahr, verbrauch (l bzw. kWh pro 100 km), gewicht_kg (Verkehrssteuer BL), parkplatz_monat, versicherung_jahr,
  verkehrssteuer_jahr (übersteuert die Schätzung)
- finanzierung: kauf | leasing; leasing_rate (pro Monat), leasing_ende, leasing_restwert
- ersatz_jahr, ersatz_preis, ersatz_planen (Standard: ja → erscheint als Lebensziel im Finanzplan und unter Sparen)

Werte und Annahmen:
- Verkehrswert (Schätzung ohne eigenen Wert): Kaufpreis −25 % im ersten Jahr, danach −15 % pro Jahr; im Leasing gehört
  das Auto der Leasinggesellschaft und zählt nicht zum Vermögen. Motorfahrzeuge gehören zum steuerbaren Vermögen
  (Hausrat ist steuerfrei) – deshalb führt die App für gekaufte Fahrzeuge ein Konto der Art «Fahrzeug» mit dem Wert nach.
- Kosten: Wertverlust bzw. Leasingrate, Versicherung (eigene Angabe bzw. Motorfahrzeug-Policen unter Versicherungen),
  Verkehrssteuer (BL: CHF 0.289846 pro kg Gesamtgewicht, Tarif 2027; sonst Schätzung 500), Vignette 40, Parkplatz,
  Energie (Benzin CHF 1.71 pro Liter, Strom 28 Rp. pro kWh – TCS 2026), Unterhalt und Reifen (Schätzung 7 Rp./km,
  elektrisch 5 Rp./km).
- Vergleich: TCS-Musterauto 2026 – Kaufpreis 45'000, 15'000 km pro Jahr, 74 Rappen pro km (Fixkosten 6'977,
  variable Kosten 4'135 pro Jahr).
- MFK: erstmals 5 Jahre nach der ersten Inverkehrsetzung, dann nach 3 Jahren, danach alle 2 Jahre.

Wartung (pro Fahrzeug, alles freiwillig): modell («Kia EV3»), km_stand (mit km_datum), service_datum und
service_km_stand (letzter Service), service_monate / service_intervall_km (übersteuern den Plan), reifen
(wechsel | ganzjahr), garantie_jahre / garantie_km. Der Wartungsplan kommt – in dieser Reihenfolge – aus den eigenen
Intervallen, aus einer Online-Abfrage über die KI-Aufgabe von Home Assistant (`wartung`, zum Prüfen markiert), aus dem
eingebauten Plan des Modells (WARTUNGSPLAENE, mit Quelle) oder aus einer typischen Annahme je Antrieb.

Sensoren aus Home Assistant: `ha_suchen()` fragt über die Template-API alle Sensoren mit Gerät ab und erkennt
Fahrzeuge an einem Kilometerzähler (odometer, mileage, Kilometerstand …). Rollen: km (Kilometerstand),
service_km (km bis zum Service), service_tage (Tage bis zum Service), service_datum (Termin), reifendruck (Warnung).
Mit einem Fahrzeug verknüpft (`geraet`, `sensoren`), liest die App die Werte einmal am Tag (Tabelle fahrzeug_werte):
Kilometerstand und Fahrleistung pro Jahr ersetzen dann die Schätzung, «km bis Service» der Herstellerintegration
(z. B. Kia Connect: «Next Service Distance») die Rechnung aus dem Plan.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

LOG = logging.getLogger("finanz")

ANTRIEBE = {"benzin": "Benzin", "diesel": "Diesel", "hybrid": "Hybrid", "elektro": "Elektro"}
VERBRAUCH = {"benzin": 6.5, "diesel": 5.5, "hybrid": 5.0, "elektro": 18.0}       # pro 100 km (l bzw. kWh)
PREIS = {"benzin": 1.71, "diesel": 1.80, "hybrid": 1.71, "elektro": 0.28}        # CHF pro l bzw. kWh
UNTERHALT_KM = {"elektro": 0.05}
UNTERHALT_STD = 0.07
VIGNETTE = 40.0
BL_STEUER_KG = 0.289846
STEUER_STD = 500.0
TCS = {"kaufpreis": 45000, "km": 15000, "rp_km": 74, "fix": 6977, "variabel": 4135}
QUELLEN = [
    ("TCS Kilometerkosten 2026", "https://www.tcs.ch/de/der-tcs/presse/medienmitteilungen-2026/kilometerkosten-2026.php"),
    ("TCS Musterauto 2026",
     "https://www.tcs.ch/de/testberichte-ratgeber/ratgeber/kontrollen-unterhalt/kilometerkosten-musterauto-2026.php"),
    ("Steuerbuch BL: Motorfahrzeuge gehören zum steuerbaren Vermögen",
     "https://kanton.baselland.ch/finanz-und-kirchendirektion/steuerverwaltung-steuerbuch/band-1/vermogen/downloads-1/"
     "band1_041_01.pdf"),
    ("MFK BL: Verkehrssteuer und Prüfintervalle",
     "https://bl-api.webcloud7.ch/politik-und-behorden/direktionen/sicherheitsdirektion/motorfahrzeugkontrolle/"
     "mfk-allgemein/infoblatt-2026.pdf"),
]


def _zahl(v, std: float = 0.0) -> float:
    try:
        t = str(v).replace("'", "").replace(",", ".").strip()
        return float(t) if t not in ("", "None") else std
    except ValueError:
        return std


def _datum(v) -> date | None:
    t = str(v or "").strip()
    if not t:
        return None
    try:
        return date.fromisoformat(t if len(t) > 7 else t + "-01")
    except ValueError:
        return None


def _jahre(von: date, bis: date) -> float:
    return max(0.0, (bis - von).days / 365.25)


def restwert_schaetzung(kaufpreis: float, alter: float) -> float:
    if alter <= 1:
        return kaufpreis * (1 - 0.25 * alter)
    return kaufpreis * 0.75 * 0.85 ** (alter - 1)


@dataclass
class Fahrzeug:
    i: int
    name: str
    person: str
    antrieb: str
    leasing: bool
    wert: float                 # Verkehrswert heute (0 im Leasing)
    wert_quelle: str
    kosten: dict[str, float]    # pro Jahr
    km_jahr: float
    mfk: date | None
    leasing_ende: date | None
    ersatz_jahr: int | None
    ersatz_betrag: float        # Ersatzpreis minus Restwert im Ersatzjahr
    hinweise: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(self.kosten.values()))

    @property
    def rp_km(self) -> float | None:
        return round(self.total / self.km_jahr * 100) if self.km_jahr else None

    @property
    def tcs_jahr(self) -> float:
        """TCS-Musterauto, auf die eigenen Kilometer umgerechnet (Fixkosten fest, variable pro km)."""
        return round(TCS["fix"] + TCS["variabel"] / TCS["km"] * (self.km_jahr or TCS["km"]))


def mfk_naechste(erstzulassung: date | None, heute: date) -> date | None:
    """Nächste Motorfahrzeugkontrolle: nach 5 Jahren, dann nach 3, danach alle 2 Jahre."""
    if not erstzulassung:
        return None
    jahre = 5
    d = date(erstzulassung.year + jahre, erstzulassung.month, 1)
    schritt = 3
    while d < date(heute.year, heute.month, 1):
        d = date(d.year + schritt, d.month, 1)
        schritt = 2
    return d


def _versicherung(k: dict, db, anzahl: int) -> float:
    try:
        import versicherungen as vi
        policen = [v for v in vi.alle(db) if v.get("sparte") == "motorfahrzeug"]
    except Exception:  # noqa: BLE001
        return 0.0
    total = sum(float(v.get("praemie_jahr") or 0) for v in policen)
    return total / max(1, anzahl)


def liste(k: dict) -> list[dict]:
    return [f for f in (k.get("fahrzeuge") or []) if isinstance(f, dict) and str(f.get("name") or "").strip()]


def alle(k: dict, db=None, heute: date | None = None) -> list[Fahrzeug]:
    heute = heute or date.today()
    roh = liste(k)
    vers_std = _versicherung(k, db, len(roh)) if db is not None else 0.0
    kanton = str((k.get("haushalt") or {}).get("kanton") or "").upper()
    erg = []
    for i, f in enumerate(roh):
        antrieb = str(f.get("antrieb") or "benzin")
        antrieb = antrieb if antrieb in ANTRIEBE else "benzin"
        leasing = str(f.get("finanzierung") or "kauf") == "leasing"
        kauf = _datum(f.get("kaufdatum")) or _datum(f.get("erstzulassung"))
        ez = _datum(f.get("erstzulassung")) or kauf
        preis = _zahl(f.get("kaufpreis"))
        km = _zahl(f.get("km_jahr"), 12000)
        hinw = []
        # Wert
        eigener = _zahl(f.get("wert"))
        if leasing:
            wert, quelle = 0.0, "Leasing – gehört der Leasinggesellschaft"
        elif eigener:
            wd = _datum(f.get("wert_datum")) or heute
            wert = eigener * (restwert_schaetzung(1, _jahre(ez, heute)) / max(1e-9, restwert_schaetzung(1, _jahre(ez, wd)))
                              if ez and wd < heute else 1)
            quelle = "eigener Wert" + (f" vom {wd:%m.%Y}, fortgeschrieben" if wd < heute else "")
        elif preis and ez:
            # Kaufpreis gilt am Kaufdatum; Alter ab Erstzulassung (Occasionen sind beim Kauf schon älter)
            alter_kauf = _jahre(ez, kauf) if kauf else 0.0
            faktor = restwert_schaetzung(1, _jahre(ez, heute)) / max(1e-9, restwert_schaetzung(1, alter_kauf))
            wert, quelle = preis * min(1.0, faktor), "Schätzung (−25 % im 1. Jahr, dann −15 % pro Jahr)"
        else:
            wert, quelle = 0.0, "Kaufpreis und Erstzulassung fehlen"
        # Kosten pro Jahr
        kosten: dict[str, float] = {}
        if leasing:
            kosten["Leasingrate"] = _zahl(f.get("leasing_rate")) * 12
        elif ez and wert:
            alter = _jahre(ez, heute)
            kosten["Wertverlust"] = max(0.0, wert * (1 - restwert_schaetzung(1, alter + 1) / restwert_schaetzung(1, alter)))
        kosten["Versicherung"] = _zahl(f.get("versicherung_jahr")) or vers_std
        steuer = _zahl(f.get("verkehrssteuer_jahr"))
        if not steuer:
            gewicht = _zahl(f.get("gewicht_kg"))
            steuer = gewicht * BL_STEUER_KG if kanton == "BL" and gewicht else STEUER_STD
        kosten["Verkehrssteuer"] = steuer
        kosten["Vignette"] = VIGNETTE
        kosten["Parkplatz"] = _zahl(f.get("parkplatz_monat")) * 12
        verbrauch = _zahl(f.get("verbrauch"), VERBRAUCH[antrieb])
        kosten["Energie"] = km / 100 * verbrauch * PREIS[antrieb]
        kosten["Unterhalt und Reifen"] = km * UNTERHALT_KM.get(antrieb, UNTERHALT_STD)
        kosten = {s: round(v) for s, v in kosten.items() if v}
        # Termine
        mfk = mfk_naechste(ez, heute)
        lende = _datum(f.get("leasing_ende")) if leasing else None
        # Ersatz
        ersatz_jahr = int(_zahl(f.get("ersatz_jahr"))) or None
        if not ersatz_jahr and lende:
            ersatz_jahr = lende.year
        if not ersatz_jahr and ez:
            ersatz_jahr = max(heute.year + 1, ez.year + 12)
        ersatz_preis = _zahl(f.get("ersatz_preis"), preis or 0)
        rest = 0.0
        if ersatz_jahr and not leasing and wert and ez:
            rest = wert * restwert_schaetzung(1, _jahre(ez, date(ersatz_jahr, 6, 30))) / max(
                1e-9, restwert_schaetzung(1, _jahre(ez, heute)))
        ersatz_betrag = max(0.0, ersatz_preis - rest)
        fz = Fahrzeug(i, str(f["name"]).strip(), str(f.get("person") or ""), antrieb, leasing, round(wert), quelle,
                      kosten, km, mfk, lende, ersatz_jahr, round(ersatz_betrag))
        if leasing:
            hinw.append(f"{fz.name}: Leasing kostet CHF {round(kosten.get('Leasingrate', 0)):,} pro Jahr".replace(",", "'")
                        + (f" bis {lende:%m.%Y}" if lende else "")
                        + " – vorzeitig auflösen ist teuer; für das nächste Auto rechtzeitig sparen, statt erneut zu leasen.")
        if "Versicherung" not in kosten:
            hinw.append(f"{fz.name}: keine Versicherung gefunden – Police unter Versicherungen hochladen oder den Betrag "
                        "pro Jahr hier eintragen (Haftpflicht und Kasko sind oft der grösste Fixkostenblock).")
        if fz.km_jahr and fz.rp_km and fz.rp_km > TCS["rp_km"] * 1.25:
            hinw.append(f"{fz.name}: rund {fz.rp_km} Rappen pro km – deutlich über dem TCS-Musterauto ({TCS['rp_km']} Rp.); "
                        "bei wenig Kilometern lohnen sich Carsharing oder ein günstigeres Auto oft.")
        fz.hinweise = hinw
        erg.append(fz)
    return erg


def ziele(k: dict, jetzt: int) -> list[dict]:
    """Ersatz der Fahrzeuge als Lebensziele (für Finanzplan und Sparen & Anlegen)."""
    erg = []
    for fz, f in zip(alle(k), liste(k)):
        if f.get("ersatz_planen") is False or not fz.ersatz_jahr or fz.ersatz_jahr < jetzt or not fz.ersatz_betrag:
            continue
        erg.append({"name": f"Ersatz {fz.name}", "betrag": float(fz.ersatz_betrag), "jahr": int(fz.ersatz_jahr),
                    "art": "muss", "fahrzeug": True})
    return erg


def abgleichen(k: dict, db, heute: date | None = None) -> bool:
    """Gekaufte Fahrzeuge als Konto der Art «Fahrzeug» mit dem Wert dieses Monats nachführen (steuerbares Vermögen)."""
    import vermoegen as vm
    heute = heute or date.today()
    stichtag = date(heute.year, heute.month, 1).isoformat()
    geaendert = False
    for fz in alle(k, db, heute):
        name = f"Fahrzeug {fz.name}"
        if fz.leasing or not fz.wert:
            continue
        x = next((x for x in vm.konten(db) if x["name"] == name), None)
        if x and x.get("datum") == stichtag and round(x.get("betrag") or 0) == fz.wert:
            continue
        kid = vm.konto_anlegen(db, name, "fahrzeug", fz.person)
        vm.saldo_setzen(db, kid, stichtag, fz.wert)
        geaendert = True
    return geaendert


def erinnerungen(k: dict, heute: date | None = None, db=None) -> list:
    from erinnerungen import Erinnerung
    heute = heute or date.today()
    erg = _wartung_erinnerungen(k, heute, db)
    for fz in alle(k, None, heute):
        if fz.mfk and 0 <= (fz.mfk - heute).days <= 90:
            erg.append(Erinnerung(f"fahrzeug-{fz.name}-mfk-{fz.mfk:%Y-%m}", f"MFK {fz.name}", fz.mfk,
                                  "Die Motorfahrzeugkontrolle steht an (Aufgebot kommt per Post) – Service vorher "
                                  "machen lassen.", "fahrzeuge"))
        if fz.leasing_ende and 0 <= (fz.leasing_ende - heute).days <= 180:
            erg.append(Erinnerung(f"fahrzeug-{fz.name}-leasing", f"Leasingende {fz.name}", fz.leasing_ende,
                                  "Rückgabe, Übernahme zum Restwert oder Ersatz entscheiden; Schäden vorher prüfen "
                                  "lassen.", "fahrzeuge"))
    if liste(k) and heute.month == 12:
        erg.append(Erinnerung(f"vignette-{heute.year + 1}", f"Vignette {heute.year + 1}", date(heute.year + 1, 1, 31),
                              "Die Autobahnvignette des neuen Jahres gilt ab 1. Dezember – bis Ende Januar lösen.",
                              "fahrzeuge"))
    return erg


# ---------------------------------------------------------------- Wartung

# Wartungspläne der Hersteller (massgebend bleiben Serviceanzeige und Serviceheft des Fahrzeugs)
WARTUNGSPLAENE = [
    {"muster": r"\bev\s?3\b", "name": "Kia EV3",
     "service_monate": 24, "service_km": 30000, "garantie_jahre": 7, "garantie_km": 150000,
     "arbeiten": [("Inspektion: Bremsen, Lenkung, Antriebswellen, Reifen, 12-V-Batterie, Klimaanlage, Hochvoltbatterie, "
                   "Fehlerspeicher und Software", 24, 30000),
                  ("Bremsflüssigkeit wechseln", 24, 0),
                  ("Innenraumfilter wechseln", 0, 30000),
                  ("Untersetzungsgetriebe prüfen", 0, 60000),
                  ("Kühlmittel erstmals wechseln (danach alle 24 Monate bzw. 30'000 km)", 120, 180000),
                  ("eCall-Notrufbatterie ersetzen", 48, 0)],
     "quellen": [("CarWiki: Kia EV3 Inspektion und Wartungsplan", "https://carwiki.de/kia-ev3-inspektion/"),
                 ("Kia: 7-Jahre-Garantie (Bedingungen im Garantieheft)", "https://www.kia.com/de/garantie")]},
]
TYPISCH = {   # ohne Plan des Modells: typische Intervalle, im Serviceheft prüfen
    "elektro": (24, 30000), "benzin": (12, 20000), "diesel": (12, 20000), "hybrid": (12, 15000)}
REIFEN_WINTER = (10, 1, 11, 15)      # Erinnerung vom 1.10. bis 15.11. (Faustregel «von O bis O»)
REIFEN_SOMMER = (4, 1, 5, 15)        # vom 1.4. bis 15.5.


def plan_fuer(f: dict) -> dict | None:
    text = f"{f.get('modell') or ''} {f.get('name') or ''}".lower()
    return next((p for p in WARTUNGSPLAENE if re.search(p["muster"], text)), None)


def _plus_monate(d: date, monate: int) -> date:
    m = d.month - 1 + monate
    j, m = d.year + m // 12, m % 12 + 1
    import calendar
    return date(j, m, min(d.day, calendar.monthrange(j, m)[1]))


@dataclass
class Wartung:
    plan: str                       # «Kia EV3 (Hersteller)», «typisch für Elektro», «Online-Abfrage (KI) …»
    quellen: list[tuple[str, str]]
    service_monate: int
    service_km: int
    km_stand: float | None
    km_quelle: str                  # «Sensor sensor.ev3_odometer 21.11.2026», «eigene Angabe 03.2026», ''
    km_jahr: float                  # gemessen bzw. eingetragen
    km_jahr_quelle: str
    naechster: date | None          # nächster Service (früheres von Zeit und Kilometern)
    rest_km: float | None
    grund: str
    garantie_ende: date | None
    garantie_km: int
    arbeiten: list[tuple[str, date | None, int | None]] = field(default_factory=list)   # (Arbeit, fällig, bei km)
    reifen: str = ""
    reifendruck_warnung: bool = False
    pruefen: bool = False           # Plan aus der Online-Abfrage noch nicht geprüft


def _werte(db, name: str) -> dict[str, list[tuple[str, float]]]:
    if db is None:
        return {}
    try:
        tabellen(db)
        erg: dict[str, list[tuple[str, float]]] = {}
        for d, s, w in db.execute("SELECT datum, schluessel, wert FROM fahrzeug_werte WHERE fahrzeug = ? ORDER BY datum",
                                  (name,)):
            erg.setdefault(s, []).append((d, w))
        return erg
    except Exception:  # noqa: BLE001
        return {}


def wartung(f: dict, fz: "Fahrzeug", db=None, heute: date | None = None) -> Wartung:
    heute = heute or date.today()
    ez = _datum(f.get("erstzulassung")) or _datum(f.get("kaufdatum"))
    plan = plan_fuer(f)
    online = f.get("wartung") if isinstance(f.get("wartung"), dict) else {}
    if plan:
        name, quellen = f"{plan['name']} (Hersteller)", list(plan["quellen"])
        monate, km_int = plan["service_monate"], plan["service_km"]
        g_jahre, g_km = plan.get("garantie_jahre", 0), plan.get("garantie_km", 0)
        arbeiten_plan = list(plan["arbeiten"])
    else:
        monate, km_int = TYPISCH.get(fz.antrieb, (12, 20000))
        name, quellen, g_jahre, g_km = f"typisch für {ANTRIEBE.get(fz.antrieb, fz.antrieb)} – im Serviceheft prüfen", [], 0, 0
        arbeiten_plan = [("Service laut Serviceheft", monate, km_int), ("Bremsflüssigkeit wechseln", 24, 0)]
    pruefen = False
    if online and not plan:
        monate = int(_zahl(online.get("service_monate"), monate)) or monate
        km_int = int(_zahl(online.get("service_km"), km_int)) or km_int
        g_jahre = int(_zahl(online.get("garantie_jahre"), g_jahre))
        g_km = int(_zahl(online.get("garantie_km"), g_km))
        arb = [(str(a.get("text") or "")[:120], int(_zahl(a.get("monate"))), int(_zahl(a.get("km"))))
               for a in online.get("arbeiten") or [] if isinstance(a, dict) and a.get("text")]
        arbeiten_plan = arb or arbeiten_plan
        name = f"Online-Abfrage ({online.get('datum', '')})"
        if online.get("quelle"):
            quellen = [(str(online["quelle"])[:120], str(online["quelle"]) if str(online["quelle"]).startswith("http") else "")]
        pruefen = not online.get("geprueft")
    if _zahl(f.get("service_monate")) or _zahl(f.get("service_intervall_km")):
        monate = int(_zahl(f.get("service_monate"), monate)) or monate
        km_int = int(_zahl(f.get("service_intervall_km"), km_int)) or km_int
        name = "eigene Intervalle"
    g_jahre = int(_zahl(f.get("garantie_jahre"), g_jahre))
    g_km = int(_zahl(f.get("garantie_km"), g_km))

    # Kilometerstand und Fahrleistung: Sensor vor eigener Angabe
    w = _werte(db, fz.name)
    km_stand, km_quelle = None, ""
    if w.get("km"):
        d, v = w["km"][-1]
        km_stand, km_quelle = v, f"Sensor, {date.fromisoformat(d):%d.%m.%Y}"
    elif _zahl(f.get("km_stand")):
        km_stand = _zahl(f.get("km_stand"))
        kd = _datum(f.get("km_datum"))
        km_quelle = "eigene Angabe" + (f", {kd:%d.%m.%Y}" if kd else "")
        if kd and kd < heute and fz.km_jahr:          # bis heute fortschreiben
            km_stand += fz.km_jahr * (heute - kd).days / 365.25
            km_quelle += ", fortgeschrieben"
    km_jahr, km_jahr_quelle = fz.km_jahr, "eigene Angabe" if _zahl(f.get("km_jahr")) else "Annahme 12'000 km"
    if len(w.get("km", [])) >= 2:
        (d0, v0), (d1, v1) = w["km"][0], w["km"][-1]
        tage = (date.fromisoformat(d1) - date.fromisoformat(d0)).days
        if tage >= 30 and v1 > v0:
            km_jahr, km_jahr_quelle = (v1 - v0) / tage * 365.25, f"gemessen über {tage} Tage"
    pro_tag = km_jahr / 365.25 if km_jahr else 0

    # nächster Service
    letzter = _datum(f.get("service_datum"))
    letzter_km = _zahl(f.get("service_km_stand"))
    kandidaten: list[tuple[date, str]] = []
    rest_km = None
    if w.get("service_km"):
        rest_km = w["service_km"][-1][1]
        grund = "km bis Service laut Fahrzeug"
    else:
        grund = ""
    if w.get("service_datum"):
        try:
            kandidaten.append((date.fromtimestamp(w["service_datum"][-1][1]), "Termin laut Fahrzeug"))
        except (OverflowError, OSError, ValueError):
            pass
    if w.get("service_tage"):
        kandidaten.append((heute + timedelta(days=int(w["service_tage"][-1][1])), "Tage bis Service laut Fahrzeug"))
    if not kandidaten:
        basis = letzter or ez
        if basis:
            d = _plus_monate(basis, monate)
            while not letzter and d < heute - timedelta(days=60):      # ohne letzten Service: nächster Termin im Raster
                d = _plus_monate(d, monate)
            kandidaten.append((d, f"{monate} Monate nach {'dem letzten Service' if letzter else 'der Inverkehrsetzung'}"))
    if rest_km is None and km_stand is not None and km_int:
        ziel = (letzter_km + km_int) if letzter_km else (int(km_stand // km_int) + 1) * km_int
        rest_km = ziel - km_stand
        grund = grund or f"alle {km_int:,} km".replace(",", "'")
    if rest_km is not None and pro_tag:
        kandidaten.append((heute + timedelta(days=max(0, int(rest_km / pro_tag))), grund))
    naechster, grund_ = min(kandidaten) if kandidaten else (None, "")

    # Arbeiten aus dem Plan
    arbeiten = []
    basis = letzter or ez
    for text, m, kmx in arbeiten_plan:
        dd = None
        if m and basis:
            dd = _plus_monate(basis, m)
            while dd < heute:
                dd = _plus_monate(dd, m)
        bei = None
        if kmx and km_stand is not None:
            bei = (int(km_stand // kmx) + 1) * kmx
        arbeiten.append((text, dd, bei))
    garantie = _plus_monate(ez, 12 * g_jahre) if ez and g_jahre else None
    warnung = bool(w.get("reifendruck") and w["reifendruck"][-1][1] > 0 and w["reifendruck"][-1][0] >= (
        heute - timedelta(days=3)).isoformat())
    return Wartung(name, quellen, monate, km_int, round(km_stand) if km_stand is not None else None, km_quelle,
                   round(km_jahr), km_jahr_quelle, naechster, round(rest_km) if rest_km is not None else None, grund_,
                   garantie, g_km, arbeiten, str(f.get("reifen") or "wechsel"), warnung, pruefen)


def _wartung_erinnerungen(k: dict, heute: date, db) -> list:
    from erinnerungen import Erinnerung
    erg = []
    for fz, f in zip(alle(k, None, heute), liste(k)):
        try:
            wa = wartung(f, fz, db, heute)
        except Exception as e:  # noqa: BLE001
            LOG.debug("Wartung %s: %s", fz.name, e)
            continue
        bald_km = wa.rest_km is not None and wa.rest_km <= 2000
        if wa.naechster and ((wa.naechster - heute).days <= 60 or bald_km):
            rest = f" (noch rund {wa.rest_km:,} km)".replace(",", "'") if wa.rest_km is not None else ""
            erg.append(Erinnerung(f"fahrzeug-{fz.name}-service-{wa.naechster:%Y-%m}", f"Service {fz.name}",
                                  wa.naechster, f"Service fällig{rest} – {wa.grund}. Termin in der Garage buchen; "
                                  "danach Datum und Kilometerstand beim Fahrzeug eintragen.", "fahrzeuge"))
        if wa.reifen == "wechsel":
            for (m0, t0, m1, t1), art, text in ((REIFEN_WINTER, "winter", "Winterreifen montieren"),
                                               (REIFEN_SOMMER, "sommer", "Sommerreifen montieren")):
                von, bis = date(heute.year, m0, t0), date(heute.year, m1, t1)
                if von - timedelta(days=14) <= heute <= bis:
                    erg.append(Erinnerung(f"fahrzeug-{fz.name}-reifen-{art}-{heute.year}", f"{text}: {fz.name}", bis,
                                          "Faustregel «von O bis O» (Oktober bis Ostern). Profil prüfen: Winterreifen "
                                          "mindestens 4 mm, Sommerreifen 3 mm empfohlen (gesetzlich 1.6 mm); "
                                          "Reifendruck nach dem Wechsel kontrollieren.", "fahrzeuge"))
        if wa.reifendruck_warnung:
            erg.append(Erinnerung(f"fahrzeug-{fz.name}-reifendruck-{heute:%Y-%m-%d}", f"Reifendruck {fz.name}", heute,
                                  "Das Fahrzeug meldet einen zu tiefen Reifendruck – an der Tankstelle prüfen.",
                                  "fahrzeuge"))
        if wa.garantie_ende and 0 <= (wa.garantie_ende - heute).days <= 120:
            erg.append(Erinnerung(f"fahrzeug-{fz.name}-garantie", f"Garantie {fz.name} läuft ab", wa.garantie_ende,
                                  "Vor Ablauf alle Mängel in der Garage prüfen und beheben lassen (noch auf Garantie)"
                                  + (f"; die Garantie endet auch bei {wa.garantie_km:,} km.".replace(",", "'")
                                     if wa.garantie_km else "."), "fahrzeuge"))
        for text, dd, _ in wa.arbeiten:
            if dd and 0 <= (dd - heute).days <= 30 and "Inspektion" not in text and not text.startswith("Service"):
                erg.append(Erinnerung(f"fahrzeug-{fz.name}-{re.sub(r'[^a-z]+', '-', text.lower())[:30]}-{dd:%Y-%m}",
                                      f"{fz.name}: {text}", dd, "Laut Wartungsplan fällig – meist beim nächsten Service "
                                      "mitmachen lassen.", "fahrzeuge"))
    return erg


# ---------------------------------------------------------------- Sensoren aus Home Assistant

ROLLEN = {"km": "Kilometerstand", "service_km": "km bis Service", "service_tage": "Tage bis Service",
          "service_datum": "Service-Termin", "reifendruck": "Reifendruck-Warnung"}
_MUSTER = {
    "km": r"odometer|mileage|kilometerstand|kilometer_?stand|km_?stand|gesamtkilometer|total_?distance|odo\b",
    "service_km": r"(next|naechst|nächst)\w*[ _]?(service|inspection|inspektion)\w*[ _]?(distance|km|mileage)?|"
                  r"(service|inspection|inspektion)\w*[ _]?(distance|km|kilomet)",
    "service_tage": r"(service|inspection|inspektion)\w*[ _]?(days|tage|time)",
    "service_datum": r"(service|inspection|inspektion)\w*[ _]?(date|datum|due)",
    "reifendruck": r"(tire|tyre|reifen)\w*[ _]?(pressure|druck)",
}
_VORLAGE = """{%- set ns = namespace(l=[]) -%}
{%- for s in (states.sensor | list) + (states.binary_sensor | list) -%}
{%- if s.entity_id is search('odometer|mileage|kilomet|km_|distance|service|inspection|inspektion|tire|tyre|reifen|odo', ignorecase=True)
      or s.attributes.unit_of_measurement in ['km', 'mi'] -%}
{%- set d = device_id(s.entity_id) -%}
{%- if d -%}
{%- set ns.l = ns.l + [{'e': s.entity_id, 'n': s.name, 's': s.state, 'u': s.attributes.unit_of_measurement | default(''),
    'c': s.attributes.device_class | default(''), 'g': device_attr(d, 'name_by_user') or device_attr(d, 'name'),
    'h': device_attr(d, 'manufacturer') or '', 'm': device_attr(d, 'model') or ''}] -%}
{%- endif -%}{%- endif -%}{%- endfor -%}
{{ ns.l | tojson }}"""


def tabellen(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS fahrzeug_werte (datum TEXT NOT NULL, fahrzeug TEXT NOT NULL, "
               "schluessel TEXT NOT NULL, wert REAL, PRIMARY KEY (datum, fahrzeug, schluessel))")
    db.execute("CREATE TABLE IF NOT EXISTS fahrzeug_geraete (name TEXT PRIMARY KEY, daten TEXT NOT NULL, gefunden TEXT)")


def rolle(entity_id: str, name: str, einheit: str, klasse: str) -> str | None:
    t = f"{entity_id} {name}".lower().replace("-", "_")
    vergangen = bool(re.search(r"\blast|_last|letzt|previous|vorig", t))
    for r in ("service_km", "service_tage", "service_datum", "reifendruck", "km"):
        if re.search(_MUSTER[r], t):
            if vergangen and r != "km":
                continue
            if r == "km" and einheit not in ("km", "mi", ""):
                continue
            if r == "service_datum" and klasse not in ("date", "timestamp", ""):
                continue
            if r == "reifendruck" and not entity_id.startswith("binary_sensor."):
                continue
            if r == "service_km" and einheit not in ("km", "mi", ""):
                continue
            return r
    return None


@dataclass
class Geraet:
    name: str
    hersteller: str
    modell: str
    sensoren: dict[str, str]                 # Rolle → entity_id
    werte: dict[str, str]                    # Rolle → Zustand (Anzeige)


def geraete_aus(liste_: list[dict]) -> list[Geraet]:
    """Sensoren nach Gerät gruppieren; ein Fahrzeug hat einen Kilometerzähler."""
    gruppen: dict[str, Geraet] = {}
    for x in liste_:
        r = rolle(str(x.get("e") or ""), str(x.get("n") or ""), str(x.get("u") or ""), str(x.get("c") or ""))
        if not r:
            continue
        g = gruppen.setdefault(str(x.get("g") or ""), Geraet(str(x.get("g") or ""), str(x.get("h") or ""),
                                                            str(x.get("m") or ""), {}, {}))
        if r not in g.sensoren:
            g.sensoren[r] = str(x["e"])
            g.werte[r] = f"{x.get('s')} {x.get('u') or ''}".strip()
    return [g for g in gruppen.values() if g.name and "km" in g.sensoren]


def _ha(pfad: str, daten: dict | None = None):
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("Kein Zugriff auf Home Assistant (die App läuft nicht im Home Assistant).")
    req = urllib.request.Request(f"http://supervisor/core/api/{pfad}", data=json.dumps(daten).encode() if daten else None,
                                 method="POST" if daten else "GET",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 – feste Adresse im Supervisor
        return r.read().decode("utf-8")


def ha_suchen(db) -> list[Geraet]:
    """Fahrzeuge unter den Geräten von Home Assistant suchen und das Ergebnis merken."""
    roh = json.loads(_ha("template", {"template": _VORLAGE}) or "[]")
    gefunden = geraete_aus(roh)
    tabellen(db)
    db.execute("DELETE FROM fahrzeug_geraete")
    for g in gefunden:
        db.execute("INSERT INTO fahrzeug_geraete VALUES (?, ?, ?)", (g.name, json.dumps(g.__dict__), date.today().isoformat()))
    db.commit()
    return gefunden


def gefundene(db) -> list[Geraet]:
    try:
        tabellen(db)
        return [Geraet(**json.loads(d)) for (d,) in db.execute("SELECT daten FROM fahrzeug_geraete ORDER BY name")]
    except Exception:  # noqa: BLE001
        return []


def zu_fahrzeug(g: Geraet, f: dict) -> bool:
    """Passt das Gerät zum Fahrzeug (Name bzw. Modell)?"""
    if f.get("geraet"):
        return f["geraet"] == g.name
    worte = {w for w in re.findall(r"[a-z0-9]{2,}", f"{f.get('name', '')} {f.get('modell', '')}".lower())}
    geraet = set(re.findall(r"[a-z0-9]{2,}", f"{g.name} {g.hersteller} {g.modell}".lower()))
    return bool(worte & geraet - {"auto", "car", "the"})


def einlesen(db, name: str, werte: dict[str, float], heute: date | None = None) -> int:
    heute = heute or date.today()
    tabellen(db)
    for s, v in werte.items():
        db.execute("INSERT OR REPLACE INTO fahrzeug_werte VALUES (?, ?, ?, ?)", (heute.isoformat(), name, s, v))
    db.commit()
    return len(werte)


def _wert(z: dict) -> float | None:
    st = str(z.get("state") or "")
    if st in ("on", "off"):
        return 1.0 if st == "on" else 0.0
    try:
        v = float(st)
    except ValueError:
        try:
            return datetime.fromisoformat(st.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    if (z.get("attributes") or {}).get("unit_of_measurement") == "mi":
        v *= 1.609344
    return v


_VERSUCH: datetime | None = None


def holen(k: dict, db, heute: date | None = None) -> int:
    n = 0
    for f in liste(k):
        for r, eid in (f.get("sensoren") or {}).items():
            if r not in ROLLEN:
                continue
            try:
                z = json.loads(_ha(f"states/{eid}"))
            except (urllib.error.HTTPError, ValueError) as e:
                LOG.info("Fahrzeug %s: Sensor %s nicht lesbar (%s)", f.get("name"), eid, e)
                continue
            v = _wert(z)
            if v is not None:
                n += einlesen(db, str(f["name"]).strip(), {r: v}, heute)
    return n


def aktualisieren(k: dict, db, heute: date | None = None) -> bool:
    """Einmal am Tag die verknüpften Sensoren lesen (nur im Home Assistant)."""
    global _VERSUCH
    if not os.environ.get("SUPERVISOR_TOKEN") or not any(f.get("sensoren") for f in liste(k)):
        return False
    heute = heute or date.today()
    tabellen(db)
    if db.execute("SELECT 1 FROM fahrzeug_werte WHERE datum = ?", (heute.isoformat(),)).fetchone():
        return False
    if _VERSUCH and datetime.now() - _VERSUCH < timedelta(hours=6):
        return False
    _VERSUCH = datetime.now()
    try:
        return holen(k, db, heute) > 0
    except Exception as e:  # noqa: BLE001
        LOG.warning("Fahrzeug-Sensoren: %s", e)
        return False


# ---------------------------------------------------------------- Wartungsplan online (KI-Aufgabe)

KI_ANWEISUNG = """Suche den Wartungsplan des Herstellers für dieses Fahrzeug in der Schweiz: {modell}, {antrieb},
erste Inverkehrsetzung {ez}. Antworte nur mit JSON: service_monate (Zahl, Serviceintervall in Monaten), service_km
(Zahl, Serviceintervall in km), garantie_jahre (Zahl), garantie_km (Zahl), arbeiten (Liste von Objekten mit text,
monate, km – z. B. Bremsflüssigkeit, Innenraumfilter, Zahnriemen, Kühlmittel), quelle (Webadresse oder Name des
Dokuments), unsicher (true, wenn du die Werte nicht aus einer Herstellerquelle hast). Unbekannte Werte weglassen."""


def online_abfragen(k: dict, i: int) -> dict:
    """Wartungsplan über die KI-Aufgabe von Home Assistant holen (zum Prüfen markiert)."""
    import versicherungen as vi
    f = liste(k)[i]
    modell = str(f.get("modell") or f.get("name"))
    daten = vi.ki_aufgabe(KI_ANWEISUNG.format(modell=modell, antrieb=ANTRIEBE.get(str(f.get("antrieb")), ""),
                                              ez=f.get("erstzulassung") or "unbekannt"),
                          (k.get("ki") or {}).get("entity", ""), "Wartungsplan Fahrzeug")
    erg = {"datum": date.today().isoformat(), "geprueft": False}
    for s in ("service_monate", "service_km", "garantie_jahre", "garantie_km"):
        v = _zahl(daten.get(s))
        if v > 0:
            erg[s] = int(v)
    erg["arbeiten"] = [{"text": str(a.get("text"))[:120], "monate": int(_zahl(a.get("monate"))), "km": int(_zahl(a.get("km")))}
                       for a in (daten.get("arbeiten") or []) if isinstance(a, dict) and a.get("text")][:12]
    if daten.get("quelle"):
        erg["quelle"] = str(daten["quelle"])[:200]
    erg["unsicher"] = bool(daten.get("unsicher"))
    if not erg.get("service_monate") and not erg.get("service_km"):
        raise RuntimeError("Die KI fand kein Serviceintervall – im Serviceheft nachsehen und von Hand eintragen.")
    return erg
