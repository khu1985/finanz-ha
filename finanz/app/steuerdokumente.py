"""Steuerdokumente: Steuererklärungen, Veranlagungsverfügungen und Steuerrechnungen.

Hochladen, Steuerperiode und Eckwerte erkennen (steuerbares Einkommen Kanton/Bund, Steuerbeträge,
Abzüge, Liegenschaft), mehrere Jahre vergleichen, Erklärung und Veranlagung abgleichen, Grenzsteuersatz
schätzen und die Werte in die Steuer-Einstellungen einer Person übernehmen.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

import json
import re
from datetime import datetime
from pathlib import Path

import versicherungen as vi

TYPEN = {
    "erklaerung": "Steuererklärung",
    "veranlagung": "Veranlagungsverfügung / definitive Rechnung",
    "rechnung": "Provisorische Steuerrechnung",
    "sonstiges": "Sonstiges",
}

# Schlüssel → (Beschriftung, Muster für die Zeile)
FELDER = {
    "steuerbar_kanton": ("Steuerbares Einkommen Kanton", None),
    "steuerbar_bund": ("Steuerbares Einkommen Bund", None),
    "satzbestimmend": ("Satzbestimmendes Einkommen", r"satzbestimmend"),
    "steuerbares_vermoegen": ("Steuerbares Vermögen", r"steuerbares vermögen|steuerbares reinvermögen"),
    "steuer_kanton_gemeinde": ("Staats- und Gemeindesteuer", r"(?:total )?(?:staats-|kantons-) ?(?:und|u\.) ?gemeindesteuer|total kanton und gemeinde|total steuern kanton"),
    "vermoegenssteuer": ("Vermögenssteuer", r"vermögenssteuer|steuer (?:auf dem|vom) vermögen"),
    "staatssteuer": ("Staatssteuer", r"^\s*staatssteuer|kantonssteuer(?! und)"),
    "gemeindesteuer": ("Gemeindesteuer", r"^\s*gemeindesteuer|einwohnergemeinde"),
    "bundessteuer": ("Direkte Bundessteuer", r"direkte bundessteuer|bundessteuer"),
    "einkuenfte_total": ("Total der Einkünfte", r"total (?:der )?einkünfte|gesamteinkommen"),
    "lohn_netto": ("Nettolohn (unselbständige Erwerbstätigkeit)", r"unselbständige|nettolohn|haupterwerb"),
    "eigenmietwert": ("Eigenmietwert", r"eigenmietwert"),
    "mietertrag": ("Mietertrag", r"mietertr[aä]g|mietzinseinnahmen|mieteinnahmen"),
    "abzug_3a": ("Abzug Säule 3a", r"säule 3a|gebundene selbstvorsorge|3a-beitr"),
    "abzug_pk_einkauf": ("Abzug PK-Einkauf", r"einkauf.{0,30}(?:vorsorge|pensionskasse|bvg)|(?:pensionskasse|bvg).{0,20}einkauf"),
    "schuldzinsen": ("Schuldzinsen", r"schuldzinsen"),
    "unterhalt_liegenschaft": ("Liegenschaftsunterhalt", r"unterhaltskosten|liegenschaftsunterhalt|unterhalt (?:der |des )?(?:liegenschaft|gebäude)"),
    "berufskosten": ("Berufskosten", r"berufsauslagen|berufskosten|berufsorientierte"),
    "kinderabzug": ("Kinderabzug", r"kinderabzug|abzug für (?:minderjährige )?kinder"),
    "kinderbetreuung": ("Kinderbetreuung", r"kinderbetreuung|fremdbetreuung|drittbetreuung"),
    "wertschriften": ("Wertschriften und Guthaben", r"wertschriften"),
    "schulden": ("Schulden", r"total (?:der )?schulden|private schulden"),
}

EINKOMMENSSTEUER = {"steuer_kanton_gemeinde", "staatssteuer", "gemeindesteuer", "bundessteuer"}

# Übernahme in die Konfiguration: Schlüssel → Ziel ("steuer:" = Steuereinheit der Person, "person:", "wohnen:")
ZIELE = {
    "steuerbar_kanton": "steuer:steuerbar_kanton",
    "steuerbar_bund": "steuer:steuerbar_bund",
    "steuer_kanton_gemeinde": "steuer:steuer_kanton_gemeinde",
    "grenzsteuersatz": "steuer:grenzsteuersatz_kanton",
    "steuerbares_vermoegen": "steuer:steuerbar_vermoegen",
    "vermoegenssteuer": "steuer:vermoegenssteuer",
    "abzug_3a": "person:saeule3a.beitrag_jahr",
    "eigenmietwert": "wohnen:eigenmietwert",
}


def tabellen(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS steuer_dok (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dateiname TEXT NOT NULL,
            datei TEXT NOT NULL DEFAULT '',
            hochgeladen TEXT NOT NULL,
            typ TEXT NOT NULL DEFAULT 'sonstiges',
            jahr INTEGER NOT NULL DEFAULT 0,
            person TEXT NOT NULL DEFAULT '',
            werte TEXT NOT NULL DEFAULT '{}',
            uebernommen TEXT NOT NULL DEFAULT '',
            quelle TEXT NOT NULL DEFAULT 'muster',
            text TEXT NOT NULL DEFAULT ''
        );
        """
    )


def ordner(daten: Path) -> Path:
    o = daten / "steuern"
    o.mkdir(parents=True, exist_ok=True)
    return o


# ---------------------------------------------------------------- Erkennung

def typ_erkennen(text: str) -> str:
    t = text.lower()
    if re.search(r"veranlagungsverfügung|veranlagungsentscheid|definitive (?:steuer)?rechnung|schlussrechnung|einschätzungsentscheid", t):
        return "veranlagung"
    if re.search(r"provisorische (?:steuer)?rechnung|ratenrechnung|akontorechnung", t):
        return "rechnung"
    if re.search(r"steuererklärung|steuererklaerung|wertschriftenverzeichnis|hilfsblatt", t):
        return "erklaerung"
    return "sonstiges"


def jahr_erkennen(text: str) -> int:
    m = re.search(r"(?:steuerperiode|steuerjahr|steuererklärung|veranlagung|bemessungsjahr)\D{0,12}(20\d{2})", text, re.I)
    if m:
        return int(m.group(1))
    jahre = [int(j) for j in re.findall(r"\b(20[1-3]\d)\b", text)]
    return max(set(jahre), key=jahre.count) if jahre else 0


def _betraege(text: str) -> list[float]:
    werte = []
    for m in re.finditer(r"(?<![\d.'’])(-?\d{1,3}(?:['’ ]\d{3})+(?:[.,]\d{1,2})?|-?\d+(?:[.,]\d{2})?)(?![\d'’])", text):
        roh = m.group(1)
        try:
            w = vi.zahl(roh)
        except ValueError:
            continue
        if 1900 <= abs(w) <= 2100 and not re.search(r"[.,'’]", roh):
            continue  # Jahreszahl
        if re.fullmatch(r"\d{1,3}", roh):
            continue  # Ziffern-Nummern im Formular
        werte.append(w)
    return werte


def _zeilenwert(zeile: str, muster: str) -> float | None:
    rest = re.split(muster, zeile, maxsplit=1, flags=re.I)[-1]
    rest = re.sub(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b", " ", rest)
    rest = re.sub(r"\b\d{1,2}(?:[.,]\d{1,3})?\s*%", " ", rest)  # Prozentangaben
    werte = [w for w in _betraege(rest) if abs(w) >= 50]
    return werte[-1] if werte else None


def erkennen(text: str) -> dict:
    erg = {"typ": typ_erkennen(text), "jahr": jahr_erkennen(text), "werte": {}}
    if not text.strip():
        return erg
    m = re.search(r"(?i:steuerpflichtige[r]? person|steuerpflichtig|name|herr|frau)\s*:?[ \t]*"
                  r"([A-ZÄÖÜ][\w-]+(?:[ \t][A-ZÄÖÜ0-9][\w-]*)?)", text)
    if m:
        erg["person"] = m.group(1).strip()
    zeilen = text.splitlines()
    # Steuerbares Einkommen: Kanton und Bund oft in einer Zeile oder getrennt beschriftet
    for z in zeilen:
        if not re.search(r"steuerbares einkommen", z, re.I):
            continue
        werte = [w for w in _betraege(re.split(r"steuerbares einkommen", z, flags=re.I)[-1]) if w >= 1000]
        zl = z.lower()
        if "bund" in zl and not re.search(r"staat|kanton", zl):
            if werte:
                erg["werte"].setdefault("steuerbar_bund", werte[-1])
        elif re.search(r"staat|kanton|gemeinde", zl) and "bund" not in zl:
            if werte:
                erg["werte"].setdefault("steuerbar_kanton", werte[-1])
        elif len(werte) >= 2:
            erg["werte"].setdefault("steuerbar_kanton", werte[0])
            erg["werte"].setdefault("steuerbar_bund", werte[1])
        elif werte:
            erg["werte"].setdefault("steuerbar_kanton", werte[0])
    for schluessel, (_, muster) in FELDER.items():
        if not muster or schluessel in erg["werte"]:
            continue
        for z in zeilen:
            if schluessel in EINKOMMENSSTEUER and re.search(r"vermögen", z, re.I):
                continue  # «Staatssteuer Vermögen» gehört zur Vermögenssteuer
            if re.search(muster, z, re.I) and not re.search(r"steuerbares einkommen", z, re.I):
                w = _zeilenwert(z, muster)
                if w is not None:
                    erg["werte"][schluessel] = abs(w)
                    break
    w = erg["werte"]
    if "steuer_kanton_gemeinde" not in w and ("staatssteuer" in w or "gemeindesteuer" in w):
        w["steuer_kanton_gemeinde"] = w.get("staatssteuer", 0) + w.get("gemeindesteuer", 0)
    return erg


# ---------------------------------------------------------------- Speicher

def hochladen(db, daten: Path, dateiname: str, inhalt: bytes) -> int:
    tabellen(db)
    text = vi.text_auslesen(dateiname, inhalt)
    e = erkennen(text)
    name = vi._sicherer_name(dateiname)
    cur = db.execute(
        "INSERT INTO steuer_dok (dateiname, hochgeladen, typ, jahr, person, werte, quelle, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, datetime.now().isoformat(timespec="seconds"), e["typ"], e["jahr"], e.get("person", ""),
         json.dumps(e["werte"]), "muster" if text.strip() else "ohne Text", text))
    did = cur.lastrowid
    pfad = ordner(daten) / f"{did}{Path(name).suffix.lower() or '.pdf'}"
    pfad.write_bytes(inhalt)
    db.execute("UPDATE steuer_dok SET datei = ? WHERE id = ?", (pfad.name, did))
    db.commit()
    return did


def _zeile(r) -> dict:
    d = dict(r)
    d["werte"] = json.loads(d["werte"] or "{}")
    return d


def alle(db) -> list[dict]:
    tabellen(db)
    return [_zeile(r) for r in db.execute("SELECT * FROM steuer_dok ORDER BY jahr DESC, person, typ")]


def einer(db, did: int) -> dict | None:
    tabellen(db)
    r = db.execute("SELECT * FROM steuer_dok WHERE id = ?", (did,)).fetchone()
    return _zeile(r) if r else None


def speichern(db, did: int, typ: str, jahr: int, person: str, werte: dict, quelle: str | None = None) -> None:
    db.execute("UPDATE steuer_dok SET typ = ?, jahr = ?, person = ?, werte = ?" + (", quelle = ?" if quelle else "")
               + " WHERE id = ?", (typ, jahr, person, json.dumps(werte), *([quelle] if quelle else []), did))
    db.commit()


def loeschen(db, daten: Path, did: int) -> None:
    d = einer(db, did)
    if d and d["datei"]:
        (ordner(daten) / d["datei"]).unlink(missing_ok=True)
    db.execute("DELETE FROM steuer_dok WHERE id = ?", (did,))
    db.commit()


# ---------------------------------------------------------------- Auswertung

def massgebend(doks: list[dict]) -> dict[tuple[str, int], dict]:
    """Pro (Person, Jahr) das massgebende Dokument: Veranlagung vor Erklärung vor Rechnung."""
    rang = {"veranlagung": 0, "erklaerung": 1, "rechnung": 2, "sonstiges": 3}
    erg: dict[tuple[str, int], dict] = {}
    for d in sorted(doks, key=lambda x: rang.get(x["typ"], 9)):
        schluessel = (d["person"] or "Haushalt", d["jahr"])
        erg.setdefault(schluessel, d)
    return erg


def vergleich(doks: list[dict]) -> dict:
    """Mehrjahresvergleich: {person: {jahr: werte}} und die vorkommenden Kennzahlen."""
    tabelle: dict[str, dict[int, dict]] = {}
    for (person, jahr), d in massgebend(doks).items():
        if jahr:
            tabelle.setdefault(person, {})[jahr] = d["werte"] | {"_typ": d["typ"], "_id": d["id"]}
    return tabelle


def grenzsteuersatz(jahre: dict[int, dict]) -> float | None:
    """Grenzsteuersatz Kanton+Gemeinde aus zwei Jahren schätzen (Δ Steuer / Δ steuerbares Einkommen)."""
    punkte = sorted((j, w["steuerbar_kanton"], w["steuer_kanton_gemeinde"]) for j, w in jahre.items()
                    if w.get("steuerbar_kanton") and w.get("steuer_kanton_gemeinde"))
    for (_, e0, s0), (_, e1, s1) in zip(reversed(punkte[:-1]), reversed(punkte[1:])):
        if abs(e1 - e0) >= 5000:
            satz = (s1 - s0) / (e1 - e0) * 100
            if 5 <= satz <= 45:
                return round(satz, 1)
    return None


def abgleich(doks: list[dict]) -> list[str]:
    """Unterschiede zwischen Steuererklärung und Veranlagung derselben Person und desselben Jahres."""
    hinweise = []
    gruppen: dict[tuple[str, int], dict[str, dict]] = {}
    for d in doks:
        gruppen.setdefault((d["person"] or "Haushalt", d["jahr"]), {})[d["typ"]] = d
    for (person, jahr), g in sorted(gruppen.items()):
        if "erklaerung" in g and "veranlagung" in g:
            e, v = g["erklaerung"]["werte"], g["veranlagung"]["werte"]
            for s in ("steuerbar_kanton", "steuerbar_bund", "steuerbares_vermoegen"):
                if s in e and s in v and abs(e[s] - v[s]) >= 100:
                    diff = v[s] - e[s]
                    hinweise.append(f"{person} {jahr}: {FELDER[s][0]} veranlagt {_f(v[s])} statt deklariert {_f(e[s])} "
                                    f"({'+' if diff > 0 else '−'}{_f(abs(diff))}) – Korrektur der Steuerverwaltung prüfen; "
                                    "Einsprache meist innert 30 Tagen.")
    return hinweise


def _f(v: float) -> str:
    return f"{v:,.0f}" >> TS


def hinweise(k: dict, d: dict) -> list[str]:
    import steuern as st
    w, h = d["werte"], []
    kz = k["kennzahlen"]
    person = next((p for p in k["personen"] if vi.gleiche_person(p["name"], d["person"])), None)
    if w.get("steuerbar_kanton") and w.get("steuer_kanton_gemeinde"):
        h.append(f"Effektiver Steuersatz Kanton und Gemeinde: {w['steuer_kanton_gemeinde'] / w['steuerbar_kanton'] * 100:.1f} %.")
    mit_abzuegen = d["typ"] == "erklaerung" or any(s in w for s in ("abzug_3a", "abzug_pk_einkauf", "berufskosten", "schuldzinsen"))
    if person and float(person.get("lohn_brutto", 0)) > 0 and mit_abzuegen:
        a3 = w.get("abzug_3a", 0)
        if a3 < kz["saeule3a_max"] - 50:
            luecke = kz["saeule3a_max"] - a3
            e = st.ersparnis_abzug(k, luecke, person["name"])
            h.append(f"Säule 3a: {_f(a3)} abgezogen, bis zum Maximum fehlen {_f(luecke)} – Ersparnis rund CHF {_f(e['total'])}. "
                     "Seit 2026 lassen sich Lücken ab 2025 nachzahlen.")
        pot = float(person["pk"].get("einkauf_potenzial", 0) or 0)
        if pot and not w.get("abzug_pk_einkauf"):
            betrag = min(pot, 30000)
            e = st.ersparnis_abzug(k, betrag, person["name"])
            h.append(f"Kein PK-Einkauf abgezogen. Einkaufspotenzial {_f(pot)}; ein Einkauf von {_f(betrag)} spart rund "
                     f"CHF {_f(e['total'])} ({e['total'] / betrag * 100:.0f} %). Auf mehrere Jahre verteilen.")
    emw = w.get("eigenmietwert", 0)
    if emw:
        unterhalt = w.get("unterhalt_liegenschaft", 0)
        if unterhalt and unterhalt <= emw * 0.2 + 1:
            h.append("Liegenschaftsunterhalt: offenbar Pauschale abgezogen. In Jahren mit höheren effektiven Kosten "
                     "(Renovation) effektive Kosten mit Belegen abziehen – Wahl pro Jahr möglich.")
        h.append(f"Eigenmietwert {_f(emw)}: Ab {kz['eigenmietwert_abschaffung']} entfallen Eigenmietwert, Schuldzins- und "
                 "Unterhaltsabzug. Grössere Unterhaltsarbeiten wenn möglich bis 2028 ausführen und abziehen.")
    if w.get("mietertrag"):
        h.append(f"Mietertrag {_f(w['mietertrag'])} versteuert – Unterhalt, der die vermietete Wohnung betrifft, bleibt "
                 "auch nach 2029 abzugsfähig.")
    if k["haushalt"].get("zivilstand") != "verheiratet" and len(k["haushalt"].get("kinder") or []) and w.get("kinderabzug"):
        h.append("Konkubinat mit Kind: Kinderabzug und Elterntarif erhält in der Regel der Elternteil mit dem höheren Einkommen "
                 "bzw. mit der Obhut – Aufteilung bei beiden Erklärungen prüfen.")
    return h


def uebernehmen(k: dict, d: dict, person_name: str, schluessel: list[str], grenz: float | None = None) -> list[str]:
    """Werte in die Konfiguration schreiben (Steuereinheit der Person, Person, Wohnen)."""
    werte = dict(d["werte"])
    if grenz:
        werte["grenzsteuersatz"] = grenz
    personen = [p["name"] for p in k["personen"]]
    if person_name not in personen:
        raise ValueError("Bitte eine Person wählen.")
    verheiratet = k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet"
    st_cfg = k["steuern"]
    if verheiratet:
        einheit = st_cfg
    else:
        liste = st_cfg.setdefault("personen", [])
        einheit = next((e for e in liste if str(e.get("person", "")).lower() == person_name.lower()), None)
        if einheit is None:
            einheit = {"person": person_name, "steuerbar_bund": 0, "steuerbar_kanton": 0, "steuer_kanton_gemeinde": 0,
                       "grenzsteuersatz_kanton": st_cfg.get("grenzsteuersatz_kanton", 0), "kinder": 0}
            liste.append(einheit)
    person = k["personen"][personen.index(person_name)]
    erledigt = []
    for s in schluessel:
        if s not in werte or s not in ZIELE:
            continue
        art, pfad = ZIELE[s].split(":")
        ziel = {"steuer": einheit, "person": person, "wohnen": k["wohnen"]}[art]
        teile = pfad.split(".")
        for t in teile[:-1]:
            ziel = ziel.setdefault(t, {})
        ziel[teile[-1]] = round(float(werte[s]), 1) if s == "grenzsteuersatz" else int(round(float(werte[s])))
        erledigt.append(FELDER.get(s, ("Grenzsteuersatz",))[0] if s != "grenzsteuersatz" else "Grenzsteuersatz")
    return erledigt


KI_ANWEISUNG = """Lies dieses Schweizer Steuerdokument und antworte NUR mit einem JSON-Objekt.
Schlüssel (nur vorhandene Werte, Zahlen in CHF ohne Tausendertrennzeichen): typ (erklaerung, veranlagung, rechnung),
jahr (Steuerperiode), person, {schluessel}.

Dokument:
{text}"""


def ki_auslesen(d: dict, entity_id: str) -> dict:
    anweisung = KI_ANWEISUNG.format(schluessel=", ".join(f"{s} ({b})" for s, (b, _) in FELDER.items()),
                                    text=d["text"][:30000])
    roh = vi.ki_aufgabe(anweisung, entity_id, "Steuerdokument auslesen")
    werte = {}
    for s, v in roh.items():
        if s in FELDER and v not in (None, ""):
            try:
                werte[s] = abs(vi.zahl(str(v)))
            except ValueError:
                pass
    typ = roh.get("typ") if roh.get("typ") in TYPEN else d["typ"]
    jahr = int(roh.get("jahr") or d["jahr"] or 0)
    return {"typ": typ, "jahr": jahr, "person": str(roh.get("person") or d["person"]), "werte": werte}
