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
