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
    assert st.kantonssteuer(s["steuerbar_kanton"] - 1000, s) == s["steuer_kanton_gemeinde"] - 220


def test_ersparnis_abzug(k):
    e = st.ersparnis_abzug(k, 7258)
    assert e["kanton"] == round(7258 * 0.22)
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
    summe = lambda name: sum(z[1] for z in v[name]["zeilen"])  # noqa: E731
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
