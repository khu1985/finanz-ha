"""Ampeln: grün / gelb / rot (grau = keine Daten) für alle Bereiche der Finanzplanung."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

GRUEN, GELB, ROT, GRAU = "gruen", "gelb", "rot", "grau"
RANG = {ROT: 3, GELB: 2, GRUEN: 1, GRAU: 0}
TEXT = {GRUEN: "in Ordnung", GELB: "prüfen", ROT: "handeln", GRAU: "keine Daten"}


@dataclass
class Ampel:
    bereich: str
    status: str
    text: str
    seite: str     # Pfad der Seite mit den Details


def schlechteste(stati) -> str:
    stati = [s for s in stati if s]
    return max(stati, key=lambda s: RANG[s]) if stati else GRAU


def schwelle(wert: float, gut: float, mittel: float, hoeher_besser: bool = True) -> str:
    if hoeher_besser:
        return GRUEN if wert >= gut else GELB if wert >= mittel else ROT
    return GRUEN if wert <= gut else GELB if wert <= mittel else ROT


def chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")


# ---------------------------------------------------------------- Einzelbewertungen

def deckung_status(status: str) -> str:
    return {"ok": GRUEN, "pruefen": GELB, "fehlt": ROT, "info": GRAU}.get(status, GRAU)


def termin_status(tage: int) -> str:
    return ROT if tage <= 14 else GELB if tage <= 45 else GRUEN


def iv_status(quote: float) -> str:
    return schwelle(quote, 70, 55)


def tod_status(kapital: float, richtwert: float) -> str:
    if not richtwert:
        return GRUEN if kapital else GRAU
    return schwelle(kapital / richtwert, 1.0, 0.5)


def tragbarkeit_status(quote: float, maximum: float) -> str:
    return schwelle(quote, maximum, maximum + 5, hoeher_besser=False)


def amortisation_status(verfuegbar: float, ziel: float) -> str:
    if not ziel:
        return GRAU
    return schwelle(verfuegbar / ziel, 1.0, 0.8)


def luecke_status(luecke: float, bedarf: float) -> str:
    if not bedarf:
        return GRAU
    return GRUEN if luecke <= 0 else GELB if luecke <= bedarf * 0.1 else ROT


# ---------------------------------------------------------------- Gesamtbewertung

def bewerten(k: dict, db, heute: date | None = None) -> list[Ampel]:
    import berater as br
    import konfig
    import steuerdokumente as sd
    import steuern as st
    import vermoegen as vm
    import versicherungen as vi
    import vorsorge as vs
    import wohnen as wo

    heute = heute or date.today()
    erg: list[Ampel] = []
    nv = vm.nettovermoegen(db)

    # Vorsorge: Pensionslücke
    l = vs.pensionsluecke(k, nv["frei"], heute.year)
    s = luecke_status(l.luecke, l.bedarf)
    erg.append(Ampel("Ruhestand", s, "keine Pensionslücke" if s == GRUEN else f"Lücke CHF {chf(l.luecke)}/Jahr ab {l.jahr}",
                     "vorsorge"))

    # Liquidität / Notreserve
    konten = vm.konten(db)
    bank = sum(x["wert"] for x in konten if x["art"] == "bank")
    reserve = float(k["wohnen"].get("reserve", 0) or 0) or 30000
    if konten:
        s = schwelle(bank, reserve, reserve * 0.5)
        erg.append(Ampel("Liquidität", s, f"Konten CHF {chf(bank)} (Reserve {chf(reserve)})", "vermoegen"))
    else:
        erg.append(Ampel("Liquidität", GRAU, "keine Saldi erfasst", "vermoegen"))

    # Wohnen: Tragbarkeit und Amortisation
    if k["wohnen"].get("aktiv"):
        t = wo.tragbarkeit(k, heute.year)
        s = tragbarkeit_status(t["quote"], k["kennzahlen"]["tragbarkeit_max"])
        erg.append(Ampel("Tragbarkeit", s, f"{t['quote']:.1f} % des Einkommens, Belehnung {t['belehnung']:.0f} %", "wohnen"))
        a = br.amortisation(k, db, heute)
        if a:
            s = amortisation_status(a.verfuegbar, a.ziel)
            erg.append(Ampel("Amortisation", s, f"CHF {chf(a.verfuegbar)} verfügbar bis {a.faellig.strftime('%m.%Y')} "
                                                f"(Ziel {chf(a.ziel)})", "wohnen"))

    # Steuern: 3a und PK-Einkauf
    kz = k["kennzahlen"]
    offen = [p["name"] for p in k["personen"]
             if float(p.get("lohn_brutto", 0)) > 0 and float(p["saeule3a"].get("beitrag_jahr", 0)) < kz["saeule3a_max"] - 50]
    grenz = st.steuern_heute(k)["grenz_total"]
    einkauf = [p["name"] for p in k["personen"] if float(p["pk"].get("einkauf_potenzial", 0) or 0) > 20000
               and not p["pk"].get("einkauf_geplant")]
    if offen:
        erg.append(Ampel("Steuern", GELB, "3a nicht ausgeschöpft: " + ", ".join(offen), "steuern"))
    elif einkauf and grenz >= 30:
        erg.append(Ampel("Steuern", GELB, f"PK-Einkauf prüfen (Grenzsteuersatz {grenz:.0f} %): " + ", ".join(einkauf), "steuern"))
    else:
        erg.append(Ampel("Steuern", GRUEN, "3a ausgeschöpft", "steuern"))
    doks = sd.alle(db)
    if doks:
        letzte = max((d["jahr"] for d in doks if d["typ"] == "veranlagung"), default=0)
        abgl = sd.abgleich(doks)
        s = GELB if abgl or letzte < heute.year - 2 else GRUEN
        text = (f"{len(abgl)} Korrektur(en) der Veranlagung" if abgl else
                f"letzte Veranlagung {letzte}" if letzte else "noch keine Veranlagung")
        erg.append(Ampel("Steuerdokumente", s, text, "steuern"))

    # Versicherungen
    vertraege = vi.alle(db)
    if vertraege:
        check = vi.deckungscheck(k, vertraege)
        fehlt = [t for st_, t, _ in check if st_ == "fehlt"]
        pruefen = [t for st_, t, _ in check if st_ == "pruefen"]
        s = ROT if fehlt else GELB if pruefen else GRUEN
        text = ("fehlt: " + ", ".join(sorted(set(fehlt)))) if fehlt else \
               ("prüfen: " + ", ".join(sorted(set(pruefen)))) if pruefen else "Grunddeckung vollständig"
        erg.append(Ampel("Versicherungsschutz", s, text, "versicherungen"))
        termine = vi.kuendigungstermine(vertraege, heute)
        if termine:
            t = termine[0]
            tage = (t.kuendigen_bis - heute).days
            erg.append(Ampel("Kündigungsfristen", termin_status(tage),
                             f"nächste bis {t.kuendigen_bis.strftime('%d.%m.%Y')} ({tage} Tage)", "versicherungen"))
    else:
        erg.append(Ampel("Versicherungsschutz", GRAU, "keine Verträge erfasst", "versicherungen"))

    # Risiko Invalidität und Tod
    rs = vi.risiko(k, vs.ahv(k, heute.year))
    if any(r.iv_pk or r.iv_extern for r in rs):
        s = schlechteste(iv_status(r.iv_quote) for r in rs if r.lohn)
        erg.append(Ampel("Invalidität", s, ", ".join(f"{r.name} {r.iv_quote:.0f} %" for r in rs if r.lohn) + " des Lohns",
                         "versicherungen"))
    else:
        erg.append(Ampel("Invalidität", GRAU, "PK-Leistungen fehlen – Vorsorgeausweis hochladen", "vorsorge"))
    if any(r.tod_kapital or r.tod_renten for r in rs):
        stati = [tod_status(r.tod_kapital, r.tod_bedarf_kapital) for r in rs]
        if k["haushalt"].get("zivilstand") != "verheiratet" and any(
                float(p["risiko"].get("partnerrente_pk", 0)) and not p["risiko"].get("partner_bei_pk_gemeldet")
                for p in k["personen"]):
            stati.append(GELB)
        erg.append(Ampel("Todesfall", schlechteste(stati),
                         ", ".join(f"{r.name} CHF {chf(r.tod_kapital)}" for r in rs) + " Kapital", "versicherungen"))

    # Krankenkasse
    import krankenkasse as kk
    ergebnisse = kk.haushalt(k, vi.alle(db))
    if ergebnisse:
        spar = sum(e.ersparnis for e in ergebnisse)
        erg.append(Ampel("Krankenkasse", GELB if spar >= 200 else GRUEN,
                         f"Franchise-Optimierung spart rund CHF {chf(spar)}/Jahr" if spar >= 200 else "Franchisen passen",
                         "versicherungen"))

    # Anlage
    import anlage as an
    c = an.pruefen(k, db, heute)
    if c.finanz_total:
        brach = max(0, c.anlegbar - c.depot)
        erg.append(Ampel("Anlage", GELB if brach > 20000 or c.krypto_anteil > float(an.konfiguration(k)["krypto_max"]) else GRUEN,
                         f"CHF {chf(brach)} ohne Zweck auf Konten" if brach > 20000 else "Aufteilung passt", "vermoegen"))

    # Erinnerungen
    import erinnerungen as er
    offen = er.alle(k, db, heute)
    if offen:
        dringend = [e for e in offen if e.tage(heute) <= 7]
        s = ROT if dringend else GELB if any(e.tage(heute) <= 30 for e in offen) else GRUEN
        erg.append(Ampel("Erinnerungen", s, f"{len(offen)} anstehend" + (f", {len(dringend)} dringend" if dringend else "")
                         + f" – nächste: {offen[0].titel}", ""))

    # Daten
    letzter = db.execute("SELECT MAX(datum) FROM saldi").fetchone()[0]
    todo = konfig.konfig_pfad().read_text(encoding="utf-8").count("TODO") if konfig.konfig_pfad().exists() else 0
    if letzter:
        alter = (heute - date.fromisoformat(letzter)).days
        s = schlechteste([schwelle(alter, 45, 120, hoeher_besser=False), GELB if todo else GRUEN])
        erg.append(Ampel("Daten", s, f"Saldi {alter} Tage alt" + (f", {todo} TODO offen" if todo else ""), "einstellungen"))
    else:
        erg.append(Ampel("Daten", GELB if todo else GRAU, f"{todo} TODO offen" if todo else "noch keine Saldi", "einstellungen"))
    return erg


def pro_seite(ampeln: list[Ampel]) -> dict[str, str]:
    """Schlechteste Ampel pro Seite (für die Navigation); die Übersicht fasst alles zusammen."""
    seiten: dict[str, list[str]] = {}
    for a in ampeln:
        seiten.setdefault(a.seite, []).append(a.status)
    erg = {s: schlechteste(v) for s, v in seiten.items()}
    erg[""] = schlechteste(a.status for a in ampeln)
    return erg
