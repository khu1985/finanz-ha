"""Liquiditätsplan: Kontostand Monat für Monat über die nächsten 12 Monate.

Start: heutiger Stand der Bankkonten (Art «Bank»). Pro Monat:
- Einnahmen: Durchschnitt der Buchungen, pro Kalendermonat aus dem Vorjahr, wenn 12 Monate vorliegen (13. Monatslohn,
  Bonus erscheinen so im richtigen Monat).
- Laufende Ausgaben: Durchschnitt pro Monat ohne Steuern und ohne die unten einzeln geplanten Beträge.
- Einzelne Beträge im Monat, in dem sie anfallen: Steuern (offene Beträge laut «Steuern bezahlen», auf Wunsch in
  Monatsraten), wiederkehrende Rechnungen, die nicht monatlich kommen (vierteljährlich bis jährlich, aus den
  Buchungen erkannt), Versicherungsprämien ohne erkannte Buchung (jährlich im Monat des Vertragsbeginns),
  Verkehrssteuer und Vignette der Fahrzeuge, MFK, geplante PK-Einkäufe und Lebensziele mit Monat.
- Sparen: Einzahlungen in 3a, Depot usw. laut Buchungen (Durchschnitt), sonst die 3a-Einzahlung im Dezember.
Ohne Buchungen rechnet der Plan mit dem Sparpotenzial aus den Einstellungen als monatlichem Überschuss vor den
einzeln geplanten Beträgen.

Ergebnis: Stand am Monatsende, Tiefpunkt, Vergleich mit der Notreserve und der Betrag, der pro Monat für die
grossen Rechnungen zurückgelegt werden sollte.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
NICHT_MONATLICH = {"alle 2 Monate", "vierteljährlich", "halbjährlich", "jährlich"}
MONATLICH_KK = {"kvg", "vvg"}           # Krankenkasse: Prämie jeden Monat (im Durchschnitt enthalten)


def _chf(v: float) -> str:
    return f"{v:,.0f}" >> TS


def _monat_plus(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _tag(jahr: int, monat: int, tag: int) -> date:
    return date(jahr, monat, min(tag, calendar.monthrange(jahr, monat)[1]))


@dataclass
class Posten:
    datum: date
    name: str
    betrag: float           # negativ = Ausgabe
    rubrik: str             # Steuern, Rechnungen, Versicherungen, Fahrzeuge, Vorsorge, Ziele, Einnahmen
    seite: str = ""
    geschaetzt: bool = False


@dataclass
class Monat:
    monat: date
    start: float
    einnahmen: float
    laufend: float          # laufende Ausgaben (negativ)
    sparen: float           # Einzahlungen 3a, Depot (negativ)
    posten: list[Posten]

    @property
    def einzeln(self) -> float:
        return sum(p.betrag for p in self.posten)

    @property
    def ende(self) -> float:
        return self.start + self.einnahmen + self.laufend + self.sparen + self.einzeln

    @property
    def name(self) -> str:
        return f"{MONATE[self.monat.month - 1]} {self.monat:%y}"


@dataclass
class Plan:
    start: float
    stand_vom: str
    reserve: float
    monate: list[Monat]
    quelle: str             # "buchungen" | "einstellungen"
    einzeln_jahr: float     # Summe der einzeln geplanten Ausgaben (positiv)
    zuruecklegen: float     # pro Monat
    hinweise: list[str] = field(default_factory=list)

    @property
    def tief(self) -> Monat:
        return min(self.monate, key=lambda m: m.ende)


def reserve(k: dict) -> float:
    w = k.get("wohnen") or {}
    bedarf = float(k["haushalt"].get("bedarf_ruhestand", 0) or 0)
    return float(w.get("reserve", 0) or 0) or round(bedarf / 2)


def _wiederholen(erste: date, tage: float, von: date, bis: date) -> list[date]:
    erg, d, i = [], erste, 0
    while d < von and i < 50:
        i += 1
        d = erste + timedelta(days=round(tage * i))
    while d <= bis and i < 60:
        erg.append(d)
        i += 1
        d = erste + timedelta(days=round(tage * i))
    return erg


def rechnen(k: dict, db, heute: date | None = None, monate: int = 12) -> Plan:
    import abos as ab
    import budget as bu
    import steuerzahlung as sz
    import vermoegen as vm
    import versicherungen as vi

    heute = heute or date.today()
    von = date(heute.year, heute.month, 1)
    bis = _monat_plus(von, monate) - timedelta(days=1)
    lq = vm.liquiditaet(db)
    letzte = db.execute("SELECT MAX(s.datum) FROM saldi s JOIN konten k ON k.id = s.konto_id WHERE k.art = 'bank'"
                        ).fetchone()[0] or ""
    start = float(lq["total"])
    hinweise: list[str] = []
    posten: list[Posten] = []
    abgezogen: dict[str, float] = {}       # pro Jahr aus dem Durchschnitt herausgenommen, je Budget-Kategorie

    # --- Steuern
    st_posten = sz.auswerten(k, db, heute)
    raten = str(sz.cfg(k).get("raten") or "einmal") == "monatlich"
    for p in st_posten:
        if p.offen <= 0:
            continue
        fae = max(p.faellig, heute)
        if fae > bis:
            continue
        name = f"{p.name} {p.jahr}" + (" (geschätzt)" if p.quelle == "geschätzt" else "")
        if raten and p.faellig > heute:
            n = sz._monate_bis(heute, p.faellig)
            for i in range(n):
                d = _monat_plus(von, i)
                if d <= bis:
                    posten.append(Posten(_tag(d.year, d.month, 25), name + " (Rate)", -p.offen / n, "Steuern",
                                         "steuerzahlung", p.quelle == "geschätzt"))
        else:
            posten.append(Posten(fae, name, -p.offen, "Steuern", "steuerzahlung", p.quelle == "geschätzt"))

    # --- Buchungen: Durchschnitt und nicht monatliche Rechnungen
    a = bu.auswerten(k, db, heute=heute)
    buchungen = bu.alle(db) if a else []
    vertraege = vi.alle(db)
    erkannt = ab.erkennen(buchungen, vertraege, heute) if a else []
    for x in erkannt:
        if x.eingang or x.rhythmus not in NICHT_MONATLICH or x.kategorie in ("Steuern", bu.SPAREN, bu.UMBUCHUNG):
            continue
        tage = next(t for n, t, *_ in ab.RHYTHMEN if n == x.rhythmus)
        for d in _wiederholen(date.fromisoformat(x.naechste), tage, heute, bis):
            posten.append(Posten(d, x.name, -x.betrag, "Rechnungen", "budget"))
        abgezogen[x.kategorie] = abgezogen.get(x.kategorie, 0.0) + x.pro_jahr

    # --- Versicherungen ohne erkannte Buchung: jährlich im Monat des Vertragsbeginns
    erkannte_namen = " ".join(x.schluessel for x in erkannt)
    for v in vertraege:
        if v["sparte"] in MONATLICH_KK or not float(v.get("praemie_jahr") or 0):
            continue
        if v.get("ablauf") and str(v["ablauf"]) < heute.isoformat():
            continue
        vers = (v.get("versicherer") or "").lower().split()
        if vers and len(vers[0]) > 2 and vers[0] in erkannte_namen:
            continue
        try:
            b = date.fromisoformat(str(v.get("beginn") or ""))
        except ValueError:
            b = date(heute.year, 1, 1)
        d = _tag(von.year, b.month, b.day)
        if d < von:
            d = _tag(von.year + 1, b.month, b.day)
        if d <= bis:
            name = f"{vi.SPARTEN.get(v['sparte'], 'Versicherung')} {v.get('versicherer') or ''}".strip()
            posten.append(Posten(d, name, -float(v["praemie_jahr"]), "Versicherungen", "versicherungen",
                                 not v.get("beginn")))
            abgezogen["Versicherungen"] = abgezogen.get("Versicherungen", 0.0) + float(v["praemie_jahr"])

    # --- Fahrzeuge: Verkehrssteuer (Januar angenommen), Vignette (Dezember), MFK
    try:
        import fahrzeuge as fz
        for f in fz.alle(k, db, heute):
            for name, monat in (("Verkehrssteuer", 1), ("Vignette", 12)):
                betrag = float(f.kosten.get(name) or 0)
                if not betrag:
                    continue
                d = date(von.year if monat >= von.month else von.year + 1, monat, 15)
                if d <= bis:
                    posten.append(Posten(d, f"{name} {f.name}", -betrag, "Fahrzeuge", "fahrzeuge", name == "Verkehrssteuer"))
                    abgezogen["Mobilität"] = abgezogen.get("Mobilität", 0.0) + betrag
            if f.mfk and von <= f.mfk <= bis:
                posten.append(Posten(f.mfk, f"MFK {f.name} (Gebühr und Vorbereitung)", -300.0, "Fahrzeuge", "fahrzeuge",
                                     True))
    except Exception:  # noqa: BLE001 – Fahrzeuge sind optional
        pass

    # --- Vorsorge: geplante PK-Einkäufe (Dezember)
    for p in k["personen"]:
        for e in (p.get("pk") or {}).get("einkauf_geplant") or []:
            try:
                d = date(int(e["jahr"]), 12, 10)
            except (KeyError, TypeError, ValueError):
                continue
            if von <= d <= bis and float(e.get("betrag") or 0):
                posten.append(Posten(d, f"PK-Einkauf {p['name']}", -float(e["betrag"]), "Vorsorge", "szenarien"))

    # --- Lebensziele mit Monat (ohne Monat: Juli des Zieljahres, als Annahme markiert)
    for z in k.get("ziele") or []:
        try:
            jahr, betrag = int(z.get("jahr")), float(z.get("betrag") or 0)
        except (TypeError, ValueError):
            continue
        monat = int(z.get("monat") or 0) if str(z.get("monat") or "").isdigit() else 0
        d = date(jahr, monat if 1 <= monat <= 12 else 7, 15)
        if betrag > 0 and von <= d <= bis:
            posten.append(Posten(d, str(z.get("name") or "Ziel"), -betrag, "Ziele", "finanzplan", not monat))

    # --- Durchschnitt pro Monat
    if a and (a.monate < 3 or a.einnahmen <= 0):
        hinweise.append(f"Erst {a.monate} Monat(e) Buchungen bzw. keine Einnahmen darin – der Plan rechnet deshalb "
                        "mit dem Sparpotenzial aus den Einstellungen. Ab drei Monaten Kontoauszügen mit Lohn zählen "
                        "die Buchungen.")
        a = None
    if a:
        quelle = "buchungen"
        steuern_j = next((v for n, v, _ in a.kategorien if n == "Steuern"), 0.0)
        kat = {n: v for n, v, _ in a.kategorien}
        weg = sum(min(v, kat.get(n, 0.0)) for n, v in abgezogen.items())
        laufend = -max(0.0, a.ausgaben - steuern_j - weg) / 12
        sparen = -a.sparen_konto / 12
        pro_monat = {int(m[5:7]): ein for m, ein, _, _ in a.monatlich} if a.monate >= 12 else {}
        einnahmen_mittel = a.einnahmen / 12
        if a.monate < 12:
            hinweise.append(f"Nur {a.monate} Monate Buchungen – Einnahmen als Durchschnitt; 13. Monatslohn und Bonus "
                            "fehlen im richtigen Monat. Für einen genaueren Plan 12 Monate importieren.")
    else:
        quelle = "einstellungen"
        spar = sum(float(p.get("sparen_monat", 0) or 0) for p in k["personen"])
        # Sparpotenzial gilt nach allen Ausgaben: die einzeln geplanten kommen im Durchschnitt wieder dazu
        einzeln = -sum(p.betrag for p in posten if p.rubrik not in ("Vorsorge", "Ziele"))
        einnahmen_mittel, laufend, sparen, pro_monat = spar + einzeln / 12, 0.0, 0.0, {}
        try:                                  # Kindersparen: Dauerauftrag aufs Konto der Kinder
            import kindersparen as ksp
            sparen = -ksp.monat_total(ksp.plaene(k, db, heute))
        except Exception:  # noqa: BLE001
            pass
        if not any("Sparpotenzial" in h for h in hinweise):
            hinweise.append("Noch keine Buchungen: Überschuss pro Monat aus dem Sparpotenzial der Einstellungen. Mit "
                            "importierten Kontoauszügen (unter «Budget») wird der Plan genauer.")
    if not a or a.sparen_konto < 1000:
        for p in k["personen"]:
            b3 = float((p.get("saeule3a") or {}).get("beitrag_jahr") or 0)
            d = date(von.year, 12, 20)
            if b3 and float(p.get("lohn_brutto", 0) or 0) > 0 and von <= d <= bis:
                posten.append(Posten(d, f"3a-Einzahlung {p['name']}", -b3, "Vorsorge", "vorsorge"))

    liste = []
    stand = start
    for i in range(monate):
        m = _monat_plus(von, i)
        ende_m = _monat_plus(m, 1) - timedelta(days=1)
        ein = pro_monat.get(m.month, einnahmen_mittel)
        anteil = 1.0
        if i == 0:                                   # laufender Monat: nur der Rest ab heute
            anteil = (ende_m.day - heute.day + 1) / ende_m.day
        mp = sorted((p for p in posten if m <= p.datum <= ende_m), key=lambda p: p.datum)
        mo = Monat(m, stand, ein * anteil, laufend * anteil, sparen * anteil, mp)
        liste.append(mo)
        stand = mo.ende

    einzeln_jahr = -sum(p.betrag for p in posten if p.rubrik not in ("Ziele",))
    zurueck = round(einzeln_jahr / monate / 50) * 50
    plan = Plan(round(start), letzte, reserve(k), liste, quelle, round(einzeln_jahr), zurueck, hinweise)
    t = plan.tief
    if not start:
        hinweise.insert(0, "Noch keine Saldi der Bankkonten – unter «Vermögen» erfassen, sonst startet der Plan bei 0.")
    elif letzte and (heute - date.fromisoformat(letzte)).days > 45:
        hinweise.insert(0, f"Saldi vom {date.fromisoformat(letzte):%d.%m.%Y} – für einen genauen Start unter «Vermögen» "
                           "nachführen.")
    if t.ende < 0:
        hinweise.insert(0, f"Im {t.name} fehlen rund CHF {_chf(-t.ende)} auf den Bankkonten – Geld vom Depot oder Sparkonto "
                           "rechtzeitig umbuchen, grosse Rechnungen in Raten zahlen oder Ausgaben verschieben.")
    elif plan.reserve and t.ende < plan.reserve:
        hinweise.insert(0, f"Im {t.name} sinken die Bankkonten auf CHF {_chf(t.ende)} – CHF {_chf(plan.reserve - t.ende)} "
                           f"unter der Notreserve von CHF {_chf(plan.reserve)}.")
    if lq["gesperrt"] and t.ende - lq["gesperrt"] < 0 <= t.ende:
        hinweise.append(f"CHF {_chf(lq['gesperrt'])} liegen auf Sparkonten mit Bezugslimite – ohne Kündigung reicht das "
                        f"Geld im {t.name} nicht.")
    if zurueck:
        hinweise.append(f"Für Steuern und grosse Rechnungen rund CHF {_chf(zurueck)} pro Monat auf ein separates Konto "
                        "legen (Dauerauftrag) – dann bleibt das Privatkonto ruhig.")
    return plan


def erinnerungen(k: dict, db, heute: date) -> list:
    """Engpass in den nächsten drei Monaten."""
    import erinnerungen as er
    try:
        p = rechnen(k, db, heute, 4)
    except Exception:  # noqa: BLE001
        return []
    if not p.start:
        return []
    for m in p.monate[1:]:
        if m.ende < 0 or (p.reserve and m.ende < p.reserve * 0.5):
            return [er.Erinnerung(f"liquiditaet-{m.monat:%Y-%m}", f"Kontostand im {m.name} knapp", m.monat,
                                  f"Laut Liquiditätsplan noch rund CHF {_chf(m.ende)} auf den Bankkonten "
                                  f"(Notreserve CHF {_chf(p.reserve)}). Grosse Posten: "
                                  + ", ".join(f"{x.name} CHF {_chf(-x.betrag)}" for x in
                                              sorted(m.posten, key=lambda x: x.betrag)[:3] if x.betrag < 0) + ".",
                                  "liquiditaet")]
    return []
