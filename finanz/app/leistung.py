"""Leistung der App messen: Ladezeiten der Seiten und Aktionen, Rechenzeit der grossen Berechnungen,
Hintergrundaufgaben, Datenmengen und Ressourcen – als Grundlage für technische Verbesserungen (Seite «Vorschläge»).

Gemessen wird im Speicher (wenige Mikrosekunden pro Aufruf) und alle 15 Minuten in die Datenbank geschrieben,
getrennt pro App-Version, damit sich Verbesserungen von Version zu Version vergleichen lassen.
"""
from __future__ import annotations

import functools
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LOG = logging.getLogger("finanz")
_SPERRE = threading.Lock()
_WERTE: dict[tuple[str, str], list[float]] = {}     # (Art, Name) → [Anzahl, Summe ms, Max ms]
_START = time.time()

# Berechnungen, die gemessen werden (Modul, Funktion) – Aufrufe über das Modul laufen dann über die Messung
FUNKTIONEN = [
    ("vorsorge", "pensionsluecke"), ("finanzplan", "rechnen"), ("ampel", "bewerten"), ("erinnerungen", "alle"),
    ("hypothek", "vergleichen"), ("budget", "auswerten"), ("budget", "alle"), ("abos", "erkennen"),
    ("kkpraemien", "vergleich"), ("kkpraemien", "einlesen"), ("wertschriften", "uebersicht"), ("anlage", "pruefen"),
    ("krankenkasse", "haushalt"), ("steuern", "kapitalbezug_varianten"), ("szenarien", "einkauf_optimieren"),
    ("fruehpension", "vergleich"), ("vorschlaege", "sammeln"), ("vorschlaege", "textauszuege"),
    ("versicherungen", "alle"), ("versicherungen", "text_auslesen"), ("ocr", "pdf_text"), ("sichtung", "ausfuehren"),
    ("bankimport", "aus_datei"), ("esteuerauszug", "lesen"), ("marktzinsen", "holen"), ("kkpraemien", "herunterladen"),
    ("bericht", "automatisch"), ("steuererklaerung", "erstellen"), ("nachlass", "faelle"),
]
LANGSAM_SEITE_MS = 1500
LANGSAM_FUNKTION_MS = 800


def erfassen(art: str, name: str, ms: float) -> None:
    with _SPERRE:
        w = _WERTE.setdefault((art, name), [0, 0.0, 0.0])
        w[0] += 1
        w[1] += ms
        w[2] = max(w[2], ms)


def seitenname(pfad: str) -> str:
    """«versicherungen/12/speichern» → «versicherungen/‹id›/speichern» (Kennungen zusammenfassen)."""
    return re.sub(r"(?<=/)[0-9a-f]{6,}|(?<=/)\d+", "‹id›", pfad or "") or "übersicht"


def gemessen(name: str):
    def deko(f):
        @functools.wraps(f)
        def innen(*a, **kw):
            t = time.perf_counter()
            try:
                return f(*a, **kw)
            finally:
                erfassen("funktion", name, (time.perf_counter() - t) * 1000)
        innen.__gemessen__ = True
        return innen
    return deko


def instrumentieren() -> int:
    """Die Funktionen aus FUNKTIONEN in ihren Modulen durch gemessene Fassungen ersetzen (einmal beim Start)."""
    import importlib
    n = 0
    for modul, funktion in FUNKTIONEN:
        try:
            m = importlib.import_module(modul)
            f = getattr(m, funktion, None)
            if f and not getattr(f, "__gemessen__", False):
                setattr(m, funktion, gemessen(f"{modul}.{funktion}")(f))
                n += 1
        except Exception as e:  # noqa: BLE001
            LOG.debug("Messung %s.%s nicht möglich: %s", modul, funktion, e)
    return n


class Stoppuhr:
    """with Stoppuhr("hintergrund", "Sensoren"): … – für Abläufe ohne eigene Funktion."""

    def __init__(self, art: str, name: str):
        self.art, self.name = art, name

    def __enter__(self):
        self.t = time.perf_counter()
        return self

    def __exit__(self, *_):
        erfassen(self.art, self.name, (time.perf_counter() - self.t) * 1000)


# ---------------------------------------------------------------- Speichern

def tabellen(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS leistung (version TEXT NOT NULL, art TEXT NOT NULL, name TEXT NOT NULL, "
               "anzahl INTEGER NOT NULL, summe_ms REAL NOT NULL, max_ms REAL NOT NULL, zuletzt TEXT NOT NULL, "
               "PRIMARY KEY (version, art, name))")


def sichern(db, version: str | None = None) -> int:
    """Gesammelte Werte in die Datenbank übernehmen und im Speicher leeren."""
    if version is None:
        import meta
        version = meta.version()
    with _SPERRE:
        werte = dict(_WERTE)
        _WERTE.clear()
    if not werte:
        return 0
    tabellen(db)
    jetzt = datetime.now().isoformat(timespec="seconds")
    for (art, name), (n, s, mx) in werte.items():
        db.execute("INSERT INTO leistung VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(version, art, name) DO UPDATE SET "
                   "anzahl = anzahl + excluded.anzahl, summe_ms = summe_ms + excluded.summe_ms, "
                   "max_ms = MAX(max_ms, excluded.max_ms), zuletzt = excluded.zuletzt",
                   (version, art, name, int(n), s, mx, jetzt))
    db.commit()
    return len(werte)


@dataclass
class Messung:
    art: str
    name: str
    anzahl: int
    mittel_ms: float
    max_ms: float
    vorher_ms: float | None = None      # Mittel der Vorversion


def messungen(db, version: str | None = None) -> tuple[list[Messung], str]:
    """Messungen der aktuellen Version (inkl. noch nicht gesicherter), mit dem Mittel der Vorversion zum Vergleich."""
    import meta
    version = version or meta.version()
    sichern(db, version)
    tabellen(db)
    versionen = [r[0] for r in db.execute("SELECT DISTINCT version FROM leistung")]
    vorher = max((v for v in versionen if _vt(v) < _vt(version)), key=_vt, default="")
    alt = {(a, n): s / max(1, c) for a, n, c, s in db.execute(
        "SELECT art, name, anzahl, summe_ms FROM leistung WHERE version = ?", (vorher,))} if vorher else {}
    erg = [Messung(a, n, c, round(s / max(1, c), 1), round(mx, 1),
                   round(alt[(a, n)], 1) if (a, n) in alt else None)
           for a, n, c, s, mx in db.execute("SELECT art, name, anzahl, summe_ms, max_ms FROM leistung WHERE version = ?",
                                            (version,))]
    erg.sort(key=lambda m: -(m.mittel_ms * m.anzahl))
    return erg, vorher


def _vt(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", v or "0"))


# ---------------------------------------------------------------- System und Daten

def _meminfo() -> dict[str, int]:
    erg = {}
    try:
        for z in Path("/proc/meminfo").read_text().splitlines():
            teile = z.split()
            if len(teile) >= 2 and teile[1].isdigit():
                erg[teile[0].rstrip(":")] = int(teile[1]) * 1024
    except OSError:
        pass
    return erg


def _rss() -> int:
    try:
        for z in Path("/proc/self/status").read_text().splitlines():
            if z.startswith("VmRSS:"):
                return int(z.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def _ordner(p: Path) -> int:
    try:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except OSError:
        return 0


def system(db, daten: Path) -> dict:
    mem = _meminfo()
    try:
        last = os.getloadavg()
    except OSError:
        last = (0.0, 0.0, 0.0)
    zeilen = {}
    for t in ("buchungen", "saldi", "konten", "vertraege", "vorsorge_dok", "steuer_dok", "kk_praemien", "marktzinsen",
              "wertschriften", "steuerauszug", "monatsstand", "erinnerungen_gesendet"):
        try:
            zeilen[t] = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:  # noqa: BLE001
            pass
    dbdatei = daten / "finanz.sqlite"
    return {
        "kerne": os.cpu_count() or 1,
        "last": tuple(round(x, 2) for x in last),
        "ram_total": mem.get("MemTotal", 0),
        "ram_frei": mem.get("MemAvailable", 0),
        "prozess": _rss(),
        "laufzeit_h": round((time.time() - _START) / 3600, 1),
        "db": dbdatei.stat().st_size if dbdatei.exists() else 0,
        "dokumente": sum(_ordner(daten / o) for o in ("versicherungen", "vorsorge", "steuern")),
        "log": (daten / "finanz.log").stat().st_size if (daten / "finanz.log").exists() else 0,
        "zeilen": zeilen,
        "treffer": _treffer(),
    }


def _treffer() -> float | None:
    try:
        import zwischenspeicher as zs
        n = zs.TREFFER["ja"] + zs.TREFFER["nein"]
        return zs.TREFFER["ja"] / n * 100 if n else None
    except Exception:  # noqa: BLE001
        return None


def _mb(b: float) -> str:
    return f"{b / 1024 / 1024:.1f} MB"


def vorschlaege(db, daten: Path) -> list[tuple[str, str, int]]:
    """(Titel, Detail, Gewicht 3/2/1) – technische Verbesserungen aus den Messungen."""
    ms, vorher = messungen(db)
    s = system(db, daten)
    erg = []
    for m in ms:
        if m.art in ("seite", "aktion") and m.mittel_ms >= LANGSAM_SEITE_MS and m.anzahl >= 3:
            erg.append((f"{('Seite' if m.art == 'seite' else 'Aktion')} «{m.name}» lädt langsam",
                        f"Ø {m.mittel_ms / 1000:.1f} s bei {m.anzahl} Aufrufen, längster {m.max_ms / 1000:.1f} s",
                        3 if m.mittel_ms >= 3000 else 2))
        elif m.art == "funktion" and m.mittel_ms >= LANGSAM_FUNKTION_MS and m.anzahl >= 3 and \
                not m.name.startswith(("ocr.", "sichtung.", "kkpraemien.herunterladen", "marktzinsen.holen")):
            erg.append((f"Berechnung «{m.name}» ist langsam",
                        f"Ø {m.mittel_ms:.0f} ms bei {m.anzahl} Aufrufen – Kandidat für Zwischenspeicher", 2))
        if m.vorher_ms and m.anzahl >= 5 and m.mittel_ms > 1.5 * m.vorher_ms and m.mittel_ms - m.vorher_ms > 200:
            erg.append((f"«{m.name}» ist langsamer geworden", f"Ø {m.vorher_ms:.0f} ms in {vorher} → "
                        f"{m.mittel_ms:.0f} ms", 2))
    ocr = next((m for m in ms if m.name == "ocr.pdf_text"), None)
    if ocr and ocr.mittel_ms > 60_000:
        erg.append(("Texterkennung dauert über eine Minute pro Dokument",
                    "weniger Seiten (ocr.max_seiten) oder tiefere Auflösung prüfen", 1))
    if s["db"] > 100 * 1024 * 1024:
        erg.append(("Datenbank über 100 MB", _mb(s["db"]) + " – alte Buchungen oder Prämien aufräumen", 1))
    if s["zeilen"].get("buchungen", 0) > 50_000:
        erg.append(("Sehr viele Buchungen", f"{s['zeilen']['buchungen']} – Auswertungen begrenzen", 1))
    if s["ram_total"] and s["ram_frei"] / s["ram_total"] < 0.1:
        erg.append(("Wenig freier Arbeitsspeicher im System", f"{_mb(s['ram_frei'])} von {_mb(s['ram_total'])} frei", 2))
    if s["prozess"] > 300 * 1024 * 1024:
        erg.append(("Die App belegt viel Arbeitsspeicher", _mb(s["prozess"]), 2))
    if s["last"][1] > s["kerne"] * 0.9:
        erg.append(("Das System ist stark ausgelastet", f"Last (5 Min.) {s['last'][1]} bei {s['kerne']} Kernen", 1))
    return erg


def bericht_text(db, daten: Path, anzahl: int = 12) -> list[str]:
    """Zeilen für den Text zum Weitergeben (nur Zeiten und Mengen, keine Inhalte)."""
    ms, vorher = messungen(db)
    s = system(db, daten)
    zeilen = [f"System: {s['kerne']} Kerne, RAM {_mb(s['ram_total'])} (frei {_mb(s['ram_frei'])}), App {_mb(s['prozess'])}, "
              + (f"Zwischenspeicher {s['treffer']:.0f} % Treffer, " if s.get("treffer") is not None else "") +
              f"Last {s['last'][0]}/{s['last'][1]}/{s['last'][2]}, Datenbank {_mb(s['db'])}, Dokumente {_mb(s['dokumente'])}",
              "Datensätze: " + ", ".join(f"{t} {n}" for t, n in s["zeilen"].items() if n)]
    for m in ms[:anzahl]:
        v = f" (vorher {m.vorher_ms:.0f})" if m.vorher_ms is not None else ""
        zeilen.append(f"{m.art} {m.name}: {m.anzahl}×, Ø {m.mittel_ms:.0f} ms{v}, max {m.max_ms:.0f} ms")
    if vorher:
        zeilen.append(f"Vergleich mit Version {vorher}")
    return zeilen
