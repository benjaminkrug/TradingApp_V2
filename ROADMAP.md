# AI Short-Term Trading Intelligence Platform — Roadmap v2

> Überarbeitete Fassung nach Analyse der ursprünglichen Roadmap und der vier Referenz-Transkripte (`/transkript`). Änderungen gegenüber v1 sind mit **[v2]** markiert und am Ende jeweils begründet.

## 0. Status dieses Dokuments

Dies ist ein Planungsdokument, keine Implementierung. Es dient als Grundlage für ein technisches PRD und anschließend den Master-Prompt für die Umsetzung. Bevor Code geschrieben wird, müssen die offenen Entscheidungen in Abschnitt 3 getroffen werden.

---

## 1. Projektziel

**Arbeitstitel:** AI Short-Term Trading Intelligence Platform

Eine webbasierte Plattform, die kurzfristige Handelsmöglichkeiten in US-Aktien erkennt, bewertet und als konkrete, nachvollziehbare Trading-Vorschläge liefert — **kein Buy-and-Hold-System**, **kein autonomer Trading-Bot**.

Fokus: kurzfristige Long-Trades, Intraday, klar definierter Entry/Stop/Target, dynamisches Risk Management, quantitatives Backtesting, Out-of-Sample-Validierung, Paper- und Forward-Trading vor jedem Echtgeldeinsatz.

Zielformat einer Ausgabe:

```
BUY – NVDA
Entry: $XXX   Stop Loss: $XXX   Take Profit: $XXX
Risk/Reward: 1:2.4   Signal Score: 87/100
Erwartete Haltedauer: 20–90 Minuten
Strategie: Momentum + VWAP Reclaim
Marktregime: Bullish   Relative Volume: 2.1x   Signalqualität: HIGH
```

Der Nutzer entscheidet über die Ausführung. Das System handelt nicht autonom mit echtem Geld (siehe Abschnitt 8).

---

## 2. Leitprinzip: Der Backtest ist der eigentliche Gegner

> *"Die größte technische Herausforderung ist nicht Claude. Die größte Herausforderung ist: Einen Backtest zu bauen, dem man überhaupt vertrauen kann."*

Jede Zahl, jede Rendite, jeder Score in diesem System ist wertlos, wenn die zugrunde liegende Datenpipeline Look-Ahead Bias, Survivorship Bias oder unrealistische Ausführungsannahmen enthält. Dieses Prinzip hat Vorrang vor jeder anderen Anforderung in diesem Dokument — im Zweifel wird zugunsten von Prüfbarkeit und gegen Geschwindigkeit entschieden.

**[v2] Belegt durch Referenzmaterial:** Im Transkript `wYuP1QFZ0Bg` (Claude soll "so viel Geld wie möglich" verdienen) zeigt sich das Muster live:

1. Versuch 1: **2.000.000 %** Rendite, 8 % Max Drawdown → offensichtlicher Bug (TradingView liefert nur OHLC pro Bar, keine Tick-Daten; ein zu enger Trailing-Stop erzeugt unrealistische Intra-Bar-Fills). DaviddTech selbst: *"There is something completely wrong with this code."*
2. Versuch 2 (mit Stop/Take-Profit): 58.000 % Rendite, aber **66 % Max Drawdown** — für einen Menschen praktisch unhandelbar.
3. Versuch 3 (auf Teilzeitraum optimiert): 5.622 % Rendite, 18 % Drawdown, sieht sauber aus. **Auf dem vollen historischen Datensatz getestet, springt der Drawdown auf 36 %.** Klassisches Overfitting an einen günstig gewählten Zeitraum.

Dieses Beispiel ist die beste verfügbare Illustration für Abschnitt 8 und wird als Referenzfall in der Anti-Overfitting-Dokumentation der Plattform verwendet.

---

## 3. Offene Entscheidungen — mit Empfehlung

Die ursprüngliche Roadmap listete fünf offene Entscheidungen ohne Vorschlag. **[v2]** Hier mit konkreter Empfehlung und Begründung, damit daraus eine Ja/Nein- bzw. Anpassungs-Entscheidung wird statt einer Blankoseite:

| # | Frage | Empfehlung | Begründung |
|---|---|---|---|
| 1 | Welche Aktien? | Statische Liste von ~30 sehr liquiden Large Caps für MVP (kein Live-Scanner in v1) | Reduziert Datenkosten und Survivorship-Bias-Aufwand; dynamischer Scanner kommt nach validierter Pipeline |
| 2 | Haltedauer? | 30 Min – wenige Stunden, Exit spätestens Handelsende | 1–5-Min-Scalping ist am anfälligsten für Slippage/Ausführungsrisiko (siehe Transkript `iQs2oRX6Q`: nur 4 Trades in 2h, statistisch bedeutungslos, DaviddTech selbst würde es nicht live handeln) |
| 3 | Long only oder Long+Short? | Long only für MVP | Short braucht Borrow-Verfügbarkeit/-Kosten als zusätzliche Datenschicht — vermeidbare Komplexität in v1 |
| 4 | Datenanbieter? | **Alpaca** (Start), später **Polygon.io** ergänzen | Bündelt Marktdaten + Paper Trading + spätere Live-Ausführung in einer API; erzwingt technisch das Prinzip "gleiche Logik in Paper wie Live" (Abschnitt 12) |
| 5 | Risiko pro Trade? | 0,25–0,5 % | Konservativ genug für die Lern-/Validierungsphase, deckt sich mit dem Rechenbeispiel in Abschnitt 9 |
| **6 [v2, neu]** | PDT-Status / Kontogröße? | Vor Phase "Controlled Live Test" verbindlich klären | Die FINRA Pattern-Day-Trader-Regel verlangt ≥25.000 $ Kontowert für 4+ Day-Trades in 5 Handelstagen. Ohne diese Klärung ist unklar, ob reines Intraday überhaupt handelbar ist oder ob ein Cash-Account-Modell bzw. Swing-Fallback (Halten über 1–3 Tage) nötig wird. Betrifft direkt Frage 2 und das Kontomodell in Phase "Paper Trading". Crypto-Referenzsysteme (wie in den Transkripten) umgehen dieses Problem nur, weil sie keine Aktien handeln — für uns ist es nicht optional. |

---

## 4. Architektur-Grundsatzentscheidung: Eigenbau vs. Orchestrierung

**[v2] Neu — resultiert direkt aus der Analyse der Referenz-Transkripte.**

Die vier Transkripte zeigen, dass die reale "DaviddTech"-Methodik technisch deutlich leichtgewichtiger ist als ursprünglich angenommen: kein eigenes Backend, sondern **Claude Code + MCP-Server (tradingkit.com für Backtesting, ein TradingView-Indikator-MCP, trigger.trade als Webhook-Bridge zu Broker/Exchange) + TradingView für Charting/Pine-Script/Ausführung**, orchestriert über ein GitHub-Repo mit "Skills" (CLAUDE.md-Workflow-Definitionen) und einen Cronjob.

Das ist eine echte Architektur-Weiche mit unterschiedlichen Trade-offs:

| | **A. Eigenbau** (ursprüngliche Roadmap) | **B. Orchestrierung** (DaviddTech-Stil) |
|---|---|---|
| Geschwindigkeit zum ersten Ergebnis | Wochen bis Monate | Tage |
| Kontrolle über Backtest-Korrektheit | Vollständig, auditierbar | Blackbox eines Drittanbieters (tradingkit.com) — widerspricht Abschnitt 2 |
| US-Aktien-Eignung | Explizit dafür gebaut | Unklar — alle vier Transkripte handeln ausschließlich Crypto (BTC/ETH/USDT); tradingkit.com wird nur für Forex/Gold/Crypto erwähnt, US-Aktien kein einziges Mal |
| Point-in-Time-Korrektheit nachweisbar | Ja, da selbst gebaut | Nein, nicht prüfbar |
| PDT-Problem | Muss aktiv gelöst werden | Wird umgangen (weil Crypto), löst unser Problem nicht |
| Tick-Daten-Genauigkeit im Backtest | Bestimmbar durch eigene Engine | TradingView liefert nur OHLC pro Bar → strukturelles Risiko bei engen Stops (siehe Abschnitt 2) |

**Empfehlung: Hybrid.** TradingView/Pine Script optional als schnelle Ideenfindungs- und Visualisierungsschicht in einer frühen Explorationsphase, aber die eigentliche Validierungs-Pipeline (Backtest mit nachweisbarer Punkt-in-Zeit-Garantie, OOS, Walk-Forward, survivorship-bias-freies Universum) wird selbst gebaut, sobald es um US-Aktien und reales Kapital geht. Grund: Man kann die Korrektheit eines fremden Backtesters nicht auditieren — das widerspricht dem Leitprinzip in Abschnitt 2 direkt.

**[v2] Wichtige Abgrenzung von der Referenzquelle:** Im Transkript `FbuYWdwA_wU` (KI-Hedgefonds "Jarvis") erhält Claude über einen MCP-Server die Fähigkeit, Strategien basierend auf Regeln (z. B. Bollinger-Bänder um die eigene Equity-Kurve) **selbstständig zu pausieren/reaktivieren, während bereits echtes Geld über eine reale Exchange-Anbindung läuft**, gesteuert durch einen unbeaufsichtigten 15-Minuten-Cronjob. Das widerspricht unserer eigenen Regel in Abschnitt 8 ("Claude darf nicht automatisch Echtgeld einsetzen"). Diese Referenzquelle predigt an anderer Stelle Disziplin, demonstriert aber selbst das Gegenteil, vermutlich aus Demo-Gründen. **Diesen Teil der Methodik übernehmen wir nicht.**

---

## 5. Warum kein reiner "AI Trading Bot"

Ein LLM soll nicht selbst aus einem Chart "raten". Schichtenarchitektur:

```
MARKTDATEN → SCANNER → TECHNISCHE FEATURES → MARKTREGIME → STRATEGIE ENGINE
→ SIGNAL ENGINE → RISK ENGINE → SIGNAL SCORING → AI ANALYSIS
→ FINAL TRADE PROPOSAL → PAPER TRADING → FORWARD TESTING
```

Die quantitative Engine erzeugt die Rohsignale. Claude dient zur Strategieentwicklung, Analyse von Testergebnissen, Mustererkennung, Erklärung von Signalen, Regimeanalyse und Hypothesengenerierung — nicht als Entscheider über echtes Kapital.

---

## 6. Trading-Regeln (Phase 1 — vor jeder Codezeile festzulegen)

- **Markt:** US-Aktien, Startuniversum: statische Liste ~30 liquide Large Caps (siehe Abschnitt 3.1), später dynamisches S&P-500-Universum. Keine Penny Stocks.
- **Handelsstil:** Intraday, Trade wird grundsätzlich am selben Handelstag geschlossen.
- **Zeitebenen:** 1h (übergeordneter Trend) → 15m (Setup) → 5m (Entry), optional 1m später. **[v2] Anmerkung:** Multi-Timeframe-Alignment ohne Look-Ahead ist der fehleranfälligste Teil des gesamten Systems (siehe Abschnitt 9) — nicht unterschätzen.
- **[v2] PDT-Rahmen:** siehe Frage 6 in Abschnitt 3, vor Phase "Controlled Live Test" verbindlich klären.

---

## 7. Market Data Layer

Benötigt: OHLCV, Intraday, Historie, Near-Realtime, Volumen, Corporate Actions, Splits, Trading Calendar, Market Hours, plus SPY/QQQ/Sektor-ETFs/VIX zur Unterscheidung "Aktie ist stark" vs. "Markt zieht alles mit".

**[v2] Ergänzung — Survivorship Bias:** Ein Backtest gegen die *heutige* S&P-500-Zusammensetzung über mehrere Jahre ist systematisch zu optimistisch, weil ausgeschiedene/gescheiterte Unternehmen fehlen. Erforderlich: **historische Index-Mitgliedschaft mit Datumsstempel** (welche Aktie war an Tag X im Index). Das ist bei den meisten günstigen Datenanbietern nicht sauber enthalten und muss explizit beschafft/geprüft werden — gehört als Pflichtpunkt in diese Phase, nicht nur in die Checkliste (Abschnitt 15).

**[v2] Ergänzung — Point-in-Time-Zwang:** Die Datenschicht muss so gebaut sein, dass zu einem Simulationszeitpunkt t **strukturell kein Zugriff auf Daten von t+1 möglich ist** (z. B. eine Point-in-Time-API statt direkter DataFrame-Indizierung). Das ist der einzige verlässliche Schutz gegen Look-Ahead Bias — eine reine Verhaltensregel für Claude ("nutze keine Zukunftsdaten") reicht nicht, da auch unabsichtliche Fehler beim Feature-Engineering leicht Zukunftsdaten einschleusen.

---

## 8. Rolle von Claude — erlaubt / verboten

**Claude darf:** Strategien entwickeln und programmieren, Backtests ausführen, Ergebnisse analysieren, Strategien vergleichen, Hypothesen entwickeln, Fehler im Backtest suchen, Parameter testen, Reports erzeugen, Strategien versionieren.

**Claude darf NICHT:** Backtest-Ergebnisse manipulieren, Daten aus der Zukunft verwenden, eine Strategie aufgrund eines einzelnen Ergebnisses aktivieren, OOS-Daten zur Optimierung verwenden, Risiken ignorieren, **automatisch Echtgeld einsetzen**.

**[v2] Diese Regeln müssen technisch erzwungen werden, nicht nur als Prompt-Anweisung existieren:**
- Look-Ahead-Schutz → Point-in-Time-API (Abschnitt 7), kein Vertrauen auf Verhalten.
- "Keine OOS-Daten zur Optimierung" → automatisierter Zugriffsschutz: OOS-Datensatz ist für den Optimierungs-Prozess technisch nicht lesbar, erst nach Freeze der Strategie freigeschaltet.
- "Kein automatischer Echtgeld-Einsatz" → jede Order in der Live-/Controlled-Test-Phase durchläuft einen expliziten Freigabeschritt durch den Nutzer; es gibt keinen Codepfad, der das umgeht (siehe Abschnitt 4, Abgrenzung von "Jarvis").
- Die 12-Punkte-Checkliste (Abschnitt 15) wird als **automatisierte CI-Gate-Pipeline** implementiert, nicht als Dokument, das ein Mensch/eine AI manuell durchgeht.

---

## 9. Backtesting Engine

**[v2] Wichtigste Änderung:** Nicht komplett neu bauen. Ein event-driven Backtest-Framework von Grund auf ist selbst ein Mehrmonatsprojekt und der fehleranfälligste Teil des Systems (Multi-Timeframe-Alignment ohne Leakage ist notorisch bug-anfällig — z. B. "sieht die 5m-Bar um 10:31 versehentlich die 1h-Bar, die erst um 11:00 abgeschlossen wird?").

Empfehlung: auf einem etablierten Framework aufsetzen, z. B. **Nautilus Trader** (unterstützt identischen Code-Pfad für Backtest und Live/Paper — erzwingt technisch das Prinzip aus Abschnitt 12, "keine getrennte Logik"). Alternativen: `backtrader`, `zipline-reloaded`. Vektorisierte Engines (`vectorbt`) sind schneller, aber bei Multi-Timeframe-Logik leakage-anfälliger — für dieses Projekt eher ungeeignet.

**Vorgehen:** Zuerst mit **synthetischen Testfällen mit bekanntem Ergebnis** verifizieren (z. B. eine konstruierte Strategie, deren korrektes P&L man von Hand berechnen kann), bevor echte historische Daten eingespielt werden. Das de-risked den kritischsten Systemteil früh, statt ihn erst nach der aufwändigen Dateningestion zu entdecken.

Getestete Metriken: Total/Annualized Return, Win Rate, Profit Factor, Sharpe, Sortino, Max Drawdown, Average Trade, Expectancy, Trade Count, Average Holding Time, Best/Worst Trade, Consecutive Losses — inklusive realistischer Gebühren, Spread, Slippage, Entry-/Exit-Ausführung.

**[v2] Slippage/Fees:** Nicht raten. Kalibrieren an echten Spread-/Volumendaten bzw. konservative feste Annahmen (z. B. 1–2 Ticks + Spread pro Seite) statt eines pauschalen Prozentsatzes.

---

## 10. Anti-Overfitting-System

In-Sample (Strategieentwicklung) → Validation (Parameteroptimierung) → Out-of-Sample (unbekannte Daten) → Forward Test (Daten, die erst nach Strategieentwicklung entstehen). Konkrete Aufteilung abhängig vom Datenbestand.

Ergänzt um **Walk-Forward Testing** (rollierendes Train→Test, um Regimewechsel-Robustheit zu prüfen) und **Monte-Carlo-Robustheitstests** (Trade-Resampling/-Shuffling, um die Verteilung möglicher Drawdowns zu schätzen — **[v2]** dieser Punkt wurde in v1 nur in der Architekturgrafik erwähnt, aber nie als eigene Methode beschrieben; hiermit nachgetragen).

**[v2] Sequenzierungs-Fix:** Strategy Factory und AI Strategy Generator werden **erst aktiviert, nachdem** 2–3 manuell codierte Strategien komplett durch die volle Pipeline (Backtest → OOS → Walk-Forward → Paper) gelaufen sind und die Pipeline selbst anhand der synthetischen Testfälle (Abschnitt 9) verifiziert wurde. Der Wert des automatisierten Strategie-Generators hängt vollständig davon ab, dass die Validierung bereits vertrauenswürdig ist — sonst automatisiert man das Erzeugen von Fehlschlüssen.

**[v2] Belegt durch Transkript `wYuP1QFZ0Bg`:** Die dort gezeigte Vorgehensweise ("auf kleinerem Datensatz optimieren, dann auf vollem Datensatz gegentesten") ist im Kern richtig, wurde dort aber **ad hoc durch iterative menschliche Rückmeldung an Claude** durchgeführt, nicht als vorab festgelegter, sauberer Split. Genau das ist das Risiko, das unsere eigene Regel "Claude darf OOS-Daten nicht zur Optimierung verwenden" verhindern soll (Abschnitt 8) — der Referenzfall zeigt, wie leicht das in der Praxis verwässert wird, wenn es nicht technisch erzwungen ist.

---

## 11. Regime Detection & Strategy Portfolio

Marktregime: Bull / Bear / Sideways / High Volatility / Low Volatility / Event Driven. Eine Strategie wird nur aktiviert, wenn sie zum aktuellen Regime passt (z. B. VWAP Momentum: aktiv im Bullmarkt, pausiert im Seitwärtsmarkt, reduzierte Positionsgröße bei hoher Volatilität).

Frage ist nicht "welche Strategie ist die beste", sondern "welche Strategien sind **jetzt** am besten geeignet" — Portfolio aus mehreren, möglichst unkorrelierten Strategien statt einer einzelnen.

---

## 12. Signal Engine, Scoring & Risk Engine

Signal-Ausgabe mit Entry/Stop/Target, Risk/Reward, Strategie, Marktregime, Relative Volume, Confidence.

**[v2] Wichtige Korrektur am Scoring:** v1 schlug feste Gewichte vor (Market Regime 20 Punkte, Trend 15, Momentum 15, …). Das widerspricht dem eigenen Leitprinzip: Ein handgestricktes Scoring-Schema ist genauso overfitting-anfällig wie eine handoptimierte Strategie, wirkt aber objektiv, weil es wie eine Formel aussieht. **Gewichte werden aus historischen, OOS-validierten Trade-Ergebnissen kalibriert** (z. B. logistische Regression Trade-Outcome vs. Features), nicht a priori festgelegt, und regelmäßig mit derselben Train/OOS-Disziplin wie Strategien selbst neu validiert.

**Risk Engine:** Fixer Risikoanteil pro Trade (Empfehlung 0,25–0,5 %, siehe Abschnitt 3), automatische Positionsgrößenberechnung, zusätzlich Max Daily Loss, Max Open Positions, Max Sector Exposure, Max Correlation Exposure, Max Consecutive Losses, Volatility Adjustment.

**[v2] Kill-Switch als Code, nicht als Regel:** Max Daily Loss muss ein hartes technisches Halt-Signal sein (Prozess stoppt automatisch alle neuen Trades bei Erreichen des Limits), nicht nur ein Parameter, den eine Strategie "beachten sollte". Ebenso: Circuit Breaker bei Datenfeed-/API-Fehlern.

---

## 13. Exit Engine

Jeder Trade braucht Stop Loss (ATR- oder Struktur-basiert) und Take Profit (Fixed R, Struktur, ATR, dynamisch). Trailing Stop nur, wenn Backtest **und** reale Ausführung zeigen, dass er handelbar ist.

**[v2] Konkreter Beleg:** Transkript `p-iQs2oRX6Q` (5-Min-Scalper mit echtem Geld): DaviddTech berichtet, dass er selbst durch zu enge Trailing-Stops Geld verloren hat, weil TradingView-Alerts zu langsam beim Broker ankamen und der reale Exit deutlich schlechter ausfiel als im Backtest angenommen (~16:13–16:50 im Transkript). Seine eigene Konsequenz: Stop-Loss wo möglich direkt an der Börse per Market-Order statt über Trailing-Logik in der Chart-Plattform. Für unsere Architektur heißt das: Exit-Logik gehört so nah wie möglich an die Order-Ausführung, nicht in eine externe Alert-Kette mit Latenz.

---

## 14. News & Earnings Filter, Paper Trading, Forward Testing

Vor jedem Trade: Prüfung auf Earnings, relevante News, ungewöhnliche Volatilität. Paper Trading nutzt **exakt dieselbe Logik** wie später live (keine getrennte "schöne" Backtest-Engine und andere Live-Logik — durchsetzbar z. B. durch Nautilus Trader, siehe Abschnitt 9).

Forward Testing über mehrere Wochen, idealerweise Monate, vor jedem Echtgeldeinsatz. **[v2]** Referenzwert aus Transkript `FbuYWdwA_wU`: DaviddTech testet dort typischerweise **mindestens 20 Trades bzw. ca. 3 Monate** Forward-Test, bevor eine Strategie überhaupt zur manuellen Freigabe ansteht.

---

## 15. Wichtigste Sicherheitsregel — die 12-Punkte-Checkliste

Eine Strategie gilt erst als "Candidate Strategy", wenn alle Punkte bestanden sind:

1. Kein Look-Ahead Bias? 2. Keine Daten-Leakage? 3. Keine Survivorship Bias? 4. Realistische Gebühren? 5. Realistische Slippage? 6. Realistische Ausführung? 7. Ausreichend Trades? 8. OOS positiv? 9. Walk-Forward stabil? 10. Monte-Carlo akzeptabel? 11. Verschiedene Marktregime getestet? 12. Paper Trading bestätigt die Ergebnisse?

**[v2]** Diese Liste wird als automatisierte Gate-Pipeline implementiert (siehe Abschnitt 8), die eine Strategie-Version blockiert, bis alle Punkte technisch nachgewiesen sind — nicht als Checkliste, die manuell "abgehakt" wird.

**[v2] Referenzbeleg für Punkt 7 (ausreichend Trades):** Transkript `p-iQs2oRX6Q` zeigt eine "100 %-Gewinnrate" auf Basis von **4 Trades in 2 Stunden** mit echtem Geld. DaviddTech kommentiert selbst richtig: Das ist trotz perfekter Trefferquote statistisch bedeutungslos und keine Basis für eine Live-Entscheidung.

---

## 16. Dashboard, Trade Detail View, Trade Journal, Strategy Versioning

Unverändert zu v1: Marktübersicht (SPY/QQQ/VIX), Top Signals, aktive Strategien, Portfolio-Kennzahlen; Trade Detail View mit nachvollziehbarer "Why this trade?"-Begründung statt bloßer Zahl; Trade Journal mit vollständigen Ausführungsdaten für spätere AI-Analyse; jede Strategie versioniert (Regeln, Parameter, Backtest, OOS, Walk-Forward, Änderungen, Performance).

---

## 17. Technische Architektur

| Bereich | Empfehlung | **[v2]** Anmerkung |
|---|---|---|
| Frontend | Vue 3 + TypeScript (oder React) | unverändert |
| Backend | Python + FastAPI | unverändert |
| Backtesting | **Nautilus Trader** (oder backtrader/zipline-reloaded) statt Eigenbau | siehe Abschnitt 9 |
| Datenbank | PostgreSQL, für Zeitreihen **TimescaleDB-Extension** empfohlen | TimescaleDB skaliert deutlich besser für Intraday-OHLCV-Volumen |
| Cache | Redis | unverändert |
| Background Jobs | Celery/Redis oder moderne Job-Queue | unverändert |
| Charts | TradingView Lightweight Charts | unverändert |
| Marktdaten | **Alpaca** (Start), **Polygon.io** ergänzend | siehe Abschnitt 3 |
| AI | Claude API, als Tool-Use gegen definierte Backtest-/Daten-API, nicht als freier Code-Ausführer gegen Live-Kapital | siehe Abschnitt 8 |
| Deployment | Docker, später Cloud/Monitoring/Logging/Secrets | unverändert |

---

## 18. MVP-Scope

**Enthält:** US-Aktien (statische Liste ~30 liquide Titel), 5m/15m/1h, Long only, Intraday only, 3–5 manuell codierte Strategien (Strategy Factory/AI-Generator erst danach), Backtesting mit Fees/Slippage auf etabliertem Framework, OOS, Walk-Forward, Risk Management inkl. hartem Kill-Switch, Signal Scoring (kalibriert, nicht geraten), Dashboard, Paper Trading mit identischer Live-Logik.

**Enthält NICHT:** automatische Echtgeldorders, komplexes Deep Learning, Hunderte Indikatoren, Crypto/Forex/Optionen/HFT, vollautomatisches Trading, dynamischer Scanner (kommt nach validierter Pipeline), Short-Selling.

---

## 19. Entwicklungsphasen (angepasste Reihenfolge)

**[v2]** Reihenfolge geändert: Backtest-Engine-Korrektheit wird **vor** umfangreicher Dateningestion verifiziert; Strategy Factory/AI-Generator läuft **nach** manueller End-to-End-Validierung.

| Phase | Inhalt | Ergebnis |
|---|---|---|
| 1. Research | Anforderungen, Trading Rules, Risiko-Modell, **Entscheidungen aus Abschnitt 3 inkl. PDT-Frage** | Verbindliche Spezifikation |
| 2. Backtest-Engine-Fundament **[v2 vorgezogen]** | Framework-Wahl, Aufbau mit synthetischen Testfällen, Point-in-Time-API | Nachweislich korrekte Engine, bevor echte Daten reinkommen |
| 3. Data Layer | Historische + Intraday-Daten, Corporate Actions, **historische Indexmitgliedschaft**, Data Quality Checks | Vertrauenswürdige Datenbasis |
| 4. Strategy Factory (manuell) **[v2 reduziert]** | 2–3 Strategien von Hand codiert | Erste End-to-End-Durchläufe |
| 5. Validation Engine | Train/Test-Split, OOS, Walk-Forward, Monte Carlo, Leakage-Detection als CI-Gate | Automatisierte 12-Punkte-Checkliste |
| 6. Signal Engine | Scanner (statische Liste zuerst), Signalgenerierung, kalibriertes Scoring, Entry/SL/TP/Size | Konkrete Signale |
| 7. AI Strategy Generator **[v2 nach hinten verschoben]** | Claude generiert weitere Strategien gegen die verifizierte Pipeline | Skalierte Strategie-Bibliothek |
| 8. Web-App | Dashboard, Charts, Signals, Trade Details, Journal | Nutzbares Frontend |
| 9. Paper Trading | Live-Daten, simulierte Ausführung mit identischer Logik | Realistische Performance-Daten |
| 10. Forward Testing | Mehrere Wochen/Monate, kein Echtgeld | Bestätigung der OOS-Ergebnisse |
| 11. Controlled Live Test | Erst nach Klärung PDT/Kontogröße, sehr kleines Kapital | Validierung unter echten Marktbedingungen |

Jede Phase endet mit: Implement → Test → Validate → Document → Report → **Freigabe abwarten**, bevor die nächste Phase beginnt.

---

## 20. Master-Prompt-Grundgerüst für Claude Code

Einstieg nicht als "Build me a trading bot", sondern:

> *"You are the lead quantitative developer responsible for building a research-grade short-term equity trading platform. Your first objective is not maximum backtested profit. Your first objective is producing statistically credible, executable and robust trading signals."*

Danach vollständige Spezifikation aus diesem Dokument, phasenweise Implementierung mit Freigabeschritt nach jeder Phase (Abschnitt 19), plus explizite technische Guardrails aus Abschnitt 8.

---

## Änderungsprotokoll v1 → v2

Alle mit **[v2]** markierten Abschnitte wurden ergänzt oder korrigiert auf Basis von: (a) einer strukturierten Kritik der ursprünglichen Roadmap (Survivorship Bias, PDT-Regel, Backtest-Engine-Risiko, Look-Ahead-Durchsetzung, Scoring-Kalibrierung statt Ratens, Sequenzierung Strategy Factory nach Pipeline-Validierung) und (b) der Analyse der vier Transkripte in `/transkript` (Tool-Stack-Realität der Referenzquelle, Crypto- statt Aktien-Fokus, drei konkrete Overfitting-Fallbeispiele, TradingView-Tick-Daten-Limitation, Widerspruch zwischen gepredigter Disziplin und demonstriertem autonomem Live-Handel mit echtem Kapital).
