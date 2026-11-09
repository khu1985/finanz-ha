"""Versicherungen, Vorsorgedokumente, Risiko, Konkubinat, Berater und Import-Ordner (erfundene Daten)."""
import copy
from datetime import date

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
    assert konkubinat["wohnen"]["eigenmietwert"] == 20_000 and konkubinat["personen"][0]["saeule3a"]["beitrag_jahr"] == 5000


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

def test_sensoren(k, db):
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


def test_sensoren_fehler_und_aus(k, db):
    import sensoren

    def kaputt(e, n):
        raise RuntimeError("kein Token")
    sensoren.schreiben(k, db, senden=kaputt)
    assert sensoren.status()["fehler"] == "kein Token"
    k["sensoren"] = {"aktiv": False}
    assert sensoren.schreiben(k, db, senden=kaputt) == []
