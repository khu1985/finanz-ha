"""Frühpensionierung: Pensionierungsalter 58 bis 65 für den ganzen Haushalt vergleichen.

Annahmen (heutige Franken; nominale Prognosen mit der Teuerung abgezinst, Verzehr mit realer Rendite):
- Pensionskasse: Altersleistung frühestens ab 58; Guthaben bis zum Rücktritt (bei einer Prognose der Kasse anteilig
  gekürzt), Umwandlungssatz pro Jahr vor 65 um `pk_kuerzung_uws` Prozentpunkte tiefer.
- AHV: Vorbezug höchstens 2 Jahre (ab 63, −6,8 % pro Jahr); wer früher aufhört, bezieht die AHV ab 63.
  Bis 65 zahlen Nichterwerbstätige AHV-Beiträge auf Vermögen und Renteneinkommen (vereinfacht).
- Überbrückung bis zur AHV: Bedarf minus PK-Renten, aus dem Kapital bezahlt.
- Sparen endet mit dem Rücktritt; das restliche Kapital (3a, PK-Kapital, freies Vermögen, nach Steuer und Überbrückung)
  wird über die Ruhestandsjahre verzehrt.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date

import steuern as st
import vorsorge as vs


@dataclass
class Variante:
    alter: int
    jahr: int                    # Jahr, in dem der Haushalt in Pension geht (spätere Person)
    ahv_ab: int                  # Alter AHV-Bezug
    ueberbrueckung_jahre: float
    ueberbrueckung: float        # Kosten bis zur AHV (Bedarf − PK-Renten + AHV-Beiträge)
    ahv_beitraege: float
    ahv: float
    pk_rente: float
    pk_kapital: float
    kapital_netto: float         # bei Rücktritt nach Steuer, inkl. freiem Vermögen und Sparen
    kapital_rest: float          # nach Überbrückung
    verzehr: float
    einkommen: float
    bedarf: float
    luecke: float
    hinweise: list = field(default_factory=list)


def ahv_ne_beitrag(vermoegen: float, renteneinkommen: float, kz: dict) -> float:
    """AHV/IV/EO-Beitrag Nichterwerbstätige pro Jahr (vereinfacht linear zwischen Minimum und Maximum)."""
    basis = max(0.0, vermoegen) + 20 * max(0.0, renteneinkommen)
    mn, mx = float(kz.get("ahv_ne_min", 530)), float(kz.get("ahv_ne_max", 26500))
    grenze_max = float(kz.get("ahv_ne_vermoegen_max", 8_950_000))
    grenze_min = float(kz.get("ahv_ne_vermoegen_min", 350_000))
    if basis <= grenze_min:
        return mn
    return round(min(mx, mn + (mx - mn) * (basis - grenze_min) / (grenze_max - grenze_min)))


def _pk_angepasst(p: dict, k: dict, alter: int) -> dict:
    """PK-Konfiguration für einen Rücktritt mit `alter`: Prognose der Kasse anteilig, Umwandlungssatz gekürzt."""
    q = copy.deepcopy(p)
    q["pensionierung_alter"] = alter
    cfg = q["pk"]
    kuerzung = float((k.get("fruehpension") or {}).get("pk_kuerzung_uws", 0.2)) / 100
    ausweis = float(cfg.get("ausweis_alterskapital") or 0)
    rente = float(cfg.get("ausweis_altersrente") or 0)
    uws65 = (rente / ausweis) if ausweis and rente else float(cfg.get("umwandlungssatz", 6.8)) / 100
    if ausweis and alter < 65:
        eigen = copy.deepcopy(p)
        eigen["pk"]["ausweis_alterskapital"] = 0
        eigen["pk"]["einkauf_geplant"] = []
        a = copy.deepcopy(eigen)
        a["pensionierung_alter"] = alter
        b = copy.deepcopy(eigen)
        b["pensionierung_alter"] = 65
        ga, gb = vs.pk(a, k).guthaben_pensionierung, vs.pk(b, k).guthaben_pensionierung
        ausweis = ausweis * (ga / gb if gb else 1.0)
        cfg["ausweis_alterskapital"] = round(ausweis)
    uws = max(0.03, uws65 - kuerzung * max(0, 65 - alter))
    if ausweis:
        cfg["ausweis_altersrente"] = round(ausweis * uws)
    else:
        cfg["umwandlungssatz"] = round(uws * 100, 3)
    return q


def variante(k: dict, alter: int, vermoegen_frei: float, heute: date | None = None) -> Variante:
    heute = heute or date.today()
    kz = k["kennzahlen"]
    hh = k["haushalt"]
    personen = [_pk_angepasst(p, k, alter) for p in k["personen"]]
    k2 = copy.deepcopy(k)
    k2["personen"] = personen
    # AHV: frühestens mit 63
    ahv_ab = max(alter, 63)
    k_ahv = copy.deepcopy(k2)
    for p in k_ahv["personen"]:
        p["pensionierung_alter"] = ahv_ab
    ahv = sum(r.rente_jahr for r in vs.ahv(k_ahv, heute.year))
    pks = [vs.pk(p, k2) for p in personen]
    drei = [vs.saeule3a(p, k2, heute.year) for p in personen]
    jahr = max(vs.pensionsjahr(p) for p in personen)
    kk = vs.kaufkraft(k, jahr - heute.year)          # nominal → heutige Franken
    ahv = ahv * vs.ahv_real_faktor(k, jahr - heute.year)
    pk_rente = sum(x.rente_jahr for x in pks) * kk
    pk_kapital = sum(x.kapital for x in pks) * kk
    steuer = st.kapitalbezug_varianten(k2, pks, drei)["gestaffelt"]["steuer_total"] * kk
    sparen = sum(float(p.get("sparen_monat", 0) or 0) * 12 * max(0, vs.pensionsjahr(p) - heute.year) for p in personen)
    netto = sum(d.kapital for d in drei) * kk + pk_kapital - steuer + max(0.0, vermoegen_frei) + sparen
    bedarf = float(hh.get("bedarf_ruhestand", 0))
    jahre_ueber = max(0, ahv_ab - alter)
    renteneinkommen = pk_rente
    ahv_b = sum(ahv_ne_beitrag(netto / max(1, len(personen)), renteneinkommen / max(1, len(personen)), kz)
                for _ in personen) * max(0, 65 - alter)
    ueber = max(0.0, bedarf - pk_rente) * jahre_ueber + ahv_b
    rest = max(0.0, netto - ueber)
    # Lebenserwartung fix: wer die AHV früher bezieht, verzehrt das Kapital über entsprechend mehr Jahre
    jahre_verzehr = int(hh.get("entnahme_jahre", 25)) + max(0, 65 - ahv_ab)
    verzehr = vs.annuitaet(rest, jahre_verzehr, float(hh.get("entnahme_rendite", 0)) - vs.teuerung(k))
    import zuzug as zz
    ausland = sum(zz.rente_ausland(p) for p in k["personen"])     # ab AHV-Alter angenommen
    einkommen = ahv + pk_rente + verzehr + ausland
    hinw = []
    if netto < ueber:
        hinw.append(f"Mit {alter} reicht das Kapital nicht für die Überbrückung bis zur AHV.")
    if alter < 58:
        hinw.append("Die meisten Pensionskassen erlauben den Altersrücktritt frühestens mit 58.")
    return Variante(alter, jahr, ahv_ab, jahre_ueber, round(ueber), round(ahv_b), round(ahv), round(pk_rente), round(pk_kapital),
                    round(netto), round(rest), round(verzehr), round(einkommen), round(bedarf),
                    round(max(0.0, bedarf - einkommen)), hinw)


def vergleich(k: dict, vermoegen_frei: float, von: int = 58, bis: int = 65, heute: date | None = None) -> list[Variante]:
    return [variante(k, a, vermoegen_frei, heute) for a in range(von, bis + 1)]


def fruehestes_ohne_luecke(varianten: list[Variante]) -> int | None:
    return next((v.alter for v in varianten if v.luecke <= 0), None)
