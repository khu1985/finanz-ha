"""Lebensereignisse durchspielen: Stellenverlust, Trennung bzw. Scheidung und die Aufteilung der Kosten im Paar.

Alles sind Näherungen für die Planung, keine Rechtsauskunft:
- Stellenverlust nach dem Arbeitslosenversicherungsgesetz (AVIG): versicherter Verdienst höchstens CHF 148'200 pro
  Jahr; Taggeld 80 % mit Unterhaltspflicht für Kinder unter 25 oder bei kleinem Taggeld (bis CHF 140), sonst 70 %;
  21,7 Taggelder pro Monat; 200 Taggelder bis 25 ohne Kinder, 400 nach 18 Beitragsmonaten, 520 ab 55 (22 Monate),
  dazu 120, wenn die Arbeitslosigkeit in den letzten 4 Jahren vor dem AHV-Alter beginnt; allgemeine Wartetage nach
  versichertem Verdienst. Abzüge auf dem Taggeld (AHV/IV/EO, Unfall, BVG-Risiko) rund 6,4 %.
- Trennung: Errungenschaftsbeteiligung (Art. 196 ff. ZGB) – jede Person behält ihr Eigengut und erhält die Hälfte
  der gesamten Errungenschaft; Teilung der während der Ehe geäufneten PK-Guthaben (Art. 122 ZGB). Im Konkubinat
  behält jede Person ihr Vermögen, Gemeinsames wird nach Anteilen geteilt. Unterhalt ist nicht gerechnet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

ALV_MAX = 148_200
ALV_ABZUEGE = 0.064
TAGE_MONAT = 21.7
NETTO_FAKTOR = 0.87        # Nettolohn ≈ 87 % des Bruttolohns (AHV/IV/EO, ALV, Unfall, PK-Beitrag)


def _netto(p: dict) -> float:
    return float(p.get("lohn_brutto") or 0) * NETTO_FAKTOR / 12


def _ausgaben_monat(k: dict, db) -> tuple[float, str]:
    """Ausgaben des Haushalts pro Monat: aus dem Budget, sonst Nettolöhne minus Sparpotenzial."""
    try:
        import budget as bu
        a = bu.auswerten(k, db)
        if a and a.ausgaben and a.monate >= 3:
            return a.ausgaben / 12, f"Budget ({a.monate} Monate)"
    except Exception:  # noqa: BLE001
        pass
    netto = sum(_netto(p) for p in k["personen"])
    sparen = sum(float(p.get("sparen_monat") or 0) for p in k["personen"])
    return max(0.0, netto - sparen), "Nettolöhne minus Sparpotenzial"


def _reserve(db) -> float:
    import vermoegen as vm
    return sum(x["wert"] for x in vm.konten(db) if x["art"] == "bank" and not x.get("aufgeloest"))


# ---------------------------------------------------------------- Stellenverlust

@dataclass
class Stellenverlust:
    person: str
    alter: int
    versichert_monat: float
    satz: int                    # 70 oder 80
    taggeld: float
    alv_monat: float             # netto
    taggelder: int
    wartetage: int
    bezug_monate: float
    ausgaben: float
    ausgaben_quelle: str
    andere_einkommen: float      # Nettolohn der anderen Person(en)
    luecke_alv: float            # pro Monat während des Bezugs (negativ = Überschuss)
    luecke_danach: float
    reserve: float
    reicht_monate: float | None  # wie lange die Reserve die Lücke deckt (None = keine Lücke)
    pk_weniger: float            # fehlende Altersgutschriften bei voller Bezugsdauer
    hinweise: list[str] = field(default_factory=list)


def _wartetage(versichert: float, kinder: bool) -> int:
    if kinder:
        return 0 if versichert <= 5000 else 5
    for grenze, tage in ((10416, 20), (7500, 15), (5000, 10), (3000, 5)):
        if versichert > grenze:
            return tage
    return 0


def stellenverlust(k: dict, db, person: str, heute: date | None = None) -> Stellenverlust:
    import kinder as ki
    import vorsorge as vs
    heute = heute or date.today()
    p = next(x for x in k["personen"] if x["name"] == person)
    alter = heute.year - vs.geburtsjahr(p)
    kinder = any(ki.alter(c, heute.year) < 25 for c in ki.eigene(k, person))
    versichert = min(float(p.get("lohn_brutto") or 0), ALV_MAX) / 12
    satz = 80 if kinder or versichert * 0.8 / TAGE_MONAT <= 140 else 70
    taggeld = versichert * satz / 100 / TAGE_MONAT
    if alter < 25 and not kinder:
        anzahl = 200
    elif alter >= 55:
        anzahl = 520
    else:
        anzahl = 400
    if vs.pensionsjahr(p) - heute.year <= 4:
        anzahl += 120
    alv = taggeld * TAGE_MONAT * (1 - ALV_ABZUEGE)
    ausgaben, quelle = _ausgaben_monat(k, db)
    andere = sum(_netto(x) for x in k["personen"] if x["name"] != person)
    luecke = ausgaben - andere - alv
    danach = ausgaben - andere
    reserve = _reserve(db)
    monate = anzahl / TAGE_MONAT
    if luecke <= 0 and danach <= 0:
        reicht = None
    elif luecke > 0:
        reicht = reserve / luecke if reserve / luecke <= monate else monate + max(0.0, reserve - luecke * monate) / max(danach, 1)
    else:
        reicht = monate + reserve / danach if danach > 0 else None
    beitrag = float(p["pk"].get("sparbeitrag_jahr") or 0) or \
        vs.bvg_koordinierter_lohn(float(p.get("lohn_brutto") or 0), k["kennzahlen"]) * vs.bvg_gutschriftsatz(alter, k["kennzahlen"]) / 100
    s = Stellenverlust(person, alter, round(versichert), satz, round(taggeld, 2), round(alv), anzahl,
                       _wartetage(versichert, kinder), round(monate, 1), round(ausgaben), quelle, round(andere),
                       round(luecke), round(danach), round(reserve), None if reicht is None else round(reicht, 1),
                       round(beitrag * monate / 12))
    s.hinweise = _hinweise_stelle(s, p)
    return s


def _hinweise_stelle(s: Stellenverlust, p: dict) -> list[str]:
    chf = lambda v: f"{v:,.0f}".replace(",", "'")  # noqa: E731
    h = []
    if float(p.get("lohn_brutto") or 0) > ALV_MAX:
        h.append(f"Versichert ist höchstens CHF {chf(ALV_MAX)} – der Lohn darüber ist nicht gedeckt.")
    if s.luecke_alv > 0:
        h.append(f"Während der Arbeitslosigkeit fehlen rund CHF {chf(s.luecke_alv)} pro Monat.")
    if s.reicht_monate is not None and s.reicht_monate < 6:
        h.append(f"Die Reserve auf den Konten deckt das nur rund {s.reicht_monate:.0f} Monate – Ziel sind 3–6 Monatsausgaben "
                 "plus die Lücke bei Stellenverlust.")
    elif s.reicht_monate is None:
        h.append("Die übrigen Einkommen und das Taggeld decken die Ausgaben – kein Verzehr der Reserve nötig.")
    h.append(f"Wartetage zuerst ohne Taggeld: {s.wartetage}. Anmeldung beim RAV spätestens am ersten Tag ohne Lohn; "
             "Kündigungsfrist für die Stellensuche nutzen (Nachweise von Bewerbungen schon vorher).")
    h.append(f"Pensionskasse: Das Guthaben geht auf ein Freizügigkeitskonto, Altersgutschriften fallen weg – bei voller "
             f"Bezugsdauer rund CHF {chf(s.pk_weniger)} weniger PK-Kapital. Tod und Invalidität bleiben über die "
             "Auffangeinrichtung versichert.")
    h.append("Krankentaggeld und Unfall: Unfall ist über die ALV versichert (SUVA); Krankentaggeld der Firma endet – "
             "Übertritt in die Einzelversicherung innert 3 Monaten prüfen.")
    return h


# ---------------------------------------------------------------- Trennung

@dataclass
class Anteil:
    person: str
    vermoegen: float             # heute zugeordnet (eigene Konten + Hälfte der gemeinsamen)
    eigengut: float
    anspruch: float              # nach Güterrecht bzw. Eigentum
    ausgleich: float             # zu erhalten (+) bzw. zu zahlen (−)
    pk_heute: float
    pk_ausgleich: float          # PK-Teilung: zu erhalten (+) bzw. abzugeben (−)
    netto_monat: float
    kosten_allein: float         # typische Ausgaben eines Einpersonenhaushalts (BFS)
    haus_tragbar: bool | None    # könnte die Person das Haus allein halten?


@dataclass
class Trennung:
    verheiratet: bool
    anteile: list[Anteil]
    gemeinsam: float
    haus_netto: float
    hinweise: list[str] = field(default_factory=list)


def trennung(k: dict, db, heute: date | None = None) -> Trennung | None:
    import habe
    import vermoegen as vm
    import vorsorge as vs
    heute = heute or date.today()
    personen = k["personen"]
    if len(personen) < 2:
        return None
    verheiratet = str(k["haushalt"].get("zivilstand", "")).lower().startswith("verh")
    namen = [p["name"] for p in personen[:2]]
    eigen = {n: 0.0 for n in namen}
    gemeinsam = 0.0
    haus = 0.0
    vorsorge_konten = {n: False for n in namen}
    for x in vm.konten(db):
        if x.get("aufgeloest"):
            continue
        if x["art"] in ("immobilie", "hypothek"):
            haus += x["wert"]
            if x["person"] in eigen and x["art"] == "immobilie":
                pass
            continue
        if x["person"] in eigen:
            eigen[x["person"]] += x["wert"]
            if x["art"] == "saeule3a":
                vorsorge_konten[x["person"]] = True
        else:
            gemeinsam += x["wert"]
    for p in personen[:2]:
        if not vorsorge_konten[p["name"]]:
            eigen[p["name"]] += float((p.get("saeule3a") or {}).get("guthaben") or 0)
    anteil_1 = float(personen[0].get("eigentum_anteil") or 0) / 100 or \
        (1 - float(personen[1].get("eigentum_anteil") or 0) / 100 if personen[1].get("eigentum_anteil") else 0.5)
    haus_anteil = {namen[0]: haus * anteil_1, namen[1]: haus * (1 - anteil_1)}
    verm = {n: eigen[n] + gemeinsam / 2 + haus_anteil[n] for n in namen}
    eg = {p["name"]: float(p.get("eigengut") or 0) for p in personen[:2]}
    if verheiratet:
        errungenschaft = {n: max(0.0, verm[n] - eg[n]) for n in namen}
        haelfte = sum(errungenschaft.values()) / 2
        anspruch = {n: min(verm[n], eg[n]) + haelfte for n in namen}
    else:
        anspruch = dict(verm)
    pk = {p["name"]: float(p["pk"].get("altersguthaben") or 0) for p in personen[:2]}
    pk_heirat = {p["name"]: float(p["pk"].get("guthaben_heirat") or 0) for p in personen[:2]}
    if verheiratet:
        diff = ((pk[namen[0]] - pk_heirat[namen[0]]) - (pk[namen[1]] - pk_heirat[namen[1]])) / 2
        pk_aus = {namen[0]: -diff, namen[1]: diff}
    else:
        pk_aus = {n: 0.0 for n in namen}
    allein = {p["name"]: habe.DATEN["typ"]["allein_65" if heute.year - vs.geburtsjahr(p) >= 65 else "allein_u65"]
              for p in personen[:2]}
    w = k.get("wohnen") or {}
    tragbar = {n: None for n in namen}
    if w.get("aktiv") and haus:
        import wohnen as wo
        t = wo.tragbarkeit(k, heute.year)
        for p in personen[:2]:
            lohn = float(p.get("lohn_brutto") or 0)
            kalk = t["kalk_kosten"]
            tragbar[p["name"]] = bool(lohn) and kalk / lohn * 100 <= float(k["kennzahlen"]["tragbarkeit_max"])
    anteile = []
    for p in personen[:2]:
        n = p["name"]
        g = allein[n]
        kosten = g["konsum"][0] + g["kk_grund"][0] + g["kk_zusatz"][0] + g["versicherungen"][0] + g["steuern"][0]
        anteile.append(Anteil(n, round(verm[n]), round(eg[n]), round(anspruch[n]), round(anspruch[n] - verm[n]),
                              round(pk[n]), round(pk_aus[n]), round(_netto(p)), round(kosten), tragbar[n]))
    t_ = Trennung(verheiratet, anteile, round(gemeinsam), round(haus))
    t_.hinweise = _hinweise_trennung(t_, k)
    return t_


def _hinweise_trennung(t: Trennung, k: dict) -> list[str]:
    chf = lambda v: f"{v:,.0f}".replace(",", "'")  # noqa: E731
    h = []
    for a in t.anteile:
        frei = a.netto_monat - a.kosten_allein
        if frei < 0:
            h.append(f"{a.person}: allein fehlen rund CHF {chf(-frei)} pro Monat gegenüber den typischen Kosten eines "
                     "Einpersonenhaushalts – ohne Unterhalt gerechnet.")
    if t.verheiratet:
        if not any(a.eigengut for a in t.anteile):
            h.append("Eigengut fehlt: Was jemand vor der Ehe besass oder geerbt bzw. geschenkt erhielt, gehört nicht zur "
                     "Errungenschaft – unter Einstellungen als «Eigengut» je Person erfassen, sonst wird alles geteilt.")
        h.append("PK-Teilung: geteilt wird, was während der Ehe angespart wurde. Ohne Angabe des Guthabens bei der Heirat "
                 "(«PK-Guthaben bei Heirat») rechnet die App mit dem ganzen Guthaben.")
    else:
        h.append("Konkubinat: kein Güterrecht, keine PK-Teilung, kein nachehelicher Unterhalt – jede Person behält, was "
                 "auf sie lautet. Gemeinsames wird nach Anteilen geteilt; ein Konkubinatsvertrag regelt das vorab.")
    if any(a.haus_tragbar is not None for a in t.anteile):
        wer = [a.person for a in t.anteile if a.haus_tragbar]
        h.append(("Das Haus allein halten könnte nach der Tragbarkeitsregel: " + ", ".join(wer)) if wer else
                 "Allein trägt niemand das Haus nach der Tragbarkeitsregel (Kosten über einem Drittel des Lohns) – "
                 "Verkauf oder Übernahme mit zusätzlichen Eigenmitteln prüfen.")
        if t.haus_netto > 0:
            h.append(f"Wer das Haus übernimmt, zahlt die andere Person aus: Eigenkapital im Haus CHF {chf(t.haus_netto)}.")
    if (k.get("haushalt") or {}).get("kinder"):
        h.append("Mit Kindern: Kinder- und Betreuungsunterhalt, Obhut und Erziehungsgutschriften kommen dazu – "
                 "Berechnung mit der Fachstelle oder einer Anwältin.")
    return h


# ---------------------------------------------------------------- Geld im Paar

@dataclass
class Variante:
    name: str
    beitraege: dict[str, float]
    frei: dict[str, float]


@dataclass
class Aufteilung:
    gemeinsam: float
    quelle: str
    netto: dict[str, float]
    varianten: list[Variante]
    renten: dict[str, float]      # AHV + PK pro Jahr ab Pensionierung (heutige Franken, grob)
    hinweise: list[str] = field(default_factory=list)


GEMEINSAM_BUDGET = ("Wohnen", "Lebensmittel", "Kinder und Betreuung", "Versicherungen", "Telekom und Abos",
                    "Gebühren und Zinsen")
GEMEINSAM_BFS = ("wohnen", "nahrung", "einrichtung", "kommunikation", "versicherungen", "gebuehren")


def _gemeinsam(k: dict, db) -> tuple[float, str]:
    """Typische gemeinsame Kosten: Wohnen, Lebensmittel, Kinder, Versicherungen, Telekom – aus dem Budget oder dem BFS."""
    try:
        import budget as bu
        a = bu.auswerten(k, db)
        if a and a.monate >= 3:
            s = sum(v for n, v, _ in a.kategorien if n in GEMEINSAM_BUDGET) / 12
            if s:
                return s, "Budget: Wohnen, Lebensmittel, Kinder, Versicherungen, Telekom"
    except Exception:  # noqa: BLE001
        pass
    import habe
    g = habe.DATEN["typ"][habe.haushaltstyp(k, date.today().year)]
    return sum(g[x][0] for x in GEMEINSAM_BFS), "Mittel vergleichbarer Haushalte (BFS)"


def aufteilung(k: dict, db, gemeinsam: float | None = None) -> Aufteilung | None:
    import vorsorge as vs
    personen = k["personen"][:2]
    if len(personen) < 2:
        return None
    netto = {p["name"]: round(_netto(p)) for p in personen}
    total = sum(netto.values())
    if gemeinsam is None:
        cfg = float((k.get("haushalt") or {}).get("gemeinsame_ausgaben_monat") or 0)
        gemeinsam, quelle = (cfg, "Einstellungen") if cfg else _gemeinsam(k, db)
    else:
        quelle = "Eingabe"
    namen = list(netto)
    varianten = []
    haelfte = {n: gemeinsam / 2 for n in namen}
    prop = {n: gemeinsam * netto[n] / total if total else gemeinsam / 2 for n in namen}
    gleich = {n: netto[n] - (total - gemeinsam) / 2 for n in namen}
    for name, b in (("Je die Hälfte", haelfte), ("Im Verhältnis zum Einkommen", prop), ("Gleich viel frei für beide", gleich)):
        varianten.append(Variante(name, {n: round(v) for n, v in b.items()}, {n: round(netto[n] - b[n]) for n in namen}))
    ahv = {r.name: r.rente_jahr for r in vs.ahv(k)}
    renten = {p["name"]: round(ahv.get(p["name"], 0) + vs.pk(p, k).rente_jahr) for p in personen}
    a = Aufteilung(round(gemeinsam), quelle, netto, varianten, renten)
    a.hinweise = _hinweise_aufteilung(a, k)
    return a


def _hinweise_aufteilung(a: Aufteilung, k: dict) -> list[str]:
    chf = lambda v: f"{v:,.0f}".replace(",", "'")  # noqa: E731
    h = []
    namen = list(a.netto)
    if a.netto and max(a.netto.values()) and min(a.netto.values()) / max(a.netto.values()) < 0.7:
        h.append("Die Einkommen sind ungleich: Je die Hälfte belastet die Person mit weniger Einkommen stark; im Verhältnis "
                 "zum Einkommen bleibt beiden derselbe Anteil frei.")
    if a.renten:
        tief, hoch = sorted(namen, key=lambda n: a.renten[n])[0], sorted(namen, key=lambda n: a.renten[n])[-1]
        diff = a.renten[hoch] - a.renten[tief]
        if diff > 6000:
            konk = not str(k["haushalt"].get("zivilstand", "")).lower().startswith("verh")
            h.append(f"Vorsorge: {tief} erhält im Alter voraussichtlich rund CHF {chf(diff)} weniger Rente pro Jahr als "
                     f"{hoch}. Ausgleich z. B. über 3a-Einzahlungen und PK-Einkäufe von {tief} (aus dem gemeinsamen Topf) "
                     + ("– im Konkubinat besonders wichtig, weil es keine PK-Teilung und keine Witwen- bzw. Witwerrente gibt."
                        if konk else "– bei einer Scheidung würde das während der Ehe Angesparte geteilt."))
    return h
