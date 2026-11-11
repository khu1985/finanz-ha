"""Detail-Fragebögen zur Nachlass-Checkliste – die Antworten fliessen in den Notfallordner.

Pro Bereich der Checkliste (Testament, Pensionskasse, 3a, Policen, Vorsorgeauftrag, Patientenverfügung,
Konkubinatsvertrag, Liegenschaft, Willensvollstrecker, Notfallordner) konkrete Fragen: was gibt es, wer ist
begünstigt bzw. bevollmächtigt, wo liegt das Original, wann zuletzt geprüft. Gespeichert unter
`nachlass.fragebogen.<bereich>.<person oder haushalt>.<frage>` in finanz.yaml (bleibt im Home Assistant).
"""
from __future__ import annotations

from dataclasses import dataclass

JA_NEIN = ["", "ja", "nein", "in Arbeit"]
HAUSHALT = "haushalt"


@dataclass(frozen=True)
class Frage:
    schluessel: str
    text: str
    art: str = "text"                 # text | lang | datum | auswahl
    auswahl: tuple[str, ...] = ()
    hilfe: str = ""
    wichtig: bool = False             # zählt für «vollständig» und steht im Notfallordner zuerst


@dataclass(frozen=True)
class Bereich:
    schluessel: str                   # wie in nachlass.CHECKLISTE
    titel: str
    je_person: bool
    fragen: tuple[Frage, ...]
    nur_konkubinat: bool = False


def _jn(schluessel: str, text: str, hilfe: str = "", wichtig: bool = True) -> Frage:
    return Frage(schluessel, text, "auswahl", tuple(JA_NEIN), hilfe, wichtig)


BEREICHE: tuple[Bereich, ...] = (
    Bereich("testament", "Testament bzw. Erbvertrag", True, (
        _jn("vorhanden", "Gibt es ein Testament oder einen Erbvertrag?"),
        Frage("form", "Form", "auswahl", ("", "eigenhändig (von Hand geschrieben)", "öffentlich beurkundet (Notar)",
                                          "Erbvertrag (Notar)"), "Eigenhändig: vollständig von Hand, datiert, unterschrieben."),
        Frage("datum", "Datum", "datum"),
        Frage("original", "Wo liegt das Original?", hilfe="z. B. Notar, Gemeinde (Testamentsaufbewahrung), Safe", wichtig=True),
        Frage("kopie", "Kopie bei"),
        Frage("inhalt", "Wer erhält was (Kurzfassung)?", "lang",
              hilfe="Erben, Quoten, Vermächtnisse – die Pflichtteile der Nachkommen beachten"),
        Frage("geprueft", "Zuletzt geprüft", "datum", hilfe="nach Heirat, Geburt, Trennung, Kauf der Liegenschaft prüfen"),
    )),
    Bereich("pk_meldung", "Pensionskasse: Lebenspartner und Begünstigung", True, (
        Frage("kasse", "Pensionskasse", wichtig=True),
        _jn("gemeldet", "Partner bzw. Partnerin der Kasse gemeldet?",
            "Im Konkubinat Voraussetzung für Lebenspartnerrente und Todesfallkapital – meist zu Lebzeiten schriftlich."),
        Frage("datum", "Gemeldet am", "datum"),
        _jn("bestaetigung", "Schriftliche Bestätigung der Kasse vorhanden?", wichtig=False),
        Frage("leistungen", "Leistungen im Todesfall laut Reglement", "lang",
              hilfe="Partnerrente, Waisenrente, Todesfallkapital – siehe Vorsorgeausweis"),
        Frage("kontakt", "Kontakt der Kasse (Telefon, Versichertennummer)"),
    )),
    Bereich("begünstigung_3a", "Säule 3a: Begünstigung", True, (
        Frage("konten", "Konten bzw. Policen 3a (Anbieter)", "lang", wichtig=True),
        Frage("beguenstigt", "Begünstigte Person(en)", wichtig=True),
        _jn("schriftlich", "Begünstigung schriftlich bei der Stiftung bzw. Versicherung festgelegt?",
            "Lebenspartner nach 5 Jahren Zusammenleben oder mit gemeinsamem Kind möglich – sonst gilt die gesetzliche "
            "Reihenfolge."),
        Frage("datum", "Festgelegt am", "datum"),
    )),
    Bereich("begünstigung_policen", "Risiko- und Lebensversicherungen: Begünstigte", True, (
        Frage("policen", "Policen (Versicherer, Art, Summe)", "lang", wichtig=True),
        Frage("beguenstigt", "Begünstigte Person(en)", wichtig=True),
        _jn("bestaetigt", "Begünstigung vom Versicherer bestätigt?", wichtig=False),
        Frage("datum", "Zuletzt angepasst", "datum"),
    )),
    Bereich("vorsorgeauftrag", "Vorsorgeauftrag", True, (
        _jn("vorhanden", "Gibt es einen Vorsorgeauftrag?"),
        Frage("form", "Form", "auswahl", ("", "eigenhändig (von Hand geschrieben)", "öffentlich beurkundet (Notar)")),
        Frage("person", "Beauftragte Person", wichtig=True),
        Frage("ersatz", "Ersatzperson"),
        Frage("bereiche", "Bereiche", "auswahl", ("", "Vermögenssorge, Rechtsverkehr und Personensorge",
                                                 "nur Vermögenssorge und Rechtsverkehr", "nur Personensorge")),
        _jn("infostar", "Hinterlegungsort beim Zivilstandsamt (Infostar) eingetragen?", "So findet die KESB ihn sofort.",
            wichtig=False),
        Frage("original", "Wo liegt das Original?", wichtig=True),
        Frage("datum", "Datum", "datum"),
    )),
    Bereich("patientenverfuegung", "Patientenverfügung", True, (
        _jn("vorhanden", "Gibt es eine Patientenverfügung?"),
        Frage("vertretung", "Vertretungsperson für medizinische Entscheide", wichtig=True),
        Frage("hinterlegt", "Hinterlegt bei", hilfe="Hausarzt, Spitalakte, Karte im Portemonnaie, elektronisches Patientendossier"),
        Frage("organspende", "Organspende", "auswahl", ("", "ja", "nein", "nur bestimmte Organe", "Angehörige entscheiden")),
        Frage("wuensche", "Wichtigste Wünsche (Kurzfassung)", "lang"),
        Frage("datum", "Zuletzt aktualisiert", "datum"),
    )),
    Bereich("konkubinatsvertrag", "Konkubinatsvertrag", False, (
        _jn("vorhanden", "Gibt es einen Konkubinatsvertrag?"),
        Frage("datum", "Datum", "datum"),
        Frage("eigentum", "Wem gehört was (Hausrat, Fahrzeuge, Konten)?", "lang"),
        Frage("darlehen", "Darlehen und Beiträge an die Liegenschaft", "lang"),
        Frage("wohnen", "Regelung Wohnen und Trennung", "lang"),
        Frage("original", "Wo liegt das Original?", wichtig=True),
    ), nur_konkubinat=True),
    Bereich("liegenschaft", "Regelung für die Liegenschaft", False, (
        Frage("eigentum", "Eigentumsform", "auswahl", ("", "Alleineigentum", "Miteigentum", "Gesamteigentum"), wichtig=True),
        Frage("regelung", "Was gilt im Todesfall?", "auswahl", ("", "Partner erhält alles (Testament/Ehevertrag)",
                                                                "Wohnrecht", "Nutzniessung", "Kaufsrecht",
                                                                "keine Regelung")),
        Frage("ausgleich", "Wie wird die Auszahlung an die Erben finanziert?", "lang",
              hilfe="z. B. Todesfallrisiko-Police, Erhöhung der Hypothek, Ersparnisse"),
        _jn("tragbar", "Kann der überlebende Partner die Hypothek allein tragen?", wichtig=False),
        Frage("dokumente", "Wo liegen Grundbuchauszug, Kaufvertrag, Hypothekarvertrag?"),
    )),
    Bereich("willensvollstrecker", "Willensvollstrecker", False, (
        _jn("bestimmt", "Ist ein Willensvollstrecker im Testament bestimmt?"),
        Frage("name", "Name", wichtig=True),
        Frage("kontakt", "Telefon / E-Mail"),
        Frage("ersatz", "Ersatz"),
        Frage("honorar", "Honorar bzw. Vereinbarung"),
    )),
    Bereich("notfallordner", "Notfallordner, Zugänge und letzte Wünsche", True, (
        Frage("wer_weiss", "Wer weiss, wo der Notfallordner liegt?", wichtig=True),
        Frage("zugaenge", "Zugänge: Passwort-Manager, Notfallzugriff, Handy-Code", "lang",
              hilfe="Nur den Ort bzw. das Verfahren notieren – keine Passwörter hier eintragen."),
        Frage("digital", "Digitaler Nachlass (E-Mail, Fotos, soziale Netzwerke, Abos)", "lang",
              hilfe="Nachlasskontakt bei Apple und Google, Wünsche zu Konten"),
        Frage("bestattung", "Bestattungswünsche", "lang", hilfe="Erd-/Feuerbestattung, Ort, Zeremonie, Vorsorgevertrag"),
        Frage("weiteres", "Haustiere, laufende Verpflichtungen, persönliche Nachrichten", "lang"),
    )),
)

NACH_SCHLUESSEL = {b.schluessel: b for b in BEREICHE}


def bereiche(k: dict) -> list[Bereich]:
    konkubinat = k["haushalt"].get("zivilstand", "verheiratet") != "verheiratet" and len(k["personen"]) > 1
    return [b for b in BEREICHE if konkubinat or not b.nur_konkubinat]


def antworten(k: dict) -> dict:
    return ((k.get("nachlass") or {}).get("fragebogen") or {})


def spalten(k: dict, b: Bereich) -> list[str]:
    """Personen (je Person) oder «haushalt»."""
    return [p["name"] for p in k["personen"]] if b.je_person else [HAUSHALT]


def wert(k: dict, b: Bereich, wer: str, frage: str) -> str:
    return str(((antworten(k).get(b.schluessel) or {}).get(wer) or {}).get(frage) or "").strip()


def stand(k: dict, b: Bereich) -> tuple[int, int]:
    """(beantwortet, total) der wichtigen Fragen über alle Spalten."""
    wichtige = [f for f in b.fragen if f.wichtig] or list(b.fragen)
    total = len(wichtige) * len(spalten(k, b))
    erfasst = sum(1 for w in spalten(k, b) for f in wichtige if wert(k, b, w, f.schluessel))
    return erfasst, total


def speichern(k: dict, bereich: str, form: dict) -> int:
    """Formularwerte «<spalte>|<frage>» übernehmen; gibt die Anzahl ausgefüllter Felder zurück."""
    b = NACH_SCHLUESSEL[bereich]
    fb = k.setdefault("nachlass", {}).setdefault("fragebogen", {})
    neu: dict = {}
    n = 0
    for wer in spalten(k, b):
        werte = {}
        for f in b.fragen:
            v = str(form.get(f"{wer}|{f.schluessel}", "")).strip()
            if v:
                werte[f.schluessel] = v[:2000]
                n += 1
        if werte:
            neu[wer] = werte
    if neu:
        fb[bereich] = neu
    else:
        fb.pop(bereich, None)
    return n


def erledigt_vorschlag(k: dict, b: Bereich, wer: str) -> bool:
    """Ein Bereich gilt als erledigt, wenn die Ja/Nein-Kernfrage «ja» ist und die wichtigen Felder ausgefüllt sind."""
    kern = next((f for f in b.fragen if f.art == "auswahl" and f.auswahl == tuple(JA_NEIN)), None)
    if kern and wert(k, b, wer, kern.schluessel) != "ja":
        return False
    return all(wert(k, b, wer, f.schluessel) for f in b.fragen if f.wichtig)


def fuer_notfallordner(k: dict) -> list[tuple[str, list[tuple[str, list[str]]]]]:
    """Ausgefüllte Antworten für den Notfallordner: [(Bereich, [(Frage, [Antwort je Spalte])])] – nur Beantwortetes."""
    erg = []
    for b in bereiche(k):
        zeilen = []
        for f in sorted(b.fragen, key=lambda f: not f.wichtig):
            werte = [wert(k, b, w, f.schluessel) for w in spalten(k, b)]
            if any(werte):
                zeilen.append((f.text, werte))
        if zeilen:
            erg.append((b.titel, zeilen))
    return erg
