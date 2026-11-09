"""Fristen der Steuererklärung (natürliche Personen, unselbständig erwerbend) nach Kanton.

Stand: Steuerjahr 2025 (Einreichung 2026). Quellen: Übersichten von taxea.ch und swisslivingindex.ch sowie Blick
(März 2026). Wo die Quellen voneinander abweichen oder die Frist auf dem Formular steht, ist `pruefen` gesetzt.
Massgebend ist immer das Datum auf der zugestellten Steuererklärung; eigene Werte unter
`erinnerungen.steuererklaerung_frist` und `erinnerungen.fristerstreckung` haben Vorrang.
"""
from __future__ import annotations

from dataclasses import dataclass

# Kanton: (ordentliche Frist MM-TT, spätestmögliche Erstreckung MM-TT oder "", prüfen?, Hinweis)
FRISTEN: dict[str, tuple[str, str, bool, str]] = {
    "AG": ("03-31", "", False, "Erstreckung auf Gesuch; kostenlos bis Ende Juni."),
    "AI": ("04-30", "11-30", False, ""),
    "AR": ("03-31", "10-31", True, "Frist steht auch auf dem Formular."),
    "BE": ("03-15", "11-15", False, "Kostenlos bis Mitte Juli, danach gebührenpflichtig."),
    "BL": ("03-31", "11-30", False, "Bis rund zwei Monate nach der Frist werden keine Mahnungen verschickt; "
                                   "Erstreckung online über die Steuerverwaltung."),
    "BS": ("03-31", "12-31", True, "Kostenlos bis Ende September."),
    "FR": ("03-31", "12-15", False, ""),
    "GE": ("03-31", "08-31", True, "Quellen nennen als spätestes Datum August bis Dezember."),
    "GL": ("03-31", "12-31", True, "Frist steht auch auf dem Formular."),
    "GR": ("03-31", "09-30", True, "Selbständige 30. September; spätere Erstreckung je nach Quelle bis November."),
    "JU": ("02-28", "10-31", True, "Quellen nennen Ende Februar bzw. Mitte Juli."),
    "LU": ("", "08-31", True, "Frist steht auf dem Formular (rund 30 Tage nach Zustellung)."),
    "NE": ("02-21", "10-31", True, "Kostenlos bis Ende April."),
    "NW": ("03-31", "12-31", False, ""),
    "OW": ("03-31", "12-31", True, "Quellen nennen 31. März bzw. 30. April."),
    "SG": ("03-31", "12-31", True, "Frist steht auch auf dem Formular."),
    "SH": ("03-31", "11-30", False, ""),
    "SO": ("03-31", "11-30", False, "Kostenlos bis Ende Juli."),
    "SZ": ("03-31", "12-31", False, ""),
    "TG": ("04-30", "11-30", True, "Kostenlos bis Ende September; Frist steht auch auf dem Formular."),
    "TI": ("04-30", "12-31", True, ""),
    "UR": ("03-31", "09-30", True, ""),
    "VD": ("03-15", "09-30", False, "Kostenlos bis Ende Juni."),
    "VS": ("03-31", "07-31", True, "Quellen nennen Juli bzw. Dezember als spätestes Datum."),
    "ZG": ("04-30", "12-31", False, ""),
    "ZH": ("03-31", "11-30", False, ""),
}

NAMEN = {
    "AG": "Aargau", "AI": "Appenzell Innerrhoden", "AR": "Appenzell Ausserrhoden", "BE": "Bern", "BL": "Basel-Landschaft",
    "BS": "Basel-Stadt", "FR": "Freiburg", "GE": "Genf", "GL": "Glarus", "GR": "Graubünden", "JU": "Jura", "LU": "Luzern",
    "NE": "Neuenburg", "NW": "Nidwalden", "OW": "Obwalden", "SG": "St. Gallen", "SH": "Schaffhausen", "SO": "Solothurn",
    "SZ": "Schwyz", "TG": "Thurgau", "TI": "Tessin", "UR": "Uri", "VD": "Waadt", "VS": "Wallis", "ZG": "Zug", "ZH": "Zürich",
}


@dataclass
class Frist:
    kanton: str
    frist: str               # MM-TT
    erstreckung: str         # MM-TT oder ""
    gewaehlt: str            # tatsächlich verwendete Frist (eigene Erstreckung oder ordentliche Frist)
    quelle: str              # "kanton" | "eigen" | "erstreckt" | "standard"
    pruefen: bool
    hinweis: str

    @property
    def name(self) -> str:
        return NAMEN.get(self.kanton, self.kanton)


def _mmtt(text: str) -> str:
    t = str(text or "").strip().strip(".-")
    if not t:
        return ""
    teile = t.replace(".", "-").split("-")
    if len(teile) == 3 and len(teile[0]) == 4:          # JJJJ-MM-TT
        teile = teile[1:]
    elif len(teile) >= 2 and len(teile[-1]) == 4:        # TT.MM.JJJJ oder TT.MM.
        teile = [teile[1], teile[0]]
    elif len(teile) == 2 and "." in t:                   # TT.MM
        teile = [teile[1], teile[0]]
    m, d = int(teile[-2]), int(teile[-1])
    if not (1 <= m <= 12 and 1 <= d <= 31):
        raise ValueError(f"Datum nicht erkannt: {text!r} (erwartet MM-TT)")
    return f"{m:02d}-{d:02d}"


def steuererklaerung(k: dict) -> Frist:
    kanton = str(k["haushalt"].get("kanton", "") or "").strip().upper()
    cfg = k.get("erinnerungen") or {}
    frist, erstreckung, pruefen, hinweis = FRISTEN.get(kanton, ("03-31", "", True, "Kanton unbekannt – 31. März angenommen."))
    quelle = "kanton" if kanton in FRISTEN else "standard"
    eigen = _mmtt(cfg.get("steuererklaerung_frist", ""))
    if eigen and eigen != frist:
        frist, quelle, pruefen = eigen, "eigen", False
    elif eigen:
        pruefen = False
    if not frist:
        frist, quelle = "03-31", "standard"
        hinweis = (hinweis + " " if hinweis else "") + "Bis zur Eingabe der Frist wird der 31. März angenommen."
    gewaehlt = frist
    erstreckt = _mmtt(cfg.get("fristerstreckung", ""))
    if erstreckt:
        gewaehlt, quelle = erstreckt, "erstreckt"
    return Frist(kanton, frist, erstreckung, gewaehlt, quelle, pruefen, hinweis)


# ---------------------------------------------------------------- Liegenschaft

# Eigenmietwert Bund = Eigenmietwert Staat × Faktor (BL: Zuschlag 1,2 laut Wegleitung eTax BL)
EMW_BUND_FAKTOR = {"BL": 1.2}
# Pauschaler Unterhaltsabzug Staatssteuer in % (Gebäude bis 10 Jahre, älter); Bund: 10 % / 20 %
PAUSCHAL_STAAT = {"BL": (20.0, 25.0)}
PAUSCHAL_BUND = (10.0, 20.0)


def _kanton(k: dict) -> str:
    return str(k["haushalt"].get("kanton", "") or "").strip().upper()


def emw_bund_faktor(k: dict) -> float:
    return EMW_BUND_FAKTOR.get(_kanton(k), 1.0)


def pauschale(k: dict, neu: bool) -> tuple[float, float]:
    """Unterhaltspauschale (Staat, Bund) in % – `neu` = Gebäude bis 10 Jahre alt."""
    staat = PAUSCHAL_STAAT.get(_kanton(k), PAUSCHAL_BUND)
    i = 0 if neu else 1
    return staat[i], PAUSCHAL_BUND[i]
