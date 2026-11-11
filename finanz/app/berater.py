"""Anlageberater: verschiedene Beraterprofile beurteilen die Situation des Haushalts.

Die App stellt die Fakten zusammen (Personen, Vorsorge, Vermögen, Hypothek, Steuern, Versicherungen,
Amortisations-Szenario) und kombiniert sie mit der freien Situationsbeschreibung und dem Profil zu
einem Auftrag. Dieser geht an die KI-Aufgabe von Home Assistant (ai_task) oder wird zum Kopieren
angezeigt; die Antwort lässt sich dann einfügen. Alles bleibt im Konfigurationsordner der App.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

from dataclasses import dataclass, field
from datetime import date, datetime

import steuern as st
import vermoegen as vm
import versicherungen as vi
import vorsorge as vs

STANDARD_PROFILE = [
    {"id": "sicherheit", "name": "Konservativ – Sicherheit zuerst",
     "anweisung": "Du bist ein konservativer, unabhängiger Schweizer Finanzplaner. Oberstes Ziel sind Sicherheit, "
                  "Liquidität und planbare Kosten. Du bevorzugst Schuldenabbau und Absicherung vor Rendite."},
    {"id": "steuern", "name": "Steueroptimierer",
     "anweisung": "Du bist ein Schweizer Steuerexperte für Privatpersonen. Du suchst legale Optimierungen: "
                  "PK-Einkäufe, 3a, Staffelung von Kapitalbezügen, Liegenschaftsunterhalt, Wohnsitzkanton. "
                  "Beachte Sperrfristen (3 Jahre nach PK-Einkauf) und die Abschaffung des Eigenmietwerts ab 2029."},
    {"id": "hypothek", "name": "Hypothekar- und Immobilienberater",
     "anweisung": "Du bist ein unabhängiger Hypothekarberater in der Schweiz. Du beurteilst Amortisation, "
                  "Laufzeiten, Festhypothek vs. SARON, Staffelung, Tragbarkeit und Zinsrisiko."},
    {"id": "vorsorge", "name": "Vorsorge- und Pensionsplaner",
     "anweisung": "Du bist ein Schweizer Vorsorgeplaner. Du beurteilst AHV, Pensionskasse, 3a, Rente vs. Kapital, "
                  "Frühpensionierung und die Absicherung bei Invalidität und Tod (besonders bei Konkubinat)."},
    {"id": "wachstum", "name": "Wachstum – langfristige Rendite",
     "anweisung": "Du bist ein unabhängiger Anlageberater mit langfristigem Horizont. Du denkst in Asset Allocation, "
                  "Kosten (TER), Diversifikation und Opportunitätskosten von Schuldenabbau gegenüber Anlagen."},
    {"id": "kritiker", "name": "Advocatus Diaboli",
     "anweisung": "Du prüfst die Pläne kritisch: Welche Annahmen sind zu optimistisch, welche Risiken werden "
                  "übersehen (Jobverlust, Trennung, Tod, Invalidität, Zinsanstieg, Immobilienpreise)?"},
]

REGELN = """Regeln für deine Antwort:
- Antworte auf Deutsch (Schweiz), konkret und strukturiert: 1. Einschätzung, 2. Empfehlungen mit Beträgen und Zeitpunkten,
  3. Begründung mit nachvollziehbarer Rechnung, 4. Risiken und offene Fragen.
- Keine Produktwerbung, keine Anbieterempfehlungen ohne Begründung. Nenne Annahmen ausdrücklich.
- Rechne mit den Fakten unten; wenn etwas fehlt, sag, welche Angabe du brauchst.
- Weise darauf hin, dass dies keine verbindliche Anlage-, Steuer- oder Rechtsberatung ist."""


def profile(k: dict) -> list[dict]:
    eigene = (k.get("berater") or {}).get("profile") or []
    return eigene or STANDARD_PROFILE


def profil(k: dict, pid: str) -> dict:
    return next((p for p in profile(k) if p["id"] == pid), profile(k)[0])


# ---------------------------------------------------------------- Amortisation bis zur Fälligkeit

@dataclass
class Amortisation:
    faellig: date
    monate: int
    hypothek: float
    liquiditaet_heute: float
    sparen: float
    verpfaendet: float
    steuer_bezug: float
    einkaeufe: float
    reserve: float
    verfuegbar: float
    ziel: float
    maximal: float
    moeglich: float
    hypothek_danach: float
    zeilen: list = field(default_factory=list)
    hinweise: list = field(default_factory=list)


def _monate(von: date, bis: date) -> int:
    return max(0, (bis.year - von.year) * 12 + bis.month - von.month)


def amortisation(k: dict, db, heute: date | None = None) -> Amortisation | None:
    w = k["wohnen"]
    if not w.get("aktiv") or not w.get("hypothek_faellig"):
        return None
    heute = heute or date.today()
    faellig = date.fromisoformat(str(w["hypothek_faellig"]))
    monate = _monate(heute, faellig)
    jahre = monate / 12
    hypothek = max(0.0, float(w.get("kaufpreis", 0)) - float(w.get("eigenmittel", 0)))
    konten = vm.konten(db)
    ausnahmen = set(w.get("nicht_antasten") or ["krypto", "immobilie", "hypothek", "kredit", "vorsorge"])
    liquid = sum(x["wert"] for x in konten if x["art"] not in ausnahmen)
    sparen = sum(float(p.get("sparen_monat", 0) or 0) for p in k["personen"]) * monate
    zeilen, verpf = [], 0.0
    for v in w.get("verpfaendet") or []:
        r = float(v.get("rendite", 0)) / 100
        wert = float(v.get("guthaben", 0)) * (1 + r) ** jahre + float(v.get("beitrag_monat", 0)) * monate
        zeilen.append((v.get("name", "Vorsorge"), round(wert)))
        verpf += wert
    steuer = float(w.get("steuer_bezug_verpfaendet", 0) or 0)
    einkaeufe = 0.0
    for p in k["personen"]:
        for e in p["pk"].get("einkauf_geplant") or []:
            if heute.year <= int(e["jahr"]) <= faellig.year:
                einkaeufe += float(e["betrag"]) - st.ersparnis_abzug(k, float(e["betrag"]), p["name"])["total"]
    reserve = float(w.get("reserve", 0) or 0)
    verfuegbar = liquid + sparen + verpf - steuer - einkaeufe - reserve
    ziel, maximal = float(w.get("amortisation_ziel", 0) or 0), float(w.get("amortisation_max", 0) or 0)
    moeglich = max(0.0, min(verfuegbar, maximal or verfuegbar, hypothek))
    hinw = []
    if ziel and verfuegbar < ziel:
        hinw.append(f"Bis zur Fälligkeit fehlen rund CHF {ziel - verfuegbar:,.0f} für die Ziel-Amortisation." >> TS)
    if einkaeufe:
        hinw.append("Geplante PK-Einkäufe binden Geld bis zur Pensionierung; danach ist 3 Jahre lang kein "
                    "Kapitalbezug (auch kein WEF-Vorbezug) möglich, ohne den Steuerabzug zu verlieren.")
    for p in k["personen"]:
        b = float(p["saeule3a"].get("beitrag_jahr", 0))
        if b > k["kennzahlen"]["saeule3a_max"]:
            hinw.append(f"{p['name']}: 3a-Beitrag {b:,.0f} über dem Maximum {k['kennzahlen']['saeule3a_max']:,.0f} – "
                        "Überschuss ist nicht abzugsfähig." >> TS)
    return Amortisation(faellig, monate, round(hypothek), round(liquid), round(sparen), round(verpf), round(steuer),
                        round(einkaeufe), round(reserve), round(verfuegbar), ziel, maximal, round(moeglich),
                        round(hypothek - moeglich), zeilen, hinw)


# ---------------------------------------------------------------- Fakten und Auftrag

def _chf(v) -> str:
    return f"CHF {float(v):,.0f}" >> TS


def _kinder_liste(k: dict) -> list[dict]:
    import kinder as ki
    return ki.liste(k)


def _kind_text(k: dict, c: dict, heute: date) -> str:
    import kinder as ki
    teile = [f"Jg. {ki.geburtsjahr(c)}", f"{ki.alter(c, heute.year)} Jahre"]
    if str(c.get("eltern") or "gemeinsam") not in ("gemeinsam", ""):
        teile.append(f"Kind von {c['eltern']}")
    if ki.betreuung_jahr(c, heute.year):
        teile.append(f"Betreuung {_chf(ki.betreuung_jahr(c, heute.year))}/Jahr")
    teile.append(f"unterhaltsberechtigt bis {ki.ausbildung_bis(c)}")
    return ", ".join(teile)


def fakten(k: dict, db, heute: date | None = None) -> str:
    heute = heute or date.today()
    hh = k["haushalt"]
    z = [f"Stand: {heute.strftime('%d.%m.%Y')}",
         f"Haushalt: {hh.get('zivilstand')}, Kanton {hh.get('kanton')}, Kinder: "
         + (", ".join(f"{c['name']} ({_kind_text(k, c, heute)})" for c in _kinder_liste(k)) or "keine")]
    ahv = {r.name: r for r in vs.ahv(k, heute.year)}
    for p in k["personen"]:
        pk = vs.pk(p, k)
        d = vs.saeule3a(p, k, heute.year)
        z.append(
            f"- {p['name']}: geboren {p['geburtsdatum']}, Pensionierung mit {p.get('pensionierung_alter', 65)}, "
            f"Bruttolohn {_chf(p.get('lohn_brutto', 0))}, Sparpotenzial {_chf(p.get('sparen_monat', 0))}/Monat; "
            f"PK-Guthaben {_chf(p['pk'].get('altersguthaben', 0))}, Einkaufspotenzial {_chf(p['pk'].get('einkauf_potenzial', 0))}, "
            f"PK mit 65: {_chf(pk.guthaben_pensionierung)} bzw. Rente {_chf(pk.rente_jahr)}/Jahr; "
            f"3a {_chf(p['saeule3a'].get('guthaben', 0))} (Beitrag {_chf(d.beitrag)}/Jahr); "
            f"AHV geschätzt {_chf(ahv[p['name']].rente_jahr)}/Jahr.")
    nv = vm.nettovermoegen(db)
    z.append("Vermögen nach Art: " + "; ".join(f"{vm.ARTEN.get(a, a)} {_chf(v)}" for a, v in nv["nach_art"].items())
             + f"; Nettovermögen {_chf(nv['total'])}.")
    w = k["wohnen"]
    if w.get("aktiv"):
        hyp = max(0.0, float(w.get("kaufpreis", 0)) - float(w.get("eigenmittel", 0)))
        z.append(f"Liegenschaft: Wert {_chf(w.get('kaufpreis', 0))}, Hypothek {_chf(hyp)} zu {w.get('hypothek_zins')} %, "
                 f"fällig {w.get('hypothek_faellig') or 'unbekannt'}, Mieteinnahmen {_chf(w.get('mieteinnahmen_jahr', 0))}/Jahr "
                 f"({w.get('vermietet_anteil') or 0} % vermietet), Eigenmietwert {_chf(w.get('eigenmietwert', 0))} für die ganze "
                 "Liegenschaft, steuerbar nur auf den selbst bewohnten Teil (Abschaffung ab 2029).")
        a = amortisation(k, db, heute)
        if a:
            z.append(f"Amortisations-Szenario bis {a.faellig.strftime('%d.%m.%Y')} ({a.monate} Monate): heute liquide "
                     f"{_chf(a.liquiditaet_heute)} + Sparen {_chf(a.sparen)} + verpfändete Vorsorge {_chf(a.verpfaendet)} "
                     f"− Steuer Bezug {_chf(a.steuer_bezug)} − PK-Einkäufe netto {_chf(a.einkaeufe)} − Reserve {_chf(a.reserve)} "
                     f"= {_chf(a.verfuegbar)}; Ziel {_chf(a.ziel)} bis {_chf(a.maximal)}.")
    s = st.steuern_heute(k)
    z.append("Steuern heute: " + "; ".join(f"{e['name']} {_chf(e['total'])} (Grenzsatz {e['grenz_total']} %)"
                                          for e in s["einheiten"]))
    import steuerdokumente as sd
    for person, jahre in sd.vergleich(sd.alle(db)).items():
        teile_ = [f"{j}: steuerbar Kanton {_chf(w.get('steuerbar_kanton', 0))}, Steuern Kanton/Gemeinde "
                  f"{_chf(w.get('steuer_kanton_gemeinde', 0))}, Bund {_chf(w.get('bundessteuer', 0))}, 3a {_chf(w.get('abzug_3a', 0))}, "
                  f"PK-Einkauf {_chf(w.get('abzug_pk_einkauf', 0))}" for j, w in sorted(jahre.items())]
        z.append(f"Steuerhistorie {person}: " + "; ".join(teile_))
    l = vs.pensionsluecke(k, nv["frei"], heute.year)
    z.append(f"Ruhestand ab {l.jahr}: Einkommen {_chf(l.einkommen)}/Jahr, Bedarf {_chf(l.bedarf)}, Lücke {_chf(l.luecke)}"
             + (f" (heutige Franken, Teuerung {l.teuerung:g} %; Lücke im Mittel {_chf(l.luecke_mittel)}, nach "
                f"{l.spaeter_jahre} Jahren {_chf(l.luecke_spaeter)})" if l.teuerung else "") + ".")
    import kinder as ki
    if ki.liste(k):
        u = ki.uebersicht(k, heute)
        z.append(f"Kinder: Steuerwirkung heute rund {_chf(u.steuer_heute)}/Jahr"
                 + (f", letzter Kinderabzug {u.ende_jahr}" if u.ende_jahr else "") + "; "
                 + "; ".join(u.hinweise))
    import zuzug as zz
    z.extend("Zuzug: " + h for h in zz.hinweise(k, heute))
    if any(zz.rente_ausland(p) for p in k["personen"]):
        z.append("Renten aus dem Ausland: " + ", ".join(f"{p['name']} {_chf(zz.rente_ausland(p))}/Jahr ab {zz.rente_ausland_alter(p)}"
                                                        for p in k["personen"] if zz.rente_ausland(p)) + ".")
    import budget as bu
    b = bu.auswerten(k, db, heute=heute)
    if b:
        z.append(f"Budget aus {b.monate} Monaten Kontoauszügen: Einnahmen {_chf(b.einnahmen / 12)}/Monat, Ausgaben "
                 f"{_chf(b.ausgaben / 12)}/Monat, gespart {_chf((b.ueberschuss + b.sparen_konto) / 12)}/Monat; grösste Ausgaben: "
                 + ", ".join(f"{n} {_chf(j / 12)}" for n, j, _ in b.kategorien[:5]) + ".")
    vertraege = vi.alle(db)
    if vertraege:
        z.append(f"Versicherungsprämien {_chf(vi.praemien(vertraege)['total'])}/Jahr. Deckungscheck: "
                 + "; ".join(f"{t}: {x}" for s_, t, x in vi.deckungscheck(k, vertraege) if s_ in ("fehlt", "pruefen")))
    return "\n".join(z)


def auftrag(k: dict, db, pid: str, frage: str) -> str:
    p = profil(k, pid)
    situation = ((k.get("berater") or {}).get("situation") or "").strip()
    teile = [p["anweisung"], REGELN]
    if situation:
        teile.append("Situation in unseren Worten:\n" + situation)
    teile.append("Fakten aus unserer Finanzplanung:\n" + fakten(k, db))
    teile.append("Unsere Frage:\n" + (frage.strip() or "Wie sollen wir vorgehen? Bitte beurteile unsere Situation gesamthaft."))
    return "\n\n".join(teile)


# ---------------------------------------------------------------- Speicher

def tabellen(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS beratungen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datum TEXT NOT NULL,
            profil TEXT NOT NULL,
            frage TEXT NOT NULL DEFAULT '',
            auftrag TEXT NOT NULL DEFAULT '',
            antwort TEXT NOT NULL DEFAULT ''
        );
        """
    )


def speichern(db, profil_name: str, frage: str, auftrag_text: str, antwort: str) -> int:
    tabellen(db)
    cur = db.execute("INSERT INTO beratungen (datum, profil, frage, auftrag, antwort) VALUES (?, ?, ?, ?, ?)",
                     (datetime.now().isoformat(timespec="seconds"), profil_name, frage, auftrag_text, antwort))
    db.commit()
    return cur.lastrowid


def antwort_setzen(db, bid: int, antwort: str) -> None:
    db.execute("UPDATE beratungen SET antwort = ? WHERE id = ?", (antwort, bid))
    db.commit()


def alle(db) -> list[dict]:
    tabellen(db)
    return [dict(r) for r in db.execute("SELECT * FROM beratungen ORDER BY datum DESC")]


def eine(db, bid: int) -> dict | None:
    tabellen(db)
    r = db.execute("SELECT * FROM beratungen WHERE id = ?", (bid,)).fetchone()
    return dict(r) if r else None


def loeschen(db, bid: int) -> None:
    db.execute("DELETE FROM beratungen WHERE id = ?", (bid,))
    db.commit()


def fragen(k: dict, db, pid: str, frage: str) -> int:
    """Auftrag an die KI senden und Antwort speichern."""
    p = profil(k, pid)
    text = auftrag(k, db, pid, frage)
    antwort = vi.ki_aufgabe(text, (k.get("ki") or {}).get("entity", ""), f"Beratung {p['name']}",
                            json_antwort=False)
    return speichern(db, p["name"], frage, text, antwort or "")
