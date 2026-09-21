# Auswahlschicht ("Stocks in Play") — vorab festgelegtes Protokoll

**Status: vorregistriert.** Geschrieben und committet am 21.09.2026, **bevor** Auswahllogik, Datenanbindung oder Backtest existieren. Der Git-Zeitstempel ist der Beleg. Ergänzt `VALIDATION_PROTOCOL.md` um eine neue Strategiefamilie — K1, K3–K7 gelten unverändert weiter, hier kommen nur die Punkte dazu, die für eine *Auswahlschicht* (statt eines festen Symbol-Sets) neu sind.

## Warum dieses Dokument existiert

Der vollständige Gate-Lauf vom 21.09.2026 (`REAL_DATA_VALIDATION_NOTES.md`) zeigte: 0 von 27 Konfigurationen (3 Strategien × 3 Symbole × 3 Stop-Horizonte) bestehen. Der Permutationstest (K7) ergab einen p-Median von 0,799 — das Einstiegs-Timing auf einem festen Drei-Aktien-Universum trägt keine Information.

Recherche zur Fachliteratur (Zarattini, Barbon, Aziz — "A Profitable Day Trading Strategy For The U.S. Equity Market", SSRN 4729284) lokalisiert den dort belegten Effekt nicht im Einstiegsmuster, sondern in der **Titelauswahl**: Dieselbe Einstiegsregel bringt 3,2 % p. a. (Sharpe 0,48) auf einem ungefilterten Universum und 41,6 % p. a. (Sharpe 2,81) auf den nach Opening Relative Volume gefilterten "Stocks in Play". Der Nutzer hat mit dem Ziel "ernsthaft profitabel werden" entschieden, diese Auswahlschicht zu bauen — DECISIONS.md #1 (kein dynamischer Scanner) wurde dafür aufgehoben, wie zuvor #2 (Haltedauer).

**Wichtig, damit dieses Ergebnis nicht überinterpretiert wird, bevor überhaupt etwas gebaut ist:** Die zitierte Studie ist von 2023/2024. Der unabhängige Replikationsversuch, der in `REAL_DATA_VALIDATION_NOTES.md` referenziert wird (Sharpe −0,06 über 2010–2026), betraf eine **andere** Publikation derselben Autoren (Nasdaq-ETF-Variante ohne Titelauswahl, nur ein Instrument). Die hier zu testende "Stocks in Play"-Variante wurde von uns **nicht** in der unabhängigen Literatur widerlegt gefunden — aber auch nicht unabhängig bestätigt. Ein Bestehen unseres Gates wäre eine notwendige, keine hinreichende Bedingung: Falls der Effekt seit Publikation öffentlich bekannt und dadurch kleiner geworden ist (EMH-Argument aus der Mesfin-Falsifikationsstudie), würde unser Backtest das nicht zeigen können.

## Originalgetreu nachzubauende Methodik

Nicht unsere bisherigen (bereits durchgefallenen) Strategien mit einem Volumenfilter kombinieren, sondern die publizierte Rezeptur eigenständig nachbauen — sonst testen wir wieder etwas anderes als das, wofür es Evidenz gibt.

**Eignungsfilter (täglich neu, auf die gesamte liquide US-Aktienmenge angewendet):**
- Kurs > 5 USD
- Tagesvolumen > 1.000.000 Aktien
- 14-Tage-ATR > 0,50 USD

**Rangliste:** Für jede eignungsfähige Aktie: Volumen der ersten 5 Handelsminuten (09:30–09:35 ET) geteilt durch den 14-Tage-Durchschnitt desselben Fensters ("Opening Relative Volume"). **Top 20** nach diesem Verhältnis werden heute gehandelt, der Rest wird ignoriert.

**Einstieg:** Stop-Order am Ausbruch über das Hoch der ersten 5-Minuten-Kerze — **nur Long**, da DECISIONS.md #3 (Long-only) weiterhin gilt. Das ist eine bewusste, hier offen benannte Abweichung von der Studie, die auch die Short-Seite testet; wir testen nur die Long-Hälfte der Rezeptur.

**Stop-Loss:** 10 % des 14-Tage-ATR ab Einstieg — deutlich enger als alles bisher Getestete. Kein Kursziel, Ausstieg spätestens zum Sitzungsende (passend zu DECISIONS.md #2, das mehrtägiges Halten zwar erlaubt, aber nicht erzwingt — hier wird bewusst der originalgetreue Intraday-Exit dieser spezifischen Strategie übernommen, nicht das allgemeine Mehrtages-Opt-in).

**Positionsgröße:** 0,25 % Risiko pro Trade (DECISIONS.md #5, nicht die 1 % der Studie) und **kein Hebel** (DECISIONS.md #11, die Studie nutzt bis zu 4x). Technische Anmerkung, gegengeprüft an `app/paper/portfolio.py` (nicht nur behauptet): Fees werden dort korrekt proportional zur Stückzahl berechnet (`fee = fee_per_share * quantity`), wodurch der Gewinn linear mit der Positionsgröße skaliert und `trade_return_bp` (Basispunkte des eingesetzten Kapitals) **exakt** unabhängig von Risiko-Prozent und Hebel ist — numerisch verifiziert für Stückzahlen 1 bis 1000. Risiko-Prozent und Hebel verändern also nicht, ob eine Konfiguration K3/K4/K7 besteht.

**Wichtige Ausnahme von dieser Invarianz:** Sie gilt nur, solange eine Order tatsächlich in voller Größe ausgeführt wird. Sobald `max_position_pct` (K2a) oder unzureichende Kaufkraft eine Order kappt oder verwirft, ändert Risiko-Prozent/Hebel, **welche** Trades überhaupt stattfinden — und damit doch das Ergebnis. Genau das ist uns bei K2a bereits passiert (83–136 % Kontoeinsatz, 41–77 % verworfene Orders). Bei einer Auswahlschicht mit potenziell sehr engem Stop (10 % des ATR) ist dieses Risiko eher größer als kleiner — der Positionsdeckel aus K2a bleibt deshalb aktiv, und die Rate verworfener/gekappter Orders wird bei jedem Lauf mit ausgewiesen, nicht stillschweigend hingenommen.

## Neue Kriterien, die K1–K7 ergänzen

### K1-Erweiterung — kein Blick in die Zukunft bei der Auswahl selbst

Die Top-20-Rangliste eines Tages darf ausschließlich aus dem Volumen der ersten 5 Minuten *dieses* Tages und aus zuvor abgeschlossenen Handelstagen berechnet werden — niemals aus späteren Bars desselben Tages. Da die bestehende Punkt-in-Zeit-Architektur (`SimulationCursor`/`StreamingCursor`) genau das strukturell verhindert, muss die Auswahlschicht **auf demselben Cursor-Mechanismus aufgebaut werden**, nicht als separater Vorverarbeitungsschritt mit Zugriff auf die volle Historie. Wird wie K1 per `detect_leakage`-analoger Gegenprobe verifiziert (voller Lauf vs. abgeschnittener Lauf).

### K8 — Survivorship-Bias-sicheres Universum (neu, blockierend)

Ein Backtest gegen die *heutige* Aktienliste würde genau die Ausreißer verstecken, die bei dieser Strategie am wahrscheinlichsten sind: volatile, nachrichtengetriebene Titel, die delisted werden, übernommen werden oder insolvent gehen. Das ist bei dieser Strategie zentraler als bei den bisherigen Large-Cap-Tests, weil "ungewöhnlich hohes Volumen" oft genau der Auslöser für spätere Delistings ist (Übernahmegerüchte, Betrugsvorwürfe, Kapitalerhöhungen in Not).

**Anforderung:** Die tägliche Eignungs- und Ranglisten-Berechnung muss auf einer Punkt-in-Zeit-Aktienliste laufen (`PointInTimeUniverse`, existiert bereits seit Phase 3), die tatsächlich delistete/übernommene Titel für die Zeiträume enthält, in denen sie gehandelt wurden — nicht auf der heutigen Liste rückwirkend angewendet.

**Offener Punkt, noch nicht gelöst:** Woher diese Daten kommen, ist nicht identisch mit der Frage, woher die Kursdaten kommen. `PHASE3_NOTES.md` benennt das seit Phase 3 als ungelöste Lücke ("typischerweise ein kostenpflichtiger Datensatz und eine Beschaffungsaufgabe"). Bevor Databento-Guthaben für Kursdaten ausgegeben wird, muss geprüft werden, ob derselbe Anbieter auch Punkt-in-Zeit-Referenzdaten (delistete Symbole, Handelszeiträume) liefert — das ist bei reinen Marktdaten-APIs nicht selbstverständlich und wird **nicht** unterstellt, sondern vor dem Kauf verifiziert.

**Bis K8 gelöst ist, gilt jeder Gate-Lauf dieser Strategie als vorläufig** und wird entsprechend markiert — genau wie K6 bisher als NOT_APPLICABLE lief, wenn Marktphasen nicht belegt waren.

### Mehrfachtestung

Die Auswahlschicht ist eine neue, eigenständige Konfigurationsfamilie und wird **separat** von den 27 bereits gezählten Läufen protokolliert (siehe `VALIDATION_PROTOCOL.md`, Abschnitt "Protokoll der Mehrfachtestung"). Deklarierte Parameter dieser Familie, die **nicht** nachträglich optimiert werden: Top-N = 20, Rückblickfenster = 14 Tage, Öffnungsfenster = 5 Minuten, Eignungsschwellen wie oben. Jede Abweichung von diesen Werten ist ein neuer, wieder vorab zu registrierender Testpunkt.

## Datenplan

1. **Tagesbars für ein breites Universum** (mehrere tausend US-Aktien, mehrere Jahre) für die Eignungsfilter — klein, güns­tig.
2. **5-Minuten-Bars für die eignungsfähige Menge** über den gesamten Backtest-Zeitraum, mindestens für das Eröffnungsfenster (um die Rangliste zu bilden), für die tatsächlich gehandelten Top-20-Tage vollständig für den Handelstag — das ist der datenintensive Teil.
3. **Punkt-in-Zeit-Universumsdaten** für K8 (delistete Symbole) — Quelle noch offen, siehe oben.

**Vorgehen laut Nutzerentscheidung (DECISIONS.md #12):** Kein kostenloser Alpaca-Pilot vorgeschaltet, direkt das Databento-Startguthaben nutzen. Davor dennoch: eine kleine Testabfrage, um die tatsächlichen Kosten in GB zu messen, statt zu schätzen — verantwortungsvoller Umgang mit einem einmaligen, nicht nachfüllbaren Guthaben, keine erneute Konzept-Pilotierung.

## Was dieses Protokoll ausdrücklich nicht löst

- Es beweist keine zukünftige Profitabilität, selbst bei bestandenem Gate (siehe EMH-Vorbehalt oben).
- Es ersetzt K8 nicht durch eine Notlösung — solange keine echten Punkt-in-Zeit-Referenzdaten vorliegen, bleibt jedes Ergebnis vorläufig.
- Es entscheidet nicht über Hebel oder größeres Risiko für einen späteren Zeitpunkt — DECISIONS.md #11 gilt nur für diesen ersten Test.

## Änderungsprotokoll

| Datum | Änderung | Vor/nach Kenntnis von Ergebnissen? |
|---|---|---|
| 21.09.2026 | Erstfassung, vor jeder Implementierung, Datenanbindung oder jedem Testlauf | vorher |
