"""Linien- und gestapelte Säulendiagramme als SVG, ohne externe Bibliothek."""
from __future__ import annotations

from tausender import TS  # noqa: E402

from html import escape

FARBEN = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)"]
B, H = 640, 260
L, R, O, U = 78, 14, 16, 36


def chf_kurz(v: float) -> str:
    a = abs(v)
    if a >= 1_000_000:
        return f"{v / 1_000_000:.1f} Mio".replace(".", ",")
    if a >= 1000:
        return f"{v / 1000:.0f}k"
    return f"{v:.0f}"


def _skala(lo: float, hi: float, schritte: int = 4) -> list[float]:
    if hi == lo:
        hi = lo + 1
    roh = (hi - lo) / schritte
    mag = 10 ** len(str(int(roh))) / 10 if roh >= 1 else 1
    schritt = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= roh), default=roh)
    start = (lo // schritt) * schritt
    werte, v = [], start
    while v <= hi + schritt * 0.001:
        werte.append(v)
        v += schritt
    if werte[-1] < hi:
        werte.append(werte[-1] + schritt)
    return werte


def _legende(namen: list[str]) -> str:
    teile = []
    for i, n in enumerate(namen):
        teile.append(f'<span class="leg"><i style="background:{FARBEN[i % len(FARBEN)]}"></i>{escape(n)}</span>')
    return f'<div class="legende">{"".join(teile)}</div>' if len(namen) > 1 else ""


def linie(serien: dict[str, list[tuple]], titel: str = "") -> str:
    punkte = [p for s in serien.values() for p in s]
    if not punkte:
        return '<p class="leer">Noch keine Daten.</p>'
    xs = list(dict.fromkeys(p[0] for s in serien.values() for p in s))
    try:
        xs.sort()
    except TypeError:
        pass
    ys = [p[1] for p in punkte]
    ticks = _skala(min(0, min(ys)), max(ys))
    lo, hi = ticks[0], ticks[-1]
    bx, by = B - L - R, H - O - U
    px = {x: L + (bx * i / max(1, len(xs) - 1)) for i, x in enumerate(xs)}

    def py(y):
        return O + by - (y - lo) / (hi - lo) * by

    teile = [f'<svg viewBox="0 0 {B} {H}" role="img" aria-label="{escape(titel)}">']
    for t in ticks:
        teile.append(f'<line class="gitter" x1="{L}" x2="{B - R}" y1="{py(t):.1f}" y2="{py(t):.1f}"/>'
                     f'<text class="achse" x="{L - 6}" y="{py(t) + 4:.1f}" text-anchor="end">{chf_kurz(t)}</text>')
    schritt = max(1, len(xs) // 6)
    marken = [i for i in range(len(xs)) if i % schritt == 0]
    if marken and len(xs) - 1 - marken[-1] < schritt / 2 and len(marken) > 1:
        marken.pop()                                    # letzte Beschriftung nicht überlappen lassen
    if len(xs) - 1 not in marken:
        marken.append(len(xs) - 1)
    for n, i in enumerate(marken):
        x = xs[i]
        vorletzte = n == len(marken) - 2 and len(marken) >= 3
        klasse = "achse x2" if i != len(xs) - 1 and ((n % 2 == 1 and len(marken) > 4) or vorletzte) else "achse"
        anker = "end" if i == len(xs) - 1 and len(xs) > 1 else "middle"
        teile.append(f'<text class="{klasse}" x="{px[x]:.1f}" y="{H - 12}" text-anchor="{anker}">{escape(str(x))}</text>')
    for i, (name, s) in enumerate(serien.items()):
        d = " ".join(f"{'M' if j == 0 else 'L'}{px[x]:.1f},{py(y):.1f}" for j, (x, y) in enumerate(s))
        farbe = FARBEN[i % len(FARBEN)]
        teile.append(f'<path d="{d}" fill="none" stroke="{farbe}" stroke-width="2.5" stroke-linejoin="round"/>')
        if s:
            x, y = s[-1]
            teile.append(f'<circle cx="{px[x]:.1f}" cy="{py(y):.1f}" r="3.5" fill="{farbe}"><title>{escape(name)} {x}: {y:,.0f}</title></circle>' >> TS)
    teile.append("</svg>")
    return f'<figure class="diagramm">{"".join(teile)}{_legende(list(serien))}</figure>'


def saeulen(kategorien: list[str], serien: dict[str, list[float]], linie_bei: float | None = None,
            linie_text: str = "") -> str:
    """Gestapelte Säulen; optional eine horizontale Referenzlinie (z. B. Bedarf)."""
    if not kategorien:
        return '<p class="leer">Noch keine Daten.</p>'
    summen = [sum(s[i] for s in serien.values()) for i in range(len(kategorien))]
    hi_roh = max(summen + ([linie_bei] if linie_bei else []))
    ticks = _skala(0, hi_roh)
    hi = ticks[-1]
    bx, by = B - L - R, H - O - U
    breite = bx / len(kategorien)

    def py(y):
        return O + by - y / hi * by

    teile = [f'<svg viewBox="0 0 {B} {H}" role="img">']
    for t in ticks:
        teile.append(f'<line class="gitter" x1="{L}" x2="{B - R}" y1="{py(t):.1f}" y2="{py(t):.1f}"/>'
                     f'<text class="achse" x="{L - 6}" y="{py(t) + 4:.1f}" text-anchor="end">{chf_kurz(t)}</text>')
    for i, kat in enumerate(kategorien):
        x = L + i * breite + breite * 0.2
        w = breite * 0.6
        basis = 0.0
        for j, (name, werte) in enumerate(serien.items()):
            v = werte[i]
            if v <= 0:
                continue
            y1, y0 = py(basis + v), py(basis)
            teile.append(f'<rect x="{x:.1f}" y="{y1:.1f}" width="{w:.1f}" height="{max(0.5, y0 - y1 - 1):.1f}" '
                         f'rx="3" fill="{FARBEN[j % len(FARBEN)]}"><title>{escape(name)}: {v:,.0f}</title></rect>' >> TS)
            basis += v
        # Bei vielen Säulen jede zweite Beschriftung als «x2» markieren – auf dem Handy ausgeblendet
        klasse = "achse x2" if len(kategorien) > 7 and i % 2 == 1 and i != len(kategorien) - 1 else "achse"
        teile.append(f'<text class="{klasse}" x="{x + w / 2:.1f}" y="{H - 12}" text-anchor="middle">{escape(kat)}</text>')
    if linie_bei:
        y = py(linie_bei)
        teile.append(f'<line class="ziel" x1="{L}" x2="{B - R}" y1="{y:.1f}" y2="{y:.1f}"/>'
                     f'<text class="achse ziel-text" x="{B - R}" y="{y - 6:.1f}" text-anchor="end">{escape(linie_text)}</text>')
    teile.append("</svg>")
    return f'<figure class="diagramm">{"".join(teile)}{_legende(list(serien))}</figure>'
