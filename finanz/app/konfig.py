"""Laden und Speichern von finanz.yaml im Konfigurationsordner der App."""
from __future__ import annotations

import copy
import os
import shutil
from pathlib import Path

import yaml

APP_DIR = Path(__file__).resolve().parent
VORLAGE = APP_DIR / "default_config.yaml"


def datenordner() -> Path:
    pfad = Path(os.environ.get("FINANZ_DATA", "/config"))
    pfad.mkdir(parents=True, exist_ok=True)
    return pfad


def konfig_pfad() -> Path:
    return datenordner() / "finanz.yaml"


def vorlage() -> dict:
    with VORLAGE.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _mischen(basis: dict, eigen: dict) -> dict:
    """Fehlende Schlüssel aus der Vorlage ergänzen (rekursiv, nur für dicts)."""
    ergebnis = copy.deepcopy(basis)
    for k, v in (eigen or {}).items():
        if isinstance(v, dict) and isinstance(ergebnis.get(k), dict):
            ergebnis[k] = _mischen(ergebnis[k], v)
        else:
            ergebnis[k] = v
    return ergebnis


def laden() -> dict:
    pfad = konfig_pfad()
    basis = vorlage()
    if not pfad.exists():
        speichern(basis)
        return basis
    with pfad.open(encoding="utf-8") as f:
        eigen = yaml.safe_load(f) or {}
    k = _mischen(basis, eigen)
    # Personen werden nicht mit der Vorlage gemischt (sonst Musterpersonen), aber Unterschlüssel ergänzt
    if "personen" in eigen:
        muster = basis["personen"][0]
        k["personen"] = [_mischen(muster, p) for p in eigen["personen"]]
    if "haushalt" in eigen and "kinder" in eigen["haushalt"]:
        k["haushalt"]["kinder"] = eigen["haushalt"]["kinder"] or []
    return k


def speichern(k: dict) -> None:
    pfad = konfig_pfad()
    if pfad.exists():
        shutil.copy2(pfad, pfad.with_suffix(".yaml.bak"))
    tmp = pfad.with_suffix(".yaml.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        yaml.safe_dump(k, f, allow_unicode=True, sort_keys=False)
    tmp.replace(pfad)


def aus_text(text: str) -> dict:
    daten = yaml.safe_load(text)
    if not isinstance(daten, dict):
        raise ValueError("Die Konfiguration muss ein YAML-Objekt sein.")
    if not isinstance(daten.get("personen", []), list) or not daten.get("personen"):
        raise ValueError("Mindestens eine Person unter «personen» erfassen.")
    return daten
