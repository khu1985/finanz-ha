"""Amortisationsstrategie: Varianten bis zur Pensionierung im Vergleich.

Gerechnet wird Jahr für Jahr von heute bis zur ersten Pensionierung, für jede Variante gleich:
- Hypothek: Konten der Art «Hypothek» (sonst Kaufpreis − Eigenmittel), Zins `wohnen.hypothek_zins`.
  Festhypotheken lassen sich nur bei Fälligkeit (`wohnen.hypothek_faellig`, danach alle 5 Jahre angenommen)
  ohne Vorfälligkeitsentschädigung amortisieren; laufende Amortisation setzt eine flexible (SARON-)Tranche voraus.
- Schuldzinsabzug: bis zum Wegfall des Eigenmietwerts (`kennzahlen.eigenmietwert_abschaffung`, 1.1.2029) voll
  abziehbar, danach nur noch im Verhältnis des vermieteten Teils (wohnen.eigenmietwert_wegfall). Steuerwirkung zum
  heutigen Grenzsteuersatz.
- Geld, das nicht amortisiert wird, bleibt angelegt: sicher (Zins `anlage.zins_sicher`, als Einkommen versteuert)
  bzw. zum Vergleich in Wertschriften (Rendite des Anlagerisikos, ⅓ davon als steuerbarer Ertrag).
- Liquidität: freie Konten (ohne `wohnen.nicht_antasten`) plus Sparen pro Jahr (Überschuss nach allen Ausgaben, also
  nach den heutigen Zinsen – höhere oder tiefere Zinskosten kommen als Differenz dazu); Untergrenze `wohnen.reserve`.
  Der Wegfall des Eigenmietwerts verändert die Steuern für alle Varianten gleich und fällt im Vergleich weg; nur der
  wegfallende Schuldzinsabzug wirkt je nach Hypothek verschieden.
- Tragbarkeit im Alter: kalkulatorischer Zins (`kennzahlen.tragbarkeit_zins`) und 1 % Nebenkosten des Werts im
  Verhältnis zu Renten und 80 % der Mieteinnahmen; Banken verlangen höchstens ⅓ (`kennzahlen.tragbarkeit_max`).
- Verpfändete Säule 3a/3b (`wohnen.verpfaendet`) wachsen in allen Varianten gleich; «Tragbarkeit im Alter»
  amortisiert sie bei der Pensionierung zusätzlich (indirekte Amortisation).
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

from dataclasses import dataclass, field
from datetime import date


def _chf(v: float) -> str:
    return f"{v:,.0f}" >> TS


def _z(v, std: float = 0.0) -> float:
    try:
        return float(v or 0) or std
    except (TypeError, ValueError):
        return std


@dataclass
class Variante:
    schluessel: str
    name: str
    beschreibung: str
    amortisation: dict[int, float]          # Jahr → Betrag
    hypothek: dict[int, float] = field(default_factory=dict)      # Ende Jahr
    liquiditaet: dict[int, float] = field(default_factory=dict)
    zinsen_netto: float = 0.0               # Hypothekarzinsen nach Steuern bis zur Pensionierung
    ertrag_netto: float = 0.0               # Ertrag auf nicht amortisiertem Geld nach Steuern
    netto: float = 0.0                      # Liquidität − Hypothek bei Pensionierung (sicher angelegt)
    netto_anlage: float = 0.0               # dito mit Wertschriften-Rendite
    tragbarkeit_alter: float = 0.0          # % bei Pensionierung
    min_liquiditaet: float = 0.0
    hinweise: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(self.amortisation.values()))


@dataclass
class Strategie:
    start_hypothek: float
    wert: float
    zins: float
    faellig: date | None
    pension: int
    abschaffung: int
    grenz: float                    # Grenzsteuersatz total %
    abzug_nachher: float            # Anteil der Schuldzinsen, der nach dem Wegfall abziehbar bleibt (0–1)
    liquid: float
    sparen_jahr: float
    reserve: float
    verpfaendet_pension: float
    einkommen_alter: float
    max_hypothek_alter: float        # tragbar im Alter
    zins_sicher: float
    rendite_anlage: float
    varianten: list[Variante]
    empfehlung: str
    empfehlung_anlage: str
    hinweise: list[str] = field(default_factory=list)


def _faelligkeiten(faellig: date | None, heute: date, bis: int) -> list[int]:
    if not faellig:
        return []
    j = faellig.year
    erg = []
    while j <= bis:
        if j >= heute.year:
            erg.append(j)
        j += 5
    return erg


def rechnen(k: dict, db, heute: date | None = None) -> Strategie | None:
    import anlage as an
    import steuern as st
    import vermoegen as vm
    import vorsorge as vs
    import wohnen as wo
    heute = heute or date.today()
    w = k.get("wohnen") or {}
    if not w.get("aktiv"):
        return None
    konten = vm.konten(db) if db is not None else []
    hyp_konten = [x for x in konten if x["art"] == "hypothek" and not x.get("aufgeloest")]
    hypothek = -sum(x["wert"] for x in hyp_konten) if hyp_konten else max(0.0, _z(w.get("kaufpreis")) - _z(w.get("eigenmittel")))
    if hypothek <= 0:
        return None
    wert = _z((w.get("liegenschaft") or {}).get("marktwert")) or _z(w.get("kaufpreis"))
    zins = _z(w.get("hypothek_zins"), 1.5) / 100
    try:
        faellig = date.fromisoformat(str(w.get("hypothek_faellig") or "")[:10])
    except ValueError:
        faellig = None
    pension = min(vs.pensionsjahr(p) for p in k["personen"])
    abschaffung = int(_z(k["kennzahlen"].get("eigenmietwert_abschaffung"), 2029))
    t = st.steuern_heute(k)
    grenz = float(t.get("grenz_total") or 30) / 100
    try:
        abzug_nachher = wo.eigenmietwert_wegfall(k)["zins_quote"] / 100
    except Exception:  # noqa: BLE001
        abzug_nachher = _z(w.get("vermietet_anteil")) / 100
    ausnahmen = set(w.get("nicht_antasten") or ["krypto", "immobilie", "hypothek", "kredit", "vorsorge", "saeule3a"])
    liquid = sum(x["wert"] for x in konten if x["art"] not in ausnahmen and x["art"] not in vm.NICHT_FREI
                 and not x.get("aufgeloest"))
    sparen = sum(_z(p.get("sparen_monat")) for p in k["personen"]) * 12
    reserve = _z(w.get("reserve"))
    jahre_bis_pension = max(0, pension - heute.year)
    verpf = 0.0
    for v in w.get("verpfaendet") or []:
        r = _z(v.get("rendite")) / 100
        verpf += _z(v.get("guthaben")) * (1 + r) ** jahre_bis_pension + _z(v.get("beitrag_monat")) * 12 * jahre_bis_pension
    # Tragbarkeit im Alter
    try:
        einkommen_alter = vs.pensionsluecke(k, vm.nettovermoegen(db)["frei"] if db is not None else 0).einkommen
    except Exception:  # noqa: BLE001
        einkommen_alter = 0.0
    einkommen_alter += 0.8 * _z(w.get("mieteinnahmen_jahr"))
    kz = k["kennzahlen"]
    kalk, max_quote = _z(kz.get("tragbarkeit_zins"), 5.0) / 100, _z(kz.get("tragbarkeit_max"), 33.3) / 100
    max_hyp_alter = max(0.0, (einkommen_alter * max_quote - 0.01 * wert) / kalk) if einkommen_alter else 0.0
    cfg = an.konfiguration(k)
    zins_sicher = _z(cfg.get("zins_sicher"), 1.0) / 100
    rendite_anlage = float(cfg["rendite"].get(cfg.get("risiko", "mittel"), 3.5)) / 100

    termine = _faelligkeiten(faellig, heute, pension)
    erster = termine[0] if termine else None
    ziel = _z(w.get("amortisation_ziel"))
    maximal = _z(w.get("amortisation_max"))
    varianten: list[Variante] = [Variante("keine", "Nicht amortisieren", "Hypothek bleibt; Geld bleibt angelegt.", {})]
    _simulieren(varianten[0], heute.year, pension, hypothek, zins, grenz, abschaffung, abzug_nachher, liquid, sparen,
                zins_sicher, rendite_anlage, wert, einkommen_alter, kalk, 0.0, reserve)
    vorher = varianten[0].liquiditaet.get((erster or heute.year) - 1, liquid)
    verfuegbar_erster = max(0.0, vorher - reserve) if erster else 0.0
    if erster:
        if ziel:
            varianten.append(Variante("ziel", f"Ziel bei Fälligkeit {erster}",
                                      f"CHF {_chf(ziel)} bei Fälligkeit (Ziel unter Wohnen).", {erster: ziel}))
        mx = min(maximal or verfuegbar_erster, max(0.0, verfuegbar_erster), hypothek)
        if mx > 0 and (not ziel or abs(mx - ziel) > 1000):
            varianten.append(Variante("max", f"Maximum bei Fälligkeit {erster}",
                                      f"So viel wie möglich (CHF {_chf(mx)}), Notreserve bleibt.", {erster: mx}))
        laufend = {erster: ziel or mx / 2}
        for j in range(erster + 1, pension):
            laufend[j] = sparen * 0.5
        varianten.append(Variante("laufend", "Fälligkeit + jährlich",
                                  f"CHF {_chf(laufend[erster])} bei Fälligkeit, danach jedes Jahr die Hälfte des Sparens "
                                  f"(CHF {_chf(sparen * 0.5)}) – braucht eine flexible Tranche (SARON).", laufend))
    noetig = max(0.0, hypothek - max_hyp_alter - verpf) if max_hyp_alter else 0.0
    plan: dict[int, float] = {}
    rest = noetig
    vor_pension = [j for j in termine if j < pension]
    for j in vor_pension:
        teil = rest / max(1, len([x for x in vor_pension if x >= j]))
        plan[j] = teil
        rest -= teil
    if verpf or plan:
        varianten.append(Variante("alter", "Indirekt, tragbar im Alter",
                                  (f"Direkt nur CHF {_chf(noetig)} verteilt auf die Fälligkeiten, " if noetig else
                                   "Direkt nichts; ") + f"bei der Pensionierung die verpfändete 3a/3b (rund CHF "
                                  f"{_chf(verpf)}) – Schuldzinsen bleiben bis {abschaffung - 1} voll abziehbar.", plan))
    for v in varianten[1:]:
        _simulieren(v, heute.year, pension, hypothek, zins, grenz, abschaffung, abzug_nachher, liquid, sparen,
                    zins_sicher, rendite_anlage, wert, einkommen_alter, kalk, verpf if v.schluessel == "alter" else 0.0,
                    reserve)
    basis = varianten[0]
    for v in varianten[1:]:
        if v.min_liquiditaet < reserve:
            v.hinweise.append(f"Liquidität sinkt auf CHF {_chf(v.min_liquiditaet)} – unter die Notreserve von "
                              f"CHF {_chf(reserve)}.")
        diff = v.netto - basis.netto
        v.hinweise.append(f"{'+' if diff >= 0 else '−'}CHF {_chf(abs(diff))} gegenüber «nicht amortisieren» bei sicherer "
                          f"Anlage; mit Wertschriften {('+' if v.netto_anlage >= basis.netto_anlage else '−')}CHF "
                          f"{_chf(abs(v.netto_anlage - basis.netto_anlage))}.")
    ok = [v for v in varianten if v.min_liquiditaet >= reserve - 1 and v.tragbarkeit_alter <= max_quote * 100 + 0.1]
    beste = max(ok or varianten, key=lambda v: v.netto)
    beste_anl = max(ok or varianten, key=lambda v: v.netto_anlage)
    hinweise = []
    if abschaffung > heute.year:
        hinweise.append(f"Ab {abschaffung} fällt der Eigenmietwert weg: Schuldzinsen sind dann nur noch zu rund "
                        f"{abzug_nachher * 100:.0f} % abziehbar (vermieteter Teil). Amortisieren lohnt danach mehr, "
                        "weil die gesparten Zinsen nicht mehr Steuern sparen.")
    netto_hyp = zins * (1 - grenz * abzug_nachher) * 100
    netto_sicher = zins_sicher * (1 - grenz) * 100
    hinweise.append(f"Ab {abschaffung}: Hypothek kostet nach Steuern rund {netto_hyp:.2f} %, sicher angelegtes Geld bringt "
                    f"nach Steuern rund {netto_sicher:.2f} % – jeder amortisierte Franken spart die Differenz.")
    if max_hyp_alter and hypothek > max_hyp_alter:
        hinweise.append(f"Tragbar im Alter wäre eine Hypothek bis rund CHF {_chf(max_hyp_alter)} (Renten und Mieteinnahmen "
                        f"CHF {_chf(einkommen_alter)} pro Jahr) – heute CHF {_chf(hypothek)}. Die Bank prüft das spätestens "
                        "bei der Verlängerung kurz vor der Pensionierung.")
    if termine:
        hinweise.append(f"Festhypotheken nur bei Fälligkeit amortisieren ({', '.join(map(str, termine))}); dazwischen kostet "
                        "es eine Vorfälligkeitsentschädigung.")
    if k["haushalt"].get("zivilstand", "verheiratet") != "verheiratet" and len(k["personen"]) > 1:
        hinweise.append("Konkubinat: Jede Person amortisiert aus eigenem Geld ihren Anteil – sonst verschieben sich Eigentum "
                        "und Erbe (Nachlass, Schenkung an die andere Person).")
    return Strategie(round(hypothek), round(wert), zins * 100, faellig, pension, abschaffung, grenz * 100, abzug_nachher,
                     round(liquid), round(sparen), round(reserve), round(verpf), round(einkommen_alter),
                     round(max_hyp_alter), zins_sicher * 100, rendite_anlage * 100, varianten, beste.schluessel,
                     beste_anl.schluessel, hinweise)


def _simulieren(v: Variante, von: int, pension: int, hypothek: float, zins: float, grenz: float, abschaffung: int,
                abzug_nachher: float, liquid: float, sparen: float, zins_sicher: float, rendite: float, wert: float,
                einkommen_alter: float, kalk: float, verpf_alter: float, reserve: float) -> None:
    h, c, c_anl = hypothek, liquid, liquid
    zinsen = ertrag = 0.0
    z0 = hypothek * zins * (1 - grenz)          # heutige Zinslast – steckt schon im Sparen (Überschuss nach Ausgaben)
    mins = []
    for j in range(von, pension):
        abzug = 1.0 if j < abschaffung else abzug_nachher
        betrag = min(v.amortisation.get(j, 0.0), h)
        h -= betrag
        c -= betrag
        c_anl -= betrag
        z = h * zins * (1 - grenz * abzug)
        e = max(0.0, c) * zins_sicher * (1 - grenz)
        e_anl = max(0.0, c_anl) * rendite * (1 - grenz / 3)
        c += sparen + z0 - z + e
        c_anl += sparen + z0 - z + e_anl
        zinsen += z
        ertrag += e
        v.hypothek[j] = round(h)
        v.liquiditaet[j] = round(c)
        mins.append(c)
    h_alter = max(0.0, h - verpf_alter)
    v.hypothek[pension] = round(h_alter)
    v.zinsen_netto, v.ertrag_netto = round(zinsen), round(ertrag)
    v.netto, v.netto_anlage = round(c - h), round(c_anl - h)
    v.min_liquiditaet = round(min(mins) if mins else c)
    v.tragbarkeit_alter = round((h_alter * kalk + 0.01 * wert) / einkommen_alter * 100, 1) if einkommen_alter else 0.0
