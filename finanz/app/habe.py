"""Vergleich mit Schweizer Haushalten: eigene Ausgaben pro Kategorie und Sparquote neben dem Mittel vergleichbarer
Haushalte aus der Haushaltsbudgeterhebung (HABE) des Bundesamts für Statistik.

Daten: BFS, HABE 2020–2021 (Stand September 2024), Tabellen «Haushaltseinkommen und -ausgaben nach Haushaltstyp»
(je-d-20.02.01.00.13) und «nach Einkommensklasse» (je-d-20.02.01.00.12); Franken pro Monat und Haushalt (Mittelwert),
dazu die Qualität der Schätzung (a sehr gut … e schlecht). Die Werte sind fest in der App – es geht nichts ins
Internet. In den Covid-Jahren 2020/21 waren Gastronomie, Ferien und Verkehr tiefer als üblich.
"""
from __future__ import annotations

from dataclasses import dataclass, field

QUELLE = "BFS, Haushaltsbudgeterhebung 2020–2021"
LINK = "https://statistik.admin.ch/de/themen/wirtschaftliche-soziale-situation-bevoelkerung/haushaltsbudget"
TYPEN = {"alle": "alle Haushalte", "allein_u65": "Einpersonenhaushalte unter 65", "allein_65": "Einpersonenhaushalte ab 65",
         "paar_u65": "Paare unter 65 ohne Kinder", "paar_65": "Paare ab 65 ohne Kinder",
         "eineltern": "Einelternhaushalte", "paar_kinder": "Paare mit Kindern"}
KLASSEN = [(4669, "bis_4668", "unter CHF 4'669"), (7005, "4669_7004", "CHF 4'669–7'004"),
           (9734, "7005_9733", "CHF 7'005–9'733"), (13717, "9734_13716", "CHF 9'734–13'716"),
           (10 ** 9, "ab_13717", "ab CHF 13'717")]
# App-Kategorie (budget.KATEGORIEN) → HABE-Positionen
ZUORDNUNG = {
    "Wohnen": ("wohnen",), "Lebensmittel": ("nahrung", "alkohol"), "Mobilität": ("verkehr",),
    "Gesundheit": ("gesundheit",), "Telekom und Abos": ("kommunikation",), "Freizeit und Ferien": ("freizeit", "gastro"),
    "Einkäufe": ("bekleidung", "einrichtung", "andere"), "Steuern": ("steuern",), "Krankenkasse": ("kk_grund", "kk_zusatz"),
    "Versicherungen": ("versicherungen",), "Spenden": ("spenden",), "Gebühren und Zinsen": ("gebuehren",),
}
NICHT_VERGLEICHBAR = ("Kinder und Betreuung", "Bargeld", "Kreditkarte", "Übriges")

DATEN = {'einkommen': {'alle': {'brutto': (9792, 'a'),
                        'sozialversicherung': (989, 'b'),
                        'steuern': (1201, 'b'),
                        'kk_grund': (670, 'a'),
                        'verfuegbar': (6744, 'a'),
                        'kk_zusatz': (158, 'b'),
                        'versicherungen': (159, 'b'),
                        'gebuehren': (53, 'c'),
                        'spenden': (150, 'c'),
                        'konsum': (4657, 'a'),
                        'nahrung': (665, 'a'),
                        'alkohol': (111, 'c'),
                        'gastro': (388, 'b'),
                        'bekleidung': (152, 'c'),
                        'wohnen': (1383, 'a'),
                        'einrichtung': (219, 'c'),
                        'gesundheit': (209, 'c'),
                        'verkehr': (655, 'b'),
                        'kommunikation': (172, 'a'),
                        'freizeit': (408, 'b'),
                        'andere': (296, 'c'),
                        'sparbetrag': (1712, 'c'),
                        'personen': (2.1, 'a')},
               'bis_4668': {'brutto': (3260, 'b'),
                            'sozialversicherung': (101, 'd'),
                            'steuern': (407, 'd'),
                            'kk_grund': (536, 'b'),
                            'verfuegbar': (2156, 'b'),
                            'kk_zusatz': (85, 'd'),
                            'versicherungen': (88, 'c'),
                            'gebuehren': (26, 'd'),
                            'spenden': (81, 'd'),
                            'konsum': (2651, 'b'),
                            'nahrung': (435, 'c'),
                            'alkohol': (73, 'd'),
                            'gastro': (138, 'c'),
                            'bekleidung': (67, 'd'),
                            'wohnen': (1049, 'b'),
                            'einrichtung': (103, 'd'),
                            'gesundheit': (141, 'd'),
                            'verkehr': (235, 'c'),
                            'kommunikation': (119, 'c'),
                            'freizeit': (186, 'd'),
                            'andere': (106, 'd'),
                            'sparbetrag': (-690, 'e'),
                            'personen': (1.29, 'b')},
               '4669_7004': {'brutto': (5857, 'a'),
                             'sozialversicherung': (401, 'c'),
                             'steuern': (646, 'c'),
                             'kk_grund': (573, 'b'),
                             'verfuegbar': (4078, 'b'),
                             'kk_zusatz': (119, 'c'),
                             'versicherungen': (130, 'c'),
                             'gebuehren': (37, 'c'),
                             'spenden': (119, 'd'),
                             'konsum': (3524, 'b'),
                             'nahrung': (521, 'b'),
                             'alkohol': (86, 'd'),
                             'gastro': (242, 'c'),
                             'bekleidung': (88, 'c'),
                             'wohnen': (1216, 'b'),
                             'einrichtung': (137, 'c'),
                             'gesundheit': (188, 'd'),
                             'verkehr': (485, 'd'),
                             'kommunikation': (149, 'b'),
                             'freizeit': (256, 'c'),
                             'andere': (155, 'd'),
                             'sparbetrag': (275, 'e'),
                             'personen': (1.59, 'b')},
               '7005_9733': {'brutto': (8284, 'a'),
                             'sozialversicherung': (736, 'c'),
                             'steuern': (914, 'c'),
                             'kk_grund': (662, 'b'),
                             'verfuegbar': (5762, 'a'),
                             'kk_zusatz': (158, 'c'),
                             'versicherungen': (153, 'b'),
                             'gebuehren': (56, 'd'),
                             'spenden': (152, 'd'),
                             'konsum': (4273, 'b'),
                             'nahrung': (625, 'b'),
                             'alkohol': (111, 'd'),
                             'gastro': (324, 'c'),
                             'bekleidung': (130, 'c'),
                             'wohnen': (1337, 'b'),
                             'einrichtung': (171, 'c'),
                             'gesundheit': (200, 'c'),
                             'verkehr': (580, 'c'),
                             'kommunikation': (170, 'b'),
                             'freizeit': (363, 'c'),
                             'andere': (263, 'e'),
                             'sparbetrag': (1113, 'd'),
                             'personen': (2.08, 'b')},
               '9734_13716': {'brutto': (11438, 'a'),
                              'sozialversicherung': (1262, 'b'),
                              'steuern': (1230, 'c'),
                              'kk_grund': (756, 'b'),
                              'verfuegbar': (8000, 'a'),
                              'kk_zusatz': (185, 'c'),
                              'versicherungen': (189, 'c'),
                              'gebuehren': (65, 'c'),
                              'spenden': (150, 'd'),
                              'konsum': (5408, 'b'),
                              'nahrung': (779, 'b'),
                              'alkohol': (125, 'd'),
                              'gastro': (461, 'c'),
                              'bekleidung': (185, 'c'),
                              'wohnen': (1535, 'b'),
                              'einrichtung': (252, 'c'),
                              'gesundheit': (232, 'c'),
                              'verkehr': (804, 'c'),
                              'kommunikation': (198, 'b'),
                              'freizeit': (484, 'c'),
                              'andere': (353, 'c'),
                              'sparbetrag': (2153, 'c'),
                              'personen': (2.65, 'b')},
               'ab_13717': {'brutto': (20117, 'b'),
                            'sozialversicherung': (2442, 'c'),
                            'steuern': (2807, 'c'),
                            'kk_grund': (822, 'b'),
                            'verfuegbar': (13717, 'b'),
                            'kk_zusatz': (242, 'c'),
                            'versicherungen': (236, 'c'),
                            'gebuehren': (84, 'c'),
                            'spenden': (248, 'd'),
                            'konsum': (7427, 'b'),
                            'nahrung': (963, 'b'),
                            'alkohol': (161, 'd'),
                            'gastro': (774, 'c'),
                            'bekleidung': (288, 'c'),
                            'wohnen': (1777, 'b'),
                            'einrichtung': (432, 'c'),
                            'gesundheit': (283, 'c'),
                            'verkehr': (1168, 'c'),
                            'kommunikation': (225, 'b'),
                            'freizeit': (752, 'c'),
                            'andere': (604, 'c'),
                            'sparbetrag': (5704, 'c'),
                            'personen': (2.9, 'b')}},
 'typ': {'alle': {'brutto': (9792, 'a'),
                  'sozialversicherung': (989, 'b'),
                  'steuern': (1201, 'b'),
                  'kk_grund': (670, 'a'),
                  'verfuegbar': (6744, 'a'),
                  'kk_zusatz': (158, 'b'),
                  'versicherungen': (159, 'b'),
                  'gebuehren': (53, 'c'),
                  'spenden': (150, 'c'),
                  'konsum': (4657, 'a'),
                  'nahrung': (665, 'a'),
                  'alkohol': (111, 'c'),
                  'gastro': (388, 'b'),
                  'bekleidung': (152, 'c'),
                  'wohnen': (1383, 'a'),
                  'einrichtung': (219, 'c'),
                  'gesundheit': (209, 'c'),
                  'verkehr': (655, 'b'),
                  'kommunikation': (172, 'a'),
                  'freizeit': (408, 'b'),
                  'andere': (296, 'c'),
                  'sparbetrag': (1712, 'c'),
                  'personen': (2.1, 'a')},
         'allein_u65': {'brutto': (6779, 'b'),
                        'sozialversicherung': (816, 'c'),
                        'steuern': (797, 'c'),
                        'kk_grund': (364, 'b'),
                        'verfuegbar': (4592, 'b'),
                        'kk_zusatz': (71, 'c'),
                        'versicherungen': (103, 'c'),
                        'gebuehren': (36, 'd'),
                        'spenden': (143, 'd'),
                        'konsum': (3350, 'b'),
                        'nahrung': (387, 'b'),
                        'alkohol': (90, 'd'),
                        'gastro': (284, 'c'),
                        'bekleidung': (87, 'c'),
                        'wohnen': (1277, 'b'),
                        'einrichtung': (116, 'd'),
                        'gesundheit': (111, 'd'),
                        'verkehr': (465, 'd'),
                        'kommunikation': (130, 'b'),
                        'freizeit': (254, 'c'),
                        'andere': (150, 'd'),
                        'sparbetrag': (999, 'd'),
                        'personen': (1, 'a')},
         'allein_65': {'brutto': (4912, 'c'),
                       'sozialversicherung': (20, 'e'),
                       'steuern': (902, 'd'),
                       'kk_grund': (454, 'b'),
                       'verfuegbar': (3381, 'c'),
                       'kk_zusatz': (129, 'c'),
                       'versicherungen': (100, 'c'),
                       'gebuehren': (24, 'd'),
                       'spenden': (165, 'e'),
                       'konsum': (2844, 'b'),
                       'nahrung': (412, 'c'),
                       'alkohol': (71, 'e'),
                       'gastro': (164, 'd'),
                       'bekleidung': (69, 'd'),
                       'wohnen': (1065, 'c'),
                       'einrichtung': (123, 'd'),
                       'gesundheit': (196, 'd'),
                       'verkehr': (257, 'd'),
                       'kommunikation': (116, 'c'),
                       'freizeit': (213, 'c'),
                       'andere': (156, 'd'),
                       'sparbetrag': (236, 'e'),
                       'personen': (1, 'a')},
         'paar_u65': {'brutto': (13260, 'b'),
                      'sozialversicherung': (1696, 'c'),
                      'steuern': (1591, 'c'),
                      'kk_grund': (689, 'b'),
                      'verfuegbar': (9098, 'b'),
                      'kk_zusatz': (151, 'c'),
                      'versicherungen': (194, 'c'),
                      'gebuehren': (69, 'c'),
                      'spenden': (183, 'e'),
                      'konsum': (5540, 'b'),
                      'nahrung': (716, 'b'),
                      'alkohol': (148, 'd'),
                      'gastro': (553, 'c'),
                      'bekleidung': (184, 'c'),
                      'wohnen': (1575, 'b'),
                      'einrichtung': (287, 'c'),
                      'gesundheit': (226, 'd'),
                      'verkehr': (881, 'c'),
                      'kommunikation': (194, 'b'),
                      'freizeit': (510, 'c'),
                      'andere': (267, 'c'),
                      'sparbetrag': (3096, 'c'),
                      'personen': (2, 'a')},
         'paar_65': {'brutto': (8551, 'c'),
                     'sozialversicherung': (159, 'e'),
                     'steuern': (1477, 'c'),
                     'kk_grund': (864, 'a'),
                     'verfuegbar': (5734, 'c'),
                     'kk_zusatz': (268, 'c'),
                     'versicherungen': (194, 'b'),
                     'gebuehren': (55, 'c'),
                     'spenden': (163, 'd'),
                     'konsum': (4634, 'c'),
                     'nahrung': (795, 'b'),
                     'alkohol': (164, 'e'),
                     'gastro': (360, 'c'),
                     'bekleidung': (124, 'd'),
                     'wohnen': (1111, 'c'),
                     'einrichtung': (260, 'd'),
                     'gesundheit': (309, 'c'),
                     'verkehr': (598, 'd'),
                     'kommunikation': (167, 'b'),
                     'freizeit': (447, 'd'),
                     'andere': (299, 'e'),
                     'sparbetrag': (611, 'e'),
                     'personen': (2, 'a')},
         'eineltern': {'brutto': (8765, 'c'),
                       'sozialversicherung': (793, 'd'),
                       'steuern': (778, 'e'),
                       'kk_grund': (705, 'c'),
                       'verfuegbar': (6252, 'c'),
                       'kk_zusatz': (135, 'd'),
                       'versicherungen': (128, 'd'),
                       'gebuehren': (43, 'd'),
                       'spenden': (110, 'd'),
                       'konsum': (4729, 'c'),
                       'nahrung': (648, 'c'),
                       'alkohol': (75, 'e'),
                       'gastro': (306, 'd'),
                       'bekleidung': (155, 'd'),
                       'wohnen': (1593, 'c'),
                       'einrichtung': (161, 'd'),
                       'gesundheit': (209, 'd'),
                       'verkehr': (605, 'd'),
                       'kommunikation': (198, 'c'),
                       'freizeit': (420, 'd'),
                       'andere': (359, 'e'),
                       'sparbetrag': (1283, 'e'),
                       'personen': (2.57, 'c')},
         'paar_kinder': {'brutto': (14133, 'b'),
                         'sozialversicherung': (1765, 'c'),
                         'steuern': (1420, 'c'),
                         'kk_grund': (917, 'a'),
                         'verfuegbar': (9921, 'b'),
                         'kk_zusatz': (203, 'c'),
                         'versicherungen': (209, 'c'),
                         'gebuehren': (80, 'd'),
                         'spenden': (126, 'd'),
                         'konsum': (6399, 'b'),
                         'nahrung': (968, 'b'),
                         'alkohol': (101, 'd'),
                         'gastro': (553, 'c'),
                         'bekleidung': (259, 'c'),
                         'wohnen': (1626, 'b'),
                         'einrichtung': (322, 'c'),
                         'gesundheit': (243, 'c'),
                         'verkehr': (960, 'c'),
                         'kommunikation': (225, 'b'),
                         'freizeit': (595, 'c'),
                         'andere': (547, 'c'),
                         'sparbetrag': (3083, 'c'),
                         'personen': (3.82, 'a')}}}


def haushaltstyp(k: dict, jahr: int) -> str:
    import kinder as ki
    import vorsorge as vs
    personen = k.get("personen") or []
    kinder = [c for c in ki.liste(k) if ki.unterhalt(c, jahr)]
    aeltester = max((jahr - vs.geburtsjahr(p) for p in personen), default=40)
    if kinder:
        return "paar_kinder" if len(personen) >= 2 else "eineltern"
    if len(personen) >= 2:
        return "paar_65" if aeltester >= 65 else "paar_u65"
    return "allein_65" if aeltester >= 65 else "allein_u65"


def einkommensklasse(brutto_monat: float) -> tuple[str, str]:
    for grenze, schl, text in KLASSEN:
        if brutto_monat < grenze:
            return schl, text
    return KLASSEN[-1][1], KLASSEN[-1][2]


@dataclass
class Zeile:
    kategorie: str
    eigen: float                   # pro Monat
    typ: float                     # Mittel gleicher Haushaltstyp
    klasse: float                  # Mittel gleiche Einkommensklasse
    unsicher: bool                 # Schätzung des BFS mit Qualität «e»
    abweichung: float | None       # % gegenüber dem Mittel beider Vergleichsgruppen


@dataclass
class Vergleich:
    typ: str
    klasse: str
    brutto_monat: float
    zeilen: list[Zeile]
    sparquote: float | None        # eigene, % der Einnahmen
    sparquote_typ: float
    sparquote_klasse: float
    hinweise: list[str] = field(default_factory=list)
    monate: int = 0


def _summe(gruppe: dict, posten: tuple[str, ...]) -> tuple[float, bool]:
    werte = [gruppe.get(p, (0, "")) for p in posten]
    return float(sum(w[0] for w in werte)), any(w[1] == "e" for w in werte)


def _sparquote(g: dict) -> float:
    netto = g["brutto"][0] - g["sozialversicherung"][0]
    return round(g["sparbetrag"][0] / netto * 100, 1) if netto else 0.0


def vergleichen(k: dict, db, jahr: int | None = None) -> Vergleich | None:
    """Ausgaben der letzten (bis zu) 12 Monate aus dem Budget neben vergleichbaren Haushalten."""
    from datetime import date
    import budget as bu
    a = bu.auswerten(k, db)
    if not a or not a.ausgaben:
        return None
    jahr = jahr or date.today().year
    brutto = sum(float(p.get("lohn_brutto") or 0) for p in k.get("personen") or []) / 12
    if not brutto:
        brutto = a.einnahmen / 12 * 1.12                # Nettoeinnahmen grob auf brutto hochrechnen
    t = haushaltstyp(k, jahr)
    kl, kl_text = einkommensklasse(brutto)
    gt, gk = DATEN["typ"][t], DATEN["einkommen"][kl]
    eigene = {n: v / 12 for n, v, _ in a.kategorien}
    zeilen = []
    for kat, posten in ZUORDNUNG.items():
        st, ut = _summe(gt, posten)
        sk, uk = _summe(gk, posten)
        e = eigene.get(kat, 0.0)
        mittel = (st + sk) / 2
        abw = round((e - mittel) / mittel * 100) if mittel >= 20 and e else None
        zeilen.append(Zeile(kat, round(e), round(st), round(sk), ut or uk, abw))
    sq = round((a.ueberschuss + a.sparen_konto) / a.einnahmen * 100, 1) if a.einnahmen else None
    v = Vergleich(TYPEN[t], kl_text, round(brutto), zeilen, sq, _sparquote(gt), _sparquote(gk), monate=a.monate)
    v.hinweise = _hinweise(v, eigene)
    return v


def _hinweise(v: Vergleich, eigene: dict) -> list[str]:
    h = []
    for z in v.zeilen:
        if z.abweichung is None or z.unsicher or z.kategorie in ("Steuern",):
            continue
        hoeher = z.eigen > 1.3 * max(z.typ, z.klasse) and z.eigen - max(z.typ, z.klasse) >= 100
        tiefer = z.eigen < 0.7 * min(z.typ, z.klasse) and min(z.typ, z.klasse) - z.eigen >= 100
        if hoeher:
            h.append(f"{z.kategorie}: CHF {z.eigen:,.0f} pro Monat – {z.abweichung:+d} % gegenüber vergleichbaren "
                     "Haushalten. Prüfen, ob sich hier sparen lässt.".replace(",", "'"))
        elif tiefer:
            h.append(f"{z.kategorie}: deutlich unter vergleichbaren Haushalten ({z.abweichung:+d} %) – oder Buchungen "
                     "fehlen bzw. sind anders kategorisiert.")
    if v.sparquote is not None:
        ref = (v.sparquote_typ + v.sparquote_klasse) / 2
        if v.sparquote < ref - 5:
            h.append(f"Sparquote {v.sparquote:.0f} % – vergleichbare Haushalte sparen im Mittel rund {ref:.0f} % ihres "
                     "Einkommens nach Sozialabzügen.")
        elif v.sparquote > ref + 5:
            h.append(f"Sparquote {v.sparquote:.0f} % – über dem Mittel vergleichbarer Haushalte (rund {ref:.0f} %).")
    anteil_offen = sum(eigene.get(x, 0) for x in NICHT_VERGLEICHBAR) / max(1, sum(eigene.values())) * 100
    if anteil_offen > 25:
        h.append(f"{anteil_offen:.0f} % der Ausgaben sind Bargeld, Kreditkarte oder ohne Kategorie – diese fehlen im "
                 "Vergleich, die übrigen Kategorien wirken dadurch tiefer.")
    if v.monate < 12:
        h.append(f"Erst {v.monate} Monate Buchungen – jährliche Rechnungen fehlen oder zählen doppelt.")
    return h
