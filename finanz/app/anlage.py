"""Anlage-Check: Vermögen in Töpfe aufteilen (Reserve, zweckgebunden, langfristig) und die Aufteilung prüfen.

Töpfe:
1. Notreserve – auf dem Konto (wohnen.reserve oder 6 Monate Bedarf).
2. Zweckgebunden bis zur Fälligkeit der Hypothek – Anteil der Ziel-Amortisation, der nicht aus Sparen und verpfändeter
   Vorsorge kommt, plus geplante PK-Einkäufe bis dahin (nach Steuerersparnis). Kurzer Horizont: sicher anlegen.
3. Langfristig – der Rest; Aktienquote nach Risikoprofil.
Keine Produktempfehlungen; Renditen sind Annahmen.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

from dataclasses import dataclass, field
from datetime import date

import vermoegen as vm

STANDARD = {
    "risiko": "mittel",
    "zins_konto": 0.3,
    "zins_sicher": 1.0,                  # Festgeld, Kassenobligation, Geldmarkt
    "rendite": {"tief": 2.0, "mittel": 3.5, "hoch": 5.0},
    "aktienquote": {"tief": 25, "mittel": 50, "hoch": 75},
    "krypto_max": 5,
    "einzeltitel_max": 10,
}


@dataclass
class Topf:
    name: str
    betrag: float
    horizont: str
    empfehlung: str


@dataclass
class Check:
    liquide: float
    depot: float
    krypto: float
    vorsorge: float
    finanz_total: float
    toepfe: list[Topf]
    anlegbar: float
    aktien_soll: float
    aktien_ist: float
    krypto_anteil: float
    cash_anteil: float
    opportunitaet: float                 # Mehrertrag pro Jahr, wenn der langfristige Topf angelegt statt auf dem Konto ist
    opportunitaet_horizont: float        # kumuliert bis zur Pensionierung (Zinseszins)
    horizont_jahre: int
    hinweise: list[str] = field(default_factory=list)


def konfiguration(k: dict) -> dict:
    eigen = k.get("anlage") or {}
    cfg = {**STANDARD, **{s: v for s, v in eigen.items() if v not in (None, "")}}
    cfg["rendite"] = {**STANDARD["rendite"], **(eigen.get("rendite") or {})}
    cfg["aktienquote"] = {**STANDARD["aktienquote"], **(eigen.get("aktienquote") or {})}
    return cfg


def _chf(v: float) -> str:
    return f"{v:,.0f}" >> TS


def pruefen(k: dict, db, heute: date | None = None) -> Check:
    import berater as br
    import vorsorge as vs

    heute = heute or date.today()
    cfg = konfiguration(k)
    risiko = cfg["risiko"] if cfg["risiko"] in cfg["aktienquote"] else "mittel"
    konten = vm.konten(db)
    summe = lambda arten: sum(x["wert"] for x in konten if x["art"] in arten)  # noqa: E731
    liquide = summe({"bank"})
    depot = summe({"depot"})
    krypto = summe({"krypto"})
    vorsorge = summe({"vorsorge"})
    sonst = summe({"sonstiges"})
    finanz = liquide + depot + krypto + sonst
    w = k.get("wohnen") or {}
    bedarf = float(k["haushalt"].get("bedarf_ruhestand", 0) or 0)
    reserve = float(w.get("reserve", 0) or 0) or round(bedarf / 2)
    toepfe = [Topf("Notreserve", reserve, "jederzeit", f"Auf dem Konto ({cfg['zins_konto']:g} %)")]
    zweck = 0.0
    a = br.amortisation(k, db, heute) if w.get("aktiv") else None
    if a:
        aus_anderem = a.sparen + a.verpfaendet - a.steuer_bezug
        ziel = a.maximal if a.maximal and a.verfuegbar >= a.maximal else a.ziel
        zweck_amort = max(0.0, ziel - aus_anderem) if ziel else 0.0
        zweck = zweck_amort + a.einkaeufe
        jahre = max(0.0, a.monate / 12)
        toepfe.append(Topf(f"Amortisation {a.faellig:%m.%Y}", zweck_amort, f"{jahre:.1f} Jahre",
                           f"Sicher und auf die Fälligkeit terminiert, z. B. Festgeld oder Kassenobligation ({cfg['zins_sicher']:g} %)"))
        if a.einkaeufe:
            toepfe.append(Topf("Geplante PK-Einkäufe", a.einkaeufe, "nach Plan", "Auf dem Konto bis zur Überweisung"))
    anlegbar = max(0.0, liquide + depot - reserve - zweck)
    quote = float(cfg["aktienquote"][risiko])
    if krypto:
        toepfe.append(Topf("Krypto (bestehend)", krypto, "offen", "Separat führen; Anteil begrenzen"))
    if sonst:
        toepfe.append(Topf("Übriges (z. B. Genossenschaftsanteile)", sonst, "offen", "Nicht kurzfristig verfügbar"))
    toepfe.append(Topf("Langfristig", anlegbar, "über 10 Jahre",
                       f"Breit diversifiziert, kostengünstig, rund {quote:.0f} % Aktien (Profil «{risiko}»)"))
    try:
        import wertschriften as ws
        aktien = ws.aktienwert(k, db)          # mit erfassten Positionen: nur der Aktienteil des Depots
    except Exception:  # noqa: BLE001
        aktien = None
    aktien_ist = ((depot if aktien is None else min(aktien, depot or aktien)) + krypto) / finanz * 100 if finanz else 0.0
    langfristig_ist = depot
    rendite = float(cfg["rendite"][risiko])
    nicht_angelegt = max(0.0, anlegbar - langfristig_ist)
    opp = nicht_angelegt * (rendite - float(cfg["zins_konto"])) / 100
    horizont = max(1, min(vs.pensionsjahr(p) for p in k["personen"]) - heute.year)
    opp_h = nicht_angelegt * ((1 + rendite / 100) ** horizont - (1 + float(cfg["zins_konto"]) / 100) ** horizont)
    hinw = []
    if liquide < reserve:
        hinw.append(f"Konten (CHF {_chf(liquide)}) unter der Notreserve von CHF {_chf(reserve)}.")
    else:
        lq = vm.liquiditaet(db)
        if lq["sofort"] < reserve:
            frist = (f"nach {lq['kuendigung_monate']} Monaten Kündigungsfrist" if lq["kuendigung_monate"] else "nach Kündigung")
            hinw.append(f"Von der Notreserve sind wegen Bezugslimiten auf Sparkonten nur CHF {_chf(lq['sofort'])} sofort "
                        f"verfügbar; der Rest erst {frist}"
                        + (f" oder mit {lq['rueckzug_prozent']:g} % Rückzugskommission" if lq["rueckzug_prozent"] else "")
                        + " – einen Teil auf ein Konto ohne Limite legen.")
    if nicht_angelegt > 20000:
        hinw.append(f"Rund CHF {_chf(nicht_angelegt)} liegen ohne Zweck auf Konten. Langfristig angelegt (Annahme {rendite:g} % "
                    f"statt {cfg['zins_konto']:g} %) wären das rund CHF {_chf(opp)} pro Jahr bzw. CHF {_chf(opp_h)} bis zur Pensionierung.")
    krypto_anteil = krypto / finanz * 100 if finanz else 0.0
    if krypto_anteil > float(cfg["krypto_max"]):
        hinw.append(f"Krypto macht {krypto_anteil:.0f} % des Finanzvermögens aus (Richtwert höchstens {cfg['krypto_max']} %) – "
                    "hohe Schwankungen; Teilverkäufe gestaffelt planen statt auf einen Zeitpunkt.")
    fremd = vm.fremdwaehrung(db)
    fremd_total = sum(fremd.values())
    if fremd_total and finanz:
        anteil = fremd_total / finanz * 100
        teile = ", ".join(f"{w} CHF {_chf(v)}" for w, v in sorted(fremd.items(), key=lambda x: -x[1]))
        hinw.append(f"Fremdwährungen: {anteil:.0f} % des Finanzvermögens ({teile}). Ausgaben und Ruhestand sind in Franken – "
                    "Konten in Fremdwährung tragen ein Währungsrisiko; der Franken hat gegenüber dem Euro über die Jahre "
                    "meist zugelegt. Nicht benötigte Guthaben in Franken wechseln oder bewusst halten (z. B. für Ausgaben "
                    "im Euroraum)." if anteil >= 10 else
                    f"Fremdwährungen: {anteil:.0f} % des Finanzvermögens ({teile}) – kleines Währungsrisiko.")
    if zweck and depot > anlegbar + 1:
        hinw.append("Ein Teil des Depots wird bis zur Fälligkeit für die Amortisation gebraucht – Kursrisiko vor "
                    f"{a.faellig:%m.%Y} begrenzen." if a else "Ein Teil des Depots ist zweckgebunden – Kursrisiko begrenzen.")
    hinw.append("Arbeitgeberaktien (z. B. Mitarbeiterprogramme) erhöhen das Klumpenrisiko, weil Lohn und Vermögen vom gleichen "
                f"Unternehmen abhängen – Anteil am Finanzvermögen höchstens rund {cfg['einzeltitel_max']} %.")
    if w.get("aktiv") and float(w.get("hypothek_zins", 0) or 0) > float(cfg["zins_sicher"]):
        hinw.append(f"Die Hypothek kostet {float(w['hypothek_zins']):g} %, sichere Anlagen bringen rund {cfg['zins_sicher']:g} % – "
                    "Amortisation bei Fälligkeit lohnt sich, vorher ist sie bei einer Festhypothek meist nicht möglich.")
    return Check(round(liquide), round(depot), round(krypto), round(vorsorge), round(finanz), toepfe, round(anlegbar), quote,
                 round(aktien_ist, 1), round(krypto_anteil, 1), round(liquide / finanz * 100 if finanz else 0, 1), round(opp),
                 round(opp_h), horizont, hinw)
