import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import konfig
import vermoegen as vm

CSV = "Datum;Konto;Saldo;Art\n31.12.2025;Sparkonto;20'000.50;bank\n31.10.2026;Hypothek;400000;hypothek\nxx;Kaputt;1;bank\n"


def test_zahl_und_datum():
    assert vm.zahl("1'234.50") == 1234.5
    assert vm.zahl("1234,50") == 1234.5
    assert vm.zahl("CHF 1,234.50") == 1234.5
    assert vm.datum("31.12.2025") == "2025-12-31"


def test_csv_import(tmp_path):
    db = vm.verbinden(tmp_path / "t.sqlite")
    n, fehler = vm.csv_import(db, CSV.encode())
    assert n == 2 and len(fehler) == 1
    assert [k["name"] for k in vm.konten(db)] == ["Sparkonto", "Hypothek"] or len(vm.konten(db)) == 2
    assert vm.nettovermoegen(db)["total"] == round(20_000.5 - 400_000)
    assert vm.nettovermoegen(db)["frei"] == round(20_000.5)
    assert "Kaputt" not in [k["name"] for k in vm.konten(db)]


def test_konfig_speichern_mit_backup(daten, k):
    konfig.speichern(k)
    k["haushalt"]["name"] = "Test"
    konfig.speichern(k)
    assert (daten / "finanz.yaml.bak").exists()
    assert konfig.laden()["haushalt"]["name"] == "Test"


def test_konfig_ergaenzt_neue_schluessel(daten, k):
    del k["kennzahlen"]["ahv_max"]
    del k["personen"][0]["saeule3a"]
    konfig.speichern(k)
    neu = konfig.laden()
    assert neu["kennzahlen"]["ahv_max"] == 2520
    assert "guthaben" in neu["personen"][0]["saeule3a"]


@pytest.fixture
def server(daten):
    import server as srv
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


class OhneWeiterleitung(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


def _post(url, daten):
    opener = urllib.request.build_opener(OhneWeiterleitung)
    try:
        opener.open(urllib.request.Request(url, urllib.parse.urlencode(daten).encode()))
    except urllib.error.HTTPError as e:
        return e.code, e.headers["Location"]


@pytest.mark.parametrize("pfad", ["", "vorsorge", "steuern", "wohnen", "vermoegen", "versicherungen", "berater", "einstellungen"])
def test_seiten(server, pfad):
    req = urllib.request.Request(f"{server}/{pfad}", headers={"X-Ingress-Path": "/api/hassio_ingress/xyz"})
    html = urllib.request.urlopen(req).read().decode()
    assert '<base href="/api/hassio_ingress/xyz/">' in html
    assert "Fehler" not in html.split("<main>")[1][:200]


def test_einstellungen_und_saldo(server, daten):
    code, ziel = _post(f"{server}/einstellungen", {"wohnen.aktiv": "ja", "personen.0.lohn_brutto": "125'000"})
    assert code == 303 and ziel.startswith("/einstellungen")
    k = konfig.laden()
    assert k["wohnen"]["aktiv"] is True and k["personen"][0]["lohn_brutto"] == 125_000
    code, _ = _post(f"{server}/vermoegen/saldo", {"konto": "Lohn", "art": "bank", "person": "",
                                                 "datum": "2026-01-31", "betrag": "8'000"})
    assert code == 303
    html = urllib.request.urlopen(f"{server}/vermoegen").read().decode()
    assert "Lohn" in html and "8&#x27;000" in html or "8'000" in html


def test_yaml_fehler_wird_gemeldet(server):
    code, ziel = _post(f"{server}/einstellungen/yaml", {"yaml": "- nur eine liste"})
    assert code == 303 and "f=1" in ziel


def _upload(url, feld, dateiname, inhalt):
    grenze = "----finanztest"
    body = (f"--{grenze}\r\nContent-Disposition: form-data; name=\"{feld}\"; filename=\"{dateiname}\"\r\n"
            "Content-Type: application/pdf\r\n\r\n").encode() + inhalt + f"\r\n--{grenze}--\r\n".encode()
    req = urllib.request.Request(url, body, {"Content-Type": f"multipart/form-data; boundary={grenze}"})
    try:
        urllib.request.build_opener(OhneWeiterleitung).open(req)
    except urllib.error.HTTPError as e:
        return e.code, e.headers["Location"]


def test_uploads_und_detailseiten(server):
    from policen import HAUSRAT, PK_AUSWEIS, pdf
    code, ziel = _upload(f"{server}/versicherungen/hochladen", "datei", "police.pdf", pdf(HAUSRAT))
    assert code == 303 and ziel.startswith("/versicherungen/1")
    html = urllib.request.urlopen(f"{server}/versicherungen/1").read().decode()
    assert "Mobiliar" in html and "HR-998877" in html
    assert urllib.request.urlopen(f"{server}/versicherungen/1/datei").read()[:5] == b"%PDF-"
    code, ziel = _upload(f"{server}/vorsorge/hochladen", "datei", "ausweis.pdf", pdf(PK_AUSWEIS))
    assert ziel.startswith("/vorsorge/dokument/1")
    html = urllib.request.urlopen(f"{server}/vorsorge/dokument/1").read().decode()
    assert "Vorsorgeausweis" in html and "180000" in html
    code, ziel = _post(f"{server}/vorsorge/dokument/1/uebernehmen",
                       {"typ": "pk_ausweis", "person": "Person 1", "wert_einkauf_potenzial": "180000", "nimm_einkauf_potenzial": "1"})
    assert code == 303 and konfig.laden()["personen"][0]["pk"]["einkauf_potenzial"] == 180_000
    code, ziel = _post(f"{server}/berater/fragen", {"profil": "steuern", "frage": "PK-Einkauf?"})
    assert ziel.startswith("/berater/1")
    html = urllib.request.urlopen(f"{server}/berater/1").read().decode()
    assert "Steuerexperte" in html and "PK-Einkauf?" in html
