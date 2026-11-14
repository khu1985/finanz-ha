"""Webserver der Finanzplanungs-App (Home Assistant Ingress)."""
from __future__ import annotations

from tausender import TS  # noqa: E402

import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import time
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
MAX_UPLOAD = 16 * 1024 * 1024   # Grenze des Home-Assistant-Ingress pro Anfrage

MIT_ABFRAGE = {"lebensereignisse", "nachlass/fragebogen", "verfuegungen", "steuererklaerung", "bericht", "dokumente", "vorschlaege"}
SEITEN = {
    "": ("Übersicht", seiten.uebersicht),
    "vorsorge": ("Vorsorge", seiten.vorsorge),
    "steuern": ("Steuern", seiten.steuern),
    "wohnen": ("Wohnen", seiten.wohnen),
    "vermoegen": ("Vermögen", seiten.vermoegen),
    "versicherungen": ("Versicherungen", seiten.versicherungen),
    "berater": ("Anlageberater", seiten.berater),
    "nachlass": ("Nachlass und Absicherung", seiten.nachlass),
    "budget": ("Budget und Cashflow", seiten.budget),
    "finanzplan": ("Finanzplan", seiten.finanzplan),
    "sparplan": ("Sparen & Anlegen", seiten.sparplan),
    "lebensereignisse": ("Lebensereignisse", seiten.lebensereignisse),
    "fahrzeuge": ("Fahrzeuge", seiten.fahrzeuge),
    "kinder": ("Kinder", seiten.kinder),
    "steuererklaerung": ("Steuern", seiten.steuererklaerung),
    "notfall": ("Notfallordner", seiten.notfall),
    "bericht": ("Jahresbericht", seiten.bericht),
    "dokumente": ("Dokumente", seiten.dokumente),
    "vorschlaege": ("Vorschläge", seiten.vorschlaege),
    "nachlass/fragebogen": ("Fragebögen zum Nachlass", seiten.nachlass_fragebogen),
    "verfuegungen": ("Verfügungen", seiten.verfuegungen),
    "einstellungen": ("Einstellungen", seiten.einstellungen),
    "daten": ("Daten & Import", seiten.daten),
    "aenderungen": ("Änderungen", seiten.aenderungen),
}
VORLAGE_CSV = "Datum;Konto;Saldo;Art;Person\n31.12.2025;Sparkonto;25000.00;bank;\n31.12.2025;Depot;80000;depot;Person 1\n"


def db():
    return vm.verbinden(konfig.datenordner() / "finanz.sqlite")


def _umbenennen(k: dict, alt: str, neu: str) -> str:
    """Person umbenannt: Konfiguration (Verfügungen, Checklisten, Kinder …) und Zuordnungen in der Datenbank."""
    import verwaltung as vw
    konfig.person_umbenennen(k, alt, neu)
    with db() as v:
        n = vw.person_umbenennen_db(v, alt, neu)
    LOG.info("Person umbenannt (%d Zuordnungen)", n)
    return f"«{alt}» heisst jetzt «{neu}» – {n} Konten, Verträge und Dokumente nachgeführt."


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
    "vermoegen/konto": ("Konto", lambda k, v, i: seiten.konto(k, v, i), vm, None, None),
}


# Nur der Ingress-Proxy von Home Assistant darf zugreifen – andere Apps im internen Netz nicht.
# Gilt nur in Home Assistant (SUPERVISOR_TOKEN gesetzt); lokal zum Entwickeln ist alles offen.
INGRESS_PROXY = "172.30.32.2"


def zugriff_erlaubt(adresse: str) -> bool:
    if not os.environ.get("SUPERVISOR_TOKEN"):
        return True
    return adresse in (INGRESS_PROXY, "127.0.0.1", "::1")


class Handler(BaseHTTPRequestHandler):
    server_version = "Finanzplanung"
    sys_version = ""

    def parse_request(self):
        if not super().parse_request():
            return False
        if not zugriff_erlaubt(self.client_address[0]):
            LOG.warning("Zugriff von %s abgelehnt – nur über Home Assistant (Ingress)", self.client_address[0])
            self.send_error(403, "Nur über Home Assistant erreichbar")
            return False
        return True

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
        pfad, _, anker = pfad.partition("#")             # Sprungmarke gehört ans Ende der Adresse
        ziel = f"{self.basis}/{pfad}"
        if meldung:
            ziel += ("&" if "?" in ziel else "?") + f"m={quote(meldung)}" + ("&f=1" if fehler else "")
        if anker:
            ziel += "#" + anker
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
            raise ValueError("Upload zu gross (höchstens 16 MB pro Datei) – grössere Dateien über den Import-Ordner.")
        return self.rfile.read(laenge)

    def _formular(self) -> dict:
        typ = self.headers.get("Content-Type", "")
        body = self._koerper()
        if typ.startswith("multipart/form-data"):
            return multipart(typ, body)
        return {k: v[-1] for k, v in parse_qs(body.decode("utf-8"), keep_blank_values=True).items()}

    # ------------------------------------------------------------ GET
    def do_GET(self):
        import leistung as le
        t = time.perf_counter()
        try:
            return self._get()
        finally:
            pfad = self._pfad()[0]
            if pfad not in ("status", "gesundheit") and "." not in pfad.rsplit("/", 1)[-1]:
                le.erfassen("seite", le.seitenname(pfad), (time.perf_counter() - t) * 1000)

    def _get(self):
        pfad, q = self._pfad()
        try:
            if pfad == "export":
                inhalt = konfig.konfig_pfad().read_bytes() if konfig.konfig_pfad().exists() else b""
                return self.senden(200, inhalt, "application/x-yaml",
                                   {"Content-Disposition": 'attachment; filename="finanz.yaml"'})
            if pfad == "vorlage.csv":
                return self.senden(200, VORLAGE_CSV.encode("utf-8-sig"), "text/csv; charset=utf-8",
                                   {"Content-Disposition": 'attachment; filename="vermoegen-vorlage.csv"'})
            if pfad == "vorschlaege.md":
                import meta
                import vorschlaege as vs
                with db() as v:
                    k = konfig.laden()
                    st = vs.status(v)
                    liste = [x for x in vs.sammeln(k, v, konfig.datenordner()) if x.schluessel not in st]
                    auszuege = vs.textauszuege(k, v) if q.get("auszuege") == ["1"] else None
                    weg = [e[0] for e in vs.erledigt(v, meta.version())]
                    import leistung as le
                    import usability as us
                    lz = le.bericht_text(v, konfig.datenordner())
                    uz = us.bericht_text(v)
                text = vs.bericht(liste, meta.version(), str(k["haushalt"].get("kanton") or "").upper(), auszuege, weg, lz,
                                  uz)
                return self.senden(200, text.encode("utf-8"), "text/markdown; charset=utf-8",
                                   {"Content-Disposition": 'attachment; filename="finanz-vorschlaege.md"'})
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
                import dreia
                import fahrzeuge
                if dreia.abgleichen(k, verbindung):          # 3a-Konten unter Vermögen → Einstellungen
                    konfig.speichern(k)
                fahrzeuge.abgleichen(k, verbindung)          # Fahrzeugwert als Konto (steuerbares Vermögen)
                inhalt = funktion(k, verbindung, q) if pfad in MIT_ABFRAGE else funktion(k, verbindung)
            meldung = unquote(q.get("m", [""])[0])
            html = seiten.seite(titel, pfad, inhalt, self.basis, meldung, bool(q.get("f")), self._ampeln())
            self.senden(200, html.encode("utf-8"), "text/html; charset=utf-8")
        except (BrokenPipeError, ConnectionResetError):
            return    # Browser hat die Seite vorher verlassen – kein Fehler der App
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
        import leistung as le
        t = time.perf_counter()
        try:
            return self._post()
        finally:
            le.erfassen("aktion", le.seitenname(self._pfad()[0]), (time.perf_counter() - t) * 1000)

    def _post(self):
        pfad, _ = self._pfad()
        ziel = pfad.split("/")[0]
        try:
            form = self._formular()
            with SPERRE:
                meldung = self._aktion(pfad, form)
            if isinstance(meldung, tuple):
                meldung, ziel = meldung
            LOG.info("%s: %s", pfad, meldung)
            import sensoren
            sensoren.aktualisieren()
            if self.headers.get("X-Einzeln"):
                return self._json({"meldung": meldung, "fehler": False, "ziel": ziel})
            self.weiter(ziel, meldung)
        except Exception as e:  # noqa: BLE001
            # ValueError = Eingabe fehlt oder ist ungültig (Meldung an die Person) – kein Fehler der App
            (LOG.info if isinstance(e, ValueError) else LOG.warning)("Aktion %s fehlgeschlagen: %s", pfad, e)
            if self.headers.get("X-Einzeln"):
                return self._json({"meldung": str(e), "fehler": True, "ziel": ziel})
            self.weiter(ziel, str(e), fehler=True)

    def _json(self, daten: dict) -> None:
        """Antwort für Uploads, die der Browser Datei für Datei schickt (Grenze des Ingress: 16 MB pro Anfrage)."""
        import json as _j
        self.senden(200, _j.dumps(daten, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _aktion(self, pfad: str, form: dict) -> str:
        if pfad == "einstellungen":
            k = konfig.laden()
            vorher = [p.get("name") for p in k["personen"]]
            for feld, _ in seiten.alle_felder(k):
                if feld in form:
                    wert = form[feld]
                    seiten.pfad_setzen(k, feld, wert.decode() if isinstance(wert, bytes) else wert)
            meldung = "Einstellungen gespeichert."
            for alt_, p in zip(vorher, k["personen"]):
                p["name"] = str(p.get("name") or "").strip() or alt_
                if alt_ and p["name"] != alt_:
                    meldung += " " + _umbenennen(k, alt_, p["name"])
            konfig.speichern(k)
            LOG.info("Einstellungen gespeichert")
            bereich = form.get("bereich") or ""
            bereich = bereich.decode() if isinstance(bereich, bytes) else str(bereich)
            seite_ = "daten" if bereich == "sensoren" else "einstellungen"
            return meldung, (f"{seite_}#b-" + bereich if bereich.isalnum() else "einstellungen")
        if pfad == "einstellungen/namen_trennen":
            k = konfig.laden()
            teile_ = []
            for p in k["personen"]:
                if not p.get("nachname") and len(str(p.get("name") or "").split()) > 1:
                    alt_ = p["name"]
                    p["name"], p["nachname"] = konfig.namen_trennen(alt_)
                    teile_.append(f"«{alt_}» → Vorname «{p['name']}», Nachname «{p['nachname']}»")
                    _umbenennen(k, alt_, p["name"])
            konfig.speichern(k)
            return ("; ".join(teile_) + ".") if teile_ else "Nichts zu trennen.", "einstellungen"
        if pfad in ("einstellungen/yaml", "einstellungen/import"):
            roh = form.get("yaml") or form.get("datei") or b""
            text = roh.decode("utf-8") if isinstance(roh, bytes) else roh
            k = konfig.aus_text(text)
            konfig.speichern(k)
            konfig.laden()  # prüft, ob sich alles mischen lässt
            LOG.info("Konfiguration als YAML gespeichert")
            return "Konfiguration gespeichert (vorherige Fassung als finanz.yaml.bak).", "daten"
        if pfad == "vermoegen/3a_anlegen":
            import dreia
            with db() as v:
                namen = dreia.anlegen(konfig.laden(), v)
            return ("3a-Konten angelegt: " + ", ".join(namen) if namen else "Keine 3a-Guthaben ohne Konto."), "vermoegen#saeule3a"
        if pfad == "vermoegen/saldo":
            with db() as v:
                kid = vm.konto_anlegen(v, form["konto"].strip(), form.get("art", "bank"), form.get("person", ""),
                                       form.get("waehrung", "CHF"))
                vm.saldo_setzen(v, kid, vm.datum(form["datum"]), vm.zahl(form["betrag"]))
            return f"Saldo für «{form['konto'].strip()}» gespeichert."
        if pfad == "vermoegen/waehrung":
            with db() as v:
                vm.waehrung_setzen(v, int(form["id"]), form.get("waehrung", "CHF"))
            return "Währung geändert."
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
                    import budget as bu
                    konto = form.get("konto", "").strip() if len(dateien) == 1 else ""
                    a, n = bi.aus_datei(v, inhalt, name, konto, form.get("art", ""), form.get("person", ""), endsaldo)
                    konto = konto or a.konto_vorschlag
                    nb = bu.speichern(v, konto, bi.buchungen_lesen(inhalt), konfig.laden())
                    teile.append(f"{konto}: {n} Monatssaldi" + (f", {nb} neue Buchungen" if nb else "")
                                 + (f" ({a.zeitraum[0][:7]} bis {a.zeitraum[1][:7]})" if a.zeitraum else ""))
            return "Importiert – " + "; ".join(teile), ("budget" if form.get("zurueck") == "budget" else "vermoegen")
        if pfad == "budget/regel":
            import budget as bu
            stichwort = str(form.get("stichwort", "")).strip().lower()
            kat = str(form.get("kategorie", "")).strip()
            if not stichwort or not kat:
                raise ValueError("Stichwort und Kategorie angeben.")
            k = konfig.laden()
            k.setdefault("budget", {}).setdefault("regeln", {})
            k["budget"]["regeln"] = {**(k["budget"]["regeln"] or {}), stichwort: kat}
            konfig.speichern(k)
            with db() as v:
                n = bu.neu_kategorisieren(v, k)
            return f"Regel «{stichwort}» → {kat} gespeichert, {n} Buchungen neu zugeordnet.", "budget"
        if pfad == "budget/regel/loeschen":
            import budget as bu
            k = konfig.laden()
            (k.get("budget") or {}).get("regeln", {}).pop(str(form.get("stichwort", "")), None)
            konfig.speichern(k)
            with db() as v:
                bu.neu_kategorisieren(v, k)
            return "Regel gelöscht.", "budget"
        if pfad == "budget/sparen":
            import budget as bu
            k = konfig.laden()
            with db() as v:
                a = bu.auswerten(k, v)
            if not a:
                raise ValueError("Noch keine Buchungen.")
            erg = bu.sparen_uebernehmen(k, a)
            konfig.speichern(k)
            return "Sparpotenzial übernommen: " + ", ".join(f"{n} {seiten.chf(b)}/Monat" for n, b in erg.items()), "budget"
        if pfad == "budget/loeschen":
            import budget as bu
            with db() as v:
                n = bu.loeschen(v, form.get("konto") or None)
            return f"{n} Buchungen gelöscht.", "budget"
        if pfad == "vermoegen/anlage":
            k = konfig.laden()
            a = k.setdefault("anlage", {})
            if form.get("risiko") in ("tief", "mittel", "hoch"):
                a["risiko"] = form["risiko"]
            for f in ("zins_konto", "zins_sicher"):
                if str(form.get(f, "")).strip():
                    a[f] = vm.zahl(form[f])
            konfig.speichern(k)
            return "Anlage-Check gespeichert.", "vermoegen"
        if pfad == "vermoegen/loeschen":
            ids = [int(s_[6:]) for s_ in form if s_.startswith("sel_k:") and form.get(s_)]
            if form.get("id"):
                ids.append(int(form["id"]))
            if not ids:
                raise ValueError("Kein Konto ausgewählt.")
            with db() as v:
                for i in ids:
                    vm.konto_loeschen(v, i)
            return f"{len(ids)} Konto/Konten gelöscht.", "vermoegen"
        teile = pfad.split("/")
        if len(teile) == 4 and teile[:2] == ["vermoegen", "konto"] and teile[2].isdigit():
            kid, was = int(teile[2]), teile[3]
            zurueck = f"vermoegen/konto/{kid}"
            with db() as v:
                if was == "speichern":
                    vm.konto_aendern(v, kid, form.get("name", ""), form.get("art", "bank"), form.get("person", ""),
                                     form.get("waehrung", "CHF"), form.get("notiz", ""))
                    if "bezug_limit" in form:
                        vm.bezug_aendern(v, kid, vm.zahl(form.get("bezug_limit") or "0"), form.get("bezug_zeitraum", "jahr"),
                                         int(vm.zahl(form.get("kuendigung_monate") or "0")),
                                         vm.zahl(form.get("rueckzug_prozent") or "0"))
                    return "Konto gespeichert.", zurueck
                if was == "saldi":
                    alt = [s["datum"] for s in vm.saldi(v, kid)]
                    weg = [d for d in alt if form.get(f"sel_{d}")] if form.get("aktion") == "loeschen" else []
                    aend = {}
                    if form.get("aktion") != "loeschen":
                        for d in alt:
                            if form.get(f"d_{d}") and form.get(f"b_{d}") not in (None, ""):
                                aend[d] = (vm.datum(form[f"d_{d}"]), vm.zahl(form[f"b_{d}"]))
                    geaendert, geloescht = vm.saldi_aendern(v, kid, aend, weg)
                    neu = 0
                    if form.get("aktion") != "loeschen" and (form.get("neu_betrag") or "").strip():
                        vm.saldo_setzen(v, kid, vm.datum(form.get("neu_datum") or datetime.now().date().isoformat()),
                                        vm.zahl(form["neu_betrag"]))
                        neu = 1
                    if form.get("aktion") == "loeschen" and not weg:
                        raise ValueError("Kein Saldo ausgewählt.")
                    return (f"{geaendert} geändert, {geloescht} gelöscht" + (", 1 hinzugefügt" if neu else "") + "."), zurueck
                if was == "zusammenfuehren":
                    ziel = int(form["ziel"])
                    n = vm.zusammenfuehren(v, kid, ziel)
                    return f"Zusammengeführt – {n} Saldi übernommen.", f"vermoegen/konto/{ziel}"
                if was == "aufloesen":
                    if form.get("oeffnen"):
                        vm.aufloesen(v, kid, None)
                        return "Konto wieder geöffnet.", zurueck
                    vm.aufloesen(v, kid, vm.datum(form["datum"]))
                    return "Konto als aufgelöst markiert.", zurueck
        if pfad == "einstellungen/sensoren":
            import sensoren
            with db() as v:
                werte = sensoren.schreiben(konfig.laden(), v)
            st_ = sensoren.status()
            if st_["fehler"]:
                raise ValueError("Sensoren nicht geschrieben: " + st_["fehler"])
            return f"{len(werte)} Sensoren geschrieben.", "daten"
        if pfad == "wohnen/liegenschaft":
            k = konfig.laden()
            c = k["wohnen"].setdefault("liegenschaft", {})
            c["art"] = "wohnung" if form.get("art") == "wohnung" else "haus"
            c["marktwert_datum"] = str(form.get("marktwert_datum", "")).strip()
            for f in ("baujahr", "marktwert", "neuwert", "fonds_bestand", "fonds_sparen_monat"):
                t = str(form.get(f, "")).strip()
                c[f] = int(round(vm.zahl(t))) if t else 0
            t = str(form.get("wertentwicklung", "")).strip()
            c["wertentwicklung"] = vm.zahl(t) if t else 1.0
            konfig.speichern(k)
            if form.get("saldo"):
                import immobilie as im
                with db() as v:
                    p_ = im.planen(k, v)
                    ks = [x for x in vm.konten(v) if x["art"] == "immobilie"]
                    kid = ks[0]["id"] if ks else vm.konto_anlegen(v, "Liegenschaft (Schätzung)", "immobilie")
                    vm.saldo_setzen(v, kid, datetime.now().date().isoformat(), p_.marktwert)
                return f"Liegenschaft gespeichert, Wert CHF {seiten.chf(p_.marktwert)} als Saldo übernommen.", "wohnen"
            return "Liegenschaft gespeichert.", "wohnen"
        if pfad == "wohnen/bauteile":
            k = konfig.laden()
            c = k["wohnen"].setdefault("liegenschaft", {})
            if form.get("richtwerte"):
                c["bauteile"] = []
            else:
                teile = []
                for i in range(int(form.get("anzahl", 0) or 0)):
                    name = str(form.get(f"b_name_{i}", "")).strip()
                    if not name:
                        continue
                    z = {f: str(form.get(f"b_{f}_{i}", "")).strip() for f in ("letzte", "lebensdauer", "kosten")}
                    teile.append({"name": name, "letzte": int(vm.zahl(z["letzte"] or "0")),
                                  "lebensdauer": max(1, int(vm.zahl(z["lebensdauer"] or "20"))),
                                  "kosten": int(round(vm.zahl(z["kosten"] or "0")))})
                c["bauteile"] = teile
            konfig.speichern(k)
            return "Bauteile gespeichert." if not form.get("richtwerte") else "Richtwerte werden verwendet.", "wohnen"
        if pfad == "dokumente/loeschen":
            import verwaltung as vw
            ziel = form.get("zurueck") or "dokumente"
            if not ziel.split("?")[0] in ("dokumente", "versicherungen", "vorsorge", "steuern", "budget"):
                ziel = "dokumente"
            with db() as v:
                alle = vw.eintraege(v, konfig.datenordner())
                if form.get("einzeln"):
                    auswahl = [form["einzeln"]]
                elif form.get("aktion") == "duplikate":
                    auswahl = [e.schluessel for e in alle if e.duplikat_von]
                elif form.get("aktion") == "alle":
                    bereich = form.get("bereich") or ""
                    auswahl = [e.schluessel for e in alle if not bereich or e.schluessel.startswith(bereich + ":")]
                else:
                    auswahl = [s_[4:] for s_ in form if s_.startswith("sel_") and form.get(s_)]
                if not auswahl:
                    raise ValueError("Nichts ausgewählt.")
                n = vw.loeschen(v, konfig.datenordner(), auswahl)
            return f"{n} Eintrag/Einträge gelöscht.", ziel
        if pfad == "vorschlaege/usability":
            import usability as us
            with db() as v:
                e = us.pruefen(konfig.laden(), v)
                us.sichern(v, e)
            return f"Usability geprüft: Score {e.score}/100.", "vorschlaege#usability"
        if pfad == "vorschlaege":
            import vorschlaege as vs
            aktion = form.get("aktion") or ""
            with db() as v:
                if aktion == "idee":
                    vs.idee_speichern(v, form.get("idee") or "")
                    return "Idee gespeichert.", "vorschlaege"
                if aktion.startswith("idee_loeschen_"):
                    vs.idee_loeschen(v, int(aktion.rsplit("_", 1)[1]))
                    return "Idee gelöscht.", "vorschlaege"
                auswahl = [s_[4:] for s_ in form if s_.startswith("sel_") and form.get(s_)]
                if aktion == "alle_einblenden":
                    auswahl = list(vs.status(v))
                if not auswahl:
                    raise ValueError("Nichts ausgewählt.")
                if aktion in ("einblenden", "alle_einblenden"):
                    vs.ausblenden(v, auswahl, "")
                    return f"{len(auswahl)} Vorschlag/Vorschläge wieder eingeblendet.", "vorschlaege"
                vs.ausblenden(v, auswahl, "gemeldet" if aktion == "gemeldet" else "ausgeblendet")
            return f"{len(auswahl)} Vorschlag/Vorschläge {'als gemeldet markiert' if aktion == 'gemeldet' else 'ausgeblendet'}.", \
                "vorschlaege"
        if pfad == "dokumente/neu-sichten":
            import sichtung
            ziel = form.get("zurueck") if form.get("zurueck") in ("versicherungen", "vorsorge", "steuern", "einstellungen",
                                                               "dokumente", "daten") \
                else "einstellungen"
            if not sichtung.im_hintergrund(konfig.laden, db, konfig.datenordner(), "Knopf", alle=bool(form.get("alle"))):
                s = sichtung.STAND
                return (f"Neu sichten läuft bereits ({s['fertig']} von {s['gesamt'] or '?'} Dokumenten) – "
                        "bitte warten, bis es fertig ist."), ziel
            return ("Neu sichten läuft im Hintergrund – die App bleibt bedienbar. Gescannte Dokumente brauchen beim "
                    "ersten Mal etwas länger (Texterkennung)."), ziel
        if pfad == "bericht/stand":
            import bericht as br
            with db() as v:
                br.speichern(konfig.laden(), v)
            return "Stand gespeichert.", "bericht"
        if pfad == "steuererklaerung":
            import steuererklaerung as se
            jahr = int(form.get("jahr") or datetime.now().year)
            alle = [x for x in str(form.get("alle", "")).split(",") if x]
            ok = [x for x in alle if form.get(f"ok_{x}")]
            with db() as v:
                se.erledigt_setzen(v, jahr, ok, alle)
            return f"Stand für {jahr} gespeichert ({len(ok)} von {len(alle)} bereit).", f"steuererklaerung?jahr={jahr}"
        if pfad == "notfall":
            k = konfig.laden()
            kontakte = []
            for i in range(int(form.get("anzahl", 0) or 0)):
                c = {f: str(form.get(f"k_{f}_{i}", "")).strip() for f in ("rolle", "name", "telefon", "notiz")}
                if c["name"] or c["telefon"]:
                    kontakte.append(c)
            import notfall as nf
            ablage = {s_: str(form.get(f"a_{s_}", "")).strip() for s_, _, _ in nf.ABLAGE if str(form.get(f"a_{s_}", "")).strip()}
            k["notfall"] = {"kontakte": kontakte, "ablage": ablage, "notizen": str(form.get("notizen", "")).strip(),
                            "stand": datetime.now().strftime("%d.%m.%Y")}
            if form.get("erledigt"):
                cl = k.setdefault("nachlass", {}).setdefault("checkliste", {})
                cl["notfallordner"] = {p["name"]: True for p in k["personen"]}
            konfig.speichern(k)
            return "Notfallordner gespeichert." + (" In der Nachlass-Checkliste abgehakt." if form.get("erledigt") else ""), "notfall"
        if pfad == "kinder/lebenslauf":
            import kinderphasen as kp
            k = konfig.laden()
            kinder = k["haushalt"].get("kinder") or []
            try:
                c = kinder[int(form.get("i", -1))]
            except (ValueError, IndexError):
                return "Kind nicht gefunden.", "kinder"
            c["weg"] = str(form.get("weg") or "lehre") if str(form.get("weg")) in kp.WEGE else "lehre"
            c["danach"] = str(form.get("danach")) if str(form.get("danach")) in kp.DANACH else "keine"
            c["auswaerts"] = bool(form.get("auswaerts"))
            for f in ("kita_tage", "mittagstisch_tage", "nachmittag_std"):
                c[f] = max(0.0, min(7.0 if f != "nachmittag_std" else 60.0, vm.zahl(str(form.get(f) or "0"))))
            for f, lo, hi in (("kita_ab_monate", 0, 60), ("einschulung", -1, 2), ("sek2_jahre", 1, 6), ("tertiaer_jahre", 1, 8)):
                t = str(form.get(f, "")).strip()
                if t:
                    c[f] = int(max(lo, min(hi, round(vm.zahl(t)))))
                else:
                    c.pop(f, None)
            phasen = {}
            for schl in kp.PHASEN:
                eintrag = {}
                for kurz, feld in (("b", "betreuung"), ("l", "leben")):
                    t = str(form.get(f"{kurz}_{schl}", "")).strip()
                    if t:
                        eintrag[feld] = vm.zahl(t)
                if eintrag:
                    phasen[schl] = eintrag
            c["phasen"] = phasen
            if phasen:                                   # ältere Angaben ersetzt der Lebenslauf
                c.pop("betreuung_jahr", None)
                c.pop("betreuung_bis", None)
            konfig.speichern(k)
            return f"Lebenslauf von {c.get('name') or 'Kind'} gespeichert.", "kinder"
        if pfad == "kinder":
            k = konfig.laden()
            alt = k["haushalt"].get("kinder") or []
            neu = []
            for i in range(int(form.get("anzahl", 0) or 0)):
                name = str(form.get(f"name_{i}", "")).strip()
                if not name or form.get(f"loeschen_{i}"):
                    continue
                c = dict(alt[i]) if i < len(alt) else {}
                c.pop("geburtsjahr", None)
                c["name"] = name
                c["nachname"] = str(form.get(f"nachname_{i}", "")).strip()
                c["geburtsdatum"] = str(form.get(f"geburtsdatum_{i}", "")).strip()
                for f in ("eltern", "obhut", "gutschrift"):
                    if f"{f}_{i}" in form:
                        c[f] = str(form[f"{f}_{i}"]).strip()
                for f in ("ausbildung_bis", "betreuung_bis"):
                    if f"{f}_{i}" in form:
                        t = str(form.get(f"{f}_{i}", "")).strip()
                        c[f] = int(round(vm.zahl(t))) if t else 0
                for f in ("betreuung_jahr", "zulage_monat"):
                    if f"{f}_{i}" in form:
                        t = str(form.get(f"{f}_{i}", "")).strip()
                        c[f] = vm.zahl(t) if t else 0.0
                c["ausbildung_bis"] = min(25, max(18, int(c.get("ausbildung_bis") or 18)))
                c["betreuung_bis"] = c.get("betreuung_bis") or 12
                neu.append(c)
            k["haushalt"]["kinder"] = neu
            konfig.speichern(k)
            return f"{len(neu)} Kind(er) gespeichert.", "kinder"
        if pfad in ("verfuegungen", "verfuegungen/vermerken"):
            import verfuegungen as vf
            k = konfig.laden()
            typ, wer = str(form.get("typ", "")), str(form.get("wer", ""))
            if typ not in vf.NACH_TYP or wer not in vf.spalten(k, vf.NACH_TYP[typ]):
                raise ValueError("Unbekanntes Dokument.")
            ziel = f"verfuegungen?typ={typ}&wer={quote(wer)}"
            t_ = vf.NACH_TYP[typ]
            if pfad == "verfuegungen/vermerken":
                import fragebogen as fb
                bereich = fb.NACH_SCHLUESSEL[t_.fragebogen]
                kern = next((f.schluessel for f in bereich.fragen if f.auswahl == tuple(fb.JA_NEIN)), None)
                fbr = k.setdefault("nachlass", {}).setdefault("fragebogen", {}).setdefault(t_.fragebogen, {})
                eintrag = fbr.setdefault(wer if bereich.je_person else fb.HAUSHALT, {})
                if kern and eintrag.get(kern) in (None, "", "nein"):
                    eintrag[kern] = "in Arbeit"
                if any(f.schluessel == "form" for f in bereich.fragen) and not eintrag.get("form"):
                    eintrag["form"] = "eigenhändig (von Hand geschrieben)"
                konfig.speichern(k)
                return f"{t_.titel}: im Nachlass-Fragebogen als «in Arbeit» vermerkt.", ziel
            vf.speichern(k, typ, wer, form)
            konfig.speichern(k)
            return f"{t_.titel}: Entwurf aktualisiert.", ziel
        if pfad == "nachlass/fragebogen":
            import fragebogen as fb
            k = konfig.laden()
            bereich = str(form.get("bereich", ""))
            if bereich not in fb.NACH_SCHLUESSEL:
                raise ValueError("Unbekannter Bereich.")
            n = fb.speichern(k, bereich, form)
            b = fb.NACH_SCHLUESSEL[bereich]
            text = f"{b.titel}: {n} Angaben gespeichert."
            if form.get("abhaken"):
                cl = k.setdefault("nachlass", {}).setdefault("checkliste", {}).setdefault(bereich, {})
                for p in k["personen"]:
                    if (not b.je_person and fb.erledigt_vorschlag(k, b, fb.HAUSHALT)) or fb.erledigt_vorschlag(k, b, p["name"]):
                        cl[p["name"]] = True
                text += " In der Checkliste abgehakt."
            konfig.speichern(k)
            return text, f"nachlass/fragebogen?bereich={bereich}#{bereich}"
        if pfad == "nachlass/checkliste":
            import nachlass as nl
            k = konfig.laden()
            n = k.setdefault("nachlass", {})
            n["checkliste"] = {s_: {p["name"]: bool(form.get(f"{s_}|{p['name']}")) for p in k["personen"]}
                               for s_, _, _ in nl.CHECKLISTE}
            if str(form.get("zusammen_seit", "")).strip():
                n["zusammen_seit"] = int(str(form["zusammen_seit"]).strip()[:4])
            konfig.speichern(k)
            return "Nachlass-Checkliste gespeichert.", "nachlass"
        if pfad == "erinnerungen/erledigt":
            import erinnerungen as er
            with db() as v:
                er.erledigen(v, form["schluessel"])
            return "Erinnerung erledigt.", ""
        if pfad == "einstellungen/importordner":
            with db() as v:
                meldungen = importordner.einlesen(konfig.datenordner(), v)
            return (" · ".join(meldungen) if meldungen else "Der Import-Ordner ist leer."), "daten"
        if pfad.startswith("versicherungen"):
            return self._versicherungen(pfad, form)
        if pfad.startswith("vorsorge"):
            return self._vorsorge(pfad, form)
        if pfad.startswith("berater"):
            return self._berater(pfad, form)
        if pfad.startswith("steuern"):
            return self._steuern(pfad, form)
        if pfad == "fahrzeuge/speichern":
            import fahrzeuge as fz
            k = konfig.laden()
            liste = list(k.get("fahrzeuge") or [])
            neu = {}
            for feld, _, typ in seiten.FAHRZEUG_FELDER:
                t = str(form.get(feld) or "").strip()
                if not t:
                    continue
                neu[feld] = vm.zahl(t) if typ == "zahl" else t[:80]
            if not neu.get("name"):
                raise ValueError("Name des Fahrzeugs angeben.")
            if neu.get("antrieb") not in fz.ANTRIEBE:
                neu["antrieb"] = "benzin"
            neu["ersatz_planen"] = bool(form.get("ersatz_planen"))
            i = int(form.get("i")) if str(form.get("i") or "").isdigit() else None
            if i is not None and i < len(liste):
                liste[i] = neu
            else:
                liste.append(neu)
            k["fahrzeuge"] = liste
            konfig.speichern(k)
            return f"Fahrzeug «{neu['name']}» gespeichert.", "fahrzeuge"
        if pfad == "fahrzeuge/loeschen":
            k = konfig.laden()
            liste = list(k.get("fahrzeuge") or [])
            i = int(form.get("i") or -1)
            if 0 <= i < len(liste):
                weg = liste.pop(i)
                k["fahrzeuge"] = liste
                konfig.speichern(k)
                with db() as v:                                # Wertkonto bleibt, wird als aufgelöst markiert
                    x = next((x for x in vm.konten(v) if x["name"] == f"Fahrzeug {weg.get('name')}"), None)
                    if x:
                        v.execute("UPDATE konten SET aufgeloest = ? WHERE id = ?", (datetime.now().date().isoformat(), x["id"]))
                        v.commit()
            return "Fahrzeug entfernt.", "fahrzeuge"
        if pfad == "finanzplan/ziel":
            k = konfig.laden()
            name = str(form.get("name") or "").strip()[:60]
            betrag = vm.zahl(form.get("betrag") or "")
            jahr = int(str(form.get("jahr") or "0").strip() or 0)
            if not name or betrag <= 0 or not 2000 < jahr < 2150:
                raise ValueError("Name, Betrag und Jahr angeben.")
            k.setdefault("ziele", [])
            k["ziele"] = list(k["ziele"] or []) + [{"name": name, "betrag": betrag, "jahr": jahr,
                                                   "art": "muss" if form.get("art") == "muss" else "wunsch"}]
            konfig.speichern(k)
            return f"Ziel «{name}» gespeichert.", "finanzplan"
        if pfad == "finanzplan/ziel_loeschen":
            k = konfig.laden()
            i = int(form.get("i") or -1)
            liste = list(k.get("ziele") or [])
            if 0 <= i < len(liste):
                liste.pop(i)
                k["ziele"] = liste
                konfig.speichern(k)
            return "Ziel entfernt.", "finanzplan"
        if pfad == "szenarien/marktzinsen":
            import marktzinsen as mz
            with db() as v:
                try:
                    n = mz.holen(v)
                except OSError as e:
                    raise ValueError(f"Marktzinsen nicht geholt ({e}).") from e
            return f"Marktzinsen aktualisiert ({n} Werte der SNB).", "szenarien#hypothek"
        if pfad == "szenarien/offerte":
            from datetime import date as _d
            k = konfig.laden()
            st_ = k["wohnen"].setdefault("strategie", {}) or {}
            k["wohnen"]["strategie"] = st_
            datum = str(form.get("datum") or _d.today().isoformat())[:10]
            _d.fromisoformat(datum)
            zins = vm.zahl(form.get("zins") or "")
            if not 0 < zins < 15:
                raise ValueError("Zins in Prozent angeben, z. B. 1.65.")
            st_.setdefault("offerten", []).append({"bank": str(form.get("bank") or "").strip()[:60],
                                                   "produkt": str(form.get("produkt") or "fest5"), "zins": zins,
                                                   "datum": datum})
            konfig.speichern(k)
            return "Offerte gespeichert.", "szenarien#hypothek"
        if pfad == "szenarien/offerte_loeschen":
            import marktzinsen as mz
            k = konfig.laden()
            sichtbar = mz.offerten(k)
            i = int(form.get("i") or -1)
            if 0 <= i < len(sichtbar):
                weg = sichtbar[i]
                liste = k["wohnen"]["strategie"]["offerten"]
                k["wohnen"]["strategie"]["offerten"] = [o for o in liste if not (
                    o.get("bank") == weg.get("bank") and o.get("produkt") == weg.get("produkt")
                    and str(o.get("datum")) == str(weg.get("datum")) and float(o.get("zins") or 0) == weg["zins"])]
                konfig.speichern(k)
            return "Offerte entfernt.", "szenarien#hypothek"
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
                    f"{sum(plan.plan.values()):,.0f})." >> TS, "szenarien")
        raise ValueError("Unbekannte Aktion.")

    def _versicherungen(self, pfad: str, form: dict):
        daten = konfig.datenordner()
        teile = pfad.split("/")
        with db() as v:
            if pfad == "versicherungen/hochladen":
                import verwaltung as vw
                dateien, doppelt = vw.neue_dateien(v, daten, "v", form.get("_dateien_datei") or [])
                if doppelt and not dateien:
                    raise ValueError("Bereits hochgeladen: " + "; ".join(doppelt))
                ids = [vi.hochladen(v, daten, n, inhalt) for n, inhalt in dateien if inhalt]
                LOG.info("%d Versicherungsverträge hochgeladen", len(ids))
                import krankenkasse as kk
                k = konfig.laden()
                kvg = [n for vid in ids if (n := kk.police_uebernehmen(k, vi.einer(v, vid)))]
                if kvg:
                    konfig.speichern(k)
                zusatz = f" Grundversicherung von {', '.join(kvg)} in den Krankenkassen-Rechner übernommen." if kvg else ""
                zusatz += (" Übersprungen, weil schon vorhanden: " + "; ".join(doppelt)) if doppelt else ""
                if len(ids) == 1 and not kvg and not doppelt:
                    return "Vertrag analysiert – bitte die erkannten Werte prüfen.", f"versicherungen/{ids[0]}"
                return f"{len(ids)} Dokument(e) analysiert.{zusatz}"
            if pfad == "versicherungen/praemien_laden":
                import kkpraemien as kp
                k = konfig.laden()
                kanton = str(k["haushalt"].get("kanton") or "").upper()
                if not kanton:
                    raise ValueError("Zuerst den Wohnkanton unter Einstellungen eintragen.")
                datei = form.get("datei")
                if datei:
                    jahr, n = kp.einlesen(v, datei, kanton)
                else:
                    try:
                        jahr, n = kp.herunterladen(v, kanton)
                    except OSError as e:
                        raise ValueError(f"Prämien nicht geladen ({e}). Ohne Internet die Datei Prämien_CH.csv hochladen.") from e
                LOG.info("Krankenkassen-Prämien %s für %s: %d Zeilen", jahr, kanton, n)
                return f"Prämien {jahr} für Kanton {kanton} geladen ({n} Tarife).", "versicherungen"
            if pfad == "versicherungen/krankenkasse":
                k = konfig.laden()
                liste = []
                i = 0
                while f"name_{i}" in form:
                    liste.append({"name": form[f"name_{i}"], "praemie_monat": vm.zahl(form.get(f"praemie_{i}") or "0"),
                                  "franchise": int(form.get(f"franchise_{i}") or 300),
                                  "kosten_jahr": vm.zahl(form.get(f"kosten_{i}") or "0"),
                                  "modell": form.get(f"modell_{i}", "standard"), "unfall": form.get(f"unfall_{i}") == "ja"})
                    i += 1
                alt = {e.get("name"): e for e in (k.get("krankenkasse") or {}).get("personen") or []}
                for e in liste:
                    if alt.get(e["name"], {}).get("angebote"):
                        e["angebote"] = alt[e["name"]]["angebote"]
                k.setdefault("krankenkasse", {})["personen"] = liste
                konfig.speichern(k)
                return "Krankenkasse gespeichert.", "versicherungen"
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
                import verwaltung as vw
                dateien, doppelt = vw.neue_dateien(v, daten, "d", form.get("_dateien_datei") or [])
                if doppelt and not dateien:
                    raise ValueError("Bereits hochgeladen: " + "; ".join(doppelt))
                ids = [dk.hochladen(v, daten, n, inhalt) for n, inhalt in dateien if inhalt]
                if len(ids) == 1 and not doppelt:
                    return "Dokument analysiert – Werte prüfen und übernehmen.", f"vorsorge/dokument/{ids[0]}"
                return f"{len(ids)} Dokumente analysiert." + (" Übersprungen, weil schon vorhanden: " + "; ".join(doppelt) if doppelt else "")
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
                    if "guthaben_3b" in gewaehlt and "guthaben_3b" in dok["werte"]:
                        erledigt.append(dk.guthaben_3b_uebernehmen(k, v, dok, form["person"], form.get("konto_3b", "")))
                    if "guthaben_3a" in gewaehlt and "guthaben_3a" in dok["werte"] and form.get("konto_3a"):
                        import dreia
                        erledigt.append(dreia.guthaben_uebernehmen(v, dok, form["person"], form.get("konto_3a", "")))
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
            if pfad == "vermoegen/wertschriften":
                import wertschriften as ws
                n = ws.speichern(v, ws.csv_lesen(form.get("datei") or b""), "csv")
                return f"{n} Positionen importiert.", "vermoegen#wertschriften"
            if pfad == "vermoegen/wertschriften/ter":
                k = konfig.laden()
                ter = (k.setdefault("wertschriften", {}).get("ter") or {})
                for feld, wert in form.items():
                    if feld.startswith("ter_"):
                        w = str(wert.decode() if isinstance(wert, bytes) else wert).strip().replace(",", ".")
                        if w:
                            ter[feld[4:].upper()] = float(w)
                        else:
                            ter.pop(feld[4:].upper(), None)
                k["wertschriften"]["ter"] = ter
                konfig.speichern(k)
                return "Kosten gespeichert.", "vermoegen#wertschriften"
            if pfad == "steuern/steuerauszug":
                import esteuerauszug as es
                teile_ = []
                for name, inhalt in form.get("_dateien_datei") or []:
                    s = es.lesen(inhalt, name)
                    _, n = es.speichern(v, s, form.get("person", ""))
                    teile_.append(f"{s.institut or 'Bank'} {s.jahr or ''}".strip() + (f": {n} Konten/Depots ins Vermögen"
                                  if n else " (nur Totale aus dem PDF-Text)"))
                return "Steuerauszug gelesen – " + "; ".join(teile_), "steuern#steuerauszug"
            if len(teile) == 4 and teile[1] == "steuerauszug" and teile[2].isdigit() and teile[3] == "loeschen":
                import esteuerauszug as es
                es.loeschen(v, int(teile[2]))
                return "Steuerauszug entfernt (die Saldi im Vermögen bleiben).", "steuern#steuerauszug"
            if pfad == "steuern/hochladen":
                import verwaltung as vw
                dateien, doppelt = vw.neue_dateien(v, daten, "s", form.get("_dateien_datei") or [])
                if doppelt and not dateien:
                    raise ValueError("Bereits hochgeladen: " + "; ".join(doppelt))
                ids = [sd.hochladen(v, daten, n, inhalt) for n, inhalt in dateien if inhalt]
                if len(ids) == 1 and not doppelt:
                    return "Steuerdokument analysiert – Werte prüfen und übernehmen.", f"steuern/dokument/{ids[0]}"
                return f"{len(ids)} Steuerdokumente analysiert." + (" Übersprungen, weil schon vorhanden: " + "; ".join(doppelt) if doppelt else "")
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
    # pypdf meldet bei leicht defekten PDFs Hunderte harmlose Warnungen – nur echte Fehler protokollieren
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    import meta
    LOG.info("Finanzplanung %s startet", meta.version())
    konfig.laden()
    try:
        with db() as v:
            importordner.einlesen(ordner, v)
    except Exception as e:  # noqa: BLE001
        LOG.warning("Import-Ordner: %s", e)
    import zwischenspeicher
    zwischenspeicher.einschalten()
    import leistung
    leistung.instrumentieren()
    import erinnerungen
    import sensoren
    erinnerungen.hintergrund(konfig.laden, db)
    sensoren.hintergrund(konfig.laden, db)
    import sichtung
    sichtung.nach_update(konfig.laden, db, ordner)
    port = int(os.environ.get("PORT", "8099"))
    LOG.info("Finanzplanung läuft auf Port %d, Daten in %s", port, ordner)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
