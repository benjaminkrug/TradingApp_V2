# Phase 10 — Forward Testing: Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 14 und 19 ("Forward Testing über mehrere Wochen, idealerweise Monate, vor jedem Echtgeldeinsatz"; mindestens 20 Trades bzw. ca. 3 Monate, Transkript `FbuYWdwA_wU`; Ergebnis: "Bestätigung der OOS-Ergebnisse").

## Wichtige Einordnung vor allem anderen

Forward Testing ist **kein Backtest**. Ein Backtest (und Phase 9s Paper-Trading-Demo) verarbeitet eine feste, bereits vorliegende Bar-Serie in einem Aufruf. Forward Testing ist über echte, verstreichende Kalenderzeit definiert — neue Bars entstehen, während der Markt tatsächlich läuft, über Tage und Wochen hinweg. Das lässt sich durch keinen Code in einen einzigen Funktionsaufruf komprimieren, ohne zu behaupten, etwas sei passiert, was nicht passiert ist. Diese Phase liefert deshalb **keine "abgeschlossene 3-Monats-Forward-Test"-Aussage** — das wäre erfunden. Sie liefert die Infrastruktur, mit der ein solcher Test über viele einzelne, über echte Zeit verteilte Datenabrufe hinweg verfolgt und gegen ROADMAP's eigenes Kriterium ausgewertet werden kann.

## Was gebaut wurde

**`app/forward_test/session.py`**

- `ForwardTestSession` — verpackt Phase 9s exakte `PaperTradingEngine`/`Portfolio`/`DailyLossGuard` (keine neue Ausführungslogik). `ingest(bars)` ist für wiederholten Aufruf gebaut — einmal pro echtem Datenabruf (z. B. täglich), nicht einmal mit der gesamten Historie. Das ist der Unterschied zu Phase 9s `run_paper_trading()`, das eine feste Batch-Periode auf einmal verarbeitet.
- `ForwardTestCriteria` (Standard: `min_trades=20`, `min_days=90.0`) und `ForwardTestStatus.ready_for_review` — direkt ROADMAP's "mindestens 20 Trades bzw. ca. 3 Monate", "bzw." als ODER ausgewertet (ein Kriterium reicht).
- `compare_to_oos()` — Vergleichsbericht zwischen einer bereits vorliegenden OOS-`Metrics` (Phase 5) und der laufenden Forward-Test-`Metrics`. **Bewusst kein Pass/Fail-Gate mit erfundener Toleranzschwelle** — ROADMAP nennt keine Zahl dafür, wie viel Abweichung noch "bestätigt" bedeutet, und das selbst festzulegen wäre genau die Art unbestätigte Geschäftsentscheidung, die bei DECISIONS.md #4/#5 an den Nutzer eskaliert wurde. Einzig eindeutig ohne Schwellenwert: ein Vorzeichenwechsel der Expectancy zwischen OOS und Forward-Test ist unzweideutig "bestätigt die OOS-Ergebnisse nicht" — das wird explizit geflaggt, alles andere bleibt Zahlen für eine menschliche Einschätzung.

**`scripts/phase10_forward_test_demo.py`** — nutzt `RelativeVolumeMomentumStrategy` (Phase 7), rechnet deren dort dokumentiertes OOS-Ergebnis aus derselben reproduzierbaren Quelle neu nach (statt es aus PHASE7_NOTES.md abzutippen — Ergebnis stimmt exakt überein: Expectancy 0,1867 über 21 Trades), simuliert dann eine *separate, spätere, anders geseedete* synthetische Periode (95 Handelstage) als "neu entstandene Daten nach Abschluss der Strategieentwicklung" und füttert sie tageweise in `ForwardTestSession.ingest()`.

## Ein echter Fund: OOS- und Forward-Test-Expectancy sind zahlenmäßig nicht direkt vergleichbar

Der Demo-Lauf zeigte zunächst scheinbar widersprüchliche Zahlen: OOS-Expectancy 0,19 USD/Trade, Forward-Test-Expectancy 21,89 USD/Trade — ein Faktor von ~117. Nachgeprüft: **kein Fehler in der Strategie**, sondern ein Skalenunterschied zwischen den beiden Quellen. `reference_engine.run_reference_backtest()` (Quelle der OOS-Zahl) handelt laut eigener Dokumentation immer genau 1 Einheit pro Trade — ein bewusster Scope-Limit für eine Korrektheits-Referenz-Engine (Phase 2). `ForwardTestSession` dagegen nutzt Phase 9s realistische, risikobasierte Positionsgrößenberechnung (`position_size()`, oft weit über 1 Aktie). Ein Dollar-Betrag pro Trade skaliert direkt mit der Stückzahl — der Vergleich zweier Expectancy-*Beträge* über diese beiden Quellen hinweg ist deshalb bedeutungslos, nur das **Vorzeichen** bleibt vergleichbar (was `compare_to_oos()` von Anfang an auch war einzige Aussage, die es trifft). `OosComparisonReport.note` warnt jetzt explizit davor, damit niemand die rohen Zahlen als "Forward-Test performt 100× besser" fehlliest.

## Bewusst nicht in dieser Phase gebaut: News & Earnings Filter

ROADMAP Abschnitt 14 trägt den Titel "News & Earnings Filter, Paper Trading, Forward Testing" und verlangt "Vor jedem Trade: Prüfung auf Earnings, relevante News, ungewöhnliche Volatilität". Das wurde **in keiner bisherigen Phase gebaut und war bislang auch in keiner PHASE\*_NOTES.md als offener Punkt vermerkt** — ein echter, bisher unbenannter Lücke, die hier zur Konsistenz nachgetragen wird, statt sie weiter stillschweigend zu übergehen. Nicht Teil dieser Phase, weil: (a) es keine eigene Phase in der Abschnitt-19-Tabelle hat (nur Paper Trading #9 und Forward Testing #10 sind dort benannt), (b) eine echte Umsetzung eine Nachrichten-/Earnings-Kalender-Datenquelle bräuchte, die in dieser Sandbox ebenso wenig erreichbar ist wie Alpaca/Polygon, und (c) der Nutzer für diese Session nur "Phase 10 weiter" angefragt hat. Empfehlung: vor Phase 11 (Controlled Live Test) nachholen, da Abschnitt 14 es explizit als Vorbedingung "vor jedem Trade" nennt.

## Was noch offen ist

1. **Keine echte Forward-Test-Historie existiert.** Das oben Gebaute ist Infrastruktur, kein Ergebnis. Ein echter Forward-Test beginnt erst, wenn eine Strategie tatsächlich über eine verifizierte Live-/Paper-Datenquelle (Alpaca, weiterhin unverifiziert, siehe PHASE3_NOTES.md/PHASE9_NOTES.md) läuft und `ForwardTestSession.ingest()` über Wochen/Monate hinweg regelmäßig mit echten neuen Daten aufgerufen wird — z. B. durch einen täglichen Cronjob, der `AlpacaProvider.get_bars()` für den letzten Handelstag abruft.
2. **Keine der fünf implementierten Strategien hat bisher ein OOS-PASS über das volle 12-Punkte-Gate.** `RelativeVolumeMomentumStrategy` (hier als Demo-Beispiel genutzt) ist laut PHASE7_NOTES.md OOS-positiv, aber am Walk-Forward-Kriterium gescheitert — als Demo-Vehikel hier trotzdem sinnvoll (zeigt die Forward-Test-Mechanik), aber **keine Empfehlung, diese Strategie tatsächlich live zu testen**.
3. **News & Earnings Filter fehlt weiterhin** (siehe oben) — sollte vor Phase 11 geklärt werden.
4. **Kein Persistenzlayer für `ForwardTestSession`.** Der Zustand lebt nur im Prozessspeicher — für einen über Wochen laufenden Test bräuchte es eine Möglichkeit, `Portfolio`/`DailyLossGuard`/Cursor-Zustand über Prozess-Neustarts hinweg zu speichern und zu laden. Nicht Teil dieser Phase (dieselbe Art von Lücke wie Phase 8s noch nicht angebundenes Trade Journal, siehe PHASE8_NOTES.md/PHASE9_NOTES.md).

200 Tests laufen grün (9 neue: `tests/test_forward_test.py`), 7 weiterhin übersprungen (FastAPI, siehe PHASE8_NOTES.md).

**CI-Ergebnis (Run 31680108346, Commit b7397fb):** alle 4 Jobs grün.
