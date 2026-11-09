"""Hypothekar-Strategie: SARON, Festhypotheken und Mischungen über Zinsszenarien vergleichen.

Modell (jährlich, Beträge in heutigen Franken):
- SARON-Pfad je Szenario: von heute linear auf das Zielniveau innert der Anstiegsjahre, danach konstant.
- SARON-Hypothek: max(SARON, 0) + Marge.
- Festhypothek L Jahre: heute zum aktuellen Satz; bei Verlängerung zum SARON des Verlängerungsjahres plus der
  heutigen Laufzeitprämie (Festsatz L − SARON heute).
- Eine Strategie besteht aus Tranchen (Anteil, Produkt); jede Tranche wird bis zum Ende des Horizonts verlängert.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

from dataclasses import dataclass, field
from datetime import date

STANDARD = {
    "start": "",                  # leer = wohnen.hypothek_faellig
    "betrag": 0,                  # 0 = Hypothek nach dem Amortisations-Szenario
    "horizont_jahre": 10,
    "saron": 0.0,                 # aktueller SARON in %
    "marge_saron": 1.10,          # Zuschlag der Bank auf den SARON
    "fest": {2: 1.52, 3: 1.65, 5: 1.75, 7: 1.85, 10: 1.98},   # Richtsätze Migros Bank, Stand 08.11.2026 – eigene Offerten eintragen
    "forward_aufschlag": 0.15,    # Aufschlag pro Vorlaufjahr für eine Forward-Festhypothek
    "szenarien": {
        "tief": {"ziel": 0.0, "jahre": 1},
        "basis": {"ziel": 1.0, "jahre": 4},
        "stress": {"ziel": 3.0, "jahre": 3},
    },
    "strategien": [],             # eigene: [{name, tranchen: [{anteil: 50, produkt: saron|fest5|fest10 …}]}]
}

STANDARD_STRATEGIEN = [
    {"name": "SARON 100 %", "tranchen": [{"anteil": 100, "produkt": "saron"}]},
    {"name": "Fest 5 Jahre (verlängert)", "tranchen": [{"anteil": 100, "produkt": "fest5"}]},
    {"name": "Fest 10 Jahre", "tranchen": [{"anteil": 100, "produkt": "fest10"}]},
    {"name": "Mix ⅓ SARON, ⅓ 5 J., ⅓ 10 J.",
     "tranchen": [{"anteil": 33.3, "produkt": "saron"}, {"anteil": 33.3, "produkt": "fest5"}, {"anteil": 33.4, "produkt": "fest10"}]},
    {"name": "Staffel ⅓ je 3, 7, 10 J.",
     "tranchen": [{"anteil": 33.3, "produkt": "fest3"}, {"anteil": 33.3, "produkt": "fest7"}, {"anteil": 33.4, "produkt": "fest10"}]},
    {"name": "Staffel ½ 5 J., ½ 10 J.", "tranchen": [{"anteil": 50, "produkt": "fest5"}, {"anteil": 50, "produkt": "fest10"}]},
]


def konfiguration(k: dict) -> dict:
    eigen = (k.get("wohnen") or {}).get("strategie") or {}
    cfg = {**STANDARD, **{s: v for s, v in eigen.items() if v not in (None, "")}}
    cfg["fest"] = {int(j): float(z) for j, z in {**STANDARD["fest"], **(eigen.get("fest") or {})}.items()}
    cfg["szenarien"] = {**STANDARD["szenarien"], **(eigen.get("szenarien") or {})}
    return cfg


def saron_pfad(saron: float, ziel: float, jahre: int, horizont: int) -> list[float]:
    jahre = max(1, int(jahre))
    return [round(saron + (ziel - saron) * min(1.0, (t + 1) / jahre), 4) for t in range(horizont)]


def _festsatz(cfg: dict, laufzeit: int) -> float:
    if laufzeit in cfg["fest"]:
        return cfg["fest"][laufzeit]
    # zwischen zwei Laufzeiten linear interpolieren
    punkte = sorted(cfg["fest"].items())
    for (l0, z0), (l1, z1) in zip(punkte, punkte[1:]):
        if l0 < laufzeit < l1:
            return z0 + (z1 - z0) * (laufzeit - l0) / (l1 - l0)
    return punkte[-1][1] if laufzeit > punkte[-1][0] else punkte[0][1]


def tranche_zinsen(cfg: dict, produkt: str, pfad: list[float]) -> list[float]:
    """Zinssatz der Tranche pro Jahr (in %)."""
    if produkt == "saron":
        return [max(0.0, s) + cfg["marge_saron"] for s in pfad]
    laufzeit = int(produkt.replace("fest", ""))
    praemie = _festsatz(cfg, laufzeit) - cfg["saron"]
    saetze, satz = [], _festsatz(cfg, laufzeit)
    for t in range(len(pfad)):
        if t > 0 and t % laufzeit == 0:
            satz = max(0.0, pfad[t]) + praemie
        saetze.append(satz)
    return saetze


@dataclass
class Ergebnis:
    name: str
    tranchen: list
    kosten: dict[str, float]               # Szenario → Zinskosten über den Horizont
    max_jahr: dict[str, float]             # Szenario → höchste Jahreskosten
    satz: dict[str, list[float]]           # Szenario → Mischzins pro Jahr
    zinsbindung: float                     # gewichtete Jahre mit festem Zins (Sicherheit)
    flexibel: float                        # Anteil SARON (jederzeit amortisierbar)

    @property
    def spannweite(self) -> float:
        return max(self.kosten.values()) - min(self.kosten.values())


@dataclass
class Strategie:
    start: date
    betrag: float
    horizont: int
    pfade: dict[str, list[float]]
    ergebnisse: list[Ergebnis]
    empfehlung: str
    hinweise: list[str] = field(default_factory=list)
    forward_satz: dict[int, float] = field(default_factory=dict)


def vergleichen(k: dict, db=None, heute: date | None = None) -> Strategie | None:
    heute = heute or date.today()
    w = k["wohnen"]
    if not w.get("aktiv"):
        return None
    cfg = konfiguration(k)
    start_txt = cfg.get("start") or w.get("hypothek_faellig") or heute.isoformat()
    start = date.fromisoformat(str(start_txt))
    betrag = float(cfg.get("betrag") or 0)
    if not betrag:
        hypothek = max(0.0, float(w.get("kaufpreis", 0)) - float(w.get("eigenmittel", 0)))
        betrag = hypothek
        if db is not None:
            import berater as br
            a = br.amortisation(k, db, heute)
            if a:
                betrag = a.hypothek_danach
    horizont = int(cfg["horizont_jahre"])
    pfade = {n: saron_pfad(cfg["saron"], float(s["ziel"]), int(s["jahre"]), horizont) for n, s in cfg["szenarien"].items()}
    strategien = cfg.get("strategien") or STANDARD_STRATEGIEN
    ergebnisse = []
    for s in strategien:
        tr = s["tranchen"]
        summe = sum(float(t["anteil"]) for t in tr) or 100
        kosten, max_jahr, saetze = {}, {}, {}
        for n, pfad in pfade.items():
            misch = [0.0] * horizont
            for t in tr:
                z = tranche_zinsen(cfg, t["produkt"], pfad)
                misch = [m + float(t["anteil"]) / summe * x for m, x in zip(misch, z)]
            saetze[n] = [round(x, 3) for x in misch]
            jahreskosten = [betrag * x / 100 for x in misch]
            kosten[n] = round(sum(jahreskosten))
            max_jahr[n] = round(max(jahreskosten))
        bindung = sum(float(t["anteil"]) / summe * (0 if t["produkt"] == "saron" else min(int(t["produkt"][4:]), horizont))
                      for t in tr)
        flex = sum(float(t["anteil"]) / summe for t in tr if t["produkt"] == "saron")
        ergebnisse.append(Ergebnis(s["name"], tr, kosten, max_jahr, saetze, round(bindung, 1), round(flex * 100)))
    # Empfehlung für «maximale Sicherheit»: tiefste Kosten im Stress, bei Gleichstand tiefere Basis-Kosten
    stress = "stress" if "stress" in pfade else list(pfade)[-1]
    basis = "basis" if "basis" in pfade else list(pfade)[0]
    beste = min(ergebnisse, key=lambda e: (e.kosten[stress], e.kosten[basis]))
    hinw = []
    saron = next((e for e in ergebnisse if e.name.startswith("SARON")), None)
    if saron:
        praemie = beste.kosten[basis] - saron.kosten[basis]
        hinw.append(f"«{beste.name}» kostet im Basisszenario CHF {_chf(praemie)} mehr als SARON – das ist der Preis der "
                    f"Sicherheit; im Stressszenario spart sie CHF {_chf(saron.kosten[stress] - beste.kosten[stress])}.")
    vorlauf = max(0, (start - heute).days // 365)
    forward = {}
    if vorlauf >= 1:
        for laufzeit in (5, 10):
            forward[laufzeit] = round(_festsatz(cfg, laufzeit) + cfg["forward_aufschlag"] * vorlauf, 2)
        hinw.append(f"Bis zur Fälligkeit dauert es noch rund {vorlauf} Jahr(e). Mit einer Forward-Festhypothek lässt sich der Zins "
                    f"heute fixieren (Richtwert 10 J.: {forward[10]:.2f} %, Aufschlag {cfg['forward_aufschlag']:.2f} % pro Jahr Vorlauf). "
                    "Offerten meist ab 12–36 Monaten vor Fälligkeit. Die Tabelle rechnet ab Fälligkeit mit den heutigen Sätzen.")
    hinw.append("Festhypotheken lassen sich vor Ablauf nur gegen Vorfälligkeitsentschädigung auflösen – Amortisationen "
                "auf Ablauftermine legen oder in eine SARON-Tranche einplanen.")
    if beste.flexibel == 0:
        hinw.append("Eine kleine SARON- oder kurze Festtranche hält Spielraum für spätere Amortisationen offen.")
    hinw.append("Laufzeiten staffeln verteilt das Risiko, zu einem ungünstigen Zeitpunkt alles neu finanzieren zu müssen.")
    return Strategie(start, round(betrag), horizont, pfade, ergebnisse, beste.name, hinw, forward)


def _chf(v: float) -> str:
    return f"{v:,.0f}" >> TS
