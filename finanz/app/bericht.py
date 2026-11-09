"""Jahresbericht und Verlauf: Kennzahlen monatlich festhalten und Jahr für Jahr vergleichen.

- Einmal pro Monat (Hintergrund, beim ersten Lauf im Monat) bzw. per Knopf wird ein Stand gespeichert
  (Tabelle `staende`): Nettovermögen, freies Vermögen, Schulden, Vorsorge, Pensionslücke, Steuern, Budget, Ampeln.
- Der Jahresbericht vergleicht den letzten Stand eines Jahres mit dem letzten des Vorjahres. Fehlt ein Stand, wird das
  Nettovermögen aus den Saldi per Jahresende ergänzt.
- Massnahmen: Ampeln mit Handlungsbedarf und die Erinnerungen der nächsten 12 Monate.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta

# Schlüssel → (Beschriftung, höher ist besser?)
KENNZAHLEN = {
    "nettovermoegen": ("Nettovermögen", True),
    "frei": ("Freies Vermögen (ohne Immobilie und Hypothek)", True),
    "liquide": ("Konten", True),
    "wertschriften": ("Wertschriften und Krypto", True),
    "schulden": ("Hypotheken und Kredite", False),
    "pk": ("Pensionskasse (Altersguthaben)", True),
    "saeule3a": ("Säule 3a", True),
    "einkommen_ruhestand": ("Einkommen im Ruhestand pro Jahr", True),
    "pensionsluecke": ("Pensionslücke pro Jahr (Mittel)", False),
    "steuern": ("Steuern pro Jahr", False),
    "gespart_monat": ("Gespart pro Monat (Budget)", True),
    "sparquote": ("Sparquote % (Budget)", True),
    "ausgaben_monat": ("Ausgaben pro Monat (Budget)", False),
}


def _tabelle(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS staende (monat TEXT PRIMARY KEY, datum TEXT NOT NULL, werte TEXT NOT NULL)")


def messen(k: dict, db, heute: date | None = None) -> dict:
    import ampel as am
    import vermoegen as vm
    import vorsorge as vs
    heute = heute or date.today()
    w: dict = {}

    def sicher(f):
        try:
            f()
        except Exception:  # noqa: BLE001
            pass

    def vermoegen():
        nv = vm.nettovermoegen(db)
        art = nv["nach_art"]
        w.update(nettovermoegen=nv["total"], frei=nv["frei"], liquide=round(art.get("bank", 0)),
                 wertschriften=round(art.get("depot", 0) + art.get("krypto", 0)),
                 schulden=round(-(art.get("hypothek", 0) + art.get("kredit", 0))))
    sicher(vermoegen)

    def vorsorge():
        w["pk"] = round(sum(float(p["pk"].get("altersguthaben", 0) or 0) for p in k["personen"]))
        w["saeule3a"] = round(sum(float((p.get("saeule3a") or {}).get("guthaben", 0) or 0) for p in k["personen"]))
        frei = w.get("frei", 0)
        l = vs.pensionsluecke(k, frei, heute.year)
        w.update(einkommen_ruhestand=l.einkommen, pensionsluecke=max(l.luecke, l.luecke_mittel))
    sicher(vorsorge)

    def steuern():
        import steuern as st
        w["steuern"] = st.steuern_heute(k)["total_inkl"]
    sicher(steuern)

    def budget():
        import budget as bu
        b = bu.auswerten(k, db, heute=heute)
        if b:
            g = (b.ueberschuss + b.sparen_konto)
            w.update(gespart_monat=round(g / 12), ausgaben_monat=round(b.ausgaben / 12),
                     sparquote=round(g / b.einnahmen * 100, 1) if b.einnahmen else 0)
    sicher(budget)

    def ampeln():
        w["ampeln"] = {a.bereich: a.status for a in am.bewerten(k, db, heute)}
    sicher(ampeln)
    return w


def speichern(k: dict, db, heute: date | None = None) -> dict:
    heute = heute or date.today()
    _tabelle(db)
    w = messen(k, db, heute)
    db.execute("INSERT OR REPLACE INTO staende (monat, datum, werte) VALUES (?, ?, ?)",
               (f"{heute:%Y-%m}", heute.isoformat(), json.dumps(w, ensure_ascii=False)))
    db.commit()
    return w


def automatisch(k: dict, db, heute: date | None = None) -> bool:
    """Einen Stand pro Monat speichern, falls noch keiner existiert."""
    heute = heute or date.today()
    _tabelle(db)
    if db.execute("SELECT 1 FROM staende WHERE monat = ?", (f"{heute:%Y-%m}",)).fetchone():
        return False
    speichern(k, db, heute)
    return True


def staende(db) -> list[tuple[str, dict]]:
    _tabelle(db)
    return [(r[1], json.loads(r[2])) for r in db.execute("SELECT monat, datum, werte FROM staende ORDER BY monat")]


def _netto_aus_saldi(db, jahr: int) -> tuple[float, int, int] | None:
    """(Nettovermögen per Jahresende, Konten mit Saldo bis dahin, Konten total)."""
    import vermoegen as vm
    for monat, wert in vm.verlauf(db, monate=240):
        if monat == f"{jahr}-12":
            mit = db.execute("SELECT COUNT(DISTINCT konto_id) FROM saldi WHERE datum <= ?", (f"{jahr}-12-31",)).fetchone()[0]
            total = db.execute("SELECT COUNT(*) FROM konten").fetchone()[0]
            return wert, mit, total
    return None


def jahresstand(db, jahr: int) -> tuple[str, dict] | None:
    """Letzter Stand im Jahr; sonst Nettovermögen aus den Saldi per Jahresende."""
    im_jahr = [(d, w) for d, w in staende(db) if d.startswith(str(jahr))]
    if im_jahr:
        return im_jahr[-1]
    netto = _netto_aus_saldi(db, jahr)
    if netto is not None:
        wert, mit, total = netto
        return f"{jahr}-12-31", {"nettovermoegen": wert, "_aus_saldi": True, "_konten": [mit, total]}
    return None


@dataclass
class Zeile:
    schluessel: str
    titel: str
    jetzt: float | None
    vorher: float | None
    hoeher_besser: bool

    @property
    def differenz(self) -> float | None:
        if self.jetzt is None or self.vorher is None:
            return None
        return self.jetzt - self.vorher

    @property
    def besser(self) -> bool | None:
        d = self.differenz
        if d is None or abs(d) < 0.5:
            return None
        return (d > 0) == self.hoeher_besser


@dataclass
class Bericht:
    jahr: int
    stand: str
    stand_vorjahr: str
    zeilen: list[Zeile]
    ampeln: dict[str, str]
    ampeln_vorjahr: dict[str, str]
    massnahmen: list[tuple[str, str, str]]          # (wann, was, Seite)
    aussagen: list[str] = field(default_factory=list)


def erstellen(k: dict, db, jahr: int | None = None, heute: date | None = None) -> Bericht:
    import ampel as am
    import erinnerungen as er
    heute = heute or date.today()
    jahr = jahr or heute.year
    if jahr == heute.year:
        jetzt = (heute.isoformat(), messen(k, db, heute))
    else:
        jetzt = jahresstand(db, jahr) or (f"{jahr}-12-31", {})
    vorher = jahresstand(db, jahr - 1) or ("", {})
    zeilen = []
    for s, (titel, hb) in KENNZAHLEN.items():
        a, b = jetzt[1].get(s), vorher[1].get(s)
        if a is None and b is None:
            continue
        zeilen.append(Zeile(s, titel, a, b, hb))
    aussagen = []
    unvollstaendig = vorher[1].get("_konten") and vorher[1]["_konten"][0] < vorher[1]["_konten"][1]
    if unvollstaendig:
        mit, total = vorher[1]["_konten"]
        aussagen.append(f"Vorjahr aus den Saldi: nur {mit} von {total} Konten haben einen Saldo per 31.12.{jahr - 1} – "
                        "der Vergleich des Nettovermögens ist unvollständig. Saldi per Jahresende unter «Vermögen» nachtragen.")
    for z in zeilen:
        if unvollstaendig and z.schluessel == "nettovermoegen":
            continue
        d = z.differenz
        if d is None or abs(d) < 1:
            continue
        if z.schluessel in ("nettovermoegen", "pensionsluecke", "gespart_monat", "schulden", "steuern"):
            richtung = "gestiegen" if d > 0 else "gesunken"
            einheit = " Prozentpunkte" if z.schluessel == "sparquote" else ""
            betrag = f"{abs(d):.1f}{einheit}" if z.schluessel == "sparquote" else f"CHF {_chf(abs(d))}"
            aussagen.append(f"{z.titel} um {betrag} {richtung}" + (" – gut." if z.besser else " – beobachten." if z.besser is False else "."))
    ampeln_jetzt = jetzt[1].get("ampeln") or {}
    ampeln_vorher = vorher[1].get("ampeln") or {}
    for b_, s_ in ampeln_jetzt.items():
        v = ampeln_vorher.get(b_)
        if v and v != s_:
            rang = {am.GRUEN: 0, am.GELB: 1, am.ROT: 2}
            if rang.get(s_, 1) < rang.get(v, 1):
                aussagen.append(f"Ampel {b_} verbessert ({am.TEXT.get(v, v)} → {am.TEXT.get(s_, s_)}).")
            elif rang.get(s_, 1) > rang.get(v, 1):
                aussagen.append(f"Ampel {b_} verschlechtert ({am.TEXT.get(v, v)} → {am.TEXT.get(s_, s_)}).")
    massnahmen = []
    if jahr == heute.year:
        for a in am.bewerten(k, db, heute):
            if a.status in (am.ROT, am.GELB):
                massnahmen.append(("jetzt" if a.status == am.ROT else "bald", f"{a.bereich}: {a.text}", a.seite))
        bis = heute + timedelta(days=365)
        for e in er.alle(k, db, heute):
            if e.faellig <= bis:
                massnahmen.append((f"{e.faellig:%d.%m.%Y}", e.titel, e.seite))
    return Bericht(jahr, jetzt[0], vorher[0], zeilen, ampeln_jetzt, ampeln_vorher, massnahmen, aussagen)


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")
