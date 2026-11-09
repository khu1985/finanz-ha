"""Steuererklärung vorbereiten: Checkliste pro Steuerjahr aus den Daten der App.

Für das Steuerjahr J (eingereicht im Jahr J+1) entsteht eine Liste mit Belegen und Werten:
- Formales: Frist des Wohnkantons, Quellensteuer (nachträgliche ordentliche Veranlagung), Kinder per 31.12.
- Einkommen: Lohnausweise, Renten, Wertschriftenerträge (Steuerauszug)
- Abzüge: Säule 3a, PK-Einkäufe im Jahr, Kinderbetreuung, Krankheitskosten, Prämien, Spenden (aus dem Budget),
  Berufskosten
- Liegenschaft: Eigenmietwert, Schuldzinsen (Hypothek bzw. Budget), Unterhalt
- Vermögen per 31.12.: Saldi aller Konten (fehlende Saldi werden markiert), Krypto, Lebensversicherungen, Schulden
- Vorjahr: Werte aus der letzten Veranlagung zum Abgleich
Abgehakte Punkte werden pro Jahr gespeichert (Tabelle steuererklaerung_erledigt).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

GRUPPEN = ["Formales", "Einkommen", "Abzüge", "Liegenschaft", "Vermögen per 31.12.", "Vorjahr"]


@dataclass
class Punkt:
    schluessel: str
    gruppe: str
    titel: str
    beleg: str = ""                  # was bereitzulegen ist
    wert: str = ""                   # Wert aus der App (Text)
    status: str = "beleg"            # daten (Wert vorhanden), fehlt (Wert erwartet, fehlt), beleg, info
    erledigt: bool = False


@dataclass
class Checkliste:
    jahr: int
    frist: date
    punkte: list[Punkt] = field(default_factory=list)

    @property
    def offen(self) -> int:
        return sum(1 for p in self.punkte if not p.erledigt and p.status != "info")

    @property
    def total(self) -> int:
        return sum(1 for p in self.punkte if p.status != "info")


def _tabelle(db) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS steuererklaerung_erledigt (jahr INTEGER NOT NULL, schluessel TEXT NOT NULL, "
               "PRIMARY KEY (jahr, schluessel))")


def erledigt_setzen(db, jahr: int, schluessel: list[str], alle: list[str]) -> None:
    _tabelle(db)
    for s in alle:
        if s in schluessel:
            db.execute("INSERT OR IGNORE INTO steuererklaerung_erledigt (jahr, schluessel) VALUES (?, ?)", (jahr, s))
        else:
            db.execute("DELETE FROM steuererklaerung_erledigt WHERE jahr = ? AND schluessel = ?", (jahr, s))


def _erledigt(db, jahr: int) -> set[str]:
    _tabelle(db)
    return {r[0] for r in db.execute("SELECT schluessel FROM steuererklaerung_erledigt WHERE jahr = ?", (jahr,))}


def standard_jahr(heute: date) -> int:
    """Ab Oktober wird das laufende Jahr vorbereitet, sonst das Vorjahr."""
    return heute.year if heute.month >= 10 else heute.year - 1


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")


def _zahl(v) -> float:
    try:
        return float(str(v or 0).replace("'", ""))
    except ValueError:
        return 0.0


def _saldo_per(db, konto_id: int, stichtag: date) -> tuple[str, float] | None:
    r = db.execute("SELECT datum, betrag FROM saldi WHERE konto_id = ? AND datum <= ? ORDER BY datum DESC LIMIT 1",
                   (konto_id, stichtag.isoformat())).fetchone()
    nach = db.execute("SELECT datum, betrag FROM saldi WHERE konto_id = ? AND datum > ? ORDER BY datum LIMIT 1",
                      (konto_id, stichtag.isoformat())).fetchone()
    kandidaten = [x for x in (r, nach) if x]
    if not kandidaten:
        return None
    best = min(kandidaten, key=lambda x: abs((date.fromisoformat(x[0][:10]) - stichtag).days))
    return best[0][:10], float(best[1])


def _budget_summe(db, jahr: int, kategorie: str, stichwort: str | None = None) -> float | None:
    try:
        import budget as bu
        bu._tabelle(db)
    except Exception:  # noqa: BLE001
        return None
    sql = "SELECT COUNT(*), COALESCE(SUM(betrag), 0) FROM buchungen WHERE datum BETWEEN ? AND ? AND kategorie = ?"
    args = [f"{jahr}-01-01", f"{jahr}-12-31", kategorie]
    if stichwort:
        sql += " AND lower(text) LIKE ?"
        args.append(f"%{stichwort}%")
    n, s = db.execute(sql, args).fetchone()
    return -float(s) if n else None


def erstellen(k: dict, db, jahr: int | None = None, heute: date | None = None) -> Checkliste:
    import kantone
    import kinder as ki
    import vermoegen as vm
    import vorsorge as vs
    import zuzug as zz

    heute = heute or date.today()
    jahr = jahr or standard_jahr(heute)
    stichtag = date(jahr, 12, 31)
    f = kantone.steuererklaerung(k)
    mm, tt = (int(x) for x in f.gewaehlt.split("-"))
    frist = date(jahr + 1, mm, min(tt, 28) if mm == 2 else tt)
    pkt: list[Punkt] = []
    personen = k["personen"]
    verheiratet = k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet"

    # Formales
    pkt.append(Punkt("frist", "Formales", f"Frist {f.name or 'Kanton'}: {frist:%d.%m.%Y}",
                     wert=("erstreckt" if f.quelle == "erstreckt" else "") + (f" – {f.hinweis}" if f.hinweis else ""),
                     status="info"))
    if not verheiratet and len(personen) > 1:
        pkt.append(Punkt("zwei_erklaerungen", "Formales", "Konkubinat: zwei Steuererklärungen",
                         "Kinderabzug, Elterntarif und Betreuungskosten zwischen beiden Erklärungen abstimmen", status="beleg"))
    for p in personen:
        if zz.quellensteuer(p, k):
            pkt.append(Punkt(f"nov_{p['name']}", "Formales", f"{p['name']}: Quellensteuer – ordentliche Veranlagung",
                             "Antrag bis 31. März bzw. Steuererklärung bei obligatorischer Veranlagung",
                             "beantragt" if zz.cfg(p)["nov_beantragt"] else "noch nicht beantragt",
                             "daten" if zz.cfg(p)["nov_beantragt"] else "fehlt"))
    for c in ki.liste(k):
        a = ki.alter(c, jahr)
        if a < 0:
            continue
        if ki.unterhalt(c, jahr):
            beleg = "Ausbildungsbestätigung (Schule, Lehrvertrag, Immatrikulation)" if a >= 18 else ""
            pkt.append(Punkt(f"kind_{c['name']}", "Formales", f"Kind {c['name']} ({a} Jahre per 31.12.)", beleg,
                             f"Kinderabzug; im Konkubinat bei {ki.obhut(k, c)}" if not verheiratet and len(personen) > 1
                             else "Kinderabzug", "daten" if not beleg else "beleg"))

    # Einkommen
    for p in personen:
        n = p["name"]
        if vs.pensionsjahr(p) <= jahr:
            pkt.append(Punkt(f"renten_{n}", "Einkommen", f"{n}: Rentenbescheinigungen AHV und Pensionskasse",
                             "Rentenbescheinigungen der Ausgleichskasse und der Pensionskasse"))
        elif _zahl(p.get("lohn_brutto")):
            pkt.append(Punkt(f"lohnausweis_{n}", "Einkommen", f"{n}: Lohnausweis",
                             "Lohnausweis des Arbeitgebers (auch Nebenerwerb, Taggelder)",
                             f"Bruttolohn laut App CHF {_chf(_zahl(p['lohn_brutto']))}", "beleg"))
    konten = vm.konten(db)
    if any(x["art"] in ("depot", "bank") for x in konten):
        pkt.append(Punkt("steuerauszug", "Einkommen", "Zins- und Wertschriftenerträge",
                         "Steuerauszug bzw. Zinsausweise der Banken (Verrechnungssteuer zurückfordern)"))

    # Abzüge
    for p in personen:
        n = p["name"]
        if vs.pensionsjahr(p) <= jahr:
            continue
        b3a = _zahl((p.get("saeule3a") or {}).get("beitrag_jahr"))
        pkt.append(Punkt(f"3a_{n}", "Abzüge", f"{n}: Säule 3a", "Bescheinigung der Vorsorgestiftung(en)",
                         f"geplant CHF {_chf(b3a)} (Maximum {_chf(_zahl(k['kennzahlen'].get('saeule3a_max', 7258)))})"
                         if b3a else "kein Beitrag erfasst", "daten" if b3a else "fehlt"))
        einkauf = sum(_zahl(e.get("betrag")) for e in p["pk"].get("einkauf_geplant") or [] if int(e.get("jahr", 0)) == jahr)
        if einkauf:
            pkt.append(Punkt(f"pk_{n}", "Abzüge", f"{n}: Einkauf Pensionskasse {jahr}", "Einkaufsbestätigung der Kasse",
                             f"geplant CHF {_chf(einkauf)}", "daten"))
    bet = sum(min(_zahl(k["kennzahlen"].get("bund_betreuung_max", 25800)), ki.betreuung_jahr(c, jahr))
              for c in ki.liste(k) if ki.alter(c, jahr) < int(_zahl(k["kennzahlen"].get("bund_betreuung_alter", 14))))
    if bet:
        pkt.append(Punkt("betreuung", "Abzüge", "Kinderbetreuung durch Dritte", "Rechnungen Kita, Tagesstruktur, Tagesfamilie",
                         f"laut Kinder-Seite CHF {_chf(bet)}", "daten"))
    try:
        import krankenkasse as kk
        import versicherungen as vi
        vi.tabellen(db)
        kkp = kk.personen(k, vi.alle(db))
        praemien = sum(x.praemie_monat * 12 for x in kkp)
        kosten = sum(x.kosten_jahr for x in kkp)
    except Exception:  # noqa: BLE001
        praemien, kosten = 0.0, 0.0
    pkt.append(Punkt("praemien", "Abzüge", "Versicherungsprämien", "Prämienübersicht der Krankenkasse (oft Pauschale)",
                     f"Grundversicherung rund CHF {_chf(praemien)}" if praemien else "", "daten" if praemien else "beleg"))
    pkt.append(Punkt("krankheit", "Abzüge", "Krankheits- und Zahnarztkosten",
                     "Leistungsabrechnungen (Franchise, Selbstbehalt), Zahnarzt, Brille – abziehbar über 5 % des Nettoeinkommens",
                     f"erwartete Kosten CHF {_chf(kosten)}" if kosten else "", "daten" if kosten else "beleg"))
    spenden = _budget_summe(db, jahr, "Spenden")
    pkt.append(Punkt("spenden", "Abzüge", "Spenden", "Spendenbescheinigungen (ab CHF 100 an steuerbefreite Organisationen)",
                     f"laut Budget CHF {_chf(spenden)}" if spenden else "", "daten" if spenden else "beleg"))
    pkt.append(Punkt("beruf", "Abzüge", "Berufskosten", "Arbeitsweg (Abo, Kilometer), auswärtige Verpflegung, "
                     "Weiterbildung – sonst Pauschale", status="beleg"))

    # Liegenschaft
    w = k.get("wohnen") or {}
    if w.get("aktiv"):
        emw = _zahl(w.get("eigenmietwert"))
        pkt.append(Punkt("eigenmietwert", "Liegenschaft", "Eigenmietwert und Vermögenssteuerwert",
                         "Letzte Veranlagung bzw. Schätzung der Liegenschaft", f"CHF {_chf(emw)}" if emw else "",
                         "daten" if emw else "fehlt"))
        zinsen_budget = _budget_summe(db, jahr, "Wohnen", "hypothek")
        hyp = sum(-x["wert"] for x in konten if x["art"] == "hypothek")
        geschaetzt = hyp * _zahl(w.get("hypothek_zins")) / 100 if hyp else 0
        wert = (f"laut Budget CHF {_chf(zinsen_budget)}" if zinsen_budget else
                f"geschätzt CHF {_chf(geschaetzt)} ({_zahl(w.get('hypothek_zins')):g} % auf {_chf(hyp)})" if geschaetzt else "")
        pkt.append(Punkt("schuldzinsen", "Liegenschaft", "Hypothekarzinsen", "Zinsausweis der Bank per 31.12.", wert,
                         "daten" if wert else "beleg"))
        pkt.append(Punkt("unterhalt", "Liegenschaft", "Unterhaltskosten",
                         "Rechnungen für Reparaturen und Unterhalt; effektiv abziehen, wenn höher als die Pauschale "
                         "(meist 10 % bzw. 20 % des Eigenmietwerts)", status="beleg"))

    # Vermögen per 31.12.
    for x in konten:
        s = _saldo_per(db, x["id"], stichtag)
        beleg = {"bank": "Saldo- bzw. Zinsausweis", "depot": "Steuerauszug (Kurswerte 31.12.)",
                 "krypto": "Bestand und Kurswert per 31.12. (Kursliste ESTV)", "hypothek": "Zinsausweis mit Schuld per 31.12.",
                 "kredit": "Schuldbestätigung", "immobilie": "Steuerwert laut Veranlagung",
                 "vorsorge": "Rückkaufswert per 31.12. (3b) – Konten der Säule 3a nicht deklarieren"}.get(x["art"], "Nachweis per 31.12.")
        if s and abs((date.fromisoformat(s[0]) - stichtag).days) <= 31:
            wert, status = f"CHF {_chf(abs(s[1]))} am {date.fromisoformat(s[0]):%d.%m.%Y}", "daten"
        elif stichtag >= heute:
            wert, status = "Saldo per 31.12. nach Jahresende erfassen", "beleg"
        else:
            wert, status = "Saldo per 31.12. fehlt in der App", "fehlt"
        pkt.append(Punkt(f"konto_{x['id']}", "Vermögen per 31.12.", f"{x['name']} ({vm.ARTEN.get(x['art'], x['art'])})",
                         beleg, wert, status))
    try:
        import versicherungen as vi
        for v in vi.alle(db):
            if v["sparte"] == "leben_3b":
                pkt.append(Punkt(f"police_{v['id']}", "Vermögen per 31.12.", f"Lebensversicherung {v['versicherer']} {v['police']}".strip(),
                                 "Rückkaufswert per 31.12. (Bescheinigung der Versicherung)"))
    except Exception:  # noqa: BLE001
        pass
    pkt.append(Punkt("vorsorge_info", "Vermögen per 31.12.", "Säule 3a, Pensionskasse und Freizügigkeit",
                     wert="nicht als Vermögen deklarieren (steuerfrei bis zum Bezug)", status="info"))

    # Vorjahr
    try:
        import steuerdokumente as sd
        sd.tabellen(db)
        vj = {key: d for key, d in sd.massgebend(sd.alle(db)).items() if key[1] == jahr - 1}
    except Exception:  # noqa: BLE001
        vj = {}
    if vj:
        for (person, _), d in vj.items():
            werte = d["werte"]
            teile = [f"{lbl} {_chf(_zahl(werte[s]))}" for s, lbl in (("steuerbar_kanton", "steuerbar Kanton"),
                     ("abzug_3a", "3a"), ("schuldzinsen", "Schuldzinsen"), ("unterhalt_liegenschaft", "Unterhalt"),
                     ("kinderbetreuung", "Betreuung")) if werte.get(s)]
            pkt.append(Punkt(f"vorjahr_{person}", "Vorjahr", f"{person}: {jahr - 1} ({d['typ']})", wert=", ".join(teile),
                             status="info"))
    else:
        pkt.append(Punkt("vorjahr", "Vorjahr", f"Veranlagung {jahr - 1}",
                         "Unter «Steuern» hochladen – dann erscheinen die Vorjahreswerte zum Abgleich", status="info"))
    erledigt = _erledigt(db, jahr)
    for p_ in pkt:
        p_.erledigt = p_.schluessel in erledigt
    return Checkliste(jahr, frist, pkt)


def offene_fehlende(c: Checkliste) -> list[Punkt]:
    return [p for p in c.punkte if p.status == "fehlt" and not p.erledigt]


def sichtbar(heute: date, frist: date) -> bool:
    return frist - timedelta(days=150) <= heute <= frist
