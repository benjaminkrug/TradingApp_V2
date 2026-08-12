# Phase 4 — Strategy Factory (manuell): Status & offene Punkte

Referenz: `ROADMAP.md` Abschnitt 8 und 19 ("2-3 Strategien von Hand codiert, komplett durch die Pipeline gelaufen, bevor der AI-Strategy-Generator aktiviert wird").

## Was fertig ist und getestet wurde (21 neue Tests, 71 insgesamt)

- **`app/features/indicators.py`** — kausale Indikatoren (SMA, EMA, ATR, Session-VWAP, Opening Range), ausschließlich die drei tatsächlich von den Strategien benötigten, keine allgemeine TA-Bibliothek. Alle Werte gegen Handrechnung geprüft (z. B. EMA-Seed-Berechnung, ATR-True-Range).
- **Drei Strategien aus ROADMAP.md Abschnitt 8**, alle als reine Funktionen von `cursor.history` implementiert (kein interner Positions-Zustand, siehe `app/strategies/base.py`):
  - `VwapMomentumStrategy` (Strategie A)
  - `EmaPullbackStrategy` (Strategie C)
  - `OpeningRangeBreakoutStrategy` (Strategie B)
- Jede Strategie: isolierte Signal-Tests mit konstruierten, nachvollziehbaren Kursverläufen **und** ein End-to-End-Lauf durch `run_reference_backtest` mit exakt nachgerechnetem Fill-Preis/PnL — das ist die in Abschnitt 19 geforderte "Erste End-to-End-Durchführung".

## Zwei echte Fehler gefunden und behoben (nicht nur dokumentiert)

1. **Opening-Range-Breakout hatte einen Logikfehler:** Auf der letzten Bar, die die Opening Range selbst definiert, wurde bereits ein SELL-Signal ausgelöst — weil ihr eigener Schlusskurs fast immer ≤ eine Range-High ist, die teilweise aus ihrem eigenen Hoch berechnet wurde. Kein Look-Ahead-Fehler (keine Zukunftsdaten beteiligt), aber ein bedeutungsloses Signal. Fix: Die Strategie wertet erst ab der ersten Bar *nach* Abschluss der Opening-Range-Bildung.
2. **Ein eigener Test unterstellte einen profitablen VWAP-Momentum-Trade, ohne ihn nachzurechnen** — der Test schlug prompt fehl (tatsächliches Ergebnis: −12,5 statt "profitabel"). Grund, nicht wegdiskutiert: VWAP ist ein nachlaufender, kumulativer Indikator; das SELL-Signal feuert erst mehrere Bars nach Beginn eines Crashs. Der Test wurde korrigiert, um das tatsächliche (negative) Ergebnis exakt zu prüfen, statt die Erwartung stillschweigend anzupassen.

## Bewusste Design-Entscheidung: keine interne Positions-Verfolgung in Strategien

Strategien könnten versuchen, selbst zu verfolgen, ob sie "gerade in einer Position sind" (z. B. um Exit-Logik anders zu gestalten). Das würde riskieren, mit dem tatsächlichen Fill-Status der Engine auseinanderzulaufen (z. B. wenn ein BUY-Signal wegen bereits offener Position ignoriert wird, siehe `reference_engine.py`). Stattdessen sind alle drei Strategien rein reaktiv auf Preisverhalten — Entry- und Exit-Bedingungen sind beide unabhängig von einer angenommenen Positions-Historie formuliert. Die Engine bleibt alleinige Quelle der Wahrheit für den Positionsstatus.

## Was noch offen ist

1. **Kein echtes Backtesting gegen reale Marktdaten.** Alpaca/Polygon sind weiterhin unverifizierte Stubs (Phase 3). Alle Tests hier laufen gegen konstruierte, synthetische Kursverläufe — ehrlich so benannt, nicht als "Backtest-Ergebnis" verkauft.
2. **Kein Stop-Loss/Take-Profit als eigene Exit-Mechanik.** Die Referenz-Engine kennt nur BUY/SELL/HOLD-Signale, keine intrabar-Stop-Überwachung. Das gehört laut ROADMAP.md in die Risk-/Exit-Engine (Phase 6), nicht in Phase 4 — hier ging es um Entry/Exit-*Logik*, nicht um Risikomanagement.
3. **`ema_series` ist O(n) pro Aufruf, O(n²) über einen ganzen Backtest** — für die kleinen, handverifizierten Testfälle hier unproblematisch, aber vor einem echten Mehrtausend-Bar-Backtest zu optimieren (inkrementelle Indikator-Zustände), sobald Nautilus Trader eingebunden wird.
4. **Nur 3 Indikatoren, nur 3 Strategien** — bewusst nicht mehr gebaut als für diese Phase gebraucht (kein RSI, kein MACD, keine weiteren Strategien aus Abschnitt 8). Kommt bei Bedarf in späteren Phasen.
