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
    import waehrung
    if not pfad.exists():
        speichern(basis)
        waehrung.uebernehmen(basis)
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
    waehrung.uebernehmen(k)
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


# ---------------------------------------------------------------- Namen: Vorname in der App, voller Name in Schreiben

def _eintrag(k: dict, name: str) -> tuple[dict | None, bool]:
    """Person bzw. Kind mit diesem Namen (Anzeigename): (Eintrag, ist_kind)."""
    for p in k.get("personen") or []:
        if p.get("name") == name:
            return p, False
    for c in (k.get("haushalt") or {}).get("kinder") or []:
        if c.get("name") == name:
            return c, True
    return None, False


def nachname(k: dict, name: str) -> str:
    """Nachname einer Person bzw. eines Kindes; Kinder ohne eigenen erben den des (ersten) Elternteils."""
    e, kind = _eintrag(k, name)
    if not e:
        return ""
    n = str(e.get("nachname") or "").strip()
    if n or not kind:
        return n
    eltern = str(e.get("eltern") or "gemeinsam")
    personen = k.get("personen") or []
    kandidaten = [p for p in personen if p.get("name") == eltern] or personen
    return next((str(p.get("nachname") or "").strip() for p in kandidaten if p.get("nachname")), "")


def vollname(k: dict, name: str) -> str:
    """«Vorname Nachname» für Verfügungen, Verträge und Schreiben; in der App reicht der Vorname."""
    n = nachname(k, name)
    return f"{name} {n}" if n and not name.endswith(n) else name


def namen_ausschreiben(k: dict, text: str) -> str:
    """Im Text eines Schreibens jeden Vornamen der Personen und Kinder durch den vollen Namen ersetzen."""
    import re
    namen = [p.get("name") for p in k.get("personen") or []] + \
        [c.get("name") for c in (k.get("haushalt") or {}).get("kinder") or []]
    for name in sorted({n for n in namen if n}, key=len, reverse=True):
        n = nachname(k, name)
        if n and not name.endswith(n):
            text = re.sub(rf"(?<![\w-]){re.escape(name)}(?![\w-])(?!\s+{re.escape(n)}\b)", f"{name} {n}", text)
    return text


def namen_trennen(name: str) -> tuple[str, str]:
    """«Anna Muster-Beispiel» → («Anna», «Muster-Beispiel»); mehrteilige Vornamen bleiben vorne."""
    teile = name.split()
    return (" ".join(teile[:-1]), teile[-1]) if len(teile) > 1 else (name, "")


def person_umbenennen(k: dict, alt: str, neu: str) -> None:
    """Überall in der Konfiguration, wo der alte Name als Schlüssel oder Wert steht, den neuen eintragen."""
    def gehe(x):
        if isinstance(x, dict):
            return {(neu if key == alt else key): gehe(v) for key, v in x.items()}
        if isinstance(x, list):
            return [gehe(v) for v in x]
        return neu if x == alt else x
    for key in list(k):
        if key != "personen":
            k[key] = gehe(k[key])
    for p in k.get("personen") or []:
        for key in list(p):
            if key != "name":
                p[key] = gehe(p[key])
