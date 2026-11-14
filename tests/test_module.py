"""Versicherungen, Vorsorgedokumente, Risiko, Konkubinat, Berater und Import-Ordner (erfundene Daten)."""
import copy
from datetime import date
import re

import pytest

import berater as br
import dokumente as dk
import importordner
import konfig
import steuern as st
import vermoegen as vm
import versicherungen as vi
import vorsorge as vs
from policen import DREI_A, HAUSRAT, KVG, LEBEN, PK_AUSWEIS, RECHTSSCHUTZ_1, RECHTSSCHUTZ_2, pdf


@pytest.fixture
def db(tmp_path):
    return vm.verbinden(tmp_path / "t.sqlite")


@pytest.fixture
def konkubinat(k):
    k = copy.deepcopy(k)
    k["haushalt"]["zivilstand"] = "ledig"
    k["steuern"]["personen"] = [
        {"person": "Person 1", "steuerbar_bund": 100_000, "steuerbar_kanton": 100_000,
         "steuer_kanton_gemeinde": 12_000, "grenzsteuersatz_kanton": 20, "kinder": 1},
        {"person": "Person 2", "steuerbar_bund": 100_000, "steuerbar_kanton": 100_000,
         "steuer_kanton_gemeinde": 13_000, "grenzsteuersatz_kanton": 22, "kinder": 0},
    ]
    return k


# ---------------------------------------------------------------- Versicherungen

def test_policen_erkennen():
    t = vi.text_auslesen("a.pdf", pdf(KVG))
    e = vi.erkennen(t)
    assert e["sparte"] == "kvg" and e["versicherer"] == "Helsana" and e["person"] == "Person 1"
    assert e["praemie_jahr"] == pytest.approx(412.5 * 12) and e["franchise"] == 300 and e["unfall_eingeschlossen"] == 1
    e = vi.erkennen(vi.text_auslesen("b.pdf", pdf(HAUSRAT)))
    assert e["sparte"] == "hausrat_haftpflicht" and e["ablauf"] == "2027-03-14" and e["kuendigungsfrist_monate"] == 3
    assert e["praemie_jahr"] == pytest.approx(612.4) and e["summe"] == 120_000
    assert vi.erkennen(LEBEN)["sparte"] == "leben_3b"


def test_hochladen_und_deckungscheck(k, db, tmp_path):
    for text in (KVG, HAUSRAT, LEBEN, RECHTSSCHUTZ_1, RECHTSSCHUTZ_2):
        vi.hochladen(db, tmp_path, "police.pdf", pdf(text))
    alle = vi.alle(db)
    assert len(alle) == 5 and (tmp_path / "versicherungen" / "1.pdf").exists()
    check = {(s, t) for s, t, _ in vi.deckungscheck(k, alle)}
    assert ("ok", "Privathaftpflicht") in check and ("ok", "Hausrat") in check
    assert ("pruefen", "Rechtsschutz") in check                       # Doppelversicherung
    assert ("pruefen", "Unfalldeckung") in check                      # angestellt + Unfall in KVG
    texte = [x for _, t, x in vi.deckungscheck(k, alle) if t == "Grundversicherung"]
    assert any("Person 1: vorhanden" in x for x in texte) and any("Person 2" in x and "obligatorisch" in x for x in texte)
    assert vi.praemien(alle)["total"] == round(4950 + 612.4 + 3000 + 330 + 290)


def test_csv_liste(k, db):
    csv = "Versicherung;Anbieter;Betrag;Person;Summe\nHausrat;Smile;217.40;;\nHaushalt/Haftpflicht;Baloise;124.50;;\n" \
          "Tod Person 1;Vaudoise;292.60;Person 1;156000\nInvaliden Person 2;Helvetia;756.40;Person 2;24000\n" \
          "Kantonale Gebäudeversicherung;BGV;250.85;;\nGebäudeversicherung;Helvetia;1582.50;;\n"
    n, fehler = vi.csv_import(db, csv.encode())
    assert n == 6 and not fehler
    sparten = sorted(v["sparte"] for v in vi.alle(db))
    assert sparten == sorted(["hausrat", "haftpflicht", "risiko_leben", "erwerbsunfaehigkeit", "gebaeude", "gebaeude"])
    k["wohnen"]["aktiv"] = True
    gebaeude = [s for s, t, _ in vi.deckungscheck(k, vi.alle(db)) if t == "Gebäude"]
    assert gebaeude == ["ok"]                                         # kantonal + privat ist üblich


def test_kuendigungstermine():
    heute = date(2026, 11, 8)
    t = vi.naechster_termin({"sparte": "kvg"}, heute)
    assert t.kuendigen_bis == date(2026, 11, 30) and t.wirksam_auf == date(2027, 1, 1)
    v = {"sparte": "hausrat", "beginn": "2022-03-15", "ablauf": "2027-03-14", "kuendigungsfrist_monate": 3}
    t = vi.naechster_termin(v, heute)
    assert t.wirksam_auf == date(2027, 3, 14) and t.kuendigen_bis == date(2026, 12, 14)
    v = {"sparte": "hausrat", "beginn": "2025-01-01", "ablauf": "", "kuendigungsfrist_monate": 3}
    assert vi.naechster_termin(v, heute).wirksam_auf == date(2028, 1, 1)   # Art. 35a VVG: Ende 3. Jahr


# ---------------------------------------------------------------- Vorsorgedokumente

def test_vorsorgeausweis_erkennen_und_uebernehmen(k, db, tmp_path):
    did = dk.hochladen(db, tmp_path, "ausweis.pdf", pdf(PK_AUSWEIS))
    d = dk.einer(db, did)
    assert d["typ"] == "pk_ausweis" and d["stichtag"] == "2026-01-01" and d["person"] == "Person 1"
    w = d["werte"]
    assert w["altersguthaben"] == 250_000 and w["einkauf_potenzial"] == 180_000
    assert w["ausweis_alterskapital"] == 1_200_000 and w["ausweis_altersrente"] == 60_000
    assert w["umwandlungssatz"] == 5.0 and w["iv_rente_pk"] == 72_000 and w["iv_kinderrente_pk"] == 14_400
    assert w["partnerrente_pk"] == 43_200 and w["todesfallkapital_pk"] == 50_000 and w["sparbeitrag_jahr"] == 14_400
    erledigt = dk.uebernehmen(k, d, 0, list(w))
    p = k["personen"][0]
    assert p["pk"]["altersguthaben"] == 250_000 and p["risiko"]["iv_rente_pk"] == 72_000 and p["pk"]["stand"] == "2026-01-01"
    assert len(erledigt) >= 10
    e = vs.pk(p, k)
    assert e.guthaben_pensionierung == 1_200_000 and e.rente_jahr == 60_000   # Prognose der Kasse


def test_3a_auszug(db, tmp_path):
    d = dk.einer(db, dk.hochladen(db, tmp_path, "3a.pdf", pdf(DREI_A)))
    assert d["typ"] == "saeule3a" and d["anbieter"] == "VIAC"
    assert d["werte"]["guthaben_3a"] == pytest.approx(48_500.25) and d["werte"]["beitrag_3a"] == 7258


# ---------------------------------------------------------------- Konkubinat und Risiko

def test_konkubinat_getrennte_steuern(konkubinat):
    s = st.steuern_heute(konkubinat)
    assert len(s["einheiten"]) == 2
    kz = konkubinat["kennzahlen"]
    assert s["einheiten"][0]["bund"] == round(st.bundessteuer(100_000, False, 1, kz))   # Elterntarif
    assert s["einheiten"][1]["bund"] == round(st.bundessteuer(100_000, False, 0, kz))   # Grundtarif
    assert s["einheiten"][0]["bund"] < s["einheiten"][1]["bund"]
    assert st.ersparnis_abzug(konkubinat, 1000, "Person 2")["kanton"] == pytest.approx(220, abs=2)
    pks = [vs.pk(p, konkubinat) for p in konkubinat["personen"]]
    drei = [vs.saeule3a(p, konkubinat, 2026) for p in konkubinat["personen"]]
    v = st.kapitalbezug_varianten(konkubinat, pks, drei)
    assert {z[1] for z in v["gestaffelt"]["zeilen"]} == {"Person 1", "Person 2"}


def test_konkubinat_ahv_ohne_plafond(konkubinat):
    for p in konkubinat["personen"]:
        p["lohn_brutto"], p["ahv"]["beitragsjahre_bisher"] = 120_000, 44
    assert sum(r.rente_monat_plafoniert for r in vs.ahv(konkubinat, 2026)) == 5040


def test_risiko_konkubinat(konkubinat):
    p = konkubinat["personen"][0]
    p["risiko"].update(iv_rente_pk=50_000, partnerrente_pk=30_000, waisenrente_pk=10_000, todesfallkapital_pk=100_000)
    r = vi.risiko(konkubinat, vs.ahv(konkubinat, 2026))[0]
    assert r.iv_pk == 50_000 and r.iv_total > 50_000
    assert r.tod_renten == round(r.iv_ahv * 0.4 + 10_000)          # keine Partnerrente ohne Meldung, keine AHV-Witwenrente
    assert any("Meldung" in h for h in r.hinweise) and any("AHV-Witwen" in h for h in r.hinweise)
    p["risiko"]["partner_bei_pk_gemeldet"] = True
    assert vi.risiko(konkubinat, vs.ahv(konkubinat, 2026))[0].tod_renten == r.tod_renten + 30_000


# ---------------------------------------------------------------- Berater

def test_amortisation_und_auftrag(k, db):
    k["wohnen"].update(aktiv=True, kaufpreis=2_000_000, eigenmittel=800_000, hypothek_faellig="2030-07-01",
                       amortisation_ziel=600_000, amortisation_max=800_000, reserve=50_000, steuer_bezug_verpfaendet=6000,
                       verpfaendet=[{"name": "3a", "guthaben": 40_000, "beitrag_monat": 500, "rendite": 0}])
    k["personen"][0]["sparen_monat"] = 2000
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Konto", "bank"), "2026-11-01", 300_000)
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Krypto", "krypto"), "2026-11-01", 50_000)
    a = br.amortisation(k, db, date(2026, 11, 8))
    assert a.monate == 44 and a.liquiditaet_heute == 300_000                # Krypto nicht angetastet
    assert a.verpfaendet == 40_000 + 500 * 44 and a.sparen == 2000 * 44
    assert a.verfuegbar == 300_000 + 88_000 + 62_000 - 6000 - 50_000
    assert a.moeglich == a.verfuegbar and any("fehlen" in h for h in a.hinweise)
    k["berater"] = {"situation": "Wir wollen Sicherheit.", "profile": []}
    text = br.auftrag(k, db, "hypothek", "Wie amortisieren?")
    assert "Hypothekarberater" in text and "Wir wollen Sicherheit." in text and "Wie amortisieren?" in text
    assert "Amortisations-Szenario" in text and "Person 1" in text
    bid = br.speichern(db, "Test", "Frage", text, "")
    br.antwort_setzen(db, bid, "## Antwort\n- Punkt")
    assert br.eine(db, bid)["antwort"].startswith("## Antwort")


# ---------------------------------------------------------------- Import-Ordner

def test_importordner(daten, k):
    imp = importordner.ordner(daten)
    k["haushalt"]["name"] = "Import-Test"
    (imp / "finanz.yaml").write_text(konfig.yaml.safe_dump(k, allow_unicode=True), encoding="utf-8")
    (imp / "vermoegen.csv").write_text("Datum;Konto;Saldo\n01.01.2026;Konto;1000\n", encoding="utf-8")
    (imp / "versicherungen.csv").write_text("Versicherung;Anbieter;Betrag\nHausrat;X;100\n", encoding="utf-8")
    (imp / "ausweis.pdf").write_bytes(pdf(PK_AUSWEIS))
    (imp / "police_kvg.pdf").write_bytes(pdf(KVG))
    db = vm.verbinden(daten / "finanz.sqlite")
    meldungen = importordner.einlesen(daten, db)
    assert len(meldungen) == 5 and not any("Fehler" in m for m in meldungen)
    assert konfig.laden()["haushalt"]["name"] == "Import-Test"
    assert len(vi.alle(db)) == 2 and len(dk.alle(db)) == 1 and vm.nettovermoegen(db)["total"] == 1000
    assert not [p for p in imp.iterdir() if p.is_file()] and len(list((imp / "erledigt").iterdir())) == 5


# ---------------------------------------------------------------- Steuerdokumente

def test_steuerdokumente(konkubinat, db, tmp_path):
    import steuerdokumente as sd
    from policen import STEUERERKLAERUNG, VERANLAGUNG_2024, VERANLAGUNG_2025
    ids = [sd.hochladen(db, tmp_path, n, pdf(t)) for n, t in
           (("erklaerung.pdf", STEUERERKLAERUNG), ("v25.pdf", VERANLAGUNG_2025), ("v24.pdf", VERANLAGUNG_2024))]
    e, v25, v24 = (sd.einer(db, i) for i in ids)
    assert (e["typ"], e["jahr"], e["person"]) == ("erklaerung", 2025, "Person 1")
    assert e["werte"]["steuerbar_kanton"] == 140_000 and e["werte"]["steuerbar_bund"] == 145_000
    assert e["werte"]["abzug_3a"] == 5000 and e["werte"]["eigenmietwert"] == 20_000 and e["werte"]["mietertrag"] == 15_300
    assert v25["typ"] == "veranlagung" and v25["werte"]["steuer_kanton_gemeinde"] == 23_000   # Staat + Gemeinde
    assert v24["jahr"] == 2024 and v24["werte"]["steuer_kanton_gemeinde"] == 20_200
    vergleich = sd.vergleich(sd.alle(db))["Person 1"]
    assert vergleich[2025]["_typ"] == "veranlagung"                                      # Veranlagung zählt
    assert sd.grenzsteuersatz(vergleich) == 28.0                                          # 2'800 / 10'000
    abgl = sd.abgleich(sd.alle(db))
    assert len(abgl) == 1 and "141'200" in abgl[0] and "+1'200" in abgl[0]
    tipps = " ".join(sd.hinweise(konkubinat, e))
    assert "3a" in tipps and "PK-Einkauf" in tipps and "2029" in tipps
    erledigt = sd.uebernehmen(konkubinat, v25, "Person 1", ["steuerbar_kanton", "steuer_kanton_gemeinde", "grenzsteuersatz"], 28.0)
    einheit = konkubinat["steuern"]["personen"][0]
    assert einheit["steuerbar_kanton"] == 141_200 and einheit["steuer_kanton_gemeinde"] == 23_000
    assert einheit["grenzsteuersatz_kanton"] == 28.0 and len(erledigt) == 3
    sd.uebernehmen(konkubinat, e, "Person 1", ["eigenmietwert", "abzug_3a"])
    # deklariert ist der halbe Anteil → in der Konfiguration die ganze Liegenschaft
    assert konkubinat["wohnen"]["eigenmietwert"] == 40_000 and konkubinat["personen"][0]["saeule3a"]["beitrag_jahr"] == 5000
    konkubinat["wohnen"]["vermietet_anteil"] = 38
    sd.uebernehmen(konkubinat, e, "Person 1", ["eigenmietwert", "mietertrag"])
    assert konkubinat["wohnen"]["eigenmietwert"] == round(20_000 / 0.5 / 0.62)
    assert konkubinat["wohnen"]["mieteinnahmen_jahr"] == 30_600


def test_steuer_uebernahme_neue_person(konkubinat, db, tmp_path):
    import steuerdokumente as sd
    from policen import VERANLAGUNG_2025
    konkubinat["steuern"]["personen"] = []
    d = sd.einer(db, sd.hochladen(db, tmp_path, "v.pdf", pdf(VERANLAGUNG_2025)))
    sd.uebernehmen(konkubinat, d, "Person 2", ["steuerbar_bund"])
    assert konkubinat["steuern"]["personen"][0]["person"] == "Person 2"
    assert konkubinat["steuern"]["personen"][0]["steuerbar_bund"] == 145_000


# ---------------------------------------------------------------- Ampeln

def test_ampel_schwellen():
    import ampel as am
    assert am.termin_status(10) == am.ROT and am.termin_status(30) == am.GELB and am.termin_status(90) == am.GRUEN
    assert am.iv_status(80) == am.GRUEN and am.iv_status(60) == am.GELB and am.iv_status(40) == am.ROT
    assert am.tragbarkeit_status(30, 33.3) == am.GRUEN and am.tragbarkeit_status(36, 33.3) == am.GELB
    assert am.tragbarkeit_status(40, 33.3) == am.ROT
    assert am.amortisation_status(900_000, 800_000) == am.GRUEN and am.amortisation_status(700_000, 800_000) == am.GELB
    assert am.luecke_status(0, 100_000) == am.GRUEN and am.luecke_status(5_000, 100_000) == am.GELB
    assert am.schlechteste([am.GRUEN, am.GELB, am.GRAU]) == am.GELB and am.schlechteste([]) == am.GRAU


def test_ampel_bewertung(k, daten, db):
    import ampel as am
    from policen import KVG, pdf
    leer = {a.bereich: a for a in am.bewerten(k, db)}
    assert leer["Versicherungsschutz"].status == am.GRAU and leer["Liquidität"].status == am.GRAU
    vi.hochladen(db, daten, "kvg.pdf", pdf(KVG))
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Konto", "bank"), date.today().isoformat(), 100_000)
    a = {x.bereich: x for x in am.bewerten(k, db)}
    assert a["Versicherungsschutz"].status == am.ROT and "Privathaftpflicht" in a["Versicherungsschutz"].text
    assert a["Kündigungsfristen"].status in (am.GRUEN, am.GELB, am.ROT)
    assert a["Liquidität"].status == am.GRUEN
    seiten = am.pro_seite(list(a.values()))
    assert seiten["versicherungen"] == am.ROT and seiten[""] == am.ROT


# ---------------------------------------------------------------- Szenarien

def test_einkauf_optimieren_verteilt_progression(konkubinat):
    import szenarien as sz
    p = konkubinat["personen"][0]
    p["pk"].update(einkauf_potenzial=60_000, einkauf_geplant=[], kapitalbezug_anteil=0)
    plan = sz.einkauf_optimieren(konkubinat, "Person 1", 0, 2026, 2028, schwelle=0, schritt=5000, heute=date(2026, 11, 8))
    assert sum(plan.plan.values()) == 60_000 and set(plan.plan) == {2026, 2027, 2028}
    assert max(plan.plan.values()) - min(plan.plan.values()) <= 5000                # gleichmässig verteilt
    assert plan.total_ersparnis > plan.einjahr_ersparnis                            # Staffeln lohnt sich
    assert all(b > a for (_, a), (_, b) in zip(plan.kurve[1:], plan.kurve[:-1]) if a and b) or plan.kurve
    begrenzt = sz.einkauf_optimieren(konkubinat, "Person 1", 20_000, 2026, 2030, heute=date(2026, 11, 8))
    assert sum(begrenzt.plan.values()) == 20_000
    sz.plan_uebernehmen(konkubinat, plan)
    assert len(p["pk"]["einkauf_geplant"]) == 3
    nachher = sz.einkauf_optimieren(konkubinat, "Person 1", 0, 2026, 2028, heute=date(2026, 11, 8))
    assert nachher.potenzial == 0 and not nachher.plan                              # Potenzial ausgeschöpft


def test_einkauf_sperrfrist_vor_kapitalbezug(konkubinat):
    import szenarien as sz
    p = konkubinat["personen"][0]
    p["geburtsdatum"] = "1966-01-01"                                                # Pension 2031
    p["pk"].update(einkauf_potenzial=50_000, einkauf_geplant=[], kapitalbezug_anteil=100)
    plan = sz.einkauf_optimieren(konkubinat, "Person 1", 0, 2026, 2031, heute=date(2026, 11, 8))
    assert plan.gesperrt == [2028, 2029, 2030] and set(plan.plan) <= {2026, 2027}
    assert plan.kapitalsteuer_mehr > 0 and plan.netto < plan.total_ersparnis + plan.zins_ertrag


def test_heirat_vergleich(konkubinat, db):
    import szenarien as sz
    for p in konkubinat["personen"]:
        p["lohn_brutto"], p["ahv"]["beitragsjahre_bisher"] = 120_000, 44
        p["risiko"].update(partnerrente_pk=30_000, waisenrente_pk=0)
    h = sz.heirat_vergleich(konkubinat, db)
    assert h.moeglich
    assert h.ahv_konkubinat == 2 * 2520 * 13 and h.ahv_verheiratet == 3780 * 13 and h.ahv_diff < 0   # Plafonierung
    d = sz.steuer_verheiratet(konkubinat)
    assert d["zweiverdiener"] == 14_100 and d["bund_einkommen"] == 200_000 - 2800 - 14_100 - 100
    assert all(rv > rk for _, rk, rv in h.hinterbliebene)                           # Witwenrente + Ehegattenrente
    k1 = copy.deepcopy(konkubinat)
    k1["steuern"]["personen"] = []
    assert not sz.heirat_vergleich(k1, db).moeglich


# ---------------------------------------------------------------- Hypothekar-Strategie

def test_hypothek_strategie(k):
    import hypothek as hy
    k["wohnen"].update(aktiv=True, kaufpreis=2_000_000, eigenmittel=1_000_000, hypothek_faellig="2030-07-01",
                       strategie={"saron": 0.0, "marge_saron": 1.0, "fest": {5: 1.8, 10: 2.0}, "horizont_jahre": 10})
    s = hy.vergleichen(k, None, date(2026, 11, 8))
    e = {x.name: x for x in s.ergebnisse}
    assert s.betrag == 1_000_000 and s.start == date(2030, 7, 1)
    fest10 = e["Fest 10 Jahre"]
    assert fest10.kosten["tief"] == fest10.kosten["stress"] == 200_000             # 10 Jahre × 2 %
    saron = e["SARON 100 %"]
    assert saron.kosten["tief"] == 100_000 and saron.kosten["stress"] > fest10.kosten["stress"]
    assert s.empfehlung == "Fest 10 Jahre"                                         # tiefste Kosten im Stress
    assert e["Fest 5 Jahre (verlängert)"].kosten["tief"] < e["Fest 5 Jahre (verlängert)"].kosten["stress"]  # Verlängerung zum Marktzins
    assert 10 in s.forward_satz and s.forward_satz[10] > 2.0                       # Forward mit Aufschlag
    assert hy.saron_pfad(0.0, 3.0, 3, 5) == [1.0, 2.0, 3.0, 3.0, 3.0]


# ---------------------------------------------------------------- Bank-Import

def test_bankimport_raiffeisen(db):
    from pathlib import Path

    import bankimport as bi
    inhalt = (Path(__file__).parent / "bank" / "raiffeisen.csv").read_bytes()
    a = bi.analysieren(inhalt, "raiffeisen.csv")
    assert a.bank == "Raiffeisen" and a.iban == "CH1280808001234567890" and a.konto_vorschlag == "Raiffeisen …7890"
    assert a.monatssaldi == {"2026-09": ("2026-09-30", 18000.0), "2026-10": ("2026-10-31", 25000.0)}
    assert a.einnahmen == 18000 and a.ausgaben == 3000
    a, n = bi.aus_datei(db, inhalt, "raiffeisen.csv", person="Person 1")
    assert n == 2 and vm.nettovermoegen(db)["total"] == 25000


def test_bankimport_ohne_saldo(db):
    from pathlib import Path

    import bankimport as bi
    inhalt = (Path(__file__).parent / "bank" / "postfinance_ohne_saldo.csv").read_bytes()
    a = bi.analysieren(inhalt, "pf.csv")
    assert a.iban == "CH9300762011623852957" and not a.monatssaldi and a.einnahmen == 12000 and a.ausgaben == 420.5
    with pytest.raises(ValueError):
        bi.aus_datei(db, inhalt, "pf.csv")
    _, n = bi.aus_datei(db, inhalt, "pf.csv", konto="Privatkonto", endsaldo=20_000)
    assert n == 3
    saldi = {r["datum"]: r["betrag"] for r in db.execute("SELECT datum, betrag FROM saldi")}
    assert saldi == {"2026-08-25": 14300.0, "2026-09-10": 14000.0, "2026-10-25": 20000.0}


def test_bankimport_latin1_und_komma():
    import bankimport as bi
    csv = "Datum,Beschreibung,Betrag,Saldo\n01.11.2026,Überweisung,-50.00,950.00\n".encode("cp1252")
    a = bi.analysieren(csv, "konto.csv")
    assert a.letzter == ("2026-11-01", 950.0)
    with pytest.raises(ValueError):
        bi.analysieren(b"nur;irgendwas\n1;2\n")


# ---------------------------------------------------------------- Erinnerungen

def test_erinnerungen(k, db, tmp_path):
    import erinnerungen as er
    heute = date(2026, 11, 8)
    k["personen"][0]["pk"]["einkauf_geplant"] = [{"jahr": 2026, "betrag": 20000}]
    k["wohnen"].update(aktiv=True, hypothek_faellig="2028-07-01")
    k["erinnerungen"] = {"eigene": [{"titel": "Depot prüfen", "datum": "11-20", "vorlauf": 30},
                                    {"titel": "Zu weit weg", "datum": "2027-06-30"}]}
    titel = {e.titel for e in er.alle(k, db, heute)}
    assert {"3a einzahlen – Person 1", "3a einzahlen – Person 2", "PK-Einkauf überweisen – Person 1",
            "Krankenkasse vergleichen", "Hypothek per 01.07.2028 vorbereiten", "Depot prüfen", "Vermögen erfassen"} <= titel
    assert "Zu weit weg" not in titel
    kvg = next(e for e in er.alle(k, db, heute) if e.titel == "Krankenkasse vergleichen")
    assert kvg.faellig == date(2026, 11, 30) and er.status(kvg, heute) == "gelb"
    er.erledigen(db, kvg.schluessel)
    assert "Krankenkasse vergleichen" not in {e.titel for e in er.alle(k, db, heute)}
    assert any(e.titel.startswith("Steuererklärung 2025 einreichen") for e in er.alle(k, db, date(2026, 3, 1)))


def test_benachrichtigung_einmal_pro_stufe(k, db):
    import erinnerungen as er
    gesendet = []
    k["erinnerungen"] = {"benachrichtigung": "mobile_app_test", "eigene": [{"titel": "Test", "datum": "2026-11-20"}]}
    heute = date(2026, 11, 8)
    erste = er.benachrichtigen(k, db, heute, senden=lambda d, x: gesendet.append((d, x)))
    assert erste and all(d == "notify.mobile_app_test" for d, _ in gesendet)
    assert er.benachrichtigen(k, db, heute, senden=lambda d, x: gesendet.append((d, x))) == []      # nicht doppelt
    faellig = er.benachrichtigen(k, db, date(2026, 11, 20), senden=lambda d, x: gesendet.append((d, x)))
    assert any("Fällig: Test" in t for t in faellig)
    k["erinnerungen"]["benachrichtigung"] = ""
    assert er.benachrichtigen(k, db, heute, senden=lambda d, x: 1 / 0) == []



# ---------------------------------------------------------------- Fristen und Steueroptimierung

def test_fristen_kanton(k):
    import kantone
    k["haushalt"]["kanton"] = "BE"
    f = kantone.steuererklaerung(k)
    assert (f.frist, f.gewaehlt, f.quelle) == ("03-15", "03-15", "kanton") and f.erstreckung == "11-15"
    k["haushalt"]["kanton"] = "zg"
    assert kantone.steuererklaerung(k).frist == "04-30"
    k["erinnerungen"] = {"steuererklaerung_frist": "05.04.", "fristerstreckung": "2026-09-30"}
    f = kantone.steuererklaerung(k)
    assert (f.frist, f.gewaehlt, f.quelle) == ("04-05", "09-30", "erstreckt")
    k["erinnerungen"] = {"steuererklaerung_frist": "03-31"}
    k["haushalt"]["kanton"] = "BL"
    assert kantone.steuererklaerung(k).quelle == "kanton"                        # alter Standardwert = Kantonsfrist
    k["haushalt"]["kanton"] = "LU"
    k["erinnerungen"] = {}
    f = kantone.steuererklaerung(k)
    assert f.pruefen and f.gewaehlt == "03-31" and f.quelle == "standard"
    assert len(kantone.FRISTEN) == 26


def test_erinnerung_steuererklaerung_nach_kanton(k, db):
    import erinnerungen as er
    k["haushalt"]["kanton"] = "BE"
    titel = {e.titel: e for e in er.alle(k, db, date(2026, 2, 1))}
    e = next(v for t, v in titel.items() if t.startswith("Steuererklärung 2025"))
    assert e.faellig == date(2026, 3, 15) and "Bern" in e.titel and "Erstreckung bis spätestens 15.11." in e.text
    k["erinnerungen"] = {"fristerstreckung": "09-30"}
    e = next(x for x in er.alle(k, db, date(2026, 9, 1)) if x.titel.startswith("Steuererklärung 2025"))
    assert e.faellig == date(2026, 9, 30) and "erstreckte" in e.titel


def test_erinnerungen_steueroptimierung(konkubinat, db, tmp_path):
    import erinnerungen as er
    import steuerdokumente as sd
    from policen import STEUERERKLAERUNG
    k = konkubinat
    k["personen"][0]["pk"].update(einkauf_potenzial=60_000, einkauf_geplant=[])
    k["personen"][1]["pk"].update(einkauf_potenzial=0)
    k["personen"][0]["saeule3a"]["konten"] = 1
    k["wohnen"].update(aktiv=True, eigenmietwert=20_000)
    sd.hochladen(db, tmp_path, "erklaerung.pdf", pdf(STEUERERKLAERUNG))           # 2025: 3a-Abzug 5'000
    liste = {e.titel: e for e in er.alle(k, db, date(2026, 11, 9))}
    pk = liste["PK-Einkauf 2026 prüfen – Person 1"]
    assert "Optimal wären rund CHF" in pk.text and pk.seite == "szenarien"
    assert "PK-Einkauf 2026 prüfen – Person 2" not in liste
    luecke = liste["3a-Lücke 2025 nachzahlen – Person 1"]
    assert "2'258" in luecke.text
    assert "Liegenschaftsunterhalt planen" in liste and "Weiteres 3a-Konto eröffnen – Person 1" in liste
    k["personen"][0]["pk"]["einkauf_geplant"] = [{"jahr": 2026, "betrag": 20_000}]
    liste = {e.titel for e in er.alle(k, db, date(2026, 11, 9))}
    assert "PK-Einkauf überweisen – Person 1" in liste and "PK-Einkauf 2026 prüfen – Person 1" not in liste
    assert "Liegenschaftsunterhalt planen" not in {e.titel for e in er.alle(k, db, date(2029, 11, 9))}


# ---------------------------------------------------------------- Krankenkasse

def test_kostenbeteiligung():
    import krankenkasse as kk
    assert kk.kostenbeteiligung(0, 2500, False) == 0
    assert kk.kostenbeteiligung(1000, 2500, False) == 1000
    assert kk.kostenbeteiligung(5000, 300, False) == 300 + 470
    assert kk.kostenbeteiligung(50_000, 2500, False) == 2500 + 700
    assert kk.kostenbeteiligung(50_000, 0, True) == 350


def test_franchise_optimierung():
    import krankenkasse as kk
    p = kk.Person("A", False, 300, 500.0, 500.0, "standard", True, True)
    pr, geschaetzt = kk.praemien(p)
    assert geschaetzt and pr[300] == 6000 and pr[2500] == 6000 - 0.7 * 2200          # Höchstrabatt
    e = kk.rechnen(p)
    assert e.beste == 2500 and e.ersparnis == round((6000 + 300 + 20) - (6000 - 1540 + 500))  # inkl. Selbstbehalt 10 %
    assert 1500 < e.break_even[0][2] < 3000                                             # tiefe Franchise lohnt sich erst ab …
    assert any("Telmed" in h for h in e.hinweise) and any("sistieren" in h for h in e.hinweise)
    krank = kk.rechnen(kk.Person("B", False, 2500, 371.67, 8000.0, "hausarzt", False, True))
    assert krank.beste == 300
    offerte = kk.Person("C", False, 300, 500.0, 0, "hausarzt", False, True, angebote={2500: 420})
    assert kk.praemien(offerte)[0][2500] == 420 * 12


def test_krankenkasse_aus_police(k, db, tmp_path):
    import krankenkasse as kk
    from policen import KVG
    vi.hochladen(db, tmp_path, "kvg.pdf", pdf(KVG))
    personen = kk.personen(k, vi.alle(db))
    p1 = next(p for p in personen if p.name == "Person 1")
    assert p1.franchise == 300 and p1.praemie_monat == pytest.approx(412.5) and p1.unfall
    assert any(p.kind for p in personen)
    assert [e.person.name for e in kk.haushalt(k, vi.alle(db))] == ["Person 1"]


# ---------------------------------------------------------------- Frühpensionierung

def test_fruehpension(k):
    import fruehpension as fp
    k["personen"] = k["personen"][:1]
    k["haushalt"]["zivilstand"] = "ledig"
    p = k["personen"][0]
    p["geburtsdatum"] = "1970-01-01"
    p["ahv"]["beitragsjahre_bisher"] = 44
    p["pk"].update(ausweis_alterskapital=800_000, ausweis_altersrente=48_000, kapitalbezug_anteil=0)
    k["annahmen"]["teuerung"] = 0
    v = {x.alter: x for x in fp.vergleich(k, 300_000, heute=date(2026, 11, 9))}
    assert v[65].pk_rente == 48_000 and v[65].ueberbrueckung == 0 and v[65].ahv_ab == 65
    assert v[60].ahv_ab == 63 and v[60].ueberbrueckung > 0 and v[60].pk_rente < v[65].pk_rente
    assert v[63].ahv == round(v[65].ahv * (1 - 2 * 0.068))                               # 2 Jahre Vorbezug
    assert v[58].einkommen < v[62].einkommen < v[65].einkommen
    assert fp.ahv_ne_beitrag(100_000, 0, k["kennzahlen"]) == 530
    assert fp.ahv_ne_beitrag(20_000_000, 0, k["kennzahlen"]) == 26_500
    k["haushalt"]["bedarf_ruhestand"] = v[62].einkommen
    assert fp.fruehestes_ohne_luecke(fp.vergleich(k, 300_000, heute=date(2026, 11, 9))) == 62


# ---------------------------------------------------------------- Anlage-Check

def test_anlage_check(k, db):
    import anlage as an
    k["wohnen"].update(aktiv=True, kaufpreis=2_000_000, eigenmittel=1_000_000, hypothek_faellig="2030-07-01",
                       amortisation_ziel=300_000, amortisation_max=300_000, reserve=50_000, verpfaendet=[],
                       steuer_bezug_verpfaendet=0)
    for p in k["personen"]:
        p["sparen_monat"] = 0
        p["pk"]["einkauf_geplant"] = []
    for name, art, betrag in (("Konto", "bank", 600_000), ("Depot", "depot", 50_000), ("Krypto", "krypto", 60_000)):
        vm.saldo_setzen(db, vm.konto_anlegen(db, name, art), "2026-11-01", betrag)
    c = an.pruefen(k, db, date(2026, 11, 9))
    namen = [t.name for t in c.toepfe]
    assert namen[0] == "Notreserve" and namen[-1] == "Langfristig" and "Amortisation 07.2030" in namen
    assert c.toepfe[1].betrag == 300_000 and c.anlegbar == 600_000 + 50_000 - 50_000 - 300_000
    assert sum(t.betrag for t in c.toepfe) == c.finanz_total
    assert c.krypto_anteil == pytest.approx(60 / 710 * 100, abs=0.1)
    assert any("Krypto" in h for h in c.hinweise) and any("ohne Zweck" in h for h in c.hinweise)
    assert c.opportunitaet == round((300_000 - 50_000) * (3.5 - 0.3) / 100)


# ---------------------------------------------------------------- Sensoren

def test_sensoren(k, daten, db):
    import sensoren
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Konto", "bank"), "2026-11-01", 100_000)
    gesendet = {}
    werte = sensoren.schreiben(k, db, senden=lambda e, n: gesendet.__setitem__(e, n), heute=date(2026, 11, 9))
    ids = set(gesendet)
    assert not sensoren.status().get("bereich_fehler"), sensoren.status()["bereich_fehler"]
    assert {"sensor.finanz_nettovermoegen", "sensor.finanz_ampel", "sensor.finanz_naechste_frist",
            "sensor.finanz_steuererklaerung_frist", "sensor.finanz_pensionsluecke", "sensor.finanz_erinnerungen"} <= ids
    nv = gesendet["sensor.finanz_nettovermoegen"]
    assert nv["state"] == "100000" and nv["attributes"]["unit_of_measurement"] == "CHF"
    assert nv["attributes"]["device_class"] == "monetary" and nv["attributes"]["friendly_name"] == "Finanzen Nettovermögen"
    ampel = gesendet["sensor.finanz_ampel"]
    assert ampel["state"] in ("gruen", "gelb", "rot") and ampel["attributes"]["device_class"] == "enum"
    assert "bereiche" in ampel["attributes"]
    assert gesendet["sensor.finanz_saldi_alter"]["state"] == "8"
    assert sensoren.status()["anzahl"] == len(werte) and not sensoren.status()["fehler"]
    k["sensoren"] = {"aktiv": True, "praefix": "geld"}
    gesendet.clear()
    sensoren.schreiben(k, db, senden=lambda e, n: gesendet.__setitem__(e, n))
    assert all(e.startswith("sensor.geld_") for e in gesendet)


def test_sensoren_fehler_und_aus(k, daten, db):
    import sensoren

    def kaputt(e, n):
        raise RuntimeError("kein Token")
    sensoren.schreiben(k, db, senden=kaputt)
    assert sensoren.status()["fehler"] == "kein Token"
    k["sensoren"] = {"aktiv": False}
    assert sensoren.schreiben(k, db, senden=kaputt) == []


# ---------------------------------------------------------------- Nachlass

def test_erbschaftssteuer_bl(konkubinat):
    import nachlass as nl
    k = konkubinat
    k["haushalt"]["kanton"] = "BL"
    k["nachlass"] = {"zusammen_seit": 2015}
    steuer, text, geprueft = nl.partner_steuer(k, 330_000, date(2026, 11, 9))
    assert steuer == 45_000 and geprueft and "15 %" in text                    # (330'000 − 30'000) × 15 %
    k["nachlass"] = {"zusammen_seit": 2024}
    assert nl.partner_steuer(k, 110_000, date(2026, 11, 9))[0] == 30_000         # (110'000 − 10'000) × 30 %
    k["nachlass"] = {"erbschaftssteuer": {"satz": 10, "freibetrag": 0}}
    assert nl.partner_steuer(k, 100_000)[0] == 10_000
    k["nachlass"] = {}
    k["haushalt"]["kanton"] = "XY"
    assert nl.partner_steuer(k, 100_000)[2] is False


def test_nachlass_faelle(konkubinat, db):
    import nachlass as nl
    k = konkubinat
    k["haushalt"]["kanton"] = "BL"
    k["nachlass"] = {"zusammen_seit": 2015}
    k["wohnen"].update(aktiv=True, kaufpreis=2_000_000, eigenmittel=800_000)
    vm.saldo_setzen(db, vm.konto_anlegen(db, "P1", "bank", "Person 1"), "2026-11-01", 200_000)
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Gemeinsam", "bank", ""), "2026-11-01", 100_000)
    f1, f2 = nl.faelle(k, db, date(2026, 11, 9))
    assert f1.verstorben == "Person 1" and f1.nachlass == 200_000 + 50_000 + 400_000 and f1.davon_liegenschaft == 400_000
    assert f1.erbe_partner_ohne == 0 and f1.erbe_partner_mit == 325_000 and f1.erbe_kinder_mit == 325_000
    assert f1.steuer_partner_mit == round((325_000 - 30_000) * 0.15)
    assert f1.ausgleich_haus == 400_000                                          # ohne Testament alles auszahlen
    assert any("Ohne Testament" in h for h in f1.hinweise)
    k["nachlass"]["checkliste"] = {"testament": {"Person 1": True, "Person 2": False}}
    f1, _ = nl.faelle(k, db, date(2026, 11, 9))
    assert f1.ausgleich_haus == 400_000 - 325_000
    verh = copy.deepcopy(k)
    verh["haushalt"]["zivilstand"] = "verheiratet"
    f1v, _ = nl.faelle(verh, db, date(2026, 11, 9))
    assert f1v.erbe_partner_ohne == 325_000 and f1v.erbe_partner_mit == round(650_000 * 0.75) and f1v.steuer_partner_mit == 0
    liste = nl.checkliste(k)
    assert liste[0][0] == "testament" and liste[0][3] == {"Person 1": True, "Person 2": False}


def test_ampel_nachlass(konkubinat, daten, db):
    import ampel as am
    a = {x.bereich: x for x in am.bewerten(konkubinat, db)}
    assert a["Nachlass"].status == am.ROT
    konkubinat["nachlass"] = {"checkliste": {s: {"Person 1": True, "Person 2": True} for s, _, _ in
                                             __import__("nachlass").CHECKLISTE}}
    a = {x.bereich: x for x in am.bewerten(konkubinat, db)}
    assert a["Nachlass"].status == am.GRUEN


# ---------------------------------------------------------------- Individualbesteuerung und Vermögenssteuer

def test_heirat_individualbesteuerung(konkubinat, db):
    import szenarien as sz
    k = konkubinat
    for p in k["personen"]:
        p["lohn_brutto"], p["ahv"]["beitragsjahre_bisher"] = 120_000, 44
    k["kennzahlen"]["individualbesteuerung_ab"] = 2030
    h = sz.heirat_vergleich(k, db, date(2026, 11, 9))
    assert h.ib_jahr == 2030 and h.jahre_ehetarif == 4 and h.jahre_bis_pension > h.jahre_ehetarif
    assert h.kapital_diff_ib == 0                                                # Pension nach 2030
    assert h.bilanz_mit_ib == pytest.approx(-h.steuer_diff * 4 + h.ahv_diff * h.jahre_ruhestand)
    assert h.qualitativ[0].startswith("Individualbesteuerung")


def test_vermoegenssteuer(k):
    import steuern as st
    k["steuern"].update(steuerbar_vermoegen=800_000, vermoegenssteuer=2_400)
    s = st.steuern_heute(k)
    assert s["vermoegen"] == 2400 and s["total_inkl"] == s["total"] + 2400
    k["steuern"]["vermoegenssteuer"] = 0
    k["kennzahlen"]["vermoegen_promille"] = 2.5
    assert st.steuern_heute(k)["vermoegen"] == 2000


def test_steuerdokument_vermoegenssteuer():
    import steuerdokumente as sd
    text = ("Veranlagungsverfügung Steuerperiode 2025\nSteuerbares Einkommen Staat 141'200 Bund 145'000\n"
            "Steuerbares Vermögen 600'000\nStaatssteuer Einkommen 14'000.00\nStaatssteuer Vermögen 1'500.00\n"
            "Gemeindesteuer 9'000.00\nVermögenssteuer total 2'100.00\n")
    w = sd.erkennen(text)["werte"]
    assert w["staatssteuer"] == 14_000 and w["vermoegenssteuer"] == 2_100 and w["steuerbares_vermoegen"] == 600_000


def test_tausender_nur_zahlen():
    from tausender import TS
    assert f"Damit A kann, wären CHF {555000:,.0f} und {1234.5:,.2f}" >> TS == "Damit A kann, wären CHF 555'000 und 1'234.50"
    assert "1,5 Jahre, 12,345" >> TS == "1,5 Jahre, 12'345"


def test_teuerung_pensionsluecke(k):
    import vorsorge as vs
    k0 = copy.deepcopy(k)
    k0["annahmen"]["teuerung"] = 0
    k["annahmen"]["teuerung"] = 2.0
    l0, l2 = vs.pensionsluecke(k0, 100_000, 2026), vs.pensionsluecke(k, 100_000, 2026)
    jahre = l2.jahr - 2026
    assert l2.kaufkraft == round(1 / 1.02 ** jahre, 4)
    assert l2.pk_rente == round(l0.pk_rente * 1 / 1.02 ** jahre) and l2.pk_rente_nominal == l0.pk_rente
    assert l2.ahv == l0.ahv                                   # Mischindex hält die Kaufkraft (ohne Reallohnwachstum)
    assert l2.kapitalverzehr < l0.kapitalverzehr              # reale Rendite tiefer, Kapital abgezinst
    assert l2.luecke_spaeter >= l2.luecke and l2.luecke_mittel >= l2.luecke
    assert l0.luecke_mittel == l0.luecke and len(l2.verlauf) == k["haushalt"]["entnahme_jahre"]
    assert abs(l2.verlauf[1][2] - l2.pk_rente / 1.02) <= 1      # PK-Rente verliert jedes Jahr Kaufkraft


# ---------------------------------------------------------------- Budget

def _auszug(konto_text: str, zeilen: list[tuple[str, str, float]]) -> bytes:
    kopf = f"Konto;{konto_text}\n\nBuchungsdatum;Buchungstext;Betrag;Saldo\n"
    saldo, rumpf = 10_000.0, []
    for tag, text, betrag in zeilen:
        saldo += betrag
        rumpf.append(f"{tag};{text};{betrag:.2f};{saldo:.2f}")
    return (kopf + "\n".join(rumpf) + "\n").encode("utf-8")


def _jahr_buchungen():
    z = []
    for m in range(1, 13):
        z += [(f"25.{m:02d}.2025", "Lohnzahlung Arbeitgeber AG", 8000.0),
              (f"01.{m:02d}.2025", "Hypothekarzins Migros Bank", -900.0),
              (f"05.{m:02d}.2025", "Einkauf MIGROS Filiale", -600.0),
              (f"06.{m:02d}.2025", "CSS Kranken-Versicherung", -500.0),
              (f"07.{m:02d}.2025", "Zahlung an Muster GmbH", -400.0),
              (f"10.{m:02d}.2025", "Übertrag auf Sparkonto", -1000.0),
              (f"12.{m:02d}.2025", "VIAC Säule 3a", -600.0),
              (f"28.{m:02d}.2025", "Coop Pronto Tankstelle", -100.0)]
    z.append(("31.12.2025", "Kontoführung", -5.0))
    return z


def test_budget_kategorien():
    import budget as bu
    assert bu.kategorie("Einkauf MIGROS Basel", -50) == "Lebensmittel"
    assert bu.kategorie("Lohnzahlung März", 8000) == bu.LOHN
    assert bu.kategorie("Rückerstattung CSS", 120) == bu.EINNAHMEN
    assert bu.kategorie("VIAC 3a Einzahlung", -600) == bu.SPAREN
    assert bu.kategorie("Steuerverwaltung BL Rate", -1500) == "Steuern"
    assert bu.kategorie("Zahlung an Muster GmbH", -400) == bu.UEBRIGES
    assert bu.kategorie("Zahlung an Muster GmbH", -400, {"muster gmbh": "Wohnen"}) == "Wohnen"


def test_budget_auswertung(k, db):
    import bankimport as bi
    import budget as bu
    inhalt = _auszug("CH93 0076 2011 6238 5295 7", _jahr_buchungen())
    b = bi.buchungen_lesen(inhalt)
    assert len(b) == 97 and b[0] == ("2025-01-25", 8000.0, "Lohnzahlung Arbeitgeber AG")
    assert bu.speichern(db, "Privatkonto", b, k) == 97
    assert bu.speichern(db, "Privatkonto", b, k) == 0                 # doppelter Import erkannt
    # Gegenbuchung auf dem Sparkonto → Umbuchung
    bu.speichern(db, "Sparkonto", [(f"2025-{m:02d}-10", 1000.0, "Gutschrift")
                                   for m in range(1, 13)], k)
    k["personen"][0]["sparen_monat"] = 3000
    for p in k["personen"][1:]:
        p["sparen_monat"] = 0
    a = bu.auswerten(k, db, heute=date(2026, 1, 15))
    assert a.monate == 12 and a.einnahmen == 96_000
    assert a.ausgaben == 12 * (900 + 600 + 500 + 400 + 100) + 5
    assert a.sparen_konto == 12 * 600 and a.umbuchungen == 24
    kat = {n: j for n, j, _ in a.kategorien}
    assert kat["Wohnen"] == 10_800 and kat["Krankenkasse"] == 6000 and kat[bu.UEBRIGES] == 4800
    assert a.unbekannt[0][0].lower().startswith("zahlung an muster")
    assert any("mehr gespart" in h for h in a.hinweise)                 # rund 6'100 pro Monat statt 3'000 geplant
    import ampel as am
    assert bu.status(a) in (am.GRUEN, am.GELB)
    erg = bu.sparen_uebernehmen(k, a)
    assert sum(erg.values()) == pytest.approx((a.ueberschuss + a.sparen_konto) / 12, abs=100)
    k.setdefault("budget", {})["regeln"] = {"muster gmbh": "Wohnen"}
    assert bu.neu_kategorisieren(db, k) == 12
    assert bu.auswerten(k, db, heute=date(2026, 1, 15)).unbekannt == []


# ---------------------------------------------------------------- Zuzug in die Schweiz

def _zuzug(k, datum, **mehr):
    p = k["personen"][0]
    p["geburtsdatum"] = "1985-06-15"
    p["ahv"]["beitragsjahre_bisher"] = 0
    p["zuzug"] = {"datum": datum, **mehr}
    return p


def test_zuzug_ahv(k):
    import vorsorge as vs
    import zuzug as zz
    k["haushalt"]["zivilstand"] = "ledig"
    vorher = vs.ahv(k, 2026)[0]
    p = _zuzug(k, "2016-04-01", land="Deutschland")
    # Beitragspflicht ab 1.1.2006 → ab Zuzug 1.4.2016 bis 1.6.2050: 34 Jahre
    assert zz.ahv_moegliche_jahre(p) == 34 and zz.ahv_bisher_schaetzen(p, 2026) == 9
    nachher = vs.ahv(k, 2026)[0]
    assert nachher.beitragsjahre == 34 and nachher.rente_monat < vorher.rente_monat
    p["ahv"]["beitragsjahre_bisher"] = 10                  # IK-Auszug hat Vorrang, Obergrenze bleibt
    assert vs.ahv(k, 2026)[0].beitragsjahre == 34
    k["haushalt"]["kinder"] = [{"geburtsjahr": 2012}]
    assert vs.erziehungsjahre(p, k["haushalt"]["kinder"]) == len(range(2016, 2029))
    h = " ".join(zz.hinweise(k, date(2026, 11, 9)))
    assert "10 fehlen" in h and "Freizügigkeitsabkommen" in h


def test_zuzug_pk_einkauf(k):
    import szenarien as sz
    import vorsorge as vs
    import zuzug as zz
    p = _zuzug(k, "2024-03-01")
    p["lohn_brutto"] = 100_000
    p["pk"]["einkauf_potenzial"] = 200_000
    assert zz.einkauf_limit(p, 2026) == 20_000 and zz.einkauf_limit(p, 2029) == 20_000 and zz.einkauf_limit(p, 2030) is None
    plan = sz.einkauf_optimieren(k, p["name"], 0, 2026, 2030, schritt=5000, heute=date(2026, 1, 1))
    assert all(plan.plan.get(j, 0) <= 20_000 for j in (2026, 2027, 2028))
    assert any("Art. 60b" in h for h in plan.hinweise)
    p["pk"]["einkauf_geplant"] = [{"jahr": 2026, "betrag": 50_000}]
    assert any("60b" in w for w in vs.pk(p, k).warnungen)
    p["zuzug"]["pk_vorher_ch"] = True
    assert zz.einkauf_limit(p, 2026) is None


def test_zuzug_quellensteuer_und_fristen(k):
    import erinnerungen as er
    import zuzug as zz
    k["haushalt"]["zivilstand"] = "ledig"
    p = _zuzug(k, "2026-10-01", bewilligung="B")
    p["lohn_brutto"] = 90_000
    assert zz.quellensteuer(p, k)
    titel = [e.titel for e in zz.erinnerungen(k, date(2026, 11, 9))]
    assert any("Krankenkasse" in t for t in titel) and any("Gemeinde" in t for t in titel)
    assert not any("Veranlagung" in t for t in titel)       # 2025 noch nicht in der Schweiz
    titel = [e.titel for e in zz.erinnerungen(k, date(2027, 2, 1))]
    assert any("Veranlagung beantragen" in t for t in titel)
    p["zuzug"]["nov_beantragt"] = True
    assert not any("Veranlagung" in e.titel for e in zz.erinnerungen(k, date(2027, 2, 1)))
    k["haushalt"]["zivilstand"] = "verheiratet"              # Partner ohne B/L: ordentliche Besteuerung
    assert not zz.quellensteuer(p, k)


def test_zuzug_rente_ausland(k):
    import vorsorge as vs
    k["annahmen"]["teuerung"] = 0
    ohne = vs.pensionsluecke(k, 0, 2026)
    p = _zuzug(k, "2016-04-01", rente_ausland_jahr=6000, rente_ausland_ab=67)
    mit = vs.pensionsluecke(k, 0, 2026)
    assert mit.verlauf[-1][4] == 6000
    if mit.jahr >= 1985 + 67:
        assert mit.ausland == 6000
    else:
        assert mit.ausland == 0 and mit.luecke_mittel <= ohne.luecke_mittel + 10_000


# ---------------------------------------------------------------- Kinder

def _kinder(k, *kinder):
    k["haushalt"]["kinder"] = list(kinder)
    return k


def test_kinder_grundlagen(k):
    import kinder as ki
    _kinder(k, {"name": "A", "geburtsdatum": "2010-03-01"},
            {"name": "B", "geburtsdatum": "2020-08-15", "ausbildung_bis": 25, "betreuung_jahr": 18000, "betreuung_bis": 12},
            {"name": "C", "geburtsjahr": 2004})                 # alte Form
    assert [ki.alter(c, 2026) for c in ki.liste(k)] == [16, 6, 22]
    assert ki.anzahl(k, 2026) == 2                               # C über 18 ohne Ausbildung
    assert ki.anzahl(k, 2028) == 1 and ki.anzahl(k, 2045) == 0 and ki.anzahl(k, 2044) == 1
    a, b, _ = ki.liste(k)
    assert ki.zulage_jahr(a, 2026) == 268 * 12 and ki.zulage_jahr(b, 2026) == 215 * 12
    assert ki.betreuung_jahr(b, 2026) == 18000 and ki.betreuung_jahr(b, 2032) == 0
    u = ki.uebersicht(k, date(2026, 11, 9))
    assert u.ende_jahr == 2044 and u.jahre[0].steuer_kinder > 2 * 263
    assert u.jahre[0].abzug_betreuung_bund == 18000
    import steuern as st
    assert st.anzahl_kinder(k, 2026) == 2


def test_kinder_konkubinat_und_ahv(konkubinat):
    import kinder as ki
    import steuern as st
    import vorsorge as vs
    k = konkubinat
    p1, p2 = (p["name"] for p in k["personen"][:2])
    _kinder(k, {"name": "A", "geburtsdatum": "2018-01-01", "obhut": p2, "gutschrift": p2},
            {"name": "B", "geburtsdatum": "2016-01-01", "eltern": p1})
    e = {x.name: x.kinder for x in st.einheiten(k)}
    assert e[p2] == 1 and e[p1] == 1                             # B: eigenes Kind von p1 → Elterntarif bei p1
    assert ki.gutschrift_anteil(k, ki.liste(k)[0], p1) == 0 and ki.gutschrift_anteil(k, ki.liste(k)[0], p2) == 1
    assert ki.gutschrift_anteil(k, ki.liste(k)[1], p2) == 0
    ej1 = vs.erziehungsjahre(k["personen"][0], k["haushalt"]["kinder"], k)
    ej2 = vs.erziehungsjahre(k["personen"][1], k["haushalt"]["kinder"], k)
    assert ej1 == 16 and ej2 == 16
    # Nachlass: Pflichtteil nur für eigene Nachkommen
    assert len(ki.eigene(k, p1)) == 2 and len(ki.eigene(k, p2)) == 1


def test_kinder_risiko_kk_erinnerungen(k, db):
    import kinder as ki
    import krankenkasse as kk
    import versicherungen as vi
    import vorsorge as vs
    p1 = k["personen"][0]["name"]
    jahr = date.today().year
    _kinder(k, {"name": "Klein", "geburtsdatum": f"{jahr - 3}-01-01"}, {"name": "Gross", "geburtsdatum": f"{jahr - 21}-01-01"})
    r = vi.risiko(k, vs.ahv(k, jahr))[0]
    assert r.iv_kinder_ahv > 0
    namen = {p.name: p.kind for p in kk.personen(k, [])}
    assert namen["Klein"] is True and namen["Gross"] is False
    g = ki.liste(k)[0]
    titel = [e.titel for e in ki.erinnerungen(k, date(ki.geburtsjahr(g) + 16, 1, 1) - __import__("datetime").timedelta(days=30))]
    assert any("Ausbildungszulage" in t for t in titel)
    assert ki.anzahl(k, person=p1) == 1


def test_kinderrente_pensionsluecke(k):
    import vorsorge as vs
    k["annahmen"]["teuerung"] = 0
    gj = int(str(k["personen"][0]["geburtsdatum"])[:4])
    pj = max(vs.pensionsjahr(p) for p in k["personen"])
    _kinder(k, {"name": "Spät", "geburtsdatum": f"{pj - 10}-01-01"})
    l = vs.pensionsluecke(k, 0, 2026)
    assert l.kinderrenten > 0 and gj
    _kinder(k)
    assert vs.pensionsluecke(k, 0, 2026).kinderrenten == 0


# ---------------------------------------------------------------- Teilzeit, Steuererklärung, Notfallordner

def test_teilzeit(k):
    import teilzeit as tz
    p = k["personen"][1]
    p["pensum"], p["lohn_brutto"] = 100, 100_000
    _kinder(k, {"name": "A", "geburtsdatum": "2024-03-01", "betreuung_jahr": 24000})
    e = tz.rechnen(k, p["name"], 60, 2027, 2030, heute=date(2026, 11, 9))
    assert len(e.jahre) == 4 and e.jahre[0].brutto == 40_000
    j = e.jahre[0]
    assert 30_000 < j.netto < 40_000 and j.betreuung == round(24000 * 0.4) and j.steuern > 0
    assert j.saldo == -j.netto + j.steuern + j.betreuung
    assert e.pk_kapital_weniger > 0 and e.pro_tag > 0
    # unter die BVG-Eintrittsschwelle
    e2 = tz.rechnen(k, p["name"], 20, 2027, 2027, betreuung=0, heute=date(2026, 11, 9))
    assert any("Eintrittsschwelle" in h for h in e2.hinweise) and e2.jahre[0].betreuung == 0


def test_steuererklaerung(k, db):
    import steuererklaerung as se
    import vermoegen as vm
    a = vm.konto_anlegen(db, "Privatkonto", "bank")
    b = vm.konto_anlegen(db, "Depot", "depot")
    vm.saldo_setzen(db, a, "2025-12-31", 12_000)
    vm.saldo_setzen(db, b, "2025-06-30", 50_000)
    k["personen"][0]["pk"]["einkauf_geplant"] = [{"jahr": 2025, "betrag": 10_000}]
    _kinder(k, {"name": "A", "geburtsdatum": "2006-05-01", "ausbildung_bis": 25, "betreuung_jahr": 0})
    c = se.erstellen(k, db, 2025, date(2026, 2, 1))
    p = {x.schluessel: x for x in c.punkte}
    assert p[f"konto_{a}"].status == "daten" and p[f"konto_{b}"].status == "fehlt"
    assert "10'000" in p[f"pk_{k['personen'][0]['name']}"].wert
    assert "Ausbildungsbestätigung" in p["kind_A"].beleg
    assert c.frist.year == 2026 and c.offen == c.total
    se.erledigt_setzen(db, 2025, [f"konto_{a}"], [x.schluessel for x in c.punkte])
    assert se.erstellen(k, db, 2025, date(2026, 2, 1)).offen == c.total - 1
    assert se.standard_jahr(date(2026, 11, 9)) == 2026 and se.standard_jahr(date(2026, 3, 1)) == 2025


def test_notfall(k):
    import notfall as nf
    assert nf.vollstaendigkeit(k)[0] == 0
    k["notfall"] = {"kontakte": [{"rolle": "Hausarzt", "name": "Dr. Muster", "telefon": "061"}],
                    "ablage": {"testament": "Notar", "passwoerter": "Umschlag im Safe"}}
    assert nf.vollstaendigkeit(k) == (3, len(nf.ABLAGE) + 3)
    k["haushalt"]["zivilstand"] = "ledig"
    assert any("Konkubinat" in s.was for s in nf.erste_schritte(k))


def test_dokumentation_aktuell():
    """Diagramme gerendert und im README, Changelog zur Version, alle Module und Seiten dokumentiert."""
    import importlib.util
    from pathlib import Path
    pfad = Path(__file__).resolve().parent.parent / "tools" / "doku.py"
    spec = importlib.util.spec_from_file_location("doku", pfad)
    doku = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doku)
    assert doku.pruefen() == []


# ---------------------------------------------------------------- Jahresbericht, Fremdwährungen, Liegenschaft

def test_waehrung_konten(k, db):
    import vermoegen as vm
    import waehrung as wg
    k.setdefault("waehrungen", {})["kurse"] = {"EUR": 0.9, "USD": 0.8}
    wg.uebernehmen(k)
    a = vm.konto_anlegen(db, "Sparkasse", "bank", "", "EUR")
    b = vm.konto_anlegen(db, "Konto CHF", "bank")
    vm.saldo_setzen(db, a, "2026-10-31", 10_000)
    vm.saldo_setzen(db, b, "2026-10-31", 5_000)
    assert vm.nettovermoegen(db)["total"] == 14_000
    assert vm.fremdwaehrung(db) == {"EUR": 9_000}
    assert wg.erkennen("Konto;Währung\n1;EUR\n2;EUR") == "EUR" and wg.erkennen("Saldo CHF") == "CHF"
    k["waehrungen"]["kurse"] = {}
    wg.uebernehmen(k)
    assert wg.kurs("EUR") == wg.STANDARD["EUR"]
    import zuzug as zz
    p = k["personen"][0]
    p["zuzug"] = {"rente_ausland_jahr": 10_000, "rente_ausland_waehrung": "EUR"}
    assert zz.rente_ausland(p) == round(10_000 * wg.STANDARD["EUR"], 6)


def test_jahresbericht(k, db, daten):
    import bericht as br
    import vermoegen as vm
    a = vm.konto_anlegen(db, "Konto", "bank")
    vm.saldo_setzen(db, a, "2025-12-15", 50_000)
    vm.saldo_setzen(db, a, "2026-10-15", 70_000)
    assert br.automatisch(k, db, date(2026, 11, 9)) is True
    assert br.automatisch(k, db, date(2026, 11, 20)) is False
    assert len(br.staende(db)) == 1
    vorjahr = br.jahresstand(db, 2025)
    assert vorjahr[1]["_aus_saldi"] and vorjahr[1]["nettovermoegen"] == 50_000
    b = br.erstellen(k, db, 2026, date(2026, 11, 9))
    z = {x.schluessel: x for x in b.zeilen}
    assert z["nettovermoegen"].differenz == 20_000 and z["nettovermoegen"].besser is True
    assert any("Nettovermögen um CHF 20'000 gestiegen" in s for s in b.aussagen)


def test_liegenschaft(k, db):
    import immobilie as im
    k["wohnen"].update(aktiv=True, kaufpreis=1_000_000, eigenmittel=250_000)
    k["wohnen"]["liegenschaft"] = {"baujahr": 2000, "neuwert": 800_000, "fonds_bestand": 10_000}
    k["kennzahlen"]["eigenmietwert_abschaffung"] = 2029
    p = im.planen(k, db, date(2026, 11, 9))
    assert p.marktwert == 1_000_000 and p.hypothek == 750_000 and p.belehnung == 75.0
    heizung = [f for f in p.faelligkeiten if f.name.startswith("Heizung")]
    assert heizung[0].jahr == 2026 and heizung[0].ueberfaellig and heizung[0].kosten == 32_000
    assert p.soll_monat_dauer > 0 and p.empfohlen_monat >= p.soll_monat_dauer
    assert any("2028" in h for h in p.hinweise)
    import ampel as am
    assert im.status(p, date(2026, 11, 9)) == am.ROT
    k["wohnen"]["liegenschaft"]["art"] = "wohnung"
    namen = {b["name"] for b in im.bauteile(k, date(2026, 11, 9))}
    assert "Küche" in namen and "Dach (Eindeckung)" not in namen
    k["wohnen"]["liegenschaft"].update(marktwert=900_000, marktwert_datum="2024-11-09", wertentwicklung=2)
    assert abs(im.planen(k, db, date(2026, 11, 9)).marktwert - 900_000 * 1.02 ** 2) < 500
    k["wohnen"]["liegenschaft"]["bauteile"] = [{"name": "Dach", "letzte": 2020, "lebensdauer": 30, "kosten": 60_000}]
    e = im.erinnerungen(k, date(2049, 1, 1))
    assert e and "Dach" in e[0].titel


def test_vorsorgedokument_3b(k, db):
    import dokumente as dk
    import vermoegen as vm
    text = ("Mobiliar Versicherung\nFreie Vorsorge Säule 3b – Police 12.345.678\nVersicherte Person: Muster Anna\n"
            "Stand 31.12.2025\nRückkaufswert CHF 39'748.00\nJahresprämie CHF 3'000.00\n"
            "Erlebensfallkapital CHF 60'000.00\nTodesfallkapital CHF 100'000.00\n")
    e = dk.erkennen(text)
    assert e["typ"] == "saeule3b" and e["anbieter"] == "Mobiliar"
    assert e["werte"] == {"guthaben_3b": 39748, "praemie_3b": 3000, "erlebensfall_3b": 60000, "todesfall_3b": 100000}
    dok = {"typ": "saeule3b", "werte": e["werte"], "stichtag": "2025-12-31", "anbieter": "Mobiliar"}
    name = k["personen"][0]["name"]
    k["wohnen"]["verpfaendet"] = [{"name": f"3b Mobiliar {name}", "guthaben": 1}]
    erledigt = dk.uebernehmen(k, dok, 0, list(e["werte"]))
    assert k["personen"][0]["risiko"]["todesfallkapital_extern"] == 100000
    assert "3b-Guthaben" not in " ".join(erledigt)
    txt = dk.guthaben_3b_uebernehmen(k, db, dok, name, "")
    konto = next(x for x in vm.konten(db) if x["art"] == "vorsorge")
    assert konto["name"] == f"3b Mobiliar {name}" and konto["betrag"] == 39748 and konto["datum"] == "2025-12-31"
    assert k["wohnen"]["verpfaendet"][0]["guthaben"] == 39748 and "3b" in txt


def test_text_status():
    import ampel as am
    import seiten
    assert seiten.text_status("")[0] == am.ROT and seiten.text_status(None)[0] == am.ROT
    assert seiten.text_status("kurz")[0] == am.GELB
    assert seiten.text_status("x" * 500)[0] == am.GRUEN
    assert "Kein Text in der Datei gefunden" in seiten.text_karte("", False)


def test_krankenkassen_police_kvg_vvg(k, db, tmp_path):
    import krankenkasse as kk
    from policen import KK_POLICE
    e = vi.erkennen(KK_POLICE)
    z = e.pop("_zusatz")
    assert e["sparte"] == "kvg" and e["versicherer"] == "Atupri" and e["person"] == "Muster Anna"
    assert e["praemie_jahr"] == pytest.approx(422.15 * 12) and e["modell"] == "hausarzt" and e["franchise"] == 2500
    assert e["unfall_eingeschlossen"] == 0 and e["unfall_praemie"] == 270 and e["police"] == "1234567"
    assert e["geburtsdatum"] == "1985-03-12" and e["beginn"] == "2027-01-01" and "Dr. Beispiel" in e["notiz"]
    assert z["sparte"] == "vvg" and z["praemie_jahr"] == pytest.approx(315) and z["ablauf"] == "2027-12-31"
    assert "Mivita Reala (22.80/Monat)" in z["produkte"] and "UTI" in z["produkte"] and z["summe"] == 200_000
    # Hochladen: zwei Verträge aus einem PDF, gemeinsame Datei
    vid = vi.hochladen(db, tmp_path, "kk.txt", KK_POLICE.encode())
    alle = vi.alle(db)
    assert {v["sparte"] for v in alle} == {"kvg", "vvg"} and len({v["datei"] for v in alle}) == 1
    # In den Krankenkassen-Rechner übernehmen
    p1 = k["personen"][0]
    p1["name"] = "Anna"
    assert kk.police_uebernehmen(k, vi.einer(db, vid)) == "Anna"
    eintrag = k["krankenkasse"]["personen"][0]
    assert eintrag["franchise"] == 2500 and eintrag["modell"] == "hausarzt" and eintrag["unfall"] is False
    ps = {p.name: p for p in kk.personen(k, vi.alle(db))}
    assert ps["Anna"].unfall_praemie == 270 and ps["Anna"].anlaufstelle.startswith("Dr. Beispiel")
    h = kk.haushalt_hinweise(k, vi.alle(db), date(2026, 11, 9))
    assert any("30.11." in x for x in h) and any("Zahnspange" in x for x in h)
    # Datei bleibt, solange der zweite Vertrag sie nutzt
    vi.loeschen(db, tmp_path, vid)
    assert (tmp_path / "versicherungen" / alle[0]["datei"]).exists()


def test_neu_sichten(k, db, tmp_path, daten):
    import dokumente as dk
    import sichtung
    from policen import HAUSRAT, KK_POLICE
    # Policen wie mit einer älteren Version: falsche Werte, Zusatzversicherung fehlt
    a = vi.hochladen(db, tmp_path, "kk.txt", KK_POLICE.encode())
    for v in vi.alle(db):
        if v["id"] != a:
            db.execute("DELETE FROM vertraege WHERE id = ?", (v["id"],))
    vi.aktualisieren(db, a, {"praemie_jahr": 22.5, "modell": ""}, quelle="muster")
    b = vi.hochladen(db, tmp_path, "hausrat.pdf", pdf(HAUSRAT))
    vi.aktualisieren(db, b, {"praemie_jahr": 700}, quelle="hand")              # von Hand korrigiert
    d = dk.hochladen(db, tmp_path, "3a.txt", b"Saeule 3a Konto\\nSaldo per 31.12.2025 CHF 12'000.00\\n")
    dk.speichern(db, d, "saeule3a", "Person 1", {"guthaben_3a": 1}, quelle="muster")
    db.execute("UPDATE vorsorge_dok SET uebernommen = '2026-01-01' WHERE id = ?", (d,))
    k["personen"][0]["name"] = "Anna"
    r = sichtung.ausfuehren(k, db, tmp_path, "Test")
    assert vi.einer(db, a)["praemie_jahr"] == pytest.approx(422.15 * 12) and vi.einer(db, a)["modell"] == "hausarzt"
    assert vi.einer(db, b)["praemie_jahr"] == 700 and r.geschuetzt == 1
    assert {v["sparte"] for v in vi.alle(db)} >= {"kvg", "vvg"} and len(r.neu) == 1
    dok = dk.einer(db, d)
    assert dok["uebernommen"] == "" and dok["person"] == "Person 1"            # gewählte Person bleibt
    assert any("Vorsorge" in x and "bitte neu übernehmen" in x for x in r.geaendert)
    assert k["krankenkasse"]["personen"][0]["modell"] == "hausarzt"
    det = {(x["bereich"], x["feld"]): x for x in r.details}
    assert det[("Versicherungen", "Prämie pro Jahr")]["alt"] == "22.50"
    assert det[("Versicherungen", "Prämie pro Jahr")]["neu"] == "5'065.80"
    assert det[("Versicherungen", "Modell")]["alt"] == "–" and det[("Versicherungen", "Modell")]["neu"] == "Hausarzt"
    assert det[("Vorsorge", "3a-Guthaben")]["alt"] == "1" and det[("Vorsorge", "3a-Guthaben")]["neu"] == "12'000"
    assert any(x["feld"] == "neuer Vertrag" for x in r.details)
    assert sichtung.letzte(db).details == r.details
    # mit «alle» wird auch die Handkorrektur überschrieben
    sichtung.ausfuehren(k, db, tmp_path, "Test", alle=True)
    assert vi.einer(db, b)["praemie_jahr"] == pytest.approx(612.4)
    assert sichtung.letzte(db).ausloeser == "Test"
    # zweite Sichtung ohne Änderungen
    r2 = sichtung.ausfuehren(k, db, tmp_path, "Test")
    assert not r2.geaendert and not r2.neu


def test_neu_sichten_nach_update(k, db, tmp_path, daten):
    import meta
    import sichtung
    from policen import HAUSRAT
    assert sichtung.wenn_neue_version(lambda: k, db, tmp_path) is None         # ohne Dokumente: nur Version merken
    assert sichtung.letzte(db).version == meta.version() and sichtung.letzte(db).geprueft == 0
    vi.hochladen(db, tmp_path, "hausrat.pdf", pdf(HAUSRAT))
    assert sichtung.wenn_neue_version(lambda: k, db, tmp_path) is None         # gleiche Version: nichts tun
    db.execute("UPDATE sichtung SET bericht = replace(bericht, '\"version\": \"' || version, '\"version\": \"0.0.1')")
    b = sichtung.wenn_neue_version(lambda: k, db, tmp_path)                     # neue Version: neu sichten
    assert b.geprueft == 1 and b.ausloeser == f"Update auf {meta.version()}"


def test_plausibilitaet_einstellungen(k):
    import ampel as am
    import pruefung as pr
    p = k["personen"][0]
    p.update(geburtsdatum="1985-03-12", lohn_brutto=120000)
    p["pk"].update(altersguthaben=0, stand="", ausweis_alterskapital=800000, ausweis_altersrente=40000)
    p["ahv"]["beitragsjahre_bisher"] = 30
    p["saeule3a"]["beitrag_jahr"] = 9000
    assert pr.pruefen(k, "personen.0.geburtsdatum", date(2026, 11, 9))[0] == am.GRUEN
    assert pr.pruefen(k, "personen.0.pk.altersguthaben", date(2026, 11, 9))[0] == am.ROT
    assert pr.pruefen(k, "personen.0.ahv.beitragsjahre_bisher", date(2026, 11, 9))[0] == am.ROT   # 41 Jahre alt
    assert pr.pruefen(k, "personen.0.saeule3a.beitrag_jahr", date(2026, 11, 9))[0] == am.ROT
    assert pr.pruefen(k, "personen.0.pk.ausweis_altersrente", date(2026, 11, 9))[0] == am.GRUEN
    p["pk"]["ausweis_altersrente"] = 400000                                                        # vertauscht
    assert "vertauscht" in pr.pruefen(k, "personen.0.pk.ausweis_altersrente", date(2026, 11, 9))[1]
    p["lohn_brutto"] = 9000                                                                        # Monatslohn
    assert "Monatslohn" in pr.pruefen(k, "personen.0.lohn_brutto", date(2026, 11, 9))[1]
    k["haushalt"]["bedarf_ruhestand"] = 0
    assert pr.pruefen(k, "haushalt.bedarf_ruhestand")[0] == am.ROT
    k["haushalt"]["kanton"] = "XY"
    assert pr.pruefen(k, "haushalt.kanton")[0] == am.ROT
    k["wohnen"]["aktiv"] = False
    assert pr.pruefen(k, "wohnen.kaufpreis")[0] == am.GRAU
    import seiten
    zf = pr.zusammenfassung(k, seiten.alle_felder(k))
    assert zf[am.ROT] and sum(len(v) for v in zf.values()) == len(seiten.alle_felder(k))


def test_dokumente_verwalten(k, db, tmp_path):
    import dokumente as dk
    import verwaltung as vw
    from policen import HAUSRAT, KK_POLICE
    a = vi.hochladen(db, tmp_path, "kk.txt", KK_POLICE.encode())             # zwei Verträge, eine Datei
    hausrat = pdf(HAUSRAT)
    b = vi.hochladen(db, tmp_path, "hausrat.pdf", hausrat)
    c = vi.hochladen(db, tmp_path, "hausrat-kopie.pdf", hausrat)               # Duplikat
    d = dk.hochladen(db, tmp_path, "3a.txt", b"Saeule 3a Konto\\nSaldo CHF 1'000.00\\n")
    import budget as bu
    bu.speichern(db, "Privatkonto", [("2026-01-05", -50.0, "Migros")], k)
    alle = {e.schluessel: e for e in vw.eintraege(db, tmp_path)}
    assert len([s for s in alle if s.startswith("v:")]) == 4 and f"d:{d}" in alle and "b:Privatkonto" in alle
    assert alle[f"v:{c}"].duplikat_von == f"v:{b}" and not alle[f"v:{a}"].duplikat_von
    assert not [e for e in alle.values() if e.schluessel.startswith("v:") and e.duplikat_von and e.schluessel != f"v:{c}"]
    neu, doppelt = vw.neue_dateien(db, tmp_path, "v", [("x.pdf", hausrat), ("y.txt", b"neu")])
    assert [n for n, _ in neu] == ["y.txt"] and doppelt and "schon vorhanden" in doppelt[0]
    assert vw.loeschen(db, tmp_path, [f"v:{c}", f"d:{d}", "b:Privatkonto", "x:1"]) == 3
    rest = {e.schluessel for e in vw.eintraege(db, tmp_path)}
    assert f"v:{c}" not in rest and f"d:{d}" not in rest and "b:Privatkonto" not in rest
    assert not (tmp_path / "vorsorge" / f"{d}.txt").exists()


def test_vorschlaege_aus_daten_anonymisiert(k, db, tmp_path):
    from datetime import datetime
    import dokumente as dk
    import vorschlaege as vs
    from policen import HAUSRAT
    k["personen"][0]["name"] = "Annelies Muster-Gubler"
    k["haushalt"]["kanton"] = "ZG"
    k["wohnen"]["aktiv"] = True
    # Police: Prämie von Hand korrigiert → «falsch erkannt»; Dateiname enthält den Namen
    vid = vi.hochladen(db, tmp_path, "Police Annelies Muster-Gubler.pdf", pdf(HAUSRAT))
    vi.aktualisieren(db, vid, {"praemie_jahr": 987.65, "person": "Annelies Muster-Gubler"}, quelle="hand")
    # 3a-Auszug ohne Beitrag → «nicht erkannt»
    dk.hochladen(db, tmp_path, "3a.txt", "Säule 3a Vorsorgekonto\nGuthaben CHF 12'345.00\n".encode())
    # Protokoll mit persönlichen Angaben
    (tmp_path / "finanz.log").write_text(
        f"{datetime.now():%Y-%m-%d %H:%M:%S},123 WARNING Import 'Annelies 2025.pdf' fehlgeschlagen: CHF 1'234 am 03.04.2025 "
        "an annelies@example.ch, IBAN CH93 0076 2011 6238 5295 7\n", encoding="utf-8")
    liste = vs.sammeln(k, db, tmp_path)
    titel = [v.titel for v in liste]
    assert any("Prämie pro Jahr" in t and "falsch erkannt" in t for t in titel)
    assert any("3a-Beitrag" in t and "nicht erkannt" in t for t in titel)
    assert any("Kanton ZG: Unterhaltspauschale" in t for t in titel)
    assert liste[0].gewicht == vs.HOCH                                   # von Hand korrigiert zuerst
    text = vs.bericht(liste, "9.9.9", "ZG")
    for privat in ("Annelies", "Gubler", "12'345", "987", "1'234", "03.04.2025", "example.ch", "CH93", "Police"):
        assert privat not in text, privat
    assert "WARNING: Import ‹…› fehlgeschlagen" in text
    # ausblenden, eigene Idee, Issue-Link
    vs.ausblenden(db, [liste[0].schluessel])
    assert vs.status(db) == {liste[0].schluessel: "ausgeblendet"}
    vs.idee_speichern(db, "Export für Annelies als Excel")
    assert any(v.bereich == "Eigene Ideen" and v.titel == "Export für ‹…› als Excel" for v in vs.sammeln(k, db, tmp_path))
    link = vs.issue_link("https://github.com/x/y", "a" * 9000, "1.0")
    assert link.startswith("https://github.com/x/y/issues/new?title=") and len(link) < 20000


def test_vorschlaege_pro_dokument_gruppiert_mit_textauszug(k, db, tmp_path):
    import vorschlaege as vs
    k["personen"][0]["name"] = "Annelies Muster-Gubler"
    text = ("Irgendwas anderes 42\nMuster Versicherungen AG\nFrau Annelies Muster-Gubler\nDorfstrasse 12\n9999 Musterhausen\n"
            "Hausratversicherung Police 12-345.678\nVersicherungsbeginn 01.01.2024\n"
            "Jahresprämie total CHF 456.70\nKündigung: 3 Monate vor Ablauf\n")
    vid = vi.hochladen(db, tmp_path, "Police Gubler.txt", text.encode())
    vi.aktualisieren(db, vid, {"praemie_jahr": 400.0, "kuendigungsfrist_monate": 2, "person": "Annelies Muster-Gubler"},
                     quelle="hand")
    liste = [v for v in vs.sammeln(k, db, tmp_path) if "falsch erkannt" in v.titel or "nicht erkannt" in v.titel]
    zeile = [v.titel for v in liste if "Prämie pro Jahr" in v.titel]
    assert len(zeile) == 1 and "«Kündigungsfrist (Monate)»" in zeile[0]       # eine Zeile pro Dokument
    auszuege = vs.textauszuege(k, db)
    assert len(auszuege) == 1
    zeilen = auszuege[0][1]
    assert "Jahresprämie total CHF 999.99" in zeilen and "Kündigung: 9 Monate vor Ablauf" in zeilen
    bericht = vs.bericht(liste, "9.9.9", "", auszuege)
    for privat in ("Annelies", "Gubler", "Dorfstrasse", "Musterhausen", "456", "12-345", "Irgendwas"):
        assert privat not in bericht, privat
    assert "### Textauszüge" in bericht and "### Textauszüge" not in vs.bericht(liste, "9.9.9")


def test_kantonale_gebaeudeversicherung_nicht_kuendbar():
    bgv = "Basellandschaftliche Gebäudeversicherung\nRechnung Gebäudeversicherung 2026\nPrämie CHF 812.40\n"
    e = vi.erkennen(bgv)
    assert e["versicherer"] == "Basellandschaftliche Gebäudeversicherung" and e["sparte"] == "gebaeude"
    assert e["kuendigungsfrist_monate"] == 0 and "nicht kündbar" in e["notiz"]
    assert vi.naechster_termin({**e, "ablauf": "2026-12-31"}, date(2026, 6, 1)) is None
    privat = "Helvetia Versicherungen\nGebäudeversicherung\n" + "Zeile\n" * 15 + "Feuer ist bei der BGV versichert\n"
    assert vi.erkennen(privat)["versicherer"] == "Helvetia"


def test_erkennung_aus_textauszuegen_0_30():
    # Rechnung mit Zwischentotal und Überschussbeteiligung: der zu bezahlende Betrag zählt
    bgv = ("Basellandschaftliche Gebäudeversicherung\nJahresprämienrechnung\nGrundstück Grundbetrag 80.00 4.00 84.00\n"
           "Zwischentotal 512.40\nÜberschussbeteiligung Teil Prämie -40.10\nZu bezahlender Betrag 468.30\n")
    assert vi.erkennen(bgv)["praemie_jahr"] == 468.30
    # Kündigungsfrist als Wort, jährliches Kündigungsrecht
    helv = ("Helvetia Versicherungen\nGebäudeversicherung\nJährliches Kündigungsrecht\n"
            "Den Vertragspartnern steht das Recht zu, den Vertrag drei Monate vor Ablauf jedes Versicherungsjahres zu kündigen.")
    assert vi.erkennen(helv)["kuendigungsfrist_monate"] == 3
    # smile (Helvetia-Marke, duzt), Laufzeit von–bis
    smile = ("Police 123\nVertragsdaten Versicherungslaufzeit 01.03.2025 – 28.02.2026\nHausratversicherung\n"
             "Helvetia Schweizerische Versicherungsgesellschaft AG\nDeine Jahresprämie Total CHF 312.50\n"
             "Gesetzliche Abgaben CHF 15.60\n")
    e = vi.erkennen(smile)
    assert e["versicherer"] == "Smile" and e["praemie_jahr"] == 312.50
    assert e["beginn"] == "2025-03-01" and e["ablauf"] == "2026-02-28"
    # Erwerbsunfähigkeit: Beginn «erstmals fällig», Ablauf «Ende der Leistungspflicht»
    eu = ("Helvetia\nErwerbsunfähigkeit\nEnde der Leistungspflicht spätestens am 31.05.2049\n"
          "Total Jahresprämie erstmals fällig am 01.06.2020 1'234.50\n")
    e = vi.erkennen(eu)
    assert e["beginn"] == "2020-06-01" and e["ablauf"] == "2049-05-31" and e["praemie_jahr"] == 1234.50


def test_pk_ausweis_tabellen():
    import dokumente as dk
    text = ("Vorsorgeausweis Pensionskasse Asga\nAltersguthaben per 01.01.2026 123'456.00\n"
            "Finanzierung über alle Pläne und Stiftungen Ihr Beitrag Ihre Altersgutschrift\n"
            "pro Monat 450.00 1'100.00\nLeistungen im Alter - Projektionszinssatz 2%\n"
            "Alter Alterskapital Altersrente\n60 400'000.00 21'000.00\n65 512'345.00 27'500.00\n"
            "Todesfallsumme 150'000.00\nDie Kasse hat Ihr Alterskapital mit 2,5 % verzinst (2025).\n"
            "Umwandlungssatz 5.4 %\nInvalidenrente, Wartefrist 24 Monate 36'000.00\n")
    e = dk.erkennen(text)
    w = e["werte"]
    assert e["anbieter"] == "Asga"
    assert w["ausweis_alterskapital"] == 512345 and w["ausweis_altersrente"] == 27500
    assert w["sparbeitrag_jahr"] == 13200 and w["todesfallkapital_pk"] == 150000 and w["zins"] == 2.5


def test_textauszug_ohne_personalien_und_gesundheitsangaben():
    import vorschlaege as vs
    text = ("Prämie total CHF 100.00\nE-Mail anna.muster@example.ch\nGeburtsdatum 01.02.1980\nNationalität Schweiz\n"
            "Herrn Ben Muster\nkeine Leistungen für Erkrankungen des rechten Knies\nJahresprämie CHF 200.00\n")
    zeilen = vs.auszug(text, {"praemie_jahr"}, [])
    assert "Prämie total CHF 999.99" in zeilen and "Jahresprämie CHF 999.99" in zeilen
    assert not any(re.search(r"example|muster|Geburt|Nationalit|Herrn|Erkrank", z, re.I) for z in zeilen)


def test_ocr_fuer_gescannte_pdfs(monkeypatch, caplog):
    import io
    import shutil
    import ocr
    from PIL import Image, ImageDraw, ImageFont
    if not ocr.verfuegbar():
        pytest.skip("tesseract/pdftoppm nicht installiert")
    bild = Image.new("L", (1700, 700), 255)
    zeichnen = ImageDraw.Draw(bild)
    schrift = ImageFont.load_default(size=48)
    for i, zeile in enumerate(["Hausratversicherung", "Versicherungsnehmer Max Muster", "Jahresprämie CHF 245.00"]):
        zeichnen.text((80, 80 + i * 110), zeile, fill=0, font=schrift)
    puffer = io.BytesIO()
    bild.save(puffer, format="PDF", resolution=150)
    inhalt = puffer.getvalue()
    from pypdf import PdfReader
    assert not (PdfReader(io.BytesIO(inhalt)).pages[0].extract_text() or "").strip()     # wirklich nur ein Bild
    text = vi.text_auslesen("scan.pdf", inhalt)
    assert "Hausrat" in text and "245" in text
    assert vi.erkennen(text)["sparte"] == "hausrat"
    assert shutil.which("tesseract")
    # pdftoppm scheitert → eingebettetes Scan-Bild direkt lesen; Grund steht lesbar im Protokoll
    echt = ocr._nett
    monkeypatch.setattr(ocr, "_nett", lambda b: ["false"] if b[0] == "pdftoppm" else echt(b))
    with caplog.at_level("WARNING", logger="finanz"):
        assert "Hausrat" in ocr.pdf_text(inhalt, "scan.pdf")
    assert "Exit-Code 1" in caplog.text and "eingebettete Bilder" in caplog.text


def test_neu_sichten_im_hintergrund_und_ocr_nur_einmal(k, db, tmp_path, daten, monkeypatch):
    import contextlib
    import sqlite3
    import ocr
    import sichtung
    import seiten
    # gescanntes PDF: einmal erkannter Text wird beim Neu-Sichten wiederverwendet, nicht nochmals per OCR gerechnet
    aufrufe = []
    monkeypatch.setattr(ocr, "verfuegbar", lambda: True)
    monkeypatch.setattr(ocr, "pdf_text", lambda inhalt, name="": aufrufe.append(name) or "Hausratversicherung " * 5)
    leer = pdf("")
    vi.hochladen(db, tmp_path, "scan.pdf", leer)
    assert aufrufe == ["scan.pdf"]
    sichtung.ausfuehren(k, db, tmp_path, "Test")
    assert aufrufe == ["scan.pdf"]                                          # kein zweites Mal
    assert sichtung.STAND["laeuft"] is False and sichtung.STAND["fertig"] == sichtung.STAND["gesamt"] == 1
    # Knopf: läuft im Hintergrund; ein zweiter Klick startet keinen zweiten Lauf
    pfad = tmp_path / "x.sqlite"

    @contextlib.contextmanager
    def verbinden():
        v = sqlite3.connect(pfad, check_same_thread=False)
        v.row_factory = sqlite3.Row
        yield v
        v.close()
    with sichtung._SPERRE:
        assert not sichtung.im_hintergrund(lambda: k, verbinden, tmp_path)
        sichtung.STAND.update(laeuft=True, fertig=2, gesamt=5, aktuell="police.pdf", ausloeser="Knopf")
        html = seiten.sichtung_knopf("dokumente")
        assert "2 von 5" in html and "police.pdf" in html and "<button" not in html
        sichtung.STAND["laeuft"] = False
    assert sichtung.im_hintergrund(lambda: k, verbinden, tmp_path)
    for _ in range(100):
        if not sichtung.STAND["laeuft"]:
            break
        import time
        time.sleep(0.05)
    assert sichtung.STAND["laeuft"] is False


def test_vorschlaege_nur_meldungen_der_aktuellen_version(k, db, tmp_path):
    from datetime import datetime, timedelta
    import meta
    import vorschlaege as vs
    t = datetime.now() - timedelta(hours=3)

    def z(min_):
        return f"{t + timedelta(minutes=min_):%Y-%m-%d %H:%M:%S},1"
    (tmp_path / "finanz.log").write_text("\n".join([
        f"{z(0)} INFO Finanzplanung 0.0.1 startet",
        f"{z(1)} WARNING Alte Warnung schon behoben",
        f"{z(2)} INFO Finanzplanung {meta.version()} startet",
        f"{z(3)} WARNING Neue Warnung",
        f"{z(4)} INFO Finanzplanung {meta.version()} startet",          # Neustart derselben Version zählt mit
        f"{z(5)} ERROR Neuer Fehler",
    ]) + "\n", encoding="utf-8")
    titel = {v.titel: v.detail for v in vs.sammeln(k, db, tmp_path) if v.bereich == "Fehler und Warnungen"}
    assert set(titel) == {"WARNING: Neue Warnung", "ERROR: Neuer Fehler"}
    assert all(d == f"seit Version {meta.version()}" for d in titel.values())


def test_berater_nutzt_eingestellte_ki_entitaet(k, db, monkeypatch):
    import berater
    aufrufe = []
    monkeypatch.setattr(vi, "ki_aufgabe", lambda text, entity, name, json_antwort=True: aufrufe.append(entity) or "Antwort")
    k["ki"].update(aktiv=True, entity="ai_task.lokal")
    berater.fragen(k, db, berater.profile(k)[0]["id"], "Amortisieren oder anlegen?")
    assert aufrufe == ["ai_task.lokal"]


def test_konten_verwalten(db):
    import budget
    a = vm.konto_anlegen(db, "Sparkonto", "bank")
    b = vm.konto_anlegen(db, "Raiffeisen …7890", "bank")
    for tag, betrag in (("2026-01-31", 1000), ("2026-02-28", 1200), ("2026-03-31", 1500)):
        vm.saldo_setzen(db, a, tag, betrag)
    vm.saldo_setzen(db, b, "2026-03-31", 9999)
    vm.saldo_setzen(db, b, "2026-04-30", 1700)
    buchung = [("2026-03-05", -50.0, "Migros")]
    budget.speichern(db, "Sparkonto", buchung)
    # umbenennen: Buchungen wandern mit, ein erneuter Import erkennt sie als schon vorhanden
    vm.konto_aendern(db, a, "Sparkonto ZKB", "bank", "", "CHF", "IBAN …1234")
    assert vm.konto(db, a)["buchungen"] == 1 and vm.konto(db, a)["notiz"] == "IBAN …1234"
    assert budget.speichern(db, "Sparkonto ZKB", buchung) == 0
    with pytest.raises(ValueError, match="schon ein Konto"):
        vm.konto_aendern(db, a, "Raiffeisen …7890", "bank", "", "CHF")
    # Saldi bearbeiten und löschen
    g, l_ = vm.saldi_aendern(db, a, {"2026-02-28": ("2026-02-27", 1250.0)}, ["2026-01-31"])
    assert (g, l_) == (1, 1)
    assert [(s["datum"], s["betrag"]) for s in vm.saldi(db, a)] == [("2026-03-31", 1500), ("2026-02-27", 1250)]
    # zusammenführen: gleicher Tag → Zielkonto gilt; Buchungen und Saldi wandern, Quelle verschwindet
    budget.speichern(db, "Raiffeisen …7890", buchung + [("2026-04-02", -20.0, "Coop")])
    assert vm.zusammenfuehren(db, b, a) == 1                                   # nur 2026-04-30 neu
    assert vm.konto(db, b) is None
    assert {s["datum"]: s["betrag"] for s in vm.saldi(db, a)}["2026-03-31"] == 1500
    assert vm.konto(db, a)["buchungen"] == 2                                   # Migros nur einmal
    # auflösen und wieder öffnen
    vm.aufloesen(db, a, "2026-05-31")
    assert vm.konten(db)[0]["aufgeloest"] == "2026-05-31" and vm.konten(db)[0]["betrag"] == 0
    vm.aufloesen(db, a, None)
    assert vm.konten(db)[0]["aufgeloest"] == "" and vm.konten(db)[0]["betrag"] == 1700
    # löschen entfernt auch die Buchungen
    vm.konto_loeschen(db, a)
    assert db.execute("SELECT COUNT(*) FROM buchungen").fetchone()[0] == 0


EU_POLICE = """Muster Versicherungen AG
Police Nr. 12.345.678
Erwerbsunfähigkeitsversicherung
Versicherte Person: Person 1
Leistungen bei Erwerbsunfähigkeit infolge Krankheit und Unfall
Erwerbsunfähigkeitsrente jährlich CHF 24'000.00
Wartefrist 720 Tage
Leistungsdauer bis Alter 65
Prämienbefreiung bei Erwerbsunfähigkeit eingeschlossen
Leistungen ab einem Erwerbsunfähigkeitsgrad von 25 %
Jahresprämie CHF 1'234.50
Vertragsbeginn 01.01.2020 Vertragsablauf 31.12.2049"""


def test_invaliditaet_aus_policen(k, db, tmp_path):
    import sichtung
    e = vi.erkennen(EU_POLICE)
    assert e["sparte"] == "erwerbsunfaehigkeit"
    assert (e["iv_rente_jahr"], e["iv_wartefrist_monate"], e["iv_bis_alter"]) == (24_000, 24, 65)
    assert (e["iv_ursache"], e["iv_grad_min"], e["iv_beitragsbefreiung"]) == ("Krankheit und Unfall", 25, 1)
    monatlich = vi.iv_erkennen("Invalidenrente\nCHF 1'500 pro Monat\nInvaliditätskapital CHF 100'000")
    assert monatlich["iv_rente_jahr"] == 18_000 and monatlich["iv_kapital"] == 100_000
    assert vi.iv_erkennen("Hausratversicherung Versicherungssumme CHF 80'000") == {}
    # in die Risiko-Rechnung: «Extern» aus der Police, solange in den Einstellungen 0 steht
    vid = vi.hochladen(db, tmp_path, "eu.pdf", pdf(EU_POLICE))
    vi.aktualisieren(db, vid, {"person": "Person 1"})
    k["personen"][0]["risiko"]["iv_rente_extern"] = 0
    r = vi.risiko(k, vs.ahv(k, 2026), vi.alle(db))[0]
    assert r.iv_extern == 24_000
    k["personen"][0]["risiko"]["iv_rente_extern"] = 10_000                      # eigener Wert hat Vorrang
    r = vi.risiko(k, vs.ahv(k, 2026), vi.alle(db))[0]
    assert r.iv_extern == 10_000 and any("Policen 24'000" in h for h in r.hinweise)
    # von Hand bearbeitet: Neu-Sichten ergänzt nur leere IV-Felder, überschreibt nichts
    vi.aktualisieren(db, vid, {"praemie_jahr": 999.0, "iv_rente_jahr": 0, "iv_wartefrist_monate": 12}, quelle="hand")
    sichtung.ausfuehren(k, db, tmp_path, "Test")
    v = vi.einer(db, vid)
    assert v["praemie_jahr"] == 999 and v["iv_wartefrist_monate"] == 12 and v["iv_rente_jahr"] == 24_000
    assert v["quelle"] == "hand"


def test_verfuegungen_erbteile_und_entwuerfe(k):
    from fractions import Fraction as F
    import verfuegungen as vf
    k["personen"][0]["name"], k["personen"][1]["name"] = "Anna", "Ben"
    # verheiratet mit einem Kind: Ehegatte max. ¾, Kind Pflichtteil ¼
    k["haushalt"].update(zivilstand="verheiratet", kinder=[{"name": "Lia", "geburtsdatum": "2020-01-01"}])
    l = vf.lage(k, "Anna")
    assert vf.verfuegbar(l) == F(1, 2)
    v = {e: n for e, _, _, n in vf.verteilung(l, {"ziel": "partner_max"}).zeilen}
    assert v == {"Ben": F(3, 4), "Lia": F(1, 4)}
    assert any("Pflichtteil verletzt: Lia" in w for w in vf.verteilung(l, {"ziel": "eigene", "quoten": "Ben: 90\nLia: 10"}).warnungen)
    # verheiratet ohne Kinder, Eltern leben: verfügbar 5/8, Ehegatte alles möglich
    k["haushalt"]["kinder"] = []
    assert vf.verfuegbar(vf.lage(k, "Anna", {"eltern": "ja"})) == F(5, 8)
    # Konkubinat mit Kind: Partner höchstens ½; ohne Kinder alles verfügbar
    k["haushalt"].update(zivilstand="ledig", kinder=[{"name": "Lia", "geburtsdatum": "2020-01-01"}])
    assert {e: n for e, _, _, n in vf.verteilung(vf.lage(k, "Anna"), {"ziel": "partner_max"}).zeilen}["Ben"] == F(1, 2)
    k["haushalt"]["kinder"] = []
    assert vf.verfuegbar(vf.lage(k, "Anna")) == 1
    # Texte
    k["verfuegungen"] = {"testament": {"Anna": {"ziel": "partner_max", "bezeichnung": "lebenspartner",
                                                "willensvollstrecker": "Notariat Muster"}}}
    t = vf.text(k, "testament", "Anna")
    assert "wende ich meinem Lebenspartner Ben zu" in t and "Willensvollstrecker setze ich Notariat Muster" in t
    assert "[Unterschrift]" in t
    assert "Ich beauftrage Ben mit der Personensorge" in vf.text(k, "vorsorgeauftrag", "Anna")
    assert "BVV 3" in vf.text(k, "beguenstigung_3a", "Anna")                 # Konkubinat: Grundlage nennen
    assert "Unterschrift Ben" in vf.text(k, "konkubinatsvertrag", vf.HAUSHALT)
    assert [t_.schluessel for t_ in vf.typen(k)].count("konkubinatsvertrag") == 1


def test_camt053_import(db):
    import io
    import zipfile
    from pathlib import Path
    import bankimport as bi
    import camt
    inhalt = (Path(__file__).parent / "daten" / "camt053_beispiel.xml").read_bytes()
    k = camt.lesen(inhalt)[0]
    assert k.iban.endswith("2957") and len(k.buchungen) == 4          # vorgemerkte Buchung zählt nicht
    assert ("2026-02-03", -200.0, "Krankenkasse Sammelauftrag") in k.buchungen   # Sammelauftrag aufgeteilt
    assert camt.monatssaldi(k)["2026-01"] == ("2026-01-25", 7000.0)
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("auszug.xml", inhalt)
    a, n = bi.aus_datei(db, puffer.getvalue(), "camt.zip")
    assert a.bank == "Raiffeisen" and n == 3 and a.ausgaben == 1350
    assert len(bi.buchungen_lesen(inhalt)) == 4


def test_verfuegungen_ehevertrag_erbvertrag_darlehen_schenkung(k):
    import verfuegungen as vf
    k["haushalt"]["zivilstand"] = "verheiratet"
    assert {"ehevertrag", "erbvertrag", "darlehen", "schenkung"} <= {t.schluessel for t in vf.typen(k)}
    t = vf.text(k, "ehevertrag", vf.HAUSHALT)
    assert "Art. 216 Abs. 1 ZGB" in t and "durch Tod" in t and "Notar" in t
    vf.speichern(k, "darlehen", vf.HAUSHALT, {"nehmer": "Kind A", "betrag": "50000", "zins": "1", "rueckzahlung": "raten",
                                              "rueckzahlung_detail": "CHF 5000 pro Jahr", "erbteilung": "erlass"})
    t = vf.text(k, "darlehen", vf.HAUSHALT)
    assert "CHF 50000" in t and "1 % pro Jahr" in t and "CHF 5000 pro Jahr" in t and "erlassen" in t
    vf.speichern(k, "schenkung", vf.HAUSHALT, {"empfaenger": "Kind A", "gegenstand": "CHF 30'000",
                                               "ausgleich": "befreit", "rueckfall": "ja"})
    t = vf.text(k, "schenkung", vf.HAUSHALT)
    assert t.startswith("Schenkungsvertrag") and "Art. 527 ZGB" in t and "Art. 247 OR" in t
    assert "Kind 1" in vf.text(k, "erbvertrag", vf.HAUSHALT)                  # Schlusserben aus den Kindern
    k["haushalt"]["zivilstand"] = "konkubinat"
    assert "ehevertrag" not in {t.schluessel for t in vf.typen(k)}


def test_notfall_meldeliste(k, db, tmp_path):
    import notfall as nf
    vi.hochladen(db, tmp_path, "p.txt", "Mobiliar\nHausratversicherung\nPolice Nr. 12-345\nJahresprämie CHF 300.00\n".encode())
    stellen = [s for s, _, _ in nf.meldeliste(k, db)]
    assert "AHV-Ausgleichskasse" in stellen and "Steuerverwaltung" in stellen
    assert any(s.startswith("Mobiliar – Hausrat") for s in stellen)


def test_esteuerauszug_xml(k, db):
    from pathlib import Path
    import esteuerauszug as es
    import steuererklaerung as se
    inhalt = (Path(__file__).parent / "daten" / "esteuerauszug_beispiel.xml").read_bytes()
    s = es.lesen(inhalt, "steuerauszug.xml")
    assert (s.jahr, s.steuerwert, s.ertrag_a, s.ertrag_b, s.vst) == (2025, 60500, 410, 120, 143.5)
    assert s.schulden == 300000 and s.schuldzinsen == 4500 and s.spesen == 150
    depot = next(p for p in s.posten if p.art == "depot")
    assert depot.steuerwert == 40000 and depot.titel == 2 and depot.vst == 140
    _, n = es.speichern(db, s)
    assert n == 3
    konten = {x["name"]: x for x in vm.konten(db)}
    assert "Raiffeisen …2957" in konten and konten["Raiffeisen …2957"]["art"] == "bank"
    hypo = next(x for x in konten.values() if x["art"] == "hypothek")
    assert db.execute("SELECT betrag FROM saldi WHERE konto_id = ?", (hypo["id"],)).fetchone()[0] == -300000
    es.speichern(db, s)                                      # nochmals: ersetzt, verdoppelt nicht
    assert len(es.alle(db)) == 1 and es.summen(db, 2025)["vst"] == 143.5
    punkte = {p.schluessel: p for p in se.erstellen(k, db, 2025).punkte}
    assert "Verrechnungssteuer 143.50" in punkte["steuerauszug"].wert.replace("'", "")


def test_esteuerauszug_pdf_text():
    import esteuerauszug as es
    text = ("Raiffeisenbank Musterhausen\nSteuerauszug per 31.12.2025\nTotal Steuerwert 61'234.00\n"
            "Bruttoertrag A (mit Verrechnungssteuer) 410.00\nBruttoertrag B (ohne Verrechnungssteuer) 120.00\n"
            "Verrechnungssteueranspruch 143.50\n")
    assert es.ist_steuerauszug_text(text)
    s = es.aus_text(text)
    assert (s.jahr, s.steuerwert, s.ertrag_a, s.ertrag_b, s.vst) == (2025, 61234, 410, 120, 143.5)


def test_vorschlaege_durch_update_erledigt(db):
    import vorschlaege as vs
    a = vs.Vorschlag("Dokumente erkennen", "Hausrat (Muster): «Prämie pro Jahr» falsch erkannt")
    b = vs.Vorschlag("Dokumente erkennen", "Hausrat (Muster): «Sparte» falsch erkannt")
    c = vs.Vorschlag("Dokumente erkennen", "Gebäude (Muster): «Ablauf» nicht erkannt")
    vs.verlauf_nachfuehren(db, [a, b, c], "1.0.0")
    vs.verlauf_nachfuehren(db, [c], "1.1.0")                  # a und b mit dem Update weg
    erl = vs.erledigt(db, "1.1.0")
    assert len(erl) == 1 and erl[0][0].titel == "Hausrat (Muster): «Prämie pro Jahr», «Sparte»" and erl[0][3] == "update"
    vs.verlauf_nachfuehren(db, [], "1.1.0")                   # c durch eigene Änderung in derselben Version
    assert [e[3] for e in vs.erledigt(db) if "Gebäude" in e[0].titel] == ["aenderung"]
    vs.verlauf_nachfuehren(db, [a], "1.2.0")                  # wieder aufgetaucht → offen
    assert not any("Prämie" in e[0].titel for e in vs.erledigt(db))
    assert "### Mit 1.1.0 erledigt" in vs.bericht([], "1.1.0", "", None, [e[0] for e in erl])


def test_vollname_in_verfuegungen_vorname_in_der_app(k):
    import konfig
    import verfuegungen as vf
    k["personen"][0].update(name="Anna", nachname="Muster")
    k["personen"][1].update(name="Ben", nachname="Beispiel")
    k["haushalt"]["kinder"] = [{"name": "Lia", "geburtsdatum": "2018-03-01", "eltern": "gemeinsam"}]
    assert konfig.vollname(k, "Anna") == "Anna Muster" and konfig.vollname(k, "Lia") == "Lia Muster"
    k["haushalt"]["kinder"][0]["nachname"] = "Beispiel"
    assert konfig.vollname(k, "Lia") == "Lia Beispiel"
    text = vf.text(k, "testament", "Anna")
    assert "Anna Muster" in text and "Anna Muster Muster" not in text
    assert konfig.namen_ausschreiben(k, "Annabelle und Ben Beispiel") == "Annabelle und Ben Beispiel"
    assert konfig.namen_trennen("Anna Maria Muster-Beispiel") == ("Anna Maria", "Muster-Beispiel")


def test_person_umbenennen_fuehrt_alles_nach(k, db):
    import konfig
    import verwaltung as vw
    k["personen"][0]["name"] = "Anna Muster"
    k["verfuegungen"] = {"testament": {"Anna Muster": {"ziel": "partner"}}}
    k["haushalt"]["kinder"] = [{"name": "Lia", "eltern": "Anna Muster", "obhut": "Anna Muster"}]
    kid = vm.konto_anlegen(db, "Sparkonto", "bank", "Anna Muster")
    konfig.person_umbenennen(k, "Anna Muster", "Anna")
    assert "Anna" in k["verfuegungen"]["testament"] and k["haushalt"]["kinder"][0]["eltern"] == "Anna"
    assert k["personen"][0]["name"] == "Anna Muster"                 # der Name selbst wird vom Aufrufer gesetzt
    assert vw.person_umbenennen_db(db, "Anna Muster", "Anna") == 1
    assert db.execute("SELECT person FROM konten WHERE id = ?", (kid,)).fetchone()[0] == "Anna"


KK_2027 = ("﻿Versicherer,Kanton,Hoheitsgebiet,Geschäftsjahr,Erhebungsjahr,Region,Altersklasse,Unfalleinschluss,Tarif,"
           "Tariftyp,Altersuntergruppe,Franchisestufe,Franchise,Prämie,isBaseP,isBaseF,Tarifbezeichnung\n"
           "8,BL,P_OKPCH,2027,2026,PR_REG_1,AKA_03_ERW,OHN_UNF,B1,BASE,E1,FRASTU_01,FRA_01_E_0300,500.0,1,1,Standard\n"
           "8,BL,P_OKPCH,2027,2026,PR_REG_1,AKA_03_ERW,OHN_UNF,B1,BASE,E1,FRASTU_06,FRA_06_E_2500,380.0,0,0,Standard\n"
           "312,BL,P_OKPCH,2027,2026,PR_REG_1,AKA_03_ERW,OHN_UNF,HMO,PRAXIS,E1,FRASTU_01,FRA_01_E_0300,450.0,0,1,HMO\n"
           "312,BL,P_OKPCH,2027,2026,PR_REG_2,AKA_03_ERW,OHN_UNF,HMO,PRAXIS,E1,FRASTU_01,FRA_01_E_0300,420.0,0,1,HMO\n"
           "312,ZH,P_OKPCH,2027,2026,PR_REG_1,AKA_03_ERW,OHN_UNF,HMO,PRAXIS,E1,FRASTU_01,FRA_01_E_0300,600.0,0,1,HMO\n")
KK_2026 = ("Versicherer,Kanton,Hoheitsgebiet,Geschäftsjahr,Erhebungsjahr,Region,Altersklasse,Unfalleinschluss,Tarif,"
           "Tariftyp,Altersuntergruppe,Franchisestufe,Franchise,Prämie,isBaseP,isBaseF,Tarifbezeichnung\n"
           "8,BL,CH,2026,2025,PR-REG CH1,AKL-ERW,OHN-UNF,B1,TAR-BASE,E1,FRAST1,FRA-300,480.0,1,1,Standard\n")


def test_kassenvergleich_bag_praemien(k, db):
    import kkpraemien as kp
    assert kp.einlesen(db, KK_2026.encode(), "BL") == (2026, 1)
    assert kp.einlesen(db, KK_2027.encode(), "bl") == (2027, 4)          # nur der Kanton
    assert kp.jahre(db, "BL") == [2027, 2026]
    a = kp.angebote(db, "BL", 1, "ERW", False, 0)
    assert [(x.kasse, x.franchise) for x in a] == [("CSS", 2500), ("Atupri", 300), ("CSS", 300)]
    a = kp.angebote(db, "BL", 1, "ERW", False, 5000)                       # hohe Kosten: tiefe Franchise lohnt
    assert (a[0].kasse, a[0].franchise) == ("Atupri", 300)
    assert kp.angebote(db, "BL", 1, "ERW", False, 0, 2026)[0].praemie_monat == 480
    k["haushalt"]["kanton"] = "BL"
    vertraege = [{"sparte": "kvg", "notiz": "Prämienregion BL 2", "person": "Person 1"}]
    assert kp.region_aus_policen(vertraege, "BL") == 2
    k["krankenkasse"]["region"] = "1"
    erg = kp.vergleich(k, db, [])
    assert erg["jahr"] == 2027 and erg["region"] == 1 and erg["personen"][0]["angebote"]


def test_wertschriften_positionen(k, db):
    from pathlib import Path
    import esteuerauszug as es
    import wertschriften as ws
    es.speichern(db, es.lesen((Path(__file__).parent / "daten" / "esteuerauszug_beispiel.xml").read_bytes()))
    u = ws.uebersicht(k, db)
    assert u.wert == 40000 and u.waehrungen == {"CHF": 25000, "USD": 15000} and u.ohne_ter == 1
    k["wertschriften"] = {"ter": {"CH0000000001": 0.4}}
    assert ws.uebersicht(k, db).kosten == 100
    neu = ws.csv_lesen("Datum;Depot;ISIN;Name;Kategorie;Währung;Menge;Kurs;Wert CHF\n"
                       "31.12.2026;Raiffeisen Depot …3456;CH0000000001;Fonds A;FUND;CHF;100;270;27000\n"
                       "31.12.2026;Raiffeisen Depot …3456;CH0000000003;Swiss Bond Index Fund;FUND;CHF;10;100;1000\n".encode())
    ws.speichern(db, neu, "csv")
    u = ws.uebersicht(k, db)
    assert u.stichtag == "2026-12-31" and u.vorjahr == "2025-12-31"
    fonds_a = next(p for p in u.positionen if p.isin == "CH0000000001")
    assert fonds_a.rendite == 8.0 and u.klassen == {"Aktien": 27000, "Obligationen": 1000}
    assert ws.aktienwert(k, db) == 27000


def test_wiederkehrende_zahlungen():
    import abos
    from datetime import date
    b = []
    for m in range(1, 13):
        b.append({"datum": f"2026-{m:02d}-05", "betrag": -29.9 if m < 9 else -34.9, "text": f"STREAMING AG Karte 1234 {m}",
                  "kategorie": "Telekom und Abos"})
        b.append({"datum": f"2026-{m:02d}-1{m % 9}", "betrag": -float(40 + m * 7), "text": "Grossverteiler Musterhausen",
                  "kategorie": "Lebensmittel"})
    for m in (1, 4, 7, 10):
        b.append({"datum": f"2026-{m:02d}-01", "betrag": -412.3, "text": "Musterkasse Gesundheit QR 99", "kategorie": "KK"})
    erg = {a.schluessel: a for a in abos.erkennen(b, [{"versicherer": "Musterkasse", "sparte": "kvg"}], date(2026, 12, 10))}
    assert set(erg) == {"streaming", "musterkasse gesundheit"}
    s = erg["streaming"]
    assert (s.rhythmus, s.betrag, s.aenderung, s.naechste) == ("monatlich", 34.9, 16.7, "2027-01-04")
    q = erg["musterkasse gesundheit"]
    assert q.rhythmus == "vierteljährlich" and q.pro_jahr == 1649.2 and q.vertrag == "Musterkasse (kvg)"


def test_finanzplan_monte_carlo(k):
    import finanzplan as fp
    k["haushalt"]["bedarf_ruhestand"] = 60000
    p = fp.rechnen(k, 300000, 2026, pfade=300)
    assert p.jahre[0].jahr == 2026 and p.end_jahr >= p.pension_jahr and p.erfolg == 100
    assert p.bedarf_sicher and p.bedarf_sicher > 60000
    k["haushalt"]["bedarf_ruhestand"] = 400000
    q = fp.rechnen(k, 0, 2026, pfade=300)
    assert q.erfolg < 10 and q.reicht_bis and q.reicht_bis < q.end_jahr
    assert q.perzentile[10][-1][1] <= q.perzentile[90][-1][1]


SNB_ZIKREPRO = ('"CubeId";"zikrepro"\n"PublishingDate";"2026-11-02 09:00"\n\n"Date";"D0";"D1";"Value"\n'
                '"2026-07";"M";"50";"1.60"\n"2026-08";"M";"50";"1.70"\n"2026-09";"M";"50";"1.80"\n"2026-10";"M";"50";"1.90"\n'
                '"2026-10";"M";"10";"2.10"\n"2026-10";"M";"20";"1.40"\n"2026-10";"M";"SARJ03";"1.05"\n'
                '"2026-10";"M";"MV";"2.80"\n"2026-10";"05Q";"50";"1.85"\n"2026-10";"M";"S1";"0.20"\n')
SNB_ZIREPO = ('"CubeId";"zirepo"\n"PublishingDate";"2026-11-12 18:00"\n\n"Date";"D0";"Value"\n'
              '"2026-11-11";"H0";"0.05"\n"2026-11-12";"H0";"0.04"\n"2026-11-12";"H6";"0.10"\n')


def test_marktzinsen_snb_und_offerten(k, db):
    from datetime import date
    import hypothek as hy
    import marktzinsen as mz
    assert mz.einlesen(db, SNB_ZIKREPRO, SNB_ZIREPO) == 10
    akt = mz.aktuell(db)
    assert akt["fest5"] == (1.9, "2026-10") and akt["saron"] == (0.04, "2026-11-12") and akt["variabel"][0] == 2.8
    assert mz.trend(db, "fest5") == 0.3
    k["wohnen"]["strategie"] = {}
    cfg = hy.konfiguration(k, db)
    assert cfg["fest"][5] == 1.9 and cfg["fest"][10] == 2.1 and cfg["saron"] == 0.04 and cfg["marge_saron"] == 1.01
    assert cfg["herkunft"]["fest5"].startswith("SNB")
    k["wohnen"]["strategie"]["offerten"] = [
        {"bank": "Musterbank", "produkt": "fest5", "zins": 1.72, "datum": date.today().isoformat()},
        {"bank": "Alte Bank", "produkt": "fest10", "zins": 1.5, "datum": "2020-01-01"}]       # zu alt
    cfg = hy.konfiguration(k, db)
    assert cfg["fest"][5] == 1.72 and cfg["herkunft"]["fest5"] == "Offerte Musterbank" and cfg["fest"][10] == 2.1
    k["wohnen"]["strategie"]["fest"] = {5: 1.55}                                                 # Einstellungen gehen vor
    assert hy.konfiguration(k, db)["fest"][5] == 1.55
    k["wohnen"]["aktiv"] = False
    assert mz.aktualisieren(k, db) is False


def test_neue_erinnerungen_und_finanzplan_ampel(k, daten, db):
    from datetime import date
    import ampel as am
    import budget as bu
    import erinnerungen as er
    k["personen"][0]["name"] = "Anna Muster"
    k["haushalt"]["bedarf_ruhestand"] = 400000
    b = [(f"2026-{m:02d}-05", -29.9 if m < 10 else -34.9, "STREAMING AG") for m in range(1, 12)]
    bu.speichern(db, "Bank", b, k)
    titel = {e.titel for e in er.alle(k, db, date(2026, 11, 20))}
    assert "Vor- und Nachname trennen" in titel and "Notfallordner und Verfügungen prüfen" in titel
    assert "Finanzplan ist knapp" in titel and any(t.startswith("Teurer geworden") for t in titel)
    assert "E-Steuerauszüge 2026 einlesen" in {e.titel for e in er.alle(k, db, date(2027, 2, 1))}
    fp = next(a for a in am.bewerten(k, db, date(2026, 11, 20)) if a.bereich == "Finanzplan")
    assert fp.status == am.ROT


def test_leistung_messen_und_vorschlagen(db, tmp_path):
    import leistung as le
    import vorsorge as vs_
    le._WERTE.clear()
    assert le.seitenname("versicherungen/12/speichern") == "versicherungen/‹id›/speichern" and le.seitenname("") == "übersicht"
    alt = vs_.pensionsluecke
    try:
        assert le.instrumentieren() > 10 and vs_.pensionsluecke is not alt and le.instrumentieren() == 0
    finally:
        vs_.pensionsluecke = alt
    for ms in (2500, 3500, 3000):
        le.erfassen("seite", "finanzplan", ms)
    le.erfassen("funktion", "ampel.bewerten", 100)
    le.sichern(db, "1.0.0")
    for _ in range(5):
        le.erfassen("funktion", "ampel.bewerten", 400)
    ms, vorher = le.messungen(db, "1.1.0")
    assert vorher == "1.0.0" and ms[0].name == "ampel.bewerten" and ms[0].vorher_ms == 100
    ms, _ = le.messungen(db, "1.0.0")
    assert {m.name: m.mittel_ms for m in ms}["finanzplan"] == 3000
    import meta
    import unittest.mock as um
    with um.patch.object(meta, "version", return_value="1.1.0"):
        titel = [t for t, _, _ in le.vorschlaege(db, tmp_path)]
    assert "«ampel.bewerten» ist langsamer geworden" in titel
    s = le.system(db, tmp_path)
    assert s["kerne"] >= 1 and "zeilen" in s
    assert any(z.startswith("System:") for z in le.bericht_text(db, tmp_path))


def test_zwischenspeicher(tmp_path):
    import sqlite3
    import time as _t
    import zwischenspeicher as zs
    zs.leeren()
    db = sqlite3.connect(tmp_path / "z.sqlite")
    db.execute("CREATE TABLE t (x INTEGER)")
    db.commit()
    aufrufe = []

    @zs.speichernd("test.summe")
    def summe(k, db_):
        aufrufe.append(1)
        return {"s": sum(r[0] for r in db_.execute("SELECT x FROM t")), "k": k["a"]}
    assert summe({"a": 1}, db) == {"s": 0, "k": 1} and summe({"a": 1}, db)["s"] == 0 and len(aufrufe) == 1
    summe({"a": 1}, db)["s"] = 99                                  # Kopie – der Speicher bleibt unverändert
    assert summe({"a": 1}, db)["s"] == 0
    assert summe({"a": 2}, db)["k"] == 2 and len(aufrufe) == 2     # andere Konfiguration
    _t.sleep(0.01)
    db.execute("INSERT INTO t VALUES (5)")
    assert summe({"a": 1}, db)["s"] == 5                           # offene Transaktion: neu gerechnet
    db.commit()
    n = len(aufrufe)
    assert summe({"a": 1}, db)["s"] == 5 and len(aufrufe) == n + 1  # Änderung gespeichert: neuer Stand
    assert summe({"a": 1}, db)["s"] == 5 and len(aufrufe) == n + 1
    mem = sqlite3.connect(":memory:")
    mem.execute("CREATE TABLE t (x INTEGER)")
    summe({"a": 1}, mem), summe({"a": 1}, mem)
    assert len(aufrufe) == n + 3                                    # im Arbeitsspeicher nie zwischengespeichert


def test_vergleich_mit_schweizer_haushalten(k, db):
    import budget as bu
    import habe
    assert habe.einkommensklasse(5000)[0] == "4669_7004" and habe.einkommensklasse(20000)[0] == "ab_13717"
    k["personen"][0]["lohn_brutto"] = 90000
    k["personen"][1]["lohn_brutto"] = 30000
    k["haushalt"]["kinder"] = []
    assert habe.haushaltstyp(k, 2026) == "paar_u65"
    k["haushalt"]["kinder"] = [{"name": "Lia", "geburtsdatum": "2018-01-01", "eltern": "gemeinsam"}]
    assert habe.haushaltstyp(k, 2026) == "paar_kinder"
    b = []
    for m in range(1, 13):
        b += [(f"2025-{m:02d}-25", 8000.0, "Lohn"), (f"2025-{m:02d}-01", -3200.0, "Miete Verwaltung"),
              (f"2025-{m:02d}-10", -900.0, "Migros"), (f"2025-{m:02d}-28", -31.0, "Monatsende")]
    bu.speichern(db, "Bank", b, k)
    db.execute("UPDATE buchungen SET kategorie = 'Wohnen' WHERE text LIKE 'Miete%'")
    db.execute("UPDATE buchungen SET kategorie = 'Lebensmittel' WHERE text = 'Migros'")
    db.commit()
    v = habe.vergleichen(k, db, 2026)
    wohnen = next(z for z in v.zeilen if z.kategorie == "Wohnen")
    assert v.typ == "Paare mit Kindern" and v.klasse == "CHF 9'734–13'716"
    assert wohnen.eigen == 3200 and wohnen.typ == 1626 and wohnen.abweichung > 50
    assert any(h.startswith("Wohnen:") for h in v.hinweise) and v.sparquote is not None


def test_vergleich_ohne_buchungen(k, db):
    import habe
    import seiten
    k["personen"][0]["lohn_brutto"] = 90000
    v = habe.vergleichen(k, db, 2026)
    assert v and not v.aus_budget and v.hinweise[0].startswith("Noch keine Buchungen")
    assert next(z for z in v.zeilen if z.kategorie == "Steuern").eigen > 0
    html = seiten.budget(k, db)
    assert "Vergleich mit Schweizer Haushalten" in html and "Noch keine Buchungen" in html


def test_stellenverlust_alv(k, db):
    from datetime import date
    import lebensereignisse as le
    k["haushalt"]["kinder"] = []
    p = k["personen"][0]
    p.update(geburtsdatum="1985-01-01", lohn_brutto=180000, sparen_monat=0)
    s = le.stellenverlust(k, db, p["name"], date(2026, 6, 1))
    assert s.versichert_monat == 12350 and s.satz == 70 and s.taggelder == 400 and s.wartetage == 20
    assert abs(s.taggeld - 12350 * 0.7 / 21.7) < 0.01
    assert any("höchstens CHF 148'200" in h for h in s.hinweise)
    p["geburtsdatum"] = "1965-01-01"
    assert le.stellenverlust(k, db, p["name"], date(2026, 6, 1)).taggelder == 640      # ab 55 und 4 Jahre vor AHV-Alter
    k["haushalt"]["kinder"] = [{"name": "Lia", "geburtsdatum": "2015-01-01", "eltern": "gemeinsam"}]
    assert le.stellenverlust(k, db, p["name"], date(2026, 6, 1)).satz == 80


def test_trennung_und_aufteilung(k, db):
    import lebensereignisse as le
    a, b = k["personen"][0], k["personen"][1]
    k["haushalt"]["zivilstand"] = "verheiratet"
    a.update(eigengut=20000, lohn_brutto=120000)
    b.update(eigengut=0, lohn_brutto=60000)
    a["saeule3a"]["guthaben"], b["saeule3a"]["guthaben"] = 0, 0
    a["pk"].update(altersguthaben=200000, guthaben_heirat=50000)
    b["pk"].update(altersguthaben=60000, guthaben_heirat=10000)
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Konto A", "bank", a["name"]), "2026-01-31", 100000)
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Konto B", "bank", b["name"]), "2026-01-31", 20000)
    t = le.trennung(k, db)
    x, y = t.anteile
    # Errungenschaft: A 100'000 − 20'000 = 80'000, B 20'000 → je 50'000; A behält Eigengut 20'000
    assert (x.anspruch, y.anspruch) == (70000, 50000) and (x.ausgleich, y.ausgleich) == (-30000, 30000)
    assert (x.pk_ausgleich, y.pk_ausgleich) == (-50000, 50000)                         # (150'000 − 50'000) / 2
    k["haushalt"]["zivilstand"] = "ledig"
    t = le.trennung(k, db)
    assert t.anteile[0].ausgleich == 0 and t.anteile[0].pk_ausgleich == 0
    auf = le.aufteilung(k, db, 3000)
    gleich = next(v for v in auf.varianten if v.name.startswith("Gleich"))
    assert abs(gleich.frei[a["name"]] - gleich.frei[b["name"]]) <= 1
    prop = next(v for v in auf.varianten if v.name.startswith("Im Verhältnis"))
    assert prop.beitraege[a["name"]] == 2000 and prop.beitraege[b["name"]] == 1000


def test_lebensziele_im_finanzplan(k):
    import finanzplan as fp
    k["haushalt"]["bedarf_ruhestand"] = 70000
    k["ziele"] = [{"name": "Weltreise", "betrag": 60000, "jahr": 2029, "art": "wunsch"},
                  {"name": "alt", "betrag": 1000, "jahr": 2001}]
    p = fp.rechnen(k, 20000, 2026, pfade=200)
    assert [z["name"] for z in p.ziele] == ["Weltreise"] and p.ziele[0]["sparrate"] == 1667
    assert p.erfolg_ohne_ziele is not None and p.erfolg <= p.erfolg_ohne_ziele
    ohne = fp.rechnen({**k, "ziele": []}, 20000, 2026, simulation=False)
    jahr_2030 = lambda plan: next(z.vermoegen for z in plan.jahre if z.jahr == 2030)  # noqa: E731
    assert jahr_2030(ohne) - jahr_2030(fp.rechnen(k, 20000, 2026, simulation=False)) > 60000


# ---------------------------------------------------------------- Lebenslauf der Kinder

def test_kinderphasen_zeitplan_und_vergleich(k):
    import kinderphasen as kp
    _kinder(k, {"name": "A", "geburtsdatum": "2020-05-10", "kita_tage": 2},
            {"name": "B", "geburtsdatum": "2020-09-10", "weg": "gymnasium", "auswaerts": True})
    a, b = kp.alle(k, date(2026, 11, 13))
    assert [p.schluessel for p in a.phasen] == ["kleinkind", "kita", "kindergarten", "primar", "sek1", "lehre"]
    kg = next(p for p in a.phasen if p.schluessel == "kindergarten")
    assert kg.von == date(2024, 8, 1) and a.selbstaendig == date(2038, 8, 1)       # Stichtag 31. Juli
    assert next(p for p in b.phasen if p.schluessel == "kindergarten").von == date(2025, 8, 1)
    assert [p.schluessel for p in b.phasen][-2:] == ["gymnasium", "studium"] and b.selbstaendig == date(2045, 8, 1)
    kita = a.phasen[1]
    assert kita.betreuung_vergleich == round(2 * 127 * 50 / 12) and kita.leben_vergleich == 475   # eines von 2 Kindern
    assert b.phasen[-1].leben_vergleich == 1600 and b.phasen[-1].betreuung_vergleich == 290
    assert a.aktuell.schluessel == "primar" and a.rest < sum(p.total for p in a.phasen)
    assert kp.leben_vergleich(3) == 665 and kp.leben_vergleich(10, 3) == 660 and kp.leben_vergleich(15, 2) == 1035
    assert any("Ausbildungsende" in h for h in b.hinweise)                          # Studium bis 24, Abzug bis 18


def test_kinderphasen_eigene_kosten_steuern_finanzplan(k):
    import finanzplan as fp
    import kinder as ki
    import kinderphasen as kp
    _kinder(k, {"name": "A", "geburtsdatum": "2024-02-01", "kita_tage": 3, "ausbildung_bis": 18,
                "phasen": {"kita": {"betreuung": 1500}, "primar": {"leben": 500}}})
    c = ki.liste(k)[0]
    lauf = kp.lebenslauf(c, 1, date(2026, 1, 1))
    kita = next(p for p in lauf.phasen if p.schluessel == "kita")
    assert kita.betreuung == 1500 and kita.betreuung_vergleich > 1500
    assert ki.betreuung_jahr(c, 2026) == 18000 and ki.betreuung_jahr(c, 2028) == 1500 * 7 and ki.betreuung_jahr(c, 2029) == 0   # Kita bis Juli 2028
    # Finanzplan: Veränderung gegenüber dem ersten Jahr, nach der Selbständigkeit sinken die Kosten
    jahre = list(range(2026, 2050))
    d = kp.finanzplan(k, jahre, 2060)
    assert 2026 not in d and d[2045] < 0
    p = fp.rechnen(k, 100_000, 2026, simulation=False)
    assert p.kinder and any("Lebenslauf der Kinder" in h for h in p.hinweise)
    k["finanzplan"] = {"kinderkosten": False}
    assert kp.finanzplan(k, jahre, 2060) == {}


def test_kinderphasen_alte_betreuung_und_erinnerungen(k):
    import kinder as ki
    import kinderphasen as kp
    _kinder(k, {"name": "A", "geburtsdatum": "2023-09-20", "betreuung_jahr": 12000, "betreuung_bis": 6})
    c = ki.liste(k)[0]
    assert ki.betreuung_jahr(c, 2026) == 12000                                       # ohne Lebenslauf: alte Regel
    lauf = kp.lebenslauf(c, 1, date(2026, 11, 13))
    assert [p.betreuung_eigen for p in lauf.phasen[:3]] == [1000, 1000, None]
    e = kp.erinnerungen(k, date(2027, 12, 15))
    assert any("Kindergarten" in x.titel and "kostet A" in x.text for x in e)


# ---------------------------------------------------------------- Säule 3a als Konten

def test_3a_art_erkennen_und_umstellen(tmp_path):
    assert vm.ist_3a("VIAC …1234") and vm.ist_3a("Vorsorgekonto 3a Musterbank") and vm.ist_3a("Konto", "frankly")
    assert not vm.ist_3a("3b Musterversicherung") and not vm.ist_3a("Privatkonto") and not vm.ist_3a("Freizügigkeit 3a")
    db = vm.verbinden(tmp_path / "t.sqlite")
    vm.konto_anlegen(db, "finpension 3a", "vorsorge", "Anna")
    vm.konto_anlegen(db, "3b Police Muster", "vorsorge", "Anna")
    db.execute("DROP TABLE konten_3a_umgestellt")          # Stand vor 0.41: noch nicht umgestellt
    db.commit()
    db = vm.verbinden(tmp_path / "t.sqlite")
    arten = {x["name"]: x["art"] for x in vm.konten(db)}
    assert arten == {"finpension 3a": "saeule3a", "3b Police Muster": "vorsorge"}


def test_3a_gebunden_nicht_frei():
    db = vm.verbinden(":memory:")
    for name, art, wert in (("Lohn", "bank", 10_000), ("3a A", "saeule3a", 30_000), ("3b A", "vorsorge", 5_000)):
        vm.saldo_setzen(db, vm.konto_anlegen(db, name, art, "Anna"), "2026-10-31", wert)
    nv = vm.nettovermoegen(db)
    assert nv["total"] == 45_000 and nv["gebunden"] == 35_000 and nv["verfuegbar"] == 10_000
    assert nv["frei"] == 15_000                            # 3a über das 3a-Modell, 3b zählt bei der Pensionierung mit


def test_3a_abgleich_anlegen_und_bezugsplan(k):
    import dreia
    db = vm.verbinden(":memory:")
    p1 = k["personen"][0]
    p1["geburtsdatum"] = "1970-06-01"
    p1["saeule3a"]["guthaben"] = 12_000
    k["personen"][1]["saeule3a"]["guthaben"] = 0
    assert [p["name"] for p in dreia.ohne_konto(k, db)] == [p1["name"]]
    assert dreia.anlegen(k, db, date(2026, 11, 1)) == [f"3a {p1['name']}"]
    vm.saldo_setzen(db, vm.konto_anlegen(db, "3a Musterbank", "saeule3a", p1["name"]), "2026-10-31", 36_000)
    assert dreia.abgleichen(k, db) and not dreia.abgleichen(k, db)
    cfg = p1["saeule3a"]
    assert (cfg["guthaben"], cfg["konten"], cfg["anteile"], cfg["aus_konten"]) == (48_000, 2, [0.25, 0.75], True)
    plan = dreia.bezugsplan(k, db)
    pj = st.pensionsjahr(p1)
    assert [(b.konto, b.jahr) for b in plan] == [(f"3a {p1['name']}", pj - 1), ("3a Musterbank", pj)]
    # Steuern: gestaffelt im Verhältnis der Kontostände
    class E:
        kapital = 0.0
    class D:
        kapital = 100_000.0
    assert st._bezuege(p1, E, D, True) == {pj - 1: 25_000, pj: 75_000}
    # Konten gelöscht → Wert bleibt, gilt wieder als von Hand
    db.execute("DELETE FROM konten")
    assert dreia.abgleichen(k, db) and "aus_konten" not in cfg and cfg["guthaben"] == 48_000


def test_kassenvergleich_praemie_unplausibel(k, db):
    import kkpraemien as kp
    kp.einlesen(db, KK_2027.encode(), "BL")
    k["haushalt"]["kanton"] = "BL"
    k["krankenkasse"]["region"] = 1
    police = {"id": 1, "sparte": "kvg", "person": "Person 1", "versicherer": "Atupri Gesundheitsversicherung",
              "franchise": 300, "praemie_jahr": 900 * 12, "modell": "hmo", "unfall_eingeschlossen": 0, "notiz": "",
              "beginn": "2026-01-01", "geburtsdatum": ""}
    k["krankenkasse"]["personen"] = [{"name": "Person 1", "kosten_jahr": 1000}]      # Rest aus der Police
    e = next(x for x in kp.vergleich(k, db, [police])["personen"] if x["person"].name == "Person 1")
    assert e["person"].praemie_monat == 900 and e["person"].kosten_jahr == 1000 and e["person"].franchise == 300
    assert e["zu_hoch"] and e["bezug_monat"] == 450 and e["heute_kvg"] == 450 * 12 + 300 + 70


# ---------------------------------------------------------------- Sparen und Anlegen

def test_sparplan_reihenfolge_und_verteilung(k):
    import sparplan as sp
    db = vm.verbinden(":memory:")
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Lohn", "bank", ""), "2026-10-31", 80_000)
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Depot", "depot", ""), "2026-10-31", 30_000)
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Leasing", "kredit", ""), "2026-10-31", -12_000)
    k["ziele"] = [{"name": "Auto", "betrag": 20_000, "jahr": 2029}]
    for p in k["personen"]:
        p["sparen_monat"] = 1500
    k["personen"][0]["saeule3a"]["beitrag_jahr"] = 3000
    k["wohnen"]["aktiv"] = False
    p = sp.rechnen(k, db, date(2026, 11, 13))
    s = {x.nr: x for x in p.schritte}
    reserve = 50_000                                                    # Vorlage: Bedarf/2
    assert s[1].status == sp.ERLEDIGT and p.ueberschuss == 80_000 - reserve
    assert s[2].jetzt == 12_000 and s[2].monat == 0                     # Kredit sofort vom Konto
    assert s[3].status == sp.TEILWEISE and s[3].jetzt == 4258 and s[3].monat == round(2 * 7258 / 12)
    assert s[4].jetzt == 30_000 - 12_000 - 4258 and s[4].monat > 0     # Rest des Überschusses fürs Auto
    assert sum(x.monat for x in p.schritte) == 3000 and s[6].monat == 3000 - s[3].monat - s[4].monat
    assert [x.name for x in p.klassen][0].startswith("Aktien") and p.naechster_kauf
    assert any(a.topf == "Säule 3a" for a in p.produktarten)


def test_sparplan_ohne_sparpotenzial_und_reserve_luecke(k):
    import sparplan as sp
    db = vm.verbinden(":memory:")
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Lohn", "bank", ""), "2026-10-31", 10_000)
    k["wohnen"]["aktiv"] = False
    for p in k["personen"]:
        p["sparen_monat"] = 0
    p = sp.rechnen(k, db, date(2026, 11, 13))
    assert p.schritte[0].status == sp.OFFEN and p.schritte[0].einmalig == 40_000
    assert any("Kein Sparpotenzial" in h for h in p.hinweise) and not any("reicht" in h for h in p.hinweise)


# ---------------------------------------------------------------- Usability

def test_usability_html_pruefung():
    import usability as us
    breit = "<table><thead><tr>" + "<th>x</th>" * 7 + "</tr></thead><tbody><tr>" + "<td>1</td>" * 7 + "</tr></tbody></table>"
    karten = '<section class="karte"></section>' * 11
    formular = "<form>" + '<input name="a">' * 31 + "<button>OK</button></form>"
    html = (breit + karten + formular + '<div class="kpi"></div>' * 8 + '<svg viewBox="0 0 1 1"></svg>'
            + "<p>" + "x" * 50 + "</p>")
    titel = {p.titel for p in us.pruefen_html(html)}
    assert {"Tabelle scrollt auf dem Handy seitlich", "Seite sehr lang", "Sehr grosses Formular",
            "Eingabefelder ohne Beschriftung", "Viele Kennzahlen auf einmal", "Diagramme ohne Beschreibung",
            "Sehr lange Wörter laufen auf dem Handy über"} <= titel
    gut = ('<table class="responsiv"><thead><tr><th>a</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>'
           '<form><label>Name<input name="n"></label><button>OK</button></form>')
    assert us.pruefen_html(gut) == []


def test_usability_kontrast_und_alle_seiten(k, daten):
    import seiten
    import usability as us
    assert round(us.kontrast("#ffffff", "#000000")) == 21
    assert us.darstellung(seiten.CSS) == []                      # alle Farbpaare in Hell und Dunkel ≥ 4.5:1
    schlecht = ":root{--text:#777777;--karte:#888888}html[data-theme=dark]{--akzent:#4fb3d4}"
    assert us.darstellung(schlecht)
    db = vm.verbinden(":memory:")
    e = us.pruefen(k, db, "9.9.9")
    assert e.seiten and 0 <= e.score <= 100 and all(s.score > 0 for s in e.seiten)
    assert not any(p.titel == "Seite lässt sich nicht anzeigen" for s in e.seiten for p in s.probleme)
    us.sichern(db, e)
    assert us.letztes(db)[0].score == e.score and us.bericht_text(db)[0].startswith("Usability-Score")
    assert not us.faellig(db, "9.9.9", e.zeit[:10]) and us.faellig(db, "9.9.10", e.zeit[:10])


def test_sparplan_hypothek_ist_keine_teure_schuld(k):
    import sparplan as sp
    db = vm.verbinden(":memory:")
    vm.saldo_setzen(db, vm.konto_anlegen(db, "Hypothek Musterbank", "hypothek", ""), "2026-10-31", -600_000)
    s2 = sp.rechnen(k, db, date(2026, 11, 13)).schritte[1]
    assert s2.status == sp.ENTFAELLT and "Hypothek (CHF 600'000) zählt nicht" in s2.text


def test_waehrungen_revolut_und_wise():
    import waehrung as wg
    revolut = "AED AUD BGN CAD CHF CLP COP CZK DKK EGP EUR GBP HKD HUF ILS INR ISK JPY KRW KZT MAD MXN NOK NZD PHP PLN QAR " \
              "RON RSD SAR SEK SGD THB TRY USD ZAR".split()
    assert set(revolut) <= set(wg.WAEHRUNGEN) and {"KES", "NGN", "VND", "XOF", "UAH"} <= set(wg.WAEHRUNGEN)
    assert wg.WAEHRUNGEN[:4] == ["CHF", "EUR", "USD", "GBP"] and wg.name("sek") == "SEK – Schwedische Krone"
    k = wg.kurse()
    assert round(k["BGN"][0], 4) == round(0.92 / 1.95583, 4) and "fest an EUR" in k["XOF"][1]
    assert wg.erkennen("PENSIONSKASSE Konto in SEK, Saldo SEK 1'000") == "SEK"      # «PEN» in «PENSION» zählt nicht
    assert wg.erkennen("Kontoauszug CHF") == "CHF"
