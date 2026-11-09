import pytest

import steuern as st
import vorsorge as vs
import wohnen as wo


@pytest.mark.parametrize("einkommen,verheiratet,erwartet", [
    (29_700, True, 0), (53_400, True, 237), (100_000, True, 1_816), (200_000, True, 11_887),
    (1_000_000, True, 115_000), (50_000, False, 400.84), (100_000, False, 2_688.07),
])
def test_bundessteuer_tarif(k, einkommen, verheiratet, erwartet):
    assert st.bundessteuer(einkommen, verheiratet, 0, k["kennzahlen"]) == pytest.approx(erwartet, abs=0.5)


def test_elterntarif_und_mindeststeuer(k):
    kz = k["kennzahlen"]
    assert st.bundessteuer(100_000, True, 2, kz) == pytest.approx(1_816 - 2 * 263)
    assert st.bundessteuer(31_000, True, 0, kz) == 0          # unter CHF 25 wird nicht erhoben


def test_kanton_linear(k):
    s = k["steuern"]
    assert st.kantonssteuer(s["steuerbar_kanton"], s) == s["steuer_kanton_gemeinde"]
    assert st.kantonssteuer(s["steuerbar_kanton"] - 1000, s) == pytest.approx(s["steuer_kanton_gemeinde"] - 220, abs=2)
    # grosse Abzüge: progressiv sinkend, nie negativ, Ersparnis höchstens Grenzsteuersatz × Abzug
    gross = s["steuer_kanton_gemeinde"] - st.kantonssteuer(s["steuerbar_kanton"] - 100_000, s)
    assert 100_000 * 0.10 < gross < 100_000 * 0.22


def test_ersparnis_abzug(k):
    e = st.ersparnis_abzug(k, 7258)
    assert e["kanton"] == pytest.approx(7258 * 0.22, rel=0.03)
    assert e["total"] == e["bund"] + e["kanton"]


def test_kapitalsteuer_ein_fuenftel(k):
    kz = k["kennzahlen"]
    k["steuern"]["kapitalbezug_kanton"] = [[0, 0]]
    t = st.kapitalsteuer(200_000, k)
    assert t["bund"] == round(st.tarif_progressiv(200_000, kz["bund_tarif_verheiratet"]) / 5)
    assert t["kanton"] == 0


def test_staffelung_spart_steuern(k):
    pks = [vs.pk(p, k) for p in k["personen"]]
    drei = [vs.saeule3a(p, k, 2026) for p in k["personen"]]
    v = st.kapitalbezug_varianten(k, pks, drei)
    summe = lambda name: sum(z[2] for z in v[name]["zeilen"])  # noqa: E731
    assert summe("gestaffelt") == pytest.approx(summe("alles_auf_einmal"), abs=5)  # gleiches Kapital
    assert v["ersparnis"] > 0


def test_tragbarkeit(k):
    k["wohnen"].update(aktiv=True, kaufpreis=1_000_000, eigenmittel=200_000, unterhalt_pauschal=1.0)
    t = wo.tragbarkeit(k, 2026)
    assert t["hypothek"] == 800_000 and t["belehnung"] == 80.0
    assert t["zweite"] == pytest.approx(800_000 - 667_000)
    assert t["kalk_kosten"] == round(800_000 * 0.05 + 10_000 + t["amortisation"])
    k["wohnen"]["kaufpreis"] = t["max_preis"]
    assert wo.tragbarkeit(k, 2026)["quote"] <= 33.3 + 0.05


def test_eigenmietwert_wegfall(k):
    k["wohnen"].update(eigenmietwert=20_000, kaufpreis=1_000_000, eigenmittel=1_000_000)
    e = wo.eigenmietwert_wegfall(k)
    assert e["netto_heute"] == 16_000 and e["steuereffekt"] < 0   # ohne Schulden: Entlastung


def test_liegenschaft_teilweise_vermietet(k):
    k["haushalt"]["zivilstand"] = "ledig"
    k["wohnen"].update(aktiv=True, eigenmietwert=20_000, vermietet_anteil=38, mieteinnahmen_jahr=29_760,
                       kaufpreis=1_000_000, eigenmittel=400_000, hypothek_zins=2.0)
    s = wo.liegenschaft_steuer(k)
    assert s["eigenmietwert"] == 12_400 and s["mieteinnahmen"] == 29_760 and s["schuldzinsen"] == 12_000
    p1, p2 = (p["name"] for p in k["personen"])
    assert wo.eigentum_anteile(k) == {p1: 50, p2: 50}                     # ohne Angabe gleiche Teile
    h = wo.liegenschaft_steuer(k, p1)
    assert h["eigenmietwert"] == 6_200 and h["mieteinnahmen"] == 14_880 and h["schuldzinsen"] == 6_000
    k["personen"][0]["eigentum_anteil"] = 70                              # Rest an die andere Person
    assert wo.eigentum_anteile(k) == {p1: 70, p2: 30}
    e = wo.eigenmietwert_wegfall(k, aktiven_uebrig=0)
    assert e["zins_quote"] == 38 and e["netto_nachher"] == round(29_760 - 12_000 * 0.38 - 29_760 * 0.2)
    import pruefung
    k["wohnen"]["mieteinnahmen_jahr"] = 0
    assert pruefung.pruefen(k, "wohnen.vermietet_anteil")[0] == "gelb"
    k["personen"][1]["eigentum_anteil"] = 50
    assert pruefung.pruefen(k, "personen.0.eigentum_anteil")[0] == "rot"  # 120 %


def test_liegenschaft_bl_bund_und_unternutzung(k):
    import pruefung
    k["haushalt"]["kanton"] = "BL"
    k["wohnen"].update(aktiv=True, eigenmietwert=20_000, vermietet_anteil=0, mieteinnahmen_jahr=0, zimmer=6,
                       zimmer_ungenutzt=2, kaufpreis=1_000_000, eigenmittel=1_000_000)
    k["wohnen"]["liegenschaft"]["baujahr"] = 1990
    s = wo.liegenschaft_steuer(k)
    assert s["unternutzung"] == 25                                 # 2 ÷ (6 + 2 Nebenräume beim Haus)
    assert s["eigenmietwert"] == 15_000 and s["eigenmietwert_bund"] == 18_000   # Bund = Staat × 1,2
    assert (s["pauschal"], s["pauschal_bund"]) == (25, 20)        # BL Staat 25 %, Bund 20 % (älter als 10 Jahre)
    assert s["netto"] == 11_250 and s["netto_bund"] == 14_400
    k["wohnen"]["liegenschaft"]["art"] = "wohnung"
    assert wo.unternutzung(k) == 2 / 7                            # Stockwerkeigentum: + 1 Nebenraum
    assert pruefung.pruefen(k, "wohnen.eigenmietwert_bund")[0] == "grau"   # automatisch
    k["wohnen"]["eigenmietwert_bund"] = 20_000
    assert pruefung.pruefen(k, "wohnen.eigenmietwert_bund")[0] == "gelb"   # gleich wie Staat
    k["wohnen"]["zimmer_ungenutzt"] = 6
    assert pruefung.pruefen(k, "wohnen.zimmer_ungenutzt")[0] == "rot"
