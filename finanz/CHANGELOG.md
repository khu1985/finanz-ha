# Änderungen

## 0.48.0 – 2026-11-14

- **Vermögen pro Person:** neue Karte oben auf «Vermögen» mit gestapeltem Balken je Person und «gemeinsam» (Konten,
  Wertschriften, Säule 3a, Vorsorge 3b, Immobilie, Fahrzeug, Sonstiges; Schulden abgezogen). Das
  Pensionskassen-Guthaben steht hell daneben (gehört der Person, zählt nicht zum Nettovermögen). Bei zwei Personen
  zeigt die Karte die Aufteilung mit dem Gemeinsamen je zur Hälfte; Konten ohne Person werden genannt.

## 0.47.1 – 2026-11-14

- **Neue Ampeln** (Übersicht und Punkte im Menü): Sparen (nächster offener Schritt), Kinder (Ausbildungsende im
  Lebenslauf), Fahrzeuge (MFK, Leasingende, fehlende Versicherung), Solar & vZEV (überfällige Rechnungen, fehlende
  Werte)
- Dokumentation nachgeführt: Inhaltsverzeichnis, Erste Schritte, Erinnerungen, Ampeln, Konfiguration und Diagramme
  (Architektur, laufende Abläufe, Jahreslauf) mit Sparen & Anlegen, Säule 3a als Konten, Sparkonten, Fahrzeugen,
  Solar & vZEV und Usability

## 0.47.0 – 2026-11-14

- **Solar & vZEV** (neue Seite unter Familie & Wohnen): Die Finanz-App liest die Sensoren der vZEV-App aus Home
  Assistant (Wertschöpfung mit Verkauf an Mieter, Eigenverbrauch und Einspeisung, Produktion, offene Rechnungen) –
  einmal am Tag oder auf Knopfdruck; ohne vZEV-App Jahreswerte von Hand
  - Ertrag nach Unterhalt und Steuern, Investition minus Förderung und Steuerersparnis, Amortisation und Rendite
  - Steuern BL: Abzug der Investition als Energiesparmassnahme, Einspeisung netto; Punkte in der Checkliste der
    Steuererklärung
  - Module, Wechselrichter und Batterie in der Erneuerungsplanung unter Wohnen
  - Finanzplan: Ertrag ab der Pensionierung als Einnahme, Wegfall nach der Lebensdauer
  - Erinnerungen: Jahresabrechnung für die Steuererklärung, überfällige Rechnungen

## 0.46.0 – 2026-11-14

- **Fahrzeuge** (neue Seite unter Familie & Wohnen): pro Auto Wert, Kosten pro Jahr und pro Kilometer (Wertverlust bzw.
  Leasingrate, Versicherung, Verkehrssteuer – in BL nach Gewicht –, Vignette, Parkplatz, Energie, Unterhalt) mit
  Vergleich zum TCS-Musterauto und zur Kategorie Mobilität im Budget
  - Gekaufte Autos erscheinen unter Vermögen als Konto der Art «Fahrzeug» (steuerbares Vermögen, nicht frei verfügbar)
  - Ersatz als Lebensziel im Finanzplan und unter Sparen & Anlegen; Leasing unter «Teure Schulden» erwähnt
  - Erinnerungen: MFK, Leasingende, Vignette

## 0.45.1 – 2026-11-14

- **Einstellungen kürzer:** Sensoren, Import-Ordner, Dokumente neu sichten, YAML und Sichern sind auf dem neuen
  Reiter «Daten & Import»
- Lange Wörter (z. B. Dateinamen) brechen überall um statt über den Rand zu laufen
- Übersicht: sechs statt sieben Kennzahlen (die Versicherungsprämien stehen unter Versicherungen)
- **Usability-Prüfung genauer:** zugeklappte Teile zählen nicht (z. B. die Franchise-Tabellen der Krankenkasse und die
  Jahrestabelle im Finanzplan); Notfallordner und Jahresbericht dürfen als Druckseiten lang sein; Kennzahlen werden pro
  Reihe gezählt; «sehr grosses Formular» erst ab 50 Feldern (grössere Formulare haben die Speicher-Leiste)

## 0.45.0 – 2026-11-14

- **Filter über Tabellen:** Konten, Dokumente, Versicherungen, Vorsorgedokumente, Wertschriften und Finanzplan (Jahr
  für Jahr) haben eine aufklappbare Filterleiste – pro Spalte Textsuche oder Mehrfachauswahl (bei wenigen
  verschiedenen Werten wie Art, Person, Sparte, Phase), mit Anzahl passender Einträge und «Filter zurücksetzen»; der
  Filter bleibt beim Neuladen erhalten

## 0.44.2 – 2026-11-14

- **Sparkonten mit Bezugslimite:** pro Bankkonto Bezug ohne Kündigung (pro Jahr oder Monat), Kündigungsfrist und
  Rückzugskommission erfassen (Kontoseite); die Kontenliste zeigt die Limite. Der Anlage-Check weist darauf hin, wenn
  die Notreserve deswegen nicht sofort verfügbar ist; «Jetzt vom Konto» unter Sparen & Anlegen setzt nur ein, was ohne
  Kündigung beziehbar ist, und nennt die Frist für den Rest

## 0.44.1 – 2026-11-14

- **Mehr Währungen für Konten:** alle 58, die Revolut oder Wise als Guthaben führen (z. B. AED, AUD, CAD, CZK, DKK,
  HKD, JPY, NOK, PLN, SEK, SGD, THB, TRY, ZAR), in der Auswahl mit Namen. Tageskurse der EZB für 28 davon; BGN und
  XOF über den festen Kurs zum Euro; für die übrigen eigenen Kurs unter `waehrungen.kurse` eintragen
- Währungserkennung im Bank-Import nur noch für ganze Codes (z. B. «PEN» in «Pension» zählt nicht)

## 0.44.0 – 2026-11-14

- **Usability-Score unter Vorschläge:** Die App zeigt alle Seiten mit den eigenen Daten an und prüft sie einmal am
  Tag (oder auf Knopfdruck) – lange Seiten, Tabellen, die auf dem Handy seitlich scrollen oder sehr lang werden,
  grosse Formulare, Felder ohne Beschriftung, viele Kennzahlen, Diagramme ohne Beschreibung, überlange Wörter,
  Ladezeit und den Farbkontrast in Hell und Dunkel. Score gesamt und pro Seite mit Vergleich zur Vorversion; die
  Punkte erscheinen als Vorschläge (Bereich «Usability») und im Text zum Weitergeben
- **Behoben:** Im dunklen Modus war Text auf Knöpfen kaum lesbar (z. B. der aktive Filter «Alle» unter Dokumente);
  die Filterknöpfe unter Dokumente erbten seit 0.43.0 das Aussehen der Reiter
- Tabellen auf dem Handy: lange Werte (z. B. Dateinamen) brechen um statt abgeschnitten zu werden
- Formulare ab 8 Feldern blenden bei Änderungen unten «Ungespeicherte Änderungen – Speichern» ein und fragen beim
  Verlassen nach
- Diagramme und Eingabefelder der Krankenkasse haben eine Beschreibung für Screenreader
- Sparen & Anlegen: Schritt «Teure Schulden» erklärt, warum die Hypothek nicht dazu zählt und wo die
  Amortisation bzw. die Hypothekar-Strategie steht (statt «Keine Kredite erfasst»)

## 0.43.2 – 2026-11-14

- **Einstellungen:** «Speichern» in jedem Bereich (Haushalt, jede Person, Steuern, Wohnen, KI, Erinnerungen,
  Sensoren); nach dem Speichern bleibt die Seite beim Bereich. Sobald etwas geändert ist, erscheint unten eine Leiste
  «Ungespeicherte Änderungen – Speichern», und beim Verlassen ohne Speichern fragt der Browser nach
- Behoben: Stand der Hinweis «Vor- und Nachname» oben, waren die Felder nicht im Formular – Speichern hatte keine
  Wirkung. Namen wie «Person 1» gelten nicht mehr als Vor- und Nachname
- Meldungen nach dem Speichern erscheinen oben eingeblendet, wenn die Seite zu einem Bereich springt

## 0.43.1 – 2026-11-14

- Menü (Seitenleiste und Handy): Gruppen durch Linien getrennt, Gruppentitel kräftiger, Seiten eingerückt mit einer
  Führungslinie (bei der aktuellen Seite farbig) – Gruppe und Seite sind klar zu unterscheiden; «Steuern» steht als
  eigener Eintrag zwischen zwei Linien

## 0.43.0 – 2026-11-14

- **Menü neu gruppiert:** Überblick, Geld (Budget, Vermögen, Sparen & Anlegen), Steuern, Zukunft (Vorsorge,
  Finanzplan, Szenarien, Lebensereignisse), Familie & Wohnen (Kinder, Wohnen, Versicherungen), Absicherung
  (Nachlass, Verfügungen, Notfallordner), App (Dokumente, Einstellungen, Vorschläge)
- **Aufklappbare Gruppen** in der Seitenleiste und im Handy-Menü: offen sind der Überblick und die Gruppe der
  aktuellen Seite; zugeklappte Gruppen zeigen einen Ampel-Punkt, wenn eine Seite darin Handlungsbedarf hat
- **Steuern** und **Steuererklärung** sind eine Seite mit zwei Reitern; **Protokoll** und **Änderungen** sind Reiter
  bei den Einstellungen (Warnungen von heute als Zahl). Adressen bleiben gleich

## 0.42.0 – 2026-11-13

- Neue Seite **Sparen & Anlegen** (unter Bestand):
  - **Reihenfolge für den nächsten Franken:** Notreserve, teure Schulden, Säule 3a (mit Steuerersparnis),
    zweckgebunden (Amortisation, Lebensziele), PK-Einkauf (ab 25 % Grenzsteuersatz), langfristig – je mit Stand
    und Link zur passenden Seite
  - **Jetzt vom Konto:** Geld über Reserve und Zweck wird in derselben Reihenfolge eingesetzt
  - **Sparplan pro Monat:** das Sparpotenzial auf die Schritte verteilt, mit Hinweis, wenn es nicht reicht
  - **Aufteilung Soll-Ist** im langfristigen Topf und welche Anlageklasse beim nächsten Kauf dran ist; Schweiz-Anteil
    im Depot
  - **Produktarten** pro Topf und worauf zu achten ist; teure Fonds (über 0,5 % Kosten) aus den Wertschriften
- Anlage-Check: Hinweis zum Kursrisiko nennt das Fälligkeitsdatum der Hypothek statt fest 2030

## 0.41.2 – 2026-11-13

- Kassenvergleich: Ersparnis bei gleichem Modell und gleicher Franchise wird genannt; Hinweistexte ohne
  sichtbare HTML-Zeichen

## 0.41.1 – 2026-11-13

- **Kassenvergleich prüft die heutige Prämie:** Liegt sie über dem, was die Grundversicherung mit derselben Franchise
  laut BAG kostet, erscheint ein Hinweis (meist sind Zusatzversicherungen eingerechnet); die Ersparnis wird dann mit
  dem BAG-Wert der eigenen Kasse gerechnet statt mit der zu hohen Prämie
- Neue Spalte **«Höchstens»** (Prämie + volle Franchise + maximaler Selbstbehalt) und ein Hinweis, wenn ohne
  erwartete Gesundheitskosten eine höhere Franchise vorgeschlagen wird
- **Krankenkasse in den Einstellungen:** Eigene Angaben pro Person ergänzen die Police statt sie zu ersetzen –
  z. B. nur die erwarteten Gesundheitskosten eintragen

## 0.41.0 – 2026-11-13

- **Säule 3a unter Vermögen:** neue Art «Säule 3a» – jedes 3a-Konto bzw. -Depot mit Person und Verlauf
  - Guthaben, Anzahl und Anteile der 3a-Konten gehen automatisch in die Einstellungen der Person (Pensionslücke,
    Finanzplan, Kapitalbezugssteuer); ohne 3a-Konten gilt weiter der Wert in den Einstellungen
  - Karte «Säule 3a» mit geplantem Bezug je Konto; die Kapitalbezugssteuer rechnet gestaffelt im Verhältnis der
    Kontostände. «Als 3a-Konto anlegen» übernimmt ein Guthaben aus den Einstellungen
  - Bank-Import erkennt 3a-Konten (VIAC, frankly, finpension, «3a», «Vorsorgekonto»); 3a-Auszüge unter Vorsorge
    lassen sich als Saldo eines 3a-Kontos übernehmen; früher als «Vorsorge» importierte 3a-Konten werden umgestellt
- **Gebundene Vorsorge:** 3a und 3b zählen zum Nettovermögen, aber nicht mehr zum frei verfügbaren Vermögen
  (neue Kennzahl und Sensor «Gebundene Vorsorge»). Behoben: Ein importiertes 3a-Konto zählte bisher als freies
  Vermögen und bei der Pensionierung ein zweites Mal
- 3a erscheint nicht mehr im Vermögen der Steuererklärung und nicht im Nachlass
- **Steuerdokumente:** Bei gemeinsamer Erklärung ist die Person vorgewählt; fehlende Eingaben erscheinen nicht mehr
  als Warnung unter «Vorschläge»
- **Kinder:** Lebenslauf wird zwischengespeichert (Seite und Steuern schneller)

## 0.40.0 – 2026-11-13

- **Lebenslauf der Kinder** auf der Seite Kinder: Phasen von der Geburt bis zur Selbständigkeit – Kleinkind, Kita,
  Kindergarten, Primarschule, Sekundarstufe I, Berufslehre bzw. Gymnasium oder Fachmittelschule, Studium bzw.
  Fachhochschule. Beginn nach Stichtag 31. Juli, Einschulung verschiebbar, Dauer anpassbar
  - **Zeitachse je Kind** (alle Kinder untereinander) und **Kosten pro Jahr** über alle Kinder
  - **Kosten pro Phase:** Betreuung & Ausbildung sowie Lebenshaltung pro Monat; leere Felder rechnen mit
    **Vergleichswerten** aus der Zürcher Kinderkosten-Tabelle, den Kita-Vollkosten (INFRAS), Tarifen für
    Tagesstrukturen, Kosten am Gymnasium und dem Studienbudget der Universität Basel – mit Quellen
  - Eigene Betreuungsbeträge zählen für den Steuerabzug; ältere Angaben «Betreuung pro Jahr bis Alter» werden
    übernommen
  - **Finanzplan:** Mehr- und Minderkosten der Kinder gegenüber heute verändern das Sparpotenzial
  - **Hinweise und Erinnerungen** zu Phasenwechseln (Kita-Platz, Kindergarten, Lehrstellensuche, Gymnasium, Studium)
    mit den neuen Kosten

## 0.39.0 – 2026-11-13

Aus Sicht einer Lebensberatung: Lebensereignisse und Ziele.

- **Lebensereignisse** (neue Seite unter Planung):
  - **Stellenverlust** pro Person: Taggeld nach Arbeitslosenversicherung (70/80 %, höchstens CHF 148'200 versichert,
    Anzahl Taggelder nach Alter, Wartetage), Lücke zum Budget, wie lange die Reserve reicht, fehlende PK-Gutschriften
  - **Trennung bzw. Scheidung:** Güterrecht (Eigengut, hälftige Errungenschaft), PK-Teilung, zwei Haushalte mit den
    typischen Kosten allein, wer das Haus tragen könnte; im Konkubinat ohne Güterrecht und PK-Teilung
  - **Geld im Paar:** gemeinsame Kosten je hälftig, im Verhältnis zum Einkommen oder so, dass beiden gleich viel
    bleibt – mit der Vorsorgelücke der Person mit weniger Einkommen
- **Lebensziele** im Finanzplan: Ziele mit Betrag, Jahr und Wichtigkeit; Sparrate, Deckung aus dem Vermögen und
  Wirkung auf die Wahrscheinlichkeit, dass das Geld reicht
- **Neue Einstellungen:** Eigengut und PK-Guthaben bei Heirat pro Person, gemeinsame Ausgaben pro Monat

## 0.38.1 – 2026-11-13

- **Vergleich mit Schweizer Haushalten auch ohne Buchungen:** Die Vergleichswerte erscheinen sofort; eigene Werte
  kommen aus der Planung (Steuern, Krankenkassenprämien, Wohnkosten bei Wohneigentum, Sparquote aus dem
  Sparpotenzial), bis Kontoauszüge importiert sind

## 0.38.0 – 2026-11-13

- **Vergleich mit Schweizer Haushalten** im Budget: Ausgaben pro Kategorie und Sparquote neben dem Mittel von
  Haushalten gleichen Typs (z. B. Paare mit Kindern) und gleicher Einkommensklasse – aus der Haushaltsbudgeterhebung
  2020–2021 des Bundesamts für Statistik, fest in der App. Ampel und Hinweise, wo die eigenen Ausgaben deutlich
  darüber liegen

## 0.37.0 – 2026-11-13

Schneller, nach den ersten Messwerten aus Home Assistant (Übersicht bisher bis 23 s):

- **Zwischenspeicher:** Ampeln, Erinnerungen, Finanzplan, Steuererklärung, Pensionslücke, PK-Einkauf-Optimierung
  und Vertragsliste werden nicht mehr bei jeder Seite und jedem Hintergrundlauf neu gerechnet, sondern erst, wenn
  sich Daten oder Konfiguration ändern. Lokal lädt die Übersicht doppelt so schnell; auf dem Raspberry Pi bzw.
  Home Assistant Green ist der Gewinn grösser
- **Neu sichten nach Updates** liest PDFs nicht mehr erneut aus, wenn ihr Text schon gespeichert ist – nur die
  Erkennung läuft neu
- **Vorschläge «Leistung»:** Messwerte im Text nicht mehr als «‹Zahl›» unkenntlich (es sind nur Zeiten)
- **Dokumentation:** Diagramme Architektur und laufende Abläufe (Marktzinsen, Zwischenspeicher, Leistung), Übersichten
  zu Vorschlägen und Leistung

## 0.36.0 – 2026-11-13

- **Leistung messen** (Seite Vorschläge): Ladezeit jeder Seite und Aktion, Rechenzeit der grossen Berechnungen und
  der Hintergrundaufgaben, dazu System (Kerne, Last, Arbeitsspeicher) und Datenmengen – pro Version, mit dem
  Vergleich zur Vorversion. Langsame Stellen werden zu Vorschlägen im Bereich «Leistung», die Messwerte stehen im
  Text zum Weitergeben

## 0.35.0 – 2026-11-13

Aufgaben und Ampeln in der Übersicht kennen die neuen Funktionen:

- **Krankenkasse vergleichen:** Hinweis, die BAG-Prämien des Folgejahres zu laden, bzw. die Ersparnis laut
  Kassenvergleich
- **Hypothek vorbereiten:** mit den aktuellen Richtzinsen und ihrer Entwicklung; Hinweis, Offerten zu erfassen
- **Neue Aufgaben:** E-Steuerauszüge einlesen (Januar–März), Abo teurer geworden, grössere jährliche Zahlung steht
  an, Finanzplan ist knapp, Notfallordner und Verfügungen jährlich prüfen, Vor- und Nachname trennen
- **Neue Ampel «Finanzplan»:** wie oft das Geld in den simulierten Verläufen bis zum Endalter reicht

## 0.34.1 – 2026-11-13

- **Marktzinsen:** Marge der SARON-Hypothek auch aus dem Mittel mit 3 Jahren Rahmenlaufzeit (das 5-jährige
  veröffentlicht die SNB nicht immer); SARON-Verlauf über zwei Jahre statt nur die letzten Wochen; Hinweis, dass der
  SARON im SNB-Datenportal mit Verzögerung erscheint

## 0.34.0 – 2026-11-13

- **Hypothek mit Marktzinsen:** Die App holt einmal am Tag beim SNB-Datenportal den SARON und die publizierten
  Hypothekarzinsen der Banken (Festhypotheken 1–15 Jahre, variabel, SARON-Hypothek). Die Hypothekar-Strategie rechnet
  damit statt mit festen Standardwerten; Karte mit aktuellen Sätzen, Verlauf über 24 Monate und Hinweis vor der
  Fälligkeit, wenn sich die Festzinsen deutlich bewegen
- **Offerten erfassen:** konkrete Angebote einer Bank (Produkt, Zins, Datum) – eine Offerte der letzten 90 Tage geht
  dem Marktmittel vor, wenn sie günstiger ist; Links zu Vergleichsdiensten für die Suche

## 0.33.0 – 2026-11-13

Was spezialisierte Anbieter (VZ, Kubera, Copilot, Comparis) können und bisher fehlte:

- **Finanzplan** (neue Seite unter Planung): Jahr für Jahr bis 95 – Lohn bzw. Renten, Sparen und Entnahmen,
  Vermögen. 1000 simulierte Börsenverläufe zeigen die Bandbreite, wie wahrscheinlich das Geld reicht, wann es in
  schlechten Verläufen ausgeht und welcher Bedarf mit 90 % Sicherheit tragbar ist
- **Wertschriften pro Position** unter Vermögen: aus dem E-Steuerauszug (XML) oder einer eigenen Liste; Aufteilung
  nach Anlageklasse, Region und Währung, Rendite gegenüber dem Vorjahr, laufende Fondskosten (TER), Hinweise zu
  Klumpenrisiken. Der Anlage-Check rechnet mit der echten Aktienquote
- **Alle Krankenkassen im Vergleich:** offizielle Prämien des BAG laden (oder Datei hochladen) – pro Person die
  günstigsten Angebote über alle Modelle und Franchisen nach Gesamtkosten, das günstigste bei gleichem Modell und
  die günstigste Variante bei der eigenen Kasse. Neue Einstellung «Prämienregion»
- **Wiederkehrende Zahlungen und Abos** im Budget: Rhythmus, Betrag pro Jahr, nächste Belastung, Preisänderungen,
  verknüpfte Verträge
- **Dokumentation:** README-Einleitung und App-Beschreibung im App-Store mit den neuen Bereichen

## 0.32.1 – 2026-11-13

Dokumentation geprüft und nachgeführt:

- **Übersichten** (Inhalt, Menü, Seiten, Funktionen, Module) mit E-Steuerauszug, camt.053, Verfügungen, Fragebögen,
  Meldeliste, Kontoseite, Vorschlägen und Dokumenten
- **Erste Schritte** mit Vor- und Nachname, Kinder-Seite und camt.053; veraltetes YAML-Beispiel ersetzt
- **Konfiguration** um `verfuegungen`, `nachlass.fragebogen` und `ocr` ergänzt; Import-Ordner um `steuerauszug*`
- **Rechenmodell und Fehlersuche:** Texterkennung, camt.053 und E-Steuerauszug statt «gescannte PDFs werden nicht
  gelesen»
- **Diagramme** Architektur, Dokumentverarbeitung und Jahreslauf aktualisiert

## 0.32.0 – 2026-11-12

- **Vorname in der App, voller Name in Schreiben:** neues Feld «Nachname» pro Person und Kind. Verfügungen, Verträge,
  Briefe (z. B. 3a-Begünstigung) und der Notfallordner schreiben Vor- und Nachname aus; Kinder ohne eigenen Nachnamen
  erhalten den des Elternteils
- **Namen aufteilen:** Steht unter Einstellungen ein voller Name im Vornamenfeld, teilt die App ihn auf Knopfdruck auf
- **Umbenennen ohne Datenverlust:** Ändert sich der Name einer Person, werden Konten, Verträge, Vorsorge- und
  Steuerdokumente, Verfügungen, Checklisten und Kinder-Zuordnungen nachgeführt

## 0.31.0 – 2026-11-11

- **Kontoauszüge im Bankformat camt.053** (ISO 20022, XML oder ZIP mit mehreren Tagesauszügen; auch camt.052/054):
  Buchungsdatum, Betrag, Gegenpartei und Mitteilung pro Buchung, Sammelaufträge einzeln, vorgemerkte Buchungen nicht;
  Monatssaldi aus dem Schlusssaldo. Unter Vermögen und Budget sowie im Import-Ordner
- **E-Steuerauszug der Bank (eCH-0196):** neu unter «Steuern». Aus der XML-Datei (direkt oder als Anhang im PDF)
  kommen Konten, Depots und Schulden mit dem Saldo per 31.12. ins Vermögen; Steuerwert, Bruttoerträge A und B,
  Verrechnungssteueranspruch, Schuldzinsen und Spesen stehen in der Checkliste der Steuererklärung. Vom PDF allein
  liest die App die Totale
- **Verfügungen:** Entwürfe für Ehevertrag, Erbvertrag, Darlehen in der Familie sowie Schenkung bzw. Erbvorbezug
- **Notfallordner:** Meldeliste – welche Stellen nach einem Todesfall zu benachrichtigen sind (Gemeinde, AHV,
  Arbeitgeber, Pensionskasse, 3a/3b, Banken, Versicherungen), aus den erfassten Daten
- **Vorschläge haken sich selbst ab:** Die App merkt sich offene Vorschläge. Kommt einer nach einem Update nicht mehr
  vor, erscheint er unter «Erledigt» mit der Version («durch Update auf …» bzw. «durch deine Änderung»). Was eine
  Version erledigt hat, steht auch im Text zum Weitergeben

## 0.30.0 – 2026-11-11

Erkennung verbessert anhand anonymisierter Textauszüge:

- **Prämie:** der zu bezahlende Betrag zählt vor Zwischentotal, Überschussbeteiligung, Stempel und Abgaben
  (z. B. Rechnung der Basellandschaftlichen Gebäudeversicherung)
- **Kündigungsfrist** auch als Wort («drei Monate vor Ablauf») und bei «jährlichem Kündigungsrecht»
- **Beginn und Ablauf** aus «Versicherungslaufzeit … – …», «erstmals fällig am» und «Ende der Leistungspflicht»
- **smile** wird auch erkannt, wenn im Text nur die Helvetia als Versicherungsgesellschaft steht
- **Vorsorgeausweis Pensionskasse:** Tabellen mit Beschriftung in der Zeile darüber (Alter / Alterskapital /
  Altersrente; Ihr Beitrag / Altersgutschrift pro Monat), «Todesfallsumme», «Alterskapital mit … % verzinst»,
  bekannte Pensionskassen als Anbieter (z. B. Asga, Publica, BVK)
- **Textauszüge noch zurückhaltender:** Zeilen mit E-Mail, Geburtsdatum, Nationalität, versicherter Person,
  «Herrn» und Gesundheitsangaben (Vorbehalte, Erkrankungen, Verletzungen) werden weggelassen

## 0.29.0 – 2026-11-11

- **Kantonale Gebäudeversicherungen** (z. B. Basellandschaftliche Gebäudeversicherung, GVZ, GVB, AGV, GVBS, ECA)
  werden am Briefkopf erkannt: Sparte Gebäude, als obligatorisch und nicht kündbar vermerkt, keine Kündigungstermine
- **Vorschläge kompakter:** pro Dokument eine Zeile mit allen betroffenen Feldern statt einer Zeile pro Feld
- **Anonymisierte Textauszüge (wahlweise):** unter «Weitergeben» lassen sich die Zeilen rund um nicht oder falsch
  erkannte Felder anhängen – alle Ziffern durch 9 ersetzt, Namen, Anrede- und Adresszeilen entfernt, höchstens
  40 Zeilen pro Dokument. Standardmässig aus; der Text ist vor dem Weitergeben sichtbar

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
