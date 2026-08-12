# Verbindliche Entscheidungen

Festgehalten aus `ROADMAP.md`, Abschnitt 3, als Grundlage für die Implementierung. Änderungen an diesen Punkten sind möglich, aber müssen hier aktualisiert und begründet werden — Code und Dokumentation orientieren sich an diesem Stand.

| # | Frage | Entscheidung | Stand |
|---|---|---|---|
| 1 | Aktienuniversum | Statische Liste ~30 liquide US-Large-Caps für MVP, kein Live-Scanner in v1 | festgelegt |
| 2 | Haltedauer | 30 Min – wenige Stunden, Exit spätestens Handelsende (Intraday) | festgelegt |
| 3 | Long/Short | Long only für MVP | festgelegt |
| 4 | Datenanbieter | Alpaca (Start), Polygon.io ergänzend | festgelegt |
| 5 | Risiko pro Trade | 0,25–0,5 % des simulierten Kontos | festgelegt |
| 6 | PDT-Regel / Kontogröße | **offen** — muss vor Phase 11 (Controlled Live Test) mit dem Nutzer geklärt werden | **offen** |

## Weitere technische Festlegungen (ROADMAP.md Abschnitt 17)

- Backend: Python + FastAPI
- Backtesting-Framework: Nautilus Trader 1.231.0, **Installierbarkeit auf GitHub Actions (ubuntu-latest/Python 3.12) verifiziert am 12.08.2026** — siehe `PHASE2_NOTES.md`. Noch nicht als harte Abhängigkeit eingebunden, da noch kein Code darauf aufbaut (folgt Phase 3/4).
- Datenbank: PostgreSQL + TimescaleDB-Extension für Zeitreihen
- Cache/Queue: Redis, Celery
- Frontend: Vue 3 + TypeScript
- Charts: TradingView Lightweight Charts
- Deployment: Docker

## Nicht-Ziele des MVP

Keine automatischen Echtgeldorders, kein Deep Learning, kein dynamischer Scanner, kein Short-Selling, kein Crypto/Forex/Optionen/HFT, keine vollautomatische Kapitalsteuerung durch die KI (siehe `ROADMAP.md` Abschnitt 8).
