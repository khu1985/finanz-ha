"""UX-Score: wie die App erlebt und genutzt wird – Befragung, Verhalten und technische Usability.

Abgrenzung: Der Usability-Score (usability.py) prüft automatisch, ob die Oberfläche handwerklich gut bedienbar ist
(ISO 9241-11: Effektivität, Effizienz, Zufriedenheit bei einer Aufgabe). UX (ISO 9241-210) umfasst das ganze
Erleben: Nutzen, Vertrauen, ob man gerne zurückkommt und ob die Daten gepflegt bleiben.

Teile (0–100, gewichtet 40/40/20; fehlt ein Teil, zählen die übrigen im gleichen Verhältnis):
- Befragung: UEQ-S (User Experience Questionnaire, Kurzform; Schrepp, Hinderks & Thomaschewski 2017) mit 8
  Gegensatzpaaren von −3 bis +3 – pragmatische Qualität (Bedienung) und hedonische Qualität (Erleben) – plus zwei
  eigene Aussagen: «Ich vertraue den Zahlen» und «Die App hilft mir zu entscheiden» (1–5). Alle 90 Tage.
- Verhalten (angelehnt an Googles HEART-Modell), letzte 90 Tage: Wochen mit Nutzung, Anteil genutzter Seiten,
  Formulare ohne Eingabefehler, Aktualität der Daten (Saldi, PK-Ausweis) und überfällige Erinnerungen.
- Usability: der automatische Score der aktuellen Version.

Aufgezeichnet werden nur Seitenaufrufe und Formulare (Seitenname, Zeit, ob mit Eingabefehler) – keine Inhalte,
nur in der eigenen Datenbank; ausschalten mit `ux.aufzeichnen: false`. Einträge älter als 400 Tage werden gelöscht.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

UEQ_S = [  # (negativ, positiv, Skala)
    ("behindernd", "unterstützend", "pragmatisch"),
    ("kompliziert", "einfach", "pragmatisch"),
    ("ineffizient", "effizient", "pragmatisch"),
    ("verwirrend", "übersichtlich", "pragmatisch"),
    ("langweilig", "spannend", "hedonisch"),
    ("uninteressant", "interessant", "hedonisch"),
    ("konventionell", "originell", "hedonisch"),
    ("herkömmlich", "neuartig", "hedonisch"),
]
EIGENE = [("vertrauen", "Ich vertraue den Zahlen der App."),
          ("nutzen", "Die App hilft mir, finanzielle Entscheide zu treffen.")]
GEWICHTE = {"befragung": 0.4, "verhalten": 0.4, "usability": 0.2}
UMFRAGE_TAGE = 90
# Grössere Änderungen an der Bedienung (Vertrauen, «Heute», Menü, Kurz-Zeilen, Checklisten): danach nach zwei Wochen
# Nutzung erneut fragen, auch wenn die 90 Tage noch nicht um sind
UX_AENDERUNG = date(2026, 11, 22)
FENSTER = 90
QUELLEN = [("UEQ – User Experience Questionnaire (Kurzform UEQ-S)", "https://www.ueq-online.org/"),
           ("HEART-Framework (Google Research)", "https://research.google/pubs/measuring-the-user-experience-on-a-large-scale-user-centered-metrics-for-web-applications/")]

_PUFFER: list[tuple[str, str, str]] = []
_SPERRE = threading.Lock()
_AN = True


def einstellen(k: dict) -> None:
    global _AN
    _AN = bool((k.get("ux") or {}).get("aufzeichnen", True))


def tabellen(db) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS ux_ereignisse (zeit TEXT NOT NULL, art TEXT NOT NULL, seite TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS ux_ereignisse_zeit ON ux_ereignisse (zeit);
        CREATE TABLE IF NOT EXISTS ux_umfrage (datum TEXT PRIMARY KEY, antworten TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ux_verlauf (datum TEXT PRIMARY KEY, score INTEGER NOT NULL, teile TEXT NOT NULL);
    """)


def erfassen(art: str, seite: str) -> None:
    """art: aufruf | ok | fehler. Nur im Speicher – `sichern` schreibt in die Datenbank."""
    if not _AN:
        return
    with _SPERRE:
        _PUFFER.append((datetime.now().isoformat(timespec="seconds"), art, (seite or "übersicht").split("/")[0] or "übersicht"))
        if len(_PUFFER) > 5000:
            del _PUFFER[:1000]


def sichern(db) -> None:
    with _SPERRE:
        neu = list(_PUFFER)
        _PUFFER.clear()
    tabellen(db)
    if neu:
        db.executemany("INSERT INTO ux_ereignisse VALUES (?, ?, ?)", neu)
    grenze = (date.today() - timedelta(days=400)).isoformat()
    db.execute("DELETE FROM ux_ereignisse WHERE zeit < ?", (grenze,))
    db.commit()


# ---------------------------------------------------------------- Befragung

def umfrage_speichern(db, antworten: dict, heute: date | None = None) -> None:
    tabellen(db)
    for i, _ in enumerate(UEQ_S):
        w = antworten.get(f"u{i}")
        if w is None or not -3 <= int(w) <= 3:
            raise ValueError("Bitte alle 8 Gegensatzpaare beantworten.")
    for s, _ in EIGENE:
        w = antworten.get(s)
        if w is None or not 1 <= int(w) <= 5:
            raise ValueError("Bitte beide Aussagen bewerten.")
    daten = {k_: int(v) for k_, v in antworten.items() if k_.startswith("u") or k_ in dict(EIGENE)}
    if antworten.get("notiz"):
        daten["notiz"] = str(antworten["notiz"])[:500]
    db.execute("INSERT OR REPLACE INTO ux_umfrage VALUES (?, ?)", ((heute or date.today()).isoformat(),
                                                                    json.dumps(daten, ensure_ascii=False)))


def umfragen(db) -> list[tuple[str, dict]]:
    tabellen(db)
    return [(r[0], json.loads(r[1])) for r in db.execute("SELECT datum, antworten FROM ux_umfrage ORDER BY datum")]


def umfrage_faellig(db, heute: date | None = None) -> bool:
    heute = heute or date.today()
    u = umfragen(db)
    if not u:
        return True
    letzte = date.fromisoformat(u[-1][0])
    if letzte < UX_AENDERUNG <= heute - timedelta(days=14):
        return True
    return (heute - letzte).days >= UMFRAGE_TAGE


@dataclass
class Befragung:
    datum: str
    pragmatisch: float          # −3 … +3
    hedonisch: float
    vertrauen: int              # 1 … 5
    nutzen: int
    tiefste: str                # schwächstes Gegensatzpaar
    score: int                  # 0 … 100


def befragung(db, heute: date | None = None) -> Befragung | None:
    heute = heute or date.today()
    u = umfragen(db)
    if not u or (heute - date.fromisoformat(u[-1][0])).days > 2 * UMFRAGE_TAGE:
        return None
    datum, a = u[-1]
    werte = [int(a.get(f"u{i}", 0)) for i in range(len(UEQ_S))]
    prag = sum(werte[:4]) / 4
    hed = sum(werte[4:]) / 4
    i = min(range(len(werte)), key=lambda j: werte[j])
    score = ((prag + 3) / 6 + (hed + 3) / 6 + (int(a["vertrauen"]) - 1) / 4 + (int(a["nutzen"]) - 1) / 4) / 4 * 100
    return Befragung(datum, round(prag, 2), round(hed, 2), int(a["vertrauen"]), int(a["nutzen"]),
                     f"{UEQ_S[i][0]} – {UEQ_S[i][1]}", round(score))


def bewertung_ueq(wert: float) -> str:
    """Einordnung nach UEQ: über +0,8 positiv, unter −0,8 negativ."""
    return "positiv" if wert > 0.8 else "negativ" if wert < -0.8 else "neutral"


# ---------------------------------------------------------------- Verhalten

def _seiten() -> dict[str, str]:
    import seiten
    erg: dict[str, str] = {}
    for _, eintraege in seiten.NAVIGATION:
        for pfad, titel in eintraege:
            erg[pfad] = titel
    for gruppe in seiten.REITER:
        for pfad, titel in gruppe:
            erg.setdefault(pfad, titel)
    return erg


@dataclass
class Verhalten:
    tage: int                   # Tage mit Aufzeichnung im Fenster
    wochen_aktiv: int
    wochen: int
    seiten_genutzt: int
    seiten_total: int
    ungenutzt: list[str]
    formulare: int
    eingabefehler: int
    fehler_seiten: list[tuple[str, int, int]]      # (Seite, Fehler, Formulare)
    saldi_tage: int | None
    pk_monate: list[tuple[str, int]]
    erinnerungen_ueberfaellig: int
    teile: dict[str, float]     # Teilwert → 0 … 1
    score: int | None


def _alter_saldi(db) -> int | None:
    z = db.execute("SELECT MAX(s.datum) FROM saldi s JOIN konten k ON k.id = s.konto_id WHERE k.art = 'bank'"
                   ).fetchone()[0]
    return (date.today() - date.fromisoformat(z[:10])).days if z else None


def _linear(wert: float, gut: float, schlecht: float) -> float:
    if wert <= gut:
        return 1.0
    if wert >= schlecht:
        return 0.0
    return 1 - (wert - gut) / (schlecht - gut)


def verhalten(k: dict, db, heute: date | None = None) -> Verhalten:
    import erinnerungen as er
    heute = heute or date.today()
    tabellen(db)
    von = (heute - timedelta(days=FENSTER)).isoformat()
    ereignisse = db.execute("SELECT zeit, art, seite FROM ux_ereignisse WHERE zeit >= ?", (von,)).fetchall()
    erster = db.execute("SELECT MIN(zeit) FROM ux_ereignisse").fetchone()[0]
    tage = min(FENSTER, (heute - date.fromisoformat(erster[:10])).days + 1) if erster else 0
    seiten = _seiten()
    import seiten as se
    alias = se.MENU_ALIAS
    aufrufe = [(z, s) for z, a, s in ereignisse if a == "aufruf"]
    besucht = {s for _, s in aufrufe} | {alias.get(s, s) for _, s in aufrufe}
    besucht |= {"" for _, s in aufrufe if s == "übersicht"}
    ungenutzt = [t for p, t in seiten.items() if p not in besucht]
    wochen = max(1, min(13, (tage + 6) // 7))
    aktiv = len({date.fromisoformat(z[:10]).isocalendar()[:2] for z, _ in aufrufe})
    formulare = [(a, s) for _, a, s in ereignisse if a in ("ok", "fehler")]
    fehler = sum(1 for a, _ in formulare if a == "fehler")
    pro_seite: dict[str, list[int]] = {}
    for a, s in formulare:
        x = pro_seite.setdefault(s, [0, 0])
        x[1] += 1
        x[0] += a == "fehler"
    fehler_seiten = sorted(((seiten.get(s, s), f, n) for s, (f, n) in pro_seite.items() if f), key=lambda x: -x[1])
    saldi = _alter_saldi(db)
    pk = []
    for p in k["personen"]:
        try:
            stand = date.fromisoformat(str((p.get("pk") or {}).get("stand") or "")[:10])
            pk.append((p["name"], (heute.year - stand.year) * 12 + heute.month - stand.month))
        except ValueError:
            pass
    try:
        ueber = sum(1 for e in er.alle(k, db, heute) if (heute - e.faellig).days > 30)
    except Exception:  # noqa: BLE001
        ueber = 0
    teile: dict[str, float] = {}
    if tage >= 7:
        teile["Nutzung"] = min(1.0, aktiv / wochen)
        teile["Seiten genutzt"] = len(seiten) and (len(seiten) - len(ungenutzt)) / len(seiten)
    if len(formulare) >= 3:
        teile["Formulare ohne Fehler"] = 1 - fehler / len(formulare)
    akt = []
    if saldi is not None:
        akt.append(_linear(saldi, 35, 120))
    akt += [_linear(m, 15, 27) for _, m in pk]
    akt.append(max(0.0, 1 - ueber / 8))
    teile["Daten aktuell"] = sum(akt) / len(akt)
    score = round(sum(teile.values()) / len(teile) * 100) if teile else None
    return Verhalten(tage, aktiv, wochen, len(seiten) - len(ungenutzt), len(seiten), ungenutzt, len(formulare), fehler,
                     fehler_seiten, saldi, pk, ueber, teile, score)


# ---------------------------------------------------------------- Gesamt

@dataclass
class Ergebnis:
    score: int | None
    teile: dict[str, int | None]
    befragung: Befragung | None
    verhalten: Verhalten
    usability: int | None
    umfrage_faellig: bool
    hinweise: list[tuple[str, str, int]] = field(default_factory=list)   # (Titel, Detail, Gewicht 1–3)


def berechnen(k: dict, db, heute: date | None = None) -> Ergebnis:
    import usability as us
    heute = heute or date.today()
    b = befragung(db, heute)
    v = verhalten(k, db, heute)
    e, _ = us.letztes(db)
    u = e.score if e else None
    teile = {"befragung": b.score if b else None, "verhalten": v.score, "usability": u}
    da = {n: w for n, w in teile.items() if w is not None}
    score = round(sum(w * GEWICHTE[n] for n, w in da.items()) / sum(GEWICHTE[n] for n in da)) if da else None
    faellig = umfrage_faellig(db, heute)
    h: list[tuple[str, str, int]] = []
    if faellig and v.tage >= 14:
        h.append(("Kurzbefragung zur App ausfüllen", "8 Gegensatzpaare und 2 Aussagen, rund eine Minute – alle 90 Tage.", 2))
    if v.tage >= 30 and v.ungenutzt:
        h.append((f"{len(v.ungenutzt)} Seiten in {min(v.tage, FENSTER)} Tagen nicht geöffnet",
                  ", ".join(v.ungenutzt[:8]) + (" …" if len(v.ungenutzt) > 8 else "")
                  + " – nicht gebraucht, nicht gefunden oder nicht verständlich?", 1))
    for titel, f, n in v.fehler_seiten[:3]:
        if f >= 2 and f / n >= 0.2:
            h.append((f"Formulare auf «{titel}» oft mit Eingabefehler", f"{f} von {n} abgeschickten Formularen", 2))
    if v.saldi_tage is not None and v.saldi_tage > 45:
        h.append(("Saldi der Bankkonten veraltet", f"letzter Stand vor {v.saldi_tage} Tagen – Import oder Erfassung "
                  "zu umständlich?", 2))
    for name, m in v.pk_monate:
        if m > 15:
            h.append((f"PK-Ausweis von {name} {m} Monate alt", "neuen Vorsorgeausweis hochladen", 1))
    if v.erinnerungen_ueberfaellig >= 3:
        h.append((f"{v.erinnerungen_ueberfaellig} Erinnerungen seit über 30 Tagen offen",
                  "erledigen oder prüfen, ob sie zu früh bzw. unnötig kommen", 2))
    if b:
        if b.pragmatisch < 0.8:
            h.append(("Befragung: Bedienung nur neutral bzw. negativ", f"pragmatische Qualität {b.pragmatisch:+.1f} "
                      f"(UEQ, −3 bis +3); schwächstes Paar «{b.tiefste}»", 3 if b.pragmatisch < -0.8 else 2))
        if b.vertrauen <= 3:
            h.append(("Befragung: Vertrauen in die Zahlen tief", f"{b.vertrauen} von 5 – welche Zahlen wirken falsch?", 3))
        if b.nutzen <= 3:
            h.append(("Befragung: App hilft wenig bei Entscheiden", f"{b.nutzen} von 5", 2))
    return Ergebnis(score, teile, b, v, u, faellig, h)


def verlauf_sichern(k: dict, db, heute: date | None = None) -> None:
    heute = heute or date.today()
    tabellen(db)
    if db.execute("SELECT 1 FROM ux_verlauf WHERE datum = ?", (heute.isoformat(),)).fetchone():
        return
    e = berechnen(k, db, heute)
    if e.score is not None:
        db.execute("INSERT OR REPLACE INTO ux_verlauf VALUES (?, ?, ?)",
                   (heute.isoformat(), e.score, json.dumps(e.teile)))
        db.commit()


def verlauf(db) -> list[tuple[str, int, dict]]:
    tabellen(db)
    return [(r[0], r[1], json.loads(r[2])) for r in db.execute("SELECT * FROM ux_verlauf ORDER BY datum")]


def vorschlaege(k: dict, db) -> list[tuple[str, str, int]]:
    """Für die Vorschläge (Bereich «UX») – nur Seitennamen, Mengen und Bewertungen, keine persönlichen Daten."""
    return [(t, d, g) for t, d, g in berechnen(k, db).hinweise if not t.startswith("PK-Ausweis von")]


def erinnerungen(k: dict, db, heute: date) -> list:
    import erinnerungen as er
    tabellen(db)
    erster = db.execute("SELECT MIN(zeit) FROM ux_ereignisse").fetchone()[0]
    if not erster or (heute - date.fromisoformat(erster[:10])).days < 14 or not umfrage_faellig(db, heute):
        return []
    u = umfragen(db)
    stichtag = date.fromisoformat(u[-1][0]) + timedelta(days=UMFRAGE_TAGE) if u else heute
    if u and date.fromisoformat(u[-1][0]) < UX_AENDERUNG:
        stichtag = min(stichtag, UX_AENDERUNG + timedelta(days=14))
    return [er.Erinnerung(f"ux-umfrage-{stichtag:%Y-%m}", "Kurzbefragung zur App", stichtag,
                          "Eine Minute: wie die App sich anfühlt und ob du den Zahlen vertraust – für den UX-Score.",
                          "vorschlaege#ux")]
