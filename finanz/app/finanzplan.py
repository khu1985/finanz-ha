"""Finanzplan Jahr für Jahr bis ins hohe Alter – mit Simulation schwankender Renditen (Monte Carlo).

Alles in heutigen Franken. Bis zur Pensionierung wächst das freie Vermögen mit der realen Rendite und dem
Sparpotenzial (`personen[].sparen_monat`); PK und 3a laufen in ihren eigenen Modellen und kommen bei der
Pensionierung nach Kapitalbezugssteuer dazu (wie bei der Pensionslücke). Danach deckt das Vermögen, was AHV,
PK-Renten, Renten aus dem Ausland und Kinderrenten am Bedarf im Ruhestand nicht decken. Der Bedarf versteht sich
inkl. Steuern (wie überall in der App).

Die Simulation zieht für jedes Jahr eine Rendite (lognormal, Mittelwert = reale Rendite des Risikoprofils,
Schwankung nach Aktienquote) und zählt, in wie vielen von 1000 Verläufen das Geld bis zum Endalter reicht.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date

PFADE = 1000
SIGMA_AKTIEN = 0.16      # Schwankung pro Jahr, breit diversifiziert
SIGMA_SICHER = 0.04      # Obligationen, Geldmarkt


@dataclass
class Jahr:
    jahr: int
    alter: str                 # z. B. «52 / 50»
    phase: str                 # Erwerb, Pension
    einkommen: float           # Lohn bzw. Renten (AHV, PK, Ausland, Kinderrenten)
    sparen: float              # Zufluss (+) bzw. Entnahme (−) aus dem Vermögen
    kapital: float             # PK/3a-Kapital nach Steuern, das in diesem Jahr dazukommt
    vermoegen: float           # Ende Jahr


@dataclass
class Plan:
    jahre: list[Jahr]
    pension_jahr: int
    end_jahr: int
    end_alter: int
    rendite_real: float        # % (Mittelwert)
    sigma: float               # % Schwankung
    bedarf: float
    reicht_bis: int | None     # deterministisch: letztes Jahr mit Vermögen > 0 (None = reicht)
    erfolg: float = 0.0        # % der Verläufe, in denen das Geld bis zum Endalter reicht
    perzentile: dict[int, list[tuple[int, float]]] = field(default_factory=dict)   # 10/50/90 → [(Jahr, Vermögen)]
    pleite_median: int | None = None   # in schlechten Verläufen (10 %): Jahr, in dem das Geld ausgeht
    bedarf_sicher: float | None = None  # höchster Bedarf, der in 90 % der Verläufe reicht
    hinweise: list[str] = field(default_factory=list)


def _annahmen(k: dict) -> tuple[float, float]:
    import anlage as an
    import vorsorge as vs
    cfg = an.konfiguration(k)
    risiko = cfg["risiko"] if cfg["risiko"] in cfg["aktienquote"] else "mittel"
    q = float(cfg["aktienquote"][risiko]) / 100
    mu = float(cfg["rendite"][risiko]) - vs.teuerung(k)
    sigma = math.sqrt((q * SIGMA_AKTIEN) ** 2 + ((1 - q) * SIGMA_SICHER) ** 2) * 100
    return mu, sigma


def _grundlagen(k: dict, vermoegen_frei: float, jetzt: int):
    import kinder as ki
    import vorsorge as vs
    import zuzug as zz
    l0 = vs.pensionsluecke(k, 0.0, jetzt)            # Kapital aus PK/3a ohne freies Vermögen
    t = vs.teuerung(k)
    personen = k["personen"]
    pension = l0.jahr
    end_alter = int((k.get("finanzplan") or {}).get("bis_alter") or 95)
    juengste = max(vs.geburtsjahr(p) for p in personen)
    ende = juengste + end_alter
    ahv_real = l0.ahv                                # AHV ohne Kinderrenten (heutige Franken, ab Pension)
    ahv_person = {r.name: r.rente_jahr * vs.ahv_real_faktor(k, pension - jetzt) for r in vs.ahv(k, jetzt)}

    def renten(j: int) -> float:
        n = j - pension
        kr = sum(0.4 * ahv_person.get(x["name"], 0) * sum(1 for c in ki.eigene(k, x["name"]) if ki.unterhalt(c, j))
                 for x in personen if j >= vs.geburtsjahr(x) + 65)
        aus = sum(zz.rente_ausland(x) for x in personen if j >= vs.geburtsjahr(x) + zz.rente_ausland_alter(x))
        return ahv_real + l0.pk_rente / (1 + t / 100) ** max(0, n) + kr + aus

    lohn = sum(float(p.get("lohn_brutto") or 0) for p in personen)
    sparen = sum(float(p.get("sparen_monat") or 0) for p in personen) * 12
    alter = lambda j: " / ".join(str(j - vs.geburtsjahr(p)) for p in personen)  # noqa: E731
    return l0, pension, ende, end_alter, renten, lohn, sparen, alter, max(0.0, vermoegen_frei)


def _verlauf(start: float, jahre: list[int], pension: int, kapital: float, sparen: float, renten: list[float],
             bedarf: float, renditen: list[float]) -> list[float]:
    """renten: Renten pro Jahr (gleiche Länge wie jahre, vorberechnet)."""
    v = start
    erg = []
    for j, rente, r in zip(jahre, renten, renditen):
        if j < pension:
            v = v * (1 + r) + sparen
        else:
            if j == pension:
                v += kapital
            v = (v - max(0.0, bedarf - rente)) * (1 + r)
        erg.append(v)
    return erg


def _pfade(n: int, anzahl: int, mu: float, sigma: float, seed: int = 42) -> list[list[float]]:
    rnd = random.Random(seed)
    m = math.log(1 + mu / 100) - (sigma / 100) ** 2 / 2
    s = sigma / 100
    return [[math.exp(rnd.gauss(m, s)) - 1 for _ in range(n)] for _ in range(anzahl)]


def rechnen(k: dict, vermoegen_frei: float, jetzt: int | None = None, simulation: bool = True,
            pfade: int = PFADE) -> Plan:
    jetzt = jetzt or date.today().year
    l0, pension, ende, end_alter, renten, lohn, sparen, alter, start = _grundlagen(k, vermoegen_frei, jetzt)
    bedarf = float(k["haushalt"].get("bedarf_ruhestand") or 0)
    mu, sigma = _annahmen(k)
    jahre = list(range(jetzt, ende + 1))
    kapital = float(l0.kapital_netto)
    rl = [renten(j) if j >= pension else 0.0 for j in jahre]
    det = _verlauf(start, jahre, pension, kapital, sparen, rl, bedarf, [mu / 100] * len(jahre))
    zeilen = []
    for j, v in zip(jahre, det):
        if j < pension:
            zeilen.append(Jahr(j, alter(j), "Erwerb", lohn, sparen, 0.0, round(v)))
        else:
            rente = rl[jahre.index(j)]
            zeilen.append(Jahr(j, alter(j), "Pension", round(rente), -round(max(0.0, bedarf - rente)),
                               round(kapital) if j == pension else 0.0, round(v)))
    reicht_bis = next((j - 1 for j, v in zip(jahre, det) if v < 0), None)
    plan = Plan(zeilen, pension, ende, end_alter, round(mu, 2), round(sigma, 1), bedarf, reicht_bis)
    if simulation and len(jahre) > 1:
        sims = _pfade(len(jahre), pfade, mu, sigma)
        verlaeufe = [_verlauf(start, jahre, pension, kapital, sparen, rl, bedarf, r) for r in sims]
        ok = sum(1 for vl in verlaeufe if min(vl[jahre.index(pension):] if pension in jahre else vl) >= 0)
        plan.erfolg = round(ok / len(verlaeufe) * 100, 1)
        for p in (10, 50, 90):
            plan.perzentile[p] = []
        for i, j in enumerate(jahre):
            werte = sorted(vl[i] for vl in verlaeufe)
            for p in (10, 50, 90):
                plan.perzentile[p].append((j, round(max(0.0, werte[int(len(werte) * p / 100)]))))
        schlecht = sorted(verlaeufe, key=lambda vl: vl[-1])[: max(1, len(verlaeufe) // 10)]
        jahre_pleite = sorted(next((j for j, v in zip(jahre, vl) if v < 0), ende + 1) for vl in schlecht)
        median = jahre_pleite[len(jahre_pleite) // 2]
        plan.pleite_median = median if median <= ende else None
        plan.bedarf_sicher = _bedarf_sicher(start, jahre, pension, kapital, sparen, rl, sims[:200], bedarf)
    plan.hinweise = _hinweise(plan, k)
    return plan


def _bedarf_sicher(start, jahre, pension, kapital, sparen, renten, sims, bedarf) -> float:
    """Höchster Bedarf pro Jahr, der in 90 % der Verläufe bis zum Endalter reicht (Halbierungsverfahren)."""
    i0 = jahre.index(pension) if pension in jahre else 0

    def quote(b):
        ok = sum(1 for r in sims if min(_verlauf(start, jahre, pension, kapital, sparen, renten, b, r)[i0:]) >= 0)
        return ok / len(sims)
    tief, hoch = 0.0, max(bedarf * 2, 50_000)
    for _ in range(11):
        mitte = (tief + hoch) / 2
        if quote(mitte) >= 0.9:
            tief = mitte
        else:
            hoch = mitte
    return round(tief / 100) * 100


def _hinweise(p: Plan, k: dict) -> list[str]:
    h = []
    chf = lambda v: f"{v:,.0f}".replace(",", "'")  # noqa: E731
    if p.reicht_bis:
        h.append(f"Mit der mittleren Rendite reicht das Vermögen bis {p.reicht_bis} – danach fehlen jedes Jahr Mittel.")
    if p.perzentile:
        if p.erfolg >= 90:
            h.append(f"In {p.erfolg:.0f} % der simulierten Verläufe reicht das Geld bis {p.end_alter} – solide.")
        elif p.erfolg >= 70:
            h.append(f"In {p.erfolg:.0f} % der Verläufe reicht das Geld bis {p.end_alter}. Etwas Puffer schaffen: später "
                     "pensionieren, mehr sparen, PK-Einkauf oder Bedarf senken.")
        else:
            h.append(f"Nur in {p.erfolg:.0f} % der Verläufe reicht das Geld bis {p.end_alter} – der Plan ist knapp.")
        if p.pleite_median:
            h.append(f"In den schlechtesten 10 % der Verläufe ist das Vermögen um {p.pleite_median} aufgebraucht "
                     "(danach bleiben AHV und PK-Renten).")
        if p.bedarf_sicher is not None and p.bedarf:
            diff = p.bedarf_sicher - p.bedarf
            h.append(f"Mit 90 % Sicherheit tragbar: rund CHF {chf(p.bedarf_sicher)} pro Jahr "
                     + (f"(CHF {chf(diff)} mehr als geplant)." if diff >= 0 else f"(CHF {chf(-diff)} weniger als geplant)."))
    if not p.bedarf:
        h.append("Bedarf im Ruhestand fehlt (Einstellungen → Haushalt) – ohne ihn wird nichts entnommen.")
    return h
