"""Rechenkern Wohneigentum: Tragbarkeit nach Bankenpraxis und Wegfall des Eigenmietwerts."""
from __future__ import annotations

from steuern import steuern_heute
from vorsorge import pensionsjahr


def tragbarkeit(k: dict, jetzt: int) -> dict:
    kz, w = k["kennzahlen"], k["wohnen"]
    preis = float(w.get("kaufpreis", 0))
    eigen = float(w.get("eigenmittel", 0))
    pk_vorbezug = float(w.get("davon_pk_vorbezug", 0))
    hypothek = max(0.0, preis - eigen)
    belehnung = hypothek / preis * 100 if preis else 0.0
    grenze_2 = preis * kz["zweite_hypothek_ab"] / 100
    zweite = max(0.0, hypothek - grenze_2)
    # 2. Hypothek innert 15 Jahren, spätestens bis zur ersten Pensionierung amortisieren
    bis_pension = min(pensionsjahr(p) for p in k["personen"]) - jetzt
    jahre = max(1, min(kz["amortisation_jahre"], bis_pension))
    amort = zweite / jahre
    unterhalt = preis * float(w.get("unterhalt_pauschal", 1.0)) / 100
    kalk = hypothek * kz["tragbarkeit_zins"] / 100 + unterhalt + amort
    einkommen = sum(float(p.get("lohn_brutto", 0)) for p in k["personen"]) + 0.8 * float(w.get("mieteinnahmen_jahr", 0) or 0)
    quote = kalk / einkommen * 100 if einkommen else 0.0
    effektiv = hypothek * float(w.get("hypothek_zins", 0)) / 100 + unterhalt + amort
    eigen_bar = eigen - pk_vorbezug
    pruef = []
    if belehnung > kz["belehnung_max"]:
        pruef.append(f"Belehnung {belehnung:.0f} % über {kz['belehnung_max']} % – mehr Eigenmittel nötig.")
    if eigen_bar < preis * 0.10:
        pruef.append("Weniger als 10 % «harte» Eigenmittel (ohne PK-Vorbezug).")
    if quote > kz["tragbarkeit_max"]:
        pruef.append(f"Tragbarkeit {quote:.1f} % über {kz['tragbarkeit_max']:.0f} % des Bruttoeinkommens.")
    return {
        "hypothek": round(hypothek), "belehnung": round(belehnung, 1), "zweite": round(zweite),
        "amortisation": round(amort), "amort_jahre": jahre, "unterhalt": round(unterhalt),
        "kalk_kosten": round(kalk), "einkommen": round(einkommen), "quote": round(quote, 1),
        "effektiv_jahr": round(effektiv), "effektiv_monat": round(effektiv / 12),
        "max_preis": round(_max_preis(k, eigen, einkommen)), "pruefungen": pruef,
    }


def _max_preis(k: dict, eigen: float, einkommen: float) -> float:
    """Höchster Kaufpreis, der Tragbarkeit und Belehnung einhält (Bisektion)."""
    kz, w = k["kennzahlen"], k["wohnen"]
    unten, oben = 0.0, max(eigen * 20, 1.0)
    for _ in range(60):
        preis = (unten + oben) / 2
        hyp = max(0.0, preis - eigen)
        zweite = max(0.0, hyp - preis * kz["zweite_hypothek_ab"] / 100)
        kosten = hyp * kz["tragbarkeit_zins"] / 100 + preis * float(w.get("unterhalt_pauschal", 1)) / 100 \
            + zweite / kz["amortisation_jahre"]
        ok = (hyp / preis * 100 <= kz["belehnung_max"]) and (kosten <= einkommen * kz["tragbarkeit_max"] / 100)
        unten, oben = (preis, oben) if ok else (unten, preis)
    return unten


def eigenmietwert_wegfall(k: dict) -> dict:
    """Steuerliche Wirkung des Systemwechsels (Wegfall Eigenmietwert und Abzüge)."""
    w = k["wohnen"]
    emw = float(w.get("eigenmietwert", 0))
    hyp = max(0.0, float(w.get("kaufpreis", 0)) - float(w.get("eigenmittel", 0)))
    zinsen = hyp * float(w.get("hypothek_zins", 0)) / 100 if w.get("schuldzinsen_abzug", True) else 0.0
    unterhalt = emw * 0.20  # Pauschalabzug (Liegenschaft über 10 Jahre alt: oft 20 % des EMW)
    heute_netto = emw - zinsen - unterhalt
    grenz = steuern_heute(k)["grenz_total"] / 100
    effekt = -heute_netto * grenz  # positiv = mehr Steuern nach dem Wechsel
    return {
        "eigenmietwert": round(emw), "schuldzinsen": round(zinsen), "unterhalt": round(unterhalt),
        "netto_heute": round(heute_netto), "steuereffekt": round(effekt),
        "ab": k["kennzahlen"]["eigenmietwert_abschaffung"],
    }
