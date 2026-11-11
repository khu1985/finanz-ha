"""Texterkennung (OCR) für gescannte PDFs mit tesseract und pdftoppm (poppler).

Wird nur genutzt, wenn ein PDF keinen eingebetteten Text hat. Fehlen die Programme, bleibt der Text leer wie bisher.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

LOG = logging.getLogger("finanz")
MAX_SEITEN = 6            # Policen und Ausweise: das Wichtige steht vorne
DPI = 200                 # reicht für gedruckten Text und ist auf dem Raspberry Pi gut doppelt so schnell wie 300
ZEIT_PRO_SEITE = 180      # Sekunden (Raspberry Pi)
MIN_ZEICHEN = 40          # weniger Text gilt als «gescannt»
STANDARD_SPRACHEN = "deu" # jede weitere Sprache kostet Zeit; in finanz.yaml unter ocr.sprachen änderbar


def _einstellungen() -> dict:
    try:
        import konfig
        return konfig.laden().get("ocr") or {}
    except Exception:  # noqa: BLE001
        return {}


def verfuegbar() -> bool:
    return bool(shutil.which("tesseract") and shutil.which("pdftoppm"))


@lru_cache(maxsize=1)
def installiert() -> frozenset[str]:
    try:
        aus = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=20).stdout
    except Exception:  # noqa: BLE001
        return frozenset()
    return frozenset(z.strip() for z in aus.splitlines()[1:] if z.strip())


def sprachen(gewuenscht: str | None = None) -> str:
    """Gewünschte und installierte Sprachen, z. B. «deu» oder «deu+fra» (Standard: Deutsch)."""
    gewuenscht = gewuenscht or str(_einstellungen().get("sprachen") or STANDARD_SPRACHEN)
    da = installiert()
    gewaehlt = [s for s in gewuenscht.replace(",", "+").split("+") if s.strip() in da]
    return "+".join(s.strip() for s in gewaehlt) or ("deu" if "deu" in da else "eng")


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
            subprocess.run(["pdftoppm", "-r", str(DPI), "-gray", "-png", "-l",
                            str(int(_einstellungen().get("max_seiten") or MAX_SEITEN)), str(pdf),
                            str(Path(tmp) / "s")], check=True, capture_output=True, timeout=ZEIT_PRO_SEITE * MAX_SEITEN)
        except Exception as e:  # noqa: BLE001
            LOG.warning("OCR: PDF %s nicht in Bilder umwandelbar: %s", name, e)
            return ""
        sprache = sprachen()
        # Seiten parallel auf allen Kernen, dafür jede Seite nur mit einem Thread (schneller als tesseract-intern)
        umgebung = {**os.environ, "OMP_THREAD_LIMIT": "1"}

        def seite(bild: Path) -> str:
            try:
                return subprocess.run(["tesseract", str(bild), "stdout", "-l", sprache, "--psm", "3"],
                                      capture_output=True, text=True, timeout=ZEIT_PRO_SEITE, env=umgebung).stdout
            except Exception as e:  # noqa: BLE001
                LOG.warning("OCR: Seite %s von %s fehlgeschlagen: %s", bild.stem, name, e)
                return ""
        bilder = sorted(Path(tmp).glob("s*.png"))
        with ThreadPoolExecutor(max_workers=max(1, min(4, os.cpu_count() or 1))) as pool:
            seiten = list(pool.map(seite, bilder))
        text = "\n\f\n".join(seiten)
        LOG.info("OCR: %s – %d Seite(n), %d Zeichen erkannt", name or "PDF", len(seiten), len(text.strip()))
        return text
