"""Budget und Cashflow: Buchungen aus den Kontoauszügen kategorisieren und auswerten.

- Buchungen kommen aus dem Bank-Import (CSV mit Betrag und Text); Duplikate werden beim erneuten Import erkannt.
- Kategorien über Stichworte (Schweizer Händler, Versicherer, Behörden …); eigene Regeln unter `budget.regeln`
  gehen vor.
- Umbuchungen zwischen eigenen Konten (gleicher Betrag, Gegenbuchung innert 4 Tagen oder Stichwort) zählen weder als
  Einnahme noch als Ausgabe; Einzahlungen in 3a, PK-Einkauf oder Depot zählen als Sparen.
- Auswertung über die letzten vollständigen Monate (Standard 12): Ø pro Monat und Jahr je Kategorie, Sparquote,
  Vergleich mit dem Sparpotenzial der Planung.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

UMBUCHUNG = "Umbuchung"
SPAREN = "Sparen und Vorsorge"
LOHN = "Lohn"
EINNAHMEN = "Übrige Einnahmen"
UEBRIGES = "Übriges"

# Reihenfolge = Priorität; Stichworte klein, als Teilwort gesucht
KATEGORIEN: list[tuple[str, tuple[str, ...]]] = [
    (UMBUCHUNG, ("übertrag", "umbuchung", "kontoübertrag", "eigenes konto", "eigene konten", "account transfer",
                 "dauerauftrag an eigen")),
    (SPAREN, ("säule 3a", "saeule 3a", "3a ", "vorsorgekonto", "vorsorgestiftung", "viac", "frankly", "finpension",
              "einkauf pensionskasse", "pk-einkauf", "freizügigkeit", "wertschriftenkauf", "börsenauftrag", "sparplan",
              "fondssparplan", "true wealth", "selma", "inyova", "swissquote", "interactive brokers")),
    (LOHN, ("lohn", "salär", "salaer", "gehalt", "salary", "lohnzahlung", "13. monatslohn", "bonus")),
    ("Steuern", ("steuerverwaltung", "steueramt", "steuerrechnung", "steuern ", "kantonale steuer", "bundessteuer",
                 "gemeindesteuer", "staatssteuer", "estv")),
    ("Wohnen", ("hypothek", "hypothekarzins", "miete", "mietzins", "nebenkosten", "heizkosten", "stockwerkeigentum",
                "verwaltung", "iwb", "ebl", "primeo", "ewz", "bkw", "ckw", "axpo", "groupe e", "romande energie",
                "wasser", "abwasser", "kehricht", "gebäudeversicherung", "liegenschaft", "serafe", "billag",
                "elektrizität", "strom", "gasverbund", "fernwärme")),
    ("Krankenkasse", ("css", "helsana", "swica", "sanitas", "visana", "concordia", "kpt", "groupe mutuel",
                      "sympany", "assura", "atupri", "ökk", "oekk", "egk", "aquilana", "krankenkasse", "agrisano")),
    ("Versicherungen", ("axa", "mobiliar", "helvetia", "zurich versicherung", "zürich versicherung", "baloise",
                        "generali", "allianz", "vaudoise", "smile.direct", "tcs", "swiss life", "pax ", "elvia",
                        "versicherung", "rega")),
    ("Lebensmittel", ("migros", "coop", "denner", "aldi", "lidl", "volg", "spar ", "manor food", "globus delicatessa",
                      "bäckerei", "baeckerei", "metzgerei", "landi", "farmy", "fooby", "alnatura", "prodega")),
    ("Mobilität", ("sbb", "bls", "bvb", "tnw", "zvv", "postauto", "tamoil", "shell", "avia", "bp ", "migrol",
                   "agrola", "socar", "eni ", "coop pronto", "parking", "parkhaus", "mobility", "publibike",
                   "strassenverkehrsamt", "motorfahrzeug", "garage", "amag", "emil frey", "vignette", "easyride")),
    ("Kinder und Betreuung", ("kita", "krippe", "tagesstruktur", "tagesheim", "spielgruppe", "schule", "musikschule",
                              "babysitter", "tagesmutter", "hort", "ferienlager", "pro juventute")),
    ("Gesundheit", ("apotheke", "pharmacie", "drogerie", "arzt", "ärzt", "praxis", "zahnarzt", "spital",
                    "physiotherap", "optiker", "fielmann", "amavita", "sunstore", "medbase", "santémed")),
    ("Telekom und Abos", ("swisscom", "sunrise", "salt ", "wingo", "yallo", "quickline", "netflix", "spotify",
                          "disney", "apple.com", "itunes", "google", "microsoft", "amazon prime", "zattoo",
                          "blick+", "nzz", "tamedia", "ringier", "upc")),
    ("Einkäufe", ("galaxus", "digitec", "zalando", "ikea", "amazon", "interdiscount", "media markt", "mediamarkt",
                  "manor", "jumbo", "hornbach", "bauhaus", "obi ", "ochsner", "h&m", "zara", "decathlon",
                  "brack", "microspot", "tchibo", "aliexpress", "temu", "pfister")),
    ("Freizeit und Ferien", ("restaurant", "café", "cafe ", "bar ", "mcdonald", "starbucks", "burger king",
                             "takeaway", "uber eats", "just eat", "kino", "pathé", "ticketcorner", "booking.com",
                             "airbnb", "hotel", "swiss intl", "easyjet", "edelweiss", "hotelplan", "tui ", "kuoni",
                             "bergbahn", "skipass", "fitness", "migros fitness", "zoo")),
    ("Bargeld", ("bancomat", "geldautomat", "bargeldbezug", "atm ", "postomat", "cash withdrawal")),
    ("Kreditkarte", ("viseca", "cornèr", "corner card", "cornercard", "swisscard", "cembra", "kreditkarte",
                     "visa ", "mastercard", "american express", "amex")),
    ("Spenden", ("spende", "stiftung", "caritas", "unicef", "rotes kreuz", "srk", "heks", "glückskette", "wwf")),
    ("Gebühren und Zinsen", ("kontoführung", "gebühr", "spesen", "bankgebühr", "kontogebühr", "zinsabschluss",
                             "sollzins", "depotgebühr")),
]
AUSGABE_KATEGORIEN = [n for n, _ in KATEGORIEN if n not in (UMBUCHUNG, SPAREN, LOHN)] + [UEBRIGES]
ALLE = [n for n, _ in KATEGORIEN] + [EINNAHMEN, UEBRIGES]


def _tabelle(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS buchungen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            konto TEXT NOT NULL,
            datum TEXT NOT NULL,
            betrag REAL NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            kategorie TEXT NOT NULL DEFAULT '',
            schluessel TEXT NOT NULL UNIQUE
        );
        CREATE INDEX IF NOT EXISTS buchungen_datum ON buchungen(datum);
        """
    )


def _norm(t: str) -> str:
    return " " + re.sub(r"\s+", " ", (t or "").lower()) + " "


def regeln(k: dict) -> dict[str, str]:
    return {str(s).lower(): str(kat) for s, kat in ((k.get("budget") or {}).get("regeln") or {}).items() if s and kat}


def kategorie(text: str, betrag: float, eigene: dict[str, str] | None = None) -> str:
    t = _norm(text)
    for stichwort, kat in (eigene or {}).items():
        if stichwort in t:
            return kat
    for name, woerter in KATEGORIEN:
        if any(w in t for w in woerter):
            if betrag > 0 and name not in (UMBUCHUNG, LOHN, SPAREN):
                return EINNAHMEN          # Rückerstattungen u. ä.
            if betrag < 0 and name == LOHN:
                continue
            return name
    return EINNAHMEN if betrag > 0 else UEBRIGES


def speichern(db, konto: str, buchungen: list[tuple[str, float, str]], k: dict | None = None) -> int:
    """Buchungen eines Kontos speichern; bereits importierte (gleiches Datum, Betrag, Text) werden übersprungen."""
    _tabelle(db)
    eigene = regeln(k or {})
    zaehler: dict[tuple, int] = {}
    neu = 0
    for tag, betrag, text in buchungen:
        basis = (konto, tag, round(betrag, 2), text)
        zaehler[basis] = zaehler.get(basis, 0) + 1
        sch = hashlib.sha1(("|".join(map(str, basis)) + f"|{zaehler[basis]}").encode()).hexdigest()
        cur = db.execute("INSERT OR IGNORE INTO buchungen (konto, datum, betrag, text, kategorie, schluessel) "
                         "VALUES (?,?,?,?,?,?)", (konto, tag, betrag, text, kategorie(text, betrag, eigene), sch))
        neu += cur.rowcount
    return neu


def neu_kategorisieren(db, k: dict) -> int:
    _tabelle(db)
    eigene = regeln(k)
    n = 0
    for r in db.execute("SELECT id, betrag, text, kategorie FROM buchungen").fetchall():
        kat = kategorie(r["text"], r["betrag"], eigene)
        if kat != r["kategorie"]:
            db.execute("UPDATE buchungen SET kategorie=? WHERE id=?", (kat, r["id"]))
            n += 1
    return n


def loeschen(db, konto: str | None = None) -> int:
    _tabelle(db)
    if konto:
        return db.execute("DELETE FROM buchungen WHERE konto=?", (konto,)).rowcount
    return db.execute("DELETE FROM buchungen").rowcount


def alle(db) -> list[dict]:
    _tabelle(db)
    return [dict(r) for r in db.execute("SELECT * FROM buchungen ORDER BY datum, id")]


def _umbuchungen(buchungen: list[dict]) -> set[int]:
    """Paare gleichen Betrags mit umgekehrtem Vorzeichen auf zwei verschiedenen Konten innert 4 Tagen."""
    ids: set[int] = set()
    offen: dict[float, list[dict]] = {}
    for b in buchungen:
        if b["kategorie"] in (LOHN,):
            continue
        offen.setdefault(round(abs(b["betrag"]), 2), []).append(b)
    for gruppe in offen.values():
        if len(gruppe) < 2:
            continue
        minus = [b for b in gruppe if b["betrag"] < 0]
        plus = [b for b in gruppe if b["betrag"] > 0]
        for m in minus:
            dm = date.fromisoformat(m["datum"])
            for p in plus:
                if p["id"] in ids or p["konto"] == m["konto"]:
                    continue
                if abs((date.fromisoformat(p["datum"]) - dm).days) <= 4:
                    ids.update((m["id"], p["id"]))
                    break
    return ids


@dataclass
class Auswertung:
    von: str
    bis: str
    monate: int
    einnahmen: float                      # pro Jahr
    ausgaben: float                       # pro Jahr (ohne Sparen und Umbuchungen)
    sparen_konto: float                   # Einzahlungen in 3a, PK, Depot pro Jahr
    ueberschuss: float                    # Einnahmen − Ausgaben pro Jahr (inkl. Sparen)
    sparquote: float                      # Überschuss in % der Einnahmen
    sparen_plan: float                    # Sparpotenzial laut Planung pro Jahr
    kategorien: list[tuple[str, float, float]]      # (Kategorie, pro Jahr, Anteil %)
    monatlich: list[tuple[str, float, float, dict]]  # (JJJJ-MM, Einnahmen, Ausgaben, {Kategorie: Ausgaben})
    unbekannt: list[tuple[str, int, float]]         # (Text, Anzahl, Summe) häufige Buchungen ohne Kategorie
    konten: list[str]
    anzahl: int
    umbuchungen: int
    hinweise: list[str] = field(default_factory=list)


def auswerten(k: dict, db, monate: int = 12, heute: date | None = None) -> Auswertung | None:
    heute = heute or date.today()
    buchungen = alle(db)
    if not buchungen:
        return None
    letzte = max(b["datum"] for b in buchungen)
    ende = date.fromisoformat(letzte)
    # nur vollständige Monate: endet der letzte Auszug nicht am Monatsende, zählt dieser Monat nicht
    naechster = (ende.replace(day=28) + timedelta(days=4)).replace(day=1)
    if (naechster - ende).days > 3:
        ende = ende.replace(day=1) - timedelta(days=1)
    erster = date.fromisoformat(min(b["datum"] for b in buchungen))
    start_m = date(ende.year, ende.month, 1)
    for _ in range(monate - 1):
        start_m = (start_m - timedelta(days=1)).replace(day=1)
    erster_voll = erster.replace(day=1) if erster.day <= 3 else (erster.replace(day=28) + timedelta(days=4)).replace(day=1)
    start = max(start_m, erster_voll).isoformat()
    auswahl = [b for b in buchungen if start <= b["datum"] <= ende.isoformat()]
    if not auswahl:
        auswahl = buchungen
        start, ende = erster.isoformat(), date.fromisoformat(letzte)
    umb = _umbuchungen(auswahl)
    monats: dict[str, list] = {}
    kat_sum: dict[str, float] = {}
    unbekannt: dict[str, list] = {}
    einnahmen = ausgaben = sparen = 0.0
    n_umb = 0
    for b in auswahl:
        m = monats.setdefault(b["datum"][:7], [0.0, 0.0, {}])
        kat = b["kategorie"]
        if b["id"] in umb or kat == UMBUCHUNG:
            n_umb += 1
            continue
        if kat == SPAREN:
            sparen += -b["betrag"]
            continue
        if b["betrag"] > 0:
            einnahmen += b["betrag"]
            m[0] += b["betrag"]
        else:
            ausgaben += -b["betrag"]
            m[1] += -b["betrag"]
            m[2][kat] = m[2].get(kat, 0) + -b["betrag"]
            kat_sum[kat] = kat_sum.get(kat, 0) + -b["betrag"]
            if kat == UEBRIGES:
                schl = re.sub(r"[\d.,:/\-]+", " ", b["text"]).strip()[:40] or "(ohne Text)"
                u = unbekannt.setdefault(schl, [0, 0.0])
                u[0] += 1
                u[1] += -b["betrag"]
    n_monate = max(1, len(monats))
    f = 12 / n_monate
    ein_j, aus_j, spar_j = einnahmen * f, ausgaben * f, sparen * f
    ueber = ein_j - aus_j
    plan = sum(float(p.get("sparen_monat", 0) or 0) for p in k.get("personen", [])) * 12
    kats = sorted(((n, round(v * f), round(v / ausgaben * 100, 1) if ausgaben else 0.0) for n, v in kat_sum.items()),
                  key=lambda x: -x[1])
    hinw = []
    if n_monate < 12:
        hinw.append(f"Nur {n_monate} Monat(e) erfasst – jährliche Rechnungen (Steuern, Versicherungen) können fehlen "
                    "oder doppelt zählen. Für ein verlässliches Budget 12 Monate importieren.")
    if kat_sum.get("Kreditkarte"):
        hinw.append("Kreditkarten-Abrechnungen sind als eine Ausgabe gezählt. Wer die Kartenumsätze separat importiert, "
                    "erfasst die Abrechnung mit einer Regel als «Umbuchung», damit nichts doppelt zählt.")
    anteil_uebrig = kat_sum.get(UEBRIGES, 0) / ausgaben * 100 if ausgaben else 0
    if anteil_uebrig > 20:
        hinw.append(f"{anteil_uebrig:.0f} % der Ausgaben ohne Kategorie – unten Stichworte zuordnen.")
    if plan and ueber + spar_j < plan * 0.9:
        hinw.append("Laut Konten wird weniger gespart als in der Planung angenommen "
                    f"({_chf((ueber + spar_j) / 12)} statt {_chf(plan / 12)} pro Monat). Sparpotenzial anpassen, "
                    "damit Amortisation, PK-Einkauf und Pensionslücke stimmen.")
    elif plan and ueber + spar_j > plan * 1.2:
        hinw.append(f"Laut Konten wird mehr gespart als geplant ({_chf((ueber + spar_j) / 12)} statt {_chf(plan / 12)} pro "
                    "Monat) – das Sparpotenzial kann erhöht werden.")
    bedarf = float((k.get("haushalt") or {}).get("bedarf_ruhestand", 0) or 0)
    ohne = aus_j - sum(kat_sum.get(x, 0) * f for x in ("Steuern", "Kinder und Betreuung"))
    if bedarf and ohne > bedarf * 1.1:
        hinw.append(f"Die heutigen Ausgaben ohne Steuern und Kinderbetreuung (CHF {_chf(ohne)} pro Jahr) liegen über dem "
                    f"Bedarf im Ruhestand (CHF {_chf(bedarf)}) – Bedarf prüfen.")
    monatlich = [(m, round(v[0]), round(v[1]), {x: round(y) for x, y in v[2].items()}) for m, v in sorted(monats.items())]
    unb = sorted(((t, n, round(s)) for t, (n, s) in unbekannt.items()), key=lambda x: -x[2])[:15]
    return Auswertung(start, ende.isoformat(), n_monate, round(ein_j),
                      round(aus_j), round(spar_j), round(ueber), round(ueber / ein_j * 100, 1) if ein_j else 0.0,
                      round(plan), kats, monatlich, unb, sorted({b["konto"] for b in auswahl}), len(auswahl), n_umb, hinw)


def status(a: Auswertung | None) -> str:
    """Ampel: rot = mehr ausgegeben als eingenommen, gelb = weniger gespart als geplant oder unter 6 Monaten Daten."""
    import ampel as am
    if a is None:
        return am.GRAU
    gespart = a.ueberschuss + a.sparen_konto
    if gespart < 0:
        return am.ROT
    if a.monate < 6 or (a.sparen_plan and gespart < a.sparen_plan * 0.9):
        return am.GELB
    return am.GRUEN


def sparen_uebernehmen(k: dict, a: Auswertung) -> dict[str, float]:
    """Gesparten Betrag pro Monat (Überschuss + Einzahlungen) nach Bruttolohn auf die Personen verteilen."""
    total = max(0.0, (a.ueberschuss + a.sparen_konto) / 12)
    personen = k["personen"]
    loehne = [float(p.get("lohn_brutto", 0) or 0) for p in personen]
    summe = sum(loehne) or len(personen)
    erg = {}
    for p, lohn in zip(personen, loehne):
        anteil = (lohn or (0 if sum(loehne) else 1)) / summe
        p["sparen_monat"] = round(total * anteil / 50) * 50
        erg[p["name"]] = p["sparen_monat"]
    return erg


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")
