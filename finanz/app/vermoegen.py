"""Vermögen: Konten und Saldi in SQLite, CSV-Import, Nettovermögen und Verlauf."""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date, datetime
from pathlib import Path

ARTEN = {
    "bank": "Bankkonto", "depot": "Wertschriften", "krypto": "Krypto", "saeule3a": "Säule 3a",
    "vorsorge": "Vorsorge 3b (Police)", "immobilie": "Immobilie", "fahrzeug": "Fahrzeug", "hypothek": "Hypothek",
    "kredit": "Kredit", "sonstiges": "Sonstiges",
}
SCHULDEN = {"hypothek", "kredit"}
# Gebundenes Vorsorgevermögen: zählt zum Nettovermögen, ist aber nicht jederzeit verfügbar (3a bis frühestens 5 Jahre
# vor dem Referenzalter, 3b-Policen bis zum Ablauf bzw. verpfändet).
GEBUNDEN = {"saeule3a", "vorsorge"}
# Nicht im freien Vermögen der Pensionsplanung: Immobilie/Hypothek und die Säule 3a – sie kommt über ihr eigenes
# Modell (Einstellungen → 3a, aus den 3a-Konten nachgeführt) bei der Pensionierung dazu. 3b-Policen laufen
# typischerweise bis zur Pensionierung und zählen dort mit.
NICHT_FREI = {"immobilie", "hypothek", "saeule3a", "fahrzeug"}
DREI_A_ANBIETER = ("viac", "frankly", "finpension", "selma 3a", "descartes", "inyova 3a", "yuh 3a")


def ist_3a(name: str, bank: str = "") -> bool:
    """Name bzw. Anbieter eines Kontos sieht nach Säule 3a aus (nicht 3b)."""
    t = f" {bank} {name} ".lower()
    if "3b" in t or "freizügig" in t or "freizuegig" in t:
        return False
    return (" 3a" in t or "3a " in t or "3a-" in t or "säule 3" in t or "saeule 3" in t or "vorsorgekonto" in t
            or "vorsorgefonds" in t or any(a in t for a in DREI_A_ANBIETER))


def verbinden(pfad: Path) -> sqlite3.Connection:
    # Wartezeit bei gleichzeitigem Schreiben (Hintergrund, z. B. Neu-Sichten nach einem Update) statt «database is locked»
    db = sqlite3.connect(pfad, timeout=30)
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
    for spalte in ("notiz", "aufgeloest"):              # aufgeloest: Datum, an dem das Konto aufgelöst wurde
        if spalte not in spalten:
            db.execute(f"ALTER TABLE konten ADD COLUMN {spalte} TEXT NOT NULL DEFAULT ''")
            db.commit()
    # Sparkonten: Bezugslimite (Kontowährung) pro Monat bzw. Jahr ohne Kündigung, Kündigungsfrist, Rückzugskommission
    for spalte, typ in (("bezug_limit", "REAL NOT NULL DEFAULT 0"), ("bezug_zeitraum", "TEXT NOT NULL DEFAULT 'jahr'"),
                        ("kuendigung_monate", "INTEGER NOT NULL DEFAULT 0"), ("rueckzug_prozent", "REAL NOT NULL DEFAULT 0")):
        if spalte not in spalten:
            db.execute(f"ALTER TABLE konten ADD COLUMN {spalte} {typ}")
            db.commit()
    # bis 0.40: 3a-Anbieter wurden als «Vorsorge» (3b) importiert → als Säule 3a einordnen (einmalig)
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'konten_3a_umgestellt'").fetchone():
        for kid, name in db.execute("SELECT id, name FROM konten WHERE art = 'vorsorge'").fetchall():
            if ist_3a(name):
                db.execute("UPDATE konten SET art = 'saeule3a' WHERE id = ?", (kid,))
        db.execute("CREATE TABLE konten_3a_umgestellt (am TEXT)")
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


def _buchungen_da(db) -> bool:
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'buchungen'").fetchone())


def konto_loeschen(db, konto_id: int, mit_buchungen: bool = True) -> None:
    """Konto mit allen Saldi löschen – und mit den Buchungen des Budgets, die zu diesem Konto gehören."""
    k = konto(db, konto_id)
    if k and mit_buchungen and _buchungen_da(db):
        db.execute("DELETE FROM buchungen WHERE konto = ?", (k["name"],))
    db.execute("DELETE FROM saldi WHERE konto_id = ?", (konto_id,))
    db.execute("DELETE FROM konten WHERE id = ?", (konto_id,))
    db.commit()


def konto(db, konto_id: int) -> dict | None:
    r = db.execute("SELECT * FROM konten WHERE id = ?", (konto_id,)).fetchone()
    if not r:
        return None
    erg = dict(r)
    erg["buchungen"] = (db.execute("SELECT COUNT(*) FROM buchungen WHERE konto = ?", (erg["name"],)).fetchone()[0]
                        if _buchungen_da(db) else 0)
    return erg


def saldi(db, konto_id: int) -> list[dict]:
    """Alle Saldi eines Kontos, neueste zuerst."""
    return [dict(r) for r in db.execute("SELECT datum, betrag FROM saldi WHERE konto_id = ? ORDER BY datum DESC",
                                        (konto_id,))]


def bezug_aendern(db, konto_id: int, limit: float, zeitraum: str, kuendigung: int, rueckzug: float) -> None:
    """Bezugslimite eines Sparkontos (0 = ohne Limite), Kündigungsfrist in Monaten, Rückzugskommission in %."""
    db.execute("UPDATE konten SET bezug_limit = ?, bezug_zeitraum = ?, kuendigung_monate = ?, rueckzug_prozent = ? "
               "WHERE id = ?", (max(0.0, float(limit or 0)), "monat" if zeitraum == "monat" else "jahr",
                                max(0, int(kuendigung or 0)), max(0.0, float(rueckzug or 0)), konto_id))
    db.commit()


def sofort(x: dict, monate: int = 1) -> float:
    """Wie viel (CHF) von einem Konto innerhalb von `monate` ohne Kündigung bezogen werden kann – nur Bankkonten."""
    wert = max(0.0, float(x.get("wert") or 0))
    limit = float(x.get("bezug_limit") or 0)
    if x.get("art") != "bank" or limit <= 0 or not wert:
        return wert
    betrag = abs(float(x.get("betrag") or 0))
    kurs = wert / betrag if betrag else 1.0
    frei = limit * (monate if x.get("bezug_zeitraum") == "monat" else 1) * kurs
    return min(wert, frei)


def liquiditaet(db, monate: int = 1) -> dict:
    """Bankkonten: total, sofort verfügbar (innert `monate`), Rest mit Kündigungsfrist und die eingeschränkten Konten."""
    ks = [x for x in konten(db) if x["art"] == "bank" and not x.get("aufgeloest")]
    total = sum(max(0.0, x["wert"]) for x in ks)
    frei = sum(sofort(x, monate) for x in ks)
    eingeschraenkt = [x for x in ks if sofort(x, monate) < max(0.0, x["wert"]) - 0.5]
    frist = max((int(x.get("kuendigung_monate") or 0) for x in eingeschraenkt), default=0)
    kommission = max((float(x.get("rueckzug_prozent") or 0) for x in eingeschraenkt), default=0.0)
    return {"total": round(total), "sofort": round(frei), "gesperrt": round(total - frei), "konten": eingeschraenkt,
            "kuendigung_monate": frist, "rueckzug_prozent": kommission}


def konto_aendern(db, konto_id: int, name: str, art: str, person: str, waehrung: str, notiz: str = "") -> None:
    """Stammdaten ändern; beim Umbenennen wandern die Buchungen des Budgets mit."""
    alt = konto(db, konto_id)
    if not alt:
        raise ValueError("Konto nicht gefunden.")
    name = (name or "").strip()
    if not name:
        raise ValueError("Der Kontoname darf nicht leer sein.")
    andere = db.execute("SELECT id FROM konten WHERE name = ? AND id != ?", (name, konto_id)).fetchone()
    if andere:
        raise ValueError(f"Es gibt schon ein Konto «{name}» – zum Zusammenlegen «Zusammenführen» verwenden.")
    db.execute("UPDATE konten SET name = ?, art = ?, person = ?, waehrung = ?, notiz = ? WHERE id = ?",
               (name, art if art in ARTEN else "sonstiges", person or "", (waehrung or "CHF").upper(),
                (notiz or "").strip(), konto_id))
    if name != alt["name"] and _buchungen_da(db):
        import budget
        budget.konto_umbenennen(db, alt["name"], name)
    db.commit()


def saldi_aendern(db, konto_id: int, aenderungen: dict[str, tuple[str, float]], loeschen: list[str]) -> tuple[int, int]:
    """Saldi bearbeiten: {altes Datum: (neues Datum, Betrag)} und Daten zum Löschen. Gibt (geändert, gelöscht)."""
    vorher = {s["datum"]: s["betrag"] for s in saldi(db, konto_id)}
    geloescht = 0
    for d in loeschen:
        if d in vorher:
            db.execute("DELETE FROM saldi WHERE konto_id = ? AND datum = ?", (konto_id, d))
            geloescht += 1
    geaendert = 0
    for alt, (neu, betrag) in aenderungen.items():
        if alt in loeschen or alt not in vorher or (neu == alt and abs(betrag - vorher[alt]) < 0.005):
            continue
        db.execute("DELETE FROM saldi WHERE konto_id = ? AND datum = ?", (konto_id, alt))
        db.execute("INSERT OR REPLACE INTO saldi (konto_id, datum, betrag) VALUES (?, ?, ?)", (konto_id, neu, betrag))
        geaendert += 1
    db.commit()
    return geaendert, geloescht


def zusammenfuehren(db, quelle_id: int, ziel_id: int) -> int:
    """Saldi und Buchungen von `quelle` ins Konto `ziel` übernehmen und `quelle` löschen.

    Gibt es an einem Tag in beiden Konten einen Saldo, gilt der des Zielkontos. Gibt die Anzahl übernommener Saldi."""
    if quelle_id == ziel_id:
        raise ValueError("Ein Konto kann nicht mit sich selbst zusammengeführt werden.")
    q, z = konto(db, quelle_id), konto(db, ziel_id)
    if not q or not z:
        raise ValueError("Konto nicht gefunden.")
    vorher = db.execute("SELECT COUNT(*) FROM saldi WHERE konto_id = ?", (ziel_id,)).fetchone()[0]
    db.execute("INSERT OR IGNORE INTO saldi (konto_id, datum, betrag) SELECT ?, datum, betrag FROM saldi WHERE konto_id = ?",
               (ziel_id, quelle_id))
    neu = db.execute("SELECT COUNT(*) FROM saldi WHERE konto_id = ?", (ziel_id,)).fetchone()[0] - vorher
    if _buchungen_da(db):
        import budget
        budget.konto_umbenennen(db, q["name"], z["name"])
    db.execute("DELETE FROM saldi WHERE konto_id = ?", (quelle_id,))
    db.execute("DELETE FROM konten WHERE id = ?", (quelle_id,))
    db.commit()
    return neu


def aufloesen(db, konto_id: int, tag: str | None) -> None:
    """Konto als aufgelöst markieren (Saldo 0 ab diesem Tag, Verlauf bleibt) – oder mit tag=None wieder öffnen."""
    if tag:
        db.execute("INSERT OR REPLACE INTO saldi (konto_id, datum, betrag) VALUES (?, ?, 0)", (konto_id, tag))
        db.execute("UPDATE konten SET aufgeloest = ? WHERE id = ?", (tag, konto_id))
    else:
        k = konto(db, konto_id)
        if k and k["aufgeloest"]:
            db.execute("DELETE FROM saldi WHERE konto_id = ? AND datum = ? AND betrag = 0", (konto_id, k["aufgeloest"]))
        db.execute("UPDATE konten SET aufgeloest = '' WHERE id = ?", (konto_id,))
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
        SELECT k.id, k.name, k.art, k.person, k.waehrung, k.notiz, k.aufgeloest, k.bezug_limit, k.bezug_zeitraum,
               k.kuendigung_monate, k.rueckzug_prozent, s.datum, s.betrag,
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
    gebunden = sum(k["wert"] for k in ks if k["art"] in GEBUNDEN)
    nach_art: dict[str, float] = {}
    for k in ks:
        nach_art[k["art"]] = nach_art.get(k["art"], 0) + k["wert"]
    verfuegbar = sum(k["wert"] for k in ks if k["art"] not in NICHT_FREI | GEBUNDEN)
    return {"total": round(total), "frei": round(frei), "gebunden": round(gebunden), "verfuegbar": round(verfuegbar),
            "nach_art": nach_art}


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
