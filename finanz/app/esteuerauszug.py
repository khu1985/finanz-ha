"""E-Steuerauszug der Bank (Standard eCH-0196) lesen: Konten, Wertschriften, Schulden, Erträge, Verrechnungssteuer.

Der Steuerauszug ist ein PDF für Menschen plus dieselben Daten maschinenlesbar (XML nach eCH-0196). Die App liest
- die **XML-Datei** direkt (manche Banken bieten sie im E-Banking zum Download an) oder als Anhang im PDF,
- sonst die **Totale aus dem PDF-Text** (Steuerwert, Bruttoertrag A/B, Verrechnungssteueranspruch).
Die Barcodes (PDF417) auf den letzten Seiten kann die App nicht lesen – dafür fehlt im App-Image ein Barcode-Leser.

Konten und Depots kommen mit dem Saldo per Stichtag (31.12.) ins Vermögen, die Summen in die Steuererklärung.
"""
from __future__ import annotations

import io
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from xml.etree import ElementTree as ET


@dataclass
class Posten:
    art: str                 # bank, depot, schuld
    name: str
    nummer: str = ""         # IBAN, Konto- oder Depotnummer
    waehrung: str = "CHF"
    saldo: float = 0.0       # in Kontowährung
    steuerwert: float = 0.0  # in CHF
    ertrag_a: float = 0.0    # mit Verrechnungssteuer
    ertrag_b: float = 0.0    # ohne Verrechnungssteuer (bei Schulden: Schuldzinsen)
    vst: float = 0.0
    titel: int = 0           # Anzahl Wertschriften im Depot


@dataclass
class Steuerauszug:
    institut: str = ""
    jahr: int = 0
    stichtag: str = ""
    kanton: str = ""
    quelle: str = "xml"      # xml oder pdf-text
    steuerwert: float = 0.0
    ertrag_a: float = 0.0
    ertrag_b: float = 0.0
    vst: float = 0.0
    schulden: float = 0.0
    schuldzinsen: float = 0.0
    spesen: float = 0.0
    posten: list[Posten] = field(default_factory=list)


def _name(e: ET.Element) -> str:
    return e.tag.rsplit("}", 1)[-1]


def _alle(e: ET.Element, name: str) -> list[ET.Element]:
    return [x for x in e.iter() if _name(x) == name]


def _kinder(e: ET.Element, name: str) -> list[ET.Element]:
    return [x for x in e if _name(x) == name]


def _z(e: ET.Element | None, attr: str) -> float:
    try:
        return float((e.get(attr) if e is not None else None) or 0)
    except ValueError:
        return 0.0


def _summe(elemente: list[ET.Element], attr: str) -> float:
    return round(sum(_z(e, attr) for e in elemente), 2)


def ist_xml(inhalt: bytes) -> bool:
    kopf = inhalt[:3000].decode("utf-8", "ignore")
    return "taxStatement" in kopf and "eCH-0196" in kopf


def _xml_aus_pdf(inhalt: bytes) -> bytes | None:
    """Eingebettete eCH-0196-XML-Datei (Dateianhang des PDFs), falls vorhanden."""
    try:
        from pypdf import PdfReader
        leser = PdfReader(io.BytesIO(inhalt))
        for _name_, daten in (leser.attachments or {}).items():
            for d in (daten if isinstance(daten, list) else [daten]):
                if ist_xml(d):
                    return d
    except Exception:  # noqa: BLE001
        return None
    return None


def aus_xml(xml: bytes) -> Steuerauszug:
    try:
        w = ET.fromstring(xml)
    except ET.ParseError as e:
        raise ValueError(f"Steuerauszug (XML) nicht lesbar: {e}") from e
    if _name(w) != "taxStatement":
        w = next(iter(_alle(w, "taxStatement")), None)
        if w is None:
            raise ValueError("Kein eCH-0196-Steuerauszug in der Datei.")
    inst = next(iter(_alle(w, "institution")), None)
    s = Steuerauszug(institut=(inst.get("name") if inst is not None else "") or "",
                     jahr=int(w.get("taxPeriod") or 0), stichtag=(w.get("periodTo") or "")[:10],
                     kanton=w.get("canton") or "", quelle="xml")
    for k in _alle(w, "bankAccount"):
        tw = next(iter(_kinder(k, "taxValue")), None)
        zahlungen = _kinder(k, "payment")
        s.posten.append(Posten(
            "bank", k.get("bankAccountName") or "Konto", k.get("iban") or k.get("bankAccountNumber") or "",
            (k.get("bankAccountCurrency") or (tw.get("balanceCurrency") if tw is not None else "") or "CHF").upper(),
            _z(tw, "balance"), _z(k, "totalTaxValue") or _z(tw, "value"),
            _z(k, "totalGrossRevenueA") or _summe(zahlungen, "grossRevenueA"),
            _z(k, "totalGrossRevenueB") or _summe(zahlungen, "grossRevenueB"),
            _z(k, "totalWithHoldingTaxClaim") or _summe(zahlungen, "withHoldingTaxClaim")))
    for d in _alle(w, "depot"):
        titel = _kinder(d, "security")
        werte = [tw for t in titel for tw in _kinder(t, "taxValue")]
        zahlungen = [p for t in titel for p in _kinder(t, "payment")]
        steuerwert = _summe(werte, "value")
        s.posten.append(Posten("depot", "Depot", d.get("depotNumber") or "", "CHF", steuerwert, steuerwert,
                               _summe(zahlungen, "grossRevenueA"), _summe(zahlungen, "grossRevenueB"),
                               _summe(zahlungen, "withHoldingTaxClaim"), len(titel)))
    for k in _alle(w, "liabilityAccount"):
        tw = next(iter(_kinder(k, "taxValue")), None)
        zinsen = _z(k, "totalGrossRevenueB") or _summe(_kinder(k, "payment"), "grossRevenueB")
        s.posten.append(Posten("schuld", k.get("bankAccountName") or "Schuld", k.get("iban") or
                               k.get("bankAccountNumber") or "", (k.get("bankAccountCurrency") or "CHF").upper(),
                               _z(tw, "balance"), _z(k, "totalTaxValue") or _z(tw, "value"), 0.0, zinsen))
    s.steuerwert = _z(w, "totalTaxValue") or round(sum(p.steuerwert for p in s.posten if p.art != "schuld"), 2)
    s.ertrag_a = _z(w, "totalGrossRevenueA") or round(sum(p.ertrag_a for p in s.posten if p.art != "schuld"), 2)
    s.ertrag_b = _z(w, "totalGrossRevenueB") or round(sum(p.ertrag_b for p in s.posten if p.art != "schuld"), 2)
    s.vst = _z(w, "totalWithHoldingTaxClaim") or round(sum(p.vst for p in s.posten), 2)
    s.schulden = round(sum(abs(p.steuerwert) for p in s.posten if p.art == "schuld"), 2)
    s.schuldzinsen = round(sum(p.ertrag_b for p in s.posten if p.art == "schuld"), 2)
    ausgaben = next(iter(_alle(w, "listOfExpenses")), None)
    s.spesen = _z(ausgaben, "totalExpensesDeductible") or _z(ausgaben, "totalExpenses")
    return s


_BETRAG = r"(-?\d{1,3}(?:['’ ]\d{3})*(?:\.\d{2})?)"


def _nach(text: str, muster: str) -> float:
    m = re.search(muster + r"[^\n\d-]{0,60}" + _BETRAG, text, re.I)
    return float(re.sub(r"['’ ]", "", m.group(1))) if m else 0.0


def ist_steuerauszug_text(text: str) -> bool:
    t = text.lower()
    return ("steuerauszug" in t or "steuerverzeichnis" in t or "e-steuerauszug" in t) and \
        ("steuerwert" in t) and ("verrechnungssteuer" in t or "bruttoertrag" in t)


def aus_text(text: str) -> Steuerauszug:
    """Nur die Totale aus dem lesbaren Teil des PDFs (wenn kein XML dabei ist)."""
    jahr = re.search(r"(?:steuerjahr|steuerperiode|per\s+31\.\s?12\.)\s*(20\d{2})", text, re.I) or \
        re.search(r"31\.12\.(20\d{2})", text)
    inst = next((z.strip() for z in text.splitlines()[:15] if re.search(r"\b(bank|banque|ag|sa)\b", z, re.I)), "")
    s = Steuerauszug(institut=inst[:80], jahr=int(jahr.group(1)) if jahr else 0, quelle="pdf-text")
    s.stichtag = f"{s.jahr}-12-31" if s.jahr else ""
    s.steuerwert = _nach(text, r"total\s+(?:der\s+)?steuerwert\w*")
    s.ertrag_a = _nach(text, r"bruttoertrag\w*\s+(?:a\b|mit\s+verrechnungssteuer|mit\s+vst)")
    s.ertrag_b = _nach(text, r"bruttoertrag\w*\s+(?:b\b|ohne\s+verrechnungssteuer|ohne\s+vst)")
    s.vst = _nach(text, r"verrechnungssteuer(?:anspruch|\s+\(?anspruch\)?)")
    s.schuldzinsen = _nach(text, r"(?:total\s+)?schuldzinsen")
    s.schulden = abs(_nach(text, r"total\s+(?:der\s+)?schulden"))
    s.spesen = _nach(text, r"(?:abzugsfähige\s+)?(?:depot|vermögensverwaltungs)?spesen")
    if not (s.steuerwert or s.ertrag_a or s.ertrag_b):
        raise ValueError("Steuerauszug erkannt, aber keine Totale gefunden – bitte die XML-Datei hochladen, falls die "
                         "Bank eine anbietet.")
    return s


def lesen(inhalt: bytes, name: str = "") -> Steuerauszug:
    if ist_xml(inhalt):
        return aus_xml(inhalt)
    if inhalt[:5] == b"%PDF-":
        xml = _xml_aus_pdf(inhalt)
        if xml:
            return aus_xml(xml)
        import versicherungen as vi
        text = vi.text_auslesen(name or "steuerauszug.pdf", inhalt)
        if ist_steuerauszug_text(text):
            return aus_text(text)
    raise ValueError("Kein E-Steuerauszug erkannt (eCH-0196 als XML oder PDF der Bank).")


# ---------------------------------------------------------------- Speichern und übernehmen

def tabellen(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS steuerauszug (id INTEGER PRIMARY KEY AUTOINCREMENT, institut TEXT, "
               "jahr INTEGER, stichtag TEXT, quelle TEXT, daten TEXT NOT NULL, datum TEXT NOT NULL)")


def _bankname(institut: str) -> str:
    import bankimport as bi
    return next((n for s_, n in bi.BANKEN if s_ in institut.lower()), institut.split(",")[0].strip()[:30] or "Bank")


def kontoname(s: Steuerauszug, p: Posten) -> str:
    """Wie beim Kontoauszug-Import («Raiffeisen …1234»), damit Saldi aus beiden Quellen im selben Konto landen."""
    bank = _bankname(s.institut)
    endung = ("…" + re.sub(r"\s", "", p.nummer)[-4:]) if p.nummer else p.name
    return {"bank": f"{bank} {endung}", "depot": f"{bank} Depot {endung}"}.get(p.art, f"{bank} {p.name} {endung}".strip())


def speichern(db, s: Steuerauszug, person: str = "") -> tuple[int, int]:
    """Auszug ablegen und Saldi per Stichtag ins Vermögen übernehmen. Ergibt (id, Anzahl übernommener Konten)."""
    import vermoegen as vm
    tabellen(db)
    db.execute("DELETE FROM steuerauszug WHERE institut = ? AND jahr = ? AND quelle = ?", (s.institut, s.jahr, s.quelle))
    cur = db.execute("INSERT INTO steuerauszug (institut, jahr, stichtag, quelle, daten, datum) VALUES (?, ?, ?, ?, ?, ?)",
                     (s.institut, s.jahr, s.stichtag, s.quelle, json.dumps(asdict(s), ensure_ascii=False),
                      datetime.now().isoformat(timespec="seconds")))
    n = 0
    if s.stichtag:
        for p in s.posten:
            if p.art == "schuld":
                art = "hypothek" if re.search(r"hypo|liegenschaft", p.name, re.I) else "kredit"
            else:
                art = p.art
            kid = vm.konto_anlegen(db, kontoname(s, p), art, person, p.waehrung if p.art == "bank" else "CHF")
            vm.saldo_setzen(db, kid, s.stichtag, -abs(p.saldo) if art in vm.SCHULDEN else p.saldo)
            n += 1
    db.commit()
    return cur.lastrowid, n


def alle(db) -> list[dict]:
    tabellen(db)
    erg = []
    for r in db.execute("SELECT id, daten FROM steuerauszug ORDER BY jahr DESC, institut"):
        d = json.loads(r[1])
        d["id"] = r[0]
        erg.append(d)
    return erg


def loeschen(db, sid: int) -> None:
    tabellen(db)
    db.execute("DELETE FROM steuerauszug WHERE id = ?", (sid,))
    db.commit()


def summen(db, jahr: int) -> dict | None:
    """Summen aller Steuerauszüge eines Jahres für die Steuererklärung."""
    auszuege = [a for a in alle(db) if a["jahr"] == jahr]
    if not auszuege:
        return None
    felder = ("steuerwert", "ertrag_a", "ertrag_b", "vst", "schulden", "schuldzinsen", "spesen")
    erg = {f: round(sum(a.get(f) or 0 for a in auszuege), 2) for f in felder}
    erg["institute"] = [a["institut"] for a in auszuege]
    return erg
