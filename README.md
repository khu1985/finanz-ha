# Finanzplanung – Home-Assistant-App

Finanzplanung für einen Schweizer Haushalt (Ehepaar, Konkubinat oder Einzelperson) als App im Home Assistant:
Vorsorge, Steuern, Wohneigentum, Vermögen, Versicherungen und Anlageberater – mit Ampeln, die zeigen, wo etwas
ansteht. Bedienung und Rechenmodell siehe [finanz/DOCS.md](finanz/DOCS.md) (in Home Assistant unter «Dokumentation»),
Änderungen siehe [finanz/CHANGELOG.md](finanz/CHANGELOG.md).

> Keine Anlage-, Steuer- oder Rechtsberatung. Schätzungen mit vereinfachten Modellen.

## Funktionen

| Bereich | Inhalt |
|---|---|
| Übersicht | Ampeln pro Bereich, Kennzahlen, Hinweise, Statuszeile, Vermögensverlauf, Einkommen im Ruhestand |
| Vorsorge | AHV (Rentenskala 44, Splitting, Erziehungsgutschriften, Plafond, 13. Rente), Pensionskasse (Ausweis-Prognose oder BVG-Minimum, Einkäufe, Sperrfrist), Säule 3a, Pensionslücke; Vorsorgeausweis, 3a- und IK-Auszug hochladen |
| Steuern | Bundessteuer nach Tarif, Kanton als Kurve durch die letzte Veranlagung, Konkubinat getrennt, 3a und PK-Einkauf simulieren, Kapitalbezug gestaffelt; Steuererklärungen und Veranlagungen hochladen, Mehrjahresvergleich, Grenzsteuersatz, Abgleich |
| Wohnen | Tragbarkeit, maximaler Kaufpreis, Amortisation bis zur Fälligkeit (inkl. verpfändeter 3a/3b), Wegfall des Eigenmietwerts ab 2029 |
| Vermögen | Konten und Saldi, Bank-Import aus E-Banking-CSV, eigene Listen, Nettovermögen und Verlauf |
| Versicherungen | Policen als PDF oder Liste, Erkennung, Deckungscheck, Kündigungstermine, Risiko Invalidität und Tod |
| Szenarien | PK-Einkäufe optimal auf Jahre verteilen; Hypothekar-Strategie (SARON, Fest, Staffelung, Zinsszenarien); Vergleich verheiratet ↔ Konkubinat |
| Erinnerungen | 3a, PK-Einkauf (inkl. optimaler Betrag), 3a-Lücken, Liegenschaftsunterhalt, Krankenkasse, Kündigungsfristen, Steuererklärung mit Frist des Wohnkantons, Hypothek, eigene; optional Benachrichtigung über Home Assistant |
| Berater | Sechs Beraterprofile mit Situation und Fakten aus der Planung; über die KI-Aufgabe von Home Assistant oder zum Kopieren |
| Einstellungen | Formular, YAML-Editor, Import-Ordner, Export; Protokoll und Änderungen in der App |

## Installation

Home Assistant → Einstellungen → Apps → App-Store → ⋮ → Repositories → `https://github.com/khu1985/finanz-ha`
hinzufügen, dann «Finanzplanung» installieren und starten. Die App erscheint als «Finanzen» in der Seitenleiste.

**Vorabversion testen:** Statt der Adresse oben `https://github.com/khu1985/finanz-ha#tests` hinzufügen. Damit
installiert Home Assistant den Stand des Branches `tests` (siehe [Entwicklung](#entwicklung)). Beide Fassungen lassen
sich nebeneinander installieren; jede hat ihren eigenen Konfigurationsordner.

## Persönliche Daten

Persönliche Daten (Löhne, Guthaben, Saldi, Policen, Ausweise, Steuerunterlagen) gehören **nicht** in dieses
Repository. Sie werden in der App erfasst oder in den Import-Ordner `/addon_configs/<…>_finanz/import/` kopiert
(Samba, File editor, Studio Code Server). Die App liest `finanz.yaml`, `vermoegen*.csv`, `versicherungen*.csv` und PDFs
beim Start oder per Knopf ein. Alles liegt danach im Konfigurationsordner der App und ist im Home-Assistant-Backup
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
        F["Formulare<br/>Einstellungen"]
        I["Import-Ordner<br/>finanz.yaml, CSV, PDF"]
        U["Uploads<br/>Kontoauszüge, Policen,<br/>Vorsorge- und Steuerdokumente"]
    end
    subgraph App["Finanz-App (Container im Home Assistant, Ingress, AppArmor)"]
        direction TB
        S["server.py<br/>Webserver, Formulare, Uploads"]
        D["Dokumente<br/>bankimport, versicherungen,<br/>dokumente, steuerdokumente"]
        K["Rechenkern<br/>vorsorge, steuern, wohnen, vermoegen"]
        Z["Szenarien<br/>szenarien, hypothek, berater"]
        A["ampel.py, erinnerungen.py<br/>Bewertung und Aufgaben"]
        SE["seiten.py<br/>Seiten, Diagramme, Statusanzeige"]
    end
    subgraph Daten["Konfigurationsordner (im Backup)"]
        direction LR
        Y[("finanz.yaml")]
        DB[("finanz.sqlite")]
        P[("PDFs")]
        L[("finanz.log")]
    end
    HA["Home Assistant<br/>KI-Aufgabe, Benachrichtigung"]
    F & I & U --> S
    S --> D --> DB & P
    S --> Y
    Y & DB --> K --> Z
    K & Z --> A --> SE
    Z -. optional .-> HA
    A -. stündlich .-> HA
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
| `finanz/app/vermoegen.py` | Konten, Saldi, CSV-Import, Verlauf |
| `finanz/app/versicherungen.py` | Policen, Erkennung, Deckungscheck, Kündigungstermine, Risiko, KI-Aufgabe |
| `finanz/app/dokumente.py` | Vorsorgeausweis, 3a- und IK-Auszug |
| `finanz/app/steuerdokumente.py` | Steuererklärung, Veranlagung, Mehrjahresvergleich, Abgleich |
| `finanz/app/hypothek.py` | Hypothekar-Strategie über Zinsszenarien |
| `finanz/app/bankimport.py` | Kontoauszüge aus dem E-Banking einlesen |
| `finanz/app/kantone.py` | Fristen der Steuererklärung aller Kantone |
| `finanz/app/erinnerungen.py` | Erinnerungen, erledigt-Status, Benachrichtigung über Home Assistant |
| `finanz/app/szenarien.py` | PK-Einkauf-Optimierung, Vergleich verheiratet ↔ Konkubinat |
| `finanz/app/berater.py` | Beraterprofile, Fakten, Amortisations-Szenario, Beratungen |
| `finanz/app/importordner.py` | Import-Ordner für persönliche Dateien |
| `finanz/app/konfig.py`, `meta.py` | Konfiguration laden/speichern, Version, Changelog, Protokoll |
| `finanz/app/diagramme.py` | Linien- und Säulendiagramme als SVG |
| `finanz/app/default_config.yaml` | Vorlage mit Musterhaushalt und Kennzahlen 2026 |

## Rechenmodell

### Vorsorge und Pensionslücke

[![Rechenmodell Vorsorge](docs/vorsorge.svg)](docs/vorsorge.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart TD
    P["Personen<br/>Geburtsdatum, Lohn, Pensionierungsalter"] --> AHV
    P --> PK
    P --> A3
    VA["Vorsorgeausweis<br/>Prognose mit 65"] -. übernommen .-> PK
    IK["IK-Auszug<br/>Beitragsjahre"] -. übernommen .-> AHV
    AHV["AHV<br/>Skala 44 × Beitragsjahre ÷ 44<br/>Ehe: Splitting, Plafond 150 %<br/>× 13 Monatsrenten"] --> E
    PK["Pensionskasse<br/>Guthaben × (1 + Zins) + Sparbeitrag + Einkauf<br/>Rente = Guthaben ohne Kapital × Umwandlungssatz"] --> E
    PK -- Kapitalanteil --> KAP
    A3["Säule 3a<br/>Guthaben × (1 + Rendite) + Beitrag"] --> KAP
    VM["Freies Vermögen<br/>ohne Immobilie und Hypothek"] --> KAP
    KAP["Kapital bei Pensionierung<br/>− Kapitalbezugssteuer (gestaffelt)"] --> AN["Kapitalverzehr<br/>Annuität über Jahre und Rendite"]
    AN --> E["Einkommen im Ruhestand<br/>AHV + PK-Renten + Kapitalverzehr"]
    B["Bedarf im Ruhestand"] --> L
    E --> L{"Pensionslücke<br/>Bedarf − Einkommen"}
    L --> AMP["Ampel Ruhestand<br/>grün: keine Lücke · gelb: ≤ 10 % · rot: mehr"]
```

</details>

### Steuern und PK-Einkauf

[![Rechenmodell Steuern](docs/steuern.svg)](docs/steuern.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart TD
    SD["Steuerdokumente<br/>Erklärung, Veranlagung"] -. übernommen .-> REF
    REF["Letzte Veranlagung je Steuereinheit<br/>steuerbares Einkommen, Steuer, Grenzsteuersatz"] --> KT
    REF --> BU
    EH{"Zivilstand"} -- verheiratet --> E1["eine Steuereinheit<br/>Haushalt"]
    EH -- Konkubinat --> E2["je Person eine Steuereinheit<br/>Elterntarif für die Person mit Kind"]
    E1 & E2 --> REF
    BU["Bundessteuer<br/>Tarif, Elterntarif −263/Kind, max. 11,5 %"] --> T["Steuer heute"]
    KT["Kanton und Gemeinde<br/>S × (x ÷ E)^e – trifft Steuer und Grenzsatz"] --> T
    T --> AB["Abzug simulieren<br/>Steuer(x) − Steuer(x − Abzug)"]
    AB --> OPT["PK-Einkauf optimieren<br/>Schritt für Schritt ins Jahr mit der<br/>höchsten Ersparnis pro Franken"]
    SP["Sperrfrist<br/>3 Jahre vor Kapitalbezug"] --> OPT
    OPT --> PLAN["Plan pro Jahr<br/>Ersparnis, letzter Franken, Netto-Vorteil"]
    PLAN -. übernehmen .-> EK[("pk.einkauf_geplant")]
    T --> HV["Vergleich verheiratet ↔ Konkubinat<br/>Bund: Summe − Abzüge · Kanton: Splitting"]
```

</details>

### Amortisation und Hypothekar-Strategie

[![Amortisation und Hypothek](docs/hypothek.svg)](docs/hypothek.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart TD
    W["Liegenschaft<br/>Wert, Hypothek, Fälligkeit"] --> AM
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
    U["PDF oder CSV<br/>Upload oder Import-Ordner"] --> T["Text auslesen<br/>pypdf, Kodierung"]
    T --> E{"Art erkennen"}
    E -- Kontoauszug --> B["Bank, IBAN, Spalten<br/>letzter Saldo je Monat"]
    E -- Police --> V["Versicherer, Sparte, Prämie,<br/>Daten, Fristen, Summen"]
    E -- Vorsorge --> VO["Altersguthaben, Einkauf,<br/>Prognose 65, Risikoleistungen"]
    E -- Steuern --> S["Periode, steuerbares Einkommen,<br/>Steuern, Abzüge"]
    T -. optional .-> KI["KI-Aufgabe<br/>Home Assistant"] -. Werte .-> P
    B --> DB[("Saldi")]
    V & VO & S --> P["Prüfen<br/>erkannt ↔ heute"]
    P -- übernehmen --> K[("finanz.yaml")]
    DB & K --> A["Ampeln, Hinweise,<br/>Szenarien, Berater"]
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
    SEITE["jeder Seitenaufruf"] --> AMP["Ampeln neu bewerten<br/>Navigation, Übersicht"]
    LOG["jede Aktion"] --> PR["Protokoll<br/>rotiert bei 1 MB"]
```

</details>

### Im Jahreslauf (von Hand, mit Erinnerungen)

[![Jahreslauf](docs/prozess-jahr.svg)](docs/prozess-jahr.svg)

<details><summary>Als Mermaid-Diagramm</summary>

```mermaid
flowchart TD
    M["monatlich<br/>Kontoauszüge importieren (Bank-Import)"] --> UE["Übersicht und Ampeln aktuell"]
    J["Januar<br/>Kennzahlen prüfen (AHV, BVG, 3a, Tarif)"] --> F
    F["Februar–März<br/>Vorsorgeausweise hochladen und übernehmen"] --> SE
    SE["bis Frist (Standard 31. März)<br/>Steuererklärung einreichen und hochladen"] --> VE
    VE["nach Veranlagung<br/>Veranlagung hochladen: Abgleich, Grenzsteuersatz"] --> SZ
    SZ["Szenarien<br/>PK-Einkauf optimieren, Plan übernehmen"] --> KV
    KV["September–November<br/>Krankenkasse vergleichen, bis 30.11. kündigen"] --> DZ
    DZ["Oktober–Dezember<br/>3a einzahlen (bis 20.12.), PK-Einkauf überweisen (bis 10.12.)"] --> J
    VT["laufend<br/>Kündigungsfristen 60 Tage vorher"] -.-> UE
    HY["36–12 Monate vor Fälligkeit<br/>Hypothekar-Strategie, Offerten, Forward"] -.-> UE
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

Diagramme: Quellen als Mermaid in `docs/*.mmd`, daraus die SVGs mit
`for f in docs/*.mmd; do mmdc -i "$f" -o "${f%.mmd}.svg" -b white -t neutral; done` erzeugen.

## Tests

`tests/` prüft Rechenkern, Dokumenterkennung und Web-App mit erfundenen Daten, z. B. Eckwerte der Rentenskala,
Ehepaar-Plafond und Konkubinat, Bundessteuer an Tarifgrenzen, Kantonssteuer-Kurve, Staffelung, Tragbarkeit,
Erkennung von Policen, Vorsorgeausweisen und Steuerdokumenten aus erzeugten PDFs, Kündigungsfristen nach VVG,
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
