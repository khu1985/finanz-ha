"""Rechenkern Steuern.

- Direkte Bundessteuer exakt nach Tarif (aus kennzahlen), inkl. Elterntarif und Höchstsatz.
- Staats- und Gemeindesteuer als Potenzkurve durch die letzte Veranlagung (Steuer und Grenzsteuersatz).
- Kapitalleistungen: Bund 1/5 des Tarifs (DBG Art. 38), Kanton mit effektivem Satz aus Tabelle.
- Verheiratete werden gemeinsam besteuert (eine Steuereinheit), Konkubinatspaare getrennt
  (je eine Steuereinheit unter steuern.personen).
"""
from __future__ import annotations

from dataclasses import dataclass

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
    """Verheiratete und Alleinstehende mit Kindern: Verheiratetentarif, Elterntarif pro Kind."""
    einkommen = max(0.0, float(einkommen) // 100 * 100)  # auf 100 Franken abgerundet
    stufen = kz["bund_tarif_verheiratet"] if (verheiratet or kinder) else kz["bund_tarif_ledig"]
    steuer = min(tarif_progressiv(einkommen, stufen), einkommen * kz["bund_hoechstsatz"] / 100)
    steuer -= kinder * kz["bund_elterntarif_kind"]
    steuer = max(0.0, steuer)
    return 0.0 if steuer < 25 else round(steuer, 2)


def kantonssteuer(einkommen: float, st: dict) -> float:
    """Staats- und Gemeindesteuer als Potenzkurve durch die letzte Veranlagung.

    Steuer(x) = S · (x / E)^e mit e = Grenzsteuersatz · E / S: trifft die veranlagte Steuer S beim Einkommen E
    und dort genau den Grenzsteuersatz; darunter sinkt die Steuer progressiv statt linear (auch grosse Abzüge
    wie PK-Einkäufe werden so realistisch bewertet).
    """
    ref_e = float(st.get("steuerbar_kanton", 0))
    ref_s = float(st.get("steuer_kanton_gemeinde", 0))
    g = float(st.get("grenzsteuersatz_kanton", 0)) / 100
    if einkommen <= 0:
        return 0.0
    if ref_e <= 0 or ref_s <= 0:
        return round(max(0.0, ref_s + g * (einkommen - ref_e)), 2)
    exponent = max(1.0, g * ref_e / ref_s)
    return round(ref_s * (einkommen / ref_e) ** exponent, 2)


def anzahl_kinder(k: dict) -> int:
    return len(k["haushalt"].get("kinder") or [])


@dataclass
class Einheit:
    name: str
    personen: list[str]     # Namen der Personen in dieser Steuereinheit
    st: dict                # steuerbar_bund, steuerbar_kanton, steuer_kanton_gemeinde, grenzsteuersatz_kanton
    verheiratet: bool
    kinder: int


def einheiten(k: dict) -> list[Einheit]:
    st = k["steuern"]
    namen = [p["name"] for p in k["personen"]]
    if _verheiratet(k) or not st.get("personen"):
        return [Einheit("Haushalt" if len(namen) > 1 else namen[0], namen, st, _verheiratet(k),
                        anzahl_kinder(k))]
    erg = []
    for i, e in enumerate(st["personen"]):
        name = str(e.get("person") or (namen[i] if i < len(namen) else f"Person {i + 1}"))
        merged = {"steuerbar_bund": 0, "steuerbar_kanton": 0, "steuer_kanton_gemeinde": 0, "steuerbar_vermoegen": 0,
                  "vermoegenssteuer": 0,
                  "grenzsteuersatz_kanton": st.get("grenzsteuersatz_kanton", 0)} | e
        erg.append(Einheit(name, [name], merged, False, int(e.get("kinder", 0) or 0)))
    return erg


def einheit_von(k: dict, person: str | None) -> Einheit:
    alle = einheiten(k)
    if person:
        for e in alle:
            if any(n.lower() == person.lower() for n in e.personen):
                return e
    return alle[0]


def _rechne(e: Einheit, kz: dict) -> dict:
    s = e.st
    bund = bundessteuer(s["steuerbar_bund"], e.verheiratet, e.kinder, kz)
    kanton = kantonssteuer(s["steuerbar_kanton"], s)
    grenz_bund = (bundessteuer(s["steuerbar_bund"] + 1000, e.verheiratet, e.kinder, kz) - bund) / 10
    total = bund + kanton
    return {
        "name": e.name, "bund": round(bund), "kanton": round(kanton), "total": round(total),
        "vermoegen": round(vermoegenssteuer(s, kz)),
        "grenz_bund": round(grenz_bund, 1),
        "grenz_total": round(grenz_bund + float(s.get("grenzsteuersatz_kanton", 0)), 1),
        "effektiv": round(total / s["steuerbar_kanton"] * 100, 1) if s["steuerbar_kanton"] else 0.0,
    }


def vermoegenssteuer(st_: dict, kz: dict) -> float:
    """Vermögenssteuer (Kanton und Gemeinde) aus der Veranlagung; fehlt der Betrag, Schätzung mit Promille-Satz."""
    betrag = float(st_.get("vermoegenssteuer", 0) or 0)
    if betrag:
        return betrag
    basis = float(st_.get("steuerbar_vermoegen", 0) or 0)
    return basis * float(kz.get("vermoegen_promille", 0) or 0) / 1000


def steuern_heute(k: dict) -> dict:
    kz = k["kennzahlen"]
    teile = [_rechne(e, kz) for e in einheiten(k)]
    total = sum(t["total"] for t in teile)
    basis = sum(float(e.st["steuerbar_kanton"]) for e in einheiten(k))
    return {
        "einheiten": teile,
        "bund": sum(t["bund"] for t in teile), "kanton": sum(t["kanton"] for t in teile), "total": total,
        "vermoegen": sum(t["vermoegen"] for t in teile), "total_inkl": total + sum(t["vermoegen"] for t in teile),
        "grenz_bund": max(t["grenz_bund"] for t in teile),
        "grenz_total": max(t["grenz_total"] for t in teile),
        "effektiv": round(total / basis * 100, 1) if basis else 0.0,
    }


def ersparnis_abzug(k: dict, abzug: float, person: str | None = None) -> dict:
    """Steuerersparnis, wenn das steuerbare Einkommen (Bund und Kanton) einer Person um `abzug` sinkt."""
    kz = k["kennzahlen"]
    e = einheit_von(k, person)
    s = e.st
    b0 = bundessteuer(s["steuerbar_bund"], e.verheiratet, e.kinder, kz)
    b1 = bundessteuer(s["steuerbar_bund"] - abzug, e.verheiratet, e.kinder, kz)
    k0 = kantonssteuer(s["steuerbar_kanton"], s)
    k1 = kantonssteuer(s["steuerbar_kanton"] - abzug, s)
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


def kapitalsteuer(betrag: float, k: dict, einheit: Einheit | None = None) -> dict:
    """Steuer auf Kapitalleistungen eines Jahres einer Steuereinheit (Ehepaare: Summe beider)."""
    kz, st = k["kennzahlen"], k["steuern"]
    if betrag <= 0:
        return {"bund": 0, "kanton": 0, "total": 0}
    e = einheit or einheiten(k)[0]
    stufen = kz["bund_tarif_verheiratet"] if (e.verheiratet or e.kinder) else kz["bund_tarif_ledig"]
    b = betrag // 100 * 100
    bund = min(tarif_progressiv(b, stufen), b * kz["bund_hoechstsatz"] / 100) / 5
    kanton = betrag * effektiver_satz_kanton(betrag, st.get("kapitalbezug_kanton", [])) / 100
    return {"bund": round(bund), "kanton": round(kanton), "total": round(bund + kanton)}


def _bezuege(p: dict, pk_e, d, gestaffelt: bool) -> dict[int, float]:
    plan: dict[int, float] = {}
    pj = pensionsjahr(p)
    if pk_e.kapital:
        plan[pj] = plan.get(pj, 0) + pk_e.kapital
    konten = max(1, int(p["saeule3a"].get("konten", 1)))
    if d.kapital:
        if not gestaffelt or konten == 1:
            plan[pj] = plan.get(pj, 0) + d.kapital
        else:
            # Bezug ab 5 Jahre vor dem Referenzalter; ein Konto pro Jahr, das letzte im Pensionsjahr
            jahre = [j for j in range(pj - konten + 1, pj + 1) if j >= geburtsjahr(p) + 60] or [pj]
            for j in jahre:
                plan[j] = plan.get(j, 0) + d.kapital / len(jahre)
    return plan


def kapitalbezug_varianten(k: dict, pks, drei) -> dict:
    """Pro Variante: Zeilen (Jahr, Steuereinheit, Bezug, Steuer) und Steuertotal."""
    erg = {}
    for name, gestaffelt in (("alles_auf_einmal", False), ("gestaffelt", True)):
        zeilen = []
        for e in einheiten(k):
            plan: dict[int, float] = {}
            for p, pk_e, d in zip(k["personen"], pks, drei):
                if p["name"] in e.personen:
                    for j, b in _bezuege(p, pk_e, d, gestaffelt).items():
                        plan[j] = plan.get(j, 0) + b
            zeilen += [(j, e.name, round(b), kapitalsteuer(b, k, e)) for j, b in sorted(plan.items())]
        zeilen.sort(key=lambda z: (z[0], z[1]))
        erg[name] = {"zeilen": zeilen, "steuer_total": sum(z[3]["total"] for z in zeilen)}
    erg["ersparnis"] = erg["alles_auf_einmal"]["steuer_total"] - erg["gestaffelt"]["steuer_total"]
    return erg
