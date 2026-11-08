"""HTML-Seiten der App (serverseitig gerendert, ohne JavaScript-Framework)."""
from __future__ import annotations

from datetime import date
from html import escape

import yaml

import diagramme as dg
import steuern as st
import vermoegen as vm
import vorsorge as vs
import wohnen as wo

NAV = [("", "Übersicht"), ("vorsorge", "Vorsorge"), ("steuern", "Steuern"), ("wohnen", "Wohnen"),
       ("vermoegen", "Vermögen"), ("einstellungen", "Einstellungen")]

CSS = """
:root{--bg:#f6f7f9;--karte:#fff;--text:#1c2430;--leise:#5d6b7a;--linie:#e3e7ec;--akzent:#0a708f;
--gut:#2e7d4f;--warn:#b26a00;--schlecht:#b3261e;--c1:#0a708f;--c2:#e08a2e;--c3:#6b8f3a;--c4:#8a5bb5;--c5:#c2457a}
@media (prefers-color-scheme:dark){:root{--bg:#111418;--karte:#1b2027;--text:#e7ebef;--leise:#9aa7b4;
--linie:#2b323b;--akzent:#4fb3d4;--gut:#6cc58f;--warn:#e7a948;--schlecht:#f08a82;--c1:#4fb3d4;--c2:#f0a75a;
--c3:#9cc46a;--c4:#b48be0;--c5:#e57aa8}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--karte);border-bottom:1px solid var(--linie)}
nav{display:flex;gap:4px;overflow-x:auto;padding:8px 16px;max-width:1100px;margin:0 auto}
nav a{padding:6px 12px;border-radius:999px;color:var(--leise);text-decoration:none;white-space:nowrap}
nav a.aktiv{background:var(--akzent);color:#fff}
main{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:4px 0 16px}h2{font-size:17px;margin:0 0 12px}
.raster{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr))}
.karte{background:var(--karte);border:1px solid var(--linie);border-radius:12px;padding:16px;margin-bottom:16px}
.kpis{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:16px}
.kpi{background:var(--karte);border:1px solid var(--linie);border-radius:12px;padding:12px 14px}
.kpi b{display:block;font-size:22px;font-variant-numeric:tabular-nums}.kpi span{color:var(--leise);font-size:13px}
.gut{color:var(--gut)}.warn{color:var(--warn)}.schlecht{color:var(--schlecht)}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--linie);text-align:left}
td.z,th.z{text-align:right}th{color:var(--leise);font-weight:600;font-size:13px}
.tab{overflow-x:auto}
.diagramm{margin:0}.diagramm svg{width:100%;height:auto;display:block}
.gitter{stroke:var(--linie)}.achse{fill:var(--leise);font-size:11px}
.ziel{stroke:var(--schlecht);stroke-dasharray:5 4;stroke-width:1.5}.ziel-text{fill:var(--schlecht)}
.legende{display:flex;flex-wrap:wrap;gap:12px;font-size:13px;color:var(--leise);margin-top:6px}
.leg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.hinweise{margin:0;padding-left:18px}.hinweise li{margin:4px 0}
.leise{color:var(--leise);font-size:13px}.leer{color:var(--leise)}
form .felder{display:grid;gap:10px 16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr))}
label{display:flex;flex-direction:column;font-size:13px;color:var(--leise);gap:4px}
input,select,textarea{font:inherit;color:var(--text);background:var(--bg);border:1px solid var(--linie);
border-radius:8px;padding:8px 10px;width:100%}
textarea{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;min-height:420px}
button,.knopf{font:inherit;background:var(--akzent);color:#fff;border:0;border-radius:8px;padding:8px 16px;
cursor:pointer;text-decoration:none;display:inline-block}
.knopf.zweit,button.zweit{background:transparent;color:var(--akzent);border:1px solid var(--akzent)}
button.klein{padding:2px 10px;font-size:13px}
.zeile{display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-top:12px}
.meldung{padding:10px 14px;border-radius:8px;margin-bottom:16px;background:var(--karte);border-left:4px solid var(--akzent)}
.meldung.fehler{border-color:var(--schlecht)}
details summary{cursor:pointer;color:var(--akzent)}
"""


def chf(v: float, vorzeichen: bool = False) -> str:
    s = f"{abs(v):,.0f}".replace(",", "'")
    if v < 0:
        return "−" + s
    return ("+" if vorzeichen and v > 0 else "") + s


def seite(titel: str, pfad: str, inhalt: str, basis: str = "", meldung: str = "", fehler: bool = False) -> str:
    nav = "".join(
        f'<a href="{p or "./"}" class="{"aktiv" if p == pfad else ""}">{n}</a>' for p, n in NAV)
    m = f'<div class="meldung{" fehler" if fehler else ""}">{escape(meldung)}</div>' if meldung else ""
    return f"""<!doctype html><html lang="de-CH"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><base href="{escape(basis)}/">
<title>{escape(titel)} – Finanzplanung</title><style>{CSS}</style></head>
<body><header><nav>{nav}</nav></header><main><h1>{escape(titel)}</h1>{m}{inhalt}</main></body></html>"""


def kpi(wert: str, text: str, klasse: str = "") -> str:
    return f'<div class="kpi"><b class="{klasse}">{wert}</b><span>{escape(text)}</span></div>'


def karte(titel: str, inhalt: str) -> str:
    return f'<section class="karte"><h2>{escape(titel)}</h2>{inhalt}</section>'


def tabelle(kopf: list[str], zeilen: list[list], zahlen_ab: int = 1) -> str:
    th = "".join(f'<th class="{"z" if i >= zahlen_ab else ""}">{escape(h)}</th>' for i, h in enumerate(kopf))
    tr = []
    for z in zeilen:
        tds = "".join(f'<td class="{"z" if i >= zahlen_ab else ""}">{c}</td>' for i, c in enumerate(z))
        tr.append(f"<tr>{tds}</tr>")
    return f'<div class="tab"><table><thead><tr>{th}</tr></thead><tbody>{"".join(tr)}</tbody></table></div>'


def hinweisliste(punkte: list[str]) -> str:
    if not punkte:
        return '<p class="gut">Keine Auffälligkeiten.</p>'
    return '<ul class="hinweise">' + "".join(f"<li>{escape(p)}</li>" for p in punkte) + "</ul>"


# ---------------------------------------------------------------- Übersicht

def uebersicht(k: dict, db) -> str:
    jetzt = date.today().year
    nv = vm.nettovermoegen(db)
    luecke = vs.pensionsluecke(k, nv["frei"], jetzt)
    steuer = st.steuern_heute(k)
    pks = [vs.pk(p, k) for p in k["personen"]]
    drei = [vs.saeule3a(p, k, jetzt) for p in k["personen"]]
    kap = st.kapitalbezug_varianten(k, pks, drei)

    # Steuerpotenzial: 3a ausschöpfen + nächster Einkauf (höchstens Potenzial, max. 20'000 als Beispiel)
    kz = k["kennzahlen"]
    offen_3a = sum(max(0.0, kz["saeule3a_max"] - float(p["saeule3a"].get("beitrag_jahr", 0)))
                   for p in k["personen"] if float(p.get("lohn_brutto", 0)) > 0)
    pot_3a = st.ersparnis_abzug(k, offen_3a)["total"] if offen_3a else 0

    hinweise = []
    for e in pks:
        hinweise += e.warnungen
    for d in drei:
        hinweise += d.hinweise
    if kap["ersparnis"] > 1000:
        hinweise.append(f"Gestaffelter Kapitalbezug spart rund CHF {chf(kap['ersparnis'])} Steuern (siehe «Steuern»).")
    if k["wohnen"].get("aktiv"):
        hinweise += wo.tragbarkeit(k, jetzt)["pruefungen"]
    if luecke.luecke > 0:
        hinweise.append(f"Pensionslücke von CHF {chf(luecke.luecke)} pro Jahr ab {luecke.jahr}.")

    kpis = "".join([
        kpi(chf(nv["total"]), "Nettovermögen (CHF)"),
        kpi(chf(luecke.einkommen), f"Einkommen im Ruhestand ab {luecke.jahr} (CHF/Jahr)"),
        kpi(chf(-luecke.luecke) if luecke.luecke else "keine", "Pensionslücke (CHF/Jahr)",
            "schlecht" if luecke.luecke else "gut"),
        kpi(f"{luecke.ersatzquote:.0f} %", "Ersatzquote zum heutigen Lohn"),
        kpi(chf(steuer["total"]), f"Steuern pro Jahr · Grenzsatz {steuer['grenz_total']:.0f} %"),
        kpi(chf(pot_3a), "Mögliche Ersparnis 3a (CHF/Jahr)", "gut" if pot_3a else ""),
    ])
    verl = vm.verlauf(db)
    return kpis + '<div class="raster">' + karte("Hinweise", hinweisliste(hinweise)) + karte(
        "Nettovermögen", dg.linie({"Nettovermögen": verl}, "Nettovermögen")
        + '<p class="leise">Saldi unter «Vermögen» erfassen oder als CSV importieren.</p>') + "</div>" + karte(
        "Ruhestand: Einkommen und Bedarf", _luecke_diagramm(luecke))


def _luecke_diagramm(l: vs.Luecke) -> str:
    return dg.saeulen(["Heute (Lohn)", f"Ruhestand {l.jahr}"],
                      {"AHV": [0, l.ahv], "Pensionskasse": [0, l.pk_rente],
                       "Kapitalverzehr": [0, l.kapitalverzehr], "Lohn": [l.lohn_heute, 0]},
                      linie_bei=l.bedarf, linie_text=f"Bedarf {chf(l.bedarf)}")


# ---------------------------------------------------------------- Vorsorge

def vorsorge(k: dict, db) -> str:
    jetzt = date.today().year
    kz = k["kennzahlen"]
    ahv = vs.ahv(k, jetzt)
    pks = [vs.pk(p, k) for p in k["personen"]]
    drei = [vs.saeule3a(p, k, jetzt) for p in k["personen"]]
    luecke = vs.pensionsluecke(k, vm.nettovermoegen(db)["frei"], jetzt)

    zeilen_ahv = [[escape(r.name), r.alter, r.beitragsjahre, r.erziehungsjahre, chf(r.einkommen),
                   chf(r.rente_monat), chf(r.rente_monat_plafoniert), chf(r.rente_jahr)] for r in ahv]
    monate = 13 if kz.get("ahv_13_rente") else 12
    ahv_html = tabelle(["Person", "Alter", "Beitragsjahre", "Erz.-Jahre", "Ø Einkommen", "Rente/Mt.",
                        "plafoniert", f"pro Jahr (×{monate})"], zeilen_ahv) + (
        f'<p class="leise">Rentenskala 44, Einkommenssplitting und Erziehungsgutschriften vereinfacht. '
        f'Plafond Ehepaar: CHF {chf(kz["ahv_max"] * kz["ahv_plafond_ehepaar"] / 100)}/Monat. '
        f'Den genauen Wert liefert der IK-Auszug bzw. die Rentenvorausberechnung der Ausgleichskasse.</p>')

    zeilen_pk = []
    for p, e in zip(k["personen"], pks):
        zeilen_pk.append([escape(e.name), vs.pensionsjahr(p), chf(e.guthaben_pensionierung), chf(e.einkaeufe),
                          chf(e.kapital), chf(e.rente_jahr)])
    pk_html = tabelle(["Person", "Pension", "Altersguthaben", "Einkäufe", "Kapital", "Rente/Jahr"], zeilen_pk)
    pk_html += dg.linie({e.name: e.verlauf for e in pks}, "Altersguthaben")

    zeilen_3a = [[escape(d.name), chf(d.beitrag), chf(d.kapital)] for d in drei]
    ersparnis = st.ersparnis_abzug(k, sum(d.beitrag for d in drei))
    drei_html = tabelle(["Person", "Beitrag/Jahr", "Kapital bei Pensionierung"], zeilen_3a) + (
        f'<p>Steuerersparnis der heutigen 3a-Beiträge: <b>CHF {chf(ersparnis["total"])}</b> pro Jahr '
        f'(Bund {chf(ersparnis["bund"])}, Kanton/Gemeinde {chf(ersparnis["kanton"])}).</p>')

    lk = luecke
    luecke_html = tabelle(["Position", f"CHF/Jahr ab {lk.jahr}"], [
        ["AHV (beide, plafoniert)", chf(lk.ahv)],
        ["Pensionskassen-Renten", chf(lk.pk_rente)],
        [f"Kapitalverzehr ({k['haushalt']['entnahme_jahre']} Jahre, {k['haushalt']['entnahme_rendite']} %) "
         f"aus CHF {chf(lk.kapital_netto)} netto", chf(lk.kapitalverzehr)],
        ["<b>Einkommen total</b>", f"<b>{chf(lk.einkommen)}</b>"],
        ["Bedarf", chf(lk.bedarf)],
        ["<b>Lücke</b>", f'<b class="{"schlecht" if lk.luecke else "gut"}">{chf(lk.luecke)}</b>'],
    ]) + f'<p class="leise">Kapital nach Kapitalbezugssteuer von CHF {chf(lk.kapitalsteuer)} (gestaffelt), inkl. freiem Vermögen.</p>'

    return (karte("Pensionslücke", _luecke_diagramm(lk) + luecke_html)
            + karte("1. Säule – AHV", ahv_html)
            + karte("2. Säule – Pensionskasse", pk_html)
            + karte("Säule 3a", drei_html + dg.linie({d.name: d.verlauf for d in drei}, "3a")))


# ---------------------------------------------------------------- Steuern

def steuern(k: dict, db) -> str:
    jetzt = date.today().year
    s = st.steuern_heute(k)
    kz = k["kennzahlen"]
    heute = "".join([
        kpi(chf(s["bund"]), "Direkte Bundessteuer"),
        kpi(chf(s["kanton"]), "Staats- und Gemeindesteuer"),
        kpi(chf(s["total"]), f"Total · effektiv {s['effektiv']:.1f} %"),
        kpi(f"{s['grenz_total']:.1f} %", f"Grenzsteuersatz (Bund {s['grenz_bund']:.1f} %)"),
    ])
    # Abzüge simulieren
    zeilen = []
    for p in k["personen"]:
        pot = float(p["pk"].get("einkauf_potenzial", 0) or 0)
        for betrag in sorted({10000, 20000, round(pot)} - {0}):
            if betrag <= pot:
                e = st.ersparnis_abzug(k, betrag)
                zeilen.append([f"PK-Einkauf {escape(p['name'])}", chf(betrag), chf(e["total"]),
                               f"{e['total'] / betrag * 100:.0f} %"])
    e3 = st.ersparnis_abzug(k, kz["saeule3a_max"])
    zeilen.insert(0, ["3a-Maximalbeitrag (eine Person)", chf(kz["saeule3a_max"]), chf(e3["total"]),
                      f"{e3['total'] / kz['saeule3a_max'] * 100:.0f} %"])
    abzuege = tabelle(["Massnahme", "Abzug", "Ersparnis", "in % des Abzugs"], zeilen) + (
        '<p class="leise">PK-Einkäufe auf mehrere Jahre verteilen glättet die Progression. '
        'In den 3 Jahren vor einem Kapitalbezug sind Einkäufe steuerlich heikel.</p>')

    pks = [vs.pk(p, k) for p in k["personen"]]
    drei = [vs.saeule3a(p, k, jetzt) for p in k["personen"]]
    kap = st.kapitalbezug_varianten(k, pks, drei)

    def plan(v):
        z = [[j, chf(b), chf(t["bund"]), chf(t["kanton"]), chf(t["total"])] for j, b, t in v["zeilen"]]
        z.append(["<b>Total</b>", "", "", "", f"<b>{chf(v['steuer_total'])}</b>"])
        return tabelle(["Jahr", "Bezug", "Bund", "Kanton", "Steuer"], z)

    kap_html = (f'<p>Ersparnis durch Staffelung: <b class="gut">CHF {chf(kap["ersparnis"])}</b></p>'
                '<div class="raster"><div><h2>Alles im Pensionsjahr</h2>' + plan(kap["alles_auf_einmal"])
                + '</div><div><h2>3a-Konten gestaffelt</h2>' + plan(kap["gestaffelt"]) + "</div></div>"
                '<p class="leise">Bund: ein Fünftel des ordentlichen Tarifs. Kanton: effektiver Satz aus der Tabelle '
                'unter Einstellungen (Schätzung – mit dem kantonalen Rechner prüfen). Ehepaare werden pro Jahr addiert.</p>')
    return heute.join(['<div class="kpis">', '</div>']) + karte("Abzüge simulieren", abzuege) + karte(
        "Kapitalbezug PK und 3a", kap_html)


# ---------------------------------------------------------------- Wohnen

def wohnen(k: dict, db) -> str:
    if not k["wohnen"].get("aktiv"):
        return karte("Wohneigentum", '<p>Unter «Einstellungen» → Wohnen aktivieren und Kaufpreis, '
                     'Eigenmittel und Zins erfassen.</p>')
    t = wo.tragbarkeit(k, date.today().year)
    e = wo.eigenmietwert_wegfall(k)
    kz = k["kennzahlen"]
    kl = "schlecht" if t["quote"] > kz["tragbarkeit_max"] else "gut"
    kpis = "".join([
        kpi(f"{t['quote']:.1f} %", f"Tragbarkeit (max. {kz['tragbarkeit_max']:.0f} %)", kl),
        kpi(f"{t['belehnung']:.0f} %", f"Belehnung (max. {kz['belehnung_max']} %)",
            "schlecht" if t["belehnung"] > kz["belehnung_max"] else "gut"),
        kpi(chf(t["effektiv_monat"]), "Effektive Kosten pro Monat"),
        kpi(chf(t["max_preis"]), "Maximal tragbarer Kaufpreis"),
    ])
    trag = tabelle(["Position", "CHF/Jahr"], [
        [f"Hypothek CHF {chf(t['hypothek'])} × {kz['tragbarkeit_zins']} % (kalkulatorisch)",
         chf(t["hypothek"] * kz["tragbarkeit_zins"] / 100)],
        ["Unterhalt und Nebenkosten", chf(t["unterhalt"])],
        [f"Amortisation 2. Hypothek CHF {chf(t['zweite'])} in {t['amort_jahre']} Jahren", chf(t["amortisation"])],
        ["<b>Kalkulatorische Kosten</b>", f"<b>{chf(t['kalk_kosten'])}</b>"],
        ["Bruttoeinkommen Haushalt", chf(t["einkommen"])],
    ]) + hinweisliste(t["pruefungen"])
    emw = tabelle(["Position", "CHF/Jahr"], [
        ["Eigenmietwert (heute steuerbar)", chf(e["eigenmietwert"])],
        ["− Schuldzinsen", chf(-e["schuldzinsen"])],
        ["− Unterhalt (Pauschale 20 %)", chf(-e["unterhalt"])],
        ["<b>Netto heute versteuert</b>", f"<b>{chf(e['netto_heute'])}</b>"],
        [f"Steuereffekt ab {e['ab']} (Grenzsatz)",
         f'<b class="{"schlecht" if e["steuereffekt"] > 0 else "gut"}">{chf(e["steuereffekt"], True)}</b>'],
    ]) + (f'<p class="leise">Ab {e["ab"]} entfallen Eigenmietwert, Schuldzins- und Unterhaltsabzug für selbst '
          'bewohntes Eigentum (Volksabstimmung vom 28.9.2025). Positiv = mehr Steuern.</p>')
    return f'<div class="kpis">{kpis}</div>' + '<div class="raster">' + karte("Tragbarkeit", trag) + karte(
        "Wegfall Eigenmietwert", emw) + "</div>"


# ---------------------------------------------------------------- Vermögen

def vermoegen(k: dict, db) -> str:
    ks = vm.konten(db)
    nv = vm.nettovermoegen(db)
    personen = [p["name"] for p in k["personen"]]
    zeilen = []
    for x in ks:
        zeilen.append([escape(x["name"]), vm.ARTEN.get(x["art"], x["art"]), escape(x["person"] or "gemeinsam"),
                       escape(x["datum"] or "–"), chf(x["wert"]),
                       f'<form method="post" action="vermoegen/loeschen" onsubmit="return confirm(\'Konto und alle Saldi löschen?\')">'
                       f'<input type="hidden" name="id" value="{x["id"]}"><button class="zweit klein">Löschen</button></form>'])
    zeilen.append(["<b>Total</b>", "", "", "", f"<b>{chf(nv['total'])}</b>", ""])
    liste = tabelle(["Konto", "Art", "Person", "Stand", "Saldo", ""], zeilen, zahlen_ab=4)

    heute = date.today().isoformat()
    konto_opts = "".join(f'<option value="{escape(x["name"])}">' for x in ks)
    arten = "".join(f'<option value="{a}">{n}</option>' for a, n in vm.ARTEN.items())
    pers = '<option value="">gemeinsam</option>' + "".join(f'<option>{escape(p)}</option>' for p in personen)
    erfassen = f"""<form method="post" action="vermoegen/saldo"><div class="felder">
<label>Konto<input name="konto" list="konten" required placeholder="z. B. Sparkonto ZKB"></label>
<datalist id="konten">{konto_opts}</datalist>
<label>Art (bei neuem Konto)<select name="art">{arten}</select></label>
<label>Person<select name="person">{pers}</select></label>
<label>Datum<input type="date" name="datum" value="{heute}" required></label>
<label>Saldo CHF<input name="betrag" inputmode="decimal" required placeholder="12'500.00"></label>
</div><div class="zeile"><button>Saldo speichern</button></div></form>"""
    importieren = """<form method="post" action="vermoegen/import" enctype="multipart/form-data">
<p class="leise">CSV mit den Spalten <code>Datum;Konto;Saldo</code>, optional <code>Art;Person</code>.
Arten: bank, depot, krypto, immobilie, hypothek, kredit, sonstiges. Bestehende Saldi am gleichen Datum werden ersetzt.</p>
<div class="zeile"><input type="file" name="datei" accept=".csv,text/csv" required style="max-width:360px">
<button>Importieren</button><a class="knopf zweit" href="vorlage.csv">Vorlage herunterladen</a></div></form>"""
    arten_zeilen = [[vm.ARTEN.get(a, a), chf(v)] for a, v in sorted(nv["nach_art"].items(), key=lambda x: -x[1])]
    return ('<div class="kpis">' + kpi(chf(nv["total"]), "Nettovermögen") + kpi(chf(nv["frei"]), "Freies Vermögen (ohne Immobilie/Hypothek)") + "</div>"
            + karte("Verlauf", dg.linie({"Nettovermögen": vm.verlauf(db)}))
            + karte("Konten", liste)
            + '<div class="raster">' + karte("Saldo erfassen", erfassen) + karte("CSV importieren", importieren)
            + karte("Nach Art", tabelle(["Art", "CHF"], arten_zeilen)) + "</div>")


# ---------------------------------------------------------------- Einstellungen

def _felder_person(i: int) -> list[tuple]:
    p = f"personen.{i}."
    return [
        (p + "name", "Name"), (p + "geburtsdatum", "Geburtsdatum (JJJJ-MM-TT)"),
        (p + "pensionierung_alter", "Pensionierungsalter"), (p + "lohn_brutto", "Bruttolohn/Jahr"),
        (p + "ahv.beitragsjahre_bisher", "AHV-Beitragsjahre bisher"), (p + "ahv.fehlende_jahre", "AHV fehlende Jahre"),
        (p + "ahv.einkommen_durchschnitt", "Ø AHV-Einkommen (0 = Lohn)"),
        (p + "pk.altersguthaben", "PK-Altersguthaben"), (p + "pk.stand", "Stand Ausweis (JJJJ-MM-TT)"),
        (p + "pk.sparbeitrag_jahr", "PK-Sparbeitrag/Jahr (0 = BVG-Minimum)"), (p + "pk.zins", "PK-Zins %"),
        (p + "pk.umwandlungssatz", "Umwandlungssatz %"), (p + "pk.einkauf_potenzial", "Einkaufspotenzial"),
        (p + "pk.kapitalbezug_anteil", "Kapitalbezug %"),
        (p + "saeule3a.guthaben", "3a-Guthaben"), (p + "saeule3a.beitrag_jahr", "3a-Beitrag/Jahr"),
        (p + "saeule3a.rendite", "3a-Rendite %"), (p + "saeule3a.konten", "Anzahl 3a-Konten"),
    ]


FELDER_HAUSHALT = [
    ("haushalt.name", "Name"), ("haushalt.zivilstand", "Zivilstand (verheiratet/ledig)"), ("haushalt.kanton", "Kanton"),
    ("haushalt.bedarf_ruhestand", "Bedarf im Ruhestand/Jahr"), ("haushalt.entnahme_jahre", "Kapitalverzehr Jahre"),
    ("haushalt.entnahme_rendite", "Rendite im Ruhestand %"), ("annahmen.lohnentwicklung", "Reale Lohnentwicklung %"),
]
FELDER_STEUERN = [
    ("steuern.steuerbar_bund", "Steuerbares Einkommen Bund"), ("steuern.steuerbar_kanton", "Steuerbares Einkommen Kanton"),
    ("steuern.steuer_kanton_gemeinde", "Staats- und Gemeindesteuer CHF"),
    ("steuern.grenzsteuersatz_kanton", "Grenzsteuersatz Kanton+Gemeinde %"),
]
FELDER_WOHNEN = [
    ("wohnen.aktiv", "Wohneigentum rechnen"), ("wohnen.kaufpreis", "Kaufpreis"), ("wohnen.eigenmittel", "Eigenmittel"),
    ("wohnen.davon_pk_vorbezug", "davon PK-Vorbezug"), ("wohnen.hypothek_zins", "Hypothekarzins %"),
    ("wohnen.eigenmietwert", "Eigenmietwert"), ("wohnen.unterhalt_pauschal", "Unterhalt+Nebenkosten % vom Preis"),
]


def pfad_lesen(k: dict, pfad: str):
    obj = k
    for teil in pfad.split("."):
        obj = obj[int(teil)] if isinstance(obj, list) else obj.get(teil)
        if obj is None:
            return None
    return obj


def pfad_setzen(k: dict, pfad: str, roh: str) -> None:
    teile = pfad.split(".")
    obj = k
    for teil in teile[:-1]:
        obj = obj[int(teil)] if isinstance(obj, list) else obj.setdefault(teil, {})
    alt = obj.get(teile[-1])
    roh = roh.strip()
    if isinstance(alt, bool):
        wert = roh.lower() in ("1", "true", "ja", "on")
    elif isinstance(alt, int):
        wert = int(round(vm.zahl(roh))) if roh else 0
    elif isinstance(alt, float):
        wert = vm.zahl(roh) if roh else 0.0
    else:
        wert = roh
    obj[teile[-1]] = wert


def alle_felder(k: dict) -> list[tuple]:
    felder = FELDER_HAUSHALT + FELDER_STEUERN + FELDER_WOHNEN
    for i in range(len(k["personen"])):
        felder += _felder_person(i)
    return felder


def _feld(k: dict, pfad: str, text: str) -> str:
    wert = pfad_lesen(k, pfad)
    if isinstance(wert, bool):
        return (f'<label>{escape(text)}<select name="{pfad}"><option value="ja"{" selected" if wert else ""}>ja</option>'
                f'<option value="nein"{"" if wert else " selected"}>nein</option></select></label>')
    modus = ' inputmode="decimal"' if isinstance(wert, (int, float)) else ""
    return f'<label>{escape(text)}<input name="{pfad}" value="{escape(str(wert if wert is not None else ""))}"{modus}></label>'


def einstellungen(k: dict, db) -> str:
    def gruppe(titel, felder):
        return karte(titel, '<div class="felder">' + "".join(_feld(k, p, t) for p, t in felder) + "</div>")

    teile = [gruppe("Haushalt", FELDER_HAUSHALT)]
    for i, p in enumerate(k["personen"]):
        teile.append(gruppe(p.get("name") or f"Person {i + 1}", _felder_person(i)))
    teile += [gruppe("Steuern (aus der letzten Veranlagung)", FELDER_STEUERN), gruppe("Wohnen", FELDER_WOHNEN)]
    formular = ('<form method="post" action="einstellungen">' + "".join(teile)
                + '<div class="zeile"><button>Speichern</button></div></form>')
    text = escape(yaml.safe_dump(k, allow_unicode=True, sort_keys=False))
    experte = f"""<details><summary>Alles als YAML bearbeiten (Kinder, PK-Einkäufe, Kennzahlen, Personen hinzufügen/entfernen)</summary>
<form method="post" action="einstellungen/yaml"><textarea name="yaml" spellcheck="false">{text}</textarea>
<div class="zeile"><button>YAML speichern</button></div></form></details>"""
    datei = """<form method="post" action="einstellungen/import" enctype="multipart/form-data">
<div class="zeile"><a class="knopf zweit" href="export">finanz.yaml herunterladen</a>
<input type="file" name="datei" accept=".yaml,.yml" required style="max-width:300px"><button>YAML importieren</button></div>
<p class="leise">Die vorherige Fassung wird als finanz.yaml.bak gesichert. Alle Daten liegen im
Konfigurationsordner der App und sind im Home-Assistant-Backup enthalten.</p></form>"""
    return formular + karte("Experte", experte) + karte("Sichern und übertragen", datei)
