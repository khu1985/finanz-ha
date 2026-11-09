# Änderungen

## 0.14.0 – 2026-11-09

- **Zuzug in die Schweiz** pro Person in den Stammdaten (Datum, Herkunftsland, Bewilligung, Eintritt in die Schweizer
  Pensionskasse, Rente aus dem Ausland, ordentliche Veranlagung):
  - AHV: Beitragsjahre höchstens ab Zuzug (ohne IK-Auszug lückenlos ab Zuzug), Erziehungsgutschriften nur für Jahre in
    der Schweiz, Hinweis auf Teilrente und Renten aus EU/EFTA-Staaten
  - Pensionskasse: Einkaufsgrenze 20 % des versicherten Lohns pro Jahr in den ersten 5 Jahren (BVV 2 Art. 60b) im
    PK-Einkauf-Optimierer und als Warnung bei geplanten Einkäufen; neues Feld «Versicherter Lohn»
  - 3a-Nachzahlung nur für Jahre in der Schweiz
  - Renten aus dem Ausland in Pensionslücke (ab Bezugsalter), Frühpensionierung, Diagramm und Sensor
  - Quellensteuer (B/L): Hinweis und jährliche Erinnerung, die nachträgliche ordentliche Veranlagung bis 31. März zu
    beantragen; ab 120'000 Lohn obligatorisch
  - Erinnerungen rund um den Zuzug: Anmeldung Gemeinde (14 Tage), Krankenkasse (3 Monate), Vorsorge aus dem Ausland,
    Führerausweis und Fahrzeug (12 Monate)
  - Karte «Zuzug in die Schweiz» unter Vorsorge, Hinweise in der Übersicht und für die Berater
## 0.13.0 – 2026-11-09

- **Budget und Cashflow** (neue Seite unter Bestand): der Bank-Import übernimmt neben den Monatssaldi die einzelnen
  Buchungen (doppelte werden erkannt). Kategorien über Stichworte (Händler, Krankenkassen, Versicherer, Steuerämter,
  Energieversorger …) und eigene Regeln; Umbuchungen zwischen eigenen Konten werden erkannt, Einzahlungen in 3a, PK
  und Depot zählen als Sparen. Einnahmen, Ausgaben, Sparquote und Ausgaben pro Kategorie und Monat (Diagramm), Buchungen
  ohne Kategorie mit Zuordnung per Klick, Vergleich mit dem Sparpotenzial der Planung und Übernahme per Knopf;
  Ampel «Budget», Sensoren `ausgaben_monat`, `gespart_monat`, `sparquote`; Angaben für die Berater
- **Teuerung im Rechenmodell** (`annahmen.teuerung`, Standard 1 %): nominale Prognosen (Vorsorgeausweis, 3a,
  Kapitalbezug) werden in heutige Franken umgerechnet, der Kapitalverzehr rechnet mit realer Rendite, PK-Renten verlieren
  im Ruhestand Kaufkraft, die AHV folgt dem Mischindex. Pensionslücke zusätzlich im Durchschnitt und nach 20 Jahren
  (Diagramm, Ampel, Sensor-Attribute); gilt auch für die Frühpensionierung
## 0.12.0 – 2026-11-09

- **Nachlass und Absicherung** (neue Seite unter Planung): was der Partner bzw. die Partnerin bei einem Todesfall
  erhält – Erbteil mit und ohne Testament, Erbschaftssteuer des Wohnkantons (Basel-Landschaft geprüft: Konkubinat ab
  5 Jahren gemeinsamem Wohnsitz 15 % nach Freibetrag 30'000, sonst 30 %), AHV- und PK-Leistungen, Todesfallkapital,
  Betrag zum Behalten der Liegenschaft; Checkliste pro Person (Testament, Begünstigungen PK/3a/Policen,
  Vorsorgeauftrag, Patientenverfügung, Konkubinatsvertrag, Notfallordner); Ampel «Nachlass»
- **Individualbesteuerung im Heiratsvergleich:** Bilanz mit gemeinsamer Besteuerung und mit Individualbesteuerung
  ab `kennzahlen.individualbesteuerung_ab` (Standard 2032, Volksabstimmung vom 8. März 2026 angenommen) – der
  Heiratsnachteil bei den Einkommenssteuern fällt dann weg
- **Vermögenssteuer** in der Steuerrechnung: Betrag aus der Veranlagung oder steuerbares Vermögen ×
  `kennzahlen.vermoegen_promille`; Steuerdokumente erkennen Vermögenssteuer und steuerbares Vermögen; neue Kennzahl
  «Steuern total pro Jahr» (Übersicht, Sensor)
- Tausendertrennzeichen setzen keine Apostrophe mehr an Stelle von Kommas im Text
## 0.11.0 – 2026-11-09

- **Sensoren für Home Assistant** (`sensor.finanz_*`): Nettovermögen, freies Vermögen, Liquidität, Alter der Saldi,
  Einkommen im Ruhestand, Pensionslücke, Ersatzquote, frühestes Pensionsalter, Steuern, Grenzsteuersatz, Frist der
  Steuererklärung, Amortisation, Versicherungsprämien, Krankenkassen-Ersparnis, Geld ohne Zweck, Ampel (gesamt, mit
  Bereichen als Attribut), Anzahl «handeln», Erinnerungen und nächste Frist – mit Einheiten, Geräte- und Zustandsklassen
  für Verlauf und Statistik
- Geschrieben beim Start, alle 15 Minuten und nach jeder Änderung; Status, Liste und Beispiele für Dashboard und
  Automation unter Einstellungen; Präfix einstellbar, abschaltbar

## 0.10.0 – 2026-11-09

- **Krankenkasse: Franchise und Modell** (Versicherungen): pro Person und Kind Prämie, Franchise, erwartete
  Gesundheitskosten, Modell und Unfalldeckung erfassen; Gesamtkosten je Franchise, optimale Franchise, Ersparnis,
  Kosten-Szenarien und Break-even; Hinweise zu Hausarzt/Telmed und Unfall sistieren. Prämien anderer Franchisen
  geschätzt mit dem gesetzlichen Höchstrabatt oder aus eigenen Offerten. Ampel und Krankenkassen-Erinnerung mit Ersparnis
- **Frühpensionierung** (Szenarien): Rücktritt mit 58 bis 65 für den Haushalt – AHV frühestens mit 63, gekürzter
  Umwandlungssatz, Überbrückung bis zur AHV inkl. Beiträge als Nichterwerbstätige, Kapitalverzehr bis zum gleichen
  Lebensende; frühestes Alter ohne Pensionslücke
- **Anlage-Check** (Vermögen): Aufteilung in Notreserve, zweckgebundene Amortisation, PK-Einkäufe und langfristigen Topf;
  Aktienquote nach Risikoprofil, Krypto-Anteil, Klumpenrisiko, Mehrertrag bei Anlage statt Konto; Ampel

## 0.9.0 – 2026-11-09

- **Frist der Steuererklärung nach Wohnkanton** (alle 26 Kantone, Stand Steuerjahr 2025): ordentliche Frist und
  spätestmögliche Erstreckung; eigene Frist laut Formular und gewährte Erstreckung in den Einstellungen; neue Karte
  «Frist Steuererklärung» unter Steuern mit Ampel
- **Erinnerungen aus der Steueroptimierung:** optimaler PK-Einkauf des laufenden Jahres (aus dem Optimierer, solange
  kein Einkauf geplant ist), 3a-Lücke des Vorjahres nachzahlen (aus den Steuerdokumenten), Liegenschaftsunterhalt vor
  dem Wegfall des Eigenmietwerts, weiteres 3a-Konto für den gestaffelten Bezug
- Erinnerung zur Steuererklärung mit Tipps je nach Haushalt (Unterhalt effektiv, Kinderabzug im Konkubinat, Erstreckung)

## 0.8.0 – 2026-11-09

- **Menü wie in der vZEV-App:** Seiten in Gruppen (Überblick, Planung, Bestand, App); auf grossen Bildschirmen als
  Seitenleiste, auf Tablets als Leiste mit Trennern, auf dem Handy hinter dem Knopf «Menü» als zweispaltige Liste;
  Ampelpunkte bleiben, beim Protokoll die Zahl der Warnungen von heute
- **Darstellung umschalten:** Knopf neben der Version wechselt Auto (wie das Gerät) → Hell → Dunkel; die Wahl bleibt
  im Browser gespeichert, ohne Aufblitzen beim Laden

## 0.7.0 – 2026-11-08

- **Hypothekar-Strategie** (Szenarien): SARON, Festhypotheken und Mischungen bzw. Staffelungen über drei
  SARON-Szenarien (tief, basis, stress) – Zinskosten über den Horizont, höchste Jahreskosten, Zinsbindung, Ampel nach
  Robustheit, Empfehlung für maximale Sicherheit, Richtwert für eine Forward-Festhypothek; Sätze anpassbar
- **Bank-Import:** Kontoauszüge als CSV aus dem E-Banking (Raiffeisen, UBS, ZKB, PostFinance, Kantonalbanken u. a.);
  erkennt Kodierung, Trennzeichen, Vorspann, IBAN, Bank und Spalten und übernimmt den letzten Saldo jedes Monats;
  ohne Saldo-Spalte Rückrechnung ab einem Endsaldo; im Import-Ordner als bank*.csv oder konto*.csv
- **Erinnerungen:** 3a-Einzahlung, PK-Einkauf, Krankenkasse, Kündigungsfristen, Steuererklärung, Vorsorgeausweise,
  Kennzahlen, Hypothek, Saldi und eigene Erinnerungen; auf der Übersicht mit Ampel und «erledigt»; optional
  Benachrichtigung über Home Assistant (Notify-Dienst oder Meldung) beim Erscheinen und bei Fälligkeit

## 0.6.0 – 2026-11-08

- Neue Seite **Szenarien**
- **PK-Einkauf optimieren:** verteilt das Einkaufspotenzial (oder ein Budget) schrittweise auf die Jahre mit der höchsten
  Ersparnis pro Franken, beachtet die Sperrfrist vor einem Kapitalbezug und eine Mindest-Ersparnis; zeigt Ersparnis pro
  Jahr, Vergleich mit «alles in einem Jahr», Netto-Vorteil inkl. Zins und Kapitalbezugssteuer sowie die Kurve der
  Grenz-Ersparnis. Der Plan lässt sich als geplante Einkäufe übernehmen.
- **Verheiratet oder Konkubinat:** Einkommenssteuern heute (Bund mit Verheiratetenabzug, Zweiverdienerabzug und
  Elterntarif, Kanton mit Splitting), AHV mit Plafonierung, Steuer auf Kapitalbezügen, Renten für Hinterbliebene,
  Gesamtbilanz und rechtliche Unterschiede (Erbrecht, PK, Güterrecht)
- Neue Kennzahlen für die Abzüge des Bundes und `steuern.ehe_splitting_divisor` für den Kanton

## 0.5.0 – 2026-11-08

- **Ampeln** (grün = in Ordnung, gelb = prüfen, rot = handeln, grau = keine Daten):
  - Übersicht: Ampel-Kacheln für Ruhestand, Liquidität, Tragbarkeit, Amortisation, Steuern, Steuerdokumente,
    Versicherungsschutz, Kündigungsfristen, Invalidität, Todesfall und Daten – sortiert nach Dringlichkeit, mit Link
  - Navigation: Punkt an Seiten mit gelber oder roter Ampel
  - Kennzahlen (Pensionslücke, Ersatzquote, Tragbarkeit, Belehnung, nächste Kündigungsfrist), Deckungscheck,
    Kündigungstermine, Risiko Invalidität/Tod, Amortisation, Dokumente (übernommen) und Beratungen (beantwortet)

## 0.4.0 – 2026-11-08

- **Steuerdokumente:** Steuererklärungen, Veranlagungsverfügungen und Steuerrechnungen hochladen; Erkennung von
  Steuerperiode, Person, steuerbarem Einkommen Kanton/Bund, Vermögen, Steuerbeträgen, Eigenmietwert, Mietertrag und Abzügen
- Mehrjahresvergleich pro Person, Grenzsteuersatz aus zwei Veranlagungen, Abgleich Erklärung ↔ Veranlagung
- Hinweise zu 3a, PK-Einkauf, Liegenschaftsunterhalt, Eigenmietwert 2029, Mietertrag und Kinderabzug im Konkubinat
- Übernahme in die Steuer-Einstellungen (auch neue Person bei Konkubinat), optional per KI auslesen
- Berater erhalten die Steuerhistorie als Fakten; Import-Ordner erkennt steuer*.pdf und veranlagung*.pdf
- Kantonssteuer als Potenzkurve statt linear: grosse Abzüge (z. B. PK-Einkauf) werden realistischer bewertet

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
