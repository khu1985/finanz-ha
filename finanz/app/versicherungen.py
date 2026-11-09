"""Versicherungen: Verträge hochladen, Text auslesen, Eckdaten erkennen und den Haushalt analysieren.

Die Erkennung arbeitet lokal mit Mustern (Versicherer, Sparte, Prämie, Daten, Fristen). Gescannte PDFs
ohne Textebene werden gespeichert, die Eckdaten dann von Hand ergänzt. Optional kann eine KI-Aufgabe
(ai_task) von Home Assistant die Eckdaten auslesen.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

import io
import json
import logging
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

LOG = logging.getLogger("finanz")

SPARTEN = {
    "kvg": "Krankenkasse Grundversicherung",
    "vvg": "Krankenkasse Zusatzversicherung",
    "haftpflicht": "Privathaftpflicht",
    "hausrat": "Hausrat",
    "hausrat_haftpflicht": "Hausrat + Privathaftpflicht",
    "gebaeude": "Gebäude",
    "motorfahrzeug": "Motorfahrzeug",
    "rechtsschutz": "Rechtsschutz",
    "risiko_leben": "Todesfallrisiko",
    "leben_3b": "Lebensversicherung (Sparen, 3a/3b)",
    "erwerbsunfaehigkeit": "Erwerbsunfähigkeit",
    "unfall": "Unfall",
    "reise": "Reise",
    "tier": "Tier",
    "sonstiges": "Sonstiges",
}

# Stichwörter je Sparte mit Gewicht; die Sparte mit der höchsten Summe gewinnt.
STICHWORTE = {
    "kvg": [("grundversicherung", 5), ("obligatorische krankenpflege", 6), ("kvg", 4), ("franchise", 2),
            ("hausarztmodell", 3), ("telmed", 3), ("hmo", 2), ("prämienverbilligung", 2)],
    "vvg": [("zusatzversicherung", 5), ("spitalversicherung", 4), ("halbprivat", 4), ("ambulant", 2),
            ("vvg", 2), ("alternativmedizin", 3), ("zahnversicherung", 3)],
    "haftpflicht": [("privathaftpflicht", 6), ("haftpflicht", 3), ("personen- und sachschäden", 2)],
    "hausrat": [("hausrat", 6), ("einfacher diebstahl", 3), ("feuer", 1), ("wasser", 1), ("glasbruch", 1)],
    "gebaeude": [("gebäudeversicherung", 6), ("gebäudewasser", 4), ("versicherungswert gebäude", 4),
                 ("elementarschäden", 1), ("neuwert", 1)],
    "motorfahrzeug": [("motorfahrzeug", 6), ("kontrollschild", 5), ("teilkasko", 4), ("vollkasko", 4),
                      ("fahrzeug", 2), ("bonus", 1), ("lenker", 2)],
    "rechtsschutz": [("rechtsschutz", 7)],
    "risiko_leben": [("todesfallkapital", 5), ("risikoversicherung", 5), ("todesfallrisiko", 6),
                     ("hypothekarschutz", 4), ("ablebensversicherung", 4)],
    "leben_3b": [("gemischte lebensversicherung", 7), ("erlebensfallkapital", 5), ("rückkaufswert", 5),
                 ("säule 3b", 5), ("säule 3a", 3), ("überschussbeteiligung", 3), ("garantiertes kapital", 3)],
    "erwerbsunfaehigkeit": [("erwerbsunfähigkeit", 6), ("erwerbsausfall", 5), ("invaliditätsrente", 3),
                            ("wartefrist", 2)],
    "unfall": [("unfallversicherung", 5), ("taggeld", 1), ("invaliditätskapital", 2)],
    "reise": [("reiseversicherung", 6), ("annullierung", 4), ("assistance", 3), ("reiseschutz", 5)],
    "tier": [("tierversicherung", 6), ("hund", 2), ("katze", 2)],
}

VERSICHERER = [
    "Helvetia Baloise", "Helvetia", "Baloise", "Basler", "AXA", "Allianz", "Mobiliar", "Zurich", "Generali",
    "Vaudoise", "Smile", "TCS", "Swiss Life", "Pax", "Elvia", "Protekta", "Coop Rechtsschutz", "Dextra",
    "Simpego", "Wefox", "Emmental Versicherung", "GVB", "Gebäudeversicherung", "CSS", "Helsana", "Swica",
    "Sanitas", "Concordia", "Visana", "KPT", "Groupe Mutuel", "Assura", "Atupri", "Sympany", "ÖKK", "EGK",
    "Aquilana", "Sumiswalder", "Agrisano", "Galenos", "Vivao", "Luzerner Hinterland", "Rhenusana",
    "Lalux", "Youplus", "Liechtenstein Life", "Fisch Asset", "Europäische Reiseversicherung", "Epona",
]

MONATE = {"januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6, "juli": 7,
          "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12}

BETRAG = r"(?:CHF|Fr\.|SFr\.?)?\s*([0-9]{1,3}(?:['’ ]?[0-9]{3})*(?:[.,][0-9]{2})?|[0-9]+(?:[.,][0-9]{2})?)\s*(?:CHF|Fr\.)?"
DATUM = r"(\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}|\d{1,2}\.\s?(?:" + "|".join(MONATE) + r")\s+\d{4})"


# ---------------------------------------------------------------- Speicher

def tabellen(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS vertraege (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dateiname TEXT NOT NULL,
            datei TEXT NOT NULL DEFAULT '',
            hochgeladen TEXT NOT NULL,
            sparte TEXT NOT NULL DEFAULT 'sonstiges',
            versicherer TEXT NOT NULL DEFAULT '',
            police TEXT NOT NULL DEFAULT '',
            person TEXT NOT NULL DEFAULT '',
            praemie_jahr REAL NOT NULL DEFAULT 0,
            beginn TEXT NOT NULL DEFAULT '',
            ablauf TEXT NOT NULL DEFAULT '',
            kuendigungsfrist_monate INTEGER NOT NULL DEFAULT 3,
            franchise REAL NOT NULL DEFAULT 0,
            selbstbehalt REAL NOT NULL DEFAULT 0,
            summe REAL NOT NULL DEFAULT 0,
            unfall_eingeschlossen INTEGER NOT NULL DEFAULT 0,
            notiz TEXT NOT NULL DEFAULT '',
            quelle TEXT NOT NULL DEFAULT 'muster',
            text TEXT NOT NULL DEFAULT ''
        );
        """
    )


FELDER = ["sparte", "versicherer", "police", "person", "praemie_jahr", "beginn", "ablauf",
          "kuendigungsfrist_monate", "franchise", "selbstbehalt", "summe", "unfall_eingeschlossen", "notiz"]


def ordner(daten: Path) -> Path:
    o = daten / "versicherungen"
    o.mkdir(parents=True, exist_ok=True)
    return o


def _sicherer_name(name: str) -> str:
    name = os.path.basename(name or "vertrag.pdf")
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name)[:120] or "vertrag.pdf"


def hochladen(db, daten: Path, dateiname: str, inhalt: bytes) -> int:
    tabellen(db)
    text = text_auslesen(dateiname, inhalt)
    erkannt = erkennen(text)
    cur = db.execute(
        "INSERT INTO vertraege (dateiname, hochgeladen, text) VALUES (?, ?, ?)",
        (_sicherer_name(dateiname), datetime.now().isoformat(timespec="seconds"), text))
    vid = cur.lastrowid
    endung = Path(_sicherer_name(dateiname)).suffix.lower() or ".pdf"
    pfad = ordner(daten) / f"{vid}{endung}"
    pfad.write_bytes(inhalt)
    db.execute("UPDATE vertraege SET datei = ? WHERE id = ?", (pfad.name, vid))
    aktualisieren(db, vid, erkannt, quelle="muster" if text.strip() else "ohne Text")
    return vid


def aktualisieren(db, vid: int, werte: dict, quelle: str | None = None) -> None:
    teile, args = [], []
    for f in FELDER:
        if f in werte and werte[f] is not None:
            teile.append(f"{f} = ?")
            args.append(werte[f])
    if quelle:
        teile.append("quelle = ?")
        args.append(quelle)
    if teile:
        db.execute(f"UPDATE vertraege SET {', '.join(teile)} WHERE id = ?", (*args, vid))
        db.commit()


def alle(db) -> list[dict]:
    tabellen(db)
    return [dict(r) for r in db.execute("SELECT * FROM vertraege ORDER BY sparte, versicherer")]


def einer(db, vid: int) -> dict | None:
    tabellen(db)
    r = db.execute("SELECT * FROM vertraege WHERE id = ?", (vid,)).fetchone()
    return dict(r) if r else None


def loeschen(db, daten: Path, vid: int) -> None:
    v = einer(db, vid)
    if v and v["datei"]:
        (ordner(daten) / v["datei"]).unlink(missing_ok=True)
    db.execute("DELETE FROM vertraege WHERE id = ?", (vid,))
    db.commit()


# ---------------------------------------------------------------- Text und Erkennung

def text_auslesen(dateiname: str, inhalt: bytes) -> str:
    if dateiname.lower().endswith(".pdf") or inhalt[:5] == b"%PDF-":
        try:
            from pypdf import PdfReader
            leser = PdfReader(io.BytesIO(inhalt))
            return "\n".join((s.extract_text() or "") for s in leser.pages[:40])
        except Exception as e:  # noqa: BLE001
            LOG.warning("PDF %s nicht lesbar: %s", dateiname, e)
            return ""
    return inhalt.decode("utf-8", errors="replace")


def zahl(t: str) -> float:
    t = t.replace("'", "").replace("’", "").replace(" ", "")
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    return float(t.replace(",", ""))


def datum_iso(t: str) -> str:
    t = t.strip().lower().replace(" ", "")
    for name, nr in MONATE.items():
        if name in t:
            tag, jahr = re.match(r"(\d{1,2})\.(?:\D+)(\d{4})", t).groups()
            return date(int(jahr), nr, int(tag)).isoformat()
    teile = t.split(".")
    jahr = int(teile[2]) + (2000 if len(teile[2]) == 2 else 0)
    return date(jahr, int(teile[1]), int(teile[0])).isoformat()


def sparte_erkennen(text: str) -> str:
    t = text.lower()
    punkte = {s: sum(g * t.count(w) for w, g in liste) for s, liste in STICHWORTE.items()}
    if punkte["hausrat"] >= 6 and punkte["haftpflicht"] >= 6:
        return "hausrat_haftpflicht"
    beste = max(punkte, key=punkte.get)
    return beste if punkte[beste] >= 3 else "sonstiges"


def _erstes_datum(text: str, stichworte: str) -> str:
    m = re.search(rf"(?:{stichworte})[^\n\d]{{0,40}}{DATUM}", text, re.I)
    if m:
        try:
            return datum_iso(m.group(1))
        except (ValueError, AttributeError, IndexError):
            pass
    return ""


def praemie_erkennen(text: str) -> float:
    kandidaten = []
    for zeile in text.splitlines():
        z = zeile.lower()
        if not re.search(r"prämie|praemie|total|zu bezahlen|rechnungsbetrag|betrag", z):
            continue
        if re.search(r"summe|franchise|selbstbehalt|versicherungswert|kapital|leistung", z):
            continue
        for m in re.finditer(BETRAG, zeile):
            try:
                wert = zahl(m.group(1))
            except ValueError:
                continue
            if wert < 10 or (1900 <= wert <= 2100 and "." not in m.group(1)):
                continue  # Jahreszahlen und Kleinstbeträge
            faktor = 12 if re.search(r"monat|mtl", z) else 4 if "quartal" in z else 2 if "halbj" in z else 1
            gewicht = 3 if re.search(r"jahresprämie|total|gesamtprämie|zu bezahlen", z) else 1
            kandidaten.append((gewicht, wert * faktor))
    if not kandidaten:
        return 0.0
    gewicht = max(g for g, _ in kandidaten)
    return round(max(w for g, w in kandidaten if g == gewicht), 2)


def erkennen(text: str) -> dict:
    erg: dict = {}
    if not text.strip():
        return erg
    erg["sparte"] = sparte_erkennen(text)
    for name in VERSICHERER:
        if re.search(rf"\b{re.escape(name)}\b", text, re.I):
            erg["versicherer"] = name
            break
    m = re.search(r"(?:Police|Policen|Vertrags|Versicherten)[- ]?(?:Nr\.?|nummer)\s*:?\s*([A-Z0-9][A-Z0-9./\-]{3,30})",
                  text, re.I)
    if m:
        erg["police"] = m.group(1).strip(".")
    m = re.search(r"(?i:versicherte person|versicherter|versicherungsnehmer(?:in)?)\s*:?[ \t]*"
                  r"((?:Herr|Frau)\s+)?([A-ZÄÖÜ][\w-]+(?:[ \t][A-ZÄÖÜ0-9][\w-]*)?)", text)
    if m:
        erg["person"] = m.group(2).strip()
    erg["praemie_jahr"] = praemie_erkennen(text)
    erg["beginn"] = _erstes_datum(text, r"vertragsbeginn|versicherungsbeginn|beginn|gültig ab|ab dem")
    erg["ablauf"] = _erstes_datum(text, r"vertragsablauf|ablauf|vertragsende|gültig bis|läuft bis|endet am")
    m = re.search(r"kündigungsfrist\D{0,20}(\d{1,2})\s*monat", text, re.I) or \
        re.search(r"(\d{1,2})\s*monate?\D{0,40}(?:vor|kündig)", text, re.I)
    if m:
        erg["kuendigungsfrist_monate"] = int(m.group(1))
    m = re.search(r"franchise\D{0,20}" + BETRAG, text, re.I)
    if m:
        erg["franchise"] = zahl(m.group(1))
    m = re.search(r"selbstbehalt\D{0,20}" + BETRAG, text, re.I)
    if m:
        erg["selbstbehalt"] = zahl(m.group(1))
    m = re.search(r"(?:versicherungssumme|garantiesumme|todesfallkapital|versicherungswert)\D{0,30}" + BETRAG,
                  text, re.I)
    if m:
        erg["summe"] = zahl(m.group(1))
    t = text.lower()
    if re.search(r"ohne unfall|unfall\w*\s*(?:ist\s*)?(?:sistiert|ausgeschlossen)", t):
        erg["unfall_eingeschlossen"] = 0
    elif re.search(r"(?:mit|inkl\.?|inklusive)\s*unfall|unfall\w*\s*(?:ist\s*)?eingeschlossen", t):
        erg["unfall_eingeschlossen"] = 1
    return erg


# ---------------------------------------------------------------- KI (optional, über Home Assistant)

KI_ANWEISUNG = """Lies diesen Schweizer Versicherungsvertrag und antworte NUR mit einem JSON-Objekt mit den Schlüsseln:
sparte (eine von: {sparten}), versicherer, police, person, praemie_jahr (Zahl, CHF pro Jahr inkl. Abgaben),
beginn (JJJJ-MM-TT), ablauf (JJJJ-MM-TT), kuendigungsfrist_monate (Zahl), franchise (Zahl), selbstbehalt (Zahl),
summe (Zahl, Versicherungssumme), unfall_eingeschlossen (0 oder 1), notiz (höchstens drei kurze Sätze zu
Besonderheiten, Ausschlüssen und Auffälligkeiten). Unbekannte Werte weglassen.

Vertrag:
{text}"""


def ki_aufgabe(anweisung: str, entity_id: str = "", name: str = "Finanzplanung", json_antwort: bool = True):
    """Ruft ai_task.generate_data in Home Assistant auf (braucht SUPERVISOR_TOKEN und homeassistant_api)."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise RuntimeError("Kein Zugriff auf Home Assistant (SUPERVISOR_TOKEN fehlt).")
    nutzlast = {"task_name": name, "instructions": anweisung}
    if entity_id:
        nutzlast["entity_id"] = entity_id
    req = urllib.request.Request(
        "http://supervisor/core/api/services/ai_task/generate_data?return_response",
        data=json.dumps(nutzlast).encode(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as antwort:
            roh = json.loads(antwort.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"KI-Aufgabe fehlgeschlagen ({e.code}): {e.read().decode()[:300]}") from e
    daten = _finde_daten(roh)
    if not json_antwort:
        return daten if isinstance(daten, str) else json.dumps(daten, ensure_ascii=False, indent=2)
    if isinstance(daten, str):
        m = re.search(r"\{.*\}", daten, re.S)
        daten = json.loads(m.group(0)) if m else {}
    if not isinstance(daten, dict):
        raise RuntimeError("Die KI-Antwort enthielt kein JSON.")
    return daten


def ki_auslesen(text: str, entity_id: str) -> dict:
    if not text.strip():
        raise RuntimeError("Der Vertrag enthält keinen lesbaren Text (gescannt?).")
    anweisung = KI_ANWEISUNG.format(sparten=", ".join(SPARTEN), text=text[:30000])
    return bereinigen(ki_aufgabe(anweisung, entity_id, "Versicherungsvertrag auslesen"))


def _finde_daten(obj):
    if isinstance(obj, dict):
        if "data" in obj:
            return obj["data"]
        for v in obj.values():
            gefunden = _finde_daten(v)
            if gefunden is not None:
                return gefunden
    return None


def bereinigen(werte: dict) -> dict:
    """Werte aus Formular oder KI in die richtigen Typen bringen."""
    erg = {}
    for f in FELDER:
        if f not in werte or werte[f] in (None, ""):
            continue
        v = werte[f]
        if f in ("praemie_jahr", "franchise", "selbstbehalt", "summe"):
            erg[f] = zahl(str(v))
        elif f in ("kuendigungsfrist_monate", "unfall_eingeschlossen"):
            erg[f] = int(float(str(v).replace("ja", "1").replace("nein", "0")))
        elif f in ("beginn", "ablauf"):
            s = str(v).strip()
            erg[f] = s if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else datum_iso(s)
        elif f == "sparte":
            erg[f] = v if v in SPARTEN else "sonstiges"
        else:
            erg[f] = str(v).strip()
    return erg


# ---------------------------------------------------------------- Analyse

def plus_monate(d: date, monate: int) -> date:
    m = d.month - 1 + monate
    j, m = d.year + m // 12, m % 12 + 1
    tage = [31, 29 if j % 4 == 0 and (j % 100 or j % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(j, m, min(d.day, tage[m - 1]))


@dataclass
class Termin:
    vertrag: dict
    kuendigen_bis: date
    wirksam_auf: date
    grund: str


def naechster_termin(v: dict, heute: date) -> Termin | None:
    if v["sparte"] == "kvg":
        frist = date(heute.year, 11, 30)
        if heute > frist:
            frist = date(heute.year + 1, 11, 30)
        return Termin(v, frist, date(frist.year + 1, 1, 1),
                      "Grundversicherung: Wechsel auf 1. Januar, Kündigung bis 30. November (eingeschrieben).")
    frist_m = int(v.get("kuendigungsfrist_monate") or 3)
    kandidaten = []
    if v.get("ablauf"):
        t = date.fromisoformat(v["ablauf"])
        while plus_monate(t, -frist_m) < heute:
            t = plus_monate(t, 12)  # stillschweigende Verlängerung um ein Jahr
        kandidaten.append((t, frist_m, "auf Vertragsablauf"))
    if v.get("beginn"):
        b = date.fromisoformat(v["beginn"])
        # Art. 35a VVG: auf Ende des 3. Jahres und danach jährlich, Frist 3 Monate
        t = plus_monate(b, 36)
        while plus_monate(t, -3) < heute:
            t = plus_monate(t, 12)
        kandidaten.append((t, 3, "ordentliche Kündigung nach 3 Jahren (Art. 35a VVG)"))
    if not kandidaten:
        return None
    t, f, grund = min(kandidaten)
    return Termin(v, plus_monate(t, -f), t, grund)


def kuendigungstermine(vertraege: list[dict], heute: date) -> list[Termin]:
    termine = [t for v in vertraege if (t := naechster_termin(v, heute))]
    return sorted(termine, key=lambda t: t.kuendigen_bis)


def _personen_namen(k: dict) -> list[str]:
    return [p["name"] for p in k["personen"]] + [c.get("name", "Kind") for c in k["haushalt"].get("kinder") or []]


def gleiche_person(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    return bool(a and b) and (a == b or a in b.split() or b in a.split() or a.startswith(b + " ") or b.startswith(a + " "))


def deckungscheck(k: dict, vertraege: list[dict]) -> list[tuple[str, str, str]]:
    """Liste von (Status, Thema, Text); Status: ok | fehlt | pruefen | info."""
    nach: dict[str, list] = {}
    for v in vertraege:
        nach.setdefault(v["sparte"], []).append(v)
        if v["sparte"] == "hausrat_haftpflicht":
            nach.setdefault("hausrat", []).append(v)
            nach.setdefault("haftpflicht", []).append(v)
    erg = []

    # Grundversicherung pro Person
    kvg_personen = [v["person"] for v in nach.get("kvg", []) if v["person"].strip()]
    for name in _personen_namen(k):
        if any(gleiche_person(name, x) for x in kvg_personen):
            erg.append(("ok", "Grundversicherung", f"{name}: vorhanden."))
        elif nach.get("kvg") and not kvg_personen:
            erg.append(("pruefen", "Grundversicherung", f"{name}: Police vorhanden, aber keine Person zugeordnet."))
        else:
            erg.append(("fehlt", "Grundversicherung", f"{name}: keine Police erfasst – obligatorisch."))

    def einfach(sparte, thema, pflicht_text, wichtig=True):
        anzahl = len(nach.get(sparte, []))
        if anzahl == 1:
            erg.append(("ok", thema, "vorhanden."))
        elif anzahl > 1:
            erg.append(("pruefen", thema, f"{anzahl} Policen – mögliche Doppelversicherung, Deckungen vergleichen."))
        else:
            erg.append(("fehlt" if wichtig else "info", thema, pflicht_text))

    einfach("haftpflicht", "Privathaftpflicht", "keine Police erfasst – dringend empfohlen (ein Vertrag für den ganzen Haushalt).")
    einfach("hausrat", "Hausrat", "keine Police erfasst – empfohlen; Summe auf den Neuwert des Hausrats setzen.")
    if k["wohnen"].get("aktiv") or nach.get("gebaeude"):
        if len(nach.get("gebaeude", [])) == 2:
            erg.append(("ok", "Gebäude", "2 Policen – üblich: kantonale Gebäudeversicherung (Feuer, Elementar) "
                        "plus private Gebäudeversicherung (Wasser, Glas, Haftpflicht). Deckungen auf Überschneidungen prüfen."))
        else:
            einfach("gebaeude", "Gebäude", "keine Police erfasst – in den meisten Kantonen obligatorisch (kantonale Gebäudeversicherung).")
    if nach.get("rechtsschutz"):
        einfach("rechtsschutz", "Rechtsschutz", "", wichtig=False)
    if nach.get("reise"):
        einfach("reise", "Reise", "", wichtig=False)
        erg.append(("info", "Reise", "Viele Kreditkarten und Zusatzversicherungen decken Reise und Annullierung bereits."))

    # Todesfall: Hypothek oder Kinder
    hypothek = max(0.0, float(k["wohnen"].get("kaufpreis", 0)) - float(k["wohnen"].get("eigenmittel", 0))) \
        if k["wohnen"].get("aktiv") else 0.0
    import kinder as ki
    kinder = ki.anzahl(k)                     # unterhaltsberechtigte Kinder
    risiko = sum(float(v["summe"] or 0) for v in nach.get("risiko_leben", []) + nach.get("leben_3b", []))
    if hypothek or kinder:
        bedarf = hypothek * 0.5 + kinder * 100_000
        if risiko >= bedarf * 0.8:
            erg.append(("ok", "Todesfall", f"Todesfallsumme CHF {risiko:,.0f} – Richtwert CHF {bedarf:,.0f}." >> TS))
        else:
            erg.append(("pruefen", "Todesfall",
                        f"Erfasste Todesfallsumme CHF {risiko:,.0f}, Richtwert CHF {bedarf:,.0f} "
                        "(halbe Hypothek + 100'000 pro Kind). Witwen-/Waisenrenten von AHV und PK berücksichtigen; "
                        "eine reine Risikoversicherung ist meist günstig." >> TS))

    # Unfall doppelt: Grundversicherung mit Unfall bei Angestellten (UVG ab 8 Std./Woche)
    for v in nach.get("kvg", []):
        if v["unfall_eingeschlossen"]:
            person = next((p for p in k["personen"] if gleiche_person(p["name"], v["person"])), None)
            if person and float(person.get("lohn_brutto", 0)) > 0:
                erg.append(("pruefen", "Unfalldeckung",
                            f"{person['name']}: Unfall in der Grundversicherung eingeschlossen. Angestellte ab 8 Std./Woche "
                            "sind über den Arbeitgeber (UVG) versichert – Unfall sistieren spart rund 7–10 % Prämie."))
    # Franchise
    for v in nach.get("kvg", []):
        f = float(v["franchise"] or 0)
        if f and any(gleiche_person(p["name"], v["person"]) for p in k["personen"]):
            if f < 2500:
                erg.append(("info", "Franchise",
                            f"{v['person']}: Franchise CHF {f:,.0f}. Bei tiefen Gesundheitskosten (unter rund CHF 2'000 "
                            "pro Jahr) ist die Franchise 2'500 meist günstiger." >> TS))
    # Sparversicherungen
    for v in nach.get("leben_3b", []):
        erg.append(("info", "Lebensversicherung",
                    f"{v['versicherer'] or 'Police'} {v['police']}: Sparversicherung mit Kosten und langer Bindung. "
                    "Rückkaufswert und Kosten mit «Risikoversicherung + 3a-Wertschriften» vergleichen; "
                    "nicht vorschnell auflösen (Verlust bei frühem Rückkauf)."))
    # Erwerbsunfähigkeit
    if not nach.get("erwerbsunfaehigkeit"):
        erg.append(("info", "Erwerbsunfähigkeit",
                    "Keine private Police erfasst. IV und Pensionskasse decken einen Teil – Leistungen im Vorsorgeausweis prüfen."))
    return erg


def praemien(vertraege: list[dict]) -> dict:
    nach: dict[str, float] = {}
    for v in vertraege:
        nach[v["sparte"]] = nach.get(v["sparte"], 0) + float(v["praemie_jahr"] or 0)
    total = sum(nach.values())
    return {"total": round(total), "monat": round(total / 12), "nach_sparte": dict(sorted(nach.items(), key=lambda x: -x[1]))}


# ---------------------------------------------------------------- Liste importieren (ohne PDF)

ALIAS = [
    (r"grundvers|kvg|krankenkasse", "kvg"), (r"zusatz|vvg|spital", "vvg"),
    (r"hausrat.*haftpflicht|haftpflicht.*hausrat", "hausrat_haftpflicht"),
    (r"haftpflicht", "haftpflicht"), (r"hausrat", "hausrat"), (r"geb[äa]ude", "gebaeude"),
    (r"motorfahrzeug|auto|fahrzeug|moto", "motorfahrzeug"), (r"rechtsschutz", "rechtsschutz"),
    (r"invalid|erwerbsunf|erwerbsausfall", "erwerbsunfaehigkeit"), (r"\btod|todesfall|risiko", "risiko_leben"),
    (r"3b|3a|lebensvers", "leben_3b"), (r"uvg|unfall", "unfall"), (r"reise|annull", "reise"), (r"tier", "tier"),
]


def sparte_aus_text(text: str) -> str:
    t = (text or "").strip().lower()
    if t in SPARTEN:
        return t
    for muster, sparte in ALIAS:
        if re.search(muster, t):
            return sparte
    return "sonstiges"


def csv_import(db, inhalt: bytes) -> tuple[int, list[str]]:
    """Spalten (Kopfzeile, Reihenfolge egal): Versicherung/Sparte; Anbieter/Versicherer; Betrag/Prämie;
    optional Person; Police; Beginn; Ablauf; Kündigungsfrist; Franchise; Summe; Notiz."""
    import csv

    tabellen(db)
    text = inhalt.decode("utf-8-sig", errors="replace")
    try:
        dialekt = csv.Sniffer().sniff(text[:2048], delimiters=";,\t")
    except csv.Error:
        class dialekt(csv.excel):  # noqa: N801
            delimiter = ";"
    leser = csv.DictReader(io.StringIO(text), dialect=dialekt)
    spalten = {(s or "").strip().lower(): s for s in leser.fieldnames or []}

    def spalte(*namen):
        return next((spalten[n] for n in namen if n in spalten), None)

    s_sparte = spalte("versicherung", "sparte", "art")
    s_vers = spalte("anbieter", "versicherer", "gesellschaft")
    s_betrag = spalte("betrag", "prämie", "praemie", "prämie/jahr", "jahresprämie")
    if not s_sparte or not s_betrag:
        raise ValueError("Spalten «Versicherung» und «Betrag» (bzw. «Sparte» und «Prämie») fehlen.")
    weitere = {"person": spalte("person"), "police": spalte("police", "police-nr", "policennummer"),
               "beginn": spalte("beginn"), "ablauf": spalte("ablauf"),
               "kuendigungsfrist_monate": spalte("kündigungsfrist", "kuendigungsfrist"),
               "franchise": spalte("franchise"), "summe": spalte("summe", "versicherungssumme", "leistung"),
               "notiz": spalte("notiz", "kommentar")}
    n, fehler = 0, []
    for i, zeile in enumerate(leser, start=2):
        name = (zeile.get(s_sparte) or "").strip()
        if not name:
            continue
        try:
            werte = {"sparte": sparte_aus_text(name), "versicherer": (zeile.get(s_vers) or "").strip() if s_vers else "",
                     "praemie_jahr": zeile.get(s_betrag) or "0"}
            for feld, sp in weitere.items():
                if sp and (zeile.get(sp) or "").strip():
                    werte[feld] = zeile[sp].strip()
            werte = bereinigen(werte)
            if werte.get("sparte") == "sonstiges" or name.lower() not in SPARTEN:
                werte["notiz"] = (name + (" – " + werte["notiz"] if werte.get("notiz") else "")).strip()
            cur = db.execute("INSERT INTO vertraege (dateiname, hochgeladen, quelle) VALUES (?, ?, 'liste')",
                             (name, datetime.now().isoformat(timespec="seconds")))
            aktualisieren(db, cur.lastrowid, werte)
            n += 1
        except (ValueError, TypeError, AttributeError) as e:
            fehler.append(f"Zeile {i}: {e}")
    db.commit()
    return n, fehler


# ---------------------------------------------------------------- Risiko Invalidität und Tod

@dataclass
class Risiko:
    name: str
    lohn: float
    iv_ahv: float
    iv_kinder_ahv: float
    iv_pk: float
    iv_kinder_pk: float
    iv_extern: float
    iv_total: float
    iv_quote: float
    tod_renten: float
    tod_kapital: float
    tod_bedarf_kapital: float
    hinweise: list


def risiko(k: dict, ahv_ergebnisse) -> list[Risiko]:
    import kinder as ki
    verheiratet = k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet"
    w = k["wohnen"]
    hypothek = max(0.0, float(w.get("kaufpreis", 0)) - float(w.get("eigenmittel", 0))) if w.get("aktiv") else 0.0
    anteil_hyp = hypothek / max(1, len(k["personen"]))
    erg = []
    for p, a in zip(k["personen"], ahv_ergebnisse):
        r = p.get("risiko", {})
        lohn = float(p.get("lohn_brutto", 0))
        kinder = ki.anzahl(k, person=p["name"])    # eigene und gemeinsame Kinder bis 18 bzw. in Ausbildung
        # IV-Rente ≈ Altersrente ohne Vorbezug/Plafond, ohne 13. Rente (12 Monate); Kinderrente 40 %
        iv = a.vollrente * a.beitragsjahre / k["kennzahlen"]["ahv_vollbeitragsjahre"] * 12
        iv_kind = iv * 0.4 * kinder
        iv_pk = float(r.get("iv_rente_pk", 0))
        iv_kind_pk = float(r.get("iv_kinderrente_pk", 0)) * kinder
        iv_ext = float(r.get("iv_rente_extern", 0))
        total = iv + iv_kind + iv_pk + iv_kind_pk + iv_ext
        quote = total / lohn * 100 if lohn else 0
        h = []
        if lohn and quote < 70:
            h.append(f"Invalidität: {quote:.0f} % des Lohns gedeckt – Richtwert 70–80 %.")
        if iv_ext and iv_pk and quote > 100:
            h.append("Invalidität: Leistungen über dem Lohn – Überentschädigung wird meist gekürzt, externe Police prüfen.")
        # Tod: Renten für Hinterbliebene
        waisen = (iv * 0.4 + float(r.get("waisenrente_pk", 0))) * kinder
        partner_pk = float(r.get("partnerrente_pk", 0))
        partner_ahv = iv * 0.8 if verheiratet else 0.0
        if not verheiratet:
            if partner_pk and not r.get("partner_bei_pk_gemeldet"):
                h.append("Tod: Lebenspartnerrente der PK gibt es nur, wenn die Partnerschaft der Kasse gemeldet ist "
                         "(meist schriftlich zu Lebzeiten) – Meldung prüfen.")
                partner_pk = 0.0
            h.append("Tod: Ohne Heirat keine AHV-Witwen-/Witwerrente für den Partner – nur Waisenrenten.")
        renten = partner_ahv + partner_pk + waisen
        kapital = float(r.get("todesfallkapital_pk", 0)) + float(r.get("todesfallkapital_extern", 0))
        if not verheiratet and kapital:
            h.append("Tod: Begünstigung des Partners für PK-Todesfallkapital und Risikopolicen schriftlich festlegen; "
                     "Erbschaftssteuer für Konkubinatspartner im Wohnkanton prüfen.")
        if anteil_hyp and kapital < anteil_hyp * 0.5:
            h.append(f"Tod: Todesfallkapital CHF {kapital:,.0f} deckt weniger als die Hälfte des Hypothekenanteils "
                     f"(CHF {anteil_hyp:,.0f})." >> TS)
        erg.append(Risiko(p["name"], lohn, round(iv), round(iv_kind), round(iv_pk), round(iv_kind_pk), round(iv_ext),
                          round(total), round(quote, 1), round(renten), round(kapital), round(anteil_hyp * 0.5), h))
    return erg
