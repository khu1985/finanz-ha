"""Steuern bezahlen: Rechnungen (provisorisch, definitiv), Zahlungen, offene Beträge, Fälligkeit und Zinsen.

Pro Steuerjahr und Steuer (Staats- und Gemeindesteuer, separat erhobene Gemeindesteuer, direkte Bundessteuer):
- Soll: definitive Rechnung (Veranlagung) vor provisorischer Rechnung vor Schätzung aus «Steuern heute».
  Rechnungen von Hand oder aus hochgeladenen Steuerdokumenten (provisorische Rechnung, Veranlagungsverfügung).
- Bezahlt: von Hand erfasste Zahlungen und aus den Buchungen (Kategorie «Steuern») übernommene.
- Offen, Fälligkeit, Verzugszins nach dem Verfall, Vergütungszins für Vorauszahlungen, Betrag pro Monat zum
  Zurücklegen und – mit der definitiven Rechnung – Nachzahlung bzw. Rückerstattung.

Fälligkeit und Zinsen (Stand 2026):
- Kanton BL: provisorische Rechnung im Januar, Staatssteuer fällig am 30. September des Steuerjahres; danach
  Verzugszins 5 % (2026), Vergütungszins auf Vorauszahlungen 0,1 % (2026). Die Gemeinden erheben ihre Steuer
  zum Teil selbst – Fälligkeit dann laut Rechnung der Gemeinde.
- Direkte Bundessteuer: fällig am 1. März des Folgejahres, zahlbar innert 30 Tagen; Verzugszins 4,0 %,
  Vergütungszins auf Vorauszahlungen 0,0 % (2026).
- Übrige Kantone: Vergütungszins 2026 laut Übersicht von Beobachter/cash.ch (Quelle moneyland.ch); Fälligkeit
  30. September angenommen, bis ein eigenes Datum eingetragen ist (steht auf der provisorischen Rechnung).
Eigene Werte unter `steuerzahlung` in der Konfiguration haben Vorrang.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

import re
from dataclasses import dataclass, field
from datetime import date

ARTEN = {"kanton": "Staats- und Gemeindesteuer", "gemeinde": "Gemeindesteuer", "bund": "Direkte Bundessteuer"}
TYPEN = {"provisorisch": "provisorische Rechnung", "definitiv": "definitive Rechnung"}

# Verfall der Staatssteuer im Steuerjahr (MM-TT); fehlt der Kanton: 30. September, zu prüfen
FAELLIG_KANTON = {"BL": "09-30"}
FAELLIG_BUND = "03-31"          # Folgejahr: fällig 1. März, zahlbar innert 30 Tagen
# Vergütungszins 2026 auf Vorauszahlungen in % (Beobachter/cash.ch, Quelle moneyland.ch und Kantone)
VERGUETUNG_2026 = {
    "AG": 0.25, "AR": 1.0, "AI": 1.0, "BL": 0.1, "BS": 0.5, "BE": 0.25, "FR": 0.0, "GE": 0.1, "GL": 1.0, "GR": 0.25,
    "JU": 0.0, "LU": 0.0, "NE": 0.0, "NW": 0.0, "OW": 0.5, "SH": 1.0, "SZ": 0.5, "SO": 0.0, "SG": 0.25, "TI": 0.1,
    "TG": 1.0, "UR": 0.25, "VS": 0.25, "ZG": 2.0, "ZH": 0.75,
}
VERZUG_2026 = {"BL": 5.0}
VERZUG_STANDARD = 4.0           # wenn der Kanton fehlt: Satz des Bundes als Annahme
BUND_VERGUETUNG, BUND_VERZUG = 0.0, 4.0

QUELLEN = [
    ("Kanton BL: Fälligkeit der Staatssteuer",
     "https://www.baselland.ch/politik-und-behorden/direktionen/finanz-und-kirchendirektion/steuerverwaltung/"
     "aktuelles-aus-der-steuerverwaltung/faelligkeit-der-staatssteuer-2024"),
    ("Kanton BL: Zinssätze", "https://www.baselland.ch/politik-und-behorden/direktionen/finanz-und-kirchendirektion/"
                             "steuerverwaltung/steuerzahlungen/zinssaetze"),
    ("Bund: Vergütungs- und Verzugszinsen ab 2026",
     "https://law.ch/lawnews/2025/10/neue-verguetungs-und-verzugszinssaetze-fuer-bundessteuern-abgaben-sanktionen-ab-2026/"),
    ("Beobachter: Vergütungszins aller Kantone 2024–2026",
     "https://www.beobachter.ch/geld/steuern/hier-lohnt-es-sich-die-steuern-fruh-zu-zahlen-die-ubersicht-918027"),
]


def _chf(v: float) -> str:
    return f"{v:,.0f}" >> TS


def tabellen(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS steuer_rechnungen (jahr INTEGER NOT NULL, art TEXT NOT NULL, typ TEXT NOT NULL,
            betrag REAL NOT NULL, faellig TEXT NOT NULL DEFAULT '', PRIMARY KEY (jahr, art, typ));
        CREATE TABLE IF NOT EXISTS steuer_zahlungen (id INTEGER PRIMARY KEY, jahr INTEGER NOT NULL, art TEXT NOT NULL,
            datum TEXT NOT NULL, betrag REAL NOT NULL, notiz TEXT NOT NULL DEFAULT '', quelle TEXT NOT NULL DEFAULT '');
        """
    )


# ---------------------------------------------------------------- Einstellungen

def _kanton(k: dict) -> str:
    return str(k["haushalt"].get("kanton", "") or "").strip().upper()


def cfg(k: dict) -> dict:
    return dict(k.get("steuerzahlung") or {})


def _zahl(v, std: float | None = None) -> float | None:
    try:
        return float(v) if v not in (None, "") else std
    except (TypeError, ValueError):
        return std


def gemeinde_anteil(k: dict) -> float:
    """Anteil der Gemeinde an Staats- und Gemeindesteuer (0–1) aus dem Gemeindesteuerfuss (% der Staatssteuer):
    Fuss ÷ (100 + Fuss); sonst aus den getrennt erfassten Beträgen, zuletzt aus dem alten Feld `gemeinde_anteil`."""
    st = k.get("steuern") or {}
    fuss = _zahl(st.get("gemeindesteuerfuss"), 0) or 0
    if fuss:
        return fuss / (100 + fuss)
    staat, gem = _zahl(st.get("staatssteuer"), 0) or 0, _zahl(st.get("gemeindesteuer"), 0) or 0
    if staat and gem:
        return gem / (staat + gem)
    return (_zahl(cfg(k).get("gemeinde_anteil"), 0) or 0) / 100


def gemeinde_separat(k: dict) -> bool:
    return bool(cfg(k).get("gemeinde_separat")) and gemeinde_anteil(k) > 0


def arten(k: dict) -> list[str]:
    return ["kanton", "gemeinde", "bund"] if gemeinde_separat(k) else ["kanton", "bund"]


def bezeichnung(k: dict, art: str) -> str:
    if art == "kanton" and gemeinde_separat(k):
        return "Staatssteuer"
    return ARTEN.get(art, art)


def _mmtt(text) -> str:
    import kantone
    try:
        return kantone._mmtt(text)
    except (ValueError, IndexError):
        return ""


def faellig(k: dict, art: str, jahr: int) -> tuple[date, bool]:
    """Fälligkeit (Verfall) und ob das Datum nur angenommen ist."""
    c = cfg(k)
    if art == "bund":
        m, t = (int(x) for x in FAELLIG_BUND.split("-"))
        return date(jahr + 1, m, t), False
    eigen = _mmtt(c.get("faellig_gemeinde") if art == "gemeinde" else c.get("faellig_kanton"))
    if not eigen and art == "gemeinde":
        eigen = _mmtt(c.get("faellig_kanton"))
    std = FAELLIG_KANTON.get(_kanton(k))
    mmtt = eigen or std or "09-30"
    m, t = (int(x) for x in mmtt.split("-"))
    return date(jahr, m, t), not eigen and (not std or art == "gemeinde")


def zinsen(k: dict, art: str) -> tuple[float, float]:
    """(Vergütungszins, Verzugszins) in % pro Jahr."""
    c = cfg(k)
    if art == "bund":
        return BUND_VERGUETUNG, BUND_VERZUG
    kt = _kanton(k)
    return (_zahl(c.get("verguetungszins"), VERGUETUNG_2026.get(kt, 0.0)),
            _zahl(c.get("verzugszins"), VERZUG_2026.get(kt, VERZUG_STANDARD)))


# ---------------------------------------------------------------- Rechnungen und Zahlungen

def rechnung_speichern(db, jahr: int, art: str, typ: str, betrag: float, faellig_: str = "") -> None:
    tabellen(db)
    if art not in ARTEN or typ not in TYPEN:
        raise ValueError("Steuer bzw. Art der Rechnung unbekannt.")
    if not 2000 <= jahr <= 2100 or betrag < 0:
        raise ValueError("Steuerjahr bzw. Betrag prüfen.")
    db.execute("INSERT OR REPLACE INTO steuer_rechnungen VALUES (?, ?, ?, ?, ?)", (jahr, art, typ, betrag, faellig_ or ""))


def rechnung_loeschen(db, jahr: int, art: str, typ: str) -> None:
    tabellen(db)
    db.execute("DELETE FROM steuer_rechnungen WHERE jahr = ? AND art = ? AND typ = ?", (jahr, art, typ))


def zahlung_speichern(db, jahr: int, art: str, datum: str, betrag: float, notiz: str = "", quelle: str = "") -> int:
    tabellen(db)
    if art not in ARTEN:
        raise ValueError("Steuer unbekannt.")
    date.fromisoformat(datum)
    if not betrag:
        raise ValueError("Betrag angeben.")
    cur = db.execute("INSERT INTO steuer_zahlungen (jahr, art, datum, betrag, notiz, quelle) VALUES (?, ?, ?, ?, ?, ?)",
                     (jahr, art, datum, betrag, (notiz or "").strip()[:120], quelle))
    return cur.lastrowid


def zahlung_loeschen(db, zid: int) -> None:
    tabellen(db)
    db.execute("DELETE FROM steuer_zahlungen WHERE id = ?", (zid,))


def zahlungen(db) -> list[dict]:
    tabellen(db)
    return [dict(r) for r in db.execute("SELECT * FROM steuer_zahlungen ORDER BY datum DESC, id DESC")]


def rechnungen(k: dict, db) -> dict[tuple[int, str, str], dict]:
    """Rechnungen je (Jahr, Steuer, Typ): von Hand erfasste vor solchen aus hochgeladenen Steuerdokumenten."""
    tabellen(db)
    erg: dict[tuple[int, str, str], dict] = {}
    try:
        import steuerdokumente as sd
        for d in sd.alle(db):
            typ = {"rechnung": "provisorisch", "veranlagung": "definitiv"}.get(d["typ"])
            w = d.get("werte") or {}
            if not typ or not d.get("jahr"):
                continue
            kanton = float(w.get("steuer_kanton_gemeinde") or 0) + float(w.get("vermoegenssteuer") or 0)
            teile = [("kanton", kanton), ("bund", float(w.get("bundessteuer") or 0))]
            if gemeinde_separat(k):
                anteil = gemeinde_anteil(k)
                verm = float(w.get("vermoegenssteuer") or 0)
                if w.get("staatssteuer") and w.get("gemeindesteuer"):
                    staat, gem = float(w["staatssteuer"]) + verm * (1 - anteil), float(w["gemeindesteuer"]) + verm * anteil
                else:
                    staat, gem = kanton * (1 - anteil), kanton * anteil
                teile = [("kanton", staat), ("gemeinde", gem), teile[1]]
            for art, betrag in teile:
                if betrag > 0:
                    alt = erg.get((d["jahr"], art, typ))
                    erg[(d["jahr"], art, typ)] = {"betrag": betrag + (alt["betrag"] if alt and d["person"] != alt.get(
                        "person") else 0), "faellig": "", "quelle": "Dokument", "person": d.get("person")}
    except Exception:  # noqa: BLE001 – Dokumente sind optional
        pass
    for r in db.execute("SELECT * FROM steuer_rechnungen"):
        erg[(r["jahr"], r["art"], r["typ"])] = {"betrag": r["betrag"], "faellig": r["faellig"], "quelle": "eigene Angabe"}
    return erg


def _art_raten(k: dict, text: str) -> str:
    t = text.lower()
    if "bund" in t:
        return "bund"
    if "gemeinde" in t and gemeinde_separat(k) and not re.search(r"staats|kanton", t):
        return "gemeinde"
    return "kanton"


def _jahr_raten(art: str, text: str, tag: date) -> int:
    m = re.findall(r"\b(20[2-4]\d)\b", text)
    if m:
        return int(m[-1])
    if art == "bund":
        return tag.year - 1 if tag.month <= 6 else tag.year
    return tag.year - 1 if tag.month <= 1 else tag.year


def aus_buchungen(k: dict, db) -> list[dict]:
    """Belastungen der Kategorie «Steuern» aus den Buchungen, die noch nicht als Zahlung übernommen sind."""
    import budget as bu
    tabellen(db)
    schon = {r[0] for r in db.execute("SELECT quelle FROM steuer_zahlungen WHERE quelle != ''")}
    erg = []
    for b in bu.alle(db):
        if b.get("kategorie") != "Steuern" or b["betrag"] >= 0:
            continue
        q = f"buchung:{b['id']}"
        if q in schon:
            continue
        text = b.get("text") or ""
        art = _art_raten(k, text)
        erg.append({"quelle": q, "datum": b["datum"], "betrag": -b["betrag"], "text": text, "art": art,
                    "jahr": _jahr_raten(art, text, date.fromisoformat(b["datum"]))})
    return erg


def buchungen_uebernehmen(k: dict, db) -> int:
    neu = aus_buchungen(k, db)
    for b in neu:
        zahlung_speichern(db, b["jahr"], b["art"], b["datum"], b["betrag"], b["text"][:120], b["quelle"])
    return len(neu)


# ---------------------------------------------------------------- Auswertung

@dataclass
class Posten:
    jahr: int
    art: str
    name: str
    soll: float
    quelle: str                 # "definitiv" | "provisorisch" | "geschätzt"
    bezahlt: float
    faellig: date
    faellig_angenommen: bool
    verguetungszins: float      # % p.a.
    verzugszins: float          # % p.a.
    verzug_bisher: float        # aufgelaufener Verzugszins (Schätzung)
    verguetung_jetzt: float     # Vergütungszins, wenn der offene Betrag heute bezahlt wird
    monatlich: float            # bis zur Fälligkeit pro Monat zurücklegen
    differenz: float | None     # definitiv minus provisorisch (positiv = Nachzahlung)
    hinweise: list[str] = field(default_factory=list)

    @property
    def offen(self) -> float:
        return round(self.soll - self.bezahlt)


def _schaetzung(k: dict) -> dict[str, float]:
    import steuern as st
    s = st.steuern_heute(k)
    kanton = float(s["kanton"]) + float(s["vermoegen"])
    erg = {"kanton": kanton, "bund": float(s["bund"])}
    if gemeinde_separat(k):
        anteil = gemeinde_anteil(k)
        erg["gemeinde"], erg["kanton"] = kanton * anteil, kanton * (1 - anteil)
    return erg


def _monate_bis(heute: date, ziel: date) -> int:
    return max(1, (ziel.year - heute.year) * 12 + ziel.month - heute.month + (1 if ziel.day >= heute.day else 0))


def auswerten(k: dict, db, heute: date | None = None) -> list[Posten]:
    """Offene und kürzlich fällige Steuern: Vorjahr (wenn erfasst), laufendes und nächstes Steuerjahr."""
    heute = heute or date.today()
    re_ = rechnungen(k, db)
    bez: dict[tuple[int, str], float] = {}
    for z in zahlungen(db):
        bez[(z["jahr"], z["art"])] = bez.get((z["jahr"], z["art"]), 0.0) + float(z["betrag"])
    schaetzung = _schaetzung(k)
    try:
        import anlage as an
        zins_konto = float(an.konfiguration(k).get("zins_konto") or 0)
    except Exception:  # noqa: BLE001
        zins_konto = 0.0
    erg = []
    for jahr in range(heute.year - 2, heute.year + 2):
        for art in arten(k):
            fae, angenommen = faellig(k, art, jahr)
            daten = any(key[0] == jahr and key[1] == art for key in re_) or (jahr, art) in bez
            if not daten and not (heute <= fae <= date(heute.year + 1, 12, 31) and (fae - heute).days <= 400):
                continue
            prov, defi = re_.get((jahr, art, "provisorisch")), re_.get((jahr, art, "definitiv"))
            if defi:
                soll, quelle = defi["betrag"], "definitiv"
            elif prov:
                soll, quelle = prov["betrag"], "provisorisch"
            else:
                soll, quelle = schaetzung.get(art, 0.0), "geschätzt"
            for r in (defi, prov):
                if r and r.get("faellig"):
                    try:
                        fae, angenommen = date.fromisoformat(r["faellig"]), False
                    except ValueError:
                        pass
                    break
            bezahlt = round(bez.get((jahr, art), 0.0))
            vg, vz = zinsen(k, art)
            offen = soll - bezahlt
            p = Posten(jahr, art, bezeichnung(k, art), round(soll), quelle, bezahlt, fae, angenommen, vg, vz, 0.0, 0.0,
                       0.0, round(defi["betrag"] - prov["betrag"]) if defi and prov else None)
            if not daten and soll <= 0:
                continue
            if offen > 0.5:
                if heute > fae and quelle != "definitiv":
                    p.verzug_bisher = round(offen * vz / 100 * (heute - fae).days / 365)
                    p.hinweise.append(f"Seit {fae:%d.%m.%Y} fällig – auf CHF {_chf(offen)} läuft Verzugszins von {vz:g} % "
                                      f"(bisher rund CHF {_chf(p.verzug_bisher)}).")
                elif heute > fae:
                    p.hinweise.append(f"Nachzahlung CHF {_chf(offen)} laut definitiver Rechnung – Zahlungsfrist auf der "
                                      "Rechnung (meist 30 Tage).")
                else:
                    p.verguetung_jetzt = round(offen * vg / 100 * (fae - heute).days / 365)
                    p.monatlich = round(offen / _monate_bis(heute, fae))
                    if vg > zins_konto and p.verguetung_jetzt >= 5:
                        p.hinweise.append(f"Jetzt bezahlen bringt rund CHF {_chf(p.verguetung_jetzt)} Vergütungszins ({vg:g} %, "
                                          f"mehr als das Sparkonto mit {zins_konto:g} %).")
                    elif zins_konto > vg:
                        p.hinweise.append(f"Bis zur Fälligkeit auf dem Sparkonto lassen ({zins_konto:g} % statt {vg:g} % "
                                          f"Vergütungszins) und spätestens am {fae:%d.%m.%Y} bezahlen.")
            elif offen < -0.5:
                p.hinweise.append(f"CHF {_chf(-offen)} zu viel bezahlt – kommt mit der definitiven Rechnung zurück"
                                  + (" (mit Vergütungszins)." if vg else "."))
            if p.differenz:
                p.hinweise.append(("Nachzahlung" if p.differenz > 0 else "Rückerstattung")
                                  + f" gegenüber der provisorischen Rechnung: CHF {_chf(abs(p.differenz))}.")
            if quelle == "geschätzt" and fae >= heute:
                p.hinweise.append("Betrag geschätzt aus «Steuern heute» – mit der provisorischen Rechnung ersetzen.")
            if angenommen and fae >= heute:
                p.hinweise.append("Fälligkeit angenommen – Datum auf der Rechnung prüfen und unten eintragen.")
            erg.append(p)
    return erg


def offen_total(posten: list[Posten]) -> float:
    return round(sum(max(0.0, p.offen) for p in posten))


def faellige(posten: list[Posten], heute: date, bis: date) -> list[tuple[date, Posten]]:
    """Offene Beträge, die bis `bis` fällig werden (überfällige auf heute)."""
    return sorted(((max(p.faellig, heute), p) for p in posten if p.offen > 0 and p.faellig <= bis), key=lambda x: x[0])


def erinnerungen(k: dict, db, heute: date) -> list:
    import erinnerungen as er
    erg = []
    for p in auswerten(k, db, heute):
        if p.offen <= 0:
            continue
        tage = (p.faellig - heute).days
        if -60 <= tage <= 45:
            text = (f"Offen CHF {_chf(p.offen)} ({p.quelle})." + (" " + p.hinweise[0] if p.hinweise else ""))
            erg.append(er.Erinnerung(f"steuer-zahlen-{p.art}-{p.jahr}", f"{p.name} {p.jahr} bezahlen", p.faellig, text,
                                     "steuerzahlung"))
    return erg
