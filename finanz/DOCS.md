# Finanzplanung

Die App rechnet die Finanzplanung eines Schweizer Haushalts: Vorsorge (AHV, Pensionskasse, 3a),
Steuern, Wohneigentum und Vermögen. Sie erscheint als «Finanzen» in der Seitenleiste.

**Keine Anlage-, Steuer- oder Rechtsberatung.** Die Ergebnisse sind Schätzungen mit vereinfachten Modellen.
Für Entscheide (PK-Einkauf, Kapitalbezug, Hauskauf) die Werte mit Vorsorgeausweis, IK-Auszug,
kantonalem Steuerrechner oder einer Fachperson prüfen.

## Erste Schritte

1. **Einstellungen** öffnen und die Musterwerte ersetzen:
   - pro Person Geburtsdatum, Bruttolohn, AHV-Beitragsjahre (IK-Auszug), Werte aus dem Vorsorgeausweis, 3a
   - Steuern aus der letzten Veranlagung: steuerbares Einkommen Bund und Kanton, Staats- und Gemeindesteuer,
     Grenzsteuersatz (mit dem Steuerrechner des Kantons: Einkommen um 1'000 erhöhen, Mehrsteuer ÷ 10)
2. Kinder, geplante PK-Einkäufe oder eine dritte Person unter **Experte → YAML** erfassen, z. B.
   ```yaml
   haushalt:
     kinder:
       - {name: Lea, geburtsjahr: 2018}
   personen:
     - name: Person 1
       pk:
         einkauf_geplant:
           - {jahr: 2027, betrag: 20000}
           - {jahr: 2028, betrag: 20000}
   ```
3. Unter **Vermögen** Konten mit Saldo erfassen oder eine CSV importieren (`Datum;Konto;Saldo;Art;Person`).
   Hypotheken und Kredite zählen negativ. Immobilie und Hypothek zählen nicht zum freien Vermögen
   für die Pensionsplanung.

## Persönliche Daten importieren

Persönliche Daten gehören **nicht** ins GitHub-Repository. Kopiere sie (Samba, File editor oder Studio Code Server)
in den Import-Ordner der App: `/addon_configs/<…>_finanz/import/` (in der App `/config/import/`).
Die App liest ihn beim Start und mit «Einstellungen → Import-Ordner jetzt einlesen» ein und verschiebt
erledigte Dateien nach `import/erledigt/`.

| Datei | Wirkung |
|---|---|
| `finanz.yaml` | ersetzt die Konfiguration (vorherige Fassung als `finanz.yaml.bak`) |
| `vermoegen*.csv` | Konten und Saldi (`Datum;Konto;Saldo;Art;Person`) |
| `versicherungen*.csv` | Versicherungsliste (`Versicherung;Anbieter;Betrag;Person;Summe;Notiz`) |
| `versicherung*.pdf`, `police*.pdf` | Versicherungsvertrag analysieren |
| übrige `*.pdf` | Vorsorgedokument (Vorsorgeausweis, 3a-, IK-Auszug) analysieren |

## Nicht verheiratet (Konkubinat)

`haushalt.zivilstand: ledig` und unter `steuern.personen` je eine Steuererklärung erfassen. Dann rechnet die App
getrennte Steuern (Elterntarif für die Person mit `kinder: 1`), Kapitalbezüge pro Person und die AHV ohne Plafonierung.
Die Risiko-Analyse weist darauf hin, dass es ohne Heirat keine AHV-Hinterlassenenrente für den Partner gibt und
eine PK-Lebenspartnerrente nur nach Meldung bei der Kasse.

## Versicherungen

Policen als PDF hochladen (mehrere gleichzeitig) oder als CSV-Liste importieren. Die Erkennung arbeitet lokal mit
Mustern; jedes Feld lässt sich auf der Vertragsseite korrigieren. Die Seite zeigt:

- **Deckungscheck:** Grundversicherung pro Person und Kind, Privathaftpflicht, Hausrat, Gebäude (kantonal + privat ist
  üblich), Todesfallsumme gegenüber Hypothek und Kindern, Doppelversicherungen, Unfall in der Grundversicherung bei
  Angestellten, Franchise, Sparversicherungen
- **Kündigungstermine:** Grundversicherung bis 30. November, sonst auf Ablauf bzw. nach 3 Jahren (Art. 35a VVG)
- **Risiko Invalidität und Tod:** IV-Rente (≈ AHV-Rente ohne 13. Rente, Kinderrenten 40 %), PK und externe Policen;
  Renten für Hinterbliebene und Todesfallkapital

## Vorsorgedokumente

Unter «Vorsorge» Vorsorgeausweise, 3a- und IK-Auszüge hochladen. Erkannt werden u. a. Altersguthaben,
Einkaufspotenzial, Prognose mit 65 (Kapital und Rente), Sparbeitrag, Umwandlungssatz, Invaliden-, Partner- und
Waisenrenten, Todesfallkapital, 3a-Saldo und AHV-Beitragsjahre. Werte prüfen, Person wählen und übernehmen.
Ist ein Alterskapital laut Ausweis erfasst, rechnet die App mit der Prognose der Kasse (plus geplante Einkäufe).

## Anlageberater

Sechs Profile (Sicherheit, Steuern, Hypothek, Vorsorge, Wachstum, Advocatus Diaboli; eigene unter `berater.profile`).
Die App kombiniert das Profil mit eurer Situationsbeschreibung, den Fakten aus der Planung und dem
Amortisations-Szenario bis zur Fälligkeit der Hypothek (liquide Mittel ohne «nicht antasten», Sparen, verpfändete
3a/3b, Steuer beim Bezug, PK-Einkäufe, Reserve). Ist `ki.aktiv` eingeschaltet, geht der Auftrag an die KI-Aufgabe
(`ai_task.generate_data`) von Home Assistant; sonst lässt er sich kopieren und die Antwort wieder einfügen.
Die Berater sind KI-Profile, keine zugelassenen Anlageberater.

## KI (optional)

In Home Assistant eine KI-Integration mit KI-Aufgabe einrichten (z. B. OpenAI, Anthropic, Google), dann unter
Einstellungen «KI-Aufgabe nutzen» auf ja und optional die Entität setzen. Genutzt für Berater sowie zum Auslesen von
Verträgen und Vorsorgedokumenten. Dabei verlassen Dokumenttext bzw. Planungsdaten Home Assistant in Richtung des
gewählten KI-Anbieters.

## Seiten

| Seite | Inhalt |
|---|---|
| Übersicht | Kennzahlen, Hinweise (3a nicht ausgeschöpft, Sperrfrist, Tragbarkeit, Pensionslücke), Vermögensverlauf |
| Vorsorge | AHV pro Person, PK-Verlauf bis zur Pensionierung, 3a, Pensionslücke |
| Steuern | Steuern heute, Ersparnis von 3a und PK-Einkäufen, Kapitalbezug alles auf einmal vs. gestaffelt |
| Wohnen | Tragbarkeit nach Bankenpraxis, maximaler Kaufpreis, Wegfall des Eigenmietwerts ab 2029 |
| Vermögen | Konten, Saldi, CSV-Import, Verlauf am Monatsende |
| Versicherungen | Verträge, Deckungscheck, Kündigungstermine, Risiko Invalidität/Tod, Prämien |
| Berater | Situation, Beraterprofile, Amortisations-Szenario, bisherige Beratungen |
| Einstellungen | Formular, YAML-Editor, finanz.yaml herunterladen und importieren |

## Rechenmodell

Alle Beträge in heutigen Franken (keine Teuerung).

**AHV.** Monatliche Vollrente nach Rentenskala 44 als stetige Formel (bis 15'120: Minimalrente,
bis 45'360: 74 % der Minimalrente + 13/600 des Einkommens, darüber 104 % + 8/600, höchstens
Maximalrente). Teilrente = Vollrente × Beitragsjahre ÷ 44. Beitragsjahre = bisherige + künftige bis 65
(bei Frühpensionierung wird angenommen, dass als Nichterwerbstätige weiter Beiträge bezahlt werden).
Verheiratete: Einkommen beider gemittelt (Splitting), Erziehungsgutschriften (3 × jährliche Minimalrente
pro Jahr mit Kind unter 16) hälftig. Vorbezug −6,8 % pro Jahr, Aufschub nach Tabelle.
Ehepaare: Summe höchstens 150 % der Maximalrente. Pro Jahr 13 Monatsrenten (13. AHV-Rente ab Dez. 2026).

**Pensionskasse.** Jährlich: Guthaben × (1 + Zins) + Sparbeitrag + Einkauf. Sparbeitrag laut Ausweis,
sonst BVG-Minimum (koordinierter Lohn × Altersgutschrift 7/10/15/18 %). Rente = Guthaben ohne
Kapitalanteil × Umwandlungssatz. Warnung, wenn Einkäufe in den 3 Jahren vor einem Kapitalbezug liegen.

**Säule 3a.** Guthaben × (1 + Rendite) + Beitrag bis zur Pensionierung.

**Pensionslücke.** Einkommen ab dem Jahr, in dem beide pensioniert sind = AHV + PK-Renten +
Kapitalverzehr. Der Kapitalverzehr ist die Annuität aus 3a, PK-Kapital und freiem Vermögen nach
Kapitalbezugssteuer über die eingestellten Jahre und Rendite. Der Bedarf versteht sich inkl. Steuern.

**Steuern.** Direkte Bundessteuer exakt nach Tarif (Verheirateten- oder Grundtarif, Elterntarif
CHF 263 pro Kind, Höchstsatz 11,5 %). Staats- und Gemeindesteuer als Potenzkurve durch die letzte
Veranlagung: Steuer(x) = Steuer_ref × (x ÷ Einkommen_ref)^e, wobei e so gewählt ist, dass beim Referenzeinkommen genau
der Grenzsteuersatz gilt – darunter sinkt die Steuer progressiv, sodass auch grosse PK-Einkäufe realistisch bewertet werden. Kapitalleistungen: Bund ein Fünftel des Tarifs, Kanton mit effektivem Satz aus
der Tabelle `steuern.kapitalbezug_kanton` (Schätzwerte – mit dem kantonalen Rechner ersetzen).
Gestaffelt: ein 3a-Konto pro Jahr, das letzte im Pensionsjahr, frühestens ab 60.

**Wohnen.** Tragbarkeit = (Hypothek × 5 % + Unterhalt/Nebenkosten + Amortisation der 2. Hypothek
über 66,7 % in höchstens 15 Jahren bzw. bis zur Pensionierung) ÷ Bruttoeinkommen, höchstens 33 %.
Belehnung höchstens 80 %, mindestens 10 % Eigenmittel ohne PK. Wegfall Eigenmietwert: heute versteuerter
Saldo (Eigenmietwert − Schuldzinsen − 20 % Unterhaltspauschale) × Grenzsteuersatz.

## Kennzahlen

Die Kennzahlen (AHV, BVG, 3a, Bundessteuertarif, Tragbarkeit) stehen im Abschnitt `kennzahlen` der
Konfiguration, Stand 2026. Sie werden in der Regel alle zwei Jahre (AHV/BVG) bzw. jährlich (3a,
Steuertarif) angepasst und lassen sich im YAML-Editor überschreiben.

## Daten und Sicherung

| Datei | Inhalt |
|---|---|
| `finanz.yaml` | Haushalt, Personen, Steuern, Wohnen, Annahmen, Kennzahlen; frühere Fassung als `finanz.yaml.bak` |
| `finanz.sqlite` | Konten, Saldi, Verträge, Vorsorgedokumente, Beratungen |
| `versicherungen/`, `vorsorge/` | hochgeladene PDFs |
| `import/` | Import-Ordner, erledigte Dateien unter `import/erledigt/` |
| `finanz.log` | Protokoll |

Alles liegt im Konfigurationsordner der App und ist im Home-Assistant-Backup enthalten.
Ohne KI braucht die App kein Internet.

## Steuerdokumente

Unter «Steuern» Steuererklärungen, Veranlagungsverfügungen und Steuerrechnungen hochladen (auch mehrere Jahre).
Die App erkennt Steuerperiode, Person, steuerbares Einkommen Kanton und Bund, steuerbares Vermögen, Staats-,
Gemeinde- und Bundessteuer, Lohn, Eigenmietwert, Mietertrag sowie Abzüge (3a, PK-Einkauf, Schuldzinsen,
Liegenschaftsunterhalt, Berufskosten, Kinder). Daraus entstehen:

- **Vergleich pro Person** über die Jahre (Veranlagung vor Erklärung) mit Veränderung zum Vorjahr
- **Geschätzter Grenzsteuersatz** Kanton + Gemeinde aus zwei Veranlagungen (Δ Steuer ÷ Δ Einkommen)
- **Abgleich** Erklärung ↔ Veranlagung: Korrekturen der Steuerverwaltung (Einsprachefrist beachten)
- **Hinweise:** 3a nicht ausgeschöpft, PK-Einkauf ungenutzt (mit Ersparnis), Unterhalt Pauschale vs. effektiv,
  Wegfall Eigenmietwert ab 2029, Mietertrag, Kinderabzug im Konkubinat
- **Übernahme** in die Steuer-Einstellungen der Person (bei Konkubinat in `steuern.personen`), Eigenmietwert und 3a

Im Import-Ordner werden `steuer*.pdf` und `veranlagung*.pdf` als Steuerdokumente erkannt.

## Szenarien

**PK-Einkauf optimieren.** Person, Budget (0 = ganzes Potenzial), Zeitraum, Mindest-Ersparnis pro Franken und
Schrittweite wählen. Die App legt Schritt für Schritt jeweils dort ein, wo der nächste Franken am meisten Steuern spart,
bei gleichem Einkommen in jedem Jahr. So entsteht eine gleichmässige Verteilung über die Jahre. Einkäufe in den
3 Jahren vor einem geplanten Kapitalbezug sind gesperrt. Der Netto-Vorteil enthält den Zins bis 65 und zieht die
zusätzliche Kapitalbezugssteuer ab. Mit «Plan übernehmen» werden die Einkäufe unter `pk.einkauf_geplant` eingetragen.

**Verheiratet oder Konkubinat.** Braucht je Person eine Steuererklärung unter `steuern.personen`. Verglichen werden:
Einkommenssteuern heute (Bund: Summe beider Einkommen, Verheiratetenabzug, Zweiverdienerabzug 50 % des tieferen
Erwerbseinkommens, mindestens 8'600, höchstens 14'100, Elterntarif; Kanton: Summe mit Splitting-Divisor auf dem
Mittel der beiden Steuerkurven, einstellbar über `steuern.ehe_splitting_divisor`), AHV-Renten (Plafonierung auf 150 %),
Steuer auf Kapitalbezügen (zusammengerechnet) und Renten für Hinterbliebene (AHV-Witwen-/Witwerrente,
PK-Ehegattenrente). Dazu eine Gesamtbilanz ohne Teuerung und Zins sowie die rechtlichen Unterschiede.

## Ampeln

Grün = in Ordnung, gelb = prüfen, rot = handeln, grau = keine Daten. Die Übersicht zeigt alle Bereiche als
Kacheln (dringendste zuerst); ein Punkt in der Navigation markiert Seiten mit gelber oder roter Ampel.

| Bereich | Grün | Gelb | Rot |
|---|---|---|---|
| Ruhestand | keine Lücke | Lücke bis 10 % des Bedarfs | grössere Lücke |
| Liquidität | Konten ≥ Reserve | ≥ halbe Reserve | darunter |
| Tragbarkeit | ≤ 33 % | bis 38 % | darüber |
| Amortisation | Ziel erreicht | ≥ 80 % des Ziels | darunter |
| Steuern | 3a ausgeschöpft | 3a offen oder PK-Einkauf bei Grenzsatz ≥ 30 % prüfen | – |
| Steuerdokumente | aktuell, ohne Korrekturen | Korrektur der Veranlagung oder älter als 2 Jahre | – |
| Versicherungsschutz | vollständig | etwas zu prüfen | obligatorische/empfohlene Deckung fehlt |
| Kündigungsfristen | > 45 Tage | ≤ 45 Tage | ≤ 14 Tage |
| Invalidität | ≥ 70 % des Lohns | ≥ 55 % | darunter |
| Todesfall | Kapital ≥ Richtwert | ≥ 50 % oder Partnerrente nicht gemeldet | darunter |
| Daten | Saldi ≤ 45 Tage, keine TODO | bis 120 Tage oder TODO offen | älter |

## Version, Änderungen und Protokoll

Die Version steht oben neben «Finanzen»; ein Tipp darauf öffnet die Änderungen. Das Symbol mit den Linien öffnet
das Protokoll (Filter nach Stufe, Download), das Zahnrad die Einstellungen. Die Statuszeile auf der Übersicht zeigt,
wie aktuell die Daten sind und ob etwas Aufmerksamkeit braucht.

## Sicherheit

Die App läuft nur über Ingress (kein offener Port) und mit eigenem AppArmor-Profil (`apparmor.txt`) –
zusammen Sicherheitsbewertung 8. `homeassistant_api` wird nur für die optionale KI-Aufgabe genutzt.
