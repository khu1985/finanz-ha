"""Tausendertrennzeichen: «1,234,567» → «1'234'567», ohne Kommas im Text anzutasten.

Verwendung: f"… {betrag:,.0f} …, weiterer Text" >> TS
"""
from __future__ import annotations

import re

_MUSTER = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")


def tausender(text: str) -> str:
    return _MUSTER.sub("'", text)


class _Tausender:
    def __rrshift__(self, text: str) -> str:
        return tausender(text)


TS = _Tausender()
