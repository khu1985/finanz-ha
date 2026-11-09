"""Zuzug in die Schweiz: Wirkung eines Zuzugsdatums pro Person auf AHV, Pensionskasse, 3a, Steuern und Fristen.

Stammdaten unter `personen[].zuzug`:
- datum: Zuzug in die Schweiz (leer = schon immer bzw. vor dem 21. Altersjahr in der Schweiz)
- land: Herkunftsland (Hinweise zu Abkommen)
- bewilligung: leer/CH, C, B, L – B und L ohne Schweizer oder C-Partner in der Ehe: Quellensteuer
- pk_eintritt: erster Eintritt in eine Schweizer Pensionskasse (leer = Zuzugsdatum)
- pk_vorher_ch: schon früher in einer Schweizer Pensionskasse versichert (dann keine Einkaufsbegrenzung)
- rente_ausland_jahr, rente_ausland_ab, rente_ausland_waehrung: erwartete Altersrente aus dem Ausland (heutige
  Kaufkraft, z. B. in EUR laut Renteninformation) und Bezugsalter
- nov_beantragt: nachträgliche ordentliche Veranlagung (Quellensteuer) beantragt

Regeln:
- AHV: Beitragspflicht ab 1. Januar nach dem 20. Geburtstag, in der Schweiz erst ab Zuzug. Jahre im Ausland sind
  Beitragslücken (Teilrente); EU/EFTA-Staaten und Abkommensstaaten zahlen ihre Rente separat (rente_ausland_jahr).
  Erziehungsgutschriften nur für Jahre mit Wohnsitz in der Schweiz.
- Pensionskasse: Wer aus dem Ausland zuzieht und nie in einer Schweizer Kasse war, darf in den ersten 5 Jahren nach
  dem Eintritt jährlich höchstens 20 % des versicherten Lohns einkaufen (BVV 2 Art. 60b).
- Säule 3a: Nachzahlung von Lücken (seit 2026 für Jahre ab 2025) nur für Jahre mit AHV-pflichtigem Erwerbseinkommen in
  der Schweiz.
- Quellensteuer: Abzüge für 3a und PK-Einkäufe nur mit nachträglicher ordentlicher Veranlagung (NOV), Antrag bis
  31. März des Folgejahres; ab 120'000 Bruttolohn obligatorisch.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

STANDARD = {
    "datum": "",
    "land": "",
    "bewilligung": "",
    "pk_eintritt": "",
    "pk_vorher_ch": False,
    "rente_ausland_jahr": 0.0,
    "rente_ausland_ab": 0,
    "rente_ausland_waehrung": "CHF",
    "nov_beantragt": False,
}
QUELLENSTEUER = {"B", "L"}
NOV_PFLICHT = 120_000
EU_EFTA = {"deutschland", "österreich", "frankreich", "italien", "spanien", "portugal", "niederlande", "belgien",
           "luxemburg", "irland", "dänemark", "schweden", "finnland", "polen", "tschechien", "slowakei", "ungarn",
           "slowenien", "kroatien", "griechenland", "zypern", "malta", "estland", "lettland", "litauen", "rumänien",
           "bulgarien", "norwegen", "island", "liechtenstein"}


def cfg(person: dict) -> dict:
    return {**STANDARD, **(person.get("zuzug") or {})}


def _datum(text) -> date | None:
    t = str(text or "").strip()
    if not t:
        return None
    try:
        return date.fromisoformat(t[:10])
    except ValueError:
        try:
            tag, monat, jahr = t.split(".")[:3]
            return date(int(jahr), int(monat), int(tag))
        except (ValueError, TypeError):
            return None


def datum(person: dict) -> date | None:
    return _datum(cfg(person)["datum"])


def _zahl(v) -> float:
    try:
        return float(str(v).replace("'", "").replace(",", ".") or 0)
    except ValueError:
        return 0.0


def _geburt(person: dict) -> date:
    t = str(person["geburtsdatum"])
    try:
        return date.fromisoformat(t[:10])
    except ValueError:
        return date(int(t[:4]), 1, 1)


def _monate(a: date, b: date) -> int:
    return max(0, (b.year - a.year) * 12 + b.month - a.month)


def ahv_beginn(person: dict) -> date:
    """Beginn der Schweizer AHV-Beitragsdauer: 1.1. nach dem 20. Geburtstag bzw. Zuzug, wenn später."""
    start = date(_geburt(person).year + 21, 1, 1)
    z = datum(person)
    return max(start, z) if z else start


def ahv_moegliche_jahre(person: dict) -> int | None:
    """Höchstmögliche Beitragsjahre bis 65 ab dem Zuzug; None ohne Zuzug."""
    if not datum(person):
        return None
    g = _geburt(person)
    ende = date(g.year + 65, g.month, 1)
    return _monate(ahv_beginn(person), ende) // 12


def ahv_bisher_schaetzen(person: dict, jetzt: int) -> int:
    return _monate(ahv_beginn(person), date(jetzt, 1, 1)) // 12


def in_ch(person: dict, jahr: int) -> bool:
    """Wohnsitz in der Schweiz in diesem Jahr (mindestens teilweise)."""
    z = datum(person)
    return not z or jahr >= z.year


def pk_eintritt(person: dict) -> date | None:
    c = cfg(person)
    return _datum(c["pk_eintritt"]) or datum(person)


def versicherter_lohn(person: dict) -> float:
    v = _zahl((person.get("pk") or {}).get("versicherter_lohn", 0))
    return v or _zahl(person.get("lohn_brutto", 0))


def einkauf_limit(person: dict, jahr: int) -> float | None:
    """Höchster Einkauf in diesem Jahr nach BVV 2 Art. 60b; None = keine Begrenzung."""
    c = cfg(person)
    e = pk_eintritt(person)
    if not e or c["pk_vorher_ch"] or not datum(person):
        return None
    ende = date(e.year + 5, e.month, min(e.day, 28))
    if date(jahr, 1, 1) >= ende:
        return None
    return round(versicherter_lohn(person) * 0.2)


def einkauf_ende(person: dict) -> date | None:
    e = pk_eintritt(person)
    if not e or cfg(person)["pk_vorher_ch"] or not datum(person):
        return None
    return date(e.year + 5, e.month, min(e.day, 28))


def quellensteuer(person: dict, k: dict) -> bool:
    b = str(cfg(person)["bewilligung"]).strip().upper()
    if b not in QUELLENSTEUER:
        return False
    verheiratet = k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet"
    if verheiratet:
        partner = [p for p in k["personen"] if p is not person]
        if any(str(cfg(p)["bewilligung"]).strip().upper() not in QUELLENSTEUER for p in partner):
            return False          # Ehepartner mit Schweizer Bürgerrecht oder C-Bewilligung: ordentlich besteuert
    return True


def rente_ausland(person: dict) -> float:
    """Erwartete Rente aus dem Ausland in Franken (Betrag in der angegebenen Währung, heutige Kaufkraft)."""
    import waehrung as wg
    c = cfg(person)
    return wg.in_chf(_zahl(c["rente_ausland_jahr"]), str(c.get("rente_ausland_waehrung") or "CHF"))


def rente_ausland_alter(person: dict) -> int:
    ab = int(_zahl(cfg(person)["rente_ausland_ab"]))
    return ab or int(person.get("pensionierung_alter", 65))


@dataclass
class Status:
    person: str
    datum: date | None
    jahre_ch: float
    ahv_moeglich: int | None
    ahv_luecke: int
    einkauf_limit: float | None
    einkauf_bis: date | None
    quellensteuer: bool
    rente_ausland: float


def status(k: dict, heute: date | None = None) -> list[Status]:
    heute = heute or date.today()
    erg = []
    for p in k["personen"]:
        z = datum(p)
        moeglich = ahv_moegliche_jahre(p)
        voll = int(k["kennzahlen"].get("ahv_vollbeitragsjahre", 44))
        erg.append(Status(p["name"], z, round(_monate(z, heute) / 12, 1) if z and z <= heute else 0.0, moeglich,
                          max(0, voll - moeglich) if moeglich is not None else 0,
                          einkauf_limit(p, heute.year), einkauf_ende(p), quellensteuer(p, k), rente_ausland(p)))
    return erg


def hinweise(k: dict, heute: date | None = None) -> list[str]:
    heute = heute or date.today()
    hinw = []
    for p, s in zip(k["personen"], status(k, heute)):
        c = cfg(p)
        if not s.datum:
            continue
        land = str(c["land"] or "").strip()
        if s.ahv_luecke:
            txt = (f"{s.person}: Zuzug {s.datum:%d.%m.%Y} – höchstens {s.ahv_moeglich} AHV-Beitragsjahre bis 65, "
                   f"{s.ahv_luecke} fehlen zur Vollrente (Teilrente). Beitragsjahre im Ausland lassen sich nicht nachzahlen.")
            if land.lower() in EU_EFTA:
                txt += f" {land} zahlt für die dortigen Beitragsjahre eine eigene Rente (Freizügigkeitsabkommen)"
                txt += " – unter «Rente Ausland» erfassen." if not s.rente_ausland else "."
            elif not s.rente_ausland:
                txt += " Prüfen, ob ein Sozialversicherungsabkommen eine Rente aus dem Herkunftsland ermöglicht."
            hinw.append(txt)
        if s.einkauf_limit is not None:
            hinw.append(f"{s.person}: Bis {s.einkauf_bis:%d.%m.%Y} sind PK-Einkäufe auf CHF {_chf(s.einkauf_limit)} pro Jahr "
                        "begrenzt (20 % des versicherten Lohns, BVV 2 Art. 60b – Zuzug aus dem Ausland). Der Optimierer "
                        "berücksichtigt das.")
        if s.quellensteuer:
            lohn = _zahl(p.get("lohn_brutto", 0))
            if lohn >= NOV_PFLICHT:
                hinw.append(f"{s.person}: Quellensteuer mit Lohn ab CHF 120'000 – die nachträgliche ordentliche Veranlagung "
                            "ist obligatorisch; 3a und PK-Einkäufe in der Steuererklärung abziehen.")
            elif not c["nov_beantragt"]:
                hinw.append(f"{s.person}: Quellensteuer – 3a-Beiträge und PK-Einkäufe senken die Steuer nur mit einer "
                            "nachträglichen ordentlichen Veranlagung (Antrag bis 31. März des Folgejahres, gilt danach "
                            "für alle weiteren Jahre).")
        if s.datum > heute:
            hinw.append(f"{s.person}: Zuzug am {s.datum:%d.%m.%Y} geplant – AHV, PK und 3a rechnen ab diesem Datum.")
    return hinw


def erinnerungen(k: dict, heute: date | None = None) -> list:
    """Fristen rund um den Zuzug und die Quellensteuer."""
    from erinnerungen import Erinnerung

    heute = heute or date.today()
    erg = []
    for p in k["personen"]:
        z = datum(p)
        c = cfg(p)
        n = p["name"]
        if z and z - timedelta(days=120) <= heute <= z + timedelta(days=400):
            fristen = [
                (z + timedelta(days=14), "Anmeldung bei der Gemeinde",
                 "Innert 14 Tagen nach dem Zuzug bei der Einwohnerkontrolle anmelden (Pass, Mietvertrag bzw. "
                 "Kaufvertrag, Arbeitsvertrag)."),
                (z + timedelta(days=90), "Krankenkasse abschliessen",
                 "Grundversicherung innert 3 Monaten nach dem Zuzug abschliessen – sie gilt dann rückwirkend ab Zuzug. "
                 "Franchise und Modell unter «Versicherungen» vergleichen."),
                (z + timedelta(days=90), "Vorsorge aus dem Ausland klären",
                 "Versicherungsverlauf im Herkunftsland anfordern; Freizügigkeit bzw. ausländische Guthaben prüfen. "
                 "Ohne Erwerb: bei der Ausgleichskasse als Nichterwerbstätige anmelden."),
                (z + timedelta(days=365), "Fahrzeug und Führerausweis umschreiben",
                 "Ausländischer Führerausweis innert 12 Monaten umtauschen; Fahrzeug einführen und einlösen."),
            ]
            for faellig, titel, text in fristen:
                erg.append(Erinnerung(f"zuzug-{n}-{titel}", f"{titel} – {n}", faellig, text, "einstellungen"))
        if quellensteuer(p, k) and not c["nov_beantragt"] and _zahl(p.get("lohn_brutto", 0)) < NOV_PFLICHT \
                and in_ch(p, heute.year - 1):
            faellig = date(heute.year, 3, 31)
            if heute <= faellig:
                erg.append(Erinnerung(f"nov-{n}-{heute.year}", f"Ordentliche Veranlagung beantragen – {n}", faellig,
                                      f"Quellensteuer {heute.year - 1}: Antrag auf nachträgliche ordentliche Veranlagung "
                                      "bis 31. März stellen, damit 3a, PK-Einkauf und Berufskosten abgezogen werden. "
                                      "Danach unter Einstellungen «NOV beantragt» setzen.", "steuern"))
    return erg


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")
