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

## Seiten

| Seite | Inhalt |
|---|---|
| Übersicht | Kennzahlen, Hinweise (3a nicht ausgeschöpft, Sperrfrist, Tragbarkeit, Pensionslücke), Vermögensverlauf |
| Vorsorge | AHV pro Person, PK-Verlauf bis zur Pensionierung, 3a, Pensionslücke |
| Steuern | Steuern heute, Ersparnis von 3a und PK-Einkäufen, Kapitalbezug alles auf einmal vs. gestaffelt |
| Wohnen | Tragbarkeit nach Bankenpraxis, maximaler Kaufpreis, Wegfall des Eigenmietwerts ab 2029 |
| Vermögen | Konten, Saldi, CSV-Import, Verlauf am Monatsende |
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
CHF 263 pro Kind, Höchstsatz 11,5 %). Staats- und Gemeindesteuer als lineare Näherung um die letzte
Veranlagung: Steuer(x) = Steuer_ref + Grenzsteuersatz × (x − Einkommen_ref) – gut für Abzüge bis einige
zehntausend Franken. Kapitalleistungen: Bund ein Fünftel des Tarifs, Kanton mit effektivem Satz aus
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
| `finanz.sqlite` | Konten und Saldi |
| `finanz.log` | Protokoll |

Alles liegt im Konfigurationsordner der App und ist im Home-Assistant-Backup enthalten.
Die App braucht kein Internet.
