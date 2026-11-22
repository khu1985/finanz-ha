"""Entnahmeplan im Ruhestand: Rente oder Kapital, in welcher Reihenfolge beziehen – und reicht das Geld?

Jahr für Jahr ab der Pensionierung bis `entnahme.bis_alter` (Standard 95), in heutigen Franken, je Steuereinheit
(Ehepaar gemeinsam, im Konkubinat jede Person für sich mit der Hälfte des Bedarfs):

- Einnahmen: AHV ab 65 (hält die Kaufkraft ungefähr, Mischindex), PK-Rente (nominal fix, verliert die Teuerung),
  Ertrag des Vermögens (`haushalt.entnahme_rendite`; ⅓ davon steuerbar wie in der Amortisation).
- Kapitalbezüge (PK-Kapital, Säule 3a gestaffelt wie unter Vorsorge) mit der Kapitalleistungssteuer des Bezugsjahrs.
- Einkommenssteuer auf AHV, PK-Rente und steuerbaren Ertrag abzüglich `entnahme.abzuege` pro Person (Pauschale für
  Krankenkasse, Berufs- und Sozialabzüge), Vermögenssteuer mit `kennzahlen.vermoegen_promille`.
- Startvermögen: freie Konten der Einheit heute (gemeinsame Konten anteilig) plus `sparen_monat` bis zur Pensionierung,
  ohne Rendite (vorsichtig, heutige Franken).
- Der Bedarf (`haushalt.bedarf_ruhestand`) wird aus Einnahmen und Vermögen gedeckt; geht das Vermögen aus, zeigt die
  Variante das Jahr und die Lücke.

Varianten unterscheiden sich im PK-Kapitalanteil (0 %, wie eingestellt, 50 %, 100 %). Vereinfacht: Tarife in
heutigen Franken, keine Witwen- bzw. Partnerrenten, keine Rückzahlung von Hypotheken.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date

STANDARD = {"bis_alter": 95, "abzuege": 8000}


@dataclass
class Jahr:
    jahr: int
    einnahmen: float          # AHV + PK-Rente
    kapital_netto: float      # Kapitalbezüge nach Steuern
    steuern: float            # Einkommens-, Vermögens- und Kapitalsteuer
    entnahme: float           # aus dem Vermögen
    vermoegen: float          # Ende Jahr
    luecke: float = 0.0


@dataclass
class Variante:
    schluessel: str
    name: str
    anteil: float | None                  # PK-Kapitalanteil in % (None = wie eingestellt)
    steuern_kapital: float = 0.0
    steuern_laufend: float = 0.0
    vermoegen_85: float = 0.0
    vermoegen_ende: float = 0.0
    reicht_bis: int | None = None         # erstes Jahr ohne Deckung
    luecke_total: float = 0.0
    rente_jahr: float = 0.0               # AHV + PK-Rente im ersten Jahr (heutige Franken)
    jahre: dict[str, list[Jahr]] = field(default_factory=dict)   # je Einheit

    @property
    def steuern(self) -> float:
        return self.steuern_kapital + self.steuern_laufend


@dataclass
class Plan:
    varianten: list[Variante]
    bis_alter: int
    bezugsplan: list[tuple[int, str, float, float]]    # (Jahr, Einheit, Bezug, Steuer) – wie eingestellt
    hinweise: list[str]


def konfiguration(k: dict) -> dict:
    return STANDARD | (k.get("entnahme") or {})


def frei_pro_person(k: dict, db) -> dict[str, float]:
    """Freie Mittel heute je Person (eigene Konten plus Anteil an gemeinsamen), ohne Vorsorge, Liegenschaft und
    Schulden."""
    import vermoegen as vm
    from versicherungen import gleiche_person
    aus = {"immobilie", "hypothek", "kredit", "vorsorge", "saeule3a", "fahrzeug"}
    frei = [x for x in vm.konten(db) if x["art"] not in aus and not x.get("aufgeloest")]
    namen = [p["name"] for p in k["personen"]]
    gemeinsam = sum(x["wert"] for x in frei if not x.get("person")) / max(1, len(namen))
    erg = {}
    for n in namen:
        erg[n] = gemeinsam + sum(x["wert"] for x in frei if x.get("person") and gleiche_person(n, x["person"]))
    # Konten einer Person, die keinem Namen zugeordnet werden kann, verteilen
    rest = sum(x["wert"] for x in frei if x.get("person") and not any(gleiche_person(n, x["person"]) for n in namen))
    for n in namen:
        erg[n] += rest / max(1, len(namen))
    return erg


def _einkommenssteuer(e, steuerbar: float, kz: dict) -> float:
    import steuern as st
    if steuerbar <= 0:
        return 0.0
    return st.bundessteuer(steuerbar, e.verheiratet, 0, kz) + st.kantonssteuer(steuerbar, e.st)


def _rechnen(k: dict, db, schluessel: str, name: str, anteil: float | None, jetzt: int) -> Variante:
    import steuern as st
    import vorsorge as vs
    kk = copy.deepcopy(k)
    if anteil is not None:
        for p in kk["personen"]:
            p["pk"]["kapitalbezug_anteil"] = anteil
    cfg = konfiguration(kk)
    kz = kk["kennzahlen"]
    hh = kk["haushalt"]
    t = vs.teuerung(kk)
    rendite = float(hh.get("entnahme_rendite", 0) or 0)
    real = (rendite - t) / 100
    bedarf_hh = float(hh.get("bedarf_ruhestand", 0) or 0)
    promille = float(kz.get("vermoegen_promille", 0) or 0) / 1000
    bis_alter = int(cfg["bis_alter"])
    abzug_p = float(cfg["abzuege"])
    frei = frei_pro_person(kk, db)
    ahv = {r.name: r for r in vs.ahv(kk, jetzt)}
    v = Variante(schluessel, name, anteil)
    for e in st.einheiten(kk):
        pers = [p for p in kk["personen"] if p["name"] in e.personen]
        if not pers:
            continue
        start = max(vs.pensionsjahr(p) for p in pers)
        ende = max(vs.geburtsjahr(p) for p in pers) + bis_alter
        bedarf = bedarf_hh * len(pers) / max(1, len(kk["personen"]))
        vermoegen = sum(frei.get(p["name"], 0) + float(p.get("sparen_monat") or 0) * 12 * max(0, vs.pensionsjahr(p) - jetzt)
                        for p in pers)
        # Kapitalbezüge der Einheit je Jahr (nominal) mit Steuer; vor dem Start ins Startvermögen
        plan: dict[int, float] = {}
        renten_nom = {}
        for p in pers:
            pk_e = vs.pk(p, kk)
            d = vs.saeule3a(p, kk, jetzt)
            renten_nom[p["name"]] = (vs.pensionsjahr(p), pk_e.rente_jahr)
            for j, b in st._bezuege(p, pk_e, d, True).items():
                plan[j] = plan.get(j, 0) + b
        kap_netto: dict[int, float] = {}
        for j, b in plan.items():
            steuer = st.kapitalsteuer(b, kk, e)["total"]
            v.steuern_kapital += steuer * vs.kaufkraft(kk, j - jetzt)
            kap_netto[j] = (b - steuer) * vs.kaufkraft(kk, j - jetzt)
        vermoegen += sum(b for j, b in kap_netto.items() if j < start)
        zeilen = []
        for j in range(start, ende + 1):
            ahv_j = sum(ahv[p["name"]].rente_jahr * vs.ahv_real_faktor(kk, j - jetzt)
                        for p in pers if p["name"] in ahv and j >= vs.geburtsjahr(p) + int(ahv[p["name"]].alter or 65))
            pk_j = sum(r * vs.kaufkraft(kk, j - jetzt) for n_, (pj, r) in renten_nom.items() if j >= pj)
            if j == start:
                v.rente_jahr += ahv_j + pk_j
            ertrag_steuerbar = max(0.0, vermoegen) * rendite / 100 / 3
            steuerbar = ahv_j + pk_j + ertrag_steuerbar - abzug_p * len(pers)
            steuer = _einkommenssteuer(e, steuerbar, kz) + max(0.0, vermoegen) * promille
            v.steuern_laufend += steuer
            kap = kap_netto.get(j, 0.0) if j >= start else 0.0
            entnahme = max(0.0, bedarf + steuer - ahv_j - pk_j)
            vermoegen = vermoegen * (1 + real) + kap - entnahme
            luecke = 0.0
            if vermoegen < 0:
                luecke = -vermoegen
                vermoegen = 0.0
                if v.reicht_bis is None or j < v.reicht_bis:
                    v.reicht_bis = j
            v.luecke_total += luecke
            zeilen.append(Jahr(j, round(ahv_j + pk_j), round(kap), round(steuer), round(entnahme), round(vermoegen),
                               round(luecke)))
            juengste = max(vs.geburtsjahr(p) for p in pers)
            if j == juengste + 85:
                v.vermoegen_85 += vermoegen
        v.vermoegen_ende += vermoegen
        v.jahre[e.name] = zeilen
    return v


def rechnen(k: dict, db, jetzt: int | None = None) -> Plan | None:
    import steuern as st
    import vorsorge as vs
    jetzt = jetzt or date.today().year
    if not float(k["haushalt"].get("bedarf_ruhestand", 0) or 0):
        return None
    eingestellt = [float(p["pk"].get("kapitalbezug_anteil", 0) or 0) for p in k["personen"]]
    gleich = len(set(eingestellt)) == 1
    varianten = []
    for schl, name, anteil in (("rente", "Nur Rente", 0.0), ("eingestellt", "Wie eingestellt", None),
                               ("halb", "Halb Rente, halb Kapital", 50.0), ("kapital", "Nur Kapital", 100.0)):
        if schl != "eingestellt" and gleich and anteil == eingestellt[0]:
            continue                  # gleich wie «wie eingestellt»
        if schl == "eingestellt":
            name += " (" + ", ".join(f"{p['name']} {a:.0f} %" for p, a in zip(k["personen"], eingestellt)) + " Kapital)"
        varianten.append(_rechnen(k, db, schl, name, anteil, jetzt))
    pks = [vs.pk(p, k) for p in k["personen"]]
    drei = [vs.saeule3a(p, k, jetzt) for p in k["personen"]]
    kv = st.kapitalbezug_varianten(k, pks, drei)
    bezugsplan = [(j, e, b, s["total"]) for j, e, b, s in kv["gestaffelt"]["zeilen"]]
    hinweise = _hinweise(k, varianten, kv, jetzt)
    return Plan(varianten, int(konfiguration(k)["bis_alter"]), bezugsplan, hinweise)


def _chf(v: float) -> str:
    from tausender import TS
    return f"CHF {v:,.0f}" >> TS


def _hinweise(k: dict, varianten: list[Variante], kv: dict, jetzt: int) -> list[str]:
    h = []
    ok = [v for v in varianten if v.reicht_bis is None]
    if ok:
        beste = max(ok, key=lambda v: v.vermoegen_ende)
        h.append(f"Am meisten bleibt mit «{beste.name}»: {_chf(beste.vermoegen_ende)} mit "
                 f"{konfiguration(k)['bis_alter']} (heutige Franken), Steuern total {_chf(beste.steuern)}.")
    knapp = [v for v in varianten if v.reicht_bis is not None]
    for v in knapp:
        h.append(f"«{v.name}»: Das Vermögen reicht bis {v.reicht_bis}; danach fehlen insgesamt {_chf(v.luecke_total)}.")
    rente = next((v for v in varianten if v.schluessel == "rente"), None)
    kapital = next((v for v in varianten if v.schluessel == "kapital"), None)
    if rente and kapital:
        h.append(f"Die Rente ist lebenslang garantiert (Langlebigkeit, Börse): «Nur Rente» bringt im ersten Jahr "
                 f"{_chf(rente.rente_jahr)} Renten statt {_chf(kapital.rente_jahr)}. Kapital bleibt flexibel und "
                 "vererbbar, muss aber selbst angelegt werden und kann ausgehen.")
    if kv.get("ersparnis", 0) > 500:
        h.append(f"3a gestaffelt beziehen (ein Konto pro Jahr ab 60) spart rund {_chf(kv['ersparnis'])} Kapitalsteuer "
                 "gegenüber allem im Pensionsjahr – im Bezugsplan unten schon so gerechnet.")
    konk = k["haushalt"].get("zivilstand", "verheiratet") != "verheiratet" and len(k["personen"]) > 1
    if konk:
        h.append("Im Konkubinat versteuert jede Person ihre Bezüge separat (tiefere Progression) – eine PK-Rente "
                 "für den Partner gibt es nach dem Tod aber nur, wenn das Reglement sie vorsieht und die Partnerschaft "
                 "gemeldet ist. Mit Kapital bleibt das Geld für den Partner verfügbar (Testament!).")
    h.append("Reihenfolge: zuerst freies Vermögen und gestaffelte 3a-Bezüge, PK-Kapital im Pensionsjahr (frühestens "
             "3 Jahre nach dem letzten Einkauf), Freizügigkeitsguthaben bis 5 Jahre nach dem Rentenalter aufschieben – "
             "verschiedene Jahre senken die Progression.")
    return h
