"""Herkunft der Werte: woher jeder Wert der Einstellungen kommt, wie alt er ist und ob er bestätigt ist.

Jedes Speichern der Einstellungen vergleicht alt und neu; geänderte Werte werden mit Quelle und Datum notiert.
Die Quelle setzt die auslösende Stelle mit `with quelle("Vorsorgeausweis ASGA 01.01.2026"):` – ohne Angabe gilt
«von Hand» (Formular). Von Hand eingetragene Werte gelten als bestätigt; Werte aus Dokumenten, automatischen
Abgleichen oder Importen bleiben «zu prüfen», bis sie auf der Seite «Datenqualität» bestätigt werden.
Werte, die nie geändert wurden und noch dem Beispielwert der Vorlage entsprechen, sind als solche markiert.
"""
from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date

LOG = logging.getLogger("finanz")
_LOKAL = threading.local()
HAND = "von Hand"

# Werte, die sich jedes Jahr ändern: älter als 15 Monate → «veraltet?»
JAEHRLICH = ("lohn_brutto", "pk.altersguthaben", "pk.altersrente", "pk.einkauf_potenzial", "saeule3a.guthaben",
             "steuern.steuerbar", "steuern.steuer_kanton", "steuern.bundessteuer", "steuern.vermoegenssteuer",
             "risiko.iv_rente_pk", "risiko.partnerrente_pk", "risiko.todesfallkapital_pk", "ahv.beitragsjahre_bisher")


# Persönliche Werte, bei denen der Beispielwert der Vorlage sicher nicht stimmt
BEISPIEL = ("lohn_brutto", "geburtsdatum", "pk.altersguthaben", "pk.einkauf_potenzial", "pk.sparbeitrag_jahr",
            "pk.ausweis_alterskapital", "pk.ausweis_altersrente", "saeule3a.guthaben", "ahv.beitragsjahre_bisher",
            "risiko.iv_rente_pk", "risiko.partnerrente_pk", "risiko.todesfallkapital_pk", "risiko.iv_rente_extern",
            "steuern.steuerbar_bund", "steuern.steuerbar_kanton", "steuern.steuer_kanton_gemeinde",
            "steuern.grenzsteuersatz_kanton", "steuern.steuerbar_vermoegen", "steuern.vermoegenssteuer",
            "haushalt.bedarf_ruhestand", "wohnen.kaufpreis", "wohnen.eigenmittel", "wohnen.eigenmietwert",
            "wohnen.hypothek_zins", "haushalt.kinder.0.geburtsdatum")


@contextlib.contextmanager
def quelle(text: str):
    alt = getattr(_LOKAL, "quelle", None)
    _LOKAL.quelle = text
    try:
        yield
    finally:
        _LOKAL.quelle = alt


def aktuelle_quelle() -> str:
    return getattr(_LOKAL, "quelle", None) or HAND


def tabellen(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS herkunft (pfad TEXT PRIMARY KEY, wert TEXT NOT NULL, quelle TEXT NOT NULL,
                  datum TEXT NOT NULL, bestaetigt TEXT)""")


def flach(d, praefix: str = "") -> dict[str, object]:
    """Blätter der Konfiguration: «personen.0.pk.altersguthaben» → Wert. Listen aus Dicts mit Index, sonst als Ganzes."""
    erg: dict[str, object] = {}
    if isinstance(d, dict):
        for k_, v in d.items():
            erg.update(flach(v, f"{praefix}{k_}."))
    elif isinstance(d, list) and d and all(isinstance(x, dict) for x in d) and praefix.startswith(("personen.",
                                                                                                    "haushalt.kinder.",
                                                                                                    "steuern.personen.")):
        for i, x in enumerate(d):
            erg.update(flach(x, f"{praefix}{i}."))
    else:
        erg[praefix[:-1]] = d
    return erg


def _text(v) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


def erfassen(alt: dict, neu: dict, db=None) -> int:
    """Geänderte Blätter mit der aktuellen Quelle notieren (aus konfig.speichern)."""
    a, n = flach(alt), flach(neu)
    q = aktuelle_quelle()
    heute = date.today().isoformat()
    geaendert = [(p, _text(w)) for p, w in n.items() if _text(a.get(p)) != _text(w)
                 and not p.startswith(("kennzahlen.", "budget.regeln", "sensoren.", "ki.", "ocr."))]
    if not geaendert:
        return 0
    eigen = db is None
    if eigen:
        import konfig
        pfad = konfig.datenordner() / "finanz.sqlite"
        if not pfad.parent.exists():
            return 0
        db = sqlite3.connect(pfad, timeout=10)
    try:
        tabellen(db)
        db.executemany("INSERT OR REPLACE INTO herkunft VALUES (?, ?, ?, ?, ?)",
                       [(p, w, q, heute, heute if q == HAND else None) for p, w in geaendert])
        db.commit()
    finally:
        if eigen:
            db.close()
    return len(geaendert)


def bestaetigen(db, k: dict, pfade: list[str]) -> int:
    tabellen(db)
    werte = flach(k)
    heute = date.today().isoformat()
    n = 0
    for p in pfade:
        if p not in werte:
            continue
        z = db.execute("SELECT 1 FROM herkunft WHERE pfad = ?", (p,)).fetchone()
        if z:
            db.execute("UPDATE herkunft SET bestaetigt = ?, wert = ? WHERE pfad = ?", (heute, _text(werte[p]), p))
        else:
            db.execute("INSERT INTO herkunft VALUES (?, ?, ?, ?, ?)", (p, _text(werte[p]), "unbekannt (vor der "
                                                                          "Aufzeichnung)", "", heute))
        n += 1
    db.commit()
    return n


@dataclass
class Info:
    pfad: str
    wert: object
    quelle: str          # «von Hand», «Vorsorgeausweis …», «Beispielwert der Vorlage», «unbekannt»
    datum: str           # Datum der letzten Änderung ('' = unbekannt)
    bestaetigt: str      # Datum der Bestätigung ('' = nicht bestätigt)
    status: str          # ok | pruefen | beispiel | veraltet | unbekannt | standard

    @property
    def text(self) -> str:
        teile = [self.quelle]
        if self.datum:
            teile.append(f"{date.fromisoformat(self.datum):%d.%m.%Y}")
        if self.bestaetigt and self.quelle != HAND:
            teile.append(f"bestätigt {date.fromisoformat(self.bestaetigt):%d.%m.%Y}")
        return ", ".join(teile)


_VORLAGE: dict | None = None


def _vorlage() -> dict:
    global _VORLAGE
    if _VORLAGE is None:
        import konfig
        _VORLAGE = flach(konfig.vorlage())
    return _VORLAGE


def alle(db, k: dict, heute: date | None = None) -> dict[str, Info]:
    heute = heute or date.today()
    tabellen(db)
    zeilen = {r[0]: r for r in db.execute("SELECT pfad, wert, quelle, datum, bestaetigt FROM herkunft")}
    vorlage = _vorlage()
    konkubinat = k["haushalt"].get("zivilstand", "verheiratet") != "verheiratet" and bool((k.get("steuern") or {}).get("personen"))
    erg = {}
    for p, w in flach(k).items():
        if konkubinat and p.startswith("steuern.") and not p.startswith("steuern.personen.") and \
                p.rsplit(".", 1)[-1] in ("steuerbar_bund", "steuerbar_kanton", "steuer_kanton_gemeinde", "staatssteuer",
                                         "gemeindesteuer", "grenzsteuersatz_kanton", "steuerbar_vermoegen",
                                         "vermoegenssteuer"):
            erg[p] = Info(p, w, "nicht verwendet (Konkubinat: Werte pro Person)", "", "", "standard")
            continue
        z = zeilen.get(p)
        if z and z[1] == _text(w):
            quelle_, datum, best = z[2], z[3], z[4] or ""
        elif z:                                   # seither ohne Aufzeichnung geändert (z. B. YAML von Hand)
            quelle_, datum, best = "geändert ausserhalb der App", "", ""
        elif p in vorlage and _text(vorlage[p]) == _text(w):
            persoenlich = p.endswith(BEISPIEL) and w not in (0, "", None, [], {}, False)
            quelle_, datum, best = ("Beispielwert der Vorlage" if persoenlich else "Standardwert"), "", ""
        else:
            quelle_, datum, best = "unbekannt (vor der Aufzeichnung)", "", ""
        if quelle_ == "Beispielwert der Vorlage" and not best:
            status = "beispiel"
        elif datum and any(p.endswith(j) or f".{j}" in p for j in JAEHRLICH) and \
                (heute - date.fromisoformat(datum)).days > 456 and (not best or (heute - date.fromisoformat(best)).days > 456):
            status = "veraltet"
        elif best or quelle_ == HAND:
            status = "ok"
        elif quelle_ == "Standardwert":
            status = "standard"
        elif quelle_.startswith("unbekannt") or quelle_.startswith("geändert"):
            status = "unbekannt"
        else:
            status = "pruefen"
        erg[p] = Info(p, w, quelle_, datum, best, status)
    return erg


def info(db, k: dict, pfad: str) -> Info | None:
    return alle(db, k).get(pfad)
