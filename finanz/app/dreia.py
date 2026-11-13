"""Säule 3a als Konten unter «Vermögen»: Abgleich mit den Einstellungen und gestaffelter Bezug je Konto.

Jedes 3a-Konto bzw. 3a-Depot ist ein Konto der Art `saeule3a` mit Person und Saldo-Verlauf. Hat eine Person
mindestens ein 3a-Konto, führt die App `personen[].saeule3a.guthaben`, `.konten` und `.anteile` (Anteile der Konten,
aufsteigend – für den gestaffelten Bezug) daraus nach; der Wert in den Einstellungen gilt nur ohne 3a-Konten.
Die 3a zählt zum Nettovermögen (gebunden), aber nicht zum freien Vermögen – sie kommt über das 3a-Modell bei der
Pensionierung dazu, damit nichts doppelt zählt.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

LOG = logging.getLogger("finanz")


def _person(name: str, personen: list[dict]) -> dict | None:
    import versicherungen as vi
    if not name and len(personen) == 1:
        return personen[0]
    return next((p for p in personen if name and vi.gleiche_person(p["name"], name)), None)


def konten(k: dict, db) -> dict[str, list[dict]]:
    """{Personenname: [Konto, …]} – nicht zugeordnete 3a-Konten unter ''."""
    import vermoegen as vm
    erg: dict[str, list[dict]] = {}
    for x in vm.konten(db):
        if x["art"] != "saeule3a" or x.get("aufgeloest"):
            continue
        p = _person(x["person"], k["personen"])
        erg.setdefault(p["name"] if p else "", []).append(x)
    return erg


def abgleichen(k: dict, db) -> bool:
    """Guthaben, Anzahl und Anteile der 3a-Konten in die Einstellungen übernehmen; True, wenn sich etwas geändert hat."""
    try:
        je = konten(k, db)
    except Exception as e:  # noqa: BLE001
        LOG.debug("3a-Abgleich: %s", e)
        return False
    geaendert = False
    for p in k["personen"]:
        ks = je.get(p["name"]) or []
        cfg = p.setdefault("saeule3a", {})
        if not ks:
            if cfg.pop("aus_konten", None):          # Konten gelöscht → Wert bleibt, ist aber wieder von Hand
                cfg.pop("anteile", None)
                geaendert = True
            continue
        summe = round(sum(x["wert"] for x in ks))
        anteile = sorted(round(x["wert"] / summe, 4) if summe else round(1 / len(ks), 4) for x in ks)
        neu = {"guthaben": summe, "konten": len(ks), "anteile": anteile, "aus_konten": True}
        if any(cfg.get(s) != v for s, v in neu.items()):
            cfg.update(neu)
            geaendert = True
    return geaendert


def ohne_konto(k: dict, db) -> list[dict]:
    """Personen mit 3a-Guthaben in den Einstellungen, aber ohne 3a-Konto unter Vermögen."""
    je = konten(k, db)
    return [p for p in k["personen"] if not je.get(p["name"])
            and float((p.get("saeule3a") or {}).get("guthaben") or 0) > 0]


def anlegen(k: dict, db, heute: date | None = None) -> list[str]:
    """Für Personen ohne 3a-Konto je ein Konto «3a <Name>» mit dem Guthaben aus den Einstellungen anlegen."""
    import vermoegen as vm
    heute = heute or date.today()
    erg = []
    for p in ohne_konto(k, db):
        name = f"3a {p['name']}"
        kid = vm.konto_anlegen(db, name, "saeule3a", p["name"])
        vm.saldo_setzen(db, kid, heute.isoformat(), float(p["saeule3a"]["guthaben"]))
        erg.append(name)
    return erg


def guthaben_uebernehmen(db, dok: dict, person: str, konto: str) -> str:
    """3a-Guthaben aus einem Auszug als Saldo eines 3a-Kontos unter «Vermögen»."""
    import vermoegen as vm
    wert = float(dok["werte"]["guthaben_3a"])
    konto = (konto or konto_vorschlag(dok, person)).strip()
    kid = vm.konto_anlegen(db, konto, "saeule3a", person)
    vm.saldo_setzen(db, kid, dok.get("stichtag") or date.today().isoformat(), wert)
    return f"3a-Guthaben als Saldo «{konto}»"


def konto_vorschlag(dok: dict, person: str) -> str:
    return " ".join(x for x in ("3a", dok.get("anbieter") or "", person) if x).strip()


@dataclass
class Bezug:
    person: str
    konto: str
    wert: float
    jahr: int


def bezugsplan(k: dict, db) -> list[Bezug]:
    """Ein Konto pro Jahr, frühestens 5 Jahre vor dem Referenzalter, das grösste im Pensionsjahr."""
    import vorsorge as vs
    erg = []
    je = konten(k, db)
    for p in k["personen"]:
        ks = sorted(je.get(p["name"]) or [], key=lambda x: x["wert"])
        if not ks:
            continue
        pj = vs.pensionsjahr(p)
        jahre = [j for j in range(pj - len(ks) + 1, pj + 1) if j >= vs.geburtsjahr(p) + 60] or [pj]
        jahre = [jahre[0]] * (len(ks) - len(jahre)) + jahre          # mehr Konten als Jahre: mehrere im ersten Jahr
        erg += [Bezug(p["name"], x["name"], x["wert"], j) for x, j in zip(ks, jahre)]
    return erg
