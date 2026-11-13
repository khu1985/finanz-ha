"""Lebenslauf der Kinder: Phasen von der Geburt bis zur Selbständigkeit – mit eigenen Kosten und Vergleichswerten.

Phasen (Schuljahr ab 1. August; Stichtag 31. Juli, Kindergarten ab 4 Jahren wie in den meisten HarmoS-Kantonen):
Kleinkind → Kita/Tagesfamilie → Kindergarten (2 J.) → Primarschule (6 J.) → Sekundarstufe I (3 J.)
→ Berufslehre (3–4 J.) / Gymnasium (4 J.) / Fachmittelschule (3 J.) → Studium (5 J.) / Fachhochschule (3 J.) → selbständig.

Pro Kind unter `haushalt.kinder[]` (alles freiwillig):
- weg: lehre | gymnasium | fms; danach: keine | studium | fh; auswaerts: Studium nicht bei den Eltern
- kita_tage (pro Woche), kita_ab_monate (Alter beim Kita-Start, Standard 4), mittagstisch_tage, nachmittag_std (pro Woche)
- einschulung: Jahre später (+) bzw. früher (−) als nach Stichtag; sek2_jahre, tertiaer_jahre: abweichende Dauer
- phasen: {phase: {betreuung: CHF/Monat, leben: CHF/Monat}} – leer = Vergleichswert

«Betreuung & Ausbildung» = Kita, Tagesstruktur, Schulgeld, Material, Studiengebühren; «Lebenshaltung» = Essen, Kleider,
Gesundheit, Freizeit, Förderung, ÖV, Handy – ohne Wohnen und Krankenkasse (stecken in Miete/Hypothek und Prämien).

Vergleichswerte (CHF pro Monat, Stand der Quellen 2023–2026):
- Lebenshaltung: Zürcher Kinderkosten-Tabelle, Stand 1.4.2024 (letzte Ausgabe; ab 2026 nicht weitergeführt), Altersgruppen
  1–4, 5–12, 13–18 für Einzelkind / eines von zwei / eines von drei Kindern, ohne Wohnen, Wohnnebenkosten und Krankenkasse.
  Gilt bis 21, solange das Kind bei den Eltern wohnt.
- Kita: Vollkosten rund CHF 127 pro Tag (INFRAS 2023: 12.65 pro Stunde × 10 Stunden), 50 Wochen im Jahr. Mit
  Subventionen bzw. Betreuungsgutscheinen zahlen Eltern je nach Einkommen ab rund 12–25 pro Tag.
- Tagesstruktur: Mittagstisch rund CHF 32 inkl. Essen (Vollkosten einer Baselbieter Gemeinde 2026; subventioniert
  ab rund 15), Betreuung 11.65 pro Stunde (INFRAS), 38 Schulwochen.
- Volksschule: Unterricht unentgeltlich; für Lager und Schulreisen höchstens 10 bzw. 16 Franken pro Tag (Bundesgericht).
- Gymnasium/FMS: rund 3'000 in vier Jahren plus Laptop 600–1'200 (Elterninformation einer Kantonsschule 2026).
- Lehre: Material und Gerät geschätzt 40; Lehrlingslohn rund 500–700 / 700–900 / 900–1'100 je Lehrjahr.
- Studium: Universität Basel, Lebenskostenbudget 2026: Semestergebühr 850 und Ausbildungskosten 100–200 pro Monat;
  auswärts zusätzlich Zimmer 600, mehr Verpflegung und Nebenkosten (Lebenshaltung ohne Krankenkasse rund 1'600).
"""
from __future__ import annotations

import functools
import json
from dataclasses import dataclass, field
from datetime import date

PHASEN = {
    "kleinkind": "Kleinkind", "kita": "Kita / Tagesfamilie", "kindergarten": "Kindergarten", "primar": "Primarschule",
    "sek1": "Sekundarstufe I", "lehre": "Berufslehre", "gymnasium": "Gymnasium", "fms": "Fachmittelschule",
    "studium": "Studium (Uni/ETH)", "fh": "Fachhochschule",
}
KURZ = {"kleinkind": "Klein", "kita": "Kita", "kindergarten": "KG", "primar": "Primar", "sek1": "Sek I",
        "lehre": "Lehre", "gymnasium": "Gym", "fms": "FMS", "studium": "Studium", "fh": "FH"}
WEGE = {"lehre": ("Berufslehre", 3), "gymnasium": ("Gymnasium", 4), "fms": ("Fachmittelschule", 3)}
DANACH = {"keine": ("keine weitere Ausbildung", 0), "studium": ("Studium Uni/ETH (Bachelor und Master)", 5),
          "fh": ("Fachhochschule (Bachelor)", 3)}
BETREUUNG_PHASEN = ("kleinkind", "kita", "kindergarten", "primar", "sek1")   # Drittbetreuung (Steuerabzug)

# Lebenshaltung ohne Wohnen und Krankenkasse: Altersgruppe → (Einzelkind, eines von 2, eines von 3+)
LEBEN = {1: (665, 475, 430), 5: (800, 680, 660), 13: (1145, 1035, 1035)}
LEBEN_MIT_WOHNEN = {1: (1390, 1115, 990), 5: (1525, 1320, 1220), 13: (1870, 1675, 1595)}
LEBEN_AUSWAERTS = 1600
KITA_TAG, KITA_WOCHEN = 127.0, 50
MITTAGSTISCH, BETREUUNG_STUNDE, SCHULWOCHEN = 32.0, 11.65, 38
MITTELSCHULE, LEHRE_MATERIAL, HOCHSCHULE = 80.0, 40.0, 290.0
LEHRLINGSLOHN = (600, 800, 1000, 1100)
QUELLEN = [
    ("Zürcher Kinderkosten-Tabelle 2024 (Amt für Jugend und Berufsberatung)",
     "https://www.zh.ch/content/dam/zhweb/bilder-dokumente/themen/familie/sorgerecht-unterhalt/kinderkosten_2024.pdf"),
    ("Kosten für Kita und Tagesstrukturen (familienleben.ch, nach INFRAS 2023)",
     "https://www.familienleben.ch/kind/kindergarten-kinderkrippen/die-kosten-fuer-kita-und-kindergarten-in-der-schweiz-"
     "und-moegliche-reduktionen-eine-uebersicht-9643"),
    ("Schulreisen, Lager und Projektwochen: Elternbeiträge (Kanton Basel-Landschaft 2026)",
     "https://kanton.baselland.ch/bildungs-kultur-und-sportdirektion/bildung-handbuch/organisation-schulbetrieb/finanzen/"
     "schulreisen-schullager-projekt-und-kurswochen/pdf-1/20260127_def-merkblatt-schulreisen-lager-projektwochen.pdf"),
    ("Gymnasium: Elterninformation mit Kosten (Kantonsschule Solothurn 2026)",
     "https://ksso.so.ch/fileadmin/ksso/02Bildungsangebot/gymnasium/Gym_1_Elternorientierung_2026_aktualisiert_vfinal.pdf"),
    ("Erster Lehrlingslohn (Raiffeisen)", "https://www.raiffeisen.ch/rch/de/wissen/lebensphasen/erster-lehrlingslohn.html"),
    ("Lebenskostenbudget Studium 2026 (Universität Basel)",
     "https://www.unibas.ch/dam/jcr:f5650a4d-6e2e-4c06-bf98-aa8128ef5d11/FRM_gh_Lebenskostenbudget_aktuelle_Version_D_"
     "20260101.2026-01-21-10-58-14.pdf"),
    ("Primarstufe: Stichtag und Eintrittsalter (EDK)", "https://edk.ch/de/bildungssystem-ch/obligatorium/primarstufe"),
]


def _zahl(v, std: float | None = None) -> float | None:
    try:
        t = str(v).replace("'", "").replace(",", ".").strip()
        return float(t) if t and t != "None" else std
    except ValueError:
        return std


def _plus_monate(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def _monate(a: date, b: date) -> int:
    return max(0, (b.year - a.year) * 12 + b.month - a.month)


def _alter(geburt: date, d: date) -> int:
    return d.year - geburt.year - ((d.month, d.day) < (geburt.month, geburt.day))


@dataclass
class Phase:
    schluessel: str
    titel: str
    von: date
    bis: date                         # erster Tag danach
    alter_von: int
    alter_bis: int
    betreuung_eigen: float | None
    leben_eigen: float | None
    betreuung_vergleich: float        # Durchschnitt pro Monat über die Phase
    leben_vergleich: float
    notiz: str = ""

    @property
    def monate(self) -> int:
        return _monate(self.von, self.bis)

    @property
    def betreuung(self) -> float:
        return self.betreuung_vergleich if self.betreuung_eigen is None else self.betreuung_eigen

    @property
    def leben(self) -> float:
        return self.leben_vergleich if self.leben_eigen is None else self.leben_eigen

    @property
    def monat(self) -> float:
        return self.betreuung + self.leben

    @property
    def vergleich(self) -> float:
        return self.betreuung_vergleich + self.leben_vergleich

    @property
    def total(self) -> float:
        return self.monat * self.monate

    def monate_im_jahr(self, jahr: int) -> int:
        a, b = max(self.von, date(jahr, 1, 1)), min(self.bis, date(jahr + 1, 1, 1))
        return _monate(a, b) if a < b else 0


@dataclass
class Lebenslauf:
    name: str
    geburt: date
    phasen: list[Phase]
    selbstaendig: date
    aktuell: Phase | None
    rest: float                       # Kosten ab heute bis zur Selbständigkeit
    rest_betreuung: float
    eigene: bool                      # mindestens ein eigener Betrag erfasst
    hinweise: list[str] = field(default_factory=list)

    def kosten_jahr(self, jahr: int) -> tuple[float, float]:
        """(Betreuung & Ausbildung, Lebenshaltung) im Kalenderjahr."""
        b = sum(p.betreuung * p.monate_im_jahr(jahr) for p in self.phasen)
        lb = sum(p.leben * p.monate_im_jahr(jahr) for p in self.phasen)
        return b, lb


def _rang(anzahl: int) -> int:
    return 0 if anzahl <= 1 else 1 if anzahl == 2 else 2


def leben_vergleich(alter: int, anzahl: int = 1, auswaerts: bool = False) -> float:
    if auswaerts:
        return float(LEBEN_AUSWAERTS)
    gruppe = 13 if alter >= 13 else 5 if alter >= 5 else 1
    return float(LEBEN[gruppe][_rang(anzahl)])


def kindergarten_start(kind: dict, geburt: date) -> date:
    jahr = geburt.year + (4 if (geburt.month, geburt.day) <= (7, 31) else 5)
    return date(jahr + int(_zahl(kind.get("einschulung"), 0) or 0), 8, 1)


def _eigen(kind: dict, phase: str, feld: str) -> float | None:
    p = (kind.get("phasen") or {}).get(phase) or {}
    return _zahl(p.get(feld))


def _hat_phasen(kind: dict) -> bool:
    return any(_zahl(v) is not None for p in (kind.get("phasen") or {}).values() for v in (p or {}).values())


def lebenslauf(kind: dict, anzahl: int = 1, heute: date | None = None) -> Lebenslauf | None:
    import kinder as ki
    heute = heute or date.today()
    g = ki.geburt(kind)
    if not g:
        return None
    kita_tage = _zahl(kind.get("kita_tage"), 0) or 0
    kita_ab = int(_zahl(kind.get("kita_ab_monate"), 4) or 4)
    mt = _zahl(kind.get("mittagstisch_tage"), 0) or 0
    nm = _zahl(kind.get("nachmittag_std"), 0) or 0
    weg = str(kind.get("weg") or "lehre")
    weg = weg if weg in WEGE else "lehre"
    danach = str(kind.get("danach") or ("studium" if weg == "gymnasium" else "keine"))
    danach = danach if danach in DANACH else "keine"
    auswaerts = bool(kind.get("auswaerts"))
    kg = kindergarten_start(kind, g)
    sek2 = int(_zahl(kind.get("sek2_jahre"), WEGE[weg][1]) or WEGE[weg][1])
    tert = int(_zahl(kind.get("tertiaer_jahre"), DANACH[danach][1]) or DANACH[danach][1]) if danach != "keine" else 0

    grenzen: list[tuple[str, date, date]] = []
    kita_start = _plus_monate(g, kita_ab)
    if kita_tage and kita_start < kg:
        grenzen += [("kleinkind", g, kita_start), ("kita", kita_start, kg)]
    else:
        grenzen.append(("kleinkind", g, kg))
    d = kg
    for schl, jahre in (("kindergarten", 2), ("primar", 6), ("sek1", 3), (weg, sek2), (danach, tert)):
        if jahre > 0 and schl != "keine":
            grenzen.append((schl, d, date(d.year + jahre, 8, 1)))
            d = date(d.year + jahre, 8, 1)
    selbst = d

    # ältere Konfiguration: Betreuungskosten pro Jahr bis zu einem Alter → als eigene Beträge der Betreuungsphasen
    alt_bet = _zahl(kind.get("betreuung_jahr"), 0) or 0
    alt_bis = _zahl(kind.get("betreuung_bis"), 12) or 12
    ohne_phasen = not _hat_phasen(kind)

    phasen = []
    for schl, von, bis in grenzen:
        n = max(1, _monate(von, bis))
        leben = sum(leben_vergleich(_alter(g, _plus_monate(von, i)), anzahl,
                                    auswaerts and schl in ("studium", "fh")) for i in range(n)) / n
        tagesstruktur = (mt * MITTAGSTISCH + nm * BETREUUNG_STUNDE) * SCHULWOCHEN / 12
        betreuung = {"kita": kita_tage * KITA_TAG * KITA_WOCHEN / 12, "kindergarten": tagesstruktur,
                     "primar": tagesstruktur, "sek1": tagesstruktur, "gymnasium": MITTELSCHULE, "fms": MITTELSCHULE,
                     "lehre": LEHRE_MATERIAL, "studium": HOCHSCHULE, "fh": HOCHSCHULE}.get(schl, 0.0)
        notiz = {
            "kita": f"{kita_tage:g} Tag(e) pro Woche zu Vollkosten; mit Subvention je nach Einkommen ab rund 12–25 pro Tag",
            "kleinkind": "Windeln, Ausstattung, Kinderwagen; Betreuung zu Hause oder durch Tageseltern",
            "kindergarten": "Unterricht gratis" + (f"; Tagesstruktur {mt:g} Mittag(e), {nm:g} Std. pro Woche" if mt or nm else ""),
            "primar": "Lager und Schulreisen höchstens 10–16 pro Tag" + (f"; Tagesstruktur {mt:g} Mittag(e), {nm:g} Std." if mt or nm else ""),
            "sek1": "Lehrstellensuche bzw. Übertritt ins Gymnasium im 2. Jahr" if weg == "lehre" else "Übertritt in die Mittelschule",
            "lehre": "Lehrlingslohn rund " + " / ".join(f"{x:,}".replace(",", "'") for x in LEHRLINGSLOHN[:sek2]) + " pro Monat",
            "gymnasium": "Bücher, Material, Laptop, Studienreise",
            "fms": "Bücher, Material, Laptop",
            "studium": ("auswärts wohnend" if auswaerts else "bei den Eltern wohnend") + ", Semestergebühr rund 850",
            "fh": ("auswärts wohnend" if auswaerts else "bei den Eltern wohnend") + ", Semestergebühren rund 700–850",
        }.get(schl, "")
        b_eigen = _eigen(kind, schl, "betreuung")
        if ohne_phasen and alt_bet and schl in BETREUUNG_PHASEN and _alter(g, von) < alt_bis:
            b_eigen = round(alt_bet / 12)
        phasen.append(Phase(schl, PHASEN[schl], von, bis, _alter(g, von), _alter(g, bis), b_eigen,
                            _eigen(kind, schl, "leben"), round(betreuung), round(leben), notiz))

    aktuell = next((p for p in phasen if p.von <= heute < p.bis), None)
    rest = rest_b = 0.0
    monat_heute = date(heute.year, heute.month, 1)
    for p in phasen:
        m = _monate(max(p.von, monat_heute), p.bis) if p.bis > monat_heute else 0
        rest += p.monat * m
        rest_b += p.betreuung * m
    eigene = any(p.betreuung_eigen is not None or p.leben_eigen is not None for p in phasen)
    lauf = Lebenslauf(str(kind.get("name") or "Kind"), g, phasen, selbst, aktuell, round(rest), round(rest_b), eigene)
    lauf.hinweise = _hinweise(kind, lauf, heute)
    return lauf


def _hinweise(kind: dict, lauf: Lebenslauf, heute: date) -> list[str]:
    import kinder as ki
    h = []
    n = lauf.name
    ende = _alter(lauf.geburt, lauf.selbstaendig)
    bis = ki.ausbildung_bis(kind)
    if lauf.selbstaendig > heute and abs(min(25, ende) - bis) >= 2:
        h.append(f"{n}: Ausbildungsende laut Lebenslauf mit rund {ende} Jahren, unter «Unterhaltsberechtigt bis» steht {bis} – "
                 "anpassen, damit Kinderabzug, Ausbildungszulage und Waisenrenten richtig laufen.")
    for p in lauf.phasen:
        if p.betreuung_eigen is not None and p.betreuung_vergleich and p.betreuung_eigen > p.betreuung_vergleich * 1.3 \
                and p.bis > heute:
            h.append(f"{n}, {p.titel}: Betreuung CHF {_chf(p.betreuung_eigen)} pro Monat liegt deutlich über dem Vergleich "
                     f"({_chf(p.betreuung_vergleich)}) – Anspruch auf Subvention bzw. Betreuungsgutschein prüfen.")
        if p.leben_eigen is not None and p.leben_vergleich and p.bis > heute:
            diff = p.leben_eigen - p.leben_vergleich
            if abs(diff) > max(250, p.leben_vergleich * 0.3):
                h.append(f"{n}, {p.titel}: Lebenshaltung CHF {_chf(p.leben_eigen)} pro Monat "
                         + ("über" if diff > 0 else "unter") + f" dem Vergleich ({_chf(p.leben_vergleich)}).")
    nxt = next((p for p in lauf.phasen if p.von > heute), None)
    if nxt and lauf.aktuell and (nxt.von - heute).days <= 365:
        diff = nxt.monat - lauf.aktuell.monat
        if abs(diff) >= 100:
            h.append(f"{n}: Ab {nxt.von:%m.%Y} {nxt.titel} – die Kosten " + ("steigen" if diff > 0 else "sinken")
                     + f" um rund CHF {_chf(abs(diff))} pro Monat.")
    return h


@functools.lru_cache(maxsize=64)
def _lauf(kind_json: str, anzahl: int, heute: date) -> Lebenslauf | None:
    """Zwischengespeichert: die Seite Kinder, Steuern und der Finanzplan fragen pro Jahr und Kind mehrfach."""
    return lebenslauf(json.loads(kind_json), anzahl, heute)


def von(kind: dict, anzahl: int = 1, heute: date | None = None) -> Lebenslauf | None:
    return _lauf(json.dumps(kind, sort_keys=True, default=str), anzahl, heute or date.today())


def alle(k: dict, heute: date | None = None) -> list[Lebenslauf]:
    import kinder as ki
    kinder = ki.liste(k)
    return [lauf for lauf in (_lauf(json.dumps(c, sort_keys=True, default=str), len(kinder), heute or date.today())
                              for c in kinder) if lauf]


def jahre(k: dict, von: int, bis: int, heute: date | None = None) -> list[tuple[int, float, float]]:
    """(Jahr, Betreuung & Ausbildung, Lebenshaltung) über alle Kinder."""
    laeufe = alle(k, heute)
    erg = []
    for j in range(von, bis + 1):
        b = lb = 0.0
        for lauf in laeufe:
            x, y = lauf.kosten_jahr(j)
            b, lb = b + x, lb + y
        erg.append((j, round(b), round(lb)))
    return erg


def finanzplan(k: dict, jahre_: list[int], pension: int) -> dict[int, float]:
    """Mehr- (+) bzw. Minderkosten (−) der Kinder pro Jahr für den Finanzplan.

    Vor der Pensionierung steckt das heutige Niveau schon im Sparpotenzial – es zählt die Veränderung gegenüber dem
    ersten Jahr. Ab der Pensionierung zählen die vollen Kosten (der Bedarf im Ruhestand enthält keine Kinder)."""
    if not jahre_ or (k.get("finanzplan") or {}).get("kinderkosten") is False:
        return {}
    werte = {j: b + lb for j, b, lb in jahre(k, jahre_[0], jahre_[-1], date(jahre_[0], 1, 1))}
    basis = werte.get(jahre_[0], 0.0)
    erg = {}
    for j in jahre_:
        d = werte.get(j, 0.0) - basis if j < pension else werte.get(j, 0.0)
        if abs(d) >= 1:
            erg[j] = d
    return erg


def betreuung_jahr(kind: dict, jahr: int) -> float | None:
    """Eigene Betreuungskosten (Kita, Tagesstruktur) im Jahr aus dem Lebenslauf – None, wenn keine erfasst sind."""
    if not _hat_phasen(kind):
        return None
    lauf = _lauf(json.dumps(kind, sort_keys=True, default=str), 1, date.today())
    if not lauf:
        return None
    return float(sum((p.betreuung_eigen or 0) * p.monate_im_jahr(jahr) for p in lauf.phasen
                     if p.schluessel in BETREUUNG_PHASEN))


def erinnerungen(k: dict, heute: date | None = None) -> list:
    """Phasenwechsel: Anmeldung Kita, Kindergarten, Lehrstellensuche, Studium – mit der Kostenänderung."""
    from erinnerungen import Erinnerung
    heute = heute or date.today()
    erg = []
    texte = {
        "kita": (6, "Kita-Platz anmelden", "Wartelisten sind lang – Platz suchen, Betreuungsgutschein bzw. Subvention beantragen."),
        "kindergarten": (6, "Kindergarten: Anmeldung und Tagesstruktur",
                         "Die Gemeinde meldet sich im Frühling – Mittagstisch und Nachmittagsbetreuung früh anmelden, "
                         "Kita kündigen."),
        "lehre": (12, "Lehrstellensuche", "Schnupperlehren und Bewerbungen laufen im zweitletzten Schuljahr."),
        "gymnasium": (6, "Übertritt Gymnasium", "Anmeldung und Laptop einplanen."),
        "studium": (6, "Studienbeginn", "Semestergebühr, Wohnsituation und Stipendien prüfen; Ausbildungszulage weiter beantragen."),
        "fh": (6, "Studienbeginn", "Semestergebühren und Stipendien prüfen; Ausbildungszulage weiter beantragen."),
    }
    for lauf in alle(k, heute):
        for i, p in enumerate(lauf.phasen):
            if p.schluessel not in texte:
                continue
            vorlauf, titel, text = texte[p.schluessel]
            faellig = _plus_monate(p.von, -vorlauf)
            if heute <= faellig and (faellig - heute).days <= 60:
                vorher = lauf.phasen[i - 1] if i else None
                diff = p.monat - (vorher.monat if vorher else 0)
                text2 = text + (f" Ab {p.von:%m.%Y} kostet {lauf.name} rund CHF {_chf(p.monat)} pro Monat "
                                f"({'+' if diff >= 0 else '−'}{_chf(abs(diff))}).")
                erg.append(Erinnerung(f"kind-{lauf.name}-phase-{p.schluessel}", f"{titel} – {lauf.name}", faellig,
                                      text2, "kinder"))
    return erg


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")
