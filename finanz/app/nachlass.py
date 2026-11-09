"""Nachlass und Absicherung: Was erhält der Partner beim Tod, welche Steuern fallen an, was ist geregelt?

Vereinfachtes Modell (heutige Franken, Stand Gesetz 2023):
- Nachlass einer Person = eigene Konten + Hälfte der gemeinsamen Konten + Anteil an der Liegenschaft (Wert − Hypothek)
  + freie Vorsorge 3b (Rückkaufswert). Hausrat und Schulden ausserhalb der Hypothek bleiben unberücksichtigt.
- Gesetzliche Erben: Ehegatte und Nachkommen; Konkubinatspartner erben ohne Testament nichts.
  Pflichtteil der Nachkommen 1/2 ihres gesetzlichen Anspruchs, des Ehegatten 1/2 (seit 1.1.2023).
- Vorsorge (PK-Kapital, 3a) fällt nicht in den Nachlass, sondern geht nach Reglement bzw. Begünstigungsordnung an
  Ehegatten, Lebenspartner (meist 5 Jahre gemeinsamer Haushalt oder gemeinsames Kind, Meldung nötig) und Kinder;
  sie wird als Kapitalleistung besteuert. Risikopolicen gehen an die Begünstigten.
"""
from __future__ import annotations

from tausender import TS  # noqa: E402

from dataclasses import dataclass, field
from datetime import date

import vermoegen as vm

# Erbschaftssteuer für Konkubinatspartner: Kanton → (Satz %, Freibetrag, Bedingung, geprüft?)
# BL: Gesetz über die Erbschafts- und Schenkungssteuer (SGS 334) § 12 Abs. 1 lit. b und d, § 9.
PARTNER_STEUER = {
    "BL": {"satz": 15.0, "freibetrag": 30_000, "satz_ohne": 30.0, "freibetrag_ohne": 10_000, "jahre": 5, "geprueft": True,
           "quelle": "SGS 334 § 12: 15 % nach Abzug von 30'000 bei mindestens 5 Jahren häuslicher Gemeinschaft am gleichen "
                     "Wohnsitz, sonst 30 % nach Abzug von 10'000; Ehegatten und Nachkommen befreit."},
    "SZ": {"satz": 0.0, "freibetrag": 0, "satz_ohne": 0.0, "freibetrag_ohne": 0, "jahre": 0, "geprueft": False,
           "quelle": "Keine Erbschaftssteuer im Kanton Schwyz."},
    "ZG": {"satz": 0.0, "freibetrag": 0, "satz_ohne": None, "freibetrag_ohne": 0, "jahre": None, "geprueft": False,
           "quelle": "Lebenspartner dem Ehegatten gleichgestellt (Bedingungen prüfen)."},
    "NW": {"satz": 0.0, "freibetrag": 0, "satz_ohne": None, "freibetrag_ohne": 0, "jahre": None, "geprueft": False,
           "quelle": "Lebenspartner dem Ehegatten gleichgestellt (Bedingungen prüfen)."},
    "OW": {"satz": 0.0, "freibetrag": 0, "satz_ohne": None, "freibetrag_ohne": 0, "jahre": None, "geprueft": False,
           "quelle": "Lebenspartner dem Ehegatten gleichgestellt (Bedingungen prüfen)."},
    "GR": {"satz": 0.0, "freibetrag": 0, "satz_ohne": None, "freibetrag_ohne": 0, "jahre": None, "geprueft": False,
           "quelle": "Kanton: Lebenspartner dem Ehegatten gleichgestellt; Gemeinden können bis 5 % erheben."},
}

CHECKLISTE = [
    ("testament", "Testament bzw. Erbvertrag", "Ohne Testament erbt der Partner nichts. Eigenhändig von Anfang bis Ende "
     "geschrieben, datiert, unterschrieben – oder öffentlich beim Notar. Verfügbare Quote bei einem Kind: die Hälfte."),
    ("pk_meldung", "Lebenspartner bei der Pensionskasse gemeldet", "Voraussetzung für Lebenspartnerrente und Todesfallkapital; "
     "Formular der Kasse, oft zu Lebzeiten und schriftlich."),
    ("begünstigung_3a", "Begünstigung Säule 3a angepasst", "Lebenspartner nach 5 Jahren Zusammenleben oder mit gemeinsamem "
     "Kind möglich – schriftlich bei der Stiftung bzw. Versicherung festlegen."),
    ("begünstigung_policen", "Begünstigte der Risiko- und Lebensversicherungen", "Partner namentlich als Begünstigten eintragen."),
    ("vorsorgeauftrag", "Vorsorgeauftrag", "Wer handelt bei Urteilsunfähigkeit (Vermögen, Rechtsverkehr, Person)? Sonst entscheidet die KESB."),
    ("patientenverfuegung", "Patientenverfügung", "Medizinische Wünsche und Vertretungsperson; der Konkubinatspartner ist "
     "gesetzlich nachrangig vertretungsberechtigt."),
    ("konkubinatsvertrag", "Konkubinatsvertrag", "Eigentum, Hausrat, Darlehen, Wohnrecht und Vorgehen bei Trennung regeln."),
    ("liegenschaft", "Regelung für die Liegenschaft", "Miteigentum, Wohnrecht oder Nutzniessung und Finanzierung der "
     "Auszahlung an die Erben (z. B. Todesfallrisiko-Police in Höhe des Ausgleichs)."),
    ("willensvollstrecker", "Willensvollstrecker", "Im Testament bestimmen; erleichtert die Abwicklung."),
    ("notfallordner", "Notfallordner", "Übersicht über Konten, Policen, Verträge, Kontakte und Zugänge für den Partner."),
]


@dataclass
class Fall:
    verstorben: str
    partner: str
    nachlass: float
    davon_liegenschaft: float
    kinder: int
    verheiratet: bool
    erbe_partner_ohne: float          # ohne Testament
    erbe_partner_mit: float           # mit Testament (maximale verfügbare Quote)
    erbe_kinder_mit: float
    steuer_partner_mit: float
    vorsorge_kapital: float           # Todesfallkapital PK + 3a an den Partner (sofern begünstigt)
    vorsorge_steuer: float
    policen: float                    # Risikopolicen an den Partner
    renten_partner: float             # Renten pro Jahr an den Partner (AHV-Witwe, PK)
    ausgleich_haus: float             # Auszahlung an die Kinder, damit der Partner die ganze Liegenschaft behält
    hinweise: list = field(default_factory=list)


def _jahre_zusammen(k: dict, heute: date) -> int | None:
    seit = (k.get("nachlass") or {}).get("zusammen_seit")
    if not seit:
        return None
    return heute.year - int(str(seit)[:4])


def partner_steuer(k: dict, betrag: float, heute: date | None = None) -> tuple[float, str, bool]:
    """Erbschaftssteuer für den Konkubinatspartner. Gibt (Steuer, Erklärung, geprüft) zurück."""
    heute = heute or date.today()
    cfg = k.get("nachlass") or {}
    kanton = str(k["haushalt"].get("kanton", "")).upper()
    eigen = cfg.get("erbschaftssteuer") or {}
    if eigen.get("satz") not in (None, ""):
        satz, frei = float(eigen["satz"]), float(eigen.get("freibetrag", 0) or 0)
        return round(max(0.0, betrag - frei) * satz / 100), f"eigene Angabe: {satz:g} % nach Abzug von {frei:,.0f}" >> TS, True
    r = PARTNER_STEUER.get(kanton)
    if not r:
        return 0.0, f"Satz für {kanton or 'den Kanton'} nicht hinterlegt – unter nachlass.erbschaftssteuer eintragen.", False
    jahre = _jahre_zusammen(k, heute)
    if r["jahre"] and (jahre is None or jahre < r["jahre"]) and r["satz_ohne"] is not None:
        satz, frei = r["satz_ohne"], r["freibetrag_ohne"]
        grund = (f"weniger als {r['jahre']} Jahre gemeinsamer Haushalt" if jahre is not None
                 else "Beginn des gemeinsamen Haushalts nicht erfasst (nachlass.zusammen_seit)")
        text = f"{satz:g} % nach Abzug von {frei:,.0f} ({grund})" >> TS
    else:
        satz, frei = r["satz"], r["freibetrag"]
        text = f"{satz:g} % nach Abzug von {frei:,.0f}" >> TS if satz else "steuerfrei"
    return round(max(0.0, betrag - frei) * satz / 100), text + " – " + r["quelle"], r["geprueft"]


def nachlass_von(k: dict, db, person: str) -> tuple[float, float]:
    """(Nachlass, davon Liegenschaft) einer Person."""
    import versicherungen as vi
    cfg = k.get("nachlass") or {}
    konten = vm.konten(db)
    n = len(k["personen"]) or 1
    eigen = 0.0
    for x in konten:
        if x["art"] in ("immobilie", "hypothek"):
            continue
        if not x["person"]:
            eigen += x["wert"] / n
        elif vi.gleiche_person(x["person"], person):
            eigen += x["wert"]
    w = k.get("wohnen") or {}
    haus = 0.0
    if w.get("aktiv"):
        import wohnen as wo
        anteile = wo.eigentum_anteile(k)
        anteil = float(next((v for kk, v in anteile.items() if vi.gleiche_person(kk, person)), 100 / n)) / 100
        hypothek = max(0.0, float(w.get("kaufpreis", 0)) - float(w.get("eigenmittel", 0)))
        haus = (float(w.get("kaufpreis", 0)) - hypothek) * anteil
    return round(eigen + haus), round(haus)


def faelle(k: dict, db, heute: date | None = None) -> list[Fall]:
    import steuern as st
    import versicherungen as vi
    import vorsorge as vs

    heute = heute or date.today()
    if len(k["personen"]) < 2:
        return []
    verheiratet = k["haushalt"].get("zivilstand") == "verheiratet"
    import kinder as ki
    cfg = k.get("nachlass") or {}
    testament = ((cfg.get("checkliste") or {}).get("testament") or {})
    risiko = {r.name: r for r in vi.risiko(k, vs.ahv(k, heute.year))}
    erg = []
    for p, partner in ((k["personen"][0], k["personen"][1]), (k["personen"][1], k["personen"][0])):
        nachlass, haus = nachlass_von(k, db, p["name"])
        kinder = len(ki.eigene(k, p["name"]))            # Nachkommen des Verstorbenen (jeden Alters)
        # Gesetzliche Erbfolge
        if verheiratet:
            ohne = nachlass * (0.5 if kinder else 1.0)          # Ehegatte neben Nachkommen 1/2 (ohne Güterrecht)
            mit = nachlass * (1 - (0.25 if kinder else 0.0))    # Kinder Pflichtteil 1/4 des Nachlasses
        else:
            ohne = 0.0
            mit = nachlass * (0.5 if kinder else 1.0)           # Kinder Pflichtteil 1/2
        kinder_mit = nachlass - mit
        steuer, _, _ = (0.0, "", True) if verheiratet else partner_steuer(k, mit, heute)
        # Vorsorge und Policen an den Partner
        r = p.get("risiko") or {}
        pk_kapital = float(r.get("todesfallkapital_pk", 0) or 0)
        drei_a = float(p["saeule3a"].get("guthaben", 0) or 0)
        darf = verheiratet or bool(r.get("partner_bei_pk_gemeldet"))
        vorsorge = (pk_kapital if darf else 0.0) + drei_a
        einheit = st.einheit_von(k, partner["name"])
        v_steuer = st.kapitalsteuer(vorsorge, k, einheit)["total"] if vorsorge else 0
        policen = float(r.get("todesfallkapital_extern", 0) or 0)
        renten = risiko[p["name"]].tod_renten if p["name"] in risiko else 0.0
        # Liegenschaft: Was müsste der Partner den Kindern auszahlen, um die ganze Liegenschaft zu behalten?
        ausgleich = max(0.0, haus - mit) if testament.get(p["name"]) or verheiratet else haus
        hinw = []
        if not verheiratet and not testament.get(p["name"]):
            hinw.append(f"Ohne Testament erbt {partner['name']} nichts; der ganze Nachlass von {p['name']} geht an "
                        + ("die Kinder." if kinder else "Eltern bzw. Geschwister."))
        if ausgleich > 0:
            hinw.append(f"Damit {partner['name']} die Liegenschaft behalten kann, wären rund CHF {ausgleich:,.0f} an die Erben "
                        "auszuzahlen – Liquidität oder eine Todesfallrisiko-Police in dieser Höhe einplanen." >> TS)
        if not verheiratet and not r.get("partner_bei_pk_gemeldet") and (r.get("partnerrente_pk") or pk_kapital):
            hinw.append(f"PK von {p['name']}: Lebenspartnerschaft nicht als gemeldet erfasst – sonst keine Partnerrente und kein "
                        "Todesfallkapital für den Partner.")
        if drei_a:
            hinw.append(f"3a von {p['name']} (CHF {drei_a:,.0f}): Begünstigung des Partners schriftlich bei der Stiftung festlegen."
                         >> TS)
        erg.append(Fall(p["name"], partner["name"], nachlass, haus, kinder, verheiratet, round(ohne), round(mit),
                        round(kinder_mit), steuer, round(vorsorge), round(v_steuer), round(policen), round(renten),
                        round(ausgleich), hinw))
    return erg


def checkliste(k: dict) -> list[tuple[str, str, str, dict]]:
    """(Schlüssel, Titel, Erklärung, {Person: erledigt})."""
    erledigt = (k.get("nachlass") or {}).get("checkliste") or {}
    namen = [p["name"] for p in k["personen"]]
    return [(s, t, e, {n: bool((erledigt.get(s) or {}).get(n)) for n in namen}) for s, t, e in CHECKLISTE]
