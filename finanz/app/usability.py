"""Usability-Prüfung: alle Seiten mit den eigenen Daten rendern und automatisch auf typische Probleme prüfen.

Pro Seite startet der Score bei 100 und verliert Punkte für:
- lange Seiten (viele Karten, sehr viel Text)
- Tabellen, die auf dem Handy seitlich scrollen (mehr als 5 Spalten ohne Kartenansicht) oder sehr lange Kartenlisten
- grosse Formulare mit nur einem «Speichern» am Ende, Eingabefelder ohne Beschriftung
- mehr als 6 Kennzahlen in einer Reihe, Diagramme ohne Beschreibung
Zugeklappte Teile (<details>) zählen nicht; Druckseiten (Notfallordner, Jahresbericht) dürfen lang sein.
- langsame Ladezeit (Messungen unter «Leistung»), Fehler beim Anzeigen
Dazu kommt die Darstellung für alle Seiten: Kontrast der Farben in Hell und Dunkel nach WCAG (mindestens 4.5:1 für
Text). Das Ergebnis (Score gesamt und pro Seite, Vorschläge) wird pro Version gespeichert; die Prüfung läuft einmal am
Tag im Hintergrund oder auf Knopfdruck unter «Vorschläge».
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html.parser import HTMLParser

LOG = logging.getLogger("finanz")
UEBERSPRINGEN = {"vorschlaege", "aenderungen"}   # die Seite mit dem Ergebnis; das Changelog ist absichtlich lang
DRUCKSEITEN = {"notfall", "bericht"}             # zum Ausdrucken gedacht – Länge gewollt
KONTRAST_MIN = 4.5


@dataclass
class Problem:
    titel: str
    detail: str
    abzug: int


@dataclass
class Seite:
    pfad: str
    titel: str
    score: int
    probleme: list[Problem] = field(default_factory=list)
    ms: int = 0


@dataclass
class Ergebnis:
    version: str
    zeit: str
    score: int
    seiten: list[Seite]
    darstellung: list[Problem]


class _Leser(HTMLParser):
    """Sammelt Tabellen, Formulare, Karten, Kennzahlen, Diagramme und Text einer Seite."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tabellen: list[dict] = []
        self.formulare: list[dict] = []
        self.karten = 0
        self.kpis = 0
        self.svg_ohne = 0
        self.ohne_label = 0
        self.text: list[str] = []
        self._tab: list[dict] = []
        self._form: dict | None = None
        self._label = 0
        self._ignorieren = 0
        self._zeile = 0
        self._zu = 0                    # Tiefe in zugeklappten <details> – deren Inhalt sieht man erst auf Wunsch
        self._details: list[bool] = []
        self.kpi_gruppen: list[int] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        klasse = a.get("class") or ""
        if tag == "details":
            zu = "open" not in a
            self._details.append(zu)
            self._zu += zu
        if self._zu:
            return
        if tag in ("script", "style", "textarea", "code", "pre"):
            self._ignorieren += 1
        if tag == "section" and "karte" in klasse.split():
            self.karten += 1
        if tag == "div" and "kpis" in klasse.split():
            self.kpi_gruppen.append(0)
        if tag == "div" and "kpi" in klasse.split():
            self.kpis += 1
            if self.kpi_gruppen:
                self.kpi_gruppen[-1] += 1
        if tag == "svg" and not (a.get("aria-label") or a.get("role") == "img" and a.get("aria-label")):
            self.svg_ohne += 1
        if tag == "table":
            self._tab.append({"klasse": klasse, "spalten": 0, "zeilen": 0, "kopf": True})
        if self._tab:
            t = self._tab[-1]
            if tag == "th" and t["zeilen"] == 0:
                t["spalten"] += 1
            if tag == "tr":
                self._zeile += 1
            if tag == "tbody":
                t["kopf"] = False
            if tag == "tr" and not t["kopf"]:
                t["zeilen"] += 1
        if tag == "form":
            self._form = {"aktion": a.get("action") or "", "felder": 0, "knoepfe": 0}
        if tag == "label":
            self._label += 1
        if tag in ("input", "select", "textarea"):
            typ = (a.get("type") or "text").lower()
            if typ not in ("hidden", "submit", "button", "file"):
                if self._form is not None:
                    self._form["felder"] += 1
                if not self._label and not a.get("aria-label") and not a.get("title") and typ != "checkbox":
                    self.ohne_label += 1
        if tag == "button" and self._form is not None and (a.get("type") or "submit") == "submit":
            self._form["knoepfe"] += 1

    def handle_endtag(self, tag):
        if tag == "details" and self._details:
            self._zu -= self._details.pop()
            return
        if self._zu:
            return
        if tag in ("script", "style", "textarea", "code", "pre") and self._ignorieren:
            self._ignorieren -= 1
        if tag == "table" and self._tab:
            self.tabellen.append(self._tab.pop())
        if tag == "form" and self._form is not None:
            self.formulare.append(self._form)
            self._form = None
        if tag == "label" and self._label:
            self._label -= 1

    def handle_data(self, data):
        if not self._ignorieren and not self._zu and data.strip():
            self.text.append(data)


def pruefen_html(html: str, druckseite: bool = False) -> list[Problem]:
    """Probleme einer gerenderten Seite (nur der Inhalt, ohne Menü; zugeklappte Teile zählen nicht).
    `druckseite`: zum Ausdrucken gedacht (Notfallordner, Jahresbericht) – Länge ist dort gewollt."""
    lz = _Leser()
    lz.feed(html)
    p: list[Problem] = []
    if lz.karten > 8 and not druckseite:
        p.append(Problem("Seite sehr lang", f"{lz.karten} Karten – seltenes in Reiter oder aufklappbare Teile verschieben",
                         min(12, 2 * (lz.karten - 8))))
    zeichen = sum(len(t) for t in lz.text)
    if zeichen > 15000 and not druckseite:
        p.append(Problem("Sehr viel Text", f"rund {zeichen // 1000}k Zeichen – Erklärungen kürzen oder aufklappbar machen",
                         8 if zeichen > 25000 else 4))
    for t in lz.tabellen:
        responsiv = "responsiv" in t["klasse"].split()
        if not responsiv and t["spalten"] > 5:
            p.append(Problem("Tabelle scrollt auf dem Handy seitlich",
                             f"{t['spalten']} Spalten ohne Kartenansicht", 6))
        if responsiv and t["zeilen"] * max(1, t["spalten"]) > 240:
            p.append(Problem("Lange Kartenliste auf dem Handy",
                             f"{t['zeilen']} Zeilen × {t['spalten']} Spalten – Filter, Seiten oder aufklappbare Zeilen",
                             6))
        elif t["zeilen"] > 40:
            p.append(Problem("Lange Tabelle", f"{t['zeilen']} Zeilen – Filter oder «mehr anzeigen»", 4))
    for f in lz.formulare:      # ab 8 Feldern blendet die Seite bei Änderungen eine Speicher-Leiste ein
        if f["felder"] >= 50 and f["knoepfe"] <= 1:
            p.append(Problem("Sehr grosses Formular", f"{f['felder']} Felder mit einem Knopf – in Abschnitte teilen", 4))
    if lz.ohne_label:
        p.append(Problem("Eingabefelder ohne Beschriftung", f"{lz.ohne_label} Feld(er) ohne Label",
                         min(10, 2 * lz.ohne_label)))
    gross = max(lz.kpi_gruppen, default=0)
    if gross > 6:
        p.append(Problem("Viele Kennzahlen auf einmal", f"{gross} Kennzahlen in einer Reihe – die wichtigsten 4–6 zeigen", 4))
    if lz.svg_ohne:
        p.append(Problem("Diagramme ohne Beschreibung", f"{lz.svg_ohne} Diagramm(e) ohne aria-label",
                         min(6, 2 * lz.svg_ohne)))
    return p


# ---------------------------------------------------------------- Farben

def _farben(css: str) -> dict[str, dict[str, str]]:
    erg = {}
    for thema, muster in (("hell", r":root\{([^}]*)\}"), ("dunkel", r"html\[data-theme=dark\]\{([^}]*)\}")):
        block = re.search(muster, css)
        erg[thema] = dict(re.findall(r"--([a-z0-9]+):\s*(#[0-9a-fA-F]{6})", block.group(1) if block else ""))
    for name, wert in erg["hell"].items():
        erg["dunkel"].setdefault(name, wert)
    return erg


def _lum(hexfarbe: str) -> float:
    r, g, b = (int(hexfarbe[i:i + 2], 16) / 255 for i in (1, 3, 5))
    k = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2]


def kontrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


PAARE = [("text", "karte", "Text auf Karten"), ("leise", "karte", "grauer Text auf Karten"),
         ("leise", "bg", "grauer Text auf dem Hintergrund"), ("akzent", "karte", "Links und Zweitknöpfe"),
         ("gut", "karte", "grüne Werte"), ("warn", "karte", "orange Werte"), ("schlecht", "karte", "rote Werte")]


def darstellung(css: str) -> list[Problem]:
    f = _farben(css)
    p = []
    for thema, farben in f.items():
        for vorne, hinten, text in PAARE:
            if vorne in farben and hinten in farben:
                k = kontrast(farben[vorne], farben[hinten])
                if k < KONTRAST_MIN:
                    p.append(Problem(f"Kontrast zu schwach ({thema}): {text}", f"{k:.1f}:1 statt mindestens 4.5:1", 3))
        # Knöpfe: Text auf der Akzentfarbe
        knopf = "#ffffff" if thema == "hell" else _knopf_dunkel(css)
        if "akzent" in farben and kontrast(knopf, farben["akzent"]) < KONTRAST_MIN:
            p.append(Problem(f"Kontrast zu schwach ({thema}): Text auf Knöpfen",
                             f"{kontrast(knopf, farben['akzent']):.1f}:1 statt mindestens 4.5:1", 5))
    return p


def _knopf_dunkel(css: str) -> str:
    m = re.search(r"html\[data-theme=dark\] button[^{]*\{color:(#[0-9a-fA-F]{6})", css)
    return m.group(1) if m else "#ffffff"


# ---------------------------------------------------------------- alle Seiten

def pruefen(k: dict, db, version: str = "") -> Ergebnis:
    import leistung as le
    import meta
    import seiten
    import server
    version = version or meta.version()
    zeiten = {}
    try:
        for m in le.messungen(db)[0]:
            if m.art == "seite":
                zeiten[m.name] = m.mittel_ms
    except Exception:  # noqa: BLE001
        pass
    liste = []
    for pfad, (titel, funktion) in server.SEITEN.items():
        if pfad in UEBERSPRINGEN or "/" in pfad:
            continue
        t0 = time.perf_counter()
        try:
            html = funktion(k, db, {}) if pfad in server.MIT_ABFRAGE else funktion(k, db)
            probleme = pruefen_html(html, pfad in DRUCKSEITEN)
        except Exception as e:  # noqa: BLE001
            LOG.warning("Usability: Seite %s nicht anzeigbar: %s", pfad or "übersicht", e)
            probleme = [Problem("Seite lässt sich nicht anzeigen", type(e).__name__, 40)]
        ms = round((time.perf_counter() - t0) * 1000)
        gemessen = zeiten.get(le.seitenname(pfad))
        ms_eff = max(ms, int(gemessen or 0))
        if ms_eff > 1000:
            probleme.append(Problem("Seite lädt langsam", f"rund {ms_eff / 1000:.1f} s",
                                    20 if ms_eff > 5000 else 10 if ms_eff > 2000 else 5))
        reiter = {p_: t_ for gruppe in seiten.REITER for p_, t_ in gruppe}
        name = next((n for p_, n in seiten.NAV if p_ == pfad), None) or (
            f"{titel} · {reiter[pfad]}" if pfad in reiter and reiter[pfad] != titel else titel)
        score = max(0, 100 - sum(x.abzug for x in probleme))
        liste.append(Seite(pfad, name, score, probleme, ms_eff))
    dar = darstellung(seiten.CSS)
    mittel = sum(s.score for s in liste) / len(liste) if liste else 100
    gesamt = max(0, round(mittel - sum(x.abzug for x in dar)))
    return Ergebnis(version, datetime.now().isoformat(timespec="minutes"), gesamt,
                    sorted(liste, key=lambda s: s.score), dar)


def tabellen(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS usability (version TEXT PRIMARY KEY, zeit TEXT NOT NULL, daten TEXT NOT NULL)")


def sichern(db, e: Ergebnis) -> None:
    tabellen(db)
    db.execute("INSERT OR REPLACE INTO usability VALUES (?, ?, ?)", (e.version, e.zeit, json.dumps(asdict(e))))
    db.commit()


def _laden(d: dict) -> Ergebnis:
    return Ergebnis(d["version"], d["zeit"], d["score"],
                    [Seite(s["pfad"], s["titel"], s["score"], [Problem(**p) for p in s["probleme"]], s.get("ms", 0))
                     for s in d["seiten"]], [Problem(**p) for p in d["darstellung"]])


def letztes(db) -> tuple[Ergebnis | None, Ergebnis | None]:
    """(neuestes Ergebnis, das der Version davor)."""
    tabellen(db)
    zeilen = db.execute("SELECT daten FROM usability ORDER BY zeit DESC LIMIT 2").fetchall()
    erg = [_laden(json.loads(z[0])) for z in zeilen]
    return (erg[0] if erg else None, erg[1] if len(erg) > 1 else None)


def faellig(db, version: str, heute: str) -> bool:
    tabellen(db)
    z = db.execute("SELECT zeit FROM usability WHERE version = ?", (version,)).fetchone()
    return not z or z[0][:10] < heute


def vorschlaege(db) -> list[tuple[str, str, int]]:
    """(Titel, Detail, Gewicht) für die Vorschläge – ohne persönliche Daten (nur Seitennamen und Mengen)."""
    e, _ = letztes(db)
    if not e:
        return []
    erg = []
    for p in e.darstellung:
        erg.append((p.titel, p.detail, 3 if p.abzug >= 5 else 2))
    for s in e.seiten:
        for p in s.probleme:
            erg.append((f"Seite «{s.titel}»: {p.titel}", p.detail, 3 if p.abzug >= 10 else 2 if p.abzug >= 5 else 1))
    return erg


def bericht_text(db) -> list[str]:
    e, vorher = letztes(db)
    if not e:
        return []
    alt = {s.pfad: s.score for s in (vorher.seiten if vorher else [])}
    z = [f"Usability-Score {e.score}/100" + (f" (vorher {vorher.score}, Version {vorher.version})" if vorher else "")]
    for s in e.seiten:
        if s.score < 100:
            z.append(f"{s.titel}: {s.score}" + (f" (vorher {alt[s.pfad]})" if s.pfad in alt else "") + " – "
                     + "; ".join(p.titel for p in s.probleme))
    return z
