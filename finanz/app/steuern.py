"""Rechenkern Steuern.

- Direkte Bundessteuer exakt nach Tarif (aus kennzahlen), inkl. Elterntarif und Höchstsatz.
- Staats- und Gemeindesteuer als lineare Näherung um die letzte Veranlagung:
  Steuer(x) = Steuer_ref + Grenzsteuersatz × (x − Einkommen_ref).
- Kapitalleistungen: Bund 1/5 des Tarifs (DBG Art. 38), Kanton mit effektivem Satz aus Tabelle.
"""
from __future__ import annotations

from vorsorge import geburtsjahr, pensionsjahr


def _verheiratet(k: dict) -> bool:
    return k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet"


def tarif_progressiv(einkommen: float, stufen: list) -> float:
    steuer = 0.0
    stufen = sorted((float(a), float(s)) for a, s in stufen)
    for i, (ab, satz) in enumerate(stufen):
        bis = stufen[i + 1][0] if i + 1 < len(stufen) else float("inf")
        if einkommen <= ab:
            break
        steuer += (min(einkommen, bis) - ab) * satz / 100
    return steuer


def bundessteuer(einkommen: float, verheiratet: bool, kinder: int, kz: dict) -> float:
    einkommen = max(0.0, float(einkommen) // 100 * 100)  # auf 100 Franken abgerundet
    stufen = kz["bund_tarif_verheiratet"] if verheiratet else kz["bund_tarif_ledig"]
    steuer = min(tarif_progressiv(einkommen, stufen), einkommen * kz["bund_hoechstsatz"] / 100)
    if verheiratet or kinder:
        steuer -= kinder * kz["bund_elterntarif_kind"]
    steuer = max(0.0, steuer)
    return 0.0 if steuer < 25 else round(steuer, 2)


def kantonssteuer(einkommen: float, st: dict) -> float:
    ref_e = float(st.get("steuerbar_kanton", 0))
    ref_s = float(st.get("steuer_kanton_gemeinde", 0))
    g = float(st.get("grenzsteuersatz_kanton", 0)) / 100
    return round(max(0.0, ref_s + g * (einkommen - ref_e)), 2)


def anzahl_kinder(k: dict) -> int:
    return len(k["haushalt"].get("kinder") or [])


def steuern_heute(k: dict) -> dict:
    kz, st = k["kennzahlen"], k["steuern"]
    bund = bundessteuer(st["steuerbar_bund"], _verheiratet(k), anzahl_kinder(k), kz)
    kanton = kantonssteuer(st["steuerbar_kanton"], st)
    total = bund + kanton
    grenz_bund = (bundessteuer(st["steuerbar_bund"] + 1000, _verheiratet(k), anzahl_kinder(k), kz) - bund) / 10
    return {
        "bund": round(bund), "kanton": round(kanton), "total": round(total),
        "grenz_bund": round(grenz_bund, 1),
        "grenz_total": round(grenz_bund + float(st.get("grenzsteuersatz_kanton", 0)), 1),
        "effektiv": round(total / st["steuerbar_kanton"] * 100, 1) if st["steuerbar_kanton"] else 0.0,
    }


def ersparnis_abzug(k: dict, abzug: float) -> dict:
    """Steuerersparnis, wenn das steuerbare Einkommen (Bund und Kanton) um `abzug` sinkt."""
    kz, st = k["kennzahlen"], k["steuern"]
    v, n = _verheiratet(k), anzahl_kinder(k)
    b0 = bundessteuer(st["steuerbar_bund"], v, n, kz)
    b1 = bundessteuer(st["steuerbar_bund"] - abzug, v, n, kz)
    k0 = kantonssteuer(st["steuerbar_kanton"], st)
    k1 = kantonssteuer(st["steuerbar_kanton"] - abzug, st)
    return {"bund": round(b0 - b1), "kanton": round(k0 - k1), "total": round(b0 - b1 + k0 - k1)}


def effektiver_satz_kanton(betrag: float, tabelle: list) -> float:
    punkte = sorted((float(a), float(s)) for a, s in tabelle)
    if not punkte:
        return 0.0
    if betrag <= punkte[0][0]:
        return punkte[0][1]
    for (a0, s0), (a1, s1) in zip(punkte, punkte[1:]):
        if betrag <= a1:
            return s0 + (s1 - s0) * (betrag - a0) / (a1 - a0)
    return punkte[-1][1]


def kapitalsteuer(betrag: float, k: dict) -> dict:
    """Steuer auf Kapitalleistungen eines Jahres (Ehepaare: Summe beider)."""
    kz, st = k["kennzahlen"], k["steuern"]
    if betrag <= 0:
        return {"bund": 0, "kanton": 0, "total": 0}
    stufen = kz["bund_tarif_verheiratet"] if _verheiratet(k) else kz["bund_tarif_ledig"]
    e = betrag // 100 * 100
    bund = min(tarif_progressiv(e, stufen), e * kz["bund_hoechstsatz"] / 100) / 5
    kanton = betrag * effektiver_satz_kanton(betrag, st.get("kapitalbezug_kanton", [])) / 100
    return {"bund": round(bund), "kanton": round(kanton), "total": round(bund + kanton)}


def _bezugsplan(k: dict, pks, drei, gestaffelt: bool) -> dict[int, float]:
    plan: dict[int, float] = {}
    for p, pk_e, d in zip(k["personen"], pks, drei):
        pj = pensionsjahr(p)
        if pk_e.kapital:
            plan[pj] = plan.get(pj, 0) + pk_e.kapital
        konten = max(1, int(p["saeule3a"].get("konten", 1)))
        if not d.kapital:
            continue
        if not gestaffelt or konten == 1:
            plan[pj] = plan.get(pj, 0) + d.kapital
            continue
        # Bezug ab 5 Jahre vor dem Referenzalter möglich; ein Konto pro Jahr, letztes im Pensionsjahr
        frueheste = geburtsjahr(p) + 60
        jahre = [j for j in range(pj - konten + 1, pj + 1) if j >= frueheste] or [pj]
        anteil = d.kapital / len(jahre)
        for j in jahre:
            plan[j] = plan.get(j, 0) + anteil
    return dict(sorted(plan.items()))


def kapitalbezug_varianten(k: dict, pks, drei) -> dict:
    erg = {}
    for name, gestaffelt in (("alles_auf_einmal", False), ("gestaffelt", True)):
        plan = _bezugsplan(k, pks, drei, gestaffelt)
        zeilen = [(j, round(b), kapitalsteuer(b, k)) for j, b in plan.items()]
        erg[name] = {"zeilen": zeilen, "steuer_total": sum(z[2]["total"] for z in zeilen)}
    erg["ersparnis"] = erg["alles_auf_einmal"]["steuer_total"] - erg["gestaffelt"]["steuer_total"]
    return erg
