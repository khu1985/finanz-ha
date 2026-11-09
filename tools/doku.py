"""Dokumentation synchron halten.

    python3 tools/doku.py            # Mermaid-Blöcke im README aus docs/*.mmd übernehmen, SVGs neu rendern (mmdc)
    python3 tools/doku.py --pruefen  # nur prüfen (läuft auch in den Tests)

Geprüft wird:
- jede Mermaid-Quelle docs/*.mmd ist als SVG gerendert (Prüfsumme der Quelle im SVG) und steht unverändert im README
- die Version aus finanz/config.yaml hat einen Eintrag im CHANGELOG (oberster Eintrag)
- jedes Modul unter finanz/app/ steht in der Dateitabelle des README
- jede Seite der Navigation steht in der Seitentabelle von DOCS.md
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DOCS = WURZEL / "docs"
README = WURZEL / "README.md"
MARKE = "<!-- quelle-sha1: {} -->"


def _sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _readme_bloecke(text: str) -> list[tuple[str, int, int]]:
    """(Name, Start, Ende) des Mermaid-Inhalts nach jedem Bild docs/<name>.svg."""
    erg = []
    for m in re.finditer(r"\(docs/([a-z0-9-]+)\.svg\)\]\(docs/\1\.svg\)", text):
        start = text.find("```mermaid\n", m.end())
        if start < 0:
            continue
        start += len("```mermaid\n")
        ende = text.find("```", start)
        erg.append((m.group(1), start, ende))
    return erg


def pruefen() -> list[str]:
    fehler = []
    readme = README.read_text("utf-8")
    bloecke = {n: readme[a:e] for n, a, e in _readme_bloecke(readme)}
    for mmd in sorted(DOCS.glob("*.mmd")):
        quelle = mmd.read_text("utf-8")
        svg = mmd.with_suffix(".svg")
        if not svg.exists():
            fehler.append(f"{svg.name} fehlt")
        elif MARKE.format(_sha(quelle)) not in svg.read_text("utf-8"):
            fehler.append(f"{svg.name} ist nicht aus der aktuellen {mmd.name} gerendert")
        if mmd.stem not in bloecke:
            fehler.append(f"README: Diagramm {mmd.stem} fehlt")
        elif bloecke[mmd.stem].strip() != quelle.strip():
            fehler.append(f"README: Mermaid-Block {mmd.stem} weicht von {mmd.name} ab")
    version = re.search(r'^version:\s*"?([\d.]+)"?', (WURZEL / "finanz/config.yaml").read_text("utf-8"), re.M).group(1)
    erster = re.search(r"^## ([\d.]+)", (WURZEL / "finanz/CHANGELOG.md").read_text("utf-8"), re.M)
    if not erster or erster.group(1) != version:
        fehler.append(f"CHANGELOG: oberster Eintrag {erster.group(1) if erster else '–'} statt Version {version}")
    for py in sorted((WURZEL / "finanz/app").glob("*.py")):
        if f"finanz/app/{py.name}" not in readme and py.name != "__init__.py":
            fehler.append(f"README: Modul {py.name} fehlt in der Dateitabelle")
    sys.path.insert(0, str(WURZEL / "finanz/app"))
    try:
        import seiten
        docs = (WURZEL / "finanz/DOCS.md").read_text("utf-8")
        for _, eintraege in seiten.NAVIGATION:
            for _, titel in eintraege:
                if f"| {titel} |" not in docs:
                    fehler.append(f"DOCS.md: Seite «{titel}» fehlt in der Seitentabelle")
    finally:
        sys.path.pop(0)
    return fehler


def synchronisieren() -> None:
    readme = README.read_text("utf-8")
    for name, a, e in reversed(_readme_bloecke(readme)):
        mmd = DOCS / f"{name}.mmd"
        if mmd.exists():
            readme = readme[:a] + mmd.read_text("utf-8").rstrip() + "\n" + readme[e:]
    README.write_text(readme, "utf-8")
    mmdc = shutil.which("mmdc")
    for mmd in sorted(DOCS.glob("*.mmd")):
        svg = mmd.with_suffix(".svg")
        quelle = mmd.read_text("utf-8")
        if svg.exists() and MARKE.format(_sha(quelle)) in svg.read_text("utf-8"):
            continue
        if not mmdc:
            print(f"mmdc fehlt – {svg.name} nicht gerendert")
            continue
        args = [mmdc, "-i", str(mmd), "-o", str(svg), "-b", "white", "-t", "neutral"]
        pp = Path.home() / ".mmdc-puppeteer.json"
        if pp.exists():
            args[1:1] = ["-p", str(pp)]
        subprocess.run(args, check=True, capture_output=True)
        svg.write_text(svg.read_text("utf-8").rstrip() + "\n" + MARKE.format(_sha(quelle)) + "\n", "utf-8")
        print(f"{svg.name} gerendert")


if __name__ == "__main__":
    if "--pruefen" not in sys.argv:
        synchronisieren()
    probleme = pruefen()
    for p in probleme:
        print("✗", p)
    sys.exit(1 if probleme else 0)
