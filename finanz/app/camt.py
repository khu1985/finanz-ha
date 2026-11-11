"""Kontoauszüge im Bankformat ISO 20022 (camt.053 Tagesauszug, camt.052 Kontobericht, camt.054 Avis) lesen.

Schweizer Banken bieten im E-Banking den Export «camt.053» (XML, oft mehrere Dateien als ZIP) an. Anders als
CSV ist das Format eindeutig: Buchungsdatum, Betrag mit Soll/Haben, Gegenpartei, Mitteilung und Schlusssaldo
stehen in festen Feldern. Gelesen wird namensraumunabhängig, damit alle Versionen (.001.02 bis .001.13) gehen.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from xml.etree import ElementTree as ET


@dataclass
class Konto:
    iban: str = ""
    waehrung: str = "CHF"
    bank: str = ""
    buchungen: list[tuple[str, float, str]] = field(default_factory=list)
    schlusssaldi: dict[str, float] = field(default_factory=dict)      # Datum → Saldo (CLBD)


def ist_camt(inhalt: bytes) -> bool:
    if inhalt[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(inhalt)) as z:
                return any(n.lower().endswith(".xml") for n in z.namelist())
        except zipfile.BadZipFile:
            return False
    kopf = inhalt[:4000].decode("utf-8", "ignore")
    return "<Document" in kopf and re.search(r"camt\.05[234]", kopf) is not None


def _xml_dateien(inhalt: bytes) -> list[bytes]:
    if inhalt[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(inhalt)) as z:
            return [z.read(n) for n in sorted(z.namelist()) if n.lower().endswith(".xml")]
    return [inhalt]


def _name(e: ET.Element) -> str:
    return e.tag.rsplit("}", 1)[-1]


def _kind(e: ET.Element | None, *pfad: str) -> ET.Element | None:
    for teil in pfad:
        if e is None:
            return None
        e = next((c for c in e if _name(c) == teil), None)
    return e


def _kinder(e: ET.Element | None, name: str) -> list[ET.Element]:
    return [c for c in e if _name(c) == name] if e is not None else []


def _text(e: ET.Element | None, *pfad: str) -> str:
    x = _kind(e, *pfad) if pfad else e
    return (x.text or "").strip() if x is not None else ""


def _datum(e: ET.Element | None) -> str:
    """<BookgDt><Dt>…</Dt></BookgDt> oder <DtTm>…</DtTm>."""
    t = _text(e, "Dt") or _text(e, "DtTm")
    return t[:10] if re.match(r"\d{4}-\d{2}-\d{2}", t) else ""


def _betrag(e: ET.Element) -> float:
    w = float(_text(e, "Amt") or 0)
    return -w if _text(e, "CdtDbtInd") == "DBIT" else w


def _partei(tx: ET.Element, rolle: str) -> str:
    """Name der Gegenpartei; ab camt.053.001.08 steckt er unter <Pty>."""
    p = _kind(tx, "RltdPties", rolle)
    return _text(p, "Nm") or _text(p, "Pty", "Nm")


def _tx_text(ntry: ET.Element, tx: ET.Element | None, gutschrift: bool) -> str:
    teile = []
    if tx is not None:
        teile.append(_partei(tx, "Dbtr" if gutschrift else "Cdtr"))
        rmt = _kind(tx, "RmtInf")
        teile += [_text(u) for u in _kinder(rmt, "Ustrd")]
        teile.append(_text(rmt, "Strd", "CdtrRefInf", "Ref") if not any(teile) else "")
        teile.append(_text(tx, "AddtlTxInf"))
    teile.append(_text(ntry, "AddtlNtryInf"))
    return re.sub(r"\s+", " ", " ".join(dict.fromkeys(t for t in teile if t)))[:200]


def _auszug(stmt: ET.Element, konto: Konto) -> None:
    acct = _kind(stmt, "Acct")
    konto.iban = konto.iban or _text(acct, "Id", "IBAN") or _text(acct, "Id", "Othr", "Id")
    konto.waehrung = _text(acct, "Ccy") or konto.waehrung
    konto.bank = konto.bank or _text(acct, "Svcr", "FinInstnId", "Nm")
    for bal in _kinder(stmt, "Bal"):
        art = _text(bal, "Tp", "CdOrPrtry", "Cd")
        tag = _datum(_kind(bal, "Dt"))
        if art in ("CLBD", "ITBD") and tag:
            konto.schlusssaldi[tag] = round(_betrag(bal), 2)
        elif art in ("OPBD", "PRCD") and tag:
            # Eröffnungssaldo = Saldo am Vortag
            vortag = (date.fromisoformat(tag) - timedelta(days=1)).isoformat()
            konto.schlusssaldi.setdefault(vortag, round(_betrag(bal), 2))
    for ntry in _kinder(stmt, "Ntry"):
        status = _text(ntry, "Sts", "Cd") or _text(ntry, "Sts")
        if status and status not in ("BOOK", "Book"):
            continue                                       # vorgemerkte Buchungen nicht zählen
        if _text(ntry, "RvslInd") == "true":
            pass                                           # Storno: Vorzeichen steht bereits in CdtDbtInd
        tag = _datum(_kind(ntry, "BookgDt")) or _datum(_kind(ntry, "ValDt"))
        if not tag:
            continue
        betrag = _betrag(ntry)
        gutschrift = betrag > 0
        txs = [tx for d in _kinder(ntry, "NtryDtls") for tx in _kinder(d, "TxDtls")]
        # Sammelbuchung mit Einzelbeträgen → einzeln, sonst eine Buchung
        einzel = [(tx, _kind(tx, "Amt") if _kind(tx, "Amt") is not None else _kind(tx, "AmtDtls", "TxAmt", "Amt"))
                  for tx in txs]
        if len(txs) > 1 and all(a is not None for _, a in einzel):
            summe = 0.0
            for tx, a in einzel:
                w = float(a.text or 0) * (1 if gutschrift else -1)
                summe += w
                konto.buchungen.append((tag, round(w, 2), _tx_text(ntry, tx, gutschrift)))
            if abs(summe - betrag) > 0.01:                 # Einzelbeträge passen nicht: Rest als eigene Buchung
                konto.buchungen.append((tag, round(betrag - summe, 2), _tx_text(ntry, None, gutschrift)))
        else:
            konto.buchungen.append((tag, round(betrag, 2), _tx_text(ntry, txs[0] if txs else None, gutschrift)))


def lesen(inhalt: bytes) -> list[Konto]:
    """Alle Konten der Datei (bzw. des ZIP), Buchungen chronologisch; doppelte Tagesauszüge zählen einmal."""
    konten: dict[str, Konto] = {}
    gesehen: set[str] = set()
    for xml in _xml_dateien(inhalt):
        try:
            wurzel = ET.fromstring(xml)
        except ET.ParseError as e:
            raise ValueError(f"camt-Datei nicht lesbar: {e}") from e
        for bericht in wurzel.iter():
            if _name(bericht) not in ("Stmt", "Rpt", "Ntfctn"):
                continue
            kennung = _text(bericht, "Id") + "|" + _text(bericht, "ElctrncSeqNb")
            if kennung.strip("|") and kennung in gesehen:
                continue
            gesehen.add(kennung)
            acct = _kind(bericht, "Acct")
            schl = _text(acct, "Id", "IBAN") or _text(acct, "Id", "Othr", "Id") or "?"
            _auszug(bericht, konten.setdefault(schl, Konto()))
    if not konten:
        raise ValueError("Keine Kontoauszüge (camt.052/053/054) in der Datei gefunden.")
    for k in konten.values():
        k.buchungen.sort(key=lambda b: b[0])
    return list(konten.values())


def monatssaldi(konto: Konto) -> dict[str, tuple[str, float]]:
    """Saldo am Monatsende: aus dem jüngsten Schlusssaldo über die Buchungen zurückgerechnet, bekannte Saldi gehen vor."""
    erg: dict[str, tuple[str, float]] = {}
    if konto.schlusssaldi:
        stichtag = max(konto.schlusssaldi)
        saldo = konto.schlusssaldi[stichtag]
        erg[stichtag[:7]] = (stichtag, saldo)
        for tag, betrag, _ in reversed([b for b in konto.buchungen if b[0] <= stichtag]):
            erg.setdefault(tag[:7], (tag, round(saldo, 2)))
            saldo -= betrag
        for tag, s in sorted(konto.schlusssaldi.items()):
            if tag >= erg.get(tag[:7], ("", 0))[0]:
                erg[tag[:7]] = (tag, s)
    return dict(sorted(erg.items()))
