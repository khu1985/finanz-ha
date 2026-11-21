"""Kurz-Zeilen: ein Satz mit der Kernaussage oben auf den Hauptseiten – vor Tabellen und Diagrammen.

Je Seite eine Kennzahl in Worten und – falls eine Ampel der Seite gelb oder rot ist – was zu tun ist.
Fehler verhindern die Seite nie (dann fehlt der Satz einfach).
"""
from __future__ import annotations

import logging
from datetime import date

from tausender import TS  # noqa: E402

LOG = logging.getLogger("finanz")


def _chf(v: float) -> str:
    return f"CHF {v:,.0f}" >> TS


def _budget(k, db) -> str:
    import budget as bu
    a = bu.auswerten(k, db)
    if not a:
        return "Noch keine Buchungen – Bankauszug importieren, dann zeigt das Budget Einnahmen, Ausgaben und Sparquote."
    return (f"Pro Monat kommen im Schnitt {_chf(a.einnahmen / 12)} herein und gehen {_chf(a.ausgaben / 12)} weg – "
            f"Sparquote {a.sparquote:.0f} % (letzte {a.monate} Monate).")


def _vermoegen(k, db) -> str:
    import vermoegen as vm
    nv = vm.nettovermoegen(db)
    return (f"Nettovermögen {_chf(nv['total'])}, davon frei verfügbar {_chf(nv['frei'])}.")


def _steuern(k, db) -> str:
    import steuern as st
    import steuerzahlung as sz
    s = st.steuern_heute(k)
    posten = sz.auswerten(k, db)
    offen = sz.offen_total(posten)
    return (f"Steuern rund {_chf(s['total'])} pro Jahr (Grenzsteuersatz {float(s.get('grenz_total') or 0):.0f} %)"
            + (f"; offen {_chf(offen)}." if offen > 0.5 else "; nichts offen."))


def _vorsorge(k, db) -> str:
    import vermoegen as vm
    import vorsorge as vs
    l_ = vs.pensionsluecke(k, vm.nettovermoegen(db)["frei"], date.today().year)
    if l_.luecke:
        return (f"Ab {l_.jahr} fehlen rund {_chf(l_.luecke / 12)} pro Monat zum Bedarf von {_chf(l_.bedarf / 12)} "
                "(nach AHV, PK und Vermögensverzehr).")
    return f"Ab {l_.jahr} decken AHV, PK und Vermögen den Bedarf von {_chf(l_.bedarf / 12)} pro Monat."


def _wohnen(k, db) -> str:
    import wohnen as wo
    if not (k.get("wohnen") or {}).get("aktiv"):
        return "Kein Wohneigentum erfasst – unter Einstellungen → Wohnen aktivieren, um Tragbarkeit und Amortisation zu sehen."
    t = wo.tragbarkeit(k, date.today().year)
    return (f"Hypothek {_chf(t['hypothek'])}, Belehnung {t['belehnung']:.0f} %, Tragbarkeit {t['quote']:.0f} % "
            f"(Grenze {k['kennzahlen']['tragbarkeit_max']:.0f} %); effektiv {_chf(t['effektiv_monat'])} pro Monat.")


def _versicherungen(k, db) -> str:
    import versicherungen as vi
    vs_ = [v for v in vi.alle(db) if not v.get("gekuendigt")]
    praemie = sum(float(v.get("praemie_jahr") or 0) for v in vs_)
    return f"{len(vs_)} Verträge, zusammen {_chf(praemie)} Prämie pro Jahr."


def _kinder(k, db) -> str:
    kinder = (k.get("haushalt") or {}).get("kinder") or []
    if not kinder:
        return "Keine Kinder erfasst."
    return f"{len(kinder)} Kind{'' if len(kinder) == 1 else 'er'} – Kosten, Zulagen, Steuerabzüge und Sparen auf einen Blick."


def _fahrzeuge(k, db) -> str:
    import fahrzeuge as fz
    autos = fz.alle(k, db)
    if not autos:
        return "Kein Fahrzeug erfasst."
    total = sum(a.total for a in autos)
    return f"{len(autos)} Fahrzeug{'' if len(autos) == 1 else 'e'}, zusammen rund {_chf(total)} pro Jahr (alle Kosten)."


def _konkubinat(k, db) -> str:
    import konkubinat as ko
    if not ko.aktiv(k):
        return ""
    punkte = ko.pruefen(k, db)
    gut, offen = ko.zusammenfassung(punkte)
    erst = next((p for p in punkte if p.status == "rot" and p.tun), None) or next((p for p in punkte if p.tun), None)
    return (f"{gut} von {gut + offen} Bereichen geregelt" + (f"; zuerst: {erst.tun}." if erst else "."))


def _liquiditaet(k, db) -> str:
    import liquiplan as lp
    p = lp.rechnen(k, db)
    t = p.tief
    if t.ende < 0:
        return f"Im {t.name} fehlen auf den Bankkonten rund {_chf(-t.ende)} – vorher Geld bereitstellen."
    return (f"Tiefster Kontostand {_chf(t.ende)} im {t.name}; für grosse Rechnungen {_chf(p.zuruecklegen)} pro Monat "
            "zurücklegen.")


def _sparplan(k, db) -> str:
    import sparplan as sp
    p = sp.rechnen(k, db)
    erster = next((s for s in p.schritte if s.status in (sp.OFFEN, sp.TEILWEISE)), None)
    return (f"Sparpotenzial {_chf(p.sparpotenzial)} pro Monat; "
            + (f"nächster Schritt: {erster.titel}." if erster else "alle Schritte erledigt."))


def _steuerzahlung(k, db) -> str:
    import steuerzahlung as sz
    heute = date.today()
    posten = sz.auswerten(k, db, heute)
    offen = [p for p in posten if p.offen > 0.5]
    ueber = [p for p in offen if p.faellig < heute]
    if not offen:
        return "Alle Steuerrechnungen sind bezahlt."
    n = min(offen, key=lambda p: p.faellig)
    return (f"Offen {_chf(sz.offen_total(posten))}"
            + (f", davon {len(ueber)} Position{'' if len(ueber) == 1 else 'en'} überfällig" if ueber else "")
            + f"; nächste Fälligkeit {n.faellig:%d.%m.%Y} ({n.name} {n.jahr}).")


def _steuererklaerung(k, db) -> str:
    import steuererklaerung as se
    heute = date.today()
    c = se.erstellen(k, db, se.standard_jahr(heute), heute)
    return (f"Steuererklärung {c.jahr}: {c.total - c.offen} von {c.total} Punkten bereit, Frist {c.frist:%d.%m.%Y} "
            f"(noch {(c.frist - heute).days} Tage).")


def _lebensereignisse(k, db) -> str:
    import lebensereignisse as le
    teile = []
    for p in k["personen"]:
        if not float(p.get("lohn_brutto") or 0):
            continue
        s_ = le.stellenverlust(k, db, p["name"])
        teile.append(f"{p['name']}: " + ("keine Lücke" if s_.reicht_monate is None
                                          else f"Reserve reicht rund {s_.reicht_monate:.0f} Monate"))
    return ("Bei Stellenverlust – " + "; ".join(teile) + ".") if teile else ""


SAETZE = {"budget": _budget, "vermoegen": _vermoegen, "steuern": _steuern, "vorsorge": _vorsorge,
          "wohnen": _wohnen, "versicherungen": _versicherungen, "kinder": _kinder, "fahrzeuge": _fahrzeuge,
          "finanzplan": None, "nachlass": None, "konkubinat": _konkubinat,
          "liquiditaet": _liquiditaet, "sparplan": _sparplan, "steuerzahlung": _steuerzahlung,
          "steuererklaerung": _steuererklaerung, "lebensereignisse": _lebensereignisse}


def satz(pfad: str, k: dict, db) -> str:
    """Kurz-Zeile der Seite (leer, wenn die Seite keine hat oder etwas fehlt)."""
    if pfad not in SAETZE:
        return ""
    teile = []
    f = SAETZE[pfad]
    if f:
        try:
            teile.append(f(k, db))
        except Exception as e:  # noqa: BLE001
            LOG.debug("Kurz %s: %s", pfad, e)
    try:
        import ampel as am
        schlecht = [a for a in am.bewerten(k, db) if a.status in (am.ROT, am.GELB)
                    and (a.seite or "").split("#")[0].split("/")[0] == pfad]
        schlecht.sort(key=lambda a: -am.RANG[a.status])
        if schlecht:
            teile.append(f"Zu tun: {schlecht[0].text}.")
        elif not teile:
            gut = [a for a in am.bewerten(k, db) if (a.seite or "").split("#")[0].split("/")[0] == pfad]
            if gut:
                teile.append(f"{gut[0].bereich}: {gut[0].text}.")
    except Exception as e:  # noqa: BLE001
        LOG.debug("Kurz-Ampel %s: %s", pfad, e)
    return " ".join(t for t in teile if t)
