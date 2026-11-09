"""Plausibilität der Einstellungen: Ampel pro Feld.

grün = vorhanden und plausibel · gelb = wahrscheinlich falsch, veraltet oder fehlt, die Rechnung läuft aber ·
rot = wichtiger Wert fehlt oder ist unmöglich · grau = optional bzw. leer gelassen (Standard).
"""
from __future__ import annotations

import re
from datetime import date

import ampel as am

GRUEN, GELB, ROT, GRAU = am.GRUEN, am.GELB, am.ROT, am.GRAU
ZIVILSTAENDE = {"verheiratet", "ledig", "geschieden", "verwitwet", "eingetragen"}
BEWILLIGUNGEN = {"", "CH", "C", "B", "L", "G"}


def _zahl(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace("'", "").replace(",", "."))
    except ValueError:
        return None


def _datum(v) -> date | None | bool:
    """None = leer, False = ungültig."""
    t = str(v or "").strip()
    if not t:
        return None
    try:
        return date.fromisoformat(t[:10])
    except ValueError:
        try:
            tag, monat, jahr = t.split(".")[:3]
            return date(int(jahr), int(monat), int(tag))
        except (ValueError, TypeError):
            return False


def _lesen(k: dict, pfad: str):
    obj = k
    for teil in pfad.split("."):
        try:
            obj = obj[int(teil)] if isinstance(obj, list) else obj.get(teil)
        except (IndexError, ValueError, AttributeError):
            return None
        if obj is None:
            return None
    return obj


def pruefen(k: dict, pfad: str, heute: date | None = None) -> tuple[str, str]:
    heute = heute or date.today()
    wert = _lesen(k, pfad)
    z = _zahl(wert) if not isinstance(wert, bool) else None
    kz = k.get("kennzahlen") or {}
    leer = wert is None or (isinstance(wert, str) and not wert.strip())
    m = re.match(r"personen\.(\d+)\.(.+)", pfad)
    if m:
        i = int(m.group(1))
        p = k["personen"][i] if i < len(k["personen"]) else {}
        return _person(k, p, m.group(2), wert, z, leer, kz, heute)
    verheiratet = (k.get("haushalt") or {}).get("zivilstand", "verheiratet") == "verheiratet"
    w = k.get("wohnen") or {}
    if pfad == "haushalt.zivilstand":
        return (GRUEN, "") if str(wert) in ZIVILSTAENDE else (ROT, "unbekannt – «verheiratet» oder «ledig»")
    if pfad == "haushalt.kanton":
        import kantone
        return (GRUEN, "") if str(wert or "").upper() in kantone.NAMEN else (ROT, "Kantonskürzel fehlt oder unbekannt (z. B. BL)")
    if pfad == "haushalt.bedarf_ruhestand":
        if not z:
            return ROT, "fehlt – ohne Bedarf keine Pensionslücke"
        if z < 30000:
            return GELB, "sehr tief für einen Haushalt – Betrag pro Jahr?"
        if z > 300000:
            return GELB, "sehr hoch – Betrag pro Jahr?"
    if pfad == "haushalt.entnahme_jahre" and z is not None and not 15 <= z <= 40:
        return GELB, "üblich sind 20–30 Jahre"
    if pfad == "haushalt.entnahme_rendite" and z is not None and (z > 5 or z < 0):
        return GELB, "über 5 % ist optimistisch"
    if pfad == "annahmen.lohnentwicklung" and z is not None and z > 2:
        return GELB, "reale Lohnentwicklung über 2 % ist optimistisch"
    if pfad == "annahmen.teuerung" and z is not None and not 0 <= z <= 4:
        return GELB, "üblich sind 0,5–2 %"
    if pfad.startswith("steuern."):
        if not verheiratet and pfad in ("steuern.steuerbar_bund", "steuern.steuerbar_kanton",
                                        "steuern.steuer_kanton_gemeinde", "steuern.grenzsteuersatz_kanton") and not z:
            return GRAU, "im Konkubinat pro Person (aus den Steuerdokumenten)"
        if pfad in ("steuern.steuerbar_bund", "steuern.steuerbar_kanton", "steuern.steuer_kanton_gemeinde") and not z:
            return ROT, "fehlt – Veranlagung unter «Steuern» hochladen"
        st = k.get("steuern") or {}
        if pfad == "steuern.steuerbar_kanton" and z and _zahl(st.get("steuerbar_bund")):
            if abs(z - _zahl(st["steuerbar_bund"])) > 0.5 * _zahl(st["steuerbar_bund"]):
                return GELB, "weicht stark vom Bund ab – Werte vertauscht?"
        if pfad == "steuern.steuer_kanton_gemeinde" and z and _zahl(st.get("steuerbar_kanton")):
            if z > 0.3 * _zahl(st["steuerbar_kanton"]):
                return GELB, "über 30 % des steuerbaren Einkommens – Betrag prüfen"
        if pfad == "steuern.grenzsteuersatz_kanton":
            if not z:
                return GELB, "fehlt – wird geschätzt"
            if z > 45:
                return ROT, "über 45 % ist unmöglich"
    if pfad.startswith("wohnen.") and pfad != "wohnen.aktiv" and not w.get("aktiv"):
        return GRAU, "Wohneigentum nicht aktiv"
    if pfad == "wohnen.kaufpreis" and not z:
        return ROT, "fehlt"
    if pfad == "wohnen.eigenmittel" and z is not None and _zahl(w.get("kaufpreis")):
        if z > _zahl(w["kaufpreis"]):
            return ROT, "grösser als der Kaufpreis"
        if z < 0.2 * _zahl(w["kaufpreis"]):
            return GELB, "unter 20 % – Banken verlangen meist 20 %"
    if pfad == "wohnen.hypothek_zins":
        if not z:
            return GELB, "fehlt – Zins laut Vertrag"
        if z > 5:
            return GELB, "sehr hoch – Prozent pro Jahr?"
    if pfad == "wohnen.eigenmietwert" and not z:
        return GELB, "fehlt – aus der Veranlagung"
    if pfad == "wohnen.eigenmietwert" and z and _zahl(w.get("kaufpreis")) and z > 0.06 * _zahl(w["kaufpreis"]):
        return GELB, "über 6 % des Kaufpreises – Mietwert pro Jahr?"
    if pfad == "wohnen.vermietet_anteil":
        if z is not None and not 0 <= z < 100:
            return ROT, "zwischen 0 und 99 % (ganz vermietet = keine Selbstnutzung)"
        if z and not _zahl(w.get("mieteinnahmen_jahr")):
            return GELB, "Mieteinnahmen fehlen"
    if pfad == "wohnen.mieteinnahmen_jahr" and z and not _zahl(w.get("vermietet_anteil")):
        return GELB, "vermieteter Anteil fehlt – Eigenmietwert wird nicht reduziert"
    if pfad == "wohnen.hypothek_faellig":
        d = _datum(wert)
        if d is False:
            return ROT, "Datum ungültig (JJJJ-MM-TT)"
        if d is None:
            return GELB, "fehlt – für Amortisation und Strategie"
        if d < heute:
            return GELB, "liegt in der Vergangenheit – neues Fälligkeitsdatum?"
    if pfad.startswith("erinnerungen.") and pfad.endswith(("frist", "fristerstreckung")) and not leer:
        if not re.fullmatch(r"\d{2}-\d{2}", str(wert).strip()):
            return ROT, "Format MM-TT, z. B. 03-31"
    if pfad == "ki.entity" and leer and (k.get("ki") or {}).get("aktiv"):
        return GRAU, "Standard-KI von Home Assistant"
    return (GRAU, "") if leer or (z == 0 and not isinstance(wert, bool)) else (GRUEN, "")


def _person(k, p, feld, wert, z, leer, kz, heute):
    lohn = _zahl(p.get("lohn_brutto")) or 0
    gd = _datum(p.get("geburtsdatum"))
    alter = (heute.year - gd.year) if gd else None
    bvg = _zahl(kz.get("bvg_eintrittsschwelle")) or 22680
    verheiratet = (k.get("haushalt") or {}).get("zivilstand", "verheiratet") == "verheiratet"
    pk = p.get("pk") or {}
    if feld == "name":
        return (ROT, "fehlt") if leer else (GRUEN, "")
    if feld == "geburtsdatum":
        if gd is False or gd is None:
            return ROT, "fehlt oder ungültig (JJJJ-MM-TT)"
        if not 18 <= alter <= 100:
            return ROT, f"ergibt {alter} Jahre – Datum prüfen"
    if feld == "pensionierung_alter" and z is not None:
        if not 58 <= z <= 70:
            return ROT, "zwischen 58 und 70"
        if z < 63:
            return GELB, "Frühpensionierung – Kürzungen beachten"
    if feld == "lohn_brutto":
        if not z:
            return GELB, "kein Lohn – richtig nur ohne Erwerb"
        if z > 1_000_000:
            return GELB, "sehr hoch – Jahreslohn?"
        if z < 12000:
            return GELB, "sehr tief – Monatslohn statt Jahreslohn?"
    if feld == "sparen_monat" and not z:
        return GELB, "fehlt – unter «Budget» aus den Konten übernehmen"
    if feld == "ahv.beitragsjahre_bisher":
        if not z:
            return GELB, "fehlt – IK-Auszug bestellen (ahv-iv.ch)"
        if alter is not None and z > alter - 19:
            return ROT, f"mehr als ab 21 möglich ({max(0, alter - 20)})"
    if feld == "ahv.fehlende_jahre" and z:
        return GELB, "Beitragslücke – Nachzahlung nur 5 Jahre zurück"
    if feld == "pk.altersguthaben":
        if not z and lohn >= bvg:
            return ROT, "fehlt – Vorsorgeausweis hochladen"
    if feld == "pk.stand":
        d = _datum(wert)
        if d is False:
            return ROT, "Datum ungültig"
        if d is None:
            return (GELB, "fehlt – Datum des Vorsorgeausweises") if lohn >= bvg else (GRAU, "")
        if (heute - d).days > 460:
            return GELB, "älter als ein Jahr – neuen Vorsorgeausweis hochladen"
    if feld == "pk.sparbeitrag_jahr":
        if not z and lohn >= bvg:
            return GELB, "BVG-Minimum angenommen – Sparbeitrag laut Ausweis eintragen"
        if z and lohn and z > 0.4 * lohn:
            return ROT, "über 40 % des Lohns – Betrag prüfen"
    if feld == "pk.zins" and z is not None:
        if z < 0:
            return ROT, "negativ"
        if z > 4:
            return GELB, "über 4 % ist optimistisch"
    if feld == "pk.umwandlungssatz" and z:
        if not 3 <= z <= 7.5:
            return ROT, "zwischen 3 und 7 %"
        if z > 6.8:
            return GELB, "über dem BVG-Satz – gilt meist nur für das Obligatorium"
    if feld == "pk.kapitalbezug_anteil" and z is not None and not 0 <= z <= 100:
        return ROT, "0 bis 100 %"
    if feld in ("pk.ausweis_alterskapital", "pk.ausweis_altersrente"):
        kap, rente = _zahl(pk.get("ausweis_alterskapital")), _zahl(pk.get("ausweis_altersrente"))
        if bool(kap) != bool(rente):
            return GELB, "nur einer der beiden Werte erfasst"
        if kap and rente and not 0.03 <= rente / kap <= 0.075:
            return GELB, f"Rente ÷ Kapital = {rente / kap * 100:.1f} % – Werte vertauscht?"
    if feld == "eigentum_anteil":
        w = k.get("wohnen") or {}
        if not w.get("aktiv"):
            return GRAU, "Wohneigentum nicht aktiv"
        import wohnen as wo
        summe = sum(_zahl(x.get("eigentum_anteil")) or 0 for x in k["personen"])
        if z is not None and not 0 <= z <= 100:
            return ROT, "zwischen 0 und 100 %"
        if summe > 100.5:
            return ROT, f"Summe aller Personen {summe:g} % – höchstens 100 %"
        auto = wo.eigentum_anteile(k).get(p.get("name") or "", 0)
        if not z:
            return GRAU, f"automatisch {auto:g} %"
        if 0 < summe < 99.5 and all(_zahl(x.get("eigentum_anteil")) for x in k["personen"]):
            return GELB, f"Summe {summe:g} % – Rest gehört Dritten?"
    if feld == "risiko.partner_bei_pk_gemeldet":
        if verheiratet:
            return GRAU, "nur im Konkubinat nötig"
        return (GRUEN, "") if wert else (GELB, "im Konkubinat bei der PK melden (Lebenspartnerrente)")
    if feld == "risiko.partnerrente_pk" and not z and lohn >= bvg:
        return GELB, "fehlt – aus dem Vorsorgeausweis"
    if feld == "risiko.iv_rente_pk" and not z and lohn >= bvg:
        return GELB, "fehlt – aus dem Vorsorgeausweis"
    if feld == "saeule3a.beitrag_jahr":
        maxi = _zahl(kz.get("saeule3a_max")) or 7258
        if z and z > maxi + 0.5 and lohn >= bvg:
            return ROT, f"über dem Maximum von {maxi:,.0f}".replace(",", "'")
        if not z and lohn:
            return GELB, "kein 3a-Beitrag – Steuerabzug ungenutzt"
    if feld == "saeule3a.guthaben" and not z and _zahl((p.get("saeule3a") or {}).get("beitrag_jahr")):
        return GELB, "Beitrag erfasst, aber kein Guthaben – Saldo laut 3a-Auszug eintragen"
    if feld == "saeule3a.rendite" and z and z > 6:
        return GELB, "über 6 % ist optimistisch"
    if feld == "saeule3a.konten":
        g = _zahl((p.get("saeule3a") or {}).get("guthaben")) or 0
        if z is not None and z <= 1 and g > 50000:
            return GELB, "mehrere 3a-Konten erlauben einen gestaffelten Bezug"
    if feld == "pensum" and z is not None and not 0 < z <= 100:
        return ROT, "zwischen 1 und 100 %"
    if feld == "pk.versicherter_lohn" and z and lohn and z > lohn * 1.05:
        return ROT, "höher als der Bruttolohn"
    if feld in ("zuzug.datum", "zuzug.pk_eintritt"):
        d = _datum(wert)
        if d is False:
            return ROT, "Datum ungültig (JJJJ-MM-TT)"
        if d and gd and d < gd:
            return ROT, "vor dem Geburtsdatum"
    if feld == "zuzug.bewilligung" and str(wert or "").strip().upper() not in BEWILLIGUNGEN:
        return ROT, "leer/CH, C, B, L oder G"
    if feld == "zuzug.rente_ausland_waehrung":
        import waehrung as wg
        if str(wert or "CHF").upper() not in wg.WAEHRUNGEN:
            return ROT, "Währung unbekannt (CHF, EUR, USD, GBP)"
    if feld == "zuzug.nov_beantragt":
        import zuzug as zz
        if zz.quellensteuer(p, k) and not wert and lohn < 120000:
            return GELB, "Quellensteuer: ordentliche Veranlagung beantragen"
        return (GRAU, "") if not wert else (GRUEN, "")
    if isinstance(wert, bool):
        return GRUEN, ""
    return (GRAU, "") if leer or z == 0 else (GRUEN, "")


def zusammenfassung(k: dict, felder: list[tuple], heute: date | None = None) -> dict[str, list[tuple[str, str, str]]]:
    """Status → [(Pfad, Beschriftung, Grund)]"""
    erg: dict[str, list] = {GRUEN: [], GELB: [], ROT: [], GRAU: []}
    for pfad, text in felder:
        s, grund = pruefen(k, pfad, heute)
        erg[s].append((pfad, text, grund))
    return erg
