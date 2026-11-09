"""Krankenkasse: Franchise und Modell der Grundversicherung optimieren.

Kosten pro Jahr = Prämie + Franchise (soweit Kosten anfallen) + Selbstbehalt 10 % (höchstens 700, Kinder 350).
Fehlen Prämien für andere Franchisen, schätzt die App sie mit dem gesetzlichen Höchstrabatt (Art. 95 KVV):
Rabatt = 70 % des Risikounterschieds zur Grundfranchise, höchstens 50 % der Prämie mit Grundfranchise.
Die meisten Kassen geben diesen Höchstrabatt bei hohen Franchisen weitgehend weiter.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

import re
from datetime import date
from dataclasses import dataclass, field

FRANCHISEN_ERWACHSENE = [300, 500, 1000, 1500, 2000, 2500]
FRANCHISEN_KINDER = [0, 100, 200, 300, 400, 500, 600]
SELBSTBEHALT_MAX = {"erwachsen": 700, "kind": 350}
KOSTEN_STUFEN = [0, 500, 1000, 2000, 3000, 5000, 10000, 20000]
MODELLE = {"standard": "Standard (freie Arztwahl)", "hausarzt": "Hausarzt", "telmed": "Telmed", "hmo": "HMO"}


@dataclass
class Person:
    name: str
    kind: bool
    franchise: int
    praemie_monat: float
    kosten_jahr: float
    modell: str
    unfall: bool
    angestellt: bool
    angebote: dict[int, float] = field(default_factory=dict)   # Franchise → Prämie pro Monat (eigene Offerten)
    unfall_praemie: float = 0.0          # Unfallanteil bzw. -reduktion pro Jahr laut Police
    versicherer: str = ""
    anlaufstelle: str = ""
    zusatz_monat: float = 0.0            # Zusatzversicherungen pro Monat
    zusatz: str = ""


@dataclass
class Ergebnis:
    person: Person
    franchisen: list[int]
    praemien: dict[int, float]                   # pro Jahr
    kosten: dict[int, float]                     # pro Jahr bei den erwarteten Kosten
    beste: int
    ersparnis: float                             # gegenüber heute pro Jahr
    break_even: list[tuple[int, int, float]]     # (Franchise tief, hoch, Gesundheitskosten, ab denen tief günstiger ist)
    tabelle: dict[int, dict[int, float]]         # Kosten-Stufe → Franchise → Gesamtkosten
    hinweise: list[str] = field(default_factory=list)
    geschaetzt: bool = True


def kostenbeteiligung(kosten: float, franchise: int, kind: bool) -> float:
    k = max(0.0, kosten)
    return min(k, franchise) + min(0.1 * max(0.0, k - franchise), SELBSTBEHALT_MAX["kind" if kind else "erwachsen"])


def praemien(p: Person) -> tuple[dict[int, float], bool]:
    """Jahresprämie je Franchise: eigene Offerten, sonst Schätzung mit dem Höchstrabatt."""
    liste = FRANCHISEN_KINDER if p.kind else FRANCHISEN_ERWACHSENE
    fmin = liste[0]

    def rabatt(f: int, basis: float) -> float:
        return min(0.7 * (f - fmin), 0.5 * basis)

    jahr = p.praemie_monat * 12
    # Prämie bei Grundfranchise zurückrechnen: P(F) = P0 − min(0.7 (F − Fmin), 0.5 P0)
    p0 = jahr + 0.7 * (p.franchise - fmin)
    if 0.7 * (p.franchise - fmin) > 0.5 * p0:
        p0 = jahr * 2
    erg = {f: round(max(0.0, p0 - rabatt(f, p0)), 2) for f in liste}
    for f, monat in (p.angebote or {}).items():
        if int(f) in erg and float(monat) > 0:
            erg[int(f)] = round(float(monat) * 12, 2)
    erg[p.franchise] = round(jahr, 2)
    return erg, not p.angebote


def rechnen(p: Person, rabatt_modell: float = 12.0, unfall_anteil: float = 7.0) -> Ergebnis:
    liste = FRANCHISEN_KINDER if p.kind else FRANCHISEN_ERWACHSENE
    pr, geschaetzt = praemien(p)
    kosten = {f: round(pr[f] + kostenbeteiligung(p.kosten_jahr, f, p.kind)) for f in liste}
    beste = min(liste, key=lambda f: (kosten[f], -f))
    heute = kosten.get(p.franchise, kosten[beste])
    tab = {k: {f: round(pr[f] + kostenbeteiligung(k, f, p.kind)) for f in liste} for k in KOSTEN_STUFEN}
    # Break-even zwischen tiefster und höchster Franchise: ab welchen Kosten lohnt die tiefe?
    be = []
    tief, hoch = liste[0], liste[-1]
    for k in range(0, 30001, 50):
        if pr[tief] + kostenbeteiligung(k, tief, p.kind) <= pr[hoch] + kostenbeteiligung(k, hoch, p.kind):
            be.append((tief, hoch, float(k)))
            break
    hinw = []
    if beste != p.franchise and heute - kosten[beste] >= 50:
        if p.kosten_jahr:
            hinw.append(f"{p.name}: Franchise {beste} statt {p.franchise} spart bei Kosten von rund CHF {p.kosten_jahr:,.0f} "
                        f"etwa CHF {heute - kosten[beste]:,.0f} pro Jahr." >> TS)
        else:
            hinw.append(f"{p.name}: Ohne Arztkosten wäre Franchise {beste} statt {p.franchise} rund CHF "
                        f"{heute - kosten[beste]:,.0f} pro Jahr günstiger – erwartete Gesundheitskosten eintragen (z. B. aus "
                        "der Leistungsübersicht des Vorjahres), dann rechnet die Empfehlung damit." >> TS)
    if be:
        hinw.append(f"{p.name}: Die tiefste Franchise lohnt sich erst ab Gesundheitskosten von rund CHF {be[0][2]:,.0f} pro Jahr."
                     >> TS)
    if p.modell == "standard":
        spar = pr[p.franchise] * rabatt_modell / 100
        hinw.append(f"{p.name}: Ein Hausarzt-, HMO- oder Telmed-Modell ist typischerweise {rabatt_modell:.0f} % günstiger "
                    f"(rund CHF {spar:,.0f} pro Jahr)" + (" – auch für Kinder, mit der Kinderärztin als erster Anlaufstelle."
                                                         if p.kind else ".") >> TS)
    if p.unfall and p.angestellt and not p.kind:
        spar = p.unfall_praemie or pr[beste] * unfall_anteil / 100
        hinw.append(f"{p.name}: Unfalldeckung sistieren (über den Arbeitgeber versichert) spart rund CHF {spar:,.0f} pro Jahr."
                     >> TS)
    if not p.unfall and not p.kind:
        if p.angestellt:
            hinw.append(f"{p.name}: Ohne Unfalldeckung – richtig, solange mindestens 8 Stunden pro Woche beim gleichen "
                        "Arbeitgeber angestellt (Nichtberufsunfall über den Arbeitgeber). Bei tieferem Pensum, Stellenwechsel, "
                        "Arbeitslosigkeit oder unbezahltem Urlaub innert 30 Tagen wieder einschliessen.")
        else:
            hinw.append(f"{p.name}: Ohne Unfalldeckung, aber kein Lohn erfasst – ohne Anstellung (mind. 8 Std./Woche) "
                        "muss die Unfalldeckung in der Grundversicherung eingeschlossen sein.")

    if not p.kind and beste == 300 and p.kosten_jahr < 2000:
        hinw.append(f"{p.name}: Bei schwankenden Kosten prüfen, ob eine Reserve für die hohe Franchise vorhanden ist.")
    return Ergebnis(p, liste, pr, kosten, beste, round(max(0.0, heute - kosten[beste])), be, tab, hinw, geschaetzt)


def _alter(geburtsdatum: str, jahr: int) -> int | None:
    try:
        return jahr - int(str(geburtsdatum)[:4])
    except ValueError:
        return None


def personen(k: dict, vertraege: list[dict]) -> list[Person]:
    """Aus der Konfiguration (krankenkasse.personen), ergänzt um die KVG- und VVG-Policen."""
    import kinder as ki
    import versicherungen as vi

    cfg = (k.get("krankenkasse") or {}).get("personen") or []
    loehne = {p["name"]: float(p.get("lohn_brutto", 0)) for p in k["personen"]}
    alle_kinder = ki.liste(k)
    jahr = date.today().year
    kinder = {c["name"] for c in alle_kinder if ki.alter(c, jahr) < 19}          # Kinderprämie und -franchisen bis 18
    namen = [p["name"] for p in k["personen"]] + [c["name"] for c in alle_kinder]
    for e in cfg:                                   # z. B. Kinder, die nur aus einer Police bekannt sind
        n = str(e.get("name", "")).strip()
        if n and not any(vi.gleiche_person(n, x) for x in namen):
            namen.append(n)
    kvg = [v for v in vertraege if v["sparte"] == "kvg"]
    vvg = [v for v in vertraege if v["sparte"] == "vvg"]

    def police_von(liste, name):
        treffer = [v for v in liste if vi.gleiche_person(v["person"], name)]
        return max(treffer, key=lambda v: (v.get("beginn") or "", v["id"])) if treffer else None
    erg = []
    for name in namen:
        eintrag = next((e for e in cfg if vi.gleiche_person(str(e.get("name", "")), name)), None)
        alias = str((eintrag or {}).get("police_person") or "")
        police = police_von(kvg, name) or (police_von(kvg, alias) if alias else None)
        alter = _alter((police or {}).get("geburtsdatum") or "", jahr) if police else None
        kind = name in kinder or (alter is not None and alter < 19) or bool((eintrag or {}).get("kind"))
        if eintrag:
            franchise = int(eintrag.get("franchise", 0 if kind else 300))
            praemie = float(eintrag.get("praemie_monat", 0))
            modell = str(eintrag.get("modell", "standard"))
            unfall = bool(eintrag.get("unfall", kind))
            kosten = float(eintrag.get("kosten_jahr", 0))
            angebote = {int(f): float(v) for f, v in (eintrag.get("angebote") or {}).items()}
        elif police:
            franchise = int(police["franchise"] or (0 if kind else 300))
            praemie = float(police["praemie_jahr"] or 0) / 12
            modell = police.get("modell") or "standard"
            unfall, kosten, angebote = bool(police["unfall_eingeschlossen"]), 0.0, {}
        else:
            franchise, praemie, modell, unfall, kosten, angebote = (0 if kind else 300), 0.0, "standard", kind, 0.0, {}
        liste = FRANCHISEN_KINDER if kind else FRANCHISEN_ERWACHSENE
        if franchise not in liste:
            franchise = min(liste, key=lambda f: abs(f - franchise))
        anlauf = ""
        if police:
            m = re.search(r"Erste Anlaufstelle: ([^;]+)", police.get("notiz") or "")
            anlauf = m.group(1).strip() if m else ""
        z = police_von(vvg, name) or (police_von(vvg, alias) if alias else None)
        erg.append(Person(name, kind, franchise, praemie, kosten, modell, unfall, loehne.get(name, 0) > 0, angebote,
                          float((police or {}).get("unfall_praemie") or 0), (police or {}).get("versicherer") or "",
                          anlauf, round(float(z["praemie_jahr"] or 0) / 12, 2) if z else 0.0,
                          (z.get("produkte") or z.get("notiz") or "") if z else ""))
    return erg


def police_uebernehmen(k: dict, v: dict) -> str | None:
    """Werte einer KVG-Police in den Krankenkassen-Rechner (krankenkasse.personen) übernehmen."""
    import kinder as ki
    import versicherungen as vi
    if v.get("sparte") != "kvg" or not v.get("person"):
        return None
    namen = [p["name"] for p in k["personen"]] + [c["name"] for c in ki.liste(k)]
    cfg = k.setdefault("krankenkasse", {}).setdefault("personen", [])
    name = next((n for n in namen if vi.gleiche_person(n, v["person"])), None)
    name = name or next((str(e.get("name")) for e in cfg if vi.gleiche_person(str(e.get("name", "")), v["person"])), None)
    alter = _alter(v.get("geburtsdatum") or "", date.today().year)
    if not name and alter is not None and alter < 19:
        # Kind unter anderem Namen erfasst (z. B. «Sohn»): das einzige Kind ohne Police nehmen
        kinder = [n for n in [c["name"] for c in ki.liste(k)] + [str(e.get("name")) for e in cfg if e.get("kind")]
                  if n] or [str(e.get("name")) for e in cfg
                            if str(e.get("name")) not in [p["name"] for p in k["personen"]]]
        kinder = list(dict.fromkeys(kinder))
        if len(kinder) == 1:
            name = kinder[0]
    name = name or v["person"]
    eintrag = next((e for e in cfg if vi.gleiche_person(str(e.get("name", "")), name)), None)
    if eintrag is None:
        eintrag = {"name": name, "kosten_jahr": 0}
        cfg.append(eintrag)
    eintrag.update(praemie_monat=round(float(v["praemie_jahr"] or 0) / 12, 2), franchise=int(v["franchise"] or 0),
                   modell=v.get("modell") or eintrag.get("modell", "standard"), unfall=bool(v["unfall_eingeschlossen"]),
                   police_person=v["person"])
    if alter is not None:
        eintrag["kind"] = alter < 19
    return name


def haushalt_hinweise(k: dict, vertraege: list[dict], heute: date | None = None) -> list[str]:
    """Vergleiche über den Haushalt: Modelle bei gleicher Kasse, Fristen, Zusatzversicherungen."""
    heute = heute or date.today()
    ps = personen(k, vertraege)
    hinw = []
    erw = [p for p in ps if not p.kind and p.praemie_monat > 0]
    for a in erw:
        for b in erw:
            if (a is not b and a.versicherer and a.versicherer == b.versicherer and a.franchise == b.franchise
                    and a.unfall == b.unfall and a.modell != b.modell and b.praemie_monat < a.praemie_monat - 1):
                diff = (a.praemie_monat - b.praemie_monat) * 12
                hinw.append(f"{a.name}: Das Modell «{MODELLE.get(b.modell, b.modell)}» von {b.name} ist bei {a.versicherer} "
                            f"mit gleicher Franchise rund CHF {diff:,.0f} pro Jahr günstiger als «{MODELLE.get(a.modell, a.modell)}» "
                            "(gleiche Prämienregion, ab 26 Jahren gleicher Tarif) – Wechsel bis 30.11. möglich, erste "
                            "Anlaufstelle wechselt dann." >> TS)
    neue = [v for v in vertraege if v["sparte"] == "kvg" and (v.get("beginn") or "")[:4] == str(heute.year + 1)]
    if neue and heute <= date(heute.year, 11, 30):
        tage = (date(heute.year, 11, 30) - heute).days
        hinw.append(f"Die Policen {heute.year + 1} liegen vor: Grundversicherung wechseln bzw. Franchise senken bis 30.11. "
                    f"(Eingang bei der Kasse, noch {tage} Tage), Franchise erhöhen bis 31.12. Prämien aller Kassen vergleichen: "
                    "priminfo.admin.ch (offizieller Prämienrechner des Bundes).")
    zus = [v for v in vertraege if v["sparte"] == "vvg"]
    if zus:
        hinw.append("Zusatzversicherungen nicht kündigen, bevor eine neue Versicherung schriftlich zugesagt hat – neue Kassen "
                    "verlangen eine Gesundheitsprüfung. Die Grundversicherung lässt sich unabhängig davon wechseln.")
        if any(re.search(r"zahn|denta", (v.get("notiz") or "") + (v.get("produkte") or ""), re.I) for v in zus):
            hinw.append("Zahnversicherung für Kinder behalten: Zahnspangen kosten oft mehrere tausend Franken, und viele "
                        "Kassen nehmen Kinder nur bis zu einem bestimmten Alter ohne Vorbehalt auf.")
        hinw.append("Notfälle im Ausland übernimmt die Grundversicherung nur bis zum doppelten Schweizer Tarif – eine "
                    "Zusatzversicherung mit Auslanddeckung oder eine Reiseversicherung schliesst die Lücke.")
    return hinw


def haushalt(k: dict, vertraege: list[dict]) -> list[Ergebnis]:
    cfg = k.get("krankenkasse") or {}
    return [rechnen(p, float(cfg.get("rabatt_modell", 12)), float(cfg.get("unfall_anteil", 7)))
            for p in personen(k, vertraege) if p.praemie_monat > 0]
