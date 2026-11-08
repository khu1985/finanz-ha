"""Rechenkern Vorsorge: AHV (1. Säule), Pensionskasse (2. Säule), Säule 3a, Pensionslücke.

Vereinfachungen (siehe DOCS.md):
- Beträge in heutigen Franken, keine Teuerung.
- AHV: Rentenskala 44 als stetige Formel, Einkommenssplitting über die ganze Beitragsdauer,
  Erziehungsgutschriften hälftig, Referenzalter 65.
- PK: Altersguthaben mit jährlichem Zins und Sparbeitrag (laut Ausweis oder BVG-Minimum).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


def geburtsjahr(person: dict) -> int:
    return int(str(person["geburtsdatum"])[:4])


def pensionsjahr(person: dict) -> int:
    return geburtsjahr(person) + int(person.get("pensionierung_alter", 65))


def _verheiratet(k: dict) -> bool:
    return k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet" and len(k["personen"]) >= 2


# ---------------------------------------------------------------- AHV

def ahv_vollrente_monat(einkommen: float, kz: dict) -> float:
    """Monatliche Vollrente nach Rentenskala 44 (stetige Formel, AHVG Art. 34)."""
    m = kz["ahv_min"]
    e = max(0.0, einkommen)
    if e <= 12 * m:
        rente = m
    elif e <= 36 * m:
        rente = 0.74 * m + 13 / 600 * e
    else:
        rente = 1.04 * m + 8 / 600 * e
    return round(min(rente, kz["ahv_max"]), 2)


def ahv_beitragsjahre(person: dict, jetzt: int, kz: dict) -> int:
    bisher = int(person["ahv"].get("beitragsjahre_bisher", 0))
    # Beiträge bis zum Referenzalter (bei Frühpensionierung als Nichterwerbstätige weiter bezahlt)
    bis = geburtsjahr(person) + 65
    zukuenftig = max(0, bis - jetzt)
    jahre = min(kz["ahv_vollbeitragsjahre"], bisher + zukuenftig)
    return max(0, jahre - int(person["ahv"].get("fehlende_jahre", 0)))


def erziehungsjahre(person: dict, kinder: list[dict]) -> int:
    """Jahre mit mindestens einem Kind unter 16, ab dem 21. Altersjahr bis zum Referenzalter."""
    gj = geburtsjahr(person)
    jahre = set()
    for kind in kinder or []:
        kj = int(kind.get("geburtsjahr", 0))
        if not kj:
            continue
        for j in range(kj + 1, kj + 17):
            if gj + 21 <= j < gj + 65:
                jahre.add(j)
    return len(jahre)


@dataclass
class AhvErgebnis:
    name: str
    beitragsjahre: int
    einkommen: float
    erziehungsjahre: int
    vollrente: float
    rente_monat: float           # vor Plafonierung
    rente_monat_plafoniert: float = 0.0
    rente_jahr: float = 0.0
    alter: int = 65


def ahv(k: dict, jetzt: int | None = None) -> list[AhvErgebnis]:
    kz = k["kennzahlen"]
    jetzt = jetzt or date.today().year
    personen = k["personen"]
    verh = _verheiratet(k)
    einkommen = []
    for p in personen:
        e = float(p["ahv"].get("einkommen_durchschnitt") or 0) or float(p.get("lohn_brutto", 0))
        einkommen.append(e)
    if verh:
        mittel = sum(einkommen[:2]) / 2
        einkommen = [mittel, mittel] + einkommen[2:]
    gutschrift = 3 * 12 * kz["ahv_min"]  # Erziehungsgutschrift pro Jahr
    erg = []
    for p, e in zip(personen, einkommen):
        jahre = ahv_beitragsjahre(p, jetzt, kz)
        ej = erziehungsjahre(p, k["haushalt"].get("kinder", []))
        anteil = 0.5 if verh else 1.0
        e_mit = e + (ej * gutschrift * anteil / jahre if jahre else 0)
        voll = ahv_vollrente_monat(e_mit, kz)
        rente = voll * jahre / kz["ahv_vollbeitragsjahre"]
        alter = int(p.get("pensionierung_alter", 65))
        if alter < 65:
            rente *= max(0.0, 1 - kz["ahv_vorbezug_kuerzung"] / 100 * (65 - alter))
        elif alter > 65:
            zuschlag = {1: 5.2, 2: 10.8, 3: 17.1, 4: 24.0, 5: 31.5}[min(alter - 65, 5)]
            rente *= 1 + zuschlag / 100
        erg.append(AhvErgebnis(p["name"], jahre, round(e_mit), ej, voll, round(rente, 2), alter=alter))
    # Plafonierung Ehepaar: Summe höchstens 150 % der Maximalrente
    plafond = kz["ahv_max"] * kz["ahv_plafond_ehepaar"] / 100
    summe = sum(r.rente_monat for r in erg[:2])
    faktor = min(1.0, plafond / summe) if verh and summe else 1.0
    monate = 13 if kz.get("ahv_13_rente", True) else 12
    for i, r in enumerate(erg):
        r.rente_monat_plafoniert = round(r.rente_monat * (faktor if i < 2 else 1.0), 2)
        r.rente_jahr = round(r.rente_monat_plafoniert * monate)
    return erg


# ---------------------------------------------------------------- Pensionskasse

def bvg_gutschriftsatz(alter: int, kz: dict) -> float:
    satz = 0.0
    for ab, s in sorted((int(a), float(b)) for a, b in kz["bvg_gutschriften"].items()):
        if alter >= ab:
            satz = s
    return satz if alter < 65 else 0.0


def bvg_koordinierter_lohn(lohn: float, kz: dict) -> float:
    if lohn < kz["bvg_eintrittsschwelle"]:
        return 0.0
    max_koord = kz["bvg_max_lohn"] - kz["bvg_koordinationsabzug"]
    koord = min(lohn, kz["bvg_max_lohn"]) - kz["bvg_koordinationsabzug"]
    return max(kz["bvg_min_koord_lohn"], min(koord, max_koord))


@dataclass
class PkErgebnis:
    name: str
    verlauf: list[tuple[int, float]]
    guthaben_pensionierung: float
    kapital: float
    rente_jahr: float
    einkaeufe: float
    warnungen: list[str] = field(default_factory=list)


def pk(person: dict, k: dict) -> PkErgebnis:
    kz = k["kennzahlen"]
    cfg = person["pk"]
    gj = geburtsjahr(person)
    start = int(str(cfg.get("stand", f"{date.today().year}-01-01"))[:4])
    ende = pensionsjahr(person)
    guthaben = float(cfg.get("altersguthaben", 0))
    zins = float(cfg.get("zins", kz["bvg_mindestzins"])) / 100
    lohn = float(person.get("lohn_brutto", 0))
    wachstum = float(k["annahmen"].get("lohnentwicklung", 0)) / 100
    einkauf = {}
    for e in cfg.get("einkauf_geplant") or []:
        einkauf[int(e["jahr"])] = einkauf.get(int(e["jahr"]), 0) + float(e["betrag"])
    verlauf = [(start, round(guthaben))]
    for jahr in range(start, ende):
        alter = jahr - gj
        if float(cfg.get("sparbeitrag_jahr") or 0) > 0:
            beitrag = float(cfg["sparbeitrag_jahr"]) * (1 + wachstum) ** (jahr - start)
        else:
            beitrag = bvg_koordinierter_lohn(lohn * (1 + wachstum) ** (jahr - start), kz) * bvg_gutschriftsatz(alter, kz) / 100
        guthaben = guthaben * (1 + zins) + beitrag + einkauf.get(jahr, 0)
        verlauf.append((jahr + 1, round(guthaben)))
    anteil = min(100.0, max(0.0, float(cfg.get("kapitalbezug_anteil", 0)))) / 100
    kapital = guthaben * anteil
    uws = float(cfg.get("umwandlungssatz", kz["bvg_umwandlungssatz"])) / 100
    rente = (guthaben - kapital) * uws
    warn = []
    summe_einkauf = sum(einkauf.values())
    if summe_einkauf > float(cfg.get("einkauf_potenzial", 0) or 0) > 0:
        warn.append(f"{person['name']}: geplante Einkäufe ({summe_einkauf:,.0f}) übersteigen das Einkaufspotenzial.".replace(",", "'"))
    if kapital > 0:
        for j in einkauf:
            if j >= ende - 3:
                warn.append(f"{person['name']}: Einkauf {j} liegt in den 3 Jahren vor dem Kapitalbezug – "
                            "der Steuerabzug kann rückgängig gemacht werden (Sperrfrist).")
    return PkErgebnis(person["name"], verlauf, round(guthaben), round(kapital), round(rente), summe_einkauf, warn)


# ---------------------------------------------------------------- Säule 3a

@dataclass
class DreiAErgebnis:
    name: str
    verlauf: list[tuple[int, float]]
    kapital: float
    beitrag: float
    hinweise: list[str] = field(default_factory=list)


def saeule3a(person: dict, k: dict, jetzt: int | None = None) -> DreiAErgebnis:
    kz = k["kennzahlen"]
    cfg = person["saeule3a"]
    jetzt = jetzt or date.today().year
    ende = pensionsjahr(person)
    g = float(cfg.get("guthaben", 0))
    r = float(cfg.get("rendite", 0)) / 100
    beitrag = float(cfg.get("beitrag_jahr", 0))
    verlauf = [(jetzt, round(g))]
    for jahr in range(jetzt, ende):
        g = g * (1 + r) + beitrag
        verlauf.append((jahr + 1, round(g)))
    hinw = []
    if beitrag < kz["saeule3a_max"] and float(person.get("lohn_brutto", 0)) > 0:
        hinw.append(f"{person['name']}: 3a-Maximum ({kz['saeule3a_max']:,.0f}) nicht ausgeschöpft – "
                    "seit 2026 können Lücken ab 2025 nachträglich eingezahlt werden.".replace(",", "'"))
    if beitrag > kz["saeule3a_max"]:
        hinw.append(f"{person['name']}: 3a-Beitrag über dem Maximum mit Pensionskasse.")
    return DreiAErgebnis(person["name"], verlauf, round(g), beitrag, hinw)


# ---------------------------------------------------------------- Pensionslücke

def annuitaet(kapital: float, jahre: int, rendite: float) -> float:
    """Jährlicher Betrag, mit dem ein Kapital über n Jahre aufgebraucht wird."""
    if kapital <= 0 or jahre <= 0:
        return 0.0
    r = rendite / 100
    if r == 0:
        return kapital / jahre
    return kapital * r / (1 - (1 + r) ** -jahre)


@dataclass
class Luecke:
    jahr: int
    ahv: float
    pk_rente: float
    kapitalverzehr: float
    kapital_netto: float
    kapitalsteuer: float
    einkommen: float
    bedarf: float
    luecke: float
    ersatzquote: float
    lohn_heute: float


def pensionsluecke(k: dict, vermoegen_frei: float = 0.0, jetzt: int | None = None) -> Luecke:
    from steuern import kapitalbezug_varianten  # vermeidet Zirkelimport

    ahv_e = ahv(k, jetzt)
    pks = [pk(p, k) for p in k["personen"]]
    drei = [saeule3a(p, k, jetzt) for p in k["personen"]]
    hh = k["haushalt"]
    jahr = max(pensionsjahr(p) for p in k["personen"])
    kap = kapitalbezug_varianten(k, pks, drei)
    steuer = kap["gestaffelt"]["steuer_total"]
    brutto = sum(x.kapital for x in drei) + sum(x.kapital for x in pks)
    netto = brutto - steuer + max(0.0, vermoegen_frei)
    verzehr = annuitaet(netto, int(hh.get("entnahme_jahre", 25)), float(hh.get("entnahme_rendite", 0)))
    a = sum(r.rente_jahr for r in ahv_e)
    p = sum(x.rente_jahr for x in pks)
    einkommen = a + p + verzehr
    bedarf = float(hh.get("bedarf_ruhestand", 0))
    lohn = sum(float(x.get("lohn_brutto", 0)) for x in k["personen"])
    return Luecke(jahr, round(a), round(p), round(verzehr), round(netto), round(steuer), round(einkommen),
                  round(bedarf), round(max(0.0, bedarf - einkommen)),
                  round(einkommen / lohn * 100, 1) if lohn else 0.0, round(lohn))
