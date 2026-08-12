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
2. **Statisches Universum ist eine Beispielliste**, keine vom Nutzer geprüfte oder empfohlene Auswahl — siehe Docstring in `scanner.py`. Kein dynamischer Scanner (Liquidität, Relative-Volume-Filter über den ganzen Markt) im MVP-Scope, passend zu `DECISIONS.md`.
3. **Kein Marktregime im Signal.** Die ursprüngliche Roadmap sieht Regime Detection (Bull/Bear/Sideways/High-Vol) als eigenen Baustein vor; das wurde nicht in Phase 6 gezogen, da es weder in der Phasenbeschreibung noch in den aktuellen Daten (kein SPY/QQQ/VIX-Zugriff) angelegt ist. Bleibt eine offene Lücke für eine spätere Phase.
4. **`build_signal()` ist long-only**, passend zu `DECISIONS.md` #3.
