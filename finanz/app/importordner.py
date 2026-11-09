"""Import-Ordner: Dateien, die in <Konfigurationsordner>/import/ kopiert werden, automatisch einlesen.

- finanz.yaml                → ersetzt die Konfiguration (vorherige Fassung als finanz.yaml.bak)
- vermoegen*.csv             → Konten und Saldi
- versicherungen*.csv        → Versicherungsliste (ohne PDF)
- bank*.csv, konto*.csv      → Kontoauszug aus dem E-Banking (Monatssaldi)
- versicherung*.pdf, police* → Versicherungsvertrag hochladen und analysieren
- steuer*.pdf, veranlagung*  → Steuererklärung / Veranlagung analysieren
- übrige *.pdf               → Vorsorgedokument (Vorsorgeausweis, 3a-, IK-Auszug)

Eingelesene Dateien werden nach import/erledigt/ verschoben.
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

import dokumente as dk
import steuerdokumente as sd
import konfig
import vermoegen as vm
import versicherungen as vi

LOG = logging.getLogger("finanz")


def ordner(daten: Path) -> Path:
    o = daten / "import"
    (o / "erledigt").mkdir(parents=True, exist_ok=True)
    return o


def einlesen(daten: Path, db) -> list[str]:
    meldungen = []
    imp = ordner(daten)
    for pfad in sorted(p for p in imp.iterdir() if p.is_file() and not p.name.startswith(".")):
        name = pfad.name.lower()
        try:
            inhalt = pfad.read_bytes()
            if name in ("finanz.yaml", "finanz.yml"):
                konfig.speichern(konfig.aus_text(inhalt.decode("utf-8")))
                konfig.laden()
                meldungen.append(f"{pfad.name}: Konfiguration übernommen")
            elif name.endswith(".csv") and name.startswith("vermoegen"):
                n, fehler = vm.csv_import(db, inhalt)
                meldungen.append(f"{pfad.name}: {n} Saldi" + (f", {len(fehler)} übersprungen" if fehler else ""))
            elif name.endswith(".csv") and (name.startswith("bank") or name.startswith("konto")):
                import bankimport as bi
                import budget as bu
                a, n = bi.aus_datei(db, inhalt, pfad.name)
                nb = bu.speichern(db, a.konto_vorschlag, bi.buchungen_lesen(inhalt), konfig.laden())
                meldungen.append(f"{pfad.name}: {n} Monatssaldi, {nb} Buchungen für {a.konto_vorschlag}")
            elif name.endswith(".csv") and name.startswith("versicherung"):
                n, fehler = vi.csv_import(db, inhalt)
                meldungen.append(f"{pfad.name}: {n} Verträge" + (f", {len(fehler)} übersprungen" if fehler else ""))
            elif name.endswith(".pdf") and _doppelt(db, daten, name, inhalt):
                meldungen.append(f"{pfad.name}: schon vorhanden, nicht erneut eingelesen")
            elif name.endswith(".pdf") and (name.startswith("versicherung") or name.startswith("police")):
                vid = vi.hochladen(db, daten, pfad.name, inhalt)
                import krankenkasse as kk
                kc = konfig.laden()
                if kk.police_uebernehmen(kc, vi.einer(db, vid)):
                    konfig.speichern(kc)
                meldungen.append(f"{pfad.name}: Versicherungsvertrag analysiert")
            elif name.endswith(".pdf") and (name.startswith("steuer") or name.startswith("veranlagung")):
                sd.hochladen(db, daten, pfad.name, inhalt)
                meldungen.append(f"{pfad.name}: Steuerdokument analysiert")
            elif name.endswith(".pdf"):
                dk.hochladen(db, daten, pfad.name, inhalt)
                meldungen.append(f"{pfad.name}: Vorsorgedokument analysiert")
            else:
                meldungen.append(f"{pfad.name}: unbekannter Dateityp, übersprungen")
                continue
            ziel = imp / "erledigt" / f"{datetime.now():%Y%m%d-%H%M%S}_{pfad.name}"
            shutil.move(str(pfad), ziel)
        except Exception as e:  # noqa: BLE001
            LOG.warning("Import %s fehlgeschlagen: %s", pfad.name, e)
            meldungen.append(f"{pfad.name}: Fehler – {e}")
    for m in meldungen:
        LOG.info("Import-Ordner: %s", m)
    return meldungen


def _doppelt(db, daten, name: str, inhalt: bytes) -> bool:
    import verwaltung as vw
    kurz = "v" if name.startswith(("versicherung", "police")) else "s" if name.startswith(("steuer", "veranlagung")) else "d"
    return not vw.neue_dateien(db, daten, kurz, [(name, inhalt)])[0]
