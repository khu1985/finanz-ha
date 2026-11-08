# Änderungen

## 0.2.0 – 2026-11-08

- **Versicherungen:** Policen als PDF hochladen oder als CSV-Liste importieren; Erkennung von Versicherer,
  Sparte, Prämie, Daten, Fristen, Franchise und Summen; Deckungscheck (Grundversicherung, Haftpflicht, Hausrat,
  Gebäude, Todesfall, Doppelversicherungen, Unfalldeckung, Franchise), Kündigungstermine, Prämien nach Sparte
- **Risiko Invalidität und Tod** pro Person aus AHV, Pensionskasse und externen Policen, mit Hinweisen für Konkubinatspaare
- **Vorsorgedokumente:** Vorsorgeausweis, 3a- und IK-Auszug hochladen, Werte erkennen, prüfen und einer Person übernehmen
- **Anlageberater:** sechs Beraterprofile, Situationsbeschreibung, Fakten aus der Planung, Amortisations-Szenario bis
  zur Fälligkeit der Hypothek; Auftrag an die KI-Aufgabe von Home Assistant oder zum Kopieren
- **Konkubinat:** getrennte Besteuerung (steuern.personen), Elterntarif für Alleinstehende mit Kind, keine AHV-Plafonierung
- Prognose laut Vorsorgeausweis (Alterskapital, Altersrente), Mieteinnahmen in der Tragbarkeit
- **Import-Ordner** für persönliche Daten (finanz.yaml, CSV, PDF) – nichts davon gehört ins Repository
- **AppArmor-Profil** (Sicherheitsbewertung 8 zusammen mit Ingress)

## 0.1.0 – 2026-11-08

Erste Fassung.

- Übersicht mit Nettovermögen, Einkommen im Ruhestand, Pensionslücke, Ersatzquote, Steuern und Hinweisen
- Vorsorge: AHV (Rentenskala 44, Splitting, Erziehungsgutschriften, Plafond, 13. AHV-Rente), Pensionskasse
  (Ausweis oder BVG-Minimum, Einkäufe, Kapitalbezug, Sperrfrist-Warnung), Säule 3a, Pensionslücke
- Steuern: direkte Bundessteuer nach Tarif, Kanton/Gemeinde als Näherung um die letzte Veranlagung,
  3a und PK-Einkauf simulieren, Kapitalbezug alles auf einmal vs. gestaffelt
- Wohnen: Tragbarkeit, maximaler Kaufpreis, Wegfall des Eigenmietwerts ab 2029
- Vermögen: Konten, Saldi erfassen, CSV-Import, Verlauf
- Einstellungen als Formular oder YAML, Import/Export von finanz.yaml
