"""Vorsorgedokumente: Vorsorgeausweis der Pensionskasse, 3a-Auszug, IK-Auszug der AHV.

Hochladen, Text auslesen, Werte erkennen und auf Wunsch in die Einstellungen einer Person übernehmen.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

import versicherungen as vi

TYPEN = {
    "pk_ausweis": "Vorsorgeausweis Pensionskasse",
    "saeule3a": "Säule-3a-Auszug",
    "saeule3b": "Säule 3b (freie Vorsorge: Police oder Konto)",
    "ik_auszug": "IK-Auszug / Rentenvorausberechnung AHV",
    "sonstiges": "Sonstiges",
}

# Erkannte Werte: Schlüssel → (Beschriftung, Zielpfad unter personen.<i>., Muster)
WERTE_PK = {
    "altersguthaben": ("Altersguthaben heute", "pk.altersguthaben",
                       r"(?:vorhandenes |aktuelles )?altersguthaben(?! im alter| mit| bei)(?!.*\b6[0-9]\b)"),
    "einkauf_potenzial": ("Maximaler Einkauf", "pk.einkauf_potenzial",
                          r"(?:maximal(?:e[rn]?)? (?:möglich(?:e[rn]?)? )?einkauf|einkaufspotenzial|einkaufsmöglichkeit|möglicher einkauf|einkaufssumme)"),
    "ausweis_alterskapital": ("Alterskapital mit 65 (Prognose)", "pk.ausweis_alterskapital",
                              r"(?:alterskapital|voraussichtliches altersguthaben|altersguthaben (?:im alter|mit|bei) 6[0-9]|projiziertes altersguthaben)"),
    "ausweis_altersrente": ("Altersrente pro Jahr (Prognose)", "pk.ausweis_altersrente",
                            r"(?:jährliche |voraussichtliche )?altersrente"),
    "sparbeitrag_jahr": ("Sparbeitrag pro Jahr (AN + AG)", "pk.sparbeitrag_jahr",
                         r"(?:sparbeitrag|altersgutschrift)(?:e)?(?: total| arbeitnehmer und arbeitgeber)?"),
    "umwandlungssatz": ("Umwandlungssatz %", "pk.umwandlungssatz", r"umwandlungssatz"),
    "zins": ("Zins %", "pk.zins", r"(?:projektionszins|verzinsung|zinssatz)"),
    "iv_rente_pk": ("Invalidenrente pro Jahr", "risiko.iv_rente_pk", r"invalidenrente(?!.*kind)"),
    "iv_kinderrente_pk": ("Invaliden-Kinderrente pro Jahr", "risiko.iv_kinderrente_pk",
                          r"invaliden-?kinderrente|kinderrente bei invalidität"),
    "partnerrente_pk": ("Ehegatten-/Partnerrente pro Jahr", "risiko.partnerrente_pk",
                        r"(?:ehegatten|lebenspartner|partner|witwen|hinterlassenen)-?rente"),
    "waisenrente_pk": ("Waisenrente pro Jahr", "risiko.waisenrente_pk", r"waisenrente"),
    "todesfallkapital_pk": ("Todesfallkapital", "risiko.todesfallkapital_pk", r"todesfallkapital"),
    "lohn": ("Jahreslohn (AHV-Lohn)", "lohn_brutto", r"(?:massgebender |gemeldeter )?(?:jahreslohn|ahv-lohn|jahresbruttolohn)"),
}

ANBIETER_3A = ["VIAC", "frankly", "finpension", "Selma", "True Wealth", "Descartes", "Mobiliar", "PostFinance",
               "Raiffeisen", "UBS", "ZKB", "Zürcher Kantonalbank", "BLKB", "Basellandschaftliche", "Swissquote",
               "Migros Bank", "Valiant", "Swiss Life", "AXA", "Helvetia", "Baloise", "Allianz"]


def tabellen(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS vorsorge_dok (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dateiname TEXT NOT NULL,
            datei TEXT NOT NULL DEFAULT '',
            hochgeladen TEXT NOT NULL,
            typ TEXT NOT NULL DEFAULT 'sonstiges',
            person TEXT NOT NULL DEFAULT '',
            anbieter TEXT NOT NULL DEFAULT '',
            stichtag TEXT NOT NULL DEFAULT '',
            werte TEXT NOT NULL DEFAULT '{}',
            uebernommen TEXT NOT NULL DEFAULT '',
            quelle TEXT NOT NULL DEFAULT 'muster',
            text TEXT NOT NULL DEFAULT ''
        );
        """
    )


def ordner(daten: Path) -> Path:
    o = daten / "vorsorge"
    o.mkdir(parents=True, exist_ok=True)
    return o


# ---------------------------------------------------------------- Erkennung

def typ_erkennen(text: str) -> str:
    t = text.lower()
    punkte = {
        "pk_ausweis": sum(t.count(w) for w in ("vorsorgeausweis", "pensionskasse", "altersguthaben", "umwandlungssatz",
                                                "bvg", "invalidenrente", "einkauf")),
        "saeule3a": sum(t.count(w) for w in ("säule 3a", "saeule 3a", "3a-konto", "vorsorgekonto", "vorsorgefonds",
                                              "gebundene vorsorge", "vorsorgestiftung 3a")) * 2,
        "saeule3b": sum(t.count(w) for w in ("säule 3b", "saeule 3b", "säule-3b", "3b-konto", "3b-police", "freie vorsorge",
                                              "rückkaufswert", "erlebensfallkapital", "erlebensfall")) * 2,
        "ik_auszug": sum(t.count(w) for w in ("individuelles konto", "ik-auszug", "kontoauszug ahv",
                                               "ausgleichskasse", "beitragsjahre", "rentenvorausberechnung")) * 2,
    }
    beste = max(punkte, key=punkte.get)
    return beste if punkte[beste] >= 2 else "sonstiges"


def _betraege(zeile: str) -> list[float]:
    werte = []
    for m in re.finditer(r"(?<![\d.])(\d{1,3}(?:['’ ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,3})?)(?![\d])", zeile):
        roh = m.group(1)
        try:
            w = vi.zahl(roh)
        except ValueError:
            continue
        if 1900 <= w <= 2100 and not re.search(r"[.,']", roh):
            continue  # Jahreszahl
        werte.append(w)
    return werte


def _wert_nach(text: str, muster: str, prozent: bool = False, alter65: bool = False) -> float | None:
    kandidaten = []
    zeilen = text.splitlines()
    for i, zeile in enumerate(zeilen):
        if not re.search(muster, zeile, re.I):
            continue
        rest = re.split(muster, zeile, maxsplit=1, flags=re.I)[-1]
        if not _betraege(rest) and i + 1 < len(zeilen):
            rest += " " + zeilen[i + 1]
        rest = re.sub(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b", " ", rest)  # Datumsangaben entfernen
        werte = [w for w in _betraege(rest) if (w < 20 if prozent else w >= 100)]
        if not werte:
            continue
        bonus = 1 if alter65 and re.search(r"\b65\b", zeile) else 0
        kandidaten.append((bonus, werte[-1] if alter65 else werte[0]))
    if not kandidaten:
        return None
    if alter65:
        beste = max(b for b, _ in kandidaten)
        return max(w for b, w in kandidaten if b == beste)
    return kandidaten[0][1]


def _stichtag(text: str) -> str:
    m = re.search(r"(?:stichtag|stand|per|gültig ab|datum)\D{0,15}(\d{1,2}\.\s?\d{1,2}\.\s?\d{4})", text, re.I)
    if m:
        try:
            return vi.datum_iso(m.group(1))
        except (ValueError, IndexError):
            pass
    return ""


def erkennen(text: str) -> dict:
    erg = {"typ": typ_erkennen(text), "werte": {}, "stichtag": _stichtag(text), "anbieter": ""}
    if not text.strip():
        return erg
    m = re.search(r"(?i:versicherte person|versicherter|name|kontoinhaber(?:in)?)\s*:?[ \t]*"
                  r"((?:Herr|Frau)\s+)?([A-ZÄÖÜ][\w-]+(?:[ \t][A-ZÄÖÜ0-9][\w-]*)?)", text)
    if m:
        erg["person"] = m.group(2).strip()
    if erg["typ"] == "pk_ausweis":
        for schluessel, (_, _, muster) in WERTE_PK.items():
            w = _wert_nach(text, muster, prozent=schluessel in ("umwandlungssatz", "zins"),
                           alter65=schluessel in ("ausweis_alterskapital", "ausweis_altersrente"))
            if w is not None:
                erg["werte"][schluessel] = w
        m = re.search(r"(?:pensionskasse|vorsorgeeinrichtung|stiftung)\s*:?\s*([A-ZÄÖÜ][^\n]{2,60})", text)
        erg["anbieter"] = m.group(1).strip() if m else ""
    elif erg["typ"] == "saeule3a":
        w = _wert_nach(text, r"(?:saldo|kontostand|guthaben|gesamtvermögen|vermögen total|total vermögen|depotwert)")
        if w is not None:
            erg["werte"]["guthaben_3a"] = w
        w = _wert_nach(text, r"(?:einzahlungen|einzahlung|beiträge)\s*(?:\d{4})?")
        if w is not None and w <= 40000:
            erg["werte"]["beitrag_3a"] = w
        erg["anbieter"] = next((a for a in ANBIETER_3A if re.search(rf"\b{re.escape(a)}\b", text, re.I)), "")
    elif erg["typ"] == "saeule3b":
        for schluessel, muster in (
                ("guthaben_3b", r"(?:rückkaufswert|vertragswert|policenwert|saldo|kontostand|guthaben|depotwert|vermögen total)"),
                ("praemie_3b", r"(?:jahresprämie|prämie pro jahr|jährliche prämie|prämie|einzahlungen|einzahlung|beiträge)"),
                ("erlebensfall_3b", r"(?:garantiertes |voraussichtliches )?erlebensfall(?:kapital|leistung|summe)?"),
                ("todesfall_3b", r"(?:todesfallkapital|todesfallsumme|todesfallleistung|leistung im todesfall|bei tod)")):
            w = _wert_nach(text, muster)
            if w is not None:
                erg["werte"][schluessel] = w
        erg["anbieter"] = next((a for a in ANBIETER_3A if re.search(rf"\b{re.escape(a)}\b", text, re.I)), "")
    elif erg["typ"] == "ik_auszug":
        jahre = {}
        for zeile in text.splitlines():
            mj = re.match(r"\s*((?:19|20)\d{2})\b(.*)", zeile)
            if mj:
                werte = [w for w in _betraege(mj.group(2)) if w >= 100]
                if werte:
                    jahre[int(mj.group(1))] = jahre.get(int(mj.group(1)), 0) + werte[-1]
        if jahre:
            erg["werte"]["beitragsjahre"] = len(jahre)
            erg["werte"]["einkommen_durchschnitt"] = round(sum(jahre.values()) / len(jahre))
        w = _wert_nach(text, r"(?:voraussichtliche |monatliche )?altersrente")
        if w is not None:
            erg["werte"]["ahv_rente_monat"] = w
    return erg


ZIELE = {
    **{s: (b, z) for s, (b, z, _) in WERTE_PK.items()},
    "guthaben_3a": ("3a-Guthaben", "saeule3a.guthaben"),
    "beitrag_3a": ("3a-Beitrag pro Jahr", "saeule3a.beitrag_jahr"),
    "guthaben_3b": ("3b-Guthaben bzw. Rückkaufswert → Saldo unter Vermögen", "vermoegen"),
    "praemie_3b": ("3b-Prämie bzw. Einzahlung pro Jahr (nur Info)", ""),
    "erlebensfall_3b": ("Erlebensfallkapital (nur Info)", ""),
    "todesfall_3b": ("Todesfallleistung → Todesfallkapital Policen (ersetzt)", "risiko.todesfallkapital_extern"),
    "beitragsjahre": ("AHV-Beitragsjahre bisher", "ahv.beitragsjahre_bisher"),
    "einkommen_durchschnitt": ("Ø AHV-Einkommen", "ahv.einkommen_durchschnitt"),
    "ahv_rente_monat": ("AHV-Rente pro Monat (nur Info)", ""),
}


# ---------------------------------------------------------------- Speicher

def hochladen(db, daten: Path, dateiname: str, inhalt: bytes) -> int:
    tabellen(db)
    text = vi.text_auslesen(dateiname, inhalt)
    e = erkennen(text)
    name = vi._sicherer_name(dateiname)
    cur = db.execute(
        "INSERT INTO vorsorge_dok (dateiname, hochgeladen, typ, person, anbieter, stichtag, werte, quelle, text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, datetime.now().isoformat(timespec="seconds"), e["typ"], e.get("person", ""), e["anbieter"],
         e["stichtag"], json.dumps(e["werte"]), "muster" if text.strip() else "ohne Text", text))
    vid = cur.lastrowid
    pfad = ordner(daten) / f"{vid}{Path(name).suffix.lower() or '.pdf'}"
    pfad.write_bytes(inhalt)
    db.execute("UPDATE vorsorge_dok SET datei = ? WHERE id = ?", (pfad.name, vid))
    db.commit()
    return vid


def alle(db) -> list[dict]:
    tabellen(db)
    return [_mit_werten(r) for r in db.execute("SELECT * FROM vorsorge_dok ORDER BY hochgeladen DESC")]


def einer(db, did: int) -> dict | None:
    tabellen(db)
    r = db.execute("SELECT * FROM vorsorge_dok WHERE id = ?", (did,)).fetchone()
    return _mit_werten(r) if r else None


def _mit_werten(r) -> dict:
    d = dict(r)
    d["werte"] = json.loads(d["werte"] or "{}")
    return d


def speichern(db, did: int, typ: str, person: str, werte: dict, quelle: str | None = None) -> None:
    db.execute("UPDATE vorsorge_dok SET typ = ?, person = ?, werte = ?" + (", quelle = ?" if quelle else "")
               + " WHERE id = ?", (typ, person, json.dumps(werte), *([quelle] if quelle else []), did))
    db.commit()


def loeschen(db, daten: Path, did: int) -> None:
    d = einer(db, did)
    if d and d["datei"]:
        (ordner(daten) / d["datei"]).unlink(missing_ok=True)
    db.execute("DELETE FROM vorsorge_dok WHERE id = ?", (did,))
    db.commit()


def uebernehmen(k: dict, dok: dict, person_index: int, schluessel: list[str]) -> list[str]:
    """Ausgewählte Werte in personen.<i> der Konfiguration schreiben. Gibt die Beschriftungen zurück."""
    p = k["personen"][person_index]
    erledigt = []
    for s in schluessel:
        if s not in dok["werte"] or s not in ZIELE or not ZIELE[s][1] or ZIELE[s][1] == "vermoegen":
            continue
        ziel = ZIELE[s][1].split(".")
        obj = p
        for teil in ziel[:-1]:
            obj = obj.setdefault(teil, {})
        alt = obj.get(ziel[-1])
        wert = dok["werte"][s]
        obj[ziel[-1]] = int(round(wert)) if isinstance(alt, int) and not isinstance(alt, bool) else float(wert)
        erledigt.append(ZIELE[s][0])
    if dok["typ"] == "pk_ausweis" and dok.get("stichtag") and "altersguthaben" in schluessel:
        p["pk"]["stand"] = dok["stichtag"]
    return erledigt


WERTE_JE_TYP = {
    "pk_ausweis": list(WERTE_PK),
    "saeule3a": ["guthaben_3a", "beitrag_3a"],
    "saeule3b": ["guthaben_3b", "praemie_3b", "erlebensfall_3b", "todesfall_3b"],
    "ik_auszug": ["beitragsjahre", "einkommen_durchschnitt", "ahv_rente_monat"],
}


def konto_3b_vorschlag(dok: dict, person: str) -> str:
    return " ".join(x for x in ("3b", dok.get("anbieter") or "", person) if x).strip()


def guthaben_3b_uebernehmen(k: dict, db, dok: dict, person: str, konto: str) -> str:
    """3b-Guthaben als Saldo eines Vorsorge-Kontos unter «Vermögen»; verpfändete 3b unter Wohnen gleich nachführen."""
    import vermoegen as vm
    wert = float(dok["werte"]["guthaben_3b"])
    konto = (konto or konto_3b_vorschlag(dok, person)).strip()
    kid = vm.konto_anlegen(db, konto, "vorsorge", person)
    tag = dok.get("stichtag") or date.today().isoformat()
    vm.saldo_setzen(db, kid, tag, wert)
    for e in (k.get("wohnen") or {}).get("verpfaendet") or []:
        if str(e.get("name", "")).strip().lower() == konto.lower():
            e["guthaben"] = int(round(wert))
    return f"3b-Guthaben als Saldo «{konto}»"


KI_ANWEISUNG = """Lies dieses Schweizer Vorsorgedokument ({typ}) und antworte NUR mit einem JSON-Objekt.
Mögliche Schlüssel (nur vorhandene Werte, Zahlen ohne Tausendertrennzeichen, Renten pro Jahr):
{schluessel}, stichtag (JJJJ-MM-TT), anbieter, person.

Dokument:
{text}"""


def ki_auslesen(dok: dict, entity_id: str) -> dict:
    schluessel = ", ".join(f"{s} ({b})" for s, (b, _) in ZIELE.items())
    anweisung = KI_ANWEISUNG.format(typ=TYPEN.get(dok["typ"], "Vorsorge"), schluessel=schluessel, text=dok["text"][:30000])
    roh = vi.ki_aufgabe(anweisung, entity_id, "Vorsorgedokument auslesen")
    werte = {s: float(vi.zahl(str(v))) for s, v in roh.items() if s in ZIELE and v not in (None, "")}
    return {"werte": werte, "stichtag": str(roh.get("stichtag") or dok["stichtag"]),
            "anbieter": str(roh.get("anbieter") or dok["anbieter"])}
