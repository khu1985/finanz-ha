"""Pflegefall im Alter: Was kostet ein Pflegeheim, wie lange reicht das Vermögen, ab wann helfen Ergänzungsleistungen?

Annahmen (`pflege`, alles in heutigen Franken pro Person):
- Heimtaxe für Hotellerie und Betreuung `taxe_tag` (Standard 190), Eigenanteil Pflege `pflege_tag` (23: höchstens 20 %
  des höchsten Krankenkassenbeitrags, KVG Art. 25a), persönliche Auslagen `auslagen_monat` (400).
- Eintritt mit `eintritt_alter` (85), Dauer `dauer_jahre` (3).
- Hilflosenentschädigung der AHV je nach Grad (`hilflosigkeit`: mittel 50 %, schwer 80 % der AHV-Minimalrente,
  AHVG Art. 43bis; leichter Grad nur zu Hause) – unabhängig von Einkommen und Vermögen.
- Renten im Eintrittsjahr und Vermögen der Person aus dem Entnahmeplan («wie eingestellt»).
- Ergänzungsleistungen (ELG): nur unter der Vermögensschwelle (`el_schwelle` 100'000, Ehepaare 200'000); dabei zählt
  die selbst bewohnte Liegenschaft nicht – im Heim gilt das nur, solange der Ehegatte darin wohnt. Im Konkubinat zählt
  der Hausanteil der Person im Heim deshalb voraussichtlich mit. Vermögensverzehr im Heim (BL) `verzehr_heim` 10 %
  über dem Freibetrag (30'000 bzw. 50'000); Heimtaxe in der EL höchstens `taxe_el_max` (160 pro Tag, BL 2025).

Vereinfachte Übersicht, keine Rechtsberatung – Taxen je Heim und EL-Berechnung bei der SVA Baselland prüfen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

STANDARD = {
    "taxe_tag": 190, "pflege_tag": 23, "auslagen_monat": 400, "eintritt_alter": 85, "dauer_jahre": 3,
    "hilflosigkeit": "mittel", "el_schwelle": 100_000, "el_schwelle_paar": 200_000, "freibetrag": 30_000,
    "freibetrag_paar": 50_000, "verzehr_heim": 10, "taxe_el_max": 160,
}
HE_ANTEIL = {"keine": 0.0, "leicht": 0.0, "mittel": 0.5, "schwer": 0.8}   # im Heim: leichter Grad ohne Anspruch


@dataclass
class Fall:
    person: str
    jahr: int
    alter: int
    kosten: float              # pro Jahr
    renten: float              # AHV + PK-Rente pro Jahr
    hilflosen: float           # pro Jahr
    luecke: float              # pro Jahr (Kosten − Renten − Hilflosenentschädigung)
    vermoegen: float           # freies Vermögen der Person bei Eintritt
    hausanteil: float          # Anteil am Haus nach Hypothek (heute)
    haus_zaehlt: bool          # zählt für die EL-Schwelle
    jahre_gedeckt: float | None   # None = Renten decken die Kosten
    dauer: int
    kosten_dauer: float        # Lücke über die angenommene Dauer
    el_ab: float | None        # nach so vielen Jahren unter der EL-Schwelle (None = nie bzw. Haus zählt)
    hinweise: list[str] = field(default_factory=list)


def konfiguration(k: dict) -> dict:
    return STANDARD | (k.get("pflege") or {})


def _hausanteil(k: dict, db, person: str) -> float:
    w = k.get("wohnen") or {}
    if not w.get("aktiv"):
        return 0.0
    import vermoegen as vm
    import wohnen as wo
    wert = float((w.get("liegenschaft") or {}).get("marktwert") or w.get("kaufpreis") or 0)
    hyp = -sum(x["wert"] for x in vm.konten(db) if x["art"] == "hypothek" and not x.get("aufgeloest"))
    anteil = wo.eigentum_anteile(k).get(person, 0.0) / 100
    return max(0.0, (wert - hyp) * anteil)


def rechnen(k: dict, db, jetzt: int | None = None) -> list[Fall]:
    import entnahme as en
    import steuern as st
    import vorsorge as vs
    jetzt = jetzt or date.today().year
    c = konfiguration(k)
    verheiratet = k["haushalt"].get("zivilstand", "verheiratet") == "verheiratet" and len(k["personen"]) > 1
    try:
        plan = en.rechnen(k, db, jetzt)
        eingestellt = next((v for v in plan.varianten if v.schluessel == "eingestellt"), None) if plan else None
    except Exception:  # noqa: BLE001
        eingestellt = None
    ahv = {r.name: r for r in vs.ahv(k, jetzt)}
    he = HE_ANTEIL.get(str(c["hilflosigkeit"]), 0.5) * float(k["kennzahlen"].get("ahv_min", 1260)) * 12
    kosten = (float(c["taxe_tag"]) + float(c["pflege_tag"])) * 365 + float(c["auslagen_monat"]) * 12
    dauer = int(c["dauer_jahre"])
    erg = []
    for p in k["personen"]:
        jahr = vs.geburtsjahr(p) + int(c["eintritt_alter"])
        renten = 0.0
        if p["name"] in ahv:
            renten += ahv[p["name"]].rente_jahr * vs.ahv_real_faktor(k, jahr - jetzt)
        pk_e = vs.pk(p, k)
        renten += pk_e.rente_jahr * vs.kaufkraft(k, jahr - jetzt)
        luecke = max(0.0, kosten - renten - he)
        # Vermögen bei Eintritt: aus dem Entnahmeplan; im Ehepaar die Hälfte des gemeinsamen
        vermoegen = 0.0
        if eingestellt:
            e = st.einheit_von(k, p["name"])
            zeile = next((z for z in eingestellt.jahre.get(e.name, []) if z.jahr == jahr), None)
            if zeile is None and eingestellt.jahre.get(e.name):
                zeile = eingestellt.jahre[e.name][-1] if eingestellt.jahre[e.name][-1].jahr < jahr else None
            if zeile:
                vermoegen = zeile.vermoegen / len(e.personen)
        haus = _hausanteil(k, db, p["name"])
        haus_zaehlt = haus > 0 and not verheiratet
        schwelle = float(c["el_schwelle_paar"] if verheiratet else c["el_schwelle"])
        jahre = None if luecke <= 0 else vermoegen / luecke
        el_ab = None
        if luecke > 0 and not haus_zaehlt:
            el_ab = max(0.0, (vermoegen - schwelle) / luecke)
        hinweise = []
        if haus_zaehlt:
            hinweise.append(f"Hausanteil rund {_chf(haus)} zählt für die EL mit (Konkubinat): vor EL müsste der "
                            "Anteil verkauft oder belehnt werden – der Partner bräuchte Geld oder ein Wohnrecht.")
        if luecke <= 0:
            hinweise.append("Renten und Hilflosenentschädigung decken die Heimkosten.")
        erg.append(Fall(p["name"], jahr, int(c["eintritt_alter"]), round(kosten), round(renten), round(he),
                        round(luecke), round(vermoegen), round(haus), haus_zaehlt,
                        None if jahre is None else round(jahre, 1), dauer, round(luecke * dauer),
                        None if el_ab is None else round(el_ab, 1), hinweise))
    return erg


def _chf(v: float) -> str:
    from tausender import TS
    return f"CHF {v:,.0f}" >> TS


def massnahmen(k: dict) -> list[str]:
    konk = k["haushalt"].get("zivilstand", "verheiratet") != "verheiratet" and len(k["personen"]) > 1
    m = ["Vorsorgeauftrag und Patientenverfügung: wer entscheidet über Heimeintritt, Konten und Haus?",
         "Schenkungen und Erbvorbezüge zählen bei den Ergänzungsleistungen als Vermögensverzicht weiter mit "
         "(abnehmend um CHF 10'000 pro Jahr) – grosse Schenkungen vorher durchrechnen.",
         "Bezogene Ergänzungsleistungen zahlen die Erben aus dem Nachlass über CHF 40'000 zurück (ELG Art. 16a).",
         "Hilflosenentschädigung früh beantragen (nach 1 Jahr Hilfsbedürftigkeit), sie hängt nicht vom Vermögen ab.",
         "Private Pflegeversicherung oder Pflegekapital nur, wenn die Lücke das Vermögen übersteigt – oft genügt "
         "ein Teil des Vermögens als «Pflegereserve»."]
    if konk:
        m.insert(0, "Konkubinat: Wohnrecht oder Nutzniessung am Hausanteil im Testament bzw. Konkubinatsvertrag, damit "
                    "der Partner im Haus bleiben kann, wenn der Anteil für Heimkosten gebraucht wird.")
    return m
