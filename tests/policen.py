"""Erfundene Policen für die Tests (keine echten Personen oder Vertragsnummern)."""

KVG = """Helsana Versicherungen AG
Versicherungspolice 2027
Versicherte Person: Person 1
Versicherten-Nr. 123.4567.89
Obligatorische Krankenpflegeversicherung nach KVG (Grundversicherung)
Modell: Hausarztmodell
Franchise CHF 300
Unfalldeckung: inkl. Unfall
Gültig ab 01.01.2027
Prämie pro Monat CHF 412.50
"""

HAUSRAT = """Die Mobiliar
Hausrat- und Privathaftpflichtversicherung
Versicherungsnehmer: Person 2
Police-Nr. HR-998877
Versicherungsbeginn 15.03.2022
Vertragsablauf 14.03.2027
Hausrat Versicherungssumme CHF 120'000
Einfacher Diebstahl auswärts eingeschlossen
Privathaftpflicht Garantiesumme CHF 5'000'000
Selbstbehalt CHF 200
Kündigungsfrist: 3 Monate vor Ablauf
Jahresprämie total CHF 612.40
"""

LEBEN = """Swiss Life AG
Gemischte Lebensversicherung Säule 3b
Policennummer L-445566
Versicherungsbeginn 01.07.2015
Ablauf 30.06.2050
Erlebensfallkapital garantiert, Überschussbeteiligung nicht garantiert
Todesfallkapital CHF 150'000
Rückkaufswert per 01.07.2026: CHF 18'200
Jahresprämie CHF 3'000.00
"""

RECHTSSCHUTZ_1 = """AXA-ARAG Rechtsschutz
Privat- und Verkehrsrechtsschutz
Police-Nr. RS-1001
Beginn 01.01.2024
Prämie jährlich CHF 330.00
"""

RECHTSSCHUTZ_2 = """Coop Rechtsschutz
Rechtsschutzversicherung Privat
Police-Nr. CR-2002
Beginn 01.06.2025
Total zu bezahlen CHF 290.00
"""


def pdf(text: str) -> bytes:
    """Kleine PDF mit Textebene erzeugen (reportlab)."""
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    puffer = io.BytesIO()
    c = canvas.Canvas(puffer, pagesize=A4)
    y = 800
    for zeile in text.splitlines():
        c.drawString(50, y, zeile)
        y -= 16
    c.save()
    return puffer.getvalue()

PK_AUSWEIS = """Pensionskasse Muster
Persönlicher Vorsorgeausweis per 01.01.2026
Versicherte Person: Person 1
Jahreslohn 120'000.00
Sparbeitrag total 14'400.00
Vorhandenes Altersguthaben 250'000.00
Maximal möglicher Einkauf 180'000.00
Projiziertes Altersguthaben im Alter 65 1'200'000.00
Altersrente im Alter 65 pro Jahr 60'000.00
Umwandlungssatz 5.00 %
Invalidenrente 72'000.00
Invaliden-Kinderrente 14'400.00
Lebenspartnerrente 43'200.00
Waisenrente 14'400.00
Todesfallkapital 50'000.00
"""

DREI_A = """VIAC Vorsorgestiftung 3a
Säule 3a Kontoauszug per 31.12.2025
Kontoinhaber: Person 2
Einzahlungen 2025 7'258.00
Gesamtvermögen 48'500.25
"""

STEUERERKLAERUNG = """Kanton Muster – Steuererklärung 2025
Steuerperiode 2025
Steuerpflichtige Person: Person 1
Ziffer 100 Nettolohn aus unselbständiger Erwerbstätigkeit 150'000
Ziffer 180 Eigenmietwert 20'000
Ziffer 185 Mietertrag 15'300
Total der Einkünfte 185'300
Ziffer 300 Beiträge Säule 3a 5'000
Ziffer 310 Schuldzinsen 9'000
Ziffer 320 Liegenschaftsunterhalt 4'000
Ziffer 330 Berufsauslagen 4'500
Steuerbares Einkommen Staat 140'000 Bund 145'000
Steuerbares Vermögen 600'000
"""

VERANLAGUNG_2025 = """Veranlagungsverfügung Steuerperiode 2025
Steuerpflichtige Person: Person 1
Steuerbares Einkommen Staat 141'200 Bund 145'000
Steuerbares Vermögen 600'000
Staatssteuer 14'000.00
Gemeindesteuer 9'000.00
Direkte Bundessteuer 7'500.00
"""

VERANLAGUNG_2024 = """Veranlagungsverfügung Steuerperiode 2024
Steuerpflichtige Person: Person 1
Steuerbares Einkommen Staat 131'200 Bund 135'000
Staats- und Gemeindesteuer 20'200.00
"""
