"""Widersprüche: dieselbe Grösse an zwei Stellen mit verschiedenen Werten.

Geprüft wird, wo die App dieselbe Information doppelt kennt:
- Einstellungen gegenüber dem neuesten Dokument (Vorsorgeausweis, 3a-Auszug, IK-Auszug, Veranlagung bzw.
  Steuererklärung) – ausser der Wert wurde danach bewusst von Hand geändert.
- Hypothek unter Wohnen (Kaufpreis − Eigenmittel) gegenüber den Hypothek-Konten unter Vermögen.
- Lohn in den Einstellungen gegenüber den Lohneingängen der Buchungen (ab 6 Monaten).
- Steuerbares Einkommen gegenüber dem Lohn (grob: 45–110 % des Bruttolohns).
- Freies Vermögen der Übersicht gegenüber der Summe «Vermögen pro Person».
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

from dataclasses import dataclass
from datetime import date


def _chf(v: float) -> str:
    return f"{v:,.0f}" >> TS


@dataclass
class Befund:
    thema: str
    a: str                  # «Einstellungen: 23'681»
    b: str                  # «Vorsorgeausweis ASGA 01.01.2026: 96'416»
    erklaerung: str
    seite: str
    gewicht: int = 2        # 3 = falsche Zahlen wahrscheinlich


def _nah(a: float, b: float, toleranz: float = 0.01) -> bool:
    return abs(a - b) <= max(1.0, abs(b) * toleranz)


def _hand_danach(info, datum: str) -> bool:
    """Wert nach dem Dokument bewusst von Hand gesetzt oder bestätigt → kein Widerspruch."""
    if not info or not datum:
        return False
    return bool((info.quelle == "von Hand" and info.datum and info.datum >= datum[:10])
                or (info.bestaetigt and info.bestaetigt >= datum[:10]))


def dokumente(k: dict, db, infos: dict) -> list[Befund]:
    import dokumente as dk
    from versicherungen import gleiche_person
    erg = []
    neueste: dict[tuple[str, str], dict] = {}
    for d in dk.alle(db):
        if not d.get("person") or d["typ"] not in dk.WERTE_JE_TYP:
            continue
        schl = (d["person"], d["typ"])
        alt = neueste.get(schl)
        if not alt or (d.get("stichtag") or d["hochgeladen"]) > (alt.get("stichtag") or alt["hochgeladen"]):
            neueste[schl] = d
    for (person, typ), d in neueste.items():
        i = next((i for i, p in enumerate(k["personen"]) if gleiche_person(p["name"], person)), None)
        if i is None:
            continue
        p = k["personen"][i]
        for s, w in (d.get("werte") or {}).items():
            ziel = dk.ZIELE.get(s, ("", ""))[1]
            if not ziel or ziel == "vermoegen" or w in (None, ""):
                continue
            obj = p
            for teil in ziel.split("."):
                obj = obj.get(teil) if isinstance(obj, dict) else None
            try:
                ist, soll = float(obj or 0), float(w)
            except (TypeError, ValueError):
                continue
            if _nah(ist, soll):
                continue
            pfad = f"personen.{i}.{ziel}"
            if _hand_danach(infos.get(pfad), d.get("uebernommen") or d["hochgeladen"]):
                continue
            stand = d.get("stichtag") or d["hochgeladen"][:10]
            name = f"{dk.TYPEN.get(typ, 'Dokument')}{' ' + d['anbieter'] if d.get('anbieter') else ''} ({stand})"
            erg.append(Befund(f"{p['name']}: {dk.ZIELE[s][0]}", f"Einstellungen: {_chf(ist)}", f"{name}: {_chf(soll)}",
                              "Der neueste Ausweis zeigt einen anderen Wert. Stimmt der Ausweis, ihn auf der Dokumentseite "
                              "übernehmen; stimmt die Einstellung (z. B. falsch erkannt), sie hier bestätigen.",
                              f"vorsorge/dokument/{d['id']}", 3 if s.startswith(("iv_", "partner", "waisen", "todes",
                                                                                   "altersguthaben")) else 2))
    return erg


def steuern(k: dict, db, infos: dict) -> list[Befund]:
    """Pro Steuereinheit (Haushalt bzw. Person im Konkubinat) gegenüber dem neuesten Steuerdokument."""
    import steuerdokumente as sd
    from versicherungen import gleiche_person
    alle_docs = [d for d in sd.alle(db) if d["typ"] in ("veranlagung", "erklaerung") and d.get("jahr")]
    if not alle_docs:
        return []
    st = k.get("steuern") or {}
    if k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet" or not st.get("personen"):
        einheiten = [(st, "steuern", "", alle_docs)]
    else:
        einheiten = [(e, f"steuern.personen.{j}", str(e.get("person") or ""),
                      [d for d in alle_docs if d.get("person") and gleiche_person(d["person"], str(e.get("person") or ""))])
                     for j, e in enumerate(st["personen"])]
    erg = []
    for einheit, praefix, person, docs in einheiten:
        if not docs:
            continue
        d = max(docs, key=lambda x: (x["jahr"], x["typ"] == "veranlagung", x["hochgeladen"]))
        w_ = d.get("werte") or {}
        getrennt = bool(w_.get("staatssteuer") and w_.get("gemeindesteuer"))
        felder = ["steuerbar_kanton", "steuerbar_bund"] + (["staatssteuer", "gemeindesteuer"] if getrennt
                                                           else ["steuer_kanton_gemeinde"])
        for s_ in felder:
            w = w_.get(s_)
            if not w:
                continue
            ist = float(einheit.get(s_) or 0)
            if _nah(ist, float(w), 0.02) or _hand_danach(infos.get(f"{praefix}.{s_}"), d.get("uebernommen") or d["hochgeladen"]):
                continue
            erg.append(Befund(f"Steuern{' ' + person if person else ''}: {sd.FELDER.get(s_, (s_,))[0]}",
                              f"Einstellungen: {_chf(ist)}",
                              f"{'Veranlagung' if d['typ'] == 'veranlagung' else 'Steuererklärung'} {d['jahr']}: "
                              f"{_chf(float(w))}",
                              "Die Steuern der App rechnen mit den Einstellungen. Den Wert aus dem neuesten Steuerdokument "
                              "übernehmen oder die Einstellung bestätigen.", f"steuern/dokument/{d['id']}"))
    return erg


def hypothek(k: dict, db) -> list[Befund]:
    import vermoegen as vm
    w = k.get("wohnen") or {}
    if not w.get("aktiv"):
        return []
    konten = [x for x in vm.konten(db) if x["art"] == "hypothek" and not x.get("aufgeloest")]
    if not konten:
        return []
    auf_konten = -sum(x["wert"] for x in konten)
    wohnen = max(0.0, float(w.get("kaufpreis") or 0) - float(w.get("eigenmittel") or 0))
    if _nah(auf_konten, wohnen, 0.1):
        return []
    return [Befund("Hypothek", f"Wohnen (Kaufpreis − Eigenmittel): {_chf(wohnen)}", f"Konten unter Vermögen: {_chf(auf_konten)}",
                   "Tragbarkeit und Amortisation rechnen mit Kaufpreis − Eigenmittel, das Vermögen mit den Konten. Nach "
                   "einer Amortisation die Eigenmittel unter Wohnen anpassen.", "wohnen")]


def lohn(k: dict, db) -> list[Befund]:
    import budget as bu
    a = bu.auswerten(k, db)
    if not a or a.monate < 6:
        return []
    eingang = sum(b["betrag"] for b in bu.alle(db) if b.get("kategorie") == bu.LOHN and b["betrag"] > 0
                  and b["datum"] >= a.von) / a.monate * 12
    brutto = sum(float(p.get("lohn_brutto") or 0) for p in k["personen"])
    if not eingang or not brutto:
        return []
    quote = eingang / brutto
    if 0.7 <= quote <= 0.95:
        return []
    return [Befund("Lohn", f"Einstellungen: {_chf(brutto)} brutto pro Jahr",
                   f"Lohneingänge der Buchungen: {_chf(eingang)} pro Jahr ({quote * 100:.0f} % davon)",
                   "Netto kommen meist 75–90 % des Bruttolohns an. Lohn in den Einstellungen oder die Kategorie «Lohn» "
                   "der Buchungen prüfen (13. Monatslohn, Bonus, Lohn auf ein nicht importiertes Konto).", "budget")]


def steuerbar(k: dict) -> list[Befund]:
    brutto = sum(float(p.get("lohn_brutto") or 0) for p in k["personen"])
    st = k.get("steuern") or {}
    if k["haushalt"].get("zivilstand", "verheiratet") != "verheiratet" and st.get("personen"):
        s = sum(float(e.get("steuerbar_kanton") or 0) for e in st["personen"])
    else:
        s = float(st.get("steuerbar_kanton") or 0)
    if not brutto or not s or 0.45 <= s / brutto <= 1.1:
        return []
    return [Befund("Steuerbares Einkommen", f"Steuerbar Kanton: {_chf(s)}", f"Bruttolohn total: {_chf(brutto)}",
                   "Das steuerbare Einkommen liegt meist bei 55–90 % des Bruttolohns. Stammt es aus einem anderen Jahr "
                   "oder hat sich der Lohn stark verändert, rechnet «Steuern heute» mit veralteten Werten.", "steuern")]


def vermoegen(k: dict, db) -> list[Befund]:
    import vermoegen as vm
    nv = vm.nettovermoegen(db)
    ks = [x for x in vm.konten(db) if not x.get("aufgeloest")]
    summe = sum(x["wert"] for x in ks)
    if _nah(summe, nv["total"], 0.001):
        return []
    return [Befund("Nettovermögen", f"Übersicht: {_chf(nv['total'])}", f"Summe aller Konten: {_chf(summe)}",
                   "Interner Widerspruch der App – bitte melden.", "vermoegen", 3)]


def pruefen(k: dict, db) -> list[Befund]:
    import herkunft
    import logging
    infos = herkunft.alle(db, k)
    erg: list[Befund] = []
    for f in (lambda: dokumente(k, db, infos), lambda: steuern(k, db, infos), lambda: hypothek(k, db),
              lambda: lohn(k, db), lambda: steuerbar(k), lambda: vermoegen(k, db)):
        try:
            erg += f()
        except Exception as e:  # noqa: BLE001 – eine fehlende Quelle soll die übrigen Prüfungen nicht verhindern
            logging.getLogger("finanz").debug("Konsistenz: %s", e)
    return sorted(erg, key=lambda b: -b.gewicht)
