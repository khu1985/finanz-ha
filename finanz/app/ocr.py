"""Texterkennung (OCR) für gescannte PDFs mit tesseract und pdftoppm (poppler).

Wird nur genutzt, wenn ein PDF keinen eingebetteten Text hat. Fehlen die Programme, bleibt der Text leer wie bisher.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

LOG = logging.getLogger("finanz")
MAX_SEITEN = 10           # Policen und Ausweise: das Wichtige steht vorne
DPI = 300
ZEIT_PRO_SEITE = 90       # Sekunden (Raspberry Pi)
MIN_ZEICHEN = 40          # weniger Text gilt als «gescannt»


def verfuegbar() -> bool:
    return bool(shutil.which("tesseract") and shutil.which("pdftoppm"))


@lru_cache(maxsize=1)
def sprachen() -> str:
    """Installierte Sprachen in sinnvoller Reihenfolge (deu+fra+ita+eng, soweit vorhanden)."""
    try:
        aus = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=20).stdout
    except Exception:  # noqa: BLE001
        return "eng"
    da = {z.strip() for z in aus.splitlines()[1:]}
    gewaehlt = [s for s in ("deu", "fra", "ita", "eng") if s in da]
    return "+".join(gewaehlt) or "eng"


def braucht_ocr(text: str) -> bool:
    return len("".join(text.split())) < MIN_ZEICHEN


def pdf_text(inhalt: bytes, name: str = "") -> str:
    """Text eines gescannten PDFs per OCR, Seiten getrennt mit Seitenvorschub wie bei pypdf."""
    if not verfuegbar():
        return ""
    with tempfile.TemporaryDirectory(prefix="ocr-") as tmp:
        pdf = Path(tmp) / "d.pdf"
        pdf.write_bytes(inhalt)
        try:
            subprocess.run(["pdftoppm", "-r", str(DPI), "-gray", "-png", "-l", str(MAX_SEITEN), str(pdf),
                            str(Path(tmp) / "s")], check=True, capture_output=True, timeout=ZEIT_PRO_SEITE * MAX_SEITEN)
        except Exception as e:  # noqa: BLE001
            LOG.warning("OCR: PDF %s nicht in Bilder umwandelbar: %s", name, e)
            return ""
        seiten = []
        for bild in sorted(Path(tmp).glob("s*.png")):
            try:
                r = subprocess.run(["tesseract", str(bild), "stdout", "-l", sprachen(), "--psm", "3"],
                                   capture_output=True, text=True, timeout=ZEIT_PRO_SEITE)
                seiten.append(r.stdout)
            except Exception as e:  # noqa: BLE001
                LOG.warning("OCR: Seite %s von %s fehlgeschlagen: %s", bild.stem, name, e)
        text = "\n\f\n".join(seiten)
        LOG.info("OCR: %s – %d Seite(n), %d Zeichen erkannt", name or "PDF", len(seiten), len(text.strip()))
        return text
