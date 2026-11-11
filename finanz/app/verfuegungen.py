"""Verfügungen: Fragen mit Optionen → Entwurf für Testament, Vorsorgeauftrag, Patientenverfügung,
Konkubinatsvertrag und Begünstigung Säule 3a.

Grundlage Schweizer Recht (Erbrecht seit 1.1.2023): gesetzliche Erbteile Ehegatte/eingetragener Partner ½ neben
Nachkommen, ¾ neben dem elterlichen Stamm; Pflichtteile Nachkommen ½ und Ehegatte ½ des gesetzlichen Erbteils, Eltern
ohne Pflichtteil; Nutzniessung für den Ehegatten am Anteil der gemeinsamen Kinder plus höchstens ½ zu Eigentum (Art. 473
ZGB). Konkubinatspartner sind keine gesetzlichen Erben. Die Entwürfe sind keine Rechtsberatung.

Antworten unter `verfuegungen.<typ>.<person bzw. haushalt>` in finanz.yaml (bleibt im Home Assistant).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction as F

HAUSHALT = "haushalt"


@dataclass(frozen=True)
class Option:
    wert: str
    text: str


@dataclass(frozen=True)
class Frage:
    schluessel: str
    text: str
    art: str = "text"                      # text | lang | datum | auswahl | zahl
    optionen: tuple[Option, ...] = ()
    hilfe: str = ""
    vorgabe: str = ""


@dataclass(frozen=True)
class Typ:
    schluessel: str
    titel: str
    je_person: bool
    form: str                              # Formvorschrift in einem Satz
    fragebogen: str                        # zugehöriger Bereich im Nachlass-Fragebogen
    nur_konkubinat: bool = False


TYPEN = (
    Typ("testament", "Testament", True,
        "Eigenhändig: vollständig von Hand schreiben, mit Ort und Datum (Tag, Monat, Jahr) und unterschreiben – sonst "
        "ungültig. Alternative: öffentlich beim Notar.", "testament"),
    Typ("vorsorgeauftrag", "Vorsorgeauftrag", True,
        "Vollständig von Hand schreiben, datieren und unterschreiben – oder öffentlich beurkunden. Hinterlegungsort beim "
        "Zivilstandsamt eintragen lassen (Infostar).", "vorsorgeauftrag"),
    Typ("patientenverfuegung", "Patientenverfügung", True,
        "Schriftlich (auch am Computer), datiert und unterschrieben. Alle zwei bis drei Jahre bestätigen; Kopie beim "
        "Hausarzt hinterlegen, Hinweiskarte ins Portemonnaie.", "patientenverfuegung"),
    Typ("konkubinatsvertrag", "Konkubinatsvertrag", False,
        "Schriftlich, von beiden datiert und unterschrieben; bei Liegenschaften und grösseren Darlehen notariell prüfen "
        "lassen.", "konkubinatsvertrag", nur_konkubinat=True),
    Typ("beguenstigung_3a", "Begünstigung Säule 3a", True,
        "Brief an jede 3a-Stiftung bzw. Versicherung, unterschrieben; Bestätigung verlangen und ablegen.",
        "begünstigung_3a"),
)
NACH_TYP = {t.schluessel: t for t in TYPEN}


def _o(*paare: tuple[str, str]) -> tuple[Option, ...]:
    return tuple(Option(w, t) for w, t in paare)


JA_NEIN = _o(("ja", "ja"), ("nein", "nein"))


# ---------------------------------------------------------------- Lage der Person

@dataclass
class Lage:
    person: str
    partner: str
    verheiratet: bool
    kinder: list[str]                      # eigene Nachkommen (Namen)
    gemeinsame: list[str]                  # gemeinsame Kinder mit dem Partner
    eltern: bool                           # Eltern bzw. Geschwister leben (nur ohne Kinder relevant)
    nachlass: float = 0.0


def lage(k: dict, person: str, antworten: dict | None = None, nachlass: float = 0.0) -> Lage:
    import kinder as ki
    verheiratet = k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet"
    andere = [p["name"] for p in k["personen"] if p["name"] != person]
    partner = andere[0] if andere else ""
    eigene = ki.eigene(k, person)
    gemeinsame = [c["name"] for c in eigene if str(c.get("eltern") or "gemeinsam").lower() in ("gemeinsam", "", "beide")]
    a = antworten or {}
    return Lage(person, partner, verheiratet, [c["name"] for c in eigene], gemeinsame if partner else [],
                (a.get("eltern") or "ja") == "ja", nachlass)


# ---------------------------------------------------------------- Testament: Erbteile und Pflichtteile

def gesetzlich(l: Lage) -> dict[str, F]:
    """Gesetzliche Erbteile (ohne Testament)."""
    erg: dict[str, F] = {}
    if l.verheiratet and l.partner:
        if l.kinder:
            erg[l.partner] = F(1, 2)
            for c in l.kinder:
                erg[c] = F(1, 2) / len(l.kinder)
        elif l.eltern:
            erg[l.partner] = F(3, 4)
            erg["Eltern bzw. Geschwister"] = F(1, 4)
        else:
            erg[l.partner] = F(1)
    elif l.kinder:
        for c in l.kinder:
            erg[c] = F(1) / len(l.kinder)
    else:
        erg["Eltern bzw. Geschwister" if l.eltern else "weitere Verwandte bzw. Kanton"] = F(1)
    return erg


def pflichtteile(l: Lage) -> dict[str, F]:
    """Pflichtteile (Erbrecht seit 2023): Nachkommen und Ehegatte je ½ des gesetzlichen Erbteils, Eltern keinen."""
    g = gesetzlich(l)
    return {e: (q / 2 if (e in l.kinder or (l.verheiratet and e == l.partner)) else F(0)) for e, q in g.items()}


def verfuegbar(l: Lage) -> F:
    return 1 - sum(pflichtteile(l).values(), F(0))


PARTNER_BEZ = {
    "ehefrau": ("meiner Ehefrau", "sie", "ihr"), "ehemann": ("meinem Ehemann", "er", "ihm"),
    "lebenspartnerin": ("meiner Lebenspartnerin", "sie", "ihr"), "lebenspartner": ("meinem Lebenspartner", "er", "ihm"),
    "eingetragene_partnerin": ("meiner eingetragenen Partnerin", "sie", "ihr"),
    "eingetragener_partner": ("meinem eingetragenen Partner", "er", "ihm"),
}


def partner_frage(l: Lage) -> Frage:
    opt = (_o(("ehefrau", "Ehefrau"), ("ehemann", "Ehemann"), ("eingetragene_partnerin", "eingetragene Partnerin"),
              ("eingetragener_partner", "eingetragener Partner")) if l.verheiratet
           else _o(("lebenspartnerin", "Lebenspartnerin"), ("lebenspartner", "Lebenspartner")))
    return Frage("bezeichnung", f"{l.partner or 'Partner'} ist meine bzw. mein …", "auswahl", opt, vorgabe=opt[0].wert)


def _partner(l: Lage, a: dict) -> tuple[str, str, str]:
    """(Dativ mit Bezeichnung, er/sie, ihm/ihr)."""
    s = a.get("bezeichnung") or ("ehefrau" if l.verheiratet else "lebenspartnerin")
    return PARTNER_BEZ.get(s, PARTNER_BEZ["ehefrau"])


TESTAMENT_ZIELE = {
    "partner_max": "Partner bzw. Ehegatte so viel wie möglich (übrige Erben auf den Pflichtteil)",
    "nutzniessung": "Ehegatte: Nutzniessung am Anteil der gemeinsamen Kinder und ½ zu Eigentum (Art. 473 ZGB)",
    "kinder": "Alles den Kindern zu gleichen Teilen (gesetzlich), nur Ergänzungen regeln",
    "eigene": "Eigene Quoten festlegen",
}


def testament_fragen(l: Lage) -> list[Frage]:
    ziele = [Option(w, t) for w, t in TESTAMENT_ZIELE.items()
             if not (w == "nutzniessung" and not (l.verheiratet and l.gemeinsame))
             and not (w == "partner_max" and not l.partner)
             and not (w == "kinder" and not l.kinder)]
    fr = [
        Frage("geburtsdatum", "Geburtsdatum", "datum"),
        Frage("heimatort", "Heimatort (Bürgerort) bzw. Staatsangehörigkeit", hilfe="z. B. «von Liestal BL»"),
        Frage("wohnort", "Wohnadresse", hilfe="Strasse, PLZ Ort"),
        Frage("ziel", "Was soll das Testament vor allem erreichen?", "auswahl", tuple(ziele),
              vorgabe=ziele[0].wert if ziele else "eigene"),
    ]
    if l.partner:
        fr.append(partner_frage(l))
    if not l.kinder:
        fr.append(Frage("eltern", "Leben Eltern oder Geschwister (bzw. deren Nachkommen)?", "auswahl", JA_NEIN, vorgabe="ja",
                        hilfe="Sie erben ohne Testament, haben aber keinen Pflichtteil mehr."))
    fr += [
        Frage("quoten", "Eigene Quoten (nur bei «Eigene Quoten»)", "lang",
              hilfe="eine Zeile pro Erbe: «Name: Prozent», z. B. «Partnerin: 60» – Pflichtteile werden geprüft"),
        Frage("ersatz", "Falls der Partner bzw. Ehegatte vorher stirbt, geht sein Anteil an …", "auswahl",
              _o(("nachkommen", "meine Nachkommen"), ("gesetzlich", "die gesetzlichen Erben"),
                 ("andere", "die unten genannte Person bzw. Organisation"))),
        Frage("ersatz_name", "Ersatzerbe (nur bei «unten genannte Person»)"),
        Frage("liegenschaft", "Liegenschaft", "auswahl",
              _o(("", "keine besondere Regelung"),
                 ("zuweisung", "Partner bzw. Ehegatte übernimmt meinen Anteil unter Anrechnung an seinen Erbteil"),
                 ("wohnrecht", "lebenslanges Wohnrecht für den Partner bzw. Ehegatten"))),
        Frage("vermaechtnisse", "Vermächtnisse (einzelne Gegenstände oder Beträge)", "lang",
              hilfe="eine Zeile pro Vermächtnis: «Was → an wen», z. B. «CHF 5'000 → Patenkind Lea Muster»"),
        Frage("willensvollstrecker", "Willensvollstrecker (Name, Adresse)", hilfe="leer = keiner"),
        Frage("wv_ersatz", "Ersatz-Willensvollstrecker"),
        Frage("widerruf", "Frühere Testamente aufheben?", "auswahl", JA_NEIN, vorgabe="ja"),
    ]
    return fr


def _quoten(text: str) -> dict[str, F]:
    erg: dict[str, F] = {}
    for z in (text or "").splitlines():
        if ":" in z:
            name, _, wert = z.rpartition(":")
            try:
                erg[name.strip()] = F(str(float(wert.strip().rstrip("%").replace(",", ".")))).limit_denominator(1000) / 100
            except ValueError:
                continue
    return erg


@dataclass
class Verteilung:
    zeilen: list[tuple[str, F, F, F]]      # Erbe, gesetzlich, Pflichtteil, laut Entwurf
    nutzniessung: bool = False
    warnungen: list[str] = field(default_factory=list)


def verteilung(l: Lage, a: dict) -> Verteilung:
    g, p = gesetzlich(l), pflichtteile(l)
    ziel = a.get("ziel") or "partner_max"
    neu: dict[str, F] = {}
    nutzn = False
    warn: list[str] = []
    if ziel == "partner_max" and l.partner:
        neu = {e: q for e, q in p.items() if q}
        neu[l.partner] = neu.get(l.partner, F(0)) + verfuegbar(l)
    elif ziel == "nutzniessung" and l.verheiratet and l.gemeinsame:
        neu = {l.partner: F(1, 2)}
        for c in l.kinder:
            neu[c] = F(1, 2) / len(l.kinder)
        nutzn = True
        if set(l.kinder) - set(l.gemeinsame):
            warn.append("Nicht gemeinsame Kinder müssen ihren Pflichtteil frei von Nutzniessung erhalten.")
    elif ziel == "kinder":
        neu = dict(g)
    else:
        neu = _quoten(a.get("quoten", ""))
        if not neu:
            warn.append("Bei «Eigene Quoten» pro Zeile «Name: Prozent» eintragen.")
        summe = sum(neu.values(), F(0))
        if neu and abs(summe - 1) > F(1, 1000):
            warn.append(f"Die Quoten ergeben {float(summe) * 100:.1f} % statt 100 %.")
    for e, q in p.items():
        if q and neu.get(e, F(0)) + F(1, 100000) < q:
            warn.append(f"Pflichtteil verletzt: {e} muss mindestens {float(q) * 100:.1f} % erhalten "
                        f"(Entwurf {float(neu.get(e, F(0))) * 100:.1f} %) – anfechtbar.")
    if not l.verheiratet and l.partner and neu.get(l.partner):
        warn.append("Konkubinat: Der Partner bezahlt je nach Kanton Erbschaftssteuer – siehe Nachlass.")
    alle = list(dict.fromkeys([*g, *neu]))
    return Verteilung([(e, g.get(e, F(0)), p.get(e, F(0)), neu.get(e, F(0))) for e in alle], nutzn, warn)


def _pz(q: F) -> str:
    v = float(q) * 100
    return f"{v:.0f} %" if abs(v - round(v)) < 0.05 else f"{v:.1f} %"


def _bruch(q: F) -> str:
    return {F(1): "den ganzen Nachlass", F(1, 2): "die Hälfte", F(1, 4): "einen Viertel", F(3, 4): "drei Viertel",
            F(5, 8): "fünf Achtel", F(3, 8): "drei Achtel", F(1, 8): "einen Achtel"}.get(q, f"{_pz(q)}")


def _zeilen(text: str, trenner: str = "→") -> list[tuple[str, str]]:
    erg = []
    for z in (text or "").splitlines():
        if trenner in z:
            a, _, b = z.partition(trenner)
            erg.append((a.strip(), b.strip()))
        elif z.strip():
            erg.append((z.strip(), ""))
    return erg


def _kopf(name: str, a: dict, titel: str) -> list[str]:
    zeilen = [titel, ""]
    angaben = [f"Ich, {name}"]
    if a.get("geburtsdatum"):
        angaben.append(f"geboren am {_datum(a['geburtsdatum'])}")
    if a.get("heimatort"):
        angaben.append(f"{a['heimatort']}")
    if a.get("wohnort"):
        angaben.append(f"wohnhaft {a['wohnort']}")
    zeilen.append(", ".join(angaben) + ",")
    return zeilen


def _datum(iso: str) -> str:
    try:
        j, m, t = iso.split("-")
        return f"{int(t)}.{int(m)}.{j}"
    except ValueError:
        return iso


def testament_text(l: Lage, a: dict) -> str:
    v = verteilung(l, a)
    z = _kopf(l.person, a, "Testament")
    z += ["verfüge letztwillig, was folgt:", ""]
    n = 1
    if (a.get("widerruf") or "ja") == "ja":
        z.append(f"{n}. Ich hebe alle früheren letztwilligen Verfügungen auf.")
        n += 1
    ziel = a.get("ziel") or "partner_max"
    bez, er, ihm = _partner(l, a)
    if ziel == "partner_max" and l.partner:
        pfl = [e for e, _, p_, _ in v.zeilen if p_ and e != l.partner]
        if pfl:
            z.append(f"{n}. Ich setze {', '.join(pfl)} auf den Pflichtteil.")
            n += 1
        gesamt = dict((e, q) for e, _, _, q in v.zeilen)[l.partner]
        z.append(f"{n}. Die verfügbare Quote ({_bruch(verfuegbar(l))} meines Nachlasses) wende ich {bez} {l.partner} zu."
                 + (f" {er.capitalize()} erhält damit insgesamt {_bruch(gesamt)} meines Nachlasses."
                    if gesamt != verfuegbar(l) else ""))
        n += 1
    elif ziel == "nutzniessung":
        z.append(f"{n}. Ich wende {bez} {l.partner} die Hälfte meines Nachlasses zu Eigentum und an dem Teil, der unseren "
                 f"gemeinsamen Nachkommen ({', '.join(l.gemeinsame)}) zufällt, die lebenslängliche Nutzniessung zu "
                 "(Art. 473 ZGB).")
        n += 1
    elif ziel == "kinder":
        z.append(f"{n}. Mein Nachlass geht nach der gesetzlichen Erbfolge an meine Nachkommen "
                 f"({', '.join(l.kinder)}) zu gleichen Teilen.")
        n += 1
    else:
        for e, _, _, q in v.zeilen:
            if q:
                z.append(f"{n}. {e} erhält {_pz(q)} meines Nachlasses.")
                n += 1
    if l.partner and ziel in ("partner_max", "nutzniessung", "eigene"):
        ersatz = a.get("ersatz") or "nachkommen"
        an = {"nachkommen": "meinen Nachkommen", "gesetzlich": "meinen gesetzlichen Erben"}.get(
            ersatz, a.get("ersatz_name") or "der von mir bestimmten Person")
        z.append(f"{n}. Stirbt {l.partner} vor mir oder gleichzeitig mit mir, fällt der {ihm} zugedachte Anteil an {an}.")
        n += 1
    if a.get("liegenschaft") == "zuweisung" and l.partner:
        z.append(f"{n}. {l.partner} ist berechtigt, meinen Anteil an der Liegenschaft unter Anrechnung an den Erbteil zum "
                 "Verkehrswert im Zeitpunkt der Teilung zu übernehmen (Teilungsvorschrift).")
        n += 1
    elif a.get("liegenschaft") == "wohnrecht" and l.partner:
        z.append(f"{n}. Ich vermache {l.partner} das unentgeltliche, lebenslange Wohnrecht an unserer Liegenschaft.")
        n += 1
    for was, wer in _zeilen(a.get("vermaechtnisse", "")):
        z.append(f"{n}. Ich vermache {was}" + (f" an {wer}." if wer else "."))
        n += 1
    if a.get("willensvollstrecker"):
        z.append(f"{n}. Als Willensvollstrecker setze ich {a['willensvollstrecker']} ein"
                 + (f", ersatzweise {a['wv_ersatz']}." if a.get("wv_ersatz") else "."))
        n += 1
    z += ["", "[Ort], [Tag. Monat Jahr]", "", "[Unterschrift]"]
    return "\n".join(z)


# ---------------------------------------------------------------- Vorsorgeauftrag

def vorsorgeauftrag_fragen(l: Lage) -> list[Frage]:
    return [
        Frage("geburtsdatum", "Geburtsdatum", "datum"),
        Frage("heimatort", "Heimatort (Bürgerort) bzw. Staatsangehörigkeit"),
        Frage("wohnort", "Wohnadresse"),
        Frage("person", "Beauftragte Person (Name, Geburtsdatum, Adresse)", vorgabe=l.partner),
        Frage("ersatz", "Ersatzperson, falls die beauftragte Person nicht kann oder will"),
        Frage("bereiche", "Für welche Bereiche?", "auswahl",
              _o(("alle", "Personensorge, Vermögenssorge und Rechtsverkehr"),
                 ("vermoegen", "nur Vermögenssorge und Rechtsverkehr"), ("person", "nur Personensorge")), vorgabe="alle"),
        Frage("liegenschaft", "Darf die beauftragte Person die Liegenschaft verkaufen oder belasten?", "auswahl",
              _o(("ja", "ja"), ("nein", "nein, nur verwalten"), ("kesb", "nur mit Zustimmung der KESB"))),
        Frage("post", "Post öffnen und digitale Konten verwalten?", "auswahl", JA_NEIN, vorgabe="ja"),
        Frage("entschaedigung", "Entschädigung", "auswahl",
              _o(("spesen", "nur Ersatz der Auslagen"), ("keine", "keine"), ("angemessen", "angemessene Entschädigung")),
              vorgabe="spesen"),
        Frage("anweisungen", "Weitere Anweisungen", "lang",
              hilfe="z. B. Wohnen zu Hause solange möglich, Unterstützung der Kinder, Anlagegrundsätze"),
    ]


def vorsorgeauftrag_text(l: Lage, a: dict) -> str:
    z = _kopf(l.person, a, "Vorsorgeauftrag")
    z += ["erteile für den Fall meiner Urteilsunfähigkeit folgenden Vorsorgeauftrag (Art. 360 ff. ZGB):", ""]
    bereiche = {"alle": "der Personensorge, der Vermögenssorge und der Vertretung im Rechtsverkehr",
                "vermoegen": "der Vermögenssorge und der Vertretung im Rechtsverkehr",
                "person": "der Personensorge"}[a.get("bereiche") or "alle"]
    z.append(f"1. Ich beauftrage {a.get('person') or '[Name, Geburtsdatum, Adresse]'} mit {bereiche}.")
    n = 2
    if a.get("ersatz"):
        z.append(f"{n}. Kann oder will die beauftragte Person den Auftrag nicht übernehmen oder kündigt sie ihn, "
                 f"beauftrage ich ersatzweise {a['ersatz']}.")
        n += 1
    if (a.get("bereiche") or "alle") != "person":
        li = a.get("liegenschaft")
        if li == "ja":
            z.append(f"{n}. Die beauftragte Person darf Grundstücke verkaufen, belasten und darüber verfügen.")
            n += 1
        elif li == "nein":
            z.append(f"{n}. Grundstücke darf die beauftragte Person verwalten, aber weder verkaufen noch belasten.")
            n += 1
        elif li == "kesb":
            z.append(f"{n}. Für Verkauf oder Belastung von Grundstücken braucht die beauftragte Person die Zustimmung der "
                     "Erwachsenenschutzbehörde.")
            n += 1
    if (a.get("post") or "ja") == "ja":
        z.append(f"{n}. Die beauftragte Person darf meine Post öffnen und meine digitalen Konten verwalten.")
        n += 1
    entsch = {"spesen": "Die beauftragte Person erhält Ersatz ihrer Auslagen, aber keine Entschädigung.",
              "keine": "Die beauftragte Person erhält keine Entschädigung.",
              "angemessen": "Die beauftragte Person erhält eine angemessene Entschädigung und Ersatz ihrer Auslagen."}
    z.append(f"{n}. {entsch[a.get('entschaedigung') or 'spesen']}")
    n += 1
    if a.get("anweisungen"):
        z.append(f"{n}. {a['anweisungen'].strip()}")
    z += ["", "[Ort], [Tag. Monat Jahr]", "", "[Unterschrift]"]
    return "\n".join(z)


# ---------------------------------------------------------------- Patientenverfügung

def patientenverfuegung_fragen(l: Lage) -> list[Frage]:
    return [
        Frage("geburtsdatum", "Geburtsdatum", "datum"),
        Frage("wohnort", "Wohnadresse"),
        Frage("vertretung", "Vertretungsperson für medizinische Entscheide", vorgabe=l.partner),
        Frage("ersatz", "Ersatz-Vertretungsperson"),
        Frage("ziel", "Wenn keine Aussicht auf Rückkehr in ein bewusstes Leben besteht:", "auswahl",
              _o(("lindern", "keine lebensverlängernden Massnahmen, nur Linderung von Schmerzen und Angst"),
                 ("befristet", "Massnahmen nur befristet, solange Aussicht auf Besserung besteht"),
                 ("alles", "alle medizinisch möglichen Massnahmen")), vorgabe="lindern"),
        Frage("reanimation", "Wiederbelebung bei Herz-Kreislauf-Stillstand", "auswahl",
              _o(("ja", "ja"), ("nein", "nein"), ("situativ", "nur wenn gute Aussicht auf Erholung"))),
        Frage("ernaehrung", "Künstliche Ernährung und Beatmung in aussichtsloser Lage", "auswahl",
              _o(("nein", "nein"), ("ja", "ja"), ("befristet", "befristet"))),
        Frage("schmerz", "Schmerz- und Symptombehandlung auch wenn sie das Leben verkürzen kann", "auswahl", JA_NEIN,
              vorgabe="ja"),
        Frage("organspende", "Organspende", "auswahl",
              _o(("ja", "ja, alle Organe und Gewebe"), ("nein", "nein"), ("teilweise", "nur bestimmte (unten nennen)"),
                 ("angehoerige", "meine Vertretungsperson entscheidet"))),
        Frage("sterbeort", "Wo möchte ich sterben?", "auswahl",
              _o(("", "keine Angabe"), ("zuhause", "wenn möglich zu Hause"), ("hospiz", "im Hospiz bzw. Pflegeheim"),
                 ("spital", "im Spital"))),
        Frage("seelsorge", "Seelsorgerische Begleitung", "auswahl",
              _o(("", "keine Angabe"), ("ja", "ja"), ("nein", "nein"))),
        Frage("wuensche", "Weitere Wünsche und Werte", "lang", hilfe="was mir wichtig ist, Musik, Besuche, Ängste"),
    ]


def patientenverfuegung_text(l: Lage, a: dict) -> str:
    z = _kopf(l.person, a, "Patientenverfügung")
    z += ["lege für den Fall meiner Urteilsunfähigkeit fest (Art. 370 ff. ZGB):", ""]
    n = 1
    z.append(f"{n}. Als Vertretungsperson in medizinischen Fragen bestimme ich {a.get('vertretung') or '[Name, Telefon]'}"
             + (f", ersatzweise {a['ersatz']}." if a.get("ersatz") else "."))
    n += 1
    ziel = {"lindern": "Ist keine Rückkehr in ein bewusstes, selbstbestimmtes Leben zu erwarten, verzichte ich auf "
                       "lebensverlängernde Massnahmen. Ich wünsche Linderung von Schmerzen, Atemnot und Angst.",
            "befristet": "Lebenserhaltende Massnahmen sind nur befristet anzuwenden, solange eine begründete Aussicht auf "
                         "Besserung besteht; danach sind sie abzubrechen.",
            "alles": "Ich wünsche alle medizinisch möglichen Massnahmen zur Erhaltung meines Lebens."}
    z.append(f"{n}. {ziel[a.get('ziel') or 'lindern']}")
    n += 1
    rea = {"ja": "Bei einem Herz-Kreislauf-Stillstand wünsche ich eine Wiederbelebung.",
           "nein": "Bei einem Herz-Kreislauf-Stillstand verzichte ich auf eine Wiederbelebung.",
           "situativ": "Eine Wiederbelebung wünsche ich nur, wenn gute Aussicht auf Erholung besteht."}
    if a.get("reanimation") in rea:
        z.append(f"{n}. {rea[a['reanimation']]}")
        n += 1
    ern = {"nein": "In aussichtsloser Lage lehne ich künstliche Ernährung und künstliche Beatmung ab.",
           "ja": "Künstliche Ernährung und Beatmung sind auch in aussichtsloser Lage anzuwenden.",
           "befristet": "Künstliche Ernährung und Beatmung nur befristet, solange Aussicht auf Besserung besteht."}
    if a.get("ernaehrung") in ern:
        z.append(f"{n}. {ern[a['ernaehrung']]}")
        n += 1
    if (a.get("schmerz") or "ja") == "ja":
        z.append(f"{n}. Schmerzen und Beschwerden sollen wirksam behandelt werden, auch wenn dies mein Leben verkürzen kann.")
        n += 1
    org = {"ja": "Ich stimme der Entnahme von Organen und Geweben zur Transplantation zu.",
           "nein": "Ich lehne eine Organ- und Gewebespende ab.",
           "teilweise": "Ich stimme der Spende nur folgender Organe bzw. Gewebe zu: [aufzählen].",
           "angehoerige": "Über eine Organspende entscheidet meine Vertretungsperson."}
    if a.get("organspende") in org:
        z.append(f"{n}. {org[a['organspende']]}")
        n += 1
    ort = {"zuhause": "Wenn möglich möchte ich zu Hause sterben.", "hospiz": "Ich möchte in einem Hospiz bzw. Pflegeheim "
           "begleitet werden.", "spital": "Ich möchte im Spital betreut werden."}
    if a.get("sterbeort") in ort:
        z.append(f"{n}. {ort[a['sterbeort']]}")
        n += 1
    if a.get("seelsorge") in ("ja", "nein"):
        z.append(f"{n}. " + ("Ich wünsche seelsorgerische Begleitung." if a["seelsorge"] == "ja"
                             else "Ich wünsche keine seelsorgerische Begleitung."))
        n += 1
    if a.get("wuensche"):
        z.append(f"{n}. {a['wuensche'].strip()}")
    z += ["", "[Ort], [Tag. Monat Jahr]", "", "[Unterschrift]", "",
          "Bestätigt am: ____________  Unterschrift: ____________"]
    return "\n".join(z)


# ---------------------------------------------------------------- Konkubinatsvertrag

def konkubinatsvertrag_fragen(k: dict) -> list[Frage]:
    return [
        Frage("adresse", "Gemeinsame Wohnadresse"),
        Frage("seit", "Zusammen seit", "datum"),
        Frage("hausrat", "Hausrat und Fahrzeuge", "auswahl",
              _o(("inventar", "gehört laut Inventarliste (Beilage) der jeweiligen Person, Rest je zur Hälfte"),
                 ("haelfte", "gehört beiden je zur Hälfte"), ("kaeufer", "gehört, wer es bezahlt hat (Belege)")),
              vorgabe="inventar"),
        Frage("kosten", "Haushaltskosten", "auswahl",
              _o(("haelfte", "je zur Hälfte"), ("einkommen", "im Verhältnis der Nettoeinkommen"),
                 ("eigene", "eigene Regel (unten)")), vorgabe="haelfte"),
        Frage("kosten_regel", "Eigene Regel für die Haushaltskosten", "lang"),
        Frage("liegenschaft", "Liegenschaft: Eigentum und Beiträge", "lang",
              hilfe="Miteigentumsanteile laut Grundbuch, ungleiche Eigenmittel als Darlehen oder Ausgleich, Hypothek"),
        Frage("darlehen", "Darlehen zwischen euch", "lang", hilfe="wer, wie viel, Zins, Rückzahlung bei Trennung"),
        Frage("betreuung", "Ausgleich für Kinderbetreuung bzw. reduziertes Pensum", "lang",
              hilfe="z. B. Einzahlung in die Säule 3a oder Ausgleich der Vorsorgelücke"),
        Frage("trennung", "Bei Trennung: Liegenschaft bzw. Wohnung", "auswahl",
              _o(("uebernahme", "eine Person kann die Liegenschaft zum Verkehrswert übernehmen (unten wer)"),
                 ("verkauf", "Verkauf und Teilung nach Anteilen"), ("miete", "Mietwohnung: wer bleibt (unten)"))),
        Frage("trennung_wer", "Wer hat das Übernahme- bzw. Bleiberecht?"),
        Frage("tod", "Gegenseitige Absicherung im Todesfall", "lang",
              vorgabe="Wir setzen uns gegenseitig in Testamenten ein und begünstigen uns bei Pensionskasse, Säule 3a und "
                      "Lebensversicherungen."),
    ]


def konkubinatsvertrag_text(k: dict, a: dict) -> str:
    namen = [p["name"] for p in k["personen"]][:2]
    z = ["Konkubinatsvertrag", "", f"zwischen {namen[0]} und {namen[1] if len(namen) > 1 else '[Name]'}"
         + (f", wohnhaft {a['adresse']}" if a.get("adresse") else ""), ""]
    n = 1
    if a.get("seit"):
        z.append(f"{n}. Wir leben seit {_datum(a['seit'])} in einem gemeinsamen Haushalt.")
        n += 1
    haus = {"inventar": "Hausrat und Fahrzeuge gehören der Person, die in der beiliegenden Inventarliste genannt ist; "
                        "was nicht aufgeführt ist, gehört uns je zur Hälfte.",
            "haelfte": "Hausrat und Fahrzeuge gehören uns je zur Hälfte.",
            "kaeufer": "Hausrat und Fahrzeuge gehören der Person, die sie bezahlt hat; im Zweifel je zur Hälfte."}
    z.append(f"{n}. {haus[a.get('hausrat') or 'inventar']}")
    n += 1
    kosten = {"haelfte": "Die Kosten des gemeinsamen Haushalts tragen wir je zur Hälfte.",
              "einkommen": "Die Kosten des gemeinsamen Haushalts tragen wir im Verhältnis unserer Nettoeinkommen.",
              "eigene": (a.get("kosten_regel") or "[Regel für die Haushaltskosten]").strip()}
    z.append(f"{n}. {kosten[a.get('kosten') or 'haelfte']}")
    n += 1
    for schl, titel in (("liegenschaft", "Liegenschaft"), ("darlehen", "Darlehen"), ("betreuung", "Kinderbetreuung")):
        if a.get(schl):
            z.append(f"{n}. {titel}: {a[schl].strip()}")
            n += 1
    tr = a.get("trennung")
    if tr == "uebernahme":
        z.append(f"{n}. Bei einer Trennung kann {a.get('trennung_wer') or '[Name]'} die Liegenschaft zum Verkehrswert "
                 "übernehmen; die andere Person wird nach ihrem Anteil, ihren Beiträgen und offenen Darlehen ausbezahlt.")
        n += 1
    elif tr == "verkauf":
        z.append(f"{n}. Bei einer Trennung wird die Liegenschaft verkauft und der Erlös nach den Eigentumsanteilen und "
                 "offenen Darlehen geteilt.")
        n += 1
    elif tr == "miete":
        z.append(f"{n}. Bei einer Trennung bleibt {a.get('trennung_wer') or '[Name]'} in der Wohnung; die andere Person zieht "
                 "innert drei Monaten aus.")
        n += 1
    if a.get("tod"):
        z.append(f"{n}. {a['tod'].strip()}")
        n += 1
    z.append(f"{n}. Änderungen dieses Vertrags bedürfen der Schriftform.")
    z += ["", "[Ort], [Tag. Monat Jahr]", "", f"[Unterschrift {namen[0]}]",
          "", f"[Unterschrift {namen[1] if len(namen) > 1 else ''}]"]
    return "\n".join(z)


# ---------------------------------------------------------------- Begünstigung 3a

def beguenstigung_fragen(l: Lage) -> list[Frage]:
    return [
        Frage("stiftung", "3a-Stiftung bzw. Versicherung (Name, Adresse)"),
        Frage("konto", "Konto- bzw. Policennummer"),
        Frage("geburtsdatum", "Mein Geburtsdatum", "datum"),
        Frage("wohnort", "Meine Adresse"),
        Frage("beguenstigt", "Begünstigte Person (Name, Geburtsdatum)", vorgabe=l.partner),
        Frage("grund", "Voraussetzung für die Begünstigung", "auswahl",
              _o(("ehe", "Ehegatte bzw. eingetragener Partner (gesetzlich an erster Stelle)"),
                 ("fuenf", "Lebensgemeinschaft seit mindestens 5 Jahren ohne Unterbruch"),
                 ("kinder", "Unterhalt gemeinsamer Kinder"),
                 ("unterstuetzung", "erhebliche Unterstützung durch mich")),
              vorgabe="ehe" if l.verheiratet else "fuenf"),
        Frage("seit", "Zusammenleben seit", "datum"),
        Frage("anteil", "Anteil der begünstigten Person in %", "zahl", vorgabe="100",
              hilfe="Rest an die Nachkommen bzw. nach Gesetz"),
    ]


def beguenstigung_text(l: Lage, a: dict) -> str:
    z = [f"{l.person}" + (f", {a['wohnort']}" if a.get("wohnort") else ""), "",
         f"An: {a.get('stiftung') or '[3a-Stiftung bzw. Versicherung, Adresse]'}", "",
         f"Begünstigung im Todesfall – Vorsorgekonto/-police {a.get('konto') or '[Nummer]'}", "",
         "Sehr geehrte Damen und Herren", ""]
    anteil = a.get("anteil") or "100"
    grund = a.get("grund") or ("ehe" if l.verheiratet else "fuenf")
    wer = a.get("beguenstigt") or "[Name, Geburtsdatum]"
    if grund == "ehe":
        z.append(f"Im Todesfall soll {wer} als Ehegatte bzw. eingetragener Partner {anteil} % des Vorsorgeguthabens erhalten.")
    else:
        warum = {"fuenf": f"mit der ich seit {_datum(a['seit']) if a.get('seit') else '[Datum]'} ununterbrochen in einer "
                          "Lebensgemeinschaft lebe (mindestens fünf Jahre)",
                 "kinder": "die für den Unterhalt eines oder mehrerer gemeinsamer Kinder aufkommen muss",
                 "unterstuetzung": "die ich in erheblichem Masse unterstütze"}[grund]
        z.append(f"Gestützt auf Art. 2 Abs. 1 lit. b Ziff. 2 BVV 3 begünstige ich im Todesfall {wer}, {warum}, "
                 f"zu {anteil} % des Vorsorgeguthabens.")
    if str(anteil).strip() not in ("100", "100.0"):
        z.append("Der übrige Teil geht an die Begünstigten nach der gesetzlichen Reihenfolge.")
    z += ["", "Bitte bestätigen Sie mir den Eingang dieser Begünstigung schriftlich.", "", "Freundliche Grüsse", "",
          "[Ort], [Tag. Monat Jahr]", "", "[Unterschrift]"]
    if l.kinder and grund != "ehe":
        z += ["", "Hinweis: Nachkommen stehen in derselben Gruppe – ohne Quote teilen sie mit der begünstigten Person."]
    return "\n".join(z)


# ---------------------------------------------------------------- gemeinsame Schnittstelle

def antworten(k: dict, typ: str, wer: str) -> dict:
    return dict((((k.get("verfuegungen") or {}).get(typ) or {}).get(wer)) or {})


def fragen(k: dict, typ: str, wer: str) -> list[Frage]:
    if typ == "konkubinatsvertrag":
        return konkubinatsvertrag_fragen(k)
    l = lage(k, wer, antworten(k, typ, wer))
    return {"testament": testament_fragen, "vorsorgeauftrag": vorsorgeauftrag_fragen,
            "patientenverfuegung": patientenverfuegung_fragen, "beguenstigung_3a": beguenstigung_fragen}[typ](l)


def mit_vorgaben(k: dict, typ: str, wer: str) -> dict:
    """Antworten, ergänzt um Vorgaben (z. B. Partner als Vertretung, Geburtsdatum aus den Einstellungen)."""
    a = antworten(k, typ, wer)
    person = next((p for p in k["personen"] if p["name"] == wer), {})
    for f in fragen(k, typ, wer):
        if f.schluessel not in a:
            if f.schluessel == "geburtsdatum" and person.get("geburtsdatum"):
                a[f.schluessel] = str(person["geburtsdatum"])
            elif f.vorgabe:
                a[f.schluessel] = f.vorgabe
    return a


def text(k: dict, typ: str, wer: str) -> str:
    a = mit_vorgaben(k, typ, wer)
    if typ == "konkubinatsvertrag":
        return konkubinatsvertrag_text(k, a)
    l = lage(k, wer, a)
    return {"testament": testament_text, "vorsorgeauftrag": vorsorgeauftrag_text,
            "patientenverfuegung": patientenverfuegung_text, "beguenstigung_3a": beguenstigung_text}[typ](l, a)


def speichern(k: dict, typ: str, wer: str, form: dict) -> None:
    werte = {f.schluessel: str(form.get(f.schluessel, "")).strip()[:3000] for f in fragen(k, typ, wer)}
    k.setdefault("verfuegungen", {}).setdefault(typ, {})[wer] = werte


def typen(k: dict) -> list[Typ]:
    konkubinat = k["haushalt"].get("zivilstand", "verheiratet") != "verheiratet" and len(k["personen"]) > 1
    return [t for t in TYPEN if konkubinat or not t.nur_konkubinat]


def spalten(k: dict, t: Typ) -> list[str]:
    return [p["name"] for p in k["personen"]] if t.je_person else [HAUSHALT]


def begonnen(k: dict, t: Typ, wer: str) -> bool:
    return bool(antworten(k, t.schluessel, wer))
