"""Sparen und Anlegen: Reihenfolge für den nächsten Franken, Sparplan pro Monat, Soll-Ist der Aufteilung und Produktarten.

Reihenfolge (üblich in der Schweiz, mit den eigenen Zahlen):
1. Notreserve auffüllen   2. teure Schulden tilgen   3. Säule 3a ausschöpfen   4. zweckgebunden sparen (Amortisation,
Lebensziele)   5. PK-Einkauf, wenn er sich lohnt   6. Rest langfristig breit gestreut anlegen.

Der Sparplan verteilt das Sparpotenzial (`personen[].sparen_monat`) in dieser Reihenfolge: Lücken in Reserve und
Schulden über 12 Monate, 3a mit dem Maximum pro erwerbstätige Person, Amortisation bis zur Fälligkeit, Lebensziele bis
zum Zieljahr, der Rest langfristig. Keine Produktempfehlungen – nur Produktarten und worauf zu achten ist; Renditen und
Steuerwirkung sind Annahmen bzw. Schätzungen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

ERLEDIGT, OFFEN, TEILWEISE, ENTFAELLT = "erledigt", "offen", "teilweise", "entfällt"
PK_GRENZSATZ = 25          # ab diesem Grenzsteuersatz (%) lohnt sich ein PK-Einkauf meist
TER_HOCH = 0.5             # % pro Jahr: Fonds darüber gelten als teuer
CH_AKTIEN = (20, 40)       # üblicher Bereich Schweizer Aktien am Aktienteil (%)


@dataclass
class Schritt:
    nr: int
    titel: str
    status: str
    text: str
    einmalig: float = 0.0          # fehlt bzw. ist jetzt möglich (CHF)
    monat: float = 0.0             # Anteil am Sparplan pro Monat
    bedarf_monat: float = 0.0      # was der Schritt pro Monat bräuchte
    nutzen: str = ""
    seite: str = ""
    jetzt: float = 0.0             # vom Geld, das heute über Reserve und Zweck auf Konten liegt


@dataclass
class Klasse:
    name: str
    ist: float
    soll: float

    @property
    def diff(self) -> float:
        return self.soll - self.ist


@dataclass
class Produktart:
    topf: str
    art: str
    achten: str


@dataclass
class Plan:
    schritte: list[Schritt]
    sparpotenzial: float
    ungedeckt: float               # pro Monat, den die Schritte 1–4 bräuchten, aber das Sparpotenzial nicht hergibt
    ueberschuss: float             # heute auf Konten über Notreserve und zweckgebundenem Geld
    klassen: list[Klasse]
    naechster_kauf: str
    produktarten: list[Produktart]
    teure_fonds: list[tuple[str, float, float]] = field(default_factory=list)   # (Name, TER, Wert)
    hinweise: list[str] = field(default_factory=list)


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")


def rechnen(k: dict, db, heute: date | None = None) -> Plan:
    import anlage as an
    import berater as br
    import finanzplan as fp
    import steuern as st
    import vermoegen as vm

    heute = heute or date.today()
    kz = k["kennzahlen"]
    c = an.pruefen(k, db, heute)
    cfg = an.konfiguration(k)
    reserve = next((t.betrag for t in c.toepfe if t.name == "Notreserve"), 0.0)
    spar = sum(float(p.get("sparen_monat", 0) or 0) for p in k["personen"])
    rest = spar
    schritte: list[Schritt] = []

    def nehmen(bedarf: float) -> float:
        nonlocal rest
        x = max(0.0, min(rest, bedarf))
        rest -= x
        return round(x)

    # Geld, das heute über Reserve und Zweck auf Konten liegt, geht in derselben Reihenfolge zuerst
    zweck_heute = sum(t.betrag for t in c.toepfe if t.name.startswith(("Amortisation", "Geplante")))
    frei = max(0.0, c.liquide - reserve - zweck_heute)
    ueberschuss = frei

    def sofort(betrag: float) -> float:
        nonlocal frei
        x = max(0.0, min(frei, betrag))
        frei -= x
        return round(x)

    # 1. Notreserve
    luecke = max(0.0, reserve - c.liquide)
    b = luecke / 12
    schritte.append(Schritt(1, "Notreserve", ERLEDIGT if not luecke else OFFEN,
                            f"Ziel CHF {_chf(reserve)} auf dem Konto, vorhanden CHF {_chf(c.liquide)}"
                            + (f" – es fehlen CHF {_chf(luecke)}, über 12 Monate auffüllen." if luecke else "."),
                            luecke, nehmen(b), b, "Schutz vor Notverkäufen und Konsumkrediten", "vermoegen"))

    # 2. teure Schulden (Konsumkredit, Leasing, Kreditkarte)
    schuld = sum(abs(x["wert"]) for x in vm.konten(db) if x["art"] == "kredit" and not x.get("aufgeloest"))
    j2 = sofort(schuld)
    b = (schuld - j2) / 12
    schritte.append(Schritt(2, "Teure Schulden tilgen", ENTFAELLT if schuld <= 0 else OFFEN,
                            "Keine Kredite erfasst." if schuld <= 0 else
                            f"Kredite CHF {_chf(schuld)} – Zinsen von 5–10 % schlägt keine Anlage; zuerst tilgen"
                            + (" (aus dem Konto möglich)." if j2 >= schuld else "."),
                            schuld, nehmen(b), b, "sicherer «Ertrag» in Höhe des Kreditzinses", "vermoegen", j2))

    # 3. Säule 3a
    erwerb = [p for p in k["personen"] if float(p.get("lohn_brutto", 0) or 0) > 0]
    teile, offen, ersparnis, bedarf3a = [], 0.0, 0, 0.0
    for p in erwerb:
        maxi = float(kz["saeule3a_max"])
        if not p.get("pk", {}).get("versichert", True) and kz.get("saeule3a_max_ohne_pk"):
            maxi = min(float(kz["saeule3a_max_ohne_pk"]), 0.2 * float(p.get("lohn_brutto", 0) or 0))
        beitrag = float(p["saeule3a"].get("beitrag_jahr", 0) or 0)
        o = max(0.0, maxi - beitrag)
        offen += o
        bedarf3a += maxi / 12
        if o > 50:
            try:
                ersparnis += st.ersparnis_abzug(k, o, p["name"])["total"]
            except Exception:  # noqa: BLE001
                pass
            teile.append(f"{p['name']} CHF {_chf(o)} offen")
        else:
            teile.append(f"{p['name']} ausgeschöpft")
    if erwerb:
        status = ERLEDIGT if offen <= 50 else (TEILWEISE if offen < len(erwerb) * float(kz["saeule3a_max"]) else OFFEN)
        nutzen = (f"Steuerersparnis rund CHF {_chf(ersparnis)} pro Jahr auf dem offenen Betrag" if ersparnis else
                  "Steuerabzug jedes Jahr; das Maximum lässt sich nicht nachholen (ausser Einkauf ab 2025er Lücken)")
        j3 = sofort(offen)
        schritte.append(Schritt(3, "Säule 3a ausschöpfen", status,
                                "; ".join(teile) + f" (Maximum CHF {_chf(float(kz['saeule3a_max']))} pro Person). "
                                "Einzahlung muss bis Ende Dezember gutgeschrieben sein; ab nächstem Jahr am einfachsten "
                                "monatlich per Dauerauftrag.",
                                offen, nehmen(bedarf3a), bedarf3a, nutzen, "vorsorge", j3))
    else:
        schritte.append(Schritt(3, "Säule 3a ausschöpfen", ENTFAELLT, "Ohne Erwerbseinkommen keine Einzahlung möglich.",
                                seite="vorsorge"))

    # 4. zweckgebunden: Amortisation und Lebensziele
    a = br.amortisation(k, db, heute) if (k.get("wohnen") or {}).get("aktiv") else None
    zweck_teile, zweck_luecke, bedarf4 = [], 0.0, 0.0
    j4 = 0.0
    if a and a.ziel:
        fehl = max(0.0, a.ziel - a.verfuegbar)
        if fehl > 0 and a.monate > 0:
            x = sofort(fehl)
            j4 += x
            bedarf4 += (fehl - x) / a.monate
            zweck_luecke += fehl
            zweck_teile.append(f"Amortisation bis {a.faellig:%m.%Y}: CHF {_chf(fehl)} fehlen")
        else:
            zweck_teile.append(f"Amortisation bis {a.faellig:%m.%Y} gedeckt")
    try:
        ziele = fp.ziele_liste(k, heute.year)
    except Exception:  # noqa: BLE001
        ziele = []
    for z in ziele:
        monate = max(1, (int(z["jahr"]) - heute.year) * 12 + 12 - heute.month)
        if int(z["jahr"]) >= heute.year and float(z.get("betrag") or 0) > 0:
            x = sofort(float(z["betrag"]))
            j4 += x
            bedarf4 += (float(z["betrag"]) - x) / monate
            zweck_luecke += float(z["betrag"])
            zweck_teile.append(f"{z.get('name') or 'Ziel'} {z['jahr']}: CHF {_chf(float(z['betrag']))}"
                               + (" (vom Konto zurückgelegt)" if x >= float(z["betrag"]) else
                                  f", CHF {_chf((float(z['betrag']) - x) / monate)} pro Monat"))
    schritte.append(Schritt(4, "Zweckgebunden sparen", ENTFAELLT if not zweck_teile else
                            (ERLEDIGT if not bedarf4 else OFFEN),
                            "; ".join(zweck_teile) + ". Kurzer Horizont – sicher anlegen, auf das Datum terminiert."
                            if zweck_teile else "Keine Amortisation und keine Lebensziele erfasst (Finanzplan → Ziele).",
                            zweck_luecke, nehmen(bedarf4), bedarf4, "Geld ist da, wenn es gebraucht wird", "finanzplan",
                            round(j4)))

    # 5. PK-Einkauf
    try:
        grenz = float(st.steuern_heute(k)["grenz_total"])
    except Exception:  # noqa: BLE001
        grenz = 0.0
    pot = [(p["name"], float(p["pk"].get("einkauf_potenzial", 0) or 0)) for p in k["personen"]
           if float(p["pk"].get("einkauf_potenzial", 0) or 0) > 0]
    geplant = [e for p in k["personen"] for e in (p["pk"].get("einkauf_geplant") or [])]
    if not pot:
        schritte.append(Schritt(5, "PK-Einkauf", ENTFAELLT, "Kein Einkaufspotenzial erfasst (PK-Ausweis).", seite="steuern"))
    else:
        bsp = min(10_000.0, min(v for _, v in pot))
        try:
            e10 = st.ersparnis_abzug(k, bsp, pot[0][0])["total"]
        except Exception:  # noqa: BLE001
            e10 = 0
        lohnt = grenz >= PK_GRENZSATZ
        schritte.append(Schritt(
            5, "PK-Einkauf", (ERLEDIGT if geplant else OFFEN) if lohnt else ENTFAELLT,
            ", ".join(f"{n} Potenzial CHF {_chf(v)}" for n, v in pot) + f"; Grenzsteuersatz {grenz:.0f} %. "
            + ("Gestaffelt über mehrere Jahre einzahlen; danach 3 Jahre kein Kapitalbezug und kein WEF-Vorbezug. "
               + (f"{len(geplant)} Einkauf(e) geplant." if geplant else "Plan unter Steuern → PK-Einkauf optimieren.")
               if lohnt else f"Bei einem Grenzsteuersatz unter {PK_GRENZSATZ} % lohnt sich der Einkauf meist weniger "
                             "als freies Anlegen."),
            sum(v for _, v in pot), 0, 0,
            f"rund CHF {_chf(e10)} Steuern auf CHF {_chf(bsp)} Einkauf" if e10 else "", "steuern"))

    # 6. langfristig
    nicht_angelegt = max(0.0, min(frei, c.anlegbar - c.depot))
    schritte.append(Schritt(6, "Langfristig anlegen", OFFEN if (rest > 0 or nicht_angelegt > 20000) else ERLEDIGT,
                            f"Profil «{cfg['risiko']}»: rund {c.aktien_soll:.0f} % Aktien, Horizont über 10 Jahre. "
                            + (f"Auf Konten liegen rund CHF {_chf(nicht_angelegt)} ohne Zweck – gestaffelt anlegen "
                               "(z. B. über 6–12 Monate)." if nicht_angelegt > 20000 else ""),
                            nicht_angelegt, round(rest), 0, jetzt=round(nicht_angelegt), nutzen=
                            f"Annahme {float(cfg['rendite'][cfg['risiko']]):g} % pro Jahr statt "
                            f"{float(cfg['zins_konto']):g} % auf dem Konto", seite="vermoegen"))
    rest = 0
    ungedeckt = round(sum(s.bedarf_monat - s.monat for s in schritte if s.nr <= 4 and s.bedarf_monat > s.monat))

    verwendet = sum(s.jetzt for s in schritte if s.nr in (2, 3, 4))
    klassen, naechster, ch_hinweis = _soll_ist(k, db, c, verwendet)
    teure = []
    try:
        import wertschriften as ws
        u = ws.uebersicht(k, db)
        if u:
            teure = sorted(((p.name, p.ter, p.wert) for p in u.positionen if p.ter is not None and p.ter > TER_HOCH),
                           key=lambda x: -x[2])
    except Exception:  # noqa: BLE001
        pass

    hinw = []
    if not spar:
        hinw.append("Kein Sparpotenzial erfasst – unter Einstellungen pro Person «Sparen pro Monat» eintragen (oder unter "
                    "Budget aus den Buchungen übernehmen), dann verteilt der Sparplan es auf die Schritte.")
    if spar and ungedeckt > 0:
        hinw.append(f"Das Sparpotenzial reicht für die Schritte 1–4 nicht: es fehlen rund CHF {_chf(ungedeckt)} pro Monat. "
                    "Ziele verschieben, Budget prüfen oder Reserve langsamer auffüllen.")
    if ch_hinweis:
        hinw.append(ch_hinweis)
    if teure:
        kosten = sum(t * w / 100 for _, t, w in teure)
        hinw.append(f"{len(teure)} Fonds mit Kosten über {TER_HOCH:g} % pro Jahr (zusammen rund CHF {_chf(kosten)} pro Jahr) – "
                    "beim nächsten Kauf kostengünstige Indexfonds bzw. ETF vorziehen; Verkauf nur, wenn Steuer- und "
                    "Handelskosten tiefer sind als die eingesparten Gebühren.")
    return Plan(schritte, round(spar), ungedeckt, round(ueberschuss), klassen, naechster, produktarten(k, c), teure, hinw)


def _soll_ist(k: dict, db, c, verwendet: float = 0.0) -> tuple[list[Klasse], str, str]:
    """Langfristiger Topf: Aktien (inkl. Krypto) gegen Ziel; Rest sicher (Obligationen, Konto über Reserve und Zweck).
    `verwendet`: was «jetzt vom Konto» schon für Schulden, 3a und Ziele eingeplant ist."""
    gesamt = max(0.0, c.anlegbar - verwendet) + c.krypto
    if gesamt <= 0:
        return [], "", ""
    aktien = None
    regionen: dict[str, float] = {}
    try:
        import wertschriften as ws
        aktien = ws.aktienwert(k, db)
        u = ws.uebersicht(k, db)
        if u:
            regionen = u.regionen
    except Exception:  # noqa: BLE001
        pass
    aktien_ist = min(gesamt, (c.depot if aktien is None else min(aktien, c.depot or aktien)) + c.krypto)
    soll_aktien = gesamt * c.aktien_soll / 100
    klassen = [Klasse("Aktien (inkl. Krypto)", round(aktien_ist), round(soll_aktien)),
               Klasse("Sicher (Obligationen, Konto, Geldmarkt)", round(gesamt - aktien_ist), round(gesamt - soll_aktien))]
    d = soll_aktien - aktien_ist
    if abs(d) < max(2000, gesamt * 0.05):
        naechster = "Aufteilung im Ziel – neue Beträge im Verhältnis des Ziels aufteilen."
    elif d > 0:
        naechster = (f"Aktien rund CHF {_chf(d)} unter dem Ziel – die nächsten Käufe in breit gestreute Aktienfonds "
                     "bzw. ETF, bis das Ziel erreicht ist (ohne zu verkaufen).")
    else:
        naechster = (f"Aktien rund CHF {_chf(-d)} über dem Ziel – neue Beträge in sichere Anlagen; verkaufen nur bei "
                     "grosser Abweichung (z. B. mehr als 10 Prozentpunkte).")
    ch = ""
    aktien_reg = {r: w for r, w in regionen.items() if w > 0}
    if aktien_reg and sum(aktien_reg.values()) > 0:
        schweiz = sum(w for r, w in aktien_reg.items() if r.lower() in ("schweiz", "ch"))
        anteil = schweiz / sum(aktien_reg.values()) * 100
        if anteil > CH_AKTIEN[1]:
            ch = (f"Schweiz-Anteil im Depot {anteil:.0f} % – üblich sind rund {CH_AKTIEN[0]}–{CH_AKTIEN[1]} %; die nächsten "
                  "Käufe eher international (Klumpenrisiko: wenige grosse Titel dominieren den Schweizer Markt).")
        elif anteil < CH_AKTIEN[0] and anteil < 100:
            ch = (f"Schweiz-Anteil im Depot {anteil:.0f} % – mit Ausgaben in Franken halten viele {CH_AKTIEN[0]}–"
                  f"{CH_AKTIEN[1]} % Schweiz (kein Währungsrisiko).")
    return klassen, naechster, ch


def produktarten(k: dict, c=None) -> list[Produktart]:
    w = k.get("wohnen") or {}
    arten = [
        Produktart("Notreserve", "Spar- oder Privatkonto mit Zins",
                   "Einlagensicherung bis CHF 100'000 pro Bank und Person; jederzeit verfügbar; Zins vergleichen."),
        Produktart("Zweckgebunden (bis 5 Jahre)", "Festgeld, Kassenobligation, Geldmarktfonds",
                   "Laufzeit auf das Datum der Ausgabe abstimmen; kein Kursrisiko kurz vor dem Bedarf."),
        Produktart("Säule 3a", "3a mit Wertschriften (Indexfonds) bei mehr als 10 Jahren bis zum Bezug, sonst 3a-Konto",
                   "Gesamtkosten unter rund 0.5 % pro Jahr; Aktienanteil passend zum Horizont; bis 5 Konten für den "
                   "gestaffelten Bezug; Wechsel des Anbieters ist kostenlos möglich."),
        Produktart("Langfristig: Aktien", "Breit gestreute Indexfonds oder ETF (Welt, Schweiz)",
                   "Laufende Kosten unter rund 0.3 %; Depot- und Handelsgebühren sowie Stempelsteuer vergleichen; "
                   "regelmässig und automatisch kaufen (Sparplan); Kursgewinne sind im Privatvermögen steuerfrei, "
                   "Dividenden und Zinsen steuerbar (auch bei thesaurierenden Fonds)."),
        Produktart("Langfristig: sicherer Teil", "Obligationen-Indexfonds in Franken, Kassenobligationen",
                   "Breit gestreut, tiefe Kosten, gute Bonität; Fremdwährungsobligationen nur abgesichert."),
        Produktart("Eher meiden", "Teure aktive Fonds, gemischte Lebensversicherungen als Sparprodukt, strukturierte "
                   "Produkte, Einzeltitel-Klumpen",
                   "Hohe, oft versteckte Kosten oder Klumpenrisiko; Sparen und Versichern lieber trennen."),
    ]
    if w.get("aktiv"):
        arten.insert(3, Produktart("Indirekte Amortisation", "Säule 3a, an die Bank verpfändet",
                                   "Schuld bleibt gleich hoch (höherer Zinsabzug), 3a-Abzug zusätzlich; mit der Bank "
                                   "vereinbaren."))
    return arten
