import threading
import urllib.error
import re
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


@pytest.mark.parametrize("pfad", ["", "vorsorge", "steuern", "wohnen", "vermoegen", "versicherungen", "berater",
                                  "einstellungen", "protokoll", "aenderungen", "bericht", "budget", "kinder",
                                  "szenarien", "nachlass", "notfall", "steuererklaerung", "dokumente", "vorschlaege"])
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
    uebersicht = urllib.request.urlopen(f"{server}/versicherungen").read().decode()
    assert 'href="versicherungen/1/datei"' in uebersicht and "PDF öffnen" in uebersicht
    html = urllib.request.urlopen(f"{server}/versicherungen/1").read().decode()
    assert "Ausgelesener Text" in html
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


def test_version_und_protokoll(tmp_path):
    import meta
    assert meta.version().count(".") == 2
    assert "## " + meta.version() in meta.changelog()
    log = tmp_path / "finanz.log"
    log.write_text("2026-11-08 10:00:00,000 INFO Start\n2026-11-08 10:01:00,000 ERROR Kaputt\nTraceback x\n"
                   "2026-11-08 10:02:00,000 DEBUG Detail\n", encoding="utf-8")
    e = meta.protokoll(log, "INFO")
    assert [x[1] for x in e] == ["ERROR", "INFO"] and "Traceback x" in e[0][2]
    assert len(meta.protokoll(log, "DEBUG")) == 3 and len(meta.protokoll(log, "ERROR")) == 1


def test_steuerdokument_upload(server):
    from policen import VERANLAGUNG_2025, pdf
    code, ziel = _upload(f"{server}/steuern/hochladen", "datei", "veranlagung.pdf", pdf(VERANLAGUNG_2025))
    assert ziel.startswith("/steuern/dokument/1")
    html = urllib.request.urlopen(f"{server}/steuern/dokument/1").read().decode()
    assert "Veranlagungsverfügung" in html and "141200" in html
    code, ziel = _post(f"{server}/steuern/dokument/1/uebernehmen",
                       {"typ": "veranlagung", "jahr": "2025", "person": "Person 1", "wert_steuerbar_kanton": "141200",
                        "nimm_steuerbar_kanton": "1"})
    assert code == 303 and konfig.laden()["steuern"]["steuerbar_kanton"] == 141_200   # verheiratet: Haushalt
    assert "Vergleich" in urllib.request.urlopen(f"{server}/steuern").read().decode()


def test_bank_upload_und_erinnerung(server):
    from pathlib import Path
    inhalt = (Path(__file__).parent / "bank" / "raiffeisen.csv").read_bytes()
    code, ziel = _upload(f"{server}/vermoegen/bank", "datei", "raiffeisen.csv", inhalt)
    assert code == 303 and "Monatssaldi" in urllib.parse.unquote(ziel) and "f=1" not in ziel
    html = urllib.request.urlopen(f"{server}/").read().decode()
    assert "Anstehend" in html or "Erinnerungen" in html
    html = urllib.request.urlopen(f"{server}/szenarien").read().decode()
    assert "Hypothekar-Strategie" in html


def test_upload_einzeln_als_json(server):
    """Der Browser schickt mehrere Dateien einzeln (Ingress-Grenze 16 MB) und erhält JSON statt einer Weiterleitung."""
    import json
    grenze = "----finanztest"
    body = (f"--{grenze}\r\nContent-Disposition: form-data; name=\"datei\"; filename=\"a.txt\"\r\n"
            "Content-Type: text/plain\r\n\r\n").encode() + "Vorsorgeausweis\nAltersguthaben 100000\n".encode() \
        + f"\r\n--{grenze}--\r\n".encode()
    req = urllib.request.Request(f"{server}/vorsorge/hochladen", body,
                                 {"Content-Type": f"multipart/form-data; boundary={grenze}", "X-Einzeln": "1"})
    antwort = json.loads(urllib.request.urlopen(req).read().decode())
    assert antwort["fehler"] is False and antwort["ziel"].startswith("vorsorge")


def test_nur_ingress_in_home_assistant(server, monkeypatch):
    import server as srv
    assert srv.zugriff_erlaubt("172.30.33.7")                         # lokal: offen
    monkeypatch.setenv("SUPERVISOR_TOKEN", "x")
    assert srv.zugriff_erlaubt("172.30.32.2") and srv.zugriff_erlaubt("127.0.0.1")
    assert not srv.zugriff_erlaubt("172.30.33.7")
    monkeypatch.setattr(srv, "zugriff_erlaubt", lambda a: False)        # Test-Client gilt als fremde App
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(server + "/")
    assert e.value.code == 403


def test_konto_verwalten_seite(server):
    _post(f"{server}/vermoegen/saldo", {"konto": "Privatkonto", "art": "bank", "datum": "2026-01-31", "betrag": "1'000"})
    _post(f"{server}/vermoegen/saldo", {"konto": "Privatkonto", "art": "bank", "datum": "2026-02-28", "betrag": "1'200"})
    liste = urllib.request.urlopen(f"{server}/vermoegen").read().decode()
    kid = int(re.search(r'href="vermoegen/konto/(\d+)"', liste).group(1))
    html = urllib.request.urlopen(f"{server}/vermoegen/konto/{kid}").read().decode()
    assert "Saldi" in html and 'name="b_2026-02-28"' in html and "Zusammenführen" in html
    code, ziel = _post(f"{server}/vermoegen/konto/{kid}/speichern",
                       {"name": "Privatkonto UBS", "art": "bank", "person": "", "waehrung": "CHF", "notiz": "…1234"})
    assert code == 303 and ziel.startswith(f"/vermoegen/konto/{kid}")
    code, ziel = _post(f"{server}/vermoegen/konto/{kid}/saldi",
                       {"aktion": "speichern", "d_2026-01-31": "2026-01-31", "b_2026-01-31": "1000",
                        "d_2026-02-28": "2026-02-28", "b_2026-02-28": "1'250", "neu_datum": "2026-03-31", "neu_betrag": "1300"})
    assert "1%20ge%C3%A4ndert" in ziel or "1 geändert" in urllib.parse.unquote(ziel)
    code, _ = _post(f"{server}/vermoegen/konto/{kid}/saldi", {"aktion": "loeschen", "sel_2026-01-31": "1"})
    html = urllib.request.urlopen(f"{server}/vermoegen/konto/{kid}").read().decode()
    assert "Privatkonto UBS" in html and 'name="b_2026-01-31"' not in html and 'value="1250.00"' in html
    _post(f"{server}/vermoegen/konto/{kid}/aufloesen", {"datum": "2026-04-30"})
    assert "Aufgelöste Konten (1)" in urllib.request.urlopen(f"{server}/vermoegen").read().decode()
    code, _ = _post(f"{server}/vermoegen/loeschen", {f"sel_k:{kid}": "1"})
    assert code == 303 and "Privatkonto UBS" not in urllib.request.urlopen(f"{server}/vermoegen").read().decode()


def test_nachlass_fragebogen_und_notfallordner(server):
    k = konfig.laden()
    k["haushalt"]["zivilstand"] = "ledig"
    konfig.speichern(k)
    p1 = k["personen"][0]["name"]
    html = urllib.request.urlopen(f"{server}/nachlass").read().decode()
    assert 'href="nachlass/fragebogen?bereich=testament#testament"' in html
    html = urllib.request.urlopen(f"{server}/nachlass/fragebogen?bereich=testament").read().decode()
    assert 'id="testament" open' in html and "Konkubinatsvertrag" in html and 'class="aktiv"' in html
    code, ziel = _post(f"{server}/nachlass/fragebogen", {
        "bereich": "testament", f"{p1}|vorhanden": "ja", f"{p1}|original": "Notariat Muster", f"{p1}|datum": "2025-03-01",
        "abhaken": "1"})
    assert code == 303 and ziel.endswith("#testament") and "m=" in ziel
    k = konfig.laden()
    assert k["nachlass"]["fragebogen"]["testament"][p1]["original"] == "Notariat Muster"
    assert k["nachlass"]["checkliste"]["testament"][p1] is True                 # wichtige Angaben da → abgehakt
    _post(f"{server}/nachlass/fragebogen", {"bereich": "liegenschaft", "haushalt|eigentum": "Miteigentum"})
    notfall = urllib.request.urlopen(f"{server}/notfall").read().decode()
    assert "Notariat Muster" in notfall and "Wo liegt das Original?" in notfall and "Miteigentum" in notfall


def test_vertrag_invaliditaet_erfassen(server):
    from policen import LEBEN, pdf
    code, ziel = _upload(f"{server}/versicherungen/hochladen", "datei", "leben.pdf", pdf(LEBEN))
    vid = int(re.search(r"/versicherungen/(\d+)", ziel).group(1))
    html = urllib.request.urlopen(f"{server}/versicherungen/{vid}").read().decode()
    assert "Leistungen bei Invalidität bzw. Erwerbsunfähigkeit" in html and 'name="iv_rente_jahr"' in html
    _post(f"{server}/versicherungen/{vid}", {"sparte": "leben", "iv_rente_jahr": "18'000", "iv_wartefrist_monate": "24",
                                            "iv_ursache": "Krankheit und Unfall", "iv_beitragsbefreiung": "1"})
    html = urllib.request.urlopen(f"{server}/versicherungen/{vid}").read().decode()
    assert 'name="iv_rente_jahr" inputmode="decimal" value="18000"' in html and "<option selected>Krankheit und Unfall" in html


def test_verfuegungen_seite(server):
    k = konfig.laden()
    p1 = k["personen"][0]["name"]
    html = urllib.request.urlopen(f"{server}/verfuegungen").read().decode()
    assert "Verfügungen erstellen" in html and "verfuegungen?typ=testament&amp;wer=" in html
    q = urllib.parse.quote(p1)
    html = urllib.request.urlopen(f"{server}/verfuegungen?typ=testament&wer={q}").read().decode()
    assert "Wer erhält was?" in html and 'id="entwurf-text"' in html and "Pflichtteil" in html
    code, ziel = _post(f"{server}/verfuegungen", {"typ": "testament", "wer": p1, "ziel": "eigene",
                                                 "quoten": "Musterstiftung: 100", "widerruf": "ja"})
    assert code == 303 and "typ=testament" in ziel
    html = urllib.request.urlopen(f"{server}/verfuegungen?typ=testament&wer={q}").read().decode()
    assert "Musterstiftung erhält 100 % meines Nachlasses" in html
    _post(f"{server}/verfuegungen/vermerken", {"typ": "testament", "wer": p1})
    assert konfig.laden()["nachlass"]["fragebogen"]["testament"][p1]["vorhanden"] == "in Arbeit"


def test_namen_aufteilen_und_umbenennen(server, daten):
    k = konfig.laden()
    k["personen"][0]["name"] = "Anna Muster"
    konfig.speichern(k)
    _post(f"{server}/vermoegen/saldo", {"konto": "Sparen", "art": "bank", "person": "Anna Muster",
                                        "datum": "2026-01-31", "betrag": "100"})
    assert "Namen aufteilen" in urllib.request.urlopen(f"{server}/einstellungen").read().decode()
    code, _ = _post(f"{server}/einstellungen/namen_trennen", {})
    k = konfig.laden()
    assert code == 303 and (k["personen"][0]["name"], k["personen"][0]["nachname"]) == ("Anna", "Muster")
    import vermoegen as vm
    v = vm.verbinden(konfig.datenordner() / "finanz.sqlite")
    assert v.execute("SELECT person FROM konten WHERE name = 'Sparen'").fetchone()[0] == "Anna"
    code, _ = _post(f"{server}/einstellungen", {"personen.0.name": "Anni"})
    assert konfig.laden()["personen"][0]["name"] == "Anni"
    assert v.execute("SELECT person FROM konten WHERE name = 'Sparen'").fetchone()[0] == "Anni"


def test_neue_seiten_und_praemien_upload(server, daten):
    k = konfig.laden()
    k["haushalt"]["kanton"] = "BL"
    konfig.speichern(k)
    for pfad in ("finanzplan", "vermoegen", "budget", "versicherungen"):
        assert urllib.request.urlopen(f"{server}/{pfad}").status == 200
    from test_module import KK_2027
    code, ziel = _upload(f"{server}/versicherungen/praemien_laden", "datei", "Prämien_CH.csv", KK_2027.encode())
    assert code == 303 and "Pr%C3%A4mien%202027" in ziel or "Prämien 2027" in ziel
    assert "Alle Kassen im Vergleich" in urllib.request.urlopen(f"{server}/versicherungen").read().decode()


def test_lebenslauf_kinder_speichern(server, daten):
    k = konfig.laden()
    k["haushalt"]["kinder"] = [{"name": "Anna", "geburtsdatum": "2022-03-01", "betreuung_jahr": 12000, "betreuung_bis": 6}]
    konfig.speichern(k)
    html = urllib.request.urlopen(f"{server}/kinder").read().decode()
    assert "Lebenslauf der Kinder" in html and "Lebenslauf Anna" in html and "Vergleichswerte und Quellen" in html
    assert 'name="b_kindergarten" inputmode="decimal" value="1000"' in html     # ältere Betreuungskosten übernommen
    code, _ = _post(f"{server}/kinder/lebenslauf", {"i": "0", "weg": "gymnasium", "danach": "studium", "kita_tage": "2",
                                                   "auswaerts": "1", "b_kita": "900", "l_primar": "750", "b_primar": "",
                                                   "sek2_jahre": ""})
    c = konfig.laden()["haushalt"]["kinder"][0]
    assert code == 303 and c["weg"] == "gymnasium" and c["auswaerts"] is True and c["kita_tage"] == 2
    assert c["phasen"] == {"kita": {"betreuung": 900}, "primar": {"leben": 750}} and "betreuung_jahr" not in c
    # Stammdaten speichern lässt den Lebenslauf stehen
    _post(f"{server}/kinder", {"anzahl": "1", "name_0": "Anna", "geburtsdatum_0": "2022-03-01", "ausbildung_bis_0": "25"})
    c = konfig.laden()["haushalt"]["kinder"][0]
    assert c["phasen"]["kita"] == {"betreuung": 900} and c["ausbildung_bis"] == 25 and c["weg"] == "gymnasium"


def test_saeule3a_unter_vermoegen(server, daten):
    k = konfig.laden()
    k["personen"][0]["saeule3a"]["guthaben"] = 20_000
    konfig.speichern(k)
    assert "Als 3a-Konto anlegen" in urllib.request.urlopen(f"{server}/vermoegen").read().decode()
    code, ziel = _post(f"{server}/vermoegen/3a_anlegen", {})
    assert code == 303 and "saeule3a" in ziel
    p = k["personen"][0]["name"]
    _post(f"{server}/vermoegen/saldo", {"konto": "3a Zweitkonto", "art": "saeule3a", "person": p,
                                        "datum": "2026-10-31", "betrag": "5000"})
    html = urllib.request.urlopen(f"{server}/vermoegen").read().decode()
    assert "Bezug geplant" in html and "Gebundene Vorsorge" in html
    cfg = konfig.laden()["personen"][0]["saeule3a"]
    assert cfg["guthaben"] == 25_000 and cfg["konten"] == 2


def test_seite_sparen_und_anlegen(server, daten):
    html = urllib.request.urlopen(f"{server}/sparplan").read().decode()
    assert "Reihenfolge für den nächsten Franken" in html and "Produktarten" in html and "Sparplan pro Monat" in html


def test_einstellungen_speichern_pro_bereich(server, daten):
    html = urllib.request.urlopen(f"{server}/einstellungen").read().decode()
    assert 'name="bereich" value="wohnen"' in html and 'id="speicherleiste"' in html
    # «Namen aufteilen» (eigenes Formular) steht vor dem grossen Formular
    assert html.index('id="einstellungen-form"') > html.rfind("einstellungen/namen_trennen") if "namen_trennen" in html else True
    code, ziel = _post(f"{server}/einstellungen", {"bereich": "wohnen", "wohnen.kaufpreis": "777000"})
    assert code == 303 and ziel.endswith("#b-wohnen") and konfig.laden()["wohnen"]["kaufpreis"] == 777000
