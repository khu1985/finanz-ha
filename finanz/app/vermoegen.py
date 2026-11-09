"""Vermögen: Konten und Saldi in SQLite, CSV-Import, Nettovermögen und Verlauf."""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date, datetime
from pathlib import Path

ARTEN = {
    "bank": "Bankkonto", "depot": "Wertschriften", "krypto": "Krypto", "vorsorge": "Vorsorge 3b (frei/verpfändet)", "immobilie": "Immobilie",
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
    spalten = {r[1] for r in db.execute("PRAGMA table_info(konten)")}
    if "waehrung" not in spalten:
        db.execute("ALTER TABLE konten ADD COLUMN waehrung TEXT NOT NULL DEFAULT 'CHF'")
        db.commit()
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


def konto_anlegen(db, name: str, art: str = "bank", person: str = "", waehrung: str = "CHF") -> int:
    art = art if art in ARTEN else "sonstiges"
    row = db.execute("SELECT id FROM konten WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO konten (name, art, person, waehrung) VALUES (?, ?, ?, ?)",
                     (name, art, person, (waehrung or "CHF").upper()))
    db.commit()
    return cur.lastrowid


def saldo_setzen(db, konto_id: int, tag: str, betrag: float) -> None:
    db.execute("INSERT OR REPLACE INTO saldi (konto_id, datum, betrag) VALUES (?, ?, ?)",
               (konto_id, tag, betrag))
    db.commit()


def waehrung_setzen(db, konto_id: int, waehrung: str) -> None:
    db.execute("UPDATE konten SET waehrung = ? WHERE id = ?", ((waehrung or "CHF").upper(), konto_id))
    db.commit()


def konto_loeschen(db, konto_id: int) -> None:
    db.execute("DELETE FROM saldi WHERE konto_id = ?", (konto_id,))
    db.execute("DELETE FROM konten WHERE id = ?", (konto_id,))
    db.commit()


def csv_import(db, inhalt: bytes) -> tuple[int, list[str]]:
    """Spalten: Datum, Konto, Saldo und optional Art, Person, Währung. Trennzeichen ; oder , oder Tab."""
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
            waehrung = (zeile.get(spalten.get("währung", spalten.get("waehrung", "")), "") or "CHF").strip() or "CHF"
            kid = konto_anlegen(db, name, art, person, waehrung)
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
        SELECT k.id, k.name, k.art, k.person, k.waehrung, s.datum, s.betrag,
               (SELECT COUNT(*) FROM saldi WHERE konto_id = k.id) AS anzahl
        FROM konten k
        LEFT JOIN saldi s ON s.konto_id = k.id
             AND s.datum = (SELECT MAX(datum) FROM saldi WHERE konto_id = k.id)
        ORDER BY k.art, k.name
        """
    ).fetchall()
    import waehrung as wg
    return [dict(r) | {"wert": _vorzeichen(r["art"], wg.in_chf(r["betrag"] or 0, r["waehrung"], db))} for r in rows]


def fremdwaehrung(db) -> dict[str, float]:
    """Wert in CHF je Fremdwährung (ohne Schulden)."""
    erg: dict[str, float] = {}
    for x in konten(db):
        if (x["waehrung"] or "CHF") != "CHF" and x["art"] not in SCHULDEN:
            erg[x["waehrung"]] = erg.get(x["waehrung"], 0) + x["wert"]
    return erg


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
        rows = db.execute(
            """
            SELECT k.art, k.waehrung, s.betrag
            FROM konten k JOIN saldi s ON s.konto_id = k.id
            WHERE s.datum = (SELECT MAX(datum) FROM saldi WHERE konto_id = k.id AND datum < ?)
            """, (stichtag,)).fetchall()
        import waehrung as wg
        summe = sum(_vorzeichen(r["art"], wg.in_chf(r["betrag"], r["waehrung"], db)) for r in rows)
        punkte.append((f"{j}-{m:02d}", round(summe)))
        j, m = (j, m - 1) if m > 1 else (j - 1, 12)
    return list(reversed(punkte))
