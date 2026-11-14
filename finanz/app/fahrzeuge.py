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
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

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


def erinnerungen(k: dict, heute: date | None = None) -> list:
    from erinnerungen import Erinnerung
    heute = heute or date.today()
    erg = []
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
