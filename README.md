# Finanzplanung – Home-Assistant-App

Finanzplanung für einen Schweizer Haushalt (Ehepaar, Konkubinat oder Einzelperson) als App im Home Assistant:
Vorsorge, Steuern, Wohneigentum, Vermögen und Wertschriften, Budget, Versicherungen, Finanzplan bis ins hohe Alter,
Nachlass und Verfügungen sowie Anlageberater – mit Ampeln, die zeigen, wo etwas ansteht. Alle Daten bleiben im Home
Assistant; Dokumente (PDF, auch gescannt), Kontoauszüge (camt.053, CSV) und E-Steuerauszüge liest die App selbst. Bedienung und Rechenmodell siehe [finanz/DOCS.md](finanz/DOCS.md) (in Home Assistant unter «Dokumentation»),
Änderungen siehe [finanz/CHANGELOG.md](finanz/CHANGELOG.md).

> Keine Anlage-, Steuer- oder Rechtsberatung. Schätzungen mit vereinfachten Modellen.

## Funktionen

| Bereich | Inhalt |
|---|---|
| Übersicht | Ampeln pro Bereich, Kennzahlen, Hinweise, Statuszeile, Vermögensverlauf, Einkommen im Ruhestand |
| Vorsorge | AHV (Rentenskala 44, Splitting, Erziehungsgutschriften, Plafond, 13. Rente), Pensionskasse (Ausweis-Prognose oder BVG-Minimum, Einkäufe, Sperrfrist), Säule 3a, Pensionslücke in heutigen Franken mit Teuerung, Zuzug in die Schweiz (Beitragslücken, Einkaufsgrenze, Renten aus dem Ausland); Vorsorgeausweis, 3a-, 3b- und IK-Auszug hochladen |
| Steuern | Bundessteuer nach Tarif, Kanton als Kurve durch die letzte Veranlagung, Konkubinat getrennt, 3a und PK-Einkauf simulieren, Vermögenssteuer, Kapitalbezug gestaffelt; Steuererklärungen und Veranlagungen hochladen, Mehrjahresvergleich, Grenzsteuersatz, Abgleich; E-Steuerauszug der Bank (eCH-0196) |
| Wohnen | Tragbarkeit, maximaler Kaufpreis, Amortisation bis zur Fälligkeit (inkl. verpfändeter 3a/3b), Wegfall des Eigenmietwerts ab 2029; Wert der Liegenschaft, Erneuerungen und Erneuerungsfonds |
| Solar & vZEV | Werte der vZEV-App über Home Assistant: Ertrag, Rendite, Steuern (Abzug der Investition, Einspeisung netto), Komponenten in der Erneuerungsplanung, Einnahmen im Finanzplan |
| Fahrzeuge | Wert als steuerbares Vermögen, Kosten pro Jahr und Kilometer mit TCS-Vergleich, Leasing, Ersatz als Lebensziel, Erinnerungen für MFK und Leasingende |
| Kinder | Lebenslauf je Kind von der Kita über Schule und Lehre bzw. Gymnasium bis zum Studium – mit eigenen Kosten und Vergleichswerten je Phase (Zürcher Kinderkosten-Tabelle, Kita-Vollkosten, Studienbudget); Zulagen, Betreuung, Steuerwirkung über die Jahre; wirkt auf Steuern, AHV, Risiko, Nachlass, Krankenkasse, Finanzplan und Erinnerungen |
| Sparen & Anlegen | Reihenfolge für den nächsten Franken – Notreserve, teure Schulden, 3a, zweckgebunden, PK-Einkauf, langfristig – mit «jetzt vom Konto» und Sparplan pro Monat, Soll-Ist der Aufteilung und Produktarten (keine Produktempfehlungen) |
| Vermögen | Konten und Saldi (auch in Fremdwährung – alle Guthabenwährungen von Revolut und Wise) mit Kontoseite (umbenennen, zusammenführen, auflösen), Säule 3a je Konto (gebunden, mit Bezugsplan), Bank-Import im Format camt.053 oder als CSV, eigene Listen, Nettovermögen und Verlauf, Wertschriften pro Position (Anlageklasse, Region, Währung, Rendite, TER), Anlage-Check (Reserve, Amortisation, langfristiger Topf) |
| Budget | Buchungen aus dem Bank-Import kategorisieren, Ausgaben nach Kategorie und Monat, Sparquote, Abgleich mit dem Sparpotenzial, wiederkehrende Zahlungen und Abos mit Preisänderungen, Vergleich mit Schweizer Haushalten gleichen Typs und Einkommens |
| Lebensereignisse | Stellenverlust mit Taggeld und Reserve, Trennung bzw. Scheidung (Güterrecht, PK-Teilung, zwei Haushalte), faire Kostenaufteilung im Paar mit Vorsorgelücke |
| Finanzplan | Lebensziele mit Sparrate; Jahr für Jahr bis 95: Lohn bzw. Renten, Sparen und Entnahmen, Vermögen; 1000 simulierte Börsenverläufe, Wahrscheinlichkeit, dass das Geld reicht, mit 90 % Sicherheit tragbarer Bedarf |
| Versicherungen | Policen als PDF (auch gescannt, mit Texterkennung) oder Liste, Erkennung inkl. Invaliditätsleistungen und kantonaler Gebäudeversicherungen, Deckungscheck, Kündigungstermine, Krankenkasse (optimale Franchise und Modell, alle Kassen mit den BAG-Prämien), Risiko Invalidität und Tod |
| Szenarien | PK-Einkäufe optimal auf Jahre verteilen; Teilzeit und Kinderbetreuung (Netto, Steuern, Kita, AHV, PK); Frühpensionierung 58–65; Hypothekar-Strategie (SARON, Fest, Staffelung, Zinsszenarien, aktuelle Marktzinsen der SNB und eigene Offerten); Vergleich verheiratet ↔ Konkubinat inkl. Individualbesteuerung ab 2032 |
| Jahresbericht | Monatliche Stände, Vergleich mit dem Vorjahr, Massnahmen, Drucken |
| Steuererklärung | Checkliste pro Steuerjahr mit Belegen, Werten aus der App und Saldi per 31.12. |
| Notfallordner | Druckbare Übersicht für Angehörige mit Konten, Vorsorge, Policen, Kontakten, Ablageorten, ersten Schritten, Antworten der Fragebögen und Meldeliste für den Todesfall |
| Nachlass | Was der Partner im Todesfall erhält (Erbteil, Erbschaftssteuer, AHV/PK, Liegenschaft), Checkliste Testament, Begünstigungen, Vorsorgeauftrag, Detail-Fragebögen pro Punkt |
| Verfügungen | Entwürfe mit Fragen und Optionen: Testament (Pflichtteile, Verteilung), Vorsorgeauftrag, Patientenverfügung, Konkubinatsvertrag, 3a-Begünstigung, Ehevertrag, Erbvertrag, Darlehen, Schenkung bzw. Erbvorbezug – mit Vor- und Nachnamen |
| Erinnerungen | 3a, PK-Einkauf (inkl. optimaler Betrag), 3a-Lücken, Liegenschaftsunterhalt, Krankenkasse, Kündigungsfristen, Steuererklärung mit Frist des Wohnkantons, Hypothek, eigene; optional Benachrichtigung über Home Assistant |
| Berater | Sechs Beraterprofile mit Situation und Fakten aus der Planung; über die KI-Aufgabe von Home Assistant oder zum Kopieren |
| Sensoren | Kennzahlen, Ampel, Erinnerungen und Fristen als `sensor.finanz_*` für Dashboards und Automationen |
| Einstellungen | Formular mit Plausibilitäts-Ampel, YAML-Editor, Import-Ordner, Export, Dokumente neu sichten; Protokoll und Änderungen in der App |
| Dokumente | Alle hochgeladenen Dokumente und Buchungen: öffnen, Text-Ampel, Duplikate, löschen |
| Vorschläge | Anonymisierte Verbesserungsvorschläge aus den eigenen Daten (wahlweise mit Textauszügen), erledigte werden nach Updates selbst abgehakt; Leistungsmessung (Ladezeiten, Rechenzeiten, System) pro Version |

## Installation

Home Assistant → Einstellungen → Apps → App-Store → ⋮ → Repositories → `https://github.com/khu1985/finanz-ha`
hinzufügen, dann «Finanzplanung» installieren und starten. Die App erscheint als «Finanzen» in der Seitenleiste.

**Vorabversion testen:** Statt der Adresse oben `https://github.com/khu1985/finanz-ha#tests` hinzufügen. Damit
installiert Home Assistant den Stand des Branches `tests` (siehe [Entwicklung](#entwicklung)). Beide Fassungen lassen
sich nebeneinander installieren; jede hat ihren eigenen Konfigurationsordner.

## Persönliche Daten

Persönliche Daten (Löhne, Guthaben, Saldi, Policen, Ausweise, Steuerunterlagen) gehören **nicht** in dieses
Repository. Sie werden in der App erfasst oder in den Import-Ordner `/addon_configs/<…>_finanz/import/` kopiert
(Samba, File editor, Studio Code Server). Die App liest `finanz.yaml`, `vermoegen*.csv`, `versicherungen*.csv`, Kontoauszüge (`bank*`,
`konto*`, `camt*` als CSV, XML oder ZIP), E-Steuerauszüge (`steuerauszug*`) und PDFs beim Start oder per Knopf ein. Alles liegt danach im Konfigurationsordner der App und ist im Home-Assistant-Backup
enthalten. `.gitignore` schliesst die Datendateien aus; die Tests arbeiten nur mit erfundenen Daten.

## Architektur

Die App läuft als Container im Home Assistant und erscheint über Ingress als Seite in der Seitenleiste.
Ohne KI braucht sie kein Internet; mit KI geht der Auftrag über die KI-Aufgabe (`ai_task`) von Home Assistant.

[![Architektur](docs/architektur.svg)](docs/architektur.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart TB
    subgraph Quellen
        direction LR
        F["Formulare<br/>Einstellungen, Kinder, Fragebögen,<br/>Verfügungen, Notfallordner"]
        I["Import-Ordner<br/>finanz.yaml, CSV, camt, PDF"]
        U["Uploads<br/>Kontoauszüge, Policen, Vorsorge- und<br/>Steuerdokumente, E-Steuerauszug"]
    end
    subgraph App["Finanz-App (Container im Home Assistant, Ingress, AppArmor)"]
        direction TB
        S["server.py<br/>Webserver, Formulare, Uploads"]
        D["Dokumente<br/>bankimport, camt, budget, abos, versicherungen,<br/>dokumente, steuerdokumente, esteuerauszug,<br/>ocr, sichtung"]
        K["Rechenkern<br/>vorsorge, steuern, wohnen, immobilie,<br/>vermoegen, waehrung, kinder, kinderphasen, zuzug"]
        Z["Szenarien<br/>szenarien, finanzplan, teilzeit, fruehpension,<br/>hypothek, anlage, sparplan, wertschriften,<br/>krankenkasse, kkpraemien, marktzinsen, berater"]
        C["Checklisten und Bericht<br/>nachlass, fragebogen, verfuegungen,<br/>steuererklaerung, notfall, vorschlaege,<br/>bericht (Monatsstände)"]
        A["ampel.py, erinnerungen.py, sensoren.py<br/>Bewertung, Aufgaben, Sensoren;<br/>zwischenspeicher, leistung"]
        SE["seiten.py<br/>Seiten, Diagramme, Druckansicht"]
    end
    subgraph Daten["Konfigurationsordner (im Backup)"]
        direction LR
        Y[("finanz.yaml")]
        DB[("finanz.sqlite<br/>Saldi, Buchungen, Dokumente,<br/>Steuerauszüge, Monatsstände, Kurse")]
        P[("PDFs")]
        L[("finanz.log")]
    end
    HA["Home Assistant<br/>KI-Aufgabe, Benachrichtigung,<br/>sensor.finanz_*"]
    F & I & U --> S
    S --> D --> DB & P
    S --> Y
    Y & DB --> K --> Z
    K --> C
    K & Z & C --> A --> SE
    Z -. optional .-> HA
    EZB["EZB-Referenzkurse<br/>(optional)"] -. täglich .-> K
    BAG["BAG-Prämien<br/>(auf Knopfdruck)"] -. jährlich .-> Z
    SNB["SNB-Datenportal<br/>SARON, Hypothekarzinsen"] -. täglich .-> Z
    A -. stündlich und alle 15 Minuten .-> HA
    S --> L
```

</details>

| Datei | Aufgabe |
|---|---|
| `finanz/config.yaml` | App-Definition: Version, Ingress, AppArmor, Zugriff auf den Konfigurationsordner |
| `finanz/apparmor.txt` | AppArmor-Profil |
| `finanz/Dockerfile`, `build.yaml`, `run.sh` | Image (Python 3.12, Alpine) und Start |
| `finanz/app/server.py` | Webserver (Standardbibliothek), Ingress-Pfad, Formulare, Uploads, Protokoll |
| `finanz/app/seiten.py` | Alle Seiten, Navigation, Statusanzeige, mobile Darstellung |
| `finanz/app/ampel.py` | Ampeln für alle Bereiche und die Navigation |
| `finanz/app/vorsorge.py` | AHV, Pensionskasse, 3a, Pensionslücke |
| `finanz/app/steuern.py` | Bundessteuertarif, Kantonssteuer-Kurve, Steuereinheiten (Ehe/Konkubinat), Kapitalbezug |
| `finanz/app/wohnen.py` | Tragbarkeit, maximaler Kaufpreis, Eigenmietwert |
| `finanz/app/vermoegen.py` | Konten, Saldi, Kontoverwaltung (umbenennen, zusammenführen, auflösen), CSV-Import, Verlauf |
| `finanz/app/dreia.py` | Säule 3a als Konten: Abgleich mit den Einstellungen, Konto anlegen, gestaffelter Bezug je Konto |
| `finanz/app/versicherungen.py` | Policen, Erkennung, Deckungscheck, Kündigungstermine, Risiko, KI-Aufgabe |
| `finanz/app/dokumente.py` | Vorsorgeausweis, 3a-, 3b- und IK-Auszug |
| `finanz/app/steuerdokumente.py` | Steuererklärung, Veranlagung, Mehrjahresvergleich, Abgleich |
| `finanz/app/hypothek.py` | Hypothekar-Strategie über Zinsszenarien |
| `finanz/app/marktzinsen.py` | SARON und Richtzinsen der Banken (SNB-Datenportal), eigene Offerten |
| `finanz/app/bankimport.py` | Kontoauszüge aus dem E-Banking einlesen (CSV; camt.053 über `camt.py`) |
| `finanz/app/camt.py` | Kontoauszüge im Bankformat camt.053/052/054 (ISO 20022, XML oder ZIP) lesen |
| `finanz/app/esteuerauszug.py` | E-Steuerauszug der Bank (eCH-0196) lesen: Konten, Depots, Schulden, Erträge, Verrechnungssteuer |
| `finanz/app/krankenkasse.py` | Franchise- und Modell-Optimierung der Grundversicherung |
| `finanz/app/kkpraemien.py` | Prämien aller Krankenkassen (offene Daten des BAG) laden und pro Person vergleichen |
| `finanz/app/wertschriften.py` | Wertschriften pro Position: Anlageklasse, Region, Währung, Rendite, laufende Kosten |
| `finanz/app/habe.py` | Vergleich mit Schweizer Haushalten (Haushaltsbudgeterhebung des BFS, Daten eingebaut) |
| `finanz/app/abos.py` | Wiederkehrende Zahlungen und Abos aus den Buchungen erkennen |
| `finanz/app/lebensereignisse.py` | Stellenverlust (Arbeitslosenversicherung), Trennung bzw. Scheidung, Kosten im Paar aufteilen |
| `finanz/app/finanzplan.py` | Finanzplan Jahr für Jahr bis ins hohe Alter mit Monte-Carlo-Simulation |
| `finanz/app/fruehpension.py` | Frühpensionierung 58–65 |
| `finanz/app/anlage.py` | Anlage-Check |
| `finanz/app/sparplan.py` | Sparen und Anlegen: Reihenfolge, Sparplan pro Monat, Soll-Ist, Produktarten |
| `finanz/app/sensoren.py` | Sensoren für Home Assistant |
| `finanz/app/nachlass.py` | Nachlass, Erbschaftssteuer, Checkliste |
| `finanz/app/budget.py` | Buchungen, Kategorien, Budget-Auswertung |
| `finanz/app/verwaltung.py` | Übersicht, Duplikate und Löschen aller Dokumente |
| `finanz/app/ocr.py` | Texterkennung (tesseract) für gescannte PDFs |
| `finanz/app/fragebogen.py` | Detail-Fragebögen zur Nachlass-Checkliste für den Notfallordner |
| `finanz/app/verfuegungen.py` | Entwürfe für Testament, Vorsorgeauftrag, Patientenverfügung, Konkubinatsvertrag, 3a-Begünstigung, Ehevertrag, Erbvertrag, Darlehen, Schenkung bzw. Erbvorbezug |
| `finanz/app/zwischenspeicher.py` | Ergebnisse teurer Berechnungen wiederverwenden, bis sich Daten oder Konfiguration ändern |
| `finanz/app/leistung.py` | Leistung messen: Ladezeiten, Rechenzeiten, Hintergrundaufgaben, System und Datenmengen |
| `finanz/app/usability.py` | Usability-Prüfung aller Seiten: Score pro Seite, Kontrast in Hell und Dunkel, Vorschläge |
| `finanz/app/vorschlaege.py` | Verbesserungsvorschläge aus den eigenen Daten, anonymisiert zum Weitergeben; Textauszüge, Verlauf und «erledigt» |
| `finanz/app/pruefung.py` | Plausibilität der Einstellungen (Ampel pro Feld) |
| `finanz/app/sichtung.py` | Gespeicherte Dokumente nach Updates neu sichten |
| `finanz/app/bericht.py` | Monatsstände und Jahresbericht |
| `finanz/app/waehrung.py` | Fremdwährungen und Kurse |
| `finanz/app/immobilie.py` | Wert der Liegenschaft und Erneuerungsplanung |
| `finanz/app/teilzeit.py` | Teilzeit-Rechner |
| `finanz/app/steuererklaerung.py` | Checkliste Steuererklärung |
| `finanz/app/notfall.py` | Notfallordner, Meldeliste für den Todesfall |
| `finanz/app/solar.py` | Solaranlage und vZEV: Sensoren der vZEV-App, Rendite, Steuern, Komponenten, Finanzplan |
| `finanz/app/fahrzeuge.py` | Fahrzeuge: Wert, Kosten, Leasing, Ersatz, MFK |
| `finanz/app/kinder.py` | Kinder: Abzüge, Gutschriften, Zulagen, Zeitachse |
| `finanz/app/kinderphasen.py` | Lebenslauf der Kinder: Phasen von Kita bis Studium, eigene Kosten und Vergleichswerte, Kosten pro Jahr, Wirkung auf den Finanzplan |
| `finanz/app/zuzug.py` | Zuzug in die Schweiz: AHV-Jahre, PK-Einkaufsgrenze, Quellensteuer, Fristen |
| `finanz/app/tausender.py` | Tausendertrennzeichen |
| `finanz/app/kantone.py` | Fristen der Steuererklärung aller Kantone |
| `finanz/app/erinnerungen.py` | Erinnerungen, erledigt-Status, Benachrichtigung über Home Assistant |
| `finanz/app/szenarien.py` | PK-Einkauf-Optimierung, Vergleich verheiratet ↔ Konkubinat |
| `finanz/app/berater.py` | Beraterprofile, Fakten, Amortisations-Szenario, Beratungen |
| `finanz/app/importordner.py` | Import-Ordner für persönliche Dateien |
| `finanz/app/konfig.py`, `finanz/app/meta.py` | Konfiguration laden/speichern, Namen (Vorname/voller Name, Umbenennen), Version, Changelog, Protokoll |
| `finanz/app/diagramme.py` | Linien- und Säulendiagramme als SVG |
| `finanz/app/default_config.yaml` | Vorlage mit Musterhaushalt und Kennzahlen 2026 |

## Rechenmodell

### Vorsorge und Pensionslücke

[![Rechenmodell Vorsorge](docs/vorsorge.svg)](docs/vorsorge.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart TD
    P["Personen<br/>Geburtsdatum, Lohn, Pensum, Pensionierungsalter"] --> AHV
    P --> PK
    P --> A3
    ZU["Zuzug in die Schweiz<br/>Beitragsjahre ab Zuzug,<br/>Einkaufsgrenze 5 Jahre"] -.-> AHV & PK
    KI["Kinder<br/>Erziehungsgutschriften,<br/>Kinderrenten"] -.-> AHV
    VA["Vorsorgeausweis<br/>Prognose mit 65"] -. übernommen .-> PK
    IK["IK-Auszug<br/>Beitragsjahre"] -. übernommen .-> AHV
    AHV["AHV<br/>Skala 44 × Beitragsjahre ÷ 44<br/>Ehe: Splitting, Plafond 150 %<br/>× 13 Monatsrenten, Mischindex"] --> E
    PK["Pensionskasse<br/>Guthaben × (1 + Zins) + Sparbeitrag + Einkauf<br/>Rente = Guthaben ohne Kapital × Umwandlungssatz"] --> TE
    PK -- Kapitalanteil --> TE
    A3["Säule 3a<br/>Guthaben × (1 + Rendite) + Beitrag"] --> TE
    TE["Teuerung<br/>nominal → heutige Franken"] --> KAP
    TE --> E
    VM["Freies Vermögen<br/>ohne Immobilie und Hypothek"] --> KAP
    KAP["Kapital bei Pensionierung<br/>− Kapitalbezugssteuer (gestaffelt)"] --> AN["Kapitalverzehr<br/>Annuität mit realer Rendite"]
    AU["Renten aus dem Ausland<br/>ab Bezugsalter"] --> E
    AN --> E["Einkommen im Ruhestand<br/>AHV + PK-Renten + Kapitalverzehr + Ausland<br/>PK-Renten verlieren Kaufkraft"]
    B["Bedarf im Ruhestand"] --> L
    E --> L{"Pensionslücke<br/>bei Beginn, im Mittel, nach 20 Jahren"}
    L --> AMP["Ampel Ruhestand<br/>grün: keine Lücke · gelb: ≤ 10 % · rot: mehr"]
```

</details>

### Steuern und PK-Einkauf

[![Rechenmodell Steuern](docs/steuern.svg)](docs/steuern.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart TD
    SD["Steuerdokumente<br/>Erklärung, Veranlagung"] -. übernommen .-> REF
    REF["Letzte Veranlagung je Steuereinheit<br/>steuerbares Einkommen und Vermögen,<br/>Steuer, Grenzsteuersatz"] --> KT
    REF --> BU
    REF --> VS["Vermögenssteuer<br/>Veranlagung oder Promillesatz"]
    EH{"Zivilstand"} -- verheiratet --> E1["eine Steuereinheit<br/>Haushalt"]
    EH -- Konkubinat --> E2["je Person eine Steuereinheit<br/>Elterntarif bei der Person mit Obhut"]
    KI["Kinder<br/>Kinderabzug bis 18 bzw. Ausbildung,<br/>Drittbetreuung bis 14"] --> E1 & E2
    E1 & E2 --> REF
    BU["Bundessteuer<br/>Tarif, Elterntarif −263/Kind, max. 11,5 %"] --> T["Steuer heute"]
    KT["Kanton und Gemeinde<br/>S × (x ÷ E)^e – trifft Steuer und Grenzsatz"] --> T
    VS --> T
    T --> AB["Abzug simulieren<br/>Steuer(x) − Steuer(x − Abzug)"]
    AB --> OPT["PK-Einkauf optimieren<br/>Schritt für Schritt ins Jahr mit der<br/>höchsten Ersparnis pro Franken"]
    SP["Sperrfrist 3 Jahre vor Kapitalbezug,<br/>Einkaufsgrenze nach Zuzug"] --> OPT
    OPT --> PLAN["Plan pro Jahr<br/>Ersparnis, letzter Franken, Netto-Vorteil"]
    PLAN -. übernehmen .-> EK[("pk.einkauf_geplant")]
    AB --> TZ["Teilzeit-Rechner<br/>Nettolohn, Steuern, Kita"]
    T --> HV["Vergleich verheiratet ↔ Konkubinat<br/>mit und ohne Individualbesteuerung"]
    T --> CL["Checkliste Steuererklärung<br/>Belege, Saldi per 31.12., Vorjahr"]
```

</details>

### Amortisation und Hypothekar-Strategie

[![Amortisation und Hypothek](docs/hypothek.svg)](docs/hypothek.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart TD
    W["Liegenschaft<br/>Wert, Hypothek, Fälligkeit"] --> AM
    W --> ER["Bauteile und Lebensdauer<br/>Erneuerungen über 30 Jahre"]
    ER --> FO["Erneuerungsfonds pro Monat<br/>Kosten ÷ Lebensdauer, nie im Minus"]
    ER --> SA["Unterhaltsabzug<br/>bis zum Wegfall des Eigenmietwerts"]
    L["Liquide Mittel<br/>ohne «nicht antasten»"] --> AM
    S["Sparen bis Fälligkeit"] --> AM
    VP["Verpfändete 3a/3b<br/>− Steuer beim Bezug"] --> AM
    EK["PK-Einkäufe<br/>nach Steuerersparnis"] -- abziehen --> AM
    R["Notreserve"] -- abziehen --> AM
    AM["Amortisations-Szenario<br/>verfügbar bei Fälligkeit"] --> ZIEL{"Ziel erreicht?"}
    ZIEL --> REST["Hypothek ab Fälligkeit"]
    REST --> ST["Strategien<br/>SARON, Fest 5/10, Mix, Staffel"]
    SZ["SARON-Szenarien<br/>tief · basis · stress"] --> ST
    ZS["Sätze heute<br/>Marge, Festsätze, Laufzeitprämie"] --> ST
    ST --> K["Zinskosten über den Horizont<br/>höchste Jahreskosten, Zinsbindung"]
    K --> EMP["Empfehlung «maximale Sicherheit»<br/>tiefste Kosten im Stress"]
    K --> FW["Forward-Festhypothek<br/>Richtwert mit Aufschlag"]
```

</details>

Details zu Formeln und Annahmen: [finanz/DOCS.md → Rechenmodell](finanz/DOCS.md#rechenmodell).

## Dokumente verarbeiten

[![Dokumentverarbeitung](docs/dokumente.svg)](docs/dokumente.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart LR
    U["PDF, CSV oder XML<br/>Upload oder Import-Ordner"] --> T["Text auslesen<br/>pypdf, Kodierung;<br/>gescannt: OCR (tesseract)"]
    T --> E{"Art erkennen"}
    E -- Kontoauszug --> B["Bank, IBAN, Spalten<br/>bzw. camt.053-Felder,<br/>letzter Saldo je Monat,<br/>Buchungen mit Kategorie"]
    E -- E-Steuerauszug --> ES["eCH-0196: Konten, Depots,<br/>Schulden per 31.12.,<br/>Erträge, Verrechnungssteuer"]
    ES --> DB
    E -- Police --> V["Versicherer, Sparte, Prämie,<br/>Daten, Fristen, Summen"]
    E -- Vorsorge --> VO["Altersguthaben, Einkauf,<br/>Prognose 65, Risikoleistungen,<br/>3a, 3b-Rückkaufswert"]
    E -- Steuern --> S["Periode, steuerbares Einkommen<br/>und Vermögen, Steuern, Abzüge"]
    T -. optional .-> KI["KI-Aufgabe<br/>Home Assistant"] -. Werte .-> P
    B --> DB[("Saldi und Buchungen")]
    V & VO & S --> P["Prüfen<br/>erkannt ↔ heute"]
    P -- übernehmen --> K[("finanz.yaml")]
    DB & K --> A["Ampeln, Hinweise, Budget,<br/>Szenarien, Berater, Checklisten"]
```

</details>

Erkannte Werte werden nie stillschweigend übernommen: Die Dokumentseite zeigt erkannte und heutige Werte nebeneinander,
übernommen wird erst per Knopf.

## Prozess

### Laufend (automatisch)

[![Laufende Abläufe](docs/prozess-laufend.svg)](docs/prozess-laufend.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart LR
    ST["Start der App"] --> IO["Import-Ordner einlesen<br/>finanz.yaml, CSV, PDF"]
    IO --> ER["erledigt/<br/>verschoben"]
    H["stündlich"] --> EI["Erinnerungen prüfen"]
    EI -- neu oder fällig --> N["Benachrichtigung<br/>Notify-Dienst oder Meldung"]
    Q["alle 15 Minuten<br/>und nach Änderungen"] --> SE["Sensoren schreiben<br/>sensor.finanz_*"]
    Q --> MS["erster Lauf im Monat<br/>Stand für den Jahresbericht"]
    UP["Start nach einem App-Update"] --> NS["Dokumente neu sichten<br/>Erkennung mit gespeichertem Text"]
    Q --> KU["einmal pro Tag (optional)<br/>Wechselkurse der EZB"]
    Q --> MZ["einmal pro Tag (bei Wohneigentum)<br/>SARON und Hypothekarzinsen der SNB"]
    Q --> LE["Leistungsmessungen sichern<br/>pro Version"]
    SEITE["jeder Seitenaufruf"] --> AMP["Ampeln, Erinnerungen, Finanzplan<br/>aus dem Zwischenspeicher, neu nur nach Änderungen"]
    LOG["jede Aktion"] --> PR["Protokoll<br/>rotiert bei 1 MB"]
```

</details>

### Im Jahreslauf (von Hand, mit Erinnerungen)

[![Jahreslauf](docs/prozess-jahr.svg)](docs/prozess-jahr.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart TD
    M["monatlich<br/>Kontoauszüge importieren: Saldi und Buchungen"] --> UE["Übersicht, Budget und Ampeln aktuell"]
    J["Januar<br/>Kennzahlen prüfen (AHV, BVG, 3a, Tarif, Kinderabzug)"] --> F
    F["Februar–März<br/>Vorsorgeausweise und E-Steuerauszüge einlesen"] --> SE
    SE["bis Frist (Standard 31. März)<br/>Checkliste Steuererklärung, einreichen und hochladen"] --> VE
    VE["nach Veranlagung<br/>Veranlagung hochladen: Abgleich, Grenzsteuersatz"] --> SZ
    SZ["Szenarien<br/>PK-Einkauf optimieren, Plan übernehmen"] --> KV
    KV["September–November<br/>Krankenkasse vergleichen, bis 30.11. kündigen"] --> DZ
    DZ["Oktober–Dezember<br/>3a einzahlen (bis 20.12.), PK-Einkauf überweisen (bis 10.12.)"] --> J
    VT["laufend<br/>Kündigungsfristen 60 Tage vorher"] -.-> UE
    HY["36–12 Monate vor Fälligkeit<br/>Hypothekar-Strategie, Offerten, Forward"] -.-> UE
    KD["Kinder mit 16, 18, 19 und Ende Ausbildung<br/>Zulagen, Bestätigung, Krankenkasse;<br/>Kita, Kindergarten, Lehre, Studium"] -.-> UE
    NO["jährlich<br/>Notfallordner und Nachlass-Checkliste prüfen"] -.-> UE
    JB["Dezember–Januar<br/>Jahresbericht: Vergleich mit dem Vorjahr, Massnahmen"] -.-> J
    LG["rund 1 Jahr vor fälligen Erneuerungen<br/>Offerten, Förderbeiträge, Erneuerungsfonds"] -.-> UE
```

</details>


## Entwicklung

| Branch | Zweck | In Home Assistant |
|---|---|---|
| `main` | stabile Fassung | `https://github.com/khu1985/finanz-ha` |
| `tests` | Vorabversion zum Ausprobieren | `https://github.com/khu1985/finanz-ha#tests` |

Ablauf für Änderungen:

1. Änderung auf `tests` committen, Version in `finanz/config.yaml` erhöhen und `finanz/CHANGELOG.md` ergänzen.
2. GitHub Actions prüfen den Stand (siehe unten).
3. In Home Assistant die Vorabversion aktualisieren und ausprobieren.
4. Wenn alles passt, `tests` nach `main` übernehmen (Fast-forward oder Pull Request) – die stabile Fassung erhält das Update.

Home Assistant bietet ein Update nur an, wenn die Version in `finanz/config.yaml` höher ist.

Diagramme: Quellen als Mermaid in `docs/*.mmd`. `python3 tools/doku.py` rendert geänderte SVGs (Mermaid CLI `mmdc`)
und übernimmt die Quellen in die Mermaid-Blöcke dieses README.

Die Dokumentation wird mit jeder Version nachgeführt; ein Test (`test_dokumentation_aktuell`, auch einzeln mit
`python3 tools/doku.py --pruefen`) bricht ab, wenn ein Diagramm nicht aus der aktuellen Quelle gerendert ist, ein
Mermaid-Block im README abweicht, der Changelog keinen Eintrag zur Version hat oder ein Modul bzw. eine Seite in
README und DOCS.md fehlt.

## Tests

`tests/` prüft Rechenkern, Dokumenterkennung und Web-App mit erfundenen Daten, z. B. Eckwerte der Rentenskala,
Ehepaar-Plafond und Konkubinat, Bundessteuer an Tarifgrenzen, Kantonssteuer-Kurve, Staffelung, Tragbarkeit,
Erkennung von Policen, Vorsorgeausweisen und Steuerdokumenten aus erzeugten PDFs, camt.053 und E-Steuerauszug
(erfundene Beispiele in `tests/daten/`), BAG-Prämien in beiden Formaten, Wertschriften, Abos, Finanzplan,
Anonymisierung der Vorschläge, Kündigungsfristen nach VVG,
Ampel-Schwellen, PK-Einkauf-Optimierung, Heiratsvergleich, Hypothekar-Strategie, Bank-Import (Beispielauszüge in
`tests/bank/`), Erinnerungen und Benachrichtigungen, Import-Ordner sowie alle Seiten und Uploads hinter
einem Ingress-Pfad.

GitHub führt die Tests bei jedem Push auf `main` und `tests` und bei jedem Pull Request aus
(`.github/workflows/tests.yml`):

- **Wie im Home Assistant:** Python 3.12 mit den Paketversionen des App-Images
- **Neueste Paketversionen:** zeigt früh, wenn künftige Versionen etwas brechen
- **App-Image bauen und starten:** baut das Docker-Image, startet es und ruft Übersicht, Änderungen und Protokoll ab

Lokal:

```sh
pip install -r finanz/requirements.txt pytest reportlab
python3 -m pytest tests
FINANZ_DATA=/tmp/finanz PORT=8099 python3 finanz/app/server.py   # App unter http://localhost:8099
```

Das AppArmor-Profil lässt sich nur in Home Assistant prüfen; nach Änderungen daran zuerst über `tests` ausprobieren.
