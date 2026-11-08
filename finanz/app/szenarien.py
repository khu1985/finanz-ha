"""Szenarien: optimale PK-Einkäufe und Vergleich verheiratet ↔ Konkubinat."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date

import steuern as st
import versicherungen as vi
import vorsorge as vs


# ---------------------------------------------------------------- PK-Einkauf optimieren

@dataclass
class EinkaufPlan:
    person: str
    potenzial: float
    budget: float
    jahre: list[int]
    gesperrt: list[int]
    plan: dict[int, float]                  # Jahr → Einkauf
    ersparnis: dict[int, float]             # Jahr → Steuerersparnis
    grenz_letzter: dict[int, float]         # Jahr → Ersparnis-Satz des letzten Schritts (%)
    kurve: list[tuple[float, float]]        # (Einkauf in einem Jahr, Grenz-Ersparnis %) für die Grafik
    kapitalsteuer_mehr: float
    zins_ertrag: float
    total_ersparnis: float
    netto: float
    einjahr_ersparnis: float                # alles im ersten Jahr zum Vergleich
    hinweise: list[str] = field(default_factory=list)


def _ersparnis(k: dict, person: str, betrag: float) -> float:
    return st.ersparnis_abzug(k, betrag, person)["total"] if betrag > 0 else 0.0


def einkauf_optimieren(k: dict, person_name: str, budget: float, von: int, bis: int, schwelle: float = 0.0,
                       schritt: float = 5000, heute: date | None = None) -> EinkaufPlan:
    """Verteilt Einkäufe in Schritten auf die Jahre mit der jeweils höchsten Grenz-Ersparnis (gleiches Einkommen
    jedes Jahr angenommen). Schritte unter der Mindest-Ersparnis `schwelle` (%) werden nicht mehr eingekauft.
    Jahre in den 3 Jahren vor einem geplanten Kapitalbezug sind gesperrt."""
    heute = heute or date.today()
    p = next(x for x in k["personen"] if x["name"] == person_name)
    cfg = p["pk"]
    bereits = sum(float(e["betrag"]) for e in cfg.get("einkauf_geplant") or [])
    potenzial = max(0.0, float(cfg.get("einkauf_potenzial", 0) or 0) - bereits)
    pj = vs.pensionsjahr(p)
    kapitalbezug = float(cfg.get("kapitalbezug_anteil", 0) or 0) > 0
    jahre_alle = list(range(max(von, heute.year), min(bis, pj - 1) + 1))
    gesperrt = [j for j in jahre_alle if kapitalbezug and j >= pj - 3]
    jahre = [j for j in jahre_alle if j not in gesperrt]
    rest = min(potenzial, budget if budget > 0 else potenzial)
    plan = {j: 0.0 for j in jahre}
    letzter = {j: 0.0 for j in jahre}
    hinweise = []
    if not jahre:
        hinweise.append("Kein Jahr verfügbar – Zeitraum prüfen (Einkäufe in den 3 Jahren vor einem Kapitalbezug sind gesperrt).")
    while rest > 1 and jahre:
        betrag = min(schritt, rest)
        bestes, bester_satz = None, -1.0
        for j in jahre:
            satz = (_ersparnis(k, person_name, plan[j] + betrag) - _ersparnis(k, person_name, plan[j])) / betrag * 100
            if satz > bester_satz + 1e-9:
                bestes, bester_satz = j, satz
        if bester_satz < schwelle:
            hinweise.append(f"Weitere Einkäufe würden weniger als {schwelle:.0f} % Steuern sparen – Rest nicht eingeplant.")
            break
        plan[bestes] += betrag
        letzter[bestes] = bester_satz
        rest -= betrag
    plan = {j: b for j, b in plan.items() if b > 0}
    ersparnis = {j: round(_ersparnis(k, person_name, b)) for j, b in plan.items()}
    total = sum(ersparnis.values())
    einjahr = round(_ersparnis(k, person_name, sum(plan.values()))) if plan else 0
    # Grenz-Ersparnis-Kurve für ein Jahr
    kurve, b = [], 0.0
    obergrenze = max(potenzial, schritt)
    while b < obergrenze and len(kurve) < 60:
        n = min(schritt, obergrenze - b)
        kurve.append((b + n, (_ersparnis(k, person_name, b + n) - _ersparnis(k, person_name, b)) / n * 100))
        b += n
    # Folgen: Zins bis zur Pensionierung und Mehrsteuer beim Kapitalbezug
    zins = float(cfg.get("zins", k["kennzahlen"]["bvg_mindestzins"])) / 100
    wert_65 = sum(betrag * (1 + zins) ** max(0, pj - j - 1) for j, betrag in plan.items())
    zins_ertrag = wert_65 - sum(plan.values())
    anteil = min(100.0, float(cfg.get("kapitalbezug_anteil", 0) or 0)) / 100
    mehr_kap = 0.0
    if anteil > 0 and wert_65 > 0:
        pk = vs.pk(p, k)
        basis = pk.kapital
        einheit = st.einheit_von(k, person_name)
        mehr_kap = st.kapitalsteuer(basis + wert_65 * anteil, k, einheit)["total"] - st.kapitalsteuer(basis, k, einheit)["total"]
        hinweise.append(f"Kapitalbezug {anteil * 100:.0f} %: Der eingekaufte Betrag wird beim Bezug mit rund CHF "
                        f"{mehr_kap:,.0f} besteuert (bereits abgezogen).".replace(",", "'"))
    elif wert_65:
        hinweise.append("Bezug als Rente: Der Einkauf erhöht die Altersrente (Umwandlungssatz), die als Einkommen besteuert wird.")
    if bereits:
        hinweise.append(f"Bereits geplante Einkäufe von CHF {bereits:,.0f} sind vom Potenzial abgezogen.".replace(",", "'"))
    if k["wohnen"].get("aktiv"):
        hinweise.append("Nach einem Einkauf ist 3 Jahre lang kein Vorbezug für Wohneigentum (WEF) möglich. "
                        "Die Amortisation aus freiem Vermögen ist davon nicht betroffen.")
    netto = total + zins_ertrag - mehr_kap
    return EinkaufPlan(person_name, potenzial, budget, jahre, gesperrt, plan, ersparnis, letzter, kurve,
                       round(mehr_kap), round(zins_ertrag), total, round(netto), einjahr, hinweise)


def plan_uebernehmen(k: dict, plan: EinkaufPlan) -> None:
    p = next(x for x in k["personen"] if x["name"] == plan.person)
    liste = list(p["pk"].get("einkauf_geplant") or [])
    for j, b in sorted(plan.plan.items()):
        liste.append({"jahr": int(j), "betrag": int(round(b))})
    p["pk"]["einkauf_geplant"] = liste


# ---------------------------------------------------------------- Verheiratet ↔ Konkubinat

@dataclass
class HeiratVergleich:
    moeglich: bool
    grund: str = ""
    steuer_konkubinat: float = 0
    steuer_verheiratet: float = 0
    steuer_details: list = field(default_factory=list)
    ahv_konkubinat: float = 0
    ahv_verheiratet: float = 0
    kapital_konkubinat: float = 0
    kapital_verheiratet: float = 0
    hinterbliebene: list = field(default_factory=list)   # (Person, Rente Konkubinat, Rente verheiratet)
    qualitativ: list = field(default_factory=list)
    jahre_ruhestand: int = 25
    verheiratet_details: dict = field(default_factory=dict)

    @property
    def steuer_diff(self) -> float:          # positiv = Heirat kostet mehr Steuern pro Jahr
        return self.steuer_verheiratet - self.steuer_konkubinat

    @property
    def ahv_diff(self) -> float:             # negativ = Heirat senkt die AHV pro Jahr
        return self.ahv_verheiratet - self.ahv_konkubinat

    @property
    def kapital_diff(self) -> float:         # positiv = Heirat kostet mehr Kapitalbezugssteuer (einmalig)
        return self.kapital_verheiratet - self.kapital_konkubinat


def _verheiratet_kopie(k: dict) -> dict:
    v = copy.deepcopy(k)
    v["haushalt"]["zivilstand"] = "verheiratet"
    return v


def _konkubinat_kopie(k: dict) -> dict:
    v = copy.deepcopy(k)
    v["haushalt"]["zivilstand"] = "ledig"
    return v


def steuer_verheiratet(k: dict) -> dict:
    """Gemeinsame Besteuerung aus den Einzelwerten unter steuern.personen schätzen."""
    kz = k["kennzahlen"]
    einheiten = st.einheiten(_konkubinat_kopie(k))
    bund_einzel = [float(e.st["steuerbar_bund"]) for e in einheiten]
    kanton_einzel = [float(e.st["steuerbar_kanton"]) for e in einheiten]
    loehne = sorted(float(p.get("lohn_brutto", 0)) for p in k["personen"][:2])
    zweiverdiener = 0.0
    if len(loehne) == 2 and loehne[0] > 0:
        zweiverdiener = min(kz["bund_zweiverdiener_max"], max(kz["bund_zweiverdiener_min"], loehne[0] * kz["bund_zweiverdiener_satz"] / 100))
        zweiverdiener = min(zweiverdiener, loehne[0])
    # Bund: Einkommen addiert, Verheiratetenabzug und Zweiverdienerabzug; Versicherungsabzug Ehe statt 2 × Einzel
    vers = kz["bund_versicherungsabzug_ehe"] - 2 * kz["bund_versicherungsabzug_einzel"]
    bund_e = sum(bund_einzel) - kz["bund_verheiratetenabzug"] - zweiverdiener - vers
    kinder = st.anzahl_kinder(k)
    bund = st.bundessteuer(bund_e, True, kinder, kz)
    # Kanton: Einkommen addiert, Splitting (Divisor) auf dem Mittel der beiden Steuerkurven
    divisor = float(k["steuern"].get("ehe_splitting_divisor", 2.0) or 2.0)
    kanton_e = sum(kanton_einzel) - float(k["steuern"].get("ehe_abzug_kanton", 0) or 0)
    kurven = [st.kantonssteuer(kanton_e / divisor, e.st) for e in einheiten]
    kanton = divisor * sum(kurven) / len(kurven) if kurven else 0.0
    return {"bund": round(bund), "kanton": round(kanton), "total": round(bund + kanton),
            "bund_einkommen": round(bund_e), "kanton_einkommen": round(kanton_e), "zweiverdiener": round(zweiverdiener),
            "divisor": divisor}


def heirat_vergleich(k: dict, db, heute: date | None = None) -> HeiratVergleich:
    heute = heute or date.today()
    if len(k["personen"]) < 2:
        return HeiratVergleich(False, "Der Vergleich braucht zwei Personen.")
    konk = _konkubinat_kopie(k)
    if len(st.einheiten(konk)) < 2:
        return HeiratVergleich(False, "Für den Vergleich je Person eine Steuererklärung unter «steuern.personen» erfassen "
                                      "(steuerbares Einkommen Bund und Kanton, Steuerbetrag, Grenzsteuersatz).")
    verh = _verheiratet_kopie(k)
    s_konk = st.steuern_heute(konk)
    s_verh = steuer_verheiratet(k)
    details = [(e["name"], e["bund"], e["kanton"], e["total"]) for e in s_konk["einheiten"]]
    # AHV
    ahv_k = sum(r.rente_jahr for r in vs.ahv(konk, heute.year))
    ahv_v = sum(r.rente_jahr for r in vs.ahv(verh, heute.year))
    # Kapitalbezug (gestaffelt)
    def kap(kk):
        pks = [vs.pk(p, kk) for p in kk["personen"]]
        drei = [vs.saeule3a(p, kk, heute.year) for p in kk["personen"]]
        return st.kapitalbezug_varianten(kk, pks, drei)["gestaffelt"]["steuer_total"]
    # Verheiratet: Kapitalbezüge als eine Steuereinheit
    verh_kap = copy.deepcopy(verh)
    verh_kap["steuern"]["personen"] = []
    kap_k, kap_v = kap(konk), kap(verh_kap)
    # Hinterbliebene
    rk = vi.risiko(konk, vs.ahv(konk, heute.year))
    verh_r = copy.deepcopy(verh)
    rv = vi.risiko(verh_r, vs.ahv(verh_r, heute.year))
    hinter = [(a.name, a.tod_renten, b.tod_renten) for a, b in zip(rk, rv)]
    jahre = int(k["haushalt"].get("entnahme_jahre", 25))
    qual = [
        "Erbrecht: Ehegatten sind gesetzliche Erben mit Pflichtteil; Konkubinatspartner erben nur per Testament oder "
        "Erbvertrag (verfügbare Quote) und zahlen je nach Kanton Erbschaftssteuer – Ehegatten sind überall befreit.",
        "Pensionskasse: Ehegattenrente gilt automatisch; die Lebenspartnerrente nur bei Meldung und erfüllten Bedingungen.",
        "AHV: Bei Heirat Einkommenssplitting für die Ehejahre und Plafonierung der beiden Renten auf 150 % der Maximalrente; "
        "dafür Witwen-/Witwerrente und Verwitwetenzuschlag.",
        "Vermögen: ohne Ehevertrag Errungenschaftsbeteiligung; Wohneigentum, Hypothek und Pfandrechte bleiben wie im Grundbuch.",
        "Steuern: Verheiratete werden gemeinsam veranlagt; Kapitalbezüge im gleichen Jahr werden zusammengerechnet.",
    ]
    return HeiratVergleich(True, "", s_konk["total"], s_verh["total"], details, ahv_k, ahv_v, kap_k, kap_v, hinter,
                           qual, jahre, s_verh)
