# Änderungen

## 0.3.0 – 2026-11-08

- Version im Kopf und in der Fusszeile, Seite «Änderungen» mit diesem Changelog
- Seite «Protokoll»: neueste Einträge zuerst, Filter nach Stufe, Download; Protokolldatei wird bei 1 MB rotiert
- Statusanzeige: Ladebalken beim Seitenwechsel, Hinweisfenster mit Spinner bei Uploads, Import, KI und Beratern
  (mit Anzahl und Grösse der Dateien), Knöpfe während der Verarbeitung gesperrt
- Statuszeile auf der Übersicht: Stand der Saldi, Verträge, Dokumente, offene TODO, wartende Importe, KI, Warnungen
- Handy: Kopfzeile mit Symbolen für Protokoll und Einstellungen, wischbare Navigation (aktive Seite sichtbar),
  Kennzahlen zweispaltig, breite Tabellen als Karten, grössere Bedienelemente, keine Zoom-Sprünge bei Eingaben

## 0.2.1 – 2026-11-08

- Behoben: App startete mit 0.2.0 nicht – AppArmor-Profil nach der Vorlage von Home Assistant neu aufgebaut,
  Start ohne s6-overlay direkt mit Python

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
