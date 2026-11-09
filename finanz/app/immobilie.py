"""Liegenschaft: Marktwert nachführen und Erneuerungen planen.

Konfiguration unter `wohnen.liegenschaft`:
- art: haus | wohnung (Stockwerkeigentum: Dach, Fassade, Heizung usw. über den Erneuerungsfonds der Gemeinschaft)
- baujahr, marktwert (Schätzung; 0 = Kaufpreis), marktwert_datum, wertentwicklung (% pro Jahr seit der Schätzung)
- neuwert: Gebäudeversicherungswert (Basis der Erneuerungskosten; 0 = 60 % des Kaufpreises)
- fonds_bestand (bereits angespart), fonds_sparen_monat (geplanter Betrag)
- bauteile: [{name, letzte (Jahr der letzten Erneuerung), lebensdauer, kosten}] – leer = Richtwerte

Richtwerte für Lebensdauer und Kosten (Anteil am Neuwert) in Anlehnung an die paritätische Lebensdauertabelle;
eigene Werte und Offerten haben Vorrang. Kosten in heutigen Franken.
Steuern: werterhaltende Unterhaltskosten sind abziehbar, solange der Eigenmietwert besteuert wird
(`kennzahlen.eigenmietwert_abschaffung`); grosse Arbeiten auf zwei Steuerjahre verteilen bricht die Progression.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Name → (Lebensdauer Jahre, Anteil am Neuwert %, auch bei Stockwerkeigentum privat?)
RICHTWERTE = {
    "Heizung (Wärmeerzeugung)": (20, 4.0, False),
    "Warmwasser / Boiler": (15, 1.0, False),
    "Dach (Eindeckung)": (40, 6.0, False),
    "Fassade (Verputz, Anstrich)": (30, 5.0, False),
    "Fenster": (30, 5.0, False),
    "Küche": (20, 4.0, True),
    "Bad und Sanitär": (30, 4.0, True),
    "Elektroinstallation": (35, 2.0, False),
    "Leitungen (Wasser, Abwasser)": (40, 3.0, False),
    "Bodenbeläge": (25, 3.0, True),
    "Malerarbeiten innen": (15, 2.0, True),
    "Haushaltgeräte": (15, 1.0, True),
}
HORIZONT = 30


def _zahl(v, std=0.0) -> float:
    try:
        t = str(v).replace("'", "").replace(",", ".").strip()
        return float(t) if t else std
    except ValueError:
        return std


def konfiguration(k: dict) -> dict:
    w = k.get("wohnen") or {}
    c = dict(w.get("liegenschaft") or {})
    c.setdefault("art", "haus")
    return c


def neuwert(k: dict) -> float:
    c = konfiguration(k)
    return _zahl(c.get("neuwert")) or _zahl(k["wohnen"].get("kaufpreis")) * 0.6


def bauteile(k: dict, heute: date | None = None) -> list[dict]:
    heute = heute or date.today()
    c = konfiguration(k)
    eigen = c.get("bauteile") or []
    if eigen:
        return [{"name": str(b.get("name", "Bauteil")), "letzte": int(_zahl(b.get("letzte"))),
                 "lebensdauer": max(1, int(_zahl(b.get("lebensdauer"), 20))), "kosten": _zahl(b.get("kosten"))}
                for b in eigen]
    nw = neuwert(k)
    baujahr = int(_zahl(c.get("baujahr")))
    wohnung = str(c.get("art", "haus")) == "wohnung"
    erg = []
    for name, (dauer, anteil, privat) in RICHTWERTE.items():
        if wohnung and not privat:
            continue
        letzte = baujahr or heute.year - dauer // 2
        erg.append({"name": name, "letzte": letzte, "lebensdauer": dauer, "kosten": round(nw * anteil / 100, -2)})
    return erg


@dataclass
class Faellig:
    jahr: int
    name: str
    kosten: float
    ueberfaellig: bool


@dataclass
class Plan:
    marktwert: float
    marktwert_quelle: str
    hypothek: float
    belehnung: float
    neuwert: float
    bauteile: list[dict]
    faelligkeiten: list[Faellig]
    jahreskosten: dict[int, float]
    fonds_bestand: float
    fonds_sparen_monat: float
    soll_monat_dauer: float            # langfristig: Summe Kosten / Lebensdauer
    soll_monat_spitze: float           # damit der Fonds nie ins Minus geht (Horizont)
    abzug_bis: int                     # letztes Jahr mit Unterhaltsabzug
    steuer_ersparnis: float            # auf Arbeiten bis dahin (Grenzsteuersatz)
    hinweise: list[str] = field(default_factory=list)

    @property
    def empfohlen_monat(self) -> float:
        return max(self.soll_monat_dauer, self.soll_monat_spitze)


def planen(k: dict, db=None, heute: date | None = None) -> Plan | None:
    heute = heute or date.today()
    w = k.get("wohnen") or {}
    if not w.get("aktiv"):
        return None
    c = konfiguration(k)
    kaufpreis = _zahl(w.get("kaufpreis"))
    mw = _zahl(c.get("marktwert"))
    quelle = "Kaufpreis"
    if mw:
        try:
            ab = date.fromisoformat(str(c.get("marktwert_datum"))[:10])
        except ValueError:
            ab = heute
        jahre = max(0.0, (heute - ab).days / 365.25)
        mw = mw * (1 + _zahl(c.get("wertentwicklung"), 1.0) / 100) ** jahre
        quelle = f"Schätzung {ab:%m.%Y}" + (f" + {_zahl(c.get('wertentwicklung'), 1.0):g} %/Jahr" if jahre >= 0.5 else "")
    else:
        mw = kaufpreis
    hyp = 0.0
    if db is not None:
        import vermoegen as vm
        hyp = sum(-x["wert"] for x in vm.konten(db) if x["art"] == "hypothek")
    hyp = hyp or max(0.0, kaufpreis - _zahl(w.get("eigenmittel")))
    teile = bauteile(k, heute)
    faellig: list[Faellig] = []
    kosten: dict[int, float] = {}
    for b in teile:
        nae = b["letzte"] + b["lebensdauer"]
        ueber = nae < heute.year
        if ueber:
            nae = heute.year
        while nae < heute.year + HORIZONT:
            faellig.append(Faellig(nae, b["name"], b["kosten"], ueber))
            kosten[nae] = kosten.get(nae, 0) + b["kosten"]
            nae += b["lebensdauer"]
            ueber = False
    faellig.sort(key=lambda f: (f.jahr, f.name))
    bestand = _zahl(c.get("fonds_bestand"))
    sparen = _zahl(c.get("fonds_sparen_monat"))
    dauer = sum(b["kosten"] / b["lebensdauer"] for b in teile) / 12
    spitze, kumuliert = 0.0, 0.0
    for t, j in enumerate(range(heute.year, heute.year + HORIZONT), start=1):
        kumuliert += kosten.get(j, 0)
        spitze = max(spitze, (kumuliert - bestand) / (12 * t))
    abschaffung = int(_zahl(k["kennzahlen"].get("eigenmietwert_abschaffung"), 9999))
    abzug_bis = abschaffung - 1
    try:
        import steuern as st
        grenz = st.steuern_heute(k)["grenz_total"] / 100
    except Exception:  # noqa: BLE001
        grenz = 0.3
    vor_wechsel = sum(f.kosten for f in faellig if f.jahr <= abzug_bis)
    hinw = []
    ueberfaellig = [f for f in faellig if f.ueberfaellig]
    if ueberfaellig:
        hinw.append("Nach Lebensdauer bereits fällig: " + ", ".join(f.name for f in ueberfaellig)
                    + " – Zustand prüfen und «letzte Erneuerung» nachtragen, falls schon erneuert.")
    if not c.get("bauteile"):
        hinw.append("Gerechnet mit Richtwerten (Lebensdauer, Kosten als Anteil am Neuwert"
                    + ("" if _zahl(c.get("neuwert")) else " – Neuwert geschätzt als 60 % des Kaufpreises; den "
                       "Gebäudeversicherungswert eintragen") + "). Eigene Jahre und Offerten unten erfassen.")
    if str(c.get("art")) == "wohnung":
        hinw.append("Stockwerkeigentum: Dach, Fassade, Heizung, Leitungen u. a. zahlt der Erneuerungsfonds der "
                    "Gemeinschaft – Fondsstand und Beiträge im Protokoll der Versammlung prüfen. Hier nur die eigenen Teile.")
    if vor_wechsel and abzug_bis < heute.year + HORIZONT:
        hinw.append(f"Werterhaltende Arbeiten sind nur bis {abzug_bis} abziehbar (Wegfall Eigenmietwert ab {abschaffung}). "
                    f"Fällige Arbeiten bis dahin (CHF {_chf(vor_wechsel)}) sparen rund CHF {_chf(vor_wechsel * grenz)} "
                    "Steuern; anstehende Erneuerungen vorzuziehen kann sich lohnen.")
    gross = [f for f in faellig if f.kosten >= 20000 and f.jahr <= max(abzug_bis, heute.year + 5)]
    if gross:
        hinw.append("Grössere Arbeiten (ab CHF 20'000) wenn möglich auf zwei Steuerjahre verteilen (Rechnungen bzw. Etappen) – "
                    "das bricht die Progression. Energetische Massnahmen: Förderbeiträge (Gebäudeprogramm) vorher beantragen.")
    if sparen and sparen < max(dauer, spitze):
        hinw.append(f"Geplant sind CHF {_chf(sparen)} pro Monat für den Erneuerungsfonds, empfohlen rund "
                    f"CHF {_chf(max(dauer, spitze))}.")
    bel = hyp / mw * 100 if mw else 0.0
    if bel > 66.7:
        hinw.append(f"Belehnung {bel:.0f} % des geschätzten Werts – über zwei Dritteln verlangen Banken Amortisation; "
                    "die Bank rechnet mit ihrer eigenen, meist tieferen Bewertung.")
    return Plan(round(mw), quelle, round(hyp), round(bel, 1), round(neuwert(k)), teile, faellig, kosten, bestand, sparen,
                round(dauer), round(spitze), abzug_bis, round(vor_wechsel * grenz), hinw)


def status(p: Plan | None, heute: date | None = None) -> str:
    import ampel as am
    heute = heute or date.today()
    if p is None:
        return am.GRAU
    bald = sum(f.kosten for f in p.faelligkeiten if f.jahr <= heute.year + 2)
    if any(f.ueberfaellig for f in p.faelligkeiten) and p.fonds_bestand < bald:
        return am.ROT
    if p.fonds_bestand < bald or (p.fonds_sparen_monat and p.fonds_sparen_monat < p.empfohlen_monat * 0.9):
        return am.GELB
    return am.GRUEN


def erinnerungen(k: dict, heute: date | None = None) -> list:
    from erinnerungen import Erinnerung
    heute = heute or date.today()
    p = planen(k, None, heute)
    if not p:
        return []
    erg = []
    for f in p.faelligkeiten:
        faellig = date(f.jahr - 1, 9, 1) if f.jahr > heute.year else date(heute.year, 12, 1)
        if heute <= faellig and (faellig - heute).days <= 400 and not f.ueberfaellig:
            erg.append(Erinnerung(f"bauteil-{f.name}-{f.jahr}", f"{f.name}: Erneuerung {f.jahr} planen", faellig,
                                  f"Nach Lebensdauer fällig (rund CHF {_chf(f.kosten)}). Zustand prüfen, Offerten einholen, "
                                  "Förderbeiträge und Steuern (auf zwei Jahre verteilen) bedenken.", "wohnen"))
    return erg


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")
