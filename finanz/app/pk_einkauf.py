"""PK-Einkauf: Varianten im Vergleich – Steuern, Kapitalbezug, Zins und Wirkung auf die Invaliditätsdeckung.

Pro Person mit Einkaufspotenzial werden Varianten gleich bewertet:
- kein Einkauf, die geplanten Einkäufe (Einstellungen), alles dieses Jahr, gleichmässig auf 3 bzw. 5 Jahre,
  10 Jahre und bis zum letzten möglichen Jahr.
- Steuerersparnis pro Jahr mit dem heutigen Einkommen (Progression: verteilen spart mehr), Mehrsteuer beim
  Kapitalbezug, Zinsvorteil der PK gegenüber einer sicheren Anlage (`anlage.zins_sicher`) bis zur Pensionierung,
  Netto-Vorteil.
- Invalidität: Je nach Reglement erhöht ein Einkauf die Invalidenrente der PK – bei Plänen, die die Rente aus dem
  projizierten Altersguthaben rechnen (wie das BVG-Minimum, BVG Art. 24), um rund Einkauf × Umwandlungssatz; bei
  Plänen mit Rente in % des versicherten Lohnes gar nicht. Einstellung pro Person `pk.iv_basis` (lohn | guthaben).
  Übersteigt die Deckung danach das Ziel (`risiko.iv_ziel_prozent`, Standard 80 % des Lohns), kann die externe
  IV-Versicherung um den Überschuss gekürzt werden; die Prämie (`risiko.iv_praemie_extern` oder aus den Policen)
  sinkt im Verhältnis. Gezählt wird nur, was der Einkauf zusätzlich möglich macht.

Vorbehalte: Die PK-Deckung gilt nur beim heutigen Arbeitgeber (Stellenwechsel, Arbeitslosigkeit, Selbständigkeit),
eine private IV-Police ist davon unabhängig; eine spätere Erhöhung braucht meist eine neue Gesundheitsprüfung.
Leistungen über 90 % des entgangenen Verdienstes kürzt die PK (Überentschädigung, BVV 2 Art. 24).
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

import copy
from dataclasses import dataclass, field
from datetime import date

IV_BASIS = {"lohn": "in % des versicherten Lohnes (Einkauf ändert die IV-Rente nicht)",
            "guthaben": "aus dem projizierten Altersguthaben (Einkauf erhöht die IV-Rente)"}
IV_ZIEL = 80.0


def _chf(v: float) -> str:
    return f"{v:,.0f}" >> TS


@dataclass
class Variante:
    schluessel: str
    name: str
    plan: dict[int, float]
    einkauf: float
    steuern: float               # Ersparnis Einkommenssteuer total
    kapitalsteuer: float         # Mehrsteuer beim Kapitalbezug
    zins: float                  # Zinsvorteil der PK gegenüber einer sicheren Anlage bis zur Pensionierung
    iv_mehr: float               # zusätzliche IV-Rente der PK pro Jahr nach dem letzten Einkauf
    iv_praemie: float            # gesparte Prämien der externen IV-Versicherung (total)
    hinweise: list[str] = field(default_factory=list)

    @property
    def netto(self) -> float:
        return round(self.steuern + self.zins - self.kapitalsteuer)

    @property
    def total(self) -> float:
        return round(self.netto + self.iv_praemie)

    @property
    def satz(self) -> float:
        return self.steuern / self.einkauf * 100 if self.einkauf else 0.0

    @property
    def jahre(self) -> str:
        if not self.plan:
            return "–"
        j = sorted(self.plan)
        return str(j[0]) if len(j) == 1 else f"{j[0]}–{j[-1]} ({len(j)})"


@dataclass
class IvLage:
    basis: str
    ziel: float                  # CHF pro Jahr
    heute: float                 # IV-Leistungen total heute
    extern: float                # externe IV-Rente pro Jahr
    praemie: float               # Prämie der externen IV-Versicherung pro Jahr
    praemie_quelle: str
    bis: int                     # letztes Jahr mit Prämie (Ablauf bzw. Pensionierung)
    heute_kuerzbar: float        # schon ohne Einkauf über dem Ziel


@dataclass
class Vergleich:
    person: str
    potenzial: float
    pension: int
    iv: IvLage
    varianten: list[Variante]
    beste_steuern: str
    beste_total: str
    hinweise: list[str] = field(default_factory=list)


def _iv_lage(k: dict, db, p: dict, heute: date) -> IvLage:
    import versicherungen as vi
    import vorsorge as vs
    vertraege = vi.alle(db) if db is not None else []
    r = next(x for x in vi.risiko(k, vs.ahv(k, heute.year), vertraege) if x.name == p["name"])
    risiko = p.get("risiko") or {}
    ziel = r.lohn * float(risiko.get("iv_ziel_prozent") or IV_ZIEL) / 100
    praemie, quelle, bis = float(risiko.get("iv_praemie_extern") or 0), "Einstellungen", vs.pensionsjahr(p) - 1
    if not praemie:
        for v in vertraege:
            if not v.get("person") or not vi.gleiche_person(v["person"], p["name"]):
                continue
            if v.get("ablauf") and str(v["ablauf"]) < heute.isoformat():
                continue
            if v.get("sparte") == "erwerbsunfaehigkeit" or float(v.get("iv_rente_jahr") or 0):
                praemie += float(v.get("praemie_jahr") or 0)
                quelle = "Policen"
                if v.get("ablauf"):
                    bis = min(bis, int(str(v["ablauf"])[:4]))
    if not praemie:
        quelle = ""
    return IvLage(p.get("pk", {}).get("iv_basis") or "lohn", round(ziel), r.iv_total, r.iv_extern, praemie, quelle, bis,
                  round(min(r.iv_extern, max(0.0, r.iv_total - ziel))))


def _bewerten(k: dict, p: dict, schluessel: str, name: str, plan: dict[int, float], iv: IvLage) -> Variante:
    import kinder as ki
    import steuern as st
    import vorsorge as vs
    plan = {j: b for j, b in plan.items() if b > 0.5}
    cfg = p["pk"]
    steuern = sum(st.ersparnis_abzug(k, b, p["name"])["total"] for b in plan.values())
    pj = vs.pensionsjahr(p)
    import anlage as an
    zins = float(cfg.get("zins", k["kennzahlen"]["bvg_mindestzins"]) or 0) / 100
    sicher = float(an.konfiguration(k).get("zins_sicher") or 0) / 100
    wert = sum(b * (1 + zins) ** max(0, pj - j - 1) for j, b in plan.items())
    # Zinsvorteil gegenüber einer sicheren Anlage desselben Geldes bis zur Pensionierung
    vorteil = sum(b * ((1 + zins) ** max(0, pj - j - 1) - (1 + sicher) ** max(0, pj - j - 1)) for j, b in plan.items())
    anteil = min(100.0, float(cfg.get("kapitalbezug_anteil", 0) or 0)) / 100
    kap = 0.0
    if anteil and wert:
        basis = vs.pk(p, k).kapital
        einheit = st.einheit_von(k, p["name"])
        kap = st.kapitalsteuer(basis + wert * anteil, k, einheit)["total"] - st.kapitalsteuer(basis, k, einheit)["total"]
    # Invalidität: zusätzliche Rente aus dem Einkauf (Rente aus dem Guthaben: Einkauf × Umwandlungssatz, Kinderrente 20 %)
    uws = float(cfg.get("umwandlungssatz", 6.8) or 6.8) / 100
    kinder = ki.anzahl(k, person=p["name"])
    faktor = uws * (1 + 0.2 * kinder) if iv.basis == "guthaben" else 0.0
    praemie_total, kumuliert = 0.0, 0.0
    jahre = sorted(plan)
    if faktor and iv.praemie and iv.extern and jahre:
        for j in range(jahre[0] + 1, iv.bis + 1):
            kumuliert = sum(b for jj, b in plan.items() if jj < j)
            mehr = kumuliert * faktor
            kuerzbar = min(iv.extern, max(0.0, iv.heute + mehr - iv.ziel)) - iv.heute_kuerzbar
            praemie_total += iv.praemie * max(0.0, kuerzbar) / iv.extern
    v = Variante(schluessel, name, plan, round(sum(plan.values())), round(steuern), round(kap), round(vorteil),
                 round(sum(plan.values()) * faktor), round(praemie_total))
    return v


def _gleich(betrag: float, jahre: list[int]) -> dict[int, float]:
    if not jahre:
        return {}
    teil = round(betrag / len(jahre) / 100) * 100
    plan = {j: teil for j in jahre}
    plan[jahre[-1]] += betrag - teil * len(jahre)
    return plan


def vergleich(k: dict, db, person: str, budget: float = 0.0, heute: date | None = None) -> Vergleich:
    import vorsorge as vs
    import zuzug as zz
    heute = heute or date.today()
    p0 = next(x for x in k["personen"] if x["name"] == person)
    geplant = {int(e["jahr"]): float(e["betrag"]) for e in p0["pk"].get("einkauf_geplant") or []
               if int(e.get("jahr") or 0) >= heute.year}
    # ohne die geplanten Einkäufe dieser Person rechnen, damit alle Varianten vom gleichen Stand ausgehen
    k0 = copy.deepcopy(k)
    p = next(x for x in k0["personen"] if x["name"] == person)
    p["pk"]["einkauf_geplant"] = []
    potenzial = float(p["pk"].get("einkauf_potenzial") or 0)
    betrag = min(potenzial, budget) if budget > 0 else potenzial
    pj = vs.pensionsjahr(p)
    kapital = float(p["pk"].get("kapitalbezug_anteil") or 0) > 0
    letztes = pj - (4 if kapital else 1)
    moeglich = [j for j in range(heute.year, letztes + 1)]
    grenze = zz.einkauf_limit(p, heute.year)
    iv = _iv_lage(k0, db, p, heute)
    hinweise = []
    if grenze is not None:
        hinweise.append(f"Zuzug aus dem Ausland: höchstens CHF {_chf(grenze)} pro Jahr – «alles dieses Jahr» ist "
                        "darauf begrenzt.")
    varianten = [_bewerten(k0, p, "keiner", "Kein Einkauf", {}, iv)]
    if geplant:
        varianten.append(_bewerten(k0, p, "geplant", "Geplant (Einstellungen)", geplant, iv))
    if betrag > 0 and moeglich:
        eins = min(betrag, grenze) if grenze is not None else betrag
        varianten.append(_bewerten(k0, p, "eins", f"Alles {heute.year}", {heute.year: eins}, iv))
        for n in (3, 5):
            if len(moeglich) >= n:
                varianten.append(_bewerten(k0, p, f"gleich{n}", f"Gleichmässig auf {n} Jahre",
                                           _gleich(betrag, moeglich[:n]), iv))
        if len(moeglich) > 5:
            varianten.append(_bewerten(k0, p, "gleich_alle", f"Gleichmässig bis {moeglich[-1]}",
                                       _gleich(betrag, moeglich), iv))
        if len(moeglich) > 10:
            varianten.append(_bewerten(k0, p, "gleich10", "Gleichmässig auf 10 Jahre", _gleich(betrag, moeglich[:10]), iv))
    varianten = [v for v in varianten if v.schluessel in ("keiner", "geplant")] + sorted(
        (v for v in varianten if v.schluessel not in ("keiner", "geplant")), key=lambda v: len(v.plan))
    mit = [v for v in varianten if v.einkauf]
    beste_st = max(mit, key=lambda v: (v.steuern, -len(v.plan)), default=varianten[0])
    beste_tot = max(varianten, key=lambda v: (v.total, -len(v.plan)))
    if betrag > 0 and kapital:
        hinweise.append(f"Kapitalbezug geplant: Einkäufe ab {letztes + 1} sind gesperrt (3 Jahre vor dem Bezug) – "
                        "die Varianten enden vorher.")
    if iv.basis == "lohn":
        hinweise.append("Invalidität: Die Invalidenrente ist hier in % des versicherten Lohnes eingestellt – ein Einkauf "
                        "erhöht sie nicht, die externe IV-Versicherung bleibt nötig. Steht im Reglement, dass die Rente "
                        "aus dem projizierten Altersguthaben gerechnet wird, unten «Altersguthaben» wählen.")
    elif not iv.praemie:
        hinweise.append("Invalidität: Prämie der externen IV-Versicherung unbekannt – unten eintragen oder die Police "
                        "unter Versicherungen hochladen, dann rechnet die App die mögliche Ersparnis.")
    if iv.heute_kuerzbar:
        hinweise.append(f"Invalidität: Schon heute liegen die Leistungen CHF {_chf(iv.heute_kuerzbar)} pro Jahr über dem "
                        f"Ziel von {_chf(iv.ziel)} – die externe Rente liesse sich unabhängig vom Einkauf kürzen.")
    if any(v.iv_praemie for v in varianten):
        hinweise.append("Vor einer Kürzung der IV-Police bedenken: Die PK-Leistung gilt nur beim heutigen Arbeitgeber – "
                        "bei Stellenwechsel, Arbeitslosigkeit oder Selbständigkeit fällt sie weg bzw. auf das BVG-Minimum; "
                        "eine spätere Erhöhung der Police braucht meist eine neue Gesundheitsprüfung.")
    if beste_tot.schluessel == "keiner" and len(varianten) > 1:
        hinweise.append("Mit diesen Annahmen bringt kein Einkauf einen Vorteil – Steuersatz, Kapitalbezug und PK-Zins "
                        "prüfen.")
    return Vergleich(person, potenzial, pj, iv, varianten, beste_st.schluessel, beste_tot.schluessel, hinweise)


def alle(k: dict, db, heute: date | None = None) -> list[Vergleich]:
    return [vergleich(k, db, p["name"], heute=heute) for p in k["personen"]
            if float(p["pk"].get("einkauf_potenzial") or 0) > 0 or p["pk"].get("einkauf_geplant")]


def plan_von(k: dict, db, person: str, schluessel: str) -> dict[int, float]:
    v = vergleich(k, db, person)
    return next((x.plan for x in v.varianten if x.schluessel == schluessel), {})
