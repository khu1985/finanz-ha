"""HTML-Seiten der App (serverseitig gerendert, ohne JavaScript-Framework)."""
from __future__ import annotations

from tausender import TS  # noqa: E402

from datetime import date
from html import escape

import yaml

import diagramme as dg
import steuern as st
import vermoegen as vm
import versicherungen as vi
import berater as br
import dokumente as dk
import steuerdokumente as sd
import ampel as am
import szenarien as sz
import vorsorge as vs
import wohnen as wo

NAVIGATION = [
    ("Überblick", [("", "Übersicht"), ("berater", "Berater")]),
    ("Planung", [("vorsorge", "Vorsorge"), ("steuern", "Steuern"), ("wohnen", "Wohnen"), ("szenarien", "Szenarien"),
                 ("nachlass", "Nachlass")]),
    ("Bestand", [("vermoegen", "Vermögen"), ("versicherungen", "Versicherungen")]),
    ("App", [("einstellungen", "Einstellungen"), ("protokoll", "Protokoll"), ("aenderungen", "Änderungen")]),
]
NAV = [e for _, gruppe in NAVIGATION for e in gruppe]

CSS = """
:root{--bg:#f6f7f9;--karte:#fff;--text:#1c2430;--leise:#5d6b7a;--linie:#e3e7ec;--akzent:#0a708f;
--gut:#2e7d4f;--warn:#b26a00;--schlecht:#b3261e;--c1:#0a708f;--c2:#e08a2e;--c3:#6b8f3a;--c4:#8a5bb5;--c5:#c2457a}
:root{color-scheme:light}
html[data-theme=dark]{--bg:#111418;--karte:#1b2027;--text:#e7ebef;--leise:#9aa7b4;
--linie:#2b323b;--akzent:#4fb3d4;--gut:#6cc58f;--warn:#e7a948;--schlecht:#f08a82;--c1:#4fb3d4;--c2:#f0a75a;
--c3:#9cc46a;--c4:#b48be0;--c5:#e57aa8;color-scheme:dark}
a{color:var(--akzent)}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.side{background:var(--karte)}
.top{display:flex;align-items:center;gap:8px}
.marke{font-weight:700;font-size:17px;color:var(--text);text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}
.version{font-size:12px;color:var(--leise);background:var(--bg);border:1px solid var(--linie);border-radius:999px;
padding:1px 8px;text-decoration:none;flex-shrink:0}.version:hover{color:var(--text)}
#thema{min-height:30px;padding:0 10px;font-size:12px;font-weight:600;border-radius:999px;background:var(--bg);
color:var(--text);border:1px solid var(--linie);flex-shrink:0}
#menu{display:none;min-height:40px;margin-left:auto;flex-shrink:0;background:var(--bg);color:var(--text);border:1px solid var(--linie)}
nav a{display:inline-flex;align-items:center;padding:8px 10px;border-radius:8px;color:var(--leise);text-decoration:none;
white-space:nowrap;font-weight:500}
nav a:hover{background:var(--bg);color:var(--text)}
nav a.aktiv{background:color-mix(in srgb,var(--akzent) 16%,transparent);color:var(--text)}
nav .gl{display:none;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--leise);font-weight:600}
nav .zahl{margin-left:6px;font-size:11px;font-weight:700;border-radius:999px;padding:0 7px;background:color-mix(in srgb,var(--warn) 20%,transparent);color:var(--warn)}
@media (min-width:1200px){
 .app{display:grid;grid-template-columns:232px minmax(0,1fr);min-height:100vh}
 .side{position:sticky;top:0;height:100vh;overflow-y:auto;border-right:1px solid var(--linie);padding:20px 12px}
 .top{padding:0 10px;flex-wrap:wrap;gap:6px 8px}.marke{white-space:normal;flex-basis:100%}
 nav .gl{display:block;margin:18px 10px 4px}nav a{display:flex}
 main{padding:24px 32px}}
@media (max-width:1199px){
 .side{position:sticky;top:0;z-index:5;border-bottom:1px solid var(--linie);padding:10px 16px 0;padding-top:calc(10px + env(safe-area-inset-top))}
 nav{display:flex;overflow-x:auto;scrollbar-width:none;padding:6px 0 8px;-webkit-overflow-scrolling:touch}nav::-webkit-scrollbar{display:none}
 nav .grp{display:flex;flex-shrink:0}nav .grp+.grp{border-left:1px solid var(--linie);margin-left:6px;padding-left:6px}}
@media (max-width:759px){
 #menu{display:inline-flex}.marke{flex:1 1 0}nav{display:none}
 .side{padding:10px 16px;padding-top:calc(10px + env(safe-area-inset-top))}
 .side.offen nav{display:grid;grid-template-columns:1fr 1fr;gap:4px 16px;padding:8px 0 12px;max-height:calc(100vh - 70px);overflow-y:auto}
 .side.offen nav .grp{display:block;border:0;margin:0;padding:0}.side.offen nav .gl{display:block;margin:10px 10px 2px}
 .side.offen nav a{display:flex}}
footer{max-width:1100px;margin:8px auto 0;padding:16px 16px calc(24px + env(safe-area-inset-bottom));
color:var(--leise);font-size:12px;text-align:center}footer a{color:var(--leise)}
#lade{position:fixed;top:0;left:0;height:3px;width:0;background:var(--akzent);z-index:20;opacity:0}
#lade.an{opacity:1;animation:lade 8s cubic-bezier(.1,.7,.2,1) forwards}
@keyframes lade{from{width:0}to{width:92%}}
#status{position:fixed;inset:0;z-index:30;display:none;align-items:center;justify-content:center;
background:color-mix(in srgb,var(--bg) 70%,transparent);backdrop-filter:blur(2px)}
#status.an{display:flex}
.status-box{background:var(--karte);border:1px solid var(--linie);border-radius:14px;padding:20px 24px;max-width:320px;
margin:16px;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,.15)}.status-box p{margin:12px 0 0}
.spinner{width:34px;height:34px;margin:0 auto;border:3px solid var(--linie);border-top-color:var(--akzent);
border-radius:50%;animation:dreh .8s linear infinite}@keyframes dreh{to{transform:rotate(360deg)}}
button:disabled{opacity:.6;cursor:progress}
.meldung{transition:opacity .6s,max-height .6s;max-height:200px;overflow:hidden}.meldung.weg{opacity:0;max-height:0;padding:0;margin:0}
.status-zeile{display:flex;flex-wrap:wrap;gap:6px;margin:-6px 0 14px}
.chip{font-size:12px;border:1px solid var(--linie);background:var(--karte);border-radius:999px;padding:3px 10px;color:var(--leise)}
.chip.gut{color:var(--gut);border-color:color-mix(in srgb,var(--gut) 40%,var(--linie))}
.chip.warn{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 40%,var(--linie))}
.log{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}.log td{vertical-align:top;white-space:pre-wrap;word-break:break-word}
.log .ERROR,.log .CRITICAL{color:var(--schlecht)}.log .WARNING{color:var(--warn)}.log .DEBUG{color:var(--leise)}
.tab{position:relative}
.ampel{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:7px;vertical-align:baseline;flex:none;
background:var(--leise);opacity:.45}
.ampel.gruen{background:#2fa35b;opacity:1;box-shadow:0 0 0 3px color-mix(in srgb,#2fa35b 20%,transparent)}
.ampel.gelb{background:#e6a817;opacity:1;box-shadow:0 0 0 3px color-mix(in srgb,#e6a817 22%,transparent)}
.ampel.rot{background:#d93b30;opacity:1;box-shadow:0 0 0 3px color-mix(in srgb,#d93b30 20%,transparent)}
nav a .ampel{width:8px;height:8px;margin-right:6px;box-shadow:none}
.kpi{position:relative}.kpi>.ampel{position:absolute;top:12px;right:10px;margin:0}
.ampeln{display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));margin-bottom:16px}
.ampel-kachel{display:flex;gap:10px;align-items:flex-start;background:var(--karte);border:1px solid var(--linie);
border-radius:12px;padding:10px 12px;text-decoration:none;color:var(--text)}
.ampel-kachel .ampel{margin-top:5px}.ampel-kachel b{display:block;font-size:14px}.ampel-kachel span{color:var(--leise);font-size:12px}
.ampel-kachel.rot{border-color:color-mix(in srgb,#d93b30 45%,var(--linie))}
.ampel-kachel.gelb{border-color:color-mix(in srgb,#e6a817 45%,var(--linie))}
.ampel-legende{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--leise);margin:-8px 0 14px}
.inhalt{min-width:0}main{max-width:1100px;margin:0 auto;padding:16px}
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
details summary{cursor:pointer;color:var(--akzent);padding:4px 0}
@media (max-width:600px){
main{padding:12px}h1{font-size:20px;margin:2px 0 12px}h2{font-size:16px}
.karte{padding:12px;border-radius:10px;margin-bottom:12px}.raster{gap:0}
.kpis{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-bottom:12px}
.kpi{padding:10px 12px}.kpi b{font-size:18px}.kpi span{font-size:12px}
table{font-size:13px}th,td{padding:6px 4px}th{font-size:12px}
input,select,textarea{font-size:16px}button,.knopf{min-height:44px}button.klein{min-height:32px}
.zeile>*{flex:1 1 auto}
table.responsiv thead{display:none}table.responsiv tr{display:block;border-bottom:1px solid var(--linie);padding:6px 0}
table.responsiv td{display:flex;justify-content:space-between;gap:12px;border:0;padding:2px 2px;text-align:right}
table.responsiv td::before{content:attr(data-label);color:var(--leise);font-size:12px;text-align:left}
table.responsiv td:first-child{font-weight:600;text-align:left}table.responsiv td:first-child::before{content:none}
table.responsiv td:empty{display:none}
table.log thead{display:none}table.log tr{display:block;padding:6px 0;border-bottom:1px solid var(--linie)}
table.log td{display:inline;border:0;padding:0 8px 0 0}table.log td:last-child{display:block;padding-top:2px}.zeile input[type=file]{max-width:none!important}
}
.hinweise.ohne{list-style:none;padding:0}.deckung{margin:8px 0}.deckung .ampel{margin-right:8px}
code.entitaet{font-size:12px;word-break:break-all;white-space:normal}
.erinnerung{display:flex;gap:6px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--linie)}
.erinnerung>div{flex:1}.erinnerung .ampel{margin-top:6px}.erinnerung form{margin-left:8px}
.antwort h3{font-size:15px;margin:14px 0 6px}.antwort p{margin:6px 0}.antwort ul{margin:6px 0;padding-left:20px}
pre.text{white-space:pre-wrap;font-size:12px;max-height:480px;overflow:auto}
"""


def chf(v: float, vorzeichen: bool = False) -> str:
    s = f"{abs(v):,.0f}" >> TS
    if v < 0:
        return "−" + s
    return ("+" if vorzeichen and v > 0 else "") + s


STATUS_TEXTE = [
    ("berater/fragen", "Berater arbeitet … das kann bis zu zwei Minuten dauern."),
    ("/ki", "KI liest das Dokument … das kann eine Minute dauern."),
    ("versicherungen/hochladen", "Verträge werden hochgeladen und analysiert …"),
    ("vorsorge/hochladen", "Vorsorgedokumente werden hochgeladen und analysiert …"),
    ("steuern/hochladen", "Steuerdokumente werden hochgeladen und analysiert …"),
    ("importordner", "Import-Ordner wird eingelesen …"),
    ("import", "Daten werden importiert …"),
    ("liste", "Liste wird importiert …"),
    ("vermoegen/bank", "Kontoauszüge werden gelesen …"),
    ("uebernehmen", "Werte werden übernommen …"),
    ("loeschen", "Wird gelöscht …"),
]

JS = """
(function(){
  var texte = %s;
  var ov = document.getElementById('status'), txt = document.getElementById('status-text'), bar = document.getElementById('lade');
  function zeige(t){ txt.textContent = t; ov.classList.add('an'); }
  document.addEventListener('submit', function(e){
    if (e.defaultPrevented) return;
    var f = e.target, ziel = (e.submitter && e.submitter.getAttribute('formaction')) || f.getAttribute('action') || '';
    var t = f.dataset.status || 'Wird gespeichert …';
    for (var i = 0; i < texte.length; i++) { if (ziel.indexOf(texte[i][0]) >= 0) { t = texte[i][1]; break; } }
    var dateien = f.querySelectorAll('input[type=file]'), n = 0, groesse = 0;
    dateien.forEach(function(d){ for (var j = 0; j < d.files.length; j++) { n++; groesse += d.files[j].size; } });
    if (n) t += ' (' + n + ' Datei' + (n > 1 ? 'en' : '') + ', ' + (groesse / 1048576).toFixed(1) + ' MB)';
    zeige(t);
    setTimeout(function(){ f.querySelectorAll('button').forEach(function(b){ b.disabled = true; }); }, 0);
  });
  document.addEventListener('click', function(e){
    var a = e.target.closest('a');
    if (!a || a.target || a.hasAttribute('download') || e.ctrlKey || e.metaKey) return;
    var h = a.getAttribute('href') || '';
    if (h.indexOf('://') >= 0 || h.charAt(0) === '#' || /datei$|export$|\\.csv$|\\.log$/.test(h)) return;
    bar.classList.add('an');
  });
  window.addEventListener('pageshow', function(){ ov.classList.remove('an'); bar.classList.remove('an');
    document.querySelectorAll('button').forEach(function(b){ b.disabled = false; }); });
  var m = document.querySelector('.meldung:not(.fehler)');
  if (m) setTimeout(function(){ m.classList.add('weg'); }, 6000);
  if (location.search.indexOf('m=') >= 0 && history.replaceState) history.replaceState(null, '', location.pathname);
})();
"""

THEMA_KOPF = """<script>(function(){var t='auto';try{t=localStorage.getItem('finanz-theme')||'auto'}catch(e){}
var d=t==='dark'||(t==='auto'&&window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches);
document.documentElement.setAttribute('data-theme',d?'dark':'light');document.documentElement.setAttribute('data-wahl',t)})();</script>"""

THEMA_JS = """(function(){var b=document.getElementById('thema');if(!b)return;var h=document.documentElement,folge=['auto','light','dark'],
txt={auto:'Auto',light:'Hell',dark:'Dunkel'};function zeigen(){b.textContent=txt[h.getAttribute('data-wahl')||'auto']}
function setzen(t){try{localStorage.setItem('finanz-theme',t)}catch(e){}h.setAttribute('data-wahl',t);
var d=t==='dark'||(t==='auto'&&window.matchMedia&&matchMedia('(prefers-color-scheme: dark)').matches);h.setAttribute('data-theme',d?'dark':'light');
var m=document.querySelector('meta[name=theme-color]');if(m)m.setAttribute('content',d?'#1b2027':'#ffffff');zeigen()}
b.addEventListener('click',function(){var t=h.getAttribute('data-wahl')||'auto';setzen(folge[(folge.indexOf(t)+1)%3])});
if(window.matchMedia)matchMedia('(prefers-color-scheme: dark)').addEventListener('change',function(){if((h.getAttribute('data-wahl')||'auto')==='auto')setzen('auto')});
setzen(h.getAttribute('data-wahl')||'auto')})();
(function(){var a=document.querySelector('nav a.aktiv');if(a&&innerWidth<1200&&innerWidth>=760)a.scrollIntoView({block:'nearest',inline:'center'})})();"""

MENU_KNOPF = ("<button id=\"menu\" type=\"button\" aria-expanded=\"false\" aria-controls=\"nav\" "
              "onclick=\"var s=document.getElementById('side');var o=s.classList.toggle('offen');"
              "this.setAttribute('aria-expanded',o);this.textContent=o?'Schliessen':'Menü'\">Menü</button>")


def _warnungen_heute() -> int:
    try:
        import konfig
        import meta
        heute = date.today().isoformat()
        return sum(1 for e in meta.protokoll(konfig.datenordner() / "finanz.log", "WARNING", 200) if e[0][:10] == heute)
    except Exception:  # noqa: BLE001
        return 0


def seite(titel: str, pfad: str, inhalt: str, basis: str = "", meldung: str = "", fehler: bool = False,
          ampeln: dict | None = None) -> str:
    import json as _json

    import meta
    ampeln = ampeln or {}
    warnungen = _warnungen_heute()
    gruppen = []
    for gruppe, eintraege in NAVIGATION:
        links = []
        for p, n in eintraege:
            aktiv = p == pfad
            punkt = licht(ampeln[p]) if ampeln.get(p) in (am.GELB, am.ROT) else ""
            zahl = f'<span class="zahl" title="Warnungen heute">{warnungen}</span>' if p == "protokoll" and warnungen else ""
            aktuell = ' aria-current="page"' if aktiv else ""
            links.append(f'<a href="{p or "./"}" class="{"aktiv" if aktiv else ""}"{aktuell}>{punkt}{n}{zahl}</a>')
        gruppen.append(f'<div class="grp"><span class="gl">{gruppe}</span>{"".join(links)}</div>')
    m = f'<div class="meldung{" fehler" if fehler else ""}" role="status">{escape(meldung)}</div>' if meldung else ""
    v = meta.version()
    return f"""<!doctype html><html lang="de-CH"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><base href="{escape(basis)}/">
<meta name="theme-color" content="#ffffff"><title>{escape(titel)} – Finanzplanung</title>{THEMA_KOPF}<style>{CSS}</style></head>
<body><div id="lade"></div><div class="app"><aside class="side" id="side"><div class="top">
<a class="marke" href="./">💰 Finanzen</a><a class="version" href="aenderungen" title="Was ist neu in dieser Version">v{escape(v)}</a>
<button id="thema" type="button" title="Darstellung umstellen: Auto (wie das Gerät) → Hell → Dunkel" aria-label="Darstellung umstellen">Auto</button>
{MENU_KNOPF}</div>
<nav id="nav" aria-label="Hauptmenü">{"".join(gruppen)}</nav></aside>
<div class="inhalt"><main><h1>{escape(titel)}</h1>{m}{inhalt}</main>
<footer>Finanzplanung v{escape(v)} · <a href="aenderungen">Änderungen</a> · <a href="protokoll">Protokoll</a>
<br>Keine Anlage-, Steuer- oder Rechtsberatung.</footer></div></div>
<div id="status" aria-live="polite"><div class="status-box"><div class="spinner"></div><p id="status-text">Bitte warten …</p></div></div>
<script>{JS % _json.dumps(STATUS_TEXTE, ensure_ascii=False)}</script><script>{THEMA_JS}</script></body></html>"""


def licht(status: str, titel: str = "") -> str:
    """Ampel-Punkt; Text für Screenreader und Tooltip."""
    t = titel or am.TEXT.get(status, "")
    return f'<span class="ampel {status}" title="{escape(t)}" role="img" aria-label="Ampel {escape(am.TEXT.get(status, ""))}"></span>'


def kpi(wert: str, text: str, klasse: str = "", ampel: str = "") -> str:
    punkt = licht(ampel) if ampel else ""
    return f'<div class="kpi">{punkt}<b class="{klasse}">{wert}</b><span>{escape(text)}</span></div>'


def karte(titel: str, inhalt: str) -> str:
    return f'<section class="karte"><h2>{escape(titel)}</h2>{inhalt}</section>'


def tabelle(kopf: list[str], zeilen: list[list], zahlen_ab: int = 1) -> str:
    """Tabelle; ab fünf Spalten auf dem Handy als Karten (Beschriftung je Zelle)."""
    th = "".join(f'<th class="{"z" if i >= zahlen_ab else ""}">{escape(h)}</th>' for i, h in enumerate(kopf))
    tr = []
    for z in zeilen:
        tds = "".join(f'<td class="{"z" if i >= zahlen_ab else ""}" data-label="{escape(kopf[i]) if i < len(kopf) else ""}">'
                      f'{c}</td>' for i, c in enumerate(z))
        tr.append(f"<tr>{tds}</tr>")
    klasse = ' class="responsiv"' if len(kopf) > 4 else ""
    return f'<div class="tab"><table{klasse}><thead><tr>{th}</tr></thead><tbody>{"".join(tr)}</tbody></table></div>'


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
            "schlecht" if luecke.luecke else "gut", am.luecke_status(luecke.luecke, luecke.bedarf)),
        kpi(f"{luecke.ersatzquote:.0f} %", "Ersatzquote zum heutigen Lohn", "", am.schwelle(luecke.ersatzquote, 70, 60)),
        kpi(chf(steuer["total_inkl"]), f"Steuern pro Jahr · Grenzsatz {steuer['grenz_total']:.0f} %"),
        kpi(chf(pot_3a), "Mögliche Ersparnis 3a (CHF/Jahr)", "gut" if pot_3a else ""),
        kpi(chf(vi.praemien(vi.alle(db))["total"]), "Versicherungsprämien (CHF/Jahr)"),
    ])
    verl = vm.verlauf(db)
    return statuszeile(k, db) + ampel_karte(k, db) + erinnerungen_karte(k, db) + f'<div class="kpis">{kpis}</div>' + '<div class="raster">' + karte("Hinweise", hinweisliste(hinweise)) + karte(
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
        [licht(am.luecke_status(lk.luecke, lk.bedarf)) + "<b>Lücke</b>", f'<b class="{"schlecht" if lk.luecke else "gut"}">{chf(lk.luecke)}</b>'],
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
        kpi(chf(s["total"]), f"Einkommenssteuern · effektiv {s['effektiv']:.1f} %"),
        kpi(f"{s['grenz_total']:.1f} %", f"Grenzsteuersatz (Bund {s['grenz_bund']:.1f} %)"),
        kpi(chf(s["vermoegen"]), "Vermögenssteuer", "", am.GRAU if not s["vermoegen"] else ""),
        kpi(chf(s["total_inkl"]), "Steuern total pro Jahr"),
    ])
    einheiten_html = ""
    if len(s["einheiten"]) > 1:
        einheiten_html = karte("Pro Steuererklärung", tabelle(
            ["Steuerpflichtig", "Bund", "Kanton/Gemeinde", "Vermögen", "Total", "Grenzsatz", "effektiv"],
            [[escape(e["name"]), chf(e["bund"]), chf(e["kanton"]), chf(e["vermoegen"]), chf(e["total"] + e["vermoegen"]),
              f'{e["grenz_total"]:.1f} %', f'{e["effektiv"]:.1f} %'] for e in s["einheiten"]]))
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
        '<p><a href="szenarien">→ Optimalen PK-Einkauf über mehrere Jahre berechnen</a></p>' +
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
    return heute.join(['<div class="kpis">', '</div>']) + einheiten_html + fristen_karte(k) + steuerdokumente_karten(k, db) + karte("Abzüge simulieren", abzuege) + karte(
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
        kpi(f"{t['quote']:.1f} %", f"Tragbarkeit (max. {kz['tragbarkeit_max']:.0f} %)", kl,
            am.tragbarkeit_status(t["quote"], kz["tragbarkeit_max"])),
        kpi(f"{t['belehnung']:.0f} %", f"Belehnung (max. {kz['belehnung_max']} %)",
            "schlecht" if t["belehnung"] > kz["belehnung_max"] else "gut",
            am.schwelle(t["belehnung"], kz["zweite_hypothek_ab"], kz["belehnung_max"], hoeher_besser=False)),
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
    bank = f"""<form method="post" action="vermoegen/bank" enctype="multipart/form-data">
<p class="leise">Kontoauszug als CSV aus dem E-Banking (Raiffeisen, UBS, ZKB, PostFinance, Kantonalbanken, Migros Bank, neon,
Yuh u. a.). Die App erkennt Bank, IBAN und Spalten und übernimmt den letzten Saldo jedes Monats. Fehlt im Auszug eine
Saldo-Spalte, den heutigen Kontostand als Endsaldo angeben.</p>
<div class="felder"><label>Konto (leer = automatisch, z. B. «Raiffeisen …7890»)<input name="konto" list="konten"></label>
<label>Art<select name="art">{arten}</select></label><label>Person<select name="person">{pers}</select></label>
<label>Endsaldo (nur ohne Saldo-Spalte)<input name="endsaldo" inputmode="decimal"></label></div>
<div class="zeile"><input type="file" name="datei" accept=".csv,text/csv,.txt" multiple required style="max-width:360px">
<button>Auszug importieren</button></div></form>"""
    arten_zeilen = [[vm.ARTEN.get(a, a), chf(v)] for a, v in sorted(nv["nach_art"].items(), key=lambda x: -x[1])]
    return ('<div class="kpis">' + kpi(chf(nv["total"]), "Nettovermögen") + kpi(chf(nv["frei"]), "Freies Vermögen (ohne Immobilie/Hypothek)") + "</div>"
            + karte("Verlauf", dg.linie({"Nettovermögen": vm.verlauf(db)})) + anlage_karte(k, db)
            + karte("Konten", liste)
            + '<div class="raster">' + karte("Bank-Import", bank) + karte("Saldo erfassen", erfassen)
            + karte("CSV importieren (eigene Liste)", importieren)
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
    ("steuern.steuerbar_vermoegen", "Steuerbares Vermögen"), ("steuern.vermoegenssteuer", "Vermögenssteuer CHF (Veranlagung)"),
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
FELDER_SENSOREN = [("sensoren.aktiv", "Sensoren an Home Assistant liefern"), ("sensoren.praefix", "Präfix der Entitäten")]
FELDER_ERINNERUNG = [("erinnerungen.benachrichtigung", "Benachrichtigung (leer, «persistent» oder notify.…)"),
                     ("erinnerungen.steuererklaerung_frist", "Frist Steuererklärung (MM-TT, leer = Kanton)"),
                     ("erinnerungen.fristerstreckung", "Fristerstreckung bis (MM-TT)")]


def alle_felder(k: dict) -> list[tuple]:
    felder = FELDER_HAUSHALT + FELDER_STEUERN + FELDER_WOHNEN + FELDER_KI + FELDER_ERINNERUNG + FELDER_SENSOREN
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
              gruppe("KI (optional, z. B. für Dokumente und Berater)", FELDER_KI),
              gruppe("Erinnerungen", FELDER_ERINNERUNG), gruppe("Sensoren", FELDER_SENSOREN)]
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
<li><code>vermoegen*.csv</code> – Konten und Saldi · <code>bank*.csv</code>, <code>konto*.csv</code> – Kontoauszüge aus dem
E-Banking · <code>versicherungen*.csv</code> – Versicherungsliste</li>
<li><code>versicherung*.pdf</code> oder <code>police*.pdf</code> – Verträge · <code>steuer*.pdf</code> oder
<code>veranlagung*.pdf</code> – Steuerdokumente · übrige <code>*.pdf</code> – Vorsorgedokumente</li></ul>
<div class="zeile"><button>Import-Ordner jetzt einlesen</button></div></form>"""
    return formular + sensoren_karte(k) + karte("Import-Ordner", importieren) + karte("Experte", experte) + karte("Sichern und übertragen", datei)


# ---------------------------------------------------------------- Versicherungen



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
            "warn" if naechster and (naechster.kuendigen_bis - heute).days <= 30 else "",
            am.termin_status((naechster.kuendigen_bis - heute).days) if naechster else ""),
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
            "Liste importieren", liste_import) + "</div>" + karte("Deckungscheck", _deckung(k, [])) + krankenkasse_karte(k, db) + risiko_karte(k)
    zeilen = []
    for v in vertraege:
        t = vi.naechster_termin(v, heute)
        zeilen.append([
            f'<a href="versicherungen/{v["id"]}">{escape(v["versicherer"] or v["dateiname"])}</a>',
            escape(vi.SPARTEN.get(v["sparte"], v["sparte"])), escape(v["person"] or "–"),
            (licht(am.termin_status((t.kuendigen_bis - heute).days)) + t.kuendigen_bis.strftime("%d.%m.%Y")) if t else "–",
            chf(v["praemie_jahr"]),
        ])
    zeilen.append(["<b>Total</b>", "", "", "", f"<b>{chf(pr['total'])}</b>"])
    liste = tabelle(["Versicherer", "Sparte", "Person", "Kündigen bis", "Prämie/Jahr"], zeilen, zahlen_ab=4)
    termin_zeilen = [[licht(am.termin_status((t.kuendigen_bis - heute).days), f"noch {(t.kuendigen_bis - heute).days} Tage")
                      + t.kuendigen_bis.strftime("%d.%m.%Y"), t.wirksam_auf.strftime("%d.%m.%Y"),
                      escape(t.vertrag["versicherer"] or t.vertrag["dateiname"]), escape(t.grund)] for t in termine[:8]]
    termin_html = tabelle(["Kündigen bis", "wirksam auf", "Vertrag", "Grundlage"], termin_zeilen, zahlen_ab=9) + (
        '<p class="leise">Ohne Datum im Vertrag wird keine Frist berechnet. Massgebend sind Police und AVB; '
        'die Kündigung muss vor Fristende beim Versicherer eintreffen.</p>')
    sparten = dg.saeulen([vi.SPARTEN.get(s, s)[:14] for s in pr["nach_sparte"]],
                         {"Prämie": list(pr["nach_sparte"].values())}) if pr["total"] else ""
    return (f'<div class="kpis">{kpis}</div>' + karte("Verträge", liste)
            + '<div class="raster">' + karte("Deckungscheck", _deckung(k, vertraege))
            + karte("Kündigungstermine", termin_html) + "</div>"
            + krankenkasse_karte(k, db) + risiko_karte(k) + karte("Prämien nach Sparte", sparten)
            + '<div class="raster">' + karte("Weitere Verträge hochladen", hochladen) + karte("Liste importieren", liste_import) + "</div>")


def _deckung(k: dict, vertraege: list[dict]) -> str:
    zeilen = []
    for status, thema, text in vi.deckungscheck(k, vertraege):
        zeilen.append(f'<li class="deckung">{licht(am.deckung_status(status))}<b>{escape(thema)}:</b> {escape(text)}</li>')
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
               licht(am.GRUEN, "übernommen") if d["uebernommen"] else licht(am.GELB, "noch nicht übernommen")] for d in doks]
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
                       f'<input name="wert_{s}" value="{"" if wert is None else f"{wert:g}"}" inputmode="decimal" style="max-width:140px;min-width:104px">',
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
        zeilen.append([licht(am.iv_status(r.iv_quote) if r.lohn else am.GRAU) + escape(r.name), chf(r.iv_ahv + r.iv_kinder_ahv), chf(r.iv_pk + r.iv_kinder_pk), chf(r.iv_extern),
                       f'<b class="{"gut" if r.iv_quote >= 70 else "warn"}">{chf(r.iv_total)}</b>', f"{r.iv_quote:.0f} %"])
    iv = tabelle(["Invalidität", "IV (AHV)", "PK", "Extern", "Total/Jahr", "vom Lohn"], zeilen)
    zeilen = [[licht(am.tod_status(r.tod_kapital, r.tod_bedarf_kapital)) + escape(r.name), chf(r.tod_renten),
               chf(r.tod_kapital), chf(r.tod_bedarf_kapital)] for r in rs]
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
               escape((b["frage"] or "Gesamtbeurteilung")[:80]), licht(am.GRUEN, "beantwortet") + "beantwortet" if b["antwort"] else licht(am.GELB, "offen") + "offen"] for b in liste]
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
          [licht(am.amortisation_status(a.verfuegbar, a.ziel)) + f"Ziel {chf(a.ziel)} – {chf(a.maximal)}", f'<b class="{"gut" if a.verfuegbar >= a.ziel else "schlecht"}">'
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


# ---------------------------------------------------------------- Status, Protokoll, Änderungen

def statuszeile(k: dict, db) -> str:
    import konfig
    import meta
    chips = []
    letzter = db.execute("SELECT MAX(datum) FROM saldi").fetchone()[0]
    if letzter:
        alter = (date.today() - date.fromisoformat(letzter)).days
        chips.append(("gut" if alter <= 45 else "warn", f"Saldi vom {date.fromisoformat(letzter).strftime('%d.%m.%Y')}"))
    else:
        chips.append(("warn", "Noch keine Saldi"))
    chips.append(("", f"{len(vi.alle(db))} Verträge"))
    chips.append(("", f"{len(dk.alle(db))} Vorsorge- und {len(sd.alle(db))} Steuerdokumente"))
    todo = konfig.konfig_pfad().read_text(encoding="utf-8").count("TODO") if konfig.konfig_pfad().exists() else 0
    if todo:
        chips.append(("warn", f"{todo} offene TODO in der Konfiguration"))
    imp = konfig.datenordner() / "import"
    wartend = [p for p in imp.iterdir() if p.is_file()] if imp.exists() else []
    if wartend:
        chips.append(("warn", f"{len(wartend)} Datei(en) im Import-Ordner"))
    chips.append(("gut" if k.get("ki", {}).get("aktiv") else "", "KI an" if k.get("ki", {}).get("aktiv") else "KI aus"))
    fehler = [e for e in meta.protokoll(konfig.datenordner() / "finanz.log", "WARNING", 50)
              if e[0][:10] == date.today().isoformat()]
    if fehler:
        chips.append(("warn", f"{len(fehler)} Warnung(en) heute – Protokoll"))
    html = "".join(f'<span class="chip {c}">{escape(t)}</span>' for c, t in chips)
    return f'<div class="status-zeile">{html}</div>'


def protokoll(k: dict, db, stufe: str = "INFO") -> str:
    import konfig
    import meta
    eintraege = meta.protokoll(konfig.datenordner() / "finanz.log", stufe)
    auswahl = "".join(f'<option{" selected" if s == stufe else ""}>{s}</option>' for s in meta.STUFEN[:4])
    filter_ = f"""<form method="get" action="protokoll" data-status="Protokoll wird geladen …"><div class="zeile">
<label style="flex:0 1 200px">Ab Stufe<select name="stufe" onchange="this.form.submit()">{auswahl}</select></label>
<a class="knopf zweit" href="protokoll.log">Protokoll herunterladen</a></div></form>"""
    if not eintraege:
        return karte("Protokoll", filter_ + '<p class="leise">Keine Einträge.</p>')
    zeilen = "".join(f'<tr class="{s}"><td>{escape(z[5:16])}</td><td>{escape(s)}</td><td>{escape(t)}</td></tr>'
                     for z, s, t in eintraege)
    return karte("Protokoll", filter_ + f'<div class="tab"><table class="log"><thead><tr><th>Zeit</th><th>Stufe</th>'
                 f'<th>Meldung</th></tr></thead><tbody>{zeilen}</tbody></table></div>'
                 f'<p class="leise">Neueste zuerst, höchstens 400 Einträge. Die Stufe für neue Einträge lässt sich in der App-Konfiguration '
                 '(log_level) einstellen.</p>')


def aenderungen(k: dict, db) -> str:
    import meta
    text = meta.changelog()
    text = "\n".join(z for z in text.splitlines() if not z.startswith("# "))
    return karte(f"Version {meta.version()}", f'<div class="antwort">{_absatz(text)}</div>')


# ---------------------------------------------------------------- Steuerdokumente

VERGLEICH_FELDER = ["steuerbar_kanton", "steuerbar_bund", "steuer_kanton_gemeinde", "bundessteuer", "steuerbares_vermoegen",
                    "vermoegenssteuer",
                    "lohn_netto", "abzug_3a", "abzug_pk_einkauf", "schuldzinsen", "unterhalt_liegenschaft", "eigenmietwert",
                    "mietertrag"]


def steuerdokumente_karten(k: dict, db) -> str:
    doks = sd.alle(db)
    form = """<form method="post" action="steuern/hochladen" enctype="multipart/form-data">
<p class="leise">Steuererklärungen, Veranlagungsverfügungen oder Steuerrechnungen als PDF (mehrere Jahre möglich). Die App
erkennt Steuerperiode, steuerbares Einkommen Kanton/Bund, Steuerbeträge, Abzüge und Liegenschaftswerte, vergleicht die Jahre
und übernimmt die Werte auf Wunsch in die Steuer-Einstellungen.</p>
<div class="zeile"><input type="file" name="datei" accept=".pdf,.txt,application/pdf" multiple required style="max-width:360px">
<button>Hochladen und analysieren</button></div></form>"""
    if not doks:
        return karte("Steuerdokumente", form)
    zeilen = [[f'<a href="steuern/dokument/{d["id"]}">{d["jahr"] or "?"} · {escape(d["person"] or "Haushalt")}</a>',
               escape(sd.TYPEN.get(d["typ"], d["typ"])), chf(d["werte"].get("steuerbar_kanton", 0)),
               chf(d["werte"].get("steuer_kanton_gemeinde", 0) + d["werte"].get("bundessteuer", 0)),
               licht(am.GRUEN, "übernommen") if d["uebernommen"] else licht(am.GELB, "noch nicht übernommen")] for d in doks]
    liste = tabelle(["Jahr · Person", "Art", "Steuerbar Kanton", "Steuern", "übernommen"], zeilen, zahlen_ab=2)
    html = karte("Steuerdokumente", liste + form)
    # Mehrjahresvergleich pro Person
    for person, jahre in sd.vergleich(doks).items():
        js = sorted(jahre)
        felder = [f for f in VERGLEICH_FELDER if any(f in jahre[j] for j in js)]
        if not felder:
            continue
        z = []
        for f in felder:
            werte = [jahre[j].get(f) for j in js]
            delta = ""
            if len(js) >= 2 and werte[-1] is not None and werte[-2] is not None:
                delta = chf(werte[-1] - werte[-2], True)
            z.append([escape(sd.FELDER[f][0])] + [chf(w) if w is not None else "–" for w in werte] + [delta])
        grenz = sd.grenzsteuersatz(jahre)
        zusatz = (f'<p>Geschätzter Grenzsteuersatz Kanton + Gemeinde aus den Veranlagungen: <b>{grenz:.1f} %</b>'
                  ' – im Dokument übernehmen.</p>') if grenz else ""
        html += karte(f"Vergleich {person}", tabelle(["Kennzahl"] + [str(j) for j in js] + ["Δ Vorjahr"], z) + zusatz
                      + '<p class="leise">Pro Jahr zählt die Veranlagung, sonst die Steuererklärung.</p>')
    abgl = sd.abgleich(doks)
    if abgl:
        html += karte("Erklärung und Veranlagung", hinweisliste(abgl))
    return html


def steuer_dokument(k: dict, db, did: int) -> str:
    d = sd.einer(db, did)
    if not d:
        raise ValueError("Dokument nicht gefunden.")
    typen = "".join(f'<option value="{t}"{" selected" if t == d["typ"] else ""}>{escape(n)}</option>' for t, n in sd.TYPEN.items())
    namen = [p["name"] for p in k["personen"]]
    pers = '<option value="">– Person wählen –</option>' + "".join(
        f'<option{" selected" if vi.gleiche_person(n, d["person"]) else ""}>{escape(n)}</option>' for n in namen)
    person = next((p for p in k["personen"] if vi.gleiche_person(p["name"], d["person"])), None)
    einheit = st.einheit_von(k, person["name"] if person else None).st if person else {}
    gleiche = [x for x in sd.alle(db) if vi.gleiche_person(x["person"] or "Haushalt", d["person"] or "Haushalt")]
    grenz = sd.grenzsteuersatz({j: w for j, w in sd.vergleich(gleiche).get(d["person"] or "Haushalt", {}).items()})
    zeilen = []
    for s, (beschr, _) in sd.FELDER.items():
        wert = d["werte"].get(s)
        if wert is None and s not in ("steuerbar_kanton", "steuerbar_bund", "steuer_kanton_gemeinde", "bundessteuer"):
            continue
        ziel = sd.ZIELE.get(s, "")
        aktuell = ""
        if ziel.startswith("steuer:"):
            aktuell = chf(einheit.get(ziel.split(":")[1], 0)) if einheit else ""
        elif ziel.startswith("wohnen:"):
            aktuell = chf(k["wohnen"].get(ziel.split(":")[1], 0))
        elif ziel.startswith("person:") and person:
            aktuell = chf(pfad_lesen(person, ziel.split(":")[1]) or 0)
        haken = (f'<input type="checkbox" name="nimm_{s}" value="1" checked style="width:auto">' if wert is not None and ziel else "")
        zeilen.append([haken, escape(beschr),
                       f'<input name="wert_{s}" value="{"" if wert is None else f"{wert:g}"}" inputmode="decimal" style="max-width:140px;min-width:104px">',
                       aktuell])
    if grenz:
        zeilen.append([f'<input type="checkbox" name="nimm_grenzsteuersatz" value="1" checked style="width:auto">',
                       "Grenzsteuersatz Kanton + Gemeinde % (aus mehreren Jahren)", f"{grenz:.1f}",
                       f'{einheit.get("grenzsteuersatz_kanton", "")} %' if einheit else ""])
    quelle = {"muster": "automatisch erkannt – bitte mit dem Dokument vergleichen", "ki": "per KI ausgelesen – bitte prüfen",
              "hand": "von Hand bearbeitet", "ohne Text": "kein Text im PDF (gescannt?) – Werte von Hand eintragen"}.get(d["quelle"], d["quelle"])
    form = f"""<form method="post" action="steuern/dokument/{did}"><div class="felder">
<label>Art<select name="typ">{typen}</select></label><label>Steuerperiode<input name="jahr" value="{d['jahr'] or ''}" inputmode="numeric"></label>
<label>Person<select name="person">{pers}</select></label></div>
{tabelle(["", "Wert", "Erkannt", "Heute in den Einstellungen"], zeilen, zahlen_ab=9)}
<input type="hidden" name="grenz" value="{grenz or ''}">
<div class="zeile"><button formaction="steuern/dokument/{did}/uebernehmen">Ausgewählte Werte übernehmen</button>
<button class="zweit">Nur speichern</button><a class="knopf zweit" href="steuern/dokument/{did}/datei">Original öffnen</a></div></form>"""
    ki = ""
    if k.get("ki", {}).get("aktiv"):
        ki = (f'<form method="post" action="steuern/dokument/{did}/ki"><div class="zeile"><button class="zweit">Mit KI auslesen'
              '</button><span class="leise">Sendet den Text an die KI-Aufgabe von Home Assistant.</span></div></form>')
    tipps = sd.hinweise(k, d) + [h for h in sd.abgleich(gleiche) if str(d["jahr"]) in h]
    loeschen = (f'<form method="post" action="steuern/dokument/{did}/loeschen" onsubmit="return confirm(\'Dokument löschen?\')">'
                '<button class="zweit">Dokument löschen</button></form>')
    return (karte(f"{sd.TYPEN.get(d['typ'], d['typ'])} {d['jahr'] or ''}",
                  f'<p class="leise">{escape(d["dateiname"])} · {escape(quelle)}</p>' + form + ki)
            + (karte("Einschätzung", hinweisliste(tipps)) if tipps else "")
            + karte("Ausgelesener Text", f'<details><summary>anzeigen</summary><pre class="text">{escape(d["text"][:20000]) or "Kein Text."}</pre></details>')
            + '<p><a href="steuern">← Steuern</a></p>' + loeschen)



def ampel_karte(k: dict, db) -> str:
    ampeln = am.bewerten(k, db)
    reihen = sorted(ampeln, key=lambda a: -am.RANG[a.status])
    kacheln = "".join(
        f'<a class="ampel-kachel {a.status}" href="{a.seite}">{licht(a.status)}<div><b>{escape(a.bereich)}</b>'
        f'<span>{escape(a.text)}</span></div></a>' for a in reihen)
    zaehler = {s: sum(1 for a in ampeln if a.status == s) for s in (am.ROT, am.GELB, am.GRUEN)}
    legende = (f'<div class="ampel-legende"><span>{licht(am.ROT)}{zaehler[am.ROT]} handeln</span>'
               f'<span>{licht(am.GELB)}{zaehler[am.GELB]} prüfen</span><span>{licht(am.GRUEN)}{zaehler[am.GRUEN]} in Ordnung</span></div>')
    return f'<div class="ampeln">{kacheln}</div>' + legende


# ---------------------------------------------------------------- Szenarien

def szenarien(k: dict, db, q: dict | None = None) -> str:
    q = q or {}
    return einkauf_karte(k, db, q) + fruehpension_karte(k, db) + hypothek_karte(k, db, q) + heirat_karte(k, db)


def einkauf_karte(k: dict, db, q: dict) -> str:
    heute = date.today()
    namen = [p["name"] for p in k["personen"]]

    def wert(name, standard):
        return (q.get(name) or [str(standard)])[0]

    person = wert("person", namen[0])
    if person not in namen:
        person = namen[0]
    p = next(x for x in k["personen"] if x["name"] == person)
    budget = vm.zahl(wert("budget", "0") or "0")
    von = int(wert("von", heute.year))
    bis = int(wert("bis", min(vs.pensionsjahr(p) - 1, heute.year + 9)))
    schwelle = vm.zahl(wert("schwelle", "20") or "0")
    schritt = max(1000.0, vm.zahl(wert("schritt", "5000") or "5000"))
    opts = "".join(f'<option{" selected" if n == person else ""}>{escape(n)}</option>' for n in namen)
    form = f"""<form method="get" action="szenarien" data-status="Einkäufe werden optimiert …"><div class="felder">
<label>Person<select name="person">{opts}</select></label>
<label>Budget insgesamt (0 = ganzes Potenzial)<input name="budget" value="{budget:g}" inputmode="decimal"></label>
<label>Ab Jahr<input name="von" value="{von}" inputmode="numeric"></label>
<label>Bis Jahr<input name="bis" value="{bis}" inputmode="numeric"></label>
<label>Mindest-Ersparnis pro Franken %<input name="schwelle" value="{schwelle:g}" inputmode="decimal"></label>
<label>Schrittweite CHF<input name="schritt" value="{schritt:g}" inputmode="decimal"></label>
</div><div class="zeile"><button>Optimieren</button></div></form>"""
    plan = sz.einkauf_optimieren(k, person, budget, von, bis, schwelle, schritt, heute)
    if not plan.plan:
        return karte("PK-Einkauf optimieren", form + hinweisliste(plan.hinweise or ["Kein Einkauf sinnvoll oder kein Potenzial."]))
    eingekauft = sum(plan.plan.values())
    kpis = "".join([
        kpi(chf(eingekauft), f"Einkauf von {chf(plan.potenzial)} Potenzial"),
        kpi(chf(plan.total_ersparnis), f"Steuerersparnis ({plan.total_ersparnis / eingekauft * 100:.0f} %)", "gut"),
        kpi(chf(plan.total_ersparnis - plan.einjahr_ersparnis, True), "mehr als alles in einem Jahr", "",
            am.GRUEN if plan.total_ersparnis > plan.einjahr_ersparnis else am.GRAU),
        kpi(chf(plan.netto), "Netto-Vorteil inkl. Zins bis 65, nach Kapitalbezugssteuer"),
    ])
    zeilen = [[str(j), chf(b), f"{chf(plan.ersparnis[j])} ({plan.ersparnis[j] / b * 100:.0f} %)",
               licht(am.schwelle(plan.grenz_letzter[j], 30, 20)) + f"{plan.grenz_letzter[j]:.0f} %"]
              for j, b in sorted(plan.plan.items())]
    zeilen.append(["<b>Total</b>", f"<b>{chf(eingekauft)}</b>",
                   f"<b>{chf(plan.total_ersparnis)}</b> ({plan.total_ersparnis / eingekauft * 100:.0f} %)", ""])
    tab = tabelle(["Jahr", "Einkauf", "Ersparnis", "letzter Franken"], zeilen)
    kurve = dg.linie({"Ersparnis pro zusätzlichem Franken (%)":
                      [(int(round(b / 1000)), round(s, 1)) for b, s in plan.kurve]}, "Grenz-Ersparnis")
    kurve += '<p class="leise">Waagrecht: Einkauf in einem Jahr in Tausend Franken.</p>'
    uebernehmen = f"""<form method="post" action="szenarien/einkauf">
{"".join(f'<input type="hidden" name="{n}" value="{escape(str(v))}">' for n, v in
         (("person", person), ("budget", budget), ("von", von), ("bis", bis), ("schwelle", schwelle), ("schritt", schritt)))}
<div class="zeile"><button>Plan als geplante Einkäufe übernehmen</button>
<span class="leise">Ergänzt «einkauf_geplant» von {escape(person)}; wirkt auf PK-Prognose, Amortisation und Berater.</span></div></form>"""
    gesperrt = (f'<p class="leise">Gesperrt (3 Jahre vor Kapitalbezug): {", ".join(map(str, plan.gesperrt))}</p>'
                if plan.gesperrt else "")
    erklaerung = ('<p class="leise">Die App verteilt den Einkauf in Schritten jeweils auf das Jahr mit der höchsten Ersparnis '
                  'für den nächsten Franken (gleiches Einkommen jedes Jahr angenommen). Optimal ist, solange der letzte Franken '
                  'mehr Steuern spart als der spätere Bezug kostet – typisch 20–30 %. Die Kurve zeigt, wie stark die Ersparnis '
                  'pro Franken sinkt, wenn in einem einzigen Jahr mehr eingekauft wird.</p>')
    return karte("PK-Einkauf optimieren", form + f'<div class="kpis">{kpis}</div>' + tab + gesperrt + kurve
                 + hinweisliste(plan.hinweise) + uebernehmen + erklaerung)


def heirat_karte(k: dict, db) -> str:
    h = sz.heirat_vergleich(k, db)
    titel = "Verheiratet oder Konkubinat"
    if not h.moeglich:
        return karte(titel, f'<p>{escape(h.grund)}</p>')
    jahre = h.jahre_ruhestand
    zeilen = [
        [licht(am.GRUEN if h.steuer_diff <= 0 else am.GELB) + "Einkommenssteuern heute (pro Jahr)",
         chf(h.steuer_konkubinat), chf(h.steuer_verheiratet), chf(h.steuer_diff, True)],
        [licht(am.GRUEN if h.ahv_diff >= 0 else am.GELB) + "AHV-Renten im Ruhestand (pro Jahr)",
         chf(h.ahv_konkubinat), chf(h.ahv_verheiratet), chf(h.ahv_diff, True)],
        [licht(am.GRUEN if h.kapital_diff <= 0 else am.GELB) + "Steuer auf Kapitalbezügen (einmalig)",
         chf(h.kapital_konkubinat), chf(h.kapital_verheiratet), chf(h.kapital_diff, True)],
    ]
    for name, rk, rv in h.hinterbliebene:
        zeilen.append([licht(am.GRUEN if rv >= rk else am.GELB) + f"Renten für Hinterbliebene beim Tod von {escape(name)} (pro Jahr)",
                       chf(rk), chf(rv), chf(rv - rk, True)])
    tab = tabelle(["", "Konkubinat", "Verheiratet", "Unterschied"], zeilen)
    ib = h.ib_jahr
    b0, b1 = h.bilanz_ohne_ib, h.bilanz_mit_ib
    def satz(b):
        return f'<b class="{"gut" if b >= 0 else "schlecht"}">{"bringt" if b >= 0 else "kostet"} rund CHF {chf(abs(b))}</b>'
    fazit = karte_inhalt = (
        '<h2>Bilanz über den ganzen Zeitraum</h2>'
        + tabelle(["Annahme", "Steuern heute", "Kapitalbezug", "AHV", "Heirat"], [
            [f"Gemeinsame Besteuerung bleibt", f"{h.jahre_bis_pension} Jahre", chf(-h.kapital_diff, True),
             chf(h.ahv_diff * h.jahre_ruhestand, True), satz(b0)],
            [licht(am.GRUEN) + f"Individualbesteuerung ab {ib}", f"{h.jahre_ehetarif} Jahre (bis {ib})",
             chf(-h.kapital_diff_ib, True), chf(h.ahv_diff * h.jahre_ruhestand, True), satz(b1)],
        ], zahlen_ab=1)
        + f'<p class="leise">Steuern bis zur Pensionierung, AHV über {h.jahre_ruhestand} Ruhestandsjahre, Kapitalbezug einmalig; '
          'ohne Teuerung, Zins und den Wert der Absicherung im Todesfall. Mit Individualbesteuerung ist der Steuerunterschied '
          f'ab {ib} null (Einheitstarif für alle); übrig bleibt vor allem die AHV-Plafonierung. Jahr unter '
          '<code>kennzahlen.individualbesteuerung_ab</code> anpassen, sobald der Bundesrat den Termin festlegt.</p>')
    d = h.verheiratet_details
    annahmen = (f'<p class="leise">Verheiratet geschätzt: Bund auf CHF {chf(d["bund_einkommen"])} (Summe beider, '
                f'Verheiratetenabzug, Zweiverdienerabzug {chf(d["zweiverdiener"])}, Elterntarif), Kanton auf '
                f'CHF {chf(d["kanton_einkommen"])} mit Splitting-Divisor {d["divisor"]:g} auf dem Mittel eurer beiden Steuerkurven '
                '(steuern.ehe_splitting_divisor). Kantonale Regeln prüfen; Hinterbliebene: AHV-Witwen-/Witwerrente und '
                'PK-Ehegattenrente gegenüber nur Waisenrenten bzw. gemeldeter Lebenspartnerrente.</p>')
    return karte(titel, tab + fazit + hinweisliste(h.qualitativ) + annahmen)


def hypothek_karte(k: dict, db, q: dict) -> str:
    import copy as _copy

    import hypothek as hy
    titel = "Hypothekar-Strategie"
    if not k["wohnen"].get("aktiv"):
        return karte(titel, '<p class="leise">Unter Einstellungen → Wohnen Wohneigentum aktivieren.</p>')
    k2 = _copy.deepcopy(k)
    eigen = k2["wohnen"].setdefault("strategie", {}) or {}
    k2["wohnen"]["strategie"] = eigen
    cfg0 = hy.konfiguration(k)
    felder = [("betrag", "Hypothek ab Start (0 = nach Amortisation)", cfg0.get("betrag") or 0),
              ("horizont_jahre", "Horizont Jahre", cfg0["horizont_jahre"]),
              ("saron", "SARON heute %", cfg0["saron"]), ("marge_saron", "Marge SARON %", cfg0["marge_saron"]),
              ("fest5", "Festsatz 5 J. %", cfg0["fest"][5]), ("fest10", "Festsatz 10 J. %", cfg0["fest"][10]),
              ("stress", "SARON im Stressszenario %", cfg0["szenarien"]["stress"]["ziel"])]
    werte = {}
    for name, _, standard in felder:
        roh = (q.get("h_" + name) or [""])[0]
        werte[name] = vm.zahl(roh) if roh.strip() else float(standard)
    eigen.update({"betrag": werte["betrag"], "horizont_jahre": int(werte["horizont_jahre"]), "saron": werte["saron"],
                  "marge_saron": werte["marge_saron"],
                  "fest": {**cfg0["fest"], 5: werte["fest5"], 10: werte["fest10"]},
                  "szenarien": {**cfg0["szenarien"], "stress": {**cfg0["szenarien"]["stress"], "ziel": werte["stress"]}}})
    s = hy.vergleichen(k2, db)
    if not s:
        return karte(titel, '<p class="leise">Keine Hypothek erfasst.</p>')
    erhalten = "".join(f'<input type="hidden" name="{n}" value="{escape(v[0])}">' for n, v in q.items() if not n.startswith("h_"))
    form = (f'<form method="get" action="szenarien" data-status="Strategien werden verglichen …">{erhalten}<div class="felder">'
            + "".join(f'<label>{escape(t)}<input name="h_{n}" value="{werte[n]:g}" inputmode="decimal"></label>' for n, t, _ in felder)
            + '</div><div class="zeile"><button>Neu rechnen</button></div></form>')
    stress = "stress" if "stress" in s.pfade else list(s.pfade)[-1]
    rang = sorted(e.kosten[stress] for e in s.ergebnisse)

    def ampel_von(e):
        i = rang.index(e.kosten[stress])
        return am.GRUEN if i < len(rang) / 3 else am.GELB if i < 2 * len(rang) / 3 else am.ROT

    szen = list(s.pfade)
    zeilen = []
    for e in sorted(s.ergebnisse, key=lambda e: e.kosten[stress]):
        name = escape(e.name) + (" ★" if e.name == s.empfehlung else "")
        zeilen.append([licht(ampel_von(e)) + name] + [chf(e.kosten[n]) for n in szen]
                      + [chf(e.max_jahr[stress]), f"{e.zinsbindung:g} J."])
    tab = tabelle(["Strategie"] + [f"Kosten {n}" for n in szen] + ["max. Jahr (Stress)", "Zinsbindung"], zeilen)
    kpis = "".join([
        kpi(chf(s.betrag), f"Hypothek ab {s.start.strftime('%m.%Y')}"),
        kpi(escape(s.empfehlung), "Am sichersten (tiefste Kosten im Stress)", "", am.GRUEN),
        kpi(f"{s.horizont} Jahre", "Betrachtungshorizont"),
    ])
    pfade = dg.linie({f"SARON {n}": [(s.start.year + t, round(v, 2)) for t, v in enumerate(p)] for n, p in s.pfade.items()},
                     "SARON-Szenarien")
    return karte(titel, f'<div class="kpis">{kpis}</div>' + tab
                 + '<p class="leise">Ampel: Rang der Kosten im Stressszenario (grün = robusteste Drittel). Kosten = Zinsen über den '
                   'Horizont ohne Amortisation. Festsätze laut Einstellungen (Standard: Richtsätze einer Bank, Stand 08.11.2026) – '
                   'eigene Offerten unter wohnen.strategie eintragen.</p>'
                 + pfade + hinweisliste(s.hinweise) + form)



def erinnerungen_karte(k: dict, db) -> str:
    import erinnerungen as er
    heute = date.today()
    liste = er.alle(k, db, heute)
    if not liste:
        return ""
    zeilen = []
    for e in liste[:10]:
        t = e.tage(heute)
        wann = "überfällig" if t < 0 else "heute" if t == 0 else f"in {t} Tagen"
        link = f' <a href="{e.seite}">öffnen</a>' if e.seite else ""
        zeilen.append(
            f'<li class="erinnerung">{licht(er.status(e, heute), wann)}<div><b>{escape(e.titel)}</b>'
            f'<span class="leise"> · bis {e.faellig:%d.%m.%Y} ({wann})</span><br><span>{escape(e.text)}</span>{link}</div>'
            f'<form method="post" action="erinnerungen/erledigt" data-status="Wird gespeichert …">'
            f'<input type="hidden" name="schluessel" value="{escape(e.schluessel)}"><button class="zweit klein">erledigt</button></form></li>')
    ziel = (k.get("erinnerungen") or {}).get("benachrichtigung")
    fuss = (f'<p class="leise">Benachrichtigung über Home Assistant: {escape(ziel)}.</p>' if ziel else
            '<p class="leise">Benachrichtigungen aufs Handy unter Einstellungen → Erinnerungen einschalten.</p>')
    return karte(f"Anstehend ({len(liste)})", f'<ul class="hinweise ohne">{"".join(zeilen)}</ul>' + fuss)



def fristen_karte(k: dict) -> str:
    import erinnerungen as er
    import kantone
    f = kantone.steuererklaerung(k)
    j = date.today().year
    def tt(mmtt):
        return f"{mmtt[3:]}.{mmtt[:2]}." if mmtt else "–"
    frist = er._datum(j, *(int(x) for x in f.gewaehlt.split("-")))
    tage = (frist - date.today()).days
    if tage < -7:
        frist = er._datum(j + 1, *(int(x) for x in f.gewaehlt.split("-")))
        tage = (frist - date.today()).days
    status = am.ROT if tage <= 14 else am.GELB if tage <= 60 else am.GRUEN
    zeilen = [
        ["Wohnkanton", escape(f"{f.name} ({f.kanton})" if f.kanton else "nicht erfasst")],
        ["Ordentliche Frist", tt(f.frist) + (" (eigene Angabe)" if f.quelle == "eigen" else "")],
        ["Erstreckung möglich bis", tt(f.erstreckung)],
        [licht(status) + "Nächste Frist", f"{frist:%d.%m.%Y}" + (" (erstreckt)" if f.quelle == "erstreckt" else "")
         + f" · in {tage} Tagen" if tage >= 0 else f"{frist:%d.%m.%Y} · abgelaufen"],
    ]
    hinweise = [h for h in [f.hinweis, "Datum auf der zugestellten Steuererklärung prüfen." if f.pruefen else ""] if h]
    return karte(f"Frist Steuererklärung {j - 1 if frist.year == j else j}", tabelle(["", ""], zeilen, zahlen_ab=9)
                 + (hinweisliste(hinweise) if hinweise else "")
                 + '<p class="leise">Eigene Frist oder gewährte Erstreckung unter Einstellungen → Erinnerungen eintragen.</p>')



# ---------------------------------------------------------------- Krankenkasse

def krankenkasse_karte(k: dict, db) -> str:
    import krankenkasse as kk
    vertraege = vi.alle(db)
    personen = kk.personen(k, vertraege)
    ergebnisse = {e.person.name: e for e in kk.haushalt(k, vertraege)}
    zeilen = []
    for i, p in enumerate(personen):
        liste = kk.FRANCHISEN_KINDER if p.kind else kk.FRANCHISEN_ERWACHSENE
        fr = "".join(f'<option{" selected" if f == p.franchise else ""}>{f}</option>' for f in liste)
        mo = "".join(f'<option value="{m}"{" selected" if m == p.modell else ""}>{escape(t)}</option>' for m, t in kk.MODELLE.items())
        un = (f'<option value="ja"{" selected" if p.unfall else ""}>ja</option>'
              f'<option value="nein"{"" if p.unfall else " selected"}>nein</option>')
        zeilen.append([
            f'<input type="hidden" name="name_{i}" value="{escape(p.name)}"><b>{escape(p.name)}</b>' + (" (Kind)" if p.kind else ""),
            f'<input name="praemie_{i}" value="{p.praemie_monat:g}" inputmode="decimal" style="min-width:90px">',
            f'<select name="franchise_{i}">{fr}</select>',
            f'<input name="kosten_{i}" value="{p.kosten_jahr:g}" inputmode="decimal" style="min-width:90px">',
            f'<select name="modell_{i}">{mo}</select>', f'<select name="unfall_{i}">{un}</select>'])
    form = (f'<form method="post" action="versicherungen/krankenkasse" data-status="Franchisen werden berechnet …">'
            + tabelle(["Person", "Prämie/Monat 2027", "Franchise", "Gesundheitskosten/Jahr", "Modell", "Unfall"], zeilen, zahlen_ab=9)
            + '<div class="zeile"><button>Speichern und rechnen</button></div></form>')
    if not ergebnisse:
        return karte("Krankenkasse: Franchise und Modell", '<p class="leise">Prämie pro Monat und erwartete Gesundheitskosten '
                     '(Arzt, Medikamente, Therapien – was die Grundversicherung bezahlt) eintragen.</p>' + form)
    total_heute = sum(e.kosten.get(e.person.franchise, 0) for e in ergebnisse.values())
    total_best = sum(e.kosten[e.beste] for e in ergebnisse.values())
    kpis = "".join([
        kpi(chf(total_heute), "Kosten pro Jahr heute (Prämie + Kostenbeteiligung)"),
        kpi(chf(total_best), "mit optimaler Franchise", "gut" if total_best < total_heute else ""),
        kpi(chf(total_heute - total_best), "Ersparnis pro Jahr", "", am.GELB if total_heute - total_best >= 200 else am.GRUEN),
    ])
    teile = []
    for e in ergebnisse.values():
        z = [[licht(am.GRUEN if f == e.beste else am.GRAU, "optimal" if f == e.beste else "") + str(f)
              + (" (heute)" if f == e.person.franchise else ""), chf(e.praemien[f]),
              chf(e.kosten[f] - e.praemien[f]), f"<b>{chf(e.kosten[f])}</b>" if f == e.beste else chf(e.kosten[f])]
             for f in e.franchisen]
        stufen = [0, 1000, 2000, 5000, 10000]
        z2 = [[f"bei Kosten {chf(s)}"] + [chf(e.tabelle[s][f]) for f in (e.franchisen[0], e.franchisen[-1])]
              + [str(min(e.franchisen, key=lambda f: e.tabelle[s][f]))] for s in stufen]
        teile.append(f'<h2>{escape(e.person.name)}</h2>'
                     + tabelle(["Franchise", "Prämie/Jahr", "Kostenbeteiligung", "Total/Jahr"], z)
                     + tabelle(["Szenario", f"Franchise {e.franchisen[0]}", f"Franchise {e.franchisen[-1]}", "beste"], z2))
    hinweise = [h for e in ergebnisse.values() for h in e.hinweise]
    geschaetzt = any(e.geschaetzt for e in ergebnisse.values())
    fuss = ('<p class="leise">Prämien anderer Franchisen geschätzt mit dem gesetzlichen Höchstrabatt (70 % des Risikounterschieds, '
            'höchstens 50 % der Prämie). Genaue Prämien und Kassenvergleich: priminfo.admin.ch; eigene Offerten unter '
            '<code>krankenkasse.personen[].angebote</code> (Franchise: Prämie/Monat) eintragen. Wechsel oder Franchise-Änderung '
            'bis 30. November eingeschrieben, Erhöhung der Franchise auch bei der eigenen Kasse.</p>' if geschaetzt else "")
    return karte("Krankenkasse: Franchise und Modell", f'<div class="kpis">{kpis}</div>' + hinweisliste(hinweise)
                 + "".join(teile) + fuss + "<details><summary>Angaben bearbeiten</summary>" + form + "</details>")



# ---------------------------------------------------------------- Frühpensionierung

def fruehpension_karte(k: dict, db) -> str:
    import fruehpension as fp
    frei = vm.nettovermoegen(db)["frei"]
    varianten = fp.vergleich(k, frei)
    frueh = fp.fruehestes_ohne_luecke(varianten)
    v65 = varianten[-1]
    kpis = "".join([
        kpi(str(frueh) if frueh is not None else "–", "Frühestes Alter ohne Pensionslücke", "",
            am.GRUEN if frueh is not None and frueh <= 62 else am.GELB if frueh is not None else am.ROT),
        kpi(chf(v65.einkommen), "Einkommen pro Jahr bei Pension mit 65"),
        kpi(chf(v65.bedarf), "Bedarf im Ruhestand pro Jahr"),
    ])
    zeilen = []
    for v in varianten:
        zeilen.append([licht(am.luecke_status(v.luecke, v.bedarf)) + f"<b>{v.alter}</b> ({v.jahr})",
                       f"{v.ahv_ab}", chf(v.ueberbrueckung), chf(v.ahv), chf(v.pk_rente), chf(v.kapital_rest), chf(v.verzehr),
                       f"<b>{chf(v.einkommen)}</b>", chf(-v.luecke) if v.luecke else "–"])
    tab = tabelle(["Rücktritt mit", "AHV ab", "Überbrückung", "AHV/Jahr", "PK-Rente/Jahr", "Kapital danach",
                   "Kapitalverzehr/Jahr", "Einkommen/Jahr", "Lücke"], zeilen)
    diagramm = dg.saeulen([str(v.alter) for v in varianten],
                          {"AHV": [v.ahv for v in varianten], "Pensionskasse": [v.pk_rente for v in varianten],
                           "Kapitalverzehr": [v.verzehr for v in varianten]},
                          linie_bei=v65.bedarf, linie_text=f"Bedarf {chf(v65.bedarf)}")
    hinweise = sorted({h for v in varianten for h in v.hinweise})
    erklaerung = ('<p class="leise">Alle Personen gehen im gleichen Alter in Pension. Pensionskasse: Guthaben bis zum Rücktritt '
                  '(Prognose der Kasse anteilig gekürzt), Umwandlungssatz pro Jahr vor 65 um '
                  f'{float((k.get("fruehpension") or {}).get("pk_kuerzung_uws", 0.2)):g} Prozentpunkte tiefer. AHV frühestens mit 63 '
                  '(−6,8 % pro Jahr); bis 65 Beiträge als Nichterwerbstätige (geschätzt). Überbrückung bis zur AHV = Bedarf minus PK-Renten, '
                  'aus dem Kapital. Das Sparen endet mit dem Rücktritt; das restliche Kapital wird bis zum gleichen Lebensende verzehrt. '
                  'Für die genaue Kürzung den Vorsorgeausweis bzw. die Kasse fragen.</p>')
    return karte("Frühpensionierung", f'<div class="kpis">{kpis}</div>' + diagramm + tab
                 + (hinweisliste(hinweise) if hinweise else "") + erklaerung)



# ---------------------------------------------------------------- Anlage-Check

def anlage_karte(k: dict, db) -> str:
    import anlage as an
    c = an.pruefen(k, db)
    cfg = an.konfiguration(k)
    if not c.finanz_total:
        return karte("Anlage-Check", '<p class="leise">Saldi erfassen oder Kontoauszüge importieren.</p>')
    nicht_angelegt = max(0, c.anlegbar - c.depot)
    kpis = "".join([
        kpi(chf(c.finanz_total), "Finanzvermögen (Konten, Depot, Krypto)"),
        kpi(f"{c.cash_anteil:.0f} %", "auf Konten", "", am.GELB if nicht_angelegt > 20000 else am.GRUEN),
        kpi(f"{c.aktien_ist:.0f} %", f"in Aktien/Krypto (Ziel langfristiger Topf {c.aktien_soll:.0f} %)"),
        kpi(chf(c.opportunitaet), "möglicher Mehrertrag pro Jahr", "", am.GELB if c.opportunitaet > 2000 else am.GRUEN),
    ])
    zeilen = [[escape(t.name), chf(t.betrag), escape(t.horizont), escape(t.empfehlung)] for t in c.toepfe]
    zeilen.append(["<b>Total</b>", f"<b>{chf(sum(t.betrag for t in c.toepfe))}</b>", "", ""])
    tab = tabelle(["Topf", "Betrag", "Horizont", "Umsetzung"], zeilen, zahlen_ab=1)
    kurz = sum(t.betrag for t in c.toepfe if t.horizont not in ("offen", "über 10 Jahre"))
    uebrig = sum(t.betrag for t in c.toepfe if t.horizont == "offen" and not t.name.startswith("Krypto"))
    toepfe = dg.saeulen(["Soll", "Ist"],
                        {"Reserve und zweckgebunden": [kurz, 0], "Langfristig angelegt": [c.toepfe[-1].betrag, c.depot],
                         "Konten": [0, c.liquide], "Krypto": [c.krypto, c.krypto], "Übriges": [uebrig, uebrig]})
    risiko = "".join(f'<option value="{r}"{" selected" if r == cfg["risiko"] else ""}>{r} ({cfg["aktienquote"][r]} % Aktien, '
                     f'{cfg["rendite"][r]:g} % Rendite)</option>' for r in ("tief", "mittel", "hoch"))
    form = f"""<form method="post" action="vermoegen/anlage"><div class="felder">
<label>Risikoprofil langfristiger Topf<select name="risiko">{risiko}</select></label>
<label>Zins Konto %<input name="zins_konto" value="{cfg['zins_konto']:g}" inputmode="decimal"></label>
<label>Zins sichere Anlage %<input name="zins_sicher" value="{cfg['zins_sicher']:g}" inputmode="decimal"></label></div>
<div class="zeile"><button class="zweit">Speichern</button></div></form>"""
    fuss = ('<p class="leise">Vorsorge 3b (verpfändet), Immobilie und Hypothek zählen nicht zum Finanzvermögen. Renditen sind '
            'langfristige Annahmen, keine Prognosen; keine Produktempfehlung. Das Risikoprofil hängt von Horizont, '
            'Verlusttoleranz und Einkommenssicherheit ab.</p>')
    return karte("Anlage-Check", f'<div class="kpis">{kpis}</div>' + tab + toepfe + hinweisliste(c.hinweise) + form + fuss)



# ---------------------------------------------------------------- Sensoren

def sensoren_karte(k: dict) -> str:
    import sensoren
    cfg = k.get("sensoren") or {}
    praefix = str(cfg.get("praefix") or "finanz")
    st_ = sensoren.status()
    if not cfg.get("aktiv", True):
        zustand = licht(am.GRAU) + "ausgeschaltet"
    elif st_["fehler"]:
        zustand = licht(am.ROT) + escape("Fehler: " + st_["fehler"])
    elif st_["zeit"]:
        zustand = licht(am.GRUEN) + f'{st_["anzahl"]} Sensoren, zuletzt {escape(st_["zeit"][11:16])} Uhr'
    else:
        zustand = licht(am.GELB) + "noch nicht geschrieben (startet kurz nach dem Start der App)"
    zeilen = [[f'<code class="entitaet">{escape(e)}</code>', escape(str(w)) + (f" {escape(u)}" if u and w not in ("unknown",) else "")]
              for e, w, u in st_["werte"]]
    liste = tabelle(["Entität", "Wert"], zeilen, zahlen_ab=1) if zeilen else ""
    beispiel = f"""# Dashboard-Karte
type: entities
title: Finanzen
entities:
  - sensor.{praefix}_ampel
  - sensor.{praefix}_nettovermoegen
  - sensor.{praefix}_naechste_frist
  - sensor.{praefix}_erinnerungen
  - sensor.{praefix}_pensionsluecke
  - sensor.{praefix}_krankenkasse_ersparnis

# Automation: Hinweis, wenn eine Ampel auf Rot geht
alias: Finanzen – Ampel rot
triggers:
  - trigger: state
    entity_id: sensor.{praefix}_ampel
    to: rot
actions:
  - action: notify.notify
    data:
      title: Finanzen
      message: "{{{{ state_attr('sensor.{praefix}_ampel', 'texte') }}}}"
"""
    form = ('<form method="post" action="einstellungen/sensoren" data-status="Sensoren werden geschrieben …">'
            '<div class="zeile"><button class="zweit">Sensoren jetzt schreiben</button></div></form>')
    return karte("Sensoren in Home Assistant",
                 f"<p>{zustand}</p>" + liste
                 + '<p class="leise">Die App schreibt die Werte beim Start, alle 15 Minuten und nach jeder Änderung. '
                   'Nach einem Neustart von Home Assistant erscheinen sie spätestens nach 15 Minuten wieder.</p>'
                 + f'<details><summary>Beispiele für Dashboard und Automation</summary><pre class="text">{escape(beispiel)}</pre></details>'
                 + form)



# ---------------------------------------------------------------- Nachlass

def nachlass(k: dict, db) -> str:
    import nachlass as nl
    cfg = k.get("nachlass") or {}
    faelle = nl.faelle(k, db)
    teile = []
    if not faelle:
        teile.append(karte("Nachlass", '<p class="leise">Der Nachlass-Vergleich braucht zwei Personen.</p>'))
    else:
        verheiratet = faelle[0].verheiratet
        kopf = ["", *[f"Tod von {escape(f.verstorben)}" for f in faelle]]

        def zeile(text, werte, ampeln=None):
            z = [text]
            for i, w in enumerate(werte):
                z.append((licht(ampeln[i]) if ampeln else "") + w)
            return z
        st_text = nl.partner_steuer(k, faelle[0].erbe_partner_mit)[1] if not verheiratet else "Ehegatten sind steuerfrei."
        zeilen = [
            zeile("Nachlass (Vermögen und Anteil Liegenschaft)", [chf(f.nachlass) for f in faelle]),
            zeile("davon Liegenschaft (Anteil nach Hypothek)", [chf(f.davon_liegenschaft) for f in faelle]),
            zeile("Erbe des Partners ohne Testament", [chf(f.erbe_partner_ohne) for f in faelle],
                  [am.ROT if not f.erbe_partner_ohne and f.nachlass else am.GRUEN for f in faelle]),
            zeile("Erbe des Partners mit Testament (höchstens)", [chf(f.erbe_partner_mit) for f in faelle]),
            zeile("Pflichtteil der Kinder", [chf(f.erbe_kinder_mit) for f in faelle]),
            zeile("Erbschaftssteuer des Partners", [chf(f.steuer_partner_mit) for f in faelle]),
            zeile("Vorsorgekapital an den Partner (PK, 3a)", [chf(f.vorsorge_kapital) for f in faelle]),
            zeile("– Steuer auf dem Vorsorgekapital", [chf(f.vorsorge_steuer) for f in faelle]),
            zeile("Risikopolicen an den Partner", [chf(f.policen) for f in faelle]),
            zeile("Renten pro Jahr an Partner und Kinder", [chf(f.renten_partner) for f in faelle]),
            zeile("Auszahlung an die Erben, damit der Partner das Haus behält", [chf(f.ausgleich_haus) for f in faelle],
                  [am.GRUEN if not f.ausgleich_haus else am.GELB if f.ausgleich_haus <= f.policen + f.vorsorge_kapital else am.ROT
                   for f in faelle]),
        ]
        hinweise = [h for f in faelle for h in f.hinweise]
        annahmen = ('<p class="leise">Nachlass = eigene Konten + Hälfte der gemeinsamen + Anteil an der Liegenschaft nach Hypothek '
                    '(Anteile unter <code>nachlass.anteil_immobilie</code>, sonst gleich). Mit Testament: verfügbare Quote '
                    + ("(Kinder behalten 1/4)." if verheiratet else "(bei Kindern die Hälfte, ohne Kinder alles).")
                    + f' Erbschaftssteuer: {escape(st_text)} Vorsorge und Policen fallen nicht in den Nachlass. '
                    'Güterrecht und Hausrat sind nicht berücksichtigt – für Testament und Erbvertrag eine Fachperson beiziehen.</p>')
        teile.append(karte("Was erhält der Partner?", tabelle(kopf, zeilen) + hinweisliste(hinweise) + annahmen))
    # Checkliste
    liste = nl.checkliste(k)
    namen = [p["name"] for p in k["personen"]]
    zeilen = []
    for s_, titel, text, status in liste:
        zellen = [f'<b>{escape(titel)}</b><br><span class="leise">{escape(text)}</span>']
        for n in namen:
            ok = status[n]
            zellen.append(f'<label style="flex-direction:row;align-items:center;gap:6px;color:var(--text)">{licht(am.GRUEN if ok else am.GELB)}'
                          f'<input type="checkbox" name="{s_}|{escape(n)}" value="1"{" checked" if ok else ""} style="width:auto"></label>')
        zeilen.append(zellen)
    offen = sum(1 for _, _, _, st_ in liste for v in st_.values() if not v)
    zusammen = escape(str(cfg.get("zusammen_seit") or ""))
    form = (f'<form method="post" action="nachlass/checkliste">'
            + tabelle(["Was", *[escape(n) for n in namen]], zeilen, zahlen_ab=9)
            + f'<div class="felder"><label>Gemeinsamer Haushalt seit (Jahr)<input name="zusammen_seit" value="{zusammen}" inputmode="numeric"></label></div>'
            + '<div class="zeile"><button>Speichern</button></div></form>')
    teile.append(karte(f"Checkliste ({offen} offen)", form))
    return "".join(teile)
