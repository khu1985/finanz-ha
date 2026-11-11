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
MAX_PARALLEL = 2          # höchstens zwei Seiten gleichzeitig – Home Assistant behält Rechenleistung und Speicher


def _nett(befehl: list[str]) -> list[str]:
    """Mit niedrigster Priorität laufen lassen (Home Assistant und die App-Seiten haben Vorrang)."""
    return ["nice", "-n", "19", *befehl] if shutil.which("nice") else befehl


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


def _grund(e: Exception) -> str:
    """Kurzer, lesbarer Grund eines fehlgeschlagenen Programmaufrufs (inkl. Fehlermeldung des Programms)."""
    if isinstance(e, subprocess.TimeoutExpired):
        return f"Zeitlimit {int(e.timeout)} s überschritten"
    if isinstance(e, subprocess.CalledProcessError):
        fehler = (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        letzte = [z.strip() for z in fehler.splitlines() if z.strip()][-1:] or [""]
        return f"Exit-Code {e.returncode}" + (f": {letzte[0][:200]}" if letzte[0] else "")
    return str(e)[:200]


def _entschluesselt(inhalt: bytes) -> bytes | None:
    """PDF mit Besitzer-Passwort (ohne Öffnungs-Passwort) als unverschlüsselte Kopie – pdftoppm lehnt manche ab."""
    try:
        import io
        from pypdf import PdfReader, PdfWriter
        leser = PdfReader(io.BytesIO(inhalt))
        if not leser.is_encrypted or not leser.decrypt(""):
            return None
        schreiber = PdfWriter(clone_from=leser)
        puffer = io.BytesIO()
        schreiber.write(puffer)
        return puffer.getvalue()
    except Exception:  # noqa: BLE001
        return None


def _bilder(pdf: Path, tmp: Path, seiten: int, name: str) -> list[Path]:
    """Seitenbilder: zuerst rendern (pdftoppm), sonst die eingebetteten Scan-Bilder direkt (pdfimages)."""
    try:
        subprocess.run(_nett(["pdftoppm", "-r", str(DPI), "-gray", "-png", "-l", str(seiten), str(pdf), str(tmp / "s")]),
                       check=True, capture_output=True, timeout=ZEIT_PRO_SEITE * seiten)
    except Exception as e:  # noqa: BLE001
        LOG.warning("OCR: %s – Seiten nicht gerendert (%s), versuche eingebettete Bilder", name or "PDF", _grund(e))
    bilder = sorted(tmp.glob("s*.png"))
    if bilder:
        return bilder
    if shutil.which("pdfimages"):
        try:
            subprocess.run(_nett(["pdfimages", "-j", "-l", str(seiten), str(pdf), str(tmp / "b")]),
                           check=True, capture_output=True, timeout=ZEIT_PRO_SEITE)
        except Exception as e:  # noqa: BLE001
            LOG.warning("OCR: %s – keine eingebetteten Bilder lesbar (%s)", name or "PDF", _grund(e))
        # kleine Bilder (Logos, Unterschriften) überspringen: nur Bilder ab einem Drittel des grössten
        alle = [b for b in tmp.glob("b-*") if b.suffix in (".jpg", ".ppm", ".pbm", ".pgm", ".png")]
        gross = max((b.stat().st_size for b in alle), default=0)
        bilder = sorted(b for b in alle if b.stat().st_size >= gross / 3)
    return bilder


def pdf_text(inhalt: bytes, name: str = "") -> str:
    """Text eines gescannten PDFs per OCR, Seiten getrennt mit Seitenvorschub wie bei pypdf."""
    if not verfuegbar():
        return ""
    seiten = int(_einstellungen().get("max_seiten") or MAX_SEITEN)
    with tempfile.TemporaryDirectory(prefix="ocr-") as tmp_:
        tmp = Path(tmp_)
        pdf = tmp / "d.pdf"
        pdf.write_bytes(inhalt)
        bilder = _bilder(pdf, tmp, seiten, name)
        if not bilder:
            klar = _entschluesselt(inhalt)
            if klar:
                pdf.write_bytes(klar)
                bilder = _bilder(pdf, tmp, seiten, name)
        if not bilder:
            LOG.warning("OCR: %s – keine Seitenbilder, Text bleibt leer", name or "PDF")
            return ""
        sprache = sprachen()
        # Seiten parallel auf höchstens der Hälfte der Kerne, jede Seite nur mit einem Thread
        umgebung = {**os.environ, "OMP_THREAD_LIMIT": "1"}

        def seite(bild: Path) -> str:
            try:
                return subprocess.run(_nett(["tesseract", str(bild), "stdout", "-l", sprache, "--psm", "3"]),
                                      capture_output=True, text=True, timeout=ZEIT_PRO_SEITE, env=umgebung).stdout
            except Exception as e:  # noqa: BLE001
                LOG.warning("OCR: Seite %s von %s fehlgeschlagen: %s", bild.stem, name, _grund(e))
                return ""
        with ThreadPoolExecutor(max_workers=max(1, min(MAX_PARALLEL, (os.cpu_count() or 2) // 2))) as pool:
            texte = list(pool.map(seite, bilder))
        text = "\n\f\n".join(texte)
        LOG.info("OCR: %s – %d Seite(n), %d Zeichen erkannt", name or "PDF", len(texte), len(text.strip()))
        return text
