"""Webserver der Finanzplanungs-App (Home Assistant Ingress)."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import traceback
from datetime import datetime
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

import berater as br
import dokumente as dk
import steuerdokumente as sd
import importordner
import konfig
import seiten
import vermoegen as vm
import versicherungen as vi

LOG = logging.getLogger("finanz")
SPERRE = threading.Lock()
MAX_UPLOAD = 40 * 1024 * 1024

SEITEN = {
    "": ("Übersicht", seiten.uebersicht),
    "vorsorge": ("Vorsorge", seiten.vorsorge),
    "steuern": ("Steuern", seiten.steuern),
    "wohnen": ("Wohnen", seiten.wohnen),
    "vermoegen": ("Vermögen", seiten.vermoegen),
    "versicherungen": ("Versicherungen", seiten.versicherungen),
    "berater": ("Anlageberater", seiten.berater),
    "einstellungen": ("Einstellungen", seiten.einstellungen),
    "aenderungen": ("Änderungen", seiten.aenderungen),
}
VORLAGE_CSV = "Datum;Konto;Saldo;Art;Person\n31.12.2025;Sparkonto;25000.00;bank;\n31.12.2025;Depot;80000;depot;Person 1\n"


def db():
    return vm.verbinden(konfig.datenordner() / "finanz.sqlite")


def multipart(content_type: str, body: bytes) -> dict:
    nachricht = BytesParser(policy=email_policy).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
    teile: dict = {}
    for teil in nachricht.iter_parts():
        name = teil.get_param("name", header="content-disposition")
        if name:
            inhalt = teil.get_payload(decode=True) or b""
            dateiname = teil.get_filename()
            teile[name] = inhalt if dateiname is not None else inhalt.decode("utf-8", errors="replace")
            if dateiname:
                teile.setdefault("_dateien_" + name, []).append((dateiname, inhalt))
    return teile


DETAIL = {
    "versicherungen": ("Versicherung", lambda k, v, i: seiten.versicherung(k, v, i), vi, vi.ordner, "datei"),
    "vorsorge/dokument": ("Vorsorgedokument", lambda k, v, i: seiten.vorsorge_dokument(k, v, i), dk, dk.ordner, "datei"),
    "steuern/dokument": ("Steuerdokument", lambda k, v, i: seiten.steuer_dokument(k, v, i), sd, sd.ordner, "datei"),
    "berater": ("Beratung", lambda k, v, i: seiten.beratung(k, v, i), br, None, None),
}


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
            if pfad == "protokoll.log":
                log = konfig.datenordner() / "finanz.log"
                return self.senden(200, log.read_bytes() if log.exists() else b"", "text/plain; charset=utf-8",
                                   {"Content-Disposition": 'attachment; filename="finanz.log"'})
            if pfad == "protokoll":
                stufe = q.get("stufe", ["INFO"])[0].upper()
                with db() as v:
                    inhalt = seiten.protokoll(konfig.laden(), v, stufe)
                html = seiten.seite("Protokoll", "protokoll", inhalt, self.basis)
                return self.senden(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if pfad == "szenarien":
                with db() as v:
                    inhalt = seiten.szenarien(konfig.laden(), v, q)
                html = seiten.seite("Szenarien", "szenarien", inhalt, self.basis, unquote(q.get("m", [""])[0]),
                                    bool(q.get("f")), self._ampeln())
                return self.senden(200, html.encode("utf-8"), "text/html; charset=utf-8")
            if pfad == "gesundheit":
                return self.senden(200, b"ok", "text/plain")
            detail = self._detail(pfad)
            if detail:
                return detail
            if pfad not in SEITEN:
                return self.senden(404, "Nicht gefunden".encode(), "text/plain; charset=utf-8")
            titel, funktion = SEITEN[pfad]
            k = konfig.laden()
            with db() as verbindung:
                inhalt = funktion(k, verbindung)
            meldung = unquote(q.get("m", [""])[0])
            html = seiten.seite(titel, pfad, inhalt, self.basis, meldung, bool(q.get("f")), self._ampeln())
            self.senden(200, html.encode("utf-8"), "text/html; charset=utf-8")
        except Exception as e:  # noqa: BLE001
            LOG.error("Fehler auf %s: %s\n%s", pfad, e, traceback.format_exc())
            html = seiten.seite("Fehler", pfad, f"<pre>{seiten.escape(str(e))}</pre>"
                                '<p>Häufigste Ursache: ein Wert in den Einstellungen hat das falsche Format.</p>',
                                self.basis, "Die Seite konnte nicht berechnet werden.", True)
            self.senden(500, html.encode("utf-8"), "text/html; charset=utf-8")

    def _ampeln(self) -> dict:
        """Ampel pro Seite für die Navigation; Fehler dürfen die Seite nie verhindern."""
        try:
            import ampel
            with db() as v:
                return ampel.pro_seite(ampel.bewerten(konfig.laden(), v))
        except Exception as e:  # noqa: BLE001
            LOG.debug("Ampeln: %s", e)
            return {}

    def _detail(self, pfad: str):
        """Detailseiten /<bereich>/<id> und Originaldateien /<bereich>/<id>/datei."""
        for praefix, (titel, funktion, modul, ordner, _) in DETAIL.items():
            if not pfad.startswith(praefix + "/"):
                continue
            rest = pfad[len(praefix) + 1:].split("/")
            if not rest[0].isdigit():
                return None
            nr = int(rest[0])
            with db() as v:
                if len(rest) == 2 and rest[1] == "datei" and ordner:
                    eintrag = modul.einer(v, nr)
                    if not eintrag or not eintrag["datei"]:
                        return self.senden(404, b"nicht gefunden", "text/plain")
                    inhalt = (ordner(konfig.datenordner()) / eintrag["datei"]).read_bytes()
                    typ = "application/pdf" if eintrag["datei"].endswith(".pdf") else "text/plain; charset=utf-8"
                    return self.senden(200, inhalt, typ, {"Content-Disposition": f'inline; filename="{eintrag["dateiname"]}"'})
                inhalt = funktion(konfig.laden(), v, nr)
            _, q = self._pfad()
            html = seiten.seite(titel, praefix.split("/")[0], inhalt, self.basis,
                                unquote(q.get("m", [""])[0]), bool(q.get("f")), self._ampeln())
            return self.senden(200, html.encode("utf-8"), "text/html; charset=utf-8")
        return None

    # ------------------------------------------------------------ POST
    def do_POST(self):
        pfad, _ = self._pfad()
        ziel = pfad.split("/")[0]
        try:
            form = self._formular()
            with SPERRE:
                meldung = self._aktion(pfad, form)
            if isinstance(meldung, tuple):
                meldung, ziel = meldung
            LOG.info("%s: %s", pfad, meldung)
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
        if pfad == "vermoegen/bank":
            import bankimport as bi
            dateien = form.get("_dateien_datei") or []
            endsaldo = vm.zahl(form["endsaldo"]) if str(form.get("endsaldo", "")).strip() else None
            teile = []
            with db() as v:
                for name, inhalt in dateien:
                    a, n = bi.aus_datei(v, inhalt, name, form.get("konto", "") if len(dateien) == 1 else "",
                                        form.get("art", ""), form.get("person", ""), endsaldo)
                    teile.append(f"{a.konto_vorschlag if not form.get('konto') or len(dateien) > 1 else form['konto']}: "
                                 f"{n} Monatssaldi" + (f" ({a.zeitraum[0][:7]} bis {a.zeitraum[1][:7]})" if a.zeitraum else ""))
            return "Importiert – " + "; ".join(teile)
        if pfad == "vermoegen/loeschen":
            with db() as v:
                vm.konto_loeschen(v, int(form["id"]))
            return "Konto gelöscht."
        if pfad == "erinnerungen/erledigt":
            import erinnerungen as er
            with db() as v:
                er.erledigen(v, form["schluessel"])
            return "Erinnerung erledigt.", ""
        if pfad == "einstellungen/importordner":
            with db() as v:
                meldungen = importordner.einlesen(konfig.datenordner(), v)
            return " · ".join(meldungen) if meldungen else "Der Import-Ordner ist leer."
        if pfad.startswith("versicherungen"):
            return self._versicherungen(pfad, form)
        if pfad.startswith("vorsorge"):
            return self._vorsorge(pfad, form)
        if pfad.startswith("berater"):
            return self._berater(pfad, form)
        if pfad.startswith("steuern"):
            return self._steuern(pfad, form)
        if pfad == "szenarien/einkauf":
            import szenarien as sz
            k = konfig.laden()
            plan = sz.einkauf_optimieren(k, form["person"], vm.zahl(form.get("budget") or "0"), int(form["von"]),
                                         int(form["bis"]), vm.zahl(form.get("schwelle") or "0"),
                                         vm.zahl(form.get("schritt") or "5000"))
            if not plan.plan:
                raise ValueError("Kein Einkauf zu übernehmen.")
            sz.plan_uebernehmen(k, plan)
            konfig.speichern(k)
            return (f"{len(plan.plan)} Einkäufe für {plan.person} übernommen (total CHF "
                    f"{sum(plan.plan.values()):,.0f}).".replace(",", "'"), "szenarien")
        raise ValueError("Unbekannte Aktion.")

    def _versicherungen(self, pfad: str, form: dict):
        daten = konfig.datenordner()
        teile = pfad.split("/")
        with db() as v:
            if pfad == "versicherungen/hochladen":
                dateien = form.get("_dateien_datei") or []
                ids = [vi.hochladen(v, daten, n, inhalt) for n, inhalt in dateien if inhalt]
                LOG.info("%d Versicherungsverträge hochgeladen", len(ids))
                if len(ids) == 1:
                    return "Vertrag analysiert – bitte die erkannten Werte prüfen.", f"versicherungen/{ids[0]}"
                return f"{len(ids)} Verträge analysiert."
            if pfad == "versicherungen/liste":
                n, fehler = vi.csv_import(v, form.get("datei") or b"")
                return f"{n} Verträge importiert." + (" Übersprungen: " + "; ".join(fehler[:5]) if fehler else "")
            if len(teile) >= 2 and teile[1].isdigit():
                vid = int(teile[1])
                aktion = teile[2] if len(teile) > 2 else ""
                if aktion == "loeschen":
                    vi.loeschen(v, daten, vid)
                    return "Vertrag gelöscht."
                if aktion == "ki":
                    k = konfig.laden()
                    werte = vi.ki_auslesen(vi.einer(v, vid)["text"], k["ki"].get("entity", ""))
                    vi.aktualisieren(v, vid, werte, quelle="ki")
                    return "Per KI ausgelesen – bitte prüfen.", f"versicherungen/{vid}"
                vi.aktualisieren(v, vid, vi.bereinigen(form), quelle="hand")
                return "Vertrag gespeichert.", f"versicherungen/{vid}"
        raise ValueError("Unbekannte Aktion.")

    def _vorsorge(self, pfad: str, form: dict):
        daten = konfig.datenordner()
        teile = pfad.split("/")
        with db() as v:
            if pfad == "vorsorge/hochladen":
                dateien = form.get("_dateien_datei") or []
                ids = [dk.hochladen(v, daten, n, inhalt) for n, inhalt in dateien if inhalt]
                if len(ids) == 1:
                    return "Dokument analysiert – Werte prüfen und übernehmen.", f"vorsorge/dokument/{ids[0]}"
                return f"{len(ids)} Dokumente analysiert."
            if len(teile) >= 3 and teile[1] == "dokument" and teile[2].isdigit():
                did = int(teile[2])
                aktion = teile[3] if len(teile) > 3 else ""
                dok = dk.einer(v, did)
                if not dok:
                    raise ValueError("Dokument nicht gefunden.")
                if aktion == "loeschen":
                    dk.loeschen(v, daten, did)
                    return "Dokument gelöscht.", "vorsorge"
                if aktion == "ki":
                    k = konfig.laden()
                    erg = dk.ki_auslesen(dok, k["ki"].get("entity", ""))
                    dk.speichern(v, did, dok["typ"], dok["person"], erg["werte"], quelle="ki")
                    return "Per KI ausgelesen – bitte prüfen.", f"vorsorge/dokument/{did}"
                # Werte und Zuordnung speichern
                werte = {}
                for s_ in dk.ZIELE:
                    roh = str(form.get("wert_" + s_, "")).strip()
                    if roh:
                        werte[s_] = vi.zahl(roh)
                dk.speichern(v, did, form.get("typ", dok["typ"]), form.get("person", ""), werte,
                             quelle=None if werte == dok["werte"] else "hand")
                if aktion == "uebernehmen":
                    k = konfig.laden()
                    namen = [p["name"] for p in k["personen"]]
                    if form.get("person") not in namen:
                        raise ValueError("Bitte zuerst die Person wählen.")
                    gewaehlt = [s_ for s_ in werte if form.get("nimm_" + s_)]
                    dok = dk.einer(v, did)
                    erledigt = dk.uebernehmen(k, dok, namen.index(form["person"]), gewaehlt)
                    konfig.speichern(k)
                    v.execute("UPDATE vorsorge_dok SET uebernommen = ? WHERE id = ?",
                              (datetime.now().isoformat(timespec="seconds"), did))
                    v.commit()
                    return (f"Für {form['person']} übernommen: " + ", ".join(erledigt) if erledigt
                            else "Keine Werte ausgewählt."), f"vorsorge/dokument/{did}"
                return "Gespeichert.", f"vorsorge/dokument/{did}"
        raise ValueError("Unbekannte Aktion.")

    def _steuern(self, pfad: str, form: dict):
        daten = konfig.datenordner()
        teile = pfad.split("/")
        with db() as v:
            if pfad == "steuern/hochladen":
                dateien = form.get("_dateien_datei") or []
                ids = [sd.hochladen(v, daten, n, inhalt) for n, inhalt in dateien if inhalt]
                if len(ids) == 1:
                    return "Steuerdokument analysiert – Werte prüfen und übernehmen.", f"steuern/dokument/{ids[0]}"
                return f"{len(ids)} Steuerdokumente analysiert."
            if len(teile) >= 3 and teile[1] == "dokument" and teile[2].isdigit():
                did = int(teile[2])
                aktion = teile[3] if len(teile) > 3 else ""
                dok = sd.einer(v, did)
                if not dok:
                    raise ValueError("Dokument nicht gefunden.")
                if aktion == "loeschen":
                    sd.loeschen(v, daten, did)
                    return "Steuerdokument gelöscht.", "steuern"
                if aktion == "ki":
                    erg = sd.ki_auslesen(dok, konfig.laden()["ki"].get("entity", ""))
                    sd.speichern(v, did, erg["typ"], erg["jahr"], erg["person"], erg["werte"], quelle="ki")
                    return "Per KI ausgelesen – bitte prüfen.", f"steuern/dokument/{did}"
                werte = {}
                for s_ in sd.FELDER:
                    roh = str(form.get("wert_" + s_, "")).strip()
                    if roh:
                        werte[s_] = abs(vi.zahl(roh))
                jahr = int(str(form.get("jahr") or dok["jahr"] or 0).strip() or 0)
                sd.speichern(v, did, form.get("typ", dok["typ"]), jahr, form.get("person", ""), werte,
                             quelle=None if werte == dok["werte"] else "hand")
                if aktion == "uebernehmen":
                    k = konfig.laden()
                    gewaehlt = [s_ for s_ in list(werte) + ["grenzsteuersatz"] if form.get("nimm_" + s_)]
                    grenz = float(form["grenz"]) if form.get("grenz") else None
                    erledigt = sd.uebernehmen(k, sd.einer(v, did), form.get("person", ""), gewaehlt, grenz)
                    konfig.speichern(k)
                    v.execute("UPDATE steuer_dok SET uebernommen = ? WHERE id = ?",
                              (datetime.now().isoformat(timespec="seconds"), did))
                    v.commit()
                    return (f"Für {form['person']} übernommen: " + ", ".join(erledigt) if erledigt
                            else "Keine Werte ausgewählt."), f"steuern/dokument/{did}"
                return "Gespeichert.", f"steuern/dokument/{did}"
        raise ValueError("Unbekannte Aktion.")

    def _berater(self, pfad: str, form: dict):
        teile = pfad.split("/")
        k = konfig.laden()
        with db() as v:
            if pfad == "berater/situation":
                k.setdefault("berater", {})["situation"] = form.get("situation", "")
                konfig.speichern(k)
                return "Situation gespeichert."
            if pfad == "berater/fragen":
                pid, frage = form.get("profil", ""), form.get("frage", "")
                if k["ki"].get("aktiv"):
                    bid = br.fragen(k, v, pid, frage)
                    return "Antwort erhalten.", f"berater/{bid}"
                p = br.profil(k, pid)
                bid = br.speichern(v, p["name"], frage, br.auftrag(k, v, pid, frage), "")
                return "Auftrag erstellt – kopieren, in deinen KI-Assistenten einfügen und die Antwort hier speichern.", f"berater/{bid}"
            if len(teile) == 3 and teile[1].isdigit():
                bid = int(teile[1])
                if teile[2] == "antwort":
                    br.antwort_setzen(v, bid, form.get("antwort", ""))
                    return "Antwort gespeichert.", f"berater/{bid}"
                if teile[2] == "loeschen":
                    br.loeschen(v, bid)
                    return "Beratung gelöscht."
        raise ValueError("Unbekannte Aktion.")


def main():
    ordner = konfig.datenordner()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(),
                  RotatingFileHandler(ordner / "finanz.log", maxBytes=1_000_000, backupCount=1, encoding="utf-8")],
    )
    import meta
    LOG.info("Finanzplanung %s startet", meta.version())
    konfig.laden()
    try:
        with db() as v:
            importordner.einlesen(ordner, v)
    except Exception as e:  # noqa: BLE001
        LOG.warning("Import-Ordner: %s", e)
    import erinnerungen
    erinnerungen.hintergrund(konfig.laden, db)
    port = int(os.environ.get("PORT", "8099"))
    LOG.info("Finanzplanung läuft auf Port %d, Daten in %s", port, ordner)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
