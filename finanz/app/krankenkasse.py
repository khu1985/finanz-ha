"""Krankenkasse: Franchise und Modell der Grundversicherung optimieren.

Kosten pro Jahr = Prämie + Franchise (soweit Kosten anfallen) + Selbstbehalt 10 % (höchstens 700, Kinder 350).
Fehlen Prämien für andere Franchisen, schätzt die App sie mit dem gesetzlichen Höchstrabatt (Art. 95 KVV):
Rabatt = 70 % des Risikounterschieds zur Grundfranchise, höchstens 50 % der Prämie mit Grundfranchise.
Die meisten Kassen geben diesen Höchstrabatt bei hohen Franchisen weitgehend weiter.
"""
from __future__ import annotations

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
        hinw.append(f"{p.name}: Franchise {beste} statt {p.franchise} spart bei Kosten von rund CHF {p.kosten_jahr:,.0f} "
                    f"etwa CHF {heute - kosten[beste]:,.0f} pro Jahr.".replace(",", "'"))
    if be:
        hinw.append(f"{p.name}: Die tiefste Franchise lohnt sich erst ab Gesundheitskosten von rund CHF {be[0][2]:,.0f} pro Jahr."
                    .replace(",", "'"))
    if p.modell == "standard":
        spar = pr[beste] * rabatt_modell / 100
        hinw.append(f"{p.name}: Ein Hausarzt- oder Telmed-Modell ist typischerweise {rabatt_modell:.0f} % günstiger "
                    f"(rund CHF {spar:,.0f} pro Jahr).".replace(",", "'"))
    if p.unfall and p.angestellt:
        spar = pr[beste] * unfall_anteil / 100
        hinw.append(f"{p.name}: Unfalldeckung sistieren (über den Arbeitgeber versichert) spart rund CHF {spar:,.0f} pro Jahr."
                    .replace(",", "'"))
    if not p.kind and beste == 300 and p.kosten_jahr < 2000:
        hinw.append(f"{p.name}: Bei schwankenden Kosten prüfen, ob eine Reserve für die hohe Franchise vorhanden ist.")
    return Ergebnis(p, liste, pr, kosten, beste, round(max(0.0, heute - kosten[beste])), be, tab, hinw, geschaetzt)


def personen(k: dict, vertraege: list[dict]) -> list[Person]:
    """Aus der Konfiguration (krankenkasse.personen) oder, falls leer, aus den KVG-Policen."""
    import versicherungen as vi

    cfg = (k.get("krankenkasse") or {}).get("personen") or []
    loehne = {p["name"]: float(p.get("lohn_brutto", 0)) for p in k["personen"]}
    kinder = {c.get("name", "Kind") for c in k["haushalt"].get("kinder") or []}
    namen = [p["name"] for p in k["personen"]] + list(kinder)
    erg = []
    for name in namen:
        eintrag = next((e for e in cfg if vi.gleiche_person(str(e.get("name", "")), name)), None)
        police = next((v for v in vertraege if v["sparte"] == "kvg" and vi.gleiche_person(v["person"], name)), None)
        kind = name in kinder
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
            modell, unfall, kosten, angebote = "standard", bool(police["unfall_eingeschlossen"]), 0.0, {}
        else:
            franchise, praemie, modell, unfall, kosten, angebote = (0 if kind else 300), 0.0, "standard", kind, 0.0, {}
        liste = FRANCHISEN_KINDER if kind else FRANCHISEN_ERWACHSENE
        if franchise not in liste:
            franchise = min(liste, key=lambda f: abs(f - franchise))
        erg.append(Person(name, kind, franchise, praemie, kosten, modell, unfall, loehne.get(name, 0) > 0, angebote))
    return erg


def haushalt(k: dict, vertraege: list[dict]) -> list[Ergebnis]:
    cfg = k.get("krankenkasse") or {}
    return [rechnen(p, float(cfg.get("rabatt_modell", 12)), float(cfg.get("unfall_anteil", 7)))
            for p in personen(k, vertraege) if p.praemie_monat > 0]
