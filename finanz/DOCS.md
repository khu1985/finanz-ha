# Finanzplanung

Finanzplanung eines Schweizer Haushalts – Ehepaar, Konkubinat oder Einzelperson – direkt im Home Assistant:
Vorsorge, Steuern, Wohneigentum, Vermögen, Versicherungen, Szenarien und Anlageberater. Die App erscheint als
«Finanzen» in der Seitenleiste; Ampeln zeigen auf einen Blick, wo etwas ansteht.

**Keine Anlage-, Steuer- oder Rechtsberatung.** Die Ergebnisse sind Schätzungen mit vereinfachten Modellen.
Für Entscheide (PK-Einkauf, Kapitalbezug, Heirat, Hauskauf) die Werte mit Vorsorgeausweis, IK-Auszug,
kantonalem Steuerrechner oder einer Fachperson prüfen.

## Inhalt

1. [Erste Schritte](#erste-schritte)
2. [Bedienung](#bedienung)
3. [Seiten](#seiten)
4. [Vorsorge](#vorsorge) · [Steuern](#steuern) · [Wohnen](#wohnen) · [Vermögen](#vermögen) ·
   [Versicherungen](#versicherungen) · [Szenarien](#szenarien) · [Anlageberater](#anlageberater) ·
   [Nachlass](#nachlass-und-absicherung) · [Erinnerungen](#erinnerungen) · [Sensoren](#sensoren-in-home-assistant)
5. [Nicht verheiratet (Konkubinat)](#nicht-verheiratet-konkubinat)
6. [Ampeln](#ampeln)
7. [Persönliche Daten und Import-Ordner](#persönliche-daten-und-import-ordner)
8. [Konfiguration](#konfiguration)
9. [Rechenmodell](#rechenmodell)
10. [KI (optional)](#ki-optional)
11. [Daten, Sicherung und Sicherheit](#daten-sicherung-und-sicherheit)
12. [Fehlersuche](#fehlersuche)

## Erste Schritte

1. **Daten erfassen** – eine der beiden Varianten:
   - **Einstellungen** öffnen und die Musterwerte im Formular ersetzen: pro Person Geburtsdatum, Bruttolohn,
     Sparpotenzial, AHV-Beitragsjahre, Werte aus dem Vorsorgeausweis, 3a; Steuern aus der letzten Veranlagung;
     Wohneigentum.
   - Eine vorbereitete `finanz.yaml` unter **Einstellungen → Experte** einfügen oder in den
     [Import-Ordner](#persönliche-daten-und-import-ordner) kopieren.
2. **Dokumente hochladen** – die App liest die Werte aus und übernimmt sie auf Knopfdruck:
   - Vorsorgeausweise, 3a- und IK-Auszüge unter **Vorsorge**
   - Steuererklärungen und Veranlagungen unter **Steuern**
   - Versicherungspolicen unter **Versicherungen** (oder eine Liste als CSV)
3. **Vermögen** erfassen: Kontoauszüge aus dem E-Banking als CSV importieren, Saldi von Hand oder als eigene Liste
   (`Datum;Konto;Saldo;Art;Person`).
4. Die **Übersicht** und ihre Ampeln zeigen, wo etwas zu tun ist. Werte mit «TODO» in der Konfiguration sind
   Platzhalter; ihre Zahl steht in der Statuszeile.

Kinder, geplante PK-Einkäufe, verpfändete Vorsorge oder eine weitere Person werden im YAML-Editor erfasst, z. B.:

```yaml
haushalt:
  kinder:
    - {name: Lea, geburtsjahr: 2018}
personen:
  - name: Person 1
    pk:
      einkauf_geplant:
        - {jahr: 2027, betrag: 20000}
```

## Bedienung

- **Menü** in Gruppen – Überblick (Übersicht, Berater), Planung (Vorsorge, Steuern, Wohnen, Szenarien), Bestand
  (Vermögen, Versicherungen), App (Einstellungen, Protokoll, Änderungen). Auf grossen Bildschirmen als Seitenleiste,
  auf Tablets als wischbare Leiste, auf dem Handy hinter dem Knopf «Menü». Ein farbiger Punkt markiert Seiten mit
  gelber oder roter Ampel; beim Protokoll steht die Zahl der Warnungen von heute.
- **Version** neben «Finanzen» öffnet die Änderungen.
- **Darstellung:** Der Knopf daneben wechselt zwischen Auto (wie das Gerät), Hell und Dunkel; die Wahl bleibt im
  Browser gespeichert.
- **Statusanzeige:** Ladebalken beim Seitenwechsel; bei Uploads, Importen, KI und Beratern ein Hinweisfenster mit
  Spinner, Anzahl und Grösse der Dateien. Knöpfe sind während der Verarbeitung gesperrt.
- **Statuszeile** auf der Übersicht: Stand der Saldi, Anzahl Verträge und Dokumente, offene TODO, wartende Dateien im
  Import-Ordner, KI an/aus, Warnungen von heute.
- **Protokoll:** neueste Einträge zuerst, Filter nach Stufe, Download. Die Stufe für neue Einträge steht in der
  App-Konfiguration (`log_level`).
- **Handy:** Kennzahlen zweispaltig, breite Tabellen als Karten, grosse Bedienelemente.

## Seiten

| Seite | Inhalt |
|---|---|
| Übersicht | Ampeln, anstehende Erinnerungen, Kennzahlen, Hinweise, Statuszeile, Vermögensverlauf, Einkommen im Ruhestand |
| Vorsorge | Pensionslücke, AHV, Pensionskasse, 3a, Vorsorgedokumente |
| Steuern | Steuern heute (pro Steuererklärung), Abzüge simulieren, Steuerdokumente mit Vergleich und Abgleich, Kapitalbezug |
| Wohnen | Tragbarkeit, maximaler Kaufpreis, Wegfall Eigenmietwert, Amortisation bis zur Fälligkeit |
| Vermögen | Konten, Saldi, Anlage-Check, Bank-Import, CSV-Import, Verlauf, Aufteilung nach Art |
| Versicherungen | Verträge, Deckungscheck, Kündigungstermine, Krankenkasse (Franchise, Modell), Risiko Invalidität und Tod, Prämien |
| Szenarien | PK-Einkauf optimieren, Frühpensionierung, Hypothekar-Strategie, Vergleich verheiratet ↔ Konkubinat (mit Individualbesteuerung) |
| Nachlass | Was der Partner im Todesfall erhält, Erbschaftssteuer, Checkliste Testament, Begünstigungen, Vorsorgeauftrag |
| Berater | Situation, Beraterprofile, Amortisations-Szenario, Beratungen |
| Einstellungen | Formular, Import-Ordner, YAML-Editor, Export und Import von `finanz.yaml` |
| Protokoll, Änderungen | Protokoll der App, Changelog |

## Vorsorge

![Rechenmodell Vorsorge](https://raw.githubusercontent.com/khu1985/finanz-ha/main/docs/vorsorge.svg)

- **AHV** pro Person mit Beitragsjahren, Erziehungsjahren, Durchschnittseinkommen, Rente pro Monat und Jahr
  (13. AHV-Rente), bei Ehepaaren plafoniert.
- **Pensionskasse:** Verlauf des Altersguthabens bis zur Pensionierung, Einkäufe, Kapitalbezug, Rente. Ist ein
  Alterskapital laut Vorsorgeausweis erfasst, rechnet die App mit dieser Prognose (plus geplante Einkäufe).
- **Säule 3a:** Kapital bei Pensionierung und Steuerersparnis der Beiträge.
- **Pensionslücke:** AHV + PK-Renten + Kapitalverzehr gegenüber dem Bedarf im Ruhestand.
- **Vorsorgedokumente:** Vorsorgeausweis, 3a- und IK-Auszug als PDF hochladen. Erkannt werden u. a.
  Altersguthaben, Einkaufspotenzial, Prognose mit 65, Sparbeitrag, Umwandlungssatz, Invaliden-, Partner- und
  Waisenrenten, Todesfallkapital, Jahreslohn, 3a-Saldo und AHV-Beitragsjahre. Auf der Dokumentseite stehen
  erkannte und heutige Werte nebeneinander; Person wählen, Werte prüfen, übernehmen. Dazu eine Einschätzung
  (Ersparnis eines Einkaufs, Umwandlungssatz, Beitragslücken, Partnerrente im Konkubinat).

## Steuern

![Rechenmodell Steuern](https://raw.githubusercontent.com/khu1985/finanz-ha/main/docs/steuern.svg)

- **Steuern heute:** Bund nach Tarif, Kanton und Gemeinde als Kurve durch die letzte Veranlagung, Grenz- und
  effektiver Steuersatz – bei Konkubinat pro Steuererklärung.
- **Abzüge simulieren:** 3a-Maximum und PK-Einkäufe pro Person mit Ersparnis; der optimale Einkauf über mehrere
  Jahre steht unter [Szenarien](#szenarien).
- **Steuerdokumente:** Steuererklärungen, Veranlagungsverfügungen und Steuerrechnungen hochladen (auch mehrere
  Jahre). Erkannt werden Steuerperiode, Person, steuerbares Einkommen Kanton und Bund, steuerbares Vermögen,
  Staats-, Gemeinde- und Bundessteuer, Lohn, Eigenmietwert, Mietertrag und Abzüge (3a, PK-Einkauf, Schuldzinsen,
  Liegenschaftsunterhalt, Berufskosten, Kinder). Daraus entstehen:
  - **Vergleich pro Person** über die Jahre (Veranlagung vor Erklärung) mit Veränderung zum Vorjahr
  - **Grenzsteuersatz** Kanton + Gemeinde aus zwei Veranlagungen (Δ Steuer ÷ Δ Einkommen), übernehmbar
  - **Abgleich** Erklärung ↔ Veranlagung: Korrekturen der Steuerverwaltung (Einsprache meist innert 30 Tagen)
  - **Hinweise:** 3a offen, PK-Einkauf ungenutzt, Unterhalt Pauschale vs. effektiv, Eigenmietwert bis 2028,
    Mietertrag, Kinderabzug im Konkubinat
  - **Übernahme** in die Steuer-Einstellungen der Person, Eigenmietwert und 3a
- **Kapitalbezug PK und 3a:** alles im Pensionsjahr gegenüber gestaffelt, pro Steuereinheit.
- **Vermögenssteuer:** Betrag aus der Veranlagung (`steuern.vermoegenssteuer`, auch aus Steuerdokumenten) oder
  steuerbares Vermögen × `kennzahlen.vermoegen_promille` ‰. «Steuern total pro Jahr» = Einkommens- plus Vermögenssteuer.

## Wohnen

Tragbarkeit nach Bankenpraxis (Mieteinnahmen zu 80 %), Belehnung, maximal tragbarer Preis, effektive Kosten,
Wirkung des Wegfalls des Eigenmietwerts ab 2029 und – mit Fälligkeit der Hypothek – das **Amortisations-Szenario**:
heute liquide Mittel (ohne die Arten unter `wohnen.nicht_antasten`) + Sparen bis zur Fälligkeit + verpfändete
3a/3b − Steuer beim Bezug − geplante PK-Einkäufe (nach Steuerersparnis) − Notreserve, verglichen mit Ziel- und
Maximal-Amortisation.

## Vermögen

Konten mit Art (Bank, Wertschriften, Krypto, Vorsorge 3b, Immobilie, Hypothek, Kredit, Sonstiges) und Person.
**Anlage-Check.** Teilt das Finanzvermögen (Konten, Depot, Krypto, Übriges) in Töpfe: Notreserve (`wohnen.reserve`,
sonst ein halber Jahresbedarf), Amortisation bei Fälligkeit (Ziel bzw. Maximum, soweit nicht aus Sparen und
verpfändeter Vorsorge gedeckt; sicher und terminiert anlegen), geplante PK-Einkäufe und den langfristigen Topf mit
Aktienquote nach Risikoprofil (tief 25 %, mittel 50 %, hoch 75 %; Renditeannahmen 2 / 3,5 / 5 %). Dazu der Anteil auf
Konten, in Aktien und Krypto (Richtwert höchstens 5 %), der mögliche Mehrertrag pro Jahr und bis zur Pensionierung,
Hinweise zu Klumpenrisiko (Arbeitgeberaktien) und Hypothekarzins. Risikoprofil und Zinsen auf der Karte einstellbar
(`anlage`). Keine Produktempfehlungen.

Saldi von Hand, als eigene Liste oder per **Bank-Import**; ein Saldo pro Konto und Tag, neuere ersetzen ältere.

**Bank-Import.** Kontoauszug im E-Banking als CSV exportieren (Raiffeisen, UBS, ZKB, PostFinance, Kantonalbanken,
Migros Bank, neon, Yuh u. a.) und unter «Vermögen → Bank-Import» hochladen oder als `bank*.csv` bzw. `konto*.csv` in den
Import-Ordner legen. Die App erkennt Kodierung, Trennzeichen, Vorspann-Zeilen, IBAN, Bank und die Spalten (Datum,
Saldo, Betrag oder Gutschrift/Belastung) und übernimmt den letzten Saldo jedes Monats. Der Kontoname entsteht
automatisch (z. B. «Raiffeisen …7890») oder wird angegeben. Fehlt die Saldo-Spalte, den heutigen Kontostand als
Endsaldo angeben; die App rechnet die Monatssaldi aus den Beträgen zurück. Hypotheken und Kredite zählen
negativ. Das freie Vermögen (ohne Immobilie und Hypothek) fliesst in den Kapitalverzehr im Ruhestand.

## Versicherungen

Policen als PDF (mehrere gleichzeitig) oder als CSV-Liste (`Versicherung;Anbieter;Betrag;Person;Summe;Notiz`). Die
Sparte wird aus Text bzw. Bezeichnung erkannt; jedes Feld lässt sich auf der Vertragsseite korrigieren.

- **Deckungscheck:** Grundversicherung pro Person und Kind, Privathaftpflicht, Hausrat, Gebäude (kantonal + privat
  ist üblich), Todesfallsumme gegenüber Hypothek und Kindern, Doppelversicherungen, Unfall in der Grundversicherung
  bei Angestellten, Franchise, Sparversicherungen, Erwerbsunfähigkeit
- **Kündigungstermine:** Grundversicherung bis 30. November auf 1. Januar, sonst auf Ablauf bzw. nach 3 Jahren
  (Art. 35a VVG)
- **Krankenkasse: Franchise und Modell:** Pro Person und Kind Prämie pro Monat, Franchise, erwartete
  Gesundheitskosten (was die Grundversicherung bezahlt), Modell und Unfalldeckung eintragen (vorbelegt aus den
  KVG-Policen). Gesamtkosten = Prämie + Franchise + 10 % Selbstbehalt (höchstens 700, Kinder 350). Ohne eigene Offerten
  schätzt die App die Prämien anderer Franchisen mit dem gesetzlichen Höchstrabatt (70 % des Risikounterschieds,
  höchstens 50 % der Prämie). Ergebnis: optimale Franchise, Ersparnis, Kosten bei 0 bis 10'000 Franken
  Gesundheitskosten, ab welchen Kosten die tiefste Franchise lohnt, Hinweise zu Hausarzt/Telmed (`rabatt_modell`) und
  Unfall sistieren. Eigene Offerten unter `krankenkasse.personen[].angebote` (`{2500: 380.50}`). Wechsel bis 30. November.
- **Risiko Invalidität und Tod** pro Person: IV-Rente der AHV, PK und externe Policen gegenüber dem Lohn; Renten für
  Hinterbliebene und Todesfallkapital gegenüber dem Richtwert

## Szenarien

**PK-Einkauf optimieren.** Person, Budget (0 = ganzes Potenzial), Zeitraum, Mindest-Ersparnis pro Franken und
Schrittweite wählen. Die App legt Schritt für Schritt dort ein, wo der nächste Franken am meisten Steuern spart
(gleiches Einkommen in jedem Jahr angenommen) – so entsteht eine gleichmässige Verteilung. Einkäufe in den 3 Jahren
vor einem geplanten Kapitalbezug sind gesperrt; Schritte unter der Mindest-Ersparnis werden nicht eingeplant.

Das Ergebnis zeigt Einkauf und Ersparnis pro Jahr, die Ersparnis des letzten Frankens (Ampel: ≥ 30 % grün,
≥ 20 % gelb), den Vorteil gegenüber «alles in einem Jahr», den Netto-Vorteil (inkl. Zins bis 65, abzüglich der
zusätzlichen Kapitalbezugssteuer) und die Kurve der Grenz-Ersparnis. «Plan übernehmen» trägt die Einkäufe unter
`pk.einkauf_geplant` ein; ein erneuter Lauf rechnet nur noch mit dem verbleibenden Potenzial.

![Amortisation und Hypothek](https://raw.githubusercontent.com/khu1985/finanz-ha/main/docs/hypothek.svg)

**Frühpensionierung.** Vergleicht den Rücktritt des ganzen Haushalts mit 58 bis 65: Pensionskasse mit Guthaben bis
zum Rücktritt (Prognose der Kasse anteilig gekürzt) und einem pro Jahr vor 65 um `fruehpension.pk_kuerzung_uws`
Prozentpunkte tieferen Umwandlungssatz; AHV frühestens mit 63 (−6,8 % pro Jahr Vorbezug); bis 65 AHV-Beiträge als
Nichterwerbstätige (Schätzung aus Vermögen und Renten); Überbrückung bis zur AHV = Bedarf minus PK-Renten aus dem
Kapital; das Sparen endet mit dem Rücktritt; das restliche Kapital wird bis zum gleichen Lebensende verzehrt. Ergebnis:
Einkommen und Lücke pro Alter (Diagramm mit Bedarf) und das früheste Alter ohne Lücke.

**Hypothekar-Strategie.** Vergleicht für die Hypothek ab Fälligkeit (nach dem Amortisations-Szenario) SARON,
Festhypotheken und Mischungen bzw. Staffelungen über drei SARON-Szenarien (tief, basis, stress; Zielniveau und
Anstiegsjahre einstellbar). Die SARON-Hypothek kostet SARON + Marge; eine Festhypothek läuft zum heutigen Satz und
wird bei Ablauf zum SARON des Verlängerungsjahres plus der heutigen Laufzeitprämie verlängert. Ergebnis: Zinskosten
über den Horizont je Szenario, höchste Jahreskosten im Stress, Zinsbindung, Ampel nach Robustheit und eine Empfehlung
für maximale Sicherheit (tiefste Kosten im Stress). Dazu der «Preis der Sicherheit» gegenüber SARON, ein Richtwert für
eine Forward-Festhypothek und Hinweise zu Vorfälligkeit und Staffelung. Sätze lassen sich auf der Seite oder unter
`wohnen.strategie` (`saron`, `marge_saron`, `fest`, `szenarien`, `strategien`, `forward_aufschlag`) anpassen – eigene
Offerten eintragen.

**Verheiratet oder Konkubinat.** Braucht je Person eine Steuererklärung unter `steuern.personen`. Verglichen werden:

| Punkt | Annahme bei Heirat |
|---|---|
| Einkommenssteuern heute | Bund: Summe beider Einkommen, Verheiratetenabzug, Zweiverdienerabzug (50 % des tieferen Erwerbseinkommens, 8'600 bis 14'100), Versicherungsabzug Ehe, Elterntarif. Kanton: Summe mit Splitting-Divisor (`steuern.ehe_splitting_divisor`) auf dem Mittel der beiden Steuerkurven |
| AHV-Renten | Plafonierung beider Renten auf 150 % der Maximalrente |
| Kapitalbezüge | im gleichen Jahr zusammengerechnet |
| Hinterbliebene | AHV-Witwen-/Witwerrente und PK-Ehegattenrente statt nur Waisenrenten bzw. gemeldeter Lebenspartnerrente |

Dazu eine Gesamtbilanz (Steuern bis zur Pensionierung, AHV über die Ruhestandsjahre, Kapitalbezug einmalig; ohne
Teuerung und Zins) und die rechtlichen Unterschiede (Erbrecht, Pensionskasse, Güterrecht). Die Bilanz steht zweimal:
mit gemeinsamer Besteuerung bis zur Pensionierung und mit **Individualbesteuerung** ab
`kennzahlen.individualbesteuerung_ab` (Standard 2032; am 8. März 2026 angenommen, Kantone spätestens 2032). Ab dann
zählt bei den Einkommenssteuern kein Heiratsunterschied mehr; AHV-Plafond, Hinterbliebenenleistungen und Erbrecht
bleiben.

## Nachlass und Absicherung

Für jeden Todesfall (Person A stirbt, Person B stirbt) zeigt die Seite, was der überlebende Partner erhält:

| Zeile | Herkunft |
|---|---|
| Erbteil ohne / mit Testament | Konkubinat: ohne Testament nichts; mit Testament die frei verfügbare Quote (mit Kindern ½, sonst alles). Verheiratet: ½ bzw. ¾ mit Testament |
| Erbschaftssteuer | nach Wohnkanton (`nachlass.erbschaftssteuer` überschreibt); BL: Konkubinat ab 5 Jahren gemeinsamem Wohnsitz (`nachlass.zusammen_seit`) 15 % nach 30'000, sonst 30 % nach 10'000; Ehegatten befreit |
| AHV, Pensionskasse | Witwen-/Witwerrente bzw. Waisenrenten; PK-Lebenspartnerrente nur, wenn gemeldet |
| Todesfallkapital, 3a | aus Risiko-Angaben und Begünstigung |
| Liegenschaft | Anteil (`nachlass.anteil_immobilie`) – was an die Erben auszuzahlen wäre, um die Liegenschaft zu behalten |

Die **Checkliste** pro Person (Testament, PK-Partnerschaft gemeldet, Begünstigung 3a und Policen, Vorsorgeauftrag,
Patientenverfügung, Konkubinatsvertrag, Regelung Liegenschaft, Willensvollstrecker, Notfallordner) wird unter
`nachlass.checkliste` gespeichert. Ampel: rot im Konkubinat ohne Testamente, gelb bei offenen Punkten. Keine
Rechtsberatung – Testament und Vorsorgeauftrag handschriftlich bzw. notariell errichten.

## Anlageberater

Sechs Profile: Konservativ, Steueroptimierer, Hypothekar- und Immobilienberater, Vorsorge- und Pensionsplaner,
Wachstum, Advocatus Diaboli; eigene unter `berater.profile` (`id`, `name`, `anweisung`). Der Auftrag kombiniert das
Profil mit eurer Situationsbeschreibung (`berater.situation`), den Fakten aus der Planung (Personen, Vorsorge,
Vermögen, Liegenschaft, Amortisations-Szenario, Steuern und Steuerhistorie, Ruhestand, Versicherungen) und eurer
Frage. Mit KI geht er an die KI-Aufgabe von Home Assistant; ohne KI lässt er sich kopieren und die Antwort wieder
einfügen. Alle Beratungen bleiben gespeichert. Die Berater sind KI-Profile, keine zugelassenen Anlageberater.

## Erinnerungen

![Jahreslauf](https://raw.githubusercontent.com/khu1985/finanz-ha/main/docs/prozess-jahr.svg)

Die Übersicht zeigt anstehende Aufgaben mit Ampel (rot ≤ 7 Tage oder überfällig, gelb ≤ 30 Tage) und dem Knopf
«erledigt», der die Aufgabe bis zur nächsten Periode ausblendet:

| Erinnerung | Zeitraum | Fällig |
|---|---|---|
| 3a einzahlen (pro Person mit Lohn) | ab 15. Oktober | 20. Dezember |
| Geplanter PK-Einkauf dieses Jahres | ab 1. September | 10. Dezember |
| Krankenkasse vergleichen | 20. September bis 30. November | 30. November |
| Kündigungsfristen der Verträge | 60 Tage vorher | Fristende |
| Steuererklärung | 2 Monate vor der ordentlichen Frist | Frist des Wohnkantons bzw. gewährte Erstreckung (siehe unten) |
| PK-Einkauf prüfen (aus dem Optimierer, wenn kein Einkauf geplant) | ab 1. September | 10. Dezember |
| 3a-Lücke des Vorjahres nachzahlen (aus den Steuerdokumenten) | ab 1. September | 20. Dezember |
| Liegenschaftsunterhalt planen (bis zum Wegfall des Eigenmietwerts) | ab 1. Oktober, bis 2028 | 31. Dezember |
| Weiteres 3a-Konto eröffnen (weniger als 3 Konten) | ab 15. Oktober | 20. Dezember |
| Neue Vorsorgeausweise hochladen | Februar bis April | 31. März |
| Kennzahlen prüfen | Januar | 31. Januar |
| Hypothek vorbereiten | 36 Monate vor Fälligkeit | 12 Monate vor Fälligkeit |
| Saldi nachführen | wenn die letzten Saldi über einen Monat alt sind | – |

**Frist der Steuererklärung.** Die App kennt die ordentliche Frist und die spätestmögliche Erstreckung aller
26 Kantone (Stand Steuerjahr 2025) und nimmt den Kanton aus `haushalt.kanton`. Wo die Frist auf dem Formular steht
oder die Quellen abweichen, weist sie darauf hin. Eine abweichende Frist laut Formular unter Einstellungen →
Erinnerungen als «Frist Steuererklärung» (MM-TT) eintragen, eine gewährte Erstreckung als «Fristerstreckung bis».
Die Karte «Frist Steuererklärung» unter Steuern zeigt den Stand mit Ampel (rot ≤ 14 Tage, gelb ≤ 60 Tage).

Eigene Erinnerungen unter `erinnerungen.eigene`:

```yaml
erinnerungen:
  eigene:
    - {titel: Depot ausgleichen, datum: "06-30", wiederholung: jaehrlich, vorlauf: 14, text: "Gewichtung prüfen"}
    - {titel: Miete Einliegerwohnung prüfen, datum: "01", wiederholung: monatlich, vorlauf: 3}
    - {titel: Notar, datum: "2027-02-15", text: "Testament besprechen"}
```

**Benachrichtigung aufs Handy:** unter Einstellungen → Erinnerungen `benachrichtigung` setzen – einen Notify-Dienst
(z. B. `notify.mobile_app_iphone`) oder `persistent` für eine Meldung in Home Assistant. Die App prüft stündlich und
sendet je Erinnerung höchstens zwei Meldungen: beim Erscheinen und bei Fälligkeit.

## Sensoren in Home Assistant

Die App liefert ihre Kennzahlen als Sensoren an Home Assistant – für Dashboards, Verlauf und Automationen
(Präfix unter Einstellungen → Sensoren, Standard `finanz`):

| Sensor | Inhalt |
|---|---|
| `sensor.finanz_nettovermoegen`, `_freies_vermoegen`, `_liquiditaet` | CHF; Aufteilung nach Art als Attribut |
| `sensor.finanz_saldi_alter` | Tage seit den letzten Saldi |
| `sensor.finanz_einkommen_ruhestand`, `_pensionsluecke`, `_ersatzquote` | Ruhestand (AHV, PK, Kapitalverzehr als Attribute) |
| `sensor.finanz_fruehestes_pensionsalter` | frühestes Alter ohne Lücke; Einkommen je Alter als Attribut |
| `sensor.finanz_steuern_jahr`, `_grenzsteuersatz` | Steuern heute; pro Person als Attribut |
| `sensor.finanz_steuererklaerung_frist` | Datum der nächsten Frist (Kanton, Erstreckung) |
| `sensor.finanz_amortisation_verfuegbar` | bei Fälligkeit verfügbar; Ziel und Fälligkeit als Attribute |
| `sensor.finanz_versicherungspraemien`, `_krankenkasse_ersparnis` | Prämien; optimale Franchise je Person |
| `sensor.finanz_ungenutzt` | Geld ohne Zweck auf Konten; Mehrertrag und Krypto-Anteil |
| `sensor.finanz_ampel` | `gruen` / `gelb` / `rot`; Bereiche und Texte als Attribute |
| `sensor.finanz_handeln` | Anzahl roter Bereiche |
| `sensor.finanz_erinnerungen`, `_naechste_frist` | anstehende Erinnerungen; nächste mit Titel und Tagen |

Die Werte werden beim Start, alle 15 Minuten und nach jeder Änderung geschrieben. Über die REST-API gesetzte Zustände
überstehen keinen Neustart von Home Assistant; sie erscheinen danach spätestens nach 15 Minuten wieder. Unter
Einstellungen → Sensoren stehen Status, alle Werte und Beispiele für eine Dashboard-Karte und eine Automation.

## Nicht verheiratet (Konkubinat)

`haushalt.zivilstand: ledig` und unter `steuern.personen` je eine Steuererklärung erfassen (`person`,
`steuerbar_bund`, `steuerbar_kanton`, `steuer_kanton_gemeinde`, `grenzsteuersatz_kanton`, `kinder`). Dann gilt:

- getrennte Steuern; die Person mit `kinder: 1` erhält Elterntarif und Verheiratetentarif beim Bund
- Kapitalbezüge pro Person
- AHV ohne Plafonierung, aber auch ohne Witwen-/Witwerrente für den Partner
- PK-Lebenspartnerrente nur, wenn die Partnerschaft der Kasse gemeldet ist (`risiko.partner_bei_pk_gemeldet`)
- Hinweise zu Begünstigung und Erbschaftssteuer

Steuerdokumente legen fehlende Einträge unter `steuern.personen` bei der Übernahme selbst an.

## Ampeln

Grün = in Ordnung, gelb = prüfen, rot = handeln, grau = keine Daten. Die Übersicht zeigt alle Bereiche als
Kacheln (dringendste zuerst, mit Link); Ampeln stehen auch bei Kennzahlen, im Deckungscheck, bei Kündigungsterminen,
Risiko-Tabellen, Amortisation, PK-Einkauf, Szenarien, Dokumenten und Beratungen.

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
| Krankenkasse | Franchisen passen | Optimierung spart ≥ 200 pro Jahr | – |
| Anlage | Aufteilung passt | über 20'000 ohne Zweck auf Konten oder Krypto über dem Richtwert | – |
| Nachlass | Checkliste erledigt | Punkte offen | Konkubinat ohne Testament beider Personen |
| Erinnerungen | nichts in den nächsten 30 Tagen | etwas innert 30 Tagen | etwas innert 7 Tagen oder überfällig |
| Daten | Saldi ≤ 45 Tage, keine TODO | bis 120 Tage oder TODO offen | älter |

## Persönliche Daten und Import-Ordner

![Dokumentverarbeitung](https://raw.githubusercontent.com/khu1985/finanz-ha/main/docs/dokumente.svg)

Persönliche Daten gehören **nicht** ins GitHub-Repository. Kopiere sie (Samba, File editor oder Studio Code Server)
in den Import-Ordner der App: `/addon_configs/<…>_finanz/import/` (in der App `/config/import/`). Die App liest ihn
beim Start und mit «Einstellungen → Import-Ordner jetzt einlesen» ein und verschiebt erledigte Dateien nach
`import/erledigt/`.

| Datei | Wirkung |
|---|---|
| `finanz.yaml` | ersetzt die Konfiguration (vorherige Fassung als `finanz.yaml.bak`) |
| `vermoegen*.csv` | Konten und Saldi (`Datum;Konto;Saldo;Art;Person`) |
| `bank*.csv`, `konto*.csv` | Kontoauszug aus dem E-Banking (Monatssaldi) |
| `versicherungen*.csv` | Versicherungsliste (`Versicherung;Anbieter;Betrag;Person;Summe;Notiz`) |
| `versicherung*.pdf`, `police*.pdf` | Versicherungsvertrag analysieren |
| `steuer*.pdf`, `veranlagung*.pdf` | Steuerdokument analysieren |
| übrige `*.pdf` | Vorsorgedokument (Vorsorgeausweis, 3a-, IK-Auszug) analysieren |

## Konfiguration

Alles steht in `finanz.yaml`; fehlende Schlüssel ergänzt die App aus der Vorlage. Bearbeiten über das Formular
oder **Einstellungen → Experte**.

| Abschnitt | Inhalt |
|---|---|
| `haushalt` | Name, Zivilstand (`verheiratet`/`ledig`), Kanton, Kinder, Bedarf im Ruhestand, Kapitalverzehr |
| `personen[]` | Geburtsdatum, Pensionierungsalter, Bruttolohn, Sparpotenzial; `ahv`, `pk` (inkl. Ausweis-Prognose, Einkäufe, Kapitalbezug), `risiko`, `saeule3a` |
| `steuern` | Haushaltswerte (verheiratet) oder `personen[]` (Konkubinat), steuerbares Vermögen und Vermögenssteuer, Kapitalbezugssätze Kanton, Splitting für den Heiratsvergleich |
| `wohnen` | Wert, Eigenmittel, Zins, Eigenmietwert, Mieteinnahmen, Fälligkeit, Amortisationsziel, Reserve, `nicht_antasten`, `verpfaendet`, `strategie` |
| `erinnerungen` | `benachrichtigung`, `steuererklaerung_frist` (leer = Kanton), `fristerstreckung`, `eigene` |
| `krankenkasse` | `personen[]` (Prämie, Franchise, Kosten, Modell, Unfall, Angebote), `rabatt_modell`, `unfall_anteil` |
| `anlage` | `risiko`, `zins_konto`, `zins_sicher`, `krypto_max` |
| `fruehpension` | `pk_kuerzung_uws` |
| `nachlass` | `zusammen_seit`, `anteil_immobilie`, `erbschaftssteuer` (überschreibt den Kanton), `checkliste` |
| `sensoren` | `aktiv`, `praefix` |
| `ki` | `aktiv`, `entity` |
| `berater` | `situation`, eigene `profile` |
| `annahmen` | Lohnentwicklung, Rendite |
| `kennzahlen` | AHV, BVG, 3a, Bundessteuertarif und Abzüge, Tragbarkeit, `vermoegen_promille`, `individualbesteuerung_ab` (Stand 2026) |

Die Kennzahlen werden in der Regel alle zwei Jahre (AHV/BVG) bzw. jährlich (3a, Steuertarif, Abzüge) angepasst
und lassen sich im YAML-Editor überschreiben.

## Rechenmodell

Alle Beträge in heutigen Franken (keine Teuerung).

**AHV.** Monatliche Vollrente nach Rentenskala 44 als stetige Formel (bis 15'120: Minimalrente, bis 45'360: 74 %
der Minimalrente + 13/600 des Einkommens, darüber 104 % + 8/600, höchstens Maximalrente). Teilrente = Vollrente ×
Beitragsjahre ÷ 44. Beitragsjahre = bisherige + künftige bis 65 (bei Frühpensionierung als Nichterwerbstätige weiter
bezahlt). Verheiratete: Einkommen beider gemittelt (Splitting), Erziehungsgutschriften (3 × jährliche Minimalrente
pro Jahr mit Kind unter 16) hälftig; Summe höchstens 150 % der Maximalrente. Vorbezug −6,8 % pro Jahr, Aufschub
nach Tabelle. 13 Monatsrenten pro Jahr. IV-Rente ≈ Altersrente ohne 13. Rente, Kinderrenten 40 %, Witwen-/Witwerrente
80 %.

**Pensionskasse.** Jährlich: Guthaben × (1 + Zins) + Sparbeitrag + Einkauf. Sparbeitrag laut Ausweis, sonst
BVG-Minimum (koordinierter Lohn × Altersgutschrift 7/10/15/18 %). Mit Ausweis-Prognose: Alterskapital und
Umwandlungssatz der Kasse, geplante Einkäufe mit Zins dazu. Rente = Guthaben ohne Kapitalanteil × Umwandlungssatz.

**Säule 3a.** Guthaben × (1 + Rendite) + Beitrag bis zur Pensionierung.

**Pensionslücke.** Einkommen ab dem Jahr, in dem alle pensioniert sind = AHV + PK-Renten + Kapitalverzehr
(Annuität aus 3a, PK-Kapital und freiem Vermögen nach Kapitalbezugssteuer über die eingestellten Jahre und
Rendite). Der Bedarf versteht sich inkl. Steuern.

**Steuern.** Direkte Bundessteuer exakt nach Tarif (Verheirateten- bzw. Elterntarif mit CHF 263 pro Kind oder
Grundtarif, Höchstsatz 11,5 %). Staats- und Gemeindesteuer als Kurve durch die letzte Veranlagung:
Steuer(x) = Steuer_ref × (x ÷ Einkommen_ref)^e, mit e so gewählt, dass beim Referenzeinkommen genau der
Grenzsteuersatz gilt – grosse Abzüge sinken so progressiv statt linear. Kapitalleistungen: Bund ein Fünftel des
Tarifs, Kanton mit effektivem Satz aus `steuern.kapitalbezug_kanton` (Schätzwerte – mit dem kantonalen Rechner
ersetzen). Gestaffelt: ein 3a-Konto pro Jahr, das letzte im Pensionsjahr, frühestens ab 60.

**Wohnen.** Tragbarkeit = (Hypothek × 5 % + Unterhalt/Nebenkosten + Amortisation der 2. Hypothek über 66,7 % in
höchstens 15 Jahren bzw. bis zur Pensionierung) ÷ (Bruttoeinkommen + 80 % der Mieteinnahmen), höchstens 33 %.
Belehnung höchstens 80 %, mindestens 10 % Eigenmittel ohne PK. Wegfall Eigenmietwert: heute versteuerter Saldo
(Eigenmietwert − Schuldzinsen − 20 % Unterhaltspauschale) × Grenzsteuersatz.

**Erkennung von Dokumenten.** Lokal mit Mustern aus der Textebene des PDFs (erste 40 Seiten). Gescannte PDFs ohne
Text werden gespeichert; die Werte dann von Hand eintragen oder per KI auslesen, sofern das PDF Text enthält.

## KI (optional)

In Home Assistant eine KI-Integration mit KI-Aufgabe einrichten (z. B. OpenAI, Anthropic, Google), dann unter
Einstellungen «KI-Aufgabe nutzen» auf ja und optional die Entität setzen. Genutzt für Berater sowie zum Auslesen von
Verträgen, Vorsorge- und Steuerdokumenten. Dabei verlassen Dokumenttext bzw. Planungsdaten Home Assistant in
Richtung des gewählten KI-Anbieters.

## Daten, Sicherung und Sicherheit

![Architektur](https://raw.githubusercontent.com/khu1985/finanz-ha/main/docs/architektur.svg)

| Datei / Ordner | Inhalt |
|---|---|
| `finanz.yaml` | Konfiguration; frühere Fassung als `finanz.yaml.bak` |
| `finanz.sqlite` | Konten, Saldi, Verträge, Vorsorge- und Steuerdokumente, Beratungen, erledigte und gesendete Erinnerungen |
| `versicherungen/`, `vorsorge/`, `steuern/` | hochgeladene PDFs |
| `import/` | Import-Ordner, erledigte Dateien unter `import/erledigt/` |
| `finanz.log` | Protokoll (rotiert bei 1 MB) |

Alles liegt im Konfigurationsordner der App und ist im Home-Assistant-Backup enthalten. Ohne KI braucht die App
kein Internet. Sie läuft nur über Ingress (kein offener Port) und mit eigenem AppArmor-Profil (`apparmor.txt`) –
zusammen Sicherheitsbewertung 8. `homeassistant_api` wird nur für die optionale KI-Aufgabe und die
Benachrichtigungen und Sensoren genutzt.

## Fehlersuche

- **App startet nicht:** App-Protokoll in Home Assistant ansehen; bei «Permission denied» betrifft es meist das
  AppArmor-Profil – bitte melden.
- **Seite zeigt «Fehler»:** meist ein Wert im falschen Format (z. B. Text statt Zahl, Datum nicht `JJJJ-MM-TT`).
  Details im Protokoll der App; Konfiguration im YAML-Editor korrigieren oder `finanz.yaml.bak` zurückholen.
- **Dokument erkennt nichts:** «Ausgelesener Text» auf der Dokumentseite prüfen. Ist er leer, ist das PDF gescannt.
- **Bank-Import meldet «Keine Kopfzeile»:** Den Auszug als CSV (nicht PDF/Excel) exportieren; die Kopfzeile muss
  eine Datums- und eine Betrags- oder Saldo-Spalte enthalten.
- **Keine Benachrichtigung:** Namen des Notify-Dienstes in Home Assistant unter Entwicklerwerkzeuge → Aktionen prüfen;
  Fehler stehen im Protokoll.
- **Import-Ordner liest nichts:** Dateinamen prüfen (siehe Tabelle); fehlerhafte Dateien bleiben im Ordner, der
  Grund steht im Protokoll.
- **Vorabversion testen:** `https://github.com/khu1985/finanz-ha#tests` als Repository hinzufügen.
