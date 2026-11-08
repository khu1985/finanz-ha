"""HTML-Seiten der App (serverseitig gerendert, ohne JavaScript-Framework)."""
from __future__ import annotations

from datetime import date
from html import escape

import yaml

import diagramme as dg
import steuern as st
import vermoegen as vm
import versicherungen as vi
import berater as br
import dokumente as dk
import vorsorge as vs
import wohnen as wo

NAV = [("", "Übersicht"), ("vorsorge", "Vorsorge"), ("steuern", "Steuern"), ("wohnen", "Wohnen"),
       ("vermoegen", "Vermögen"), ("versicherungen", "Versicherungen"), ("berater", "Berater"),
       ("einstellungen", "Einstellungen")]

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
.hinweise.ohne{list-style:none;padding:0}.deckung{margin:8px 0}.deckung>b:first-child{display:inline-block;width:18px}
.antwort h3{font-size:15px;margin:14px 0 6px}.antwort p{margin:6px 0}.antwort ul{margin:6px 0;padding-left:20px}
pre.text{white-space:pre-wrap;font-size:12px;max-height:480px;overflow:auto}
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
    pot_3a = sum(st.ersparnis_abzug(k, max(0.0, kz["saeule3a_max"] - float(p["saeule3a"].get("beitrag_jahr", 0))),
                                    p["name"])["total"]
                 for p in k["personen"] if float(p.get("lohn_brutto", 0)) > 0) if offen_3a else 0

    hinweise = []
    for e in pks:
        hinweise += e.warnungen
    for d in drei:
        hinweise += d.hinweise
    if kap["ersparnis"] > 1000:
        hinweise.append(f"Gestaffelter Kapitalbezug spart rund CHF {chf(kap['ersparnis'])} Steuern (siehe «Steuern»).")
    if k["wohnen"].get("aktiv"):
        hinweise += wo.tragbarkeit(k, jetzt)["pruefungen"]
    for t in vi.kuendigungstermine(vi.alle(db), date.today()):
        if (t.kuendigen_bis - date.today()).days <= 45:
            hinweise.append(f"Kündigungsfrist {t.vertrag['versicherer'] or vi.SPARTEN[t.vertrag['sparte']]}: "
                            f"bis {t.kuendigen_bis.strftime('%d.%m.%Y')} (siehe «Versicherungen»).")
    hinweise += [f"{thema}: {text}" for status, thema, text in vi.deckungscheck(k, vi.alle(db))
                 if status == "fehlt" and vi.alle(db)]
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
        kpi(chf(vi.praemien(vi.alle(db))["total"]), "Versicherungsprämien (CHF/Jahr)"),
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
    teile = [st.ersparnis_abzug(k, d.beitrag, p["name"]) for p, d in zip(k["personen"], drei)]
    if st.einheiten(k)[0].verheiratet:
        teile = [st.ersparnis_abzug(k, sum(d.beitrag for d in drei))]
    ersparnis = {x: sum(t[x] for t in teile) for x in ("bund", "kanton", "total")}
    drei_html = tabelle(["Person", "Beitrag/Jahr", "Kapital bei Pensionierung"], zeilen_3a) + (
        f'<p>Steuerersparnis der heutigen 3a-Beiträge: <b>CHF {chf(ersparnis["total"])}</b> pro Jahr '
        f'(Bund {chf(ersparnis["bund"])}, Kanton/Gemeinde {chf(ersparnis["kanton"])}).</p>')

    lk = luecke
    luecke_html = tabelle(["Position", f"CHF/Jahr ab {lk.jahr}"], [
        ["AHV" + (" (plafoniert)" if st.einheiten(k)[0].verheiratet and len(k["personen"]) > 1 else ""), chf(lk.ahv)],
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
            + karte("Säule 3a", drei_html + dg.linie({d.name: d.verlauf for d in drei}, "3a"))
            + vorsorge_dokumente_karte(k, db))


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
    einheiten_html = ""
    if len(s["einheiten"]) > 1:
        einheiten_html = karte("Pro Steuererklärung", tabelle(
            ["Steuerpflichtig", "Bund", "Kanton/Gemeinde", "Total", "Grenzsatz", "effektiv"],
            [[escape(e["name"]), chf(e["bund"]), chf(e["kanton"]), chf(e["total"]), f'{e["grenz_total"]:.1f} %',
              f'{e["effektiv"]:.1f} %'] for e in s["einheiten"]]))
    # Abzüge simulieren
    zeilen = []
    for p in k["personen"]:
        pot = float(p["pk"].get("einkauf_potenzial", 0) or 0)
        for betrag in sorted({10000, 20000, round(pot)} - {0}):
            if betrag <= pot:
                e = st.ersparnis_abzug(k, betrag, p["name"])
                zeilen.append([f"PK-Einkauf {escape(p['name'])}", chf(betrag), chf(e["total"]),
                               f"{e['total'] / betrag * 100:.0f} %"])
    for i, p in enumerate(k["personen"]):
        e3 = st.ersparnis_abzug(k, kz["saeule3a_max"], p["name"])
        zeilen.insert(i, [f"3a-Maximalbeitrag {escape(p['name'])}", chf(kz["saeule3a_max"]), chf(e3["total"]),
                          f"{e3['total'] / kz['saeule3a_max'] * 100:.0f} %"])
    abzuege = tabelle(["Massnahme", "Abzug", "Ersparnis", "in % des Abzugs"], zeilen) + (
        '<p class="leise">PK-Einkäufe auf mehrere Jahre verteilen glättet die Progression. '
        'In den 3 Jahren vor einem Kapitalbezug sind Einkäufe steuerlich heikel.</p>')

    pks = [vs.pk(p, k) for p in k["personen"]]
    drei = [vs.saeule3a(p, k, jetzt) for p in k["personen"]]
    kap = st.kapitalbezug_varianten(k, pks, drei)

    def plan(v):
        mehrere = len(st.einheiten(k)) > 1
        z = [[j] + ([escape(n)] if mehrere else []) + [chf(b), chf(t["bund"]), chf(t["kanton"]), chf(t["total"])]
             for j, n, b, t in v["zeilen"]]
        z.append(["<b>Total</b>"] + ([""] if mehrere else []) + ["", "", "", f"<b>{chf(v['steuer_total'])}</b>"])
        return tabelle(["Jahr"] + (["Person"] if mehrere else []) + ["Bezug", "Bund", "Kanton", "Steuer"], z,
                       zahlen_ab=2 if mehrere else 1)

    kap_html = (f'<p>Ersparnis durch Staffelung: <b class="gut">CHF {chf(kap["ersparnis"])}</b></p>'
                '<div class="raster"><div><h2>Alles im Pensionsjahr</h2>' + plan(kap["alles_auf_einmal"])
                + '</div><div><h2>3a-Konten gestaffelt</h2>' + plan(kap["gestaffelt"]) + "</div></div>"
                '<p class="leise">Bund: ein Fünftel des ordentlichen Tarifs. Kanton: effektiver Satz aus der Tabelle '
                'unter Einstellungen (Schätzung – mit dem kantonalen Rechner prüfen). Ehepaare werden pro Jahr addiert, '
                'Konkubinatspaare getrennt besteuert.</p>')
    return heute.join(['<div class="kpis">', '</div>']) + einheiten_html + karte("Abzüge simulieren", abzuege) + karte(
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
    a = br.amortisation(k, db)
    amort = karte("Amortisation bis zur Fälligkeit", _amortisation_html(a)) if a else ""
    return f'<div class="kpis">{kpis}</div>' + '<div class="raster">' + karte("Tragbarkeit", trag) + karte(
        "Wegfall Eigenmietwert", emw) + "</div>" + amort


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
        (p + "sparen_monat", "Sparpotenzial/Monat"),
        (p + "ahv.beitragsjahre_bisher", "AHV-Beitragsjahre bisher"), (p + "ahv.fehlende_jahre", "AHV fehlende Jahre"),
        (p + "ahv.einkommen_durchschnitt", "Ø AHV-Einkommen (0 = Lohn)"),
        (p + "pk.altersguthaben", "PK-Altersguthaben"), (p + "pk.stand", "Stand Ausweis (JJJJ-MM-TT)"),
        (p + "pk.sparbeitrag_jahr", "PK-Sparbeitrag/Jahr (0 = BVG-Minimum)"), (p + "pk.zins", "PK-Zins %"),
        (p + "pk.umwandlungssatz", "Umwandlungssatz %"), (p + "pk.einkauf_potenzial", "Einkaufspotenzial"),
        (p + "pk.kapitalbezug_anteil", "Kapitalbezug %"),
        (p + "pk.ausweis_alterskapital", "Alterskapital 65 laut Ausweis"), (p + "pk.ausweis_altersrente", "Altersrente laut Ausweis"),
        (p + "risiko.iv_rente_pk", "IV-Rente PK/Jahr"), (p + "risiko.iv_kinderrente_pk", "IV-Kinderrente PK/Jahr"),
        (p + "risiko.iv_rente_extern", "IV-Rente extern/Jahr"), (p + "risiko.partnerrente_pk", "Partnerrente PK/Jahr"),
        (p + "risiko.waisenrente_pk", "Waisenrente PK/Jahr"), (p + "risiko.todesfallkapital_pk", "Todesfallkapital PK"),
        (p + "risiko.todesfallkapital_extern", "Todesfallkapital extern"),
        (p + "risiko.partner_bei_pk_gemeldet", "Partner bei PK gemeldet"),
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
    ("wohnen.aktiv", "Wohneigentum rechnen"), ("wohnen.kaufpreis", "Kaufpreis bzw. Verkehrswert"), ("wohnen.eigenmittel", "Eigenmittel"),
    ("wohnen.davon_pk_vorbezug", "davon PK-Vorbezug"), ("wohnen.hypothek_zins", "Hypothekarzins %"),
    ("wohnen.eigenmietwert", "Eigenmietwert"), ("wohnen.unterhalt_pauschal", "Unterhalt+Nebenkosten % vom Preis"),
    ("wohnen.mieteinnahmen_jahr", "Mieteinnahmen/Jahr"), ("wohnen.hypothek_faellig", "Hypothek fällig (JJJJ-MM-TT)"),
    ("wohnen.amortisation_ziel", "Ziel-Amortisation bei Fälligkeit"), ("wohnen.amortisation_max", "Maximale Amortisation"),
    ("wohnen.reserve", "Notreserve"),
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


FELDER_KI = [("ki.aktiv", "KI-Aufgabe von Home Assistant nutzen"), ("ki.entity", "KI-Entität (leer = Standard)")]


def alle_felder(k: dict) -> list[tuple]:
    felder = FELDER_HAUSHALT + FELDER_STEUERN + FELDER_WOHNEN + FELDER_KI
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
    teile += [gruppe("Steuern (aus der letzten Veranlagung)", FELDER_STEUERN), gruppe("Wohnen", FELDER_WOHNEN),
              gruppe("KI (optional, z. B. für Dokumente und Berater)", FELDER_KI)]
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
    importieren = f"""<form method="post" action="einstellungen/importordner">
<p>Persönliche Daten gehören nicht ins GitHub-Repository. Kopiere sie stattdessen (z. B. mit Samba, dem File editor oder
Studio Code Server) in den Ordner <code>/addon_configs/…_finanz/import/</code> – in der App ist das <code>/config/import/</code>.
Die App liest den Ordner beim Start und mit diesem Knopf ein und verschiebt erledigte Dateien nach <code>import/erledigt/</code>.</p>
<ul class="hinweise"><li><code>finanz.yaml</code> – ersetzt die ganze Konfiguration (vorherige Fassung wird gesichert)</li>
<li><code>vermoegen*.csv</code> – Konten und Saldi · <code>versicherungen*.csv</code> – Versicherungsliste</li>
<li><code>versicherung*.pdf</code> oder <code>police*.pdf</code> – Verträge · übrige <code>*.pdf</code> – Vorsorgedokumente</li></ul>
<div class="zeile"><button>Import-Ordner jetzt einlesen</button></div></form>"""
    return formular + karte("Import-Ordner", importieren) + karte("Experte", experte) + karte("Sichern und übertragen", datei)


# ---------------------------------------------------------------- Versicherungen

STATUS = {"ok": ("✓", "gut"), "fehlt": ("✗", "schlecht"), "pruefen": ("!", "warn"), "info": ("i", "leise")}


def versicherungen(k: dict, db) -> str:
    heute = date.today()
    vertraege = vi.alle(db)
    pr = vi.praemien(vertraege)
    termine = vi.kuendigungstermine(vertraege, heute)
    naechster = termine[0] if termine else None
    kpis = "".join([
        kpi(str(len(vertraege)), "Verträge"),
        kpi(chf(pr["total"]), f"Prämien pro Jahr · {chf(pr['monat'])}/Monat"),
        kpi(naechster.kuendigen_bis.strftime("%d.%m.%Y") if naechster else "–",
            "Nächste Kündigungsfrist" + (f" ({escape(naechster.vertrag['versicherer'] or vi.SPARTEN[naechster.vertrag['sparte']])})" if naechster else ""),
            "warn" if naechster and (naechster.kuendigen_bis - heute).days <= 30 else ""),
    ])
    hochladen = """<form method="post" action="versicherungen/hochladen" enctype="multipart/form-data">
<p class="leise">Policen, Offerten oder Prämienrechnungen als PDF hochladen (mehrere möglich). Die App liest Versicherer,
Sparte, Prämie, Daten, Fristen und Summen aus; alles lässt sich danach korrigieren. Gescannte PDFs ohne Text bitte von Hand ergänzen.</p>
<div class="zeile"><input type="file" name="datei" accept=".pdf,.txt,application/pdf" multiple required style="max-width:360px">
<button>Hochladen und analysieren</button></div></form>"""
    liste_import = """<form method="post" action="versicherungen/liste" enctype="multipart/form-data">
<p class="leise">Policen ohne PDF als CSV: <code>Versicherung;Anbieter;Betrag</code>, optional <code>Person;Police;Beginn;Ablauf;Summe;Notiz</code>.
Die Sparte wird aus der Bezeichnung erkannt (z. B. «Hausrat», «Tod Person 1», «Invaliden Person 2»).</p>
<div class="zeile"><input type="file" name="datei" accept=".csv,text/csv" required style="max-width:360px"><button>Importieren</button></div></form>"""
    if not vertraege:
        return f'<div class="kpis">{kpis}</div>' + '<div class="raster">' + karte("Verträge hochladen", hochladen) + karte(
            "Liste importieren", liste_import) + "</div>" + karte("Deckungscheck", _deckung(k, [])) + risiko_karte(k)
    zeilen = []
    for v in vertraege:
        t = vi.naechster_termin(v, heute)
        zeilen.append([
            f'<a href="versicherungen/{v["id"]}">{escape(v["versicherer"] or v["dateiname"])}</a>',
            escape(vi.SPARTEN.get(v["sparte"], v["sparte"])), escape(v["person"] or "–"),
            t.kuendigen_bis.strftime("%d.%m.%Y") if t else "–", chf(v["praemie_jahr"]),
        ])
    zeilen.append(["<b>Total</b>", "", "", "", f"<b>{chf(pr['total'])}</b>"])
    liste = tabelle(["Versicherer", "Sparte", "Person", "Kündigen bis", "Prämie/Jahr"], zeilen, zahlen_ab=4)
    termin_zeilen = [[t.kuendigen_bis.strftime("%d.%m.%Y"), t.wirksam_auf.strftime("%d.%m.%Y"),
                      escape(t.vertrag["versicherer"] or t.vertrag["dateiname"]), escape(t.grund)] for t in termine[:8]]
    termin_html = tabelle(["Kündigen bis", "wirksam auf", "Vertrag", "Grundlage"], termin_zeilen, zahlen_ab=9) + (
        '<p class="leise">Ohne Datum im Vertrag wird keine Frist berechnet. Massgebend sind Police und AVB; '
        'die Kündigung muss vor Fristende beim Versicherer eintreffen.</p>')
    sparten = dg.saeulen([vi.SPARTEN.get(s, s)[:14] for s in pr["nach_sparte"]],
                         {"Prämie": list(pr["nach_sparte"].values())}) if pr["total"] else ""
    return (f'<div class="kpis">{kpis}</div>' + karte("Verträge", liste)
            + '<div class="raster">' + karte("Deckungscheck", _deckung(k, vertraege))
            + karte("Kündigungstermine", termin_html) + "</div>"
            + risiko_karte(k) + karte("Prämien nach Sparte", sparten)
            + '<div class="raster">' + karte("Weitere Verträge hochladen", hochladen) + karte("Liste importieren", liste_import) + "</div>")


def _deckung(k: dict, vertraege: list[dict]) -> str:
    zeilen = []
    for status, thema, text in vi.deckungscheck(k, vertraege):
        zeichen, klasse = STATUS[status]
        zeilen.append(f'<li class="deckung"><b class="{klasse}">{zeichen}</b> <b>{escape(thema)}:</b> {escape(text)}</li>')
    return f'<ul class="hinweise ohne">{"".join(zeilen)}</ul>'


def versicherung(k: dict, db, vid: int) -> str:
    v = vi.einer(db, vid)
    if not v:
        raise ValueError("Vertrag nicht gefunden.")
    personen = _personen_optionen(k, v["person"])
    sparten = "".join(f'<option value="{s}"{" selected" if s == v["sparte"] else ""}>{escape(n)}</option>'
                      for s, n in vi.SPARTEN.items())

    def feld(name, text, typ="text"):
        wert = v[name]
        if typ == "date" or name in ("versicherer", "police", "notiz"):
            pass
        elif isinstance(wert, float):
            wert = f"{wert:.2f}".rstrip("0").rstrip(".")
        return f'<label>{escape(text)}<input name="{name}" type="{typ}" value="{escape(str(wert))}"></label>'

    unfall = (f'<label>Unfall eingeschlossen<select name="unfall_eingeschlossen">'
              f'<option value="0"{"" if v["unfall_eingeschlossen"] else " selected"}>nein</option>'
              f'<option value="1"{" selected" if v["unfall_eingeschlossen"] else ""}>ja</option></select></label>')
    formular = f"""<form method="post" action="versicherungen/{vid}"><div class="felder">
<label>Sparte<select name="sparte">{sparten}</select></label>
{feld("versicherer", "Versicherer")}{feld("police", "Police-Nr.")}
<label>Person<select name="person">{personen}</select></label>
{feld("praemie_jahr", "Prämie pro Jahr CHF")}{feld("beginn", "Beginn", "date")}{feld("ablauf", "Ablauf", "date")}
{feld("kuendigungsfrist_monate", "Kündigungsfrist (Monate)")}{feld("franchise", "Franchise CHF")}
{feld("selbstbehalt", "Selbstbehalt CHF")}{feld("summe", "Versicherungssumme CHF")}{unfall}
</div><label style="margin-top:10px">Notiz<input name="notiz" value="{escape(v["notiz"])}"></label>
<div class="zeile"><button>Speichern</button><a class="knopf zweit" href="versicherungen/{vid}/datei">Original öffnen</a></div></form>"""
    t = vi.naechster_termin(v, date.today())
    termin = (f'<p>Nächste Kündigung: bis <b>{t.kuendigen_bis.strftime("%d.%m.%Y")}</b>, wirksam auf '
              f'{t.wirksam_auf.strftime("%d.%m.%Y")} – {escape(t.grund)}</p>') if t else \
        '<p class="leise">Für eine Kündigungsfrist Beginn oder Ablauf erfassen.</p>'
    quelle = {"muster": "automatisch erkannt – bitte prüfen", "ohne Text": "kein Text im PDF (gescannt?) – Werte von Hand erfassen",
              "ki": "per KI ausgelesen – bitte prüfen", "hand": "von Hand bearbeitet"}.get(v["quelle"], v["quelle"])
    ki = ""
    if k.get("ki", {}).get("aktiv"):
        ki = (f'<form method="post" action="versicherungen/{vid}/ki"><div class="zeile"><button class="zweit">'
              'Mit KI auslesen</button><span class="leise">Sendet den Vertragstext an die in Home Assistant '
              'konfigurierte KI-Aufgabe.</span></div></form>')
    text = escape(v["text"][:20000]) or "Kein Text gefunden."
    loeschen = (f'<form method="post" action="versicherungen/{vid}/loeschen" onsubmit="return confirm(\'Vertrag und Datei löschen?\')">'
                '<button class="zweit">Vertrag löschen</button></form>')
    return (karte(f"{v['versicherer'] or v['dateiname']} · {vi.SPARTEN.get(v['sparte'], v['sparte'])}",
                  f'<p class="leise">{escape(v["dateiname"])} · {escape(quelle)}</p>' + termin + formular + ki)
            + karte("Ausgelesener Text", f'<details><summary>anzeigen</summary><pre class="text">{text}</pre></details>')
            + '<p><a href="versicherungen">← alle Verträge</a></p>' + loeschen)


def _personen_optionen(k: dict, aktuell: str) -> str:
    namen = vi._personen_namen(k)
    if aktuell and not any(vi.gleiche_person(n, aktuell) for n in namen):
        namen = [aktuell] + namen
    opts = ['<option value="">Haushalt</option>']
    for n in namen:
        sel = " selected" if aktuell and vi.gleiche_person(n, aktuell) else ""
        opts.append(f'<option{sel}>{escape(n)}</option>')
    return "".join(opts)


# ---------------------------------------------------------------- Vorsorgedokumente

def vorsorge_dokumente_karte(k: dict, db) -> str:
    doks = dk.alle(db)
    zeilen = [[f'<a href="vorsorge/dokument/{d["id"]}">{escape(d["dateiname"])}</a>', escape(dk.TYPEN.get(d["typ"], d["typ"])),
               escape(d["person"] or "–"), escape(d["stichtag"] or "–"), str(len(d["werte"])),
               "✓" if d["uebernommen"] else ""] for d in doks]
    liste = tabelle(["Dokument", "Art", "Person", "Stichtag", "Werte", "übernommen"], zeilen, zahlen_ab=4) if doks else ""
    form = """<form method="post" action="vorsorge/hochladen" enctype="multipart/form-data">
<p class="leise">Vorsorgeausweis der Pensionskasse, 3a-Auszug oder IK-Auszug/Rentenvorausberechnung als PDF. Die App erkennt
Altersguthaben, Einkaufspotenzial, Prognose mit 65, Invaliden- und Todesfallleistungen bzw. Saldo und Beitragsjahre;
die Werte lassen sich prüfen und einer Person übernehmen.</p>
<div class="zeile"><input type="file" name="datei" accept=".pdf,.txt,application/pdf" multiple required style="max-width:360px">
<button>Hochladen und analysieren</button></div></form>"""
    return karte("Vorsorgedokumente", liste + form)


def vorsorge_dokument(k: dict, db, did: int) -> str:
    d = dk.einer(db, did)
    if not d:
        raise ValueError("Dokument nicht gefunden.")
    typen = "".join(f'<option value="{t}"{" selected" if t == d["typ"] else ""}>{escape(n)}</option>' for t, n in dk.TYPEN.items())
    namen = [p["name"] for p in k["personen"]]
    pers = '<option value="">– Person wählen –</option>' + "".join(
        f'<option{" selected" if vi.gleiche_person(n, d["person"]) else ""}>{escape(n)}</option>' for n in namen)
    relevante = [s for s in dk.ZIELE if s in d["werte"]] + [s for s in dk.ZIELE if s not in d["werte"]]
    zeilen = []
    for s in relevante:
        if d["typ"] == "pk_ausweis" and s in ("guthaben_3a", "beitrag_3a", "beitragsjahre", "einkommen_durchschnitt", "ahv_rente_monat"):
            continue
        if d["typ"] == "saeule3a" and s not in ("guthaben_3a", "beitrag_3a"):
            continue
        if d["typ"] == "ik_auszug" and s not in ("beitragsjahre", "einkommen_durchschnitt", "ahv_rente_monat"):
            continue
        beschr, ziel = dk.ZIELE[s]
        wert = d["werte"].get(s)
        aktuell = ""
        person = next((p for p in k["personen"] if vi.gleiche_person(p["name"], d["person"])), None)
        if person and ziel:
            alt = pfad_lesen(person, ziel)
            aktuell = chf(alt) if isinstance(alt, (int, float)) and not isinstance(alt, bool) else ""
        haken = (f'<input type="checkbox" name="nimm_{s}" value="1" checked style="width:auto">'
                 if wert is not None and ziel else "")
        zeilen.append([haken, escape(beschr),
                       f'<input name="wert_{s}" value="{"" if wert is None else f"{wert:g}"}" inputmode="decimal" style="max-width:140px">',
                       aktuell])
    quelle = {"muster": "automatisch erkannt – bitte mit dem Dokument vergleichen", "ki": "per KI ausgelesen – bitte prüfen",
              "hand": "von Hand bearbeitet", "ohne Text": "kein Text im PDF (gescannt?) – Werte von Hand eintragen"}.get(d["quelle"], d["quelle"])
    tab = tabelle(["", "Wert", "Erkannt", "Heute in den Einstellungen"], zeilen, zahlen_ab=9)
    form = f"""<form method="post" action="vorsorge/dokument/{did}"><div class="felder">
<label>Art<select name="typ">{typen}</select></label><label>Person<select name="person">{pers}</select></label></div>
{tab}<div class="zeile"><button formaction="vorsorge/dokument/{did}/uebernehmen">Ausgewählte Werte übernehmen</button>
<button class="zweit">Nur speichern</button><a class="knopf zweit" href="vorsorge/dokument/{did}/datei">Original öffnen</a></div></form>"""
    ki = ""
    if k.get("ki", {}).get("aktiv"):
        ki = (f'<form method="post" action="vorsorge/dokument/{did}/ki"><div class="zeile"><button class="zweit">Mit KI auslesen'
              '</button><span class="leise">Sendet den Text an die KI-Aufgabe von Home Assistant.</span></div></form>')
    analyse = _dokument_analyse(k, d)
    loeschen = (f'<form method="post" action="vorsorge/dokument/{did}/loeschen" onsubmit="return confirm(\'Dokument löschen?\')">'
                '<button class="zweit">Dokument löschen</button></form>')
    return (karte(f"{dk.TYPEN.get(d['typ'], d['typ'])}" + (f" · {d['anbieter']}" if d["anbieter"] else ""),
                  f'<p class="leise">{escape(d["dateiname"])} · Stichtag {escape(d["stichtag"] or "unbekannt")} · {escape(quelle)}</p>'
                  + form + ki)
            + (karte("Einschätzung", hinweisliste(analyse)) if analyse else "")
            + karte("Ausgelesener Text", f'<details><summary>anzeigen</summary><pre class="text">{escape(d["text"][:20000]) or "Kein Text."}</pre></details>')
            + '<p><a href="vorsorge">← Vorsorge</a></p>' + loeschen)


def _dokument_analyse(k: dict, d: dict) -> list[str]:
    w, h = d["werte"], []
    person = next((p for p in k["personen"] if vi.gleiche_person(p["name"], d["person"])), None)
    if d["typ"] == "pk_ausweis":
        if w.get("einkauf_potenzial") and person:
            e = st.ersparnis_abzug(k, min(w["einkauf_potenzial"], 50000), person["name"])
            h.append(f"Ein PK-Einkauf von CHF {chf(min(w['einkauf_potenzial'], 50000))} spart rund CHF {chf(e['total'])} Steuern "
                     f"({e['total'] / min(w['einkauf_potenzial'], 50000) * 100:.0f} %). Danach 3 Jahre kein Kapitalbezug/WEF-Vorbezug.")
        if w.get("ausweis_altersrente") and w.get("ausweis_alterskapital"):
            uws = w["ausweis_altersrente"] / w["ausweis_alterskapital"] * 100
            h.append(f"Umwandlungssatz laut Prognose {uws:.2f} %"
                     + (" – unter dem BVG-Mindestsatz von 6,8 %, typisch für umhüllende Kassen." if uws < 6.8 else "."))
        if w.get("iv_rente_pk") and person and person.get("lohn_brutto"):
            h.append(f"Invalidenrente PK = {w['iv_rente_pk'] / float(person['lohn_brutto']) * 100:.0f} % des Lohns; "
                     "zusammen mit der IV-Rente der AHV ergibt sich die Absicherung (siehe «Versicherungen» → Risiko).")
        if w.get("partnerrente_pk") and k["haushalt"].get("zivilstand") != "verheiratet":
            h.append("Partnerrente: Bei Konkubinat nur, wenn die Lebenspartnerschaft der Kasse gemeldet ist.")
    elif d["typ"] == "ik_auszug" and w.get("beitragsjahre") and person:
        alter = date.today().year - vs.geburtsjahr(person)
        soll = max(0, min(44, alter - 20))
        if w["beitragsjahre"] < soll:
            h.append(f"{int(soll - w['beitragsjahre'])} mögliche Beitragslücke(n) – Lücken der letzten 5 Jahre lassen sich nachzahlen.")
    elif d["typ"] == "saeule3a" and w.get("beitrag_3a", 0) > k["kennzahlen"]["saeule3a_max"]:
        h.append("Einzahlungen über dem 3a-Maximum – Überschuss zurückfordern, er ist nicht abzugsfähig.")
    return h


# ---------------------------------------------------------------- Risiko (Invalidität, Tod)

def risiko_karte(k: dict) -> str:
    ahv = vs.ahv(k, date.today().year)
    rs = vi.risiko(k, ahv)
    zeilen = []
    for r in rs:
        zeilen.append([escape(r.name), chf(r.iv_ahv + r.iv_kinder_ahv), chf(r.iv_pk + r.iv_kinder_pk), chf(r.iv_extern),
                       f'<b class="{"gut" if r.iv_quote >= 70 else "warn"}">{chf(r.iv_total)}</b>', f"{r.iv_quote:.0f} %"])
    iv = tabelle(["Invalidität", "IV (AHV)", "PK", "Extern", "Total/Jahr", "vom Lohn"], zeilen)
    zeilen = [[escape(r.name), chf(r.tod_renten), chf(r.tod_kapital), chf(r.tod_bedarf_kapital)] for r in rs]
    tod = tabelle(["Tod von …", "Renten Hinterbliebene/Jahr", "Todesfallkapital", "Richtwert Kapital"], zeilen)
    hinweise = [x for r in rs for x in r.hinweise]
    return karte("Risiko Invalidität und Tod", iv + tod + hinweisliste(sorted(set(hinweise), key=hinweise.index))
                 + '<p class="leise">IV-Rente ≈ Altersrente der AHV ohne 13. Rente, Kinderrenten 40 %. PK- und externe Leistungen '
                   'aus den Einstellungen (Abschnitt «risiko» pro Person) bzw. aus dem hochgeladenen Vorsorgeausweis.</p>')


# ---------------------------------------------------------------- Anlageberater

def berater(k: dict, db) -> str:
    profile = br.profile(k)
    situation = escape((k.get("berater") or {}).get("situation") or "")
    sit = f"""<form method="post" action="berater/situation"><label>Unsere Situation und Ziele (bleibt im Home Assistant)
<textarea name="situation" style="min-height:220px;font-family:inherit;font-size:14px">{situation}</textarea></label>
<div class="zeile"><button class="zweit">Speichern</button></div></form>"""
    opts = "".join(f'<option value="{escape(p["id"])}">{escape(p["name"])}</option>' for p in profile)
    ki_aktiv = k.get("ki", {}).get("aktiv")
    fragen = f"""<form method="post" action="berater/fragen"><div class="felder">
<label>Berater<select name="profil">{opts}</select></label></div>
<label style="margin-top:10px">Frage (optional)<textarea name="frage" style="min-height:90px;font-family:inherit;font-size:14px"
placeholder="z. B. Wie erreichen wir bis zur Fälligkeit eine Amortisation von 600'000–800'000? Lohnt sich ein PK-Einkauf?"></textarea></label>
<div class="zeile"><button>{"Beratung anfragen" if ki_aktiv else "Auftrag erstellen"}</button>
<span class="leise">{"Geht an die KI-Aufgabe von Home Assistant." if ki_aktiv else "KI unter Einstellungen → YAML (ki.aktiv) einschalten oder den Auftrag kopieren."}</span></div></form>"""
    a = br.amortisation(k, db)
    amort = _amortisation_html(a) if a else '<p class="leise">Für das Szenario unter Wohnen die Fälligkeit der Hypothek erfassen.</p>'
    liste = br.alle(db)
    zeilen = [[f'<a href="berater/{b["id"]}">{escape(b["datum"][:16].replace("T", " "))}</a>', escape(b["profil"]),
               escape((b["frage"] or "Gesamtbeurteilung")[:80]), "✓" if b["antwort"] else "offen"] for b in liste]
    verlauf = tabelle(["Datum", "Berater", "Frage", "Antwort"], zeilen, zahlen_ab=9) if liste else '<p class="leise">Noch keine Beratungen.</p>'
    return ('<div class="raster">' + karte("Situation", sit) + karte("Berater fragen", fragen) + "</div>"
            + karte("Amortisation bis zur Fälligkeit", amort) + karte("Bisherige Beratungen", verlauf)
            + '<p class="leise">Die Berater sind KI-Profile, keine zugelassenen Anlageberater. Ergebnisse kritisch prüfen.</p>')


def _amortisation_html(a) -> str:
    z = [["Liquide Mittel heute (ohne nicht anzutastende Arten)", chf(a.liquiditaet_heute)],
         [f"Sparen bis {a.faellig.strftime('%m.%Y')} ({a.monate} Monate)", chf(a.sparen)]]
    z += [[f"Verpfändet: {escape(n)}", chf(w)] for n, w in a.zeilen]
    z += [["− Steuer beim Bezug der verpfändeten Vorsorge", chf(-a.steuer_bezug)],
          ["− Geplante PK-Einkäufe (nach Steuerersparnis)", chf(-a.einkaeufe)],
          ["− Notreserve", chf(-a.reserve)],
          ["<b>Verfügbar bei Fälligkeit</b>", f"<b>{chf(a.verfuegbar)}</b>"],
          [f"Ziel {chf(a.ziel)} – {chf(a.maximal)}", f'<b class="{"gut" if a.verfuegbar >= a.ziel else "schlecht"}">'
                                                    f'{chf(a.moeglich)} möglich</b>'],
          ["Hypothek danach", chf(a.hypothek_danach)]]
    return tabelle(["Position", "CHF"], z) + hinweisliste(a.hinweise)


def beratung(k: dict, db, bid: int) -> str:
    b = br.eine(db, bid)
    if not b:
        raise ValueError("Beratung nicht gefunden.")
    antwort = (f'<div class="antwort">{_absatz(b["antwort"])}</div>' if b["antwort"] else
               '<p class="leise">Noch keine Antwort. Auftrag unten kopieren, in deinen KI-Assistenten einfügen und die Antwort hier speichern.</p>')
    einfuegen = f"""<form method="post" action="berater/{bid}/antwort"><label>Antwort einfügen bzw. bearbeiten
<textarea name="antwort" style="min-height:{160 if b['antwort'] else 260}px;font-family:inherit;font-size:14px">{escape(b['antwort'])}</textarea></label>
<div class="zeile"><button class="zweit">Antwort speichern</button></div></form>"""
    auftrag = f"""<details{"" if b["antwort"] else " open"}><summary>Auftrag anzeigen</summary>
<textarea readonly id="auftrag" style="min-height:300px">{escape(b['auftrag'])}</textarea>
<div class="zeile"><button type="button" class="zweit" onclick="navigator.clipboard.writeText(document.getElementById('auftrag').value);this.textContent='Kopiert'">Kopieren</button></div></details>"""
    loeschen = (f'<form method="post" action="berater/{bid}/loeschen" onsubmit="return confirm(\'Beratung löschen?\')">'
                '<button class="zweit">Löschen</button></form>')
    return (karte(f"{b['profil']} · {b['datum'][:16].replace('T', ' ')}",
                  (f'<p><b>Frage:</b> {escape(b["frage"])}</p>' if b["frage"] else "") + antwort)
            + karte("Auftrag und Antwort", auftrag + einfuegen) + '<p><a href="berater">← Anlageberater</a></p>' + loeschen)


def _absatz(text: str) -> str:
    """Sehr einfache Darstellung von Markdown: Überschriften, Listen, fett, Absätze."""
    import re as _re
    html, liste = [], False
    for zeile in text.splitlines():
        z = escape(zeile.rstrip())
        z = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", z)
        if _re.match(r"^\s*([-*•]|\d+\.)\s+", z):
            if not liste:
                html.append("<ul>")
                liste = True
            html.append("<li>" + _re.sub(r"^\s*([-*•]|\d+\.)\s+", "", z) + "</li>")
            continue
        if liste:
            html.append("</ul>")
            liste = False
        if _re.match(r"^#{1,6}\s", z):
            html.append("<h3>" + _re.sub(r"^#{1,6}\s", "", z) + "</h3>")
        elif z.strip():
            html.append(f"<p>{z}</p>")
    if liste:
        html.append("</ul>")
    return "".join(html)
