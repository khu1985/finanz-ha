"""Kinder: Erfassung und Wirkung auf Steuern, AHV, Risiko, Nachlass, Krankenkasse und Fristen.

Pro Kind unter `haushalt.kinder[]`:
- name, geburtsdatum (JJJJ-MM-TT; ältere Konfigurationen mit `geburtsjahr` funktionieren weiter)
- eltern: «gemeinsam» oder Name einer Person (Kind aus einer früheren Beziehung)
- obhut: Person, die im Konkubinat Kinderabzug und Elterntarif geltend macht (leer = höheres Einkommen)
- gutschrift: AHV-Erziehungsgutschrift «hälftig» oder Name einer Person (Ehepaare immer hälftig)
- ausbildung_bis: Alter, bis zu dem das Kind unterhaltsberechtigt ist (18, in Ausbildung höchstens 25)
- betreuung_jahr, betreuung_bis: Kosten für Kita, Tagesstruktur o. Ä. pro Jahr und bis zu welchem Alter (ältere Form;
  sobald im Lebenslauf eigene Beträge je Phase stehen, zählen diese – siehe kinderphasen.py)
- zulage_monat: Kinder- bzw. Ausbildungszulage pro Monat (0 = Mindestansatz 215 bzw. 268)

Regeln (Stand 2025/2026):
- Kinderabzug Bund 6'800 pro Kind bis 18 bzw. in Ausbildung; Elterntarif 263 pro Kind; Abzug für Drittbetreuung
  bis 14 Jahre höchstens 25'800 (`kennzahlen.bund_kinderabzug`, `bund_betreuung_max`, `bund_betreuung_alter`).
  Kanton: `kennzahlen.kanton_kinderabzug` mit dem Grenzsteuersatz.
- AHV: Erziehungsgutschrift für Jahre mit Kindern unter 16; Waisen- und Kinderrenten bis 18, in Ausbildung bis 25.
- Kinderzulage bis 16, Ausbildungszulage 16 bis 25 (Mindestansätze des Bundes; viele Kantone zahlen mehr).
- Krankenkasse: Kinderprämie und -franchisen bis 18, junge Erwachsene 19 bis 25.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

STANDARD = {"name": "Kind", "nachname": "", "geburtsdatum": "", "eltern": "gemeinsam", "obhut": "", "gutschrift": "hälftig",
            "ausbildung_bis": 18, "betreuung_jahr": 0, "betreuung_bis": 12, "zulage_monat": 0}
ZULAGE_KIND, ZULAGE_AUSBILDUNG = 215, 268


def _zahl(v, std: float = 0.0) -> float:
    try:
        t = str(v).replace("'", "").replace(",", ".").strip()
        return float(t) if t else std
    except ValueError:
        return std


def liste(k: dict) -> list[dict]:
    erg = []
    for c in k["haushalt"].get("kinder") or []:
        c = {**STANDARD, **(c or {})}
        if not c.get("geburtsdatum") and c.get("geburtsjahr"):
            c["geburtsdatum"] = f"{int(c['geburtsjahr'])}-07-01"
        erg.append(c)
    return erg


def geburt(kind: dict) -> date | None:
    t = str(kind.get("geburtsdatum") or "").strip()
    if not t and kind.get("geburtsjahr"):
        return date(int(kind["geburtsjahr"]), 7, 1)
    try:
        return date.fromisoformat(t[:10])
    except ValueError:
        try:
            tag, monat, jahr = t.split(".")[:3]
            return date(int(jahr), int(monat), int(tag))
        except (ValueError, TypeError):
            return date(int(t[:4]), 7, 1) if t[:4].isdigit() else None


def geburtsjahr(kind: dict) -> int:
    g = geburt(kind)
    return g.year if g else 0


def alter(kind: dict, jahr: int) -> int:
    """Alter, das das Kind im Jahr erreicht."""
    gj = geburtsjahr(kind)
    return jahr - gj if gj else -1


def ausbildung_bis(kind: dict) -> int:
    return int(min(25, max(18, _zahl(kind.get("ausbildung_bis"), 18))))


def unterhalt(kind: dict, jahr: int) -> bool:
    """Kinderabzug, Waisen- und Kinderrenten: geboren und jünger als das Ausbildungsende."""
    a = alter(kind, jahr)
    return 0 <= a < ausbildung_bis(kind)


def von_person(kind: dict, person: str) -> bool:
    e = str(kind.get("eltern") or "gemeinsam").strip()
    return e.lower() in ("gemeinsam", "", "beide") or e == person


def eigene(k: dict, person: str) -> list[dict]:
    return [c for c in liste(k) if von_person(c, person)]


def anzahl(k: dict, jahr: int | None = None, person: str | None = None) -> int:
    """Kinder mit Kinderabzug im Jahr (minderjährig oder in Ausbildung)."""
    jahr = jahr or date.today().year
    kinder = eigene(k, person) if person else liste(k)
    return sum(1 for c in kinder if unterhalt(c, jahr))


def obhut(k: dict, kind: dict) -> str:
    """Person mit Kinderabzug und Elterntarif im Konkubinat."""
    o = str(kind.get("obhut") or "").strip()
    namen = [p["name"] for p in k["personen"]]
    if o in namen:
        return o
    e = str(kind.get("eltern") or "").strip()
    if e in namen:
        return e
    return max(k["personen"], key=lambda p: _zahl(p.get("lohn_brutto", 0)))["name"]


def anzahl_obhut(k: dict, person: str, jahr: int | None = None) -> int:
    jahr = jahr or date.today().year
    return sum(1 for c in liste(k) if unterhalt(c, jahr) and obhut(k, c) == person)


def gutschrift_anteil(k: dict, kind: dict, person: str) -> float:
    """Anteil der AHV-Erziehungsgutschrift dieser Person für dieses Kind."""
    if not von_person(kind, person):
        return 0.0
    verheiratet = k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet" and len(k["personen"]) >= 2
    e = str(kind.get("eltern") or "gemeinsam").strip()
    if e not in ("gemeinsam", "", "beide"):
        return 0.5 if verheiratet else 1.0      # eigenes Kind: allein bzw. in der Ehe hälftig mit dem Ehegatten
    if verheiratet:
        return 0.5
    g = str(kind.get("gutschrift") or "hälftig").strip()
    if g in [p["name"] for p in k["personen"]]:
        return 1.0 if g == person else 0.0
    return 0.5


def zulage_jahr(kind: dict, jahr: int) -> float:
    a = alter(kind, jahr)
    if a < 0 or a >= 25 or (a >= 16 and a >= ausbildung_bis(kind)):
        return 0.0
    eigen = _zahl(kind.get("zulage_monat"))
    if eigen:
        betrag = eigen if a < 16 else max(eigen, ZULAGE_AUSBILDUNG)
    else:
        betrag = ZULAGE_KIND if a < 16 else ZULAGE_AUSBILDUNG
    return betrag * 12


def betreuung_jahr(kind: dict, jahr: int) -> float:
    """Kita, Tagesstruktur o. Ä.: aus dem Lebenslauf (eigene Beträge je Phase), sonst Betrag pro Jahr bis zum Alter."""
    import kinderphasen as kp
    aus_lauf = kp.betreuung_jahr(kind, jahr)
    if aus_lauf is not None:
        return aus_lauf
    a = alter(kind, jahr)
    if a < 0 or a >= _zahl(kind.get("betreuung_bis"), 12):
        return 0.0
    return _zahl(kind.get("betreuung_jahr"))


@dataclass
class Jahr:
    jahr: int
    kinder: int                      # mit Kinderabzug
    alter: dict[str, int]
    zulagen: float
    betreuung: float
    abzug_betreuung_bund: float
    steuer_kinder: float             # Steuerersparnis aus Kinderabzug, Betreuungsabzug und Elterntarif (Schätzung)


@dataclass
class Uebersicht:
    jahre: list[Jahr]
    ende_jahr: int | None            # letztes Jahr mit Kinderabzug
    steuer_heute: float
    hinweise: list[str] = field(default_factory=list)


def _grenz_bund(k: dict) -> float:
    import steuern as st
    try:
        s = st.steuern_heute(k)
        return max((e.get("grenz_bund", 0) for e in s["einheiten"]), default=0) / 100
    except Exception:  # noqa: BLE001
        return 0.08


def _grenz_kanton(k: dict) -> float:
    st_ = k.get("steuern") or {}
    werte = [_zahl(e.get("grenzsteuersatz_kanton")) for e in st_.get("personen") or []] or [_zahl(st_.get("grenzsteuersatz_kanton"))]
    return max(werte) / 100


def uebersicht(k: dict, heute: date | None = None, jahre: int = 30) -> Uebersicht:
    heute = heute or date.today()
    kz = k["kennzahlen"]
    kinder = liste(k)
    abzug_bund = _zahl(kz.get("bund_kinderabzug"), 6800)
    abzug_kanton = _zahl(kz.get("kanton_kinderabzug"))
    bet_max = _zahl(kz.get("bund_betreuung_max"), 25800)
    bet_alter = int(_zahl(kz.get("bund_betreuung_alter"), 14))
    elterntarif = _zahl(kz.get("bund_elterntarif_kind"), 263)
    gb, gk = _grenz_bund(k), _grenz_kanton(k)
    erg = []
    ende = None
    for j in range(heute.year, heute.year + jahre):
        n = sum(1 for c in kinder if unterhalt(c, j))
        zul = sum(zulage_jahr(c, j) for c in kinder)
        bet = sum(betreuung_jahr(c, j) for c in kinder)
        abz_bet = sum(min(bet_max, betreuung_jahr(c, j)) for c in kinder if alter(c, j) < bet_alter)
        steuer = n * (abzug_bund * gb + abzug_kanton * gk + elterntarif) + abz_bet * (gb + gk)
        if n:
            ende = j
        if not n and not zul and not bet and j > heute.year + 1 and ende is not None and j > ende + 1:
            break
        erg.append(Jahr(j, n, {c["name"]: alter(c, j) for c in kinder if 0 <= alter(c, j) < 30}, round(zul), round(bet),
                        round(abz_bet), round(steuer)))
    hinw = []
    verheiratet = k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet"
    if kinder and not verheiratet and len(k["personen"]) >= 2:
        hinw.append("Konkubinat: Kinderabzug beim Bund je hälftig bei gemeinsamer Sorge; den Elterntarif erhält, wer das Kind "
                    "überwiegend unterhält (meist das höhere Einkommen). Unter «Obhut» festlegen – die Steuern rechnen danach.")
        if any(str(c.get("gutschrift") or "hälftig") == "hälftig" for c in kinder):
            hinw.append("AHV-Erziehungsgutschriften bei gemeinsamer Sorge: hälftig, wenn nichts anderes vereinbart ist. "
                        "Eine Vereinbarung zugunsten des Elternteils mit dem tieferen Einkommen erhöht dessen Rente.")
    if not abzug_kanton and kinder:
        hinw.append("Kantonaler Kinderabzug fehlt (kennzahlen.kanton_kinderabzug) – die Steuerwirkung zählt nur den Bund.")
    if ende is not None and ende >= heute.year:
        steuer_ende = erg[0].steuer_kinder if erg else 0
        hinw.append(f"Ab {ende + 1} fällt der letzte Kinderabzug weg – die Steuern steigen um rund CHF "
                    f"{_chf(steuer_ende)} pro Jahr gegenüber heute (Kinderabzüge, Betreuung, Elterntarif).")
    for c in kinder:
        bis = ausbildung_bis(c)
        a = alter(c, heute.year)
        if 15 <= a < 18 and bis == 18:
            hinw.append(f"{c['name']}: Bei einer Ausbildung nach 18 «Ausbildung bis» auf das erwartete Ende setzen "
                        "(höchstens 25) – Kinderabzug, Ausbildungszulage und Waisenrenten laufen weiter.")
    return Uebersicht(erg, ende, erg[0].steuer_kinder if erg else 0, hinw)


def erinnerungen(k: dict, heute: date | None = None) -> list:
    from erinnerungen import Erinnerung

    heute = heute or date.today()
    erg = []
    for c in liste(k):
        g = geburt(c)
        if not g:
            continue
        n = c["name"]

        def am(alter_: int) -> date:
            try:
                return g.replace(year=g.year + alter_)
            except ValueError:
                return date(g.year + alter_, 2, 28)
        punkte = [
            (16, "Ausbildungszulage beantragen",
             "Ab 16 ersetzt die Ausbildungszulage die Kinderzulage – Ausbildungsbestätigung beim Arbeitgeber bzw. der "
             "Familienausgleichskasse einreichen."),
            (18, "Volljährigkeit: Ausbildung bestätigen",
             "Kinderabzug, Ausbildungszulage und Waisenrenten laufen nur mit Ausbildung weiter – Bestätigung bereithalten; "
             "«Ausbildung bis» in der App prüfen."),
            (19, "Krankenkasse: junge Erwachsene",
             "Ab dem Jahr, in dem das Kind 19 wird, gelten Prämien für junge Erwachsene und die Franchisen der Erwachsenen – "
             "Franchise wählen (unter «Versicherungen» vergleichen)."),
            (ausbildung_bis(c), "Ende Kinderabzug und Zulagen",
             "Kinderabzug, Ausbildungszulage, Waisen- und Kinderrenten enden – Budget, Steuern und Risikoschutz anpassen."),
        ]
        for alter_, titel, text in punkte:
            faellig = date(g.year + alter_, 1, 1) if alter_ == 19 else am(alter_)
            if heute <= faellig <= date(heute.year + 1, 12, 31) and (faellig - heute).days <= 120:
                erg.append(Erinnerung(f"kind-{n}-{alter_}-{titel}", f"{titel} – {n}", faellig, text, "kinder"))
    return erg


def _chf(v: float) -> str:
    return f"{v:,.0f}".replace(",", "'")
