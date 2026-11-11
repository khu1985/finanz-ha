# Änderungen

## 0.28.0 – 2026-11-11

- **Verfügungen (neue Seite unter Planung):** Entwürfe mit Fragen und Optionen für
  - **Testament:** Ziel wählen (Partner maximal begünstigen, Nutzniessung für den Ehegatten nach Art. 473 ZGB, Kinder
    gesetzlich, eigene Quoten), Ersatzerben, Liegenschaft, Vermächtnisse, Willensvollstrecker; Tabelle «Wer erhält
    was?» mit gesetzlichem Erbteil, Pflichtteil (Erbrecht seit 2023) und Betrag; Warnung bei verletzten Pflichtteilen
  - **Vorsorgeauftrag, Patientenverfügung, Konkubinatsvertrag, Begünstigung Säule 3a**
  - Text zum Abschreiben bzw. Drucken mit Formvorschrift; im Nachlass-Fragebogen als «in Arbeit» vermerken
- Nachlass-Checkliste und Fragebögen verlinken auf die passenden Entwürfe

## 0.27.0 – 2026-11-11

- **Fragebögen zum Nachlass** (Nachlass → Checkliste → «Fragebogen» bzw. Nachlass → Fragebögen): pro Bereich die
  konkreten Angaben – Testament (Form, Datum, wo das Original liegt, wer was erhält), Pensionskasse (Meldung des
  Partners, Bestätigung, Leistungen), 3a und Policen (Begünstigte, schriftlich festgelegt), Vorsorgeauftrag
  (beauftragte Person, Ersatz, Infostar), Patientenverfügung (Vertretung, Hinterlegung, Organspende),
  Konkubinatsvertrag, Liegenschaft (Eigentumsform, Regelung, Finanzierung der Auszahlung), Willensvollstrecker,
  Zugänge, digitaler Nachlass und Bestattungswünsche – je Person oder für den Haushalt
- Die Antworten erscheinen im **Notfallordner** (auch in der Druckfassung); sind die wichtigen Angaben vollständig,
  lässt sich der Punkt direkt in der Checkliste abhaken
- Navigation markiert auch Unterseiten (z. B. Konto, Fragebögen) beim richtigen Menüpunkt
- **Invaliditätsleistungen bei Versicherungen:** neue Felder pro Vertrag (Rente pro Jahr, Invaliditätskapital,
  Wartefrist, Rente bis Alter, Ursache, Mindest-Invaliditätsgrad, Prämienbefreiung), automatisch aus dem Vertragstext
  gelesen – auch aus bestehenden Dokumenten beim Neu-Sichten nach dem Update (bei von Hand bearbeiteten Verträgen nur
  leere Felder); fliessen als «Extern» in «Risiko Invalidität und Tod», mit Hinweisen zu langer Wartefrist und
  reinen Unfallpolicen

## 0.26.0 – 2026-11-11

- **Konten verwalten (Vermögen → Konto anklicken):** eigene Seite pro Konto mit
  - Name, Art, Person, Währung und Notiz ändern – beim Umbenennen wandern die Budget-Buchungen mit
  - allen Saldi in einer Tabelle: Datum und Betrag direkt korrigieren, einzelne oder ausgewählte löschen, neuen
    Saldo hinzufügen; Verlauf des Kontos als Grafik
  - Zusammenführen doppelter Konten (z. B. von Hand erfasst und später per Bank-Import angelegt) inkl. Buchungen
    ohne Doppelte
  - Auflösen: Saldo 0 ab einem Datum, Verlauf bleibt; aufgelöste Konten stehen eingeklappt unter der Liste
- Kontenliste mit Auswahl-Kästchen zum Löschen mehrerer Konten; Löschen entfernt auch die Buchungen des Kontos
- **Übersichtlicher:**
  - Krankenkasse: eine Zeile pro Person (heute, optimal, Ersparnis, ab welchen Kosten die tiefste Franchise lohnt);
    die Details als eine aufklappbare Tabelle Franchise × Gesundheitskosten statt zwei langer Tabellen pro Person
  - Hinzufügen steht überall direkt unter der Liste: Versicherungen (Hochladen, Liste importieren), Vermögen
    (Saldo erfassen, Bank-Import, CSV), Budget (Kontoauszüge), Kinder (Erfassen zuerst); Auswertungen danach
  - Prämien nach Sparte als horizontale Balken – lange Spartennamen überlappen nicht mehr
  - Berater: Amortisations-Szenario eingeklappt (Bearbeiten unter Wohnen)
- **Kopieren** (Vorschläge, Berater-Auftrag) funktioniert jetzt auch im Home-Assistant-Fenster; geht es nicht, wird der
  Text markiert

## 0.25.4 – 2026-11-11

- **Berater:** nutzen jetzt die eingestellte KI-Entität (Einstellungen → KI); bisher immer die Standard-KI-Aufgabe
  von Home Assistant

## 0.25.3 – 2026-11-11

- **Vorschläge:** Meldungen aus dem Protokoll zählen nur seit dem Start der installierten Version – was ein Update
  behoben hat, verschwindet sofort statt erst nach 30 Tagen

## 0.25.2 – 2026-11-11

- **Weniger Last auf dem Home Assistant:** Die Texterkennung gescannter PDFs läuft mit niedrigster Priorität und
  höchstens zwei Seiten gleichzeitig (vorher bis vier) – Home Assistant behält Rechenleistung und Speicher
- **Texterkennung robuster:** Lässt sich ein PDF nicht in Seitenbilder umwandeln, liest die App die eingebetteten
  Scan-Bilder direkt (schneller) und entsperrt PDFs mit Besitzer-Passwort; der Grund eines Fehlers steht lesbar im
  Protokoll (Fehlermeldung des Programms statt nur «exit status 1»)

## 0.25.1 – 2026-11-11

- **Neu sichten blieb hängen:** Die Texterkennung lief bei jeder Sichtung für alle Scans neu (10 Seiten, 300 dpi,
  drei Sprachen – auf dem Raspberry Pi Minuten pro Dokument), und der Knopf wartete auf eine bereits laufende
  Sichtung. Jetzt:
  - erkannter Text wird wiederverwendet – OCR nur einmal pro Dokument
  - schneller: Deutsch (einstellbar unter `ocr: sprachen`), 6 Seiten, 200 dpi, Seiten parallel auf allen Kernen
  - Neu sichten läuft im Hintergrund mit Fortschrittsanzeige («7 von 25»); ein zweiter Klick startet keinen
    zweiten Lauf

## 0.25.0 – 2026-11-10

Umgesetzt aus den ersten Vorschlägen (App → Vorschläge):

- **Texterkennung (OCR) für gescannte PDFs** mit tesseract (Deutsch, Französisch, Italienisch); bereits
  hochgeladene Scans werden nach dem Update beim automatischen Neu-Sichten ausgelesen
- **smile** wird als Versicherer erkannt (bisher Helvetia, weil smile zu Helvetia gehört)
- **Grundversicherung:** Kündigungsfrist 1 Monat (Ende Jahr, Eingang bis 30.11.) statt 3 Monate
- Protokoll ohne Rauschen: abgebrochene Verbindungen (Broken pipe, Connection reset) sind keine Fehler mehr,
  harmlose pypdf-Warnungen zu defekten PDFs werden nicht mehr protokolliert

## 0.24.0 – 2026-11-10

- **Vorschläge (App → Vorschläge):** leitet aus den eigenen Daten ab, wo die App besser werden kann – von Hand
  korrigierte Werte in Policen, Vorsorge- und Steuerdokumenten (Erkennung lag falsch), nicht erkannte Felder,
  Arten und Sparten, gescannte PDFs ohne Text, Fehler und Warnungen im Protokoll (30 Tage, gruppiert), fehlende
  kantonale Werte und Einstellungen mit roter Ampel; dazu eigene Ideen
- Alles anonymisiert (Namen, Orte, Policen-/Kontonummern, Dateinamen, E-Mail, IBAN, AHV-Nr., Daten, Beträge) und
  nach Wichtigkeit sortiert; Weitergeben nur von Hand: kopieren, als .md herunterladen oder als GitHub-Issue
  vorbefüllt öffnen; Vorschläge ausblenden oder als gemeldet markieren
- **Sicherheit:** pypdf 5.1 → 7.0.1 (behebt die von Dependabot gemeldeten Lücken: präparierte PDFs konnten die
  App mit Endlosschleifen oder Speicherverbrauch blockieren), PyYAML 6.0.3

## 0.23.0 – 2026-11-10

- **Sicherheit:** Die App beantwortet im Home Assistant nur noch Anfragen über Ingress – andere Apps im internen
  Netz können sie nicht mehr direkt aufrufen (403)
- Repository: Tests nur mit Leserechten, Dependabot für Pakete und GitHub Actions, lokale Werkzeug-Einstellungen und
  Zugangsdaten (`.claude/settings.local.json`, `.mcp.json`, `.env`, Schlüssel) in `.gitignore`
- Doku: Empfehlungen zu Backup, Konten, Samba, KI und Fernzugriff

## 0.22.0 – 2026-11-09

- **Eigenmietwert Staat und Bund getrennt:** Bund = Staat × Kantonsfaktor (BL 1,2) oder eigener Wert; Wohnen,
  Steuererklärungs-Checkliste und Deklaration je Person zeigen beide Werte
- **Unternutzungsabzug:** Zimmer und dauernd ungenutzte Zimmer erfassen; Abzug = Eigenmietwert × ungenutzte Zimmer ÷
  (Zimmer + 2 Nebenräume beim Haus bzw. + 1 bei Stockwerkeigentum), mit Hinweis auf die Voraussetzungen
- **Unterhaltspauschale nach Kanton:** BL Staat 20 % / 25 %, Bund 10 % / 20 % (bis bzw. über 10 Jahre); Steuereffekt
  des Wegfalls ab 2029 mit Grenzsätzen von Staat und Bund getrennt
- «Selbstnutzung seit» in den Einstellungen und in der Checkliste

## 0.21.0 – 2026-11-09

- **Teilweise vermietete Liegenschaft:** neue Einstellung «Vermieteter Anteil %»; der Eigenmietwert (ganze
  Liegenschaft) wird auf den selbst bewohnten Teil reduziert, Mieteinnahmen sind voll steuerbar, die
  Unterhaltspauschale (10 % bzw. 20 % je nach Alter des Gebäudes) gilt auf beides
- **Eigentumsanteil pro Person** («Anteil an der Liegenschaft %») für getrennte Steuererklärungen: Wohnen zeigt
  die Deklaration je Person (Eigenmietwert, Mieteinnahmen, Schuldzinsen, Pauschale); auch Steuererklärungs-Checkliste
  und Nachlass rechnen damit
- **Wegfall Eigenmietwert ab 2029** mit gemischter Nutzung: Mieteinnahmen und Unterhalt des vermieteten Teils
  bleiben, Schuldzinsen anteilig nach vermieteter Liegenschaft zum Gesamtvermögen
- Übernahme aus Steuerdokumenten rechnet deklarierten Eigenmietwert und Mietertrag auf die ganze Liegenschaft hoch;
  Ampeln für vermieteten Anteil, Mieteinnahmen und Eigentumsanteile

## 0.20.0 – 2026-11-09

- **Dokumente-Übersicht unter App:** alle hochgeladenen Policen, Vorsorge- und Steuerdokumente und Buchungen pro
  Konto mit Grösse, Datum, Person und Link zum Original; Filter nach Bereich, Kennzahlen (Speicher, Duplikate,
  ohne Text)
- **Löschen überall:** einzeln, Auswahl (mit «alle wählen») oder alle eines Bereichs – auf der Dokumente-Seite und
  direkt in den Listen Versicherungen, Vorsorge und Steuern; Buchungen pro Konto löschen
- **Duplikate:** dieselbe Datei wird beim Hochladen und im Import-Ordner nicht ein zweites Mal eingelesen;
  vorhandene Duplikate lassen sich mit einem Klick entfernen
- Weniger «database is locked» beim Löschen, während die App Dokumente im Hintergrund neu sichtet

## 0.19.0 – 2026-11-09

- **Ampeln bei den Einstellungen:** jedes Feld zeigt, ob der Wert plausibel ist (grün), wahrscheinlich falsch,
  veraltet oder fehlend (gelb, mit kurzem Grund unter dem Feld), ein wichtiger Wert fehlt bzw. unmöglich ist (rot)
  oder optional leer bleibt (grau). Geprüft werden u. a. Geburtsdatum, Pensionierungsalter, Jahreslohn (Monatslohn
  statt Jahreslohn?), AHV-Beitragsjahre gegenüber dem Alter, PK-Guthaben und Alter des Vorsorgeausweises, Sparbeitrag,
  Umwandlungssatz, Ausweis-Kapital und -Rente (vertauscht?), 3a über dem Maximum oder ohne Guthaben, Partnermeldung
  im Konkubinat, Steuerwerte, Kanton, Bedarf im Ruhestand, Wohnen, Zuzug und Datumsformate
- Oben eine Zusammenfassung (plausibel, prüfen, fehlen) und die Liste «Zu prüfen» mit Sprung zum Feld; Ampel
  «Einstellungen» in der Übersicht
## 0.18.1 – 2026-11-09

- **Neu sichten: geänderte Werte als Tabelle** unter Einstellungen → «Dokumente neu sichten»: pro Dokument (Bereich,
  Versicherer bzw. Datei, Sparte, Person, mit Link) jedes geänderte Feld mit Wert vorher und neu, auch neu angelegte
  Zusatzversicherungen; Modell, Sparte und Unfalldeckung in Klartext
## 0.18.0 – 2026-11-09

- **Dokumente nach Updates neu sichten:** Nach jedem App-Update liest die App alle gespeicherten Policen, Vorsorge-
  und Steuerdokumente im Hintergrund mit der neuen Erkennung neu – ohne erneutes Hochladen. Von Hand oder per KI
  korrigierte Werte bleiben erhalten (nur der Text wird erneuert), die gewählte Person bleibt. Ändern sich Werte eines
  bereits übernommenen Vorsorge- oder Steuerdokuments, erscheint es wieder als «noch nicht übernommen»;
  Krankenkassen-Policen gehen neu in den Krankenkassen-Rechner, eine neu erkannte Zusatzversicherung wird als eigener
  Vertrag angelegt; Buchungen werden mit den aktuellen Regeln neu kategorisiert
- Karte «Dokumente neu sichten» unter Einstellungen mit dem Ergebnis der letzten Sichtung und Knopf (optional auch
  bearbeitete Dokumente); Knopf «Alle Dokumente neu sichten» bei Versicherungen, Vorsorge- und Steuerdokumenten;
  Hinweis in der Übersicht nach einem Update mit geänderten Werten
## 0.17.2 – 2026-11-09

- **Krankenkassen-Policen genauer auslesen:** Policen mit Grund- und Zusatzversicherung im gleichen PDF (z. B. Atupri)
  werden seitenweise gelesen: Monatsprämie, Modell (Standard, Hausarzt/CareMed, HMO, Telmed), Franchise, Unfalldeckung
  samt Unfallanteil, versicherte Person mit Geburtsdatum, Versicherten-Nr., gültig ab, erste Anlaufstelle (Arzt bzw.
  Praxis), Prämienregion; die Zusatzversicherung wird als eigener Vertrag mit Produkten, Rabatten und Prämie erfasst
- KVG-Policen werden beim Hochladen automatisch in den Krankenkassen-Rechner übernommen (Kinder auch unter anderem
  Namen); die Karte zeigt eine Übersicht aller Policen mit Grund- und Zusatzprämien pro Monat und Jahr
- Neue Empfehlungen: günstigeres Modell bei der gleichen Kasse im Haushalt, Frist 30.11. mit verbleibenden Tagen,
  Unfalldeckung (8-Stunden-Regel, ohne Lohn), Modelle für Kinder, Zusatzversicherungen nicht vor einer Zusage kündigen,
  Zahnversicherung für Kinder, Notfälle im Ausland; Hinweis, wenn keine Gesundheitskosten erfasst sind
## 0.17.1 – 2026-11-09

- **Upload mehrerer Dateien:** Home Assistant nimmt pro Anfrage höchstens 16 MB an («Maximum request body size
  16777216 exceeded»). Der Browser lädt mehrere Dateien jetzt einzeln hoch – mit Fortschritt «Datei 2 von 5» und
  einer gemeinsamen Meldung. Einzelne Dateien über 16 MB werden übersprungen mit dem Hinweis auf den Import-Ordner.
  Gilt für Vorsorge-, Steuer- und Versicherungsdokumente sowie Kontoauszüge
- **Säule 3b bei den Vorsorgedokumenten:** neue Art «Säule 3b (freie Vorsorge: Police oder Konto)» mit Erkennung von
  Rückkaufswert bzw. Guthaben, Prämie, Erlebensfall- und Todesfallkapital. Das Guthaben wird als Saldo eines
  Vorsorge-Kontos unter «Vermögen» übernommen (Konto wählbar; eine gleichnamige verpfändete 3b unter Wohnen wird
  nachgeführt), die Todesfallleistung als Todesfallkapital der Policen; Hinweise zu Vermögenssteuer und Begünstigung
- **Versicherungen:** in der Vertragsliste ein Direktlink «PDF öffnen» zum Original und eine Ampel für den
  ausgelesenen Text (rot: kein Text gefunden, z. B. gescanntes PDF; gelb: sehr wenig Text; grau: aus einer Liste
  erfasst, ohne Dokument)
- Ampel und Hinweis beim ausgelesenen Text auch auf den Detailseiten und in den Listen der Vorsorge- und
  Steuerdokumente
## 0.17.0 – 2026-11-09

- **Jahresbericht** (neue Seite unter Überblick): die App speichert jeden Monat einen Stand (Nettovermögen, freies
  Vermögen, Konten, Wertschriften, Schulden, Pensionskasse, 3a, Einkommen im Ruhestand, Pensionslücke, Steuern,
  Budget, Ampeln). Der Bericht vergleicht ein Jahr mit dem Vorjahr (fehlt ein Stand, Nettovermögen aus den Saldi per
  Jahresende – mit Hinweis, wenn Konten ohne Saldo sind), fasst das Wichtigste zusammen, zeigt Ampeln mit Vorjahr und
  die Massnahmen der nächsten 12 Monate; «Stand jetzt speichern», Drucken bzw. PDF
- **Konten in Fremdwährung:** Währung pro Konto (CHF, EUR, USD, GBP), Umrechnung in Franken für Nettovermögen,
  Verlauf, Budget, Anlage-Check, Steuer-Checkliste und Notfallordner; Kurse unter `waehrungen.kurse` (Standard EUR
  0.92, Stand 09.11.2026) oder auf Wunsch täglich der Referenzkurs der EZB (`waehrungen.automatisch`); Bank-Import
  erkennt die Währung; Anlage-Check zeigt den Fremdwährungsanteil; Rente aus dem Ausland in EUR erfassbar
- **Liegenschaft: Wert und Erneuerung** (Seite Wohnen): geschätzter Wert mit Wertentwicklung und Belehnung, Bauteile
  mit Lebensdauer und Kosten (Richtwerte nach Anteil am Gebäudeversicherungswert oder eigene Werte, Stockwerkeigentum
  nur eigene Teile), Erneuerungen über 30 Jahre, empfohlener Erneuerungsfonds, steuerliche Abziehbarkeit bis zum
  Wegfall des Eigenmietwerts, Hinweise (auf zwei Jahre verteilen, Förderbeiträge, Belehnung); Wert als Saldo
  übernehmen; Ampel «Liegenschaft» und Erinnerungen vor fälligen Erneuerungen
- Tabellen mit langen Texten erscheinen auf dem Handy als Karten (Anlage-Check, Heiratsvergleich, Notfallordner)
## 0.16.0 – 2026-11-09

- **Teilzeit und Kinderbetreuung** (Szenarien): Pensum einer Person für einen Zeitraum reduzieren und sehen, was es
  kostet – weniger Nettolohn (nach Sozialabzügen und PK-Beitrag), weniger Steuern (inkl. wegfallendem
  Betreuungsabzug), eingesparte Kita-Kosten, Saldo pro Jahr und was ein Arbeitstag netto bringt. Langfristig:
  AHV-Rente (mit Plafond und Splitting), PK-Kapital und -Rente, Summe über den Ruhestand, IV-Leistungen. Hinweise zu
  BVG-Eintrittsschwelle, Koordinationsabzug und Konkubinat. Neues Feld «Pensum» pro Person, Kennzahl `sozialabzug`
- **Steuererklärung vorbereiten** (neue Seite unter Planung): Checkliste pro Steuerjahr aus den Daten der App –
  Frist, Quellensteuer, Kinder, Lohnausweise, 3a, PK-Einkäufe, Kinderbetreuung, Krankheitskosten, Prämien, Spenden
  (aus dem Budget), Eigenmietwert, Schuldzinsen, Unterhalt, Saldi aller Konten per 31.12. (fehlende werden markiert),
  Lebensversicherungen, Vorjahreswerte aus der Veranlagung. Punkte abhaken, Fortschritt, Drucken; Ampel in den
  Monaten vor der Frist; die Erinnerung zur Frist führt auf die Checkliste
- **Notfallordner** (neue Seite unter Planung): Personen, erste Schritte im Todesfall (mit Hinweisen fürs
  Konkubinat), Konten mit letztem Saldo, Vorsorge und Leistungen im Todesfall, Versicherungen, Liegenschaft, offene
  Punkte der Nachlass-Checkliste; wichtige Kontakte und Ablageorte erfassen; Druckansicht bzw. PDF ohne Menü und
  Formulare; Abhaken in der Nachlass-Checkliste per Knopf
- Teilzeit-Tabelle fasst gleiche Jahre zusammen; Druckansicht für alle Seiten (ohne Menü, Tabellen als Tabellen)
## 0.15.1 – 2026-11-09

- **iPhone-Ansicht geprüft** (iPhone 15 hoch und quer, hell und dunkel): kein seitlicher Überlauf auf allen Seiten
- Diagramme auf dem Handy mit grösserer Achsenschrift; bei vielen Säulen bzw. Daten nur jede zweite Beschriftung,
  keine überlappenden Datumsangaben; Werte auf der Y-Achse werden nicht mehr abgeschnitten
- Eingabefelder auf dem Handy mit 16 px Schrift, damit iOS beim Antippen nicht hineinzoomt (auch Textfelder beim
  Berater); Checkboxen grösser zum Antippen
- Zeitachse auf der Seite Kinder als kompakte Tabelle statt einer Karte pro Jahr
- Keine automatische Schriftvergrösserung von iOS im Querformat
## 0.15.0 – 2026-11-09

- **Kinder** (neue Seite unter Planung): Kinder erfassen mit Geburtsdatum, gemeinsam oder aus einer früheren
  Beziehung, Obhut bzw. Elterntarif und AHV-Erziehungsgutschrift (Konkubinat), Ausbildung bis (18–25),
  Betreuungskosten und Zulagen. Zeitachse bis zur Selbständigkeit mit Zulagen, Betreuung und Steuerwirkung
  (Kinderabzug Bund 6'800, Elterntarif 263, Drittbetreuung bis 25'800, kantonaler Abzug einstellbar)
- Angepasst:
  - Steuern: Kinder mit Kinderabzug nur bis 18 bzw. Ende Ausbildung; im Konkubinat Elterntarif bei der Person mit
    der Obhut (erfasste Kinder gehen `steuern.personen[].kinder` vor); Heiratsvergleich entsprechend
  - AHV: Erziehungsgutschriften pro Kind und Person (Ehe hälftig, Konkubinat nach Vereinbarung, nur eigene Kinder);
    AHV-Kinderrenten zur Altersrente in der Pensionslücke
  - Risiko: IV-Kinder- und Waisenrenten nur für eigene, unterhaltsberechtigte Kinder; Todesfall-Richtwert
  - Nachlass: Pflichtteil nur für Nachkommen der verstorbenen Person
  - Krankenkasse: Kinder aus der Liste, Kinderfranchisen bis 18, ab 19 Erwachsenenfranchisen
  - Erinnerungen: Ausbildungszulage mit 16, Ausbildungsbestätigung mit 18, Krankenkasse mit 19, Ende Kinderabzug
  - Berater: Kinder mit Alter, Betreuung und Steuerwirkung
- Bestehende Einträge mit `geburtsjahr` funktionieren weiter
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
