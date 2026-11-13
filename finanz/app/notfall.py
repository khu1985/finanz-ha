"""Notfallordner: Übersicht für Angehörige – was es gibt, wo es liegt, wen man anruft und was zu tun ist.

Aus der App: Personen, Kinder, Konten mit letztem Saldo, Vorsorge (Dokumente, Risikoleistungen), Versicherungen,
Liegenschaft. Selbst gepflegt unter `notfall`: Kontakte (Rolle, Name, Telefon, Notiz) und Ablageorte.
Die Seite lässt sich drucken (Druckansicht ohne Menü und Formulare).
"""
from __future__ import annotations

from dataclasses import dataclass

KONTAKT_ROLLEN = ["Hausarzt", "Notar / Willensvollstrecker", "Bank", "Versicherungsberater", "Pensionskasse",
                  "Arbeitgeber (HR)", "Steuerberatung", "Verwaltung / Vermieter", "Vertrauensperson"]

ABLAGE = [
    ("testament", "Testament / Erbvertrag", "Original muss nach dem Tod sofort der Behörde eingereicht werden"),
    ("vorsorgeauftrag", "Vorsorgeauftrag", ""),
    ("patientenverfuegung", "Patientenverfügung", "auch beim Hausarzt hinterlegen"),
    ("ausweise", "Ausweise, Familienbüchlein, Heiratsurkunde", ""),
    ("policen", "Policen und Vorsorgeausweise", ""),
    ("bank", "Bankunterlagen, Vollmachten, Karten", "Vollmacht «über den Tod hinaus» erleichtert die ersten Wochen"),
    ("passwoerter", "Passwort-Manager / Notfallzugang", "z. B. Notfallzugriff des Passwort-Managers, versiegelter Umschlag"),
    ("digital", "Digitales: E-Mail, Fotos, Konten, Abos", "Nachlasskontakt bei Apple/Google einrichten"),
    ("schluessel", "Schlüssel, Safe, Bankschliessfach", ""),
    ("liegenschaft", "Grundbuchauszug, Kaufvertrag, Hypothekarvertrag", ""),
]


@dataclass
class Schritt:
    wann: str
    was: str
    detail: str


def erste_schritte(k: dict) -> list[Schritt]:
    verheiratet = k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet"
    s = [
        Schritt("Sofort", "Arzt rufen", "Ärztliche Todesbescheinigung; bei Tod zu Hause Hausarzt bzw. Notfallarzt."),
        Schritt("Innert 2 Tagen", "Todesfall melden", "Beim Bestattungsamt bzw. der Wohngemeinde (Todesbescheinigung, "
                "Ausweise, Familienbüchlein). Bestattung und Wünsche klären."),
        Schritt("Sofort nach Auffinden", "Testament einreichen", "Jedes Testament muss der Erbschaftsbehörde bzw. dem Notar "
                "eingereicht werden (Art. 556 ZGB) – auch wenn es ungültig scheint."),
        Schritt("Erste Woche", "Arbeitgeber und Banken informieren", "Konten werden bis zur Erbbescheinigung meist "
                "gesperrt; laufende Rechnungen mit Vollmacht über den Tod hinaus oder aus eigenem Konto zahlen."),
        Schritt("Erste Wochen", "Hinterlassenenleistungen anmelden", "AHV-Ausgleichskasse (Witwen-, Witwer-, Waisenrenten), "
                "Pensionskasse (Rente bzw. Todesfallkapital), 3a-Stiftungen, Lebens- und Unfallversicherungen."),
        Schritt("Erste Wochen", "Krankenkasse, Versicherungen, Verträge", "Policen der verstorbenen Person kündigen bzw. "
                "anpassen; Abos, Handy, Mitgliedschaften."),
        Schritt("Monate", "Erbbescheinigung und Teilung", "Erbbescheinigung beantragen, Inventar, Steuererklärung bis zum "
                "Todestag, Grundbuch, Erbteilung (Willensvollstrecker oder Erbengemeinschaft)."),
    ]
    if not verheiratet and len(k["personen"]) > 1:
        s.insert(4, Schritt("So früh wie möglich", "Konkubinat: Ansprüche geltend machen",
                            "Der Lebenspartner ist kein gesetzlicher Erbe und bekommt keine AHV-Hinterlassenenrente. "
                            "Lebenspartnerrente bzw. Todesfallkapital bei der Pensionskasse und Begünstigung bei 3a und "
                            "Policen aktiv anmelden – Kassen setzen dafür teils Fristen. Testament und Konkubinatsvertrag "
                            "vorlegen."))
    return s


def meldeliste(k: dict, db) -> list[tuple[str, str, str]]:
    """Konkrete Stellen, die nach einem Todesfall zu melden sind – aus den erfassten Daten (Stelle, Wozu, Person)."""
    import dokumente as dk
    import vermoegen as vm
    import versicherungen as vi
    erg: list[tuple[str, str, str]] = []
    gesehen: set[tuple[str, str]] = set()

    def neu(stelle: str, wozu: str, person: str = "") -> None:
        if stelle and (stelle.lower(), person) not in gesehen:
            gesehen.add((stelle.lower(), person))
            erg.append((stelle, wozu, person))

    for p in k["personen"]:
        neu("Wohngemeinde bzw. Bestattungsamt", "Todesfall melden (innert 2 Tagen), Bestattung", p["name"])
        neu("AHV-Ausgleichskasse", "Rente stoppen bzw. Hinterlassenenrenten beantragen", p["name"])
        if p.get("arbeitgeber"):
            neu(str(p["arbeitgeber"]), "Arbeitgeber: Lohn bis Todestag, Lohnnachgenuss", p["name"])
    try:
        dk.tabellen(db)
        for d in dk.alle(db):
            if d.get("anbieter") and d["typ"] in ("pk_ausweis", "saeule3a", "saeule3b"):
                wozu = {"pk_ausweis": "Pensionskasse: Hinterlassenenrente bzw. Todesfallkapital anmelden",
                        "saeule3a": "Säule 3a: Auszahlung an die Begünstigten", "saeule3b": "Säule 3b: Leistung bzw. "
                        "Rückkaufswert"}[d["typ"]]
                neu(str(d["anbieter"]), wozu, str(d.get("person") or ""))
    except Exception:  # noqa: BLE001
        pass
    try:
        for x in vm.konten(db):
            if x["art"] in ("bank", "depot", "saeule3a", "vorsorge", "hypothek", "kredit") and not x.get("aufgeloest"):
                wozu = {"hypothek": "Hypothek: Schuldner melden, Zinsen weiter zahlen", "kredit": "Kredit melden"}.get(
                    x["art"], "Konto melden (Sperre bis zur Erbbescheinigung), Saldo am Todestag verlangen")
                neu(str(x["name"]), wozu, str(x.get("person") or ""))
    except Exception:  # noqa: BLE001
        pass
    try:
        vi.tabellen(db)
        for v in vi.alle(db):
            sparte = vi.SPARTEN.get(v["sparte"], v["sparte"])
            wozu = ("Leistung im Todesfall anmelden" if v["sparte"] in ("risiko_leben", "leben_3b", "unfall",
                                                                         "erwerbsunfaehigkeit")
                    else "Vertrag kündigen bzw. auf Hinterbliebene umschreiben")
            neu(f"{v.get('versicherer') or 'Versicherung'} – {sparte}", wozu + (f" (Police {v['police']})"
                                                                                if v.get("police") else ""),
                str(v.get("person") or ""))
    except Exception:  # noqa: BLE001
        pass
    neu("Steuerverwaltung", "Steuererklärung bis zum Todestag; Inventar für die Erbschaftssteuer")
    return erg


def konfiguration(k: dict) -> dict:
    cfg = k.get("notfall") or {}
    return {"kontakte": list(cfg.get("kontakte") or []), "ablage": dict(cfg.get("ablage") or {}),
            "notizen": str(cfg.get("notizen") or ""), "stand": str(cfg.get("stand") or "")}


def vollstaendigkeit(k: dict) -> tuple[int, int]:
    """(erfasst, total) für Kontakte (Hausarzt, Notar/Bank) und Ablageorte."""
    cfg = konfiguration(k)
    ablage = sum(1 for s, _, _ in ABLAGE if str(cfg["ablage"].get(s, "")).strip())
    kontakte = min(3, sum(1 for c in cfg["kontakte"] if str(c.get("name", "")).strip()))
    return ablage + kontakte, len(ABLAGE) + 3
