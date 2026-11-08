"""Vermögen: Konten und Saldi in SQLite, CSV-Import, Nettovermögen und Verlauf."""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date, datetime
from pathlib import Path

ARTEN = {
    "bank": "Bankkonto", "depot": "Wertschriften", "krypto": "Krypto", "immobilie": "Immobilie",
    "hypothek": "Hypothek", "kredit": "Kredit", "sonstiges": "Sonstiges",
}
SCHULDEN = {"hypothek", "kredit"}
# Konten, die nicht ins freie Vermögen für die Pensionsplanung zählen (Immobilie/Hypothek)
NICHT_FREI = {"immobilie", "hypothek"}


def verbinden(pfad: Path) -> sqlite3.Connection:
    db = sqlite3.connect(pfad)
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS konten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            art TEXT NOT NULL DEFAULT 'bank',
            person TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS saldi (
            konto_id INTEGER NOT NULL REFERENCES konten(id) ON DELETE CASCADE,
            datum TEXT NOT NULL,
            betrag REAL NOT NULL,
            PRIMARY KEY (konto_id, datum)
        );
        """
    )
    db.execute("PRAGMA foreign_keys = ON")
    return db


def zahl(text: str) -> float:
    t = str(text).strip().replace("'", "").replace("’", "").replace(" ", "").replace("CHF", "")
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".")
    return float(t)


def datum(text: str) -> str:
    t = str(text).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Datum nicht erkannt: {t!r}")


def konto_anlegen(db, name: str, art: str = "bank", person: str = "") -> int:
    art = art if art in ARTEN else "sonstiges"
    row = db.execute("SELECT id FROM konten WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO konten (name, art, person) VALUES (?, ?, ?)", (name, art, person))
    db.commit()
    return cur.lastrowid


def saldo_setzen(db, konto_id: int, tag: str, betrag: float) -> None:
    db.execute("INSERT OR REPLACE INTO saldi (konto_id, datum, betrag) VALUES (?, ?, ?)",
               (konto_id, tag, betrag))
    db.commit()


def konto_loeschen(db, konto_id: int) -> None:
    db.execute("DELETE FROM saldi WHERE konto_id = ?", (konto_id,))
    db.execute("DELETE FROM konten WHERE id = ?", (konto_id,))
    db.commit()


def csv_import(db, inhalt: bytes) -> tuple[int, list[str]]:
    """Spalten: Datum, Konto, Saldo und optional Art, Person. Trennzeichen ; oder , oder Tab."""
    text = inhalt.decode("utf-8-sig", errors="replace")
    try:
        dialekt = csv.Sniffer().sniff(text[:2048], delimiters=";,\t")
    except csv.Error:
        class dialekt(csv.excel):  # noqa: N801
            delimiter = ";"
    leser = csv.DictReader(io.StringIO(text), dialect=dialekt)
    spalten = {(s or "").strip().lower(): s for s in leser.fieldnames or []}
    fehlend = [s for s in ("datum", "konto", "saldo") if s not in spalten]
    if fehlend:
        raise ValueError("Spalten fehlen: " + ", ".join(fehlend) + " (erwartet: Datum;Konto;Saldo[;Art;Person])")
    n, fehler = 0, []
    for i, zeile in enumerate(leser, start=2):
        try:
            name = zeile[spalten["konto"]].strip()
            if not name:
                continue
            art = (zeile.get(spalten.get("art", ""), "") or "bank").strip().lower()
            person = (zeile.get(spalten.get("person", ""), "") or "").strip()
            tag, betrag = datum(zeile[spalten["datum"]]), zahl(zeile[spalten["saldo"]])
            kid = konto_anlegen(db, name, art, person)
            saldo_setzen(db, kid, tag, betrag)
            n += 1
        except (ValueError, KeyError, TypeError) as e:
            fehler.append(f"Zeile {i}: {e}")
    return n, fehler


def _vorzeichen(art: str, betrag: float) -> float:
    return -abs(betrag) if art in SCHULDEN else betrag


def konten(db) -> list[dict]:
    rows = db.execute(
        """
        SELECT k.id, k.name, k.art, k.person, s.datum, s.betrag,
               (SELECT COUNT(*) FROM saldi WHERE konto_id = k.id) AS anzahl
        FROM konten k
        LEFT JOIN saldi s ON s.konto_id = k.id
             AND s.datum = (SELECT MAX(datum) FROM saldi WHERE konto_id = k.id)
        ORDER BY k.art, k.name
        """
    ).fetchall()
    return [dict(r) | {"wert": _vorzeichen(r["art"], r["betrag"] or 0)} for r in rows]


def nettovermoegen(db) -> dict:
    ks = konten(db)
    total = sum(k["wert"] for k in ks)
    frei = sum(k["wert"] for k in ks if k["art"] not in NICHT_FREI)
    nach_art: dict[str, float] = {}
    for k in ks:
        nach_art[k["art"]] = nach_art.get(k["art"], 0) + k["wert"]
    return {"total": round(total), "frei": round(frei), "nach_art": nach_art}


def verlauf(db, monate: int = 36) -> list[tuple[str, float]]:
    """Nettovermögen am Monatsende (letzter bekannter Saldo je Konto)."""
    erster = db.execute("SELECT MIN(datum) FROM saldi").fetchone()[0]
    if not erster:
        return []
    heute = date.today()
    j, m = heute.year, heute.month
    punkte = []
    for _ in range(monate):
        stichtag = date(j + (m == 12), m % 12 + 1, 1).isoformat()  # erster Tag des Folgemonats
        if stichtag <= erster:
            break
        row = db.execute(
            """
            SELECT COALESCE(SUM(CASE WHEN k.art IN ('hypothek','kredit') THEN -ABS(s.betrag) ELSE s.betrag END), 0)
            FROM konten k JOIN saldi s ON s.konto_id = k.id
            WHERE s.datum = (SELECT MAX(datum) FROM saldi WHERE konto_id = k.id AND datum < ?)
            """, (stichtag,)).fetchone()
        punkte.append((f"{j}-{m:02d}", round(row[0])))
        j, m = (j, m - 1) if m > 1 else (j - 1, 12)
    return list(reversed(punkte))
