"""Sparen für die Kinder: Bestand, Sparplan, Ziel und Empfehlung pro Kind.

- Bestand: Konten der Art «Kindersparen» mit dem Kind als Person (unter Vermögen). Sie zählen zum Nettovermögen,
  aber nicht zur Notreserve und nicht zum freien Vermögen der Eltern.
- Pro Kind unter `haushalt.kinder[]`: sparen_monat (CHF), sparen_ziel (CHF, leer = Vorschlag), sparen_alter (Zielalter,
  Standard 18), sparen_anlage (konto | fonds), sparen_rendite (% pro Jahr, leer = Standard).
- Vorschlag fürs Ziel: Ausbildungskosten ab der Sekundarstufe II laut Lebenslauf (Schulgeld, Material,
  Studiengebühren; auswärts studieren: Mehrkosten fürs Wohnen) plus CHF 5'000 Start (Führerausweis, Mietkaution).
- Wert am Ziel mit monatlichem Zinseszins; nötiger Betrag pro Monat für das Ziel; Anteil an der Kinderzulage.
- Anlage: Horizont unter 5 Jahren aufs Konto, ab 10 Jahren lohnt ein Fonds-Sparplan; 3–5 Jahre vor dem Ziel
  schrittweise in sichere Anlagen umschichten.

Recht und Steuern (Stand 2026):
- Konto auf den Namen des Kindes: Das Geld gehört dem Kind. Die Eltern verwalten es bis 18 (ZGB Art. 318); die
  Erträge dürfen für Unterhalt, Erziehung und Ausbildung verwendet werden, das Vermögen selbst nur mit Bewilligung
  der Kindesschutzbehörde (ZGB Art. 319 und 320). Ab 18 verfügt das Kind selbst.
- Konto auf den Namen der Eltern (mit Vermerk): bleibt Vermögen der Eltern, flexibel, fällt aber in Güterrecht und
  Nachlass.
- Steuern: Vermögen und Erträge minderjähriger Kinder werden den Eltern zugerechnet (DBG Art. 9 Abs. 2, StHG
  Art. 3 Abs. 3) – ausser Erwerbseinkommen.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

from dataclasses import dataclass, field
from datetime import date

START_BETRAG = 5000.0
ANLAGEN = {"konto": "Jugendsparkonto", "fonds": "Fonds-Sparplan (Aktien und Obligationen)"}
QUELLEN = [
    ("ZGB Art. 318–320: Kindesvermögen", "https://www.fedlex.admin.ch/eli/cc/24/233_245_233/de#art_318"),
    ("DBG Art. 9: Einkommen der Kinder", "https://www.fedlex.admin.ch/eli/cc/1991/1184_1184_1184/de#art_9"),
]


def _chf(v: float) -> str:
    return f"{v:,.0f}" >> TS


def _zahl(v, std: float | None = None) -> float | None:
    try:
        t = str(v).replace("'", "").replace(",", ".").strip()
        return float(t) if t else std
    except (TypeError, ValueError):
        return std


def wert_am_ziel(bestand: float, monat: float, monate: int, rendite: float) -> float:
    r = rendite / 100 / 12
    if monate <= 0:
        return bestand
    if not r:
        return bestand + monat * monate
    f = (1 + r) ** monate
    return bestand * f + monat * (f - 1) / r


def noetig(bestand: float, ziel: float, monate: int, rendite: float) -> float:
    if monate <= 0:
        return max(0.0, ziel - bestand)
    r = rendite / 100 / 12
    f = (1 + r) ** monate if r else 1.0
    rest = ziel - bestand * f
    if rest <= 0:
        return 0.0
    return rest / ((f - 1) / r) if r else rest / monate


@dataclass
class Plan:
    name: str
    alter: int
    bestand: float
    konten: list[str]
    monat: float
    anlage: str
    rendite: float
    ziel: float
    ziel_vorschlag: float
    ziel_eigen: bool
    ziel_alter: int
    ziel_datum: date
    monate: int
    wert: float                    # Wert am Ziel mit dem heutigen Sparplan
    noetig_monat: float            # für das Ziel nötig pro Monat
    zulage: float                  # Kinder- bzw. Ausbildungszulage pro Monat heute
    ausbildung: list[tuple[str, float]]   # Bestandteile des Vorschlags
    hinweise: list[str] = field(default_factory=list)

    @property
    def luecke(self) -> float:
        return max(0.0, round(self.ziel - self.wert))

    @property
    def jahre(self) -> float:
        return self.monate / 12


def _bestand(k: dict, db, name: str) -> tuple[float, list[str]]:
    if db is None:
        return 0.0, []
    import vermoegen as vm
    from versicherungen import gleiche_person
    ks = [x for x in vm.konten(db) if x["art"] == "kindersparen" and not x.get("aufgeloest")
          and x.get("person") and gleiche_person(x["person"], name)]
    return sum(max(0.0, x["wert"]) for x in ks), [x["name"] for x in ks]


def vorschlag(k: dict, kind: dict, anzahl: int, heute: date) -> list[tuple[str, float]]:
    import kinderphasen as kp
    lauf = kp.von(kind, anzahl, heute)
    teile = []
    if lauf:
        rang = kp._rang(anzahl)
        for p in lauf.phasen:
            if p.schluessel not in ("lehre", "gymnasium", "fms", "studium", "fh") or p.bis <= heute:
                continue
            monate = p.monate if p.von >= heute else kp._monate(heute, p.bis)
            if p.betreuung:
                teile.append((f"{p.titel}: Schulgeld, Material, Gebühren", p.betreuung * monate))
            if p.schluessel in ("studium", "fh") and kind.get("auswaerts"):
                mehr = p.leben - kp.LEBEN[13][rang]
                if mehr > 0:
                    teile.append((f"{p.titel}: Mehrkosten auswärts wohnen", mehr * monate))
    teile.append(("Start: Führerausweis, Mietkaution, erste Einrichtung", START_BETRAG))
    return [(t, round(b, -2)) for t, b in teile]


def plaene(k: dict, db=None, heute: date | None = None) -> list[Plan]:
    import anlage as an
    import kinder as ki
    heute = heute or date.today()
    liste = ki.liste(k)
    cfg = an.konfiguration(k)
    erg = []
    for kind in liste:
        geburt = ki.geburt(kind)
        if not geburt:
            continue
        alter = heute.year - geburt.year - ((heute.month, heute.day) < (geburt.month, geburt.day))
        ziel_alter = int(_zahl(kind.get("sparen_alter"), 18) or 18)
        try:
            ziel_datum = geburt.replace(year=geburt.year + ziel_alter)
        except ValueError:                                # 29. Februar
            ziel_datum = date(geburt.year + ziel_alter, 3, 1)
        if ziel_datum <= heute or alter < 0:
            continue
        monate = (ziel_datum.year - heute.year) * 12 + ziel_datum.month - heute.month
        bestand, konten = _bestand(k, db, kind["name"])
        monat = _zahl(kind.get("sparen_monat"), 0.0) or 0.0
        anlage = str(kind.get("sparen_anlage") or "")
        if anlage not in ANLAGEN:
            anlage = "fonds" if monate >= 120 else "konto"
        std = cfg["rendite"]["mittel"] if anlage == "fonds" else max(float(cfg["zins_konto"]), 0.5)
        rendite = _zahl(kind.get("sparen_rendite"), std)
        teile = vorschlag(k, kind, len(liste), heute)
        vor = sum(b for _, b in teile)
        ziel_eigen = _zahl(kind.get("sparen_ziel"), 0.0) or 0.0
        ziel = ziel_eigen or vor
        jahr_alter = ki.alter(kind, heute.year)
        zulage = ki.zulage_jahr(kind, heute.year) / 12 if jahr_alter >= 0 else 0.0
        p = Plan(kind["name"], alter, round(bestand), konten, monat, anlage, rendite, round(ziel), round(vor),
                 bool(ziel_eigen), ziel_alter, ziel_datum, monate, round(wert_am_ziel(bestand, monat, monate, rendite)),
                 round(noetig(bestand, ziel, monate, rendite)), round(zulage), teile)
        h = p.hinweise
        if not monat and not bestand:
            h.append(f"Noch kein Sparplan: für CHF {_chf(ziel)} bis {ziel_datum:%m.%Y} braucht es rund "
                     f"CHF {_chf(p.noetig_monat)} pro Monat" + (f" ({p.noetig_monat / zulage * 100:.0f} % der Zulage)."
                                                                 if zulage else "."))
        elif p.luecke:
            h.append(f"Mit CHF {_chf(monat)} pro Monat fehlen am Ziel rund CHF {_chf(p.luecke)} – CHF "
                     f"{_chf(p.noetig_monat)} pro Monat würden reichen.")
        else:
            h.append(f"Ziel erreicht: rund CHF {_chf(p.wert)} am {ziel_datum:%d.%m.%Y}.")
        if anlage == "konto" and monate >= 120:
            mehr = wert_am_ziel(bestand, monat or p.noetig_monat, monate, cfg["rendite"]["mittel"]) \
                - wert_am_ziel(bestand, monat or p.noetig_monat, monate, rendite)
            if mehr >= 1000:
                h.append(f"Noch {monate // 12} Jahre: ein Fonds-Sparplan brächte bei {cfg['rendite']['mittel']:g} % rund "
                         f"CHF {_chf(mehr)} mehr als das Konto – mit Schwankungen.")
        if anlage == "fonds" and monate < 60:
            h.append("Weniger als 5 Jahre bis zum Ziel: schrittweise vom Fonds aufs Konto umschichten, damit ein "
                     "Börsentief das Geld nicht kurz vor dem Bedarf trifft.")
        if not konten and (bestand or monat):
            h.append("Konto unter «Vermögen» mit der Art «Kindersparen» und dem Kind als Person erfassen – dann zählt "
                     "der Bestand hier mit und nicht zur Notreserve.")
        erg.append(p)
    return erg


def monat_total(ps: list[Plan]) -> float:
    return round(sum(p.monat for p in ps))


def erinnerungen(k: dict, db, heute: date) -> list:
    import erinnerungen as er
    erg = []
    for p in plaene(k, db, heute):
        tage = (p.ziel_datum - heute).days
        if p.bestand and p.ziel_alter == 18 and 0 <= tage <= 60:
            erg.append(er.Erinnerung(f"kindersparen-18-{p.name}-{p.ziel_datum.year}", f"{p.name} wird 18: Kindersparen",
                                     p.ziel_datum, f"CHF {_chf(p.bestand)} – ab 18 verfügt {p.name} selbst über Konten auf "
                                     "eigenen Namen. Übergabe, Zweck und Unterschriften mit der Bank klären.", "kinder"))
        if p.anlage == "fonds" and p.bestand and 0 <= tage - 5 * 365 <= 60:
            erg.append(er.Erinnerung(f"kindersparen-umschichten-{p.name}-{p.ziel_datum.year}",
                                     f"Kindersparen {p.name}: umschichten", p.ziel_datum.replace(year=p.ziel_datum.year - 5)
                                     if not (p.ziel_datum.month == 2 and p.ziel_datum.day == 29) else
                                     date(p.ziel_datum.year - 5, 3, 1),
                                     "Noch 5 Jahre bis zum Ziel: den Fonds-Sparplan schrittweise aufs Konto umschichten.",
                                     "kinder"))
    return erg
