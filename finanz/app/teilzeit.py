"""Teilzeit und Kinderbetreuung: was eine Pensumsreduktion kurz- und langfristig kostet.

Pro Jahr der Reduktion (heutige Franken, gleiches Einkommen jedes Jahr):
- Lohn: Bruttolohn × (Pensum alt − neu) / Pensum alt; netto nach Sozialabzügen (`kennzahlen.sozialabzug`, AHV/IV/EO/ALV)
  und dem Arbeitnehmeranteil an den PK-Sparbeiträgen.
- PK-Sparbeiträge: mit Sparbeitrag laut Ausweis proportional zum Pensum (Kassen mit Koordinationsabzug nach Pensum);
  ohne Angabe BVG-Minimum – der volle Koordinationsabzug trifft Teilzeit überproportional, unter der Eintrittsschwelle
  entfällt die PK ganz.
- Steuern: das steuerbare Einkommen sinkt um den Nettolohn, steigt aber um den wegfallenden Betreuungsabzug.
- Betreuung: eingesparte Kita-Kosten (Standard: Betreuungskosten der Kinder × Anteil der Reduktion).
Langfristig: AHV über ein tieferes Durchschnittseinkommen (Plafond und Splitting berücksichtigt), PK-Kapital und -Rente
über die fehlenden Sparbeiträge mit Zins, Risikoleistungen proportional zum Lohn.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date

import kinder as ki
import steuern as st
import vorsorge as vs

ARBEITSTAGE = 220


@dataclass
class Jahr:
    jahr: int
    brutto: float               # weniger Bruttolohn
    netto: float                # weniger Nettolohn (nach Sozialabzügen und PK)
    steuern: float              # weniger Steuern
    betreuung: float            # weniger Betreuungskosten
    saldo: float                # Veränderung im Portemonnaie (negativ = weniger)


@dataclass
class Ergebnis:
    person: str
    pensum_alt: float
    pensum_neu: float
    von: int
    bis: int
    jahre: list[Jahr]
    netto_total: float
    steuern_total: float
    betreuung_total: float
    saldo_total: float
    pro_tag: float              # was ein zusätzlicher Arbeitstag netto bringt (nach Steuern und Kita)
    ahv_rente_weniger: float    # pro Jahr im Ruhestand
    pk_kapital_weniger: float
    pk_rente_weniger: float     # pro Jahr, falls als Rente bezogen
    ruhestand_total: float      # AHV und PK über die Entnahmejahre
    risiko_iv_weniger: float    # IV-Rente PK pro Jahr während der Teilzeit (proportional)
    hinweise: list[str] = field(default_factory=list)


def _zahl(v, std=0.0) -> float:
    try:
        return float(str(v).replace("'", "").replace(",", ".")) if str(v).strip() else std
    except ValueError:
        return std


def _sparbeitrag(p: dict, lohn: float, alter: int, kz: dict) -> float:
    sb = _zahl(p["pk"].get("sparbeitrag_jahr"))
    if sb > 0:
        return sb * lohn / max(1.0, _zahl(p.get("lohn_brutto")))
    return vs.bvg_koordinierter_lohn(lohn, kz) * vs.bvg_gutschriftsatz(alter, kz) / 100


def betreuung_standard(k: dict, jahr: int, anteil: float) -> float:
    return round(sum(ki.betreuung_jahr(c, jahr) for c in ki.liste(k)) * anteil)


def rechnen(k: dict, person: str, pensum_neu: float, von: int, bis: int, betreuung: float | None = None,
            heute: date | None = None) -> Ergebnis:
    heute = heute or date.today()
    kz = k["kennzahlen"]
    p = next(x for x in k["personen"] if x["name"] == person)
    alt = _zahl(p.get("pensum"), 100) or 100
    neu = max(0.0, min(alt, pensum_neu))
    anteil = (alt - neu) / alt
    lohn = _zahl(p.get("lohn_brutto"))
    lohn_neu = lohn * neu / alt
    sozial = _zahl(kz.get("sozialabzug"), 6.4) / 100
    gj = vs.geburtsjahr(p)
    pj = vs.pensionsjahr(p)
    bis = min(bis, pj - 1)
    bet_max = _zahl(kz.get("bund_betreuung_max"), 25800)
    jahre = []
    pk_weniger = 0.0
    zins = _zahl(p["pk"].get("zins"), kz["bvg_mindestzins"]) / 100
    for j in range(max(von, heute.year), bis + 1):
        alter = j - gj
        d_brutto = lohn - lohn_neu
        d_pk = _sparbeitrag(p, lohn, alter, kz) - _sparbeitrag(p, lohn_neu, alter, kz)
        d_netto = d_brutto * (1 - sozial) - d_pk / 2
        bet = betreuung if betreuung is not None else betreuung_standard(k, j, anteil)
        # wegfallender Betreuungsabzug (nur Kinder unter dem Abzugsalter, höchstens Maximum)
        abzugsfaehig = sum(min(bet_max, ki.betreuung_jahr(c, j)) for c in ki.liste(k)
                           if ki.alter(c, j) < _zahl(kz.get("bund_betreuung_alter"), 14))
        d_abzug = min(bet, abzugsfaehig)
        d_steuer = st.ersparnis_abzug(k, d_netto - d_abzug, person)["total"]
        jahre.append(Jahr(j, round(d_brutto), round(d_netto), round(d_steuer), round(bet),
                          round(-d_netto + d_steuer + bet)))
        pk_weniger += d_pk * (1 + zins) ** max(0, pj - j - 1)
    n = len(jahre)
    netto_t = sum(x.netto for x in jahre)
    steuer_t = sum(x.steuern for x in jahre)
    bet_t = sum(x.betreuung for x in jahre)
    saldo_t = sum(x.saldo for x in jahre)
    tage = ARBEITSTAGE * (alt - neu) / 100 * n
    pro_tag = (netto_t - steuer_t - bet_t) / tage if tage else 0.0
    # AHV: tieferes Durchschnittseinkommen über die Beitragsjahre
    ahv_vorher = {r.name: r.rente_jahr for r in vs.ahv(k, heute.year)}
    k2 = copy.deepcopy(k)
    p2 = next(x for x in k2["personen"] if x["name"] == person)
    e = _zahl(p2["ahv"].get("einkommen_durchschnitt")) or lohn
    beitragsjahre = max(1, vs.ahv_beitragsjahre(p2, heute.year, kz))
    p2["ahv"]["einkommen_durchschnitt"] = max(0.0, e - (lohn - lohn_neu) * n / beitragsjahre)
    ahv_nachher = {r.name: r.rente_jahr for r in vs.ahv(k2, heute.year)}
    ahv_weniger = sum(ahv_vorher.values()) - sum(ahv_nachher.values())          # Haushalt (Plafond, Splitting)
    uws = _zahl(p["pk"].get("umwandlungssatz"), kz["bvg_umwandlungssatz"]) / 100
    ausweis_k, ausweis_r = _zahl(p["pk"].get("ausweis_alterskapital")), _zahl(p["pk"].get("ausweis_altersrente"))
    if ausweis_k and ausweis_r:
        uws = ausweis_r / ausweis_k
    pk_rente = pk_weniger * uws
    entnahme = int(_zahl(k["haushalt"].get("entnahme_jahre"), 25))
    ruhestand = (ahv_weniger + pk_rente) * entnahme
    iv = _zahl((p.get("risiko") or {}).get("iv_rente_pk")) * anteil
    hinw = []
    verheiratet = k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet"
    if lohn >= kz["bvg_eintrittsschwelle"] > lohn_neu:
        hinw.append(f"Mit {neu:g} % liegt der Lohn (CHF {_chf(lohn_neu)}) unter der BVG-Eintrittsschwelle von CHF "
                    f"{_chf(kz['bvg_eintrittsschwelle'])} – ohne freiwillige Lösung der Kasse entfallen PK-Sparbeiträge und "
                    "Risikoschutz ganz, und in die 3a geht nur noch 20 % des Einkommens.")
    if not _zahl(p["pk"].get("sparbeitrag_jahr")) and lohn_neu >= kz["bvg_eintrittsschwelle"]:
        hinw.append("Gerechnet mit dem BVG-Minimum: der volle Koordinationsabzug trifft Teilzeit überproportional. Viele "
                    "Kassen kürzen ihn nach Pensum – Reglement prüfen und den Sparbeitrag laut Ausweis eintragen.")
    if verheiratet:
        hinw.append("Verheiratet: Die AHV-Einkommen werden in der Ehe geteilt (Splitting), und der Plafond von 150 % "
                    "dämpft den Verlust oft. Das PK-Guthaben wird bei einer Scheidung geteilt.")
    else:
        hinw.append(f"Konkubinat: Kein AHV-Splitting und kein Ausgleich der PK bei einer Trennung – der Verlust bleibt bei "
                    f"{person}. Ausgleich im Konkubinatsvertrag regeln, z. B. Einzahlungen in 3a oder PK-Einkäufe für "
                    "die Person mit dem tieferen Pensum.")
    if ki.liste(k):
        hinw.append("Kinder- und Ausbildungszulagen bleiben bei Teilzeit gleich hoch. AHV-Erziehungsgutschriften gibt es "
                    "unabhängig vom Pensum.")
    if iv:
        hinw.append(f"Risikoschutz: IV-Rente der PK sinkt während der Teilzeit um rund CHF {_chf(iv)} pro Jahr; Taggeld und "
                    "Todesfallleistungen ebenfalls – Deckung unter «Versicherungen» prüfen.")
    return Ergebnis(person, alt, neu, max(von, heute.year), bis, jahre, netto_t, steuer_t, bet_t, saldo_t, round(pro_tag),
                    round(ahv_weniger), round(pk_weniger), round(pk_rente), round(ruhestand), round(iv), hinw)


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")
