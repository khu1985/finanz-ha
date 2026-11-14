"""Fremdwährungen: Konten und Renten in EUR, USD … in Franken umrechnen.

Kurse = Franken pro Einheit der Fremdwährung (EUR 0.92 heisst 1 EUR = 0.92 CHF).
Reihenfolge: automatisch geholter Tageskurs (wenn `waehrungen.automatisch`, Quelle: Referenzkurse der EZB über
frankfurter.dev, einmal pro Tag) → `waehrungen.kurse` aus der Konfiguration → Standard (EUR, Stand 09.11.2026).
Ohne Kurs wird 1:1 gerechnet und ein Hinweis angezeigt. Der Verlauf rechnet frühere Saldi mit dem heutigen Kurs.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from datetime import date

LOG = logging.getLogger("finanz")

STANDARD = {"CHF": 1.0, "EUR": 0.92}
STANDARD_STAND = "09.11.2026"
# Währungen, die Revolut (36, Stand 2026) bzw. Wise (rund 50) als Guthaben führen – die häufigsten zuerst
NAMEN = {
    "CHF": "Schweizer Franken", "EUR": "Euro", "USD": "US-Dollar", "GBP": "Britisches Pfund",
    "AED": "VAE-Dirham", "ARS": "Argentinischer Peso", "AUD": "Australischer Dollar", "BDT": "Bangladesch-Taka",
    "BGN": "Bulgarischer Lew", "BWP": "Botswana-Pula", "CAD": "Kanadischer Dollar", "CLP": "Chilenischer Peso",
    "CNY": "Chinesischer Yuan", "COP": "Kolumbianischer Peso", "CRC": "Costa-Rica-Colón", "CZK": "Tschechische Krone",
    "DKK": "Dänische Krone", "EGP": "Ägyptisches Pfund", "GEL": "Georgischer Lari", "GHS": "Ghanaischer Cedi",
    "HKD": "Hongkong-Dollar", "HUF": "Ungarischer Forint", "IDR": "Indonesische Rupiah", "ILS": "Israelischer Schekel",
    "INR": "Indische Rupie", "ISK": "Isländische Krone", "JPY": "Japanischer Yen", "KES": "Kenia-Schilling",
    "KRW": "Südkoreanischer Won", "KZT": "Kasachischer Tenge", "LKR": "Sri-Lanka-Rupie", "MAD": "Marokkanischer Dirham",
    "MXN": "Mexikanischer Peso", "MYR": "Malaysischer Ringgit", "NGN": "Nigerianische Naira", "NOK": "Norwegische Krone",
    "NPR": "Nepalesische Rupie", "NZD": "Neuseeland-Dollar", "PEN": "Peruanischer Sol", "PHP": "Philippinischer Peso",
    "PKR": "Pakistanische Rupie", "PLN": "Polnischer Złoty", "QAR": "Katar-Riyal", "RON": "Rumänischer Leu",
    "RSD": "Serbischer Dinar", "SAR": "Saudi-Riyal", "SEK": "Schwedische Krone", "SGD": "Singapur-Dollar",
    "THB": "Thailändischer Baht", "TRY": "Türkische Lira", "TZS": "Tansania-Schilling", "UAH": "Ukrainische Hrywnja",
    "UGX": "Uganda-Schilling", "UYU": "Uruguayischer Peso", "VND": "Vietnamesischer Dong",
    "XOF": "CFA-Franc (Westafrika)", "ZAR": "Südafrikanischer Rand", "ZMW": "Sambischer Kwacha",
}
WAEHRUNGEN = list(NAMEN)
# Tageskurse der EZB (frankfurter.dev) gibt es nur für diese; die übrigen unter Einstellungen → Währungskurse eintragen
EZB = {"AUD", "BRL", "CAD", "CNY", "CZK", "DKK", "EUR", "GBP", "HKD", "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW",
       "MXN", "MYR", "NOK", "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD", "ZAR"}
# fest an den Euro gebunden: Einheiten pro Euro
AN_EURO = {"BGN": 1.95583, "XOF": 655.957}


def name(waehrung: str) -> str:
    w = (waehrung or "CHF").upper()
    return f"{w} – {NAMEN[w]}" if w in NAMEN else w
_KONFIG: dict[str, float] = {}
_AUTOMATISCH = False


def uebernehmen(k: dict) -> None:
    """Beim Laden der Konfiguration aufgerufen."""
    global _AUTOMATISCH
    cfg = k.get("waehrungen") or {}
    _KONFIG.clear()
    for w, v in (cfg.get("kurse") or {}).items():
        try:
            if float(v) > 0:
                _KONFIG[str(w).upper()] = float(v)
        except (TypeError, ValueError):
            pass
    _AUTOMATISCH = bool(cfg.get("automatisch"))


def _tabelle(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS kurse (waehrung TEXT PRIMARY KEY, kurs REAL NOT NULL, datum TEXT NOT NULL)")


def kurse(db=None) -> dict[str, tuple[float, str]]:
    """Währung → (Kurs, Quelle)."""
    erg = {w: (v, f"Standard {STANDARD_STAND}") for w, v in STANDARD.items()}
    erg.update({w: (v, "Einstellungen") for w, v in _KONFIG.items()})
    if db is not None and _AUTOMATISCH:
        try:
            _tabelle(db)
            for r in db.execute("SELECT waehrung, kurs, datum FROM kurse"):
                erg[r[0]] = (float(r[1]), f"EZB {r[2]}")
        except Exception:  # noqa: BLE001
            pass
    eur = erg.get("EUR")
    for w, n in AN_EURO.items():                     # fester Kurs zum Euro
        if w not in erg and eur:
            erg[w] = (eur[0] / n, f"fest an EUR ({eur[1]})")
    erg["CHF"] = (1.0, "")
    return erg


def kurs(waehrung: str | None, db=None) -> float:
    w = (waehrung or "CHF").upper()
    return kurse(db).get(w, (1.0, ""))[0]


def bekannt(waehrung: str | None, db=None) -> bool:
    return (waehrung or "CHF").upper() in kurse(db)


def in_chf(betrag: float, waehrung: str | None, db=None) -> float:
    return float(betrag or 0) * kurs(waehrung, db)


def aktualisieren(db, waehrungen: list[str], heute: date | None = None) -> list[str]:
    """Tageskurse der EZB holen (nur wenn automatisch eingeschaltet). Gibt die aktualisierten Währungen zurück."""
    if not _AUTOMATISCH:
        return []
    heute = heute or date.today()
    _tabelle(db)
    offen = [w for w in {w.upper() for w in waehrungen} | ({"EUR"} if any(w.upper() in AN_EURO for w in waehrungen) else set())
             if w in EZB]
    stand = {r[0]: r[1] for r in db.execute("SELECT waehrung, datum FROM kurse")}
    offen = [w for w in offen if stand.get(w) != heute.isoformat()]
    erg = []
    for w in offen:
        try:
            url = f"https://api.frankfurter.dev/v1/latest?base={w}&symbols=CHF"
            with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310 – feste Adresse
                daten = json.loads(r.read().decode("utf-8"))
            k = float(daten["rates"]["CHF"])
            db.execute("INSERT OR REPLACE INTO kurse (waehrung, kurs, datum) VALUES (?, ?, ?)", (w, k, heute.isoformat()))
            erg.append(w)
        except Exception as e:  # noqa: BLE001
            LOG.warning("Kurs %s nicht geholt: %s", w, e)
    if erg:
        db.commit()
    return erg


def erkennen(text: str) -> str:
    """Währung aus einem Kontoauszug (Kopfzeilen) erkennen."""
    import re
    t = text[:3000].upper()
    zaehler = {w: len(re.findall(rf"\b{w}\b", t)) for w in WAEHRUNGEN if w != "CHF"}
    w, n = max(zaehler.items(), key=lambda x: x[1])
    return w if n and n >= len(re.findall(r"\bCHF\b", t)) else "CHF"
