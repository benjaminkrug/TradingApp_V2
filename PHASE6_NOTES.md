# Phase 6 — Signal Engine: Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 12, 13, 16, 17, 19, 23.

## Was fertig ist und getestet wurde (32 neue Tests, 140 insgesamt)

- **`app/features/indicators.py`** — `relative_volume` ergänzt (aktuelle Bar-Volumen ./. Durchschnitt der vorherigen `lookback` Bars, aktuelle Bar bewusst ausgeschlossen aus ihrem eigenen Durchschnitt).
- **`app/signals/risk.py`** — ATR-Stop, Risk/Reward-Target, Positionsgröße (Formel gegen das Rechenbeispiel aus ROADMAP.md Abschnitt 13 exakt verifiziert: 50.000 Konto, 0,5 % Risiko, Entry 100, Stop 98 → 125 Stück), und `DailyLossGuard` als echter Kill-Switch-Code (ROADMAP Abschnitt 12).
- **`app/signals/scoring.py`** — reine-Python-Logistic-Regression (Gradientenverfahren, kein NumPy/scikit-learn nötig) zur Kalibrierung von Signal-Scores aus historischen Trade-Ergebnissen. Getestet an einem linear trennbaren Datensatz (korrekte Trennung nachgewiesen, nicht nur behauptet).
- **`app/signals/signal.py`** — `build_signal()`: fasst Strategie-Entscheidung, ATR-Stop/Target, Positionsgröße, Relative Volume und optionale Score-Kalibrierung zu einem `Signal` mit `rationale`-Liste zusammen (ROADMAP Abschnitt 23: nie eine Zahl ohne Begründung zeigen).
- **`app/signals/scanner.py`** — statische MVP-Universumsliste (DECISIONS.md #1), keine Live-Scanner-Logik.

## Wichtiger Fund während der Entwicklung: `DailyLossGuard` war zunächst nicht "sticky"

Der erste Entwurf berechnete `can_trade()` live aus dem laufenden kumulierten PnL. Das bedeutet: Ein großer Gewinn *nach* dem Auslösen des Tageslimits hätte den Kill-Switch stillschweigend wieder freigeschaltet — genau das Gegenteil dessen, was ein hartes Tageslimit leisten soll ("für heute ist Schluss", nicht "bis der Saldo wieder besser aussieht"). Beim Formulieren eines Tests dafür ist der Fehler aufgefallen. Fix: `DailyLossGuard` merkt sich jetzt einen `_tripped`-Zustand, der nur durch explizites `reset()` aufgehoben wird — mit Regressionstest, der genau dieses Szenario prüft.

## Bewusste Design-Entscheidung: kein erfundener Score ohne echte Kalibrierungsdaten

`build_signal()` liefert `score=None` und `confidence="UNCALIBRATED"`, wenn kein `CalibratedModel` übergeben wird — **nicht** einen plausibel aussehenden Platzhalterwert. Grund: Es gibt noch keine echten, OOS-validierten historischen Trade-Ergebnisse (keine Live-Marktdaten, siehe `PHASE3_NOTES.md`), aus denen sich ehrlich kalibrieren ließe. Ein erfundener Score wäre exakt der Fehler, den ROADMAP.md Abschnitt 16 explizit korrigiert (die ursprüngliche, handgestrickte Punktetabelle aus der ersten Roadmap-Fassung).

## Was noch offen ist

1. **Kein echtes Kalibrierungs-Dataset.** Sobald Phase 9 (Paper Trading) reale, realisierte Trades mit Ergebnis liefert, kann `fit_logistic_regression()` erstmals sinnvoll auf echten Daten laufen statt nur auf synthetischen Testfällen.
2. **Statisches Universum ist eine Beispielliste**, keine vom Nutzer geprüfte oder empfohlene Auswahl — siehe Docstring in `scanner.py` und die Korrektur in `DECISIONS.md` #1 (nur die *Form* der Entscheidung war bestätigt, nicht die konkreten 30 Ticker). Kein dynamischer Scanner (Liquidität, Relative-Volume-Filter über den ganzen Markt) im MVP-Scope, passend zu `DECISIONS.md`.
3. **Kein Marktregime im Signal.** Die ursprüngliche Roadmap sieht Regime Detection (Bull/Bear/Sideways/High-Vol) als eigenen Baustein vor; das wurde nicht in Phase 6 gezogen, da es weder in der Phasenbeschreibung noch in den aktuellen Daten (kein SPY/QQQ/VIX-Zugriff) angelegt ist. Bleibt eine offene Lücke für eine spätere Phase.
4. **`build_signal()` ist long-only**, passend zu `DECISIONS.md` #3.

## Update 12.08.2026: kritische Nachprüfung — zwei weitere Funde, behoben

1. **`fit_logistic_regression` hatte keine Regularisierung.** Auf einem kleinen, (nahezu) trennbaren Datensatz — genau die Größenordnung, in der dieses System realistisch kalibrieren wird, 30–50 Trades — divergieren die Gewichte bei unregularisierter Gradientenabstiegs-Logistic-Regression, statt zu konvergieren: In einem konkreten Test wuchs ein Gewicht von 13,8 nach 5.000 Iterationen auf 17,4 nach 20.000 Iterationen weiter an, ohne sich zu stabilisieren. Das hätte zu übermäßig selbstsicheren Scores (nahe 0 oder 100) führen können — ironischerweise genau die Art Overfitting, die dieses Modul eigentlich ersetzen soll (handgestrickte, überangepasste Gewichte). Fix: L2-Regularisierung mit konservativem Default (`l2_penalty=0.1`), verifiziert, dass die Gewichte jetzt unabhängig von der Iterationszahl konvergieren, während die korrekte Klassentrennung erhalten bleibt.
2. **`entry` in `build_signal()` nutzt den aktuellen Schlusskurs, nicht den nächsten Open** wie `reference_engine`'s Backtest-Ausführungsmodell (die in Phase 2 explizit korrigierte Konvention). Das ist inhaltlich richtig — ein Live-Signal für einen Menschen kann per Definition keinen "nächsten Balken" kennen, "letzter Preis" als Referenz ist Standardpraxis —, aber der Unterschied war bisher unbegründet im Code. Jetzt im Docstring explizit klargestellt, warum das kein Rückfall in den in Phase 2 behobenen Fehler ist und warum ein Backtest von `Signal`-Verbrauchern trotzdem weiterhin über `reference_engine`s Konvention laufen muss, nicht über `build_signal()`s Referenzpreis.

8 neue/angepasste Tests für diese Funde (siehe auch `PHASE5_NOTES.md`), alle 148 Tests der Gesamt-Suite laufen grün.
