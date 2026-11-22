"""Zinsrisiko bei der Verlängerung der Hypothek: Was halten Budget und Tragbarkeit bei 2 bis 6 % aus?

Für die Fälligkeit (`wohnen.hypothek_faellig`) und das erste volle Jahr danach, mit der Amortisation aus dem Vergleich
(ohne zusätzliche direkte Amortisation bzw. mit der grössten möglichen):
- Zinsen nach Steuern: abziehbar nur noch der vermietete Anteil, wenn der Eigenmietwert weggefallen ist.
- Übrige Wirkung des Systemwechsels (Eigenmietwert und Unterhaltsabzug fallen weg) – gleich für alle Zinssätze.
- Mehrkosten pro Monat gegenüber heute und was vom geplanten Sparen (`personen[].sparen_monat`) bleibt.
- Tragbarkeit zum jeweiligen Zins mit heutigen Löhnen (plus 80 % der Mieteinnahmen) und 1 % Unterhalt.
- Schmerzgrenze: Zins, bei dem das Sparen ohne zusätzliche Amortisation auf null fällt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

ZINSEN = (2.0, 3.0, 4.0, 5.0, 6.0)


@dataclass
class Zeile:
    zins: float
    direkt: float
    rest: float
    netto_jahr: float           # Zinsen nach Steuern pro Jahr
    mehr_monat: float           # gegenüber heute, inkl. übriger Wirkung des Systemwechsels
    bleibt_monat: float         # Sparen pro Monat danach
    tragbarkeit: float          # %


@dataclass
class Risiko:
    faellig: date
    hypothek_heute: float
    zins_heute: float
    netto_heute: float          # pro Jahr
    sparen_monat: float
    systemwechsel: float        # übrige Steuerwirkung pro Jahr (+ = mehr Steuern)
    zeilen: list[Zeile]
    schmerzgrenze: float | None
    schmerzgrenze_direkt: float | None
    direkt_max: float
    hinweise: list[str] = field(default_factory=list)


def _chf(v: float) -> str:
    from tausender import TS
    return f"CHF {v:,.0f}" >> TS


def rechnen(k: dict, db, heute: date | None = None) -> Risiko | None:
    import amortisation as am
    import steuern as st
    import vermoegen as vm
    import wohnen as wo
    heute = heute or date.today()
    w = k.get("wohnen") or {}
    if not w.get("aktiv"):
        return None
    basis = am.vergleich(k, db, zins=ZINSEN[0], heute=heute)
    if not basis:
        return None
    hyp_konten = [x for x in vm.konten(db) if x["art"] == "hypothek" and not x.get("aufgeloest")]
    hyp_heute = -sum(x["wert"] for x in hyp_konten) if hyp_konten else basis.hypothek
    zins_heute = float(w.get("hypothek_zins") or 0)
    grenz = basis.grenz / 100                                           # Vergleich speichert %
    netto_heute = hyp_heute * zins_heute / 100 * (1 - grenz)          # heute noch voll abziehbar
    sparen = sum(float(p.get("sparen_monat") or 0) for p in k["personen"])
    abschaffung = int(float(k["kennzahlen"].get("eigenmietwert_abschaffung") or 2029))
    systemwechsel = 0.0
    if basis.faellig.year + 1 >= abschaffung:
        try:
            e = wo.eigenmietwert_wegfall(k)
            g = float(st.steuern_heute(k)["grenz_total"]) / 100
            systemwechsel = float(e["steuereffekt"]) - float(e["schuldzinsen"]) * (1 - float(e["zins_quote"]) / 100) * g
        except Exception:  # noqa: BLE001
            systemwechsel = 0.0
    t = wo.tragbarkeit(k, heute.year)
    einkommen = float(t.get("einkommen") or 0)
    wert = float((w.get("liegenschaft") or {}).get("marktwert") or w.get("kaufpreis") or 0)
    unterhalt = wert * 0.01
    direkt_max = basis.zeilen[-1].direkt if basis.zeilen else 0.0
    zeilen = []
    for z in ZINSEN:
        v = am.vergleich(k, db, zins=z, heute=heute)
        for r in ([v.zeilen[0], v.zeilen[-1]] if len(v.zeilen) > 1 else v.zeilen[:1]):
            mehr = (r.netto_zinsen - netto_heute + systemwechsel) / 12
            zeilen.append(Zeile(z, r.direkt, r.rest, round(r.netto_zinsen), round(mehr), round(sparen - mehr),
                                round((r.rest * z / 100 + unterhalt) / einkommen * 100, 1) if einkommen else 0.0))

    def grenze(rest: float) -> float | None:
        faktor = rest * (1 - grenz * basis.abzug) / 100
        if faktor <= 0:
            return None
        return max(0.0, (sparen * 12 + netto_heute - systemwechsel) / faktor)
    sg = grenze(basis.zeilen[0].rest)
    sg_d = grenze(basis.zeilen[-1].rest) if len(basis.zeilen) > 1 else None
    hinweise = []
    if sg is not None:
        hinweise.append(f"Schmerzgrenze ohne zusätzliche Amortisation: rund {sg:.1f} % – darüber reicht das geplante "
                        "Sparen nicht mehr für die Zinsen." + (f" Mit {_chf(direkt_max)} direkt amortisiert: "
                                                               f"{sg_d:.1f} %." if sg_d is not None else ""))
    if systemwechsel:
        hinweise.append(f"Ab {abschaffung} fallen Eigenmietwert und Unterhaltsabzug weg: übrige Steuerwirkung "
                        f"{'+' if systemwechsel > 0 else '−'}{_chf(abs(systemwechsel))} pro Jahr (in den Mehrkosten "
                        "enthalten); Schuldzinsen sind dann nur noch für den vermieteten Teil abziehbar.")
    hoch = [z for z in zeilen if z.direkt == 0 and z.tragbarkeit > float(k["kennzahlen"]["tragbarkeit_max"])]
    if hoch:
        hinweise.append(f"Ab {hoch[0].zins:.0f} % liegt die Tragbarkeit über {k['kennzahlen']['tragbarkeit_max']:.0f} % "
                        "– bei der Verlängerung kann die Bank dann eine Amortisation verlangen, auch wenn das Budget "
                        "noch reicht.")
    hinweise.append("Absichern: einen Teil früh fest verlängern (Forward-Festhypothek, siehe Rechner → Hypothek), "
                    "Reserve für ein bis zwei Jahre Mehrkosten halten, verpfändete Vorsorge und Liquidität für eine "
                    "Amortisation bei Bedarf bereithalten.")
    return Risiko(basis.faellig, round(hyp_heute), zins_heute, round(netto_heute), round(sparen), round(systemwechsel),
                  zeilen, None if sg is None else round(sg, 2), None if sg_d is None else round(sg_d, 2), direkt_max,
                  hinweise)
