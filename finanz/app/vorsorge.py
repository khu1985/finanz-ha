"""Rechenkern Vorsorge: AHV (1. Säule), Pensionskasse (2. Säule), Säule 3a, Pensionslücke.

Vereinfachungen (siehe DOCS.md):
- Beträge in heutigen Franken, keine Teuerung.
- AHV: Rentenskala 44 als stetige Formel, Einkommenssplitting über die ganze Beitragsdauer,
  Erziehungsgutschriften hälftig, Referenzalter 65.
- PK: Altersguthaben mit jährlichem Zins und Sparbeitrag (laut Ausweis oder BVG-Minimum).
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

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
    import zuzug as zz
    bisher = int(person["ahv"].get("beitragsjahre_bisher", 0))
    moeglich = zz.ahv_moegliche_jahre(person)
    if moeglich is not None and not bisher:                     # ohne IK-Auszug: lückenlos ab Zuzug
        return max(0, min(kz["ahv_vollbeitragsjahre"], moeglich) - int(person["ahv"].get("fehlende_jahre", 0)))
    # Beiträge bis zum Referenzalter (bei Frühpensionierung als Nichterwerbstätige weiter bezahlt)
    bis = geburtsjahr(person) + 65
    zuzug_jahr = zz.datum(person).year if moeglich is not None else 0
    zukuenftig = max(0, bis - max(jetzt, zuzug_jahr))
    jahre = min(kz["ahv_vollbeitragsjahre"], bisher + zukuenftig)
    if moeglich is not None:
        jahre = min(jahre, moeglich)                            # Jahre vor dem Zuzug sind Beitragslücken
    return max(0, jahre - int(person["ahv"].get("fehlende_jahre", 0)))


def erziehungsjahre(person: dict, kinder: list[dict], k: dict | None = None) -> float:
    """Jahre mit mindestens einem Kind unter 16, ab dem 21. Altersjahr bis zum Referenzalter. Mit `k` gewichtet nach dem
    Anteil der Gutschrift (hälftig, ganz oder keine – nur eigene bzw. gemeinsame Kinder)."""
    import kinder as ki
    import zuzug as zz
    gj = geburtsjahr(person)
    z = zz.datum(person)
    ab = max(gj + 21, z.year) if z else gj + 21            # Gutschriften nur mit Wohnsitz in der Schweiz
    jahre: dict[int, float] = {}
    for kind in kinder or []:
        kj = ki.geburtsjahr(kind)
        if not kj:
            continue
        anteil = ki.gutschrift_anteil(k, kind, person["name"]) if k else 1.0
        if anteil <= 0:
            continue
        for j in range(kj + 1, kj + 17):
            if ab <= j < gj + 65:
                jahre[j] = max(jahre.get(j, 0.0), anteil)
    return sum(jahre.values())


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
        ej = erziehungsjahre(p, k["haushalt"].get("kinder", []), k)     # bereits mit Anteil gewichtet
        e_mit = e + (ej * gutschrift / jahre if jahre else 0)
        voll = ahv_vollrente_monat(e_mit, kz)
        rente = voll * jahre / kz["ahv_vollbeitragsjahre"]
        alter = int(p.get("pensionierung_alter", 65))
        if alter < 65:
            rente *= max(0.0, 1 - kz["ahv_vorbezug_kuerzung"] / 100 * (65 - alter))
        elif alter > 65:
            zuschlag = {1: 5.2, 2: 10.8, 3: 17.1, 4: 24.0, 5: 31.5}[min(alter - 65, 5)]
            rente *= 1 + zuschlag / 100
        erg.append(AhvErgebnis(p["name"], jahre, round(e_mit), round(ej, 1), voll, round(rente, 2), alter=alter))
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
    uws = float(cfg.get("umwandlungssatz", kz["bvg_umwandlungssatz"])) / 100
    ausweis_kapital = float(cfg.get("ausweis_alterskapital") or 0)
    if ausweis_kapital > 0:
        # Prognose der Kasse übernehmen; geplante Einkäufe mit Zins bis zur Pensionierung dazurechnen
        zusatz = sum(b * (1 + zins) ** max(0, ende - j - 1) for j, b in einkauf.items())
        ziel = ausweis_kapital + zusatz
        eigen_ende = guthaben
        faktor = ziel / eigen_ende if eigen_ende else 1.0
        start_wert = verlauf[0][1]
        verlauf = [(j, round(start_wert + (w - start_wert) * (ziel - start_wert) / (eigen_ende - start_wert)))
                   if eigen_ende != start_wert else (j, round(w * faktor)) for j, w in verlauf]
        guthaben = ziel
        ausweis_rente = float(cfg.get("ausweis_altersrente") or 0)
        if ausweis_rente > 0:
            uws = ausweis_rente / ausweis_kapital
    anteil = min(100.0, max(0.0, float(cfg.get("kapitalbezug_anteil", 0)))) / 100
    kapital = guthaben * anteil
    rente = (guthaben - kapital) * uws
    warn = []
    summe_einkauf = sum(einkauf.values())
    if summe_einkauf > float(cfg.get("einkauf_potenzial", 0) or 0) > 0:
        warn.append(f"{person['name']}: geplante Einkäufe ({summe_einkauf:,.0f}) übersteigen das Einkaufspotenzial." >> TS)
    import zuzug as zz
    for j, b in sorted(einkauf.items()):
        grenze = zz.einkauf_limit(person, j)
        if grenze is not None and b > grenze:
            warn.append(f"{person['name']}: Einkauf {j} von {b:,.0f} über der Grenze von {grenze:,.0f} pro Jahr in den ersten "
                        "5 Jahren nach dem Zuzug (BVV 2 Art. 60b)." >> TS)
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
                    "seit 2026 können Lücken ab 2025 nachträglich eingezahlt werden." >> TS)
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


def teuerung(k: dict) -> float:
    """Angenommene Teuerung in % pro Jahr (annahmen.teuerung)."""
    return float((k.get("annahmen") or {}).get("teuerung", 0) or 0)


def kaufkraft(k: dict, jahre: float) -> float:
    """Faktor, mit dem ein nominaler Betrag in `jahre` Jahren in heutige Franken umgerechnet wird."""
    return 1 / (1 + teuerung(k) / 100) ** max(0.0, jahre)


def ahv_real_faktor(k: dict, jahre: float) -> float:
    """AHV-Renten folgen dem Mischindex (Mittel aus Preisen und Nominallöhnen) – real wächst die Rente um die
    Hälfte des Reallohnwachstums (annahmen.lohnentwicklung)."""
    real = float((k.get("annahmen") or {}).get("lohnentwicklung", 0) or 0) / 2 / 100
    return (1 + real) ** max(0.0, jahre)


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
    teuerung: float = 0.0
    kaufkraft: float = 1.0                 # Faktor nominal → heutige Franken bei Pensionierung
    pk_rente_nominal: float = 0.0
    kapital_nominal: float = 0.0
    luecke_mittel: float = 0.0             # Durchschnitt über die Entnahmejahre (PK-Renten verlieren Kaufkraft)
    luecke_spaeter: float = 0.0            # nach `spaeter_jahre`
    einkommen_spaeter: float = 0.0
    spaeter_jahre: int = 20
    verlauf: list = field(default_factory=list)   # [(Jahr, AHV, PK, Verzehr, Ausland)] in heutigen Franken
    ausland: float = 0.0                   # Altersrenten aus dem Ausland (heutige Franken)
    kinderrenten: float = 0.0              # AHV-Kinderrenten zur Altersrente (Kinder bis 18 bzw. in Ausbildung)


def pensionsluecke(k: dict, vermoegen_frei: float = 0.0, jetzt: int | None = None) -> Luecke:
    """Alles in heutigen Franken. Nominal prognostizierte Kapitalien und PK-Renten werden mit der Teuerung bis zur
    Pensionierung abgezinst; PK-Renten sind danach meist nicht indexiert und verlieren jedes Jahr Kaufkraft, die AHV
    folgt dem Mischindex; der Kapitalverzehr rechnet mit der realen Rendite (Entnahmerendite − Teuerung)."""
    from steuern import kapitalbezug_varianten  # vermeidet Zirkelimport

    jetzt = jetzt or date.today().year
    ahv_e = ahv(k, jetzt)
    pks = [pk(p, k) for p in k["personen"]]
    drei = [saeule3a(p, k, jetzt) for p in k["personen"]]
    hh = k["haushalt"]
    jahr = max(pensionsjahr(p) for p in k["personen"])
    t = teuerung(k)
    kk = kaufkraft(k, jahr - jetzt)
    kap = kapitalbezug_varianten(k, pks, drei)
    steuer = kap["gestaffelt"]["steuer_total"]
    brutto = sum(x.kapital for x in drei) + sum(x.kapital for x in pks)
    netto_nominal = brutto - steuer
    netto = netto_nominal * kk + max(0.0, vermoegen_frei)
    jahre = int(hh.get("entnahme_jahre", 25))
    rendite_real = float(hh.get("entnahme_rendite", 0)) - t
    verzehr = annuitaet(netto, jahre, rendite_real)
    a = sum(r.rente_jahr for r in ahv_e) * ahv_real_faktor(k, jahr - jetzt)
    p_nom = sum(x.rente_jahr for x in pks)
    p = p_nom * kk
    import zuzug as zz

    def ausland_im(jahr_: int) -> float:
        return sum(zz.rente_ausland(x) for x in k["personen"] if jahr_ >= geburtsjahr(x) + zz.rente_ausland_alter(x))
    aus = ausland_im(jahr)
    import kinder as ki
    ahv_person = {r.name: r.rente_jahr * ahv_real_faktor(k, jahr - jetzt) for r in ahv_e}

    def kinderrenten_im(jahr_: int) -> float:
        """AHV-Kinderrente 40 % der Altersrente pro Kind des pensionierten Elternteils (vereinfacht, ohne Plafond)."""
        return sum(0.4 * ahv_person.get(x["name"], 0) * sum(1 for c in ki.eigene(k, x["name"]) if ki.unterhalt(c, jahr_))
                   for x in k["personen"] if jahr_ >= geburtsjahr(x) + 65)
    kr = kinderrenten_im(jahr)
    einkommen = a + p + verzehr + aus + kr
    bedarf = float(hh.get("bedarf_ruhestand", 0))
    lohn = sum(float(x.get("lohn_brutto", 0)) for x in k["personen"])
    verlauf, luecken = [], []
    for j in range(max(1, jahre)):
        p_j = p / (1 + t / 100) ** j
        aus_j = ausland_im(jahr + j)
        kr_j = kinderrenten_im(jahr + j)
        verlauf.append((jahr + j, round(a + kr_j), round(p_j), round(verzehr), round(aus_j)))
        luecken.append(max(0.0, bedarf - (a + kr_j + p_j + verzehr + aus_j)))
    spaeter = min(20, max(0, jahre - 1))
    einkommen_sp = (a + p / (1 + t / 100) ** spaeter + verzehr + ausland_im(jahr + spaeter)
                    + kinderrenten_im(jahr + spaeter))
    return Luecke(jahr, round(a), round(p), round(verzehr), round(netto), round(steuer * kk), round(einkommen),
                  round(bedarf), round(max(0.0, bedarf - einkommen)),
                  round(einkommen / lohn * 100, 1) if lohn else 0.0, round(lohn),
                  t, round(kk, 4), round(p_nom), round(netto_nominal),
                  round(sum(luecken) / len(luecken)) if luecken else 0, round(max(0.0, bedarf - einkommen_sp)),
                  round(einkommen_sp), spaeter, verlauf, round(aus), round(kr))
