"""Webserver der Finanzplanungs-App (Home Assistant Ingress)."""
from __future__ import annotations

import logging
import os
import threading
import traceback
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

import konfig
import seiten
import vermoegen as vm

LOG = logging.getLogger("finanz")
SPERRE = threading.Lock()
MAX_UPLOAD = 5 * 1024 * 1024

SEITEN = {
    "": ("Übersicht", seiten.uebersicht),
    "vorsorge": ("Vorsorge", seiten.vorsorge),
    "steuern": ("Steuern", seiten.steuern),
    "wohnen": ("Wohnen", seiten.wohnen),
    "vermoegen": ("Vermögen", seiten.vermoegen),
    "einstellungen": ("Einstellungen", seiten.einstellungen),
}
VORLAGE_CSV = "Datum;Konto;Saldo;Art;Person\n31.12.2025;Sparkonto;25000.00;bank;\n31.12.2025;Depot;80000;depot;Person 1\n"


def db():
    return vm.verbinden(konfig.datenordner() / "finanz.sqlite")


def multipart(content_type: str, body: bytes) -> dict:
    nachricht = BytesParser(policy=email_policy).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
    teile = {}
    for teil in nachricht.iter_parts():
        name = teil.get_param("name", header="content-disposition")
        if name:
            teile[name] = teil.get_payload(decode=True) or b""
    return teile


class Handler(BaseHTTPRequestHandler):
    server_version = "Finanzplanung"

    # ------------------------------------------------------------ Hilfen
    @property
    def basis(self) -> str:
        return self.headers.get("X-Ingress-Path", "").rstrip("/")

    def log_message(self, fmt, *args):  # noqa: D401
        LOG.debug("%s %s", self.address_string(), fmt % args)

    def senden(self, status: int, inhalt: bytes, typ: str, extra: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(inhalt)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(inhalt)

    def weiter(self, pfad: str, meldung: str = "", fehler: bool = False):
        ziel = f"{self.basis}/{pfad}"
        if meldung:
            ziel += f"?m={quote(meldung)}" + ("&f=1" if fehler else "")
        self.send_response(303)
        self.send_header("Location", ziel)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _pfad(self) -> tuple[str, dict]:
        url = urlparse(self.path)
        return url.path.strip("/"), parse_qs(url.query)

    def _koerper(self) -> bytes:
        laenge = int(self.headers.get("Content-Length") or 0)
        if laenge > MAX_UPLOAD:
            raise ValueError("Datei zu gross (max. 5 MB).")
        return self.rfile.read(laenge)

    def _formular(self) -> dict:
        typ = self.headers.get("Content-Type", "")
        body = self._koerper()
        if typ.startswith("multipart/form-data"):
            return multipart(typ, body)
        return {k: v[-1] for k, v in parse_qs(body.decode("utf-8"), keep_blank_values=True).items()}

    # ------------------------------------------------------------ GET
    def do_GET(self):
        pfad, q = self._pfad()
        try:
            if pfad == "export":
                inhalt = konfig.konfig_pfad().read_bytes() if konfig.konfig_pfad().exists() else b""
                return self.senden(200, inhalt, "application/x-yaml",
                                   {"Content-Disposition": 'attachment; filename="finanz.yaml"'})
            if pfad == "vorlage.csv":
                return self.senden(200, VORLAGE_CSV.encode("utf-8-sig"), "text/csv; charset=utf-8",
                                   {"Content-Disposition": 'attachment; filename="vermoegen-vorlage.csv"'})
            if pfad == "gesundheit":
                return self.senden(200, b"ok", "text/plain")
            if pfad not in SEITEN:
                return self.senden(404, "Nicht gefunden".encode(), "text/plain; charset=utf-8")
            titel, funktion = SEITEN[pfad]
            k = konfig.laden()
            with db() as verbindung:
                inhalt = funktion(k, verbindung)
            meldung = unquote(q.get("m", [""])[0])
            html = seiten.seite(titel, pfad, inhalt, self.basis, meldung, bool(q.get("f")))
            self.senden(200, html.encode("utf-8"), "text/html; charset=utf-8")
        except Exception as e:  # noqa: BLE001
            LOG.error("Fehler auf %s: %s\n%s", pfad, e, traceback.format_exc())
            html = seiten.seite("Fehler", pfad, f"<pre>{seiten.escape(str(e))}</pre>"
                                '<p>Häufigste Ursache: ein Wert in den Einstellungen hat das falsche Format.</p>',
                                self.basis, "Die Seite konnte nicht berechnet werden.", True)
            self.senden(500, html.encode("utf-8"), "text/html; charset=utf-8")

    # ------------------------------------------------------------ POST
    def do_POST(self):
        pfad, _ = self._pfad()
        ziel = pfad.split("/")[0]
        try:
            form = self._formular()
            with SPERRE:
                meldung = self._aktion(pfad, form)
            self.weiter(ziel, meldung)
        except Exception as e:  # noqa: BLE001
            LOG.warning("Aktion %s fehlgeschlagen: %s", pfad, e)
            self.weiter(ziel, str(e), fehler=True)

    def _aktion(self, pfad: str, form: dict) -> str:
        if pfad == "einstellungen":
            k = konfig.laden()
            for feld, _ in seiten.alle_felder(k):
                if feld in form:
                    wert = form[feld]
                    seiten.pfad_setzen(k, feld, wert.decode() if isinstance(wert, bytes) else wert)
            konfig.speichern(k)
            LOG.info("Einstellungen gespeichert")
            return "Einstellungen gespeichert."
        if pfad in ("einstellungen/yaml", "einstellungen/import"):
            roh = form.get("yaml") or form.get("datei") or b""
            text = roh.decode("utf-8") if isinstance(roh, bytes) else roh
            k = konfig.aus_text(text)
            konfig.speichern(k)
            konfig.laden()  # prüft, ob sich alles mischen lässt
            LOG.info("Konfiguration als YAML gespeichert")
            return "Konfiguration gespeichert (vorherige Fassung als finanz.yaml.bak)."
        if pfad == "vermoegen/saldo":
            with db() as v:
                kid = vm.konto_anlegen(v, form["konto"].strip(), form.get("art", "bank"), form.get("person", ""))
                vm.saldo_setzen(v, kid, vm.datum(form["datum"]), vm.zahl(form["betrag"]))
            return f"Saldo für «{form['konto'].strip()}» gespeichert."
        if pfad == "vermoegen/import":
            with db() as v:
                n, fehler = vm.csv_import(v, form.get("datei") or b"")
            LOG.info("CSV-Import: %d Saldi, %d Fehler", n, len(fehler))
            text = f"{n} Saldi importiert."
            if fehler:
                text += " Übersprungen: " + "; ".join(fehler[:5]) + (" …" if len(fehler) > 5 else "")
            return text
        if pfad == "vermoegen/loeschen":
            with db() as v:
                vm.konto_loeschen(v, int(form["id"]))
            return "Konto gelöscht."
        raise ValueError("Unbekannte Aktion.")


def main():
    ordner = konfig.datenordner()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(ordner / "finanz.log", encoding="utf-8")],
    )
    konfig.laden()
    port = int(os.environ.get("PORT", "8099"))
    LOG.info("Finanzplanung läuft auf Port %d, Daten in %s", port, ordner)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
