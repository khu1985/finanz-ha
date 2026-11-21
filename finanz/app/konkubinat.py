"""Konkubinat-Check: Wo ist ein unverheiratetes Paar schlechter (oder besser) gestellt als ein Ehepaar, und was ist
dagegen schon geregelt?

Je Bereich (Tod, Urteilsunfähigkeit, Trennung, Kinder, Steuern und AHV) ein Punkt mit Lage, Ampel und dem nächsten
Schritt. Der Status kommt aus den Daten der App: Nachlass-Checkliste, PK-Meldung, Beginn des gemeinsamen Haushalts,
Nachlass-Fälle (Ausgleich für das Haus) und Heiratsvergleich. Keine Rechtsberatung – Stand Gesetz 2023/2026.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from tausender import TS  # noqa: E402

import ampel as am

LOG = logging.getLogger("finanz")


@dataclass
class Punkt:
    bereich: str          # Tod, Urteilsunfähigkeit, Trennung, Kinder, Steuern und AHV
    titel: str
    status: str           # am.GRUEN / am.GELB / am.ROT / am.GRAU (nur Information)
    lage: str             # was im Konkubinat gilt bzw. wie es bei euch aussieht
    tun: str = ""         # nächster Schritt ("" wenn erledigt)
    seite: str = ""


def aktiv(k: dict) -> bool:
    return k["haushalt"].get("zivilstand", "verheiratet") != "verheiratet" and len(k["personen"]) > 1


def _chf(v: float) -> str:
    return f"CHF {v:,.0f}" >> TS


def _haken(k: dict, schluessel: str) -> dict[str, bool]:
    erl = ((k.get("nachlass") or {}).get("checkliste") or {}).get(schluessel) or {}
    return {p["name"]: bool(erl.get(p["name"])) for p in k["personen"]}


def _alle(h: dict[str, bool]) -> bool:
    return all(h.values())


def _fehlt(h: dict[str, bool]) -> str:
    return ", ".join(n for n, v in h.items() if not v)


def pruefen(k: dict, db, heute: date | None = None) -> list[Punkt]:
    import nachlass as nl
    heute = heute or date.today()
    if not aktiv(k):
        return []
    erg: list[Punkt] = []
    namen = [p["name"] for p in k["personen"][:2]]
    jahre = nl._jahre_zusammen(k, heute)
    seit = (k.get("nachlass") or {}).get("zusammen_seit")

    # ---------------------------------------------------------------- Tod
    t = _haken(k, "testament")
    erg.append(Punkt("Tod", "Erbe", am.GRUEN if _alle(t) else am.ROT,
                     "Konkubinatspartner sind keine gesetzlichen Erben – ohne Testament oder Erbvertrag geht alles an "
                     "Kinder, Eltern oder Geschwister.",
                     "" if _alle(t) else f"Testament bzw. Erbvertrag: {_fehlt(t)}", "verfuegungen?typ=testament"))

    kanton = str(k["haushalt"].get("kanton", "")).upper()
    r = nl.PARTNER_STEUER.get(kanton)
    if r and r.get("jahre") and r.get("satz_ohne") is not None:
        if jahre is None:
            st_, lage, tun = am.GELB, (f"Erbschaftssteuer {kanton}: {r['satz']:g} % nach 5 Jahren gemeinsamem Haushalt, "
                                        f"sonst {r['satz_ohne']:g} %."), "Beginn des gemeinsamen Haushalts erfassen"
        elif jahre >= r["jahre"]:
            st_, lage, tun = am.GRUEN, (f"Erbschaftssteuer {kanton}: {r['satz']:g} % nach Abzug von "
                                        f"{_chf(r['freibetrag'])} (seit {seit} gemeinsamer Haushalt)."), ""
        else:
            ab = int(str(seit)[:4]) + r["jahre"]
            st_, lage, tun = am.GELB, (f"Erbschaftssteuer {kanton}: bis {ab} {r['satz_ohne']:g} % nach Abzug von "
                                       f"{_chf(r['freibetrag_ohne'])}, danach {r['satz']:g} %."), \
                "Bis dahin den Todesfallschutz um die höhere Steuer ergänzen"
        erg.append(Punkt("Tod", "Erbschaftssteuer", st_, lage, tun, "nachlass"))
    elif r:
        erg.append(Punkt("Tod", "Erbschaftssteuer", am.GRAU, r["quelle"], "", "nachlass"))
    else:
        erg.append(Punkt("Tod", "Erbschaftssteuer", am.GELB, f"Satz für {kanton or 'den Kanton'} nicht hinterlegt.",
                         "Satz unter nachlass.erbschaftssteuer eintragen", "einstellungen"))

    try:
        faelle = nl.faelle(k, db, heute)
    except Exception as e:  # noqa: BLE001
        LOG.debug("Konkubinat Nachlass: %s", e)
        faelle = []
    if (k.get("wohnen") or {}).get("aktiv"):
        import wohnen as wo
        anteile = wo.eigentum_anteile(k)
        teile = " / ".join(f"{n} {v:.0f} %" for n, v in anteile.items())
        offen = [f for f in faelle if f.ausgleich_haus > f.policen + f.vorsorge_kapital]
        knapp = [f for f in faelle if 0 < f.ausgleich_haus <= f.policen + f.vorsorge_kapital]
        lg = _haken(k, "liegenschaft")
        if offen:
            st_ = am.ROT
            lage = "; ".join(f"Tod von {f.verstorben}: {_chf(f.ausgleich_haus)} an die Erben, gedeckt "
                             f"{_chf(f.policen + f.vorsorge_kapital)}" for f in offen)
            tun = "Testament, Wohnrecht oder Todesfallrisiko-Police in Höhe des Ausgleichs"
        elif knapp or not _alle(lg):
            st_ = am.GELB
            lage = (f"Miteigentum {teile}. " + ("; ".join(f"Tod von {f.verstorben}: Ausgleich {_chf(f.ausgleich_haus)} "
                                                          "aus Vorsorge und Policen gedeckt" for f in knapp) or
                                                 "Kein Ausgleich an Erben nötig."))
            tun = "" if _alle(lg) else f"Regelung für die Liegenschaft festhalten: {_fehlt(lg)}"
        else:
            st_, lage, tun = am.GRUEN, f"Miteigentum {teile}; der Partner kann das Haus behalten.", ""
        erg.append(Punkt("Tod", "Haus behalten", st_, "Bei einem Todesfall erben die gesetzlichen Erben den Anteil am "
                         "Haus; der Partner muss sie auszahlen. " + lage, tun, "nachlass"))

    pk_ok = {p["name"]: bool((p.get("risiko") or {}).get("partner_bei_pk_gemeldet")) or _haken(k, "pk_meldung")[p["name"]]
             for p in k["personen"][:2]}
    erg.append(Punkt("Tod", "Pensionskasse", am.GRUEN if _alle(pk_ok) else am.ROT,
                     "Lebenspartnerrente und Todesfallkapital nur, wenn das Reglement sie vorsieht und die Partnerschaft "
                     "gemeldet ist (meist 5 Jahre gemeinsamer Haushalt oder gemeinsames Kind).",
                     "" if _alle(pk_ok) else f"Lebenspartner bei der PK melden: {_fehlt(pk_ok)}", "nachlass"))

    b3 = _haken(k, "begünstigung_3a")
    kinder_gem = _gemeinsame_kinder(k)
    voraus = (jahre is not None and jahre >= 5) or kinder_gem > 0
    erg.append(Punkt("Tod", "Säule 3a", am.GRUEN if _alle(b3) and voraus else am.GELB if voraus or _alle(b3) else am.ROT,
                     "Der Partner ist begünstigt nach 5 Jahren gemeinsamem Haushalt oder wenn er für gemeinsame Kinder "
                     "sorgt – aber nur, wenn die Stiftung davon weiss."
                     + ("" if voraus else " Bei euch ist das (noch) nicht erfüllt bzw. nicht erfasst."),
                     "" if _alle(b3) else f"Begünstigung schriftlich bei der Stiftung festlegen: {_fehlt(b3)}",
                     "verfuegungen?typ=beguenstigung_3a"))

    tf = _haken(k, "todesfallschutz")
    bp = _haken(k, "begünstigung_policen")
    try:
        import szenarien as sz
        h = sz.heirat_vergleich(k, db, heute)
        luecke = sum(max(0.0, v - kk) for _, kk, v in h.hinterbliebene) if h.moeglich else 0.0
    except Exception as e:  # noqa: BLE001
        LOG.debug("Konkubinat Heirat: %s", e)
        h, luecke = None, 0.0
    lage = "Keine AHV-Witwen- oder Witwerrente; Waisenrenten für Kinder gibt es wie bei Verheirateten."
    if luecke:
        lage += (f" Als Ehepaar erhielte der Hinterbliebene im Schnitt rund {_chf(luecke / 2)} mehr Rente pro Jahr "
                 "(AHV-Witwen- bzw. Witwerrente, PK-Ehegattenrente); eine gemeldete PK-Lebenspartnerrente ersetzt einen "
                 "Teil davon.")
    erg.append(Punkt("Tod", "Renten und Todesfallschutz", am.GRUEN if _alle(tf) and _alle(bp) else am.GELB, lage,
                     "" if _alle(tf) and _alle(bp) else
                     "; ".join(x for x in (f"Todesfallschutz prüfen: {_fehlt(tf)}" if not _alle(tf) else "",
                                           f"Begünstigte der Policen: {_fehlt(bp)}" if not _alle(bp) else "") if x),
                     "versicherungen"))

    # ---------------------------------------------------------------- Urteilsunfähigkeit
    va = _haken(k, "vorsorgeauftrag")
    pv = _haken(k, "patientenverfuegung")
    erg.append(Punkt("Urteilsunfähigkeit", "Vertretung", am.GRUEN if _alle(va) and _alle(pv) else am.ROT
                     if not any(va.values()) else am.GELB,
                     "Ehegatten dürfen sich von Gesetzes wegen im Alltag vertreten; Konkubinatspartner nicht. Medizinisch "
                     "ist der Partner im gemeinsamen Haushalt erst nach Ehegatten vertretungsberechtigt; für Konten, "
                     "Hypothek und Verträge braucht es einen Vorsorgeauftrag, sonst setzt die KESB einen Beistand ein.",
                     "; ".join(x for x in (f"Vorsorgeauftrag: {_fehlt(va)}" if not _alle(va) else "",
                                           f"Patientenverfügung: {_fehlt(pv)}" if not _alle(pv) else "") if x),
                     "verfuegungen?typ=vorsorgeauftrag"))

    # ---------------------------------------------------------------- Trennung
    kv = _haken(k, "konkubinatsvertrag")
    lage = ("Kein Güterrecht und kein Unterhalt zwischen den Partnern: Jeder behält, was ihm gehört; "
            "bei Miteigentum am Haus entscheidet der Grundbucheintrag.")
    if (k.get("wohnen") or {}).get("aktiv"):
        lage += " Für die Hypothek haften beide solidarisch."
    erg.append(Punkt("Trennung", "Konkubinatsvertrag", am.GRUEN if any(kv.values()) else am.GELB, lage,
                     "" if any(kv.values()) else "Konkubinatsvertrag: Haus, Hausrat, Darlehen und Auszahlung regeln",
                     "verfuegungen?typ=konkubinatsvertrag"))

    # ---------------------------------------------------------------- Kinder
    if kinder_gem:
        erg.append(Punkt("Kinder", "Gemeinsame Kinder", am.GRAU,
                         f"{kinder_gem} gemeinsame{'s' if kinder_gem == 1 else ''} Kind{'' if kinder_gem == 1 else 'er'}: "
                         "Kindesanerkennung, Erklärung über die gemeinsame elterliche Sorge und ein Unterhaltsvertrag "
                         "(bei Trennung) sind beim Zivilstandsamt bzw. der KESB zu regeln. Kinderabzug und Elterntarif "
                         "erhält in der Steuererklärung eine Person.", "", "kinder"))

    # ---------------------------------------------------------------- Steuern und AHV
    if h is not None and h.moeglich:
        teile = []
        if h.steuer_diff > 0:
            teile.append(f"getrennt rund {_chf(h.steuer_diff)} weniger Steuern pro Jahr")
        elif h.steuer_diff < 0:
            teile.append(f"verheiratet rund {_chf(-h.steuer_diff)} weniger Steuern pro Jahr")
        if h.ahv_diff < 0:
            teile.append(f"zwei ungekürzte AHV-Renten, rund {_chf(-h.ahv_diff)} mehr pro Jahr als verheiratet "
                         "(Plafonierung)")
        erg.append(Punkt("Steuern und AHV", "Was das Konkubinat bringt", am.GRAU,
                         (("Im Vergleich zur Heirat: " + "; ".join(teile) + ". ") if teile else "")
                         + f"Ab spätestens {h.ib_jahr} werden auch Ehepaare getrennt besteuert.", "",
                         "szenarien"))
    return erg


def _gemeinsame_kinder(k: dict) -> int:
    import kinder as ki
    if len(k["personen"]) < 2:
        return 0
    a = {str(c.get("name")) for c in ki.eigene(k, k["personen"][0]["name"])}
    return sum(1 for c in ki.eigene(k, k["personen"][1]["name"]) if str(c.get("name")) in a)


def zusammenfassung(punkte: list[Punkt]) -> tuple[int, int]:
    """(geregelt, zu regeln) – Informationspunkte zählen nicht."""
    rel = [p for p in punkte if p.status != am.GRAU]
    return sum(1 for p in rel if p.status == am.GRUEN), sum(1 for p in rel if p.status != am.GRUEN)
