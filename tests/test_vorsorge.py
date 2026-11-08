import pytest

import vorsorge as vs


def test_rentenskala_eckwerte(k):
    kz = k["kennzahlen"]
    assert vs.ahv_vollrente_monat(10_000, kz) == 1260          # Minimalrente
    assert vs.ahv_vollrente_monat(15_120, kz) == 1260          # Knick 1
    assert vs.ahv_vollrente_monat(45_360, kz) == pytest.approx(1915.2)  # Knick 2, stetig
    assert vs.ahv_vollrente_monat(90_720, kz) == 2520          # Maximalrente
    assert vs.ahv_vollrente_monat(200_000, kz) == 2520


def test_ahv_teilrente_und_plafond(k):
    k["haushalt"]["kinder"] = []
    p1, p2 = k["personen"]
    p1["lohn_brutto"] = p2["lohn_brutto"] = 120_000
    p1["ahv"]["beitragsjahre_bisher"] = p2["ahv"]["beitragsjahre_bisher"] = 44
    erg = vs.ahv(k, 2026)
    assert all(r.rente_monat == 2520 for r in erg)
    assert sum(r.rente_monat_plafoniert for r in erg) == pytest.approx(3780)
    assert erg[0].rente_jahr == round(1890 * 13)               # 13. AHV-Rente
    p1["ahv"]["fehlende_jahre"] = 4
    erg = vs.ahv(k, 2026)
    assert erg[0].beitragsjahre == 40


def test_ahv_vorbezug(k):
    k["personen"] = k["personen"][:1]
    k["haushalt"]["zivilstand"] = "ledig"
    k["personen"][0]["ahv"]["beitragsjahre_bisher"] = 44
    k["personen"][0]["lohn_brutto"] = 120_000
    k["personen"][0]["pensionierung_alter"] = 63
    r = vs.ahv(k, 2026)[0]
    assert r.rente_monat == pytest.approx(2520 * (1 - 2 * 0.068))


def test_erziehungsjahre(k):
    p = k["personen"][0]  # Jahrgang 1985
    assert vs.erziehungsjahre(p, [{"geburtsjahr": 2018}]) == 16
    assert vs.erziehungsjahre(p, [{"geburtsjahr": 2018}, {"geburtsjahr": 2020}]) == 18


def test_bvg_minimum(k):
    kz = k["kennzahlen"]
    assert vs.bvg_koordinierter_lohn(20_000, kz) == 0
    assert vs.bvg_koordinierter_lohn(25_000, kz) == 3780        # Mindestwert
    assert vs.bvg_koordinierter_lohn(60_000, kz) == 60_000 - 26_460
    assert vs.bvg_koordinierter_lohn(200_000, kz) == 90_720 - 26_460
    assert vs.bvg_gutschriftsatz(30, kz) == 7 and vs.bvg_gutschriftsatz(58, kz) == 18


def test_pk_ohne_zins_ist_summe_der_gutschriften(k):
    p = k["personen"][0]
    p["geburtsdatum"] = "1966-01-01"   # 60 im Jahr 2026
    p["pk"].update(altersguthaben=100_000, stand="2026-01-01", zins=0, sparbeitrag_jahr=10_000,
                   kapitalbezug_anteil=50, umwandlungssatz=6.0, einkauf_geplant=[{"jahr": 2028, "betrag": 5000}])
    e = vs.pk(p, k)
    assert e.guthaben_pensionierung == 100_000 + 5 * 10_000 + 5000
    assert e.kapital == 77_500
    assert e.rente_jahr == round(77_500 * 0.06)
    assert any("Sperrfrist" in w for w in e.warnungen)          # Einkauf 2028, Bezug 2031


def test_3a_und_annuitaet(k):
    p = k["personen"][0]
    p["geburtsdatum"] = "1964-01-01"
    p["saeule3a"].update(guthaben=10_000, beitrag_jahr=1_000, rendite=0)
    assert vs.saeule3a(p, k, 2026).kapital == 10_000 + 3 * 1_000
    assert vs.annuitaet(100_000, 10, 0) == 10_000
    assert vs.annuitaet(100_000, 10, 5) == pytest.approx(12_950.46, abs=0.01)


def test_pensionsluecke(k):
    l = vs.pensionsluecke(k, 0, 2026)
    assert l.einkommen == pytest.approx(l.ahv + l.pk_rente + l.kapitalverzehr, abs=2)
    k["haushalt"]["bedarf_ruhestand"] = l.einkommen + 10_000
    assert vs.pensionsluecke(k, 0, 2026).luecke == pytest.approx(10_000, abs=2)
