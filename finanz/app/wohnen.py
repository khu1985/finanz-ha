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


def _z(v, std: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else std
    except (TypeError, ValueError):
        return std


def eigentum_anteile(k: dict) -> dict[str, float]:
    """Eigentumsanteil an der Liegenschaft in % je Person.

    Quelle: Feld «Anteil an der Liegenschaft» der Personen; Personen mit 0 teilen sich den Rest zu gleichen Teilen.
    Ohne Angaben gilt nachlass.anteil_immobilie (ältere Konfiguration), sonst gleiche Teile.
    """
    namen = [p.get("name") or f"Person {i + 1}" for i, p in enumerate(k["personen"])]
    if not namen:
        return {}
    eigen = {n: _z(p.get("eigentum_anteil")) for n, p in zip(namen, k["personen"])}
    if not any(eigen.values()):
        alt = (k.get("nachlass") or {}).get("anteil_immobilie") or {}
        eigen = {n: _z(next((v for kk, v in alt.items() if str(kk).strip().lower() == n.strip().lower()), 0)) for n in namen}
    rest = max(0.0, 100 - sum(eigen.values()))
    offen = [n for n, v in eigen.items() if not v]
    return {n: (v if v else rest / len(offen)) for n, v in eigen.items()}


def pauschalsatz(k: dict, jahr: int | None = None) -> tuple[float, float]:
    """Pauschaler Unterhaltsabzug (Staat, Bund) in %: je nach Kanton und Alter des Gebäudes (bis 10 Jahre / älter)."""
    from datetime import date
    import kantone
    bj = int(_z(((k.get("wohnen") or {}).get("liegenschaft") or {}).get("baujahr")))
    return kantone.pauschale(k, bool(bj) and (jahr or date.today().year) - bj <= 10)


def unternutzung(k: dict) -> float:
    """Anteil Unternutzung: nicht genutzte Zimmer ÷ (Zimmer + Nebenräume: 2 beim Haus, 1 bei Stockwerkeigentum)."""
    w = k.get("wohnen") or {}
    zimmer, leer = _z(w.get("zimmer")), _z(w.get("zimmer_ungenutzt"))
    if not zimmer or not leer:
        return 0.0
    neben = 1 if str((w.get("liegenschaft") or {}).get("art")) == "wohnung" else 2
    return min(1.0, leer / (zimmer + neben))


def liegenschaft_steuer(k: dict, person: str | None = None) -> dict:
    """Steuerwerte der Liegenschaft bei gemischter Nutzung (selbst bewohnt / vermietet), Staat und Bund.

    Eigenmietwert (Staat, ganze Liegenschaft) und Mieteinnahmen gelten für die ganze Liegenschaft; der Eigenmietwert
    wird auf den selbst bewohnten Teil und um die Unternutzung reduziert, die Mieteinnahmen sind voll steuerbar.
    Bund: eigener Wert oder Staat × Kantonsfaktor (BL 1,2). Mit `person` werden alle Werte auf deren Eigentumsanteil
    umgerechnet (getrennte Steuererklärungen, z. B. im Konkubinat oder bei Miteigentum).
    """
    import kantone
    w = k.get("wohnen") or {}
    vermietet = min(100.0, max(0.0, _z(w.get("vermietet_anteil"))))
    selbst = 100 - vermietet
    emw_voll = _z(w.get("eigenmietwert"))
    emw_bund_voll = _z(w.get("eigenmietwert_bund")) or emw_voll * kantone.emw_bund_faktor(k)
    miete_voll = _z(w.get("mieteinnahmen_jahr"))
    hyp = max(0.0, _z(w.get("kaufpreis")) - _z(w.get("eigenmittel")))
    zinsen_voll = hyp * _z(w.get("hypothek_zins")) / 100 if w.get("schuldzinsen_abzug", True) else 0.0
    anteil = eigentum_anteile(k).get(person, 100.0) if person else 100.0
    f = anteil / 100
    satz, satz_bund = pauschalsatz(k)
    u = unternutzung(k)
    emw_selbst = emw_voll * selbst / 100
    emw = emw_selbst * (1 - u) * f
    emw_bund = emw_bund_voll * selbst / 100 * (1 - u) * f
    miete = miete_voll * f
    zinsen = zinsen_voll * f
    unterhalt = (emw + miete) * satz / 100
    unterhalt_bund = (emw_bund + miete) * satz_bund / 100
    return {
        "vermietet": vermietet, "selbst": selbst, "anteil": anteil, "pauschal": satz, "pauschal_bund": satz_bund,
        "unternutzung": round(u * 100, 1), "unternutzung_betrag": round(emw_selbst * u * f),
        "emw_voll": round(emw_voll), "emw_bund_voll": round(emw_bund_voll), "emw_selbst_voll": round(emw_selbst),
        "miete_voll": round(miete_voll), "zinsen_voll": round(zinsen_voll),
        "eigenmietwert": round(emw), "eigenmietwert_bund": round(emw_bund), "mieteinnahmen": round(miete),
        "schuldzinsen": round(zinsen), "unterhalt": round(unterhalt), "unterhalt_bund": round(unterhalt_bund),
        "netto": round(emw + miete - zinsen - unterhalt),
        "netto_bund": round(emw_bund + miete - zinsen - unterhalt_bund),
    }


def eigenmietwert_wegfall(k: dict, aktiven_uebrig: float | None = None) -> dict:
    """Steuerliche Wirkung des Systemwechsels (Wegfall Eigenmietwert und Abzüge) für den ganzen Haushalt.

    Selbst bewohnter Teil: Eigenmietwert, Unterhalt und Schuldzinsen fallen weg. Vermieteter Teil: Mieteinnahmen bleiben
    steuerbar, Unterhalt bleibt abziehbar, Schuldzinsen nur noch im Verhältnis der vermieteten Liegenschaft zum
    Gesamtvermögen (`aktiven_uebrig` = übrige Aktiven ohne Liegenschaft; ohne Angabe: vermieteter Anteil).
    """
    w = k["wohnen"]
    s = liegenschaft_steuer(k)
    wert = _z((w.get("liegenschaft") or {}).get("marktwert")) or _z(w.get("kaufpreis"))
    vermietet_wert = wert * s["vermietet"] / 100
    if aktiven_uebrig is None or not wert:
        quote = s["vermietet"] / 100
    else:
        quote = vermietet_wert / (wert + max(0.0, aktiven_uebrig)) if vermietet_wert else 0.0
    zinsen_nachher = s["schuldzinsen"] * quote
    unterhalt_nachher = s["mieteinnahmen"] * s["pauschal"] / 100
    nachher = s["mieteinnahmen"] - zinsen_nachher - unterhalt_nachher
    nachher_bund = s["mieteinnahmen"] * (1 - s["pauschal_bund"] / 100) - zinsen_nachher
    t = steuern_heute(k)
    g_bund = t["grenz_bund"] / 100
    g_staat = t["grenz_total"] / 100 - g_bund
    # positiv = mehr Steuern nach dem Wechsel (Staat und Bund mit eigenem Eigenmietwert und eigener Pauschale)
    effekt = (nachher - s["netto"]) * g_staat + (nachher_bund - s["netto_bund"]) * g_bund
    return s | {
        "netto_heute": s["netto"], "zinsen_nachher": round(zinsen_nachher), "unterhalt_nachher": round(unterhalt_nachher),
        "netto_nachher": round(nachher), "netto_bund_nachher": round(nachher_bund), "zins_quote": round(quote * 100, 1), "steuereffekt": round(effekt),
        "ab": k["kennzahlen"]["eigenmietwert_abschaffung"],
    }
